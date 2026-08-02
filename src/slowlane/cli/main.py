"""Main CLI entrypoint for slowlane."""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from pathlib import Path

import click
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

app = typer.Typer(
    name="slowlane",
    help="Command-line automation for App Store Connect and the Apple Developer Portal.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(spaceauth_app, name="spaceauth", help="Session authentication commands")
app.add_typer(asc_app, name="asc", help="App Store Connect operations")
app.add_typer(signing_app, name="signing", help="Certificates and provisioning profiles")
app.add_typer(upload_app, name="upload", help="Upload IPA/pkg files")
app.add_typer(env_app, name="env", help="CI environment helpers")

console = Console()
error_console = Console(stderr=True)
_effective_json_output = False


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"slowlane version {__version__}")
        raise typer.Exit()


def setup_logging(verbose: bool, json_output: bool) -> None:
    """Configure logging based on options."""
    if json_output:
        logging.basicConfig(
            level=logging.CRITICAL + 1,
            handlers=[logging.NullHandler()],
            force=True,
        )
    elif verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(message)s",
            handlers=[RichHandler(console=error_console, show_time=False, show_path=False)],
            force=True,
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(message)s",
            handlers=[RichHandler(console=error_console, show_time=False, show_path=False)],
            force=True,
        )


def _root_flag_enabled(*flags: str) -> bool:
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in flags:
            return True
        if arg in ("--config", "-c"):
            index += 2
            continue
        if arg.startswith("--config="):
            index += 1
            continue
        if arg == "--" or not arg.startswith("-"):
            return False
        index += 1
    return False


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true")


def _json_requested() -> bool:
    return _root_flag_enabled("--json") or _env_flag_enabled("SLOWLANE_JSON")


def _debug_requested() -> bool:
    return (
        _root_flag_enabled("--verbose", "-v")
        or _env_flag_enabled("SLOWLANE_VERBOSE")
        or logging.getLogger().isEnabledFor(logging.DEBUG)
    )


def _root_config_path() -> Path | None:
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("--config", "-c"):
            if index + 1 < len(args):
                return Path(args[index + 1])
            return None
        if arg.startswith("--config="):
            value = arg.partition("=")[2]
            return Path(value) if value else None
        if arg == "--" or not arg.startswith("-"):
            return None
        index += 1
    return None


def _preload_json_output() -> bool:
    requested = _json_requested()
    if requested or not sys.argv[1:] or _root_flag_enabled("--version", "-V", "--help"):
        return requested

    try:
        config = SlowlaneConfig.load(_root_config_path())
        config.apply_env_overrides()
    except SlowlaneError:
        return requested
    return config.output.format == "json"


def _emit_error(error_type: str, message: str, exit_code: int, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "error": {
                        "type": error_type,
                        "message": message,
                        "exit_code": exit_code,
                    }
                },
                separators=(",", ":"),
            ),
            err=True,
        )
        return
    label = "Unexpected error" if error_type == "UnexpectedError" else "Error"
    typer.echo(f"{label}: {message}", err=True)


def _print_traceback(error: BaseException, json_output: bool) -> None:
    if not json_output and _debug_requested():
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


@app.callback()
def main(
    ctx: typer.Context,
    show_version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version information and exit",
    ),
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
    """Command-line automation for Apple developer services."""
    global _effective_json_output

    config_file = Path(config_path) if config_path else None
    config = SlowlaneConfig.load(config_file)
    config.apply_env_overrides()

    if json_output:
        config.output.format = "json"
    if verbose:
        config.output.verbose = True

    _effective_json_output = config.output.format == "json"
    setup_logging(config.output.verbose, _effective_json_output)

    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["console"] = console


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"slowlane version {__version__}")


def run() -> None:
    """Main entry point with error handling."""
    global _effective_json_output
    _effective_json_output = _preload_json_output()
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int) and result:
            if result == 130:
                _emit_error("KeyboardInterrupt", "Interrupted", 130, _effective_json_output)
            raise SystemExit(result)
    except SlowlaneError as e:
        exit_code = int(e.exit_code)
        _emit_error(type(e).__name__, str(e), exit_code, _effective_json_output)
        _print_traceback(e, _effective_json_output)
        sys.exit(exit_code)
    except click.ClickException as e:
        message = e.format_message()
        if message:
            error_type = "UsageError" if isinstance(e, click.UsageError) else type(e).__name__
            _emit_error(error_type, message, e.exit_code, _effective_json_output)
        sys.exit(e.exit_code)
    except (click.Abort, KeyboardInterrupt) as e:
        _emit_error("KeyboardInterrupt", "Interrupted", 130, _effective_json_output)
        _print_traceback(e, _effective_json_output)
        sys.exit(130)
    except Exception as e:
        exit_code = int(ExitCode.GENERAL_ERROR)
        message = str(e) or type(e).__name__
        _emit_error("UnexpectedError", message, exit_code, _effective_json_output)
        _print_traceback(e, _effective_json_output)
        sys.exit(exit_code)


if __name__ == "__main__":
    run()
