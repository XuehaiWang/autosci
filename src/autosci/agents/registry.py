"""Agent registry with self-registration and auto-discovery."""

import logging
from pathlib import Path

from autosci.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Central registry for all agents.

    Supports two registration modes:
    - Class-based: agent_registry.register(MyAgentClass) — for agents needing Python logic
    - Instance-based: agent_registry.register_instance(dynamic_agent) — DynamicAgent from YAML

    Discovery order (discover_yaml):
    1. Built-in templates: agents/templates/*.yaml   — always loaded
    2. User overrides:     ~/.autosci/agents/*.yaml  — loaded after, can override built-ins

    The delegate tool looks up agents by name via get().
    The MainAgent's system prompt includes the list from list_available().
    """

    def __init__(self):
        self._agents: dict[str, type[BaseAgent]] = {}       # class-based
        self._instances: dict[str, BaseAgent] = {}           # instance-based (DynamicAgent)

    def register(self, agent_class: type[BaseAgent]) -> None:
        """Register an agent class."""
        name = agent_class.name
        if not name:
            raise ValueError(f"Agent class {agent_class.__name__} has no 'name' attribute")
        if name in self._agents or name in self._instances:
            logger.warning(f"Agent '{name}' already registered, overwriting")
        self._agents[name] = agent_class
        logger.debug(f"Registered agent class: {name}")

    def register_instance(self, agent: BaseAgent) -> None:
        """Register a pre-built agent instance (e.g. DynamicAgent)."""
        name = agent.name
        if not name:
            raise ValueError(f"Agent instance has no 'name' attribute")
        if name in self._agents or name in self._instances:
            logger.warning(f"Agent '{name}' already registered, overwriting")
        self._instances[name] = agent
        logger.debug(f"Registered agent instance: {name}")

    def get(self, name: str) -> BaseAgent:
        """Look up an agent by name. Returns an instance (creates one for class-based agents)."""
        if name in self._instances:
            return self._instances[name]
        if name in self._agents:
            return self._agents[name]()
        available = list(self._agents.keys()) + list(self._instances.keys())
        raise KeyError(f"Unknown agent: '{name}'. Available: {available}")

    def list_available(self) -> list[dict]:
        """Return metadata for all registered agents."""
        result = []
        for cls in self._agents.values():
            result.append({"name": cls.name, "role": cls.role})
        for inst in self._instances.values():
            result.append({"name": inst.name, "role": inst.role})
        return result

    def all_names(self) -> list[str]:
        """Return all registered agent names."""
        return list(self._agents.keys()) + list(self._instances.keys())

    def discover_yaml(self, extra_dirs: list[str] = None) -> int:
        """Load all YAML agent definitions and register them as DynamicAgents.

        Loading order (later entries can override earlier ones by name):
        1. Built-in templates: src/autosci/agents/templates/*.yaml
        2. User dir:           ~/.autosci/agents/*.yaml
        3. extra_dirs          (caller-supplied paths, if any)

        Args:
            extra_dirs: additional directories to scan beyond the defaults.

        Returns:
            Number of agents successfully loaded.
        """
        from autosci.agents.dynamic_agent import load_agent_yaml

        builtin_templates = Path(__file__).parent / "templates"
        dirs = [str(builtin_templates), "~/.autosci/agents/"] + (extra_dirs or [])

        loaded = 0
        for dir_path in dirs:
            expanded = Path(dir_path).expanduser()
            if not expanded.is_dir():
                continue
            for yaml_file in sorted(expanded.glob("*.yaml")) + sorted(expanded.glob("*.yml")):
                agent = load_agent_yaml(str(yaml_file))
                if agent:
                    self.register_instance(agent)
                    loaded += 1

        if loaded:
            logger.info(f"Discovered {loaded} YAML-defined agent(s)")
        return loaded


# Singleton instance
agent_registry = AgentRegistry()
