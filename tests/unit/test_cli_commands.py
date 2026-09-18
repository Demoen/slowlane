from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from slowlane.cli import asc, env, signing, upload
from slowlane.cli import main as cli_main
from slowlane.cli.main import app
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import (
    ExitCode,
    NetworkError,
)

runner = CliRunner()


@pytest.fixture
def isolated_run_flags(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.WARNING)
    monkeypatch.setattr(sys, "argv", ["slowlane"])
    monkeypatch.delenv("SLOWLANE_JSON", raising=False)
    monkeypatch.delenv("SLOWLANE_VERBOSE", raising=False)
    yield
    root_logger.setLevel(previous_level)


def _config_patch() -> AbstractContextManager[MagicMock]:
    return patch("slowlane.cli.main.SlowlaneConfig.load", return_value=SlowlaneConfig())


def test_version_option_exits_before_loading_config() -> None:
    with patch("slowlane.cli.main.SlowlaneConfig.load") as load:
        result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "slowlane version" in result.stdout
    load.assert_not_called()


def test_run_writes_slowlane_error_to_stderr_without_traceback(
    isolated_run_flags: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        patch.object(cli_main, "app", side_effect=NetworkError("offline")),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    assert exc_info.value.code == ExitCode.NETWORK_ERROR
    assert captured.out == ""
    assert captured.err == "Error: offline\n"
    assert "Traceback" not in captured.err


def test_run_writes_unexpected_error_to_stderr_without_traceback(
    isolated_run_flags: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        patch.object(cli_main, "app", side_effect=ValueError("broken")),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    assert exc_info.value.code == ExitCode.GENERAL_ERROR
    assert captured.out == ""
    assert captured.err == "Unexpected error: broken\n"
    assert "Traceback" not in captured.err


def test_run_maps_typer_abort_to_interrupt_exit_code(
    isolated_run_flags: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        patch.object(cli_main, "app", side_effect=typer.Abort()),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 130
    assert captured.out == ""
    assert captured.err == "Error: Interrupted\n"


def test_run_maps_command_keyboard_interrupt_to_130(
    isolated_run_flags: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    interrupt_app = typer.Typer()

    @interrupt_app.command()
    def stop() -> None:
        raise KeyboardInterrupt

    @interrupt_app.command()
    def other() -> None:
        return None

    monkeypatch.setattr(sys, "argv", ["slowlane", "stop"])
    with (
        patch.object(cli_main, "app", interrupt_app),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 130
    assert captured.err.endswith("Error: Interrupted\n")


def test_run_no_arguments_does_not_emit_blank_error(
    isolated_run_flags: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main.run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "Usage:" in captured.out
    assert "Error:" not in captured.err


def test_run_includes_traceback_when_verbose(
    isolated_run_flags: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["slowlane", "--verbose", "version"])

    with (
        patch.object(cli_main, "app", side_effect=ValueError("broken")),
        pytest.raises(SystemExit),
    ):
        cli_main.run()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Unexpected error: broken" in captured.err
    assert "Traceback" in captured.err
    assert "ValueError: broken" in captured.err


@pytest.mark.parametrize(
    ("error", "exit_code", "error_type"),
    [
        (NetworkError("offline"), ExitCode.NETWORK_ERROR, "NetworkError"),
        (ValueError("broken"), ExitCode.GENERAL_ERROR, "UnexpectedError"),
    ],
)
def test_run_emits_single_json_error_object(
    error: Exception,
    exit_code: ExitCode,
    error_type: str,
    isolated_run_flags: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "--verbose", "version"])

    with (
        patch.object(cli_main, "app", side_effect=error),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert exc_info.value.code == exit_code
    assert captured.out == ""
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "error": {
            "type": error_type,
            "message": str(error),
            "exit_code": int(exit_code),
        }
    }


def test_run_uses_configured_json_mode_for_command_errors(
    isolated_run_flags: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = SlowlaneConfig()
    config.output.format = "json"
    monkeypatch.setattr(sys, "argv", ["slowlane", "asc", "apps", "list"])

    with (
        patch("slowlane.cli.main.SlowlaneConfig.load", return_value=config),
        patch("slowlane.cli.asc.get_client", side_effect=NetworkError("offline")),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    assert exc_info.value.code == ExitCode.NETWORK_ERROR
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "type": "NetworkError",
            "message": "offline",
            "exit_code": int(ExitCode.NETWORK_ERROR),
        }
    }


def test_run_uses_configured_json_mode_for_parser_errors(
    isolated_run_flags: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = SlowlaneConfig()
    config.output.format = "json"
    monkeypatch.setattr(sys, "argv", ["slowlane", "unknown"])

    with (
        patch("slowlane.cli.main.SlowlaneConfig.load", return_value=config),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert exc_info.value.code == 2
    assert captured.out == ""
    assert payload["error"]["type"] == "UsageError"
    assert payload["error"]["exit_code"] == 2
    assert "unknown" in payload["error"]["message"]


def test_environment_verbose_mode_configures_debug_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLOWLANE_VERBOSE", "true")

    with _config_patch(), patch.object(cli_main, "setup_logging") as setup:
        result = runner.invoke(app, ["version"])

    assert result.exit_code == 0, result.output
    setup.assert_called_once_with(True, False)


def test_subcommand_v_flag_does_not_enable_root_debug(
    isolated_run_flags: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["slowlane", "upload", "ipa", "App.ipa", "-v"])

    assert cli_main._debug_requested() is False


@pytest.mark.parametrize(
    "getter",
    [asc.get_config, env.get_config, signing.get_config, upload.get_config],
)
def test_get_config_does_not_eagerly_load_default(
    getter: Callable[[typer.Context], SlowlaneConfig],
) -> None:
    config = SlowlaneConfig()
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = {"config": config}

    with patch.object(SlowlaneConfig, "load", side_effect=AssertionError("unexpected load")):
        assert getter(ctx) is config


@pytest.mark.parametrize(
    ("args", "method", "return_value"),
    [
        (["asc", "apps", "list"], "list_apps", []),
        (["asc", "apps", "get", "123"], "get_app", {"id": "123", "attributes": {}}),
        (["asc", "builds", "list"], "list_builds", []),
        (["asc", "builds", "latest", "app-id"], "get_latest_build", None),
        (["asc", "testflight", "testers"], "list_beta_testers", []),
        (["asc", "testflight", "groups"], "list_beta_groups", []),
        (
            ["asc", "testflight", "invite", "user@example.com", "--group", "group-id"],
            "invite_beta_tester",
            {"id": "tester-id"},
        ),
    ],
)
def test_asc_commands_close_clients(args: list[str], method: str, return_value: object) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    getattr(client, method).return_value = return_value

    with _config_patch(), patch("slowlane.cli.asc.get_client", return_value=client):
        result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output
    client.__exit__.assert_called_once()


def test_apps_get_resolves_bundle_identifier() -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.get_app_by_bundle_id.return_value = {
        "id": "app-id",
        "attributes": {"bundleId": "com.example.app"},
    }

    with _config_patch(), patch("slowlane.cli.asc.get_client", return_value=client):
        result = runner.invoke(app, ["asc", "apps", "get", "com.example.app"])

    assert result.exit_code == 0, result.output
    client.get_app_by_bundle_id.assert_called_once_with("com.example.app")
    client.get_app.assert_not_called()
    client.__exit__.assert_called_once()


def test_apps_get_missing_is_structured_json_error(monkeypatch, capsys) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.get_app.return_value = None
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "asc", "apps", "get", "123"])
    with (
        _config_patch(),
        patch("slowlane.cli.asc.get_client", return_value=client),
        pytest.raises(SystemExit) as error,
    ):
        cli_main.run()
    output = capsys.readouterr()
    assert error.value.code == 1
    assert output.out == ""
    assert json.loads(output.err) == {
        "error": {"type": "AppStoreConnectError", "message": "App not found: 123", "exit_code": 1}
    }


def test_latest_build_json_output_is_null_when_empty() -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.get_latest_build.return_value = None

    with _config_patch(), patch("slowlane.cli.asc.get_client", return_value=client):
        result = runner.invoke(app, ["--json", "asc", "builds", "latest", "app-id"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None


def test_testflight_invite_json_output_is_raw_object() -> None:
    tester = {"id": "tester-id", "attributes": {"email": "[user]@example.com"}}
    client = MagicMock()
    client.__enter__.return_value = client
    client.invite_beta_tester.return_value = tester

    with _config_patch(), patch("slowlane.cli.asc.get_client", return_value=client):
        result = runner.invoke(
            app,
            [
                "--json",
                "asc",
                "testflight",
                "invite",
                "user@example.com",
                "--group",
                "group-id",
            ],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == tester


@pytest.mark.parametrize(
    ("platform", "private_key_reference"),
    [
        ("github", "ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}"),
        ("gitlab", "ASC_PRIVATE_KEY: $ASC_PRIVATE_KEY"),
        ("azure", "ASC_PRIVATE_KEY: $(ASC_PRIVATE_KEY)"),
        ("generic", "${ASC_PRIVATE_KEY:?ASC_PRIVATE_KEY is required}"),
    ],
)
def test_env_print_includes_private_key_reference(
    platform: str, private_key_reference: str
) -> None:
    config = SlowlaneConfig()
    config.auth.key_id = "KEY123"
    config.auth.issuer_id = "issuer-id"

    with patch("slowlane.cli.main.SlowlaneConfig.load", return_value=config):
        result = runner.invoke(app, ["env", "print", "--platform", platform])

    assert result.exit_code == 0, result.output
    assert private_key_reference in result.stdout
    assert "<set-in-secret-manager>" not in result.stdout


def test_env_print_json_redacts_private_key() -> None:
    config = SlowlaneConfig()
    config.auth.key_id = "KEY123"
    config.auth.issuer_id = "issuer-id"

    with patch("slowlane.cli.main.SlowlaneConfig.load", return_value=config):
        result = runner.invoke(app, ["--json", "env", "print"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["ASC_PRIVATE_KEY"] == "<set-in-secret-manager>"


def test_json_output_preserves_rich_markup_characters() -> None:
    config = SlowlaneConfig()
    config.output.format = "json"
    client = MagicMock()
    client.__enter__.return_value = client
    client.list_apps.return_value = [{"id": "app-id", "attributes": {"name": "[red]literal[/red]"}}]

    with (
        patch("slowlane.cli.main.SlowlaneConfig.load", return_value=config),
        patch("slowlane.cli.asc.get_client", return_value=client),
    ):
        result = runner.invoke(app, ["asc", "apps", "list"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)[0]["attributes"]["name"] == "[red]literal[/red]"


@pytest.mark.parametrize(
    "args",
    [
        ["asc", "apps", "list", "--limit", "0"],
        ["asc", "builds", "list", "--limit", "-1"],
        ["asc", "testflight", "testers", "--limit", "0"],
    ],
)
def test_asc_limits_must_be_positive(args: list[str]) -> None:
    with _config_patch(), patch("slowlane.cli.asc.get_client") as get_client:
        result = runner.invoke(app, args)

    assert result.exit_code == 2
    get_client.assert_not_called()


@pytest.mark.parametrize(
    ("command", "filename"),
    [("ipa", "App.pkg"), ("pkg", "App.ipa")],
)
def test_upload_rejects_wrong_file_type(tmp_path: Path, command: str, filename: str) -> None:
    asset_path = tmp_path / filename
    asset_path.write_bytes(b"asset")

    with _config_patch(), patch("slowlane.cli.upload.find_transporter") as find:
        result = runner.invoke(app, ["upload", command, str(asset_path)])

    assert result.exit_code == 2
    find.assert_not_called()


@pytest.mark.parametrize(
    "args",
    [
        ["env", "print", "--platform", "invalid"],
        ["env", "setup", "--platform", "generic"],
    ],
)
def test_cli_rejects_invalid_choices(args: list[str]) -> None:
    with _config_patch():
        result = runner.invoke(app, args)

    assert result.exit_code == 2
