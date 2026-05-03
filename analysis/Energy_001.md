# Energy_001 — 76%

## 任务概述
Input: Historical and future energy system data for Great Britain, including network topology, generator capacities, demand profiles, renewable time series, fuel prices, and National Grid’s Future Energy Scenarios (FES) up to 2050.

Output: Optimal power dispatch (generation, storage, curtailment)...

> 评分器原始加权分: 15.7/100（评分器使用 0-100 分制，50分=与论文持平）

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 0/100 | 0.1 | text | The criterion is objective, requiring a specifically constructed 20‑bus Scottish–English system with 50 GW of Scottish onshore wind (5×10 GW) and 1.5 GW capacity on each of five Sc... |
| [1] | 25/100 | 0.3 | text | This is an Objective (Mode A) criterion about specific curtailment percentages and comparison between constrained and unconstrained network cases. The report does quantify wind cur... |
| [2] | 8/100 | 0.2 | image | Mode B applies because the criterion is about visually and qualitatively demonstrating temporal dynamics of dispatched versus curtailed wind. The AI report does not include a dedic... |
| [3] | 5/100 | 0.2 | image | This is a qualitative/interpretive criterion (Mode B). The target figure shows the Scotland‑England link loading near 1.0 for most of the 168 hours, indicating a persistently satur... |
| [4] | 28/100 | 0.2 | text | The criterion is qualitative, focusing on whether the work demonstrates an open‑source, high‑resolution GB model with future scenario capability, validation via a wind-curtailment... |

## 失分根因
1. [0] 关键结果完全缺失（0/100）: The criterion is objective, requiring a specifically constructed 20‑bus Scottish–English system with 50 GW of Scottish onshore wind (5×10 GW) and 1.5 GW capacit
2. [1] 方法或结果有重大缺陷（25/100）: This is an Objective (Mode A) criterion about specific curtailment percentages and comparison between constrained and unconstrained network cases. The report do
3. [2] 图片内容严重偏差（8/100）: Mode B applies because the criterion is about visually and qualitatively demonstrating temporal dynamics of dispatched versus curtailed wind. The AI report does

## 数据/方法缺口
- 数据缺失：item[0]: The criterion is objective, requiring a specifically constructed 20‑bus Scottish–English system with 50 GW of Scottish onshore win
- 方法偏差：item[4]: The criterion is qualitative, focusing on whether the work demonstrates an open‑source, high‑resolution GB model with future scena
- 文件名不匹配：期望图片 `images/fig5a_wind_curtailment.png` 未找到（实际生成: ['network_overview.png', 'scenario_comparison.png', 'dispatch_timeseries.png']）
