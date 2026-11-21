# ai-auto-gauss-DFT

[简体中文](README.md) | **English**

An AI-conversation-driven web platform for the full Gaussian quantum-chemistry and cheminformatics workflow: **molecular modeling → 2D/3D editing → `.gjf` generation → job submission (local / SSH) → molecular descriptor extraction (RDKit + DFT) → wavefunction plotting (Multiwfn / VMD)**. Includes a one-click **`中文 | EN`** UI switcher and hot-swappable AI providers.

---

## Features

| Module | Capabilities |
|--------|-------------|
| **1 Molecular Modeling** | **Conversational modeling**: say *"optimize ethanol"* in Chat and the AI resolves SMILES (PubChem / CIR) and builds the 3D conformer automatically. Also supports 2D drawing, SMILES, CAS numbers (with check-digit validation), CN/EN names, and drag-and-drop for `.mol / .sdf / .mol2 / .gjf / .out / .log / .cdxml / images`. Interactive 3Dmol.js viewer with automatic charge & multiplicity inference. |
| **2 2D/3D Editor** | Ketcher 2D canvas + 3Dmol 3D view with **bi-directional sync** and one-click functional group insertion (`-OH / -NH₂ / -COOH / -CHO / -CN / -NO₂ / -OMe / -Ac / -Ph / -SH / -SO₃H / -N₂⁺ / halides`); updates in place without duplicating molecules. |
| **3 `.gjf` Generator** | Dual-track rule recommender + AI assistant for functionals, basis sets, dispersion, and SCRF solvation; live Gaussian basis-set validation & canonicalization (`def2-TZVP → Def2TZVP`); one-click *"Load in Editor"* from AI chat code blocks. |
| **4 Job Submission** | **Local execution** (native Windows G09W/G16W, WSL2 interop, and Linux `g16`; auto-probes CPU/RAM for `%nproc`/`%mem`; automatic 32-bit G09W 4-core/1500MB capping and link0-crash retry) + **SSH remote submission** (`$HOME` expansion, `nohup` + polling + remote `formchk` + `.log`/`.fchk` retrieval); auto-parses summary badges (`E`, `Gap`, `μ`, `G`, `Nimag`) and actionable error diagnostics. |
| **5 Molecular Descriptors** | **RDKit 2D/3D descriptors** (basic, physicochemical/drug-likeness, topological indices, 3D shape Rg/PMI/NPR/PBF/vdW volume, plus all ~217 2D descriptors) + **Gaussian DFT quantum descriptors** (SCF energy, HOMO/LUMO/gap, conceptual DFT indices $I, A, \chi, \mu, \eta, S, \omega, \omega^-, \omega^+$, dipole, polarizability, thermochemistry ZPE/H/G/TS, imaginary frequencies, TD-DFT excited states, and Mulliken/APT/Hirshfeld/CM5/NPA atomic charge tables). Supports **direct `.log/.out` upload** and **batch QSAR/ML CSV/JSON export**. |
| **6 Result Plotting** | HOMO/LUMO, ESP isosurfaces, NCI / IRI / IGM / IGMH; reads exact atom/electron counts from `.fchk` headers; directory-sandboxed Multiwfn + VMD rendering. |
| **7 Bilingual & Model Freedom** | Top-bar **`中文 | EN`** toggle (persisted in `localStorage`, synced with AI chat language); supports OpenAI, Anthropic, DeepSeek, Doubao Ark, local vLLM/Ollama, any OpenAI-compatible API, and offline Mock mode. |

---

## Requirements

- **Python** ≥ 3.10 (3.11–3.13 recommended, with `rdkit`)
- **Node.js** ≥ 18 (20/22 LTS recommended)
- **Optional external tools** (modeling, descriptor extraction, `.gjf` generation, and Mock chat all work without them):
  - Gaussian (Linux `g16`/`g09`, or Windows `G09W`/`G16W`)
  - Multiwfn 3.8(dev) & VMD (only needed for wavefunction plotting)

---

## Quick Start

### Linux / macOS / WSL2

```bash
git clone https://github.com/8lampard8/ai-auto-gauss-DFT.git
cd ai-auto-gauss-DFT

# 1. Create virtualenv & install backend dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Install frontend dependencies
npm install --prefix frontend

# 3. Launch both backend (:8000) and frontend (:5173)
./dev.sh
```

Open **http://localhost:5173** in your browser.

### Windows (PowerShell)

```powershell
git clone https://github.com/8lampard8/ai-auto-gauss-DFT.git
cd ai-auto-gauss-DFT

# 1. Create virtualenv & install backend dependencies
python -m venv .venv
.\.venv\Scripts\pip.exe install -r backend\requirements.txt

# 2. Install frontend dependencies
npm install --prefix frontend

# 3. Terminal 1: Start backend (use --port 8001 if 8000 is occupied)
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 4. Terminal 2: Start frontend dev server
# (If backend runs on 8001, set $env:VITE_API_TARGET='http://127.0.0.1:8001' first)
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

### Single-Port Production Build

```bash
npm run build --prefix frontend            # outputs frontend/dist
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# FastAPI serves the built SPA directly at http://localhost:8000
```

> **Note**: Without an API key or Gaussian/Multiwfn configured, the app runs in **Mock mode** so you can explore the entire interface immediately.

---

## How to Use (Step-by-Step Workflow)

### 1. Switch Language & Configure AI / Tool Paths
- **Language Toggle**: Click **`中文 | EN`** in the top bar to switch the entire interface and descriptor labels instantaneously (saved in `localStorage`; AI chat replies follow the selected language).
- **AI Providers**: Open **⚙️ Settings**, pick a preset (OpenAI / Anthropic / DeepSeek / Doubao Ark / local vLLM·Ollama) or enter custom credentials, click **Test**, then **Set Active**.
- **External Paths**: Enter local paths for Gaussian (`g16` or `g09w.exe`), Multiwfn, and VMD at the bottom of **Settings**.

### 2. Import or Edit Molecules (🧪 Modeling / ✏️ Editor)
- **Chat-to-3D**: Ask in **💬 Chat** (e.g. *"optimize aspirin"* or paste a SMILES) to auto-resolve and build the 3D model.
- **Manual Import**: In **🧪 Modeling**, choose **Draw** (Ketcher), **SMILES**, **CAS** (e.g. `64-17-5`), **By Name** (including exact C60 fullerene geometry), or drag-and-drop `.mol / .sdf / .mol2 / .gjf / .out / .log / .cdxml / .png`.
- **Bi-directional 2D/3D Editing**: Open **✏️ Editor** to modify structures on the Ketcher 2D canvas, insert common functional groups in one click, and live-sync changes to the 3D viewer.

### 3. Generate `.gjf` & Submit Jobs (🧪 Modeling → 🧮 Jobs)
1. Pick Task Type (OPT / FREQ / OPT+FREQ / SP / TS / QST2 / TD-DFT / IRC / Scan / NMR), Solvent, and Accuracy in the `.gjf` Generator card.
2. Click **Recommend** → **Generate gjf** (or click **Load in Editor** on any ```gjf block generated in Chat), then edit freely if needed.
3. Click **Submit Job** and choose **Local** (auto-fills recommended `%nprocshared`/`%mem`) or **Remote SSH** (key or password auth, automatic `formchk` and log/fchk retrieval).
4. Monitor live logs, download `.gjf`/`.log`, and view parsed DFT summary badges (`E`, `Gap`, `μ`, `G`, `Nimag`) in **🧮 Jobs**.

### 4. Extract Molecular Descriptors & Batch Export (🧬 Descriptors)
Open **🧬 Descriptors** from the sidebar (or click **🧬 Descriptors** directly from any 3D molecule or job card):

- **Single Molecule / Job**:
  - Pick a **saved molecule** → **Extract 2D/3D** for RDKit basic, physicochemical/drug-likeness, topological, and 3D shape descriptors.
  - Pick a **job with log** → **Extract DFT + 2D/3D** for combined quantum-chemical and optimized-geometry structural descriptors.
  - **Upload / Drop `.log` / `.out`** directly to parse any external Gaussian output file on the fly (including color-coded Mulliken/APT/Hirshfeld/CM5/NPA atomic charge tables and TD-DFT excited states).
  - Toggle **Include all RDKit 2D (~217)** for the full RDKit descriptor set, search/filter live, click any row to copy, or export **CSV / JSON**.
- **Batch Extract & Export (QSAR / ML)**:
  - Switch to the **Batch Extract & Export (QSAR/ML)** tab.
  - Select any mix of saved molecules, jobs with logs, and pasted SMILES lines (`CCO,ethanol`, `c1ccccc1,benzene`, `ethanol CCO`, etc.).
  - Preview the unified feature matrix or download directly as **CSV (UTF-8 BOM for Excel / pandas / scikit-learn)** or **JSON**.

#### Descriptor REST API Examples
```bash
# Single molecule RDKit descriptors (full=true includes all ~217 2D descriptors)
curl "http://127.0.0.1:8000/api/descriptors/molecule/<molecule_id>?full=true"

# Completed job DFT + RDKit descriptors
curl "http://127.0.0.1:8000/api/descriptors/job/<job_id>"

# Batch extract & download CSV
curl -X POST http://127.0.0.1:8000/api/descriptors/export \
  -H "Content-Type: application/json" \
  -d '{"smiles_list":["CCO,ethanol","c1ccccc1,benzene"],"include_all_rdkit":false,"format":"csv"}' \
  -o descriptors.csv
```

### 5. Wavefunction Plotting (📊 Plot)
Open **📊 Plot** → select a recipe (HOMO / LUMO / ESP / NCI / IRI / IGM / IGMH) and a succeeded job with `.fchk` → customize Multiwfn / VMD scripts if desired → click **Run Plot** to render and inspect images and logs inline.

---

## Architecture

```text
ai-auto-gauss-DFT/
├── backend/                     Python 3.13 + FastAPI
│   ├── app/
│   │   ├── main.py              FastAPI entry (CORS + startup orphan-job recovery + SPA mount)
│   │   ├── config.py            Paths & default settings
│   │   ├── schemas.py           Pydantic models
│   │   ├── settings_store.py    Settings persistence (0600, masked secrets)
│   │   ├── molecules_store.py   Atomic molecule JSON store (path-traversal safe)
│   │   ├── jobs_store.py        Thread-safe SQLite WAL job ledger
│   │   ├── security.py          Directory sandbox + secret masking
│   │   ├── routers/             system / models / chat / molecules / descriptors / gjf / jobs / visualize
│   │   ├── chemistry/           importer / name_resolver / descriptors / gaussian_parser / gjf_writer / method_recommender / basis_sets / plot_recipes / knowledge
│   │   ├── ai/                  provider / openai / anthropic / mock / router / prompts / web_search
│   │   └── exec/                local_runner / ssh_runner / multiwfn_runner / vmd_runner / wsl
│   └── tests/                   pytest unit & API integration tests
├── frontend/                    React + Vite + TypeScript + 3Dmol.js + Zustand + Ketcher
│   └── src/
│       ├── i18n.ts              CN/EN bilingual dictionary (UI + descriptor labels/hints)
│       ├── store.ts             Zustand state store
│       ├── types.ts             TypeScript interfaces
│       ├── api/client.ts        REST / SSE / blob download client
│       └── components/          Modeling / MoleculeEditor / Chat / Jobs / Descriptors / Plot / Settings
├── data/                        Uploads / job dirs / plots / app.db / settings.json (gitignored)
└── dev.sh                       Linux/macOS/WSL2 one-command launcher
```

---

## Running Tests

```bash
cd backend
python -m pytest -v
```

```bash
cd frontend
npx tsc --noEmit && npm run build
```

---

## Security

- `data/settings.json` is mode `0600` (gitignored); API keys and SSH passwords are **masked** in API responses and never logged.
- Plotting and job cleanup enforce strict directory sandboxes (rejecting `..` and out-of-root paths).
- Local Gaussian invocations avoid shell string concatenation and SSH remote commands are quoted via `shlex.quote`.

---

## Roadmap

- [x] Core workflow: AI chat, molecular modeling, `.gjf` generation, local/SSH submission, Multiwfn/VMD plotting
- [x] 2D/3D bi-directionally synced editor (Ketcher + functional group shortcuts) & CAS import
- [x] Molecular descriptor extraction (RDKit 2D/3D + Gaussian DFT parser + batch QSAR/ML CSV/JSON export)
- [x] Bilingual **`中文 | EN`** UI switcher & unified Windows / WSL2 / Linux runner support
- [ ] SLURM / PBS queue integration
- [ ] Parametric scans, IRC auto-chaining, and NMR / UV-Vis spectrum plotting

## License

MIT © 2026 8lampard8
