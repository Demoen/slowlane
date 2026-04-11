"""Signing commands for certificates and provisioning profiles."""

from __future__ import annotations

import json
from typing import Any, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from slowlane.auth.session_auth import SessionAuth, get_session_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import ExitCode, RateLimitError, SlowlaneError
from slowlane.core.secrets import SecretStore
from slowlane.devportal.client import DeveloperPortalClient

app = typer.Typer(
    name="signing",
    help="Certificate and provisioning profile management.",
    no_args_is_help=True,
)

# Subcommands
certs_app = typer.Typer(name="certs", help="Certificate management")
profiles_app = typer.Typer(name="profiles", help="Provisioning profile management")

app.add_typer(certs_app, name="certs")
app.add_typer(profiles_app, name="profiles")


def get_console(ctx: typer.Context) -> Console:
    if ctx.obj is None:
        return Console()
    return cast(Console, ctx.obj.get("console", Console()))


def get_config(ctx: typer.Context) -> SlowlaneConfig:
    if ctx.obj is None:
        return SlowlaneConfig.load()
    return cast(SlowlaneConfig, ctx.obj.get("config", SlowlaneConfig.load()))


def require_session_auth(console: Console) -> SessionAuth:
    session = get_session_auth(secret_store=SecretStore())
    if not session:
        console.print(
            Panel(
                "[red]Session authentication required[/red]\n\n"
                "Developer Portal operations require Apple ID session cookies.\n"
                "JWT authentication is not supported for these endpoints.\n\n"
                "Run: [bold]slowlane spaceauth login --service developer[/bold]",
                title="⚠️ Auth Required",
            )
        )
        raise typer.Exit(code=2)
    return session


def _handle_error(console: Console, e: SlowlaneError) -> None:
    if isinstance(e, RateLimitError):
        hint = f" Retry after {e.retry_after}s." if e.retry_after else ""
        console.print(f"[yellow]Rate limited by Apple API.[/yellow]{hint}")
        raise typer.Exit(code=ExitCode.RATE_LIMITED) from e
    console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(code=1) from e


# Certificate commands
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
    session = require_session_auth(console)
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
        _handle_error(console, e)
        return

    if not certs:
        console.print("[yellow]No certificates found.[/yellow]")
        return

    if config.output.format == "json":
        console.print(json.dumps(certs, indent=2, default=str))
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
    csr_path: str | None = typer.Option(
        None,
        "--csr",
        help="Path to CSR file (auto-generated if not provided)",
    ),
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """Create a new signing certificate."""
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth(console)
    effective_team_id = team_id or config.devportal.team_id

    if csr_path:
        import pathlib

        csr_content = pathlib.Path(csr_path).read_text()
    else:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "slowlane")]))
            .sign(key, hashes.SHA256())
        )
        csr_content = csr.public_bytes(serialization.Encoding.PEM).decode()
        console.print("[dim]Generated CSR automatically.[/dim]")

    try:
        with (
            console.status("[bold blue]Creating certificate...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            cert = client.create_certificate(csr_content=csr_content, cert_type=cert_type)
    except SlowlaneError as e:
        _handle_error(console, e)
        return

    console.print(f"[green]✓[/green] Certificate created: {cert.get('certificateId', '')}")


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

    ⚠️  WARNING: Revoking a certificate will invalidate all apps signed with it!
    """
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth(console)
    effective_team_id = team_id or config.devportal.team_id

    if not force:
        console.print(
            Panel(
                "[red bold]⚠️  WARNING[/red bold]\n\n"
                "Revoking a certificate will:\n"
                "• Invalidate all provisioning profiles using this certificate\n"
                "• Require re-signing any apps distributed with this certificate\n"
                "• Potentially break existing app installations\n\n"
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
        _handle_error(console, e)
        return

    console.print(f"[green]✓[/green] Certificate {cert_id} revoked.")


# Profile commands
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
    session = require_session_auth(console)
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
        _handle_error(console, e)
        return

    if app_id:
        profiles = [p for p in profiles if p.get("appId", {}).get("identifier") == app_id]

    if not profiles:
        console.print("[yellow]No provisioning profiles found.[/yellow]")
        return

    if config.output.format == "json":
        console.print(json.dumps(profiles, indent=2, default=str))
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
    team_id: str | None = typer.Option(
        None, "--team-id", help="Team ID (required for multiple teams)"
    ),
) -> None:
    """Create a new provisioning profile."""
    console = get_console(ctx)
    config = get_config(ctx)
    session = require_session_auth(console)
    effective_team_id = team_id or config.devportal.team_id

    try:
        with (
            console.status("[bold blue]Creating profile...[/bold blue]"),
            DeveloperPortalClient(
                session_auth=session, config=config, team_id=effective_team_id
            ) as client,
        ):
            if cert_id:
                certificate_ids = [cert_id]
            else:
                certs = client.list_certificates()
                if not certs:
                    console.print("[red]No certificates found to include in profile.[/red]")
                    raise typer.Exit(code=1)
                certificate_ids = [certs[0]["certificateId"]]
                console.print(f"[dim]Auto-selected certificate: {certificate_ids[0]}[/dim]")

            profile = client.create_profile(
                name=name,
                bundle_id=bundle_id,
                profile_type=profile_type,
                certificate_ids=certificate_ids,
            )
    except SlowlaneError as e:
        _handle_error(console, e)
        return

    console.print(f"[green]✓[/green] Profile created: {profile.get('provisioningProfileId', '')}")


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
    session = require_session_auth(console)
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
        _handle_error(console, e)
        return

    console.print(f"[green]✓[/green] Profile {profile_id} deleted.")


def _output_json(console: Console, data: Any) -> None:
    console.print(json.dumps(data, indent=2, default=str))
