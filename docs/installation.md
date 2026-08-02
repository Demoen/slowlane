# Installation

## Requirements

- Python 3.14 or newer
- An App Store Connect API key for REST API and upload workflows
- Chromium for interactive Apple ID login
- Xcode or the Transporter app on macOS for IPA and PKG uploads

## Install from PyPI

Install the base package for API-key and pre-existing session workflows:

```bash
python -m pip install slowlane
```

Install the interactive-login extra when Slowlane needs to open an Apple ID login browser:

```bash
python -m pip install "slowlane[interactive]"
python -m playwright install chromium
```

With Poetry, use:

```bash
poetry add slowlane
```

or:

```bash
poetry add "slowlane[interactive]"
poetry run playwright install chromium
```

## Verify the installation

```bash
slowlane version
slowlane --help
```

## Upgrade

```bash
python -m pip install --upgrade slowlane
```

Review the [changelog](https://github.com/Demoen/slowlane/blob/main/CHANGELOG.md) before upgrading automation that depends on Developer Portal operations.

## Platform notes

App Store Connect REST API and session-management commands are designed to run on Linux, macOS, and Windows. Upload commands depend on Apple Transporter or `altool`; these tools are normally available only on macOS through Xcode or the Transporter app.
