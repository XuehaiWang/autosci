"""DynamicAgent — an agent instantiated from a YAML definition at runtime."""

from __future__ import annotations

import logging
from typing import Optional

from autosci.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# Tools that require runner-level orchestration and are therefore not available
# to YAML-defined agents (which are always leaf nodes in the delegation tree).
_ORCHESTRATION_TOOLS = {"delegate", "delegate_parallel", "create_agent", "update_claim"}


class DynamicAgent(BaseAgent):
    """An agent whose behavior is defined by a YAML file rather than Python code.

    Created by AgentRegistry when discover_yaml() loads a *.yaml agent definition.
    The class attributes (name, role, tools, max_iterations) are set per-instance
    from the YAML, and get_system_prompt() returns the YAML-specified system_prompt.

    Design constraint: DynamicAgent is always a *leaf* agent — it cannot delegate
    to subagents. Orchestration tools (delegate, delegate_parallel, create_agent,
    update_claim) are stripped from its tool list at construction time. If you need
    an agent that can orchestrate, subclass BaseAgent in Python instead.
    """

    # Instance-level overrides (set in __init__)
    name: str = ""
    role: str = ""
    tools: list[str] = []
    max_iterations: int = 30

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        tools: list[str] = None,
        max_iterations: int = 30,
        source_path: str = "",
    ):
        self.name = name
        self.role = role
        self._system_prompt = system_prompt
        # Strip orchestration tools — DynamicAgent is always a leaf node
        raw_tools = tools or []
        stripped = [t for t in raw_tools if t not in _ORCHESTRATION_TOOLS]
        if len(stripped) != len(raw_tools):
            removed = [t for t in raw_tools if t in _ORCHESTRATION_TOOLS]
            logger.warning(
                f"DynamicAgent '{name}': removed orchestration tools {removed} "
                f"(leaf agents cannot delegate)"
            )
        self.tools = stripped
        self.max_iterations = max_iterations
        self.source_path = source_path  # path to the originating YAML file

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        # available_agents is intentionally ignored: DynamicAgent is a leaf node
        # and does not have access to subagent delegation.
        return self._system_prompt

    def __repr__(self) -> str:
        return f"DynamicAgent(name={self.name!r}, source={self.source_path!r})"

    @classmethod
    def from_dict(cls, data: dict, source_path: str = "") -> "DynamicAgent":
        """Create a DynamicAgent from a parsed YAML dict.

        Expected keys:
            name (str, required): unique agent identifier
            description / role (str): one-line role description
            system_prompt (str): full system prompt text
            tools (list[str]): allowed tool names (orchestration tools are stripped)
            max_iterations (int): iteration budget (default 30)
        """
        name = data.get("name", "").strip()
        if not name:
            raise ValueError(f"Agent YAML missing 'name' field: {source_path}")
        return cls(
            name=name,
            role=data.get("description", data.get("role", "")),
            system_prompt=data.get("system_prompt", f"You are the {name} agent."),
            tools=data.get("tools", []),
            max_iterations=int(data.get("max_iterations", 30)),
            source_path=source_path,
        )


def load_agent_yaml(path: str) -> Optional[DynamicAgent]:
    """Load a single agent YAML file and return a DynamicAgent, or None on error."""
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed — cannot load YAML agents")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            logger.warning(f"Agent YAML is not a dict: {path}")
            return None
        agent = DynamicAgent.from_dict(data, source_path=path)
        logger.debug(f"Loaded YAML agent: {agent.name} from {path}")
        return agent
    except Exception as e:
        logger.warning(f"Failed to load agent YAML {path}: {e}")
        return None
