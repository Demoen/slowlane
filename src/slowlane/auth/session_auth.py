"""Session-based authentication for Apple services."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from slowlane.core.secrets import SecretStore, SessionData, hash_email


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
        session_str = os.environ.get("FASTLANE_SESSION")
        if not session_str:
            return None

        try:
            # Try base64 decode first
            try:
                decoded = base64.b64decode(session_str).decode("utf-8")
                data = json.loads(decoded)
            except Exception:
                # Fall back to direct JSON
                data = json.loads(session_str)

            cookies = data.get("cookies", data)
            email_hash = data.get("email_hash", "unknown")
            created_at_str = data.get("created_at")

            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str)
            else:
                created_at = datetime.now(UTC)

            if isinstance(cookies, dict):
                return cls(
                    cookies=cookies,
                    email_hash=email_hash,
                    created_at=created_at,
                )
        except Exception:
            pass

        return None


class SessionAuth:
    """Session-based authentication manager."""

    # Required cookies for Apple session
    REQUIRED_COOKIES: ClassVar[list[str]] = ["myacinfo", "DES"]

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
        age = datetime.now(UTC) - self._session_data.created_at.replace(
            tzinfo=UTC
        )
        return age.days >= self.STALE_THRESHOLD_DAYS

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
    1. FASTLANE_SESSION environment variable
    2. Stored session for email
    """
    # Try environment first
    creds = SessionCredentials.from_env()
    if creds:
        session_data = SessionData(
            cookies=creds.cookies,
            email_hash=creds.email_hash,
            created_at=creds.created_at,
        )
        return SessionAuth(session_data)

    # Try secret store
    if email and secret_store:
        session_data = secret_store.retrieve_session(email)
        if session_data:
            return SessionAuth(session_data)

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
