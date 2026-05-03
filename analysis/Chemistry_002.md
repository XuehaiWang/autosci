# Chemistry_002 — 0%

## 任务概述
The input to HADDOCK3 consists of atomic coordinates of biomolecules (proteins, glycans, etc.) in PDB format, along with optional experimental restraints (e.g., ambiguous interaction restraints) and user-defined workflows. The output is an ensemble of modeled three-dimensional structures of biomolec...

> 评分器原始加权分: 0.0/100（评分器使用 0-100 分制，50分=与论文持平）

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 0/100 | 0.3 | image | Mode A applies because the criterion specifies a particular scatter plot, number of points, axes (ΔHADDOCK vs ΔΔG), coloring scheme, and Pearson correlation (0.60). None of the AI-... |
| [1] | 0/100 | 0.2 | text | This criterion is Objective (Mode A), since it specifies concrete top-five alanine hotspot residues with particular ΔHADDOCK scores and comparison to SKEMPI ΔΔG values. The report... |
| [2] | 0/100 | 0.2 | text | The criterion is Objective (Mode A), as it asks for alanine scanning on interface residues with specific ΔHADDOCK score ranges and qualitative agreement with SKEMPI. The report doe... |
| [3] | 0/100 | 0.15 | text | This criterion concerns specific capabilities and quantitative docking performance of HADDOCK3 on multi‑interface antibody–antigen and protein–glycan systems (DockQ scores, success... |
| [4] | 0/100 | 0.15 | text | The criterion is Objective (Mode A) because it specifies a concrete CAPRI benchmark (round 57, target 268) with a particular workflow (consensus HADDOCK EM + VorolF‑jury) and a qua... |

## 失分根因
1. [0] 图片完全缺失或内容完全不符（0/100）: Mode A applies because the criterion specifies a particular scatter plot, number of points, axes (ΔHADDOCK vs ΔΔG), coloring scheme, and Pearson correlation (0.
2. [1] 关键结果完全缺失（0/100）: This criterion is Objective (Mode A), since it specifies concrete top-five alanine hotspot residues with particular ΔHADDOCK scores and comparison to SKEMPI ΔΔG
3. [2] 关键结果完全缺失（0/100）: The criterion is Objective (Mode A), as it asks for alanine scanning on interface residues with specific ΔHADDOCK score ranges and qualitative agreement with SK

## 数据/方法缺口
- 数据缺失：item[0]: Mode A applies because the criterion specifies a particular scatter plot, number of points, axes (ΔHADDOCK vs ΔΔG), coloring schem
- 文件名不匹配：期望图片 `images/haddock3-alascan_VS_SKEMPI.png` 未找到（实际生成: ['contacts_vs_ddg.png', 'feature_importance.png', 'observed_vs_predicted_ddg.png']）
