# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.5] - 2026-04-12

### Added
- **Signing**: Implemented `signing certs list`, `certs create`, and `certs revoke` commands against the Developer Portal API.
- **Signing**: Implemented `signing profiles list`, `profiles create`, and `profiles delete` commands against the Developer Portal API.
- **Signing**: `certs create` auto-generates a CSR if no `--csr-path` is provided.
- **Signing**: `profiles create` auto-selects the first available certificate when `--cert-id` is omitted.

### Changed
- **spaceauth verify**: Now makes a real API call via `DeveloperPortalClient` to confirm session validity and reports team count.
- **`__init__.py`**: Synced `__version__` to match `pyproject.toml` (was stuck at `0.1.0`).

### Fixed
- **CI**: Removed `|| true` from ruff format and mypy steps so failures are no longer silently ignored.
- **Type safety**: Added `cast()` in `asc/client.py`, `cli/env.py`, `cli/signing.py`, `cli/spaceauth.py`, and `cli/upload.py` to satisfy mypy.

## [0.2.4] - 2026-02-24

### Changed
- **Dependencies**: Updated core dependencies via Dependabot for the `dependencies` group.
- **Tooling**: Bumped `ruff` in the `dev-dependencies` group.
- **CI/CD**: Tweaked Dependabot configuration and CI workflow for dependency management.

## [0.2.3] - 2026-02-07

### Fixed
- **Documentation**: Removed broken "Guides" links from navigation.
- **Documentation**: Fixed rendering of "Tip" admonitions in index page.

## [0.2.2] - 2026-02-07

### Added
- **CI/CD**: Added Python 3.14 to test matrix.
- **Documentation**: Added PyPI version badge to README.

### Fixed
- **Documentation**: Corrected `site_url` in `mkdocs.yml` to point to GitHub Pages.

## [0.2.1] - 2026-02-07

### Added
- **CI/CD**: Automated GitHub Release creation on tag push.
- **CI/CD**: Simplified release workflow (removed TestPyPI).

## [0.2.0] - 2026-02-07

### Added
- **Documentation**: Comprehensive MkDocs documentation with "Slowlane" branding.
- **Branding**: New "Slowlane" aesthetic with custom CSS and a relaxed snail theme. 🐌
- **CI/CD**: GitHub Actions workflow (`docs.yml`) for automatic documentation deployment to GitHub Pages.

### Changed
- **Documentation**: Moved from basic README to full site structure (`docs/`).
- **Configuration**: Updated default configuration examples in documentation.
