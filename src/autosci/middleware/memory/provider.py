"""Memory provider — abstract interface for memory backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MemoryEntry:
    """A single memory record."""
    id: str
    type: str  # episodic | semantic | procedural
    tags: list[str]
    summary: str
    content: str
    source_session: Optional[str] = None
    created: str = ""
    updated: str = ""
    relevance_score: float = 0.0


class MemoryProvider(ABC):
    """Abstract interface for memory storage backends.

    Implementations handle how memories are stored, retrieved, and managed.
    The MemoryManager calls these methods at the appropriate lifecycle points.
    """

    # === Required methods ===

    @abstractmethod
    def store(
        self,
        content: str,
        memory_type: str,
        tags: list[str] = None,
        summary: str = None,
        source_session: str = None,
    ) -> str:
        """Store a memory entry. Returns the memory ID."""
        ...

    @abstractmethod
    def retrieve(
        self,
        query: str,
        memory_type: str = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories ranked by relevance."""
        ...

    @abstractmethod
    def get_system_prompt_block(self, task: str = None) -> str:
        """Generate a memory summary block for injection into the system prompt.

        If task is provided, bias toward task-relevant memories.
        """
        ...

    # === Optional lifecycle hooks ===

    def on_session_start(self, session_id: str, task: str) -> None:
        """Pre-fetch relevant memories for the upcoming task."""
        pass

    def on_session_end(self, session_id: str, messages: list[dict]) -> None:
        """Post-session hook — called by MemoryManager for reflection."""
        pass

    def on_pre_compress(self, messages_to_compress: list[dict]) -> None:
        """Rescue valuable information before context compression."""
        pass

    def on_delegation(
        self, parent_session: str, child_session: str,
        child_agent: str, child_task: str,
    ) -> None:
        """Prepare relevant memories for a subagent delegation."""
        pass

    def list_all(self, memory_type: str = None) -> list[MemoryEntry]:
        """List all stored memories, optionally filtered by type."""
        return []

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        return False

    def update(self, memory_id: str, content: str = None, tags: list[str] = None) -> bool:
        """Update an existing memory. Returns True if updated."""
        return False
