"""DynamicAgent — an agent instantiated from a YAML definition at runtime."""

from __future__ import annotations

import logging
import os
from typing import Optional

from autosci.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class DynamicAgent(BaseAgent):
    """An agent whose behavior is defined by a YAML file rather than Python code.

    Created by AgentRegistry when discover_yaml() loads a *.yaml agent definition.
    The class attributes (name, role, tools, max_iterations) are set per-instance
    from the YAML, and get_system_prompt() returns the YAML-specified system_prompt.
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
        self.tools = tools or []
        self.max_iterations = max_iterations
        self.source_path = source_path  # path to the originating YAML file

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        return self._system_prompt

    def __repr__(self) -> str:
        return f"DynamicAgent(name={self.name!r}, source={self.source_path!r})"

    @classmethod
    def from_dict(cls, data: dict, source_path: str = "") -> "DynamicAgent":
        """Create a DynamicAgent from a parsed YAML dict."""
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
