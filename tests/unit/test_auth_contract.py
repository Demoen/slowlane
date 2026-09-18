from pathlib import Path
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from slowlane.auth.jwt_auth import JWTAuth, JWTCredentials, get_jwt_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import JWTError
from tests.unit.test_jwt_auth import TEST_PRIVATE_KEY


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in JWTCredentials.ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("key_type", ["team", "individual"])
def test_signed_claims_match_apple_contract(key_type: str) -> None:
    credentials = JWTCredentials(
        "KEY123", "issuer" if key_type == "team" else None, TEST_PRIVATE_KEY, key_type
    )
    auth = JWTAuth(credentials)
    public_key = serialization.load_pem_private_key(TEST_PRIVATE_KEY.encode(), None).public_key()
    token = auth.get_token()
    payload = jwt.decode(token, public_key, algorithms=["ES256"], audience="appstoreconnect-v1")
    assert jwt.get_unverified_header(token) == {"alg": "ES256", "kid": "KEY123", "typ": "JWT"}
    assert payload["exp"] - payload["iat"] == 1200
    if key_type == "team":
        assert payload["iss"] == "issuer"
        assert "sub" not in payload
    else:
        assert payload["sub"] == "user"
        assert "iss" not in payload
    assert TEST_PRIVATE_KEY not in repr(credentials)


def test_partial_environment_overrides_merge_with_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_path = tmp_path / "key.p8"
    key_path.write_text(TEST_PRIVATE_KEY)
    config = SlowlaneConfig()
    config.auth.key_id = "OLD_KEY"
    config.auth.issuer_id = "issuer"
    config.auth.private_key_path = str(key_path)
    monkeypatch.setenv("ASC_KEY_ID", "NEW_KEY")
    auth = get_jwt_auth(config)
    assert auth is not None
    assert auth.key_id == "NEW_KEY"
    assert auth.issuer_id == "issuer"


def test_private_key_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = SlowlaneConfig()
    config.auth.key_id = "KEY123"
    config.auth.issuer_id = "issuer"
    config.auth.private_key_path = str(tmp_path / "missing.p8")
    store = MagicMock()
    monkeypatch.setenv("ASC_PRIVATE_KEY", TEST_PRIVATE_KEY)
    auth = get_jwt_auth(config, store)
    assert auth is not None
    store.retrieve_api_key.assert_not_called()
    monkeypatch.delenv("ASC_PRIVATE_KEY")
    with pytest.raises(JWTError, match="Unable to read"):
        get_jwt_auth(config, store)
    store.retrieve_api_key.assert_not_called()
    path = tmp_path / "environment.p8"
    path.write_text(TEST_PRIVATE_KEY)
    monkeypatch.setenv("ASC_PRIVATE_KEY_PATH", str(path))
    assert get_jwt_auth(config, store) is not None
    store.retrieve_api_key.assert_not_called()


@pytest.mark.parametrize("variable", JWTCredentials.ENVIRONMENT_VARIABLES)
def test_explicit_empty_environment_is_rejected(
    variable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SlowlaneConfig()
    config.auth.key_id = "KEY123"
    config.auth.issuer_id = "issuer"
    monkeypatch.setenv(variable, " ")
    with pytest.raises(JWTError, match=variable):
        get_jwt_auth(config)


def test_individual_key_rejects_stale_issuer() -> None:
    with pytest.raises(JWTError, match="do not use an issuer"):
        JWTAuth(JWTCredentials("KEY123", "issuer", TEST_PRIVATE_KEY, "individual"))


def test_rejects_wrong_curve_and_invalid_private_key() -> None:
    key = (
        ec.generate_private_key(ec.SECP384R1())
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    for private_key in (key, "invalid-secret-marker"):
        with pytest.raises(JWTError) as error:
            JWTAuth(JWTCredentials("KEY123", "issuer", private_key))
        assert private_key not in str(error.value)


def test_expiring_token_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("slowlane.auth.jwt_auth.time.time", lambda: 1000)
    auth = JWTAuth(JWTCredentials("KEY123", "issuer", TEST_PRIVATE_KEY))
    first = auth.get_token()
    monkeypatch.setattr("slowlane.auth.jwt_auth.time.time", lambda: 1901)
    second = auth.get_token()
    assert jwt.decode(first, options={"verify_signature": False})["iat"] == 1000
    assert jwt.decode(second, options={"verify_signature": False})["iat"] == 1901
