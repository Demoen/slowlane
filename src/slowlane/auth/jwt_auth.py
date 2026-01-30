"""JWT authentication for App Store Connect API."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import jwt

from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import JWTError
from slowlane.core.secrets import SecretStore


@dataclass
class JWTCredentials:
    """App Store Connect API key credentials."""

    key_id: str
    issuer_id: str
    private_key: str

    @classmethod
    def from_env(cls) -> JWTCredentials | None:
        """Load credentials from environment variables."""
        key_id = os.environ.get("ASC_KEY_ID")
        issuer_id = os.environ.get("ASC_ISSUER_ID")
        private_key = os.environ.get("ASC_PRIVATE_KEY")

        # Also check for key path
        if not private_key:
            key_path = os.environ.get("ASC_PRIVATE_KEY_PATH")
            if key_path and Path(key_path).exists():
                private_key = Path(key_path).read_text()

        if key_id and issuer_id and private_key:
            return cls(key_id=key_id, issuer_id=issuer_id, private_key=private_key)
        return None

    @classmethod
    def from_config(
        cls, config: SlowlaneConfig, secret_store: SecretStore | None = None
    ) -> JWTCredentials | None:
        """Load credentials from config and secret store."""
        key_id = config.auth.key_id
        issuer_id = config.auth.issuer_id

        if not key_id or not issuer_id:
            return None

        private_key: str | None = None

        # Try secret store first
        if secret_store:
            private_key = secret_store.retrieve_api_key(key_id)

        # Fall back to key path
        if not private_key and config.auth.private_key_path:
            key_path = Path(config.auth.private_key_path).expanduser()
            if key_path.exists():
                private_key = key_path.read_text()

        if private_key:
            return cls(key_id=key_id, issuer_id=issuer_id, private_key=private_key)
        return None


class JWTAuth:
    """JWT token generator for App Store Connect API."""

    # Token lifetime in seconds (max 20 minutes)
    TOKEN_LIFETIME = 20 * 60
    # Refresh token when less than this many seconds remain
    REFRESH_THRESHOLD = 5 * 60

    def __init__(self, credentials: JWTCredentials) -> None:
        self._credentials = credentials
        self._token: str | None = None
        self._token_expires_at: float = 0

    @property
    def key_id(self) -> str:
        """Get the key ID."""
        return self._credentials.key_id

    @property
    def issuer_id(self) -> str:
        """Get the issuer ID."""
        return self._credentials.issuer_id

    def _generate_token(self) -> str:
        """Generate a new JWT token."""
        now = time.time()

        headers = {
            "alg": "ES256",
            "kid": self._credentials.key_id,
            "typ": "JWT",
        }

        payload = {
            "iss": self._credentials.issuer_id,
            "iat": int(now),
            "exp": int(now + self.TOKEN_LIFETIME),
            "aud": "appstoreconnect-v1",
        }

        try:
            # Clean up the private key
            private_key = self._credentials.private_key.strip()

            token: str = jwt.encode(
                payload,
                private_key,
                algorithm="ES256",
                headers=headers,
            )

            self._token = token
            self._token_expires_at = now + self.TOKEN_LIFETIME

            return token

        except Exception as e:
            raise JWTError(f"Failed to generate JWT: {e}") from e

    def get_token(self) -> str:
        """Get a valid JWT token, generating a new one if needed."""
        now = time.time()

        # Check if we need a new token
        if self._token is None or now >= (self._token_expires_at - self.REFRESH_THRESHOLD):
            return self._generate_token()

        return self._token

    def invalidate(self) -> None:
        """Invalidate the current token."""
        self._token = None
        self._token_expires_at = 0


def get_jwt_auth(
    config: SlowlaneConfig | None = None,
    secret_store: SecretStore | None = None,
) -> JWTAuth | None:
    """Get JWT auth from environment or config.

    Priority:
    1. Environment variables (ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY)
    2. Config file + secret store
    """
    # Try environment first
    creds = JWTCredentials.from_env()
    if creds:
        return JWTAuth(creds)

    # Try config
    if config:
        creds = JWTCredentials.from_config(config, secret_store)
        if creds:
            return JWTAuth(creds)

    return None
