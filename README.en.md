# ai-auto-gauss-DFT

[简体中文](README.md) | **English**

An AI-conversation-driven web app for the full Gaussian quantum-chemistry workflow: **molecular modeling → generate gjf → submit jobs (local / SSH) → result plotting (Multiwfn / VMD)**. Switch freely between mainstream AI models and custom APIs from within the UI.

## Features

| Module | Capability |
|--------|-----------|
| **1 Molecular modeling** | **Conversational modeling**: say "optimize ethanol" in the chat and the AI identifies the molecule name → searches SMILES (PubChem/CIR) → builds the model, with the 3D view auto-updating. Also supports SMILES / mol / mol2 / gjf / out·log / cdxml / image import; 3Dmol.js 3D viewer; automatic charge & multiplicity inference. |
| **2D/3D Editor** | Ketcher 2D canvas + 3Dmol 3D view, **bi-directionally synced**; one-click insertion of functional groups (-OH / -NH₂ / -COOH / -CHO / -CN / -NO₂ / -OMe / -Ac / -Ph / -SH / -SO₃H / -N₂⁺ / halides); live sync, in-place updates (no duplicate molecules); iteratively modify complex molecules. |
| **2 Generate gjf** | Conversational querying of calculation needs; auto-recommends functional/basis-set/multiplicity/SCRF and generates a .gjf; rule-based recommender + AI dual track, editable. |
| **3 Submit jobs** | Local (WSL2 auto-invokes Windows G09W or Linux g16 via interop; auto-detects CPU/RAM to recommend `%nproc`/`%mem`; G09W auto-capped to 4 cores / 1.5GB) + SSH remote one-click submit (nohup + polling + fetch log/fchk); job ledger with **live in-run log**; on failure, auto-extracts a readable reason (memory / basis-function count / syntax / link0 crash, etc.). |
| **4 Result plotting** | HOMO/LUMO, ESP isosurfaces, NCI/IRI/IGM/IGMH; directory-sandboxed; drives Multiwfn + VMD (either can be the Windows build, via WSL interop) to render images. |
| **5 Model freedom** | OpenAI / Anthropic / any OpenAI-compatible (DeepSeek, Doubao/Ark, local vLLM/Ollama) / custom / Mock; add/edit/switch providers in the UI. |

## Architecture

```
ai-auto-gauss-DFT/
├── backend/                 Python 3.13 + FastAPI
│   └── app/
│       ├── main.py          FastAPI entry (CORS + static mount)
│       ├── config.py        paths & default settings
│       ├── schemas.py       Pydantic models
│       ├── settings_store.py settings persistence (0600, masked keys)
│       ├── molecules_store.py molecule JSON persistence
│       ├── jobs_store.py    SQLite job ledger
│       ├── security.py      path sandbox + key masking
│       ├── routers/         system / models / chat / molecules / gjf / jobs / visualize
│       ├── chemistry/       importer / name_resolver / gjf_writer / method_recommender / plot_recipes / knowledge
│       ├── ai/              provider abstraction / openai / anthropic / mock / router / prompts
│       └── exec/            local_runner / ssh_runner / multiwfn_runner / vmd_runner
├── frontend/                React + Vite + TypeScript + 3Dmol.js + zustand + Ketcher
│   └── src/{App.tsx, store.ts, types.ts, api/client.ts, components/}
├── data/                    uploads / job work dirs / plot outputs / app.db / settings.json
└── dev.sh                   one-command start: backend (:8000) + frontend (:5173)
```

## Quick start

```bash
cd ai-auto-gauss-DFT

# backend deps
python3 -m pip install -r backend/requirements.txt

# frontend deps
npm install --prefix frontend

# start both
./dev.sh
# open http://localhost:5173
```

> Without an API key or Gaussian/Multiwfn configured, the app runs in **Mock provider** mode and simulates the full flow. Set keys and paths in **Settings** to go live.

## Workflow

1. **Import a molecule**: say "optimize ethanol" in **Chat** — the AI auto-detects the name, searches SMILES (PubChem/CIR) and builds the model, shown in the 3D view. Or manually import via SMILES, name search, or drag in `.mol/.mol2/.gjf/.out/.cdxml/.png`.
2. **Generate gjf via chat**: describe your need (e.g. "opt + freq, water solvent"). With Mock, keywords trigger examples; with a real AI, it recommends a method and outputs a ```gjf block — click "load into editor".
3. **gjf editor**: pick task/solvent/accuracy → "Recommend method" → "Generate gjf" → edit manually → "Submit job".
4. **Submit jobs**: switch to the **Jobs** tab; local auto-fills nproc/mem, SSH picks a node; "one-click submit". Live polling; on completion download log/gjf; on local success, formchk auto-generates a .fchk.
5. **Plot results**: top-bar **Plot** → pick a plot type + a succeeded job with .fchk → (editable Multiwfn sequence & VMD script) → "Run plot"; the image is shown inline, logs expandable.

## 2D/3D Molecule Editor

Enter via the **Editor** item in the left nav — a two-column layout:
- **Left: Ketcher 2D canvas** — draw atoms/bonds/rings/charges/stereo; toolbar inserts **functional groups** in one click (-OH / -NH₂ / -COOH / -CHO / -CN / -NO₂ / -OMe / -Ac / -Ph / -SH / -SO₃H / -N₂⁺ / -F / -Cl / -Br / -I), then bond them to the main molecule.
- **Right: 3Dmol 3D view** — live 3D conformer of the current molecule.
- **Bi-directional sync**: switching molecules loads them into the canvas (3D→2D); "Sync to 3D" or the live-sync toggle updates the 3D from the canvas SMILES in place (2D→3D, same id — no duplicate molecules).
- Use case: incrementally add/remove groups or atoms on complex molecules (drugs, fullerenes…) with the 3D following live, then return to **Modeling** to generate gjf and submit.

> Ketcher (Indigo WASM) is heavy; it loads on demand (a few seconds) the first time you open **Editor** or the draw dialog.

## UI

Bright, clean, card-based design (light background, rounded cards, blue accent, left nav + top bar + card workspace). Nav: Modeling / Editor / Chat / Jobs / Plot / Settings. The chat panel has a persistent draggable scrollbar + a "↓ latest" button. Any render crash is caught by a top-level ErrorBoundary and shown as an error message (no white screen).

## Security

- `data/settings.json` is mode 0600; API keys / SSH passwords are **masked** in API responses and never logged.
- Plotting is allowed to write **only** inside the configured Multiwfn and VMD directories (path sandbox; rejects `..` and absolute-path escapes).
- The gjf is written to a file and run by `g16` — no shell string interpolation, so no injection.
- SSH prefers key files; credentials are not exposed.

## AI Provider config

**Settings** → pick a preset (OpenAI / Anthropic / DeepSeek / Doubao Ark / local vLLM) or fill manually:
- **Kind**: `openai` (OpenAI protocol) / `custom` (OpenAI-compatible custom base_url) / `anthropic` / `mock`
- **Base URL / API Key / model list / default model**
- "Test" verifies connectivity; "Set active" lets the top-bar dropdown switch models anytime.

## Key technical decisions

- **SCRF / solvation**: per gaussian.com/scrf and the sobko knowledge base — G16 defaults to PCM (IEFPCM), `scrf=(pcm,solvent=...)`; SMD for ΔG_solv; non-electrostatic terms need `read`+`Dis/Rep/Cav`. The recommender defaults to PCM for aqueous.
- **Method recommendation**: organic optimization B3LYP-D3(BJ)/def2-TZVP; transition states `opt=(ts,calcfc,noeigentest)`; excited states PBE0/CAM-B3LYP; heavy atoms get def2 ECPs automatically.
- **Plotting** (sobko manual, authority A): IGMH main 20→4 exports func1/func2.cub + `IGMHfill.vmd`; ESP via main 12 surface analysis; HOMO/LUMO via main 0 orbital cube. Menu numbers may differ slightly across Multiwfn versions — the frontend scripts are editable.

## Production deployment

```bash
npm run build --prefix frontend          # produces frontend/dist
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
# FastAPI auto-mounts dist at /; visit http://host:8000
```

## Roadmap

- [x] Phase 1 scaffold (FastAPI + Vite/React, health check, hardware probe)
- [x] Phase 2 AI provider abstraction + streaming chat + settings persistence
- [x] Phase 3 molecule import + 3Dmol viewer
- [x] Phase 4 gjf writer + method recommender + editor
- [x] Phase 5 job submission (local + SSH) + job ledger
- [x] Phase 6 result plotting (Multiwfn + VMD, sandboxed)
- [x] Phase 7 end-to-end run-through + docs
- [x] 2D/3D synced editor (Ketcher) + functional groups

## Future work

- SLURM/PBS queue integration (SSH currently uses nohup direct run)
- Batch / parametric scans, IRC auto-chaining
- Binary CDX, NMR/UV-Vis spectrum plotting

## License

MIT © 2026 8lampard8
