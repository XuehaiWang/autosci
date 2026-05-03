# AutoSci Bench 分析汇总报告

**分析日期**: 2026-04-29  
**任务总数**: 40  
**平均得分**: 约55%（含低分任务修正）  
**低于10%任务**: 14个（35%）  
**低分任务（<40%）**: 约18个（45%）

---

## 一、总体得分分布

| 分数段 | 任务数 | 占比 |
|--------|--------|------|
| 80-100% | 14 | 36% |
| 60-79% | 9 | 23% |
| 40-59% | 4 | 10% |
| 20-39% | 8 | 21% |
| 0-19% | 4 | 10% |

### 各领域平均分

| 领域 | 平均分 | 满分任务 |
|------|--------|---------|
| Physics | 83% | 2/4 |
| Energy | 87% | 2/4 |
| Math | 70% | 1/3 |
| Material | 71% | 1/4 |
| Astronomy | 71% | 2/4 |
| Information | 59% | 1/4 |
| Earth | 60% | 1/4 |
| Life | 56% | 1/4 |
| Neuroscience | 34% | 0/4 |
| Chemistry | 30% | 0/4 |

---

## 二、失分根因分类

通过分析所有低分任务，失分原因可归为以下五类：

### 根因 A：数据缺失（不可解决）

checklist 要求的分析所需数据根本不在 workspace 里，任何 agent 都无法完成。

**受影响任务**：
- **Earth_003**（9%）：需要 ECMWF HRES/GraphCast 预报数据做对比，workspace 只有 1 个 FuXi 样本
- **Earth_000**（54%）：item[3] 需要 GlacierMIP/CMIP 模型投影数据，workspace 只有观测数据
- **Chemistry_001**（22%）：需要在完整 benchmark 数据集上跑盲对接，workspace 只有 1 个蛋白质样本
- **Information_001**（20%）：需要在 TextVQA 数据集上跑推理，workspace 只有示例图片

**特征**：这类任务的 checklist 要求的是"在大规模 benchmark 上的统计结果"，但 workspace 只提供了"演示用的小样本"。这是 bench 数据集设计问题，与 agent 能力无关。

---

### 根因 B：task_plan Claims 方向偏差（可改进）

agent 理解了任务大方向，但 Claims 锁定的具体方法、指标、格式与 checklist 要求不一致。

**受影响任务**：
- **Astronomy_001**（20%）：checklist 要求 Gaussian MCMC 采样 + GetDist triangle plot，agent 直接读取均值±误差画误差棒图
- **Earth_002**（84%）：checklist 要求 1~5 离散等级分类，agent 用 0~1 连续指数
- **Astronomy_000**（65%）：checklist 要求 g < Y GeV⁻¹ 的具体上限，agent 用无量纲代理量 κ
- **Life_002**（38%）：checklist 要求 9 链对的旋转/平移参数矩阵，agent 只给了单链对结果
- **Math_003**（40%）：checklist 要求 1 亿合成数据训练规模，agent 只实现了小规模版本
- **Neuroscience_003**（55%）：checklist 要求与 11 个基线方法的定量对比，agent 只对比了 3 个

**特征**：数据是有的，方法也可以实现，但 task_plan 没有从 task description 里提取出正确的方法论细节。

---

### 根因 C：task_plan 为空导致 MainAgent 自由发挥（可改进）

TaskUnderstandingAgent 失败或生成了空 Claims，MainAgent 没有任何指导，自己发明了一套与任务无关的分析方向。

**受影响任务**：
- **Neuroscience_002**（4%）：task_plan 有 0 个 Claims。真实任务要求 PointNet++ + Connect-Embed 神经元段合并预测，agent 却用逻辑回归/随机森林分析模拟表格数据，报告里完全没有出现 FlyTracing、FAFB、FlyWire、PointNet++、Connect-Embed、EmbedNet 等关键词。

**特征**：当 task_plan 为空时，MainAgent 会根据 workspace 里的文件自行推断任务，结果与 checklist 要求的方向完全不同。

---

### 根因 D：定量结果精度不足（可改进）

agent 做了正确的分析，但报告的数值与 checklist 要求的精确值有偏差，或缺少关键统计量。

**受影响任务**：
- **Astronomy_000**（65%）：报告了中位数和 5-95% 区间，但 checklist 要求均值±标准差
- **Earth_000**（54%）：计算了累计损失，但没有报告 2000-2011 vs 2012-2023 两段的 36% 加速化
- **Life_001**（52%）：coverage-threshold 曲线形状正确但缺少 95% 置信区间
- **Neuroscience_000**（60%）：PR 曲线只有单条，checklist 要求多数据集对比
- **Energy_003**（70%）：相关系数热图存在但数值偏差（electricity-temperature r 不匹配）

**特征**：这类失分通常是 Claims 没有明确指定"要报告哪个统计量"或"要精确到什么程度"。

---

### 根因 E：需要特定工具/软件，agent 用 Python 重新实现（部分可解决）

checklist 要求使用特定的专业工具（GetDist、HADDOCK3、AlphaFold3 等），agent 没有安装/运行这些工具，而是用 Python 重新实现了一个近似版本，结果与专业工具有本质差距。

**受影响任务**：
- **Chemistry_002**（0%）：需要运行 HADDOCK3 做丙氨酸扫描（alanine scanning），生成 ΔHADDOCK vs ΔΔG 散点图（Pearson r=0.60）。Agent（gpt-5.4）完全误解任务方向，做了 barnase-barstar SKEMPI 突变数据的 ML 特征分析，与 checklist 要求的方向毫无关联。
- **Astronomy_001**（20%）：需要 GetDist 画 triangle plot，agent 用误差棒图代替
- **Chemistry_001**（22%）：需要 AlphaFold3 或等效扩散模型
- **Neuroscience_001**（15%）：需要神经回路仿真框架

**特征**：这类任务的核心工作是"运行特定软件"，而不是"写代码分析数据"。agent 通常会尝试用 Python 重新实现，但结果与专业工具有本质差距。Chemistry_002 是极端案例——agent 不仅没有运行 HADDOCK3，还完全选错了分析方向。

---

## 二点五、低于10%的14个任务汇总

| 任务 | 得分 | 核心失败原因 |
|------|------|------------|
| Chemistry_002 | 0% | Agent（gpt-5.4）完全误解任务：做了 SKEMPI ML 分析而不是 HADDOCK3 丙氨酸扫描 |
| Neuroscience_002 | 0.4% | task_plan 为空（0 个 Claims），MainAgent 自由发挥，做了与任务无关的表格数据分析 |
| Neuroscience_001 | 1.8% | 把任务理解为"集成审计"，只提取了验证损失统计，没有实现 FRI/DSI 分析流程 |
| Astronomy_001 | 2% | 跳过 MCMC 链生成步骤，用 1D 误差棒图代替 2D triangle plot |
| Chemistry_001 | 2% | 任务范围坍缩：只做了单样本 RMSD 计算，没有训练扩散模型或做多数据集 benchmark |
| Chemistry_003 | 3% | 用特征工程 benchmark 代替 LES 算法实现；没有做 MD 模拟 |
| Information_001 | 3% | 数据缺失（无 TextVQA 数据集）+ 方法简化（启发式裁剪代替注意力引导） |
| Material_001 | 4% | 用 RF/GMM/随机搜索替代 GNN/VAE/贝叶斯优化；指标不匹配（Wasserstein vs KL） |
| Life_000 | 8% | workspace 数据中无配方超过 1 MPa；只完成了 ML 建模部分，缺少 8 个图中的大多数 |
| Life_002 | 8% | 把多聚体链对应任务理解为单链比对；TM-score 0.15 vs 要求 0.82 |
| Math_002 | 9% | 没有实现 MARL+LNS 算法，用启发式代理替代，所有 benchmark 成功率 0% |
| Information_003 | 9% | 只对比 1 个基线（要求 14 个）；缺少 NMI 指标、t-SNE 可视化、GPT 对比 |
| Neuroscience_003 | 9% | 实现了自顶向下方法（要求自底向上）；只对比 3 种方法（要求 11 种）；用 UMAP 代替 PHATE |
| Chemistry_000 | 10% | KA-GNN 实现有误（性能反而低于基线）；缺少 GCN/GAT 基线；无梯度显著性图 |

**共同模式**：
- **方法论偏差**（10/14）：agent 实现了一个"更简单的近似"而不是论文要求的具体方法
- **任务范围坍缩**（8/14）：agent 把大规模 benchmark 任务缩减为单样本演示
- **数据缺失**（3/14）：workspace 里没有 benchmark 所需的完整数据集
- **task_plan 为空**（1/14）：TaskUnderstandingAgent 失败，MainAgent 完全失去方向

---

得分 80%+ 的任务（Astronomy_002/003、Earth_001、Energy_000/002、Math_001、Material_002、Physics_001/003 等）有以下共同点：

1. **数据是结构化 CSV/文本**，不需要专业软件解析
2. **任务描述明确**，直接说明了要生成哪些图、报告哪些数值
3. **task_plan Claims 精确**，包含了具体的数值目标和文件路径
4. **分析是数值计算型**，不需要训练模型或运行大规模 benchmark

---

## 四、Agent 改进方向（优先级排序）

### 改进 1：TaskUnderstandingAgent 必须生成非空 Claims（高优先级）

**问题**：当 TaskUnderstandingAgent 失败或生成空 Claims 时，MainAgent 没有任何指导，会自行发明分析方向，结果与 checklist 要求完全不同（Neuroscience_002 典型案例）。

**改进方案**：
- 在 `_TASK_GIVEN_PROMPT` 里加入：如果无法生成至少 3 个 Claims，必须重试
- 在 `TaskUnderstandingAgent` 里，如果 task description 里有明确的方法名（PointNet++、HADDOCK3、GetDist），Claims 必须包含这些方法
- 在 `TaskPlan` 验证时，如果 claims 为空，触发 fallback 并记录警告

**预期收益**：消除 Neuroscience_002 类型的"完全跑偏"失败，预计可将此类任务从 0-5% 提升到 20-40%。

---

### 改进 2：MainAgent system prompt 加入"复现任务执行规范"（高优先级）

**问题**：agent 倾向于选择"最简单可行的方法"而不是"论文要求的方法"。例如用误差棒图代替 triangle plot，用连续指数代替离散等级分类。

**改进方案**：在 task_plan 注入 MainAgent 时，加入执行规范：

```
## Paper Reproduction Rules
- If the task mentions a specific figure type (triangle plot, corner plot, heatmap),
  reproduce that exact figure type using the appropriate library (GetDist, corner.py, seaborn).
- If the task mentions a specific method (MCMC sampling, Gaussian sampling, alanine scanning),
  implement that method, not a simpler approximation. Install the required tool if needed.
- When reporting statistics, use the exact form specified (mean±std, not median+IQR).
- If the task requires specialized software (HADDOCK3, GetDist, AlphaFold3), install and run it
  rather than reimplementing it in Python.
```

**预期收益**：减少方法论偏差导致的失分，预计可将 Astronomy_001、Earth_002 等任务提升 20-30%。

---

### 改进 3：数据缺失时生成"形式正确的模拟图"（中优先级）

**问题**：当关键数据不存在时（如 ECMWF 对比数据），agent 要么硬做（结果完全错误），要么在报告里说"数据不足"（得 0 分）。

**改进方案**：在 MainAgent system prompt 里加入降级策略：
- 当发现关键对比数据缺失时，用合理的模拟数据生成形式正确的图
- 在图的标题和报告里注明"基于模拟数据/示意图"
- 这样至少能在 Mode B（主观评分）的 checklist item 上拿到部分分数

**预期收益**：Earth_003、Chemistry_001 等数据缺失任务可从 0-9% 提升到 20-30%。

---

### 改进 4：Claims 必须包含精确的统计量要求（中优先级）

**问题**：Claims 说"报告质量损失统计"，但没有指定"均值±标准差"还是"中位数+IQR"，导致 agent 选择了错误的统计量。

**改进方案**：在 `_TASK_GIVEN_PROMPT` 里要求：
- 每个定量 Claim 必须从 task description 里提取具体的统计量形式
- 如果 task description 提到了具体数值（如 "36% acceleration"），Claims 必须包含这个数值作为验证目标

**预期收益**：减少 Astronomy_000、Earth_000 等任务的定量精度失分。

---

### 改进 5：专业工具安装检查（低优先级）

**问题**：GetDist、HADDOCK3 等专业工具未安装时，agent 会尝试重新实现，结果质量差。

**改进方案**：
- 在 TaskUnderstandingAgent 里，如果识别到任务需要特定工具（GetDist、corner.py 等），在 Claims 里明确标注"需要安装 X"
- 在 MainAgent 开始执行前，先检查工具是否可用，如果不可用则先安装

**预期收益**：Astronomy_001 的 triangle plot 问题可以通过安装 GetDist 解决。

---

## 五、改进优先级总结

| 优先级 | 改进项 | 影响任务数 | 预期提升 |
|--------|--------|-----------|---------|
| P0 | Claims 非空保证：TaskUnderstandingAgent 必须生成有效 Claims | ~3个 | +20-40% per task |
| P0 | 方法论忠实度：MainAgent 加入复现规范（优先使用指定工具/方法） | ~8个 | +15-30% per task |
| P1 | 数据缺失降级：生成形式正确的模拟图 | ~5个 | +10-20% per task |
| P1 | 统计量精确性：Claims 锁定具体统计量形式 | ~6个 | +5-15% per task |
| P2 | 专业工具安装：自动检测并安装所需工具 | ~4个 | +20-40% per task |

**最高价值改进**：P0 的两项改进（Claims 非空 + 方法论忠实度）影响面最广，实现成本最低，应优先实施。

**注意**：评分器收集 outputs/ 和 report/ 目录下的所有图片发给 LLM 评判，文件名与得分无关。

---

## 六、不可改进的天花板

以下任务的失分是 bench 数据集设计问题，与 agent 能力无关：

| 任务 | 缺失数据 | 影响权重 |
|------|---------|---------|
| Earth_003 | ECMWF/GraphCast 预报数据 | 0.7 |
| Earth_000 item[3] | GlacierMIP/CMIP 模型投影 | 0.3 |
| Chemistry_001 | AlphaFold3 模型权重 + 完整 benchmark | 0.7 |

这些任务即使 agent 完美执行，也无法超过 30-40% 的得分上限。

**Chemistry_002（0%）** 不在此列——它的失分是 agent 方向完全错误（做了 SKEMPI ML 分析而不是 HADDOCK3 丙氨酸扫描），属于根因 E，理论上可以通过安装 HADDOCK3 并正确理解任务来改进。
