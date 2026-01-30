"""Upload commands for IPA and package files."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from slowlane.auth.jwt_auth import get_jwt_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import TransporterError
from slowlane.core.secrets import SecretStore
from slowlane.transporter.wrapper import TransporterWrapper, find_transporter

app = typer.Typer(
    name="upload",
    help="Upload IPA/pkg files to App Store Connect.",
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


@app.command("ipa")
def upload_ipa(
    ctx: typer.Context,
    ipa_path: Path = typer.Argument(
        ...,
        help="Path to IPA file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        "-v",
        help="Validate without uploading",
    ),
    skip_validation: bool = typer.Option(
        False,
        "--skip-validation",
        help="Skip validation step",
    ),
) -> None:
    """Upload an IPA file to App Store Connect.

    Uses Apple's iTMSTransporter for reliable uploads.
    Requires JWT authentication (API key).
    """
    console = get_console(ctx)
    config = get_config(ctx)

    # Check for transporter
    transporter_path = find_transporter()
    if not transporter_path:
        console.print(
            Panel(
                "[red]iTMSTransporter not found[/red]\n\n"
                "The transporter is required for IPA uploads. It's included with:\n"
                "• Xcode (macOS)\n"
                "• Transporter.app (macOS - available on App Store)\n\n"
                "Alternatively, you can use altool or the App Store Connect website.",
                title="⚠️ Transporter Missing",
            )
        )
        raise typer.Exit(code=1)

    # Get JWT auth
    jwt_auth = get_jwt_auth(config, SecretStore())
    if not jwt_auth:
        console.print(
            Panel(
                "[red]JWT authentication required[/red]\n\n"
                "IPA upload requires App Store Connect API key.\n"
                "Set these environment variables:\n"
                "• ASC_KEY_ID\n"
                "• ASC_ISSUER_ID\n"
                "• ASC_PRIVATE_KEY or ASC_PRIVATE_KEY_PATH",
                title="⚠️ Auth Required",
            )
        )
        raise typer.Exit(code=2)

    console.print(f"[bold]Uploading:[/bold] {ipa_path.name}")
    console.print(f"[bold]Transporter:[/bold] {transporter_path}")

    try:
        wrapper = TransporterWrapper(
            transporter_path=transporter_path,
            key_id=jwt_auth.key_id,
            issuer_id=jwt_auth.issuer_id,
        )

        if validate_only:
            with console.status("[bold blue]Validating IPA...[/bold blue]"):
                wrapper.validate(ipa_path)
            console.print("[green]✓[/green] Validation successful!")
        else:
            if not skip_validation:
                with console.status("[bold blue]Validating IPA...[/bold blue]"):
                    wrapper.validate(ipa_path)
                console.print("[green]✓[/green] Validation passed")

            with console.status("[bold blue]Uploading IPA...[/bold blue]"):
                wrapper.upload(ipa_path)
            console.print("[green]✓[/green] Upload successful!")

    except TransporterError as e:
        console.print(f"[red]Upload failed:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command("pkg")
def upload_pkg(
    ctx: typer.Context,
    pkg_path: Path = typer.Argument(
        ...,
        help="Path to pkg file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Upload a macOS pkg file to App Store Connect."""
    console = get_console(ctx)

    # Same logic as IPA upload
    console.print("[yellow]pkg upload uses the same transporter flow as IPA[/yellow]")
    console.print(f"Path: {pkg_path}")

    # Reuse IPA upload logic
    ctx.invoke(upload_ipa, ipa_path=pkg_path)
