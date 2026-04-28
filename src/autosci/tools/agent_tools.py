"""Agent tools — delegate subtasks, ask user for input, and spawn dynamic agents.

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


# === Create Agent ===

CREATE_AGENT_SCHEMA = {
    "name": "create_agent",
    "description": (
        "Create and run a custom YAML-defined agent for a specific subtask. "
        "Use this when no existing subagent fits the task — you can define the "
        "agent's role and tools inline, and it will be instantiated and run immediately. "
        "The agent definition is saved as a YAML file in the workspace for reuse."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique name for this agent (lowercase, no spaces)",
            },
            "description": {
                "type": "string",
                "description": "One-line description of what this agent does",
            },
            "system_prompt": {
                "type": "string",
                "description": "Full system prompt for the agent — its role, responsibilities, and guidelines",
            },
            "task": {
                "type": "string",
                "description": "The specific task to run the agent on",
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Tool names this agent may use. "
                    "Available: read_file, write_file, list_dir, glob, grep, "
                    "execute_command, web_search, web_fetch, store_memory, recall_memory"
                ),
            },
            "max_iterations": {
                "type": "integer",
                "description": "Max iteration budget (default 30)",
            },
        },
        "required": ["name", "description", "system_prompt", "task"],
    },
}


def _create_agent_placeholder(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: create_agent must be handled by the runner"


registry.register("create_agent", CREATE_AGENT_SCHEMA, _create_agent_placeholder, toolset="agent")


# === Update Claim ===

UPDATE_CLAIM_SCHEMA = {
    "name": "update_claim",
    "description": (
        "Update the verification status of a research Claim in task_plan.json. "
        "Call this whenever you obtain experimental evidence that supports, refutes, "
        "or partially validates a Claim. This creates a traceable record of "
        "which claims have been addressed and what the evidence was."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "claim_id": {
                "type": "string",
                "description": "The Claim ID to update (e.g. 'C1', 'C2')",
            },
            "status": {
                "type": "string",
                "enum": ["supported", "refuted", "partial", "unverified"],
                "description": (
                    "New status: 'supported' (evidence confirms it), "
                    "'refuted' (evidence contradicts it), "
                    "'partial' (partially confirmed with caveats), "
                    "'unverified' (reset to initial state)"
                ),
            },
            "evidence": {
                "type": "string",
                "description": (
                    "Concrete evidence for this status update: specific metric values, "
                    "experiment results, citations. Be quantitative."
                ),
            },
        },
        "required": ["claim_id", "status", "evidence"],
    },
}


def _update_claim_placeholder(**kwargs):
    """Placeholder — actual execution is intercepted by AgentRunner."""
    return "Error: update_claim must be handled by the runner"


registry.register("update_claim", UPDATE_CLAIM_SCHEMA, _update_claim_placeholder, toolset="agent")
