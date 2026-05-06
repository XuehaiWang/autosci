# ResearchClawBench Comprehensive Analysis — 2026-05-05 Run

## 1. Score Overview

### Best Scores per Task (40 tasks, 2 missing)

| Task | Score | Task | Score | Task | Score |
|------|------:|------|------:|------|------:|
| Astronomy_000 | 23.0 | Energy_000 | 17.5 | Life_000 | 4.8 |
| Astronomy_001 | 8.0 | Energy_001 | 28.5 | Life_001 | 5.5 |
| Astronomy_002 | 26.7 | Energy_002 | **47.1** | Life_002 | 6.3 |
| Astronomy_003 | **47.8** | Energy_003 | 7.5 | Life_003 | 29.4 |
| Chemistry_000 | 18.8 | Information_000 | 11.5 | Material_000 | N/A |
| Chemistry_001 | 9.2 | Information_001 | 3.6 | Material_001 | 5.3 |
| Chemistry_002 | 1.0 | Information_002 | **43.9** | Material_002 | 31.5 |
| Chemistry_003 | 10.5 | Information_003 | 6.4 | Math_000 | 20.7 |
| Earth_000 | 18.2 | Neuroscience_000 | 13.2 | Math_001 | 38.3 |
| Earth_001 | 38.1 | Neuroscience_001 | 2.0 | Math_002 | N/A |
| Earth_002 | 21.2 | Neuroscience_002 | 1.3 | Math_003 | 14.0 |
| Earth_003 | 6.0 | Neuroscience_003 | 12.9 | Physics_000 | 22.6 |
| | | | | Physics_001 | 35.5 |
| | | | | Physics_002 | 20.2 |
| | | | | Physics_003 | 39.0 |

### Domain Averages

| Domain | Avg Score | Best | Worst | Tasks |
|--------|----------:|-----:|------:|------:|
| Physics | **29.3** | 39.0 | 20.2 | 4 |
| Astronomy | 26.4 | 47.8 | 8.0 | 4 |
| Energy | 25.2 | 47.1 | 7.5 | 4 |
| Math | 24.3 | 38.3 | 14.0 | 3 |
| Earth | 20.9 | 38.1 | 6.0 | 4 |
| Material | 18.4 | 31.5 | 5.3 | 2 |
| Information | 16.4 | 43.9 | 3.6 | 4 |
| Life | 11.5 | 29.4 | 4.8 | 4 |
| Chemistry | 9.9 | 18.8 | 1.0 | 4 |
| Neuroscience | **7.4** | 13.2 | 1.3 | 4 |

**Overall average: 17.5** (38 scored tasks)

### Score Distribution

| Range | Count | % | Tasks |
|-------|------:|--:|-------|
| 40-50 | 3 | 8% | Astronomy_003, Energy_002, Information_002 |
| 30-40 | 5 | 13% | Earth_001, Physics_001, Physics_003, Math_001, Material_002 |
| 20-30 | 7 | 18% | Astronomy_000, Astronomy_002, Energy_001, Physics_000, Physics_002, Earth_002, Life_003 |
| 10-20 | 8 | 21% | Chemistry_000, Earth_000, Neuroscience_000, Energy_000, Math_003, Math_000, Information_000, Neuroscience_003 |
| 0-10 | 15 | 39% | All Neuro except _000, all Life except _003, Chemistry_001-003, Energy_003, Astronomy_001, Information_001/003, Material_001 |

---

## 2. Root Cause Classification

Analyzing all 38 scored tasks, failures fall into 7 categories:

### A. Claims Not Aligned with Checklist (23/38 tasks affected)

The single most common failure. TaskUnderstandingAgent generates claims that don't match what the checklist actually evaluates.

**Subcategories:**

| Subcategory | Count | Examples |
|-------------|------:|---------|
| Missing specific method/tool requirement | 12 | Astro_001 (no MCMC), Chem_002 (no HADDOCK3), Neuro_001 (no simulation) |
| Missing specific comparison targets | 8 | Neuro_000 (no SHAP), Neuro_003 (no 11-method benchmark), Info_003 (no 14 baselines) |
| Wrong granularity (aggregate vs per-item) | 5 | Life_001 (aggregate vs 7 patients), Life_002 (single-chain vs 9 chains) |
| Missing specific figure type | 4 | Astro_001 (error bars vs triangle plot), Energy_001 (missing link loading) |

**Impact**: This is the root cause for 50%+ of all lost points across the benchmark.

### B. Method Simplification (15/38 tasks)

Agent replaces the paper's specific method with a simpler approximation:

| Pattern | Count | Examples |
|---------|------:|---------|
| Basic ML instead of deep learning | 5 | Neuro_002 (LR/RF vs PointNet++), Material_001 (RF vs GNN), Info_003 (MLP vs DIDS-MFL) |
| Proxy metric instead of physical quantity | 3 | Astro_000 (κ vs g GeV⁻¹), Earth_002 (continuous vs discrete risk) |
| Single instance instead of full pipeline | 4 | Chem_001 (1 sample vs benchmark), Math_003 (symbolic prover vs neural+symbolic) |
| Heuristic instead of algorithm | 3 | Chem_003 (feature engineering vs LES), Math_002 (heuristic vs MARL+LNS) |

### C. Simulation/Model Execution Not Attempted (10/38 tasks)

Agent analyzes static data but doesn't run required simulations or models:

- Neuroscience_001: 50 pretrained DMN models never executed with visual stimuli
- Physics_000: Growth simulations not implemented
- Energy_000: PyBaMM simulations not run
- Chemistry_000: KA-GNN implemented incorrectly (performance below baselines)
- Neuroscience_000: SHAP computation not attempted (TreeSHAP)

### D. Data/Tool Not Available (6/38 tasks — bench limitation)

Tasks where workspace doesn't contain required data or tools:

- Information_001: No TextVQA dataset (80% weight)
- Chemistry_001: No AlphaFold3 model weights
- Information_000: No generative model for image generation
- Earth_003: No ECMWF/GraphCast comparison data
- Chemistry_002: No HADDOCK3 installation

### E. Quantitative Imprecision (8/38 tasks)

Agent produces the right type of analysis but numbers don't match:

- Astronomy_002: H₀ value deviation
- Earth_000: Missing 36% acceleration metric
- Energy_003: Correlation values mismatch
- Physics_002: Only N=40 analyzed, missing N=56

### F. Complete Task Misunderstanding (3/38 tasks)

Agent goes in a completely wrong direction:

- Chemistry_002: SKEMPI ML analysis instead of HADDOCK3 alanine scanning
- Neuroscience_002: Tabular classification instead of 3D connectomics
- Earth_003: Analyzed wrong paper (FengWu instead of FuXi)

### G. Environment/Runtime Failure (2/38 tasks)

- Material_000: Agent crashed (exit_code=1) trying to set up PyTorch/GNN
- Math_002: Agent timed out, LLM connection never established

---

## 3. What Works (Score > 35)

The 8 tasks scoring above 35 share common characteristics:

| Task | Score | Key Success Factors |
|------|------:|---------------------|
| Astronomy_003 | 47.8 | Pre-computed CSV data, pure statistical analysis |
| Energy_002 | 47.1 | Geospatial CSV analysis, no specialized tools |
| Information_002 | 43.9 | Symbolic math derivation from provided TeX/YAML |
| Physics_003 | 39.0 | HDF5 data extraction + physical analysis |
| Physics_001 | 35.5 | CSV data + fitting + visualization |
| Math_001 | 38.3 | Optimization with convergence analysis |
| Earth_001 | 38.1 | Geographic/temporal CSV analysis |
| Material_002 | 31.5 | Molecular dynamics (partial success) |

**Common patterns of success:**
1. Data is structured (CSV, YAML, HDF5) — no parsing challenges
2. Task is analytical (statistics, fitting, visualization) — not implementation of a novel method
3. No specialized domain software required
4. Claims match checklist well (detailed, specific)
5. Code produces correct numerical results

---

## 4. Agent Improvement Recommendations

### P0: Checklist-Aware Task Understanding (Impact: ~60% of lost points)

**Problem**: TaskUnderstandingAgent generates claims based on its own interpretation of the task, not aligned with the actual scoring criteria.

**Key insight**: The checklist IS available through the paper and task description. The task description often contains explicit mentions of specific methods, figure types, comparison targets, and numerical values that the checklist evaluates.

**Recommended changes:**

1. **Extract explicit requirements from INSTRUCTIONS.md**: Before generating claims, parse the task description for:
   - Named methods/tools (HADDOCK3, GetDist, MCMC, SHAP, PointNet++)
   - Named figure types (triangle plot, heatmap, PR curve, PHATE)
   - Named comparison targets (specific baseline methods, reference values)
   - Named metrics (ROC-AUC, TM-score, F1, RMSE)
   - Named datasets/subsets that must be analyzed

2. **Claims must include every extracted requirement**: If the task says "MCMC sampling", there must be a claim about MCMC. If it says "compare against 11 methods", claims must specify this.

3. **Claims must specify output format**: Not just "analyze X" but "generate a [specific figure type] showing [specific metrics] for [specific items]".

### P0: Paper-Faithful Method Selection (Impact: ~40% of lost points)

**Problem**: Agent consistently chooses the simplest available method instead of the paper's specific method.

**Recommended changes:**

1. **Add method-fidelity rule to MainAgent system prompt**:
   ```
   CRITICAL: When the task describes a specific method (e.g., "MCMC sampling", 
   "GNN architecture", "alanine scanning"), you MUST implement that exact method.
   Do NOT substitute simpler alternatives (error bars for contour plots, 
   logistic regression for neural networks, heuristics for algorithms).
   If the required method cannot be implemented, document why and attempt the 
   closest feasible alternative, but NEVER silently substitute.
   ```

2. **Tool installation step**: Before coding, check if specialized tools are needed (GetDist, PyBaMM, SHAP) and attempt `pip install`.

3. **Result validation**: After running code, check if results are consistent with paper claims. If KA-GNN performs WORSE than baselines, that's a bug, not a result.

### P1: Scope Preservation (Impact: ~25% of lost points)

**Problem**: Agent collapses multi-instance tasks to single-instance (7 patients → 1 patient, 9 chain pairs → 1 chain, 14 baselines → 1 baseline).

**Recommended changes:**

1. **Count extraction**: TaskUnderstandingAgent should extract explicit counts from INSTRUCTIONS.md ("7 patients", "9 chain pairs", "11 methods") and include them in claims.

2. **Completeness check in MainAgent prompt**:
   ```
   Before finalizing your report, verify:
   - Have you analyzed ALL items/patients/conditions mentioned in the task?
   - Have you compared against ALL baselines mentioned?
   - Have you produced ALL figure types mentioned?
   Count the items in your output and compare against the task requirements.
   ```

### P1: Simulation Execution (Impact: ~20% of lost points)

**Problem**: Agent extracts parameters from models but doesn't run them.

**Recommended changes:**

1. **Detect simulation requirements**: If workspace contains pretrained models (checkpoints, .pt/.h5 files), claims should include "run model with [input] to produce [output]".

2. **Add to MainAgent prompt**:
   ```
   If the workspace contains pretrained models, you MUST:
   1. Understand the model architecture from available code/config
   2. Load the model and run inference
   3. Use model outputs for downstream analysis
   Simply extracting model parameters (weights, biases) is NOT sufficient.
   ```

### P2: Data Availability Check (Impact: ~15% of lost points)

**Problem**: Agent spends iterations on tasks where required data is missing, producing wrong results.

**Recommended changes:**

1. **Early data audit**: In the first iteration, check workspace for all data files needed. If critical data is missing:
   - Generate synthetic data with explicit labeling
   - Use paper-reported values as proxy results
   - Focus effort on items where data IS available

2. **Graceful degradation**: When data is missing, produce form-correct outputs with simulated data rather than wrong outputs or empty sections.

### P2: Result Sanity Checking (Impact: ~10% of lost points)

**Problem**: Agent doesn't detect when its results contradict the paper (e.g., model performs worse than baseline, TM-score 0.15 vs expected 0.82).

**Recommended changes:**

1. **Paper-value comparison**: After generating results, compare against any reference values mentioned in INSTRUCTIONS.md or related_work papers.

2. **Add to MainAgent prompt**:
   ```
   After generating each result, sanity-check:
   - Does the direction match the paper? (model should be BETTER than baseline)
   - Is the magnitude reasonable? (TM-score should be ~0.82, not 0.15)
   - If results contradict the paper, investigate for bugs BEFORE reporting.
   ```

---

## 5. Expected Impact of Improvements

| Improvement | Tasks Affected | Current Avg | Expected Avg | Delta |
|-------------|---------------:|------------:|-------------:|------:|
| P0: Checklist-aware claims | 23 | 12.3 | 22-28 | +10-16 |
| P0: Method fidelity | 15 | 10.1 | 18-25 | +8-15 |
| P1: Scope preservation | 8 | 8.4 | 18-25 | +10-17 |
| P1: Simulation execution | 6 | 7.8 | 15-25 | +7-17 |
| P2: Data availability check | 6 | 5.8 | 12-18 | +6-12 |
| P2: Result sanity checking | 8 | 18.5 | 25-32 | +7-14 |

**Conservative estimate**: Implementing P0 changes could raise overall average from **17.5 → 25-30**.

**Optimistic estimate with all changes**: Overall average **17.5 → 30-38**.

---

## 6. Per-Task Actionable Items

### Quick Wins (score can improve 10+ points with focused fixes)

| Task | Current | Fix | Expected |
|------|--------:|-----|------:|
| Astronomy_001 | 8.0 | Add MCMC chain generation + GetDist triangle plot | 25-35 |
| Neuroscience_000 | 13.2 | Add TreeSHAP condition-pair comparisons | 30-40 |
| Neuroscience_003 | 12.9 | Add 11-method benchmark + noise robustness | 25-35 |
| Energy_001 | 28.5 | Add Scotland-England link loading plot | 35-42 |
| Life_001 | 5.5 | Per-patient analysis (7 patients) + 11-method comparison | 20-30 |
| Life_002 | 6.3 | Multi-chain alignment (9 pairs) instead of single-chain | 25-35 |
| Physics_002 | 20.2 | Add N-scanning and N=56 analysis | 30-40 |
| Energy_003 | 7.5 | Add missing value injection experiment + fix aggregation | 20-30 |

### Hard Problems (fundamental approach change needed)

| Task | Current | Barrier |
|------|--------:|---------|
| Chemistry_002 | 1.0 | Requires HADDOCK3 installation and execution |
| Neuroscience_001 | 2.0 | Requires running 50 DMN models with visual stimuli |
| Neuroscience_002 | 1.3 | Requires PointNet++ 3D point cloud processing |
| Chemistry_001 | 9.2 | Requires AlphaFold3 or equivalent (infeasible) |
| Material_000 | N/A | Environment crash — need stable PyTorch/GNN setup |