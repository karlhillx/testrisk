# Changelog

All notable changes to this project are documented here. This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.0.0] — 2026-09-12

### Added

- First release: rank uncovered Python functions from `coverage.json`, `coverage.xml`, or `.coverage`.
- Scoring combines missing lines, uncovered branches, cyclomatic-ish complexity, git-changed lines, and whether related tests exist.
- CLI: `--changed`, `--base`, `--top`, `--file`, `--json`, `--prompt`, `--fail-under-changed`, `--doctor`, `--quiet`, `--color`.
- Walk-up discovery of a repo root (`pyproject.toml` / `.git`) when `--repo` is `.`.
- Human report, JSON report, and an evidence-based `--prompt` for coding agents.
- Library export: `analyze`, `Gap`, `GapError`, `GapReport`, `Options`, `Risk`, `find_repo_root`.
- Type-check `testrisk` with [ty](https://docs.astral.sh/ty/) (`uv run ty check`) in the `dev` group and CI.
- Ship `py.typed` so installers and type checkers treat testrisk as typed.

### Changed

- Published as **testrisk** (PyPI, import, and CLI). `test-gap` / `testgap` were unavailable.
- Library imports no longer pull in the CLI. Catch `GapError` from `testrisk`.
- Git diffs honor `--repo` even if `GIT_DIR` is set, and decode as UTF-8.
