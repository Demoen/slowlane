"""Unit tests for AppleHTTPClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from slowlane.core.errors import AuthExpiredError, NetworkError, RateLimitError
from slowlane.core.http import AppleHTTPClient, redact_secrets


class TestRedactSecrets:
    def test_redacts_bearer_token(self) -> None:
        text = "Authorization: Bearer abc.def.ghi"
        result = redact_secrets(text)
        assert "[REDACTED]" in result
        assert "abc.def.ghi" not in result

    def test_redacts_password(self) -> None:
        text = 'password: "mysecret"'
        result = redact_secrets(text)
        assert "[REDACTED]" in result
        assert "mysecret" not in result

    def test_leaves_safe_text_unchanged(self) -> None:
        text = "Hello world, no secrets here"
        assert redact_secrets(text) == text


class TestAppleHTTPClientInit:
    def test_default_init(self) -> None:
        client = AppleHTTPClient()
        assert client._jwt_token is None
        client.close()

    def test_set_jwt_token(self) -> None:
        client = AppleHTTPClient()
        client.set_jwt_token("my.token.here")
        assert client._jwt_token == "my.token.here"
        client.close()

    def test_set_cookies(self) -> None:
        client = AppleHTTPClient()
        client.set_cookies({"session": "abc"})
        assert client._cookies == {"session": "abc"}
        client.close()

    def test_context_manager(self) -> None:
        with AppleHTTPClient() as client:
            assert client is not None

    def test_headers_include_user_agent(self) -> None:
        client = AppleHTTPClient()
        headers = client._get_headers()
        assert "slowlane/" in headers["User-Agent"]
        client.close()

    def test_headers_include_bearer_when_jwt_set(self) -> None:
        client = AppleHTTPClient(jwt_token="test.token.value")
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test.token.value"
        client.close()

    def test_headers_no_auth_without_jwt(self) -> None:
        client = AppleHTTPClient()
        headers = client._get_headers()
        assert "Authorization" not in headers
        client.close()


class TestAppleHTTPClientErrorClassification:
    def test_401_raises_auth_expired(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.headers = {}

        with pytest.raises(AuthExpiredError):
            client._classify_error(response)
        client.close()

    def test_403_raises_auth_expired(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.json.return_value = {}

        with pytest.raises(AuthExpiredError):
            client._classify_error(response)
        client.close()

    def test_429_raises_rate_limit(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = {"Retry-After": "30"}

        with pytest.raises(RateLimitError) as exc_info:
            client._classify_error(response)
        assert exc_info.value.retry_after == 30
        client.close()

    def test_429_default_retry_when_no_header(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = {}

        with pytest.raises(RateLimitError) as exc_info:
            client._classify_error(response)
        assert exc_info.value.retry_after == 60
        client.close()

    def test_500_raises_network_error(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500

        with pytest.raises(NetworkError):
            client._classify_error(response)
        client.close()

    def test_200_does_not_raise(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        # No exception raised for 2xx
        client._classify_error(response)
        client.close()


class TestAppleHTTPClientRetry:
    def test_successful_get(self) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"data": []}'
            mock_client_cls.return_value.request.return_value = mock_response

            client = AppleHTTPClient()
            response = client.get("https://example.com/test")
            assert response.status_code == 200
            client.close()

    def test_retries_on_timeout(self) -> None:
        from slowlane.core.config import HttpConfig

        config = HttpConfig(max_retries=2, backoff_factor=0.01)

        with patch("httpx.Client") as mock_client_cls:
            mock_success = MagicMock()
            mock_success.status_code = 200
            mock_success.text = ""
            mock_client_cls.return_value.request.side_effect = [
                httpx.TimeoutException("timeout"),
                mock_success,
            ]

            client = AppleHTTPClient(config=config)
            response = client.get("https://example.com/test")
            assert response.status_code == 200
            assert mock_client_cls.return_value.request.call_count == 2
            client.close()

    def test_raises_after_max_retries(self) -> None:
        from slowlane.core.config import HttpConfig

        config = HttpConfig(max_retries=1, backoff_factor=0.01)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.request.side_effect = httpx.TimeoutException("timeout")

            client = AppleHTTPClient(config=config)
            with pytest.raises(NetworkError):
                client.get("https://example.com/test")
            client.close()

    def test_get_json_returns_dict(self) -> None:
        with patch("httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"key": "value"}'
            mock_response.json.return_value = {"key": "value"}
            mock_client_cls.return_value.request.return_value = mock_response

            client = AppleHTTPClient()
            result = client.get_json("https://example.com/test")
            assert result == {"key": "value"}
            client.close()
