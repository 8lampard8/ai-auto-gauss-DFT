"""AI provider abstraction.

A Provider wraps a single model backend (OpenAI-compatible, Anthropic, or a
local Mock). All providers expose an async streaming ``stream()`` generator
that yields text deltas, plus a ``test()`` connectivity check.
"""
from __future__ import annotations

from typing import AsyncIterator, Literal

from pydantic import BaseModel, Field

MsgRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: MsgRole
    content: str = ""


ProviderKind = Literal["openai", "anthropic", "custom", "mock"]


class ProviderConfig(BaseModel):
    id: str
    name: str = ""
    kind: ProviderKind = "openai"
    base_url: str = ""
    api_key: str = ""
    models: list[str] = Field(default_factory=list)
    default_model: str = ""


class Provider:
    """Base provider. Subclasses implement ``stream``."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    async def stream(
        self, messages: list[ChatMessage], model: str | None = None
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        # make this an async generator for type checkers
        yield ""  # pragma: no cover

    async def test(self) -> tuple[bool, str]:
        """Run a tiny ping through the provider and report (ok, message)."""
        try:
            n = 0
            async for _ in self.stream(
                [ChatMessage(role="user", content="ping")],
                model=self.config.default_model or None,
            ):
                n += 1
                if n > 3:
                    break
            return True, "连接成功"
        except Exception as e:  # pragma: no cover - exercised via API
            return False, f"{type(e).__name__}: {e}"

    async def extract_json(self, system: str, user: str,
                           model: str | None = None) -> str:
        """Non-streaming JSON extraction (for molecule-name parsing).

        Returns the raw model output text (expected to be JSON). The base
        provider does not support this; subclasses override.
        """
        return ""
