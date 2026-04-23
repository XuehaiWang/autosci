"""Context engine — abstract interface for context management strategies."""

from abc import ABC, abstractmethod

from autosci.protocols.schemas import TokenUsage


class ContextEngine(ABC):
    """Abstract interface for context management.

    Implementations decide when and how to compress the conversation history
    to fit within the LLM's context window. The runner calls should_compress()
    after each turn and compress() when needed.
    """

    @abstractmethod
    def should_compress(self, current_tokens: int) -> bool:
        """Check if compression is needed based on current token count."""
        ...

    @abstractmethod
    def compress(self, messages: list[dict]) -> list[dict]:
        """Compress messages and return a shorter message list.

        The returned list replaces the current messages in the runner's loop.
        """
        ...

    def on_session_start(self, context_window: int) -> None:
        """Called when a new session starts. Sets context budget."""
        pass

    def update_token_count(self, usage: TokenUsage) -> None:
        """Update internal token tracking after each LLM call."""
        pass
