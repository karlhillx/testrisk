# Contributing

Thanks for helping improve testrisk.

## Development setup

```bash
git clone https://github.com/karlhillx/testrisk.git
cd testrisk
uv sync
```

`uv` creates `.venv` and installs the `dev` group (pytest, pytest-cov, ruff, ty).

## Checks before a PR

```bash
uv run pytest tests/
uv run ruff check testrisk tests
uv run ruff format --check testrisk tests
uv run ty check
```

Optional coverage:

```bash
uv run pytest --cov=testrisk --cov-report=term-missing tests/
```

CLI smoke test (same as CI):

```bash
uv run python -m testrisk --version
```

## Releases

Maintainers: follow [RELEASING.md](RELEASING.md) and keep [CHANGELOG.md](CHANGELOG.md) in sync with user-visible changes.

## Security

See [SECURITY.md](SECURITY.md) for how to report vulnerabilities.
