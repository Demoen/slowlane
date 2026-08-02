# Slowlane

[![CI/CD](https://github.com/Demoen/slowlane/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Demoen/slowlane/actions/workflows/ci-cd.yml)
[![PyPI version](https://badge.fury.io/py/slowlane.svg)](https://pypi.org/project/slowlane/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/slowlane?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/slowlane)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/Demoen/slowlane/blob/main/LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-261230.svg)](https://docs.astral.sh/ruff/)

Slowlane is a Python command-line application for automating selected App Store Connect and Apple Developer Portal workflows. App Store Connect REST and upload commands use API-key authentication; Developer Portal signing commands use an Apple ID session. The CLI also provides structured JSON output and CI environment helpers.

[Documentation](https://demoen.github.io/slowlane/) | [Installation](https://demoen.github.io/slowlane/installation/) | [CLI reference](https://demoen.github.io/slowlane/cli/) | [Changelog](https://github.com/Demoen/slowlane/blob/main/CHANGELOG.md)

## Capabilities

| Area | Supported operations |
| --- | --- |
| Authentication | API keys for App Store Connect; interactive Apple ID sessions for Developer Portal commands |
| Apps and builds | List apps, inspect an app, list builds, and find the latest build |
| TestFlight | List testers and groups, and invite a tester to a group |
| Code signing | List, create, and revoke certificates; list, create, and delete provisioning profiles |
| Uploads | Validate and upload IPA and PKG files with Apple Transporter |
| Automation | JSON output and environment helpers for common CI providers |

Developer Portal commands use Apple's private web-service endpoints and can require updates when Apple changes those services. Upload commands require Apple tooling that is normally available only on macOS.

## Requirements

- Python 3.14 or newer
- An App Store Connect API key for REST API and upload workflows
- Chromium for interactive Apple ID login
- Xcode or the Transporter app on macOS for IPA and PKG uploads

## Installation

Install the base package for API-key and pre-existing session workflows:

```bash
python -m pip install slowlane
```

Install the interactive-login extra and its Chromium browser:

```bash
python -m pip install "slowlane[interactive]"
python -m playwright install chromium
```

Verify the installation:

```bash
slowlane version
```

## Quick start

### App Store Connect API key

Create an API key in App Store Connect, then provide its key ID, issuer ID, and private key:

```bash
export ASC_KEY_ID="XXXXXXXXXX"
export ASC_ISSUER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export ASC_PRIVATE_KEY_PATH="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

slowlane asc apps list
slowlane asc builds list --app APP_RESOURCE_ID
```

Use `ASC_PRIVATE_KEY` instead of `ASC_PRIVATE_KEY_PATH` when the private-key contents are supplied directly by a secret manager.

### Interactive Apple ID session

Interactive login is required for Developer Portal signing operations:

```bash
slowlane spaceauth login --service developer --email developer@example.com
slowlane spaceauth verify --email developer@example.com
slowlane spaceauth export --email developer@example.com
```

Store the exported value as the `FASTLANE_SESSION` secret in CI. Treat it as a credential.

### JSON output

The global `--json` option must precede the command:

```bash
slowlane --json asc apps list
```

## Command overview

| Command | Purpose |
| --- | --- |
| `slowlane spaceauth login --service developer --email EMAIL` | Open an interactive Apple ID login and store the resulting session |
| `slowlane spaceauth export --email EMAIL` | Export a stored session for CI |
| `slowlane spaceauth verify --email EMAIL` | Verify a stored session against Apple services |
| `slowlane spaceauth doctor` | Inspect local authentication configuration |
| `slowlane asc apps list` | List apps |
| `slowlane asc apps get APP_ID_OR_BUNDLE_ID` | Get an app by resource ID or bundle ID |
| `slowlane asc builds list --app APP_ID` | List builds for an app |
| `slowlane asc builds latest APP_ID` | Get the latest build for an app |
| `slowlane asc testflight testers --app APP_ID` | List TestFlight testers |
| `slowlane asc testflight groups --app APP_ID` | List TestFlight groups |
| `slowlane asc testflight invite EMAIL --group GROUP_ID` | Invite a tester to a group |
| `slowlane signing certs list` | List signing certificates |
| `slowlane signing certs create --type TYPE --csr PATH` | Create a signing certificate from an existing CSR |
| `slowlane signing certs revoke CERT_ID` | Revoke a signing certificate |
| `slowlane signing profiles list` | List provisioning profiles |
| `slowlane signing profiles create --name NAME --type TYPE --bundle-id BUNDLE_ID [--device DEVICE_ID]` | Create a provisioning profile |
| `slowlane signing profiles delete PROFILE_ID` | Delete a provisioning profile |
| `slowlane upload ipa PATH` | Validate and upload an IPA |
| `slowlane upload pkg PATH` | Upload a macOS PKG |
| `slowlane env print --platform PLATFORM` | Print CI environment configuration |

Run `slowlane COMMAND --help` for complete options and examples.

## Configuration

Slowlane reads TOML configuration from:

- Linux and macOS: `~/.config/slowlane/config.toml`, or `$XDG_CONFIG_HOME/slowlane/config.toml`
- Windows: `%APPDATA%\slowlane\config.toml`

```toml
[auth]
key_id = "XXXXXXXXXX"
issuer_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
private_key_path = "/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

[http]
timeout = 30
max_retries = 3
backoff_factor = 0.5

[output]
format = "text"
verbose = false

[devportal]
team_id = "TEAM_ID"
```

Environment variables override file-based authentication and output settings:

| Variable | Purpose |
| --- | --- |
| `ASC_KEY_ID` | App Store Connect API key ID |
| `ASC_ISSUER_ID` | App Store Connect issuer ID |
| `ASC_PRIVATE_KEY` | Private-key contents |
| `ASC_PRIVATE_KEY_PATH` | Path to a `.p8` private-key file |
| `FASTLANE_SESSION` | Exported Slowlane session data |
| `SLOWLANE_JSON` | Set to `1` or `true` for JSON output |
| `SLOWLANE_VERBOSE` | Set to `1` or `true` for verbose logging |

See the [configuration reference](https://demoen.github.io/slowlane/configuration/) for details.

## Security

- Never commit API private keys or exported session values.
- Store credentials in the operating-system keychain or your CI provider's secret store.
- Use narrowly scoped App Store Connect roles and rotate credentials regularly.
- Review the [security policy](https://github.com/Demoen/slowlane/blob/main/SECURITY.md) before reporting a vulnerability.

## Development

```bash
poetry install --all-extras --with docs,release,security
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy src/slowlane
poetry run pytest
poetry run mkdocs build --strict
```

See the [contribution guide](https://github.com/Demoen/slowlane/blob/main/CONTRIBUTING.md) for the contribution workflow.

## License

Slowlane is available under the [MIT License](https://github.com/Demoen/slowlane/blob/main/LICENSE).

Apple, App Store Connect, TestFlight, Xcode, and Transporter are trademarks of Apple Inc. Slowlane is an independent project and is not affiliated with or endorsed by Apple Inc.
