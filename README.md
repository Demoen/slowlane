# Slowlane 🐌

**Apple automation. At your pace.**

[![CI/CD](https://github.com/Demoen/slowlane/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Demoen/slowlane/actions/workflows/ci-cd.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

A focused Python CLI for App Store Connect, TestFlight, certificates, provisioning profiles, and macOS uploads. Public Apple APIs, explicit signing choices, and JSON output for your automation.

[Documentation](https://demoen.github.io/slowlane/) · [Get started](https://demoen.github.io/slowlane/installation/) · [CLI reference](https://demoen.github.io/slowlane/cli/) · [Migration guide](https://demoen.github.io/slowlane/migration/)

## What it does

| Workflow | Operations | Requirements |
| --- | --- | --- |
| Apps and builds | List apps, inspect metadata, list builds, find the latest build | Eligible API key |
| TestFlight | List testers/groups and invite a tester to a group | Eligible API key and role |
| Signing | List/create/download/revoke certificates; list/create/download/delete profiles; list devices | Team API key with signing access |
| Uploads | Validate/upload IPA and upload PKG artifacts | macOS, team API key, Apple tooling |
| Automation | JSON results, local/online diagnostics, CI environment templates | Python 3.14+ |

REST commands run on macOS, Linux, and Windows. Uploads require macOS. Individual API keys support eligible REST operations; signing and uploads require team keys.

Supported targets: Apple Silicon macOS, x64 Linux, and x64 Windows. Intel macOS and 32-bit Windows are unsupported by the current cryptography dependency.

Slowlane does not build applications, sign artifacts, notarize packages, or submit apps for review.

## Install and connect

```bash
python -m pip install slowlane

export ASC_KEY_TYPE="team"
export ASC_KEY_ID="XXXXXXXXXX"
export ASC_ISSUER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export ASC_PRIVATE_KEY_PATH="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

slowlane doctor
slowlane doctor --online
slowlane asc apps list
slowlane --json asc builds list --app APP_RESOURCE_ID
```

For secret managers, use `ASC_PRIVATE_KEY` for private-key contents instead of a key-file path. For individual keys, explicitly set `ASC_KEY_TYPE=individual` and remove issuer settings. See [authentication](https://demoen.github.io/slowlane/authentication/).

## Sign with intention

```bash
slowlane signing certs list
slowlane signing devices list
slowlane signing profiles create \
  --name "App Store com.example.app" \
  --type appstore \
  --bundle-id com.example.app \
  --cert CERT_ID
slowlane signing profiles download PROFILE_ID --output ./App.mobileprovision
```

Profile creation requires an explicit certificate ID. You retain its matching private key. Downloads refuse to overwrite existing files. Use Xcode or your signing pipeline to consume the downloaded resources.

## Upload on macOS

```bash
slowlane upload ipa ./App.ipa --validate-only
slowlane upload ipa ./App.ipa
slowlane upload pkg ./App.pkg
```

Install current Xcode or Apple Transporter tooling. A successful transfer is separate from App Store Connect processing; inspect the build afterward.

## Upgrading from 0.3 to 0.4

Apple ID browser login, saved sessions, `spaceauth`, `FASTLANE_SESSION` integration, and private Developer Portal endpoints have been removed. Signing uses the public App Store Connect API and a team key. Remove `[devportal]`, `auth.default_mode`, `--team-id`, and the interactive installation extra from existing configuration and scripts.

Saved session data is left untouched; the new release does not read it or revoke it at Apple. Follow the [migration guide](https://demoen.github.io/slowlane/migration/) before updating automation.

## Development

```bash
poetry install --with docs,release,security
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy src/slowlane
poetry run pytest
poetry run zensical build --clean --strict
```

Preview the Zensical documentation with `poetry run zensical serve`. The snail stays.

See [CONTRIBUTING.md](CONTRIBUTING.md), the [release verification checklist](https://demoen.github.io/slowlane/release-verification/), and [SECURITY.md](SECURITY.md). Live Apple-account and macOS upload validation are separate release checks.

## License

[MIT](LICENSE). Slowlane is an independent project, not affiliated with or endorsed by Apple Inc. Apple, App Store Connect, TestFlight, Xcode, and Transporter are trademarks of Apple Inc.
