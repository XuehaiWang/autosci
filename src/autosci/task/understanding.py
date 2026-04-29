"""TaskUnderstanding — orchestrates the TaskUnderstandingAgent.

Replaces the old single-LLM-call approach. Now:
  1. Detects mode (topic_only vs task_given) from task description
  2. Runs TaskUnderstandingAgent via AgentRunner (full while-loop with tools)
  3. Reads back the written task_plan.json from workspace
  4. Falls back to minimal plan if agent fails or file is missing
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from autosci.task.schemas import TaskPlan, save_task_plan, save_task_understanding_report, load_task_plan

if TYPE_CHECKING:
    from autosci.runtime.runner import AgentRunner

logger = logging.getLogger(__name__)

# Heuristic: task descriptions shorter than this, with no method keywords,
# are treated as topic_only
_TOPIC_ONLY_MAX_CHARS = 200
_METHOD_KEYWORDS = [
    "framework", "method", "approach", "algorithm", "technique",
    "using", "based on", "via", "propose", "develop", "implement",
    "bayesian", "neural network", "deep learning", "machine learning",
    "optimization", "inference", "outperform", "improve", "reduce",
    "predict", "classify", "detect", "generate",
]


def _build_workspace_inventory(workspace: str) -> str:
    """Build a concise inventory of workspace files for the agent's initial context."""
    lines = []
    for subdir in ("data", "related_work", "images"):
        path = os.path.join(workspace, subdir)
        if os.path.isdir(path):
            files = sorted(os.listdir(path))
            if files:
                lines.append(f"{subdir}/: {', '.join(files)}")
            else:
                lines.append(f"{subdir}/: (empty)")
    return "\n".join(lines) + "\n" if lines else ""


def detect_mode(task: str) -> str:
    """Heuristically determine whether a task is topic_only or task_given."""
    task_lower = task.lower().strip()
    if len(task_lower) <= _TOPIC_ONLY_MAX_CHARS:
        has_method = any(re.search(r'\b' + re.escape(kw) + r'\b', task_lower)
                         for kw in _METHOD_KEYWORDS)
        if not has_method:
            return "topic_only"
    return "task_given"


class TaskUnderstanding:
    """Runs the TaskUnderstandingAgent and returns a TaskPlan.

    Args:
        runner: an AgentRunner instance (shared with main execution)
        workspace: path to the task workspace directory
    """

    def __init__(self, runner: "AgentRunner", workspace: str):
        self.runner = runner
        self.workspace = workspace

    def analyze(self, task: str, mode: str = None) -> TaskPlan:
        """Run the understanding agent on the task. Returns a TaskPlan.

        Args:
            task: the raw task description
            mode: "topic_only" | "task_given" | None (auto-detect)
        """
        if mode is None:
            mode = detect_mode(task)

        logger.info(f"TaskUnderstanding: mode={mode}, task={task[:80]}...")

        from autosci.task.agent import TaskUnderstandingAgent

        agent = TaskUnderstandingAgent(mode=mode)

        # Build the task message — include workspace path and inventory so agent
        # starts with context instead of wasting iterations on discovery
        inventory = _build_workspace_inventory(self.workspace)
        agent_task = (
            f"{task}\n\n"
            f"---\n"
            f"## Workspace\n"
            f"Root: {self.workspace}\n"
            f"{inventory}"
            f"\n## Required Output Files\n"
            f"  1. {os.path.join(self.workspace, 'task_understanding.md')} — full Markdown report\n"
            f"  2. {os.path.join(self.workspace, 'task_plan.json')} — structured JSON\n"
        )

        try:
            result = self.runner.run(agent=agent, task=agent_task)
            if result.status not in ("completed", "budget_exhausted"):
                logger.warning(f"TaskUnderstandingAgent ended with status={result.status}")
        except Exception as e:
            logger.warning(f"TaskUnderstandingAgent raised exception: {e}")

        # Read back the written task_plan.json
        plan = load_task_plan(self.workspace)
        if plan:
            logger.info(
                f"TaskUnderstanding complete: {len(plan.research_questions)} RQs, "
                f"{len(plan.claims)} claims, {len(plan.related_works)} papers"
            )
            # Also generate the Markdown report if not already written
            report_path = os.path.join(self.workspace, "task_understanding.md")
            if not os.path.exists(report_path):
                save_task_understanding_report(plan, self.workspace)
            return plan

        # Fallback: agent didn't write the file — build minimal plan from result text
        logger.warning("TaskUnderstanding: task_plan.json not found, using fallback")
        return TaskPlan.fallback(task)
