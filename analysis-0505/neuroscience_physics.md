# Neuroscience + Physics Domain Analysis

## Neuroscience: 13.2 / 2.0 / 1.3 / 12.9 → Avg: 7.4
## Physics: 22.6 / 35.5 / 20.2 / 39.0 → Avg: 29.3

---

# Neuroscience

## Neuroscience_000 (Score: 13.2) — Mouse Behavior Classification

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.20 | 28 | PR curves for Attack (6 conditions) |
| 1 | image | 0.20 | 0 | SHAP Lab1 vs Lab2 comparison |
| 2 | image | 0.20 | 0 | SHAP Male vs Female comparison |
| 3 | image | 0.20 | 0 | SHAP RI vs CSDS comparison |
| 4 | image | 0.20 | 38 | Permutation importance top-15 |

### Task Understanding Analysis
- **Claims**: 13 claims. C8 "supported".
- Claims cover classifier training, PR curves, permutation importance, cross-validation.
- **Fatal gap**: 60% of checklist weight (items 1-3) requires SHAP analysis comparing specific condition pairs (Lab1/Lab2, Male/Female, RI/CSDS). Claims mention permutation importance but NOT TreeSHAP condition-specific comparisons.

### Report Quality Issues
- Report (233 lines, 7 images) — has PR curves and importance plots.
- PR curves partially correct (28) — shows 6 conditions but AP values may differ.
- Permutation importance decent (38) — captures feature ranking.
- **Zero SHAP analysis** — 3 out of 5 items (60% weight) score 0 because no SHAP comparisons exist.

### Root Cause
**Missing SHAP analysis** — Claims specify permutation importance but not SHAP. The checklist is heavily SHAP-focused (3/5 items). Agent didn't recognize SHAP as the required interpretability method.

---

## Neuroscience_001 (Score: 2.0) — Drosophila DMN Visual System

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.15 | 5 | DMN architecture and parameters |
| 1 | image | 0.25 | 5 | Validation against 26 studies, 32 ON/OFF cells |
| 2 | image | 0.25 | 0 | T4/T5 direction selectivity, DSI metrics |
| 3 | image | 0.25 | 0 | Ablation (connectome + task optimization) |
| 4 | image | 0.10 | 0 | UMAP clustering of 50 DMNs |

### Task Understanding Analysis
- **Claims**: 14 claims. C14 "partial".
- Claims focus on extracting parameters from pretrained models (validation loss, learned parameters, synaptic scaling).
- **Critical gap**: Checklist requires running the DMN models with visual stimuli to get response data for direction selectivity, ablation, and UMAP. Claims only extract static parameters — no simulation.

### Report Quality Issues
- Report (253 lines, 7 images) — has parameter heatmaps but no simulation outputs.
- All items ≤ 5 — agent never ran the DMN models, only extracted checkpoint data.
- Direction selectivity analysis impossible without simulation → 0.
- UMAP of model responses impossible without simulation → 0.

### Root Cause
**Simulation not performed** — Task requires running 50 pretrained deep network models with visual stimuli. Agent only extracted static model parameters (weights, biases) without actually simulating visual responses. This is like analyzing car specs without ever driving the car.

---

## Neuroscience_002 (Score: 1.3) — FlyTracing Neuron Segment Merging

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | text | 0.15 | 0 | FlyTracing dataset construction (FAFB+FlyWire) |
| 1 | text | 0.25 | 0 | PointNet++ + Connect-Embed fusion comparison |
| 2 | text | 0.25 | 0 | EmbedNet adaptive λ₃ ablation |
| 3 | image | 0.20 | 5 | PR curves on degraded EM blocks |
| 4 | image | 0.15 | 2 | Connect-Embed voxel embedding visualization |

### Task Understanding Analysis
- **Claims**: 10 claims. C10 "supported".
- Claims describe training tabular classifiers (logistic regression, RF, gradient boosting, MLP) on simulated CSV data.
- **Total mismatch**: Checklist requires PointNet++, Connect-Embed (3D point cloud neural networks), and voxel embedding analysis. Agent trained flat classifiers on tabular features instead.

### Report Quality Issues
- Report (203 lines, 5 images) — all outputs are for tabular classifiers.
- No PointNet++ implementation, no 3D point cloud processing.
- No Connect-Embed or EmbedNet analysis.
- Agent treated the task as "binary classification on tabular data" instead of "3D connectomics neural network evaluation."

### Root Cause
**Complete task misunderstanding** — Agent reduced a 3D neural network evaluation task to flat tabular classification. The `train_simulated.csv` and `test_simulated.csv` are pre-extracted features, but the checklist expects the full deep learning pipeline analysis. Claims are completely misaligned with the checklist.

---

## Neuroscience_003 (Score: 12.9) — DELVE Feature Selection

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | text | 0.15 | 38 | Bottom-up trajectory-aware feature selection |
| 1 | text | 0.25 | 0 | Benchmark against 11 methods |
| 2 | text | 0.25 | 0 | Robustness to noise (low SNR, dropout) |
| 3 | image | 0.15 | 48 | PHATE all-features (diffuse) |
| 4 | image | 0.20 | 0 | PHATE DELVE-selected features (smooth trajectory) |

### Task Understanding Analysis
- **Claims**: 9 claims. C9 "supported".
- Claims cover dataset inventory, trajectory construction, feature ranking, PHATE comparison.
- **Gap**: Item 1 (25% weight) requires comparison against 11 named methods — claims don't specify this.
- **Gap**: Item 2 (25% weight) requires noise robustness analysis — claims mention "confounding variation" but not the specific noise types.

### Report Quality Issues
- Report (235 lines, 5 images) — reasonable.
- Methodological description scored well (38) — correctly explains bottom-up approach.
- PHATE all-features plot scored 48 — correctly shows diffuse embedding.
- PHATE DELVE-selected plot scored 0 — missing or incorrect.
- No 11-method benchmark → 0 on 0.25 weight.
- No noise robustness → 0 on 0.25 weight.

### Root Cause
**Incomplete implementation** — Agent implemented the core feature selection but skipped the comparative benchmarking (50% of score weight). PHATE visualization partially works.

---

# Physics

## Physics_000 (Score: 22.6) — Icosahedral Nanoclusters

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.30 | 22 | Caspar-Klug geometric relationships |
| 1 | image | 0.40 | 40 | Optimal mismatch formula verification |
| 2 | image | 0.30 | 0 | Atomic deposition growth simulations |

### Task Understanding Analysis
- **Claims**: 9 claims. C9 "supported".
- Claims cover Mackay sequence, hexagonal lattice, mismatch analysis, growth trajectories.
- **Gap**: Item 2 requires growth simulations — claims mention "MC and Ch1 growth trajectories" but agent used provided data rather than running simulations.

### Report Quality Issues
- Report (249 lines, 6 images) — good length.
- Optimal mismatch verification scored well (40) — correctly reproduced formula.
- Growth simulations completely missing → 0 on 0.30 weight.
- Caspar-Klug geometric figure partial (22) — concept correct but details off.

### Root Cause
**Missing simulation** — Growth simulations were not implemented. Agent analyzed provided trajectory data but didn't generate new simulation outputs.

---

## Physics_001 (Score: 35.5) — MATBG Superfluid Stiffness

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.35 | 42 | Density-dependent superfluid stiffness |
| 1 | image | 0.35 | 20 | Temperature power-law dependence |
| 2 | image | 0.30 | 46 | Current dependence (DC + microwave) |

### Task Understanding Analysis
- **Claims**: 10 claims. C10 "supported".
- Claims are well-matched: density dependence, temperature fits, current suppression, Ginzburg-Landau comparison.

### Report Quality Issues
- Report (167 lines, 3 images) — short but focused.
- Density dependence (42) and current dependence (46) scored well — agent correctly processed the data.
- Temperature dependence weak (20) — power-law exponent extraction incorrect or incomplete.

### Root Cause
**Partial success** — Two of three analyses work well. Temperature power-law fitting needs more careful implementation (BCS vs nodal vs power-law model comparison).

---

## Physics_002 (Score: 20.2) — Random Circuit Sampling (RCS) XEB Fidelity

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.20 | 0 | Fixed depth, fidelity vs N (qubits) |
| 1 | image | 0.20 | 38 | N=40, fidelity vs depth |
| 2 | image | 0.15 | 0 | N=56 MB regression probability |
| 3 | text | 0.20 | 3 | Gate-counting model consistency |
| 4 | image | 0.25 | 48 | N=40 linear XEB reproduction |

### Task Understanding Analysis
- **Claims**: 9 claims. C9 "supported".
- Claims cover XEB computation, depth scans, statistical uncertainty, depth-decay model.
- **Gap**: Claims focus on N=40 analysis. Items 0 and 2 require N-scanning (variable qubit count) and N=56 analysis — not covered.

### Report Quality Issues
- Report (234 lines, 4 images) — adequate.
- N=40 linear XEB scored best (48) — excellent reproduction.
- N=40 depth scan decent (38) — trends match.
- N-qubit scanning (0) and N=56 (0) completely missing — agent only analyzed N=40 data.
- Gate-counting model barely attempted (3).

### Root Cause
**Incomplete scope** — Agent focused exclusively on N=40 subset. Items requiring N-scanning or N=56 analysis were not attempted, likely because the data for those configurations wasn't found or processed.

---

## Physics_003 (Score: 39.0) — Floquet-Bloch tr-ARPES ⭐ Best Physics

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.50 | 42 | Energy-momentum map (Dirac + replica) |
| 1 | image | 0.30 | 30 | Polarization angle dependence |
| 2 | text | 0.20 | 45 | Anisotropy mechanism (Floquet vs LAPE) |

### Task Understanding Analysis
- **Claims**: 9 claims. C8 "supported".
- Claims well-matched: Dirac point extraction, replica band positions, polarization analysis, mechanism comparison.

### Report Quality Issues
- Report (174 lines, 4 images) — compact.
- Energy-momentum map scored 42 on 0.50 weight — good reproduction of main Dirac cone + replica.
- Mechanism discussion scored 45 — correctly contrasts Floquet vs LAPE.
- Polarization dependence weaker (30) — visual demonstration of anisotropy incomplete.

### Root Cause
**Near-success** — Agent correctly handled h5 data extraction and physical analysis. The 0.50-weight item's 42 score drives the total. Polarization analysis needs more quantitative detail.

---

## Domain-Level Patterns

### Neuroscience (Avg 7.4 — worst domain)
1. **Simulation gap** — Neuro tasks require running neural networks or complex models; agent only analyzes static data.
2. **SHAP omission** — Neuro_000 lost 60% of score by not implementing TreeSHAP.
3. **Task misunderstanding** — Neuro_002 completely wrong analysis direction (tabular instead of 3D point clouds).

### Physics (Avg 29.3 — mid-range)
1. **Data-driven tasks succeed** — Physics_001, _003 work well with provided datasets.
2. **Simulation tasks fail** — Physics_000 growth simulations, Physics_002 N-scanning.
3. **Focused analysis wins** — Physics_003's focused tr-ARPES analysis with 3 well-matched claims → best score.