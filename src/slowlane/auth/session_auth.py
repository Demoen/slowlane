"""Session-based authentication for Apple services."""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from slowlane.core.errors import SessionError
from slowlane.core.secrets import SecretStore, SessionData, hash_email

REQUIRED_SESSION_COOKIES = ("myacinfo", "DES")


@dataclass
class SessionCredentials:
    """Session cookie credentials."""

    cookies: dict[str, str]
    email_hash: str
    created_at: datetime

    @classmethod
    def from_env(cls) -> SessionCredentials | None:
        """Load session from FASTLANE_SESSION environment variable.

        The FASTLANE_SESSION format is base64-encoded JSON containing cookies.
        """
        if "FASTLANE_SESSION" not in os.environ:
            return None
        session_str = os.environ["FASTLANE_SESSION"]
        if not session_str:
            raise SessionError("FASTLANE_SESSION is set but empty")

        try:
            decoded = base64.b64decode(session_str, validate=True).decode("utf-8")
            data = json.loads(decoded)
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise SessionError("FASTLANE_SESSION is not valid exported session data") from exc

        if not isinstance(data, dict):
            raise SessionError("FASTLANE_SESSION must contain a session object")

        cookies = data.get("cookies")
        email_hash = data.get("email_hash")
        created_at_raw = data.get("created_at")
        if not isinstance(cookies, dict) or not cookies:
            raise SessionError("FASTLANE_SESSION does not contain valid cookies")
        if any(
            not isinstance(key, str) or not key or not isinstance(value, str) or not value
            for key, value in cookies.items()
        ):
            raise SessionError("FASTLANE_SESSION contains invalid cookie values")
        if any(cookie not in cookies for cookie in REQUIRED_SESSION_COOKIES):
            raise SessionError("FASTLANE_SESSION is missing required Apple cookies")
        if not isinstance(email_hash, str) or not email_hash:
            raise SessionError("FASTLANE_SESSION does not contain a valid account identifier")
        if not isinstance(created_at_raw, str):
            raise SessionError("FASTLANE_SESSION does not contain a valid creation timestamp")

        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError as exc:
            raise SessionError("FASTLANE_SESSION has an invalid creation timestamp") from exc
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise SessionError("FASTLANE_SESSION creation timestamp must include a timezone")

        return cls(cookies=cookies, email_hash=email_hash, created_at=created_at)


class SessionAuth:
    """Session-based authentication manager."""

    # Required cookies for Apple session
    REQUIRED_COOKIES: ClassVar[tuple[str, ...]] = REQUIRED_SESSION_COOKIES

    # Session considered stale after 7 days
    STALE_THRESHOLD_DAYS = 7

    def __init__(self, session_data: SessionData) -> None:
        self._session_data = session_data

    @property
    def cookies(self) -> dict[str, str]:
        """Get session cookies."""
        return self._session_data.cookies

    @property
    def email_hash(self) -> str:
        """Get email hash."""
        return self._session_data.email_hash

    @property
    def created_at(self) -> datetime:
        """Get session creation time."""
        return self._session_data.created_at

    @property
    def is_stale(self) -> bool:
        """Check if session is stale and should be refreshed."""
        created_at = self._session_data.created_at
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)
        age = datetime.now(UTC) - created_at
        return age >= timedelta(days=self.STALE_THRESHOLD_DAYS)

    def validate(self) -> bool:
        """Basic validation of session cookies."""
        return all(cookie in self._session_data.cookies for cookie in self.REQUIRED_COOKIES)

    def to_export_string(self) -> str:
        """Export session as FASTLANE_SESSION-compatible string."""
        data = self._session_data.to_dict()
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


def get_session_auth(
    email: str | None = None,
    secret_store: SecretStore | None = None,
) -> SessionAuth | None:
    """Get session auth from environment or secret store.

    Priority:
    1. Explicitly requested stored account
    2. FASTLANE_SESSION environment variable
    3. Default stored account
    """
    if email:
        if secret_store is None:
            return None
        stored = secret_store.retrieve_session(email)
        return SessionAuth(stored) if stored else None

    creds = SessionCredentials.from_env()
    if creds:
        session_data = SessionData(
            cookies=creds.cookies,
            email_hash=creds.email_hash,
            created_at=creds.created_at,
        )
        return SessionAuth(session_data)

    if secret_store:
        stored = secret_store.retrieve_default_session()
        if stored:
            return SessionAuth(stored)

    return None


def create_session_from_cookies(
    cookies: dict[str, str],
    email: str,
    target_service: str = "appstoreconnect",
) -> SessionData:
    """Create a new session from extracted cookies."""
    return SessionData(
        cookies=cookies,
        email_hash=hash_email(email),
        created_at=datetime.now(UTC),
        target_service=target_service,
    )


def validate_session_cookies(cookies: dict[str, str]) -> list[str]:
    """Validate session cookies and return list of missing required cookies."""
    missing = []
    for cookie in SessionAuth.REQUIRED_COOKIES:
        if cookie not in cookies:
            missing.append(cookie)
    return missing
