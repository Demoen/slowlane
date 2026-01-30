"""HTTP client with retries, backoff, and cookie handling."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from .config import HttpConfig
from .errors import (
    AppleFlowChangedError,
    AuthExpiredError,
    NetworkError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Patterns for redacting secrets in logs
SECRET_PATTERNS = [
    re.compile(r'(Authorization:\s*Bearer\s+)[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'),
    re.compile(r'(password["\']?\s*[:=]\s*["\']?)[^"\'&\s]+'),
    re.compile(r'(X-Apple-ID-Session-Id:\s*)[^\s]+'),
    re.compile(r'(scnt:\s*)[^\s]+'),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive information from text."""
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(r'\1[REDACTED]', result)
    return result


class AppleHTTPClient:
    """HTTP client configured for Apple APIs with retry and error handling."""

    ASC_API_BASE = "https://api.appstoreconnect.apple.com/v1"
    APPLE_AUTH_BASE = "https://idmsa.apple.com"
    DEVELOPER_PORTAL_BASE = "https://developer.apple.com"

    def __init__(
        self,
        config: HttpConfig | None = None,
        jwt_token: str | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self._config = config or HttpConfig()
        self._jwt_token = jwt_token
        self._cookies = cookies or {}

        self._client = httpx.Client(
            timeout=httpx.Timeout(self._config.timeout),
            follow_redirects=True,
            cookies=self._cookies,
        )

    def set_jwt_token(self, token: str) -> None:
        """Set JWT token for authentication."""
        self._jwt_token = token

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """Set cookies for session authentication."""
        self._cookies = cookies
        self._client.cookies.update(cookies)

    def _get_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Build request headers."""
        headers: dict[str, str] = {
            "User-Agent": "slowlane/0.1.0",
            "Accept": "application/json",
        }

        if self._jwt_token:
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
            # Could be auth issue or permission issue
            try:
                data = response.json()
                errors = data.get("errors", [])
                if errors and "authentication" in str(errors).lower():
                    raise AuthExpiredError("Authentication required", status_code=status)
            except Exception:
                pass
            raise AuthExpiredError("Access forbidden", status_code=status)

        if status == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 60
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
            except Exception:
                pass

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with exponential backoff retry."""
        headers = self._get_headers(kwargs.pop("headers", None))
        kwargs["headers"] = headers

        last_exception: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
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

                if response.status_code < 400:
                    return response

                # Check for retryable errors
                if response.status_code in (429, 500, 502, 503, 504):
                    self._classify_error(response)  # May raise RateLimitError

                # Non-retryable error
                self._classify_error(response)
                return response

            except RateLimitError as e:
                last_exception = e
                wait_time = e.retry_after or (self._config.backoff_factor * (2**attempt))
                if attempt < self._config.max_retries:
                    logger.warning("Rate limited, waiting %d seconds...", wait_time)
                    time.sleep(wait_time)
                    continue
                raise

            except httpx.TimeoutException as e:
                last_exception = NetworkError(f"Request timeout: {e}")
                if attempt < self._config.max_retries:
                    wait_time = self._config.backoff_factor * (2**attempt)
                    logger.warning("Timeout, retrying in %.1f seconds...", wait_time)
                    time.sleep(wait_time)
                    continue

            except httpx.RequestError as e:
                last_exception = NetworkError(f"Request failed: {e}")
                if attempt < self._config.max_retries:
                    wait_time = self._config.backoff_factor * (2**attempt)
                    logger.warning("Network error, retrying in %.1f seconds...", wait_time)
                    time.sleep(wait_time)
                    continue

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
        return response.json()  # type: ignore[no-any-return]

    def post_json(self, url: str, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """POST JSON data and return JSON response."""
        response = self.post(url, json=data, **kwargs)
        return response.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> AppleHTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
