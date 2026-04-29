"""Memory tools — store and recall memories during agent execution."""

import threading

from autosci.tools.registry import registry

# Thread-local storage so each child runner (thread) has its own MemoryManager
# reference without interfering with the parent or sibling runners.
_local = threading.local()


def set_memory_manager(manager) -> None:
    """Called by the runner to inject the MemoryManager instance for this thread."""
    _local.manager = manager


def _get_manager():
    return getattr(_local, "manager", None)


# === Store Memory ===

STORE_MEMORY_SCHEMA = {
    "name": "store_memory",
    "description": (
        "Store a piece of information in long-term memory for future sessions. "
        "Use this to remember key findings, domain knowledge, or effective procedures. "
        "Memories persist across sessions and are automatically retrieved when relevant."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The information to remember",
            },
            "memory_type": {
                "type": "string",
                "enum": ["episodic", "semantic", "procedural"],
                "description": (
                    "Type of memory: "
                    "'episodic' for events/results/failures, "
                    "'semantic' for domain knowledge, "
                    "'procedural' for workflows/procedures"
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords for retrieval (e.g., ['training', 'resnet', 'cifar10'])",
            },
            "summary": {
                "type": "string",
                "description": "One-line summary (under 120 chars). Auto-generated if omitted.",
            },
        },
        "required": ["content", "memory_type"],
    },
}


def store_memory(
    content: str,
    memory_type: str,
    tags: list[str] = None,
    summary: str = None,
) -> str:
    _manager = _get_manager()
    if _manager is None:
        return "Error: memory system not initialized"
    try:
        mem_id = _manager.store(
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            summary=summary,
        )
        return f"Memory stored: {mem_id} (type={memory_type})"
    except Exception as e:
        return f"Error storing memory: {e}"


registry.register("store_memory", STORE_MEMORY_SCHEMA, store_memory, toolset="memory")


# === Recall Memory ===

RECALL_MEMORY_SCHEMA = {
    "name": "recall_memory",
    "description": (
        "Search long-term memory for relevant information from past sessions. "
        "Use this to recall previous results, domain knowledge, or learned procedures."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in memory",
            },
            "memory_type": {
                "type": "string",
                "enum": ["episodic", "semantic", "procedural"],
                "description": "Filter by memory type. Omit to search all types.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results. Default: 5",
            },
        },
        "required": ["query"],
    },
}


def recall_memory(query: str, memory_type: str = None, limit: int = 5) -> str:
    _manager = _get_manager()
    if _manager is None:
        return "Error: memory system not initialized"
    try:
        memories = _manager.recall(query, memory_type=memory_type, limit=limit)
        if not memories:
            return "No relevant memories found."

        parts = [f"Found {len(memories)} relevant memories:\n"]
        for mem in memories:
            parts.append(
                f"### [{mem.type}] {mem.summary}\n"
                f"- Tags: {', '.join(mem.tags) if mem.tags else 'none'}\n"
                f"- Date: {mem.created[:10] if mem.created else 'unknown'}\n"
                f"- Relevance: {mem.relevance_score:.2f}\n\n"
                f"{mem.content}\n"
            )
        return "\n".join(parts)
    except Exception as e:
        return f"Error recalling memory: {e}"


registry.register("recall_memory", RECALL_MEMORY_SCHEMA, recall_memory, toolset="memory")
