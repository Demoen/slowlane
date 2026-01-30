"""Environment helper commands for CI integration."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from slowlane.auth.session_auth import get_session_auth
from slowlane.core.config import SlowlaneConfig
from slowlane.core.secrets import SecretStore

app = typer.Typer(
    name="env",
    help="CI environment helpers.",
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


@app.command("print")
def env_print(
    ctx: typer.Context,
    ci_platform: str = typer.Option(
        "github",
        "--platform",
        "-p",
        help="CI platform: github, gitlab, azure, generic",
    ),
    include_session: bool = typer.Option(
        False,
        "--include-session",
        help="Include FASTLANE_SESSION if available",
    ),
) -> None:
    """Print environment export commands for CI.

    Generates the appropriate syntax for setting environment
    variables in different CI platforms.
    """
    console = get_console(ctx)
    config = get_config(ctx)

    env_vars: dict[str, str] = {}

    # Check for JWT config
    if config.auth.key_id:
        env_vars["ASC_KEY_ID"] = config.auth.key_id
    if config.auth.issuer_id:
        env_vars["ASC_ISSUER_ID"] = config.auth.issuer_id

    # Check for session if requested
    if include_session:
        session = get_session_auth(secret_store=SecretStore())
        if session:
            env_vars["FASTLANE_SESSION"] = session.to_export_string()

    if not env_vars:
        console.print("[yellow]No credentials configured to export.[/yellow]")
        return

    if config.output.format == "json":
        console.print(json.dumps(env_vars, indent=2))
        return

    # Generate platform-specific output
    if ci_platform == "github":
        output = _generate_github_actions(env_vars)
        title = "GitHub Actions"
    elif ci_platform == "gitlab":
        output = _generate_gitlab_ci(env_vars)
        title = "GitLab CI"
    elif ci_platform == "azure":
        output = _generate_azure_devops(env_vars)
        title = "Azure DevOps"
    else:
        output = _generate_generic(env_vars)
        title = "Shell Export"

    console.print(
        Panel(
            Syntax(output, "yaml" if ci_platform in ("github", "gitlab") else "bash"),
            title=f"🔧 {title} Environment",
        )
    )


def _generate_github_actions(env_vars: dict[str, str]) -> str:
    """Generate GitHub Actions env format."""
    lines = ["env:"]
    for key, value in env_vars.items():
        # Use secrets reference for sensitive values
        if key in ("ASC_PRIVATE_KEY", "FASTLANE_SESSION"):
            lines.append(f"  {key}: ${{{{ secrets.{key} }}}}")
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _generate_gitlab_ci(env_vars: dict[str, str]) -> str:
    """Generate GitLab CI variables format."""
    lines = ["variables:"]
    for key, value in env_vars.items():
        if key in ("ASC_PRIVATE_KEY", "FASTLANE_SESSION"):
            lines.append(f"  {key}: ${key}")
        else:
            lines.append(f'  {key}: "{value}"')
    return "\n".join(lines)


def _generate_azure_devops(env_vars: dict[str, str]) -> str:
    """Generate Azure DevOps format."""
    lines = ["variables:"]
    for key, value in env_vars.items():
        if key in ("ASC_PRIVATE_KEY", "FASTLANE_SESSION"):
            lines.append(f"  - name: {key}")
            lines.append(f"    value: $({key})")
        else:
            lines.append(f"  - name: {key}")
            lines.append(f'    value: "{value}"')
    return "\n".join(lines)


def _generate_generic(env_vars: dict[str, str]) -> str:
    """Generate generic shell export format."""
    lines = []
    for key, value in env_vars.items():
        # Escape single quotes in value
        escaped_value = value.replace("'", "'\\''")
        lines.append(f"export {key}='{escaped_value}'")
    return "\n".join(lines)


@app.command("setup")
def env_setup(
    ctx: typer.Context,
    ci_platform: str = typer.Option(
        "github",
        "--platform",
        "-p",
        help="CI platform: github, gitlab, azure",
    ),
) -> None:
    """Show setup instructions for CI integration."""
    console = get_console(ctx)

    if ci_platform == "github":
        instructions = """
# GitHub Actions Setup

1. Go to your repository Settings > Secrets and variables > Actions

2. Add these repository secrets:
   - ASC_KEY_ID: Your App Store Connect API Key ID
   - ASC_ISSUER_ID: Your App Store Connect Issuer ID
   - ASC_PRIVATE_KEY: Contents of your .p8 file

3. Add this step to your workflow:

```yaml
jobs:
  deploy:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install slowlane
        run: pip install slowlane

      - name: Upload to App Store
        env:
          ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
        run: slowlane upload ipa ./App.ipa
```
"""
    elif ci_platform == "gitlab":
        instructions = """
# GitLab CI Setup

1. Go to your project Settings > CI/CD > Variables

2. Add these protected/masked variables:
   - ASC_KEY_ID
   - ASC_ISSUER_ID
   - ASC_PRIVATE_KEY

3. Add to your .gitlab-ci.yml:

```yaml
deploy:
  image: python:3.11
  stage: deploy
  script:
    - pip install slowlane
    - slowlane upload ipa ./App.ipa
  variables:
    ASC_KEY_ID: $ASC_KEY_ID
    ASC_ISSUER_ID: $ASC_ISSUER_ID
    ASC_PRIVATE_KEY: $ASC_PRIVATE_KEY
```
"""
    elif ci_platform == "azure":
        instructions = """
# Azure DevOps Setup

1. Go to Pipelines > Library > Variable groups

2. Create a variable group with:
   - ASC_KEY_ID
   - ASC_ISSUER_ID
   - ASC_PRIVATE_KEY (mark as secret)

3. Add to your azure-pipelines.yml:

```yaml
trigger:
  - main

pool:
  vmImage: 'macos-latest'

variables:
  - group: AppStoreConnect

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: pip install slowlane
    displayName: 'Install slowlane'

  - script: slowlane upload ipa ./App.ipa
    displayName: 'Upload to App Store'
    env:
      ASC_KEY_ID: $(ASC_KEY_ID)
      ASC_ISSUER_ID: $(ASC_ISSUER_ID)
      ASC_PRIVATE_KEY: $(ASC_PRIVATE_KEY)
```
"""
    else:
        instructions = "Unknown CI platform. Use --platform github|gitlab|azure"

    console.print(instructions)
