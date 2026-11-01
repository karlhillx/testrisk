```text
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║       ████████╗███████╗███████╗████████╗██████╗ ██╗███████╗██╗  ██╗       ║
║       ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝██╔══██╗██║██╔════╝██║ ██╔╝       ║
║          ██║   █████╗  ███████╗   ██║   ██████╔╝██║███████╗█████╔╝        ║
║          ██║   ██╔══╝  ╚════██║   ██║   ██╔══██╗██║╚════██║██╔═██╗        ║
║          ██║   ███████╗███████║   ██║   ██║  ██║██║███████║██║  ██╗       ║
║          ╚═╝   ╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝       ║
║                                                                           ║
║              Find the code most likely to need better tests               ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

# testrisk

[![PyPI](https://img.shields.io/pypi/v/testrisk.svg)](https://pypi.org/project/testrisk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/testrisk/)
[![Test](https://github.com/karlhillx/testrisk/actions/workflows/test.yml/badge.svg)](https://github.com/karlhillx/testrisk/actions/workflows/test.yml)

**Find the code most likely to need better tests.** testrisk reads `coverage.py` data, maps uncovered lines onto functions, and ranks them by test risk — not another coverage percentage.

## Why testrisk?

- **Rank gaps, do not just list them** — uncovered branches, cyclomatic-ish complexity, git-changed lines, and missing or ceremonial tests all feed one score
- **Human by default, JSON when you need it** — `--prompt` turns the same evidence into a concise agent task
- **Optional CI gates** — `--fail-under-changed 95`, `--fail-on-risk HIGH`, and `--fail-on-weak`; the default command still just advises
- **Small install** — one runtime dependency: **coverage** (see `pyproject.toml`)

```text
testrisk 1.1.0

  Coverage    91.7%   Branch 84.2%
  Changed     94.1% covered   2 uncovered lines

Highest-value test gaps

  1. demo/services.py::ServiceManager.start
     risk      HIGH  ·  18.5
     missing   15-18  ·  2 branches
     tests     indirect → tests/test_services.py

  ----------------------------------------------------------

  2. demo/services.py::parse_config
     risk      LOW  ·  4.2
     missing   8-9
     tests     tests/test_services.py

  ----------------------------------------------------------

  Next        tests/test_services.py
  Shown       2 gaps
  Risk        1 HIGH  ·  0 MEDIUM  ·  1 LOW
  Checks      0 none  ·  1 indirect  ·  0 weak  ·  1 meaningful
  Hint        Start with the top HIGH gap. Score favors changed uncovered lines and tests that cannot fail.
```

## Installation

### uvx (recommended — zero install)

```bash
cd /path/to/your/repo
uvx testrisk
```

Persistent install on your `PATH`:

```bash
uv tool install testrisk
testrisk --doctor
```

### via pipx (isolated CLI)

```bash
pipx install testrisk
```

### via pip

```bash
pip install testrisk
```

### If `testrisk` is not on your `PATH`

```bash
python -m testrisk --version
python -m testrisk --doctor
```

### from source

```bash
git clone https://github.com/karlhillx/testrisk.git
cd testrisk
uv sync
uv run testrisk --version
uv run python -m testrisk --version
```

## Quick start

Generate coverage, then rank **this branch**:

```bash
pytest --cov --cov-report=json
testrisk --changed
# or one command after the suite:
pytest --cov --cov-report=json --testrisk
```

Add `--cov-context=test` when you want testrisk to see which tests already executed a function (not just whether a test file mentions it).

`--changed` is the everyday command. A full-repo `testrisk` still works when you want every gap; the report will nudge you back to `--changed` when the list is long.

testrisk looks for `coverage.json`, then `coverage.xml`, then `.coverage`, walking up from `.` to the nearest `pyproject.toml` / `.git` when `--repo` is omitted. If coverage is older than files you just changed, doctor and the text report warn you to refresh it.

```bash
testrisk --changed                 # everyday: only gaps on git-changed lines
testrisk --top 10                  # default
testrisk --file src/foo.py         # one file or glob (repeatable)
testrisk --exclude '**/generated/**'
testrisk --no-default-omit         # keep __init__.py and migrations/ in the ranking
testrisk --min-risk HIGH           # hide LOW / MEDIUM
testrisk --weak-only               # missing, indirect, or ceremonial related tests
testrisk --json                    # machine-readable report (schema testrisk.gap/v2)
testrisk --format sarif            # GitHub code scanning
testrisk --comment                 # PR comment + GITHUB_STEP_SUMMARY when in Actions
testrisk --write-baseline          # snapshot current gaps as waived
testrisk --prompt                  # evidence-based agent task (includes source)
testrisk --explain                 # show how each score was assembled
testrisk --fail-under-changed 95   # exit 1 if changed-line coverage is low
testrisk --fail-on-risk HIGH       # exit 1 if any matched gap is HIGH or worse
testrisk --fail-on-weak            # exit 1 if related tests cannot fail
testrisk --doctor                  # coverage file, git, and the generate command
```

`--quiet` prints only the suggested next test file.

Defaults can live in `pyproject.toml` so CI and local runs match:

```toml
[tool.testrisk]
changed = true
fail-on-risk = "HIGH"
fail-on-weak = true
fail-under-changed = 95
omit = ["**/generated/**"]
include = ["src/**"]
default-omit = true
explain = false
baseline = ".testrisk-baseline"

[tool.testrisk.weights]
missing-lines = 1.0
missing-branches = 2.0
complexity = 0.75
changed-uncovered = 3.0
no-tests = 4.0
churn = 0.25
fan-in = 0.4
```

CLI flags override the table. `--exclude` merges with `omit`. `--changed` / `--no-changed` override `changed`. `--no-default-omit` turns off the built-in skip of `__init__.py` and `migrations/`.

### GitHub Actions

Use the composite action after you generate coverage. Fetch the base branch so `--changed` can diff:

```yaml
- uses: actions/checkout@v6
  with:
    fetch-depth: 0

- name: Tests with coverage
  run: pytest --cov --cov-report=json

- uses: karlhillx/testrisk@v1
  with:
    changed: true
    fail-on-risk: HIGH
    fail-on-weak: true
    fail-under-changed: "95"
    comment: true
    sarif: true

# then, optionally:
# - uses: github/codeql-action/upload-sarif@v3
#   with:
#     sarif_file: testrisk.sarif
```

On pull requests, testrisk treats `GITHUB_BASE_REF` (then `origin/<ref>`) as the default `--base`. Pin a release with `version: 1.1.0` if you do not want `uvx` to pull latest.

### `--prompt`

```text
Write focused unit tests for these uncovered behaviors.

Do not modify production code unless required to expose a testable seam.

Target:
src/foo.py::parse_config

Uncovered:
44-48, 57

Untested branches:
line 46: false branch
line 57: exception/exit branch

Complexity: 6
Score: 12.0
Risk: MEDIUM

Existing tests:
tests/test_foo.py
```

`--prompt` also includes a numbered `Source:` excerpt of the uncovered lines when the file is on disk.

## How ranking works

Each function or method with uncovered statements or branches gets a score:

| Signal | Weight |
|--------|--------|
| Uncovered executable lines | × 1 |
| Uncovered branches | × 2 |
| Complexity above 1 | × 0.75 |
| Changed uncovered lines | × 3 |
| No meaningful related tests (missing or ceremonial) | + 4 |
| Recent file churn (capped) | × 0.25 |
| Production fan-in (capped) | × 0.4 |

Risk is `HIGH` / `MEDIUM` / `LOW` from that score plus a few hard rules (for example: five or more changed uncovered lines, or complexity ≥ 10 with two uncovered branches).

Related tests are existing `test_*.py` / `*_test.py` files that mention the function. Short or generic names (`start`, `run`, `get`) also need the module stem or class name in the same file. A conventional `tests/test_<stem>.py` is not treated as coverage just because it exists. Each gap is labeled **none** (no test file yet), **indirect** (the conventional file exists but does not mention the function), **weak** (mentioned, but the checks cannot fail), or **meaningful**. When the coverage artifact includes test contexts, `executed_by` lists the tests that already ran other lines of the function — those gaps are meaningful even if the uncovered lines remain.

`.testrisk-baseline` (JSON or one qualname per line) waives known gaps from `--fail-on-risk` / `--fail-on-weak`. `--write-baseline` snapshots the current matched set.

Related tests that cannot fail — no assertions, only `assert True` / `assert x is not None`, or an import with no call — are marked **Weak**. They still appear as related files, but they do not count as meaningful checks (same +4 as none or indirect). This is a static filter, not mutation testing. testrisk does not run your suite.

`<module>` gaps (import-time statements that sit outside a function) are omitted unless they have uncovered branches or sit on git-changed lines. `__init__.py` and `migrations/` are omitted by default.

If no related test is found, the suggestion is `tests/test_<stem>.py` for a flat layout, or `tests/<package>/test_<stem>.py` for `src/` trees and nested packages.

`--base` defaults to `GITHUB_BASE_REF` (and `origin/<ref>`) when set, then `origin/main`, then `main`, then `origin/master`, then `master`, then `HEAD`. Changed lines are `git diff` against the merge-base of that ref (plus your working tree).

`--fail-on-risk` and `--fail-on-weak` look at every gap that remains after `--changed`, omit/include, `--min-risk`, and `--weak-only`, not only the `--top` slice.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (or changed-line coverage meets `--fail-under-changed`) |
| `1` | Runtime failure (no coverage data, or a `--fail-under-changed` / `--fail-on-risk` / `--fail-on-weak` gate) |
| `2` | Usage error |
| `130` | Interrupted with `Ctrl-C` |

## Use as a library

testrisk ships type hints (`py.typed`) and a small public API:

```python
from testrisk import GapError, analyze

try:
    report = analyze(".", changed_only=True, top=5)
except GapError as exc:
    raise SystemExit(exc) from exc

for gap in report.gaps:
    print(gap.qualname, gap.risk, gap.score)
```

`analyze(...)` returns a `GapReport`. JSON reports include `"schema": "testrisk.gap/v2"`. Optional kwargs: `coverage`, `changed_only`, `base`, `files`, `omit`, `top`, `min_risk`, `weights`, `weak_only`, `default_omit`, `baseline`, `write_baseline`. You can also pass an `Options` instance. `omit` / include globs and other defaults are read from `[tool.testrisk]` unless you pass `Options(apply_config=False)`. Only names in `testrisk.__all__` are public; import the CLI via `python -m testrisk` or the `testrisk` console script.

## Requirements

- **Python** 3.12+ (`requires-python` in `pyproject.toml`)
- **OS** Linux, macOS, and Windows
- **coverage** 7.x (installed automatically with `testrisk`)
- **git** (optional; needed for `--changed`, the changed-code section, and `--fail-under-changed`)

### Local development

```bash
uv sync
uv run pytest
uv run pytest --cov=testrisk --cov-report=xml tests/
uv run ruff check testrisk tests
uv run ty check
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `NO_COLOR` | Disable color when `--color auto` |
| `FORCE_COLOR` | Enable color when `--color auto` even if stdout is not a TTY |
| `TESTRISK_DEBUG` | Print a traceback on unexpected errors (same as `--verbose` for crashes) |
| `GITHUB_BASE_REF` | Default `--base` on GitHub Actions pull requests (`origin/<ref>`, then `<ref>`) |
| `GITHUB_TOKEN` / `GH_TOKEN` | Used by `--comment` to upsert the PR comment |
| `GITHUB_STEP_SUMMARY` | `--comment` appends the same markdown to the job summary |

testrisk **does not run your test suite**. It only reads coverage artifacts, source files, and git diffs.

## Troubleshooting

### "No coverage data found"

Run tests with coverage and write a report in the repo root:

```bash
pytest --cov --cov-report=json
# optional: which tests executed each line
pytest --cov --cov-context=test --cov-report=json
# or
coverage run -m pytest && coverage json
```

Then pass `--coverage PATH` if the file is not in the usual place. Rank the branch with `testrisk --changed`.

### Coverage looks stale

The coverage file is older than Python files changed on this branch (or dirty in the working tree). Re-run `pytest --cov --cov-report=json` and try again.

### Changed-code section is missing

The checkout is not a git repo, or git is not on `PATH`. `--fail-under-changed` needs git.

### `uvx: command not found`

Install [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`), then retry `uvx testrisk`.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). User-facing changes should be noted in [CHANGELOG.md](CHANGELOG.md). Security reports: [SECURITY.md](SECURITY.md).

## Links

- [PyPI](https://pypi.org/project/testrisk/)
- [GitHub Repository](https://github.com/karlhillx/testrisk)
- [Issue Tracker](https://github.com/karlhillx/testrisk/issues)
