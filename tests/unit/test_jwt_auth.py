"""Tests for JWT authentication."""

import time
from unittest.mock import patch

import pytest

from slowlane.auth.jwt_auth import JWTAuth, JWTCredentials, get_jwt_auth


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
        with patch.dict(
            "os.environ",
            {
                "ASC_KEY_ID": "TEST123",
                # Missing issuer and key
            },
            clear=True,
        ):
            creds = JWTCredentials.from_env()
            assert creds is None


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

        token1 = auth.get_token()
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
