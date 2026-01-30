# Contributing to slowlane

Thank you for your interest in contributing to slowlane! This document provides guidelines for contributing.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Demoen/slowlane.git
   cd slowlane
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

3. Install pre-commit hooks (optional but recommended):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Code Style

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Type hints are required for all public functions
- Run `ruff check src/` before submitting PRs

## Testing

Run tests with:
```bash
pytest tests/
```

With coverage:
```bash
pytest tests/ --cov=src/slowlane
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Ensure tests pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Commit Messages

Use clear, descriptive commit messages:
- `feat: Add new command for X`
- `fix: Resolve issue with Y`
- `docs: Update README`
- `test: Add tests for Z`

## Reporting Issues

- Use the issue templates when creating issues
- Include reproduction steps for bugs
- Provide environment details (OS, Python version, etc.)

## Code of Conduct

Be respectful and constructive. We're all here to build something useful together.
