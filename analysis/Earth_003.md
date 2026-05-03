# Earth_003 — 9%

## 任务概述
复现 FuXi AI 天气预报模型：基于 ERA5 全球大气再分析数据，使用三阶段级联 U-Transformer 架构，生成 15 天 6 小时分辨率预报，并与 ECMWF HRES 和 GraphCast 进行 ACC/RMSE 对比评估。

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 0/10 | 0.2 | text | 需要 ACC≥0.6 的技巧性预报时效对比（Z500: 9.25→10.5天，T2M: 10→14.5天），但无验证数据无法计算 |
| [1] | 0/10 | 0.3 | image | 需要 FuXi/GraphCast/HRES 的 ACC 和 RMSE 随时效变化曲线，但无 ECMWF/GraphCast 数据 |
| [2] | 0/10 | 0.2 | image | 需要 FuXi vs ECMWF EM 的归一化 ACC/RMSE 差值曲线，但无对比数据 |
| [3] | 3/10 | 0.3 | image | Z500 空间分布图部分相似，但缺少 ECMWF HRES 对比列，仅有 ERA5 输入和 FuXi 输出两列 |

## 失分根因
1. **数据根本缺失（决定性原因）**：workspace 只有 1 个初始时刻的 ERA5 输入（2步）和 1 个 6 小时 FuXi 预报样本，完全没有 ECMWF HRES 预报、GraphCast 预报、15 天连续预报输出、ERA5 验证目标。任何 agent 都无法完成 checklist 要求的对比评估。
2. **分辨率不匹配**：数据是 1° 分辨率（181×360），论文要求 0.25°（721×1440），无法直接对应。
3. **task_plan Claims 方向合理但无法执行**：agent 正确识别了任务目标，但数据缺口使所有定量 Claims 都无法验证。

## 数据/方法缺口
- **数据缺失（根本问题）**：缺少 ECMWF HRES 预报数据、GraphCast 预报数据、15 天连续 FuXi 预报、ERA5 验证目标序列
- **方法偏差**：无，agent 方法论理解正确
- **文件名不匹配**：`validation_comparison.png` vs checklist 要求的 `fig_p4_1.jpeg`、`fig_p5_1.png`
