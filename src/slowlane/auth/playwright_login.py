"""Playwright-based interactive login flow for Apple ID authentication."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlsplit

from slowlane.auth.session_auth import REQUIRED_SESSION_COOKIES
from slowlane.core.errors import SessionError
from slowlane.core.secrets import SessionData, hash_email

logger = logging.getLogger(__name__)


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
    TRUSTED_LOGIN_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {
            "appleid.apple.com",
            "appstoreconnect.apple.com",
            "developer.apple.com",
            "idmsa.apple.com",
        }
    )

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
                'Install it with: pip install "slowlane[interactive]" '
                "&& playwright install chromium"
            ) from exc

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless)
                try:
                    context = await browser.new_context()
                    page = await context.new_page()

                    await page.goto(self._target_url)
                    await self._wait_for_login_completion(page, context)

                    all_cookies = await context.cookies()
                    cookies_dict: dict[str, str] = {}
                    for cookie in all_cookies:
                        if cookie["name"] in self.TARGET_COOKIES or cookie["name"].startswith(
                            "myac"
                        ):
                            cookies_dict[cookie["name"]] = cookie["value"]

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
        except Exception as exc:
            detail = str(exc) or type(exc).__name__
            return PlaywrightLoginResult(
                success=False,
                cookies={},
                email="",
                error_message=f"Login flow failed: {detail}",
            )

    @staticmethod
    def _parse_trusted_url(url: str) -> tuple[str, str] | None:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except TypeError, ValueError:
            return None

        if (
            parsed.scheme != "https"
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None

        if parsed.hostname not in PlaywrightLoginFlow.TRUSTED_LOGIN_HOSTS:
            return None

        return parsed.hostname, parsed.path

    @classmethod
    def _is_login_complete_url(cls, url: str) -> bool:
        parsed = cls._parse_trusted_url(url)
        if parsed is None:
            return False

        hostname, path = parsed

        if hostname == "appstoreconnect.apple.com":
            return True

        return hostname == "developer.apple.com" and (
            path in ("/account", "/account/") or path.startswith("/account/")
        )

    async def _wait_for_login_completion(self, page: Any, context: Any) -> None:
        """Wait for the login to complete."""

        async def check_cookies() -> bool:
            if not self._is_login_complete_url(page.url):
                return False
            cookies = await context.cookies()
            cookie_names = {cookie["name"] for cookie in cookies}
            return all(name in cookie_names for name in REQUIRED_SESSION_COOKIES)

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        timeout_seconds = self.LOGIN_TIMEOUT_MS / 1000

        while True:
            elapsed = loop.time() - start_time
            if elapsed > timeout_seconds:
                raise SessionError("Login timed out after 5 minutes")

            if await check_cookies():
                return

            await asyncio.sleep(0.5)

    async def _extract_email(self, page: Any) -> str:
        """Try to extract logged-in email from the page."""
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
                        return str(text).strip()
            except Exception as exc:
                logger.debug("Could not read email selector %s: %s", selector, exc)
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
