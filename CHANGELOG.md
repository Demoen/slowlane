# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-08-02

### Added
- **CLI**: Added a top-level `--version` option and deterministic machine-readable error output.
- **Authentication**: Added default-session selection for stored Developer Portal sessions.
- **Security**: Added a vulnerability-reporting policy and automated dependency audits.

### Changed
- **Python**: Raised the minimum supported version to Python 3.14.
- **Packaging**: Migrated package metadata to PEP 621, added an optional interactive-login extra, and validated installed wheels in isolation.
- **Dependencies**: Raised vulnerable runtime dependency floors to patched releases.
- **Authentication**: Separated App Store Connect API-key authentication from Developer Portal session authentication.
- **Signing**: Certificate creation now requires an existing CSR so its private key remains under user control.
- **Testing**: Expanded regression coverage and raised the enforced branch-coverage threshold from 50% to 65%.
- **Documentation**: Reworked the README and documentation around the supported command syntax, authentication models, and configuration.

### Fixed
- **Networking**: Corrected retry behavior, bounded `Retry-After` handling, and generic HTTP error propagation.
- **App Store Connect**: Hardened pagination links, token refresh, resource cleanup, latest-build selection, and bundle identifier resolution.
- **Developer Portal**: Corrected response-level error detection, payload handling, session validation, and profile relationship identifiers.
- **Uploads**: Added Transporter JWT support, asset-file uploads, secret redaction, and correct altool platform selection.
- **Secrets**: Made encrypted-file writes atomic, cleaned up failed temporary writes, and enforced restrictive POSIX permissions.
- **Configuration**: Rejected invalid runtime and file-based settings before they can affect requests.
- **CI/CD**: Separated validation from tag-triggered releases and added explicit artifact handoff, package checks, and version checks.
- **Security**: Pinned CI actions and made static analysis and dependency auditing required checks.

## [0.2.8] - 2026-04-12

### Changed
- **Dependencies**: Bumped `click` 8.3.1→8.3.2, `cryptography` 46.0.5→46.0.7, `pyjwt` 2.11.0→2.12.1, `tomli` 2.4.0→2.4.1.
- **Dev dependencies**: Bumped `pytest` 9.0.2→9.0.3, `pytest-cov` 7.0.0→7.1.0, `mypy` 1.19.1→1.20.0, `ruff` 0.15.4→0.15.10.

### Fixed
- **Linting**: Added `B008` to `pyproject.toml` ignore list, matching the CI workflow — suppresses false-positive for `typer.Argument` in function defaults.
- **Tests**: Removed unused variable `token1` in `test_jwt_auth.py` (F841).
- **Tests**: Removed trailing whitespace from blank lines in `test_asc_client.py` and `test_secrets.py` (W293).
- **Tests**: Replaced `timezone.utc` with `datetime.UTC` in `test_secrets.py` (UP017).
- **Formatting**: Applied `ruff format` to `test_cli.py`, `test_errors.py`, and `test_transporter.py`.

## [0.2.7] - 2026-04-12

### Changed
- **Signing / Config**: Reformatted `--team-id` option help text and multi-team error messages for consistency.

## [0.2.6] - 2026-04-12

### Added
- **Signing**: All `signing certs` and `signing profiles` commands now accept `--team-id` to specify a team when the account belongs to multiple teams.
- **Signing**: Added `--json` output support to `signing certs list` and `signing profiles list` (respects global `--json` flag and `[output] format` config).
- **Signing**: Added progress spinners to all signing commands.
- **Config**: New `[devportal]` config section with `team_id` field — persists a default team across sessions.
- **Tests**: Added unit tests for `AppleHTTPClient` (retry logic, error classification, secret redaction) and `TransporterWrapper` (upload, validate, error parsing). Coverage raised from 25% to 53%.
- **Tests**: Added `tests/conftest.py` with shared fixtures (`mock_config`, `mock_jwt_auth`, `mock_session_auth`, `mock_http`).

### Changed
- **Architecture**: Extracted `BaseAppleClient` (`core/base_client.py`) — `AppStoreConnectClient` and `DeveloperPortalClient` now inherit shared `__init__`, `close`, and context manager logic.
- **Developer Portal**: `DeveloperPortalClient` now raises a clear error listing all available teams when multiple teams exist and no `team_id` is specified, instead of silently picking the first.
- **Signing**: `RateLimitError` is now handled specifically in all signing commands — prints retry-after hint and exits with code 3 instead of 1.
- **CI**: Enforced minimum 50% test coverage via `--cov-fail-under=50`.

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
- **Branding**: Added the original Slowlane documentation theme and custom CSS.
- **CI/CD**: GitHub Actions workflow (`docs.yml`) for automatic documentation deployment to GitHub Pages.

### Changed
- **Documentation**: Moved from basic README to full site structure (`docs/`).
- **Configuration**: Updated default configuration examples in documentation.
