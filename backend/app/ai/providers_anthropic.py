"""Anthropic Claude provider (Messages API, streaming)."""
from __future__ import annotations

from typing import AsyncIterator

from .provider import ChatMessage, Provider


class AnthropicProvider(Provider):
    async def stream(
        self, messages: list[ChatMessage], model: str | None = None
    ) -> AsyncIterator[str]:
        from anthropic import AsyncAnthropic

        cfg = self.config
        client = AsyncAnthropic(
            api_key=cfg.api_key or None,
            base_url=cfg.base_url or None,
            timeout=60.0,
        )
        mdl = (
            model
            or cfg.default_model
            or (cfg.models[0] if cfg.models else "claude-sonnet-4-6")
        )
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        convo = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        # Anthropic requires the conversation to begin with a user turn.
        if not convo or convo[0]["role"] != "user":
            convo = [{"role": "user", "content": "(开始)"}] + convo

        async with client.messages.stream(
            model=mdl,
            system=system,
            messages=convo,
            max_tokens=4096,
            temperature=0.3,
        ) as s:
            async for text in s.text_stream:
                yield text

    async def extract_json(self, system: str, user: str,
                           model: str | None = None) -> str:
        from anthropic import AsyncAnthropic

        cfg = self.config
        client = AsyncAnthropic(
            api_key=cfg.api_key or None,
            base_url=cfg.base_url or None,
            timeout=30.0,
        )
        mdl = (
            model
            or cfg.default_model
            or (cfg.models[0] if cfg.models else "claude-sonnet-4-6")
        )
        r = await client.messages.create(
            model=mdl,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=300,
            temperature=0.0,
        )
        return r.content[0].text if r.content else ""
