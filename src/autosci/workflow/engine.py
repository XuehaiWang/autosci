"""WorkflowEngine — drives phase-by-phase agent execution."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from autosci.workflow.schemas import WorkflowDef, PhaseResult, WorkflowResult

if TYPE_CHECKING:
    from autosci.runtime.runner import AgentRunner
    from autosci.protocols.task_plan import TaskPlan

logger = logging.getLogger(__name__)


def load_workflow(path: str) -> WorkflowDef:
    """Load a WorkflowDef from a YAML file."""
    try:
        import yaml
    except ImportError:
        raise RuntimeError("pyyaml is required for workflow support: pip install pyyaml")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow YAML must be a dict: {path}")
    return WorkflowDef.from_dict(data, source_path=path)


def find_workflow(name: str) -> Optional[str]:
    """Search for a workflow YAML by name in user dir and built-in templates.

    Returns the path string if found, None otherwise.
    """
    search_dirs = [
        Path("~/.autosci/workflows").expanduser(),
        Path(__file__).parent / "templates",
    ]
    for d in search_dirs:
        for suffix in (".yaml", ".yml"):
            candidate = d / f"{name}{suffix}"
            if candidate.exists():
                return str(candidate)
    return None


class WorkflowEngine:
    """Executes a WorkflowDef phase by phase using a shared AgentRunner.

    Each phase:
    1. Builds a full task string = original task + phase goal + upstream summaries
    2. Runs the designated agent via the runner
    3. Collects PhaseResult; skips downstream phases if a dependency failed
    """

    def __init__(self, runner: "AgentRunner"):
        self.runner = runner

    def run(
        self,
        workflow: WorkflowDef,
        task: str,
        task_plan: Optional["TaskPlan"] = None,
        console=None,
    ) -> WorkflowResult:
        """Execute all phases in dependency order.

        Args:
            workflow: the loaded WorkflowDef
            task: original user task string (injected into every phase)
            task_plan: optional structured task understanding; injected into every phase
            console: optional rich Console for progress output

        Returns:
            WorkflowResult with results for every phase
        """
        from autosci.agents.registry import agent_registry

        phases = workflow.topological_order()
        results: dict[str, PhaseResult] = {}  # phase_id -> PhaseResult
        failed_ids: set[str] = set()

        workflow_result = WorkflowResult(
            workflow_name=workflow.name,
            task=task,
            status="running",
        )

        total = len(phases)
        for idx, phase in enumerate(phases, 1):
            phase_label = f"[{idx}/{total}] Phase '{phase.id}' ({phase.agent})"

            # Check if any dependency failed → skip
            failed_deps = [d for d in phase.depends_on if d in failed_ids]
            if failed_deps:
                logger.warning(f"{phase_label} skipped — dependencies failed: {failed_deps}")
                if console:
                    console.print(f"  [yellow]SKIP[/yellow] {phase_label} (deps failed: {failed_deps})")
                pr = PhaseResult(
                    phase_id=phase.id,
                    agent=phase.agent,
                    status="skipped",
                    output="",
                    skip_reason=f"dependencies failed: {failed_deps}",
                )
                results[phase.id] = pr
                workflow_result.phases.append(pr)
                failed_ids.add(phase.id)
                continue

            # Resolve agent
            try:
                agent = agent_registry.get(phase.agent)
            except KeyError:
                logger.error(f"{phase_label} unknown agent '{phase.agent}'")
                if console:
                    console.print(f"  [red]ERROR[/red] {phase_label} — unknown agent '{phase.agent}'")
                pr = PhaseResult(
                    phase_id=phase.id,
                    agent=phase.agent,
                    status="error",
                    output=f"Unknown agent: '{phase.agent}'",
                )
                results[phase.id] = pr
                workflow_result.phases.append(pr)
                failed_ids.add(phase.id)
                continue

            # Override max_iterations if specified
            if phase.max_iterations is not None:
                agent.max_iterations = phase.max_iterations

            # Build phase task string
            phase_task = self._build_phase_task(task, phase, results, task_plan=task_plan)

            logger.info(f"Running {phase_label}")
            if console:
                console.print(f"  [cyan]RUN[/cyan]  {phase_label}")

            # Run agent
            try:
                run_result = self.runner.run(agent=agent, task=phase_task)
            except Exception as e:
                logger.exception(f"{phase_label} raised an exception")
                pr = PhaseResult(
                    phase_id=phase.id,
                    agent=phase.agent,
                    status="error",
                    output=f"Exception: {e}",
                )
                results[phase.id] = pr
                workflow_result.phases.append(pr)
                failed_ids.add(phase.id)
                continue

            status = "completed" if run_result.status == "completed" else "error"
            pr = PhaseResult(
                phase_id=phase.id,
                agent=phase.agent,
                status=status,
                output=run_result.response,
                prompt_tokens=run_result.token_usage.prompt_tokens,
                completion_tokens=run_result.token_usage.completion_tokens,
                total_tokens=run_result.token_usage.total_tokens,
                tool_calls_count=run_result.tool_calls_count,
            )
            results[phase.id] = pr
            workflow_result.phases.append(pr)

            if status == "error":
                failed_ids.add(phase.id)
                if console:
                    console.print(f"  [red]FAIL[/red] {phase_label} (status={run_result.status})")
            else:
                if console:
                    console.print(
                        f"  [green]DONE[/green] {phase_label} "
                        f"({run_result.token_usage.total_tokens:,} tokens, "
                        f"{run_result.tool_calls_count} calls)"
                    )

        # Determine overall status
        completed = sum(1 for p in workflow_result.phases if p.status == "completed")
        total_phases = len(workflow_result.phases)
        if completed == total_phases:
            workflow_result.status = "completed"
        elif completed == 0:
            workflow_result.status = "failed"
        else:
            workflow_result.status = "partial"

        return workflow_result

    def _build_phase_task(
        self,
        task: str,
        phase,
        results: dict[str, PhaseResult],
        task_plan: Optional["TaskPlan"] = None,
    ) -> str:
        """Build the full task string for a phase, injecting goal and upstream context."""
        parts = [task]

        if task_plan:
            parts.append("")
            parts.append(task_plan.to_prompt_block())

        parts += ["", f"## Your Phase Goal\n\n{phase.goal}"]

        upstream = [results[dep] for dep in phase.depends_on if dep in results]
        if upstream:
            parts.append("\n## Results from Previous Phases\n")
            for pr in upstream:
                parts.append(pr.summary)

        return "\n".join(parts)

    def save_result(self, result: WorkflowResult, workspace: str) -> str:
        """Save a WorkflowResult summary to {workspace}/workflow_result.md."""
        lines = [
            f"# Workflow Result: {result.workflow_name}",
            f"\n**Task**: {result.task}",
            f"**Status**: {result.status}",
            f"**Total tokens**: {result.total_tokens:,}",
            f"**Total tool calls**: {result.total_tool_calls}",
            "\n---\n",
        ]
        for pr in result.phases:
            status_icon = {"completed": "✓", "error": "✗", "skipped": "⊘"}.get(pr.status, "?")
            lines.append(f"## {status_icon} Phase `{pr.phase_id}` ({pr.agent})")
            lines.append(f"**Status**: {pr.status} | "
                         f"**Tokens**: {pr.total_tokens:,} | "
                         f"**Calls**: {pr.tool_calls_count}")
            if pr.status == "skipped":
                lines.append(f"\n*Skipped: {pr.skip_reason}*\n")
            else:
                lines.append(f"\n{pr.output}\n")
            lines.append("---\n")

        content = "\n".join(lines)
        path = os.path.join(workspace, "workflow_result.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
