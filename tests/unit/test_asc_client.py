from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from slowlane.asc.client import AppStoreConnectClient
from slowlane.auth.jwt_auth import JWTAuth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AppStoreConnectError, InvalidArgumentsError


def resource(kind: str, resource_id: str = "id-1", **attributes: Any) -> dict[str, Any]:
    return {"type": kind, "id": resource_id, "attributes": attributes}


@contextmanager
def api_client(
    responses: list[dict[str, Any] | httpx.Response],
    key_type: str = "team",
) -> Iterator[tuple[AppStoreConnectClient, list[httpx.Request]]]:
    requests: list[httpx.Request] = []
    pending = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert pending, f"Unexpected request: {request.method} {request.url}"
        response = pending.pop(0)
        return (
            response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)
        )

    auth = MagicMock(spec=JWTAuth)
    auth.key_type = key_type
    auth.get_token.return_value = "test.jwt.token"
    transport = httpx.Client(transport=httpx.MockTransport(handler))
    with (
        patch("slowlane.core.http.httpx.Client", return_value=transport),
        AppStoreConnectClient(jwt_auth=auth, config=SlowlaneConfig()) as client,
    ):
        yield client, requests


def test_client_requires_api_key() -> None:
    with pytest.raises(AppStoreConnectError, match="API key"):
        AppStoreConnectClient()


def test_client_closes_transport() -> None:
    with api_client([]) as (client, _):
        transport = client._http._client
    assert transport.is_closed


def test_apps_and_bundle_identifier_lookup() -> None:
    app = resource("apps", name="[red]literal[/red]", bundleId="com.example.app")
    with api_client([{"data": [app]}, {"data": app}, {"data": [app]}]) as (client, requests):
        assert client.list_apps() == [app]
        assert client.get_app("id-1") == app
        assert client.get_app_by_bundle_id("com.example.app") == app
    assert requests[2].url.params["filter[bundleId]"] == "com.example.app"
    assert all(r.headers["Authorization"] == "Bearer test.jwt.token" for r in requests)


def test_empty_app_and_build_lookup() -> None:
    with api_client([{"data": []}, {"data": []}]) as (client, _):
        assert client.get_app_by_bundle_id("com.missing.app") is None
        assert client.get_latest_build("app-1") is None


def test_build_filters_and_latest_order() -> None:
    build = resource("builds", version="42", processingState="VALID")
    with api_client([{"data": [build]}, {"data": [build]}, {"data": build}]) as (client, requests):
        assert client.list_builds("app-1", limit=25) == [build]
        assert client.get_latest_build("app-1") == build
        assert client.get_build("id-1") == build
    assert dict(requests[0].url.params) == {"filter[app]": "app-1", "limit": "25"}
    assert dict(requests[1].url.params) == {
        "filter[app]": "app-1",
        "sort": "-uploadedDate",
        "limit": "1",
    }


def test_tester_and_group_filters_and_reads() -> None:
    tester, group = resource("betaTesters"), resource("betaGroups")
    with api_client([{"data": [tester]}, {"data": [group]}, {"data": tester}]) as (
        client,
        requests,
    ):
        assert client.list_beta_testers("app-1") == [tester]
        assert client.list_beta_groups("app-1") == [group]
        assert client.get_beta_tester("id-1") == tester
    assert requests[0].url.params["filter[apps]"] == "app-1"
    assert requests[1].url.params["filter[app]"] == "app-1"


def test_pagination_preserves_server_cursor_without_repeating_initial_query() -> None:
    next_url = "https://api.appstoreconnect.apple.com/v1/apps?cursor=next&limit=200"
    with api_client(
        [
            {"data": [resource("apps", "first")], "links": {"next": next_url}},
            {"data": [resource("apps", "second")]},
        ]
    ) as (client, requests):
        assert [r["id"] for r in client.list_apps(300)] == ["first", "second"]
    assert requests[0].url.params["limit"] == "200"
    assert str(requests[1].url) == next_url


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/v1/apps",
        "http://api.appstoreconnect.apple.com/v1/apps",
        "https://api.appstoreconnect.apple.com:444/v1/apps",
        "https://user@api.appstoreconnect.apple.com/v1/apps",
        "https://api.appstoreconnect.apple.com/v2/apps",
        "https://api.appstoreconnect.apple.com/v1/apps#fragment",
        123,
    ],
)
def test_pagination_rejects_untrusted_links_before_request(url: object) -> None:
    with (
        api_client([{"data": [], "links": {"next": url}}]) as (client, requests),
        pytest.raises(AppStoreConnectError),
    ):
        client.list_apps()
    assert len(requests) == 1


def test_pagination_rejects_repeated_page() -> None:
    page = "https://api.appstoreconnect.apple.com/v1/apps"
    with (
        api_client([{"data": [], "links": {"next": page}}]) as (client, requests),
        pytest.raises(AppStoreConnectError, match="repeated"),
    ):
        client.list_apps()
    assert len(requests) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {}},
        {"data": [None]},
        {"data": [{"id": "a"}]},
        {"data": [{"id": "a", "type": "apps", "attributes": None}]},
        {"data": [], "links": []},
    ],
)
def test_list_rejects_malformed_resources(payload: dict[str, Any]) -> None:
    with api_client([payload]) as (client, _), pytest.raises(AppStoreConnectError):
        client.list_apps()


@pytest.mark.parametrize("payload", [{}, {"data": None}, {"data": []}])
def test_get_rejects_missing_resource(payload: dict[str, Any]) -> None:
    with api_client([payload]) as (client, _), pytest.raises(AppStoreConnectError):
        client.get_app("id-1")


def test_limit_truncates_and_zero_does_not_request() -> None:
    with api_client([{"data": [resource("apps", str(i)) for i in range(3)]}]) as (client, requests):
        assert client.list_apps(0) == []
        assert len(client.list_apps(2)) == 2
    assert len(requests) == 1


def test_new_tester_creation_uses_external_group_and_json_api_relationships() -> None:
    tester = resource("betaTesters", "tester-1", email="test@example.com")
    with api_client(
        [
            {"data": resource("betaGroups", "group-1", isInternalGroup=False)},
            {"data": []},
            {"data": tester},
        ]
    ) as (client, requests):
        assert client.invite_beta_tester("test@example.com", "group-1", "Ada", "Lovelace") == tester
    assert requests[-1].method == "POST"
    assert json.loads(requests[-1].content) == {
        "data": {
            "type": "betaTesters",
            "attributes": {"email": "test@example.com", "firstName": "Ada", "lastName": "Lovelace"},
            "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": "group-1"}]}},
        }
    }


@pytest.mark.parametrize("already_member", [False, True])
def test_existing_tester_is_added_once_without_recreating(already_member: bool) -> None:
    tester = resource("betaTesters", "tester-1", email="test@example.com")
    responses: list[dict[str, Any] | httpx.Response] = [
        {"data": resource("betaGroups", "group-1", isInternalGroup=False)},
        {"data": [tester]},
        {"data": [tester] if already_member else []},
    ]
    if not already_member:
        responses.append(httpx.Response(204))
    with api_client(responses) as (client, requests):
        assert client.invite_beta_tester("test@example.com", "group-1") == tester
    assert requests[2].url.params["filter[betaGroups]"] == "group-1"
    if already_member:
        assert len(requests) == 3
    else:
        assert requests[-1].url.path == "/v1/betaGroups/group-1/relationships/betaTesters"
        assert json.loads(requests[-1].content) == {
            "data": [{"type": "betaTesters", "id": "tester-1"}]
        }


def test_internal_group_invitation_is_rejected_before_mutation() -> None:
    with (
        api_client([{"data": resource("betaGroups", isInternalGroup=True)}]) as (client, requests),
        pytest.raises(InvalidArgumentsError, match="external"),
    ):
        client.invite_beta_tester("test@example.com", "group-1")
    assert len(requests) == 1
