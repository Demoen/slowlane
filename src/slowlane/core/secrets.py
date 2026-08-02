"""Secure secrets storage with keyring and encrypted fallback."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import get_data_dir
from .errors import SecretStorageError


def hash_email(email: str) -> str:
    """Hash an email address for storage (never store plaintext)."""
    return hashlib.sha256(email.lower().encode()).hexdigest()[:16]


@dataclass
class SessionData:
    """Session data with metadata."""

    cookies: dict[str, str]
    email_hash: str
    created_at: datetime
    verified_at: datetime | None = None
    target_service: str = "appstoreconnect"

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "cookies": self.cookies,
            "email_hash": self.email_hash,
            "created_at": self.created_at.isoformat(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "target_service": self.target_service,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionData:
        """Create from dictionary."""
        return cls(
            cookies=data["cookies"],
            email_hash=data["email_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            verified_at=(
                datetime.fromisoformat(data["verified_at"]) if data.get("verified_at") else None
            ),
            target_service=data.get("target_service", "appstoreconnect"),
        )


class SecretBackend(ABC):
    """Abstract base class for secret storage backends."""

    @abstractmethod
    def store(self, key: str, value: str) -> None:
        """Store a secret."""
        ...

    @abstractmethod
    def retrieve(self, key: str) -> str | None:
        """Retrieve a secret."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a secret."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a secret exists."""
        ...


class KeyringBackend(SecretBackend):
    """Store secrets in OS keychain via keyring."""

    SERVICE_NAME = "slowlane"

    def __init__(self) -> None:
        try:
            import keyring

            self._keyring = keyring
            backend = keyring.get_keyring()
            if backend.priority <= 0:
                raise SecretStorageError(f"Keyring backend is not usable: {type(backend).__name__}")
        except SecretStorageError:
            raise
        except Exception as e:
            raise SecretStorageError(f"Keyring not available: {e}") from e

    def store(self, key: str, value: str) -> None:
        """Store a secret in the keychain."""
        try:
            self._keyring.set_password(self.SERVICE_NAME, key, value)
        except Exception as e:
            raise SecretStorageError(f"Failed to store secret: {e}", key=key) from e

    def retrieve(self, key: str) -> str | None:
        """Retrieve a secret from the keychain."""
        try:
            return self._keyring.get_password(self.SERVICE_NAME, key)
        except Exception as e:
            raise SecretStorageError(f"Failed to retrieve secret: {e}", key=key) from e

    def delete(self, key: str) -> None:
        """Delete a secret from the keychain."""
        if self.retrieve(key) is None:
            return
        try:
            self._keyring.delete_password(self.SERVICE_NAME, key)
        except Exception as e:
            raise SecretStorageError(f"Failed to delete secret: {e}", key=key) from e

    def exists(self, key: str) -> bool:
        """Check if a secret exists in the keychain."""
        return self.retrieve(key) is not None


class EncryptedFileBackend(SecretBackend):
    """Encrypt fallback files with a colocated, permission-restricted key.

    This does not protect against processes running as the same account.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or get_data_dir() / "secrets"
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._set_permissions(self._storage_dir, 0o700)
            for secret_path in self._storage_dir.glob("*.enc"):
                if secret_path.is_file():
                    self._set_permissions(secret_path, 0o600)
            self._fernet = self._get_fernet()
        except SecretStorageError:
            raise
        except Exception as e:
            raise SecretStorageError(f"Failed to initialize encrypted storage: {e}") from e

    @staticmethod
    def _set_permissions(path: Path, mode: int) -> None:
        if os.name == "posix":
            os.chmod(path, mode)

    def _sync_storage_dir(self) -> None:
        if os.name != "posix":
            return

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        with contextlib.suppress(OSError):
            directory_fd = os.open(self._storage_dir, flags)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

    def _write_temporary_file(self, data: bytes, prefix: str) -> Path:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self._storage_dir,
            prefix=prefix,
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)

        try:
            if os.name == "posix":
                os.fchmod(file_descriptor, 0o600)
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                file_descriptor = -1
                temporary_file.write(data)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            return temporary_path
        except Exception:
            if file_descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(file_descriptor)
            with contextlib.suppress(OSError):
                temporary_path.unlink()
            raise

    def _atomic_write(self, path: Path, data: bytes) -> None:
        temporary_path = self._write_temporary_file(data, f".{path.name}.")
        try:
            os.replace(temporary_path, path)
            self._sync_storage_dir()
        finally:
            with contextlib.suppress(OSError):
                temporary_path.unlink()

    def _get_encryption_key_path(self) -> Path:
        """Get path to encryption key file."""
        return self._storage_dir / ".key"

    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        """Derive encryption key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    def _get_fernet(self) -> Fernet:
        """Get or create Fernet instance for encryption."""
        key_path = self._get_encryption_key_path()

        if key_path.exists():
            self._set_permissions(key_path, 0o600)
        else:
            temporary_path = self._write_temporary_file(Fernet.generate_key(), ".key.")
            try:
                try:
                    os.link(temporary_path, key_path)
                except FileExistsError:
                    pass
                else:
                    self._sync_storage_dir()
            finally:
                with contextlib.suppress(OSError):
                    temporary_path.unlink()

            self._set_permissions(key_path, 0o600)

        key = key_path.read_bytes()
        return Fernet(key)

    def _get_secret_path(self, key: str) -> Path:
        """Get path to secret file."""
        safe_key = hashlib.sha256(key.encode()).hexdigest()
        return self._storage_dir / f"{safe_key}.enc"

    def store(self, key: str, value: str) -> None:
        """Store an encrypted secret."""
        try:
            encrypted = self._fernet.encrypt(value.encode())
            path = self._get_secret_path(key)
            self._atomic_write(path, encrypted)
        except Exception as e:
            raise SecretStorageError(f"Failed to store secret: {e}", key=key) from e

    def retrieve(self, key: str) -> str | None:
        """Retrieve and decrypt a secret."""
        path = self._get_secret_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                encrypted = f.read()
            return self._fernet.decrypt(encrypted).decode()
        except Exception as e:
            raise SecretStorageError(f"Failed to retrieve secret: {e}", key=key) from e

    def delete(self, key: str) -> None:
        """Delete a secret file."""
        path = self._get_secret_path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        """Check if a secret file exists."""
        return self._get_secret_path(key).exists()


class SecretStore:
    """High-level secret storage with automatic backend selection."""

    DEFAULT_SESSION_KEY = "session:default"

    def __init__(self, backend: SecretBackend | None = None) -> None:
        if backend is not None:
            self._backend = backend
        else:
            # Try keyring first, fall back to encrypted files
            try:
                self._backend = KeyringBackend()
            except SecretStorageError:
                self._backend = EncryptedFileBackend()

    def store_api_key(self, key_id: str, private_key: str) -> None:
        """Store an API private key."""
        self._backend.store(f"api_key:{key_id}", private_key)

    def retrieve_api_key(self, key_id: str) -> str | None:
        """Retrieve an API private key."""
        return self._backend.retrieve(f"api_key:{key_id}")

    def delete_api_key(self, key_id: str) -> None:
        """Delete an API private key."""
        self._backend.delete(f"api_key:{key_id}")

    def store_session(self, email: str, session: SessionData) -> None:
        """Store session data for an account."""
        email_hash = hash_email(email)
        session.email_hash = email_hash
        data = json.dumps(session.to_dict())
        self._backend.store(f"session:{email_hash}", data)
        self._backend.store(self.DEFAULT_SESSION_KEY, email_hash)

    def retrieve_session(self, email: str) -> SessionData | None:
        """Retrieve session data for an account."""
        email_hash = hash_email(email)
        data = self._backend.retrieve(f"session:{email_hash}")
        if data is None:
            return None
        return SessionData.from_dict(json.loads(data))

    def retrieve_session_by_hash(self, email_hash: str) -> SessionData | None:
        """Retrieve session data by email hash."""
        data = self._backend.retrieve(f"session:{email_hash}")
        if data is None:
            return None
        return SessionData.from_dict(json.loads(data))

    def retrieve_default_session(self) -> SessionData | None:
        """Retrieve the most recently stored session."""
        email_hash = self._backend.retrieve(self.DEFAULT_SESSION_KEY)
        if not email_hash:
            return None
        return self.retrieve_session_by_hash(email_hash)

    def delete_session(self, email: str) -> None:
        """Delete session data for an account."""
        email_hash = hash_email(email)
        self._backend.delete(f"session:{email_hash}")
        if self._backend.retrieve(self.DEFAULT_SESSION_KEY) == email_hash:
            self._backend.delete(self.DEFAULT_SESSION_KEY)

    def update_session_verified(self, email: str) -> None:
        """Update session's last verified timestamp."""
        session = self.retrieve_session(email)
        if session:
            session.verified_at = datetime.now(UTC)
            self.store_session(email, session)
