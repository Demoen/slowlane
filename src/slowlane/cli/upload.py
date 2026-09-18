"""Upload commands for IPA and package files."""

from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.console import Console

from slowlane.auth.jwt_auth import get_jwt_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AuthExpiredError, TransporterError
from slowlane.core.secrets import SecretStore
from slowlane.transporter.wrapper import TransporterWrapper, find_transporter, require_macos

app = typer.Typer(
    name="upload",
    help="Validate and upload IPA/pkg files on macOS using a team API key.",
    no_args_is_help=True,
)


def get_console(ctx: typer.Context) -> Console:
    if ctx.obj is None:
        return Console()
    console = ctx.obj.get("console")
    return console if isinstance(console, Console) else Console()


def get_config(ctx: typer.Context) -> SlowlaneConfig:
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
    if validate_only and skip_validation:
        raise typer.BadParameter("--validate-only and --skip-validation cannot be used together")
    require_macos()
    console = get_console(ctx)
    config = get_config(ctx)
    json_output = config.output.format == "json"
    transporter_path = find_transporter()
    if not transporter_path:
        raise TransporterError(
            "No upload tool found. Install Xcode or Transporter, or set TRANSPORTER_PATH."
        )

    jwt_auth = get_jwt_auth(config)
    if jwt_auth is None and config.auth.key_id:
        jwt_auth = get_jwt_auth(config, SecretStore())
    if not jwt_auth:
        raise AuthExpiredError(
            "Uploads require a team App Store Connect API key. Configure ASC_KEY_ID, "
            "ASC_ISSUER_ID, and ASC_PRIVATE_KEY or ASC_PRIVATE_KEY_PATH."
        )
    if jwt_auth.key_type != "team":
        raise AuthExpiredError("Uploads require a team API key; individual keys are not supported")

    wrapper = TransporterWrapper(
        transporter_path=transporter_path,
        key_id=jwt_auth.key_id,
        issuer_id=jwt_auth.issuer_id,
        private_key_path=config.auth.private_key_path,
        private_key=jwt_auth.private_key,
        jwt_token_provider=jwt_auth.get_token,
        verbose=config.output.verbose,
    )
    if not json_output:
        console.print(f"{asset_type}: {asset_path.name}", markup=False)
        console.print(f"Transporter: {transporter_path}", markup=False)

    if not skip_validation:
        with (
            nullcontext()
            if json_output
            else console.status(f"[bold blue]Validating {asset_type}...[/bold blue]")
        ):
            wrapper.validate(asset_path)
    if not validate_only:
        with (
            nullcontext()
            if json_output
            else console.status(f"[bold blue]Uploading {asset_type}...[/bold blue]")
        ):
            wrapper.upload(asset_path)

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "operation": "validate" if validate_only else "upload",
                    "asset": str(asset_path),
                    "asset_type": asset_type.lower(),
                    "validated": not skip_validation,
                    "uploaded": not validate_only,
                }
            )
        )
    elif validate_only:
        console.print("[green]Validation succeeded.[/green]")
    else:
        console.print(
            "[green]Upload delivered.[/green] Apple must finish processing before the build is available."
        )


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
        False, "--validate-only", "-v", help="Validate without uploading"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip the separate validation step"
    ),
) -> None:
    """Upload an IPA file to App Store Connect from macOS."""
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
    validate_only: bool = typer.Option(
        False, "--validate-only", "-v", help="Validate without uploading"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip the separate validation step"
    ),
) -> None:
    """Upload a macOS pkg file to App Store Connect from macOS."""
    if pkg_path.suffix.lower() != ".pkg":
        raise typer.BadParameter("Expected a .pkg file", param_hint="PKG_PATH")
    _upload_asset(ctx, pkg_path, "PKG", validate_only, skip_validation)
