# Release verification

This checklist is for maintainers validating a release against Apple. Unit tests and mocked API contracts cannot establish that a particular live account, Xcode version, or distribution artifact works.

Record the candidate commit, Python/macOS/Xcode versions, verification date, and a sanitized pass/fail result for each exercised workflow. Mark untested operations explicitly.

## 0.4.0 preparation record

Prepared on **2026-09-18** in [PR #44](https://github.com/Demoen/slowlane/pull/44), based on `6aa464d` (`v0.3.0`). Package metadata and the CLI both report `0.4.0`; the development-status classifier remains **Beta**. Publication was authorized with the live Apple checks below explicitly unverified. Update the changelog date if publication happens on a later day.

| Check | Result |
| --- | --- |
| Windows, Python 3.14.5 | 353 tests passed, one POSIX-only test skipped; 88.35% coverage |
| Linux, Ubuntu 22.04 / Python 3.14.6 | 354 tests passed; 88.69% coverage |
| Ruff, formatting, mypy, lock validation | Passed |
| Bandit at the CI severity threshold; dependency audit | Passed; no known dependency vulnerabilities reported |
| Strict Zensical build and internal links/assets | Passed: 15 pages, 736 links/assets |
| Desktop/mobile documentation | Search, navigation, copying, themes, reduced motion, and overflow checks passed |
| Distribution metadata and installed-wheel CLI | Passed, including version and JSON error output |
| Release version gate | Accepts `v0.4.0`; rejects mismatched and unprefixed tags |
| GitHub Actions, including macOS | [PR checks passed on `7300393`](https://github.com/Demoen/slowlane/actions/runs/35363483191); verify the final main and tag workflows before claiming release completion |
| Live Apple reads, disposable signing resources, TestFlight membership | Not run |
| Signed IPA/PKG validation, upload, and processing confirmation on macOS | Not run |

Local preparation artifacts are built into `dist/0.4.0/` so they cannot be confused with older packages in `dist/`. The release workflow builds its own artifacts from the final tag.

Before tagging:

1. Keep the unverified live checks explicit in the beta release notes. Complete and record the checks below before claiming live Apple compatibility.
2. Pages is configured to use **GitHub Actions**, and the `github-pages` environment permits branch `main`. Verify deployment from the merged commit.
3. After merging the Dependabot configuration, enable repository dependency alerts and automated security fixes; both are disabled at preparation time. Enable private vulnerability reporting so the reporting route in `SECURITY.md` is available; that setting is also currently disabled.
4. Verify the PyPI trusted publisher for `Demoen/slowlane`, workflow `release.yml`, and environment `pypi`. The previous release used it successfully, but current PyPI-side configuration has not been inspected. The GitHub `pypi` environment currently has no reviewer or branch/tag restrictions; the environment name alone does not enforce approval.
5. Commit and push the prepared change, record its SHA, and wait for the complete CI/CD workflow to pass. Refresh this record if code or dependencies change.
6. Once verification is complete, create and push the annotated `v0.4.0` tag. A tag push starts publication to PyPI and GitHub automatically.

## Automated gates

```bash
poetry check --lock
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy src/slowlane
poetry run pytest
poetry run bandit -r src -ll -ii
poetry run pip-audit --local --progress-spinner off
poetry run zensical build --clean --strict
poetry run python scripts/check_docs.py
poetry build
poetry run twine check dist/*
```

CI runs tests on macOS, Linux, and Windows, builds documentation, audits dependencies, and smoke-tests the built wheel. A release tag must match both package versions and a changelog entry.

## Live read-only checks

With a permitted test account and team API key:

- Run `doctor` and `doctor --online`.
- List apps, fetch an app by resource ID and bundle identifier, and inspect builds.
- List TestFlight groups and testers for a test app.
- List signing certificates, profiles, and devices.
- Download a known certificate and profile to new paths and inspect them with Apple tooling.
- Repeat representative requests with JSON output and confirm stdout contains only parseable results.

With an eligible individual key, verify app access within the user's permissions. Confirm that signing and uploads reject that key before sending a request.

## Controlled write checks

Use a dedicated test app and pre-approved test resources. Obtain permission for the specific account changes before starting.

- Create a test certificate from a CSR whose private key you control.
- Create a profile with an explicit certificate and valid device resource IDs where required.
- Download and inspect the profile. Verify its bundle identifier, certificate, and devices.
- Invite an approved test address to a test group.
- Delete the test profile and revoke only the disposable test certificate when the account owner approves cleanup.
- Confirm that simulated or observed uncertain failures do not cause duplicate automatic writes.

## macOS upload checks

Use a signed, disposable test build with a unique build number and a team key authorized for its app.

- Validate an IPA without uploading.
- Upload an IPA with the selected Apple tool and verify that the expected build appears in App Store Connect.
- Exercise the PKG path with an eligible macOS test artifact before claiming PKG compatibility for that tool version.
- Inspect later processing state separately from upload completion.
- Confirm errors do not expose private keys or bearer tokens.

Do not describe uploads as live-verified if no suitable macOS runner, credentials, or signed artifact was available.

## Documentation deployment

Build and review the home page and representative guides on desktop and mobile, in light/dark modes and with reduced motion. Test search, navigation, code copying, and the preserved `/slowlane/` URLs.

The deployment workflow uses GitHub Pages artifacts. Repository **Settings → Pages → Source** must be **GitHub Actions**, and the `github-pages` environment must allow deployments from `main`, before the first deployment with this workflow. Changing repository settings and publishing are separate from preparing the code change.
