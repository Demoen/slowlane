from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from typer.testing import CliRunner

from slowlane.cli import main as cli_main
from slowlane.cli import signing
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AccessDeniedError, NetworkError, RateLimitError, SlowlaneError
from tests.unit.test_asc_client import resource

runner = CliRunner()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    mock.__enter__.return_value = mock
    monkeypatch.setattr(signing, "get_client", MagicMock(return_value=mock))
    monkeypatch.setattr(cli_main.SlowlaneConfig, "load", MagicMock(return_value=SlowlaneConfig()))
    return mock


@pytest.fixture
def csr_path(tmp_path: Path) -> Path:
    key = ec.generate_private_key(ec.SECP256R1())
    request = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test certificate")]))
        .sign(key, hashes.SHA256())
    )
    path = tmp_path / "signing.csr"
    path.write_bytes(request.public_bytes(serialization.Encoding.PEM))
    return path


@pytest.mark.parametrize(
    "args,method,kind",
    [
        (["certs", "list"], "list_certificates", "certificates"),
        (["profiles", "list"], "list_profiles", "profiles"),
        (["devices", "list"], "list_devices", "devices"),
    ],
)
@pytest.mark.parametrize("empty", [False, True])
def test_lists_emit_only_raw_json_and_close_client(
    client: MagicMock,
    args: list[str],
    method: str,
    kind: str,
    empty: bool,
) -> None:
    records = [] if empty else [resource(kind, "resource-1", name="[red]literal[/red]")]
    getattr(client, method).return_value = records
    result = runner.invoke(cli_main.app, ["--json", "signing", *args])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == records
    assert result.stderr == ""
    client.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "args,method",
    [
        (["certs", "list"], "list_certificates"),
        (["profiles", "list"], "list_profiles"),
        (["devices", "list"], "list_devices"),
    ],
)
def test_empty_text_lists(client: MagicMock, args: list[str], method: str) -> None:
    getattr(client, method).return_value = []
    result = runner.invoke(cli_main.app, ["signing", *args])
    assert result.exit_code == 0
    assert "No " in result.stdout


def test_certificate_creation_uses_csr_and_emits_resource(
    client: MagicMock, csr_path: Path
) -> None:
    certificate = resource("certificates", "cert-1", name="[red]certificate[/red]")
    client.create_certificate.return_value = certificate
    result = runner.invoke(
        cli_main.app,
        [
            "--json",
            "signing",
            "certs",
            "create",
            "--type",
            "distribution",
            "--csr",
            str(csr_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == certificate
    assert client.create_certificate.call_args.kwargs == {
        "csr_content": csr_path.read_text(),
        "cert_type": "DISTRIBUTION",
    }


def test_profile_creation_requires_explicit_certificate(client: MagicMock) -> None:
    result = runner.invoke(
        cli_main.app,
        [
            "signing",
            "profiles",
            "create",
            "--name",
            "Profile",
            "--type",
            "appstore",
            "--bundle-id",
            "com.example.app",
        ],
    )
    assert result.exit_code != 0
    assert "--cert" in result.output
    client.create_profile.assert_not_called()
    client.list_certificates.assert_not_called()


def test_certificate_creation_requires_csr(client: MagicMock) -> None:
    result = runner.invoke(cli_main.app, ["signing", "certs", "create", "--type", "development"])
    assert result.exit_code != 0
    assert "--csr" in result.output
    client.create_certificate.assert_not_called()


def test_profile_creation_resolves_bundle_identifier_and_deduplicates_devices(
    client: MagicMock,
) -> None:
    client.resolve_bundle_id.return_value = resource("bundleIds", "bundle-1")
    profile = resource("profiles", "profile-1", name="[green]literal[/green]")
    client.create_profile.return_value = profile
    result = runner.invoke(
        cli_main.app,
        [
            "--json",
            "signing",
            "profiles",
            "create",
            "--name",
            "Profile",
            "--type",
            "ad-hoc",
            "--bundle-id",
            "com.example.app",
            "--cert",
            "cert-1",
            "--device",
            "one",
            "--device",
            "one",
            "--device",
            "two",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == profile
    client.resolve_bundle_id.assert_called_once_with("com.example.app")
    client.create_profile.assert_called_once_with(
        name="Profile",
        bundle_id="bundle-1",
        profile_type="IOS_APP_ADHOC",
        certificate_ids=["cert-1"],
        device_ids=["one", "two"],
    )
    client.list_certificates.assert_not_called()


def test_profile_list_passes_bundle_identifier_filter(client: MagicMock) -> None:
    client.list_profiles.return_value = []
    result = runner.invoke(
        cli_main.app,
        [
            "signing",
            "profiles",
            "list",
            "--app",
            "com.example.app",
            "--type",
            "appstore",
        ],
    )
    assert result.exit_code == 0
    client.list_profiles.assert_called_once_with(
        profile_type="IOS_APP_STORE", bundle_id="com.example.app"
    )


@pytest.mark.parametrize(
    "command,method,field",
    [
        (["certs", "revoke", "cert-1"], "revoke_certificate", "revoked"),
        (["profiles", "delete", "profile-1"], "delete_profile", "deleted"),
    ],
)
def test_destructive_commands_require_force_and_emit_json(
    client: MagicMock,
    command: list[str],
    method: str,
    field: str,
) -> None:
    result = runner.invoke(cli_main.app, ["--json", "signing", *command])
    assert result.exit_code != 0
    getattr(client, method).assert_not_called()
    result = runner.invoke(cli_main.app, ["--json", "signing", *command, "--force"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)[field] is True
    getattr(client, method).assert_called_once_with(command[-1])


@pytest.mark.parametrize(
    "error,exit_code",
    [
        (AccessDeniedError("No provisioning access"), 1),
        (NetworkError("offline"), 4),
        (RateLimitError("Slow down", retry_after=7), 3),
    ],
)
def test_signing_errors_have_stable_json_exit_codes(
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: SlowlaneError,
    exit_code: int,
) -> None:
    client.list_certificates.side_effect = error
    monkeypatch.setattr(sys, "argv", ["slowlane", "--json", "signing", "certs", "list"])
    with pytest.raises(SystemExit) as raised:
        cli_main.run()
    output = capsys.readouterr()
    assert raised.value.code == exit_code
    assert output.out == ""
    assert json.loads(output.err)["error"]["exit_code"] == exit_code


@pytest.mark.parametrize(
    "kind,method",
    [
        ("certs", "download_certificate"),
        ("profiles", "download_profile"),
    ],
)
def test_downloads_write_once_and_emit_json(
    client: MagicMock,
    tmp_path: Path,
    kind: str,
    method: str,
) -> None:
    target = tmp_path / "signing-asset"
    getattr(client, method).return_value = b"validated asset"
    args = ["--json", "signing", kind, "download", "id-1", "--output", str(target)]
    result = runner.invoke(cli_main.app, args)
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == b"validated asset"
    assert json.loads(result.stdout) == {"id": "id-1", "path": str(target), "bytes": 15}
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600
    result = runner.invoke(cli_main.app, args)
    assert result.exit_code != 0
    assert target.read_bytes() == b"validated asset"
    getattr(client, method).assert_called_once()


def test_download_failure_removes_new_partial_file(tmp_path: Path) -> None:
    target = tmp_path / "partial.mobileprovision"
    context = typer.Context(typer.main.get_command(signing.app), obj={"config": SlowlaneConfig()})
    original_fdopen = os.fdopen

    def failing_fdopen(fd: int, mode: str) -> Any:
        stream = original_fdopen(fd, mode)

        def write(content: bytes) -> None:
            stream.write(content[:1])
            raise OSError("disk full")

        wrapped = MagicMock(wraps=stream)
        wrapped.__enter__.return_value = wrapped
        wrapped.__exit__.side_effect = lambda *_: stream.close()
        wrapped.write.side_effect = write
        return wrapped

    with (
        patch.object(signing.os, "fdopen", side_effect=failing_fdopen),
        pytest.raises(SlowlaneError, match="disk full"),
    ):
        signing._write_download(context, target, b"profile", "id-1")
    assert not target.exists()


def test_exclusive_download_failure_preserves_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "existing.mobileprovision"
    target.write_bytes(b"existing")
    context = typer.Context(typer.main.get_command(signing.app), obj={"config": SlowlaneConfig()})
    with pytest.raises(SlowlaneError):
        signing._write_download(context, target, b"replacement", "id-1")
    assert target.read_bytes() == b"existing"


@pytest.mark.parametrize("command", [["certs", "list"], ["profiles", "list"]])
def test_removed_team_flag_is_rejected(client: MagicMock, command: list[str]) -> None:
    result = runner.invoke(cli_main.app, ["signing", *command, "--team-id", "TEAM"])
    assert result.exit_code != 0
