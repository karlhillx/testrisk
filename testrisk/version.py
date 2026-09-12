"""Package version without importing the rest of ``testrisk``."""

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    try:
        return version("testrisk")
    except PackageNotFoundError:
        return "0.0.0+source"


__version__ = package_version()
