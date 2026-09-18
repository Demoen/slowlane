# Contributing to Slowlane

Contributions are welcome through GitHub issues and pull requests. Keep changes focused, include tests for observable behavior, and update user-facing documentation when commands or configuration change.

## Prerequisites

- Python 3.14 or newer
- Poetry 2.4.3
- Git

Supported development targets are 64-bit Linux, 64-bit Windows, and Apple Silicon macOS. Upload integration work requires Xcode or the Transporter app on macOS. Intel macOS and 32-bit Windows are unsupported by the current cryptography dependency.

## Development setup

```bash
git clone https://github.com/Demoen/slowlane.git
cd slowlane
poetry install --with docs,release,security
```

Use team API keys for signing and uploads. Live account checks are separate from the isolated unit suite; never give the tests production credentials.

## Quality checks

Run the same core checks used by CI:

```bash
poetry check --lock
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy src/slowlane
poetry run pytest
poetry run zensical build --clean --strict
poetry run python scripts/check_docs.py
poetry build
poetry run twine check dist/*
```

Apply Ruff formatting with:

```bash
poetry run ruff format src tests
```

## Documentation

The site uses Zensical with configuration in `zensical.toml`. Preview it with `poetry run zensical serve`. Preserve existing page paths when reorganizing navigation. Test the homepage and representative guides on mobile and desktop, including search, light/dark mode, and reduced-motion preferences.

GitHub Pages uses the artifact built by the documentation job after the package gates pass. Before the first deployment with this workflow, set repository **Settings → Pages → Source** to **GitHub Actions** and allow the `main` branch in the `github-pages` environment's deployment rules. The workflow does not push a `gh-pages` branch.

## Dependency updates

Dependabot checks on the first of each month at 09:00 Europe/Berlin, with at most one routine Python PR and one GitHub Actions PR open. Python batches include direct and transitive dependencies. Each batch includes major, minor, and patch updates; review breaking changes before merging. Routine releases have a seven-day cooldown, so a release still cooling down at the monthly check waits until the following month.

Security fixes use separate groups and bypass the monthly schedule, cooldown, and routine PR limit. When merging this policy, enable dependency alerts and Dependabot security updates in repository settings; grouping alone does not enable them. Automatic rebasing remains enabled to keep fixes mergeable. This policy takes effect when `.github/dependabot.yml` reaches the default branch; existing PRs may be regrouped.

For a manual refresh, review upstream release notes, adjust incompatible version bounds deliberately, run `poetry update --with docs,release,security`, and run the quality checks above plus `poetry run pip-audit --local`. Keep Zensical pinned to a reviewed release and GitHub Actions pinned to full commit SHAs. The policy uses [GitHub's Dependabot configuration options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).

## Pull requests

1. Create a branch from the current default branch.
2. Make one cohesive change and add or update tests.
3. Update the README, documentation, and `[Unreleased]` changelog entry when behavior changes.
4. Run the quality checks locally.
5. Open a pull request that explains the problem, the solution, and how it was verified.

Do not include Apple credentials, session exports, signing keys, real account identifiers, or private API responses in commits, fixtures, screenshots, or logs.

## Commit messages

Use concise imperative subjects. Conventional prefixes are welcome when they clarify intent, for example:

- `feat: add build filtering`
- `fix: preserve transporter credentials`
- `docs: clarify team key setup`
- `test: cover retry exhaustion`

## Maintainer releases

1. Start from a clean, current `main` branch with a successful CI run.
2. Move the relevant `[Unreleased]` entries to a dated version heading and restore an empty `[Unreleased]` section.
3. Set the same version in `pyproject.toml` and `src/slowlane/__init__.py`, then run `poetry lock` and the quality checks above.
4. Complete the [live release verification checklist](docs/release-verification.md), record any untested operations, then commit and push the release preparation and wait for CI to pass on that commit.
5. Create and push an annotated `vX.Y.Z` tag that matches the package version.
6. Confirm that the Release workflow publishes through the `pypi` environment and that the GitHub and PyPI artifact hashes match.

Configure PyPI trusted publishing for the repository's `pypi` environment before the first release. Published tags and artifacts are immutable; prepare a new version instead of moving a tag or replacing release files.

## Reporting bugs

Use the bug-report template and include the operating system, Python version, Slowlane version, command invocation with secrets removed, expected behavior, and relevant sanitized logs.

Report vulnerabilities according to [SECURITY.md](SECURITY.md), not through a public issue.
