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
    console = ctx.obj.get("console")
    return console if isinstance(console, Console) else Console()


def get_config(ctx: typer.Context) -> SlowlaneConfig:
    """Get config from context."""
    if ctx.obj is not None:
        config = ctx.obj.get("config")
        if isinstance(config, SlowlaneConfig):
            return config
    return SlowlaneConfig.load()


def _upload_asset(
    ctx: typer.Context,
    asset_path: Path,
    asset_type: str,
    validate_only: bool,
    skip_validation: bool,
) -> None:
    console = get_console(ctx)
    config = get_config(ctx)

    transporter_path = find_transporter()
    if not transporter_path:
        console.print(
            Panel(
                "[red]iTMSTransporter not found[/red]\n\n"
                "Install Xcode or the Transporter app on macOS, or set TRANSPORTER_PATH.",
                title="Transporter unavailable",
            )
        )
        raise typer.Exit(code=1)

    jwt_auth = get_jwt_auth(config)
    if jwt_auth is None and config.auth.key_id:
        jwt_auth = get_jwt_auth(config, SecretStore())
    if not jwt_auth:
        console.print(
            Panel(
                "[red]JWT authentication required[/red]\n\n"
                "IPA upload requires App Store Connect API key.\n"
                "Set these environment variables:\n"
                "- ASC_KEY_ID\n"
                "- ASC_ISSUER_ID\n"
                "- ASC_PRIVATE_KEY or ASC_PRIVATE_KEY_PATH",
                title="Authentication required",
            )
        )
        raise typer.Exit(code=2)

    console.print(f"[bold]{asset_type}:[/bold] {asset_path.name}")
    console.print(f"[bold]Transporter:[/bold] {transporter_path}")

    try:
        wrapper = TransporterWrapper(
            transporter_path=transporter_path,
            key_id=jwt_auth.key_id,
            issuer_id=jwt_auth.issuer_id,
            private_key_path=config.auth.private_key_path,
            private_key=jwt_auth.private_key,
            jwt_token_provider=jwt_auth.get_token,
            verbose=config.output.verbose,
        )

        if validate_only:
            with console.status(f"[bold blue]Validating {asset_type}...[/bold blue]"):
                wrapper.validate(asset_path)
            console.print("[green]Validation succeeded.[/green]")
        else:
            if not skip_validation:
                with console.status(f"[bold blue]Validating {asset_type}...[/bold blue]"):
                    wrapper.validate(asset_path)
                console.print("[green]Validation succeeded.[/green]")

            with console.status(f"[bold blue]Uploading {asset_type}...[/bold blue]"):
                wrapper.upload(asset_path)
            console.print("[green]Upload succeeded.[/green]")

    except TransporterError as e:
        console.print(f"[red]Upload failed:[/red] {e}")
        raise typer.Exit(code=1) from e


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
    """Upload an IPA file to App Store Connect."""
    if ipa_path.suffix.lower() != ".ipa":
        raise typer.BadParameter("Expected a .ipa file", param_hint="IPA_PATH")
    _upload_asset(ctx, ipa_path, "IPA", validate_only, skip_validation)


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
    if pkg_path.suffix.lower() != ".pkg":
        raise typer.BadParameter("Expected a .pkg file", param_hint="PKG_PATH")
    _upload_asset(ctx, pkg_path, "PKG", validate_only=False, skip_validation=False)
