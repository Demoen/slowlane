from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from typer.testing import CliRunner

from slowlane.cli import main as cli_main
from slowlane.cli import upload
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import TransporterError
from slowlane.transporter import wrapper as transport

runner = CliRunner()


@pytest.fixture(autouse=True)
def upload_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(transport, "sys", SimpleNamespace(platform="darwin"))
    for name in (
        "ASC_KEY_TYPE",
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY",
        "ASC_PRIVATE_KEY_PATH",
        "SLOWLANE_JSON",
        "SLOWLANE_VERBOSE",
        "TRANSPORTER_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli_main.SlowlaneConfig, "load", lambda path=None: SlowlaneConfig())
    logger = logging.getLogger()
    original_handlers, original_level = logger.handlers[:], logger.level
    yield
    logger.handlers = original_handlers
    logger.setLevel(original_level)


@pytest.fixture
def auth(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    credentials = MagicMock()
    credentials.key_type = "team"
    credentials.key_id = "KEY123"
    credentials.issuer_id = "issuer-id"
    credentials.private_key = "private-key"
    monkeypatch.setattr(upload, "get_jwt_auth", lambda *args: credentials)
    return credentials


@pytest.fixture
def wrapper(monkeypatch: pytest.MonkeyPatch, auth: MagicMock) -> MagicMock:
    commands = MagicMock()
    monkeypatch.setattr(upload, "find_transporter", lambda: Path("/Applications/iTMSTransporter"))
    monkeypatch.setattr(upload, "TransporterWrapper", lambda **kwargs: commands)
    return commands


@pytest.mark.parametrize("asset_type", ["ipa", "pkg"])
@pytest.mark.parametrize(
    ("flags", "validated", "uploaded"),
    [([], True, True), (["--validate-only"], True, False), (["--skip-validation"], False, True)],
)
def test_upload_json_success_and_execution_order(
    tmp_path: Path,
    wrapper: MagicMock,
    asset_type: str,
    flags: list[str],
    validated: bool,
    uploaded: bool,
) -> None:
    asset = tmp_path / f"[literal] App.{asset_type}"
    asset.write_bytes(b"asset")
    result = runner.invoke(cli_main.app, ["--json", "upload", asset_type, str(asset), *flags])

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "operation": "upload" if uploaded else "validate",
        "asset": str(asset.resolve()),
        "asset_type": asset_type,
        "validated": validated,
        "uploaded": uploaded,
    }
    expected = []
    if validated:
        expected.append(call.validate(asset.resolve()))
    if uploaded:
        expected.append(call.upload(asset.resolve()))
    assert wrapper.mock_calls == expected


@pytest.mark.parametrize("asset_type", ["ipa", "pkg"])
def test_conflicting_validation_options_never_find_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asset_type: str
) -> None:
    asset = tmp_path / f"App.{asset_type}"
    asset.write_bytes(b"asset")
    find = MagicMock()
    monkeypatch.setattr(upload, "find_transporter", find)
    result = runner.invoke(
        cli_main.app,
        ["upload", asset_type, str(asset), "--validate-only", "--skip-validation"],
    )
    assert result.exit_code == 2
    find.assert_not_called()


def test_validation_failure_prevents_upload_and_produces_json_error(
    tmp_path: Path,
    wrapper: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    asset = tmp_path / "App.ipa"
    asset.write_bytes(b"asset")
    wrapper.validate.side_effect = TransporterError("Validation rejected")
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "upload", "ipa", str(asset)])

    with pytest.raises(SystemExit) as exit_info:
        cli_main.run()

    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {"type": "TransporterError", "message": "Validation rejected", "exit_code": 1}
    }
    wrapper.upload.assert_not_called()


@pytest.mark.parametrize(
    ("failure", "exit_code"), [("missing_tool", 1), ("individual", 2), ("missing_auth", 2)]
)
def test_preflight_failure_is_json_and_does_not_execute_upload(
    tmp_path: Path,
    wrapper: MagicMock,
    auth: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
    exit_code: int,
) -> None:
    asset = tmp_path / "App.pkg"
    asset.write_bytes(b"asset")
    if failure == "missing_tool":
        monkeypatch.setattr(upload, "find_transporter", lambda: None)
    elif failure == "individual":
        auth.key_type = "individual"
    else:
        monkeypatch.setattr(upload, "get_jwt_auth", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "upload", "pkg", str(asset)])

    with pytest.raises(SystemExit) as exit_info:
        cli_main.run()

    assert exit_info.value.code == exit_code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["exit_code"] == exit_code
    assert wrapper.mock_calls == []


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_upload_rejects_unsupported_host_before_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    platform: str,
) -> None:
    asset = tmp_path / "App.ipa"
    asset.write_bytes(b"asset")
    monkeypatch.setattr(transport, "sys", SimpleNamespace(platform=platform))
    find = MagicMock()
    monkeypatch.setattr(upload, "find_transporter", find)
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "upload", "ipa", str(asset)])
    with pytest.raises(SystemExit) as exit_info:
        cli_main.run()
    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "macOS" in json.loads(captured.err)["error"]["message"]
    find.assert_not_called()


def test_human_success_does_not_claim_processing_finished(
    tmp_path: Path, wrapper: MagicMock
) -> None:
    asset = tmp_path / "App.ipa"
    asset.write_bytes(b"asset")
    result = runner.invoke(cli_main.app, ["upload", "ipa", str(asset)])
    assert result.exit_code == 0, result.output
    assert "Upload delivered." in result.stdout
    assert "Apple must finish processing" in result.stdout


def test_configured_json_avoids_progress(
    tmp_path: Path,
    wrapper: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SlowlaneConfig()
    config.output.format = "json"
    monkeypatch.setattr(cli_main.SlowlaneConfig, "load", lambda path=None: config)
    asset = tmp_path / "App.ipa"
    asset.write_bytes(b"asset")
    console = MagicMock()
    monkeypatch.setattr(upload, "get_console", lambda ctx: console)
    result = runner.invoke(cli_main.app, ["upload", "ipa", str(asset)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["uploaded"] is True
    console.status.assert_not_called()
    console.print.assert_not_called()
