# Changelog

All notable changes to this project are documented here. This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

## [1.1.0] — 2026-09-12

### Added

- Config, CI, and ranking knobs: `[tool.testrisk]`, glob `--file` / `--exclude`, `--min-risk` / `--fail-on-risk`, `--explain` (JSON `score_parts`), and `uses: karlhillx/testrisk@v1` with `GITHUB_BASE_REF`.
- A first-run path people can trust: generate-coverage recipe, stale-coverage warning, `--changed` as the everyday command (`--no-changed` overrides config), default omit of `__init__.py` and `migrations/`, and test labels `none` / `indirect` / `weak` / `meaningful`. Ceremonial related tests no longer count as coverage (`--weak-only`, `--fail-on-weak`).
- `--prompt` includes numbered source excerpts of uncovered lines.

### Changed

- Related-test detection requires a function mention (and the module or class for short names), not a conventional filename. Suggested paths nest under `tests/` for `src/` trees and deeper packages.
- Human report is numbered blocks plus a footer (shown / risk / checks / hint). Quiet `<module>` gaps are dropped unless they have uncovered branches or sit on changed lines. README leads with `--changed`.

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
