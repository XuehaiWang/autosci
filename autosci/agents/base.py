"""Base agent class — all agents inherit from this."""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Subclasses must define class attributes (name, role, tools) and implement
    get_system_prompt(). The AgentRunner can run any BaseAgent subclass
    without knowing its concrete type.
    """

    name: str = ""
    role: str = ""
    tools: list[str] = []  # allowed tool names; empty = all tools
    max_iterations: int = 50

    @abstractmethod
    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        """Build the system prompt for this agent.

        Args:
            available_agents: list of {"name": ..., "role": ...} dicts for
                subagents this agent can delegate to. None if delegation
                is not available.

        Returns:
            The complete system prompt string.
        """
        ...
