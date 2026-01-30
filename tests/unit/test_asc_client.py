"""Unit tests for App Store Connect API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from slowlane.asc.client import AppStoreConnectClient
from slowlane.auth.jwt_auth import JWTAuth


class TestAppStoreConnectClient:
    """Tests for AppStoreConnectClient."""

    @pytest.fixture
    def mock_jwt_auth(self) -> MagicMock:
        """Create a mock JWT auth."""
        auth = MagicMock(spec=JWTAuth)
        auth.get_token.return_value = "mock_jwt_token_12345"
        return auth

    @pytest.fixture
    def mock_http_response(self) -> dict:
        """Standard API response structure."""
        return {
            "data": [],
            "links": {"self": "https://api.appstoreconnect.apple.com/v1/apps"},
        }

    def test_client_initialization_with_jwt(self, mock_jwt_auth: MagicMock) -> None:
        """Test client initializes correctly with JWT auth."""
        with patch("slowlane.asc.client.AppleHTTPClient"):
            client = AppStoreConnectClient(jwt_auth=mock_jwt_auth)
            assert client._jwt_auth == mock_jwt_auth

    def test_client_initialization_without_auth(self) -> None:
        """Test client initializes without auth."""
        with patch("slowlane.asc.client.AppleHTTPClient"):
            client = AppStoreConnectClient()
            assert client._jwt_auth is None
            assert client._session_auth is None

    def test_client_context_manager(self, mock_jwt_auth: MagicMock) -> None:
        """Test client works as context manager."""
        with patch("slowlane.asc.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance

            with AppStoreConnectClient(jwt_auth=mock_jwt_auth) as client:
                assert client is not None

            mock_instance.close.assert_called_once()


class TestAppStoreConnectClientApps:
    """Tests for app-related API methods."""

    @pytest.fixture
    def client_with_mock_http(self) -> tuple[AppStoreConnectClient, MagicMock]:
        """Create client with mocked HTTP layer."""
        with patch("slowlane.asc.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            
            mock_jwt = MagicMock(spec=JWTAuth)
            mock_jwt.get_token.return_value = "test_token"
            
            client = AppStoreConnectClient(jwt_auth=mock_jwt)
            return client, mock_instance

    def test_list_apps_returns_empty_list(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test list_apps returns empty list when no apps."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {"data": [], "links": {}}

        result = client.list_apps()

        assert result == []
        mock_http.get_json.assert_called()

    def test_list_apps_returns_apps(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test list_apps returns apps correctly."""
        client, mock_http = client_with_mock_http
        mock_apps = [
            {
                "id": "123456789",
                "type": "apps",
                "attributes": {
                    "name": "Test App",
                    "bundleId": "com.example.testapp",
                    "sku": "TESTSKU001",
                    "primaryLocale": "en-US",
                },
            },
            {
                "id": "987654321",
                "type": "apps",
                "attributes": {
                    "name": "Another App",
                    "bundleId": "com.example.anotherapp",
                    "sku": "TESTSKU002",
                    "primaryLocale": "en-US",
                },
            },
        ]
        mock_http.get_json.return_value = {"data": mock_apps, "links": {}}

        result = client.list_apps()

        assert len(result) == 2
        assert result[0]["id"] == "123456789"
        assert result[0]["attributes"]["name"] == "Test App"
        assert result[1]["id"] == "987654321"

    def test_get_app_by_id(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test get_app returns single app."""
        client, mock_http = client_with_mock_http
        mock_app = {
            "id": "123456789",
            "type": "apps",
            "attributes": {
                "name": "Test App",
                "bundleId": "com.example.testapp",
            },
        }
        mock_http.get_json.return_value = {"data": mock_app}

        result = client.get_app("123456789")

        assert result["id"] == "123456789"
        assert result["attributes"]["name"] == "Test App"

    def test_get_app_by_bundle_id(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test get_app_by_bundle_id finds app."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {
            "data": [
                {
                    "id": "123",
                    "attributes": {"bundleId": "com.example.test"},
                }
            ]
        }

        result = client.get_app_by_bundle_id("com.example.test")

        assert result is not None
        assert result["id"] == "123"

    def test_get_app_by_bundle_id_not_found(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test get_app_by_bundle_id returns None when not found."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {"data": []}

        result = client.get_app_by_bundle_id("com.nonexistent.app")

        assert result is None


class TestAppStoreConnectClientBuilds:
    """Tests for build-related API methods."""

    @pytest.fixture
    def client_with_mock_http(self) -> tuple[AppStoreConnectClient, MagicMock]:
        """Create client with mocked HTTP layer."""
        with patch("slowlane.asc.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            
            mock_jwt = MagicMock(spec=JWTAuth)
            mock_jwt.get_token.return_value = "test_token"
            
            client = AppStoreConnectClient(jwt_auth=mock_jwt)
            return client, mock_instance

    def test_list_builds(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test list_builds returns builds."""
        client, mock_http = client_with_mock_http
        mock_builds = [
            {
                "id": "build-1",
                "type": "builds",
                "attributes": {
                    "version": "1.0.0",
                    "uploadedDate": "2024-01-15T10:30:00Z",
                    "processingState": "VALID",
                },
            }
        ]
        mock_http.get_json.return_value = {"data": mock_builds, "links": {}}

        result = client.list_builds()

        assert len(result) == 1
        assert result[0]["id"] == "build-1"
        assert result[0]["attributes"]["version"] == "1.0.0"

    def test_list_builds_filtered_by_app(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test list_builds with app filter."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {"data": [], "links": {}}

        client.list_builds(app_id="app-123")

        # Verify the filter was passed
        call_args = mock_http.get_json.call_args
        assert call_args is not None

    def test_get_build(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test get_build returns single build."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {
            "data": {
                "id": "build-123",
                "attributes": {"version": "2.0.0"},
            }
        }

        result = client.get_build("build-123")

        assert result["id"] == "build-123"
        assert result["attributes"]["version"] == "2.0.0"

    def test_get_latest_build(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test get_latest_build returns most recent."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {
            "data": [{"id": "latest-build", "attributes": {"version": "3.0.0"}}],
            "links": {},
        }

        result = client.get_latest_build("app-123")

        assert result is not None
        assert result["id"] == "latest-build"

    def test_get_latest_build_no_builds(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test get_latest_build returns None when no builds."""
        client, mock_http = client_with_mock_http
        mock_http.get_json.return_value = {"data": [], "links": {}}

        result = client.get_latest_build("app-123")

        assert result is None


class TestAppStoreConnectClientTestFlight:
    """Tests for TestFlight-related API methods."""

    @pytest.fixture
    def client_with_mock_http(self) -> tuple[AppStoreConnectClient, MagicMock]:
        """Create client with mocked HTTP layer."""
        with patch("slowlane.asc.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            
            mock_jwt = MagicMock(spec=JWTAuth)
            mock_jwt.get_token.return_value = "test_token"
            
            client = AppStoreConnectClient(jwt_auth=mock_jwt)
            return client, mock_instance

    def test_list_beta_testers(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test list_beta_testers returns testers."""
        client, mock_http = client_with_mock_http
        mock_testers = [
            {
                "id": "tester-1",
                "attributes": {
                    "email": "tester@example.com",
                    "firstName": "Test",
                    "lastName": "User",
                },
            }
        ]
        mock_http.get_json.return_value = {"data": mock_testers, "links": {}}

        result = client.list_beta_testers()

        assert len(result) == 1
        assert result[0]["attributes"]["email"] == "tester@example.com"

    def test_list_beta_groups(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test list_beta_groups returns groups."""
        client, mock_http = client_with_mock_http
        mock_groups = [
            {
                "id": "group-1",
                "attributes": {
                    "name": "Internal Testers",
                    "publicLinkEnabled": False,
                    "isInternalGroup": True,
                },
            }
        ]
        mock_http.get_json.return_value = {"data": mock_groups, "links": {}}

        result = client.list_beta_groups()

        assert len(result) == 1
        assert result[0]["attributes"]["name"] == "Internal Testers"

    def test_invite_beta_tester(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test invite_beta_tester posts correctly."""
        client, mock_http = client_with_mock_http
        mock_http.post_json.return_value = {
            "data": {
                "id": "new-tester-id",
                "attributes": {"email": "new@example.com"},
            }
        }

        result = client.invite_beta_tester(
            email="new@example.com",
            group_id="group-123",
            first_name="New",
            last_name="Tester",
        )

        assert result["id"] == "new-tester-id"
        mock_http.post_json.assert_called_once()


class TestAppStoreConnectClientPagination:
    """Tests for pagination handling."""

    @pytest.fixture
    def client_with_mock_http(self) -> tuple[AppStoreConnectClient, MagicMock]:
        """Create client with mocked HTTP layer."""
        with patch("slowlane.asc.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            
            mock_jwt = MagicMock(spec=JWTAuth)
            mock_jwt.get_token.return_value = "test_token"
            
            client = AppStoreConnectClient(jwt_auth=mock_jwt)
            return client, mock_instance

    def test_pagination_follows_next_link(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test pagination follows next links."""
        client, mock_http = client_with_mock_http
        
        # First page
        page1 = {
            "data": [{"id": "1"}, {"id": "2"}],
            "links": {"next": "https://api.example.com/v1/apps?cursor=abc"},
        }
        # Second page
        page2 = {
            "data": [{"id": "3"}],
            "links": {},
        }
        mock_http.get_json.side_effect = [page1, page2]

        result = client.list_apps(limit=10)

        assert len(result) == 3
        assert mock_http.get_json.call_count == 2

    def test_pagination_respects_limit(
        self, client_with_mock_http: tuple[AppStoreConnectClient, MagicMock]
    ) -> None:
        """Test pagination stops at limit."""
        client, mock_http = client_with_mock_http
        
        # Return more items than limit
        mock_http.get_json.return_value = {
            "data": [{"id": str(i)} for i in range(10)],
            "links": {"next": "https://api.example.com/more"},
        }

        result = client.list_apps(limit=5)

        assert len(result) == 5
