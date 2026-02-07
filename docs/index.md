# Slowlane 🐌

<div class="hero-snail">🐌</div>

**"Life in the fastlane is clear, but the slowlane is where the scenery is."**

*Production-grade Python CLI tool for Apple service automation. A chill, fastlane-compatible solution for authentication and App Store Connect/Developer Portal operations.*

!!! tip
    Why rush? Slowlane gets you there... eventually. (Actually it's quite fast, but we like to take our time with quality).

[![CI](https://github.com/Demoen/slowlane/actions/workflows/ci.yml/badge.svg)](https://github.com/Demoen/slowlane/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🔐 **Multiple auth modes**: JWT API keys, session cookies, interactive login
- 📱 **App Store Connect**: Apps, builds, TestFlight management
- 🔏 **Developer Portal**: Certificates and provisioning profiles
- 📦 **Upload**: IPA upload via iTunes Transporter
- 🔄 **CI-friendly**: Works on macOS, Linux, Windows with structured output

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
