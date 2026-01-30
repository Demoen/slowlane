"""Unit tests for Developer Portal API client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from slowlane.auth.session_auth import SessionAuth
from slowlane.core.secrets import SessionData
from slowlane.devportal.client import DeveloperPortalClient


class TestDeveloperPortalClient:
    """Tests for DeveloperPortalClient."""

    @pytest.fixture
    def mock_session_data(self) -> SessionData:
        """Create mock session data."""
        return SessionData(
            cookies={"myacinfo": "test_cookie", "DES": "test_des"},
            email_hash="abc123",
            created_at=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_session_auth(self, mock_session_data: SessionData) -> SessionAuth:
        """Create mock session auth."""
        return SessionAuth(mock_session_data)

    def test_client_initialization(self, mock_session_auth: SessionAuth) -> None:
        """Test client initializes correctly."""
        with patch("slowlane.devportal.client.AppleHTTPClient"):
            client = DeveloperPortalClient(session_auth=mock_session_auth)
            assert client._session_auth == mock_session_auth

    def test_client_context_manager(self, mock_session_auth: SessionAuth) -> None:
        """Test client works as context manager."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance

            with DeveloperPortalClient(session_auth=mock_session_auth) as client:
                assert client is not None

            mock_instance.close.assert_called_once()


class TestDeveloperPortalCertificates:
    """Tests for certificate-related API methods."""

    def test_list_certificates(self) -> None:
        """Test list_certificates returns certificates."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_certs = [
                {
                    "id": "cert-1",
                    "type": "certificates",
                    "name": "iOS Distribution",
                    "certificateType": "IOS_DISTRIBUTION",
                }
            ]
            mock_instance.get_json.return_value = {"certRequests": mock_certs}

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"  # Pre-set team ID

            result = client.list_certificates()

            assert len(result) == 1
            assert result[0]["id"] == "cert-1"

    def test_list_certificates_filtered_by_type(self) -> None:
        """Test list_certificates with type filter."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_instance.get_json.return_value = {"certRequests": []}

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"

            client.list_certificates(cert_type="IOS_DISTRIBUTION")

            mock_instance.get_json.assert_called_once()

    def test_get_certificate(self) -> None:
        """Test get_certificate returns certificate details."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_instance.get_json.return_value = {"id": "cert-123", "name": "Test Cert"}

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"

            result = client.get_certificate("cert-123")

            assert result["id"] == "cert-123"


class TestDeveloperPortalProfiles:
    """Tests for provisioning profile-related API methods."""

    def test_list_profiles(self) -> None:
        """Test list_profiles returns profiles."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_profiles = [
                {
                    "id": "profile-1",
                    "name": "iOS App Store",
                    "profileType": "IOS_APP_STORE",
                    "profileState": "ACTIVE",
                }
            ]
            mock_instance.get_json.return_value = {"provisioningProfiles": mock_profiles}

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"

            result = client.list_profiles()

            assert len(result) == 1
            assert result[0]["profileType"] == "IOS_APP_STORE"

    def test_get_profile(self) -> None:
        """Test get_profile returns single profile."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_instance.get_json.return_value = {
                "provisioningProfile": {"id": "profile-123", "name": "Test Profile"}
            }

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"

            result = client.get_profile("profile-123")

            assert result["id"] == "profile-123"


class TestDeveloperPortalDevices:
    """Tests for device-related API methods."""

    def test_list_devices(self) -> None:
        """Test list_devices returns devices."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_devices = [
                {
                    "id": "device-1",
                    "name": "iPhone 15",
                    "udid": "00008020-001234567890ABCD",
                    "deviceClass": "IPHONE",
                    "status": "ENABLED",
                }
            ]
            mock_instance.get_json.return_value = {"devices": mock_devices}

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"

            result = client.list_devices()

            assert len(result) == 1
            assert result[0]["deviceClass"] == "IPHONE"

    def test_list_app_ids(self) -> None:
        """Test list_app_ids returns bundle IDs."""
        with patch("slowlane.devportal.client.AppleHTTPClient") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_app_ids = [
                {
                    "id": "appid-1",
                    "identifier": "com.example.app",
                    "name": "Example App",
                }
            ]
            mock_instance.get_json.return_value = {"appIds": mock_app_ids}

            mock_session = SessionData(
                cookies={"myacinfo": "test", "DES": "test"},
                email_hash="test",
                created_at=datetime.now(UTC),
            )
            client = DeveloperPortalClient(session_auth=SessionAuth(mock_session))
            client._team_id = "TEAM123456"

            result = client.list_app_ids()

            assert len(result) == 1
            assert result[0]["identifier"] == "com.example.app"
