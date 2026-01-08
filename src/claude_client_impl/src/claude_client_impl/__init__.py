"""Public exports for the Claude client implementation package."""

from claude_client_impl.claude_impl import register as _register_client
from claude_client_impl.models_impl import register as _register_models


def register() -> None:
    """Register the Claude client and model implementations."""
    _register_client()
    _register_models()


register()
