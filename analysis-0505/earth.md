# Earth Domain Task Analysis (ResearchClawBench)

Analysis date: 2026-05-05

---

## Earth_000: GlaMBIE Global Glacier Mass Change (Score: 18.2/100)

**Workspace**: `/mnt/20t/wxh/ResearchClawBench/workspaces/Earth_000_20260503_205922/`

### 1. Score Breakdown

| Item | Type | Weight | Score | Max Possible |
|------|------|--------|-------|--------------|
| 0: Cumulative mass loss metrics (text) | text | 0.40 | 22 | 40 |
| 1: Regional rankings (image) | image | 0.10 | 38 | 10 |
| 2: Cross-method consistency (image) | image | 0.20 | 28 | 20 |
| 3: Observations vs model projections (image) | image | 0.30 | 0 | 30 |
| **Total** | | **1.00** | **18.2** | **100** |

**Low-scoring items and judge reasoning:**

- **Item 0 (score 22/100, weight 0.40):** The criterion requires cumulative 2000-2023 mass loss in Gt with uncertainty, average loss rates for two sub-periods (2000-2011 vs 2012-2023) and their percentage increase, maximum annual loss, and comparison to Greenland/Antarctic ice sheets. The report provides the maximum annual loss (548 +/- 120.2 Gt in 2023-2024) and evidence of acceleration, but **does not compute or report** the cumulative 2000-2023 mass change, the two-period average loss rates, or a quantitative comparison with Greenland/Antarctica.

- **Item 3 (score 0/100, weight 0.30):** The criterion requires comparison of observations with model projections (GlacierMIP/CMIP6) and future outlook, including scenario-dependent fractional mass loss and comparison to IPCC AR6 projections. **None of the generated figures** reproduce projection panels, show ensemble ranges, or depict emission scenario dependence. The report focuses exclusively on historical observations and regional summaries, completely omitting the forward-looking analysis.

### 2. Task Understanding

The task_plan.json correctly identifies the core research questions (global/regional mass change trajectories, regional dominance, benchmark comparison) and formulates 10 claims covering global time series, regional breakdowns, heatmaps, acceleration estimation, method comparisons, SLE conversion, and benchmark validation. However, the plan **does not include any claim about comparing observations with model projections or future outlook** -- which is what the highest-weight image criterion (0.30) evaluates. This is a critical gap in task understanding.

### 3. Report Quality

The report is well-structured with abstract, introduction, methods, results, discussion, and conclusion. It includes 5 figures:
- Global mass change time series
- Regional cumulative mass loss ranking
- Regional specific mass-change heatmap
- Method comparison for selected regions
- Benchmark comparison

**Missing content:**
- No cumulative 2000-2023 total mass change number (the report has annual values but never sums them)
- No sub-period average loss rate comparison (2000-2011 vs 2012-2023)
- No comparison to Greenland/Antarctic ice sheet contributions
- **No model projection comparison figure at all** -- the most heavily weighted image criterion
- The acceleration value (99.8 Gt/yr/decade) differs substantially from the benchmark (48 +/- 16), suggesting a methodological issue with the fit window

### 4. Code Quality

Single analysis script `code/analyze_glambie.py`. The code successfully processes the GlaMBIE CSV files and generates the 5 figures. The main code issue is that it never attempts to create a projection comparison -- the data for GlacierMIP/CMIP6 projections would need to come from the related work papers, but the agent never extracted or synthesized this information.

### 5. Root Cause

**Primary failure mode: Incomplete task understanding / missing required analysis component.**

The agent correctly processed the observational data and produced good quality historical analysis, but completely missed that the scoring checklist requires a comparison of observations with model projections and future outlook (weight 0.30). This is the single largest score loss. The task_plan never included this as a claim, suggesting the planning phase failed to identify this requirement from the paper. Additionally, the report does not compute several specific quantitative metrics the checklist demands (cumulative total, sub-period averages, ice-sheet comparison).

---

## Earth_001: NOAA Cloud Seeding Records (Score: 38.11/100)

**Workspace**: `/mnt/20t/wxh/ResearchClawBench/workspaces/Earth_001_20260503_210001/`

### 1. Score Breakdown

| Item | Type | Weight | Score | Max Possible |
|------|------|--------|-------|--------------|
| 0: Dataset stats + LLM accuracy (text) | text | 0.22 | 25 | 22 |
| 1: Geographic concentration map (image) | image | 0.20 | 42 | 20 |
| 2: Annual activity trend (image) | image | 0.20 | 46 | 20 |
| 3: Purpose composition (image) | image | 0.19 | 32 | 19 |
| 4: Agent-apparatus heatmap (image) | image | 0.19 | 47 | 19 |
| **Total** | | **1.00** | **38.11** | **100** |

**Low-scoring items and judge reasoning:**

- **Item 0 (score 25/100, weight 0.22):** The criterion requires dataset size (832 records), temporal coverage (2000-2025), state coverage (13 states), **and** LLM extraction accuracy (overall 98.38%, field-level 92-100%). The report correctly states 832 records, 2000-2025, and 13 states, but **does not mention or verify LLM extraction accuracy** at all. The accuracy metrics are part of the paper's methodology (using LLM to extract structured data from PDF reports) and the agent never addresses this.

- **Item 3 (score 32/100, weight 0.19):** The criterion requires correct multi-label purpose processing where combined labels like "augment snowpack, increase precipitation" should be split into separate concept-level counts. The report preserves combined labels as distinct categories rather than fully splitting them, resulting in an incomplete normalization procedure. The overall ranking is roughly correct but the methodology does not match the target paper's approach.

### 2. Task Understanding

The task_plan.json is well-structured with 9 claims covering data overview, choropleth, state rankings, annual counts, purpose composition, agent-apparatus summary, heatmap, and state operational profiles. The plan is thorough for the descriptive analysis but **misses the LLM extraction accuracy verification** that the checklist evaluates. The plan also does not explicitly require multi-label splitting for purpose fields.

### 3. Report Quality

This is the best report of the four Earth tasks. It is comprehensive (200 lines), well-organized, and includes all 5 required figures. The analysis is transparent and reproducible. Key strengths:
- Clear data overview with exact counts
- Strong spatial analysis with cumulative share percentages
- Informative temporal phase analysis
- Good agent-apparatus cross-tabulation

**Missing/weak:**
- No mention of LLM extraction accuracy (98.38% overall, 92-100% field-level)
- Purpose labels not fully normalized (combined labels kept as-is rather than split)
- Missing jittered point overlay on the choropleth map

### 4. Code Quality

Single script `code/analyze_cloud_seeding.py` produces all outputs and figures. The code is clean and reproducible. The main issue is a design decision: multi-label purpose strings were preserved rather than split into individual concept-level counts, which the scoring checklist penalizes.

### 5. Root Cause

**Primary failure mode: Missing checklist-specific metrics + incomplete data preprocessing.**

The agent produced a good descriptive analysis but missed two specific requirements:
1. **LLM extraction accuracy metrics** -- the paper describes using an LLM pipeline to extract structured data from PDF reports and reports 98.38% accuracy. The agent never mentions this, likely because it focused on the downstream structured CSV data rather than the paper's data extraction methodology.
2. **Multi-label purpose splitting** -- the checklist expects individual concept-level counts (splitting "augment snowpack, increase precipitation" into two separate counts), but the agent preserved combined labels as distinct categories.

Despite these gaps, this was the highest-scoring Earth task because the visual outputs (geographic map, temporal trend, heatmap) were well-executed and closely matched the expected patterns.

---

## Earth_002: Mangrove TC + SLR Composite Risk (Score: 21.2/100)

**Workspace**: `/mnt/20t/wxh/ResearchClawBench/workspaces/Earth_002_20260503_201943/`

### 1. Score Breakdown

| Item | Type | Weight | Score | Max Possible |
|------|------|--------|-------|--------------|
| 0: Global risk percentages by SSP (text) | text | 0.40 | 5 | 40 |
| 1: Global risk distribution maps (image) | image | 0.30 | 46 | 30 |
| 2: SSP370 hotspot maps (image) | image | 0.20 | 18 | 20 |
| 3: Risk area percentages across SSPs (image) | image | 0.10 | 18 | 10 |
| **Total** | | **1.00** | **21.2** | **100** |

**Low-scoring items and judge reasoning:**

- **Item 0 (score 5/100, weight 0.40):** The criterion requires quantitative proportions: approximately 40-56% of global mangrove areas face high to severe combined risk under all three SSP scenarios, with SSP245 < SSP370 < SSP585. The report defines a composite risk index and discusses hotspots, but **never quantifies the global percentage of mangrove area at high-to-severe risk levels**, nor reports explicit percentages for each SSP scenario. The key metric is entirely absent.

- **Item 2 (score 18/100, weight 0.20):** The criterion requires detailed SSP370 hotspot maps showing concentrated severe risk (score 5) in specific locations (Philippines, eastern Vietnam, northern Mozambique, Central America). The agent's figures are global-scale and country-aggregated rather than regional hotspot panels, and do not show SSP370-specific severe-risk classes.

- **Item 3 (score 18/100, weight 0.10):** The criterion requires a bar chart comparing risk area percentages across SSPs with six risk categories. The agent produced such a chart, but the severe-risk percentages are **drastically different** from the target (~21.5% vs ~1% for SSP2-4.5 and ~99% vs ~13% for SSP5-8.5). The methodology or calibration is fundamentally inconsistent with the reference results.

### 2. Task Understanding

The task_plan.json includes 7 claims covering category-wise risk shares, global frequency/risk changes under 2C warming, regional risk changes, global hotspot map, damage profiles, country risk change choropleth, and composite risk scenarios. The plan addresses the task broadly but **misses the critical requirement** to quantify the global percentage of mangrove area at each risk level for each SSP scenario.

### 3. Report Quality

The report is comprehensive (260 lines) and well-written. It successfully:
- Reconstructs TCRI-style baseline risk (96.4% from Cat 4-5, matching the ~97% target)
- Reproduces the 2C analogue changes (-2% frequency, +3% risk)
- Creates composite risk index combining TC and SLR exposure
- Generates 4 required figures

**Missing/wrong:**
- Never reports what percentage of global mangrove area falls into high/severe combined risk categories -- the highest-weight text criterion
- Risk area percentage bar chart has wildly wrong values (off by an order of magnitude)
- No SSP370-specific regional hotspot panels with discrete risk scores
- Composite index normalization appears miscalibrated (99% severe risk under SSP5-8.5 vs 13% in the paper)

### 4. Code Quality

Single script `code/mangrove_risk_analysis.py`. The code handles geospatial data (GeoPackage, NetCDF), performs spatial joins, computes risk indices, and generates maps. The main issue is in the **composite risk index calibration**: the normalization scheme (clipping to 5th-95th percentile, equal weighting) produces fundamentally different risk class distributions than the paper's methodology. The severe-risk fractions are off by more than an order of magnitude.

### 5. Root Cause

**Primary failure mode: Incorrect quantitative calibration + missing key metric.**

Two interrelated problems:
1. **Missing global risk percentage computation**: The highest-weight criterion (0.40) asks for the percentage of global mangrove area at high-to-severe combined risk. The agent never computes this, focusing instead on country-level hotspot rankings.
2. **Miscalibrated composite risk index**: The risk class percentages in the bar chart are drastically wrong (e.g., ~99% severe for SSP5-8.5 vs ~13% in the paper), suggesting the normalization/binning methodology is fundamentally different from the paper's approach. The 50/50 TC/SLR weighting with percentile-based normalization does not reproduce the paper's more nuanced risk classification.

---

## Earth_003: FuXi/FengWu Weather Forecasting (Score: 6.0/100)

**Workspace**: `/mnt/20t/wxh/ResearchClawBench/workspaces/Earth_003_20260503_201946/`

### 1. Score Breakdown

| Item | Type | Weight | Score | Max Possible |
|------|------|--------|-------|--------------|
| 0: FuXi ACC lead times + ECMWF EM stats (text) | text | 0.20 | 0 | 20 |
| 1: Multi-panel ACC/RMSE comparison (image) | image | 0.30 | 20 | 30 |
| 2: FuXi vs ECMWF EM comparison (image) | image | 0.20 | 0 | 20 |
| 3: Spatial Z500 forecast maps (image) | image | 0.30 | 0 | 30 |
| **Total** | | **1.00** | **6.0** | **100** |

**Low-scoring items and judge reasoning:**

- **Item 0 (score 0/100, weight 0.20):** The criterion requires FuXi's ACC-based skillful lead times for Z500 (extended from 9.25 to 10.5 days) and T2M (from 10 to 14.5 days), and percentages where FuXi outperforms ECMWF EM (67.92% ACC, 53.75% RMSE over 240 combinations). The report **discusses FengWu vs GraphCast instead**, providing completely different lead times and metrics. The FuXi vs ECMWF ensemble statistics are never mentioned.

- **Item 1 (score 20/100, weight 0.30):** The criterion requires a multi-panel figure comparing ACC and RMSE of ECMWF HRES, GraphCast, and FuXi for 8 variables across 15 days. The agent's plot only shows two FengWu curves (z500 and t2m) with an ACC=0.6 line, omitting GraphCast, HRES, and all other variables, and does not display RMSE at all.

- **Item 2 (score 0/100, weight 0.20):** The criterion requires FuXi vs ECMWF EM normalized ACC/RMSE difference plots over 15 days for multiple variables. The agent produced no such figure at all.

- **Item 3 (score 0/100, weight 0.30):** The criterion requires spatial Z500 geopotential height forecast maps at multiple lead times comparing ERA5, ECMWF HRES, and FuXi. None of the agent's figures show spatial forecast fields -- they are architecture diagrams, line plots, bar charts, and noisy input snapshots.

### 2. Task Understanding

**This is the most severe failure: the agent worked on the wrong paper.**

The INSTRUCTIONS.md describes the task as developing a "cascade machine learning forecasting system using three specialized U-Transformer models" -- this is FuXi, not FengWu. The data files include `006.nc` which is labeled as "FuXi output forecasts." However, the paper_summary.md describes FengWu, and the task_plan.json is entirely framed around FengWu (z500 RMSE 651 vs 733, 80% of 880 predictands, skillful lead time 10.75 days).

The scoring checklist evaluates FuXi-specific criteria:
- FuXi vs ECMWF HRES and ECMWF EM comparisons
- FuXi's cascade architecture with three specialized models
- FuXi's 15-day forecast performance
- Spatial Z500 forecast maps

The agent instead reproduced FengWu's metrics from a different paper in the related_work folder, producing figures that address none of the FuXi scoring criteria.

### 3. Report Quality

The report is technically competent but fundamentally misdirected. It describes a "Partial Reproduction and Data Audit of FengWu-Style Medium-Range Global Weather Forecasting" when the task and checklist evaluate FuXi. The report includes:
- Data structure validation (useful but insufficient)
- Sample one-step verification (ACC proxy ~0.5 for all channels, suggesting meaningless diagnostics)
- Reconstructed benchmark targets from the FengWu paper (wrong paper)
- Architecture diagram of FengWu (not FuXi)

The sample verification metrics (RMSE ~14, ACC ~0.5 across all channels) appear suspicious -- near-random performance suggests the comparison may not be meaningful.

### 4. Code Quality

Single script `code/analyze_fengwu_task.py`. The code inspects NetCDF files and generates figures. The main issue is not code quality but that the code implements the wrong analysis entirely (FengWu instead of FuXi).

### 5. Root Cause

**Primary failure mode: Wrong paper identification -- catastrophic task misunderstanding.**

The agent confused FuXi (the target paper described in INSTRUCTIONS.md and the scoring checklist) with FengWu (a related work paper in the workspace). The paper_summary.md was generated for FengWu (related_work/paper_003), and the task_plan followed suit. The scoring checklist evaluates FuXi-specific metrics (cascade U-Transformer, ECMWF EM comparison, 15-day forecasts, spatial Z500 maps), none of which the agent attempted. This is the worst-performing task across all four Earth tasks, scoring only 6.0/100.

Contributing factors:
- The INSTRUCTIONS.md task description is somewhat generic ("cascade machine learning forecasting system using three specialized U-Transformer models") and does not explicitly say "FuXi"
- The paper_summary.md appears to have been pre-generated for the wrong paper (FengWu)
- The agent did not cross-reference the data files (006.nc is labeled as FuXi output) with the task description
- Even if working on FengWu, the agent could not run the model and instead just recovered numbers from the paper text, yielding only "partial" support for claims

---

## Cross-Task Summary

| Task | Score | Primary Failure Mode |
|------|-------|---------------------|
| Earth_000 | 18.2 | Missing model projection comparison (weight 0.30, score 0); incomplete quantitative metrics |
| Earth_001 | 38.11 | Missing LLM accuracy metrics; incomplete multi-label preprocessing |
| Earth_002 | 21.2 | Missing global risk percentage computation (weight 0.40, score 5); miscalibrated risk index |
| Earth_003 | 6.0 | **Wrong paper** -- analyzed FengWu instead of FuXi; all FuXi-specific criteria unmet |

### Common Patterns

1. **Missing key metrics that the checklist evaluates**: In Earth_000, Earth_001, and Earth_002, the agent produces reasonable analysis but fails to compute specific quantitative metrics that the scoring checklist demands. The task_plan often misses these requirements, suggesting the planning phase does not sufficiently extract evaluation criteria from the paper.

2. **No model projection / forward-looking analysis**: Both Earth_000 and Earth_002 lose significant score on forward-looking analysis (model projections, scenario comparisons). The agent tends to focus on reproducing historical/observational patterns and neglects synthesis with projections or literature benchmarks.

3. **Calibration/normalization errors**: Earth_002 produces a risk index with values off by an order of magnitude. The agent's composite risk methodology (simple percentile normalization with 50/50 weighting) does not match the paper's more sophisticated approach.

4. **Paper identification failure**: Earth_003 demonstrates that the agent can completely misidentify which paper to reproduce, resulting in near-zero scores across all criteria. The paper_summary.md pipeline appears to have a bug that led to summarizing the wrong paper.

5. **Visualization gaps**: Multiple tasks lose points because figures do not match the expected multi-panel, multi-variable structure of the original papers. The agent tends to produce simpler plots (single curves, bar charts) rather than the comprehensive multi-panel comparisons that scoring criteria expect.

### Recommendations for Agent Improvement

1. **Validate paper identity**: Cross-reference INSTRUCTIONS.md task description, data file labels, and paper_summary.md to ensure the correct target paper is identified before planning begins.

2. **Extract scoring criteria more carefully**: The task_plan should explicitly attempt to identify what quantitative metrics and figure types the paper requires, including forward-looking analyses like model projections.

3. **Compute all requested percentages/aggregates**: When the paper reports specific percentages (e.g., "40-56% of area at high risk"), the agent must compute and report these exact metrics, not just qualitative hotspot rankings.

4. **Multi-label data preprocessing**: For fields with combined labels, implement proper splitting/normalization to match paper methodology.

5. **Attempt multi-panel figure reproduction**: When papers contain multi-panel comparison figures, the agent should attempt to reproduce the multi-panel structure rather than simplified single-variable plots.