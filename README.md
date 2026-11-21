# ai-auto-gauss-DFT

**简体中文** | [English](README.en.md)

AI 对话驱动的 Gaussian 量化计算与分子信息学全流程 Web 平台：**分子建模 → 2D/3D 编辑 → 生成 `.gjf` → 提交任务（本地 / SSH）→ 分子描述符提取（RDKit + DFT）→ 结果作图（Multiwfn / VMD）**。支持顶栏一键切换 **中文 / EN** 界面，并在网页内自由切换主流 AI 模型与自定义 API。

---

## 功能概览

| 模块 | 核心能力 |
|------|----------|
| **1 分子建模** | **对话直接建模**：说「帮我计算乙醇的优化」，AI 自动识别分子名 → 检索 SMILES（PubChem / CIR）→ 生成 3D 构象并刷新视图；另支持 2D 绘制、SMILES、CAS 登录号（自动校验位检查）、中英文名称、拖拽上传 `.mol / .sdf / .mol2 / .gjf / .out / .log / .cdxml / 图片`；3Dmol.js 交互查看，自动推断电荷与多重度 |
| **2 2D/3D 编辑** | Ketcher 2D 画板 + 3Dmol 3D 视图**双向同步**；一键插入常见官能团（`-OH / -NH₂ / -COOH / -CHO / -CN / -NO₂ / -OMe / -Ac / -Ph / -SH / -SO₃H / -N₂⁺ / 卤素`），原地更新构象不产生重复分子 |
| **3 生成 gjf** | 规则推荐器 + AI 对话双轨推荐泛函 / 基组 / 色散 / SCRF 溶剂模型；实时校验 Gaussian 内置基组（自动规范化如 `def2-TZVP → Def2TZVP`）；支持从对话代码块一键「载入到编辑器」并手动编辑 |
| **4 提交任务** | **本地执行**（原生 Windows G09W/G16W、WSL2 Interop、Linux `g16` 全支持；自动探测 CPU/RAM 推荐 `%nproc`/`%mem`，32 位 G09W 自动限 4 核 / 1500MB 与 link0 崩溃自动降配重试）+ **SSH 远程一键提交**（自动展开 `$HOME`、`nohup` + 轮询 + 远程 `formchk` + 回传 `.log`/`.fchk`）；完成后自动解析能量 / 能隙 / 偶极矩 / 虚频摘要，失败提取可读报错 |
| **5 分子描述符** | **RDKit 2D/3D 结构描述符**（基本信息、理化/类药性、拓扑指数、3D 形状 Rg/PMI/NPR/PBF/vdW 体积 + 全量 ~217 项 2D）+ **Gaussian DFT 量化描述符**（SCF 能量、HOMO/LUMO/能隙、概念 DFT 反应性指数 $I, A, \chi, \mu, \eta, S, \omega, \omega^-, \omega^+$、偶极矩、极化率、热力学 ZPE/H/G/TS、虚频、TD-DFT 激发态、Mulliken/APT/Hirshfeld/CM5/NPA 原子电荷表）；支持**直接拖入 `.log/.out` 解析**及多分子/任务/SMILES **批量提取导出 CSV / JSON**（适合 Excel / QSAR / 机器学习） |
| **6 结果作图** | HOMO/LUMO、ESP 等值面、NCI / IRI / IGM / IGMH；优先从 `.fchk` 头文件读取精确电子数与原子数；目录沙箱限制，驱动 Multiwfn + VMD 出图 |
| **7 双语与模型自由** | 顶栏一键切换 **中文 / EN**（对话语言同步跟随）；内置 OpenAI / Anthropic / DeepSeek / 豆包 Ark / 本地 vLLM·Ollama / 自定义 OpenAI 兼容 / Mock 演示模式 |

---

## 环境要求

- **Python** ≥ 3.10（推荐 3.11–3.13，含 `rdkit`）
- **Node.js** ≥ 18（推荐 20/22 LTS）
- **可选外部计算软件**（未配置时可使用全部建模、描述符提取、`.gjf` 生成与 Mock 对话功能）：
  - Gaussian（Linux `g16`/`g09`，或 Windows `G09W`/`G16W`）
  - Multiwfn 3.8(dev) 与 VMD（仅波函数可视化作图需要）

---

## 安装与启动（快速开始）

### 方式一：Linux / macOS / WSL2

```bash
git clone https://github.com/8lampard8/ai-auto-gauss-DFT.git
cd ai-auto-gauss-DFT

# 1. 创建虚拟环境并安装后端依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. 安装前端依赖
npm install --prefix frontend

# 3. 一键启动（后端 :8000 + 前端 :5173）
./dev.sh
```

启动后浏览器访问：**http://localhost:5173**

### 方式二：Windows（PowerShell）

```powershell
git clone https://github.com/8lampard8/ai-auto-gauss-DFT.git
cd ai-auto-gauss-DFT

# 1. 创建虚拟环境并安装后端依赖
python -m venv .venv
.\.venv\Scripts\pip.exe install -r backend\requirements.txt

# 2. 安装前端依赖
npm install --prefix frontend

# 3. 终端 1：启动后端（默认 8000 端口；若 8000 被占用可改用 --port 8001）
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 4. 终端 2：启动前端开发服务（若后端改了端口，先设置 $env:VITE_API_TARGET='http://127.0.0.1:8001'）
cd frontend
npm run dev
```

启动后浏览器访问：**http://localhost:5173**

### 方式三：生产单端口部署（前后端合并为一个端口）

```bash
npm run build --prefix frontend            # 构建产出至 frontend/dist
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# FastAPI 自动挂载静态前端，直接访问 http://localhost:8000
```

> **提示**：无 API Key、未配置 Gaussian / Multiwfn 时，系统默认以 **Mock 演示模式**运行，可直接体验分子建模、2D/3D 编辑、描述符提取、`.gjf` 生成等全部界面。

---

## 如何使用（完整工作流）

### 1. 切换语言与配置 AI / 工具路径
- **中英文切换**：点击右上角顶栏的 **`中文 | EN`** 胶囊按钮，整个界面与描述符名称实时切换并自动记住偏好；切换为 `EN` 后 AI 对话也会自动使用英文回复。
- **配置 AI 模型**：进入左侧 **「⚙️ 设置」** → 选择预设（OpenAI / Anthropic / DeepSeek / 豆包 Ark / 本地 Ollama·vLLM）或手动填写 Base URL、API Key 与模型列表 → 点击「测试」确认连通 → 「设为活跃」，即可在顶栏下拉随时切换模型。
- **配置本地软件路径**：在「设置」页面底部填入 Gaussian（如 `D:\gauss\G09W\g09w.exe` 或 `/opt/g16/g16`）、Multiwfn、VMD 路径并保存。

### 2. 导入与建模分子（🧪 建模 / ✏️ 编辑）
- **对话自动建模**：在 **「💬 对话」** 直接输入「帮我优化阿司匹林结构」或给出 SMILES，系统自动检索 SMILES（PubChem / CIR）并生成 3D 结构，在对话顶栏显示当前分子快捷入口。
- **手动导入**：在 **「🧪 建模」** 右侧卡片切换标签，支持：
  - **绘制分子**：打开 Ketcher 2D 画板手绘结构导入；
  - **SMILES**：直接粘贴如 `CCO`、`c1ccccc1`；
  - **CAS 号**：输入如 `64-17-5`（自动校验格式与校验位）；
  - **按名称**：中英文名称检索（支持富勒烯 C60 精确几何生成）；
  - **文件拖拽**：点击或直接拖入 `.mol / .sdf / .mol2 / .gjf / .out / .log / .cdxml / .png / .jpg`。
- **2D/3D 协同编辑**：点击左侧 **「✏️ 编辑」**，在左侧 Ketcher 2D 画板点击工具栏一键插入官能团并连键，开启「实时同步到 3D」即可在右侧 3Dmol 视图中实时预览构象变化。

### 3. 生成 `.gjf` 与提交计算（🧪 建模 → 🧮 任务）
1. 在 **「🧪 建模」** 右下角「gjf 输入生成」卡片中选择计算类型（OPT / FREQ / OPT+FREQ / SP / 过渡态 TS / QST2 / TD-DFT / IRC / Scan / NMR）、溶剂（气相或 PCM/SMD 常用溶剂）与精度档位（快速 / 标准 / 高精度）。
2. 点击 **「推荐方法」** 自动填充泛函、基组、色散与溶剂参数（切换分子时电荷与多重度自动同步；基组输入框实时校验合法性）。
3. 点击 **「生成 gjf」** 后可在编辑框自由修改（或在「💬 对话」中让 AI 生成后点击代码块上的 **「载入到编辑器」**）。
4. 点击 **「提交任务」**：
   - **本地执行**：自动探测本机 CPU/RAM 推荐 `%nprocshared` 与 `%mem`，G09W 自动应用 32 位内存/核数保护；
   - **SSH 远程**：新增或选择远程节点（支持 SSH 密钥或密码），自动上传并 `nohup` 运行，完成后自动执行 `formchk` 并回传 `.log` / `.fchk`。
5. 在 **「🧮 任务」** 页面可实时查看运行日志、下载 `.gjf` / `.log`，成功任务卡片自动展示 `E`、`Gap`、`μ`、`G`、`虚频` 摘要标签。

### 4. 提取分子描述符与批量导出（🧬 描述符）
点击左侧 **「🧬 描述符」**（或在 3D 查看器、任务卡片、对话顶栏点击「🧬 描述符」直达）：

- **单分子 / 任务提取**：
  - **已保存分子** → 点击「提取结构」获取 RDKit 2D/3D 描述符（含基本信息、理化/类药性、拓扑指数、3D 形状）。
  - **含日志的计算任务** → 点击「提取量化+结构」同时解析 Gaussian DFT 量化描述符与优化后几何的 RDKit 描述符。
  - **直接上传 `.log` / `.out`** → 将已有 Gaussian 输出文件点击或拖入「上传/拖入 .log/.out 直接解析」，无需新建任务即可立即提取全部量子化学描述符、原子电荷分布表（正负电荷红蓝着色）与 TD-DFT 激发态表。
  - 勾选 **「包含全部 RDKit 2D (~217 项)」** 可展开全部 217 维 RDKit 特征；支持顶部关键词实时搜索筛选、点击任意行一键复制、以及导出 **CSV / JSON**。
- **批量提取与导出（QSAR / 机器学习）**：
  - 切换到 **「批量提取与导出 (QSAR/ML)」** 标签。
  - 自由组合勾选多个「已保存分子」、多个「含日志的计算任务」，并在文本框批量粘贴 SMILES（每行一条，支持 `CCO,乙醇`、`c1ccccc1,苯`、`ethanol CCO` 等格式）。
  - 点击 **「批量提取预览」** 检查表格，或一键 **「导出 CSV (Excel/ML)」**（带 UTF-8 BOM，Excel 直接打开不乱码）/ **「导出 JSON」**。

#### 描述符 REST API 速查（可用于脚本调用）
```bash
# 单分子 RDKit 描述符（full=true 包含全部 ~217 项 2D）
curl "http://127.0.0.1:8000/api/descriptors/molecule/<molecule_id>?full=true"

# 计算任务 DFT + RDKit 描述符
curl "http://127.0.0.1:8000/api/descriptors/job/<job_id>"

# 批量提取并直接导出 CSV
curl -X POST http://127.0.0.1:8000/api/descriptors/export \
  -H "Content-Type: application/json" \
  -d '{"smiles_list":["CCO,ethanol","c1ccccc1,benzene"],"include_all_rdkit":false,"format":"csv"}' \
  -o descriptors.csv
```

### 5. 波函数可视化作图（📊 作图）
进入左侧 **「📊 作图」** → 选择作图类型（HOMO / LUMO / ESP / NCI / IRI / IGM / IGMH）与带 `.fchk` 的成功任务 → 可按需微调 Multiwfn 命令序列与 VMD 渲染脚本 → 点击 **「运行作图」**，结果图片与完整日志将直接显示在页面中。

---

## 架构概览

```text
ai-auto-gauss-DFT/
├── backend/                     Python 3.13 + FastAPI
│   ├── app/
│   │   ├── main.py              FastAPI 入口（CORS + 生命周期孤儿任务回收 + 静态前端挂载）
│   │   ├── config.py            路径与默认配置
│   │   ├── schemas.py           Pydantic 数据模型
│   │   ├── settings_store.py    设置持久化（0600，密钥掩码）
│   │   ├── molecules_store.py   分子 JSON 原子持久化（路径穿越防护）
│   │   ├── jobs_store.py        SQLite WAL 线程安全任务台账
│   │   ├── security.py          路径沙箱 + 密钥掩码
│   │   ├── routers/             system / models / chat / molecules / descriptors / gjf / jobs / visualize
│   │   ├── chemistry/           importer / name_resolver / descriptors / gaussian_parser / gjf_writer / method_recommender / basis_sets / plot_recipes / knowledge
│   │   ├── ai/                  provider / openai / anthropic / mock / router / prompts / web_search
│   │   └── exec/                local_runner / ssh_runner / multiwfn_runner / vmd_runner / wsl
│   └── tests/                   pytest 单元测试与接口集成测试
├── frontend/                    React + Vite + TypeScript + 3Dmol.js + Zustand + Ketcher
│   └── src/
│       ├── i18n.ts              中英双语映射（UI + 描述符标签/提示）
│       ├── store.ts             全局状态管理
│       ├── types.ts             TypeScript 类型定义
│       ├── api/client.ts        REST / SSE 流式 / 文件导出客户端
│       └── components/          Modeling / MoleculeEditor / Chat / Jobs / Descriptors / Plot / Settings
├── data/                        上传分子 / 任务工作目录 / 作图输出 / app.db / settings.json（git 忽略）
└── dev.sh                       Linux/macOS/WSL2 一键启动脚本
```

---

## 运行测试

```bash
cd backend
python -m pytest -v
```

```bash
cd frontend
npx tsc --noEmit && npm run build
```

---

## 安全说明

- `data/settings.json` 权限 `0600`（git 已忽略）；API Key 与 SSH 密码在接口返回时自动**掩码**，不写入日志。
- 作图与清理操作严格受目录沙箱限制（拒绝 `..` 与越界路径）。
- 本地 Gaussian 与 SSH 远端命令均避免未转义拼接（SSH 使用 `shlex.quote`），防止命令注入。

---

## 路线图

- [x] Phase 1–7：基础骨架、AI 对话、分子建模、`.gjf` 生成、本地/SSH 提交、Multiwfn/VMD 作图
- [x] 2D/3D 双向同步编辑器（Ketcher + 官能团快捷插入）与 CAS 号导入
- [x] 分子描述符提取（RDKit 2D/3D + Gaussian DFT 解析 + 批量 QSAR/ML CSV/JSON 导出）
- [x] 顶栏一键中英双语切换（`中文 | EN`）与原生 Windows / WSL2 / Linux 统一支持
- [ ] SLURM / PBS 作业队列集成
- [ ] 批量参数扫描、IRC 自动接续与 NMR / UV-Vis 谱图绘制

## 许可证

MIT © 2026 8lampard8
