"""DynamicAgent — an agent instantiated from a YAML definition at runtime."""

from __future__ import annotations

import logging
import os
from typing import Optional

from autosci.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# Tools that require runner-level orchestration and are therefore not available
# to YAML-defined agents (which are always leaf nodes in the delegation tree).
_ORCHESTRATION_TOOLS = {"delegate", "delegate_parallel", "create_agent", "update_claim"}

# Agents that ARE allowed to use orchestration tools (they are orchestrators).
_ORCHESTRATOR_AGENTS = {"main"}


class DynamicAgent(BaseAgent):
    """An agent whose behavior is defined by a YAML file rather than Python code.

    Supports two YAML formats:
    1. Directory-based (new): agents/<name>/agent.yaml + prompt.md
       - agent.yaml has: name, description, tools, max_iterations, prompt (relative path)
       - prompt.md contains the system prompt text
    2. Flat file (legacy): agents/templates/<name>.yaml
       - Single YAML with embedded system_prompt field

    Design constraint: DynamicAgent is a *leaf* agent by default — orchestration
    tools are stripped. Exception: agents listed in _ORCHESTRATOR_AGENTS keep them.
    """

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
        raw_tools = tools or []
        # Strip orchestration tools unless this is an orchestrator agent
        if name not in _ORCHESTRATOR_AGENTS:
            stripped = [t for t in raw_tools if t not in _ORCHESTRATION_TOOLS]
            if len(stripped) != len(raw_tools):
                removed = [t for t in raw_tools if t in _ORCHESTRATION_TOOLS]
                logger.warning(
                    f"DynamicAgent '{name}': removed orchestration tools {removed} "
                    f"(leaf agents cannot delegate)"
                )
            self.tools = stripped
        else:
            self.tools = raw_tools
        self.max_iterations = max_iterations
        self.source_path = source_path

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        prompt = self._system_prompt
        # For orchestrator agents, inject available subagents list
        if available_agents and "{{available_agents}}" in prompt:
            agent_lines = []
            for info in available_agents:
                if info["name"] not in (self.name, "assistant", "task_understanding"):
                    agent_lines.append(f"- **{info['name']}**: {info['role']}")
            prompt = prompt.replace("{{available_agents}}", "\n".join(agent_lines))
        elif "{{available_agents}}" in prompt:
            prompt = prompt.replace("{{available_agents}}", "(no subagents available)")
        return prompt

    def __repr__(self) -> str:
        return f"DynamicAgent(name={self.name!r}, source={self.source_path!r})"

    @classmethod
    def from_dict(cls, data: dict, source_path: str = "") -> "DynamicAgent":
        """Create a DynamicAgent from a parsed YAML dict.

        Supports both formats:
        - New: 'prompt' field → relative path to .md file
        - Legacy: 'system_prompt' field → inline prompt text
        """
        name = data.get("name", "").strip()
        if not name:
            raise ValueError(f"Agent YAML missing 'name' field: {source_path}")

        # Resolve system prompt
        system_prompt = data.get("system_prompt", "")
        prompt_file = data.get("prompt", "")

        if prompt_file and source_path:
            # Load prompt from external .md file (relative to YAML dir)
            prompt_path = os.path.join(os.path.dirname(source_path), prompt_file)
            if os.path.isfile(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    system_prompt = f.read().strip()
                logger.debug(f"Loaded prompt for '{name}' from {prompt_path}")
            else:
                logger.warning(f"Prompt file not found for '{name}': {prompt_path}")

        if not system_prompt:
            system_prompt = f"You are the {name} agent."

        return cls(
            name=name,
            role=data.get("description", data.get("role", "")),
            system_prompt=system_prompt,
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