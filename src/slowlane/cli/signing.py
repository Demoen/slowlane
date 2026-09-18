"""Signing assets managed through the App Store Connect API."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from slowlane.asc.client import normalize_certificate_type, normalize_profile_type, validate_csr
from slowlane.cli.asc import get_client, get_config, get_console, progress
from slowlane.core.errors import InvalidArgumentsError, SlowlaneError

app = typer.Typer(
    name="signing",
    help="Manage signing assets with a team App Store Connect API key.",
    no_args_is_help=True,
)
certs_app = typer.Typer(name="certs", help="Certificate management", no_args_is_help=True)
profiles_app = typer.Typer(name="profiles", help="Provisioning profiles", no_args_is_help=True)
devices_app = typer.Typer(
    name="devices", help="Registered development devices", no_args_is_help=True
)
app.add_typer(certs_app, name="certs")
app.add_typer(profiles_app, name="profiles")
app.add_typer(devices_app, name="devices")


def _result(ctx: typer.Context, resource: dict[str, Any], message: str) -> None:
    if get_config(ctx).output.format == "json":
        typer.echo(json.dumps(resource, indent=2))
    else:
        get_console(ctx).print(message, markup=False)


def _list(
    ctx: typer.Context,
    resources: list[dict[str, Any]],
    title: str,
    columns: list[tuple[str, str]],
) -> None:
    if get_config(ctx).output.format == "json":
        typer.echo(json.dumps(resources, indent=2))
        return
    if not resources:
        get_console(ctx).print(f"No {title.lower()} found.")
        return
    table = Table(title=title)
    table.add_column("ID", style="cyan")
    for label, _ in columns:
        table.add_column(label)
    for resource in resources:
        attributes = resource.get("attributes", {})
        table.add_row(resource["id"], *(str(attributes.get(field) or "") for _, field in columns))
    get_console(ctx).print(table)


def _confirm(ctx: typer.Context, force: bool, message: str) -> None:
    if force:
        return
    if get_config(ctx).output.format == "json" or not sys.stdin.isatty():
        raise InvalidArgumentsError(
            "Use --force to confirm this action in non-interactive or JSON mode"
        )
    if not typer.confirm(message, err=True):
        raise typer.Abort()


def _check_destination(path: Path) -> None:
    if path.exists():
        raise InvalidArgumentsError(f"Output already exists: {path}")
    if not path.parent.is_dir():
        raise InvalidArgumentsError(f"Output directory does not exist: {path.parent}")


def _write_download(ctx: typer.Context, path: Path, content: bytes, resource_id: str) -> None:
    try:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600
        )
    except OSError as exc:
        raise SlowlaneError(f"Unable to save download to {path}: {exc}") from exc
    try:
        output = os.fdopen(descriptor, "wb")
    except BaseException:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise
    try:
        with output:
            output.write(content)
    except BaseException as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, OSError):
            raise SlowlaneError(f"Unable to save download to {path}: {exc}") from exc
        raise
    _result(ctx, {"id": resource_id, "path": str(path), "bytes": len(content)}, f"Saved {path}")


@certs_app.command("list")
def certs_list(
    ctx: typer.Context,
    cert_type: str | None = typer.Option(None, "--type", "-t", help="Signing certificate type"),
) -> None:
    """List signing certificates."""
    normalized = normalize_certificate_type(cert_type, for_creation=False) if cert_type else None
    with progress(ctx, "Fetching certificates..."), get_client(ctx) as client:
        certificates = client.list_certificates(cert_type=normalized)
    _list(
        ctx,
        certificates,
        "Certificates",
        [
            ("Name", "name"),
            ("Type", "certificateType"),
            ("Expires", "expirationDate"),
        ],
    )


@certs_app.command("create")
def certs_create(
    ctx: typer.Context,
    cert_type: str = typer.Option(
        ..., "--type", "-t", help="development, distribution, or supported signing type"
    ),
    csr_path: Path = typer.Option(
        ...,
        "--csr",
        help="Existing PEM certificate signing request; retain its private key",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
) -> None:
    """Create a certificate from an existing, signed CSR."""
    normalized = normalize_certificate_type(cert_type)
    try:
        csr_content = csr_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InvalidArgumentsError(f"Unable to read CSR: {csr_path}") from exc
    validate_csr(csr_content)
    with progress(ctx, "Creating certificate..."), get_client(ctx) as client:
        certificate = client.create_certificate(csr_content=csr_content, cert_type=normalized)
    _result(ctx, certificate, f"Certificate created: {certificate['id']}")


@certs_app.command("revoke")
def certs_revoke(
    ctx: typer.Context,
    cert_id: str = typer.Argument(..., help="Certificate resource ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Confirm revocation without prompting"),
) -> None:
    """Revoke a certificate and invalidate profiles that use it."""
    _confirm(ctx, force, f"Revoke certificate {cert_id} and invalidate its provisioning profiles?")
    with progress(ctx, "Revoking certificate..."), get_client(ctx) as client:
        client.revoke_certificate(cert_id)
    _result(
        ctx,
        {"type": "certificates", "id": cert_id, "revoked": True},
        f"Certificate {cert_id} revoked.",
    )


@certs_app.command("download")
def certs_download(
    ctx: typer.Context,
    cert_id: str = typer.Argument(..., help="Certificate resource ID"),
    output: Path = typer.Option(..., "--output", "-o", help="New .cer file", dir_okay=False),
) -> None:
    """Download a certificate as DER without overwriting files."""
    _check_destination(output)
    with progress(ctx, "Downloading certificate..."), get_client(ctx) as client:
        content = client.download_certificate(cert_id)
    _write_download(ctx, output, content, cert_id)


@profiles_app.command("list")
def profiles_list(
    ctx: typer.Context,
    profile_type: str | None = typer.Option(
        None, "--type", "-t", help="development, appstore, or adhoc"
    ),
    app_id: str | None = typer.Option(None, "--app", "-a", help="Filter by bundle identifier"),
) -> None:
    """List provisioning profiles."""
    normalized = normalize_profile_type(profile_type) if profile_type else None
    with progress(ctx, "Fetching profiles..."), get_client(ctx) as client:
        profiles = client.list_profiles(profile_type=normalized, bundle_id=app_id)
    _list(
        ctx,
        profiles,
        "Provisioning profiles",
        [
            ("Name", "name"),
            ("Type", "profileType"),
            ("State", "profileState"),
            ("Expires", "expirationDate"),
        ],
    )


@profiles_app.command("create")
def profiles_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Profile name"),
    profile_type: str = typer.Option(..., "--type", "-t", help="development, appstore, or adhoc"),
    bundle_id: str = typer.Option(..., "--bundle-id", "-b", help="Registered bundle identifier"),
    cert_id: str = typer.Option(
        ..., "--cert", "-c", help="Certificate resource ID whose private key you hold"
    ),
    device_ids: list[str] | None = typer.Option(
        None, "--device", help="Device resource ID; repeat for multiple devices"
    ),
) -> None:
    """Create a profile using an explicitly selected certificate."""
    normalized = normalize_profile_type(profile_type)
    if not name.strip() or not bundle_id.strip() or not cert_id.strip():
        raise InvalidArgumentsError(
            "Name, bundle identifier, and certificate resource ID must be non-empty"
        )
    devices = list(dict.fromkeys(value.strip() for value in (device_ids or []) if value.strip()))
    if normalized == "IOS_APP_STORE" and devices:
        raise InvalidArgumentsError("--device is not allowed for appstore profiles")
    if normalized != "IOS_APP_STORE" and not devices:
        raise InvalidArgumentsError(
            "At least one --device is required for development and adhoc profiles"
        )
    with progress(ctx, "Creating profile..."), get_client(ctx) as client:
        bundle = client.resolve_bundle_id(bundle_id.strip())
        profile = client.create_profile(
            name=name.strip(),
            bundle_id=bundle["id"],
            profile_type=normalized,
            certificate_ids=[cert_id.strip()],
            device_ids=devices or None,
        )
    _result(ctx, profile, f"Profile created: {profile['id']}")


@profiles_app.command("delete")
def profiles_delete(
    ctx: typer.Context,
    profile_id: str = typer.Argument(..., help="Provisioning profile resource ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Confirm deletion without prompting"),
) -> None:
    """Delete a provisioning profile."""
    _confirm(ctx, force, f"Delete profile {profile_id}?")
    with progress(ctx, "Deleting profile..."), get_client(ctx) as client:
        client.delete_profile(profile_id)
    _result(
        ctx,
        {"type": "profiles", "id": profile_id, "deleted": True},
        f"Profile {profile_id} deleted.",
    )


@profiles_app.command("download")
def profiles_download(
    ctx: typer.Context,
    profile_id: str = typer.Argument(..., help="Provisioning profile resource ID"),
    output: Path = typer.Option(
        ..., "--output", "-o", help="New .mobileprovision file", dir_okay=False
    ),
) -> None:
    """Download a provisioning profile without overwriting files."""
    _check_destination(output)
    with progress(ctx, "Downloading profile..."), get_client(ctx) as client:
        content = client.download_profile(profile_id)
    _write_download(ctx, output, content, profile_id)


@devices_app.command("list")
def devices_list(ctx: typer.Context) -> None:
    """List device resource IDs for profile creation."""
    with progress(ctx, "Fetching devices..."), get_client(ctx) as client:
        devices = client.list_devices()
    _list(
        ctx,
        devices,
        "Devices",
        [
            ("Name", "name"),
            ("UDID", "udid"),
            ("Platform", "platform"),
            ("Status", "status"),
        ],
    )
