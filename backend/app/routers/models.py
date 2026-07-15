"""AI provider/model + tool-path settings endpoints."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai.provider import ProviderConfig
from ..ai.router import get_provider
from ..chemistry.knowledge import (
    BASIS_CATALOG,
    COMMON_SOLVENTS,
    FUNCTIONAL_CATALOG,
    PLOT_PROCEDURES,
    TASK_CATALOG,
)
from ..settings_store import load, merge_provider_secret, public_view, save

router = APIRouter(tags=["models"])

PROVIDER_PRESETS = [
    {
        "kind": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini"],
        "default_model": "gpt-4o-mini",
    },
    {
        "kind": "anthropic",
        "name": "Anthropic Claude",
        "base_url": "",
        "models": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5"],
        "default_model": "claude-sonnet-4-6",
    },
    {
        "kind": "custom",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
    },
    {
        "kind": "custom",
        "name": "Volcengine Ark (豆包)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["doubao-pro-32k", "doubao-1-5-pro"],
        "default_model": "doubao-pro-32k",
    },
    {
        "kind": "custom",
        "name": "本地 vLLM / Ollama",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3", "qwen2.5"],
        "default_model": "llama3",
    },
]


class ProviderInput(BaseModel):
    id: str
    name: str = ""
    kind: Literal["openai", "anthropic", "custom", "mock"] = "openai"
    base_url: str = ""
    api_key: str = ""
    models: list[str] = []
    default_model: str = ""


class ActiveInput(BaseModel):
    active_provider_id: str
    active_model: str = ""


class PathsInput(BaseModel):
    gaussian_path: str | None = None
    multiwfn_path: str | None = None
    vmd_path: str | None = None


@router.get("/models/providers")
def get_providers() -> dict:
    return public_view()


@router.get("/models/catalog")
def get_catalog() -> dict:
    return {
        "presets": PROVIDER_PRESETS,
        "functionals": FUNCTIONAL_CATALOG,
        "bases": BASIS_CATALOG,
        "tasks": TASK_CATALOG,
        "solvents": COMMON_SOLVENTS,
        "plots": PLOT_PROCEDURES,
    }


@router.post("/models/providers")
def add_provider(p: ProviderInput) -> dict:
    s = load()
    providers = s.get("providers", [])
    if any(x.get("id") == p.id for x in providers):
        raise HTTPException(409, f"provider id '{p.id}' already exists")
    providers.append(p.model_dump())
    s["providers"] = providers
    return save(s) and public_view()


@router.put("/models/providers/{pid}")
def update_provider(pid: str, p: ProviderInput) -> dict:
    s = load()
    providers = s.get("providers", [])
    idx = next((i for i, x in enumerate(providers) if x.get("id") == pid), None)
    if idx is None:
        raise HTTPException(404, f"provider '{pid}' not found")
    merged = merge_provider_secret(providers, p.model_dump())
    merged["id"] = pid
    providers[idx] = merged
    s["providers"] = providers
    save(s)
    return public_view()


@router.delete("/models/providers/{pid}")
def delete_provider(pid: str) -> dict:
    s = load()
    providers = [x for x in s.get("providers", []) if x.get("id") != pid]
    s["providers"] = providers
    if s.get("active_provider_id") == pid:
        s["active_provider_id"] = "mock"
        s["active_model"] = ""
    save(s)
    return public_view()


@router.put("/models/active")
def set_active(a: ActiveInput) -> dict:
    s = load()
    s["active_provider_id"] = a.active_provider_id
    s["active_model"] = a.active_model
    save(s)
    return public_view()


@router.put("/models/paths")
def set_paths(p: PathsInput) -> dict:
    s = load()
    if p.gaussian_path is not None:
        s["gaussian_path"] = p.gaussian_path
    if p.multiwfn_path is not None:
        s["multiwfn_path"] = p.multiwfn_path
    if p.vmd_path is not None:
        s["vmd_path"] = p.vmd_path
    save(s)
    return public_view()


@router.post("/models/providers/{pid}/test")
async def test_provider(pid: str) -> dict:
    provider = get_provider(pid)
    if pid == "mock" or provider.config.kind == "mock":
        return {"ok": True, "message": "Mock provider 始终可用(无需密钥)。"}
    ok, message = await provider.test()
    return {"ok": ok, "message": message}
