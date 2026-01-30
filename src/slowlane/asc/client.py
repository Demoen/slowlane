"""App Store Connect API client."""

from __future__ import annotations

from typing import Any

from slowlane.auth.jwt_auth import JWTAuth
from slowlane.auth.session_auth import SessionAuth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.http import AppleHTTPClient


class AppStoreConnectClient:
    """Client for App Store Connect API operations."""

    BASE_URL = "https://api.appstoreconnect.apple.com/v1"

    def __init__(
        self,
        jwt_auth: JWTAuth | None = None,
        session_auth: SessionAuth | None = None,
        config: SlowlaneConfig | None = None,
    ) -> None:
        """Initialize client with authentication.

        Args:
            jwt_auth: JWT authentication (preferred for API)
            session_auth: Session cookie authentication (fallback)
            config: Configuration for HTTP client
        """
        self._jwt_auth = jwt_auth
        self._session_auth = session_auth
        self._config = config or SlowlaneConfig.load()

        http_config = self._config.http if self._config else None
        self._http = AppleHTTPClient(config=http_config)

        # Set up auth
        if jwt_auth:
            self._http.set_jwt_token(jwt_auth.get_token())
        elif session_auth:
            self._http.set_cookies(session_auth.cookies)

    def _refresh_token_if_needed(self) -> None:
        """Refresh JWT token if using JWT auth."""
        if self._jwt_auth:
            self._http.set_jwt_token(self._jwt_auth.get_token())

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make GET request to API."""
        self._refresh_token_if_needed()
        url = f"{self.BASE_URL}/{endpoint}"
        return self._http.get_json(url, params=params)

    def _post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request to API."""
        self._refresh_token_if_needed()
        url = f"{self.BASE_URL}/{endpoint}"
        return self._http.post_json(url, data)

    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of results."""
        params = params or {}
        params["limit"] = min(limit, 200)  # API max is 200

        all_data: list[dict[str, Any]] = []
        next_url: str | None = f"{self.BASE_URL}/{endpoint}"

        while next_url and len(all_data) < limit:
            self._refresh_token_if_needed()
            response = self._http.get_json(next_url, params=params if next_url.startswith(self.BASE_URL) else None)

            data = response.get("data", [])
            all_data.extend(data)

            # Get next page URL
            links = response.get("links", {})
            next_url = links.get("next")
            params = {}  # Params are included in next URL

        return all_data[:limit]

    # Apps
    def list_apps(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all apps for the team."""
        return self._paginate("apps", limit=limit)

    def get_app(self, app_id: str) -> dict[str, Any]:
        """Get a specific app by ID."""
        response = self._get(f"apps/{app_id}")
        return response.get("data", {})

    def get_app_by_bundle_id(self, bundle_id: str) -> dict[str, Any] | None:
        """Find an app by bundle ID."""
        response = self._get("apps", params={"filter[bundleId]": bundle_id})
        data = response.get("data", [])
        return data[0] if data else None

    # Builds
    def list_builds(
        self,
        app_id: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """List builds, optionally filtered by app."""
        params: dict[str, Any] = {}
        if app_id:
            params["filter[app]"] = app_id

        return self._paginate("builds", params=params, limit=limit)

    def get_build(self, build_id: str) -> dict[str, Any]:
        """Get a specific build by ID."""
        response = self._get(f"builds/{build_id}")
        return response.get("data", {})

    def get_latest_build(self, app_id: str) -> dict[str, Any] | None:
        """Get the most recent build for an app."""
        builds = self.list_builds(app_id=app_id, limit=1)
        return builds[0] if builds else None

    # TestFlight
    def list_beta_testers(
        self,
        app_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List beta testers."""
        params: dict[str, Any] = {}
        if app_id:
            params["filter[apps]"] = app_id

        return self._paginate("betaTesters", params=params, limit=limit)

    def get_beta_tester(self, tester_id: str) -> dict[str, Any]:
        """Get a specific beta tester."""
        response = self._get(f"betaTesters/{tester_id}")
        return response.get("data", {})

    def list_beta_groups(self, app_id: str | None = None) -> list[dict[str, Any]]:
        """List beta groups."""
        params: dict[str, Any] = {}
        if app_id:
            params["filter[app]"] = app_id

        return self._paginate("betaGroups", params=params, limit=100)

    def get_beta_group(self, group_id: str) -> dict[str, Any]:
        """Get a specific beta group."""
        response = self._get(f"betaGroups/{group_id}")
        return response.get("data", {})

    def invite_beta_tester(
        self,
        email: str,
        group_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        """Invite a tester to a beta group."""
        data = {
            "data": {
                "type": "betaTesters",
                "attributes": {
                    "email": email,
                },
                "relationships": {
                    "betaGroups": {
                        "data": [{"type": "betaGroups", "id": group_id}]
                    }
                },
            }
        }

        if first_name:
            data["data"]["attributes"]["firstName"] = first_name
        if last_name:
            data["data"]["attributes"]["lastName"] = last_name

        response = self._post("betaTesters", data)
        return response.get("data", {})

    def add_tester_to_group(self, tester_id: str, group_id: str) -> None:
        """Add an existing tester to a beta group."""
        data = {
            "data": [{"type": "betaTesters", "id": tester_id}]
        }
        self._http.post(
            f"{self.BASE_URL}/betaGroups/{group_id}/relationships/betaTesters",
            json=data,
        )

    # Bundle IDs
    def list_bundle_ids(self, limit: int = 50) -> list[dict[str, Any]]:
        """List registered bundle IDs."""
        return self._paginate("bundleIds", limit=limit)

    def get_bundle_id(self, bundle_id_resource_id: str) -> dict[str, Any]:
        """Get a specific bundle ID resource."""
        response = self._get(f"bundleIds/{bundle_id_resource_id}")
        return response.get("data", {})

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> AppStoreConnectClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
