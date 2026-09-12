"""User-facing errors with clean CLI messages."""


class GapError(Exception):
    """A problem the user can act on (missing coverage, bad path, …)."""
