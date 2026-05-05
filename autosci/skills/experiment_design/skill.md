---
name: experiment_design
description: Rigorous experiment design with hypotheses, controls, and evaluation metrics
tags: [experiment, design, hypothesis, baseline, ablation, evaluation, metrics]
required_tools: [write_file]
---

## Procedure

1. **Define the research question**
   - What specific claim are we testing?
   - What would a positive/negative result look like?

2. **State hypotheses**
   - Null hypothesis (H0): the default assumption
   - Alternative hypothesis (H1): what we believe is true
   - Be specific and falsifiable

3. **Identify variables**
   - Independent variable(s): what we change
   - Dependent variable(s): what we measure
   - Confounding variables: what we must control

4. **Design baselines and controls**
   - At least one strong baseline (current state-of-the-art or standard method)
   - Ablation variants: remove/change one component at a time
   - Control condition: no intervention or random baseline

5. **Choose evaluation metrics**
   - Primary metric: the one that directly answers the research question
   - Secondary metrics: other relevant measures
   - Ensure metrics are standard and comparable to prior work

6. **Plan for statistical rigor**
   - Decide on significance level (typically α = 0.05)
   - Plan for multiple runs with different random seeds (≥3, ideally 5)
   - Report mean ± std, not just best run
   - Choose appropriate statistical test (t-test, Wilcoxon, etc.)

7. **Resource planning**
   - Estimate compute requirements (GPU hours, memory)
   - Estimate wall-clock time
   - Plan checkpointing strategy for long runs

8. **Document the plan**
   - Write experiment configuration file
   - Record all hyperparameters and their justification
   - Describe expected outcomes for each condition

## Checklist before running

- [ ] Hypotheses are clearly stated
- [ ] Baselines are defined
- [ ] Evaluation metrics are chosen
- [ ] Number of runs/seeds is decided
- [ ] Resource requirements are estimated
- [ ] All hyperparameters are documented
- [ ] Code has been tested on a small scale first
