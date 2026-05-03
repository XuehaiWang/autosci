"""Memory tools — store and recall memories during agent execution."""

import threading

# Thread-local storage so each child runner (thread) has its own MemoryManager
# reference without interfering with the parent or sibling runners.
_local = threading.local()


def set_memory_manager(manager) -> None:
    """Called by the runner to inject the MemoryManager instance for this thread."""
    _local.manager = manager


def _get_manager():
    return getattr(_local, "manager", None)


# === Store Memory ===


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


# === Recall Memory ===


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


