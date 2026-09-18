"""API-key credentials and short-lived App Store Connect tokens."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import JWTError
from slowlane.core.secrets import SecretStore


@dataclass
class JWTCredentials:
    ENVIRONMENT_VARIABLES: ClassVar[tuple[str, ...]] = (
        "ASC_KEY_TYPE",
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY",
        "ASC_PRIVATE_KEY_PATH",
    )

    key_id: str
    issuer_id: str | None
    private_key: str = field(repr=False)
    key_type: str = "team"

    @classmethod
    def from_env(cls) -> JWTCredentials | None:
        return cls.resolve(SlowlaneConfig())

    @classmethod
    def from_config(
        cls, config: SlowlaneConfig, secret_store: SecretStore | None = None
    ) -> JWTCredentials | None:
        return cls.resolve(config, secret_store, use_environment=False)

    @classmethod
    def resolve(
        cls,
        config: SlowlaneConfig,
        secret_store: SecretStore | None = None,
        *,
        use_environment: bool = True,
    ) -> JWTCredentials | None:
        environment = os.environ if use_environment else {}

        def value(name: str, fallback: str | None) -> str | None:
            raw = environment.get(name, fallback)
            if raw is not None and (not isinstance(raw, str) or not raw.strip()):
                raise JWTError(f"{name} must be a non-empty string")
            return raw.strip() if raw is not None else None

        key_type = value("ASC_KEY_TYPE", config.auth.key_type)
        key_id = value("ASC_KEY_ID", config.auth.key_id)
        issuer_id = value("ASC_ISSUER_ID", config.auth.issuer_id)
        key_path = value("ASC_PRIVATE_KEY_PATH", config.auth.private_key_path)
        private_key = value("ASC_PRIVATE_KEY", None)
        if key_type not in ("team", "individual"):
            raise JWTError("ASC_KEY_TYPE/auth.key_type must be 'team' or 'individual'")
        if not any((key_id, issuer_id, key_path, private_key)):
            return None
        if not key_id:
            raise JWTError("ASC_KEY_ID/auth.key_id is required")
        if key_type == "team" and not issuer_id:
            raise JWTError("ASC_ISSUER_ID/auth.issuer_id is required for team keys")
        if key_type == "individual" and issuer_id:
            raise JWTError(
                "Individual keys do not use an issuer ID; remove ASC_ISSUER_ID and auth.issuer_id"
            )
        if private_key is None and key_path is not None:
            path = Path(key_path).expanduser()
            try:
                private_key = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise JWTError(f"Unable to read API private key: {path}") from exc
            if not private_key.strip():
                raise JWTError("API private key file is empty")
        if private_key is None and secret_store is not None:
            private_key = secret_store.retrieve_api_key(key_id)
            if private_key is not None and not private_key.strip():
                raise JWTError("Stored API private key is empty")
        if private_key is None:
            return None
        return cls(key_id, issuer_id, private_key, key_type)


class JWTAuth:
    TOKEN_LIFETIME = 20 * 60
    REFRESH_THRESHOLD = 5 * 60

    def __init__(self, credentials: JWTCredentials) -> None:
        if credentials.key_type not in ("team", "individual"):
            raise JWTError("Unknown API key type")
        if not credentials.key_id or (credentials.key_type == "team" and not credentials.issuer_id):
            raise JWTError("A key ID and, for team keys, an issuer ID are required")
        if credentials.key_type == "individual" and credentials.issuer_id:
            raise JWTError("Individual keys do not use an issuer ID")
        try:
            key = serialization.load_pem_private_key(
                credentials.private_key.strip().encode(), password=None
            )
        except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
            raise JWTError("API private key must be an unencrypted P-256 PEM private key") from exc
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise JWTError("API private key must use the P-256 curve for ES256")
        self._credentials = credentials
        self._token: str | None = None
        self._token_expires_at: float = 0

    @property
    def key_id(self) -> str:
        return self._credentials.key_id

    @property
    def key_type(self) -> str:
        return self._credentials.key_type

    @property
    def issuer_id(self) -> str | None:
        return self._credentials.issuer_id

    @property
    def private_key(self) -> str:
        return self._credentials.private_key

    def _generate_token(self) -> str:
        now = time.time()
        payload: dict[str, str | int] = {
            "iat": int(now),
            "exp": int(now + self.TOKEN_LIFETIME),
            "aud": "appstoreconnect-v1",
        }
        if self.key_type == "individual":
            payload["sub"] = "user"
        elif self.issuer_id is not None:
            payload["iss"] = self.issuer_id
        try:
            token: str = jwt.encode(
                payload,
                self.private_key.strip(),
                algorithm="ES256",
                headers={"alg": "ES256", "kid": self.key_id, "typ": "JWT"},
            )
        except Exception as exc:
            raise JWTError("Failed to sign the App Store Connect token") from exc
        self._token = token
        self._token_expires_at = now + self.TOKEN_LIFETIME
        return token

    def get_token(self) -> str:
        if self._token is None or time.time() >= self._token_expires_at - self.REFRESH_THRESHOLD:
            return self._generate_token()
        return self._token

    def invalidate(self) -> None:
        self._token = None
        self._token_expires_at = 0


def get_jwt_auth(
    config: SlowlaneConfig | None = None, secret_store: SecretStore | None = None
) -> JWTAuth | None:
    credentials = JWTCredentials.resolve(config or SlowlaneConfig(), secret_store)
    return JWTAuth(credentials) if credentials is not None else None
