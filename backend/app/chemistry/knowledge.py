"""Curated chemistry knowledge base.

Grounding text for the LLM, distilled from the Gaussian SCRF documentation
(https://gaussian.com/scrf/) and the sobko knowledge base (Multiwfn manual
+ sobereva posts, authority A/B). Also exposes structured catalogs used by
the method recommender (Phase 4) and the frontend model/path pickers.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# SCRF / implicit solvation (from gaussian.com/scrf + sobereva 327/331)
# ---------------------------------------------------------------------------
SCRF_NOTES = """\
隐式溶剂模型 (SCRF):
- G16 默认即 PCM(IEFPCM 第二版,连续表面电荷形式)。因此写 scrf=pcm / iefpcm 是多余的,直接用默认即可。
- SMD(Truhlar)是计算溶解自由能 ΔG_solv 的推荐模型:scrf=(smd,solvent=water)。
- 默认 PCM 不计算非极性部分。若需纳入,用 scrf=(pcm,read),并在分子坐标末尾空一行后写:
    Dis
    Rep
    Cav
  分别对应色散、排斥、空穴项。
- 其它模型 IPCM / SCIPCM / Onsager(球形腔)极少使用,除非有特殊理由。
- 溶剂通过 solvent=<name> 指定,如 solvent=water、solvent=ethanol。
"""

COMMON_SOLVENTS = [
    "water", "ethanol", "methanol", "acetonitrile", "acetone",
    "dichloromethane", "chloroform", "toluene", "benzene", "hexane",
    "thf", "dmf", "dmso", "diethylether", "carbontetrachloride",
    "carbondisulfide", "n-heptane", "cyclohexane", "ammonia", "argon",
]

# ---------------------------------------------------------------------------
# Method recommendation heuristics (functional / basis / keywords per task)
# ---------------------------------------------------------------------------
METHOD_NOTES = """\
方法推荐经验(有机/主族体系为主):
- 几何优化+频率(常规): B3LYP-D3(BJ) / def2-SVP(预优化) → def2-TZVP(最终)。
  def2 系列对重原子(Rb 起)自动使用 ECP,无需额外指定。
- 含明显电荷转移 / Rydberg / 长程激发: 使用范围分离泛函 ωB97X-D。
- 反应能垒 / 动力学: M06-2X 或 ωB97X-D,基组 def2-TZVP。
- 高精度单点: 双杂化 B2PLYP-D3(BJ) / def2-TZVPP;热化学可用复合方法 CBS-QB3。
- 激发态 (TDDFT): 小分子用 PBE0;含电荷转移用 CAM-B3LYP 或 ωB97X-D。
- 过渡态优化: opt=(ts,calcfc,noeigentest) 并配合 freq 验证唯一虚频;
  若初猜难给,用 QST2/QST3(opt=qst2 / opt=qst3,需提供反应物与产物结构)。
- 频率分析: 始终带 freq;优化+频率可合并写 # opt freq。
- 多重度: 闭壳单重态=1,自由基双重态=2,三重态=3。由总自旋 S 决定 (mult=2S+1)。
- 资源: %mem 控制内存,%nprocshared 控制核数,%chk 指定检查点文件。
- 强烈建议优化后做频率分析确认势能面驻点性质(极小值无虚频,过渡态唯一虚频)。
"""

FUNCTIONAL_CATALOG = [
    "B3LYP-D3(BJ)", "ωB97X-D", "M06-2X", "PBE0", "CAM-B3LYP",
    "B2PLYP-D3(BJ)", "B3LYP", "PBE0-D3(BJ)", "M11", "MN15",
]

BASIS_CATALOG = [
    "Def2SVP", "Def2TZVP", "Def2TZVPP", "Def2QZVPP",
    "6-31G(d)", "6-31G(d,p)", "6-311G(d,p)", "6-311+G(2d,p)",
    "cc-pVTZ", "aug-cc-pVTZ", "SDD",
]

TASK_CATALOG = [
    {"id": "opt", "label": "结构优化 (OPT)"},
    {"id": "freq", "label": "频率分析 (FREQ)"},
    {"id": "optfreq", "label": "优化+频率 (OPT FREQ)"},
    {"id": "sp", "label": "单点能 (SP)"},
    {"id": "ts", "label": "过渡态优化 (opt=ts)"},
    {"id": "qst2", "label": "QST2/QST3 过渡态"},
    {"id": "tddft", "label": "激发态 (TDDFT)"},
    {"id": "irc", "label": "内禀反应坐标 (IRC)"},
    {"id": "scan", "label": "势能面扫描 (scan)"},
    {"id": "nmr", "label": "NMR"},
]

# ---------------------------------------------------------------------------
# Plotting procedures (Multiwfn + VMD) — from sobko manual, authority A.
# Consumed by Phase 6 plot_recipes; included here so the LLM can describe them.
# ---------------------------------------------------------------------------
PLOT_PROCEDURES = {
    "homo_lumo": {
        "label": "HOMO / LUMO 轨道",
        "needs": ["fchk"],
        "multiwfn": "载入 .fch → 主功能 0(查看分子轨道)→ 导出指定轨道 cube → VMD 可视化。",
        "vmd": "载入轨道 cube,等值面 ±0.05 a.u.,HOMO/LUMO 双色。",
    },
    "esp_vdw": {
        "label": "ESP 着色范德华表面图",
        "needs": ["fchk"],
        "multiwfn": "载入 .fch → 主功能 5(ESP)→ 定量分子表面分析,映射 ESP 到 vdW 表面(BWR 配色)。",
        "vmd": "导出表面 cube,在 VMD 中按 ESP 着色;或直接用 Multiwfn 自带 .A.13 流程出图。",
    },
    "igmh": {
        "label": "IGMH 弱相互作用",
        "needs": ["fchk"],
        "multiwfn": "载入 .fch → 主功能 20(弱相互作用可视化)→ 4(IGMH)→ 高质量网格 → 导出 func1.cub / func2.cub。",
        "vmd": "将 .cub 与 examples/IGMHfill.vmd 移入 VMD 目录,在 VMD 控制台 source IGMHfill.vmd。",
    },
    "iri": {
        "label": "IRI",
        "needs": ["fchk"],
        "multiwfn": "载入 .fch → 主功能 20 → 3(IRI)→ 导出 cube → 配合 IRIfill.vmd。",
        "vmd": "source IRIfill.vmd。",
    },
    "nci": {
        "label": "NCI",
        "needs": ["fchk"],
        "multiwfn": "载入 .fch → 主功能 20 → 1(NCI)→ 导出 cube → 配合 NCIfill.vmd。",
        "vmd": "source NCIfill.vmd。",
    },
}
