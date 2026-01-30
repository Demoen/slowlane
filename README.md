# Slowlane

[![CI](https://github.com/Demoen/slowlane/actions/workflows/ci.yml/badge.svg)](https://github.com/Demoen/slowlane/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)

Production-grade Python CLI tool for Apple service automation. A fastlane-compatible solution for authentication and App Store Connect/Developer Portal operations.

## Features

- 🔐 **Multiple auth modes**: JWT API keys, session cookies, interactive login
- 📱 **App Store Connect**: Apps, builds, TestFlight management
- 🔏 **Developer Portal**: Certificates and provisioning profiles
- 📦 **Upload**: IPA upload via iTunes Transporter
- 🔄 **CI-friendly**: Works on macOS, Linux, Windows with structured output

## Installation

```bash
pip install slowlane
```

Or with Poetry:

```bash
poetry add slowlane
```

## Quick Start

### Using API Key (Recommended for CI)

```bash
# Set environment variables
export ASC_KEY_ID="XXXXXXXXXX"
export ASC_ISSUER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export ASC_PRIVATE_KEY="$(cat AuthKey_XXXXXXXXXX.p8)"

# List your apps
slowlane asc apps list

# Upload an IPA
slowlane upload ipa ./MyApp.ipa
```

### Using Session Auth

```bash
# Interactive login (opens browser)
slowlane spaceauth login

# Export session for CI
slowlane spaceauth export

# Use session in CI
export FASTLANE_SESSION="..."
slowlane asc apps list
```

## Commands

| Command | Description |
|---------|-------------|
| `spaceauth login` | Interactive browser login |
| `spaceauth export` | Export session as env var |
| `spaceauth verify` | Test session validity |
| `spaceauth revoke` | Clear stored session |
| `spaceauth doctor` | Diagnose auth issues |
| `asc apps list\|get` | Manage apps |
| `asc builds list\|latest` | Manage builds |
| `asc testflight testers\|groups\|invite` | TestFlight |
| `signing certs list\|create\|revoke` | Certificates |
| `signing profiles list\|create\|delete` | Profiles |
| `upload ipa <path>` | Upload IPA |
| `env print` | Print CI exports |

## Configuration

Config file: `~/.config/slowlane/config.toml`

```toml
[auth]
default_mode = "jwt"  # or "session"

[http]
timeout = 30
max_retries = 3

[output]
format = "text"  # or "json"
```

## CI Examples

### GitHub Actions

```yaml
- name: Upload to App Store
  env:
    ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
    ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
    ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
  run: |
    pip install slowlane
    slowlane upload ipa ./app.ipa
```

## Security

- Secrets stored in OS keychain (via `keyring`) with encrypted fallback
- Sessions include metadata only (email hashed, never stored plaintext)
- Passwords never stored - only used to mint sessions interactively
- All secrets redacted from logs by default

## License

MIT
