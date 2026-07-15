"""OpenAI-compatible provider.

A single implementation covers the OpenAI API itself plus any endpoint that
speaks the OpenAI Chat Completions protocol: DeepSeek, Volcengine/Doubao
(Ark), local vLLM / Ollama (openai-compatible mode), Together, etc. The
``base_url`` selects the backend; ``api_key`` authenticates.
"""
from __future__ import annotations

from typing import AsyncIterator

from .provider import ChatMessage, Provider


class OpenAIProvider(Provider):
    async def stream(
        self, messages: list[ChatMessage], model: str | None = None
    ) -> AsyncIterator[str]:
        from openai import AsyncOpenAI

        cfg = self.config
        client = AsyncOpenAI(
            base_url=cfg.base_url or None,
            api_key=cfg.api_key or "EMPTY",
            timeout=60.0,
        )
        mdl = (
            model
            or cfg.default_model
            or (cfg.models[0] if cfg.models else "gpt-4o-mini")
        )
        payload = [{"role": m.role, "content": m.content} for m in messages]
        stream = await client.chat.completions.create(
            model=mdl,
            messages=payload,
            stream=True,
            temperature=0.3,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield text

    async def extract_json(self, system: str, user: str,
                           model: str | None = None) -> str:
        from openai import AsyncOpenAI

        cfg = self.config
        client = AsyncOpenAI(
            base_url=cfg.base_url or None,
            api_key=cfg.api_key or "EMPTY",
            timeout=30.0,
        )
        mdl = (
            model
            or cfg.default_model
            or (cfg.models[0] if cfg.models else "gpt-4o-mini")
        )
        try:
            r = await client.chat.completions.create(
                model=mdl,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            return r.choices[0].message.content or ""
        except Exception:
            # Some OpenAI-compatible backends don't support response_format;
            # fall back to a plain completion.
            r = await client.chat.completions.create(
                model=mdl,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=300,
            )
            return r.choices[0].message.content or ""
