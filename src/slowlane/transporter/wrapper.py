"""iTunes Transporter wrapper for IPA/pkg uploads."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from slowlane.core.errors import TransporterError

logger = logging.getLogger(__name__)


def _is_usable_transporter(path: Path) -> bool:
    try:
        return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))
    except OSError:
        return False


def find_transporter() -> Path | None:
    """Find the iTMSTransporter binary.

    Searches in order:
    1. TRANSPORTER_PATH environment variable
    2. Xcode bundled transporter (macOS)
    3. Transporter.app (macOS)
    4. PATH

    Returns:
        Path to transporter binary, or None if not found
    """
    if env_path := os.environ.get("TRANSPORTER_PATH"):
        path = Path(env_path)
        if _is_usable_transporter(path):
            return path

    if sys.platform == "darwin":
        xcode_paths = [
            "/Applications/Xcode.app/Contents/SharedFrameworks/ContentDeliveryServices.framework/"
            "Versions/A/itms/bin/iTMSTransporter",
            "/Applications/Xcode.app/Contents/Developer/usr/bin/altool",
        ]

        for xcode_path in xcode_paths:
            path = Path(xcode_path)
            if _is_usable_transporter(path):
                return path

        transporter_app = Path("/Applications/Transporter.app/Contents/itms/bin/iTMSTransporter")
        if _is_usable_transporter(transporter_app):
            return transporter_app

    import shutil

    if which_path := shutil.which("iTMSTransporter"):
        path = Path(which_path)
        if _is_usable_transporter(path):
            return path
    if which_path := shutil.which("altool"):
        path = Path(which_path)
        if _is_usable_transporter(path):
            return path

    return None


class TransporterWrapper:
    """Wrapper for Apple's iTMSTransporter."""

    def __init__(
        self,
        transporter_path: Path | None = None,
        key_id: str | None = None,
        issuer_id: str | None = None,
        private_key_path: str | None = None,
        private_key: str | None = None,
        jwt_token: str | None = None,
        jwt_token_provider: Callable[[], str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize transporter wrapper.

        Args:
            transporter_path: Path to transporter binary (auto-detected if None)
            key_id: App Store Connect API Key ID
            issuer_id: App Store Connect Issuer ID
            private_key_path: Path to .p8 private key file
            private_key: Contents of the .p8 private key
            jwt_token: Signed JWT for iTMSTransporter authentication
            jwt_token_provider: Supplies a fresh JWT for each command
            verbose: Enable verbose output
        """
        self._transporter_path = transporter_path or find_transporter()
        self._key_id = key_id or os.environ.get("ASC_KEY_ID")
        self._issuer_id = issuer_id or os.environ.get("ASC_ISSUER_ID")
        self._private_key_path = private_key_path or os.environ.get("ASC_PRIVATE_KEY_PATH")
        self._private_key = private_key or os.environ.get("ASC_PRIVATE_KEY")
        self._jwt_token = jwt_token
        self._jwt_token_provider = jwt_token_provider
        self._verbose = verbose

        if not self._transporter_path or not self._transporter_path.is_file():
            raise TransporterError("iTMSTransporter not found")

    def _is_altool(self) -> bool:
        """Check if using altool instead of iTMSTransporter."""
        return self._transporter_path is not None and "altool" in self._transporter_path.name

    @staticmethod
    def _altool_platform(file_path: Path) -> str:
        return "macos" if file_path.suffix.lower() == ".pkg" else "ios"

    def _build_auth_args(self) -> list[str]:
        """Build authentication arguments for transporter."""
        if self._jwt_token_provider and not self._is_altool():
            self._jwt_token = self._jwt_token_provider()
        if self._jwt_token and not self._is_altool():
            return ["-jwt", self._jwt_token]

        if not self._key_id or not self._issuer_id:
            raise TransporterError(
                "API Key credentials required. Set ASC_KEY_ID, ASC_ISSUER_ID, and "
                "ASC_PRIVATE_KEY_PATH environment variables."
            )

        if self._is_altool():
            # altool uses different argument names
            args = [
                "--apiKey",
                self._key_id,
                "--apiIssuer",
                self._issuer_id,
            ]
        else:
            # iTMSTransporter
            args = [
                "-apiKey",
                self._key_id,
                "-apiIssuer",
                self._issuer_id,
            ]

        return args

    def _redact_sensitive(self, text: str) -> str:
        if self._jwt_token:
            return text.replace(self._jwt_token, "[REDACTED]")
        return text

    @contextmanager
    def _command_environment(self) -> Iterator[dict[str, str]]:
        environment = os.environ.copy()
        if not self._is_altool() or (not self._private_key and not self._private_key_path):
            yield environment
            return

        private_key = self._private_key
        if not private_key and self._private_key_path:
            key_path = Path(self._private_key_path).expanduser()
            try:
                private_key = key_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise TransporterError(f"Unable to read API private key: {key_path}") from exc
        if not private_key or not private_key.strip():
            raise TransporterError("API private key is empty")
        if not self._key_id:
            raise TransporterError("API key ID is required for altool")

        with tempfile.TemporaryDirectory(prefix="slowlane-altool-") as temporary_directory:
            directory = Path(temporary_directory)
            if os.name == "posix":
                os.chmod(directory, 0o700)
            key_path = directory / f"AuthKey_{self._key_id}.p8"
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
                key_file.write(private_key)
                key_file.flush()
                os.fsync(key_file.fileno())
            environment["API_PRIVATE_KEYS_DIR"] = str(directory)
            yield environment

    def _run_command(
        self,
        args: list[str],
        description: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run transporter command."""
        if not self._transporter_path:
            raise TransporterError("Transporter not configured")

        cmd = [str(self._transporter_path), *args]

        logger.info("Running: %s", self._redact_sensitive(" ".join(cmd)))

        try:
            with self._command_environment() as environment:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                    env=environment,
                )

            if self._verbose:
                if result.stdout:
                    logger.debug("stdout: %s", self._redact_sensitive(result.stdout))
                if result.stderr:
                    logger.debug("stderr: %s", self._redact_sensitive(result.stderr))

            if result.returncode != 0:
                output = self._redact_sensitive(f"{result.stdout}\n{result.stderr}")
                error_msg = self._parse_error(output)
                raise TransporterError(
                    f"{description} failed: {error_msg}",
                    exit_code=result.returncode,
                )

            return result

        except subprocess.TimeoutExpired as exc:
            raise TransporterError(f"{description} timed out after 1 hour") from exc
        except FileNotFoundError as exc:
            raise TransporterError(f"Transporter not found at {self._transporter_path}") from exc
        except OSError as exc:
            raise TransporterError(
                f"Unable to execute transporter at {self._transporter_path}: {exc}"
            ) from exc

    def _parse_error(self, output: str) -> str:
        """Parse transporter output for error messages."""
        # Look for common error patterns
        patterns = [
            r"ERROR ITMS-(\d+): (.+)",
            r"Error: (.+)",
            r"\*\*\*Error: (.+)",
            r"There was an error: (.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    return f"ITMS-{match.group(1)}: {match.group(2)}"
                return match.group(1)

        # Return last non-empty line as fallback
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        return lines[-1] if lines else "Unknown error"

    def validate(self, file_path: Path) -> None:
        """Validate an IPA/pkg without uploading.

        Args:
            file_path: Path to IPA or pkg file

        Raises:
            TransporterError: If validation fails
        """
        if not file_path.exists():
            raise TransporterError(f"File not found: {file_path}")

        if self._is_altool():
            args = [
                "--validate-app",
                "-f",
                str(file_path),
                "-t",
                self._altool_platform(file_path),
                *self._build_auth_args(),
            ]
        else:
            args = ["-m", "verify", "-assetFile", str(file_path), *self._build_auth_args()]

        self._run_command(args, "Validation")

    def upload(self, file_path: Path) -> None:
        """Upload an IPA/pkg to App Store Connect.

        Args:
            file_path: Path to IPA or pkg file

        Raises:
            TransporterError: If upload fails
        """
        if not file_path.exists():
            raise TransporterError(f"File not found: {file_path}")

        if self._is_altool():
            args = [
                "--upload-app",
                "-f",
                str(file_path),
                "-t",
                self._altool_platform(file_path),
                *self._build_auth_args(),
            ]
        else:
            args = ["-m", "upload", "-assetFile", str(file_path), *self._build_auth_args()]

        self._run_command(args, "Upload")

    def lookup(self, bundle_id: str) -> dict[str, Any]:
        """Look up app metadata by bundle ID.

        Args:
            bundle_id: App bundle identifier

        Returns:
            App metadata dictionary

        Raises:
            TransporterError: If lookup fails
        """
        if self._is_altool():
            # altool doesn't support lookup directly
            raise TransporterError("Lookup not supported with altool")

        args = ["-m", "lookupMetadata", "-apple_id", bundle_id, *self._build_auth_args()]

        result = self._run_command(args, "Lookup")

        # Parse XML output
        # For now, return raw output
        return {"output": result.stdout}
