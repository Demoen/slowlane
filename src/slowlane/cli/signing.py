"""Signing commands for certificates and provisioning profiles."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from slowlane.core.config import SlowlaneConfig
from slowlane.core.secrets import SecretStore

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
    """Get console from context."""
    if ctx.obj is None:
        return Console()
    return ctx.obj.get("console", Console())


def get_config(ctx: typer.Context) -> SlowlaneConfig:
    """Get config from context."""
    if ctx.obj is None:
        return SlowlaneConfig.load()
    return ctx.obj.get("config", SlowlaneConfig.load())


def require_session_auth(console: Console) -> None:
    """Check for session auth (required for Developer Portal)."""
    from slowlane.auth.session_auth import get_session_auth

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
) -> None:
    """List signing certificates."""
    console = get_console(ctx)
    get_config(ctx)

    require_session_auth(console)

    # TODO: Implement actual API call
    console.print("[yellow]Certificate listing not yet implemented[/yellow]")
    console.print("This feature requires Developer Portal session authentication.")

    # Placeholder data for demonstration
    table = Table(title="Certificates (placeholder)")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Expires")
    table.add_column("Status")

    table.add_row(
        "ABC123",
        "iOS Distribution",
        "distribution",
        "2025-12-31",
        "Active",
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
) -> None:
    """Create a new signing certificate."""
    console = get_console(ctx)

    require_session_auth(console)

    console.print(
        Panel(
            "[yellow]Certificate creation not yet implemented[/yellow]\n\n"
            "This will:\n"
            "1. Generate a CSR if not provided\n"
            "2. Submit to Apple Developer Portal\n"
            "3. Download and install the certificate",
            title="🔏 Create Certificate",
        )
    )


@certs_app.command("revoke")
def certs_revoke(
    ctx: typer.Context,
    cert_id: str = typer.Argument(..., help="Certificate ID to revoke"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Revoke a signing certificate.

    ⚠️  WARNING: Revoking a certificate will invalidate all apps signed with it!
    """
    console = get_console(ctx)

    require_session_auth(console)

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

    console.print("[yellow]Certificate revocation not yet implemented[/yellow]")


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
) -> None:
    """List provisioning profiles."""
    console = get_console(ctx)
    get_config(ctx)

    require_session_auth(console)

    console.print("[yellow]Profile listing not yet implemented[/yellow]")

    # Placeholder
    table = Table(title="Provisioning Profiles (placeholder)")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Bundle ID")
    table.add_column("Expires")

    table.add_row(
        "PROF123",
        "MyApp Development",
        "development",
        "com.example.myapp",
        "2025-12-31",
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
) -> None:
    """Create a new provisioning profile."""
    console = get_console(ctx)

    require_session_auth(console)

    console.print(
        Panel(
            f"[yellow]Profile creation not yet implemented[/yellow]\n\n"
            f"Will create: {name}\n"
            f"Type: {profile_type}\n"
            f"Bundle ID: {bundle_id}",
            title="📦 Create Profile",
        )
    )


@profiles_app.command("delete")
def profiles_delete(
    ctx: typer.Context,
    profile_id: str = typer.Argument(..., help="Profile ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a provisioning profile."""
    console = get_console(ctx)

    require_session_auth(console)

    if not force:
        confirm = typer.confirm(f"Delete profile {profile_id}?")
        if not confirm:
            raise typer.Abort()

    console.print("[yellow]Profile deletion not yet implemented[/yellow]")
