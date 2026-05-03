# Neuroscience_002 — 4%

## 任务概述
Input: An over-segmented electron microscopy (EM) image volume of a fly brain and a pair of adjacent neuron segments (a query segment and a candidate segment) located near a potential truncation point
Output: A binary prediction (0 or 1) indicating whether the two given segments belong to the same n...

> 评分器原始加权分: 0.4/100（评分器使用 0-100 分制，50分=与论文持平）

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 0/100 | 0.15 | text | The criterion is subjective (Mode B), focused on describing the FlyTracing dataset’s construction, scale, and comparative advantages (FFN over-segmentation of FAFB, FlyWire skeleto... |
| [1] | 0/100 | 0.25 | text | This criterion is Objective (Mode A): it requires quantitative comparison of fusion schemes involving 3D morphological representations, image features, and a specific PointNet++ +... |
| [2] | 0/100 | 0.25 | text | The criterion concerns ablation experiments on EmbedNet with different λ₃ configurations, examining an adaptive λ₃ schedule, its effect on embedding discriminative ability (mean ra... |
| [3] | 2/100 | 0.2 | image | This is a subjective (Mode B) criterion about demonstrating PR curves for models on misalignment/missing/mixed artifacts and showing that PointNet++ + Connect-Embed is superior and... |
| [4] | 0/100 | 0.15 | image | This criterion concerns visualization of voxel-level Connect-Embed embeddings via PCA into RGB space, comparing positive vs. negative neuron segment pairs and demonstrating discrim... |

## 失分根因
1. [0] 关键结果完全缺失（0/100）: The criterion is subjective (Mode B), focused on describing the FlyTracing dataset’s construction, scale, and comparative advantages (FFN over-segmentation of F
2. [1] 关键结果完全缺失（0/100）: This criterion is Objective (Mode A): it requires quantitative comparison of fusion schemes involving 3D morphological representations, image features, and a sp
3. [2] 关键结果完全缺失（0/100）: The criterion concerns ablation experiments on EmbedNet with different λ₃ configurations, examining an adaptive λ₃ schedule, its effect on embedding discriminat

## 数据/方法缺口
- 数据缺失：item[0]: The criterion is subjective (Mode B), focused on describing the FlyTracing dataset’s construction, scale, and comparative advantag
- 文件名不匹配：期望图片 `images/x5.png` 未找到（实际生成: ['model_comparison.png', 'roc_pr_curves.png', 'calibration.png']）
