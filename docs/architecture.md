# AutoSci 架构文档

> 版本：v0.3.0
> 更新：2026-04-28

---

## 目录

1. [整体架构](#1-整体架构)
2. [目录结构](#2-目录结构)
3. [执行模式](#3-执行模式)
4. [核心执行引擎](#4-核心执行引擎)
5. [Agent 体系](#5-agent-体系)
6. [任务理解系统](#6-任务理解系统)
7. [工具系统](#7-工具系统)
8. [Workflow 引擎](#8-workflow-引擎)
9. [Trajectory 系统](#9-trajectory-系统)
10. [记忆系统](#10-记忆系统)
11. [上下文压缩](#11-上下文压缩)
12. [技能系统](#12-技能系统)
13. [配置系统](#13-配置系统)
14. [入口点](#14-入口点)

---

## 1. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                        Entry Points                          │
│     autosci (CLI/REPL)      autosci-bench (benchmark)        │
└───────────────────────┬──────────────────────────────────────┘
                        │ _bootstrap() + config
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                    Task Understanding                        │
│   TaskUnderstanding → TaskUnderstandingAgent → TaskPlan      │
│   (goal / ResearchQuestions / Claims / suggested_agents)     │
└───────────────────────┬──────────────────────────────────────┘
                        │ task + TaskPlan
          ┌─────────────┴─────────────┐
          ▼                           ▼
  Agent-driven mode           Workflow-driven mode
  MainAgent runs              WorkflowEngine phases
  free-form research          agent-per-phase pipeline
          │                           │
          └─────────────┬─────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                      AgentRunner                             │
│  LLMClient │ PromptBuilder │ ContextEngine │ MemoryManager   │
│  ToolRegistry │ SkillEngine │ TrajectoryRecorder             │
│  ─────────────────────────────────────────────────────────── │
│  while-loop: LLM call → tool dispatch → tool results → ...   │
└──────────────────────────────────────────────────────────────┘
```

设计哲学：**minimal, decoupled, extensible**

- `AgentRunner` 是唯一执行引擎，对 agent 类型、工具集、LLM provider 均无硬依赖
- 所有子系统通过接口（ABC）或注册表解耦，可独立替换
- 主 agent 委派子 agent 时，调用同一个 runner 实例的 `run()`，共享所有子系统

---

## 2. 目录结构

```
src/autosci/
├── agents/
│   ├── base.py              # BaseAgent ABC
│   ├── registry.py          # AgentRegistry（YAML 自发现）
│   ├── dynamic_agent.py     # DynamicAgent（YAML → 实例）
│   ├── main_agent.py        # MainAgent（编排者，Python 实现）
│   └── templates/           # 内置 YAML agent 定义（开箱即用）
│       ├── researcher.yaml
│       ├── analyst.yaml
│       ├── coder.yaml
│       ├── writer.yaml
│       └── experiment.yaml
│
├── task/
│   ├── schemas.py           # TaskPlan / Claim / ResearchQuestion
│   ├── agent.py             # TaskUnderstandingAgent
│   └── understanding.py     # TaskUnderstanding（编排入口）
│
├── workflow/
│   ├── schemas.py           # WorkflowDef / PhaseSpec / WorkflowResult
│   ├── engine.py            # WorkflowEngine（拓扑调度）
│   └── templates/           # 内置 workflow YAML 定义
│       ├── reproduce.yaml
│       └── survey.yaml
│
├── runtime/
│   ├── runner.py            # AgentRunner（核心 while-loop）
│   ├── llm_client.py        # LLM 调用（anthropic / openai-compat）
│   ├── prompt_builder.py    # system prompt 拼装
│   ├── error_handler.py     # 错误分类 + 指数退避重试
│   └── repl.py              # 交互式 TUI REPL
│
├── tools/
│   ├── registry.py          # ToolRegistry（自注册）
│   ├── file_tools.py        # read_file / write_file / list_dir / glob / grep
│   ├── terminal_tool.py     # execute_command
│   ├── web_tools.py         # web_search / web_fetch
│   ├── agent_tools.py       # delegate / create_agent / ask_user / update_claim
│   ├── memory_tools.py      # store_memory / recall_memory
│   └── skill_tools.py       # list_skills / view_skill / create_skill
│
├── trajectory/
│   ├── schemas.py           # AgentSpan / TrajectoryEvent
│   ├── recorder.py          # TrajectoryRecorder（events.jsonl + spans.json）
│   └── exporter.py          # 导出为可读报告
│
├── memory/
│   ├── provider.py          # MemoryProvider ABC + MemoryEntry
│   ├── manager.py           # MemoryManager（生命周期协调）
│   └── file_provider.py     # FileMemoryProvider（文件系统存储）
│
├── context/
│   ├── engine.py            # ContextEngine ABC
│   └── compressor.py        # SummarizationCompressor（三区压缩）
│
├── skills/
│   └── engine.py            # SkillEngine（发现 + 匹配 + 创建）
│
├── storage/
│   ├── session_store.py     # SessionStore（SQLite WAL + FTS5）
│   └── exporter.py          # SessionExporter（Markdown 导出）
│
├── protocols/
│   └── schemas.py           # RunContext / RunResult / LLMResponse 等
│
├── configs/
│   └── default.py           # 默认配置 + YAML 加载（deep merge）
│
├── builtin_skills/          # 内置技能（随 pip 包分发）
│   ├── literature_review.md
│   ├── experiment_design.md
│   └── data_analysis.md
│
├── cli.py                   # autosci 命令入口
└── bench.py                 # autosci-bench 命令入口（benchmark 适配）
```

---

## 3. 执行模式

autosci 支持两种顶层模式，共享同一套 AgentRunner 基础设施：

### 3.1 Assistant 模式（默认）

个人 AI 助手，轻量工具集，无 workspace 概念，专注于学习用户习惯：

```
autosci                   ← 交互式 REPL（绿色 banner）
autosci "what is X"       ← 单次执行

Agent: AssistantAgent（14 个工具，无 delegate/create_agent/update_claim）
Memory: ~/.autosci/memory/  ← 全局记忆
Reflection: 偏向提取用户习惯、偏好、常用工具
```

### 3.2 Scientist 模式（原 task 模式）

研究任务模式，workspace 感知，子 agent 编排，支持 workflow pipeline：

```
autosci scientist "reproduce X" -w ./workspace

Agent: MainAgent（所有工具，含 delegate/create_agent/update_claim）
Workspace: ./workspace/
└── .autosci/             ← 框架内部文件（sessions.db, trajectory/, memory/）
    ├── sessions.db
    ├── trajectory/
    ├── memory/
    │   ├── episodic/
    │   ├── semantic/
    │   └── procedural/
    └── sessions/
data/                     ← 用户可见研究目录（在 workspace 根）
code/
outputs/
report/images/
```

#### Agent-driven 子模式（默认）

```
TaskUnderstanding → TaskPlan
        ↓
MainAgent.run(task + task_plan.to_prompt_block())
        ↓
  自由规划研究流程：survey → plan → implement → analyze → report
  按需 delegate 子 agent，用 update_claim 更新 Claim 状态
```

#### Workflow-driven 子模式（`--workflow <name>`）

```
TaskUnderstanding → TaskPlan
        ↓
WorkflowEngine.run(workflow_def, task, task_plan)
        ↓
  按 phases 拓扑顺序调度：每个 phase 指定 agent + goal
  上游 phase 输出 + TaskPlan 注入下游 phase 的 task 字符串
```

适合结构固定的研究流程（如复现论文、文献综述），可通过 YAML 定制 pipeline。

内置 workflow 模板：

| 模板 | phases | 适用场景 |
|------|--------|----------|
| `reproduce` | literature → implementation → experiment → analysis → report | 论文复现 |
| `survey` | scope → deep_read → synthesis → report | 文献综述 |

---

## 4. 核心执行引擎

### 4.1 AgentRunner（`runtime/runner.py`）

系统中枢。`run(agent, task)` 接受任意 `BaseAgent` 子类，驱动完整的 while-loop：

```
runner.run(agent, task)
│
├── 初始化：session_store, context_engine, memory_manager, skill_engine, trajectory
├── 检索相关记忆 → memory_block（top-10，三信号评分）
├── 匹配相关技能 → skills_block（top-3，只注入摘要）
├── PromptBuilder.build_system_prompt(agent, ...)
├── tool_defs = tool_registry.get_definitions(agent.tools)
│
└── for iteration in range(max_iterations):
    ├── LLMClient.chat(messages, system_prompt, tool_defs)
    ├── 无 tool_calls → RunResult(status="completed") → _finalize_session()
    ├── 有 tool_calls:
    │   ├── name in _RUNNER_TOOLS → runner 直接处理（见下）
    │   └── 其他 → tool_registry.dispatch(name, args)
    └── context_engine.should_compress() → 三区压缩
```

**Runner 拦截工具（`_RUNNER_TOOLS`）**：

这些工具向 LLM 暴露 schema（在工具列表中可见），但执行时由 runner 处理，不经过 ToolRegistry：

| 工具 | 作用 |
|------|------|
| `delegate` | 以子 agent 身份调用 `self.run(child_agent, task)`，共享 runner 状态 |
| `create_agent` | 内联定义并立即运行一个临时 agent |
| `ask_user` | 暂停执行，从 stdin 读取用户输入 |
| `update_claim` | 读取 `task_plan.json` → 更新 Claim 状态 → 写回 → 记录 trajectory 事件 |

### 4.2 委派（Delegation）

```
主 agent 调用 delegate(agent="researcher", task="...")
        ↓
runner._handle_delegate()
  ├── agent_registry.get("researcher") → DynamicAgent 实例
  └── self.run(agent, task, parent_context=context)
      ├── session_store.create_session(parent_session_id=parent_sid)
      ├── [子 agent 完整 while-loop]
      └── _finalize_session() → 返回 child_result.response 给主 agent

主 agent 收到子 agent 结果，继续下一轮迭代（串行）
```

### 4.3 LLMClient（`runtime/llm_client.py`）

内部统一使用 Anthropic 消息格式。支持两种 provider：

- `anthropic`：调用 Anthropic SDK，原生格式
- `openai`：调用 OpenAI-compatible API（代理、本地 LLM 等），内部转换格式

切换 provider 只改配置，runner 和 agent 无感知。

---

## 5. Agent 体系

### 5.1 层次结构

```
BaseAgent (ABC)
    ├── AssistantAgent     — Python 实现，个人助手 system prompt，限定 14 个工具
    ├── MainAgent          — Python 实现，动态 system prompt（含子 agent 列表）
    ├── TaskUnderstandingAgent  — Python 实现，产出 TaskPlan
    └── DynamicAgent       — YAML 驱动，system_prompt 静态字符串
            ├── researcher
            ├── analyst
            ├── coder
            ├── writer
            └── experiment
```

**什么时候用 Python 实现，什么时候用 YAML？**

- YAML：system prompt 是静态字符串，工具列表固定 → 绝大多数子 agent
- Python：需要运行时动态生成 system prompt（如注入子 agent 列表、workspace 状态）→ MainAgent、AssistantAgent、TaskUnderstandingAgent

### 5.2 AssistantAgent

| 属性 | 值 |
|------|-----|
| `name` | `"assistant"` |
| `tools` | `["read_file", "write_file", "list_dir", "glob", "grep", "execute_command", "web_search", "web_fetch", "store_memory", "recall_memory", "list_skills", "view_skill", "create_skill", "ask_user"]`（14 个）|
| `max_iterations` | `50` |

System prompt 侧重个人助手风格：帮助日常任务、学习用户习惯与偏好、直接执行（不必要时不询问）。无 `delegate`、`create_agent`、`update_claim`（助手模式不编排子 agent）。

Memory reflection 偏向提取：用户偏好、工作习惯、常用工具、个人语境。

### 5.3 MainAgent（Scientist 模式）

| 属性 | 值 |
|------|-----|
| `name` | `"main"` |
| `tools` | `[]`（空 = 无限制，访问所有工具）|
| `max_iterations` | `100` |

System prompt 包含：工作区布局说明（含 `.autosci/` 内部目录）、6 步研究工作流（Understand → Survey → Plan → Implement → Analyze → Report）、所有工具使用指南、Claim 驱动研究的核心原则。

Memory reflection 偏向提取：研究发现、实验结果、有效方法论。

子 agent 列表中自动排除 `assistant` 和 `task_understanding`（内部 agent，不对主 agent 暴露）。

### 5.4 内置子 Agent（YAML）

| Agent | 额外工具 | max_iter | 职责 |
|-------|----------|----------|------|
| `researcher` | `web_search`, `web_fetch` | 30 | 文献搜索、论文阅读、知识综述 |
| `analyst` | `web_search`, `web_fetch` | 35 | 数据分析、统计测试、可视化 |
| `coder` | — | 40 | 代码实现、调试、测试 |
| `writer` | `web_search`, `web_fetch` | 25 | 科学写作、报告撰写 |
| `experiment` | — | 30 | 实验设计、参数选择、方法规划 |

所有子 agent 均有 `read_file / write_file / list_dir / glob / grep / execute_command`。

### 5.5 AgentRegistry（`agents/registry.py`）

两种注册方式：

```python
# 1. Python class（MainAgent 等）
agent_registry.register(MainAgent)

# 2. YAML（DynamicAgent，_bootstrap 中自动加载）
agent_registry.discover_yaml()
```

`discover_yaml()` 加载顺序（后者可覆盖同名 agent）：

```
1. src/autosci/agents/templates/*.yaml   ← 内置，开箱即用
2. ~/.autosci/agents/*.yaml              ← 用户自定义/覆盖
3. extra_dirs（调用方传入）
```

**扩展方式：**

- 只需配置：在 `~/.autosci/agents/` 写一个 YAML，下次启动自动注册
- 需要逻辑：继承 `BaseAgent`，实现 `get_system_prompt()`，末尾调用 `agent_registry.register(MyAgent)`

---

## 6. 任务理解系统

### 6.1 数据结构（`task/schemas.py`）

```
TaskPlan
├── raw_task: str              原始任务字符串
├── mode: str                  "topic_only" | "task_given"
├── goal: str                  一句话核心目标
├── context: TaskContext       研究对象 / 数据类型 / 已知方法 / 关键词
├── related_works: [RelatedWork]   文献：贡献 + 证据 + 边界/gap
├── research_questions: [ResearchQuestion]   可回答的问题（来自 gap）
├── claims: [Claim]            可验证的假设（核心研究命题）
│       └── status: unverified | supported | refuted | partial
└── suggested_agents: [str]    建议使用的子 agent 名称
```

**Claim 是研究议程的核心**：TaskUnderstanding 生成，MainAgent 通过 `update_claim` 工具在实验完成后更新状态（写回 `task_plan.json`，记录 trajectory 事件）。

### 6.2 执行流程

```
TaskUnderstanding(runner, workspace).analyze(task)
│
├── detect_mode(task)
│   ├── "topic_only"：任务较短且无方法关键词 → 偏向文献综述
│   └── "task_given"：明确指定方法/目标 → 偏向实现/复现
│
├── 实例化 TaskUnderstandingAgent
│   └── system prompt 包含：任务字符串 + workspace 现有文件列表
│
├── runner.run(agent, task)     ← 完整 agent loop，可调用 web_search 等工具
│
└── 解析 agent 输出 JSON → TaskPlan
    └── save_task_plan(plan, workspace)  → workspace/task_plan.json
```

### 6.3 任务计划注入

两种模式均注入 TaskPlan：

- **Agent-driven**：`full_task = task + "\n\n" + task_plan.to_prompt_block()`
- **Workflow-driven**：每个 phase 的 task 字符串中都插入 `task_plan.to_prompt_block()`

---

## 7. 工具系统

### 7.1 注册机制

```python
# 模块级，import 时自动执行
registry.register("read_file", READ_FILE_SCHEMA, read_file, toolset="file")
```

schema 是 Anthropic tool schema 格式（JSON Schema），直接传给 LLM。agent 的 `tools` 列表控制哪些工具对其可见。

### 7.2 工具列表（17 个）

| 类别 | 工具 | 说明 |
|------|------|------|
| **file** | `read_file` | 读取文件内容 |
| | `write_file` | 写入/创建文件 |
| | `list_dir` | 列出目录内容 |
| | `glob` | 文件名模式匹配 |
| | `grep` | 正则搜索文件内容 |
| **terminal** | `execute_command` | 执行 shell 命令 |
| **web** | `web_search` | 网络搜索 |
| | `web_fetch` | 抓取网页正文 |
| **agent** | `delegate` | 委派子 agent（runner 拦截）|
| | `create_agent` | 内联定义并运行临时 agent（runner 拦截）|
| | `ask_user` | 向用户提问（runner 拦截）|
| | `update_claim` | 更新 Claim 验证状态（runner 拦截）|
| **memory** | `store_memory` | 手动存入记忆 |
| | `recall_memory` | 手动检索记忆 |
| **skill** | `list_skills` | 列出所有技能 |
| | `view_skill` | 读取技能全文 |
| | `create_skill` | 运行时创建新技能 |

---

## 8. Workflow 引擎

### 8.1 YAML 定义格式

```yaml
name: reproduce
description: "Paper reproduction pipeline"
phases:
  - id: literature
    agent: researcher
    goal: "Read and summarize the target paper..."
  - id: implementation
    agent: coder
    goal: "Implement the algorithm described..."
    depends_on: [literature]
  - id: experiment
    agent: experiment
    goal: "Run experiments and record results..."
    depends_on: [implementation]
  - id: analysis
    agent: analyst
    goal: "Analyze results and compare with paper..."
    depends_on: [experiment]
  - id: report
    agent: writer
    goal: "Write the reproduction report..."
    depends_on: [analysis]
```

### 8.2 WorkflowEngine

```
WorkflowEngine.run(workflow_def, task, task_plan)
│
├── topological_order()    ← 处理 depends_on，确保执行顺序
│
└── for phase in phases:
    ├── 检查依赖是否失败 → 跳过（skip）
    ├── agent_registry.get(phase.agent)
    ├── _build_phase_task(task, phase, upstream_results, task_plan)
    │   └── task + task_plan.to_prompt_block() + phase.goal + 上游结果摘要
    └── runner.run(agent, phase_task)
        └── PhaseResult(status, output, tokens, tool_calls)
```

Phase 状态：`completed` / `error` / `skipped`（依赖失败时）

整体状态：所有完成 → `completed`；全部失败 → `failed`；部分 → `partial`

---

## 9. Trajectory 系统

### 9.1 结构

```
workspace/trajectory/
├── events.jsonl    ← 追加写入的事件流（每个 tool call、agent 动作等）
└── spans.json      ← 结构化的 agent 执行段
```

### 9.2 事件类型

| event_type | 触发时机 |
|------------|----------|
| `workflow_start` | WorkflowEngine 开始 |
| `task_plan` | TaskUnderstanding 完成，保存整个 TaskPlan |
| `agent_start` / `agent_end` | runner.run() 进入/退出 |
| `tool_call` / `tool_result` | 每次工具调用 |
| `claim_update` | update_claim 执行，记录 old_status → new_status + evidence |
| `llm_call` | 每次 LLM 请求（含 token 计数）|

`claim_update` 事件是研究进度的核心审计轨迹：记录每条 Claim 从 `unverified` 到最终状态的完整证据链。

---

## 10. 记忆系统

### 10.1 架构

```
MemoryManager
    └── FileMemoryProvider
            └── workspace/.autosci/memory/（scientist 模式）或 ~/.autosci/memory/（assistant 全局）
                ├── episodic/    mem_*.md   （发生了什么）
                ├── semantic/    mem_*.md   （学到了什么知识）
                ├── procedural/  mem_*.md   （怎么做更有效）
                └── index.json
```

### 10.2 三个触发时机

| 时机 | 触发条件 | 动作 |
|------|----------|------|
| session 开始 | 每次 `runner.run()` | 检索相关记忆注入 system prompt |
| 压缩前 | `on_pre_compress()` | 扫描即将被压缩的 tool_result，发现错误/异常 → 存 episodic 记忆 |
| session 结束 | status == "completed" | LLM 反思整个历史，提取 ≤5 条记忆写入文件（assistant 模式：提取用户习惯；scientist 模式：提取研究发现）|

### 10.3 检索评分

```
score = tag_score × 0.4 + keyword_score × 0.4 + recency_score × 0.2

tag_score     = |query_keywords ∩ mem_tags| / |query_keywords|
keyword_score = 在 summary 中匹配的关键词数 / 总关键词数
recency_score = exp(-age / 7天)
```

### 10.4 冲突检测

新存 semantic/procedural 记忆时，若与已有记忆 tag Jaccard 相似度 > 80%，更新已有记忆而非新建。

---

## 11. 上下文压缩

### 触发条件

```
prompt_tokens > context_window × 0.75
AND 最近 2 次压缩节省率不都 < 10%（防止 thrashing）
```

### 压缩流程

```
Step 1：预剪枝
  非最近 6 条消息中，tool_result 超 500 字 → 截断

Step 2：三区分割
  HEAD（保护）= 前 2 条（原始任务 + 第一次响应）
  TAIL（保护）= 末尾累积到 context_window × 0.3 为止
  MIDDLE      = 中间区（待压缩）

Step 3：LLM 摘要 MIDDLE
  失败时 fallback：截取前 10 行 + 后 10 行

Step 4：重组
  result = HEAD + [summary_msg] + TAIL
```

---

## 12. 技能系统

### 技能文件格式

```markdown
---
name: literature_review
description: Systematic process for searching and synthesizing scientific literature
tags: [literature, search, papers, review, synthesis]
---

## Literature Review Procedure
1. ...
```

### 发现顺序

```
builtin_skills/（内置，随 pip 分发）
~/.autosci/skills/（用户全局）
./skills/（项目级）
```

同名技能后扫描覆盖先扫描（用户可覆盖内置）。

### 注入方式

- **system prompt**：只注入 `name + description`（节省 token）
- **全文**：agent 调用 `view_skill` 按需读取

### 运行时创建

agent 调用 `create_skill` → 写入 `~/.autosci/skills/` → 当前 session 立即可用 → 下次 session 自动发现。

---

## 13. 配置系统

### 加载顺序（deep merge）

```
代码默认值 → ~/.autosci/config.yaml → ./autosci.yaml → 命令行 overrides
```

### 主要配置项

```yaml
llm:
  provider: openai          # anthropic | openai
  model: gpt-4o
  api_key_env: OPENAI_API_KEY
  base_url: ~               # openai-compatible 端点，留空则用官方

runtime:
  context_window: 200000
  compression_threshold: 0.75

memory:
  base_dir: ~/.autosci/memory/

storage:
  db_path: ~/.autosci/sessions.db
  auto_export: true
  export_dir: ./sessions/

skills:
  include_builtin: true
  dirs: [~/.autosci/skills/, ./skills/]

scientist:
  workspace: ~              # scientist 模式工作目录
  enable_trajectory: true
  enable_understanding: true
```

---

## 14. 入口点

### `autosci`（`cli.py`）

```bash
# 助手模式（默认，AssistantAgent，绿色 TUI）
autosci                              # 交互式 REPL
autosci "what is X"                  # 单次执行

# 科学家模式（MainAgent，蓝色 TUI）
autosci scientist "reproduce X" -w ./workspace
autosci scientist --from-file task.md -w ./workspace
autosci scientist "..." -w ./workspace --workflow reproduce

# 管理命令
autosci --init                       # 初始化 ~/.autosci/
autosci workflow list                # 列出可用 workflow
autosci workflow show reproduce      # 查看 workflow phases
autosci agent list                   # 列出已注册 agent
autosci agent add researcher         # 安装内置模板到 ~/.autosci/agents/
```

**科学家模式执行流程：**

```
_bootstrap()          ← 注册所有工具 + agent（含 YAML 内置模板）
load_config()
_init_scientist_workspace(workspace)
  ├── workspace/.autosci/{trajectory,memory/*,sessions}/
  └── workspace/{data,code,outputs,report/images}/
TaskUnderstanding.analyze(task)   ← 生成 TaskPlan，保存 .autosci/task_plan.json
        ↓
  --workflow?
  ├── 是 → WorkflowEngine.run(workflow_def, task, task_plan)
  └── 否 → runner.run(MainAgent, task + task_plan)
```

### `autosci-bench`（`bench.py`）

ResearchClawBench 评测适配器：

```bash
autosci-bench -m <PROMPT> -w <WORKSPACE>
```

- 与 `cli.py` 的 `_bootstrap()` 保持同步
- 追加 benchmark 专用提示（workspace 布局要求、报告格式）
- JSON Lines 输出到 stdout（`event: start / agent_info / usage / done`）
- 兜底：若未生成 `report/report.md`，自动写入最终响应

```json
{"event": "start", "agent": "autosci", "task": "..."}
{"event": "done", "status": "completed", "tokens": 12345}
```
