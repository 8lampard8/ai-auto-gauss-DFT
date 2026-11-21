"""Streaming chat endpoint (Server-Sent Events).

Beyond plain chat, this endpoint:
- auto-imports a molecule mentioned in the conversation (LLM / heuristic ->
  PubChem/CIR -> RDKit 3D model -> ``molecule`` SSE event)
- grounds the system prompt with the active molecule's RDKit descriptors and
  optional job quantum summary from ``req.context``
- runs blocking network/RDKit calls off the asyncio event loop
"""
from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..ai.mock import MockProvider
from ..ai.prompts import EXTRACT_PROMPT, SYSTEM_PROMPT
from ..ai.provider import ChatMessage
from ..ai.router import active_model, get_provider
from ..ai.web_search import format_search_context, search_web
from ..chemistry.descriptors import brief_summary
from ..chemistry.importer import from_smiles
from ..chemistry.name_resolver import heuristic_extract, resolve_smiles
from ..jobs_store import get as get_job
from ..molecules_store import load as load_molecule, save as save_molecule
from ..schemas import ChatRequest

router = APIRouter(tags=["chat"])


def _evt(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _parse_json_lenient(raw: str) -> dict:
    """Parse JSON even if wrapped in ```json ... ``` fences."""
    s = (raw or "").strip()
    if not s:
        return {}
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                pass
    return {}


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
            ext = _parse_json_lenient(raw)
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
        smiles = await asyncio.to_thread(resolve_smiles, name)
        if not smiles:
            return None, f"(未能检索到「{name}」的 SMILES,可在左侧手动导入)"
    display_name = "SMILES结构" if is_smiles_input else name
    try:
        mol = await asyncio.to_thread(from_smiles, smiles, display_name)
        mol = save_molecule(mol)
        return mol, ""
    except Exception as e:
        return None, f"(建模失败:{e})"


def _context_block(mol, context: dict) -> str:
    """Build a concise molecule + job descriptor block for the system prompt."""
    lines: list[str] = []
    active_mol = mol
    if active_mol is None and context.get("molecule_id"):
        try:
            active_mol = load_molecule(str(context["molecule_id"]))
        except Exception:
            active_mol = None

    if active_mol is not None:
        desc = brief_summary(active_mol)
        lines.append(
            f"[当前分子] 名称: {active_mol.name}; SMILES: {active_mol.smiles or '无'}; "
            f"电荷/多重度: {active_mol.charge} {active_mol.multiplicity}; "
            f"原子数: {len(active_mol.atoms)}"
            + (f"; 描述符: {desc}" if desc else "")
        )

    job_id = context.get("job_id")
    if job_id:
        j = get_job(str(job_id))
        if j:
            summary = j.get("summary") or {}
            lines.append(
                f"[当前任务] {j.get('id')} ({j.get('status')}) "
                f"{j.get('molecule_name')} · {j.get('spec_label')}"
                + (f"; DFT 摘要: {json.dumps(summary, ensure_ascii=False)}" if summary else "")
            )
    return "\n".join(lines)


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    provider = get_provider(req.provider_id)
    model = req.model or active_model() or None

    last_user = next(
        (m for m in reversed(req.messages) if m.role == "user"), None
    )
    last_user_text = last_user.content if last_user else ""

    mol, note = await _try_import(provider, model, last_user_text)

    # Web search augmentation (offload sync HTTP to worker thread)
    search_results: list[dict] = []
    search_query = ""
    if req.web_search and last_user_text:
        search_query = last_user_text[:120]
        search_results = await asyncio.to_thread(search_web, search_query)

    sys_text = SYSTEM_PROMPT
    if mol:
        sys_text += (
            f"\n\n[系统]已从用户描述自动检索并建模分子:{mol.name}"
            f"(SMILES:{mol.smiles}),3D 视图已显示。请基于此分子继续回答。"
        )
    elif note:
        sys_text += f"\n[系统]{note}"

    ctx_text = await asyncio.to_thread(_context_block, mol, req.context or {})
    if ctx_text:
        sys_text += "\n\n" + ctx_text

    if search_results:
        sys_text += "\n\n" + format_search_context(search_query, search_results)

    if (req.context or {}).get("lang") == "en":
        sys_text += "\n\n[Language] The user interface is set to English. Please reply concisely in English."

    msgs: list[ChatMessage] = [ChatMessage(role="system", content=sys_text)]
    for m in req.messages:
        if m.role in ("user", "assistant") and m.content:
            msgs.append(ChatMessage(role=m.role, content=m.content))

    async def gen():
        if search_results:
            yield _evt({
                "type": "search",
                "query": search_query,
                "count": len(search_results),
                "results": [{"title": r["title"], "url": r["url"]} for r in search_results],
            })
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
