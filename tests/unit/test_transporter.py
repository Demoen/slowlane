"""Unit tests for iTunes Transporter wrapper."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slowlane.core.errors import TransporterError
from slowlane.transporter.wrapper import TransporterWrapper, find_transporter


class TestFindTransporter:
    def test_uses_env_var_when_set(self, tmp_path: Path) -> None:
        fake_binary = tmp_path / "iTMSTransporter"
        fake_binary.touch()
        fake_binary.chmod(0o755)

        with patch.dict("os.environ", {"TRANSPORTER_PATH": str(fake_binary)}):
            result = find_transporter()
        assert result == fake_binary

    def test_returns_none_when_not_found(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.platform", "linux"),
            patch("shutil.which", return_value=None),
        ):
            result = find_transporter()
        assert result is None

    def test_falls_back_to_path(self, tmp_path: Path) -> None:
        fake_binary = tmp_path / "iTMSTransporter"
        fake_binary.touch()
        fake_binary.chmod(0o755)

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.platform", "linux"),
            patch("shutil.which", return_value=str(fake_binary)),
        ):
            result = find_transporter()
        assert result == fake_binary

    def test_rejects_directory_from_env(self, tmp_path: Path) -> None:
        with (
            patch.dict("os.environ", {"TRANSPORTER_PATH": str(tmp_path)}),
            patch("sys.platform", "linux"),
            patch("shutil.which", return_value=None),
        ):
            result = find_transporter()

        assert result is None


class TestTransporterWrapper:
    @pytest.fixture
    def wrapper(self, tmp_path: Path) -> TransporterWrapper:
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        private_key = tmp_path / "AuthKey_KEYID123.p8"
        private_key.write_text("PRIVATE KEY", encoding="utf-8")
        return TransporterWrapper(
            transporter_path=binary,
            key_id="KEYID123",
            issuer_id="issuer-uuid",
            private_key_path=str(private_key),
        )

    @pytest.fixture
    def altool_wrapper(self, tmp_path: Path) -> TransporterWrapper:
        binary = tmp_path / "altool"
        binary.touch()
        private_key = tmp_path / "AuthKey_KEYID123.p8"
        private_key.write_text("PRIVATE KEY", encoding="utf-8")
        return TransporterWrapper(
            transporter_path=binary,
            key_id="KEYID123",
            issuer_id="issuer-uuid",
            private_key_path=str(private_key),
        )

    def test_raises_when_transporter_not_found(self) -> None:
        with (
            patch("slowlane.transporter.wrapper.find_transporter", return_value=None),
            pytest.raises(TransporterError, match="not found"),
        ):
            TransporterWrapper(key_id="k", issuer_id="i")

    def test_raises_when_no_credentials(self, tmp_path: Path) -> None:
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        wrapper = TransporterWrapper(transporter_path=binary)

        with pytest.raises(TransporterError, match="credentials required"):
            wrapper._build_auth_args()

    def test_is_altool_detection(
        self, wrapper: TransporterWrapper, altool_wrapper: TransporterWrapper
    ) -> None:
        assert wrapper._is_altool() is False
        assert altool_wrapper._is_altool() is True

    def test_build_auth_args_transporter(self, wrapper: TransporterWrapper) -> None:
        args = wrapper._build_auth_args()
        assert "-apiKey" in args
        assert "KEYID123" in args
        assert "-apiIssuer" in args
        assert "issuer-uuid" in args

    def test_build_auth_args_altool(self, altool_wrapper: TransporterWrapper) -> None:
        args = altool_wrapper._build_auth_args()
        assert "--apiKey" in args
        assert "--apiIssuer" in args

    def test_build_auth_args_jwt(self, tmp_path: Path) -> None:
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        wrapper = TransporterWrapper(transporter_path=binary, jwt_token="header.payload.signature")

        assert wrapper._build_auth_args() == ["-jwt", "header.payload.signature"]

    def test_jwt_provider_refreshes_between_validation_and_upload(self, tmp_path: Path) -> None:
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"ipa")
        token_provider = MagicMock(side_effect=["first.jwt.token", "second.jwt.token"])
        wrapper = TransporterWrapper(
            transporter_path=binary,
            jwt_token_provider=token_provider,
        )
        result = subprocess.CompletedProcess([], 0, "success", "")

        with patch("subprocess.run", return_value=result) as run:
            wrapper.validate(ipa)
            wrapper.upload(ipa)

        commands = [call.args[0] for call in run.call_args_list]
        assert commands[0][commands[0].index("-jwt") + 1] == "first.jwt.token"
        assert commands[1][commands[1].index("-jwt") + 1] == "second.jwt.token"

    def test_altool_uses_api_key_when_jwt_is_present(self, tmp_path: Path) -> None:
        binary = tmp_path / "altool"
        binary.touch()
        wrapper = TransporterWrapper(
            transporter_path=binary,
            key_id="KEYID123",
            issuer_id="issuer-uuid",
            jwt_token="header.payload.signature",
        )

        args = wrapper._build_auth_args()

        assert "--apiKey" in args
        assert "--apiIssuer" in args
        assert "header.payload.signature" not in args

    def test_altool_stages_inline_private_key_securely(self, tmp_path: Path) -> None:
        binary = tmp_path / "altool"
        binary.touch()
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"ipa")
        wrapper = TransporterWrapper(
            transporter_path=binary,
            key_id="KEYID123",
            issuer_id="issuer-uuid",
            private_key="PRIVATE KEY CONTENT",
        )
        staged_directory: Path | None = None

        def run_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal staged_directory
            environment = kwargs["env"]
            assert isinstance(environment, dict)
            staged_directory = Path(environment["API_PRIVATE_KEYS_DIR"])
            staged_key = staged_directory / "AuthKey_KEYID123.p8"
            assert staged_key.read_text(encoding="utf-8") == "PRIVATE KEY CONTENT"
            return subprocess.CompletedProcess(command, 0, "success", "")

        with patch("subprocess.run", side_effect=run_command):
            wrapper.upload(ipa)

        assert staged_directory is not None
        assert not staged_directory.exists()

    def test_upload_file_not_found(self, wrapper: TransporterWrapper) -> None:
        with pytest.raises(TransporterError, match="File not found"):
            wrapper.upload(Path("/nonexistent/file.ipa"))

    def test_validate_file_not_found(self, wrapper: TransporterWrapper) -> None:
        with pytest.raises(TransporterError, match="File not found"):
            wrapper.validate(Path("/nonexistent/file.ipa"))

    def test_upload_success(self, wrapper: TransporterWrapper, tmp_path: Path) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")

        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "Upload successful"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as run:
            wrapper.upload(ipa)

        command = run.call_args.args[0]
        assert "-assetFile" in command
        assert "-f" not in command

    def test_validate_uses_asset_file(self, wrapper: TransporterWrapper, tmp_path: Path) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        result.stdout = "Validation successful"
        result.stderr = ""

        with patch("subprocess.run", return_value=result) as run:
            wrapper.validate(ipa)

        command = run.call_args.args[0]
        assert "-assetFile" in command
        assert "-f" not in command

    @pytest.mark.parametrize("operation", ["validate", "upload"])
    @pytest.mark.parametrize(("suffix", "platform"), [(".ipa", "ios"), (".pkg", "macos")])
    def test_altool_infers_platform(
        self,
        altool_wrapper: TransporterWrapper,
        tmp_path: Path,
        operation: str,
        suffix: str,
        platform: str,
    ) -> None:
        app = tmp_path / f"app{suffix}"
        app.write_bytes(b"fake app content")
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        result.stdout = "Success"
        result.stderr = ""

        with patch("subprocess.run", return_value=result) as run:
            getattr(altool_wrapper, operation)(app)

        command = run.call_args.args[0]
        assert command[command.index("-t") + 1] == platform

    def test_jwt_is_redacted_from_logs_and_errors(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        token = "header.payload.signature"
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")
        wrapper = TransporterWrapper(
            transporter_path=binary,
            jwt_token=token,
            verbose=True,
        )
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 1
        result.stdout = f"Command used -jwt {token}"
        result.stderr = f"Error: rejected {token}"

        with (
            caplog.at_level(logging.DEBUG, logger="slowlane.transporter.wrapper"),
            patch("subprocess.run", return_value=result),
            pytest.raises(TransporterError) as exc_info,
        ):
            wrapper.upload(ipa)

        assert token not in caplog.text
        assert token not in str(exc_info.value)
        assert "[REDACTED]" in caplog.text

    def test_upload_failure_raises_error(self, wrapper: TransporterWrapper, tmp_path: Path) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")

        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = "ERROR ITMS-90000: Invalid bundle"
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(TransporterError, match="ITMS-90000"),
        ):
            wrapper.upload(ipa)

    def test_timeout_raises_error(self, wrapper: TransporterWrapper, tmp_path: Path) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")

        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="iTMSTransporter", timeout=3600),
            ),
            pytest.raises(TransporterError, match="timed out"),
        ):
            wrapper.upload(ipa)

    def test_binary_not_found_raises_error(
        self, wrapper: TransporterWrapper, tmp_path: Path
    ) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")

        with (
            patch("subprocess.run", side_effect=FileNotFoundError()),
            pytest.raises(TransporterError, match="not found"),
        ):
            wrapper.upload(ipa)

    def test_execution_os_error_is_wrapped(
        self, wrapper: TransporterWrapper, tmp_path: Path
    ) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")

        with (
            patch("subprocess.run", side_effect=PermissionError("denied")),
            pytest.raises(TransporterError, match="Unable to execute transporter"),
        ):
            wrapper.upload(ipa)

    def test_lookup_not_supported_for_altool(self, altool_wrapper: TransporterWrapper) -> None:
        with pytest.raises(TransporterError, match="not supported"):
            altool_wrapper.lookup("com.example.app")


class TestParseError:
    @pytest.fixture
    def wrapper(self, tmp_path: Path) -> TransporterWrapper:
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        return TransporterWrapper(transporter_path=binary, key_id="k", issuer_id="i")

    def test_parses_itms_error(self, wrapper: TransporterWrapper) -> None:
        output = "ERROR ITMS-90000: The bundle identifier is invalid"
        result = wrapper._parse_error(output)
        assert "ITMS-90000" in result
        assert "invalid" in result

    def test_parses_generic_error(self, wrapper: TransporterWrapper) -> None:
        output = "Error: Something went wrong"
        result = wrapper._parse_error(output)
        assert "Something went wrong" in result

    def test_returns_last_line_as_fallback(self, wrapper: TransporterWrapper) -> None:
        output = "line 1\nline 2\nlast error line"
        result = wrapper._parse_error(output)
        assert result == "last error line"
