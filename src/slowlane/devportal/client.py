"""Developer Portal API client for certificates and profiles."""

from __future__ import annotations

from typing import Any

from slowlane.auth.session_auth import SessionAuth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import DeveloperPortalError
from slowlane.core.http import AppleHTTPClient


class DeveloperPortalClient:
    """Client for Apple Developer Portal operations.

    Note: Developer Portal operations require session-based authentication.
    JWT (API key) authentication is not supported for these endpoints.
    """

    # Developer Portal uses different endpoints than ASC API
    BASE_URL = "https://developer.apple.com/services-account/v1"
    PORTAL_URL = "https://developer.apple.com"

    def __init__(
        self,
        session_auth: SessionAuth,
        config: SlowlaneConfig | None = None,
    ) -> None:
        """Initialize client with session authentication.

        Args:
            session_auth: Session cookie authentication (required)
            config: Configuration for HTTP client
        """
        self._session_auth = session_auth
        self._config = config or SlowlaneConfig.load()

        http_config = self._config.http if self._config else None
        self._http = AppleHTTPClient(config=http_config)
        self._http.set_cookies(session_auth.cookies)

        # Team ID is needed for most operations
        self._team_id: str | None = None

    def _get_team_id(self) -> str:
        """Get the team ID from the portal."""
        if self._team_id:
            return self._team_id

        # Fetch teams
        teams = self.list_teams()
        if not teams:
            raise DeveloperPortalError("No development teams found")

        # Use first team (or could prompt user)
        self._team_id = teams[0]["teamId"]
        return self._team_id

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make GET request to portal API."""
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["teamId"] = self._get_team_id()
        return self._http.get_json(url, params=params)

    def _post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request to portal API."""
        url = f"{self.BASE_URL}/{endpoint}"
        data["teamId"] = self._get_team_id()
        return self._http.post_json(url, data)

    # Teams
    def list_teams(self) -> list[dict[str, Any]]:
        """List development teams the user belongs to."""
        response = self._http.get_json(f"{self.BASE_URL}/account/listTeams")
        return response.get("teams", [])

    # Certificates
    def list_certificates(
        self,
        cert_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List signing certificates.

        Args:
            cert_type: Filter by type (development, distribution, etc.)
        """
        params: dict[str, Any] = {}
        if cert_type:
            params["filter[certificateType]"] = cert_type

        response = self._get("account/ios/certificate/listCertRequests.action", params)
        return response.get("certRequests", [])

    def get_certificate(self, cert_id: str) -> dict[str, Any]:
        """Get certificate details."""
        response = self._get(
            "account/ios/certificate/downloadCertificateContent.action",
            params={"certificateId": cert_id},
        )
        return response

    def create_certificate(
        self,
        csr_content: str,
        cert_type: str = "development",
    ) -> dict[str, Any]:
        """Create a new certificate.

        Args:
            csr_content: Certificate Signing Request content
            cert_type: Certificate type (development, distribution)
        """
        # Map friendly names to Apple's internal types
        type_map = {
            "development": "IOS_DEVELOPMENT",
            "distribution": "IOS_DISTRIBUTION",
            "mac_development": "MAC_APP_DEVELOPMENT",
            "mac_distribution": "MAC_APP_DISTRIBUTION",
        }

        data = {
            "csrContent": csr_content,
            "certificateType": type_map.get(cert_type, cert_type),
        }

        response = self._post("account/ios/certificate/submitCertificateRequest.action", data)
        return response.get("certRequest", {})

    def revoke_certificate(self, cert_id: str) -> None:
        """Revoke a certificate."""
        self._post(
            "account/ios/certificate/revokeCertificate.action",
            {"certificateId": cert_id},
        )

    # Provisioning Profiles
    def list_profiles(
        self,
        profile_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List provisioning profiles.

        Args:
            profile_type: Filter by type (development, appstore, adhoc)
        """
        params: dict[str, Any] = {}
        if profile_type:
            params["filter[profileType]"] = profile_type

        response = self._get("account/ios/profile/listProvisioningProfiles.action", params)
        return response.get("provisioningProfiles", [])

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        """Get provisioning profile details."""
        response = self._get(
            "account/ios/profile/getProvisioningProfile.action",
            params={"provisioningProfileId": profile_id},
        )
        return response.get("provisioningProfile", {})

    def download_profile(self, profile_id: str) -> bytes:
        """Download provisioning profile content."""
        response = self._http.get(
            f"{self.BASE_URL}/account/ios/profile/downloadProfileContent",
            params={"provisioningProfileId": profile_id, "teamId": self._get_team_id()},
        )
        return response.content

    def create_profile(
        self,
        name: str,
        bundle_id: str,
        profile_type: str,
        certificate_ids: list[str],
        device_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new provisioning profile.

        Args:
            name: Profile name
            bundle_id: App bundle ID
            profile_type: Profile type (development, appstore, adhoc)
            certificate_ids: List of certificate IDs to include
            device_ids: List of device IDs (required for development/adhoc)
        """
        type_map = {
            "development": "IOS_APP_DEVELOPMENT",
            "appstore": "IOS_APP_STORE",
            "adhoc": "IOS_APP_ADHOC",
        }

        data = {
            "provisioningProfileName": name,
            "appIdId": bundle_id,
            "distributionType": type_map.get(profile_type, profile_type),
            "certificateIds": certificate_ids,
        }

        if device_ids:
            data["deviceIds"] = device_ids

        response = self._post("account/ios/profile/createProvisioningProfile.action", data)
        return response.get("provisioningProfile", {})

    def delete_profile(self, profile_id: str) -> None:
        """Delete a provisioning profile."""
        self._post(
            "account/ios/profile/deleteProvisioningProfile.action",
            {"provisioningProfileId": profile_id},
        )

    # Devices
    def list_devices(self) -> list[dict[str, Any]]:
        """List registered devices."""
        response = self._get("account/ios/device/listDevices.action")
        return response.get("devices", [])

    def register_device(
        self,
        name: str,
        udid: str,
        platform: str = "ios",
    ) -> dict[str, Any]:
        """Register a new device.

        Args:
            name: Device name
            udid: Device UDID
            platform: Platform (ios, mac)
        """
        data = {
            "deviceName": name,
            "deviceNumber": udid,
            "devicePlatform": platform,
        }

        response = self._post("account/ios/device/addDevice.action", data)
        return response.get("device", {})

    # Bundle IDs (App IDs)
    def list_app_ids(self) -> list[dict[str, Any]]:
        """List registered App IDs."""
        response = self._get("account/ios/identifiers/listAppIds.action")
        return response.get("appIds", [])

    def get_app_id(self, app_id: str) -> dict[str, Any]:
        """Get App ID details."""
        response = self._get(
            "account/ios/identifiers/getAppIdDetail.action",
            params={"appIdId": app_id},
        )
        return response.get("appId", {})

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> DeveloperPortalClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
