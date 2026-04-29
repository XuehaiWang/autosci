"""Task understanding orchestration — runs paper_summary then task_understanding agents.

This module belongs in workflow/ because it is fundamentally a two-step
sequential agent pipeline:
  1. paper_summary agent  — reads related_work/ PDFs, writes paper_summary.md
  2. task_understanding agent — reads paper_summary.md, writes task_plan.json

Both agents are defined in agents/templates/*.yaml.
The resulting TaskPlan is a protocols.task_plan data structure consumed by
WorkflowEngine, MainAgent, and the runner's update_claim tool.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from autosci.protocols.task_plan import (
    TaskPlan, save_task_plan, save_task_understanding_report, load_task_plan,
)

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


def detect_mode(task: str) -> str:
    """Heuristically determine whether a task is topic_only or task_given."""
    task_lower = task.lower().strip()
    if len(task_lower) <= _TOPIC_ONLY_MAX_CHARS:
        has_method = any(re.search(r'\b' + re.escape(kw) + r'\b', task_lower)
                         for kw in _METHOD_KEYWORDS)
        if not has_method:
            return "topic_only"
    return "task_given"


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


def run_paper_summary(runner: "AgentRunner", workspace: str) -> str | None:
    """Run the paper_summary agent and return the path to paper_summary.md, or None.

    The agent runs in an isolated runner.run() call so PDF content never
    pollutes the main agent's context window.
    """
    related_work_dir = os.path.join(workspace, "related_work")
    if not os.path.isdir(related_work_dir):
        logger.info("PaperSummary: no related_work/ directory, skipping")
        return None

    pdf_files = [f for f in os.listdir(related_work_dir) if f.endswith(".pdf")]
    if not pdf_files:
        logger.info("PaperSummary: no PDF files in related_work/, skipping")
        return None

    logger.info(f"PaperSummary: found {len(pdf_files)} PDF(s), running paper_summary agent...")

    from autosci.agents.registry import agent_registry
    agent = agent_registry.get("paper_summary")

    agent_task = (
        f"Read the research papers in `related_work/` and write `paper_summary.md`.\n\n"
        f"Workspace root: {workspace}\n"
        f"related_work/ contains: {', '.join(sorted(pdf_files))}\n"
        f"Output file: {os.path.join(workspace, 'paper_summary.md')}\n"
    )

    try:
        result = runner.run(agent=agent, task=agent_task)
        if result.status not in ("completed", "budget_exhausted"):
            logger.warning(f"paper_summary agent ended with status={result.status}")
    except Exception as e:
        logger.warning(f"paper_summary agent raised exception: {e}")

    summary_path = os.path.join(workspace, "paper_summary.md")
    if os.path.exists(summary_path):
        logger.info(f"PaperSummary: written to {summary_path}")
        return summary_path

    logger.warning("PaperSummary: paper_summary.md not found after agent run")
    return None


class TaskUnderstanding:
    """Orchestrates the two-step task understanding pipeline.

    Step 1: paper_summary agent reads related_work/ PDFs → paper_summary.md
    Step 2: task_understanding agent reads paper_summary.md → task_plan.json

    Returns a TaskPlan for injection into the main agent's prompt.
    """

    def __init__(self, runner: "AgentRunner", workspace: str):
        self.runner = runner
        self.workspace = workspace

    def analyze(self, task: str, mode: str = None) -> TaskPlan:
        """Run the understanding pipeline on the task. Returns a TaskPlan.

        Args:
            task: the raw task description
            mode: "topic_only" | "task_given" | None (auto-detect)
        """
        if mode is None:
            mode = detect_mode(task)

        logger.info(f"TaskUnderstanding: mode={mode}, task={task[:80]}...")

        # Step 1 (task_given only): run paper_summary agent in isolated context
        paper_summary_path = None
        if mode == "task_given":
            paper_summary_path = run_paper_summary(self.runner, self.workspace)

        # Step 2: run the appropriate understanding agent
        from autosci.agents.registry import agent_registry

        if mode == "topic_only":
            agent = agent_registry.get("topic_exploration")
        else:
            agent = agent_registry.get("task_understanding")

        inventory = _build_workspace_inventory(self.workspace)

        paper_summary_note = ""
        if paper_summary_path:
            paper_summary_note = (
                f"\n## Paper Summary\n"
                f"A paper_summary agent has read the related_work/ PDFs and written a\n"
                f"structured summary to: {paper_summary_path}\n"
                f"Read this file in Step 2.5 before generating Claims.\n"
            )

        agent_task = (
            f"{task}\n\n"
            f"---\n"
            f"## Workspace\n"
            f"Root: {self.workspace}\n"
            f"{inventory}"
            f"{paper_summary_note}"
            f"\n## Required Output Files\n"
            f"  1. {os.path.join(self.workspace, 'task_understanding.md')} — full Markdown report\n"
            f"  2. {os.path.join(self.workspace, 'task_plan.json')} — structured JSON\n"
        )

        try:
            result = self.runner.run(agent=agent, task=agent_task)
            if result.status not in ("completed", "budget_exhausted"):
                logger.warning(f"task understanding agent ended with status={result.status}")
        except Exception as e:
            logger.warning(f"task understanding agent raised exception: {e}")

        # Read back the written task_plan.json
        plan = load_task_plan(self.workspace)
        if plan:
            logger.info(
                f"TaskUnderstanding complete: {len(plan.research_questions)} RQs, "
                f"{len(plan.claims)} claims, {len(plan.related_works)} papers"
            )
            report_path = os.path.join(self.workspace, "task_understanding.md")
            if not os.path.exists(report_path):
                save_task_understanding_report(plan, self.workspace)
            return plan

        logger.warning("TaskUnderstanding: task_plan.json not found, using fallback")
        return TaskPlan.fallback(task)
