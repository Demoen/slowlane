"""macOS upload and validation through Apple's command-line tools."""

from __future__ import annotations

import contextlib
import logging
import os
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from xml.parsers.expat import ExpatError

from slowlane.core.errors import TransporterError

logger = logging.getLogger(__name__)

MAX_INFO_PLIST_BYTES = 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 3600


def require_macos() -> None:
    if sys.platform != "darwin":
        raise TransporterError(
            "Uploads and upload validation require macOS with Xcode or Transporter installed. "
            "App Store Connect API commands can run on other platforms."
        )


def _is_usable_transporter(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def _discovery_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _xcrun_find(name: str) -> Path | None:
    output = _discovery_output(["/usr/bin/xcrun", "--find", name])
    if output:
        path = Path(output)
        if _is_usable_transporter(path):
            return path
    return None


def _selected_xcode_transporter() -> Path | None:
    directory = os.environ.get("DEVELOPER_DIR") or _discovery_output(
        ["/usr/bin/xcode-select", "--print-path"]
    )
    if not directory:
        return None
    developer_dir = Path(directory).expanduser()
    if developer_dir.suffix == ".app":
        developer_dir = developer_dir / "Contents" / "Developer"
    path = (
        developer_dir.parent
        / "SharedFrameworks/ContentDeliveryServices.framework/Versions/A/itms/bin/iTMSTransporter"
    )
    return path if _is_usable_transporter(path) else None


def find_transporter() -> Path | None:
    """Prefer Transporter, honoring explicit paths and the selected Xcode installation."""
    require_macos()
    if "TRANSPORTER_PATH" in os.environ:
        override_value = os.environ["TRANSPORTER_PATH"].strip()
        if override_value:
            override_path = Path(override_value).expanduser()
            if _is_usable_transporter(override_path):
                return override_path
        raise TransporterError("TRANSPORTER_PATH must point to an executable file")

    if path := _xcrun_find("iTMSTransporter"):
        return path
    if path := _selected_xcode_transporter():
        return path
    app_path = Path("/Applications/Transporter.app/Contents/itms/bin/iTMSTransporter")
    if _is_usable_transporter(app_path):
        return app_path
    if value := shutil.which("iTMSTransporter"):
        path = Path(value)
        if _is_usable_transporter(path):
            return path
    if path := _xcrun_find("altool"):
        return path
    if value := shutil.which("altool"):
        path = Path(value)
        if _is_usable_transporter(path):
            return path
    return None


class TransporterWrapper:
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
        require_macos()
        self._transporter_path = transporter_path or find_transporter()
        self._key_id = key_id or os.environ.get("ASC_KEY_ID")
        self._issuer_id = issuer_id or os.environ.get("ASC_ISSUER_ID")
        self._private_key_path = private_key_path or os.environ.get("ASC_PRIVATE_KEY_PATH")
        self._private_key = private_key or os.environ.get("ASC_PRIVATE_KEY")
        self._jwt_token = jwt_token
        self._jwt_token_provider = jwt_token_provider
        self._verbose = verbose

        if not self._transporter_path or not _is_usable_transporter(self._transporter_path):
            raise TransporterError("An executable iTMSTransporter or altool was not found")

    def _is_altool(self) -> bool:
        return self._transporter_path is not None and self._transporter_path.name == "altool"

    @staticmethod
    def _altool_platform(file_path: Path) -> str:
        if file_path.suffix.lower() == ".pkg":
            return "macos"
        try:
            with zipfile.ZipFile(file_path) as archive:
                candidates = [
                    entry
                    for entry in archive.infolist()
                    if len(parts := PurePosixPath(entry.filename).parts) == 3
                    and parts[0] == "Payload"
                    and parts[1].endswith(".app")
                    and parts[2] == "Info.plist"
                ]
                if len(candidates) != 1:
                    raise TransporterError("IPA must contain exactly one main app Info.plist")
                entry = candidates[0]
                if entry.file_size > MAX_INFO_PLIST_BYTES:
                    raise TransporterError("IPA Info.plist exceeds the 1 MiB safety limit")
                with archive.open(entry) as plist_file:
                    data = plist_file.read(MAX_INFO_PLIST_BYTES + 1)
                if len(data) > MAX_INFO_PLIST_BYTES:
                    raise TransporterError("IPA Info.plist exceeds the 1 MiB safety limit")
                metadata = plistlib.loads(data)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, ExpatError) as exc:
            raise TransporterError("Unable to read the IPA's main app Info.plist") from exc
        if (
            not isinstance(metadata, dict)
            or metadata.get("CFBundleSupportedPlatforms") != ["iPhoneOS"]
            or metadata.get("DTPlatformName", "iphoneos") != "iphoneos"
        ):
            raise TransporterError(
                "The altool fallback supports only iOS device IPAs and macOS packages. "
                "Install Transporter for other Apple platforms."
            )
        return "ios"

    def _build_auth_args(self) -> list[str]:
        if not self._is_altool():
            if self._jwt_token_provider:
                self._jwt_token = self._jwt_token_provider()
            if not self._jwt_token:
                raise TransporterError("A signed App Store Connect JWT is required for Transporter")
            return ["-jwt", self._jwt_token]
        if not self._key_id or not self._issuer_id:
            raise TransporterError("Team API key ID and issuer ID are required for altool")
        if not re.fullmatch(r"[A-Za-z0-9]+", self._key_id):
            raise TransporterError("API key ID must contain only letters and digits")
        return ["--apiKey", self._key_id, "--apiIssuer", self._issuer_id]

    def _redact_sensitive(self, text: str) -> str:
        for secret in (self._jwt_token, self._private_key, os.environ.get("ASC_PRIVATE_KEY")):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        if self._private_key:
            for line in self._private_key.splitlines():
                if line and not line.startswith("-----"):
                    text = text.replace(line, "[REDACTED]")
        text = re.sub(
            r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
            "[REDACTED]",
            text,
            flags=re.DOTALL,
        )
        return re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED]", text)

    @contextmanager
    def _command_environment(self) -> Iterator[dict[str, str]]:
        environment = os.environ.copy()
        environment.pop("ASC_PRIVATE_KEY", None)
        environment.pop("FASTLANE_SESSION", None)
        if not self._is_altool():
            yield environment
            return
        if not self._private_key and self._private_key_path:
            try:
                self._private_key = (
                    Path(self._private_key_path).expanduser().read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError) as exc:
                raise TransporterError("Unable to read the API private key file") from exc
        if not self._private_key or not self._private_key.strip():
            raise TransporterError("API private key contents or a key file are required for altool")
        if not self._key_id or not re.fullmatch(r"[A-Za-z0-9]+", self._key_id):
            raise TransporterError("API key ID must contain only letters and digits")

        with tempfile.TemporaryDirectory(prefix="slowlane-altool-") as temporary_directory:
            directory = Path(temporary_directory)
            if os.name == "posix":
                os.chmod(directory, 0o700)
            key_path = directory / f"AuthKey_{self._key_id}.p8"
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
                key_file.write(self._private_key)
                key_file.flush()
                os.fsync(key_file.fileno())
            environment["API_PRIVATE_KEYS_DIR"] = str(directory)
            yield environment

    @staticmethod
    def _stop_process(process: subprocess.Popen[str]) -> None:
        kill_group = getattr(os, "killpg", None)
        try:
            if kill_group is not None:
                kill_group(process.pid, getattr(signal, "SIGKILL", 9))
            else:
                process.kill()
        except OSError:
            with contextlib.suppress(OSError):
                process.kill()
        process.communicate()

    def _run_command(self, args: list[str], description: str) -> subprocess.CompletedProcess[str]:
        command = [str(self._transporter_path), *args]
        logger.info("Running: %s", self._redact_sensitive(" ".join(command)))
        try:
            with (
                self._command_environment() as environment,
                subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=environment,
                    start_new_session=True,
                ) as process,
            ):
                try:
                    stdout, stderr = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
                except BaseException:
                    self._stop_process(process)
                    raise
                result = subprocess.CompletedProcess(
                    command,
                    process.returncode,
                    self._redact_sensitive(stdout),
                    self._redact_sensitive(stderr),
                )
        except subprocess.TimeoutExpired:
            raise TransporterError(f"{description} timed out after 1 hour") from None
        except OSError:
            raise TransporterError(
                f"Unable to execute transporter at {self._transporter_path}"
            ) from None

        if self._verbose:
            logger.debug("Transporter exited with status %d", result.returncode)
        if result.returncode != 0:
            error = self._parse_error(f"{result.stdout}\n{result.stderr}")
            raise TransporterError(
                f"{description} failed: {error}", process_exit_code=result.returncode
            )
        return result

    @staticmethod
    def _parse_error(output: str) -> str:
        for pattern in (r"ERROR ITMS-(\d+): (.+)", r"Error:\s*(.+)"):
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    return f"ITMS-{match.group(1)}: {match.group(2)}"
                return match.group(1)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        return lines[-1] if lines else "Unknown error"

    def _asset_args(self, file_path: Path, *, validate: bool) -> list[str]:
        if not file_path.is_file():
            raise TransporterError(f"File not found: {file_path}")
        if file_path.suffix.lower() not in {".ipa", ".pkg"}:
            raise TransporterError("Expected a .ipa or .pkg file")
        if file_path.stat().st_size == 0:
            raise TransporterError("Upload file is empty")
        if self._is_altool():
            return [
                "--validate-app" if validate else "--upload-app",
                "-f",
                str(file_path),
                "-t",
                self._altool_platform(file_path),
                *self._build_auth_args(),
            ]
        return [
            "-m",
            "verify" if validate else "upload",
            "-assetFile",
            str(file_path),
            *self._build_auth_args(),
        ]

    def validate(self, file_path: Path) -> None:
        self._run_command(self._asset_args(file_path, validate=True), "Validation")

    def upload(self, file_path: Path) -> None:
        self._run_command(self._asset_args(file_path, validate=False), "Upload")
