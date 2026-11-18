"""Provider selection with graceful fallback.

Priority order, like Decepticon's _DEFAULT_AUTH_PRIORITY: try the primary
provider; if it isn't configured/reachable, drop to the fallback. Methods
that fail their availability check are skipped at runtime.
"""
from __future__ import annotations

from ..config import ProviderName, Settings, get_settings
from .base import LLMProvider
from .providers.anthropic import AnthropicProvider
from .providers.ollama import OllamaProvider

_REGISTRY: dict[ProviderName, type[LLMProvider]] = {
    ProviderName.ANTHROPIC: AnthropicProvider,
    ProviderName.OLLAMA: OllamaProvider,
}


def build_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()

    order: list[ProviderName] = [settings.provider]
    if settings.fallback_provider and settings.fallback_provider != settings.provider:
        order.append(settings.fallback_provider)

    tried: list[str] = []
    for name in order:
        provider = _REGISTRY[name](settings)
        tried.append(name.value)
        if provider.available():
            return provider

    raise RuntimeError(
        f"No usable LLM provider. Tried: {', '.join(tried)}. "
        "Set ANTHROPIC_API_KEY or run a local Ollama server."
    )
