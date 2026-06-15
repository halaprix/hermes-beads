"""Hermes-Beads CLI package."""

from importlib.metadata import PackageNotFoundError, version as _v

try:
    __version__ = _v("hermes-beads")
except PackageNotFoundError:
    __version__ = "0.0.0+local"
