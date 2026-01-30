"""Playwright-based interactive login flow for Apple ID authentication."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from slowlane.core.errors import SessionError
from slowlane.core.secrets import SessionData, hash_email


@dataclass
class PlaywrightLoginResult:
    """Result from Playwright login flow."""

    success: bool
    cookies: dict[str, str]
    email: str
    error_message: str | None = None


class PlaywrightLoginFlow:
    """Interactive browser-based login flow using Playwright.

    Opens a Chromium browser for the user to complete Apple ID login
    including 2FA, then extracts cookies for session auth.
    """

    APPLE_ID_URL = "https://appleid.apple.com/auth/authorize"
    APPSTORE_CONNECT_URL = "https://appstoreconnect.apple.com"
    DEVELOPER_PORTAL_URL = "https://developer.apple.com/account"

    # Cookies we need to extract
    TARGET_COOKIES: ClassVar[list[str]] = ["myacinfo", "DES", "dqsid", "itctx", "itcdq"]

    # Timeout for login flow (5 minutes)
    LOGIN_TIMEOUT_MS = 5 * 60 * 1000

    def __init__(
        self,
        headless: bool = False,
        target_url: str | None = None,
    ) -> None:
        """Initialize login flow.

        Args:
            headless: Run browser in headless mode (not recommended for 2FA)
            target_url: URL to navigate to after login (default: App Store Connect)
        """
        self._headless = headless
        self._target_url = target_url or self.APPSTORE_CONNECT_URL

    async def run_async(self) -> PlaywrightLoginResult:
        """Run the login flow asynchronously."""
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise SessionError(
                "Playwright is required for interactive login. "
                "Install it with: pip install playwright && playwright install chromium"
            ) from exc

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Navigate to App Store Connect (will redirect to Apple ID login)
                await page.goto(self._target_url)

                # Wait for user to complete login (detected by reaching target or timeout)
                try:
                    # Wait for either successful login or specific cookies
                    await self._wait_for_login_completion(page, context)
                except Exception as e:
                    return PlaywrightLoginResult(
                        success=False,
                        cookies={},
                        email="",
                        error_message=f"Login flow failed: {e}",
                    )

                # Extract cookies
                all_cookies = await context.cookies()
                cookies_dict: dict[str, str] = {}
                for cookie in all_cookies:
                    if cookie["name"] in self.TARGET_COOKIES or cookie["name"].startswith("myac"):
                        cookies_dict[cookie["name"]] = cookie["value"]

                # Try to extract email
                email = await self._extract_email(page)

                if not cookies_dict.get("myacinfo"):
                    return PlaywrightLoginResult(
                        success=False,
                        cookies=cookies_dict,
                        email=email,
                        error_message="Login completed but required cookies not found",
                    )

                return PlaywrightLoginResult(
                    success=True,
                    cookies=cookies_dict,
                    email=email,
                )

            finally:
                await browser.close()

    async def _wait_for_login_completion(self, page: Any, context: Any) -> None:
        """Wait for the login to complete."""
        # We consider login complete when:
        # 1. URL contains appstoreconnect.apple.com or developer.apple.com
        # 2. OR we have the myacinfo cookie

        def check_url() -> bool:
            url = page.url
            return (
                "appstoreconnect.apple.com" in url
                or "developer.apple.com/account" in url
            ) and "auth" not in url

        async def check_cookies() -> bool:
            cookies = await context.cookies()
            return any(cookie["name"] == "myacinfo" for cookie in cookies)

        # Poll for completion
        start_time = asyncio.get_event_loop().time()
        timeout_seconds = self.LOGIN_TIMEOUT_MS / 1000

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                raise SessionError("Login timed out after 5 minutes")

            if check_url() or await check_cookies():
                # Give it a moment for all cookies to be set
                await asyncio.sleep(1)
                return

            await asyncio.sleep(0.5)

    async def _extract_email(self, page: Any) -> str:
        """Try to extract logged-in email from the page."""
        try:
            # Try to find email in common locations
            selectors = [
                '[data-test-id="account-email"]',
                ".account-email",
                ".user-email",
            ]
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if "@" in text:
                            return text.strip()
                except Exception:
                    pass
        except Exception:
            pass
        return ""

    def run(self) -> PlaywrightLoginResult:
        """Run the login flow synchronously."""
        return asyncio.run(self.run_async())


def interactive_login(
    headless: bool = False,
    target_service: str = "appstoreconnect",
) -> SessionData:
    """Perform interactive login and return session data.

    Args:
        headless: Run browser in headless mode (not recommended)
        target_service: "appstoreconnect" or "developer"

    Returns:
        SessionData with extracted cookies

    Raises:
        SessionError: If login fails
    """
    if target_service == "developer":
        target_url = PlaywrightLoginFlow.DEVELOPER_PORTAL_URL
    else:
        target_url = PlaywrightLoginFlow.APPSTORE_CONNECT_URL

    flow = PlaywrightLoginFlow(headless=headless, target_url=target_url)
    result = flow.run()

    if not result.success:
        raise SessionError(result.error_message or "Login failed")

    return SessionData(
        cookies=result.cookies,
        email_hash=hash_email(result.email) if result.email else "unknown",
        created_at=datetime.now(UTC),
        target_service=target_service,
    )
