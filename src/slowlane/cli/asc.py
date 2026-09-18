"""App Store Connect CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from slowlane.asc.client import AppStoreConnectClient
from slowlane.auth.jwt_auth import get_jwt_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AppStoreConnectError, AuthExpiredError
from slowlane.core.secrets import SecretStore

app = typer.Typer(
    name="asc",
    help="App Store Connect operations.",
    no_args_is_help=True,
)

apps_app = typer.Typer(name="apps", help="App management")
builds_app = typer.Typer(name="builds", help="Build management")
testflight_app = typer.Typer(name="testflight", help="TestFlight management")

app.add_typer(apps_app, name="apps")
app.add_typer(builds_app, name="builds")
app.add_typer(testflight_app, name="testflight")


def get_client(ctx: typer.Context) -> AppStoreConnectClient:
    """Get authenticated ASC client."""
    config = get_config(ctx)
    jwt_auth = get_jwt_auth(config)
    if jwt_auth is None and config.auth.key_id:
        jwt_auth = get_jwt_auth(config, SecretStore())
    if jwt_auth:
        return AppStoreConnectClient(jwt_auth=jwt_auth, config=config)

    raise AuthExpiredError(
        "App Store Connect API key authentication is required. Set "
        "ASC_KEY_ID and ASC_PRIVATE_KEY or ASC_PRIVATE_KEY_PATH. Team keys also require "
        "ASC_ISSUER_ID; individual keys require ASC_KEY_TYPE=individual without an issuer."
    )


def get_console(ctx: typer.Context) -> Console:
    """Get console from context."""
    if ctx.obj is None:
        return Console()
    console = ctx.obj.get("console")
    return console if isinstance(console, Console) else Console()


def get_config(ctx: typer.Context) -> SlowlaneConfig:
    """Get config from context."""
    if ctx.obj is None:
        return SlowlaneConfig.load()
    config = ctx.obj.get("config")
    return config if isinstance(config, SlowlaneConfig) else SlowlaneConfig.load()


def progress(ctx: typer.Context, message: str) -> AbstractContextManager[Any]:
    if get_config(ctx).output.format == "json":
        return nullcontext()
    return get_console(ctx).status(message)


def output_result(
    console: Console,
    data: dict[str, Any] | list[dict[str, Any]],
    format: str,
    table_builder: Callable[[Any], None] | None = None,
) -> None:
    """Output result in appropriate format."""
    if format == "json":
        typer.echo(json.dumps(data, indent=2, default=str))
    elif table_builder:
        table_builder(data)
    else:
        console.print(data)


@apps_app.command("list")
def apps_list(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-l", min=1, help="Max results"),
) -> None:
    """List apps in App Store Connect."""
    console = get_console(ctx)
    config = get_config(ctx)

    with progress(ctx, "[bold blue]Fetching apps...[/bold blue]"), get_client(ctx) as client:
        apps = client.list_apps(limit=limit)

    def build_table(data: list[dict[str, Any]]) -> None:
        table = Table(title="Apps")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Bundle ID")
        table.add_column("SKU")

        for app in data:
            attrs = app.get("attributes", {})
            table.add_row(
                app.get("id", ""),
                attrs.get("name", ""),
                attrs.get("bundleId", ""),
                attrs.get("sku", ""),
            )

        console.print(table)

    output_result(console, apps, config.output.format, build_table)


@apps_app.command("get")
def apps_get(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App ID or bundle ID"),
) -> None:
    """Get details for a specific app."""
    console = get_console(ctx)
    config = get_config(ctx)

    with progress(ctx, "[bold blue]Fetching app...[/bold blue]"), get_client(ctx) as client:
        app_data = client.get_app_by_bundle_id(app_id) if "." in app_id else client.get_app(app_id)

    if app_data is None:
        raise AppStoreConnectError(f"App not found: {app_id}")

    if config.output.format == "json":
        typer.echo(json.dumps(app_data, indent=2, default=str))
    else:
        attrs = app_data.get("attributes", {})
        console.print(f"[bold]App: {attrs.get('name', 'Unknown')}[/bold]")
        console.print(f"  ID: {app_data.get('id', '')}")
        console.print(f"  Bundle ID: {attrs.get('bundleId', '')}")
        console.print(f"  SKU: {attrs.get('sku', '')}")
        console.print(f"  Primary Locale: {attrs.get('primaryLocale', '')}")


@builds_app.command("list")
def builds_list(
    ctx: typer.Context,
    app_id: str | None = typer.Option(None, "--app", "-a", help="Filter by app ID"),
    limit: int = typer.Option(25, "--limit", "-l", min=1, help="Max results"),
) -> None:
    """List builds in App Store Connect."""
    console = get_console(ctx)
    config = get_config(ctx)

    with progress(ctx, "[bold blue]Fetching builds...[/bold blue]"), get_client(ctx) as client:
        builds = client.list_builds(app_id=app_id, limit=limit)

    def build_table(data: list[dict[str, Any]]) -> None:
        table = Table(title="Builds")
        table.add_column("ID", style="cyan")
        table.add_column("Build Number")
        table.add_column("Processing State")
        table.add_column("Uploaded")

        for build in data:
            attrs = build.get("attributes", {})
            table.add_row(
                build.get("id", ""),
                attrs.get("version", ""),
                attrs.get("processingState", ""),
                attrs.get("uploadedDate", "")[:10] if attrs.get("uploadedDate") else "",
            )

        console.print(table)

    output_result(console, builds, config.output.format, build_table)


@builds_app.command("latest")
def builds_latest(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App ID"),
) -> None:
    """Get the latest build for an app."""
    console = get_console(ctx)
    config = get_config(ctx)

    with (
        progress(ctx, "[bold blue]Fetching latest build...[/bold blue]"),
        get_client(ctx) as client,
    ):
        build = client.get_latest_build(app_id)

    if not build:
        if config.output.format == "json":
            typer.echo("null")
        else:
            console.print("[yellow]No builds found for this app[/yellow]")
        return

    if config.output.format == "json":
        typer.echo(json.dumps(build, indent=2, default=str))
    else:
        attrs = build.get("attributes", {})
        console.print("[bold]Latest Build[/bold]")
        console.print(f"  ID: {build.get('id', '')}")
        console.print(f"  Build Number: {attrs.get('version', '')}")
        console.print(f"  State: {attrs.get('processingState', '')}")
        console.print(f"  Uploaded: {attrs.get('uploadedDate', '')}")


@testflight_app.command("testers")
def testflight_testers(
    ctx: typer.Context,
    app_id: str | None = typer.Option(None, "--app", "-a", help="Filter by app ID"),
    limit: int = typer.Option(50, "--limit", "-l", min=1, help="Max results"),
) -> None:
    """List TestFlight testers."""
    console = get_console(ctx)
    config = get_config(ctx)

    with progress(ctx, "[bold blue]Fetching testers...[/bold blue]"), get_client(ctx) as client:
        testers = client.list_beta_testers(app_id=app_id, limit=limit)

    def build_table(data: list[dict[str, Any]]) -> None:
        table = Table(title="TestFlight Testers")
        table.add_column("ID", style="cyan")
        table.add_column("Email")
        table.add_column("First Name")
        table.add_column("Last Name")
        table.add_column("Invite Type")
        table.add_column("State")

        for tester in data:
            attrs = tester.get("attributes", {})
            table.add_row(
                tester.get("id", ""),
                attrs.get("email") or "",
                attrs.get("firstName") or "",
                attrs.get("lastName") or "",
                attrs.get("inviteType") or "",
                attrs.get("state") or "",
            )

        console.print(table)

    output_result(console, testers, config.output.format, build_table)


@testflight_app.command("groups")
def testflight_groups(
    ctx: typer.Context,
    app_id: str | None = typer.Option(None, "--app", "-a", help="Filter by app ID"),
) -> None:
    """List TestFlight beta groups."""
    console = get_console(ctx)
    config = get_config(ctx)

    with progress(ctx, "[bold blue]Fetching groups...[/bold blue]"), get_client(ctx) as client:
        groups = client.list_beta_groups(app_id=app_id)

    def build_table(data: list[dict[str, Any]]) -> None:
        table = Table(title="TestFlight Beta Groups")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Public Link Enabled")
        table.add_column("Internal")

        for group in data:
            attrs = group.get("attributes", {})
            table.add_row(
                group.get("id", ""),
                attrs.get("name", ""),
                "Yes" if attrs.get("publicLinkEnabled") else "No",
                "Yes" if attrs.get("isInternalGroup") else "No",
            )

        console.print(table)

    output_result(console, groups, config.output.format, build_table)


@testflight_app.command("invite")
def testflight_invite(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email address to invite"),
    group_id: str = typer.Option(..., "--group", "-g", help="Beta group ID"),
    first_name: str | None = typer.Option(None, "--first-name", help="First name"),
    last_name: str | None = typer.Option(None, "--last-name", help="Last name"),
) -> None:
    """Invite a tester to a TestFlight beta group."""
    console = get_console(ctx)
    config = get_config(ctx)

    with progress(ctx, "[bold blue]Inviting tester...[/bold blue]"), get_client(ctx) as client:
        tester = client.invite_beta_tester(
            email=email,
            group_id=group_id,
            first_name=first_name,
            last_name=last_name,
        )

    if config.output.format == "json":
        typer.echo(json.dumps(tester, indent=2, default=str))
    else:
        console.print(
            f"Added {email} to group {group_id}. Apple controls invitation delivery.", markup=False
        )
        console.print(f"  Tester ID: {tester.get('id', '')}")
