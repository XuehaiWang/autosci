"""Main agent — the research orchestrator."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class MainAgent(BaseAgent):
    """Top-level orchestrator agent.

    Plans the research workflow, delegates to subagents, and synthesizes results.
    Has access to all tools (tools=[] means unrestricted).
    """

    name = "main"
    role = "Research orchestrator — plans and coordinates the research workflow"
    tools = []  # empty = access to all tools
    max_iterations = 100

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        parts = [
            "# AutoSci Research Agent\n",
            "You are AutoSci, an intelligent research agent designed for "
            "end-to-end scientific research tasks.\n",
            "## Your Capabilities\n",
            "- Plan and execute research workflows",
            "- Search and analyze scientific literature",
            "- Design and run experiments",
            "- Write code for data analysis and experimentation",
            "- Analyze results and draw conclusions",
            "- Generate research reports and papers\n",
            "## Guidelines\n",
            "- Break complex research tasks into clear, manageable phases",
            "- Be thorough and methodical — scientific rigor is essential",
            "- Use tools to gather real data rather than speculating",
            "- Acknowledge uncertainty and limitations in your findings",
            "- Keep the user informed of progress at key milestones",
            "- When a task is too large, plan first, then execute step by step",
        ]

        if available_agents:
            parts.extend([
                "\n## Available Subagents\n",
                "You can delegate specialized subtasks to these agents "
                "using the `delegate` tool:\n",
            ])
            for agent_info in available_agents:
                if agent_info["name"] != self.name:  # don't list self
                    parts.append(f"- **{agent_info['name']}**: {agent_info['role']}")

        return "\n".join(parts)


# Self-register
agent_registry.register(MainAgent)
