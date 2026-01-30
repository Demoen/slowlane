"""Main CLI entrypoint for slowlane."""

from __future__ import annotations

import logging
import sys

import typer
from rich.console import Console
from rich.logging import RichHandler

from slowlane import __version__
from slowlane.cli.asc import app as asc_app
from slowlane.cli.env import app as env_app
from slowlane.cli.signing import app as signing_app
from slowlane.cli.spaceauth import app as spaceauth_app
from slowlane.cli.upload import app as upload_app
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import ExitCode, SlowlaneError

# Create Typer app
app = typer.Typer(
    name="slowlane",
    help="Python CLI for Apple service automation - fastlane-compatible authentication and App Store Connect operations.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Add subcommands
app.add_typer(spaceauth_app, name="spaceauth", help="Session authentication commands")
app.add_typer(asc_app, name="asc", help="App Store Connect operations")
app.add_typer(signing_app, name="signing", help="Certificates and provisioning profiles")
app.add_typer(upload_app, name="upload", help="Upload IPA/pkg files")
app.add_typer(env_app, name="env", help="CI environment helpers")

# Console for rich output
console = Console()


def setup_logging(verbose: bool, json_output: bool) -> None:
    """Configure logging based on options."""
    if json_output:
        # JSON output - minimal logging
        logging.basicConfig(
            level=logging.WARNING,
            format='{"level": "%(levelname)s", "message": "%(message)s"}',
        )
    elif verbose:
        # Verbose - rich handler with debug
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(message)s",
            handlers=[RichHandler(console=console, show_time=False, show_path=False)],
        )
    else:
        # Normal - warnings and errors only
        logging.basicConfig(
            level=logging.WARNING,
            format="%(message)s",
            handlers=[RichHandler(console=console, show_time=False, show_path=False)],
        )


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format (for CI)",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file",
    ),
) -> None:
    """slowlane - Python CLI for Apple service automation."""
    # Set up logging
    setup_logging(verbose, json_output)

    # Load config
    from pathlib import Path

    config_file = Path(config_path) if config_path else None
    config = SlowlaneConfig.load(config_file)
    config.apply_env_overrides()

    # Apply CLI overrides
    if json_output:
        config.output.format = "json"
    if verbose:
        config.output.verbose = True

    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["console"] = console


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"slowlane version {__version__}")


def run() -> None:
    """Main entry point with error handling."""
    try:
        app()
    except SlowlaneError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        logging.exception("Unexpected error")
        sys.exit(ExitCode.GENERAL_ERROR)


if __name__ == "__main__":
    run()
