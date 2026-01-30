"""Tests for secrets storage."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from slowlane.core.secrets import (
    EncryptedFileBackend,
    SecretStore,
    SessionData,
    hash_email,
)


class TestHashEmail:
    """Tests for email hashing."""

    def test_hash_email(self) -> None:
        """Test email hashing produces consistent output."""
        email = "test@example.com"
        hash1 = hash_email(email)
        hash2 = hash_email(email)
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated to 16 chars

    def test_hash_email_case_insensitive(self) -> None:
        """Test email hashing is case insensitive."""
        assert hash_email("Test@Example.COM") == hash_email("test@example.com")


class TestSessionData:
    """Tests for SessionData."""

    def test_to_dict(self) -> None:
        """Test serializing to dictionary."""
        now = datetime.now(timezone.utc)
        session = SessionData(
            cookies={"myacinfo": "abc123"},
            email_hash="hash123",
            created_at=now,
            target_service="appstoreconnect",
        )

        d = session.to_dict()
        assert d["cookies"] == {"myacinfo": "abc123"}
        assert d["email_hash"] == "hash123"
        assert d["target_service"] == "appstoreconnect"

    def test_from_dict(self) -> None:
        """Test deserializing from dictionary."""
        data = {
            "cookies": {"myacinfo": "abc123"},
            "email_hash": "hash123",
            "created_at": "2024-01-01T00:00:00+00:00",
            "verified_at": None,
            "target_service": "appstoreconnect",
        }

        session = SessionData.from_dict(data)
        assert session.cookies == {"myacinfo": "abc123"}
        assert session.email_hash == "hash123"


class TestEncryptedFileBackend:
    """Tests for encrypted file backend."""

    def test_store_and_retrieve(self) -> None:
        """Test storing and retrieving secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            
            backend.store("test_key", "test_value")
            value = backend.retrieve("test_key")
            
            assert value == "test_value"

    def test_retrieve_nonexistent(self) -> None:
        """Test retrieving nonexistent key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            value = backend.retrieve("nonexistent")
            assert value is None

    def test_delete(self) -> None:
        """Test deleting secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            
            backend.store("test_key", "test_value")
            assert backend.exists("test_key")
            
            backend.delete("test_key")
            assert not backend.exists("test_key")

    def test_encryption_is_real(self) -> None:
        """Test that data is actually encrypted on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            backend.store("test_key", "secret_value")
            
            # Check that the file doesn't contain plaintext
            for file in Path(tmpdir).glob("*.enc"):
                content = file.read_bytes()
                assert b"secret_value" not in content


class TestSecretStore:
    """Tests for SecretStore."""

    def test_store_and_retrieve_api_key(self) -> None:
        """Test storing and retrieving API keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            store = SecretStore(backend)
            
            store.store_api_key("KEY123", "private_key_content")
            value = store.retrieve_api_key("KEY123")
            
            assert value == "private_key_content"

    def test_store_and_retrieve_session(self) -> None:
        """Test storing and retrieving sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            store = SecretStore(backend)
            
            session = SessionData(
                cookies={"myacinfo": "abc"},
                email_hash="",
                created_at=datetime.now(timezone.utc),
            )
            
            store.store_session("test@example.com", session)
            retrieved = store.retrieve_session("test@example.com")
            
            assert retrieved is not None
            assert retrieved.cookies == {"myacinfo": "abc"}

    def test_delete_session(self) -> None:
        """Test deleting sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = EncryptedFileBackend(Path(tmpdir))
            store = SecretStore(backend)
            
            session = SessionData(
                cookies={"myacinfo": "abc"},
                email_hash="",
                created_at=datetime.now(timezone.utc),
            )
            
            store.store_session("test@example.com", session)
            store.delete_session("test@example.com")
            
            assert store.retrieve_session("test@example.com") is None
