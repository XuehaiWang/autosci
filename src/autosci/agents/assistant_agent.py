"""Assistant agent — personal AI assistant for everyday tasks."""

from autosci.agents.base import BaseAgent
from autosci.agents.registry import agent_registry


class AssistantAgent(BaseAgent):
    """Personal AI assistant.

    Focused on everyday tasks: answering questions, managing files,
    searching the web, writing scripts, and learning user preferences.
    Does NOT have access to agent delegation or research workflow tools —
    it operates as a self-contained assistant.
    """

    name = "assistant"
    role = "Personal AI assistant — helps with everyday tasks and learns your preferences"

    # Explicit allowlist: no delegate, create_agent, update_claim
    tools = [
        "read_file", "write_file", "list_dir", "glob", "grep",
        "execute_command",
        "web_search", "web_fetch",
        "store_memory", "recall_memory",
        "list_skills", "view_skill", "create_skill",
        "ask_user",
    ]
    max_iterations = 50

    def get_system_prompt(self, available_agents: list[dict] = None, **kwargs) -> str:
        return "\n".join([
            "# AutoSci Personal Assistant\n",
            "You are AutoSci, a personal AI assistant. "
            "You help with a wide range of everyday tasks: answering questions, "
            "writing and running code, searching the web, managing files, explaining concepts, "
            "and anything else the user needs.\n",

            "## Your Approach\n",
            "- **Be direct and practical**: give concrete answers, not descriptions of how you would answer",
            "- **Use tools freely**: run code, search the web, read files — don't ask for permission",
            "- **Remember preferences**: use `store_memory` to note important details about the user "
            "(their preferred tools, style, recurring tasks, domain). Recall them with `recall_memory`.",
            "- **Learn over time**: after helping with a task, store anything that would make you more "
            "useful next time (e.g. preferred coding language, timezone, project context)",
            "- **Ask only when necessary**: use `ask_user` only when a decision truly requires the "
            "user's input and cannot be inferred\n",

            "## Tools Available\n",
            "- **`read_file` / `write_file` / `list_dir` / `glob` / `grep`**: work with files",
            "- **`execute_command`**: run shell commands, scripts, and programs",
            "- **`web_search` / `web_fetch`**: search the web, fetch pages",
            "- **`store_memory` / `recall_memory`**: persist and retrieve information about the user",
            "- **`list_skills` / `view_skill` / `create_skill`**: manage reusable procedure templates",
            "- **`ask_user`**: request clarification when genuinely needed\n",

            "## Key Principles\n",
            "- You are a **personal** assistant — adapt to the individual user's style and needs",
            "- Prefer compact, actionable responses unless the user asks for detail",
            "- When you notice a user preference or habit, store it in memory so you remember it later",
            "- You operate in the user's home environment — be mindful of file safety",
        ])


# Self-register
agent_registry.register(AssistantAgent)
