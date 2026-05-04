# AutoSci 改进方案：AI 科学家基座

> 设计日期：2026-04-27  
> 状态：待评审

---

## 一、新定位

**AutoSci** 是一个面向科研任务的 **AI 科学家基座（Research Agent Platform）**，提供两种工作模式：

- **Assistant 模式**：轻量对话助手，完成日常问答和小任务
- **Research Task 模式**：完整科研 Agent，支持长周期任务、结构化轨迹记录、自组织 subagent

核心设计原则：**任务驱动、可观测、可扩展、可复现**。

---

## 二、当前主要缺陷

| 问题 | 具体表现 |
|------|---------|
| 无任务理解层 | 主 agent 直接把 task 字符串扔给 LLM，没有结构化拆解 |
| 轨迹不可查 | 只有 SQLite messages + Markdown 导出，无法看清"哪个 subagent 做了什么、产出了什么" |
| subagent 写死 | 5 个固定子 agent，无法动态定义或注册新的 |
| 工作流写死 | 主 agent 靠 LLM 自由发挥，没有可定义的工作流结构 |
| 记忆全局共享 | 所有 session 共用 `~/.autosci/memory/`，科研任务和日常助手记忆混在一起 |
| 无 workspace 概念 | task 运行时没有专属目录，实验数据散落各处 |
| 记忆质量差 | episodic 中 74% 是低价值 warning，`_rescue_from_messages` 过于粗暴 |

---

## 三、改进模块设计

### 3.1 任务理解模块（Task Understanding）

**目标**：在任务执行前，对任务进行结构化拆解，生成可追踪的目标列表。

**新增文件**：`src/autosci/task/understanding.py`

```python
@dataclass
class TaskPlan:
    raw_task: str           # 原始任务描述
    goal: str               # 核心目标（一句话）
    claims: list[str]       # 需要验证/实现的核心 claim 列表
    subtasks: list[Subtask] # 分解后的子任务
    suggested_agents: list[str]  # 建议调用的 subagent
    estimated_phases: list[str]  # 预估执行阶段

@dataclass
class Subtask:
    id: str
    description: str
    depends_on: list[str]   # 依赖其他 subtask 的 id
    suggested_agent: str
    expected_output: str    # 期望产出描述
```

**触发时机**：Research Task 模式启动时，主 agent 第一步必须调用 `TaskUnderstanding.analyze(task)` → 生成 `TaskPlan` → 持久化到 `workspace/task_plan.json` → 注入到主 agent system prompt。

**实现方式**：独立 LLM 调用（不走 while-loop），structured output prompt，要求输出 JSON。

---

### 3.2 轨迹记录系统（Trajectory）

**目标**：结构化记录每次实验的完整执行过程，人工可查阅。

**新增文件**：`src/autosci/trajectory/`

```
trajectory/
├── recorder.py      # TrajectoryRecorder：写入轨迹
├── schemas.py       # 轨迹数据结构
└── exporter.py      # 导出为 Markdown / JSON
```

**数据结构**：

```python
@dataclass
class TrajectoryEvent:
    event_type: str        # agent_start / agent_end / tool_call / tool_result
                           # delegation_start / delegation_end / compression / memory_store
    timestamp: str
    session_id: str
    agent_name: str
    data: dict             # 事件具体内容

@dataclass
class AgentSpan:
    span_id: str
    parent_span_id: str    # 委派链
    agent_name: str
    task: str
    started_at: str
    ended_at: str
    status: str
    tool_calls: list[ToolCallRecord]  # 按顺序记录每次工具调用
    input_context: str     # 系统提示摘要（前500字）
    output: str            # 最终响应
    token_usage: TokenUsage
    memories_loaded: list[str]   # 启动时加载的记忆 id
    memories_stored: list[str]   # 本次存入的记忆 id

@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    result_summary: str    # 结果前300字
    duration_ms: int
    timestamp: str
```

**存储**：`workspace/trajectory/`
- `trajectory.jsonl`：按时间顺序的事件流（每行一个 JSON event，方便流式查看）
- `spans.json`：所有 AgentSpan 的结构化汇总
- `trajectory.md`：人类可读的 Markdown 报告（自动生成）

**Markdown 格式示例**：

```markdown
# Task Trajectory — 2026-04-27 15:30

## Task Plan
**Goal**: ...
**Claims**: 1. ... 2. ...

## Execution Timeline

### [15:30:01] MainAgent started
- Task: "analyze energy storage scenarios..."
- Memory loaded: 3 relevant memories
- Suggested agents: [research, code, analysis]

### [15:30:45] → Delegated to ResearchAgent
- Task: "survey energy storage literature"
- Duration: 4m 32s
- Tool calls: read_file × 3, web_fetch × 2
- Output summary: "Found 5 relevant papers..."

### [15:35:17] → Delegated to CodeAgent
...
```

**集成点**：在 `AgentRunner` 的 `run()` 和 `_handle_delegate()` 中注入 `TrajectoryRecorder`，每个关键操作调用 `recorder.record(event)`。

---

### 3.3 自组织 subagent（Dynamic Agent Registry）

**目标**：支持用户自定义新的 subagent，无需修改代码。

**两种注册方式**：

#### 方式 A：YAML 文件定义（推荐，用户友好）

`workspace/agents/my_agent.yaml` 或 `~/.autosci/agents/my_agent.yaml`：

```yaml
name: domain_expert
role: "Domain expert for energy systems analysis"
tools: [read_file, write_file, execute_command, web_search]
max_iterations: 40
system_prompt: |
  # Domain Expert Agent
  You are an expert in energy systems...
  ## Your responsibilities:
  - ...
```

`AgentRegistry.discover_yaml(dirs)` 自动扫描并注册为 `DynamicAgent` 实例。

#### 方式 B：CLI 命令注册

```bash
autosci agent add \
  --name "domain_expert" \
  --role "Energy systems domain expert" \
  --tools "read_file,write_file,web_search" \
  --prompt-file ./my_prompt.md
```

写入 `~/.autosci/agents/domain_expert.yaml`，下次启动自动加载。

#### 方式 C：运行时注册（agent 自主创建）

新增工具 `create_agent`，主 agent 可以在任务过程中动态定义新 subagent：

```python
create_agent(
    name="energy_modeler",
    role="...",
    tools=["execute_command", "read_file", "write_file"],
    system_prompt="..."
)
```

---

### 3.4 工作流定义（Workflow）

**目标**：支持定义结构化工作流，主 agent 按流程编排，而非完全自由发挥。

**新增文件**：`src/autosci/workflow/`

```yaml
# workspace/workflow.yaml 或内置工作流
name: research_paper_reproduction
description: Reproduce results from a research paper

phases:
  - id: understand
    agent: main
    task_template: "Analyze the task and create a research plan: {task}"
    outputs: [task_plan.json]

  - id: literature
    agent: research
    task_template: "Survey related work for: {goal}"
    depends_on: [understand]
    outputs: [literature_review.md]

  - id: implement
    agent: code
    task_template: "Implement the method described in: {literature_review}"
    depends_on: [literature]
    outputs: [code/]

  - id: experiment
    agent: experiment
    task_template: "Run experiments and record results"
    depends_on: [implement]
    outputs: [outputs/]

  - id: analyze
    agent: analysis
    task_template: "Analyze experiment results"
    depends_on: [experiment]
    outputs: [analysis_report.md]

  - id: write
    agent: write
    task_template: "Write final report"
    depends_on: [analyze]
    outputs: [report/report.md]
```

**执行方式**：`WorkflowEngine` 解析 phases → 按依赖顺序调度 → 每个 phase 通过 `runner.run(agent, task)` 执行 → phase 产出作为下一 phase 的上下文输入。

---

### 3.5 双模式（Assistant vs Research Task）

**Assistant 模式**（默认）：

```bash
autosci                        # 进入 REPL，助手模式
autosci "帮我解释一下这段代码"  # 单次助手任务
```

- 轻量 system prompt（普通助手角色）
- 记忆来自 `~/.autosci/memory/`（全局）
- 不启动 TaskUnderstanding，不记录 Trajectory
- 无 workspace 概念

**Research Task 模式**：

```bash
autosci task "Reproduce the results of paper X" --workspace ./exp_001
autosci task --from-file task.md --workspace ./exp_001
autosci task --benchmark researchclawbench --task-id Math_003 --workspace ./exp_001
```

- 指定 workspace（必须），所有数据写入 workspace
- 启动 TaskUnderstanding → 生成 task_plan.json
- 记录完整 Trajectory
- 记忆隔离到 `workspace/memory/`（不与 assistant 混合）
- 可通过 `--share-memory` 参数让 task 记忆与全局记忆共享
- workspace 目录结构：

```
workspace/
├── task_plan.json          # 任务理解结果
├── trajectory/
│   ├── trajectory.jsonl    # 事件流
│   ├── spans.json          # agent 执行跨度
│   └── trajectory.md       # 人类可读报告
├── memory/                 # 任务专属记忆
│   ├── episodic/
│   ├── semantic/
│   └── procedural/
├── data/                   # 输入数据
├── code/                   # 生成代码
├── outputs/                # 中间产出
├── report/                 # 最终报告
│   ├── report.md
│   └── images/
└── sessions/               # session Markdown 导出
```

---

### 3.6 记忆质量改进

**问题**：episodic 中 74% 是低价值 warning 噪音。

**改进**：

1. `_rescue_from_messages` 严格过滤：
   - 只保留真正的 `Exception`/`Error`，过滤掉 `Warning`/`DeprecationWarning`
   - 同一 session 同类错误去重（同前缀只存一条）
   - 最小内容长度 200 字（过短的不存）

2. LLM 反思提示词改进：明确区分三类记忆，提高提取门槛，要求"只保留对未来其他任务有价值的内容"

3. Task 模式下：episodic 记忆自动关联 task_id，便于按任务检索

---

## 四、实现计划

### Phase A：Trajectory 系统（最高优先级）

**原因**：这是"可观测性"的基础，其他改进都依赖它。

1. `src/autosci/trajectory/schemas.py` — TrajectoryEvent / AgentSpan / ToolCallRecord
2. `src/autosci/trajectory/recorder.py` — TrajectoryRecorder（写 jsonl）
3. `src/autosci/trajectory/exporter.py` — 导出 Markdown 报告
4. 修改 `runner.py`：在 run() / _handle_delegate() / tool dispatch 中注入 recorder

---

### Phase B：双模式 + Workspace（次高优先级）

1. `src/autosci/task/understanding.py` — TaskUnderstanding（LLM 结构化拆解）
2. 修改 `cli.py`：添加 `autosci task` 子命令，处理 workspace 初始化
3. 修改 `AgentRunner`：接受 `workspace` 参数，切换记忆/存储路径
4. Workspace 目录初始化逻辑

---

### Phase C：自组织 subagent

1. `src/autosci/agents/dynamic_agent.py` — DynamicAgent（从 YAML 加载）
2. 修改 `AgentRegistry.discover()`：扫描 YAML 文件
3. `cli.py` 添加 `autosci agent add` 子命令
4. 新增 `create_agent` 工具（runner 拦截）

---

### Phase D：工作流引擎

1. `src/autosci/workflow/schema.py` — WorkflowDef / Phase 数据结构
2. `src/autosci/workflow/engine.py` — WorkflowEngine（解析 + 调度）
3. `cli.py` 添加 `autosci task --workflow workflow.yaml`
4. 内置 3 个科研工作流模板

---

### Phase E：记忆质量优化

1. 改进 `_rescue_from_messages` 过滤逻辑
2. 改进 LLM 反思提示词
3. Task 模式记忆隔离

---

## 五、CLI 接口汇总（改进后）

```bash
# Assistant 模式（现有，保持）
autosci                              # REPL
autosci "task"                       # 单次
autosci --init                       # 初始化工作目录

# Research Task 模式（新增）
autosci task "reproduce paper X" --workspace ./exp_001
autosci task --from-file task.md --workspace ./exp_001
autosci task --workflow research.yaml --workspace ./exp_001
autosci task --benchmark rcb --task-id Math_003 --workspace ./exp_001

# Agent 管理（新增）
autosci agent list                   # 列出所有可用 agent
autosci agent add --name X --role Y --tools a,b --prompt-file p.md
autosci agent remove --name X

# 轨迹查看（新增）
autosci trajectory show ./exp_001    # 查看 workspace 的轨迹报告
autosci trajectory list              # 列出所有历史 task
```

---

## 六、关键设计决策

| 决策点 | 选择 | 理由 |
|-------|------|------|
| Trajectory 存储格式 | JSONL（事件流）+ JSON（spans）+ MD（可读） | JSONL 支持流式追加；MD 方便人工查阅 |
| Task 记忆隔离 | workspace/memory/ 独立目录 | 避免污染全局助手记忆；通过 --share-memory 选择性共享 |
| YAML agent 定义 | 支持，优先于代码注册 | 用户无需改代码即可扩展 |
| 工作流执行 | 串行 phase（依赖驱动） | 当前 runner 串行，保持一致；未来可升级并行 |
| TaskUnderstanding | 独立 LLM 调用，不走 while-loop | 需要 structured output，不适合工具调用驱动 |
| assistant 与 task 记忆共享 | 默认隔离，`--share-memory` 开启共享 | 科研记忆和日常助手记忆语义差异大，默认隔离更干净 |
