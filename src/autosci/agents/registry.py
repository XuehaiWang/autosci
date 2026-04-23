"""Agent registry with self-registration and auto-discovery."""

import importlib
import logging
from pathlib import Path

from autosci.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Central registry for all agents.

    Agents self-register by calling agent_registry.register() at module top level.
    The delegate tool looks up agents by name via get().
    The MainAgent's system prompt includes the list from list_available().
    """

    def __init__(self):
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, agent_class: type[BaseAgent]) -> None:
        """Register an agent class."""
        name = agent_class.name
        if not name:
            raise ValueError(f"Agent class {agent_class.__name__} has no 'name' attribute")
        if name in self._agents:
            logger.warning(f"Agent '{name}' already registered, overwriting")
        self._agents[name] = agent_class
        logger.debug(f"Registered agent: {name}")

    def get(self, name: str) -> type[BaseAgent]:
        """Look up an agent class by name."""
        if name not in self._agents:
            available = list(self._agents.keys())
            raise KeyError(f"Unknown agent: '{name}'. Available: {available}")
        return self._agents[name]

    def list_available(self) -> list[dict]:
        """Return metadata for all registered agents."""
        return [
            {"name": cls.name, "role": cls.role}
            for cls in self._agents.values()
        ]

    def discover(self, subagents_dir: str = None) -> None:
        """Auto-import all agent modules in subagents/ to trigger self-registration."""
        if subagents_dir is None:
            subagents_dir = str(Path(__file__).parent / "subagents")

        subagents_path = Path(subagents_dir)
        if not subagents_path.exists():
            return

        for py_file in sorted(subagents_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"autosci.agents.subagents.{py_file.stem}"
            try:
                importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"Failed to import agent module {module_name}: {e}")


# Singleton instance
agent_registry = AgentRegistry()
