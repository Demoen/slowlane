# Slowlane

Slowlane is a Python command-line application for automating selected App Store Connect and Apple Developer Portal workflows.

[![CI/CD](https://github.com/Demoen/slowlane/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Demoen/slowlane/actions/workflows/ci-cd.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/Demoen/slowlane/blob/main/LICENSE)

## Capabilities

- Authenticate App Store Connect commands with an API key and Developer Portal commands with an Apple ID session.
- List apps, builds, TestFlight testers, and TestFlight groups.
- Invite TestFlight testers to beta groups.
- Manage Developer Portal certificates and provisioning profiles.
- Validate and upload IPA and PKG files through Apple Transporter.
- Produce JSON output for automation and CI workflows.

Developer Portal commands use Apple's private web-service endpoints and can require updates when Apple changes those services. Upload commands require Apple tooling that is normally available only on macOS.

## Install

```bash
python -m pip install slowlane
```

Interactive Apple ID login requires the optional browser dependency:

```bash
python -m pip install "slowlane[interactive]"
python -m playwright install chromium
```

## API-key example

```bash
export ASC_KEY_ID="XXXXXXXXXX"
export ASC_ISSUER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export ASC_PRIVATE_KEY_PATH="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

slowlane asc apps list
slowlane --json asc builds list --app APP_RESOURCE_ID
```

## Session example

```bash
slowlane spaceauth login --service developer --email developer@example.com
slowlane spaceauth verify --email developer@example.com
slowlane spaceauth export --email developer@example.com
```

Continue with [Installation](installation.md), [Authentication](authentication.md), or the [CLI reference](cli.md).
