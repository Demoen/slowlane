# Contributing to Slowlane

Contributions are welcome through GitHub issues and pull requests. Keep changes focused, include tests for observable behavior, and update user-facing documentation when commands or configuration change.

## Prerequisites

- Python 3.14 or newer
- Poetry 2.4.1
- Git

Interactive-login development also requires Chromium. Upload integration work requires Xcode or the Transporter app on macOS.

## Development setup

```bash
git clone https://github.com/Demoen/slowlane.git
cd slowlane
poetry install --all-extras --with docs,release,security
poetry run playwright install chromium
```

The browser installation is unnecessary when the change does not involve interactive login.

## Quality checks

Run the same core checks used by CI:

```bash
poetry check --lock
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy src/slowlane
poetry run pytest
poetry run mkdocs build --strict
poetry build
poetry run twine check dist/*
```

Apply Ruff formatting with:

```bash
poetry run ruff format src tests
```

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
- `docs: correct session setup`
- `test: cover retry exhaustion`

## Maintainer releases

1. Start from a clean, current `main` branch with a successful CI run.
2. Move the relevant `[Unreleased]` entries to a dated version heading and restore an empty `[Unreleased]` section.
3. Set the same version in `pyproject.toml` and `src/slowlane/__init__.py`, then run `poetry lock` and the quality checks above.
4. Commit and push the release preparation, then wait for CI to pass on that commit.
5. Create and push an annotated `vX.Y.Z` tag that matches the package version.
6. Confirm that the Release workflow publishes through the protected `pypi` environment and that the GitHub and PyPI artifact hashes match.

Configure PyPI trusted publishing for the repository's `pypi` environment before the first release. Published tags and artifacts are immutable; prepare a new version instead of moving a tag or replacing release files.

## Reporting bugs

Use the bug-report template and include the operating system, Python version, Slowlane version, command invocation with secrets removed, expected behavior, and relevant sanitized logs.

Report vulnerabilities according to [SECURITY.md](SECURITY.md), not through a public issue.
