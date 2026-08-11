try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

# Scaffold package. Tutorials live under ./tutorials — add your own scripts
# there. Installing this package (`pip install -e .`) pulls in every dependency
# the tutorials need (see install_requires in setup.cfg).

__all__ = ["__version__"]
