"""Unit tests for AppleHTTPClient."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from slowlane.core.errors import (
    AccessDeniedError,
    AppleFlowChangedError,
    AppStoreConnectError,
    AuthExpiredError,
    NetworkError,
    RateLimitError,
)
from slowlane.core.http import (
    MAX_RETRY_AFTER_SECONDS,
    AppleHTTPClient,
    _parse_retry_after,
    redact_secrets,
)


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

    def test_context_manager(self) -> None:
        with AppleHTTPClient() as client:
            assert client is not None

    def test_headers_include_user_agent(self) -> None:
        client = AppleHTTPClient()
        headers = client._get_headers("https://api.appstoreconnect.apple.com/v1/apps")
        assert "slowlane/" in headers["User-Agent"]
        client.close()

    def test_headers_include_bearer_when_jwt_set(self) -> None:
        client = AppleHTTPClient(jwt_token="test.token.value")
        headers = client._get_headers("https://api.appstoreconnect.apple.com/v1/apps")
        assert headers["Authorization"] == "Bearer test.token.value"
        client.close()

    def test_headers_no_auth_without_jwt(self) -> None:
        client = AppleHTTPClient()
        headers = client._get_headers("https://api.appstoreconnect.apple.com/v1/apps")
        assert "Authorization" not in headers
        client.close()

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/resource",
            "http://developer.apple.com/services-account/v1/account/listTeams",
            "https://untrusted.developer.apple.com/services-account/v1/account/listTeams",
        ],
    )
    def test_credentials_are_not_sent_to_untrusted_hosts(self, url: str) -> None:
        requests: list[httpx.Request] = []

        def handle_request(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={})

        client = AppleHTTPClient(
            jwt_token="test.token.value",
        )
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handle_request))

        with pytest.raises(AppleFlowChangedError, match="untrusted URL"):
            client.get(url)

        assert requests == []
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

    def test_403_without_authentication_error_raises_access_denied(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.json.return_value = {"errors": [{"detail": "Insufficient role permissions"}]}

        with pytest.raises(AccessDeniedError, match="Insufficient role permissions"):
            client._classify_error(response)
        client.close()

    def test_403_preserves_authentication_error(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.json.return_value = {"errors": [{"detail": "Authentication required"}]}

        with pytest.raises(AccessDeniedError, match="Authentication required"):
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

    def test_generic_4xx_raises(self) -> None:
        client = AppleHTTPClient()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 400
        response.json.return_value = {}

        with pytest.raises(AppStoreConnectError, match="HTTP 400"):
            client._classify_error(response)
        client.close()

    def test_retry_after_http_date(self) -> None:
        retry_at = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
        retry_after = _parse_retry_after(retry_at)

        assert retry_after is not None
        assert 0 <= retry_after <= 30

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("invalid", None),
            ("-10", 0),
            (str(MAX_RETRY_AFTER_SECONDS + 1), MAX_RETRY_AFTER_SECONDS),
        ],
    )
    def test_retry_after_invalid_and_bounded(self, value: str, expected: int | None) -> None:
        assert _parse_retry_after(value) == expected


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

    def test_retries_on_server_error(self) -> None:
        from slowlane.core.config import HttpConfig

        config = HttpConfig(max_retries=2, backoff_factor=0.01)

        with patch("httpx.Client") as mock_client_cls, patch("time.sleep"):
            server_error = MagicMock(spec=httpx.Response)
            server_error.status_code = 503
            server_error.text = ""
            success = MagicMock(spec=httpx.Response)
            success.status_code = 200
            success.text = ""
            mock_client_cls.return_value.request.side_effect = [server_error, success]

            client = AppleHTTPClient(config=config)
            response = client.get("https://example.com/test")

            assert response.status_code == 200
            assert mock_client_cls.return_value.request.call_count == 2
            client.close()

    def test_refreshes_jwt_between_retry_attempts(self) -> None:
        from slowlane.core.config import HttpConfig

        config = HttpConfig(max_retries=1, backoff_factor=0)
        token_provider = MagicMock(side_effect=["first-token", "second-token"])

        with patch("httpx.Client") as mock_client_cls, patch("time.sleep"):
            server_error = MagicMock(spec=httpx.Response)
            server_error.status_code = 503
            server_error.text = ""
            success = MagicMock(spec=httpx.Response)
            success.status_code = 200
            success.text = ""
            mock_client_cls.return_value.request.side_effect = [server_error, success]

            client = AppleHTTPClient(config=config)
            client.set_jwt_token_provider(token_provider)
            client.get("https://api.appstoreconnect.apple.com/v1/apps")

            calls = mock_client_cls.return_value.request.call_args_list
            assert calls[0].kwargs["headers"]["Authorization"] == "Bearer first-token"
            assert calls[1].kwargs["headers"]["Authorization"] == "Bearer second-token"
            client.close()

    @pytest.mark.parametrize(
        "failure",
        [
            httpx.Response(503),
            httpx.TimeoutException("response lost"),
        ],
    )
    def test_post_failures_are_not_retried(self, failure: httpx.Response | Exception) -> None:
        from slowlane.core.config import HttpConfig

        config = HttpConfig(max_retries=3, backoff_factor=0)

        with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as sleep:
            if isinstance(failure, httpx.Response):
                failure._content = b""
                mock_client_cls.return_value.request.return_value = failure
            else:
                mock_client_cls.return_value.request.side_effect = failure

            client = AppleHTTPClient(config=config)
            with pytest.raises(NetworkError):
                client.post("https://example.com/resource", json={"operation": "create"})

            assert mock_client_cls.return_value.request.call_count == 1
            sleep.assert_not_called()
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

    @pytest.mark.parametrize("payload", ["<html>Sign in</html>", "[]"])
    def test_get_json_rejects_unexpected_success_body(self, payload: str) -> None:
        response = httpx.Response(200, text=payload)
        client = AppleHTTPClient()

        with (
            patch.object(client, "get", return_value=response),
            pytest.raises(AppleFlowChangedError),
        ):
            client.get_json("https://example.com/test")

        client.close()

    def test_post_json_rejects_non_object_json(self) -> None:
        response = httpx.Response(200, json=[{"id": "unexpected"}])
        client = AppleHTTPClient()

        with (
            patch.object(client, "post", return_value=response),
            pytest.raises(AppleFlowChangedError, match="unexpected JSON"),
        ):
            client.post_json("https://example.com/test", {"name": "value"})

        client.close()


def test_verbose_http_logs_exclude_response_body_and_query(caplog):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, json={"token": "body-secret-marker", "private_key": "private-key-marker"}
        )

    with AppleHTTPClient(jwt_token="header-secret-marker") as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(respond))
        with caplog.at_level("DEBUG", logger="slowlane.core.http"):
            client.get(
                "https://api.appstoreconnect.apple.com/v1/betaTesters?filter[email]=query-secret-marker"
            )
    assert len(requests) == 1
    messages = "\n".join(
        record.getMessage() for record in caplog.records if record.name == "slowlane.core.http"
    )
    for marker in (
        "body-secret-marker",
        "private-key-marker",
        "header-secret-marker",
        "query-secret-marker",
    ):
        assert marker not in messages
    assert "Response: 200" in messages


@pytest.mark.parametrize("errors", [None, 42, "invalid", [None, 1, {"detail": {"invalid": True}}]])
def test_malformed_forbidden_error_remains_access_denied(errors):
    with AppleHTTPClient() as client, pytest.raises(AccessDeniedError, match="HTTP 403"):
        client._classify_error(httpx.Response(403, json={"errors": errors}))


def test_apple_error_redacts_echoed_token():
    with AppleHTTPClient(jwt_token="sensitive-token-marker") as client:
        with pytest.raises(AppStoreConnectError) as error:
            client._classify_error(
                httpx.Response(409, json={"errors": [{"detail": "Invalid sensitive-token-marker"}]})
            )
        assert "sensitive-token-marker" not in str(error.value)
        assert "[REDACTED]" in str(error.value)
