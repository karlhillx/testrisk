# Releasing testrisk

PyPI uploads use **trusted publishing** from GitHub Actions (see [.github/workflows/publish.yml](.github/workflows/publish.yml) and [PyPI: adding a publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)).

## Checklist

1. **Changelog** — Move items from `CHANGELOG.md` **Unreleased** into a dated section for the new version (e.g. `## [1.1.0] — YYYY-MM-DD`).
2. **Version** — Set `version` in `pyproject.toml` to match the tag you will publish.
3. **Lockfile** — Run `uv lock` if `pyproject.toml` dependencies or `requires-python` changed.
4. **Commit** — Push to `main` (or your release branch) with the changelog and version bump.
5. **Tag** — Create an annotated tag: `git tag -a v1.1.0 -m "Release 1.1.0"` then `git push origin v1.1.0`.
6. **GitHub Release** — In the repo, **Releases → Draft a new release**, choose the tag, publish. That triggers the **Publish to PyPI** workflow.

Use **workflow_dispatch** on that workflow only if you need a manual retry after fixing PyPI/GitHub configuration.

## Pre-release sanity

```bash
uv sync --frozen
uv run pytest tests/
uv run ruff check testrisk tests
uv run ruff format --check testrisk tests
uv run ty check
uv run python -m testrisk --version
uv run python -m testrisk --doctor
```
