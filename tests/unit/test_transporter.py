"""Contract tests for Apple's upload tooling."""

from __future__ import annotations

import logging
import os
import plistlib
import subprocess
import traceback
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from slowlane.core.errors import TransporterError
from slowlane.transporter import wrapper as transport
from slowlane.transporter.wrapper import TransporterWrapper, find_transporter


@pytest.fixture(autouse=True)
def macos_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transport, "sys", SimpleNamespace(platform="darwin"))
    for name in (
        "TRANSPORTER_PATH",
        "DEVELOPER_DIR",
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY",
        "ASC_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(0o755)
    return path


def ipa_file(path: Path, platforms: list[str] | None = None, *, binary: bool = False) -> Path:
    metadata = {"CFBundleSupportedPlatforms": platforms or ["iPhoneOS"]}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Payload/App.app/Info.plist",
            plistlib.dumps(metadata, fmt=plistlib.FMT_BINARY if binary else plistlib.FMT_XML),
        )
    return path


@pytest.fixture
def wrapper(tmp_path: Path) -> TransporterWrapper:
    return TransporterWrapper(
        transporter_path=executable(tmp_path / "iTMSTransporter"),
        jwt_token="signed.jwt.token",
    )


@pytest.fixture
def altool(tmp_path: Path) -> TransporterWrapper:
    return TransporterWrapper(
        transporter_path=executable(tmp_path / "altool"),
        key_id="KEY123",
        issuer_id="issuer-id",
        private_key="PRIVATE KEY CONTENT",
    )


@pytest.fixture
def process() -> MagicMock:
    child = MagicMock()
    child.__enter__.return_value = child
    child.communicate.return_value = ("success", "")
    child.returncode = 0
    child.pid = 12345
    return child


class TestDiscovery:
    @pytest.fixture(autouse=True)
    def isolate_installed_transporter_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original = transport._is_usable_transporter
        app_path = Path("/Applications/Transporter.app/Contents/itms/bin/iTMSTransporter")
        monkeypatch.setattr(
            transport,
            "_is_usable_transporter",
            lambda path: path != app_path and original(path),
        )

    def test_explicit_path_takes_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        binary = executable(tmp_path / "iTMSTransporter")
        monkeypatch.setenv("TRANSPORTER_PATH", str(binary))
        with patch.object(transport, "_xcrun_find") as discover:
            assert find_transporter() == binary
        discover.assert_not_called()

    @pytest.mark.parametrize("value", ["", "missing", "."])
    def test_invalid_override_fails_without_fallback(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TRANSPORTER_PATH", value)
        with (
            patch.object(transport, "_xcrun_find") as discover,
            pytest.raises(TransporterError, match="TRANSPORTER_PATH"),
        ):
            find_transporter()
        discover.assert_not_called()

    def test_nonexecutable_override_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        binary = executable(tmp_path / "iTMSTransporter")
        monkeypatch.setenv("TRANSPORTER_PATH", str(binary))
        with (
            patch.object(transport.os, "access", return_value=False),
            pytest.raises(TransporterError, match="executable"),
        ):
            find_transporter()

    def test_xcrun_selects_active_xcode(self, tmp_path: Path) -> None:
        binary = executable(tmp_path / "Selected Xcode.app" / "iTMSTransporter")
        result = subprocess.CompletedProcess([], 0, f"{binary}\n", "")
        with patch.object(transport.subprocess, "run", return_value=result) as run:
            assert find_transporter() == binary
        assert run.call_args.args[0] == ["/usr/bin/xcrun", "--find", "iTMSTransporter"]
        assert run.call_args.kwargs["timeout"] == 10

    @pytest.mark.parametrize("use_app_path", [True, False])
    def test_developer_dir_framework_discovery(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_app_path: bool
    ) -> None:
        app = tmp_path / "Custom Xcode.app"
        developer = app / "Contents" / "Developer"
        binary = executable(
            developer.parent
            / "SharedFrameworks/ContentDeliveryServices.framework/Versions/A/itms/bin/iTMSTransporter"
        )
        monkeypatch.setenv("DEVELOPER_DIR", str(app if use_app_path else developer))
        with patch.object(transport, "_xcrun_find", return_value=None):
            assert find_transporter() == binary

    def test_transporter_on_path_precedes_altool(self, tmp_path: Path) -> None:
        binary = executable(tmp_path / "iTMSTransporter")
        with (
            patch.object(transport, "_xcrun_find", return_value=None) as xcrun,
            patch.object(transport, "_selected_xcode_transporter", return_value=None),
            patch.object(transport.shutil, "which", return_value=str(binary)),
        ):
            assert find_transporter() == binary
        xcrun.assert_called_once_with("iTMSTransporter")

    def test_transporter_app_precedes_altool(self) -> None:
        app_path = Path("/Applications/Transporter.app/Contents/itms/bin/iTMSTransporter")
        with (
            patch.object(transport, "_xcrun_find", return_value=None) as xcrun,
            patch.object(transport, "_selected_xcode_transporter", return_value=None),
            patch.object(
                transport, "_is_usable_transporter", side_effect=lambda path: path == app_path
            ),
            patch.object(transport.shutil, "which") as which,
        ):
            assert find_transporter() == app_path
        xcrun.assert_called_once_with("iTMSTransporter")
        which.assert_not_called()

    def test_altool_is_last_fallback(self, tmp_path: Path) -> None:
        binary = executable(tmp_path / "altool")
        with (
            patch.object(transport, "_xcrun_find", side_effect=[None, binary]),
            patch.object(transport, "_selected_xcode_transporter", return_value=None),
            patch.object(transport.shutil, "which", return_value=None),
        ):
            assert find_transporter() == binary

    def test_missing_tools_returns_none(self) -> None:
        with (
            patch.object(transport, "_discovery_output", return_value=None),
            patch.object(transport.shutil, "which", return_value=None),
        ):
            assert find_transporter() is None

    @pytest.mark.parametrize("platform", ["linux", "win32"])
    def test_unsupported_hosts_never_launch_discovery(
        self, platform: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(transport, "sys", SimpleNamespace(platform=platform))
        with (
            patch.object(transport.subprocess, "run") as run,
            pytest.raises(TransporterError, match="require macOS"),
        ):
            find_transporter()
        run.assert_not_called()

    @pytest.mark.parametrize(
        "failure", [OSError("missing"), subprocess.TimeoutExpired("xcrun", 10)]
    )
    def test_failed_discovery_is_bounded(self, failure: Exception) -> None:
        with patch.object(transport.subprocess, "run", side_effect=failure):
            assert transport._xcrun_find("altool") is None


class TestCommands:
    @pytest.mark.parametrize(("operation", "mode"), [("validate", "verify"), ("upload", "upload")])
    @pytest.mark.parametrize("suffix", [".ipa", ".pkg"])
    def test_transporter_contract(
        self,
        wrapper: TransporterWrapper,
        process: MagicMock,
        tmp_path: Path,
        operation: str,
        mode: str,
        suffix: str,
    ) -> None:
        asset = tmp_path / f"App{suffix}"
        asset.write_bytes(b"asset")
        with patch.object(transport.subprocess, "Popen", return_value=process) as popen:
            getattr(wrapper, operation)(asset)
        assert popen.call_args.args[0] == [
            str(wrapper._transporter_path),
            "-m",
            mode,
            "-assetFile",
            str(asset),
            "-jwt",
            "signed.jwt.token",
        ]
        assert popen.call_args.kwargs["start_new_session"] is True
        assert popen.call_args.kwargs["errors"] == "replace"
        process.communicate.assert_called_once_with(timeout=3600)

    def test_token_refreshed_for_each_operation(
        self, wrapper: TransporterWrapper, process: MagicMock, tmp_path: Path
    ) -> None:
        asset = tmp_path / "App.ipa"
        asset.write_bytes(b"asset")
        wrapper._jwt_token_provider = MagicMock(side_effect=["first.jwt.token", "second.jwt.token"])
        with patch.object(transport.subprocess, "Popen", return_value=process) as popen:
            wrapper.validate(asset)
            wrapper.upload(asset)
        assert popen.call_args_list[0].args[0][-1] == "first.jwt.token"
        assert popen.call_args_list[1].args[0][-1] == "second.jwt.token"

    @pytest.mark.parametrize("operation", ["validate", "upload"])
    @pytest.mark.parametrize("binary", [False, True])
    def test_altool_accepts_ios_plist_formats(
        self,
        altool: TransporterWrapper,
        process: MagicMock,
        tmp_path: Path,
        operation: str,
        binary: bool,
    ) -> None:
        asset = ipa_file(tmp_path / "App.ipa", binary=binary)
        with patch.object(transport.subprocess, "Popen", return_value=process) as popen:
            getattr(altool, operation)(asset)
        command = popen.call_args.args[0]
        assert command[1:] == [
            "--validate-app" if operation == "validate" else "--upload-app",
            "-f",
            str(asset),
            "-t",
            "ios",
            "--apiKey",
            "KEY123",
            "--apiIssuer",
            "issuer-id",
        ]

    def test_altool_accepts_macos_package(
        self, altool: TransporterWrapper, process: MagicMock, tmp_path: Path
    ) -> None:
        asset = tmp_path / "App.pkg"
        asset.write_bytes(b"package")
        with patch.object(transport.subprocess, "Popen", return_value=process) as popen:
            altool.upload(asset)
        command = popen.call_args.args[0]
        assert command[command.index("-t") + 1] == "macos"

    @pytest.mark.parametrize(
        "platform", ["AppleTVOS", "XROS", "WatchOS", "iPhoneSimulator", "Unknown"]
    )
    def test_altool_rejects_unsupported_ipa_before_launch(
        self, altool: TransporterWrapper, tmp_path: Path, platform: str
    ) -> None:
        asset = ipa_file(tmp_path / "App.ipa", [platform])
        with (
            patch.object(transport.subprocess, "Popen") as popen,
            pytest.raises(TransporterError, match="only iOS device"),
        ):
            altool.upload(asset)
        popen.assert_not_called()

    @pytest.mark.parametrize("contents", [b"not a zip", b""])
    def test_invalid_archive_does_not_launch(
        self, altool: TransporterWrapper, tmp_path: Path, contents: bytes
    ) -> None:
        asset = tmp_path / "App.ipa"
        asset.write_bytes(contents)
        with (
            patch.object(transport.subprocess, "Popen") as popen,
            pytest.raises(TransporterError),
        ):
            altool.validate(asset)
        popen.assert_not_called()

    @pytest.mark.parametrize(
        "entries", [[], ["Payload/A.app/Info.plist", "Payload/B.app/Info.plist"]]
    )
    def test_ambiguous_main_app_rejected(
        self, altool: TransporterWrapper, tmp_path: Path, entries: list[str]
    ) -> None:
        asset = tmp_path / "App.ipa"
        with zipfile.ZipFile(asset, "w") as archive:
            for name in entries:
                archive.writestr(name, plistlib.dumps({"CFBundleSupportedPlatforms": ["iPhoneOS"]}))
        with pytest.raises(TransporterError, match="exactly one main app"):
            altool.validate(asset)

    def test_large_plist_is_rejected_without_decompression(
        self, altool: TransporterWrapper, tmp_path: Path
    ) -> None:
        asset = tmp_path / "App.ipa"
        with zipfile.ZipFile(asset, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "Payload/App.app/Info.plist", b"x" * (transport.MAX_INFO_PLIST_BYTES + 1)
            )
        with (
            patch.object(zipfile.ZipFile, "open") as open_entry,
            pytest.raises(TransporterError, match="1 MiB"),
        ):
            altool.validate(asset)
        open_entry.assert_not_called()

    @pytest.mark.parametrize("operation", ["validate", "upload"])
    def test_missing_asset_rejected(
        self, wrapper: TransporterWrapper, tmp_path: Path, operation: str
    ) -> None:
        with pytest.raises(TransporterError, match="File not found"):
            getattr(wrapper, operation)(tmp_path / "missing.ipa")

    def test_transporter_requires_signed_token(self, tmp_path: Path) -> None:
        wrapper = TransporterWrapper(
            transporter_path=executable(tmp_path / "iTMSTransporter"),
            key_id="KEY123",
            issuer_id="issuer-id",
        )
        with pytest.raises(TransporterError, match="signed App Store Connect JWT"):
            wrapper._build_auth_args()


class TestProcessSafety:
    @pytest.mark.parametrize("failure", ["success", "timeout", "cancel", "launch"])
    def test_staged_key_removed_on_every_exit(
        self,
        altool: TransporterWrapper,
        process: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure: str,
    ) -> None:
        asset = ipa_file(tmp_path / "App.ipa")
        monkeypatch.setenv("ASC_PRIVATE_KEY", "environment secret")
        staged_directory: Path | None = None
        if failure == "timeout":
            process.communicate.side_effect = [subprocess.TimeoutExpired("altool", 3600), ("", "")]
        elif failure == "cancel":
            process.communicate.side_effect = [KeyboardInterrupt(), ("", "")]

        def launch(*args: object, **kwargs: object) -> MagicMock:
            nonlocal staged_directory
            environment = kwargs["env"]
            assert isinstance(environment, dict)
            assert "ASC_PRIVATE_KEY" not in environment
            staged_directory = Path(environment["API_PRIVATE_KEYS_DIR"])
            key = staged_directory / "AuthKey_KEY123.p8"
            assert key.read_text(encoding="utf-8") == "PRIVATE KEY CONTENT"
            if os.name == "posix":
                assert key.stat().st_mode & 0o777 == 0o600
                assert staged_directory.stat().st_mode & 0o777 == 0o700
            if failure == "launch":
                raise PermissionError("denied")
            return process

        with (
            patch.object(transport.subprocess, "Popen", side_effect=launch),
            patch.object(transport.os, "killpg", create=True) as kill_group,
            patch.object(transport.signal, "SIGKILL", 9, create=True),
        ):
            if failure == "success":
                altool.upload(asset)
            elif failure == "cancel":
                with pytest.raises(KeyboardInterrupt):
                    altool.upload(asset)
            else:
                with pytest.raises(TransporterError):
                    altool.upload(asset)
        assert staged_directory is not None
        assert not staged_directory.exists()
        if failure in {"timeout", "cancel"}:
            kill_group.assert_called_once_with(process.pid, 9)
            assert process.communicate.call_count == 2

    def test_secrets_absent_from_errors_and_logs(
        self,
        wrapper: TransporterWrapper,
        process: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        asset = tmp_path / "App.ipa"
        asset.write_bytes(b"asset")
        wrapper._private_key = (
            "-----BEGIN PRIVATE KEY-----\nprivate-line\n-----END PRIVATE KEY-----"
        )
        wrapper._verbose = True
        process.returncode = 1
        process.communicate.return_value = (
            wrapper._private_key,
            "Error: rejected signed.jwt.token and private-line",
        )
        with (
            caplog.at_level(logging.DEBUG, logger="slowlane.transporter.wrapper"),
            patch.object(transport.subprocess, "Popen", return_value=process),
            pytest.raises(TransporterError) as error,
        ):
            wrapper.upload(asset)
        for secret in ("signed.jwt.token", "private-line"):
            assert secret not in str(error.value)
            assert secret not in caplog.text
        assert "[REDACTED]" in str(error.value)
        assert error.value.context["process_exit_code"] == 1

    def test_timeout_traceback_does_not_include_secret_command(
        self, wrapper: TransporterWrapper, process: MagicMock, tmp_path: Path
    ) -> None:
        asset = tmp_path / "App.ipa"
        asset.write_bytes(b"asset")
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["tool", "-jwt", "signed.jwt.token"], 3600),
            ("", ""),
        ]
        with (
            patch.object(transport.subprocess, "Popen", return_value=process),
            patch.object(wrapper, "_stop_process"),
            pytest.raises(TransporterError, match="timed out") as error,
        ):
            wrapper.upload(asset)
        formatted = "".join(traceback.format_exception(error.value))
        assert "signed.jwt.token" not in formatted

    def test_key_id_cannot_escape_staging_directory(self, altool: TransporterWrapper) -> None:
        altool._key_id = "../escape"
        with pytest.raises(TransporterError, match="letters and digits"):
            altool._build_auth_args()

    def test_altool_requires_supplied_private_key(self, altool: TransporterWrapper) -> None:
        altool._private_key = None
        with (
            pytest.raises(TransporterError, match="private key"),
            altool._command_environment(),
        ):
            pytest.fail("environment must not be provided without a key")


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("ERROR ITMS-90000: Invalid bundle", "ITMS-90000: Invalid bundle"),
        ("Error: Rejected", "Rejected"),
        ("first line\nlast line", "last line"),
        ("", "Unknown error"),
    ],
)
def test_error_parsing(output: str, expected: str) -> None:
    assert TransporterWrapper._parse_error(output) == expected
