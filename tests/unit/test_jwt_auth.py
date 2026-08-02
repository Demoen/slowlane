"""Tests for JWT authentication."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slowlane.auth.jwt_auth import JWTAuth, JWTCredentials, get_jwt_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import JWTError

# Sample test key (DO NOT USE IN PRODUCTION - this is for testing only)
# Generated with: cryptography.hazmat.primitives.asymmetric.ec.generate_private_key(ec.SECP256R1())
TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgwpYnR6cRM3lnAcVT
/+ndqQBNiU12gtzJn7Nki7n4pWqhRANCAARTJgUm8yJZuDUl6q10TCzmsbr8UkBN
fIRLxfq+JlWdRr3NX55hlG65Ac9SVyb0vYK5ZRRyfez6EoMCp+dPfQuc
-----END PRIVATE KEY-----"""


class TestJWTCredentials:
    """Tests for JWTCredentials."""

    def test_from_env_complete(self) -> None:
        """Test loading credentials from environment."""
        with patch.dict(
            "os.environ",
            {
                "ASC_KEY_ID": "TEST123",
                "ASC_ISSUER_ID": "issuer-456",
                "ASC_PRIVATE_KEY": TEST_PRIVATE_KEY,
            },
        ):
            creds = JWTCredentials.from_env()
            assert creds is not None
            assert creds.key_id == "TEST123"
            assert creds.issuer_id == "issuer-456"
            assert "PRIVATE KEY" in creds.private_key

    def test_from_env_missing(self) -> None:
        """Test missing environment variables."""
        with patch.dict("os.environ", {}, clear=True):
            creds = JWTCredentials.from_env()
            assert creds is None

    def test_from_env_partial(self) -> None:
        """Test partial environment variables."""
        with (
            patch.dict("os.environ", {"ASC_KEY_ID": "TEST123"}, clear=True),
            pytest.raises(JWTError, match="ASC_ISSUER_ID"),
        ):
            JWTCredentials.from_env()

    def test_from_env_rejects_unreadable_key_path(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "missing.p8"
        with (
            patch.dict(
                "os.environ",
                {
                    "ASC_KEY_ID": "TEST123",
                    "ASC_ISSUER_ID": "issuer-456",
                    "ASC_PRIVATE_KEY_PATH": str(missing_path),
                },
                clear=True,
            ),
            pytest.raises(JWTError, match="Unable to read"),
        ):
            JWTCredentials.from_env()

    def test_from_config_wraps_unreadable_key_path(self, tmp_path: Path) -> None:
        config = SlowlaneConfig()
        config.auth.key_id = "TEST123"
        config.auth.issuer_id = "issuer-456"
        config.auth.private_key_path = str(tmp_path)

        with pytest.raises(JWTError, match="Unable to read API private key"):
            JWTCredentials.from_config(config)

    def test_from_config_rejects_empty_key_file(self, tmp_path: Path) -> None:
        key_path = tmp_path / "empty.p8"
        key_path.write_text(" \n", encoding="utf-8")
        config = SlowlaneConfig()
        config.auth.key_id = "TEST123"
        config.auth.issuer_id = "issuer-456"
        config.auth.private_key_path = str(key_path)

        with pytest.raises(JWTError, match="private key file is empty"):
            JWTCredentials.from_config(config)


class TestJWTAuth:
    """Tests for JWTAuth."""

    def test_token_generation(self) -> None:
        """Test JWT token generation."""
        creds = JWTCredentials(
            key_id="TEST123",
            issuer_id="issuer-456",
            private_key=TEST_PRIVATE_KEY,
        )
        auth = JWTAuth(creds)

        token = auth.get_token()
        assert token is not None
        assert len(token) > 0
        # JWT has 3 parts separated by dots
        assert len(token.split(".")) == 3

    def test_token_caching(self) -> None:
        """Test that tokens are cached."""
        creds = JWTCredentials(
            key_id="TEST123",
            issuer_id="issuer-456",
            private_key=TEST_PRIVATE_KEY,
        )
        auth = JWTAuth(creds)

        token1 = auth.get_token()
        token2 = auth.get_token()
        assert token1 == token2  # Same token returned

    def test_token_invalidation(self) -> None:
        """Test token invalidation."""
        creds = JWTCredentials(
            key_id="TEST123",
            issuer_id="issuer-456",
            private_key=TEST_PRIVATE_KEY,
        )
        auth = JWTAuth(creds)

        auth.get_token()
        auth.invalidate()
        token2 = auth.get_token()

        # New token after invalidation
        # (may be same if generated in same second, so just check it exists)
        assert token2 is not None


class TestGetJWTAuth:
    """Tests for get_jwt_auth helper."""

    def test_from_env(self) -> None:
        """Test getting auth from environment."""
        with patch.dict(
            "os.environ",
            {
                "ASC_KEY_ID": "TEST123",
                "ASC_ISSUER_ID": "issuer-456",
                "ASC_PRIVATE_KEY": TEST_PRIVATE_KEY,
            },
        ):
            auth = get_jwt_auth()
            assert auth is not None
            assert auth.key_id == "TEST123"

    def test_returns_none_when_not_configured(self) -> None:
        """Test returns None when not configured."""
        with patch.dict("os.environ", {}, clear=True):
            auth = get_jwt_auth()
            assert auth is None

    def test_loads_keyring_only_credentials_on_store_retry(self) -> None:
        config = SlowlaneConfig()
        config.auth.key_id = "TEST123"
        config.auth.issuer_id = "issuer-456"
        secret_store = MagicMock()
        secret_store.retrieve_api_key.return_value = TEST_PRIVATE_KEY

        with patch.dict("os.environ", {}, clear=True):
            assert get_jwt_auth(config) is None
            auth = get_jwt_auth(config, secret_store)

        assert auth is not None
        assert auth.key_id == "TEST123"
        secret_store.retrieve_api_key.assert_called_once_with("TEST123")

    def test_partial_environment_does_not_fall_back_to_config(self) -> None:
        with (
            patch.dict("os.environ", {"ASC_KEY_ID": "wrong-account"}, clear=True),
            patch.object(JWTCredentials, "from_config") as from_config,
            pytest.raises(JWTError, match="ASC_ISSUER_ID"),
        ):
            get_jwt_auth(SlowlaneConfig())

        from_config.assert_not_called()
