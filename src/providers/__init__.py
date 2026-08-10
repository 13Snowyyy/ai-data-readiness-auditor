"""Generation providers for the AI Data Readiness Auditor.

The provider layer decouples narrative generation from the rest of the app.
``TemplateProvider`` (Template Engine Mode) is the default and works fully
offline. ``LLMProvider`` (LLM Enhanced Mode) is architected for future use and
falls back to the template provider when no API key is configured.
"""

from .base_provider import BaseProvider
from .template_provider import TemplateProvider
from .llm_provider import LLMProvider

__all__ = ["BaseProvider", "TemplateProvider", "LLMProvider", "get_provider"]


def get_provider(mode: str, provider_name: str = ""):
    """Return the appropriate provider instance for the requested mode.

    Falls back to Template Engine Mode when LLM mode is unavailable.
    """
    from .. import config

    if mode == config.MODE_LLM and config.llm_mode_available():
        return LLMProvider(provider_name=provider_name)
    return TemplateProvider()
