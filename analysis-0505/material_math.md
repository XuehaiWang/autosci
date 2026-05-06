# ResearchClawBench Analysis: Material & Math Domains (2026-05-05)

## Summary Table

| Task | Domain | Score | Mean Score (3 attempts) | Std | Status |
|------|--------|------:|------------------------:|----:|--------|
| Material_000 | Material | N/A | N/A | N/A | **FAILED** (exit_code=1, agent crashed) |
| Material_001 | Material | 5.25 (worst of 3; mean 7.85) | 7.85 | 2.14 | Completed but very low score |
| Material_002 | Material | 31.46 | 31.12 | 0.73 | Completed, low-moderate score |
| Math_000 | Math | 20.70 | 19.45 | 0.90 | Completed, low score |
| Math_001 | Math | 38.30 | 34.77 | 3.03 | Completed, best score in batch |
| Math_002 | Math | N/A | N/A | N/A | **FAILED** (exit_code=-15/SIGTERM, timeout after 5322s) |
| Math_003 | Math | 14.00 | 14.00 | 0.00 | Completed, low score |

---

## Failed Tasks

### Material_000 (Altermagnet Discovery with GNN)
- **Status**: Failed, exit_code=1, duration=2113s, cost=$0.89
- **Task**: Develop AI search engine for altermagnetic materials using crystal structure graphs. Pre-train on 5000 unlabeled structures, fine-tune on 2000 labeled (5% positive), screen 1000 candidates.
- **Report**: Only 2 lines written: "# Research Report" and empty.
- **Root cause**: Agent crashed (exit_code=1). Likely encountered a fatal error loading PyTorch `.pt` graph data or installing dependencies for GNN training. The task required deep learning (GNN pre-training + fine-tuning) which may have exceeded the agent's capability or hit environment issues (CUDA, torch-geometric, etc.).
- **Failure mode**: **Infrastructure/environment failure** -- agent could not set up the required deep learning stack.

### Math_002 (Altermagnet Discovery -- same domain as Material_000 but filed under Math?)
- **Status**: Failed, exit_code=-15 (SIGTERM), duration=5322s (88 min), no model recorded, no token usage
- **Report**: Only 2 lines: "# Research Report" / "Error: failed after max retries"
- **Root cause**: The agent timed out or was killed. The empty model field and null token usage suggest the LLM connection itself failed repeatedly before the process was killed.
- **Failure mode**: **Timeout/connection failure** -- agent never got started or kept retrying LLM calls until killed.

---

## Detailed Task Analyses

---

### Material_001: Multimodal Materials AI (Score: 5.25, mean 7.85)

#### 1. Score Breakdown

| Checklist Item | Weight | Score | Key Issue |
|----------------|-------:|------:|-----------|
| GNN property prediction (MAE ~0.15 eV/atom, training convergence) | 0.30 | 0 | **No GNN implemented at all**. Used shallow regressors (Linear Regression, RF, SVR, GBR) with MAE ~1.3 and negative R-squared. |
| VAE structure generation (lattice parameter distribution overlap, KL divergence ~0.15, 85% coverage) | 0.35 | 15 | Used GMM instead of VAE. Produced 1D KDE density plots instead of 2D lattice-parameter scatter. No KL divergence or coverage metrics reported. |
| Bayesian optimization convergence (TOF values, 20 iterations, optimal T/P) | 0.35 | 0 | **No Bayesian optimization implemented**. Used surrogate response surface with gradient boosting instead. No TOF metric, no iteration-wise convergence, no BO vs random comparison. |

#### 2. Task Understanding

The task_plan.json contains 14 claims (C1-C14) that are reasonable but **completely misaligned with the scoring criteria**. The plan focuses on:
- Linear/RF/SVR/GBR regression comparisons (not GNN)
- GMM for structure generation (not VAE)
- Response-surface surrogate optimization (not Bayesian optimization)

The agent read the INSTRUCTIONS and related papers (CGCNN, Materials Project, physics-informed ML) but chose to implement simpler baselines rather than the specific methods the evaluation expected. The paper_summary references CGCNN with formation energy MAE 0.039 eV/atom, but the agent did not implement any graph neural network.

#### 3. Report Quality

The report (`report/report.md`) is well-structured with proper academic formatting:
- Data overview table with descriptive statistics
- Regression and classification benchmark tables
- Ablation study (node-only vs edge-aware features)
- Learning curve analysis
- Permutation importance
- Structure generation with Wasserstein distances
- Optimization response surface

However, **none of the three scored results** (GNN prediction, VAE generation, BO convergence) are present. The report is a competent generic ML benchmark but does not address the paper's specific scientific claims.

#### 4. Code Quality

Single file `materials_multimodal_analysis.py` implementing the full pipeline. Code runs and produces 6 figures. The code is functionally correct for what it does -- the problem is that it implements the wrong methods.

#### 5. Root Cause Classification

**Methodological misalignment**: The agent substituted simpler methods for the domain-specific methods required by the evaluation. It used:
- Shallow regressors instead of GNN/CGCNN
- GMM instead of VAE
- Grid-search response surface instead of Bayesian optimization

This is the most impactful failure mode: the agent completed all the work but aimed at the wrong target. The task plan was reasonable for a generic ML benchmark but ignored the specific scientific methods the paper describes (GNN, VAE, Bayesian optimization).

---

### Material_002: MACE Foundation Model Validation (Score: 31.46, mean 31.12)

#### 1. Score Breakdown

| Checklist Item | Weight | Score | Key Issue |
|----------------|-------:|------:|-----------|
| Water RDF (first peak ~2.8 A, height ~2.5, stable MD) | 0.33 | 25 | MD ran stably but RDF is nearly flat -- peak height 0.095 vs expected ~2.5. Position roughly correct (2.725 A vs 2.775 A). Fundamentally wrong structure. |
| Adsorption scaling (O vs OH on 6 metals, slope 0.6-0.8) | 0.34 | 44 | **Best item**. Slope 0.758 within target range. Correct metals and ordering. Missing PBE reference line. |
| Reaction barriers (3 CRBH20 reactions, MAE ~0.3 eV) | 0.33 | 25 | Grossly incorrect barriers. One is strongly negative (~-10 eV). MAE ~4-5 eV vs expected ~0.3 eV. Workflow complete but results physically wrong. |

#### 2. Task Understanding

The task_plan.json has 14 claims (C1-C14) covering water MD, adsorption scaling, reaction barriers, architecture comparison, fine-tuning scaling, embedding PCA, and element coverage. The plan is well-aligned with the evaluation criteria. All three scored benchmarks are explicitly planned.

#### 3. Report Quality

Excellent report structure: Abstract, Introduction with 3 RQs, detailed Methods, Results with tables and figures, Robustness analysis, and Discussion. 7 figures generated. The report honestly acknowledges failures (water RDF nearly flat, reaction barriers grossly wrong) which is good scientific practice.

#### 4. Code Quality

Single file `run_benchmarks.py`. The code successfully:
- Loaded MACE-MP-0 medium model
- Ran 2000-step Langevin MD on 32 water molecules
- Built fcc(111) slabs for 6 metals and computed adsorption energies
- Computed reaction barriers from provided geometries

Issues:
- Water simulation too short (2 ps) with poor initial configuration -> nearly flat RDF
- Reaction barrier geometries from the simplified dataset produce unphysical results with pretrained MACE

#### 5. Root Cause Classification

**Partial technical success, partial simulation failure**:
- Adsorption scaling worked well (44/100) because ASE slab construction + BFGS optimization is robust
- Water failed because 2 ps is far too short for liquid equilibration, and the initial random packing was poor
- Reaction barriers failed because the simplified CRBH20 geometries in the dataset are incompatible with MACE-MP-0's training domain -- the model produces unphysical energies for these specific molecular configurations

The agent correctly identified and reported these issues but could not fix them within the constraints.

---

### Math_000: Multi-Object Tracking (SparseTrack) (Score: 20.70, mean 19.45)

#### 1. Score Breakdown

| Checklist Item | Weight | Score | Key Issue |
|----------------|-------:|------:|-----------|
| Pseudo-depth definition (distance from bbox bottom to image bottom, camera/ground priors) | 0.15 | 10 | **Incorrect definition**: used inverse box height instead of distance from box bottom to image bottom. Missing camera-above-ground and flat-ground priors. |
| Depth Cascade Matching mechanism (partition by depth, sequential IoU matching, no appearance features) | 0.15 | 44 | Partially correct: implemented depth-bin partitioning and IoU matching. But cascade sequencing (nearest to farthest) not fully described. |
| Performance vs depth levels (accuracy improving then saturating at 4-6 levels) | 0.70 | 18 | **Results contradicted expected trend**: the agent's depth-level figure shows monotonically *decreasing* MOTA as depth levels increase, opposite of the paper's claim that accuracy improves then saturates. |

#### 2. Task Understanding

The task plan has 12 claims covering data statistics, SORT/ByteTrack/SparseByteTrack implementation, metric comparisons, threshold sweeps, and qualitative visualizations. The plan is reasonable and well-structured.

However, the critical scientific claim -- that pseudo-depth decomposition *improves* tracking -- was not achieved. The agent's implementation shows pseudo-depth *hurting* performance, which directly contradicts the paper.

#### 3. Report Quality

Strong report with clear structure: Abstract, Introduction with 3 RQs, Data Overview, Methods for 3 trackers, Results with comparison table, threshold sensitivity analysis, and discussion relating to literature. 6 figures generated. The report correctly demonstrates that ByteTrack >> SORT (the main gain), but the SparseByteTrack improvement is minimal.

#### 4. Code Quality

`analyze_tracking.py` implements SORT, ByteTrack, and SparseByteTrack from scratch using scipy's Hungarian algorithm. The implementations are functional. The pseudo-depth estimation uses inverse box height (1/h), which the scorer flagged as incorrect (should be distance from box bottom to image bottom).

#### 5. Root Cause Classification

**Incorrect technical understanding + incorrect experimental results**:
- The pseudo-depth formula was wrong (inverse height vs. bottom-edge distance)
- The depth-level sweep showed the opposite trend from the paper (decreasing vs. increasing accuracy)
- The high-weight item (0.70) specifically tested whether the depth-level figure matches the paper's behavior, and it showed the opposite trend

The agent produced a reasonable tracking study but fundamentally misunderstood the pseudo-depth mechanism, leading to an implementation that degraded rather than improved with more depth levels.

---

### Math_001: VOS Framework / Accelerated Lasso (Score: 38.30, mean 34.77)

**Best score in the batch.**

#### 1. Score Breakdown

| Checklist Item | Weight | Score | Key Issue |
|----------------|-------:|------:|-----------|
| VOS-Accelerated achieves strictly lower final loss, faster convergence, fewer iterations to 1e-7 tolerance | 0.40 | 20 | Report explicitly states ISTA achieves same/slightly better final objective. All methods reach same optimum. Core claim NOT confirmed. |
| Convergence plot (log-scale, blue VOS curve steep monotonic descent below red baseline) | 0.30 | 55 | **Best item**. Log-scale plot shows accelerated schemes below ISTA baseline with widening gap. Multi-curve rather than exact two-curve layout, but qualitative trends match. |
| Robustness on ill-conditioned problems (proximal operator, non-divergence, adaptive restart damping) | 0.30 | 46 | Good coverage: proximal L1 operator, stable convergence, restart ablation with oscillation metrics. Lacks tight Lyapunov connection and condition-number-10 analysis. |

#### 2. Task Understanding

The task plan has 12 claims covering data overview, ISTA, FISTA, ADMM, ODE-inspired schemes, Lyapunov energy, convergence plots, recovery scatter, lambda sensitivity, and restart ablation. Excellent alignment with the evaluation criteria.

#### 3. Report Quality

Strong academic report with mathematical notation, clear algorithm descriptions, comprehensive results tables, and honest interpretation. 5 figures generated. The report transparently notes that the accelerated methods do NOT achieve strictly lower final loss than ISTA, which is scientifically honest but costs points on criterion 0 (weight 0.40).

#### 4. Code Quality

`run_lasso_vos_study.py` implements ISTA, FISTA, restarted FISTA, proximal heavy-ball, ODE-inspired schemes (r=1,3,5), and ADMM. Code is well-structured and reproduces the full study. Correctly computes Lipschitz constant via power iteration, implements soft-thresholding proximal operator, and tracks Lyapunov-style energy.

#### 5. Root Cause Classification

**Honest results that don't match the paper's theoretical claims**:
- The criterion expects the accelerated method to achieve strictly lower final loss, but on this particular ill-conditioned Lasso problem, all methods converge to essentially the same optimum
- The transient convergence behavior (which does show acceleration) is captured well, earning strong scores on items 1 and 2
- The agent could not make the data show what the paper claims because the specific dataset/setup does not exhibit the expected superiority clearly enough

This is a "correct implementation, disappointing results" failure rather than a methodological error.

---

### Math_003: AlphaGeometry / IMO Theorem Proving (Score: 14.00, mean 14.00)

#### 1. Score Breakdown

| Checklist Item | Weight | Score | Key Issue |
|----------------|-------:|------:|-----------|
| IMO-AG-30 success rate (25/30 = 83.3%, vs Wu's 10/30, approaching gold medalist 25.9/30) | 0.40 | 35 | Agent achieved 18/30 (60%), explicitly evaluated on IMO-AG-30 benchmark. But far below 25/30 target. No comparison to Wu's method or human gold medalist. |
| Synthetic data scale (100 million examples) | 0.35 | 0 | **Completely absent**. No synthetic training data generated or used at all. The agent used purely symbolic/heuristic methods with no learning. |
| Traceback algorithm identifying unused premise in IMO 2004 P1, leading to more general theorem | 0.25 | 0 | **Completely absent**. No traceback algorithm, no unused premise detection, no theorem generalization analysis. |

#### 2. Task Understanding

The task plan has 14 claims focused on benchmark parsing, forward/backward provers, per-goal-type analysis, rule usage attribution, search budget sensitivity, rule ablation, and related work comparison. The plan is appropriate for a symbolic theorem prover but does not address:
- Synthetic data generation (100M examples) -- a core AlphaGeometry contribution
- Neural language model component (the "neuro" in neuro-symbolic)
- Traceback algorithm for unused premise detection

The agent essentially built a purely symbolic prover, missing the neural and data-generation components entirely.

#### 3. Report Quality

Well-structured report with detailed benchmark inventory, two solver implementations (forward chaining and backward search), per-goal-type analysis, rule ablation, search-budget sensitivity, and solvability model. The 60% closure rate on backward search is genuinely non-trivial. 9 figures generated.

#### 4. Code Quality

`geometry_prover.py` implements:
- Benchmark parser for imo_ag_30.txt
- Forward rule-chaining baseline (0/30 solved)
- Heuristic backward-search prover (18/30 solved)
- Rule-usage attribution, ablation, and budget sweep

The code is substantial and functional. The backward prover achieving 60% is respectable for a purely symbolic approach.

#### 5. Root Cause Classification

**Scope limitation / missing key components**:
- The task is about AlphaGeometry, which combines a symbolic deduction engine with a neural language model trained on 100M synthetic proofs. The agent built only the symbolic part.
- Two of three scored items (synthetic data scale + traceback algorithm) received 0 because they are fundamentally about the neural/data-generation aspects that were not implemented
- The one item that was addressed (success rate) scored 35/100 because 18/30 is decent but well below the target 25/30

This task essentially required implementing a neural theorem prover with massive synthetic data generation, which is far beyond what the agent could do in a single session.

---

## Cross-Cutting Failure Mode Analysis

### Failure Mode Categories

| Failure Mode | Tasks Affected | Impact |
|-------------|----------------|--------|
| **Infrastructure/environment failure** | Material_000, Math_002 | Total failure (no score) |
| **Methodological misalignment** (wrong methods) | Material_001 | Severe (score 5.25) |
| **Incorrect technical understanding** | Math_000 (pseudo-depth definition wrong) | Moderate (score 20.7) |
| **Correct implementation, wrong results** | Math_001, Material_002 (water/barriers) | Moderate (scores 38.3, 31.46) |
| **Scope limitation** (missing key components) | Math_003 (no neural component, no synthetic data) | Severe (score 14.0) |

### Key Patterns

1. **Agent substitutes simpler methods for domain-specific ones**: Material_001 used generic ML instead of GNN/VAE/BO. Math_003 used pure symbolic search instead of neuro-symbolic. The agent tends to fall back to methods it can implement quickly rather than the specific methods the papers describe.

2. **Simulation quality issues**: Material_002's water MD was too short (2 ps) to produce meaningful liquid structure. The agent ran the simulation but did not recognize that 2000 steps at 0.5 fs is only 1 ps of dynamics, far too short for liquid water equilibration.

3. **Results that contradict paper claims**: Math_000's depth-level experiment showed the opposite trend from the paper. Math_001's accelerated methods did not achieve strictly lower final loss. When the agent's implementation produces results that disagree with the paper, it honestly reports the discrepancy rather than fabricating agreement, which is scientifically commendable but costs evaluation points.

4. **Environment/infrastructure failures cause total loss**: Material_000 (GNN/PyTorch failure) and Math_002 (timeout/connection failure) scored nothing because the agent never produced output. These are the most wasteful failures.

5. **High-weight image criteria are hardest**: Several tasks have image-based criteria with weight 0.33-0.70 that require specific quantitative features in plots. The agent generates plots that are structurally similar but quantitatively wrong (e.g., Math_000's depth-level plot showing opposite trend).

### Recommendations for Improvement

1. **Method selection**: The agent needs to prioritize implementing the specific methods mentioned in the paper summary and scoring criteria, not generic ML baselines. A pre-analysis of "what methods does the evaluation expect?" should happen before coding begins.

2. **Simulation convergence**: For MD simulations, the agent should check whether the simulation is long enough by monitoring convergence of computed properties (e.g., RDF peak height stabilization) rather than just running the prescribed number of steps.

3. **Result validation against paper claims**: Before finalizing, the agent should compare its key results against the paper's claims and flag major discrepancies. If depth levels are supposed to improve tracking but the implementation shows the opposite, that signals a bug in the implementation, not a genuine finding.

4. **Environment robustness**: The agent needs better error recovery for deep learning tasks. If PyTorch/CUDA setup fails, it should try CPU-only fallbacks or simpler model implementations rather than crashing entirely.

5. **Time management**: Math_002 used 88 minutes before being killed with no output. The agent should have a time-budget awareness to ensure it produces at least a partial report even if the main computation fails.