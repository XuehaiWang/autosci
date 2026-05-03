"""Agent tools — delegate subtasks, ask user for input, and spawn dynamic agents.

These tools are "intercepted" by the runner before normal registry dispatch.
The schemas are registered so they appear in the LLM's tool list, but the
actual execution is handled by AgentRunner._handle_agent_tool().
"""


def delegate(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: delegate must be handled by the runner"


def delegate_parallel(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: delegate_parallel must be handled by the runner"


def ask_user(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: ask_user must be handled by the runner"


def create_agent(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: create_agent must be handled by the runner"


def update_claim(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: update_claim must be handled by the runner"