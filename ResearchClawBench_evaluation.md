# ResearchClawBench 评测系统说明

> 本文档基于 `/mnt/20t/wxh/ResearchClawBench/evaluation/` 源码分析，供 autosci agent 接入该 bench 时参考。

---

## 1. 整体评测流程

评测系统是一个 Flask Web 服务，分三个阶段：

```
Phase 1: 任务执行
  选择任务 + agent → 创建 workspace → 启动 agent 子进程 → 实时捕获输出

Phase 2: 报告生成
  agent 在 workspace 中完成分析 → 写出 report/report.md + 图片

Phase 3: 评分
  judge LLM 对照 checklist 逐项打分 → 加权汇总 → 写入 _score.json
```

---

## 2. 任务结构

### 任务目录布局

```
tasks/{task_id}/
├── task_info.json           # 任务描述 + 数据文件说明
├── data/                    # 只读输入数据集
├── related_work/            # 参考论文（PDF）
└── target_study/
    ├── checklist.json       # 评分标准
    ├── paper_*.pdf          # 目标论文
    └── images/              # ground-truth 图片（用于图像评分项）
```

### task_info.json 格式

```json
{
  "task": "详细任务描述，包含输入/输出/目标",
  "data": [
    {
      "name": "数据集名称",
      "path": "./data/路径",
      "type": "sequence_data|tabular|...",
      "description": "数据内容说明"
    }
  ]
}
```

### 任务命名规则

任务 ID 以领域为前缀，如 `Neuroscience_001`、`Chemistry_001`、`Material_003`，按领域分组展示在排行榜上。

---

## 3. Agent 接入方式

### agents.json 配置

每个 agent 通过命令模板注册，支持两个占位符：

| 占位符 | 替换内容 |
|--------|----------|
| `<PROMPT>` | `$(cat '{instructions_path}')` — 避免 shell 转义问题 |
| `<WORKSPACE>` | workspace 绝对路径 |

**AutoSci 的注册命令：**
```
autosci-bench -m <PROMPT> -w <WORKSPACE>
```

### 执行协议

- agent 以子进程启动，`cwd` 设为 workspace 目录
- 设置 `PYTHONUNBUFFERED=1`，强制实时 stdout 输出
- 输出逐行写入 `_agent_output.jsonl`
- 退出码 0 = 成功，非 0 = 失败

---

## 4. INSTRUCTIONS.md — Agent 收到的任务指令

系统会在 workspace 中生成 `INSTRUCTIONS.md`，内容结构如下：

### 角色定义
> 你是一个自主科研 agent，需要独立完成从头到尾的科研任务：
> 1. 阅读理解 — 研究相关工作和数据
> 2. 思考设计 — 提出假设和分析方案
> 3. 编码执行 — 实现分析，生成图表
> 4. 分析报告 — 产出发表级别的报告

### 关键约束（必须遵守）

- **无人值守**：没有人会回答问题或授权操作
- **每次响应必须包含至少一个工具调用**（纯文字推理会导致意外终止）
- **任务完成的唯一标志**：`report/report.md` 存在且内容完整
- **严禁**：只输出计划而不调用工具、提问、纯文字推理、在报告写完前声明完成

### Workspace 布局

```
data/          — 只读输入数据集
related_work/  — 只读参考论文
code/          — 在此写分析代码
outputs/       — 保存中间结果
report/        — 写最终报告
report/images/ — 所有图片必须保存为 PNG
```

---

## 5. 评分系统

### Judge 模型

- 默认：`gpt-5.1`（OpenAI 兼容 API）
- 可通过环境变量 `SCORER_MODEL` 覆盖
- 并行评分（最多 16 个 worker）
- 支持多次评分取均值，提高稳定性

### Checklist 项目格式

```json
{
  "type": "text|image",
  "content": "来自原始论文的评分标准描述",
  "keywords": ["需要核查的技术要点"],
  "weight": 0.25,
  "path": "images/target_image.png"  // 仅 image 类型有此字段
}
```

### 评分标准（两种模式）

**Mode A：客观评分**（定量指标）

| 分数 | 含义 |
|------|------|
| 0 | 完全缺失 |
| 1-10 | 提及但无定量结果 |
| 11-20 | 有结果但方法存在根本性错误 |
| 21-30 | 显著缺陷，指标严重偏离论文 |
| 31-40 | 大体正确但明显差于论文 |
| **41-50** | **指标与原论文大致相当（高标准）** |
| 51-60 | 略优于论文 |
| 61-70 | 明显优于论文 |
| 71-80 | 大幅超越论文 |
| 81-90 | 显著超越论文 |
| 91-100 | 突破性成果，远超论文 |

**Mode B：主观评分**（定性推理）

| 分数 | 含义 |
|------|------|
| 0 | 完全缺失 |
| 1-10 | 仅有模糊泛泛的陈述 |
| 11-20 | 有描述但无实质分析 |
| 21-30 | 有分析尝试但证据不足/逻辑有漏洞 |
| 31-40 | 方向正确但深度不够，缺少关键论点 |
| **41-50** | **分析深度和严谨性与原论文相当（高标准）** |
| 51-60 | 比论文有更多支撑证据 |
| 61-70 | 逻辑链更完整，论证更严谨 |
| 71-80 | 分析明显更深入，有论文未提及的洞见 |
| 81-90 | 分析深度远超论文 |
| 91-100 | 有原创贡献，具有突破性洞见 |

> **关键：50 分 = "与已发表论文水平相当"，这是一个很高的标准。**

### 评分流程

1. 读取 `report/report.md`
2. 对每个 checklist 项：
   - 构建 prompt（rubric + 任务说明 + 评分标准 + 报告内容）
   - 图像类型：同时传入 ground-truth 图片 + workspace 中生成的图片
   - 以 `temperature=0` 调用 judge LLM
   - 解析 JSON 响应：`{"reasoning": "...", "score": 0-100}`
3. 加权汇总：`final_score = sum(score * weight) / sum(weights)`
4. 结果写入 `_score.json`

---

## 6. 输出文件结构

### Workspace 布局（运行时）

```
workspaces/{run_id}/
├── _meta.json                    # 运行元数据
├── _agent_output.jsonl           # agent stdout（逐行）
├── _score.json                   # 评分结果
├── INSTRUCTIONS.md               # 生成的任务指令
├── data/                         # 从 task/data/ 复制
├── related_work/                 # 从 task/related_work/ 复制
├── code/                         # agent 生成的代码
├── outputs/                      # agent 生成的中间结果
└── report/
    ├── report.md                 # 最终研究报告
    └── images/                   # PNG 图表
```

### _meta.json 关键字段

```json
{
  "task_id": "Neuroscience_001",
  "run_id": "Neuroscience_001_20250429_143022",
  "status": "completed|failed|stopped|running",
  "agent_name": "AutoSci",
  "exit_code": 0,
  "duration_seconds": 1234,
  "model": "claude-opus-4-6",
  "token_usage": {
    "input_tokens": 50000,
    "output_tokens": 25000,
    "cached_input_tokens": 10000,
    "total_tokens": 75000
  },
  "cost_usd": 1.23
}
```

### _score.json 关键字段

```json
{
  "total_score": 48.5,
  "items": [
    {
      "index": 0,
      "type": "image",
      "content": "评分标准描述",
      "weight": 0.15,
      "score": 45,
      "reasoning": "judge 的推理过程"
    }
  ],
  "score_history_summary": {
    "attempts": 3,
    "mean_total_score": 48.2,
    "std_total_score": 1.5
  }
}
```

---

## 7. Token 用量追踪

系统从 agent 的 stdout 中解析 token 用量，支持以下格式：

**JSON 事件格式：**
```json
{"type": "usage_stats", "usage": {"input_tokens": 50000, "output_tokens": 25000}}
```

**文本模式匹配：**
```
input tokens: 50000
output tokens: 25000
```

**追踪的字段：**
- `input_tokens` / `output_tokens`
- `cached_input_tokens`（cache 读取）
- `cache_creation_input_tokens`（cache 写入）
- `cache_creation_ephemeral_5m_input_tokens`（5分钟 cache）
- `cache_creation_ephemeral_1h_input_tokens`（1小时 cache）
- `web_search_requests`

---

## 8. autosci 接入要点

基于以上分析，autosci 接入 ResearchClawBench 需要满足：

### 必须实现

1. **CLI 入口**：`autosci-bench -m <prompt> -w <workspace>`
   - `-m` / `--message`：任务指令（INSTRUCTIONS.md 内容）
   - `-w` / `--workspace`：workspace 绝对路径

2. **工作目录**：以 workspace 为 cwd 运行，所有文件操作相对于此

3. **输出文件**：
   - `report/report.md`：最终报告（必须存在）
   - `report/images/*.png`：所有图表（必须为 PNG 格式）

4. **退出码**：成功退出码为 0

5. **Token 用量上报**（可选但推荐）：向 stdout 输出 token 用量信息

### 推荐行为

- 读取 `INSTRUCTIONS.md` 作为任务入口
- 利用 `data/` 中的数据集和 `related_work/` 中的参考论文
- 将分析代码写入 `code/`，中间结果写入 `outputs/`
- 报告中的图片引用使用相对路径 `images/xxx.png`

### 评分期望

- 目标分数 **41-50** 即达到与原论文相当的水平
- judge 对 AI 生成内容持高度怀疑态度（会识别捏造数据、无依据结论）
- 图像评分会对比 ground-truth，视觉相似但数值错误会得低分
- 具体、定量的分析优于模糊的泛泛描述

---

## 9. 示例任务：Neuroscience_001

**任务**：为果蝇视觉系统的光流估计构建连接组约束的深度机制网络（DMN）

**数据**：50 个预训练 DMN 模型，包含连接组、突触矩阵、细胞类型注释

**Checklist（5项，均为图像类型）：**

| 项目 | 权重 | 评分要点 |
|------|------|----------|
| 模型架构 | 0.15 | 六边形 CNN，45,669 个神经元，734 个参数 |
| 验证基准 | 0.25 | 26 项研究，32 个 ON/OFF 细胞，30/32 预测正确 |
| 方向选择性 | 0.25 | T4/T5 亚型，4 个偏好方向，TmY 新预测 |
| 消融研究 | 0.25 | 连接组 + 任务优化的必要性 |
| 聚类分析 | 0.10 | UMAP，功能聚类，Mi4/Mi9 耦合 |
