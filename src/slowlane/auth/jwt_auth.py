"""JWT authentication for App Store Connect API."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import jwt

from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import JWTError
from slowlane.core.secrets import SecretStore


@dataclass
class JWTCredentials:
    """App Store Connect API key credentials."""

    ENVIRONMENT_VARIABLES: ClassVar[tuple[str, ...]] = (
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY",
        "ASC_PRIVATE_KEY_PATH",
    )

    key_id: str
    issuer_id: str
    private_key: str

    @classmethod
    def from_env(cls) -> JWTCredentials | None:
        """Load credentials from environment variables."""
        if not any(name in os.environ for name in cls.ENVIRONMENT_VARIABLES):
            return None

        key_id = os.environ.get("ASC_KEY_ID", "").strip()
        issuer_id = os.environ.get("ASC_ISSUER_ID", "").strip()
        private_key = os.environ.get("ASC_PRIVATE_KEY")
        key_path_value = os.environ.get("ASC_PRIVATE_KEY_PATH")

        if not key_id or not issuer_id:
            raise JWTError("ASC_KEY_ID and ASC_ISSUER_ID must both be set")
        if private_key is not None and not private_key.strip():
            raise JWTError("ASC_PRIVATE_KEY is set but empty")
        if key_path_value is not None and not key_path_value.strip():
            raise JWTError("ASC_PRIVATE_KEY_PATH is set but empty")

        if not private_key:
            if not key_path_value:
                raise JWTError("Set ASC_PRIVATE_KEY or ASC_PRIVATE_KEY_PATH")
            key_path = Path(key_path_value).expanduser()
            try:
                private_key = key_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise JWTError(f"Unable to read ASC_PRIVATE_KEY_PATH: {key_path}") from exc
            if not private_key.strip():
                raise JWTError("ASC_PRIVATE_KEY_PATH points to an empty file")

        return cls(key_id=key_id, issuer_id=issuer_id, private_key=private_key)

    @classmethod
    def from_config(
        cls, config: SlowlaneConfig, secret_store: SecretStore | None = None
    ) -> JWTCredentials | None:
        """Load credentials from config and secret store."""
        key_id = (config.auth.key_id or "").strip()
        issuer_id = (config.auth.issuer_id or "").strip()

        if not key_id and not issuer_id:
            return None
        if not key_id or not issuer_id:
            raise JWTError("App Store Connect key ID and issuer ID must both be configured")

        private_key: str | None = None

        if secret_store:
            private_key = secret_store.retrieve_api_key(key_id)
            if private_key is not None and not private_key.strip():
                raise JWTError("Stored API private key is empty")

        key_path_value = config.auth.private_key_path
        if key_path_value is not None and not key_path_value.strip():
            raise JWTError("API private key path is empty")
        if not private_key and key_path_value:
            key_path = Path(key_path_value).expanduser()
            try:
                private_key = key_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise JWTError(f"Unable to read API private key: {key_path}") from exc
            if not private_key.strip():
                raise JWTError("API private key file is empty")

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

    @property
    def private_key(self) -> str:
        """Get the private key contents."""
        return self._credentials.private_key

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
