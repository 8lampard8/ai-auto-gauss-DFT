"""Mock provider — demoable assistant without any API key.

Simulates a guided Gaussian calculation interview using keyword matching,
and can emit a sample gjf so the full UI is exercisable offline.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .provider import ChatMessage, Provider

_SAMPLE_GJF = """\
%chk=job.chk
%mem=10GB
%nprocshared=6
# opt freq b3lyp def2-svp em=gd3bj scrf=(pcm,solvent=water)

title

0 1
C                 -0.01264500    1.08593100    0.00800000
H                 -0.00884000    1.70419300   -0.88012200
H                 -0.00884000    1.70419300    0.89612200
H                 -0.87478800    0.40590100    0.00800000
H                  0.99587300    0.40590100    0.00800000

"""

_REPLIES = [
    # (keywords, reply)
    (
        {"优化", "opt", "频率", "freq"},
        "好的,几何优化 + 频率分析。对有机分子我推荐:\n"
        "• 泛函/基组:B3LYP-D3(BJ)/def2-SVP(预优化)→ def2-TZVP(最终)\n"
        "• 关键字:# opt freq\n"
        "• 色散校正:em=gd3bj\n\n"
        "下面是示例 gjf(可在右侧编辑器修改):\n\n```gjf\n" + _SAMPLE_GJF + "```",
    ),
    (
        {"过渡态", "ts", "transition"},
        "过渡态优化建议:\n"
        "• 关键字:# opt=(ts,calcfc,noeigentest) freq\n"
        "• 必须验证唯一虚频;若初猜难给可用 QST2/QST3。\n"
        "• 泛函可考虑 M06-2X 或 ωB97X-D/def2-TZVP。",
    ),
    (
        {"激发态", "tddft", "uv", "ecd"},
        "激发态 (TDDFT):小分子用 PBE0;含电荷转移用 CAM-B3LYP 或 ωB97X-D。\n"
        "关键字示例:# pbe1pbe/def2-TZVP td(nstates=20) scrf=(pcm,solvent=water)",
    ),
    (
        {"溶剂", "scrf", "smd", "solv"},
        "隐式溶剂:G16 默认即 PCM(IEFPCM),无需显式写。\n"
        "计算溶解自由能 ΔG_solv 用 SMD:scrf=(smd,solvent=water)。\n"
        "常用溶剂:water / ethanol / methanol / acetonitrile / acetone / "
        "dichloromethane / chloroform / toluene / thf / dmso 等。",
    ),
    (
        {"homolumo", "homo", "lumo", "轨道"},
        "HOMO/LUMO 作图:需先得到 .fchk。\n"
        "Multiwfn:载入 .fch → 主功能 0 → 选择 HOMO/LUMO → 导出 cube → VMD 可视化(等值面 ±0.05)。",
    ),
    (
        {"esp", "静电势", "electrostatic"},
        "ESP 着色范德华表面图:Multiwfn 载入 .fch → 主功能 5 → 定量分子表面分析,"
        "ESP 映射到 vdW 表面(BWR 配色)。详见 .A.13。",
    ),
    (
        {"igmh", "iri", "nci", "弱相互"},
        "弱相互作用(IGMH):Multiwfn 载入 .fch → 主功能 20 → 4(IGMH)→ 高质量网格 → "
        "导出 func1.cub/func2.cub → 与 IGMHfill.vmd 一起移入 VMD 目录 → "
        "VMD 控制台 source IGMHfill.vmd。",
    ),
]


class MockProvider(Provider):
    async def stream(
        self, messages: list[ChatMessage], model: str | None = None
    ) -> AsyncIterator[str]:
        last = next((m for m in reversed(messages) if m.role == "user"), None)
        text = (last.content if last else "").lower().replace(" ", "")
        reply = self._reply(text, any(m.role == "system" for m in messages))
        # stream word-by-word to mimic a real model
        for token in _tokenize(reply):
            yield token
            await asyncio.sleep(0.015)

    def _reply(self, text: str, has_system: bool) -> str:
        for keys, reply in _REPLIES:
            if any(k.lower() in text for k in keys):
                return reply
        # default interview
        return (
            "你好,我是 Gaussian 量化计算助手。请告诉我:\n"
            "1) 计算类型(结构优化 / 频率 / 过渡态 / 激发态 / 单点 …)\n"
            "2) 是否需要溶剂?溶剂名?\n"
            "3) 期望精度(快速预优化 / 标准 / 高精度)\n"
            "4) 电荷与多重度(如 0 1)\n\n"
            "当前为 Mock 演示模式(在「设置」中配置真实 AI 后即可获得完整智能回复)。"
            "你可以试试输入「优化+频率」「过渡态」「激发态」「溶剂」「IGMH」等关键词。"
        )


def _tokenize(s: str):
    """Yield tokens preserving whitespace/newlines for natural streaming."""
    buf = ""
    for ch in s:
        buf += ch
        if ch in " \n\t,。;；:：、()（）```" or buf.endswith("```"):
            yield buf
            buf = ""
    if buf:
        yield buf
