"""HTTP client with retries, backoff, and cookie handling."""

from __future__ import annotations

import logging
import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from slowlane import __version__

from .config import HttpConfig
from .errors import (
    AccessDeniedError,
    AppleFlowChangedError,
    AuthExpiredError,
    NetworkError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

MAX_RETRY_AFTER_SECONDS = 60 * 60

# Patterns for redacting secrets in logs
SECRET_PATTERNS = [
    re.compile(r"(Authorization:\s*Bearer\s+)[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
    re.compile(r'(password["\']?\s*[:=]\s*["\']?)[^"\'&\s]+'),
    re.compile(r"(X-Apple-ID-Session-Id:\s*)[^\s]+"),
    re.compile(r"(scnt:\s*)[^\s]+"),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive information from text."""
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(r"\1[REDACTED]", result)
    return result


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        seconds = int(value.strip())
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except TypeError, ValueError, OverflowError:
            return None

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        seconds = math.ceil((retry_at - datetime.now(UTC)).total_seconds())

    return min(max(seconds, 0), MAX_RETRY_AFTER_SECONDS)


class AppleHTTPClient:
    """HTTP client configured for Apple APIs with retry and error handling."""

    ASC_API_BASE = "https://api.appstoreconnect.apple.com/v1"
    APPLE_AUTH_BASE = "https://idmsa.apple.com"
    DEVELOPER_PORTAL_BASE = "https://developer.apple.com"
    SESSION_AUTH_HOSTS = frozenset(
        {
            "appleid.apple.com",
            "appstoreconnect.apple.com",
            "developer.apple.com",
            "idmsa.apple.com",
        }
    )
    RETRYABLE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(
        self,
        config: HttpConfig | None = None,
        jwt_token: str | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self._config = config or HttpConfig()
        self._jwt_token = jwt_token
        self._jwt_token_provider: Callable[[], str] | None = None
        self._cookies = dict(cookies or {})

        self._client = httpx.Client(
            timeout=httpx.Timeout(self._config.timeout),
            follow_redirects=False,
        )
        self._install_session_cookies()

    def _install_session_cookies(self) -> None:
        self._client.cookies.clear()
        for hostname in self.SESSION_AUTH_HOSTS:
            for name, value in self._cookies.items():
                self._client.cookies.set(name, value, domain=hostname, path="/")

    def set_jwt_token(self, token: str) -> None:
        """Set JWT token for authentication."""
        self._jwt_token = token

    def set_jwt_token_provider(self, provider: Callable[[], str]) -> None:
        """Refresh the JWT before each request attempt."""
        self._jwt_token_provider = provider

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """Set cookies for session authentication."""
        self._cookies = dict(cookies)
        self._install_session_cookies()

    @staticmethod
    def _parse_https_target(url: str) -> tuple[str, str] | None:
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
            or parsed.hostname is None
        ):
            return None
        return parsed.hostname, parsed.path

    def _get_headers(
        self,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build request headers."""
        headers: dict[str, str] = {
            "User-Agent": f"slowlane/{__version__}",
            "Accept": "application/json",
        }

        target = self._parse_https_target(url)
        if self._jwt_token and target is not None:
            hostname, path = target
            trusted_jwt_target = hostname == "api.appstoreconnect.apple.com" and (
                path == "/v1" or path.startswith("/v1/")
            )
        else:
            trusted_jwt_target = False

        if self._jwt_token and trusted_jwt_target:
            headers["Authorization"] = f"Bearer {self._jwt_token}"

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def _classify_error(self, response: httpx.Response) -> None:
        """Classify HTTP errors and raise appropriate exceptions."""
        status = response.status_code

        if status == 401:
            raise AuthExpiredError("Authentication failed or expired", status_code=status)

        if status == 403:
            try:
                data = response.json()
            except Exception as e:
                logger.debug("Could not parse error body: %s", e)
            else:
                errors = data.get("errors", []) if isinstance(data, dict) else []
                if errors and "authentication" in str(errors).lower():
                    raise AuthExpiredError("Authentication required", status_code=status)
                details = [
                    str(error.get("detail") or error.get("title"))
                    for error in errors
                    if isinstance(error, dict) and (error.get("detail") or error.get("title"))
                ]
                if details:
                    raise AccessDeniedError("; ".join(details), status_code=status)
            raise AccessDeniedError("Access forbidden", status_code=status)

        if status == 429:
            retry_seconds = _parse_retry_after(response.headers.get("Retry-After"))
            if retry_seconds is None:
                retry_seconds = 60
            raise RateLimitError("Rate limit exceeded", retry_after=retry_seconds)

        if status >= 500:
            raise NetworkError(f"Server error: {status}", status_code=status)

        if status >= 400:
            try:
                data = response.json()
                errors = data.get("errors", [])
                if errors:
                    error_detail = "; ".join(
                        e.get("detail", e.get("title", str(e))) for e in errors
                    )
                    raise AppleFlowChangedError(f"API error: {error_detail}", status_code=status)
            except AppleFlowChangedError:
                raise
            except Exception as e:
                logger.debug("Could not parse error body: %s", e)

            raise AppleFlowChangedError(
                f"Apple API request failed with HTTP {status}", status_code=status
            )

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with exponential backoff retry."""
        target = self._parse_https_target(url)
        if self._cookies and (target is None or target[0] not in self.SESSION_AUTH_HOSTS):
            raise AppleFlowChangedError("Refusing to send an Apple session to an untrusted URL")
        if self._jwt_token or self._jwt_token_provider:
            trusted_jwt_target = False
            if target is not None:
                hostname, path = target
                trusted_jwt_target = hostname == "api.appstoreconnect.apple.com" and (
                    path == "/v1" or path.startswith("/v1/")
                )
            if not trusted_jwt_target:
                raise AppleFlowChangedError(
                    "Refusing to send App Store Connect credentials to an untrusted URL"
                )

        extra_headers = kwargs.pop("headers", None)
        retryable = method.upper() in self.RETRYABLE_METHODS

        last_exception: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                if self._jwt_token_provider is not None:
                    self._jwt_token = self._jwt_token_provider()
                kwargs["headers"] = self._get_headers(url, extra_headers)
                kwargs["follow_redirects"] = False

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Request: %s %s (attempt %d)",
                        method,
                        url,
                        attempt + 1,
                    )

                response = self._client.request(method, url, **kwargs)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Response: %d %s",
                        response.status_code,
                        redact_secrets(response.text[:200] if response.text else ""),
                    )

                if 300 <= response.status_code < 400:
                    if self._cookies:
                        raise AuthExpiredError(
                            "Authentication redirected; the Apple session may be expired",
                            status_code=response.status_code,
                        )
                    raise AppleFlowChangedError(
                        "Apple API returned an unexpected redirect",
                        status_code=response.status_code,
                    )

                if response.status_code < 400:
                    return response

                self._classify_error(response)
                return response

            except RateLimitError as e:
                last_exception = e
                wait_time = (
                    e.retry_after
                    if e.retry_after is not None
                    else self._config.backoff_factor * (2**attempt)
                )
                if retryable and attempt < self._config.max_retries:
                    logger.warning("Rate limited, waiting %d seconds...", wait_time)
                    time.sleep(wait_time)
                    continue
                raise

            except NetworkError as e:
                last_exception = e
                if retryable and attempt < self._config.max_retries:
                    wait_time = max(0.0, self._config.backoff_factor * (2**attempt))
                    logger.warning("Server error, retrying in %.1f seconds...", wait_time)
                    time.sleep(wait_time)
                    continue
                raise

            except httpx.TimeoutException as e:
                last_exception = NetworkError(f"Request timeout: {e}")
                if retryable and attempt < self._config.max_retries:
                    wait_time = self._config.backoff_factor * (2**attempt)
                    logger.warning("Timeout, retrying in %.1f seconds...", wait_time)
                    time.sleep(wait_time)
                    continue
                raise last_exception from e

            except httpx.RequestError as e:
                last_exception = NetworkError(f"Request failed: {e}")
                if retryable and attempt < self._config.max_retries:
                    wait_time = self._config.backoff_factor * (2**attempt)
                    logger.warning("Network error, retrying in %.1f seconds...", wait_time)
                    time.sleep(wait_time)
                    continue
                raise last_exception from e

        if last_exception:
            raise last_exception
        raise NetworkError("Request failed after retries")

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """HTTP GET request."""
        return self._request_with_retry("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """HTTP POST request."""
        return self._request_with_retry("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """HTTP PATCH request."""
        return self._request_with_retry("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """HTTP DELETE request."""
        return self._request_with_retry("DELETE", url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """GET request returning JSON."""
        response = self.get(url, **kwargs)
        return self._decode_json_object(response)

    def post_json(self, url: str, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """POST JSON data and return JSON response."""
        response = self.post(url, json=data, **kwargs)
        return self._decode_json_object(response)

    @staticmethod
    def _decode_json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except (TypeError, ValueError, UnicodeError) as exc:
            raise AppleFlowChangedError("Apple API returned a non-JSON response") from exc
        if not isinstance(data, dict):
            raise AppleFlowChangedError("Apple API returned an unexpected JSON response")
        return data

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> AppleHTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
