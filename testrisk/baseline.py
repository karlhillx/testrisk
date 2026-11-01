"""Waive known gaps so a legacy repo can adopt risk gates incrementally."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import GapError

DEFAULT_BASELINE = ".testrisk-baseline"
BASELINE_SCHEMA = "testrisk.baseline/v1"


def resolve_baseline(root: Path, explicit: Path | str | None) -> Path | None:
    """Return the baseline file to read, if any."""
    if explicit is not None:
        if str(explicit).strip() == "":
            return None
        path = Path(explicit)
        path = path if path.is_absolute() else root / path
        return path
    candidate = root / DEFAULT_BASELINE
    return candidate if candidate.is_file() else None


def load_baseline(path: Path) -> frozenset[str]:
    """Read waived qualnames from JSON or a line-oriented file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GapError(f"Could not read baseline {path}: {exc}") from exc
    stripped = text.lstrip()
    if not stripped:
        return frozenset()
    if stripped.startswith("{"):
        return _from_json(path, stripped)
    names: list[str] = []
    for line in text.splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        names.append(item)
    return frozenset(names)


def write_baseline(path: Path, qualnames: tuple[str, ...] | list[str]) -> None:
    """Write waived qualnames as JSON for stable diffs."""
    ordered = sorted(dict.fromkeys(qualnames))
    payload = {"schema": BASELINE_SCHEMA, "waived": ordered}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _from_json(path: Path, text: str) -> frozenset[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GapError(f"Could not parse baseline {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GapError(f"Baseline {path} must be a JSON object")
    raw = payload.get("waived", payload.get("gaps", []))
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise GapError(f"Baseline {path} waived entries must be strings")
    return frozenset(item.strip() for item in raw if item.strip())
