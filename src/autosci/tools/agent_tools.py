"""Agent tools — delegate subtasks and ask user for input.

These tools are "intercepted" by the runner before normal registry dispatch.
The schemas are registered so they appear in the LLM's tool list, but the
actual execution is handled by AgentRunner._handle_agent_tool().
"""

from autosci.tools.registry import registry

# === Delegate ===

DELEGATE_SCHEMA = {
    "name": "delegate",
    "description": (
        "Delegate a subtask to a specialized subagent. The subagent runs "
        "independently with its own tool set and iteration budget, then "
        "returns its result. Use this when a task is better handled by a "
        "specialist (e.g., code writing, data analysis, literature search)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Name of the subagent to delegate to (e.g., 'code', 'research', 'analysis')",
            },
            "task": {
                "type": "string",
                "description": "Clear description of the subtask for the subagent",
            },
            "context": {
                "type": "string",
                "description": "Relevant context from the current conversation to pass to the subagent",
            },
        },
        "required": ["agent", "task"],
    },
}


def _delegate_placeholder(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: delegate must be handled by the runner"


registry.register("delegate", DELEGATE_SCHEMA, _delegate_placeholder, toolset="agent")


# === Ask User ===

ASK_USER_SCHEMA = {
    "name": "ask_user",
    "description": (
        "Ask the user a question and wait for their response. Use this when "
        "you need clarification, confirmation, or a decision from the user "
        "before proceeding."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user",
            },
        },
        "required": ["question"],
    },
}


def _ask_user_placeholder(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: ask_user must be handled by the runner"


registry.register("ask_user", ASK_USER_SCHEMA, _ask_user_placeholder, toolset="agent")
