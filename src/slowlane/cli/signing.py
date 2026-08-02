"""Signing commands for certificates and provisioning profiles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from slowlane.auth.session_auth import SessionAuth, get_session_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import RateLimitError, SessionError, SlowlaneError
from slowlane.core.secrets import SecretStore
from slowlane.devportal.client import DeveloperPortalClient

app = typer.Typer(
    name="signing",
    help="Certificate and provisioning profile management.",
    no_args_is_help=True,
)

certs_app = typer.Typer(name="certs", help="Certificate management")
profiles_app = typer.Typer(name="profiles", help="Provisioning profile management")

app.add_typer(certs_app, name="certs")
app.add_typer(profiles_app, name="profiles")

_PROFILE_TYPE_ALIASES = {
    "development": "development",
    "appstore": "appstore",
    "app-store": "appstore",
    "app_store": "appstore",
    "adhoc": "adhoc",
    "ad-hoc": "adhoc",
    "ad_hoc": "adhoc",
}
_COMPATIBLE_CERTIFICATE_TYPES = {
    "development": {"DEVELOPMENT", "IOS_DEVELOPMENT", "APPLE_DEVELOPMENT"},
    "appstore": {"DISTRIBUTION", "IOS_DISTRIBUTION", "APPLE_DISTRIBUTION"},
    "adhoc": {"DISTRIBUTION", "IOS_DISTRIBUTION", "APPLE_DISTRIBUTION"},
}
_ACTIVE_CERTIFICATE_STATUSES = {"ACTIVE", "VALID", "ISSUED", "ENABLED"}


def get_console(ctx: typer.Context) -> Console:
    if ctx.obj is None:
        return Console()
    return cast(Console, ctx.obj.get("console", Console()))


def get_config(ctx: typer.Context) -> SlowlaneConfig:
    if ctx.obj is not None:
        config = ctx.obj.get("config")
        if isinstance(config, SlowlaneConfig):
            return config
    return SlowlaneConfig.load()


def require_session_auth() -> SessionAuth:
    session = get_session_auth(secret_store=SecretStore())
    if not session:
        raise SessionError(
            "Developer Portal session authentication is required. Run "
            "'slowlane spaceauth login --service developer'."
        )
    return session


def _handle_error(e: SlowlaneError, *, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "exit_code": int(e.exit_code),
                    }
                },
                separators=(",", ":"),
            ),
            err=True,
        )
        raise typer.Exit(code=e.exit_code) from e
    if isinstance(e, RateLimitError):
        hint = f" Retry after {e.retry_after}s." if e.retry_after else ""
        typer.echo(f"Error: Rate limited by Apple API.{hint}", err=True)
        raise typer.Exit(code=e.exit_code) from e
    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(code=e.exit_code) from e


def _resolve_app_id(client: DeveloperPortalClient, bundle_id: str) -> str:
    for app_id in client.list_app_ids():
        if app_id.get("identifier") != bundle_id:
            continue
        resource_id = app_id.get("appIdId") or app_id.get("id")
        if isinstance(resource_id, str) and resource_id:
            return resource_id
        break
    raise SlowlaneError(f"No Developer Portal App ID found for bundle identifier {bundle_id}")


def _normalize_identifier(value: object) -> str:
    return str(value).strip().replace("-", "_").replace(" ", "_").upper()


def _certificate_expiration(certificate: dict[str, Any]) -> datetime | None:
    value = certificate.get("expirationDate")
    if isinstance(value, datetime):
        expiration = value
    elif isinstance(value, str) and value.strip():
        try:
            expiration = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if expiration.tzinfo is None:
        return expiration.replace(tzinfo=UTC)
    return expiration.astimezone(UTC)


def _certificate_is_active(certificate: dict[str, Any]) -> bool:
    if certificate.get("isActive") is False or certificate.get("revoked") is True:
        return False
    if certificate.get("isActive") is True:
        return True

    status = next(
        (
            certificate[key]
            for key in ("status", "certificateStatus", "statusString", "statusCode")
            if certificate.get(key) is not None
        ),
        None,
    )
    if isinstance(status, bool):
        return status
    if isinstance(status, int):
        return status == 0
    return _normalize_identifier(status) in _ACTIVE_CERTIFICATE_STATUSES


def _select_certificate_id(certificates: list[dict[str, Any]], profile_type: str) -> str:
    compatible_types = _COMPATIBLE_CERTIFICATE_TYPES[profile_type]
    now = datetime.now(UTC)
    candidates: list[str] = []

    for certificate in certificates:
        certificate_type = _normalize_identifier(certificate.get("certificateType", ""))
        expiration = _certificate_expiration(certificate)
        certificate_id = certificate.get("certificateId") or certificate.get("id")
        if (
            certificate_type in compatible_types
            and _certificate_is_active(certificate)
            and expiration is not None
            and expiration > now
            and isinstance(certificate_id, str)
            and certificate_id
        ):
            candidates.append(certificate_id)

    certificate_kind = "development" if profile_type == "development" else "distribution"
    if not candidates:
        raise SlowlaneError(
            f"No active, unexpired {certificate_kind} certificate is compatible with "
            f"the {profile_type} profile. Create one or specify its ID with --cert."
        )
    if len(candidates) > 1:
        choices = ", ".join(candidates)
        raise SlowlaneError(
            f"Multiple active, unexpired {certificate_kind} certificates are compatible "
            f"with the {profile_type} profile. Specify one with --cert: {choices}"
        )
    return candidates[0]


@certs_app.command("list")
def certs_list(
    ctx: typer.Context,
    cert_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Certificate type: development, distribution, etc.",
    ),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """List signing certificates."""
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth()
    effective_team_id = team_id or config.devportal.team_id

    try:
        with (
            console.status("[bold blue]Fetching certificates...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            certs = client.list_certificates(cert_type=cert_type)
    except SlowlaneError as e:
        _handle_error(e, json_output=config.output.format == "json")
        return

    if config.output.format == "json":
        typer.echo(json.dumps(certs, indent=2, default=str))
        return

    if not certs:
        console.print("[yellow]No certificates found.[/yellow]")
        return

    table = Table(title="Certificates")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Expires")
    table.add_column("Status")

    for cert in certs:
        table.add_row(
            cert.get("certificateId", ""),
            cert.get("name", ""),
            cert.get("certificateType", ""),
            cert.get("expirationDate", ""),
            cert.get("status", ""),
        )

    console.print(table)


@certs_app.command("create")
def certs_create(
    ctx: typer.Context,
    cert_type: str = typer.Option(
        ...,
        "--type",
        "-t",
        help="Certificate type: development or distribution",
    ),
    csr_path: Path = typer.Option(
        ...,
        "--csr",
        help="Path to an existing CSR file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """Create a new signing certificate."""
    console = get_console(ctx)
    config = get_config(ctx)
    csr_content = csr_path.read_text(encoding="utf-8")
    if not csr_content.strip():
        raise typer.BadParameter("CSR file is empty", param_hint="--csr")
    session = require_session_auth()
    effective_team_id = team_id or config.devportal.team_id

    try:
        with (
            console.status("[bold blue]Creating certificate...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            cert = client.create_certificate(csr_content=csr_content, cert_type=cert_type)
    except SlowlaneError as e:
        _handle_error(e, json_output=config.output.format == "json")
        return

    console.print(f"[green]Certificate created: {cert.get('certificateId', '')}[/green]")


@certs_app.command("revoke")
def certs_revoke(
    ctx: typer.Context,
    cert_id: str = typer.Argument(..., help="Certificate ID to revoke"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """Revoke a signing certificate.

    WARNING: Revoking a certificate invalidates apps signed with it.
    """
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth()
    effective_team_id = team_id or config.devportal.team_id

    if not force:
        console.print(
            Panel(
                "[red bold]WARNING[/red bold]\n\n"
                "Revoking a certificate will:\n"
                "- Invalidate all provisioning profiles using this certificate\n"
                "- Require re-signing apps distributed with this certificate\n"
                "- Potentially break existing app installations\n\n"
                "[bold]This action cannot be undone![/bold]",
                title="Certificate Revocation",
            )
        )
        confirm = typer.confirm("Are you sure you want to revoke this certificate?")
        if not confirm:
            raise typer.Abort()

    try:
        with (
            console.status("[bold blue]Revoking certificate...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            client.revoke_certificate(cert_id)
    except SlowlaneError as e:
        _handle_error(e, json_output=config.output.format == "json")
        return

    console.print(f"[green]Certificate {cert_id} revoked.[/green]")


@profiles_app.command("list")
def profiles_list(
    ctx: typer.Context,
    profile_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Profile type: development, appstore, adhoc, enterprise",
    ),
    app_id: str | None = typer.Option(
        None,
        "--app",
        "-a",
        help="Filter by bundle ID",
    ),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """List provisioning profiles."""
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth()
    effective_team_id = team_id or config.devportal.team_id

    try:
        with (
            console.status("[bold blue]Fetching profiles...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            profiles = client.list_profiles(profile_type=profile_type)
    except SlowlaneError as e:
        _handle_error(e, json_output=config.output.format == "json")
        return

    if app_id:
        profiles = [p for p in profiles if p.get("appId", {}).get("identifier") == app_id]

    if config.output.format == "json":
        typer.echo(json.dumps(profiles, indent=2, default=str))
        return

    if not profiles:
        console.print("[yellow]No provisioning profiles found.[/yellow]")
        return

    table = Table(title="Provisioning Profiles")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Bundle ID")
    table.add_column("Expires")

    for profile in profiles:
        table.add_row(
            profile.get("provisioningProfileId", ""),
            profile.get("name", ""),
            profile.get("distributionMethod", ""),
            profile.get("appId", {}).get("identifier", ""),
            profile.get("expirationDate", ""),
        )

    console.print(table)


@profiles_app.command("create")
def profiles_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Profile name"),
    profile_type: str = typer.Option(
        ...,
        "--type",
        "-t",
        help="Profile type: development, appstore, adhoc",
    ),
    bundle_id: str = typer.Option(..., "--bundle-id", "-b", help="Bundle ID"),
    cert_id: str | None = typer.Option(
        None,
        "--cert",
        "-c",
        help="Certificate ID (auto-select if not provided)",
    ),
    device_ids: list[str] | None = typer.Option(
        None,
        "--device",
        help="Device ID to include; repeat for multiple devices",
    ),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """Create a new provisioning profile."""
    normalized_profile_type = _PROFILE_TYPE_ALIASES.get(profile_type.strip().lower())
    if normalized_profile_type is None:
        raise typer.BadParameter("must be development, appstore, or adhoc", param_hint="--type")

    normalized_device_ids = list(
        dict.fromkeys(device_id.strip() for device_id in (device_ids or []) if device_id.strip())
    )
    if normalized_profile_type in {"development", "adhoc"} and not normalized_device_ids:
        raise typer.BadParameter(
            f"at least one --device is required for {normalized_profile_type} profiles",
            param_hint="--device",
        )
    if normalized_profile_type == "appstore" and normalized_device_ids:
        raise typer.BadParameter(
            "--device is not allowed for appstore profiles", param_hint="--device"
        )

    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth()
    effective_team_id = team_id or config.devportal.team_id

    try:
        with (
            console.status("[bold blue]Creating profile...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            app_id_id = _resolve_app_id(client, bundle_id)
            if cert_id:
                certificate_ids = [cert_id]
            else:
                certificate_ids = [
                    _select_certificate_id(client.list_certificates(), normalized_profile_type)
                ]
                console.print(f"[dim]Auto-selected certificate: {certificate_ids[0]}[/dim]")

            profile = client.create_profile(
                name=name,
                bundle_id=app_id_id,
                profile_type=normalized_profile_type,
                certificate_ids=certificate_ids,
                device_ids=normalized_device_ids or None,
            )
    except SlowlaneError as e:
        _handle_error(e, json_output=config.output.format == "json")
        return

    console.print(f"[green]Profile created: {profile.get('provisioningProfileId', '')}[/green]")


@profiles_app.command("delete")
def profiles_delete(
    ctx: typer.Context,
    profile_id: str = typer.Argument(..., help="Profile ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """Delete a provisioning profile."""
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth()
    effective_team_id = team_id or config.devportal.team_id

    if not force:
        confirm = typer.confirm(f"Delete profile {profile_id}?")
        if not confirm:
            raise typer.Abort()

    try:
        with (
            console.status("[bold blue]Deleting profile...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            client.delete_profile(profile_id)
    except SlowlaneError as e:
        _handle_error(e, json_output=config.output.format == "json")
        return

    console.print(f"[green]Profile {profile_id} deleted.[/green]")
