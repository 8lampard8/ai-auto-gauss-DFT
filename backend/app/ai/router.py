"""Provider routing: resolve a provider id to a live Provider instance."""
from __future__ import annotations

from ..settings_store import load
from .provider import Provider, ProviderConfig
from .providers_anthropic import AnthropicProvider
from .providers_openai import OpenAIProvider
from .mock import MockProvider


def get_provider(provider_id: str | None = None) -> Provider:
    """Return a Provider for ``provider_id`` (or the active/mock default)."""
    settings = load()
    providers = {p["id"]: p for p in settings.get("providers", [])}
    pid = provider_id or settings.get("active_provider_id") or "mock"

    if pid == "mock" or pid not in providers:
        return MockProvider(ProviderConfig(id="mock", name="Mock", kind="mock"))

    cfg = ProviderConfig(**providers[pid])
    if cfg.kind in ("openai", "custom"):
        return OpenAIProvider(cfg)
    if cfg.kind == "anthropic":
        return AnthropicProvider(cfg)
    return MockProvider(cfg)


def active_model() -> str:
    return load().get("active_model", "") or ""
