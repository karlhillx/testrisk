"""Load coverage.py JSON, XML, or ``.coverage`` into a snapshot."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .contexts import parse_contexts
from .discover import relativize
from .errors import GapError
from .models import BranchGap, CoverageSnapshot, FileCoverage


def load_coverage(root: Path, source: Path) -> CoverageSnapshot:
    """Parse *source* (json / xml / coverage db) relative to *root*."""
    kind = _detect_format(source)
    if kind == "json":
        snapshot = _load_json(source)
    elif kind == "xml":
        snapshot = _load_xml(source, root)
    else:
        snapshot = _load_coverage_db(source)
    files = tuple(_with_relative_paths(file_cov, root) for file_cov in snapshot.files)
    return CoverageSnapshot(
        files=files,
        source=relativize(source, root),
        line_percent=snapshot.line_percent,
        branch_percent=snapshot.branch_percent,
        covered_lines=snapshot.covered_lines,
        statements=snapshot.statements,
        covered_branches=snapshot.covered_branches,
        branches=snapshot.branches,
    )


def _detect_format(path: Path) -> str:
    name = path.name
    if name == ".coverage" or name.startswith(".coverage."):
        return "db"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".xml"):
        return "xml"
    head = path.read_bytes()[:64].lstrip()
    if head.startswith(b"{") or head.startswith(b"["):
        return "json"
    if head.startswith(b"<") or head.startswith(b"<?xml"):
        return "xml"
    return "db"


def _with_relative_paths(file_cov: FileCoverage, root: Path) -> FileCoverage:
    return FileCoverage(
        path=relativize(file_cov.path, root),
        executed_lines=file_cov.executed_lines,
        missing_lines=file_cov.missing_lines,
        excluded_lines=file_cov.excluded_lines,
        missing_branches=file_cov.missing_branches,
        contexts=file_cov.contexts,
    )


def _load_json(source: Path) -> CoverageSnapshot:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GapError(f"Could not read coverage JSON {source}: {exc}") from exc
    if not isinstance(payload, dict) or "files" not in payload:
        raise GapError(f"Not a coverage.py JSON report: {source}")

    files: list[FileCoverage] = []
    raw_files = payload.get("files") or {}
    if not isinstance(raw_files, dict):
        raise GapError(f"Not a coverage.py JSON report: {source}")
    for filename, info in raw_files.items():
        if not isinstance(info, dict):
            continue
        files.append(_file_from_json(Path(filename), info))

    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    statements = int(totals.get("num_statements") or 0)
    covered = int(totals.get("covered_lines") or 0)
    line_percent = _percent(totals.get("percent_covered"), covered, statements)
    branches = totals.get("num_branches")
    covered_branches = totals.get("covered_branches")
    branch_percent = None
    if branches is not None:
        branch_n = int(branches)
        covered_n = int(covered_branches or 0)
        raw_branch = totals.get("percent_covered_branches")
        branch_percent = _percent(raw_branch, covered_n, branch_n)
        covered_branches = covered_n
        branches = branch_n
    else:
        covered_branches = None
        branches = None

    return CoverageSnapshot(
        files=tuple(files),
        source=source,
        line_percent=line_percent,
        branch_percent=branch_percent,
        covered_lines=covered,
        statements=statements,
        covered_branches=covered_branches,
        branches=branches,
    )


def _file_from_json(path: Path, info: dict) -> FileCoverage:
    executed = frozenset(int(n) for n in info.get("executed_lines") or [])
    missing = frozenset(int(n) for n in info.get("missing_lines") or [])
    excluded = frozenset(int(n) for n in info.get("excluded_lines") or [])
    branches: list[BranchGap] = []
    for raw in info.get("missing_branches") or []:
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            branches.append(BranchGap(line=int(raw[0]), dest=int(raw[1])))
    return FileCoverage(
        path=path,
        executed_lines=executed,
        missing_lines=missing,
        excluded_lines=excluded,
        missing_branches=tuple(branches),
        contexts=parse_contexts(info.get("contexts")),
    )


def _load_xml(source: Path, root: Path) -> CoverageSnapshot:
    try:
        tree = ET.parse(source)
    except (OSError, ET.ParseError) as exc:
        raise GapError(f"Could not read coverage XML {source}: {exc}") from exc
    cov = tree.getroot()
    sources = [Path(node.text) for node in cov.findall("sources/source") if node.text]
    files: list[FileCoverage] = []
    for cls in cov.findall(".//class"):
        filename = cls.get("filename")
        if not filename:
            continue
        path = _xml_filename(filename, sources, root)
        executed: set[int] = set()
        missing: set[int] = set()
        branch_gaps: list[BranchGap] = []
        for line in cls.findall("lines/line"):
            number = int(line.get("number", "0"))
            hits = int(line.get("hits", "0"))
            if hits > 0:
                executed.add(number)
            else:
                missing.add(number)
            if line.get("branch") == "true":
                for dest in _parse_missing_branches(line.get("missing-branches")):
                    branch_gaps.append(BranchGap(line=number, dest=dest))
        files.append(
            FileCoverage(
                path=path,
                executed_lines=frozenset(executed),
                missing_lines=frozenset(missing),
                excluded_lines=frozenset(),
                missing_branches=tuple(branch_gaps),
            )
        )

    statements = _int_attr(cov, "lines-valid")
    covered = _int_attr(cov, "lines-covered")
    line_percent = _rate_percent(cov.get("line-rate"), covered, statements)
    branch_valid = cov.get("branches-valid")
    if branch_valid is None:
        branch_percent = None
        covered_branches = None
        branch_count = None
    else:
        branch_count = int(branch_valid)
        covered_branches = _int_attr(cov, "branches-covered")
        branch_percent = _rate_percent(cov.get("branch-rate"), covered_branches, branch_count)

    return CoverageSnapshot(
        files=tuple(files),
        source=source,
        line_percent=line_percent,
        branch_percent=branch_percent,
        covered_lines=covered,
        statements=statements,
        covered_branches=covered_branches,
        branches=branch_count,
    )


def _xml_filename(filename: str, sources: list[Path], root: Path) -> Path:
    path = Path(filename)
    if path.is_absolute():
        return path
    for src in sources:
        candidate = src / path
        if candidate.is_file():
            return candidate
    return root / path


def _parse_missing_branches(raw: str | None) -> list[int]:
    if not raw:
        return []
    dests: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part or part in {"exit", "default"}:
            dests.append(-1)
            continue
        try:
            dests.append(int(part))
        except ValueError:
            dests.append(-1)
    return dests


def _load_coverage_db(source: Path) -> CoverageSnapshot:
    try:
        from coverage import Coverage
    except ImportError as exc:
        raise GapError("The coverage package is required to read a .coverage file.") from exc

    cov = Coverage(data_file=str(source))
    try:
        cov.load()
    except Exception as exc:
        raise GapError(f"Could not load coverage data {source}: {exc}") from exc

    data = cov.get_data()
    files: list[FileCoverage] = []
    covered = 0
    statements = 0
    covered_branches = 0
    branches = 0
    has_arcs = data.has_arcs()

    for filename in data.measured_files():
        try:
            _name, stmts, excluded, missing, _fmt = cov.analysis2(filename)
        except Exception:
            continue
        stmt_set = frozenset(int(n) for n in stmts)
        missing_set = frozenset(int(n) for n in missing)
        executed = stmt_set - missing_set
        branch_gaps: list[BranchGap] = []
        if has_arcs:
            missing_fn = getattr(data, "missing_arcs", None)
            missing_arcs = missing_fn(filename) if callable(missing_fn) else []
            missing_arcs = missing_arcs or []
            executed_arcs = data.arcs(filename) or []
            branches += len(executed_arcs)
            covered_branches += max(0, len(executed_arcs) - len(missing_arcs))
            for src, dest in missing_arcs:
                if src > 0:
                    branch_gaps.append(BranchGap(line=int(src), dest=int(dest)))
        covered += len(executed)
        statements += len(stmt_set)
        files.append(
            FileCoverage(
                path=Path(filename),
                executed_lines=executed,
                missing_lines=missing_set,
                excluded_lines=frozenset(int(n) for n in excluded),
                missing_branches=tuple(branch_gaps),
                contexts=_db_contexts(data, filename),
            )
        )

    line_percent = _percent(None, covered, statements)
    branch_percent = _percent(None, covered_branches, branches) if has_arcs else None
    return CoverageSnapshot(
        files=tuple(files),
        source=source,
        line_percent=line_percent,
        branch_percent=branch_percent,
        covered_lines=covered,
        statements=statements,
        covered_branches=covered_branches if has_arcs else None,
        branches=branches if has_arcs else None,
    )


def _db_contexts(data: object, filename: str) -> dict[int, tuple[str, ...]]:
    reader = getattr(data, "contexts_by_lineno", None)
    if not callable(reader):
        return {}
    try:
        raw = reader(filename) or {}
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    mapped: dict[int, tuple[str, ...]] = {}
    for line, values in raw.items():
        try:
            number = int(line)
        except (TypeError, ValueError):
            continue
        items = values if isinstance(values, (list, tuple, set)) else ()
        names = parse_contexts({number: list(items)}).get(number, ())
        if names:
            mapped[number] = names
    return mapped


def _percent(raw: object, covered: int, total: int) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if total <= 0:
        return 100.0
    return 100.0 * covered / total


def _rate_percent(raw: str | None, covered: int, total: int) -> float:
    if raw is not None:
        try:
            return float(raw) * 100.0
        except ValueError:
            pass
    return _percent(None, covered, total)


def _int_attr(node: ET.Element, name: str) -> int:
    raw = node.get(name)
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0
