"""Tests for the Playwright login flow."""

from __future__ import annotations

import builtins
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slowlane.auth.playwright_login import PlaywrightLoginFlow
from slowlane.core.errors import SessionError


def _playwright_manager(playwright: MagicMock) -> MagicMock:
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=playwright)
    manager.__aexit__ = AsyncMock(return_value=None)
    return manager


class TestLoginCompletionUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://appstoreconnect.apple.com",
            "https://appstoreconnect.apple.com/apps",
            "https://appstoreconnect.apple.com:443/apps",
            "https://developer.apple.com/account",
            "https://developer.apple.com/account/resources",
        ],
    )
    def test_accepts_exact_apple_hosts(self, url: str) -> None:
        assert PlaywrightLoginFlow._is_login_complete_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://appstoreconnect.apple.com",
            "https://appstoreconnect.apple.com.example.com",
            "https://example.com/?next=appstoreconnect.apple.com",
            "https://developer.apple.com.example.com/account",
            "https://developer.apple.com/support",
            "https://user@appstoreconnect.apple.com",
            "https://appstoreconnect.apple.com:8443",
            "https://appstoreconnect.apple.com:not-a-port",
        ],
    )
    def test_rejects_untrusted_or_malformed_urls(self, url: str) -> None:
        assert not PlaywrightLoginFlow._is_login_complete_url(url)


class TestPlaywrightLoginFlow:
    async def test_email_extraction_tolerates_unavailable_selectors(self) -> None:
        page = MagicMock()
        page.query_selector = AsyncMock(side_effect=RuntimeError("selector unavailable"))

        email = await PlaywrightLoginFlow()._extract_email(page)

        assert email == ""
        assert page.query_selector.await_count == 3

    async def test_wait_uses_running_loop(self) -> None:
        flow = PlaywrightLoginFlow()
        page = MagicMock()
        page.url = "https://appstoreconnect.apple.com/apps"
        context = MagicMock()
        context.cookies = AsyncMock(return_value=[{"name": "myacinfo"}, {"name": "DES"}])

        with (
            patch("asyncio.get_event_loop", side_effect=AssertionError("legacy loop lookup")),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            await flow._wait_for_login_completion(page, context)

    async def test_waits_for_all_required_cookies(self) -> None:
        flow = PlaywrightLoginFlow()
        page = MagicMock()
        page.url = "https://appstoreconnect.apple.com/apps"
        context = MagicMock()
        context.cookies = AsyncMock(
            side_effect=[
                [{"name": "myacinfo"}],
                [{"name": "myacinfo"}, {"name": "DES"}],
            ]
        )

        with patch("asyncio.sleep", new=AsyncMock()):
            await flow._wait_for_login_completion(page, context)

        assert context.cookies.await_count == 2

    async def test_cookie_does_not_complete_login_on_untrusted_host(self) -> None:
        flow = PlaywrightLoginFlow()
        flow.LOGIN_TIMEOUT_MS = 500
        page = MagicMock()
        page.url = "https://example.com/?next=appstoreconnect.apple.com"
        context = MagicMock()
        context.cookies = AsyncMock(return_value=[{"name": "myacinfo"}])
        loop = MagicMock()
        loop.time.side_effect = [0.0, 0.0, 1.0]

        with (
            patch("asyncio.get_running_loop", return_value=loop),
            patch("asyncio.sleep", new=AsyncMock()),
            pytest.raises(SessionError, match="timed out"),
        ):
            await flow._wait_for_login_completion(page, context)

        context.cookies.assert_not_awaited()

    async def test_browser_launch_failure_returns_failed_result(self) -> None:
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(side_effect=RuntimeError("browser unavailable"))

        with patch(
            "playwright.async_api.async_playwright",
            return_value=_playwright_manager(playwright),
        ):
            result = await PlaywrightLoginFlow().run_async()

        assert not result.success
        assert result.error_message == "Login flow failed: browser unavailable"

    async def test_navigation_failure_returns_failed_result_and_closes_browser(self) -> None:
        page = MagicMock()
        page.goto = AsyncMock(side_effect=RuntimeError("navigation failed"))
        context = MagicMock()
        context.new_page = AsyncMock(return_value=page)
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)

        with patch(
            "playwright.async_api.async_playwright",
            return_value=_playwright_manager(playwright),
        ):
            result = await PlaywrightLoginFlow().run_async()

        assert not result.success
        assert result.error_message == "Login flow failed: navigation failed"
        browser.close.assert_awaited_once_with()

    async def test_missing_dependency_mentions_interactive_extra(self) -> None:
        original_import = builtins.__import__

        def import_module(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            if name == "playwright.async_api":
                raise ImportError("missing playwright")
            return original_import(name, globals, locals, fromlist, level)

        with (
            patch("builtins.__import__", side_effect=import_module),
            pytest.raises(SessionError, match=r"slowlane\[interactive\]"),
        ):
            await PlaywrightLoginFlow().run_async()
