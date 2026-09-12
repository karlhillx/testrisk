# testrisk

[![PyPI](https://img.shields.io/pypi/v/testrisk.svg)](https://pypi.org/project/testrisk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/testrisk/)
[![Test](https://github.com/karlhillx/testrisk/actions/workflows/test.yml/badge.svg)](https://github.com/karlhillx/testrisk/actions/workflows/test.yml)

**Find the code most likely to need better tests.** testrisk reads `coverage.py` data, maps uncovered lines onto functions, and ranks them by test risk — not another coverage percentage.

## Why testrisk?

- **Rank gaps, do not just list them** — uncovered branches, cyclomatic-ish complexity, git-changed lines, and missing tests all feed one score
- **Human by default, JSON when you need it** — `--prompt` turns the same evidence into a concise agent task
- **Optional changed-line gate** — `--fail-under-changed 95` for CI; the default command still just advises
- **Small install** — one runtime dependency: **coverage** (see `pyproject.toml`)

```text
testrisk 1.0.0

Coverage   91.7%
Branch     84.2%

Highest-value test gaps

  1. demo/services.py::ServiceManager.start
     Missing: 15-18
     Branches: 2 uncovered
     Complexity: 3
     Risk: HIGH

Changed code
  94.1% covered
  2 uncovered executable lines

Suggested next target:
  tests/test_services.py
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

Generate coverage first (pytest-cov or coverage.py), then rank:

```bash
pytest --cov --cov-report=json
testrisk
```

testrisk looks for `coverage.json`, then `coverage.xml`, then `.coverage`, walking up from `.` to the nearest `pyproject.toml` / `.git` when `--repo` is omitted.

```bash
testrisk --changed                 # only gaps on git-changed lines
testrisk --top 10                  # default
testrisk --file src/foo.py         # one file (repeatable)
testrisk --json                    # machine-readable report
testrisk --prompt                  # evidence-based agent task
testrisk --fail-under-changed 95   # exit 1 if changed-line coverage is low
testrisk --doctor                  # coverage file, git, and Python
```

`--quiet` prints only the suggested next test file.

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
Risk: MEDIUM

Existing tests:
tests/test_foo.py
```

## How ranking works

Each function or method with uncovered statements or branches gets a score:

| Signal | Weight |
|--------|--------|
| Uncovered executable lines | × 1 |
| Uncovered branches | × 2 |
| Complexity above 1 | × 0.75 |
| Changed uncovered lines | × 3 |
| No related test file | + 4 |

Risk is `HIGH` / `MEDIUM` / `LOW` from that score plus a few hard rules (for example: five or more changed uncovered lines, or complexity ≥ 10 with two uncovered branches).

Related tests are existing `test_*.py` / `*_test.py` files that mention the function or module stem. If none exist, the suggestion is `tests/test_<stem>.py`.

`--base` defaults to `origin/main`, then `main`, then `origin/master`, then `master`, then `HEAD`. Changed lines are `git diff` against the merge-base of that ref (plus your working tree).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (or changed-line coverage meets `--fail-under-changed`) |
| `1` | Runtime failure (no coverage data, changed-line coverage below the floor) |
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

`analyze(...)` returns a `GapReport`. Optional kwargs: `coverage`, `changed_only`, `base`, `files`, `top`. You can also pass an `Options` instance. Only names in `testrisk.__all__` are public; import the CLI via `python -m testrisk` or the `testrisk` console script.

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

testrisk **does not run your test suite**. It only reads coverage artifacts, source files, and git diffs.

## Troubleshooting

### "No coverage data found"

Run tests with coverage and write a report in the repo root:

```bash
pytest --cov --cov-report=json
# or
coverage run -m pytest && coverage json
```

Then pass `--coverage PATH` if the file is not in the usual place.

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
