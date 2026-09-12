"""Allow ``python -m testgap`` and ``uv run testgap`` (the package directory)."""

from __future__ import annotations

import sys
from pathlib import Path


def _main() -> int:
    if __package__ in {None, ""}:
        root = Path(__file__).resolve().parent.parent
        root_s = str(root)
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
        from testgap.cli import main
    else:
        from .cli import main
    return main()


if __name__ == "__main__":
    sys.exit(_main())
