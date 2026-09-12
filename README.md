# test-gap

[![PyPI](https://img.shields.io/pypi/v/test-gap.svg)](https://pypi.org/project/test-gap/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/test-gap/)
[![Test](https://github.com/karlhillx/test-gap/actions/workflows/test.yml/badge.svg)](https://github.com/karlhillx/test-gap/actions/workflows/test.yml)

**Where are the tests I should write next?** test-gap reads `coverage.py` data, maps uncovered lines onto functions, and **ranks** the gaps — it is a test-work prioritizer, not another coverage percentage.

## Why test-gap?

- **Rank gaps, do not just list them** — uncovered branches, cyclomatic-ish complexity, git-changed lines, and missing tests all feed one score
- **Human by default, JSON when you need it** — `--prompt` turns the same evidence into a concise agent task
- **Optional changed-line gate** — `--fail-under-changed 95` for CI; the default command still just advises
- **Small install** — one runtime dependency: **coverage** (see `pyproject.toml`)

```text
test-gap 1.0.0

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
uvx test-gap
```

Persistent install on your `PATH`:

```bash
uv tool install test-gap
test-gap --doctor
```

### via pipx (isolated CLI)

```bash
pipx install test-gap
```

### via pip

```bash
pip install test-gap
```

### If `test-gap` is not on your `PATH`

```bash
python3 -m testgap --version
python3 -m testgap --doctor
```

### from source

```bash
git clone https://github.com/karlhillx/test-gap.git
cd test-gap
uv sync
uv run test-gap --version
uv run testgap --version          # same CLI; uv runs the package directory
uv run python -m testgap --version
```

## Quick start

Generate coverage first (pytest-cov or coverage.py), then rank:

```bash
pytest --cov --cov-report=json
test-gap
```

test-gap looks for `coverage.json`, then `coverage.xml`, then `.coverage`, walking up from `.` to the nearest `pyproject.toml` / `.git` when `--repo` is omitted.

```bash
test-gap --changed                 # only gaps on git-changed lines
test-gap --top 10                  # default
test-gap --file src/foo.py         # one file (repeatable)
test-gap --json                    # machine-readable report
test-gap --prompt                  # evidence-based agent task
test-gap --fail-under-changed 95   # exit 1 if changed-line coverage is low
test-gap --doctor                  # coverage file, git, and Python
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

test-gap ships type hints (`py.typed`) and a small public API:

```python
from testgap import GapError, analyze

try:
    report = analyze(".", changed_only=True, top=5)
except GapError as exc:
    raise SystemExit(exc) from exc

for gap in report.gaps:
    print(gap.qualname, gap.risk, gap.score)
```

`analyze(...)` returns a `GapReport`. Optional kwargs: `coverage`, `changed_only`, `base`, `files`, `top`. You can also pass an `Options` instance. Only names in `testgap.__all__` are public; import the CLI via `python -m testgap` or the `test-gap` console script.

## Requirements

- **Python** 3.12+ (`requires-python` in `pyproject.toml`)
- **OS** Linux, macOS, and Windows
- **coverage** 7.x (installed automatically with `test-gap`)
- **git** (optional; needed for `--changed`, the changed-code section, and `--fail-under-changed`)

### Local development

```bash
uv sync
uv run pytest
uv run pytest --cov=testgap --cov-report=xml tests/
uv run ruff check testgap tests
uv run ty check
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `NO_COLOR` | Disable color when `--color auto` |
| `FORCE_COLOR` | Enable color when `--color auto` even if stdout is not a TTY |
| `TEST_GAP_DEBUG` | Print a traceback on unexpected errors (same as `--verbose` for crashes) |

test-gap **does not run your test suite**. It only reads coverage artifacts, source files, and git diffs.

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

Install [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`), then retry `uvx test-gap`.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). User-facing changes should be noted in [CHANGELOG.md](CHANGELOG.md). Security reports: [SECURITY.md](SECURITY.md).

## Links

- [PyPI](https://pypi.org/project/test-gap/)
- [GitHub Repository](https://github.com/karlhillx/test-gap)
- [Issue Tracker](https://github.com/karlhillx/test-gap/issues)
