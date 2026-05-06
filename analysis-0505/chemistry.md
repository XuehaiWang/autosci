# Chemistry Domain Analysis

## Overall: 18.8 / 9.2 / 1.0 / 10.5 → Domain Avg: 9.9

---

## Chemistry_000 (Score: 18.8) — KA-GNN Molecular Property Prediction

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.45 | 18 | KA-GNN outperforms GCN/GAT across 7 datasets (ROC-AUC table) |
| 1 | text | 0.35 | 22 | Fourier KAN advantage mechanism/justification |
| 2 | text | 0.20 | 15 | KA-GAT interpretability (saliency maps, functional groups) |

### Task Understanding Analysis
- **Claims**: 10 claims. C10 "supported".
- Claims cover dataset overview, model comparison, efficiency, interpretability — reasonable coverage.
- **Gap**: Claims don't specify that KA-GNN must OUTPERFORM baselines, only "compare." Checklist explicitly requires KA-GNN to consistently beat GCN/GAT.

### Report Quality Issues
- Report has 206 lines, 5 images — adequate length.
- **Critical**: The KA-GNN implementation produced results WORSE than baselines (reverse of what the paper shows). This is a code correctness issue — the model architecture or training is buggy.
- No saliency/gradient significance maps generated for interpretability criterion.
- Fourier KAN advantage discussed but without concrete empirical evidence showing improvement.

### Root Cause
**Incorrect implementation** — KA-GNN model was implemented but performance is below baselines, indicating bugs in the architecture or training loop. The agent didn't recognize this as an error and reported the wrong results.

---

## Chemistry_001 (Score: 9.2) — AlphaFold 3 Protein-Ligand Docking

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | text | 0.30 | 5 | 76.4% success rate, comparison to AutoDock Vina |
| 1 | image | 0.25 | 18 | Protein-ligand complex visualization |
| 2 | text | 0.20 | 0 | Cross-complex generalization (nucleic acid, antibody) |
| 3 | image | 0.15 | 0 | Training convergence curve |
| 4 | text | 0.10 | 32 | Ablation study (diffusion + PairFormer) |

### Task Understanding Analysis
- **Claims**: 12 claims. C11 "supported".
- Claims attempt structural evaluation, ligand RMSD, baseline comparison — but the task requires running AlphaFold 3 or equivalent diffusion model, which is computationally infeasible in the bench environment.
- **Data limitation**: Only 1 sample protein (2L3R) provided. Checklist requires benchmark-scale results (76.4% success rate).

### Report Quality Issues
- Report (269 lines, 9 images) — longest Chemistry report.
- No actual model training or inference — agent performed structural analysis on the single provided sample.
- Training convergence curve impossible without model training → 0 score.
- Cross-complex generalization impossible with 1 sample → 0 score.

### Root Cause
**Infeasible task + scope collapse** — AlphaFold 3 cannot be trained in bench environment. Agent reduced to single-sample structural analysis, which doesn't satisfy any of the benchmark-scale requirements.

---

## Chemistry_002 (Score: 1.0) — HADDOCK3 Alanine Scanning

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.30 | 0 | ΔHADDOCK vs ΔΔG scatter (28 points, r=0.60) |
| 1 | text | 0.20 | 5 | Key residues from alanine scanning |
| 2 | text | 0.20 | 0 | HADDOCK3 alanine scanning protocol |
| 3 | text | 0.15 | 0 | Multi-interface targeting, glycan docking |
| 4 | text | 0.15 | 0 | CAPRI round 57 benchmarking |

### Task Understanding Analysis
- **Claims**: 12 claims. C12 "supported".
- **Critical mismatch**: Claims focus on structure-based contact analysis and SKEMPI mutation data analysis, NOT on running HADDOCK3 alanine scanning. Every checklist item requires HADDOCK3-specific outputs.
- Agent misunderstood the task: did ML feature analysis on SKEMPI data instead of running HADDOCK3 molecular docking.

### Report Quality Issues
- Report (241 lines, 6 images) — substantial but completely wrong direction.
- No HADDOCK3 installation or execution attempted.
- ΔHADDOCK vs ΔΔG scatter plot not produced (0 score on 0.30 weight item).
- Agent produced contact heatmaps and ML models — none relevant to checklist.

### Root Cause
**Complete task misunderstanding** — Agent interpreted "HADDOCK-oriented analysis" as "analyze interface contacts and SKEMPI mutations" instead of "run HADDOCK3 software." Claims mapped to the wrong analysis entirely. This is the worst failure mode.

---

## Chemistry_003 (Score: 10.5) — Latent Ewald Summation

### Score Breakdown
| Item | Type | Weight | Score | Topic |
|------|------|--------|-------|-------|
| 0 | image | 0.30 | 5 | Random charge recovery learning curves |
| 1 | image | 0.30 | 25 | Charged dimer binding curve |
| 2 | image | 0.30 | 5 | Ag₃ PES by charge state |
| 3 | text | 0.10 | 0 | Large-scale MD applicability |

### Task Understanding Analysis
- **Claims**: 14 claims. C14 "supported".
- Claims are comprehensive and well-structured: charge recovery, dimer binding, Ag₃ PES, ablation.
- **Gap**: Claims specify "LES-style or equivalent reciprocal-space latent-charge fitting" but agent didn't implement the actual LES algorithm — used simpler approximations.

### Report Quality Issues
- Report (203 lines, 9 images) — many images but most are incorrect.
- Charged dimer binding curve scored 25 — best item, but still far from paper quality.
- Random charge recovery (5) and Ag₃ PES (5) nearly zero — implementations are fundamentally wrong.
- No large-scale MD simulations attempted → 0.

### Root Cause
**Method simplification** — Agent built feature-engineering benchmarks instead of implementing the actual LES (Latent Ewald Summation) algorithm. The algorithm requires reciprocal-space charge fitting which was not implemented.

---

## Domain-Level Patterns

1. **Chemistry is the hardest domain** (avg 9.9) — all tasks require domain-specific software (HADDOCK3, AlphaFold3) or complex algorithm implementation (LES, KA-GNN).

2. **Task misunderstanding is catastrophic** — Chemistry_002 scored 1.0 because the agent analyzed the wrong thing entirely.

3. **Infeasible tasks** — Chemistry_001 requires training a diffusion model on benchmark-scale data, impossible in bench environment.

4. **Implementation bugs go undetected** — Chemistry_000's KA-GNN performs worse than baselines, but agent doesn't recognize this as a bug.