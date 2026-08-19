# ai-auto-gauss-DFT

**简体中文** | [English](README.en.md)

一个面向 Gaussian 量子化学计算的 AI 辅助网页工作台，将 **分子导入与建模 → 计算方法配置 → `.gjf` 生成 → 本地/SSH 提交 → 日志与任务管理 → Multiwfn/VMD 后处理** 串联到同一界面中。

项目的核心目标不是替代 Gaussian、Multiwfn 或 VMD，而是把分散的建模、输入文件准备、任务执行和结果可视化步骤组织成一套可交互、可追踪的工作流，并允许接入 OpenAI、Anthropic 及 OpenAI-compatible 模型辅助完成化学信息解析与计算设置。

> 当前版本：`0.1.0`。项目仍处于早期开发阶段，建议在提交正式计算前人工检查电荷、多重度、计算方法、基组、溶剂模型和 Gaussian route section。

## 核心能力

### 1. 分子导入与 3D 建模

支持多种结构入口，并统一转换为内部 `Molecule` 数据模型：

- **SMILES**：RDKit 解析，ETKDG 生成 3D 构象，并尝试 MMFF 优化。
- **中英文名称**：优先使用内置常见分子表，随后通过 PubChem PUG-REST 和 NCI CIR 检索 SMILES。
- **CAS 号**：先校验 CAS 格式和校验位，再通过 PubChem 解析结构。
- **文件导入**：`.mol` / `.sdf` / `.mol2` / `.gjf` / `.out` / `.log` / `.cdxml`。
- **结构图片**：优先调用本机 OSRA；若未安装，可使用已配置的 OpenAI-compatible 视觉模型识别 SMILES。
- **Gaussian 输出**：从最后一个 `Standard orientation` 读取结构，并恢复可识别的电荷、多重度和 route 信息。

前端使用 3Dmol.js 显示三维结构；分子会以 JSON 形式保存到 `data/uploads/`。

### 2. Ketcher 2D / 3D 联动编辑

内置 Ketcher 2D 编辑器，并与当前 3D 分子进行双向联动：

- 从已保存分子加载 SMILES 到 Ketcher；
- 从 Ketcher 获取新的 SMILES，并由 RDKit 重新生成 3D 构象；
- 原位更新当前 molecule id，避免每次编辑都产生重复记录；
- 可快捷插入 `-OH`、`-NH₂`、`-COOH`、`-CHO`、`-CN`、`-NO₂`、`-OMe`、`-Ph`、卤素等常用片段；
- Ketcher/Indigo 体积较大，因此采用 lazy loading，仅在使用编辑器时加载。

### 3. AI 对话与分子识别

聊天接口采用 SSE 流式输出。真实 AI provider 下，系统可先从用户消息中提取分子名称或 SMILES，再自动完成名称解析、3D 建模和分子保存。

当前支持的 provider 类型：

- `openai`
- `anthropic`
- `custom`：任意 OpenAI-compatible API，例如 DeepSeek、Volcengine Ark、本地 vLLM/Ollama 等
- `mock`：无需 API Key，用于前端和对话流程测试

聊天还可选择开启 DuckDuckGo 搜索，将搜索摘要追加到模型上下文中。

> **注意：Mock provider 只模拟 AI 对话，不会模拟 Gaussian、Multiwfn 或 VMD 的实际计算。**

### 4. Gaussian 方法推荐与 `.gjf` 生成

后端包含独立的规则推荐器，不依赖 LLM 即可根据计算类型、溶剂、精度、电荷和多重度生成基础 `MethodSpec`。

当前任务类型包括：

- OPT
- FREQ
- OPT + FREQ
- 单点能
- TS
- QST2
- IRC
- relaxed scan
- NMR
- TDDFT

默认规则覆盖 B3LYP-D3(BJ)、B2PLYP-D3(BJ)、PBE0、CAM-B3LYP 等常用组合，并支持 PCM 溶剂关键字。

基组模块会对常见 Gaussian 内置基组进行校验和规范化。例如：

```text
def2-TZVP  ->  Def2TZVP
```

生成器负责组织：

```text
%chk
%mem
%nprocshared
# route section

title

charge multiplicity
Cartesian coordinates
```

生成后的 `.gjf` 可继续在网页文本框中手工修改，再提交任务。

### 5. 本地 Gaussian 执行

本地 runner 支持两种主要模式：

#### Linux Gaussian

配置 Linux `g16`/Gaussian 可执行文件后，通过 `subprocess` 直接启动任务。成功后会尝试调用同目录下的 `formchk` 将 `job.chk` 转换为 `job.fchk`。

#### Windows G09W + WSL2

当后端运行于 WSL2、配置的是 Windows Gaussian 路径时，程序会：

1. 将 Windows 路径转换到 `/mnt/<drive>/...`；
2. 若配置的是 `g09w.exe`，自动改用命令行版 `g09.exe`；
3. 通过 Windows `cmd.exe` / WSL interop 执行 Gaussian；
4. 对 32 位 G09W 自动限制资源，最高约 `1500MB` 和 `4` 核；
5. 对典型 link0 崩溃尝试一次更保守的 `600MB / 1 core` 重试；
6. 成功后尝试运行 `formchk.exe` 并将 `.fch/.fchk` 回传到任务目录。

本地资源推荐使用物理 CPU 核数减 2，并将 `%mem` 控制在总内存约 70% 以内。

### 6. SSH 远程提交

SSH runner 基于 Paramiko，实现一个轻量级的直连远程执行流程：

```text
connect -> mkdir scratch -> upload job.gjf
        -> nohup g16 job.gjf > job.log 2>&1 &
        -> record PID -> poll kill -0
        -> download job.log / job.fchk(if present)
```

支持 SSH key、密码或本机 agent/key discovery。

当前 SSH 模式是 **nohup + PID polling**，尚未集成 SLURM/PBS 等队列系统。远程端若希望得到 `job.fchk`，需要计算环境自行生成该文件；当前 SSH runner 不会自动执行远程 `formchk`。

### 7. 任务记录与错误诊断

任务状态保存在 SQLite：

```text
data/app.db
```

每个任务保存状态、提交类型、本地/远程信息、资源配置、输入文件路径、日志路径和结果路径等信息。

本地 Gaussian 失败时，程序会尝试识别常见错误，例如：

- 内存不足；
- 基函数规模过大；
- Gaussian 输入语法错误；
- link executable 启动失败；
- G09W link0 早期崩溃；
- `Error termination via Lnk...`。

### 8. Multiwfn / VMD 后处理

当前内置的分析 recipe 包括：

- HOMO
- LUMO
- ESP cube / isosurface
- NCI
- IRI
- IGM
- IGMH

基本流程为：

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

Multiwfn 菜单编号可能随版本变化，因此前端允许在运行前编辑命令序列和 VMD Tcl 脚本。当前 recipe 主要按 Multiwfn 3.8(dev) 的菜单结构编写。

## 系统架构

```text
ai-auto-gauss-DFT/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 FastAPI 入口、CORS、生产静态文件挂载
│       ├── config.py               data 目录与默认设置
│       ├── schemas.py              Pydantic 数据模型
│       ├── settings_store.py       provider / 路径 / SSH 配置持久化
│       ├── molecules_store.py      分子 JSON 持久化
│       ├── jobs_store.py           SQLite 任务台账
│       ├── security.py             密钥掩码与路径沙箱
│       ├── routers/
│       │   ├── system.py           健康检查与硬件探测
│       │   ├── models.py           AI provider 与工具路径配置
│       │   ├── chat.py             SSE 对话、分子提取、搜索增强
│       │   ├── molecules.py        分子导入/更新/删除
│       │   ├── gjf.py              方法推荐、基组校验、gjf 生成
│       │   ├── jobs.py             本地/SSH 任务接口
│       │   └── visualize.py        Multiwfn/VMD 分析接口
│       ├── chemistry/
│       │   ├── importer.py         多格式结构解析与 3D 建模
│       │   ├── name_resolver.py    PubChem/CIR/CAS 名称解析
│       │   ├── basis_sets.py       Gaussian 基组校验与规范化
│       │   ├── method_recommender.py
│       │   ├── gjf_writer.py
│       │   ├── knowledge.py
│       │   └── plot_recipes.py
│       ├── ai/
│       │   ├── provider.py         provider 抽象
│       │   ├── providers_openai.py
│       │   ├── providers_anthropic.py
│       │   ├── mock.py
│       │   ├── router.py
│       │   ├── prompts.py
│       │   └── web_search.py
│       └── exec/
│           ├── local_runner.py     Linux Gaussian / WSL2+G09W
│           ├── ssh_runner.py       Paramiko SSH 提交
│           ├── multiwfn_runner.py
│           ├── vmd_runner.py
│           └── wsl.py
├── frontend/
│   ├── package.json                React 18 + Vite + TypeScript
│   └── src/
│       ├── App.tsx
│       ├── store.ts                Zustand 状态管理
│       ├── api/client.ts
│       └── components/             建模、Ketcher、Chat、Jobs、Plot、Settings
├── data/
│   ├── uploads/                    保存的 Molecule JSON
│   ├── jobs/                       本地任务工作目录
│   ├── plots/                      应用侧绘图目录
│   ├── app.db                      SQLite 任务数据库
│   └── settings.json               本地配置与凭据
└── dev.sh                          开发环境同时启动 FastAPI + Vite
```

## 快速开始

### 环境要求

基础 Web 应用至少需要：

- Python **3.10+**
- Node.js / npm
- Linux、macOS，或 Windows + WSL2

根据需要额外安装：

- Gaussian 16 / Gaussian 09
- Multiwfn
- VMD
- OSRA（仅用于本地图片结构识别，可选）

Gaussian、Multiwfn 和 VMD 均为独立软件，本项目不提供这些程序或许可证。

### 1. 克隆项目

```bash
git clone https://github.com/8lampard8/ai-auto-gauss-DFT.git
cd ai-auto-gauss-DFT
```

### 2. 安装后端依赖

```bash
python3 -m pip install -r backend/requirements.txt
```

主要 Python 依赖包括 FastAPI、Pydantic、RDKit、Paramiko、OpenAI SDK、Anthropic SDK、httpx 和 psutil。

### 3. 安装前端依赖

```bash
npm install --prefix frontend
```

### 4. 启动开发环境

```bash
chmod +x dev.sh
./dev.sh
```

开发模式下：

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API docs: http://localhost:8000/docs
```

Vite 会把 `/api` 请求代理到 FastAPI 的 `:8000`。

## 推荐使用流程

### Step 1 — 导入或绘制分子

在「建模」页面可通过 SMILES、CAS、名称、文件或 Ketcher 导入结构；也可以直接在「对话」中输入：

```text
计算乙醇的结构优化和频率
```

若启用了真实 AI provider，系统会尝试识别“乙醇”，解析 SMILES 并生成 3D 分子。

### Step 2 — 检查结构、电荷和多重度

自动推断只适合作为初始值。特别是自由基、离子、金属配合物、开壳层体系和特殊价态体系，应人工确认。

### Step 3 — 推荐并生成 `.gjf`

在 gjf 编辑器中选择：

- 计算类型；
- 溶剂；
- 精度；
- 电荷 / 多重度；
- 泛函 / 基组；
- `%mem` / `%nprocshared`。

随后点击「推荐方法」和「生成 gjf」。

### Step 4 — 人工检查 Gaussian 输入

建议至少检查：

```text
Link 0
Route section
Functional / basis
Charge / multiplicity
Coordinates
SCRF
Task-specific keywords
```

当前 Chat 中出现的 ```gjf 代码块支持复制和下载，但不会自动同步到建模页的 gjf 编辑器；需要手动复制，或直接使用建模页的规则生成器。

### Step 5 — 提交任务

- 本地 Linux：配置 `g16` 路径；
- Windows + WSL2：配置 G09W/G09 路径；
- SSH：建立远程 profile，配置 host、user、Gaussian path 和 scratch directory。

### Step 6 — 查看日志和结果

任务页面可查看运行状态和日志。成功任务若存在 `.fchk`，可进入「作图」页面运行 Multiwfn/VMD recipe。

## AI Provider 配置

在「设置」中可以增加 provider，并设置：

```text
id
name
kind
base_url
api_key
models
default_model
```

内置预设包括 OpenAI、Anthropic Claude、DeepSeek、Volcengine Ark 和本地 vLLM/Ollama。

若没有配置有效 provider，系统自动回退到 `mock`。

## 数据与配置

默认所有持久化数据位于：

```text
data/
```

可以通过环境变量修改数据目录：

```bash
export AAGD_DATA_DIR=/your/custom/path
```

主要文件：

```text
data/settings.json    provider、API key、工具路径、SSH profile
data/app.db           job ledger
data/uploads/*.json   molecule records
data/jobs/<job-id>/   Gaussian 输入/输出
```

`settings.json` 在支持 POSIX permission 的系统上会尝试设置为 `0600`；API Key、SSH password/passphrase 返回前会被掩码。

## 安全设计

项目实现了若干基础保护：

- 配置 API 返回时掩码敏感字段；
- Multiwfn/VMD 输出目录经过 path sandbox 检查；
- Linux Gaussian 使用参数列表调用 `subprocess.Popen`，而不是拼接 shell 命令；
- SSH profile 优先支持 key authentication。

仍需注意：

- `data/settings.json` 本质上仍保存本地明文凭据，请不要提交到 Git；
- SSH runner 会执行由 profile 中 `gaussian_path`、`scratch_dir` 等字段构造的远程 shell 命令，因此只应配置可信服务器和可信路径；
- 当前应用没有用户认证系统，不建议将设置接口直接暴露到公网。

## 生产构建

先构建前端：

```bash
npm run build --prefix frontend
```

然后启动 FastAPI：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

若 `frontend/dist` 存在，FastAPI 会把构建后的 SPA 挂载到 `/`，API 保持在 `/api/*`。

## 当前限制

- 规则推荐器主要面向常见有机/主族体系，并不能替代针对具体课题的方法学验证。
- `.gjf` importer 目前只解析笛卡尔坐标，不支持纯 Z-matrix。
- `.out/.log` importer 依赖 `Standard orientation`。
- `.cdxml` 解析是 best-effort；二进制 `.cdx` 当前前端虽可选择，但后端按文本 CDXML 解析，不能保证真正的二进制 CDX 可用。
- 图片结构识别依赖 OSRA 或兼容视觉模型，结果必须人工检查。
- SSH 当前没有 SLURM/PBS 调度支持。
- SSH runner 不自动执行远程 `formchk`。
- HOMO/LUMO 自动轨道编号使用闭壳层近似；开壳层体系需要人工确认。
- Multiwfn scripted menu 对版本敏感，执行前应检查命令序列。
- 当前没有单元测试/CI 测试套件，正式科研使用前请自行验证完整工作流。

## 后续方向

- SLURM / PBS 作业调度；
- 批量计算、参数扫描和任务依赖；
- IRC / TS 工作流自动接续；
- 更严格的 Gaussian route parser 与计算模板；
- 开壳层轨道处理；
- NMR、UV-Vis、振动光谱等结果解析；
- 更完整的测试和 CI；
- 用户认证与多用户任务隔离。

## License

MIT License © 2026 8lampard8
