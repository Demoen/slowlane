import json
import sys
from unittest.mock import MagicMock

import pytest
import yaml
from typer.testing import CliRunner

from slowlane.auth.jwt_auth import JWTCredentials
from slowlane.cli import main as cli_main
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AuthExpiredError
from tests.unit.test_jwt_auth import TEST_PRIVATE_KEY


@pytest.fixture(autouse=True)
def isolate_cli(monkeypatch: pytest.MonkeyPatch) -> SlowlaneConfig:
    for name in (*JWTCredentials.ENVIRONMENT_VARIABLES, "SLOWLANE_JSON", "SLOWLANE_VERBOSE"):
        monkeypatch.delenv(name, raising=False)
    config = SlowlaneConfig()
    monkeypatch.setattr(SlowlaneConfig, "load", lambda *args: config)
    return config


@pytest.mark.parametrize(
    "args", [["version"], ["--version"], ["doctor"], ["env", "setup"], ["env", "print"]]
)
def test_operational_json_output_is_one_value(
    args: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", *args])
    cli_main.run()
    output = capsys.readouterr()
    assert isinstance(json.loads(output.out), dict)
    assert output.err == ""


def test_doctor_online_uses_read_only_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr("slowlane.cli.asc.get_client", lambda ctx: client)
    result = CliRunner().invoke(cli_main.app, ["--json", "doctor", "--online"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["online"] == "authenticated"
    client.list_apps.assert_called_once_with(limit=1)
    client.__exit__.assert_called_once()


def test_doctor_validates_key_without_exposing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASC_KEY_ID", "KEY123")
    monkeypatch.setenv("ASC_ISSUER_ID", "issuer")
    monkeypatch.setenv("ASC_PRIVATE_KEY", TEST_PRIVATE_KEY)
    result = CliRunner().invoke(cli_main.app, ["--json", "doctor"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["authentication"] == "valid_local_key"
    assert "PRIVATE KEY" not in result.output


def test_doctor_online_failure_uses_error_envelope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "doctor", "--online"])
    with pytest.raises(SystemExit) as error:
        cli_main.run()
    output = capsys.readouterr()
    assert error.value.code == AuthExpiredError.exit_code
    assert output.out == ""
    assert json.loads(output.err)["error"]["type"] == "AuthExpiredError"


@pytest.mark.parametrize("platform", ["github", "gitlab", "azure"])
def test_ci_exports_quote_values_and_hide_key(
    platform: str, isolate_cli: SlowlaneConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    identifier = 'key: "quoted"\nnext: value'
    isolate_cli.auth.key_id = identifier
    isolate_cli.auth.issuer_id = "issuer"
    monkeypatch.setenv("ASC_PRIVATE_KEY", "private-secret-marker")
    result = CliRunner().invoke(cli_main.app, ["env", "print", "--platform", platform])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(result.stdout)
    assert data["variables" if platform == "gitlab" else "env"]["ASC_KEY_ID"] == identifier
    assert "private-secret-marker" not in result.output


@pytest.mark.parametrize("command", [["asc", "builds", "list"], ["asc", "builds", "latest", "APP"]])
def test_build_display_uses_actual_build_number(
    command: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    build = {"id": "BUILD", "attributes": {"version": "123", "processingState": "VALID"}}
    client.list_builds.return_value = [build]
    client.get_latest_build.return_value = build
    monkeypatch.setattr("slowlane.cli.asc.get_client", lambda ctx: client)
    result = CliRunner().invoke(cli_main.app, command)
    assert result.exit_code == 0, result.output
    assert "123" in result.stdout
    assert "Version" not in result.stdout


def test_tester_display_accepts_nullable_names(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.list_beta_testers.return_value = [
        {
            "id": "TESTER",
            "attributes": {
                "email": None,
                "firstName": None,
                "lastName": None,
                "inviteType": "PUBLIC_LINK",
                "state": "INSTALLED",
            },
        }
    ]
    monkeypatch.setattr("slowlane.cli.asc.get_client", lambda ctx: client)
    result = CliRunner().invoke(cli_main.app, ["asc", "testflight", "testers"])
    assert result.exit_code == 0, result.output
    assert "PUBLIC_LINK" in result.stdout
    assert "INSTALLED" in result.stdout


def test_removed_session_command_is_not_advertised() -> None:
    result = CliRunner().invoke(cli_main.app, ["--help"])
    assert result.exit_code == 0
    assert "spaceauth" not in result.stdout
    assert "doctor" in result.stdout


@pytest.mark.parametrize(("name", "value"), [("ASC_KEY_TYPE", "invalid"), ("ASC_KEY_ID", "")])
def test_configured_json_survives_invalid_environment(
    name: str,
    value: str,
    isolate_cli: SlowlaneConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    isolate_cli.output.format = "json"
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(sys, "argv", ["slowlane", "asc", "apps", "list"])
    with pytest.raises(SystemExit):
        cli_main.run()
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["error"]["type"] == "ConfigError"


@pytest.mark.parametrize("json_output", [True, False])
def test_ci_exports_follow_inline_key_precedence(
    json_output: bool, isolate_cli: SlowlaneConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_cli.auth.key_id = "KEY123"
    isolate_cli.auth.issuer_id = "issuer"
    isolate_cli.auth.private_key_path = "/stale/private.p8"
    monkeypatch.setenv("ASC_PRIVATE_KEY", "private-secret-marker")
    args = ["--json"] if json_output else []
    result = CliRunner().invoke(cli_main.app, [*args, "env", "print", "--platform", "generic"])
    assert result.exit_code == 0, result.output
    assert "ASC_PRIVATE_KEY_PATH" not in result.stdout
    assert "/stale" not in result.stdout
    assert "private-secret-marker" not in result.stdout
    assert "ASC_PRIVATE_KEY" in result.stdout


def test_gitlab_setup_uses_protected_key_file() -> None:
    result = CliRunner().invoke(cli_main.app, ["env", "setup", "--platform", "gitlab"])
    assert result.exit_code == 0
    assert "ASC_PRIVATE_KEY_PATH: File type" in result.stdout
    assert "protected/masked" not in result.stdout


def test_expected_error_does_not_leak_sensitive_cause(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from slowlane.core.errors import NetworkError

    def failure(*args: object, **kwargs: object) -> None:
        try:
            raise ValueError("sensitive-request-marker")
        except ValueError as exc:
            raise NetworkError("Request timed out") from exc

    monkeypatch.setattr(sys, "argv", ["slowlane", "--verbose", "asc", "apps", "list"])
    monkeypatch.setattr(cli_main, "app", failure)
    with pytest.raises(SystemExit):
        cli_main.run()
    output = capsys.readouterr()
    assert "Request timed out" in output.err
    assert "sensitive-request-marker" not in output.err
