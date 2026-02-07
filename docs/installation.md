# Installation

Slowlane is a Python package and can be installed via pip or poetry.

## Prerequisites

- Python 3.11 or higher
- (Optional) Xcode or Transporter app for IPA uploads on macOS

## Installation Methods

### pip (Recommended)

```bash
pip install slowlane
```

### poetry

```bash
poetry add slowlane
```

## Post-Installation

### Install Playwright (Optional)

If you plan to use interactive login (`slowlane spaceauth login`), you need to install Playwright browsers:

```bash
pip install playwright
playwright install chromium
```

This is only required for the interactive login flow. CI environments using API keys or pre-generated sessions do not need Playwright.

## Verification

Verify the installation by checking the version:

```bash
slowlane --version
```
