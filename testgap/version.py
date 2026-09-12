"""Package version without importing the rest of ``testgap``."""

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    try:
        return version("test-gap")
    except PackageNotFoundError:
        return "0.0.0+source"


__version__ = package_version()
