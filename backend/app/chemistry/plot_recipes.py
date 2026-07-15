"""Plot recipes: Multiwfn command sequences + VMD scripts, per analysis type.

Sequences verified against Multiwfn 3.8(dev). Cube export via main function 5:
``5 -> <func> -> 0 (nfiles) -> 2 (medium grid) -> 2 (export cube) -> 0 (return)``.

Placeholders substituted by the visualize router:
- ``{atoms}`` -> ``1-N`` (IGMH fragment atom range)
- ``{homo}``  -> N_occ   (HOMO orbital index)
- ``{lumo}``  -> N_occ+1 (LUMO orbital index)

Menu numbers can vary between Multiwfn versions - the frontend shows the
script as editable text before running.
"""
from __future__ import annotations


def _vmd_orbital(cube: str, tga: str, iso: float = 0.05) -> str:
    """Two isosurfaces (+/-iso) of an orbital cube, two colors."""
    return (
        f"mol new {cube}\n"
        "mol delrep 0 0\n"
        f"mol representation Isosurface {iso} 0 0 0 1\n"
        "mol color ColorID 0\n"
        "mol addrep 0\n"
        f"mol representation Isosurface {-iso} 0 0 0 1\n"
        "mol color ColorID 1\n"
        "mol addrep 0\n"
        "display resetview\n"
        "display projection Orthographic\n"
        f"render TachyonInternal {tga}\n"
        "quit\n"
    )


def _vmd_esp(density_cube: str, esp_cube: str, tga: str, iso: float = 0.001) -> str:
    """Density isosurface @ iso, colored by the ESP volume (BWR)."""
    return (
        f"mol new {density_cube}\n"
        f"mol addfile {esp_cube}\n"
        "mol delrep 0 0\n"
        f"mol representation Isosurface {iso} 0 0 0 1\n"
        "mol color Volume 1\n"
        "mol addrep 0\n"
        "color scale method BWR\n"
        "display resetview\n"
        "display projection Orthographic\n"
        f"render TachyonInternal {tga}\n"
        "quit\n"
    )


def _vmd_igm(color_cube: str, iso_cube: str, tga: str, iso: float = 0.5) -> str:
    """isosurface of iso_cube @ iso, colored by color_cube (BWR)."""
    return (
        f"mol new {color_cube}\n"
        f"mol new {iso_cube}\n"
        "mol delrep 0 0\n"
        f"mol representation Isosurface {iso} 1 0 0 1\n"
        "mol color Volume 0\n"
        "mol addrep 0\n"
        "color scale method BWR\n"
        "display resetview\n"
        "display projection Orthographic\n"
        f"render TachyonInternal {tga}\n"
        "quit\n"
    )


RECIPES: dict[str, dict] = {
    "homo": {
        "label": "HOMO 轨道",
        "needs": ["fchk"],
        # 5 -> 4 (orbital wavefunction) -> {homo} (HOMO index) -> 0 nfiles -> 2 grid -> 2 export -> 0 return
        "multiwfn_input": ["5", "4", "{homo}", "0", "2", "2", "0", "q"],
        "multiwfn_note": "主功能 5 -> 4(轨道波函数)-> {homo}(HOMO 轨道号,自动填)-> 2(网格)-> 2(导出 MOvalue.cub)。",
        "cubes": ["MOvalue.cub"],
        "iso": 0.05,
        "vmd_script": _vmd_orbital("MOvalue.cub", "homo.tga", 0.05),
        "instructions": "HOMO:导出 MOvalue.cub,VMD 等值面 ±0.05,正负叶双色。",
    },
    "lumo": {
        "label": "LUMO 轨道",
        "needs": ["fchk"],
        "multiwfn_input": ["5", "4", "{lumo}", "0", "2", "2", "0", "q"],
        "multiwfn_note": "主功能 5 -> 4(轨道波函数)-> {lumo}(LUMO 轨道号,自动填)-> 2(网格)-> 2(导出 MOvalue.cub)。",
        "cubes": ["MOvalue.cub"],
        "iso": 0.05,
        "vmd_script": _vmd_orbital("MOvalue.cub", "lumo.tga", 0.05),
        "instructions": "LUMO:同 HOMO,轨道号为 LUMO。",
    },
    "esp_vdw": {
        "label": "ESP 等值面图",
        "needs": ["fchk"],
        # 5 -> 12 (ESP) -> 0 nfiles -> 2 grid -> 2 export -> 0 return
        "multiwfn_input": ["5", "12", "0", "2", "2", "0", "q"],
        "multiwfn_note": "主功能 5 -> 12(总静电势 ESP)-> 2(网格)-> 2(导出 totesp.cub)。",
        "cubes": ["totesp.cub"],
        "iso": 0.05,
        "vmd_script": _vmd_orbital("totesp.cub", "esp.tga", 0.05),
        "instructions": (
            "ESP 等值面:±0.05 a.u.(正=蓝/电正,负=红/电负),显示亲核/亲电区域。"
            "注:VMD 不便把密度等值面按 ESP 着色(两 cube 会成不同帧),"
            "如需 vdW 表面着色图请在 Multiwfn GUI 里出图。"
        ),
    },
    "nci": {
        "label": "NCI (RDG)",
        "needs": ["fchk"],
        "multiwfn_input": ["20", "1", "2", "3", "0", "0", "q"],
        "multiwfn_note": "20(弱相互作用)-> 1(NCI)-> 2(中等网格)-> 3(导出 func1/func2.cub)。",
        "cubes": ["func1.cub", "func2.cub"],
        "iso": 0.5,
        "vmd_script": _vmd_igm("func2.cub", "func1.cub", "nci.tga"),
        "instructions": "NCI:func1=sign(λ2)ρ,func2=ρ;等值面 0.5,BWR。",
    },
    "iri": {
        "label": "IRI",
        "needs": ["fchk"],
        "multiwfn_input": ["20", "4", "2", "3", "0", "0", "q"],
        "multiwfn_note": "20 -> 4(IRI)-> 2(网格)-> 3(导出 cube)。",
        "cubes": ["func1.cub", "func2.cub"],
        "iso": 0.5,
        "vmd_script": _vmd_igm("func2.cub", "func1.cub", "iri.tga"),
        "instructions": "IRI:主功能 20 -> 4。",
    },
    "igm": {
        "label": "IGM",
        "needs": ["fchk"],
        "multiwfn_input": ["20", "10", "2", "3", "0", "0", "q"],
        "multiwfn_note": "20 -> 10(IGM)-> 2(网格)-> 3(导出 cube)。",
        "cubes": ["func1.cub", "func2.cub"],
        "iso": 0.5,
        "vmd_script": _vmd_igm("func2.cub", "func1.cub", "igm.tga"),
        "instructions": "IGM:主功能 20 -> 10。",
    },
    "igmh": {
        "label": "IGMH 弱相互作用",
        "needs": ["fchk"],
        "multiwfn_input": ["20", "11", "1", "{atoms}", "2", "3", "0", "0", "q"],
        "multiwfn_note": "20 -> 11(IGMH)-> 1 个片段 -> 原子范围 1-N(自动填)-> 2(网格)-> 3(导出 dg.cub/sl2r.cub)。",
        "cubes": ["dg.cub", "sl2r.cub"],
        "iso": 0.5,
        "vmd_script": _vmd_igm("sl2r.cub", "dg.cub", "igmh.tga"),
        "instructions": "IGMH:dg=δg,sl2r=sign(λ2)ρ;等值面 0.5,BWR。",
    },
}


def get_recipe(key: str) -> dict | None:
    return RECIPES.get(key)
