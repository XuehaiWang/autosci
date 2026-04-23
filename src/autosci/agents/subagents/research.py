"""Research agent — literature search, paper reading, knowledge synthesis."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class ResearchAgent(BaseAgent):
    name = "research"
    role = "Literature search, paper reading, and knowledge synthesis"
    tools = ["read_file", "write_file", "list_dir", "glob", "grep", "execute_command"]
    max_iterations = 30

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        return (
            "# Research Agent\n\n"
            "You are a research specialist focused on literature search, paper reading, "
            "and knowledge synthesis.\n\n"
            "## Your Responsibilities\n"
            "- Search for and read scientific papers and technical documents\n"
            "- Summarize key findings, methods, and results\n"
            "- Identify relevant prior work and state-of-the-art approaches\n"
            "- Synthesize information across multiple sources\n"
            "- Produce structured research summaries\n\n"
            "## Guidelines\n"
            "- Be thorough — cover key papers, not just the first result\n"
            "- Note limitations and potential biases in sources\n"
            "- Cite sources clearly so findings can be verified\n"
            "- Organize output as structured summaries with clear sections\n"
            "- Focus on what is directly relevant to the given task\n"
        )


agent_registry.register(ResearchAgent)
