"""Gaussian basis-set validation + normalisation.

Authoritative reference: https://gaussian.com/basissets/ (built-in basis sets).

Important spelling note (from the page): the def2 family keywords are written
**without a hyphen** -- ``Def2TZVP`` (not ``def2-TZVP``), and ``Def2SVPP``
corresponds to the chemistry name ``def2-SV(P)``. ``normalize_basis`` converts
common aliases to the canonical Gaussian keyword so the generated gjf is valid;
``validate_basis`` flags unrecognised input.

Rules are committed to GitHub so local and remote validation stay in sync.
"""
from __future__ import annotations

import re

# Canonical common basis sets (editor datalist), per gaussian.com/basissets.
COMMON_BASIS_SETS: list[str] = [
    # Pople
    "STO-3G", "3-21G", "3-21G*",
    "6-31G", "6-31G(d)", "6-31G(d,p)", "6-31G*", "6-31G**",
    "6-31+G(d)", "6-31+G(d,p)", "6-31+G(2d,p)",
    "6-311G", "6-311G(d)", "6-311G(d,p)", "6-311G**",
    "6-311+G(d,p)", "6-311+G(2d,2p)", "6-311+G(2df,2p)", "6-311+G(2df,2pd)",
    # Dunning correlation-consistent (hyphenated keywords)
    "cc-pVDZ", "cc-pVTZ", "cc-pVQZ", "cc-pV5Z",
    "cc-pCVDZ", "cc-pCVTZ", "cc-pCVQZ",
    "cc-pwCVDZ", "cc-pwCVTZ", "cc-pwCVQZ",
    "aug-cc-pVDZ", "aug-cc-pVTZ", "aug-cc-pVQZ", "aug-cc-pV5Z",
    # def2 (Gaussian keywords: NO hyphen; Def2SVPP == def2-SV(P))
    "Def2SV", "Def2SVP", "Def2SVPP",
    "Def2TZV", "Def2TZVP", "Def2TZVPP",
    "Def2QZV", "Def2QZVP", "Def2QZVPP",
    # old Ahlrichs
    "SV", "SVP", "TZV", "TZVP", "QZVP",
    # ECP / Stuttgart
    "SDD", "SDDAll", "LANL2DZ", "LANL2TZ",
    # other built-ins
    "DGDZVP", "DGDZVP2", "MidiX", "EPR-II", "EPR-III", "MTSmall", "CBSB7",
    # custom
    "gen",
]

# def2 alias -> canonical Gaussian keyword (case-insensitive lookup).
# Covers hyphenated forms and the def2-SV(P) chemistry name.
_DEF2_ALIASES: dict[str, str] = {
    "def2-sv(p)": "Def2SVPP",
    "def2-sv": "Def2SV", "def2-svp": "Def2SVP", "def2-svpp": "Def2SVPP",
    "def2-tzv": "Def2TZV", "def2-tzvp": "Def2TZVP", "def2-tzvpp": "Def2TZVPP",
    "def2-qzv": "Def2QZV", "def2-qzvp": "Def2QZVP", "def2-qzvpp": "Def2QZVPP",
    # canonical (no hyphen) also normalised to the canonical capitalisation
    "def2sv": "Def2SV", "def2svp": "Def2SVP", "def2svpp": "Def2SVPP",
    "def2tzv": "Def2TZV", "def2tzvp": "Def2TZVP", "def2tzvpp": "Def2TZVPP",
    "def2qzv": "Def2QZV", "def2qzvp": "Def2QZVP", "def2qzvpp": "Def2QZVPP",
}


def normalize_basis(basis: str) -> str:
    """Convert common aliases (e.g. def2-TZVP, def2-SV(P)) to the canonical
    Gaussian keyword (Def2TZVP, Def2SVPP). Other basis sets pass through
    (Gaussian keywords are case-insensitive)."""
    b = (basis or "").strip()
    canon = _DEF2_ALIASES.get(b.lower())
    return canon if canon else b


# Pople polarization modifier: *, **, or (...) like (d), (d,p), (2d,2p), (2df,2pd)
_POPLE_MOD = r"(?:\*{0,2}|\([2-3]?[dfps]+(?:,[2-3]?[dfps]+)*\))?"

_BASIS_RE = re.compile(
    r"""^\s*(?:
        # --- Pople ---
        (?:STO-3G|3-21G\*?|4-31G|6-31\+{0,2}G|6-311\+{0,2}G)""" + _POPLE_MOD + r"""
        # --- Dunning correlation-consistent (ma-/aug-/heavy-aug- prefixes) ---
        | (?:ma-|aug-|heavy-aug-)?cc-p(?:V|CV|wCV|AV)[DTQ56]Z
        # --- def2 (canonical keyword, NO hyphen) ---
        | (?:ma-)?Def2(?:SV|SVP|SVPP|TZV|TZVP|TZVPP|QZV|QZVP|QZVPP)
        # --- ECP / Stuttgart / Los Alamos ---
        | LANL2DZ|LANL2TZ|SDDAll|SDD
        # --- other built-ins ---
        | DGDZVP2|DGDZVP|EPR-III|EPR-II|MidiX|MTSmall|CBSB7
        | SVPFit|TZVPFit|SV|SVP|TZV|TZVP|QZVP
        # --- custom basis (gen / @external file) ---
        | gen|@[A-Za-z0-9_./-]+
      )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def is_valid_basis(basis: str) -> bool:
    """True if ``basis`` (after normalisation) is a recognised Gaussian basis."""
    return bool(basis and _BASIS_RE.match(normalize_basis(basis)))


def validate_basis(basis: str) -> tuple[bool, str]:
    """Return (ok, message). Aliases are accepted but flagged with the canonical
    form that will be written to the gjf."""
    b = (basis or "").strip()
    if not b:
        return False, "基组为空"
    n = normalize_basis(b)
    if _BASIS_RE.match(n):
        if n != b:
            return True, f"已识别:{b} → 生成 gjf 时自动写为 {n}"
        return True, "基组合法"
    return (
        False,
        f"未识别的基组「{b}」。参考 https://gaussian.com/basissets/ 的内置基组关键字"
        "(如 Def2TZVP、6-31G(d)、cc-pVTZ、SDD),或用 gen/@文件 自定义。",
    )
