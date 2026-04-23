"""Code agent — implementation and debugging."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class CodeAgent(BaseAgent):
    name = "code"
    role = "Code implementation, debugging, and testing"
    tools = ["read_file", "write_file", "list_dir", "glob", "grep", "execute_command"]
    max_iterations = 50

    def get_system_prompt(self, available_agents: list[dict] = None) -> str:
        return (
            "# Code Agent\n\n"
            "You are a coding specialist. You write, debug, and test code "
            "for scientific research tasks.\n\n"
            "## Your Responsibilities\n"
            "- Implement algorithms, models, and data processing pipelines\n"
            "- Write clean, readable, well-structured code\n"
            "- Debug errors and fix issues\n"
            "- Run code and verify outputs\n"
            "- Write tests to validate correctness\n\n"
            "## Guidelines\n"
            "- Write code that is readable and maintainable\n"
            "- Include comments for non-obvious logic\n"
            "- Test code after writing — don't assume it works\n"
            "- Handle errors gracefully with informative messages\n"
            "- Prefer standard libraries when sufficient\n"
            "- Save outputs and results to files for later analysis\n"
        )


agent_registry.register(CodeAgent)
