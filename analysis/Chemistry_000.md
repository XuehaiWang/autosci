# Chemistry_000 — 10%

## 任务概述
复现 KA-GNN（Kolmogorov-Arnold 图神经网络）用于分子性质预测：在 7 个 MoleculeNet 数据集上 KA-GCN/KA-GAT 优于 GCN/GAT，Fourier 基优于 B-spline/多项式，并通过梯度显著性图展示化学可解释性。

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 5/100 | 0.45 | image | 需要 KA-GCN/KA-GAT vs GCN/GAT 在 7 个数据集上的 ROC-AUC 对比，agent 的 KA-GNN 反而比 MLP-GNN 差（BACE: 0.421 vs 0.711），且没有 GCN/GAT 基线 |
| [1] | 18/100 | 0.35 | text | 需要 Fourier vs B-spline/多项式的形式化理论对比，agent 只简单提及 Fourier KAN，无收敛分析 |
| [2] | 5/100 | 0.2 | text | 需要梯度显著性图识别功能基团（氟、酰胺、芳香环），agent 只检查了 Fourier 系数幅度，明确说"没有分析化学有意义的子结构" |

## 失分根因
1. **核心声明无法复现**：agent 的实现中 KA-GNN 性能反而低于基线（BACE: 0.421 vs 0.711），与论文声明的"KA-GNN 优于 GCN/GAT"完全相反。
2. **缺少必要基线**：没有实现 GCN/GAT 基线，无法做论文要求的对比实验。
3. **可解释性分析不足**：没有实现梯度显著性图，无法识别化学功能基团，agent 自己也承认这一点。

## 数据/方法缺口
- **方法偏差（决定性原因）**：KA-GNN 实现有问题，导致性能低于基线；没有实现 GCN/GAT 对比基线
- **理论分析缺失**：Fourier vs B-spline/多项式 的形式化对比（通用近似定理、收敛性）完全缺失
