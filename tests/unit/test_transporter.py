"""Unit tests for iTunes Transporter wrapper."""

from __future__ import annotations

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

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.platform", "linux"),
            patch("shutil.which", return_value=str(fake_binary)),
        ):
            result = find_transporter()
        assert result == fake_binary


class TestTransporterWrapper:
    @pytest.fixture
    def wrapper(self, tmp_path: Path) -> TransporterWrapper:
        binary = tmp_path / "iTMSTransporter"
        binary.touch()
        return TransporterWrapper(
            transporter_path=binary,
            key_id="KEYID123",
            issuer_id="issuer-uuid",
            private_key_path="/path/to/key.p8",
        )

    @pytest.fixture
    def altool_wrapper(self, tmp_path: Path) -> TransporterWrapper:
        binary = tmp_path / "altool"
        binary.touch()
        return TransporterWrapper(
            transporter_path=binary,
            key_id="KEYID123",
            issuer_id="issuer-uuid",
            private_key_path="/path/to/key.p8",
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

    def test_is_altool_detection(self, wrapper: TransporterWrapper, altool_wrapper: TransporterWrapper) -> None:
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

        with patch("subprocess.run", return_value=mock_result):
            wrapper.upload(ipa)  # Should not raise

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
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="iTMSTransporter", timeout=3600)),
            pytest.raises(TransporterError, match="timed out"),
        ):
            wrapper.upload(ipa)

    def test_binary_not_found_raises_error(self, wrapper: TransporterWrapper, tmp_path: Path) -> None:
        ipa = tmp_path / "app.ipa"
        ipa.write_bytes(b"fake ipa content")

        with (
            patch("subprocess.run", side_effect=FileNotFoundError()),
            pytest.raises(TransporterError, match="not found"),
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
