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

        Supports two layouts:
        1. Directory-based: <dir>/<name>/agent.yaml (+ prompt.md)
        2. Flat file:       <dir>/<name>.yaml

        Loading order (later entries can override earlier ones by name):
        1. Built-in agents:  autosci/agents/*/agent.yaml
        2. Legacy templates: autosci/agents/templates/*.yaml
        3. User dir:         ~/.autosci/agents/*/agent.yaml + ~/.autosci/agents/*.yaml
        4. extra_dirs        (caller-supplied paths, if any)

        Returns:
            Number of agents successfully loaded.
        """
        from autosci.agents.dynamic_agent import load_agent_yaml

        agents_dir = Path(__file__).parent
        builtin_templates = agents_dir / "templates"
        dirs = [str(agents_dir), str(builtin_templates), "~/.autosci/agents/"] + (extra_dirs or [])

        loaded = 0
        for dir_path in dirs:
            expanded = Path(dir_path).expanduser()
            if not expanded.is_dir():
                continue

            # Scan subdirectories for agent.yaml (directory-based format)
            for sub in sorted(expanded.iterdir()):
                if sub.is_dir():
                    agent_yaml = sub / "agent.yaml"
                    if agent_yaml.is_file():
                        agent = load_agent_yaml(str(agent_yaml))
                        if agent:
                            self.register_instance(agent)
                            loaded += 1

            # Scan flat YAML files (legacy format)
            for yaml_file in sorted(expanded.glob("*.yaml")) + sorted(expanded.glob("*.yml")):
                # Skip if this is an agent.yaml inside a subdir (already handled)
                if yaml_file.name == "agent.yaml":
                    continue
                agent = load_agent_yaml(str(yaml_file))
                if agent:
                    self.register_instance(agent)
                    loaded += 1

        if loaded:
            logger.info(f"Discovered {loaded} YAML-defined agent(s)")
        return loaded


# Singleton instance
agent_registry = AgentRegistry()
