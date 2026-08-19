try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

# Scaffold package. Tutorials live under ./tutorials — add your own scripts
# there. Installing this package (`pip install -e .`) pulls in every dependency
# the tutorials need (see install_requires in setup.cfg).

from .chatbot import (
    get_gwdg_api_key,
    get_gwdg_base_url,
    list_gwdg_models,
    get_gwdg_chat_model,
    get_session_history
)
from .logos import get_banner

__all__ = ["__version__",
           "get_gwdg_api_key",
           "get_gwdg_base_url",
           "list_gwdg_models",
           "get_gwdg_chat_model",
           "get_session_history",
           "get_banner"
           
           ]
