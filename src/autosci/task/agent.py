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
# Task Understanding Agent (Task Analysis Mode)

You have been given a concrete research task description. Your job is to deeply
understand it and produce structured, actionable research questions and claims.

## Step 1: Context Parsing

Extract from the task description:
- **research_subject**: What object/phenomenon is being studied?
- **data_type**: What data, materials, or experimental inputs are involved?
- **task_goal**: What is the ultimate objective (what will be produced/proved)?
- **known_methods**: What existing methods/baselines are mentioned or implied?
- **key_terms**: 5-8 specific technical terms to use for literature search

## Step 2: Key Point Extraction

From the task description, identify 3-5 specific points that are *underspecified*
or *assumed* — these become the "what exactly is X?" questions that drive RQ generation.
Examples:
- "a new Bayesian framework" → What exactly is the framework structure?
- "significantly improves" → Improves by how much, on what metric?
- "outperforms baselines" → Which baselines, under what conditions?

## Step 3: Literature Search

Using the key_terms, search for 8-15 relevant papers with `web_search`.
For each paper in the results, fetch the abstract/intro with `web_fetch` if needed.
For each paper, extract:
- contribution (1-2 sentences)
- evidence (what validates the contribution)
- boundary/gap (what it does NOT do, or future work mentioned)

Focus on papers directly related to the task's method and domain.

## Step 4: Synthesis → Research Questions + Claims

Combine Context (Step 1-2) with Literature Gaps (Step 3):
- Each RQ should be derived from: a key underspecified point + a gap in related work
- Each Claim should be a concrete, falsifiable hypothesis
  - Type: "comparative" (A beats B), "existence" (X is achievable),
          "improvement" (method reduces metric by amount), "causal" (X causes Y)
  - verifiable_by: the specific experiment, dataset, or measurement

## Step 5: Output

Write `task_understanding.md` with full analysis using `write_file`.
Write `task_plan.json` with structured JSON using `write_file`.

## Output Format for task_plan.json

```json
{
  "raw_task": "<original task>",
  "mode": "task_given",
  "goal": "<one sentence core objective>",
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
    {"id": "RQ1", "question": "...", "motivation": "...", "related_work_ids": ["rw1"]}
  ],
  "claims": [
    {
      "id": "C1", "statement": "...", "type": "comparative",
      "verifiable_by": "...", "related_rq_id": "RQ1", "status": "unverified"
    }
  ],
  "suggested_agents": ["research", "code", "analysis", "write"]
}
```

Be concrete and specific. Vague claims are useless. Every claim must name a
specific metric, dataset, or measurable outcome.

## Output Format for task_understanding.md

Use the structured Markdown format with sections:
Context Parsing, Key Points, Related Work, Research Questions, Claims.
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
