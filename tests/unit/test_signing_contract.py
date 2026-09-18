from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from slowlane.core.errors import AccessDeniedError, AppStoreConnectError, InvalidArgumentsError
from tests.unit.test_asc_client import api_client, resource


@pytest.fixture(scope="module")
def signing_material() -> tuple[str, bytes, bytes]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Slowlane test")])
    request = x509.CertificateSigningRequestBuilder().subject_name(name).sign(key, hashes.SHA256())
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    profile = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(b'<?xml version="1.0"?><plist><dict/></plist>')
        .add_signer(certificate, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )
    return (
        request.public_bytes(serialization.Encoding.PEM).decode(),
        certificate.public_bytes(serialization.Encoding.DER),
        profile,
    )


@pytest.mark.parametrize(
    "method,args",
    [
        ("list_certificates", ()),
        ("get_certificate", ("cert-1",)),
        ("create_certificate", ("csr",)),
        ("revoke_certificate", ("cert-1",)),
        ("list_profiles", ()),
        ("get_profile", ("profile-1",)),
        ("delete_profile", ("profile-1",)),
        ("list_devices", ()),
        ("register_device", ("phone", "udid")),
        ("list_bundle_ids", ()),
        ("resolve_bundle_id", ("com.example.app",)),
    ],
)
def test_individual_keys_cannot_make_provisioning_requests(
    method: str, args: tuple[str, ...]
) -> None:
    with (
        api_client([], key_type="individual") as (client, requests),
        pytest.raises(AccessDeniedError, match="team API key"),
    ):
        getattr(client, method)(*args)
    assert requests == []


def test_individual_keys_can_read_apps() -> None:
    with api_client([{"data": []}], key_type="individual") as (client, _):
        assert client.list_apps() == []


def test_create_certificate_uses_modern_type_and_signed_csr(
    signing_material: tuple[str, bytes, bytes],
) -> None:
    csr, _, _ = signing_material
    result = resource("certificates", "cert-1", certificateType="DISTRIBUTION")
    with api_client([{"data": result}]) as (client, requests):
        assert client.create_certificate(csr, "distribution") == result
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/certificates"
    assert json.loads(requests[0].content) == {
        "data": {
            "type": "certificates",
            "attributes": {"csrContent": csr.strip(), "certificateType": "DISTRIBUTION"},
        }
    }


@pytest.mark.parametrize(
    "kind,csr",
    [
        ("development", "not a CSR"),
        ("development", ""),
        ("DEVELOPER_ID_APPLICATION", "bad"),
        ("enterprise", "bad"),
    ],
)
def test_certificate_input_rejected_before_request(kind: str, csr: str) -> None:
    with api_client([]) as (client, requests), pytest.raises(InvalidArgumentsError):
        client.create_certificate(csr, kind)
    assert requests == []


def test_csr_with_invalid_signature_is_rejected(signing_material: tuple[str, bytes, bytes]) -> None:
    csr = x509.load_pem_x509_csr(signing_material[0].encode())
    corrupted = bytearray(csr.public_bytes(serialization.Encoding.DER))
    corrupted[-1] ^= 1
    pem = (
        "-----BEGIN CERTIFICATE REQUEST-----\n"
        + base64.b64encode(corrupted).decode()
        + "\n-----END CERTIFICATE REQUEST-----"
    )
    with (
        api_client([]) as (client, requests),
        pytest.raises(InvalidArgumentsError, match="signed PEM"),
    ):
        client.create_certificate(pem)
    assert requests == []


def test_developer_id_certificates_can_be_listed_without_enabling_creation() -> None:
    with api_client([{"data": []}]) as (client, requests):
        assert client.list_certificates("DEVELOPER_ID_APPLICATION") == []
    assert requests[0].url.params["filter[certificateType]"] == "DEVELOPER_ID_APPLICATION"


def test_signing_lists_follow_all_pages_and_normalize_filters() -> None:
    next_url = "https://api.appstoreconnect.apple.com/v1/certificates?cursor=second"
    with api_client(
        [
            {"data": [resource("certificates", "first")], "links": {"next": next_url}},
            {"data": [resource("certificates", "second")]},
            {"data": []},
        ]
    ) as (client, requests):
        assert len(client.list_certificates("development")) == 2
        assert client.list_profiles("adhoc") == []
    assert requests[0].url.params["filter[certificateType]"] == "DEVELOPMENT"
    assert requests[0].url.params["limit"] == "200"
    assert requests[2].url.params["filter[profileType]"] == "IOS_APP_ADHOC"


def test_bundle_resolution_and_profile_filter_use_supported_relationship_endpoint() -> None:
    bundle = resource("bundleIds", "bundle-1", identifier="com.example.app")
    appstore = resource("profiles", "store", profileType="IOS_APP_STORE")
    development = resource("profiles", "dev", profileType="IOS_APP_DEVELOPMENT")
    with api_client([{"data": [bundle]}, {"data": [development, appstore]}]) as (client, requests):
        assert client.list_profiles("appstore", "com.example.app") == [appstore]
    assert requests[0].url.params["filter[identifier]"] == "com.example.app"
    assert requests[1].url.path == "/v1/bundleIds/bundle-1/profiles"
    assert dict(requests[1].url.params) == {"limit": "200"}


def test_missing_bundle_identifier_is_not_silent_success() -> None:
    with api_client([{"data": []}]) as (client, _), pytest.raises(AppStoreConnectError):
        client.resolve_bundle_id("com.missing.app")


@pytest.mark.parametrize(
    "profile_type,certificate_type,devices",
    [
        ("development", "DEVELOPMENT", ["device-1", "device-1", "device-2"]),
        ("appstore", "DISTRIBUTION", None),
        ("adhoc", "IOS_DISTRIBUTION", ["device-1"]),
    ],
)
def test_profile_creation_sends_json_api_relationships(
    profile_type: str,
    certificate_type: str,
    devices: list[str] | None,
) -> None:
    cert = resource(
        "certificates",
        "cert-1",
        certificateType=certificate_type,
        expirationDate="2099-01-01T00:00:00Z",
    )
    with api_client([{"data": cert}, {"data": resource("profiles", "profile-1")}]) as (
        client,
        requests,
    ):
        assert (
            client.create_profile("Release", "bundle-1", profile_type, ["cert-1"], devices)["id"]
            == "profile-1"
        )
    assert requests[0].url.path == "/v1/certificates/cert-1"
    assert requests[1].method == "POST"
    body = json.loads(requests[1].content)["data"]
    assert body["type"] == "profiles"
    assert body["attributes"]["name"] == "Release"
    assert body["relationships"]["bundleId"] == {"data": {"type": "bundleIds", "id": "bundle-1"}}
    assert body["relationships"]["certificates"] == {
        "data": [{"type": "certificates", "id": "cert-1"}]
    }
    if devices:
        assert body["relationships"]["devices"]["data"] == [
            {"type": "devices", "id": value} for value in dict.fromkeys(devices)
        ]
    else:
        assert "devices" not in body["relationships"]


@pytest.mark.parametrize(
    "certificate_type,expiry",
    [
        ("DEVELOPMENT", "2099-01-01T00:00:00Z"),
        ("DISTRIBUTION", "2020-01-01T00:00:00Z"),
    ],
)
def test_profile_rejects_incompatible_or_expired_certificate(
    certificate_type: str, expiry: str
) -> None:
    cert = resource(
        "certificates", "cert-1", certificateType=certificate_type, expirationDate=expiry
    )
    with api_client([{"data": cert}]) as (client, requests), pytest.raises(InvalidArgumentsError):
        client.create_profile("Profile", "bundle", "appstore", ["cert-1"])
    assert len(requests) == 1


@pytest.mark.parametrize(
    "kind,certificates,devices",
    [
        ("appstore", [], None),
        ("development", ["cert"], None),
        ("adhoc", ["cert"], []),
        ("appstore", ["cert"], ["device"]),
        ("enterprise", ["cert"], None),
        ("appstore", ["one", "two"], None),
    ],
)
def test_profile_rejects_invalid_inputs_without_network(
    kind: str,
    certificates: list[str],
    devices: list[str] | None,
) -> None:
    with api_client([]) as (client, requests), pytest.raises(InvalidArgumentsError):
        client.create_profile("Profile", "bundle", kind, certificates, devices)
    assert requests == []


def test_revoke_and_delete_use_delete_and_accept_204() -> None:
    with api_client([httpx.Response(204), httpx.Response(204)]) as (client, requests):
        client.revoke_certificate("cert-1")
        client.delete_profile("profile-1")
    assert [(r.method, r.url.path) for r in requests] == [
        ("DELETE", "/v1/certificates/cert-1"),
        ("DELETE", "/v1/profiles/profile-1"),
    ]


def test_valid_downloads_decode_to_der(signing_material: tuple[str, bytes, bytes]) -> None:
    _, certificate, profile = signing_material
    with api_client(
        [
            {
                "data": resource(
                    "certificates", certificateContent=base64.b64encode(certificate).decode()
                )
            },
            {"data": resource("profiles", profileContent=base64.b64encode(profile).decode())},
        ]
    ) as (client, _):
        assert client.download_certificate("id-1") == certificate
        assert client.download_profile("id-1") == profile


@pytest.mark.parametrize("value", [None, "", "invalid base64", "PGh0bWw+ZXJyb3I8L2h0bWw+"])
@pytest.mark.parametrize(
    "kind,field,method",
    [
        ("certificates", "certificateContent", "download_certificate"),
        ("profiles", "profileContent", "download_profile"),
    ],
)
def test_downloads_reject_missing_or_invalid_content(
    value: Any, kind: str, field: str, method: str
) -> None:
    with (
        api_client([{"data": resource(kind, **{field: value})}]) as (client, _),
        pytest.raises(AppStoreConnectError),
    ):
        getattr(client, method)("id-1")


def test_devices_discovery_and_registration_use_public_resources() -> None:
    device = resource(
        "devices", "device-1", name="Phone", udid="UDID", platform="IOS", status="ENABLED"
    )
    with api_client([{"data": [device]}, {"data": device}]) as (client, requests):
        assert client.list_devices() == [device]
        assert client.register_device("Phone", "UDID", "ios") == device
    assert requests[0].url.path == "/v1/devices"
    assert json.loads(requests[1].content) == {
        "data": {
            "type": "devices",
            "attributes": {"name": "Phone", "udid": "UDID", "platform": "IOS"},
        }
    }
