from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from slowlane.auth.session_auth import SessionAuth, SessionCredentials, get_session_auth
from slowlane.core.errors import SessionError
from slowlane.core.secrets import EncryptedFileBackend, SecretStore, SessionData


def _session(email_hash: str, created_at: datetime | None = None) -> SessionData:
    return SessionData(
        cookies={"myacinfo": f"myac-{email_hash}", "DES": f"des-{email_hash}"},
        email_hash=email_hash,
        created_at=created_at or datetime.now(UTC),
    )


def _encode(data: object) -> str:
    return base64.b64encode(json.dumps(data).encode()).decode()


def test_latest_stored_session_becomes_default(tmp_path: Path) -> None:
    store = SecretStore(EncryptedFileBackend(tmp_path))
    store.store_session("first@example.com", _session("first"))
    store.store_session("second@example.com", _session("second"))

    default_session = store.retrieve_default_session()

    assert default_session is not None
    assert default_session.cookies["myacinfo"] == "myac-second"
    assert store.retrieve_session("first@example.com") is not None


def test_deleting_default_session_clears_pointer(tmp_path: Path) -> None:
    store = SecretStore(EncryptedFileBackend(tmp_path))
    store.store_session("user@example.com", _session("user"))

    store.delete_session("user@example.com")

    assert store.retrieve_default_session() is None


def test_get_session_auth_uses_default_only_when_email_is_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FASTLANE_SESSION", raising=False)
    store = SecretStore(EncryptedFileBackend(tmp_path))
    store.store_session("user@example.com", _session("user"))

    default_auth = get_session_auth(secret_store=store)

    assert default_auth is not None
    assert default_auth.cookies["DES"] == "des-user"
    assert get_session_auth(email="missing@example.com", secret_store=store) is None


def test_session_credentials_round_trip_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _session("hash")
    monkeypatch.setenv("FASTLANE_SESSION", SessionAuth(expected).to_export_string())

    credentials = SessionCredentials.from_env()

    assert credentials is not None
    assert credentials.cookies == expected.cookies
    assert credentials.email_hash == "hash"
    assert credentials.created_at == expected.created_at


@pytest.mark.parametrize(
    "value",
    [
        "not-base64",
        json.dumps({"cookies": {"myacinfo": "a", "DES": "b"}}),
        _encode([]),
        _encode(
            {
                "cookies": {"myacinfo": "a"},
                "email_hash": "hash",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
        _encode(
            {
                "cookies": {"myacinfo": "a", "DES": 1},
                "email_hash": "hash",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
        _encode(
            {
                "cookies": {"myacinfo": "a", "DES": "b"},
                "email_hash": "hash",
                "created_at": "2026-08-02T12:00:00",
            }
        ),
    ],
)
def test_session_credentials_reject_malformed_values(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FASTLANE_SESSION", value)

    with pytest.raises(SessionError, match="FASTLANE_SESSION"):
        SessionCredentials.from_env()


def test_invalid_environment_session_does_not_fall_back_to_stored_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SecretStore(EncryptedFileBackend(tmp_path))
    store.store_session("user@example.com", _session("stored"))
    monkeypatch.setenv("FASTLANE_SESSION", "invalid")

    with pytest.raises(SessionError, match="FASTLANE_SESSION"):
        get_session_auth(secret_store=store)


def test_explicit_email_selects_stored_account_before_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SecretStore(EncryptedFileBackend(tmp_path))
    stored = _session("stored")
    environment = _session("environment")
    store.store_session("stored@example.com", stored)
    monkeypatch.setenv("FASTLANE_SESSION", SessionAuth(environment).to_export_string())

    explicit_auth = get_session_auth(email="stored@example.com", secret_store=store)
    default_auth = get_session_auth(secret_store=store)

    assert explicit_auth is not None
    assert explicit_auth.email_hash == stored.email_hash
    assert default_auth is not None
    assert default_auth.email_hash == environment.email_hash


def test_stale_check_preserves_timezone_offset() -> None:
    created_at = (datetime.now(UTC) - timedelta(days=6, hours=18)).astimezone(
        timezone(timedelta(hours=-12))
    )

    assert SessionAuth(_session("hash", created_at)).is_stale is False


def test_stale_check_accepts_legacy_naive_utc_timestamp() -> None:
    created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=8)

    assert SessionAuth(_session("hash", created_at)).is_stale is True
