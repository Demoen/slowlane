"""App Store Connect and provisioning API operations."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote, urlsplit

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import pkcs7

from slowlane.auth.jwt_auth import JWTAuth
from slowlane.core.base_client import BaseAppleClient
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AccessDeniedError, AppStoreConnectError, InvalidArgumentsError

CERTIFICATE_ALIASES = {
    "development": "DEVELOPMENT",
    "distribution": "DISTRIBUTION",
    "mac_development": "MAC_APP_DEVELOPMENT",
    "mac_distribution": "MAC_APP_DISTRIBUTION",
}
CERTIFICATE_TYPES = frozenset(
    {
        "DEVELOPMENT",
        "DISTRIBUTION",
        "IOS_DEVELOPMENT",
        "IOS_DISTRIBUTION",
        "MAC_APP_DEVELOPMENT",
        "MAC_APP_DISTRIBUTION",
        "MAC_INSTALLER_DISTRIBUTION",
    }
)
CERTIFICATE_FILTER_TYPES = CERTIFICATE_TYPES | {
    "APPLE_PAY",
    "APPLE_PAY_MERCHANT_IDENTITY",
    "APPLE_PAY_PSP_IDENTITY",
    "APPLE_PAY_RSA",
    "DEVELOPER_ID_KEXT",
    "DEVELOPER_ID_KEXT_G2",
    "DEVELOPER_ID_APPLICATION",
    "DEVELOPER_ID_APPLICATION_G2",
    "IDENTITY_ACCESS",
    "PASS_TYPE_ID",
    "PASS_TYPE_ID_WITH_NFC",
}
PROFILE_ALIASES = {
    "development": "IOS_APP_DEVELOPMENT",
    "appstore": "IOS_APP_STORE",
    "app-store": "IOS_APP_STORE",
    "app_store": "IOS_APP_STORE",
    "adhoc": "IOS_APP_ADHOC",
    "ad-hoc": "IOS_APP_ADHOC",
    "ad_hoc": "IOS_APP_ADHOC",
}


def normalize_certificate_type(value: str, *, for_creation: bool = True) -> str:
    result = CERTIFICATE_ALIASES.get(value.strip().lower(), value.strip().upper())
    allowed = CERTIFICATE_TYPES if for_creation else CERTIFICATE_FILTER_TYPES
    if result not in allowed:
        raise InvalidArgumentsError(
            "Unsupported certificate type. Use development, distribution, mac_development, "
            "mac_distribution, or an explicit supported signing certificate type. "
            "Create Developer ID certificates through Xcode or the Apple Developer website."
        )
    return result


def normalize_profile_type(value: str) -> str:
    result = PROFILE_ALIASES.get(value.strip().lower(), value.strip().upper())
    if result not in PROFILE_ALIASES.values():
        raise InvalidArgumentsError("Profile type must be development, appstore, or adhoc")
    return result


def validate_csr(content: str) -> None:
    try:
        request = x509.load_pem_x509_csr(content.encode("utf-8"))
        if not request.is_signature_valid:
            raise ValueError("Invalid signature")
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise InvalidArgumentsError("CSR must be a valid, signed PEM certificate request") from exc


class AppStoreConnectClient(BaseAppleClient):
    BASE_URL = "https://api.appstoreconnect.apple.com/v1"

    def __init__(
        self,
        jwt_auth: JWTAuth | None = None,
        config: SlowlaneConfig | None = None,
    ) -> None:
        if jwt_auth is None:
            raise AppStoreConnectError(
                "App Store Connect API requests require API key authentication"
            )
        token = jwt_auth.get_token()
        super().__init__(config)
        self._jwt_auth = jwt_auth
        self._http.set_jwt_token_provider(jwt_auth.get_token)
        self._http.set_jwt_token(token)

    def require_team_key(self) -> None:
        if self._jwt_auth.key_type != "team":
            raise AccessDeniedError(
                "Provisioning requires a team API key with Certificates, Identifiers & Profiles "
                "access. Individual API keys cannot use signing or device endpoints."
            )

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
            or parsed.fragment
            or (parsed.path != "/v1" and not parsed.path.startswith("/v1/"))
        ):
            raise AppStoreConnectError("Refusing pagination URL outside App Store Connect")

    @staticmethod
    def _id(value: str) -> str:
        if not value.strip() or value.strip() in {".", ".."}:
            raise InvalidArgumentsError("Resource ID must be non-empty")
        return quote(value.strip(), safe="")

    @staticmethod
    def _resource(value: Any, resource_type: str) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("id"), str)
            or not value["id"]
            or value.get("type") != resource_type
            or not isinstance(value.get("attributes", {}), dict)
            or not isinstance(value.get("relationships", {}), dict)
        ):
            raise AppStoreConnectError(f"Invalid {resource_type} resource in Apple API response")
        return cast(dict[str, Any], value)

    def _refresh_token_if_needed(self) -> None:
        self._http.set_jwt_token(self._jwt_auth.get_token())

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._refresh_token_if_needed()
        return self._http.get_json(f"{self.BASE_URL}/{endpoint}", params=params)

    def _get_resource(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        response = self._get(f"{resource_type}/{self._id(resource_id)}")
        return self._resource(response.get("data"), resource_type)

    def _post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        self._refresh_token_if_needed()
        response = self._http.post_json(f"{self.BASE_URL}/{endpoint}", {"data": data})
        return self._resource(response.get("data"), endpoint)

    def _delete(self, resource_type: str, resource_id: str) -> None:
        self._refresh_token_if_needed()
        self._http.delete(f"{self.BASE_URL}/{resource_type}/{self._id(resource_id)}")

    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        limit: int | None = 50,
    ) -> list[dict[str, Any]]:
        if limit is not None and limit <= 0:
            return []
        request_params = dict(params or {})
        request_params["limit"] = min(limit, 200) if limit is not None else 200
        all_data: list[dict[str, Any]] = []
        next_url: str | None = f"{self.BASE_URL}/{endpoint}"
        visited_urls: set[str] = set()
        while next_url and (limit is None or len(all_data) < limit):
            self._validate_pagination_url(next_url)
            if next_url in visited_urls:
                raise AppStoreConnectError("App Store Connect pagination repeated a page URL")
            visited_urls.add(next_url)
            self._refresh_token_if_needed()
            response = self._http.get_json(next_url, params=request_params or None)
            request_params = {}
            data = response.get("data")
            if not isinstance(data, list):
                raise AppStoreConnectError("Invalid data in App Store Connect response")
            all_data.extend(self._resource(item, endpoint.split("/")[-1]) for item in data)
            links = response.get("links", {})
            if not isinstance(links, dict):
                raise AppStoreConnectError("Invalid pagination links in App Store Connect response")
            next_value = links.get("next")
            if next_value is not None and not isinstance(next_value, str):
                raise AppStoreConnectError("Invalid App Store Connect pagination URL")
            next_url = next_value
        return all_data[:limit] if limit is not None else all_data

    def list_apps(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._paginate("apps", limit=limit)

    def get_app(self, app_id: str) -> dict[str, Any]:
        return self._get_resource("apps", app_id)

    def get_app_by_bundle_id(self, bundle_id: str) -> dict[str, Any] | None:
        apps = self._paginate("apps", {"filter[bundleId]": bundle_id}, limit=2)
        if len(apps) > 1:
            raise AppStoreConnectError(f"Multiple apps match bundle identifier {bundle_id}")
        return apps[0] if apps else None

    def list_builds(self, app_id: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
        params = {"filter[app]": app_id} if app_id else {}
        return self._paginate("builds", params=params, limit=limit)

    def get_build(self, build_id: str) -> dict[str, Any]:
        return self._get_resource("builds", build_id)

    def get_latest_build(self, app_id: str) -> dict[str, Any] | None:
        builds = self._paginate("builds", {"filter[app]": app_id, "sort": "-uploadedDate"}, limit=1)
        return builds[0] if builds else None

    def list_beta_testers(self, app_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params = {"filter[apps]": app_id} if app_id else {}
        return self._paginate("betaTesters", params=params, limit=limit)

    def get_beta_tester(self, tester_id: str) -> dict[str, Any]:
        return self._get_resource("betaTesters", tester_id)

    def list_beta_groups(
        self,
        app_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params = {"filter[app]": app_id} if app_id else {}
        return self._paginate("betaGroups", params=params, limit=limit)

    def get_beta_group(self, group_id: str) -> dict[str, Any]:
        return self._get_resource("betaGroups", group_id)

    def invite_beta_tester(
        self,
        email: str,
        group_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        email = email.strip()
        if not email or "@" not in email:
            raise InvalidArgumentsError("A tester email address is required")
        group = self.get_beta_group(group_id)
        if group.get("attributes", {}).get("isInternalGroup") is not False:
            raise InvalidArgumentsError("Email invitations require an external TestFlight group")
        existing = self._paginate("betaTesters", {"filter[email]": email}, limit=None)
        if len(existing) > 1:
            raise AppStoreConnectError(f"Multiple beta testers match {email}")
        if existing:
            tester = existing[0]
            members = self._paginate(
                "betaTesters", {"filter[email]": email, "filter[betaGroups]": group_id}, limit=1
            )
            if not members:
                self.add_tester_to_group(tester["id"], group_id)
            return tester
        attributes = {"email": email}
        if first_name:
            attributes["firstName"] = first_name
        if last_name:
            attributes["lastName"] = last_name
        return self._post(
            "betaTesters",
            {
                "type": "betaTesters",
                "attributes": attributes,
                "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": group_id}]}},
            },
        )

    def add_tester_to_group(self, tester_id: str, group_id: str) -> None:
        self._refresh_token_if_needed()
        self._http.post(
            f"{self.BASE_URL}/betaGroups/{self._id(group_id)}/relationships/betaTesters",
            json={"data": [{"type": "betaTesters", "id": tester_id}]},
        )

    def list_bundle_ids(self, limit: int | None = 50) -> list[dict[str, Any]]:
        self.require_team_key()
        return self._paginate("bundleIds", limit=limit)

    def get_bundle_id(self, bundle_id_resource_id: str) -> dict[str, Any]:
        self.require_team_key()
        return self._get_resource("bundleIds", bundle_id_resource_id)

    def resolve_bundle_id(self, identifier: str) -> dict[str, Any]:
        self.require_team_key()
        resources = self._paginate("bundleIds", {"filter[identifier]": identifier}, limit=None)
        exact = [r for r in resources if r.get("attributes", {}).get("identifier") == identifier]
        if len(exact) != 1:
            raise AppStoreConnectError(f"Expected one registered bundle ID matching {identifier}")
        return exact[0]

    def list_certificates(self, cert_type: str | None = None) -> list[dict[str, Any]]:
        self.require_team_key()
        params = (
            {"filter[certificateType]": normalize_certificate_type(cert_type, for_creation=False)}
            if cert_type
            else {}
        )
        return self._paginate("certificates", params, limit=None)

    def get_certificate(self, cert_id: str) -> dict[str, Any]:
        self.require_team_key()
        return self._get_resource("certificates", cert_id)

    def create_certificate(
        self, csr_content: str, cert_type: str = "development"
    ) -> dict[str, Any]:
        self.require_team_key()
        certificate_type = normalize_certificate_type(cert_type)
        validate_csr(csr_content)
        return self._post(
            "certificates",
            {
                "type": "certificates",
                "attributes": {
                    "csrContent": csr_content.strip(),
                    "certificateType": certificate_type,
                },
            },
        )

    def revoke_certificate(self, cert_id: str) -> None:
        self.require_team_key()
        self._delete("certificates", cert_id)

    def list_profiles(
        self,
        profile_type: str | None = None,
        bundle_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.require_team_key()
        normalized = normalize_profile_type(profile_type) if profile_type else None
        if bundle_id:
            resource = self.resolve_bundle_id(bundle_id)
            profiles = self._paginate(f"bundleIds/{self._id(resource['id'])}/profiles", limit=None)
            return [
                p
                for p in profiles
                if normalized is None or p.get("attributes", {}).get("profileType") == normalized
            ]
        params = {"filter[profileType]": normalized} if normalized else {}
        return self._paginate("profiles", params, limit=None)

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        self.require_team_key()
        return self._get_resource("profiles", profile_id)

    def create_profile(
        self,
        name: str,
        bundle_id: str,
        profile_type: str,
        certificate_ids: list[str],
        device_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self.require_team_key()
        normalized = normalize_profile_type(profile_type)
        if not name.strip() or not bundle_id.strip():
            raise InvalidArgumentsError("Profile name and bundle ID resource are required")
        if len(certificate_ids) != 1 or not certificate_ids[0].strip():
            raise InvalidArgumentsError("Specify exactly one signing certificate resource ID")
        devices = list(
            dict.fromkeys(device.strip() for device in (device_ids or []) if device.strip())
        )
        if normalized == "IOS_APP_STORE" and devices:
            raise InvalidArgumentsError("Devices are not allowed for App Store profiles")
        if normalized != "IOS_APP_STORE" and not devices:
            raise InvalidArgumentsError(
                "Development and ad hoc profiles require device resource IDs"
            )
        certificate = self.get_certificate(certificate_ids[0])
        attributes = certificate.get("attributes", {})
        compatible = (
            {"DEVELOPMENT", "IOS_DEVELOPMENT"}
            if normalized == "IOS_APP_DEVELOPMENT"
            else {"DISTRIBUTION", "IOS_DISTRIBUTION"}
        )
        try:
            expires = datetime.fromisoformat(attributes["expirationDate"].replace("Z", "+00:00"))
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise AppStoreConnectError("Certificate expiration date is missing or invalid") from exc
        if expires.tzinfo is None:
            raise AppStoreConnectError("Certificate expiration date must include a timezone")
        if expires <= datetime.now(UTC) or attributes.get("certificateType") not in compatible:
            raise InvalidArgumentsError(
                "Certificate is expired or incompatible with the profile type"
            )
        relationships: dict[str, Any] = {
            "bundleId": {"data": {"type": "bundleIds", "id": bundle_id}},
            "certificates": {"data": [{"type": "certificates", "id": certificate_ids[0]}]},
        }
        if devices:
            relationships["devices"] = {
                "data": [{"type": "devices", "id": value} for value in devices]
            }
        return self._post(
            "profiles",
            {
                "type": "profiles",
                "attributes": {
                    "name": name.strip(),
                    "profileType": normalized,
                },
                "relationships": relationships,
            },
        )

    def delete_profile(self, profile_id: str) -> None:
        self.require_team_key()
        self._delete("profiles", profile_id)

    @staticmethod
    def _decode_content(resource: dict[str, Any], field: str) -> bytes:
        value = resource.get("attributes", {}).get(field)
        try:
            if not isinstance(value, str) or not value:
                raise ValueError("Missing content")
            content = base64.b64decode(value, validate=True)
            if not content:
                raise ValueError("Empty content")
            return content
        except (ValueError, binascii.Error) as exc:
            raise AppStoreConnectError(f"Apple returned invalid {field}") from exc

    def download_certificate(self, cert_id: str) -> bytes:
        content = self._decode_content(self.get_certificate(cert_id), "certificateContent")
        try:
            x509.load_der_x509_certificate(content)
        except (ValueError, UnsupportedAlgorithm) as exc:
            raise AppStoreConnectError("Apple returned invalid DER certificate data") from exc
        return content

    def download_profile(self, profile_id: str) -> bytes:
        content = self._decode_content(self.get_profile(profile_id), "profileContent")
        try:
            if not pkcs7.load_der_pkcs7_certificates(content):
                raise ValueError("Missing signing certificates")
        except (ValueError, UnsupportedAlgorithm) as exc:
            raise AppStoreConnectError(
                "Apple returned invalid CMS provisioning profile data"
            ) from exc
        return content

    def list_devices(self) -> list[dict[str, Any]]:
        self.require_team_key()
        return self._paginate("devices", limit=None)

    def register_device(self, name: str, udid: str, platform: str = "IOS") -> dict[str, Any]:
        self.require_team_key()
        platform = platform.strip().upper()
        if platform not in {"IOS", "MAC_OS", "UNIVERSAL"} or not name.strip() or not udid.strip():
            raise InvalidArgumentsError(
                "Device requires a name, UDID, and IOS, MAC_OS, or UNIVERSAL platform"
            )
        return self._post(
            "devices",
            {
                "type": "devices",
                "attributes": {
                    "name": name.strip(),
                    "udid": udid.strip(),
                    "platform": platform,
                },
            },
        )
