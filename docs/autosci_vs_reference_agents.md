# AutoSci 架构分析：借鉴与创新

> 参考对象：hermes-agent（主要参考）、EvoScientist、ResearchClaw、ResearchHarness  
> 撰写时间：2026-04-23

---

## 一、AutoSci 整体架构一览

```
Entry (CLI / REPL / Bench)
    │
    ├── cli.py          → autosci 命令（单次 / REPL）
    ├── bench.py        → autosci-bench 命令（ResearchClawBench 适配）
    │
    ├── AgentRunner     → 核心 while-loop，agent 无关
    │   ├── LLMClient           统一 LLM 调用（anthropic / openai-compat）
    │   ├── PromptBuilder       系统提示拼装
    │   ├── ErrorHandler        错误分类 + 指数退避重试
    │   ├── ContextEngine       可插拔上下文压缩（ABC + SummarizationCompressor）
    │   ├── MemoryManager       会话生命周期记忆管理
    │   ├── SkillEngine         技能发现 + 匹配注入
    │   └── SessionStore / Exporter   SQLite + Markdown 双轨存储
    │
    ├── Agents          → AgentRegistry 自注册
    │   ├── MainAgent           编排者（max_iter=30）
    │   └── Subagents × 5       research / experiment / code / analysis / write
    │
    └── Tools           → ToolRegistry 自注册，15 个内置工具
        ├── File        read_file / write_file / list_dir / glob / grep
        ├── Terminal    execute_command
        ├── Web         web_search / web_fetch
        ├── Agent       delegate / ask_user（runner 拦截）
        ├── Memory      store_memory / recall_memory
        └── Skills      list_skills / view_skill / create_skill
```

---

## 二、逐模块对比：借鉴 vs 创新

### 2.1 核心 while-loop（AgentRunner）

| 维度 | hermes-agent | AutoSci |
|------|-------------|---------|
| 驱动模型 | 同步 while-loop，工具调用驱动 | 同步 while-loop，工具调用驱动 |
| 迭代预算 | `max_iterations` | `max_iterations`（per-agent 可配） |
| runner 是否 agent-agnostic | 否（耦合主 agent） | **是**（同一 runner 跑主 agent 和任意子 agent） |
| 工具拦截层 | `model_tools.handle_function_call` 中间层 | `_RUNNER_TOOLS` 集合，直接在 runner 拦截 |

**借鉴**：while-loop + tool-call 驱动的基本结构来自 hermes-agent。  
**创新**：AgentRunner 是完全 agent-agnostic 的——主 agent、子 agent 共用同一个 runner 实例，包括共享 SessionStore、MemoryManager、SkillEngine。hermes-agent 的子 agent 需要独立实例化 `AIAgent`，AutoSci 用一个 runner 递归调用自身（`self.run(child_agent, ...)`），架构更简洁。

---

### 2.2 多 agent 委派（Delegation）

| 维度 | hermes-agent | EvoScientist | AutoSci |
|------|-------------|--------------|---------|
| 子 agent 定义方式 | 代码内写死工具集限制 | YAML 配置文件 | Python 类 + 自注册装饰器 |
| 子 agent 类型 | 通用 AIAgent 实例 | plan/research/code/debug/analyze/write | research/experiment/code/analysis/write |
| 委派隔离 | 子 agent 有独立上下文 | 中间件图隔离 | 子 session 有独立 ID，共享 runner |
| 并行委派 | 支持批量/并行 | 依赖 LangGraph 图 | 不支持（串行） |
| 注册扩展性 | 需修改核心代码 | 修改 YAML | **`agent_registry.register()` 自注册，pip 安装即生效** |

**借鉴**：5 subagent 的研究分工（research/experiment/code/analysis/write）受 EvoScientist 的团队结构（plan/research/code/debug/analyze/write）启发。  
**创新**：AutoSci 使用 **自注册 AgentRegistry**——每个子 agent 模块导入时调用 `agent_registry.register(AgentClass)`，`agent_registry.discover()` 自动扫描 `subagents/` 包。新增 agent 只需新建一个 `.py` 文件，无需修改任何核心文件，也无需改 YAML。这比 hermes-agent（硬编码）和 EvoScientist（YAML 配置）都更简洁。

---

### 2.3 记忆系统（Memory）

| 维度 | hermes-agent | EvoScientist | AutoSci |
|------|-------------|--------------|---------|
| 记忆类型 | 内置 + 外部 provider（Mem0/Honcho 等） | user_profile / research_preferences / experiment_conclusion / learned_preferences | **episodic / semantic / procedural** |
| 存储格式 | SQLite / 外部服务 | `MEMORY.md` 单文件（Markdown 分段） | `~/.autosci/memory/{类型}/mem_*.md` + `index.json` |
| 检索方式 | FTS5 + provider 接口 | 全量注入 system prompt | **三信号加权**：tag 0.4 + keyword 0.4 + recency 0.2 |
| 反思时机 | `on_session_end` + `on_pre_compress` | 每 20 条消息触发提取 | `on_session_end`（LLM 反思）+ `on_pre_compress`（救援） |
| 委派嵌套安全性 | `on_delegation` hook | 不支持嵌套 | **`_session_stack`：push/pop 防止嵌套覆盖** |
| 冲突检测 | 无 | 内容合并（按 section） | **tag 相似度 >80% 触发更新而非新建** |

**借鉴**：三类记忆（episodic/semantic/procedural）是认知科学的标准分类，hermes-agent 和 EvoScientist 都有类似思路。`on_session_end` 反思 + `on_pre_compress` 救援的双触发点借鉴自 hermes-agent 的生命周期 hook 设计。  
**创新**：
1. **`_session_stack` 嵌套保护**：hermes-agent 用 `on_delegation` hook 通知 memory provider，但 AutoSci 中父子 session 共用同一 MemoryManager 实例，若用单一 `_current_session_id` 则嵌套委派会覆盖父 session 状态。AutoSci 用栈结构彻底解决此问题。
2. **tag 相似度冲突检测**：避免语义记忆重复积累，保持记忆库精简。
3. **三信号检索权重**：tag 0.4 + keyword 0.4 + recency 0.2，比 hermes-agent 的 FTS5 全文检索更细粒度，比 EvoScientist 的全量注入更节省 token。

---

### 2.4 上下文压缩（Context Compression）

| 维度 | hermes-agent | AutoSci |
|------|-------------|---------|
| 策略 | 头部保护 + 尾部 token 预算保护 + 中间 LLM 摘要 | 三区保护（头/中/尾）+ LLM 摘要 |
| 接口 | `context_compressor.py`（具体实现） | **`ContextEngine` ABC + `SummarizationCompressor`（可插拔）** |
| 防抖 | 无（每次触发压缩） | **anti-thrashing：压缩后冷却期，避免连续触发** |
| 触发条件 | context length 百分比 | 同，`threshold_ratio` 可配 |
| 预压缩钩子 | `on_pre_compress` 让 memory 提取信息 | 同 |

**借鉴**：三区保护策略（头保持、尾保留、中间摘要）直接借鉴 hermes-agent 的 `context_compressor.py`。  
**创新**：`ContextEngine` 定义为 ABC（抽象基类），`SummarizationCompressor` 是其默认实现。未来可替换为 `RAGCompressor`（向量检索）或 `HybridCompressor` 而无需改动 runner。hermes-agent 的压缩器是具体类，无法热换。Anti-thrashing 机制也是新增的。

---

### 2.5 技能系统（Skill System）

| 维度 | hermes-agent | EvoScientist | AutoSci |
|------|-------------|--------------|---------|
| 技能格式 | Markdown + frontmatter | YAML/Markdown | Markdown + frontmatter |
| 注入位置 | **user message**（保留 prompt cache） | system prompt | system prompt（仅 name+description） |
| 技能发现 | Skills Hub + 安装命令 | 固定目录 | **多目录自动扫描：包内 builtin + `~/.autosci/skills/` + `./skills/`** |
| 运行时创建 | 不支持 | 不支持 | **`create_skill` 工具：agent 运行时自主创建新技能** |
| 内容注入粒度 | 全量内容 | 全量内容 | **仅注入 name+description；全文通过 `view_skill` 按需读取** |

**借鉴**：Markdown + YAML frontmatter 的技能文件格式来自 hermes-agent。  
**创新**：
1. **按需加载**：系统提示只注入技能摘要（name+description），避免 token 膨胀；agent 需要时调用 `view_skill` 读取全文。hermes-agent 和 EvoScientist 都是全量注入。
2. **`create_skill` 工具**：agent 可以在研究过程中发现有效流程并固化为新技能，实现自我进化。这在 hermes-agent 和 EvoScientist 中均无对应。
3. **内置技能打包**：`builtin_skills/` 随 pip 包分发（`package-data`），安装即可用，无需额外配置。

---

### 2.6 会话存储（Session Storage）

| 维度 | hermes-agent | ResearchClaw/OpenClaw | AutoSci |
|------|-------------|----------------------|---------|
| 格式 | SQLite（WAL + FTS5） | Markdown 文件 | **SQLite（WAL + FTS5）+ Markdown 自动导出** |
| 父子会话 | `parent_session_id` | 无 | `parent_session_id` |
| 搜索 | FTS5 全文检索 | 无 | FTS5 全文检索 |
| 人类可读性 | 低 | 高 | **两者兼顾** |

**借鉴**：SQLite + WAL + FTS5 方案来自 hermes-agent；Markdown 导出灵感来自 ResearchClaw/OpenClaw 的纯文件存储方案。  
**创新**：双轨存储——SQLite 负责快速查询和全文检索，Markdown 负责人类可读、git 友好的归档。两者由 `SessionStore` + `SessionExporter` 协作完成，`auto_export=True` 默认开启。

---

### 2.7 LLM 客户端（LLMClient）

| 维度 | hermes-agent | EvoScientist | AutoSci |
|------|-------------|--------------|---------|
| 底层框架 | 直接 OpenAI SDK | LangChain `init_chat_model` | 直接调 SDK（anthropic / openai） |
| 支持 provider | OpenAI-compat + Anthropic + Bedrock + Gemini | 10+ providers | **Anthropic 原生 + OpenAI-compat（代理友好）** |
| 辅助 LLM | 独立 `auxiliary_client`（用于压缩/视觉等） | 无 | 无（复用同一 client） |
| 消息格式统一 | 内部适配 | LangChain 统一 | **AutoSci 统一为 Anthropic 格式，openai 分支做转换** |

**借鉴**：双 provider 支持（anthropic + openai-compat）的架构思路来自 hermes-agent。  
**创新**：以 Anthropic 消息格式为**内部规范格式**，`_call_openai()` 负责把内部格式转换为 OpenAI 格式。这意味着上层代码统一写 Anthropic 风格，切换 provider 只改底层适配器，无需改 runner 或工具层。hermes-agent 反之（以 OpenAI 格式为主）。

---

### 2.8 ResearchClawBench 适配（bench.py）

| 维度 | 其他 agent | AutoSci |
|------|-----------|---------|
| 接入方式 | 修改 run_agent.py / 特化 CLI 参数 | **独立 `autosci-bench` CLI 命令** |
| 输出协议 | 各自实现 | **JSON Lines 到 stdout（event: start/agent_info/usage/done）** |
| report 兜底 | 无 | **若 agent 未写 report/report.md，自动将最终响应写入** |
| 安装方式 | 需配置路径 | `pip install -e .` 即注册 `autosci-bench` 命令 |

**创新**：`bench.py` 是针对 ResearchClawBench 协议设计的干净适配层，与核心 `cli.py` 完全解耦。benchmark 专用的提示增强（`_BENCH_ADDENDUM`）、结构化 stdout 输出、report 自动兜底均在适配层处理，不污染主框架逻辑。

---

## 三、创新点汇总

| # | 创新点 | 对应模块 | 相比参考项目 |
|---|-------|---------|------------|
| 1 | **Agent-agnostic runner**：主/子 agent 共用同一 runner 实例（共享 SessionStore/Memory/Skill） | `AgentRunner` | hermes-agent 子 agent 需独立实例 |
| 2 | **AgentRegistry 自注册**：新增 agent 仅需新建 `.py`，无需改核心代码或 YAML | `agents/registry.py` | hermes 硬编码，EvoScientist YAML 配 |
| 3 | **`_session_stack` 嵌套记忆保护**：委派嵌套时父 session 状态不被覆盖 | `MemoryManager` | hermes 用 hook 通知但仍有单点状态风险 |
| 4 | **三信号检索**（tag 0.4 + keyword 0.4 + recency 0.2）+ **tag 冲突检测** | `FileMemoryProvider` | hermes FTS5 全文；EvoScientist 全量注入 |
| 5 | **ContextEngine ABC**：压缩策略可插拔，不影响 runner | `context/engine.py` | hermes 压缩器是具体类，无抽象接口 |
| 6 | **Anti-thrashing**：压缩后冷却期，防止连续压缩 | `SummarizationCompressor` | hermes-agent 无此机制 |
| 7 | **技能按需加载**：system prompt 只注入摘要，全文按需 `view_skill` | `SkillEngine` | hermes/EvoScientist 全量注入 |
| 8 | **`create_skill` 工具**：agent 运行时自主创建新技能 | `skill_tools.py` | 所有参考项目均不支持 |
| 9 | **双轨存储**：SQLite（查询）+ Markdown 自动导出（可读/git 友好） | `SessionStore + SessionExporter` | hermes 仅 SQLite；OpenClaw 仅 Markdown |
| 10 | **Anthropic 格式为内部规范**：切换 provider 只改底层适配器 | `LLMClient` | hermes 以 OpenAI 格式为主 |
| 11 | **ResearchClawBench 干净适配层**（bench.py）：独立 CLI + JSON Lines + report 兜底 | `bench.py` | 其他 agent 无标准化适配协议 |

---

## 四、借鉴来源归属

| 来源 | 借鉴内容 |
|------|---------|
| **hermes-agent** | while-loop 结构、三区上下文压缩、`on_session_end` 反思 + `on_pre_compress` 救援、SQLite WAL+FTS5、技能 Markdown frontmatter 格式、双 provider LLM 架构 |
| **EvoScientist** | 5 subagent 研究分工思路（research/experiment/code/analysis/write）、experiment_conclusion 纳入记忆的设计理念 |
| **ResearchClaw / OpenClaw** | Markdown 文件存储方案（启发了双轨存储中的 Markdown 导出部分） |
| **认知科学标准** | episodic / semantic / procedural 三类记忆的分类框架 |

---

## 五、一句话定位

> **AutoSci = hermes-agent 的极简 while-loop 架构 × 面向科研的 5-subagent 分工 × 可插拔压缩/记忆/技能 × 开箱即用的 ResearchClawBench 适配**  
>  
> 核心设计哲学：**minimal, decoupled, extensible**——每个模块都可以独立替换，主 runner 对 agent、工具、LLM provider 均无硬依赖。
