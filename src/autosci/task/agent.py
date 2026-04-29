"""TaskUnderstandingAgent — a subagent that deeply understands a research task.

Two modes:
  topic_only:  Only a broad topic given. Agent searches literature broadly,
               brainstorms ideas, selects promising directions, produces RQs+Claims.
  task_given:  Concrete task description given. Agent parses context (4 dimensions),
               searches targeted literature, extracts contributions+gaps,
               then synthesizes into specific RQs+Claims.

The agent runs as a full agent (while-loop, tools) driven by the runner.
Output is written to workspace/task_understanding.md and workspace/task_plan.json.
The resulting TaskPlan is returned for injection into the main agent's prompt.
"""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


_TOPIC_ONLY_PROMPT = """
# Task Understanding Agent (Topic Exploration Mode)

You have been given a broad research topic. Your job is to:

1. **Literature Exploration** — Search for 10-20 recent, highly-cited papers on this topic
   using `web_search`. For each promising paper, use `web_fetch` to read the abstract/intro.

2. **Idea Generation** — Based on what you find, brainstorm 4-6 candidate research ideas.
   For each idea, assess: novelty, feasibility, impact.

3. **Selection** — Pick the 1-2 most promising ideas. Justify your choice.

4. **Formalization** — For each selected idea, produce:
   - A specific Research Question (answerable, not vague)
   - 2-3 Claims (concrete, verifiable hypotheses, not just goals)
   - What experiment/data would verify each claim

5. **Output** — Write your complete analysis to a file called `task_understanding.md`
   using `write_file`, in the format specified below, then write `task_plan.json`
   with the structured JSON.

## Output Format for task_understanding.md

```
# Task Understanding Report

**Mode**: topic_only
**Goal**: <one sentence core objective of selected idea>

---

## Literature Survey

### 1. <Paper Title>
Source: <URL>
**Contribution**: ...
**Evidence**: ...
**Gap / Boundary**: ...

[repeat for each paper]

## Selected Research Direction

<Justification for why this direction is chosen>

## Research Questions

**[RQ1]** <specific question>
> Motivation: <which gap in literature motivates this>

## Claims (Hypotheses)

| ID | Statement | Type | Verify by | Status |
|----|-----------|------|-----------|--------|
| C1 | <claim> | comparative/existence/improvement/causal | <experiment> | unverified |
```

## Output Format for task_plan.json

```json
{
  "raw_task": "<original topic>",
  "mode": "topic_only",
  "goal": "<one sentence>",
  "context": {
    "research_subject": "...",
    "data_type": "...",
    "task_goal": "...",
    "known_methods": ["..."],
    "key_terms": ["..."]
  },
  "related_works": [
    {
      "title": "...", "source": "...",
      "contribution": "...", "evidence": "...", "boundary": "...",
      "year": "...", "authors": "..."
    }
  ],
  "research_questions": [
    {"id": "RQ1", "question": "...", "motivation": "...", "related_work_ids": []}
  ],
  "claims": [
    {
      "id": "C1", "statement": "...", "type": "comparative",
      "verifiable_by": "...", "related_rq_id": "RQ1", "status": "unverified"
    }
  ],
  "suggested_agents": ["research", "code", "analysis"]
}
```

Be specific and concrete. Avoid vague statements like "improve performance" —
instead write "reduce perplexity by >5% on WikiText-103 benchmark compared to baseline X".
"""


_TASK_GIVEN_PROMPT = """
# Task Understanding Agent (Paper Reproduction Mode)

You have been given a concrete research task. This is a **paper reproduction task**:
the goal is to implement the described method, run experiments on the provided data,
and produce specific quantitative results and figures that match the paper's findings.

Your job is to extract concrete, actionable reproduction targets as Claims.

## Step 1: Parse Task Description

Read the task description carefully. Extract:
- **research_subject**: What method/paper is being reproduced?
- **data_type**: What input data is provided?
- **task_goal**: What specific outputs must be produced (metrics, figures, tables)?
- **known_methods**: What methods/baselines are mentioned?
- **key_terms**: 5-8 technical terms that identify the core algorithm

## Step 2: Inventory Workspace

Use `list_dir` to explore the workspace structure:
- List `data/` — understand available input files and formats
- List `related_work/` — find local PDF papers to read
- List `images/` if it exists — understand expected output figure paths

## Step 3: Read Local Papers

For each PDF in `related_work/`, use `read_file` to read its content.
From each paper, extract:
- The core method/algorithm (contribution)
- **Exact quantitative results**: accuracy, RMSE, F1, AUC, correlation, etc. with precise values
- **Figures produced**: what visualizations are shown, what they demonstrate
- What baselines are compared against and by how much the method outperforms them
- The experimental setup: dataset, evaluation protocol, metrics

Do NOT use `web_search` — all relevant papers are already in `related_work/`.

## Step 4: Extract Reproduction Targets → Claims

Based on Steps 1-3, identify ALL specific outputs the task requires.
Each Claim is one concrete reproduction target:

**For quantitative results** (metrics to report in text):
- statement: "Reproduce [method] achieving [metric]=[value] on [dataset/condition]"
- type: "existence"
- verifiable_by: "Run [specific experiment]; report must contain [metric]=[value]"

**For figure outputs** (plots/visualizations to generate):
- statement: "Generate [figure description] and save to images/[filename].png"
- type: "existence"
- verifiable_by: "File images/[filename].png exists showing [visual description]"

**For comparative results** (method vs baseline):
- statement: "[Method] outperforms [baseline] by [delta] on [metric] under [condition]"
- type: "comparative"
- verifiable_by: "Run both methods; compare [metric] values"

Aim for 4-8 Claims that together cover all the key results the task asks for.
Every Claim must be specific enough that a reviewer can check it against the output.

## Step 5: Output

Write `task_understanding.md` with full analysis using `write_file`.
Write `task_plan.json` with structured JSON using `write_file`.

## Output Format for task_plan.json

```json
{
  "raw_task": "<original task>",
  "mode": "task_given",
  "goal": "<one sentence: reproduce [method] on [data] producing [key outputs]>",
  "context": {
    "research_subject": "...",
    "data_type": "...",
    "task_goal": "...",
    "known_methods": ["..."],
    "key_terms": ["..."]
  },
  "related_works": [
    {
      "title": "...", "source": "<path to local PDF>",
      "contribution": "...", "evidence": "<exact numbers from paper>",
      "boundary": "...", "year": "...", "authors": "..."
    }
  ],
  "research_questions": [
    {"id": "RQ1", "question": "...", "motivation": "...", "related_work_ids": ["rw1"]}
  ],
  "claims": [
    {
      "id": "C1",
      "statement": "Reproduce [method] achieving [metric]=[value] on [dataset]",
      "type": "existence",
      "verifiable_by": "Run experiment; output report contains [metric]=[value]",
      "related_rq_id": "RQ1",
      "status": "unverified"
    }
  ],
  "suggested_agents": ["code", "analysis", "write"]
}
```

Be concrete and specific. Every Claim must name exact metrics, values, and/or output
file paths. Vague claims like "demonstrate the method works" are useless.

## Output Format for task_understanding.md

Use structured Markdown with sections:
Context Parsing, Workspace Inventory, Related Work (with exact results extracted),
Research Questions, Claims (as a table).
"""


class TaskUnderstandingAgent(BaseAgent):
    """Subagent that performs deep structured understanding of a research task.

    Runs as a full agent (while-loop + tools) rather than a single LLM call.
    This allows it to actually search literature, fetch papers, and iteratively
    refine its understanding before producing Claims and Research Questions.
    """

    name = "task_understanding"
    role = "Structured research task analysis: context parsing, literature search, RQ and claim generation"
    tools = [
        "web_search", "web_fetch",
        "read_file", "write_file",
        "list_dir", "glob", "grep",
    ]
    max_iterations = 40

    # Mode is set per-instance before running
    _mode: str = "task_given"

    def __init__(self, mode: str = "task_given"):
        self._mode = mode

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        if self._mode == "topic_only":
            return _TOPIC_ONLY_PROMPT.strip()
        return _TASK_GIVEN_PROMPT.strip()


# Register so it can be delegated to if needed
agent_registry.register(TaskUnderstandingAgent)
