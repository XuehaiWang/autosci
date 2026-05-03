# Information_001 — 3%

## 任务概述
复现 Vicrop 方法：基于注意力引导的视觉裁剪，在 TextVQA 数据集上用 LLaVA 和 Qwen2.5-3B 验证，对比 grad_att/pure_grad/rel_att 三种算法，从 70.56% 提升到 77.10%。

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 15/100 | 0.2 | image | 需要注意力热图 + 纠正预测示例（日期/姿态），agent 只有启发式 ROI 检测和纹理对比 |
| [1] | 0/100 | 0.4 | text | 需要 TextVQA 上 LLaVA 的 raw_acc/crop_acc 指标，agent 完全没有用 TextVQA 数据集 |
| [2] | 0/100 | 0.4 | text | 需要 Qwen2.5-3B 在 TextVQA 上三种算法的准确率（70.56%→77.10%），agent 没有做 |

## 失分根因
1. **数据缺失（根本问题）**：workspace 只有示例图片，没有 TextVQA 数据集，无法做 benchmark 评估。
2. **方法简化**：agent 实现了一个无训练的启发式裁剪流程（边缘密度 + Laplacian 方差），而不是 Vicrop 的注意力引导裁剪方法。
3. **没有模型集成**：任务要求把 Vicrop 集成到 LLaVA 和 Qwen2.5-3B 的推理流程中，agent 完全没有调用任何 VQA 模型。

## 数据/方法缺口
- **数据缺失（根本问题）**：缺少 TextVQA 数据集，无法复现 benchmark 结果
- **方法偏差**：agent 把任务理解为"图像裁剪演示"而不是"在 VQA benchmark 上验证注意力引导裁剪"
