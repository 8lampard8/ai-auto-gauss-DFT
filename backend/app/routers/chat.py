"""Streaming chat endpoint (Server-Sent Events).

Beyond plain chat, this endpoint auto-imports a molecule mentioned in the
conversation: it extracts a molecule name (LLM for real providers, heuristic
for the Mock), resolves it to SMILES via PubChem/CIR, builds the 3D model,
and emits a ``molecule`` SSE event so the frontend viewer updates — letting
the user model a structure directly from the dialog.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..ai.mock import MockProvider
from ..ai.prompts import EXTRACT_PROMPT, SYSTEM_PROMPT
from ..ai.provider import ChatMessage
from ..ai.router import active_model, get_provider
from ..chemistry.importer import from_smiles
from ..chemistry.name_resolver import heuristic_extract, resolve_smiles
from ..molecules_store import save as save_molecule
from ..schemas import ChatRequest

router = APIRouter(tags=["chat"])


def _evt(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _try_import(provider, model: str | None, last_user_text: str):
    """Extract a molecule mention, resolve to SMILES, build & persist it.

    Returns (molecule_or_None, error_note_or_empty).
    """
    if not last_user_text:
        return None, ""
    ext: dict = {}
    if isinstance(provider, MockProvider):
        ext = heuristic_extract(last_user_text)
    else:
        try:
            raw = await provider.extract_json(EXTRACT_PROMPT, last_user_text, model)
            ext = json.loads(raw) if raw else {}
            if not isinstance(ext, dict):
                ext = {}
        except Exception:
            ext = {}

    name = ext.get("name")
    if not name:
        return None, ""
    smiles = ext.get("smiles")
    is_smiles_input = name in ("smiles", "smiles_input")
    if not smiles:
        if is_smiles_input:
            return None, "(未能识别你提供的 SMILES)"
        smiles = resolve_smiles(name)
        if not smiles:
            return None, f"(未能检索到「{name}」的 SMILES,可在左侧手动导入)"
    display_name = "SMILES结构" if is_smiles_input else name
    try:
        mol = from_smiles(smiles, display_name)
        mol = save_molecule(mol)
        return mol, ""
    except Exception as e:
        return None, f"(建模失败:{e})"


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    provider = get_provider(req.provider_id)
    model = req.model or active_model() or None

    last_user = next(
        (m for m in reversed(req.messages) if m.role == "user"), None
    )
    last_user_text = last_user.content if last_user else ""

    mol, note = await _try_import(provider, model, last_user_text)

    sys_text = SYSTEM_PROMPT
    if mol:
        sys_text += (
            f"\n\n[系统]已从用户描述自动检索并建模分子:{mol.name}"
            f"(SMILES:{mol.smiles}),3D 视图已显示。请基于此分子继续回答。"
        )
    elif note:
        sys_text += f"\n[系统]{note}"

    msgs: list[ChatMessage] = [ChatMessage(role="system", content=sys_text)]
    for m in req.messages:
        if m.role in ("user", "assistant") and m.content:
            msgs.append(ChatMessage(role=m.role, content=m.content))

    async def gen():
        if mol:
            yield _evt({"type": "molecule", "molecule": mol.model_dump()})
            yield _evt({
                "type": "delta",
                "content": f"✓ 已从对话识别分子「{mol.name}」(SMILES:{mol.smiles})并完成建模,3D 视图已更新。\n\n",
            })
        elif note:
            yield _evt({"type": "delta", "content": note + "\n\n"})
        try:
            async for delta in provider.stream(msgs, model=model):
                yield _evt({"type": "delta", "content": delta})
            yield _evt({"type": "done"})
        except Exception as e:  # pragma: no cover - surfaced to the UI
            yield _evt({"type": "error", "message": f"{type(e).__name__}: {e}"})

    return StreamingResponse(gen(), media_type="text/event-stream")
