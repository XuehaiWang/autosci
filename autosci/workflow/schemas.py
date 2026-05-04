"""Data classes for workflow definitions and execution results."""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PhaseSpec:
    """One phase in a workflow — maps to a single agent run."""

    id: str
    agent: str                          # agent name (must be registered)
    goal: str                           # phase-specific goal injected into task
    depends_on: list[str] = field(default_factory=list)
    max_iterations: Optional[int] = None  # override agent default if set

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseSpec":
        return cls(
            id=d["id"],
            agent=d["agent"],
            goal=d["goal"],
            depends_on=d.get("depends_on", []),
            max_iterations=d.get("max_iterations", None),
        )


@dataclass
class WorkflowDef:
    """A complete workflow definition loaded from YAML."""

    name: str
    description: str
    phases: list[PhaseSpec]
    source_path: str = ""

    @classmethod
    def from_dict(cls, d: dict, source_path: str = "") -> "WorkflowDef":
        phases = [PhaseSpec.from_dict(p) for p in d.get("phases", [])]
        return cls(
            name=d.get("name", "unnamed"),
            description=d.get("description", ""),
            phases=phases,
            source_path=source_path,
        )

    def topological_order(self) -> list[PhaseSpec]:
        """Return phases in dependency-respecting order (Kahn's algorithm)."""
        phase_map = {p.id: p for p in self.phases}
        in_degree = {p.id: len(p.depends_on) for p in self.phases}
        # Validate deps
        for p in self.phases:
            for dep in p.depends_on:
                if dep not in phase_map:
                    raise ValueError(f"Phase '{p.id}' depends on unknown phase '{dep}'")

        queue = collections.deque(pid for pid, deg in in_degree.items() if deg == 0)
        order = []
        while queue:
            pid = queue.popleft()
            order.append(phase_map[pid])
            for p in self.phases:
                if pid in p.depends_on:
                    in_degree[p.id] -= 1
                    if in_degree[p.id] == 0:
                        queue.append(p.id)

        if len(order) != len(self.phases):
            raise ValueError("Workflow has a dependency cycle")
        return order


@dataclass
class PhaseResult:
    """Execution result for one workflow phase."""

    phase_id: str
    agent: str
    status: str          # completed | error | skipped
    output: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0
    skip_reason: str = ""

    @property
    def summary(self) -> str:
        """Short summary for injecting into downstream phases."""
        if self.status == "skipped":
            return f"[Phase '{self.phase_id}' was skipped: {self.skip_reason}]"
        if self.status == "error":
            return f"[Phase '{self.phase_id}' failed]"
        # Truncate to first 800 chars to keep context manageable
        snippet = self.output[:800].rstrip()
        if len(self.output) > 800:
            snippet += "\n...(truncated)"
        return f"## Phase '{self.phase_id}' ({self.agent})\n\n{snippet}"


@dataclass
class WorkflowResult:
    """Complete result of a workflow execution."""

    workflow_name: str
    task: str
    status: str          # completed | partial | failed
    phases: list[PhaseResult] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(p.total_tokens for p in self.phases)

    @property
    def total_tool_calls(self) -> int:
        return sum(p.tool_calls_count for p in self.phases)

    @property
    def final_output(self) -> str:
        """Return the last completed phase's output as the workflow result."""
        for p in reversed(self.phases):
            if p.status == "completed":
                return p.output
        return "(no completed phase)"
