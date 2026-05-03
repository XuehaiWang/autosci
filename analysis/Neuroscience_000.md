# Neuroscience_000 — 60%

## 任务概述
Input: pose-derived frame-level feature tables and aligned behavior labels (Attack, Sniffing) from the official SimBA sample project. Output: trained supervised classifiers, quantitative evaluation reports, precision-recall diagnostics, confusion matrices, and feature-importance tables. Scientific o...

> 评分器原始加权分: 23.2/100（评分器使用 0-100 分制，50分=与论文持平）

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 30/100 | 0.2 | image | Mode A applies because the criterion is about quantitative PR performance and AP values. The AI report’s PR figure only shows single curves for Attack and Sniffing from one dataset... |
| [1] | 0/100 | 0.2 | image | The target figure is a grouped bar plot of mean SHAP values per biologically defined feature category comparing Lab1 vs Lab2 attack classifiers. None of the AI-generated figures co... |
| [2] | 48/100 | 0.2 | image | This criterion is subjective (Mode B) because it concerns whether the SHAP-based explanation captures sex-specific differences and matches the qualitative pattern in the paper. The... |
| [3] | 38/100 | 0.2 | image | This is a subjective (Mode B) criterion about whether the SHAP comparison figure demonstrates differing feature emphasis between RI and CSDS and links it to environmental context.... |
| [4] | 0/100 | 0.2 | image | This criterion is Objective (Mode A) because it concerns reproducing a specific permutation‑importance ranking plot for the Lab1 attack classifier and its technical details. The ta... |

## 失分根因
1. [0] 图片内容严重偏差（30/100）: Mode A applies because the criterion is about quantitative PR performance and AP values. The AI report’s PR figure only shows single curves for Attack and Sniff
2. [1] 图片完全缺失或内容完全不符（0/100）: The target figure is a grouped bar plot of mean SHAP values per biologically defined feature category comparing Lab1 vs Lab2 attack classifiers. None of the AI-
3. [3] 图片内容严重偏差（38/100）: This is a subjective (Mode B) criterion about whether the SHAP comparison figure demonstrates differing feature emphasis between RI and CSDS and links it to env

## 数据/方法缺口
- 数据缺失：item[1]: The target figure is a grouped bar plot of mean SHAP values per biologically defined feature category comparing Lab1 vs Lab2 attac
- 文件名不匹配：期望图片 `images/figure1_pr_curves.png` 未找到（实际生成: ['confusion_matrices.png', 'precision_recall_curves.png', 'data_overview.png']）
