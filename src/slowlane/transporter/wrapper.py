"""iTunes Transporter wrapper for IPA/pkg uploads."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from slowlane.core.errors import TransporterError

logger = logging.getLogger(__name__)


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
    # Check environment variable
    if env_path := os.environ.get("TRANSPORTER_PATH"):
        path = Path(env_path)
        if path.exists():
            return path

    if sys.platform == "darwin":
        # macOS: Check Xcode locations
        xcode_paths = [
            "/Applications/Xcode.app/Contents/SharedFrameworks/ContentDeliveryServices.framework/"
            "Versions/A/itms/bin/iTMSTransporter",
            "/Applications/Xcode.app/Contents/Developer/usr/bin/altool",  # Alternative
        ]

        for xcode_path in xcode_paths:
            path = Path(xcode_path)
            if path.exists():
                return path

        # Check Transporter.app
        transporter_app = Path(
            "/Applications/Transporter.app/Contents/itms/bin/iTMSTransporter"
        )
        if transporter_app.exists():
            return transporter_app

    # Check PATH
    import shutil

    if path := shutil.which("iTMSTransporter"):
        return Path(path)
    if path := shutil.which("altool"):
        return Path(path)

    return None


class TransporterWrapper:
    """Wrapper for Apple's iTMSTransporter."""

    def __init__(
        self,
        transporter_path: Path | None = None,
        key_id: str | None = None,
        issuer_id: str | None = None,
        private_key_path: str | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize transporter wrapper.

        Args:
            transporter_path: Path to transporter binary (auto-detected if None)
            key_id: App Store Connect API Key ID
            issuer_id: App Store Connect Issuer ID
            private_key_path: Path to .p8 private key file
            verbose: Enable verbose output
        """
        self._transporter_path = transporter_path or find_transporter()
        self._key_id = key_id or os.environ.get("ASC_KEY_ID")
        self._issuer_id = issuer_id or os.environ.get("ASC_ISSUER_ID")
        self._private_key_path = private_key_path or os.environ.get("ASC_PRIVATE_KEY_PATH")
        self._verbose = verbose

        if not self._transporter_path:
            raise TransporterError("iTMSTransporter not found")

    def _is_altool(self) -> bool:
        """Check if using altool instead of iTMSTransporter."""
        return self._transporter_path is not None and "altool" in self._transporter_path.name

    def _build_auth_args(self) -> list[str]:
        """Build authentication arguments for transporter."""
        if not self._key_id or not self._issuer_id:
            raise TransporterError(
                "API Key credentials required. Set ASC_KEY_ID, ASC_ISSUER_ID, and "
                "ASC_PRIVATE_KEY_PATH environment variables."
            )

        if self._is_altool():
            # altool uses different argument names
            args = [
                "--apiKey", self._key_id,
                "--apiIssuer", self._issuer_id,
            ]
        else:
            # iTMSTransporter
            args = [
                "-apiKey", self._key_id,
                "-apiIssuer", self._issuer_id,
            ]

        return args

    def _run_command(
        self,
        args: list[str],
        description: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run transporter command."""
        if not self._transporter_path:
            raise TransporterError("Transporter not configured")

        cmd = [str(self._transporter_path), *args]

        logger.info("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout for uploads
            )

            if self._verbose:
                if result.stdout:
                    logger.debug("stdout: %s", result.stdout)
                if result.stderr:
                    logger.debug("stderr: %s", result.stderr)

            if result.returncode != 0:
                error_msg = self._parse_error(result.stdout + result.stderr)
                raise TransporterError(
                    f"{description} failed: {error_msg}",
                    exit_code=result.returncode,
                )

            return result

        except subprocess.TimeoutExpired as exc:
            raise TransporterError(f"{description} timed out after 1 hour") from exc
        except FileNotFoundError as exc:
            raise TransporterError(f"Transporter not found at {self._transporter_path}") from exc

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
            args = ["--validate-app", "-f", str(file_path), "-t", "ios", *self._build_auth_args()]
        else:
            args = ["-m", "verify", "-f", str(file_path), *self._build_auth_args()]

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
            args = ["--upload-app", "-f", str(file_path), "-t", "ios", *self._build_auth_args()]
        else:
            args = ["-m", "upload", "-f", str(file_path), *self._build_auth_args()]

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
