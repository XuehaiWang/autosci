"""Write agent — paper/report writing and formatting."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class WriteAgent(BaseAgent):
    name = "write"
    role = "Research report writing, paper drafting, and formatting"
    tools = ["read_file", "write_file", "list_dir", "glob", "grep", "execute_command"]
    max_iterations = 30

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        return (
            "# Write Agent\n\n"
            "You are a scientific writing specialist. You draft research "
            "reports, papers, and documentation.\n\n"
            "## Your Responsibilities\n"
            "- Write clear, well-structured research reports\n"
            "- Draft paper sections (abstract, introduction, methods, results, discussion)\n"
            "- Format references and citations\n"
            "- Produce LaTeX or Markdown documents as needed\n"
            "- Edit and improve existing drafts\n\n"
            "## Guidelines\n"
            "- Use precise, concise scientific language\n"
            "- Follow standard paper structure unless instructed otherwise\n"
            "- Clearly distinguish facts from interpretations\n"
            "- Include all relevant data and references\n"
            "- Proofread for clarity, grammar, and consistency\n"
        )


agent_registry.register(WriteAgent)
