"""App Store Connect API client."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlsplit

from slowlane.auth.jwt_auth import JWTAuth
from slowlane.auth.session_auth import SessionAuth
from slowlane.core.base_client import BaseAppleClient
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AppStoreConnectError


class AppStoreConnectClient(BaseAppleClient):
    """Client for App Store Connect API operations."""

    BASE_URL = "https://api.appstoreconnect.apple.com/v1"

    @classmethod
    def _validate_pagination_url(cls, url: str) -> None:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except (TypeError, ValueError) as exc:
            raise AppStoreConnectError("Invalid App Store Connect pagination URL") from exc

        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.appstoreconnect.apple.com"
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or (parsed.path != "/v1" and not parsed.path.startswith("/v1/"))
        ):
            raise AppStoreConnectError("Refusing pagination URL outside App Store Connect")

    def __init__(
        self,
        jwt_auth: JWTAuth | None = None,
        session_auth: SessionAuth | None = None,
        config: SlowlaneConfig | None = None,
    ) -> None:
        if jwt_auth is None:
            raise AppStoreConnectError(
                "App Store Connect API requests require API key authentication"
            )

        super().__init__(config)
        self._jwt_auth = jwt_auth
        self._session_auth = session_auth

        self._http.set_jwt_token_provider(jwt_auth.get_token)
        self._http.set_jwt_token(jwt_auth.get_token())

    def _refresh_token_if_needed(self) -> None:
        if self._jwt_auth:
            self._http.set_jwt_token(self._jwt_auth.get_token())

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._refresh_token_if_needed()
        url = f"{self.BASE_URL}/{endpoint}"
        return self._http.get_json(url, params=params)

    def _post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        self._refresh_token_if_needed()
        url = f"{self.BASE_URL}/{endpoint}"
        return self._http.post_json(url, data)

    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of results up to limit."""
        if limit <= 0:
            return []

        params = dict(params or {})
        params["limit"] = min(limit, 200)  # API max is 200

        all_data: list[dict[str, Any]] = []
        next_url: str | None = f"{self.BASE_URL}/{endpoint}"
        request_params: dict[str, Any] | None = params
        visited_urls: set[str] = set()

        while next_url and len(all_data) < limit:
            self._validate_pagination_url(next_url)
            if next_url in visited_urls:
                raise AppStoreConnectError("App Store Connect pagination repeated a page URL")
            visited_urls.add(next_url)
            self._refresh_token_if_needed()
            response = self._http.get_json(next_url, params=request_params or None)
            request_params = None

            data = response.get("data", [])
            if not isinstance(data, list):
                raise AppStoreConnectError("Invalid data in App Store Connect response")
            all_data.extend(data)

            links = response.get("links", {})
            if not isinstance(links, dict):
                raise AppStoreConnectError("Invalid pagination links in App Store Connect response")
            next_value = links.get("next")
            if next_value is not None and not isinstance(next_value, str):
                raise AppStoreConnectError("Invalid App Store Connect pagination URL")
            next_url = next_value

        return all_data[:limit]

    # Apps
    def list_apps(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._paginate("apps", limit=limit)

    def get_app(self, app_id: str) -> dict[str, Any]:
        response = self._get(f"apps/{app_id}")
        return cast(dict[str, Any], response.get("data", {}))

    def get_app_by_bundle_id(self, bundle_id: str) -> dict[str, Any] | None:
        response = self._get("apps", params={"filter[bundleId]": bundle_id})
        data = response.get("data", [])
        return data[0] if data else None

    # Builds
    def list_builds(
        self,
        app_id: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if app_id:
            params["filter[app]"] = app_id

        return self._paginate("builds", params=params, limit=limit)

    def get_build(self, build_id: str) -> dict[str, Any]:
        response = self._get(f"builds/{build_id}")
        return cast(dict[str, Any], response.get("data", {}))

    def get_latest_build(self, app_id: str) -> dict[str, Any] | None:
        builds = self._paginate(
            "builds",
            params={"filter[app]": app_id, "sort": "-uploadedDate"},
            limit=1,
        )
        return builds[0] if builds else None

    # TestFlight
    def list_beta_testers(
        self,
        app_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if app_id:
            params["filter[apps]"] = app_id

        return self._paginate("betaTesters", params=params, limit=limit)

    def get_beta_tester(self, tester_id: str) -> dict[str, Any]:
        response = self._get(f"betaTesters/{tester_id}")
        return cast(dict[str, Any], response.get("data", {}))

    def list_beta_groups(self, app_id: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if app_id:
            params["filter[app]"] = app_id

        return self._paginate("betaGroups", params=params, limit=100)

    def get_beta_group(self, group_id: str) -> dict[str, Any]:
        response = self._get(f"betaGroups/{group_id}")
        return cast(dict[str, Any], response.get("data", {}))

    def invite_beta_tester(
        self,
        email: str,
        group_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "data": {
                "type": "betaTesters",
                "attributes": {
                    "email": email,
                },
                "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": group_id}]}},
            }
        }

        if first_name:
            data["data"]["attributes"]["firstName"] = first_name
        if last_name:
            data["data"]["attributes"]["lastName"] = last_name

        response = self._post("betaTesters", data)
        return cast(dict[str, Any], response.get("data", {}))

    def add_tester_to_group(self, tester_id: str, group_id: str) -> None:
        data = {"data": [{"type": "betaTesters", "id": tester_id}]}
        self._refresh_token_if_needed()
        self._http.post(
            f"{self.BASE_URL}/betaGroups/{group_id}/relationships/betaTesters",
            json=data,
        )

    # Bundle IDs
    def list_bundle_ids(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._paginate("bundleIds", limit=limit)

    def get_bundle_id(self, bundle_id_resource_id: str) -> dict[str, Any]:
        response = self._get(f"bundleIds/{bundle_id_resource_id}")
        return cast(dict[str, Any], response.get("data", {}))
