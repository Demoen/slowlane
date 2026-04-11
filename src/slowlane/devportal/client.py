"""Developer Portal API client for certificates and profiles."""

from __future__ import annotations

from typing import Any, cast

from slowlane.auth.session_auth import SessionAuth
from slowlane.core.base_client import BaseAppleClient
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import DeveloperPortalError


class DeveloperPortalClient(BaseAppleClient):
    """Client for Apple Developer Portal operations.

    Note: Developer Portal operations require session-based authentication.
    JWT (API key) authentication is not supported for these endpoints.
    """

    BASE_URL = "https://developer.apple.com/services-account/v1"
    PORTAL_URL = "https://developer.apple.com"

    def __init__(
        self,
        session_auth: SessionAuth,
        config: SlowlaneConfig | None = None,
        team_id: str | None = None,
    ) -> None:
        super().__init__(config)
        self._session_auth = session_auth
        self._http.set_cookies(session_auth.cookies)

        # Explicit > config default > auto-detect on first use
        self._team_id: str | None = team_id or self._config.devportal.team_id

    def _get_team_id(self) -> str:
        if self._team_id:
            return self._team_id

        teams = self.list_teams()
        if not teams:
            raise DeveloperPortalError("No development teams found")

        if len(teams) > 1:
            team_list = ", ".join(f"{t['teamId']} ({t.get('name', '?')})" for t in teams)
            raise DeveloperPortalError(
                f"Multiple teams found: {team_list}. "
                "Use --team-id or set [devportal] team_id in config."
            )

        self._team_id = teams[0]["teamId"]
        return self._team_id

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["teamId"] = self._get_team_id()
        return self._http.get_json(url, params=params)

    def _post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        data["teamId"] = self._get_team_id()
        return self._http.post_json(url, data)

    # Teams
    def list_teams(self) -> list[dict[str, Any]]:
        response = self._http.get_json(f"{self.BASE_URL}/account/listTeams")
        return cast(list[dict[str, Any]], response.get("teams", []))

    # Certificates
    def list_certificates(
        self,
        cert_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if cert_type:
            params["filter[certificateType]"] = cert_type

        response = self._get("account/ios/certificate/listCertRequests.action", params)
        return cast(list[dict[str, Any]], response.get("certRequests", []))

    def get_certificate(self, cert_id: str) -> dict[str, Any]:
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
        return cast(dict[str, Any], response.get("certRequest", {}))

    def revoke_certificate(self, cert_id: str) -> None:
        self._post(
            "account/ios/certificate/revokeCertificate.action",
            {"certificateId": cert_id},
        )

    # Provisioning Profiles
    def list_profiles(
        self,
        profile_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if profile_type:
            params["filter[profileType]"] = profile_type

        response = self._get("account/ios/profile/listProvisioningProfiles.action", params)
        return cast(list[dict[str, Any]], response.get("provisioningProfiles", []))

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        response = self._get(
            "account/ios/profile/getProvisioningProfile.action",
            params={"provisioningProfileId": profile_id},
        )
        return cast(dict[str, Any], response.get("provisioningProfile", {}))

    def download_profile(self, profile_id: str) -> bytes:
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
        type_map = {
            "development": "IOS_APP_DEVELOPMENT",
            "appstore": "IOS_APP_STORE",
            "adhoc": "IOS_APP_ADHOC",
        }

        data: dict[str, Any] = {
            "provisioningProfileName": name,
            "appIdId": bundle_id,
            "distributionType": type_map.get(profile_type, profile_type),
            "certificateIds": certificate_ids,
        }

        if device_ids:
            data["deviceIds"] = device_ids

        response = self._post("account/ios/profile/createProvisioningProfile.action", data)
        return cast(dict[str, Any], response.get("provisioningProfile", {}))

    def delete_profile(self, profile_id: str) -> None:
        self._post(
            "account/ios/profile/deleteProvisioningProfile.action",
            {"provisioningProfileId": profile_id},
        )

    # Devices
    def list_devices(self) -> list[dict[str, Any]]:
        response = self._get("account/ios/device/listDevices.action")
        return cast(list[dict[str, Any]], response.get("devices", []))

    def register_device(
        self,
        name: str,
        udid: str,
        platform: str = "ios",
    ) -> dict[str, Any]:
        data = {
            "deviceName": name,
            "deviceNumber": udid,
            "devicePlatform": platform,
        }

        response = self._post("account/ios/device/addDevice.action", data)
        return cast(dict[str, Any], response.get("device", {}))

    # Bundle IDs (App IDs)
    def list_app_ids(self) -> list[dict[str, Any]]:
        response = self._get("account/ios/identifiers/listAppIds.action")
        return cast(list[dict[str, Any]], response.get("appIds", []))

    def get_app_id(self, app_id: str) -> dict[str, Any]:
        response = self._get(
            "account/ios/identifiers/getAppIdDetail.action",
            params={"appIdId": app_id},
        )
        return cast(dict[str, Any], response.get("appId", {}))
