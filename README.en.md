# ai-auto-gauss-DFT

[简体中文](README.md) | **English**

An AI-assisted web workbench for Gaussian quantum-chemistry workflows, connecting **molecule import and modeling → method setup → `.gjf` generation → local/SSH execution → job and log management → Multiwfn/VMD post-processing** in one interface.

The project is not intended to replace Gaussian, Multiwfn, or VMD. Its purpose is to organize the otherwise fragmented steps of structure preparation, input generation, job execution, and wavefunction visualization into an interactive and traceable workflow, with optional OpenAI, Anthropic, and OpenAI-compatible models for chemistry-aware parsing and assistance.

> Current version: `0.1.0`. This is an early-stage project. Before using generated inputs for production calculations, manually verify the charge, multiplicity, electronic-structure method, basis set, solvation model, and Gaussian route section.

## Core capabilities

### 1. Molecule import and 3D modeling

Multiple structure sources are normalized into the internal `Molecule` model:

- **SMILES**: parsed with RDKit, embedded in 3D with ETKDG, then refined with MMFF when possible.
- **Chinese or English names**: resolved first against a small built-in dictionary, then through PubChem PUG-REST and the NCI Chemical Identifier Resolver (CIR).
- **CAS Registry Numbers**: format and check-digit validation followed by PubChem structure resolution.
- **Files**: `.mol` / `.sdf` / `.mol2` / `.gjf` / `.out` / `.log` / `.cdxml`.
- **Structure images**: OSRA is used when available; otherwise a configured OpenAI-compatible vision model can be asked to recover a SMILES string.
- **Gaussian outputs**: the final `Standard orientation` is parsed together with detectable charge, multiplicity, and route information.

The frontend renders structures with 3Dmol.js. Molecules are persisted as JSON under `data/uploads/`.

### 2. Synchronized Ketcher 2D / 3D editing

The built-in Ketcher editor is connected to the current 3D structure:

- load the current molecule's SMILES into Ketcher;
- export an edited SMILES and regenerate a 3D conformer with RDKit;
- update the molecule in place while preserving its molecule ID;
- insert common fragments such as `-OH`, `-NH₂`, `-COOH`, `-CHO`, `-CN`, `-NO₂`, `-OMe`, `-Ph`, and halogens;
- lazy-load Ketcher/Indigo only when the editor is opened.

### 3. AI chat and molecule recognition

The chat API streams responses through Server-Sent Events (SSE). With a real AI provider, the backend can first extract a molecule name or SMILES from the latest user message, resolve it, construct the 3D molecule, and persist it before continuing the conversation.

Supported provider kinds are:

- `openai`
- `anthropic`
- `custom` for any OpenAI-compatible endpoint, including DeepSeek, Volcengine Ark, local vLLM/Ollama, and similar services
- `mock` for testing the UI and chat path without an API key

Optional DuckDuckGo search augmentation can add search snippets to the model context.

> **The Mock provider only mocks AI chat. It does not emulate actual Gaussian, Multiwfn, or VMD calculations.**

### 4. Gaussian method recommendation and `.gjf` generation

A standalone rule-based recommender is available even without an LLM. It maps task type, solvent, accuracy tier, charge, and multiplicity to a basic `MethodSpec`.

Currently exposed task types include:

- OPT
- FREQ
- OPT + FREQ
- single-point energy
- TS
- QST2
- IRC
- relaxed scan
- NMR
- TDDFT

The current rules cover commonly used combinations such as B3LYP-D3(BJ), B2PLYP-D3(BJ), PBE0, and CAM-B3LYP, together with PCM solvent keywords where requested.

The basis-set module validates common Gaussian built-in basis sets and normalizes aliases. For example:

```text
def2-TZVP  ->  Def2TZVP
```

The `.gjf` writer assembles:

```text
%chk
%mem
%nprocshared
# route section

title

charge multiplicity
Cartesian coordinates
```

The generated input remains editable in the browser before submission.

### 5. Local Gaussian execution

The local runner supports two primary execution modes.

#### Linux Gaussian

When a Linux Gaussian executable such as `g16` is configured, the backend launches it directly through `subprocess`. After a successful run, it makes a best-effort attempt to call `formchk` from the same installation directory and generate `job.fchk`.

#### Windows G09W through WSL2

When the backend runs under WSL2 and a Windows Gaussian path is configured, the runner can:

1. translate the Windows path to `/mnt/<drive>/...`;
2. replace the GUI launcher `g09w.exe` with command-line `g09.exe`;
3. execute Gaussian through Windows `cmd.exe` and WSL interop;
4. cap 32-bit G09W resources at approximately `1500MB` and `4` cores;
5. retry a characteristic early link0 crash once with `600MB / 1 core`;
6. run `formchk.exe` after a successful calculation when possible and copy the resulting `.fch/.fchk` back into the job directory.

For normal local execution, the resource recommender reserves two physical CPU cores and limits `%mem` to roughly 70% of total RAM.

### 6. SSH remote execution

The SSH runner uses Paramiko and implements a lightweight direct-execution workflow:

```text
connect -> mkdir scratch -> upload job.gjf
        -> nohup g16 job.gjf > job.log 2>&1 &
        -> record PID -> poll kill -0
        -> download job.log / job.fchk(if present)
```

SSH key files, passwords, and local agent/key discovery are supported.

The current SSH backend uses **nohup + PID polling** rather than a scheduler such as SLURM or PBS. If a remote `.fchk` is required, the remote environment must generate it itself; the current SSH runner does not automatically invoke remote `formchk`.

### 7. Job ledger and failure diagnostics

Job state is persisted in SQLite:

```text
data/app.db
```

Each record stores execution status, local/remote mode, resource settings, input and log paths, result paths, and related metadata.

For failed local Gaussian runs, the backend attempts to classify several common failure patterns, including:

- insufficient memory;
- excessive basis-function size;
- Gaussian input syntax errors;
- missing or failed Gaussian link executables;
- early G09W link0 crashes;
- `Error termination via Lnk...` failures.

### 8. Multiwfn / VMD post-processing

Built-in analysis recipes currently include:

- HOMO
- LUMO
- ESP cube / isosurface
- NCI
- IRI
- IGM
- IGMH

The general pipeline is:

```text
successful Gaussian job
        ↓
      .fchk
        ↓
 Multiwfn scripted input
        ↓
     cube files
        ↓
  VMD scripted render
        ↓
      image
```

Multiwfn menu numbering can vary between releases, so both the command sequence and the VMD Tcl script remain editable before execution. The current recipes were written primarily against Multiwfn 3.8(dev).

## Architecture

```text
ai-auto-gauss-DFT/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 FastAPI entry point, CORS, production static mount
│       ├── config.py               data paths and default settings
│       ├── schemas.py              Pydantic data models
│       ├── settings_store.py       provider / tool-path / SSH persistence
│       ├── molecules_store.py      molecule JSON persistence
│       ├── jobs_store.py           SQLite job ledger
│       ├── security.py             secret masking and path sandboxing
│       ├── routers/
│       │   ├── system.py           health and hardware probing
│       │   ├── models.py           AI providers and external-tool paths
│       │   ├── chat.py             SSE chat, molecule extraction, search augmentation
│       │   ├── molecules.py        import / update / delete molecules
│       │   ├── gjf.py              method recommendation, basis validation, gjf generation
│       │   ├── jobs.py             local / SSH job APIs
│       │   └── visualize.py        Multiwfn / VMD analysis APIs
│       ├── chemistry/
│       │   ├── importer.py         multi-format parsing and 3D construction
│       │   ├── name_resolver.py    PubChem / CIR / CAS resolution
│       │   ├── basis_sets.py       Gaussian basis validation and normalization
│       │   ├── method_recommender.py
│       │   ├── gjf_writer.py
│       │   ├── knowledge.py
│       │   └── plot_recipes.py
│       ├── ai/
│       │   ├── provider.py         provider abstraction
│       │   ├── providers_openai.py
│       │   ├── providers_anthropic.py
│       │   ├── mock.py
│       │   ├── router.py
│       │   ├── prompts.py
│       │   └── web_search.py
│       └── exec/
│           ├── local_runner.py     Linux Gaussian / WSL2 + G09W
│           ├── ssh_runner.py       Paramiko SSH execution
│           ├── multiwfn_runner.py
│           ├── vmd_runner.py
│           └── wsl.py
├── frontend/
│   ├── package.json                React 18 + Vite + TypeScript
│   └── src/
│       ├── App.tsx
│       ├── store.ts                Zustand state management
│       ├── api/client.ts
│       └── components/             modeling, Ketcher, Chat, Jobs, Plot, Settings
├── data/
│   ├── uploads/                    persisted Molecule JSON
│   ├── jobs/                       local job work directories
│   ├── plots/                      application-side plot directory
│   ├── app.db                      SQLite job database
│   └── settings.json               local configuration and credentials
└── dev.sh                          starts FastAPI and Vite for development
```

## Quick start

### Requirements

The base web application requires at least:

- Python **3.10+**
- Node.js / npm
- Linux, macOS, or Windows with WSL2

Install additional software only for the features you need:

- Gaussian 16 / Gaussian 09
- Multiwfn
- VMD
- OSRA for local image-to-structure recognition (optional)

Gaussian, Multiwfn, and VMD are independent third-party applications. This repository does not distribute those programs or their licenses.

### 1. Clone the repository

```bash
git clone https://github.com/8lampard8/ai-auto-gauss-DFT.git
cd ai-auto-gauss-DFT
```

### 2. Install backend dependencies

```bash
python3 -m pip install -r backend/requirements.txt
```

Major Python dependencies include FastAPI, Pydantic, RDKit, Paramiko, the OpenAI SDK, the Anthropic SDK, httpx, and psutil.

### 3. Install frontend dependencies

```bash
npm install --prefix frontend
```

### 4. Start the development environment

```bash
chmod +x dev.sh
./dev.sh
```

Development endpoints:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API docs: http://localhost:8000/docs
```

Vite proxies `/api` requests to FastAPI on port `8000`.

## Recommended workflow

### Step 1 — Import or draw a molecule

From the **Modeling** view, import a structure by SMILES, CAS number, name, file, or Ketcher. Alternatively, ask for a molecule in **Chat**, for example:

```text
Optimize ethanol and calculate frequencies.
```

With a real provider enabled, the backend will attempt to identify ethanol, resolve its SMILES, and build the 3D molecule automatically.

### Step 2 — Verify structure, charge, and multiplicity

Automatic inference is only an initial estimate. Radicals, ions, metal complexes, open-shell systems, and unusual valence states require manual verification.

### Step 3 — Recommend a method and generate `.gjf`

Choose or edit:

- task type;
- solvent;
- accuracy tier;
- charge / multiplicity;
- functional / basis set;
- `%mem` / `%nprocshared`.

Then use **Recommend Method** and **Generate gjf**.

### Step 4 — Review the Gaussian input manually

At minimum, inspect:

```text
Link 0
Route section
Functional / basis
Charge / multiplicity
Coordinates
SCRF
Task-specific keywords
```

A ```gjf code block generated in Chat can currently be copied or downloaded, but it is not automatically synchronized into the Modeling-view gjf editor. Copy it manually if needed, or use the rule-based generator in the Modeling view.

### Step 5 — Submit the job

- Local Linux: configure the `g16` executable path.
- Windows + WSL2: configure the G09W/G09 path.
- SSH: create a remote profile with host, user, Gaussian path, and scratch directory.

### Step 6 — Inspect logs and post-process results

The Jobs view exposes status and logs. A successful job with an available `.fchk` can be passed to the Plot view for Multiwfn/VMD analysis.

## AI provider configuration

Providers can be added from **Settings** with fields such as:

```text
id
name
kind
base_url
api_key
models
default_model
```

Built-in presets include OpenAI, Anthropic Claude, DeepSeek, Volcengine Ark, and local vLLM/Ollama endpoints.

If no usable configured provider is selected, the backend falls back to `mock`.

## Data and configuration

Persistent state is stored under:

```text
data/
```

The root data directory can be overridden with:

```bash
export AAGD_DATA_DIR=/your/custom/path
```

Important files include:

```text
data/settings.json    providers, API keys, tool paths, SSH profiles
data/app.db           job ledger
data/uploads/*.json   molecule records
data/jobs/<job-id>/   Gaussian inputs and outputs
```

On systems supporting POSIX permissions, `settings.json` is set to mode `0600` on save. API keys and SSH passwords/passphrases are masked before configuration data is returned to the frontend.

## Security notes

The project includes several basic safeguards:

- sensitive configuration fields are masked in API responses;
- Multiwfn/VMD write locations are checked against a path sandbox;
- Linux Gaussian is launched with an argument list through `subprocess.Popen` rather than a shell command string;
- SSH profiles support key-based authentication.

Important caveats remain:

- `data/settings.json` still contains local credentials in plaintext and must not be committed to Git;
- the SSH runner constructs remote shell commands from profile values such as `gaussian_path` and `scratch_dir`, so only trusted servers and trusted configuration values should be used;
- there is currently no user-authentication layer, so the settings APIs should not be exposed directly to the public internet.

## Production build

Build the frontend first:

```bash
npm run build --prefix frontend
```

Then start FastAPI:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

When `frontend/dist` exists, FastAPI mounts the built SPA at `/`, while API routes remain under `/api/*`.

## Current limitations

- The rule-based recommender is primarily designed for common organic/main-group use cases and does not replace method validation for a specific research problem.
- The `.gjf` importer currently parses Cartesian coordinates only; pure Z-matrix inputs are unsupported.
- The `.out/.log` importer relies on `Standard orientation`.
- `.cdxml` parsing is best-effort. Although the frontend currently maps `.cdx` files to the same import path, the backend parses textual CDXML and does not guarantee support for binary CDX files.
- Image structure recognition depends on OSRA or a compatible vision model and always requires manual validation.
- SSH execution does not yet integrate SLURM or PBS.
- The SSH runner does not automatically run remote `formchk`.
- Automatic HOMO/LUMO orbital indexing uses a closed-shell approximation; open-shell systems require manual inspection.
- Multiwfn scripted menus are version-sensitive and should be reviewed before execution.
- The repository currently has no unit-test/CI test suite; validate the complete workflow before production research use.

## Planned directions

- SLURM / PBS job schedulers;
- batch calculations, parameter sweeps, and job dependencies;
- automatic IRC / TS workflow chaining;
- stricter Gaussian route parsing and calculation templates;
- open-shell orbital handling;
- NMR, UV-Vis, and vibrational-spectrum result parsing;
- broader automated testing and CI;
- authentication and multi-user job isolation.

## License

MIT License © 2026 8lampard8
