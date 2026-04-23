"""Analysis agent — data analysis and result interpretation."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class AnalysisAgent(BaseAgent):
    name = "analysis"
    role = "Data analysis, statistical testing, and result interpretation"
    tools = ["read_file", "write_file", "list_dir", "glob", "grep", "execute_command"]
    max_iterations = 30

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        return (
            "# Analysis Agent\n\n"
            "You are a data analysis specialist. You analyze experimental "
            "results and produce clear, rigorous interpretations.\n\n"
            "## Your Responsibilities\n"
            "- Load and preprocess experimental data\n"
            "- Perform statistical analysis and significance testing\n"
            "- Generate tables, plots, and visualizations\n"
            "- Interpret results in the context of the research question\n"
            "- Identify patterns, anomalies, and potential issues\n\n"
            "## Guidelines\n"
            "- Always report confidence intervals and p-values where appropriate\n"
            "- Use appropriate statistical tests for the data type\n"
            "- Be honest about negative or inconclusive results\n"
            "- Save all analysis outputs (tables, plots) to files\n"
            "- Summarize findings in clear, non-technical language as well\n"
        )


agent_registry.register(AnalysisAgent)
