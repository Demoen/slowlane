from __future__ import annotations

import io
import json
import logging
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from click import Abort
from rich.console import Console
from typer.testing import CliRunner

from slowlane.asc.client import AppStoreConnectClient
from slowlane.auth.session_auth import SessionAuth
from slowlane.cli import asc, env, signing, spaceauth, upload
from slowlane.cli import main as cli_main
from slowlane.cli.main import app
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import (
    AppStoreConnectError,
    AuthExpiredError,
    ExitCode,
    NetworkError,
    SlowlaneError,
)
from slowlane.core.secrets import EncryptedFileBackend, SecretStore, SessionData

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


def _session(cookies: dict[str, str] | None = None) -> SessionData:
    return SessionData(
        cookies=cookies or {"myacinfo": "myac", "DES": "des"},
        email_hash="hash",
        created_at=datetime.now(UTC),
    )


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


def test_run_maps_click_abort_to_interrupt_exit_code(
    isolated_run_flags: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with patch.object(cli_main, "app", side_effect=Abort()), pytest.raises(SystemExit) as exc_info:
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


def test_missing_signing_session_is_cp1252_safe_json(
    isolated_run_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout_bytes = io.BytesIO()
    stderr_bytes = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_bytes, encoding="cp1252", write_through=True)
    stderr = io.TextIOWrapper(stderr_bytes, encoding="cp1252", write_through=True)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "signing", "certs", "list"])
    monkeypatch.setattr(cli_main, "console", Console(file=stdout, force_terminal=False))
    monkeypatch.setattr(cli_main, "error_console", Console(file=stderr, force_terminal=False))

    with (
        _config_patch(),
        patch("slowlane.cli.signing.SecretStore", return_value=MagicMock()),
        patch("slowlane.cli.signing.get_session_auth", return_value=None),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli_main.run()

    assert exc_info.value.code == ExitCode.AUTH_EXPIRED
    assert stdout_bytes.getvalue() == b""
    payload = json.loads(stderr_bytes.getvalue().decode("cp1252"))
    assert payload["error"]["type"] == "SessionError"
    assert payload["error"]["exit_code"] == ExitCode.AUTH_EXPIRED


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
    [asc.get_config, env.get_config, signing.get_config, spaceauth.get_config, upload.get_config],
)
def test_get_config_does_not_eagerly_load_default(
    getter: Callable[[typer.Context], SlowlaneConfig],
) -> None:
    config = SlowlaneConfig()
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = {"config": config}

    with patch.object(SlowlaneConfig, "load", side_effect=AssertionError("unexpected load")):
        assert getter(ctx) is config


def test_asc_cli_does_not_fall_back_to_stored_session() -> None:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = {"config": SlowlaneConfig()}
    secret_store = MagicMock()
    secret_store.retrieve_default_session.return_value = _session()

    with (
        patch("slowlane.cli.asc.get_jwt_auth", return_value=None),
        patch("slowlane.cli.asc.SecretStore", return_value=secret_store),
        patch("slowlane.cli.asc.AppStoreConnectClient") as client_type,
        pytest.raises(AuthExpiredError, match="API key authentication is required"),
    ):
        asc.get_client(ctx)

    client_type.assert_not_called()


def test_asc_client_rejects_session_only_auth() -> None:
    with pytest.raises(AppStoreConnectError, match="require API key authentication"):
        AppStoreConnectClient(session_auth=SessionAuth(_session()))


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


def test_apps_get_missing_is_structured_json_error() -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.get_app.return_value = None

    with _config_patch(), patch("slowlane.cli.asc.get_client", return_value=client):
        result = runner.invoke(app, ["--json", "asc", "apps", "get", "123"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "type": "AppStoreConnectError",
            "message": "App not found: 123",
            "exit_code": 1,
        }
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
        ("azure", "value: $(ASC_PRIVATE_KEY)"),
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


def test_upload_passes_signed_jwt_to_transporter(tmp_path: Path) -> None:
    ipa_path = tmp_path / "App.ipa"
    ipa_path.write_bytes(b"ipa")
    transporter_path = tmp_path / "iTMSTransporter"
    jwt_auth = MagicMock()
    jwt_auth.key_id = "KEY123"
    jwt_auth.issuer_id = "issuer-id"
    jwt_auth.private_key = "PRIVATE KEY"
    jwt_auth.get_token.return_value = "signed.jwt.token"
    wrapper = MagicMock()
    config = SlowlaneConfig()
    config.output.verbose = True

    with (
        patch("slowlane.cli.main.SlowlaneConfig.load", return_value=config),
        patch("slowlane.cli.upload.find_transporter", return_value=transporter_path),
        patch("slowlane.cli.upload.SecretStore", return_value=MagicMock()),
        patch("slowlane.cli.upload.get_jwt_auth", return_value=jwt_auth),
        patch("slowlane.cli.upload.TransporterWrapper", return_value=wrapper) as wrapper_type,
    ):
        result = runner.invoke(app, ["upload", "ipa", str(ipa_path), "--validate-only"])

    assert result.exit_code == 0, result.output
    wrapper_type.assert_called_once_with(
        transporter_path=transporter_path,
        key_id="KEY123",
        issuer_id="issuer-id",
        private_key_path=None,
        private_key="PRIVATE KEY",
        jwt_token_provider=jwt_auth.get_token,
        verbose=True,
    )
    jwt_auth.get_token.assert_not_called()
    wrapper.validate.assert_called_once_with(ipa_path)


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
        ["spaceauth", "login", "--service", "invalid"],
        ["env", "print", "--platform", "invalid"],
        ["env", "setup", "--platform", "generic"],
    ],
)
def test_cli_rejects_invalid_choices(args: list[str]) -> None:
    with _config_patch():
        result = runner.invoke(app, args)

    assert result.exit_code == 2


def test_login_rejects_missing_required_cookies() -> None:
    with (
        _config_patch(),
        patch("slowlane.cli.spaceauth.interactive_login", return_value=_session({"myacinfo": "x"})),
        patch("slowlane.cli.spaceauth.SecretStore") as secret_store,
    ):
        result = runner.invoke(app, ["spaceauth", "login", "--email", "user@example.com"])

    assert result.exit_code == 2
    assert "Missing cookies: DES" in result.stdout
    assert "Login successful" not in result.stdout
    secret_store.assert_not_called()


def test_login_without_email_prints_immediately_usable_export() -> None:
    session = _session()
    with (
        _config_patch(),
        patch("slowlane.cli.spaceauth.interactive_login", return_value=session),
        patch("slowlane.cli.spaceauth.SecretStore") as secret_store,
    ):
        result = runner.invoke(app, ["spaceauth", "login"])

    assert result.exit_code == 0, result.output
    assert f'export FASTLANE_SESSION="{SessionAuth(session).to_export_string()}"' in result.stdout
    secret_store.assert_not_called()


def test_export_uses_default_stored_session(tmp_path: Path) -> None:
    session = _session()
    store = SecretStore(EncryptedFileBackend(tmp_path))
    store.store_session("user@example.com", session)

    with _config_patch(), patch("slowlane.cli.spaceauth.SecretStore", return_value=store):
        result = runner.invoke(app, ["spaceauth", "export"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == (
        f'export FASTLANE_SESSION="{SessionAuth(session).to_export_string()}"'
    )


def test_verify_returns_remote_failure_exit_code() -> None:
    auth = SessionAuth(_session())
    portal = MagicMock()
    portal.__enter__.return_value = portal
    portal.list_teams.side_effect = NetworkError("offline")

    with (
        _config_patch(),
        patch("slowlane.cli.spaceauth.get_session_auth", return_value=auth),
        patch("slowlane.devportal.client.DeveloperPortalClient", return_value=portal),
    ):
        result = runner.invoke(app, ["spaceauth", "verify"])

    assert result.exit_code == 4
    assert "Could not verify session via API" in result.stdout
    portal.__exit__.assert_called_once()


def test_certificate_creation_requires_csr() -> None:
    with _config_patch():
        result = runner.invoke(app, ["signing", "certs", "create", "--type", "development"])

    assert result.exit_code == 2
    assert "--csr" in result.output


def test_certificate_creation_uses_existing_csr(tmp_path: Path) -> None:
    csr_path = tmp_path / "request.csr"
    csr_path.write_text("CSR CONTENT", encoding="utf-8")
    client = MagicMock()
    client.create_certificate.return_value = {"certificateId": "cert-id"}
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "certs",
                "create",
                "--type",
                "development",
                "--csr",
                str(csr_path),
            ],
        )

    assert result.exit_code == 0, result.output
    client.create_certificate.assert_called_once_with(
        csr_content="CSR CONTENT", cert_type="development"
    )
    client_manager.__exit__.assert_called_once()


def test_profile_creation_resolves_bundle_identifier() -> None:
    client = MagicMock()
    client.list_app_ids.return_value = [{"id": "portal-app-id", "identifier": "com.example.app"}]
    client.create_profile.return_value = {"provisioningProfileId": "profile-id"}
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "profiles",
                "create",
                "--name",
                "Example",
                "--type",
                "appstore",
                "--bundle-id",
                "com.example.app",
                "--cert",
                "cert-id",
            ],
        )

    assert result.exit_code == 0, result.output
    client.list_app_ids.assert_called_once_with()
    client.create_profile.assert_called_once_with(
        name="Example",
        bundle_id="portal-app-id",
        profile_type="appstore",
        certificate_ids=["cert-id"],
        device_ids=None,
    )
    client_manager.__exit__.assert_called_once()


@pytest.mark.parametrize("profile_type", ["development", "adhoc"])
def test_device_profile_requires_device(profile_type: str) -> None:
    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth") as require_session,
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "profiles",
                "create",
                "--name",
                "Development",
                "--type",
                profile_type,
                "--bundle-id",
                "com.example.app",
                "--cert",
                "cert-id",
            ],
        )

    assert result.exit_code == 2
    assert "at least one --device is required" in result.output
    require_session.assert_not_called()


def test_appstore_profile_rejects_device() -> None:
    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth") as require_session,
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "profiles",
                "create",
                "--name",
                "App Store",
                "--type",
                "appstore",
                "--bundle-id",
                "com.example.app",
                "--cert",
                "cert-id",
                "--device",
                "device-id",
            ],
        )

    assert result.exit_code == 2
    assert "--device is not allowed" in result.output
    require_session.assert_not_called()


def test_profile_creation_passes_repeated_devices() -> None:
    client = MagicMock()
    client.list_app_ids.return_value = [
        {"appIdId": "portal-app-id", "identifier": "com.example.app"}
    ]
    client.create_profile.return_value = {"provisioningProfileId": "profile-id"}
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "profiles",
                "create",
                "--name",
                "Development",
                "--type",
                "development",
                "--bundle-id",
                "com.example.app",
                "--cert",
                "cert-id",
                "--device",
                "device-1",
                "--device",
                "device-2",
            ],
        )

    assert result.exit_code == 0, result.output
    client.create_profile.assert_called_once_with(
        name="Development",
        bundle_id="portal-app-id",
        profile_type="development",
        certificate_ids=["cert-id"],
        device_ids=["device-1", "device-2"],
    )


def test_profile_creation_auto_selects_only_compatible_active_certificate() -> None:
    client = MagicMock()
    client.list_app_ids.return_value = [
        {"appIdId": "portal-app-id", "identifier": "com.example.app"}
    ]
    client.list_certificates.return_value = [
        {
            "certificateId": "development",
            "certificateType": "IOS_DEVELOPMENT",
            "status": "ACTIVE",
            "expirationDate": "2099-01-01T00:00:00Z",
        },
        {
            "certificateId": "expired",
            "certificateType": "IOS_DISTRIBUTION",
            "status": "ACTIVE",
            "expirationDate": "2020-01-01T00:00:00Z",
        },
        {
            "certificateId": "revoked",
            "certificateType": "IOS_DISTRIBUTION",
            "status": "REVOKED",
            "expirationDate": "2099-01-01T00:00:00Z",
        },
        {
            "certificateId": "distribution",
            "certificateType": "IOS_DISTRIBUTION",
            "statusString": "Issued",
            "expirationDate": "2099-01-01T00:00:00Z",
        },
    ]
    client.create_profile.return_value = {"provisioningProfileId": "profile-id"}
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "profiles",
                "create",
                "--name",
                "App Store",
                "--type",
                "appstore",
                "--bundle-id",
                "com.example.app",
            ],
        )

    assert result.exit_code == 0, result.output
    client.create_profile.assert_called_once_with(
        name="App Store",
        bundle_id="portal-app-id",
        profile_type="appstore",
        certificate_ids=["distribution"],
        device_ids=None,
    )


def test_profile_creation_rejects_ambiguous_automatic_certificate() -> None:
    client = MagicMock()
    client.list_app_ids.return_value = [
        {"appIdId": "portal-app-id", "identifier": "com.example.app"}
    ]
    client.list_certificates.return_value = [
        {
            "certificateId": certificate_id,
            "certificateType": "IOS_DISTRIBUTION",
            "status": "ACTIVE",
            "expirationDate": "2099-01-01T00:00:00Z",
        }
        for certificate_id in ("cert-1", "cert-2")
    ]
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(
            app,
            [
                "signing",
                "profiles",
                "create",
                "--name",
                "App Store",
                "--type",
                "appstore",
                "--bundle-id",
                "com.example.app",
            ],
        )

    assert result.exit_code == 1
    assert "Specify one with --cert: cert-1, cert-2" in result.output
    client.create_profile.assert_not_called()


def test_automatic_certificate_selection_requires_active_unexpired_match() -> None:
    certificates = [
        {
            "certificateId": "expired",
            "certificateType": "IOS_DISTRIBUTION",
            "status": "ACTIVE",
            "expirationDate": "2020-01-01T00:00:00Z",
        },
        {
            "certificateId": "inactive",
            "certificateType": "IOS_DISTRIBUTION",
            "status": "REVOKED",
            "expirationDate": "2099-01-01T00:00:00Z",
        },
    ]

    with pytest.raises(SlowlaneError, match="No active, unexpired distribution certificate"):
        signing._select_certificate_id(certificates, "appstore")


def test_signing_json_output_preserves_bracketed_values() -> None:
    certificates = [
        {
            "certificateId": "[certificate-id]",
            "name": "[bold]literal markup[/bold]",
            "certificateType": "IOS_DISTRIBUTION",
        }
    ]
    client = MagicMock()
    client.list_certificates.return_value = certificates
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(app, ["--json", "signing", "certs", "list"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == certificates
    assert "[bold]literal markup[/bold]" in result.stdout


@pytest.mark.parametrize(
    ("command", "method"),
    [
        (["signing", "certs", "list"], "list_certificates"),
        (["signing", "profiles", "list"], "list_profiles"),
    ],
)
def test_signing_empty_lists_are_valid_json(command: list[str], method: str) -> None:
    client = MagicMock()
    getattr(client, method).return_value = []
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(app, ["--json", *command])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize(
    ("error", "exit_code"),
    [
        (NetworkError("offline"), ExitCode.NETWORK_ERROR),
        (AuthExpiredError("expired"), ExitCode.AUTH_EXPIRED),
    ],
)
def test_signing_preserves_error_exit_code(error: SlowlaneError, exit_code: ExitCode) -> None:
    client = MagicMock()
    client.list_certificates.side_effect = error
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(app, ["signing", "certs", "list"])

    assert result.exit_code == exit_code
    assert str(error) in result.stderr


def test_signing_emits_structured_json_error() -> None:
    client = MagicMock()
    client.list_certificates.side_effect = NetworkError("offline")
    client_manager = MagicMock()
    client_manager.__enter__.return_value = client

    with (
        _config_patch(),
        patch("slowlane.cli.signing.require_session_auth", return_value=MagicMock()),
        patch("slowlane.cli.signing.DeveloperPortalClient", return_value=client_manager),
    ):
        result = runner.invoke(app, ["--json", "signing", "certs", "list"])

    assert result.exit_code == ExitCode.NETWORK_ERROR
    assert json.loads(result.stderr) == {
        "error": {
            "type": "NetworkError",
            "message": "offline",
            "exit_code": ExitCode.NETWORK_ERROR,
        }
    }
    assert result.stdout == ""
