"""Load ``[tool.testrisk]`` defaults from ``pyproject.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import GapError
from .models import Risk, parse_risk
from .rank import DEFAULT_WEIGHTS, Weights

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    """Project defaults. CLI flags override these."""

    base: str | None = None
    top: int = 10
    changed: bool = False
    fail_under_changed: float | None = None
    fail_on_risk: Risk | None = None
    min_risk: Risk | None = None
    omit: tuple[str, ...] = ()
    include: tuple[str, ...] = ()
    explain: bool = False
    weak_only: bool = False
    fail_on_weak: bool = False
    default_omit: bool = True
    baseline: str | None = None
    weights: Weights = DEFAULT_WEIGHTS


def load_settings(root: Path) -> Settings:
    """Read ``[tool.testrisk]`` from *root* / ``pyproject.toml``, if present."""
    path = root / "pyproject.toml"
    if not path.is_file():
        return Settings()
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise GapError(f"Could not read {path}: {exc}") from exc
    tool = payload.get("tool")
    if not isinstance(tool, dict):
        return Settings()
    raw = tool.get("testrisk")
    if raw is None:
        return Settings()
    if not isinstance(raw, dict):
        raise GapError("[tool.testrisk] must be a table")
    return parse_settings(raw)


def parse_settings(raw: dict[str, object]) -> Settings:
    """Build :class:`Settings` from a TOML table."""
    settings = Settings()
    if _has(raw, "base"):
        settings = replace(settings, base=_opt_str(_get(raw, "base"), "base"))
    if _has(raw, "top"):
        settings = replace(settings, top=_int(_get(raw, "top"), "top", minimum=0))
    if _has(raw, "changed"):
        settings = replace(settings, changed=_bool(_get(raw, "changed"), "changed"))
    if _has(raw, "fail_under_changed", "fail-under-changed"):
        value = _float(
            _get(raw, "fail_under_changed", "fail-under-changed"),
            "fail-under-changed",
        )
        if not 0 <= value <= 100:
            raise GapError("[tool.testrisk] fail-under-changed must be between 0 and 100")
        settings = replace(settings, fail_under_changed=value)
    if _has(raw, "fail_on_risk", "fail-on-risk"):
        settings = replace(
            settings,
            fail_on_risk=_risk(_get(raw, "fail_on_risk", "fail-on-risk"), "fail-on-risk"),
        )
    if _has(raw, "min_risk", "min-risk"):
        settings = replace(
            settings,
            min_risk=_risk(_get(raw, "min_risk", "min-risk"), "min-risk"),
        )
    if _has(raw, "omit", "exclude"):
        settings = replace(settings, omit=_str_tuple(_get(raw, "omit", "exclude"), "omit"))
    if _has(raw, "include", "files"):
        settings = replace(settings, include=_str_tuple(_get(raw, "include", "files"), "include"))
    if _has(raw, "explain"):
        settings = replace(settings, explain=_bool(_get(raw, "explain"), "explain"))
    if _has(raw, "weak_only", "weak-only"):
        settings = replace(
            settings,
            weak_only=_bool(_get(raw, "weak_only", "weak-only"), "weak-only"),
        )
    if _has(raw, "fail_on_weak", "fail-on-weak"):
        settings = replace(
            settings,
            fail_on_weak=_bool(_get(raw, "fail_on_weak", "fail-on-weak"), "fail-on-weak"),
        )
    if _has(raw, "default_omit", "default-omit"):
        settings = replace(
            settings,
            default_omit=_bool(_get(raw, "default_omit", "default-omit"), "default-omit"),
        )
    if _has(raw, "baseline"):
        settings = replace(settings, baseline=_opt_str(_get(raw, "baseline"), "baseline"))
    weights_raw = raw.get("weights")
    if weights_raw is not None:
        if not isinstance(weights_raw, dict):
            raise GapError("[tool.testrisk.weights] must be a table")
        settings = replace(settings, weights=_parse_weights(weights_raw))
    return settings


def has_testrisk_table(root: Path) -> bool:
    """True when ``pyproject.toml`` defines ``[tool.testrisk]``."""
    path = root / "pyproject.toml"
    if not path.is_file():
        return False
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tool = payload.get("tool")
    return isinstance(tool, dict) and isinstance(tool.get("testrisk"), dict)


def _parse_weights(raw: dict[str, object]) -> Weights:
    current = Weights()
    mapping = {
        "missing_lines": ("missing_lines", "missing-lines"),
        "missing_branches": ("missing_branches", "missing-branches"),
        "complexity": ("complexity",),
        "changed_uncovered": ("changed_uncovered", "changed-uncovered"),
        "no_tests": ("no_tests", "no-tests"),
        "churn": ("churn",),
        "fan_in": ("fan_in", "fan-in"),
    }
    values: dict[str, float] = {}
    for field, aliases in mapping.items():
        if any(alias in raw or alias.replace("_", "-") in raw for alias in aliases):
            values[field] = _float(_get(raw, *aliases), aliases[0])
    return replace(current, **values)


def _has(raw: dict[str, object], *names: str) -> bool:
    return any(name in raw or name.replace("_", "-") in raw for name in names)


def _get(raw: dict[str, object], *names: str) -> object:
    for name in names:
        if name in raw:
            return raw[name]
        kebab = name.replace("_", "-")
        if kebab in raw:
            return raw[kebab]
    raise KeyError(names[0])


def _opt_str(value: object, name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    raise GapError(f"[tool.testrisk] {name} must be a string")


def _int(value: object, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GapError(f"[tool.testrisk] {name} must be an integer")
    if minimum is not None and value < minimum:
        raise GapError(f"[tool.testrisk] {name} must be >= {minimum}")
    return value


def _float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GapError(f"[tool.testrisk] {name} must be a number")
    return float(value)


def _bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in _TRUE | _FALSE:
        return value.strip().lower() in _TRUE
    raise GapError(f"[tool.testrisk] {name} must be a boolean")


def _str_tuple(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise GapError(f"[tool.testrisk] {name} entries must be strings")
            items.append(item.strip())
        return tuple(items)
    raise GapError(f"[tool.testrisk] {name} must be a string or array of strings")


def _risk(value: object, name: str) -> Risk:
    if not isinstance(value, str):
        raise GapError(f"[tool.testrisk] {name} must be LOW, MEDIUM, or HIGH")
    try:
        return parse_risk(value)
    except ValueError as exc:
        raise GapError(f"[tool.testrisk] {exc}") from exc
