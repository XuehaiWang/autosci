"""Scientist mode public API.

Provides ``run_scientist()`` — the canonical entry point for running AutoSci
in scientist mode.  Both the CLI (``autosci scientist``) and the bench adapter
(``autosci-bench``) call this function directly, so there is a single source
of truth for the scientist workflow.

Workflow
--------
1. Init workspace (.autosci/ internals + research dirs at root)
2. Build scientist config (storage/memory/trajectory paths)
3. Bootstrap tools and agents
4. Create TrajectoryRecorder + AgentRunner
5. Run TaskUnderstandingAgent → TaskPlan
6. Inject task plan into prompt
7. Run MainAgent (or WorkflowEngine if workflow_name given)
8. Export trajectory report
9. Return RunResult
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ── Public result type ─────────────────────────────────────────────────────────

@dataclass
class ScientistResult:
    """Result returned by run_scientist()."""
    status: str                          # "completed" | "budget_exhausted" | "error" | ...
    response: str                        # Final agent response text
    task_plan: Optional[object] = None   # TaskPlan instance (or None if understanding skipped)
    trajectory_report: Optional[str] = None  # Path to trajectory report file
    token_usage: Optional[object] = None
    tool_calls_count: int = 0
    workspace: str = ""
    autosci_dir: str = ""


# ── Core function ──────────────────────────────────────────────────────────────

def run_scientist(
    task: str,
    workspace: str,
    *,
    model: str = None,
    max_iterations: int = None,
    workflow_name: str = None,
    share_memory: bool = False,
    enable_understanding: bool = True,
    on_event: Callable[[str, dict], None] = None,
) -> ScientistResult:
    """Run AutoSci in scientist mode.

    Args:
        task:               Task description string.
        workspace:          Path to the project workspace directory.
        model:              Override LLM model name.
        max_iterations:     Override agent iteration budget.
        workflow_name:      If set, run workflow-driven mode (e.g. "reproduce").
        share_memory:       If True, use global ~/.autosci/memory/ instead of
                            workspace-local .autosci/memory/.
        enable_understanding: If False, skip TaskUnderstandingAgent (faster, less context).
        on_event:           Optional callback(event_name, data) for progress reporting.
                            Called with events: "workspace_ready", "task_plan",
                            "agent_start", "agent_done", "trajectory".

    Returns:
        ScientistResult with status, response, task_plan, trajectory_report, etc.
    """
    from autosci.cli import _init_scientist_workspace, _build_scientist_config, _bootstrap
    from autosci.configs.default import load_config
    from autosci.agents.main_agent import MainAgent
    from autosci.runtime.runner import AgentRunner
    from autosci.trajectory.recorder import TrajectoryRecorder
    from autosci.workflow.understanding import TaskUnderstanding
    from autosci.protocols.task_plan import save_task_plan

    def _emit(event: str, **data):
        if on_event:
            on_event(event, data)

    # ── 1. Workspace ──────────────────────────────────────────────────────────
    workspace, autosci_dir = _init_scientist_workspace(workspace)
    _emit("workspace_ready", workspace=workspace, autosci_dir=autosci_dir)

    # ── 2. Config ─────────────────────────────────────────────────────────────
    base_config = load_config()
    if model:
        base_config["llm"]["model"] = model
    config = _build_scientist_config(base_config, autosci_dir, share_memory=share_memory)
    if not enable_understanding:
        config["scientist"]["enable_understanding"] = False

    # ── 3. Bootstrap ──────────────────────────────────────────────────────────
    _bootstrap()

    # ── 4. Trajectory + Runner ────────────────────────────────────────────────
    recorder = None
    if config["scientist"]["enable_trajectory"]:
        traj_dir = os.path.join(autosci_dir, "trajectory")
        recorder = TrajectoryRecorder(traj_dir)

    runner = AgentRunner(config, trajectory_recorder=recorder)

    # ── 5. Workflow resolution ────────────────────────────────────────────────
    workflow_def = None
    if workflow_name:
        from autosci.workflow.engine import load_workflow, find_workflow
        wf_path = find_workflow(workflow_name)
        if not wf_path:
            raise ValueError(f"Workflow '{workflow_name}' not found. "
                             "Run `autosci workflow list` to see available workflows.")
        workflow_def = load_workflow(wf_path)

    # ── 6. Task understanding ─────────────────────────────────────────────────
    task_plan = None
    if config["scientist"]["enable_understanding"]:
        logger.info("Running TaskUnderstandingAgent...")
        understanding = TaskUnderstanding(runner, workspace)
        task_plan = understanding.analyze(task)
        save_task_plan(task_plan, autosci_dir)
        _emit("task_plan",
              goal=task_plan.goal,
              claims=len(task_plan.claims),
              rqs=len(task_plan.research_questions))

    os.chdir(workspace)

    # ── 7a. Workflow-driven mode ──────────────────────────────────────────────
    if workflow_def:
        from autosci.workflow.engine import WorkflowEngine
        engine = WorkflowEngine(runner)
        wf_result = engine.run(workflow_def, task, task_plan=task_plan)
        result_path = engine.save_result(wf_result, workspace)
        _emit("agent_done", status=wf_result.status, result_path=result_path)
        return ScientistResult(
            status=wf_result.status,
            response=wf_result.final_output,
            task_plan=task_plan,
            token_usage=None,
            tool_calls_count=wf_result.total_tool_calls,
            workspace=workspace,
            autosci_dir=autosci_dir,
        )

    # ── 7b. Agent-driven mode ─────────────────────────────────────────────────
    full_task = task
    if task_plan:
        full_task = task + "\n\n" + task_plan.to_prompt_block()

    agent = MainAgent()
    if max_iterations:
        agent.max_iterations = max_iterations

    _emit("agent_start", model=config["llm"]["model"],
          max_iterations=agent.max_iterations)

    result = runner.run(agent, full_task)

    _emit("agent_done", status=result.status,
          total_tokens=result.token_usage.total_tokens,
          tool_calls=result.tool_calls_count)

    # ── 8. Trajectory export ──────────────────────────────────────────────────
    traj_report = None
    if recorder:
        traj_report = runner.export_trajectory(
            task=task,
            task_plan=task_plan.to_dict() if task_plan else None,
        )
        if traj_report:
            _emit("trajectory", path=traj_report)

    return ScientistResult(
        status=result.status,
        response=result.response,
        task_plan=task_plan,
        trajectory_report=traj_report,
        token_usage=result.token_usage,
        tool_calls_count=result.tool_calls_count,
        workspace=workspace,
        autosci_dir=autosci_dir,
    )
