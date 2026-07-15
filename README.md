# ai-auto-gauss-DFT

AI 对话驱动的 Gaussian 量化计算全流程网页:**分子建模 → 生成 gjf → 提交任务(本地 / SSH)→ 结果作图(Multiwfn / VMD)**。可在网页内自由切换主流 AI 模型与自定义 API。

## 功能概览

| 模块 | 能力 |
|------|------|
| **1 分子建模** | **对话直接建模**:在对话框说「帮我计算乙醇的优化」,AI 自动识别分子名→检索 SMILES(PubChem/CIR)→建模,3D 视图自动更新;另支持 SMILES / mol / mol2 / gjf / out·log / cdxml / 图片导入;3Dmol.js 3D 查看;自动推断电荷与多重度 |
| **2 生成 gjf** | 对话式询问计算需求,自动推荐泛函/基组/多重度/SCRF 并生成 .gjf;规则推荐器 + AI 双轨,可编辑 |
| **3 提交任务** | 本地(WSL2 自动经 interop 调 Windows G09W 或 Linux g16;自动探测 CPU/RAM 推荐 `%nproc`/`%mem`,G09W 自动限 4 核/1.5GB)+ SSH 远程一键提交(nohup + 轮询 + 回传 log/fchk);任务台账与**运行中实时日志**;失败自动提取可读原因(内存/基函数/语法/link0 崩溃等) |
| **4 结果作图** | HOMO/LUMO、ESP 等值面、NCI/IRI/IGM/IGMH;沙箱限目录,驱动 Multiwfn + VMD(均可为 Windows 版,经 WSL interop)出图 |
| **5 模型自由** | OpenAI / Anthropic / 任意 OpenAI 兼容(DeepSeek、豆包/Ark、本地 vLLM/Ollama)/ 自定义 / Mock;网页内增删改与切换 |

## 架构

```
ai-auto-gauss-DFT/
├── backend/                 Python 3.13 + FastAPI
│   └── app/
│       ├── main.py          FastAPI 入口(CORS + 静态挂载)
│       ├── config.py        路径与默认设置
│       ├── schemas.py       Pydantic 模型
│       ├── settings_store.py 设置持久化(0600,密钥掩码)
│       ├── molecules_store.py 分子 JSON 持久化
│       ├── jobs_store.py    SQLite 任务台账
│       ├── security.py      路径沙箱 + 密钥掩码
│       ├── routers/         system / models / chat / molecules / gjf / jobs / visualize
│       ├── chemistry/       importer / name_resolver / gjf_writer / method_recommender / plot_recipes / knowledge
│       ├── ai/              provider 抽象 / openai / anthropic / mock / router / prompts
│       └── exec/            local_runner / ssh_runner / multiwfn_runner / vmd_runner
├── frontend/                React + Vite + TypeScript + 3Dmol.js + zustand
│   └── src/{App.tsx, store.ts, types.ts, api/client.ts, components/}
├── data/                    上传 / 任务工作目录 / 作图输出 / app.db / settings.json
└── dev.sh                   一键启动后端(:8000)+ 前端(:5173)
```

## 快速开始

```bash
cd ai-auto-gauss-DFT

# 后端依赖
python3 -m pip install -r backend/requirements.txt

# 前端依赖
npm install --prefix frontend

# 一键启动
./dev.sh
# 浏览器打开 http://localhost:5173
```

> 无 API Key、未配置 Gaussian/Multiwfn 时,以 **Mock provider** 与模拟流程演示全部界面;在「设置」中填入密钥与路径后即转真实。

## 使用流程

1. **导入分子**:可直接在「对话」中说「帮我计算乙醇的优化」——AI 自动识别分子名、检索 SMILES(PubChem/CIR)并建模,3D 视图自动显示;也可左上「导入分子」手动导入 SMILES、按名称检索,或拖入 `.mol/.mol2/.gjf/.out/.cdxml/.png`。
2. **对话生成 gjf**:右侧「对话」描述需求(如「优化+频率,水作溶剂」)。Mock 模式下关键词触发示例;配置真实 AI 后智能推荐方法并输出 ```gjf 代码块,点「载入到编辑器」。
3. **gjf 编辑器**(左侧下方「gjf」按钮):选计算类型/溶剂/精度 →「推荐方法」→「生成 gjf」→ 可手动编辑 →「提交任务」。
4. **提交任务**:切到「任务」标签;本地自动填 nproc/mem,SSH 选节点;「一键提交」。运行中自动轮询,完成可下载 log/gjf,本地成功后自动 formchk 生成 .fchk。
5. **结果作图**:顶栏「作图」→ 选作图类型 + 带 .fchk 的成功任务 →(可编辑 Multiwfn 序列与 VMD 脚本)→「运行作图」,图片回显,日志可展开。

## 安全

- `data/settings.json` 权限 0600;API Key / SSH 密码在接口返回时**掩码**,绝不写日志。
- 作图流程**只允许**在配置的 Multiwfn 目录与 VMD 目录内写文件(路径沙箱,拒绝 `..` 与绝对路径越界)。
- gjf 写入文件后交 `g16` 执行,不经 shell 字符串拼接,避免注入。
- SSH 优先密钥文件;凭据不外泄。

## AI Provider 配置

「设置」→ 选预设(OpenAI / Anthropic / DeepSeek / 豆包 Ark / 本地 vLLM)或手动填写:
- **类型**:`openai`(OpenAI 协议)/ `custom`(OpenAI 兼容自定义 base_url)/ `anthropic` / `mock`
- **Base URL / API Key / 模型列表 / 默认模型**
- 「测试」验证连通;「设为活跃」后顶栏下拉可随时切换模型。

## 关键技术决策

- **SCRF / 溶剂**:依据 gaussian.com/scrf 与 sobko 知识库 —— G16 默认 PCM(IEFPCM),`scrf=(pcm,solvent=...)`;SMD 用于 ΔG_solv;非极性项需 `read`+`Dis/Rep/Cav`。推荐器默认水相用 PCM。
- **方法推荐**:有机优化 B3LYP-D3(BJ)/def2-TZVP;过渡态 `opt=(ts,calcfc,noeigentest)`;激发态 PBE0/CAM-B3LYP;重原子 def2 自动 ECP。
- **作图流程**(sobko 手册,权威 A):IGMH 主功能 20→4 导出 func1/func2.cub + `IGMHfill.vmd`;ESP 主功能 12 定量表面分析;HOMO/LUMO 主功能 0 导出轨道 cube。Multiwfn 菜单号随版本可能略有差异,前端脚本可编辑。

## 生产部署

```bash
npm run build --prefix frontend          # 产出 frontend/dist
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
# FastAPI 自动挂载 dist 到 /,访问 http://host:8000
```

## 路线图

- [x] Phase 1 骨架(FastAPI + Vite/React,健康检查,硬件探测)
- [x] Phase 2 AI provider 抽象 + 流式对话 + 设置持久化
- [x] Phase 3 分子导入 + 3Dmol 查看器
- [x] Phase 4 gjf 生成器 + 方法推荐器 + 编辑器
- [x] Phase 5 任务提交(本地 + SSH)+ 任务台账
- [x] Phase 6 结果作图(Multiwfn + VMD,沙箱)
- [x] Phase 7 端到端走查 + 文档

## 2D/3D 分子编辑器(新)

左侧导航「编辑」进入,左右双栏:
- **左:Ketcher 2D 画板** -- 画原子/键/环/电荷/立体;工具栏一键**插入功能基团**(-OH / -NH₂ / -COOH / -CHO / -CN / -NO₂ / -OMe / -Ac / -Ph / -SH / -SO₃H / -N₂⁺ / -F / -Cl / -Br / -I),插入后用键连到主分子。
- **右:3Dmol 3D 视图** -- 实时显示当前分子的 3D 构象。
- **双向同步**:切换分子自动载入画板(3D→2D);「同步到 3D」或「实时同步」把画板 SMILES 原地更新到 3D(2D→3D,同一 id 不产生重复分子)。
- 用途:在复杂分子(药物、富勒烯等)上逐步增删基团/原子,3D 实时跟随,再回「建模」生成 gjf 提交。

> Ketcher(Indigo WASM)较重,首次进入「编辑」或「绘制分子」时按需加载(约几秒)。

## 界面

明亮简洁卡片式(浅色背景、圆角卡片、蓝色主调、左侧导航 + 顶栏 + 卡片工作区)。导航:建模 / 编辑 / 对话 / 任务 / 作图 / 设置。对话栏有常驻可拖动滚动条 +「↓ 最新」按钮。任何渲染崩溃由顶层 ErrorBoundary 捕获并显示错误(不再白屏)。

## 后续可扩展

- SLURM/PBS 队列集成(当前 SSH 用 nohup 直跑)
- 批量/参数扫描、IRC 自动接续
- 内嵌 2D 结构编辑器(Ketcher)
- 二进制 CDX、NMR/UV-Vis 谱图绘制
