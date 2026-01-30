"""Spaceauth commands for session authentication."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from slowlane.auth.playwright_login import interactive_login
from slowlane.auth.session_auth import get_session_auth, validate_session_cookies
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import SessionError
from slowlane.core.secrets import SecretStore

app = typer.Typer(
    name="spaceauth",
    help="Session authentication commands for Apple ID login.",
    no_args_is_help=True,
)


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


@app.command()
def login(
    ctx: typer.Context,
    email: str | None = typer.Option(
        None,
        "--email",
        "-e",
        help="Apple ID email (optional, for session storage)",
    ),
    service: str = typer.Option(
        "appstoreconnect",
        "--service",
        "-s",
        help="Target service: appstoreconnect or developer",
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Run browser in headless mode (not recommended)",
    ),
) -> None:
    """Interactive login via browser.

    Opens a browser window for you to complete Apple ID login,
    including 2FA verification. Cookies are extracted and stored
    securely for future use.
    """
    console = get_console(ctx)

    console.print(
        Panel(
            "[bold]Interactive Apple ID Login[/bold]\n\n"
            "A browser window will open. Please:\n"
            "1. Enter your Apple ID credentials\n"
            "2. Complete 2FA verification if prompted\n"
            "3. Wait for the page to load fully\n\n"
            "[dim]The browser will close automatically once login is detected.[/dim]",
            title="🍎 Spaceauth Login",
        )
    )

    try:
        with console.status("[bold blue]Launching browser...[/bold blue]"):
            session_data = interactive_login(headless=headless, target_service=service)

        # Validate cookies
        missing = validate_session_cookies(session_data.cookies)
        if missing:
            console.print(
                f"[yellow]Warning:[/yellow] Missing cookies: {', '.join(missing)}"
            )

        # Store session
        if email:
            secret_store = SecretStore()
            secret_store.store_session(email, session_data)
            console.print(f"[green]✓[/green] Session stored for {email}")
        else:
            console.print(
                "[yellow]Note:[/yellow] Session not stored (no --email provided). "
                "Use 'spaceauth export' to get the session string."
            )

        # Show session info
        console.print("\n[green]✓ Login successful![/green]")
        console.print(f"  Cookies captured: {len(session_data.cookies)}")
        console.print(f"  Service: {session_data.target_service}")

    except SessionError as e:
        console.print(f"[red]Login failed:[/red] {e}")
        raise typer.Exit(code=2) from e
    except ImportError as e:
        console.print(
            "[red]Playwright not installed.[/red]\n\n"
            "Install it with:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )
        raise typer.Exit(code=1) from e


@app.command()
def export(
    ctx: typer.Context,
    email: str | None = typer.Option(
        None,
        "--email",
        "-e",
        help="Apple ID email to export session for",
    ),
) -> None:
    """Export session as FASTLANE_SESSION environment variable.

    Prints a single line that can be used in CI:
        export FASTLANE_SESSION="..."
    """
    console = get_console(ctx)
    config = get_config(ctx)

    # Try to get session
    session_auth = get_session_auth(email=email, secret_store=SecretStore())

    if not session_auth:
        console.print("[red]No session found.[/red] Run 'spaceauth login' first.")
        raise typer.Exit(code=2)

    export_str = session_auth.to_export_string()

    if config.output.format == "json":
        import json

        console.print(json.dumps({"FASTLANE_SESSION": export_str}))
    else:
        console.print(f'export FASTLANE_SESSION="{export_str}"')


@app.command()
def verify(
    ctx: typer.Context,
    email: str | None = typer.Option(
        None,
        "--email",
        "-e",
        help="Apple ID email to verify session for",
    ),
) -> None:
    """Verify that a session is still valid.

    Attempts to make a request to Apple's API to verify
    the session cookies are still valid.
    """
    console = get_console(ctx)

    session_auth = get_session_auth(email=email, secret_store=SecretStore())

    if not session_auth:
        console.print("[red]No session found.[/red] Run 'spaceauth login' first.")
        raise typer.Exit(code=2)

    # Basic validation
    if not session_auth.validate():
        console.print("[red]Session invalid:[/red] Missing required cookies")
        raise typer.Exit(code=2)

    if session_auth.is_stale:
        console.print(
            "[yellow]Warning:[/yellow] Session is older than 7 days and may be expired"
        )

    # TODO: Make actual API request to verify
    console.print("[green]✓[/green] Session appears valid (basic check)")
    console.print(f"  Created: {session_auth.created_at}")
    console.print(f"  Cookies: {len(session_auth.cookies)}")


@app.command()
def revoke(
    ctx: typer.Context,
    email: str = typer.Option(
        ...,
        "--email",
        "-e",
        help="Apple ID email to revoke session for",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
) -> None:
    """Revoke and delete a stored session."""
    console = get_console(ctx)

    if not force:
        confirm = typer.confirm(f"Delete session for {email}?")
        if not confirm:
            raise typer.Abort()

    secret_store = SecretStore()
    secret_store.delete_session(email)

    console.print(f"[green]✓[/green] Session deleted for {email}")


@app.command()
def doctor(
    ctx: typer.Context,
) -> None:
    """Diagnose authentication issues.

    Checks for:
    - Required dependencies
    - Environment variables
    - Stored credentials
    - Config file
    """
    console = get_console(ctx)
    config = get_config(ctx)

    table = Table(title="Auth Diagnostics")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    # Check Playwright
    try:
        from importlib.metadata import version as get_version
        pw_version = get_version("playwright")
        table.add_row("Playwright", "[green]✓ Installed[/green]", pw_version)
    except ImportError:
        table.add_row("Playwright", "[red]✗ Not installed[/red]", "pip install playwright")

    # Check JWT credentials
    from slowlane.auth.jwt_auth import JWTCredentials

    jwt_creds = JWTCredentials.from_env()
    if jwt_creds:
        table.add_row(
            "JWT (env)",
            "[green]✓ Configured[/green]",
            f"Key ID: {jwt_creds.key_id[:8]}...",
        )
    else:
        table.add_row("JWT (env)", "[yellow]○ Not set[/yellow]", "ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY")

    # Check config
    if config.auth.key_id:
        table.add_row(
            "JWT (config)",
            "[green]✓ Configured[/green]",
            f"Key ID: {config.auth.key_id[:8]}...",
        )
    else:
        table.add_row("JWT (config)", "[yellow]○ Not set[/yellow]", "~/.config/slowlane/config.toml")

    # Check session env
    import os

    if os.environ.get("FASTLANE_SESSION"):
        table.add_row("Session (env)", "[green]✓ Set[/green]", "FASTLANE_SESSION")
    else:
        table.add_row("Session (env)", "[yellow]○ Not set[/yellow]", "Run 'spaceauth login' or 'spaceauth export'")

    # Check secret store
    try:
        secret_store = SecretStore()
        backend_name = type(secret_store._backend).__name__
        table.add_row("Secret Store", "[green]✓ Available[/green]", backend_name)
    except Exception as e:
        table.add_row("Secret Store", "[red]✗ Error[/red]", str(e))

    console.print(table)
