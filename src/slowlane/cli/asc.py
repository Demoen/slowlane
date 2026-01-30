"""App Store Connect CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from slowlane.asc.client import AppStoreConnectClient
from slowlane.auth.jwt_auth import get_jwt_auth
from slowlane.auth.session_auth import get_session_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.errors import AuthExpiredError
from slowlane.core.secrets import SecretStore

app = typer.Typer(
    name="asc",
    help="App Store Connect operations.",
    no_args_is_help=True,
)

# Subcommands
apps_app = typer.Typer(name="apps", help="App management")
builds_app = typer.Typer(name="builds", help="Build management")
testflight_app = typer.Typer(name="testflight", help="TestFlight management")

app.add_typer(apps_app, name="apps")
app.add_typer(builds_app, name="builds")
app.add_typer(testflight_app, name="testflight")


def get_client(ctx: typer.Context) -> AppStoreConnectClient:
    """Get authenticated ASC client."""
    if ctx.obj is None:
        config = SlowlaneConfig.load()
    else:
        config = ctx.obj.get("config", SlowlaneConfig.load())
    secret_store = SecretStore()

    # Try JWT first
    jwt_auth = get_jwt_auth(config, secret_store)
    if jwt_auth:
        return AppStoreConnectClient(jwt_auth=jwt_auth, config=config)

    # Fall back to session
    session_auth = get_session_auth(secret_store=secret_store)
    if session_auth:
        return AppStoreConnectClient(session_auth=session_auth, config=config)

    raise AuthExpiredError(
        "No authentication configured. Either set ASC_KEY_ID/ASC_ISSUER_ID/ASC_PRIVATE_KEY "
        "or run 'spaceauth login'"
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


def output_result(
    console: Console,
    data: dict[str, Any] | list[dict[str, Any]],
    format: str,
    table_builder: Callable[[Any], None] | None = None,
) -> None:
    """Output result in appropriate format."""
    if format == "json":
        console.print(json.dumps(data, indent=2, default=str))
    elif table_builder:
        table_builder(data)
    else:
        console.print(data)


# Apps commands
@apps_app.command("list")
def apps_list(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
) -> None:
    """List all apps in App Store Connect."""
    console = get_console(ctx)
    config = get_config(ctx)

    with console.status("[bold blue]Fetching apps...[/bold blue]"):
        client = get_client(ctx)
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

    with console.status("[bold blue]Fetching app...[/bold blue]"):
        client = get_client(ctx)
        app_data = client.get_app(app_id)

    if config.output.format == "json":
        console.print(json.dumps(app_data, indent=2, default=str))
    else:
        attrs = app_data.get("attributes", {})
        console.print(f"[bold]App: {attrs.get('name', 'Unknown')}[/bold]")
        console.print(f"  ID: {app_data.get('id', '')}")
        console.print(f"  Bundle ID: {attrs.get('bundleId', '')}")
        console.print(f"  SKU: {attrs.get('sku', '')}")
        console.print(f"  Primary Locale: {attrs.get('primaryLocale', '')}")


# Builds commands
@builds_app.command("list")
def builds_list(
    ctx: typer.Context,
    app_id: str | None = typer.Option(None, "--app", "-a", help="Filter by app ID"),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results"),
) -> None:
    """List builds in App Store Connect."""
    console = get_console(ctx)
    config = get_config(ctx)

    with console.status("[bold blue]Fetching builds...[/bold blue]"):
        client = get_client(ctx)
        builds = client.list_builds(app_id=app_id, limit=limit)

    def build_table(data: list[dict[str, Any]]) -> None:
        table = Table(title="Builds")
        table.add_column("ID", style="cyan")
        table.add_column("Version")
        table.add_column("Build Number")
        table.add_column("Processing State")
        table.add_column("Uploaded")

        for build in data:
            attrs = build.get("attributes", {})
            table.add_row(
                build.get("id", ""),
                attrs.get("version", ""),
                attrs.get("buildVersionIdentifier", ""),
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

    with console.status("[bold blue]Fetching latest build...[/bold blue]"):
        client = get_client(ctx)
        build = client.get_latest_build(app_id)

    if not build:
        console.print("[yellow]No builds found for this app[/yellow]")
        return

    if config.output.format == "json":
        console.print(json.dumps(build, indent=2, default=str))
    else:
        attrs = build.get("attributes", {})
        console.print("[bold]Latest Build[/bold]")
        console.print(f"  ID: {build.get('id', '')}")
        console.print(f"  Version: {attrs.get('version', '')}")
        console.print(f"  Build Number: {attrs.get('buildVersionIdentifier', '')}")
        console.print(f"  State: {attrs.get('processingState', '')}")
        console.print(f"  Uploaded: {attrs.get('uploadedDate', '')}")


# TestFlight commands
@testflight_app.command("testers")
def testflight_testers(
    ctx: typer.Context,
    app_id: str | None = typer.Option(None, "--app", "-a", help="Filter by app ID"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
) -> None:
    """List TestFlight testers."""
    console = get_console(ctx)
    config = get_config(ctx)

    with console.status("[bold blue]Fetching testers...[/bold blue]"):
        client = get_client(ctx)
        testers = client.list_beta_testers(app_id=app_id, limit=limit)

    def build_table(data: list[dict[str, Any]]) -> None:
        table = Table(title="TestFlight Testers")
        table.add_column("ID", style="cyan")
        table.add_column("Email")
        table.add_column("First Name")
        table.add_column("Last Name")
        table.add_column("Invite Type")

        for tester in data:
            attrs = tester.get("attributes", {})
            table.add_row(
                tester.get("id", ""),
                attrs.get("email", ""),
                attrs.get("firstName", ""),
                attrs.get("lastName", ""),
                attrs.get("betaTesterMetric", {}).get("betaTesterState", ""),
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

    with console.status("[bold blue]Fetching groups...[/bold blue]"):
        client = get_client(ctx)
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

    with console.status("[bold blue]Inviting tester...[/bold blue]"):
        client = get_client(ctx)
        tester = client.invite_beta_tester(
            email=email,
            group_id=group_id,
            first_name=first_name,
            last_name=last_name,
        )

    console.print(f"[green]✓[/green] Invited {email} to group {group_id}")
    console.print(f"  Tester ID: {tester.get('id', '')}")
