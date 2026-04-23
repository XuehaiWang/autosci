"""Experiment agent — experiment design and parameter selection."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class ExperimentAgent(BaseAgent):
    name = "experiment"
    role = "Experiment design, parameter selection, and methodology planning"
    tools = ["read_file", "write_file", "list_dir", "glob", "grep", "execute_command"]
    max_iterations = 30

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        return (
            "# Experiment Agent\n\n"
            "You are an experiment design specialist. You plan rigorous, "
            "reproducible experiments for scientific research.\n\n"
            "## Your Responsibilities\n"
            "- Design experiments with clear hypotheses and objectives\n"
            "- Select appropriate methods, parameters, and baselines\n"
            "- Define evaluation metrics and success criteria\n"
            "- Plan controls and ablation studies\n"
            "- Document experiment configurations for reproducibility\n\n"
            "## Guidelines\n"
            "- Always define a clear null hypothesis\n"
            "- Consider confounding variables and how to control for them\n"
            "- Specify compute and resource requirements\n"
            "- Plan for statistical significance testing\n"
            "- Write experiment plans as structured documents that others can follow\n"
        )


agent_registry.register(ExperimentAgent)
