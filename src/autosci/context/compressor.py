"""Summarization-based context compressor.

Uses a three-zone protection model:

    HEAD ZONE (protected) — system prompt + first exchange
    MIDDLE ZONE (compressible) — old conversation turns, tool results
    TAIL ZONE (protected) — recent context

Compression pipeline:
1. Prune old tool results (replace with summaries, truncate long args)
2. Split messages into head/middle/tail zones
3. Summarize the middle zone via LLM
4. Anti-thrashing: skip if recent compressions saved < 10%
"""

import json
import logging
from typing import Optional

from autosci.context.engine import ContextEngine
from autosci.protocols.schemas import TokenUsage

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English, ~2 for CJK."""
    return max(1, len(text) // 3)


def _estimate_message_tokens(msg: dict) -> int:
    """Estimate tokens in a message."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return _estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                total += _estimate_tokens(json.dumps(block, ensure_ascii=False))
            else:
                total += _estimate_tokens(str(block))
        return total
    return _estimate_tokens(str(content))


class SummarizationCompressor(ContextEngine):
    """Lossy summarization-based context compression."""

    def __init__(
        self,
        context_window: int = 200000,
        threshold_ratio: float = 0.75,
        tail_budget_ratio: float = 0.3,
        max_summary_tokens: int = 2000,
        llm_client=None,
        summary_model: str = None,
    ):
        self.context_window = context_window
        self.threshold_tokens = int(context_window * threshold_ratio)
        self.tail_budget = int(context_window * tail_budget_ratio)
        self.max_summary_tokens = max_summary_tokens
        self.llm_client = llm_client
        self.summary_model = summary_model

        # Token tracking
        self._last_prompt_tokens = 0

        # Anti-thrashing: track savings from recent compressions
        self._compression_history: list[float] = []

    def on_session_start(self, context_window: int) -> None:
        self.context_window = context_window
        self.threshold_tokens = int(context_window * 0.75)
        self.tail_budget = int(context_window * 0.3)
        self._compression_history.clear()

    def update_token_count(self, usage: TokenUsage) -> None:
        self._last_prompt_tokens = usage.prompt_tokens

    def should_compress(self, current_tokens: int = None) -> bool:
        """Check if compression is needed."""
        tokens = current_tokens or self._last_prompt_tokens
        if tokens < self.threshold_tokens:
            return False

        # Anti-thrashing: if last 2 compressions saved < 10%, skip
        if len(self._compression_history) >= 2:
            recent = self._compression_history[-2:]
            if all(saving < 0.1 for saving in recent):
                logger.info("Skipping compression: anti-thrashing (recent compressions ineffective)")
                return False

        return True

    def compress(self, messages: list[dict]) -> list[dict]:
        """Compress messages using the three-zone protection model."""
        if len(messages) <= 3:
            return messages

        before_tokens = sum(_estimate_message_tokens(m) for m in messages)
        logger.info(f"Compressing context: ~{before_tokens} tokens, {len(messages)} messages")

        # Step 1: Prune tool results
        messages = self._prune_tool_results(messages)

        # Step 2: Split into zones
        head, middle, tail = self._split_zones(messages)

        if not middle:
            logger.info("No middle zone to compress")
            return messages

        # Step 3: Summarize middle zone
        summary = self._summarize_middle(middle)

        # Step 4: Reconstruct message list
        summary_msg = {
            "role": "user",
            "content": (
                f"[Context compressed. Previous conversation summary:]\n\n"
                f"{summary}\n\n"
                f"[End of summary. The conversation continues below with the most recent context.]"
            ),
        }
        result = head + [summary_msg] + tail

        # Track compression effectiveness
        after_tokens = sum(_estimate_message_tokens(m) for m in result)
        saving = 1.0 - (after_tokens / before_tokens) if before_tokens > 0 else 0
        self._compression_history.append(saving)
        logger.info(
            f"Compression: {before_tokens} -> {after_tokens} tokens "
            f"({saving:.0%} reduction, {len(messages)} -> {len(result)} messages)"
        )

        return result

    def _prune_tool_results(self, messages: list[dict]) -> list[dict]:
        """Replace old, large tool results with truncated summaries."""
        pruned = []
        # Keep last N messages as-is (recent context)
        recent_count = min(6, len(messages))

        for i, msg in enumerate(messages):
            is_recent = (i >= len(messages) - recent_count)

            if is_recent:
                pruned.append(msg)
                continue

            content = msg.get("content")
            if isinstance(content, list):
                new_content = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result_text = block.get("content", "")
                        if isinstance(result_text, str) and len(result_text) > 500:
                            block = {
                                **block,
                                "content": result_text[:500] + "\n... [truncated]",
                            }
                    new_content.append(block)
                pruned.append({**msg, "content": new_content})
            else:
                pruned.append(msg)

        return pruned

    def _split_zones(self, messages: list[dict]) -> tuple[list, list, list]:
        """Split messages into head (protected), middle (compressible), tail (protected)."""
        if len(messages) <= 4:
            return messages, [], []

        # Head: first 2 messages (user query + first assistant response)
        head_size = min(2, len(messages))

        # Tail: accumulate from the end until we hit the tail budget
        tail_start = len(messages)
        tail_tokens = 0
        for i in range(len(messages) - 1, head_size - 1, -1):
            msg_tokens = _estimate_message_tokens(messages[i])
            if tail_tokens + msg_tokens > self.tail_budget:
                break
            tail_tokens += msg_tokens
            tail_start = i

        # Ensure tail has at least 2 messages
        tail_start = min(tail_start, len(messages) - 2)
        # Ensure tail doesn't overlap head
        tail_start = max(tail_start, head_size)

        head = messages[:head_size]
        middle = messages[head_size:tail_start]
        tail = messages[tail_start:]

        logger.debug(
            f"Zones: head={len(head)}, middle={len(middle)}, tail={len(tail)}"
        )
        return head, middle, tail

    def _summarize_middle(self, middle: list[dict]) -> str:
        """Summarize the middle zone messages."""
        # Build a text representation of middle messages for summarization
        text_parts = []
        for msg in middle:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = self._flatten_content(content)
            if isinstance(content, str) and content.strip():
                # Truncate individual messages for the summary prompt
                if len(content) > 1000:
                    content = content[:1000] + "..."
                text_parts.append(f"[{role}]: {content}")

        conversation_text = "\n\n".join(text_parts)

        # If we have an LLM client, use it for summarization
        if self.llm_client:
            return self._llm_summarize(conversation_text)

        # Fallback: simple extractive summary (no LLM)
        return self._simple_summarize(conversation_text)

    def _llm_summarize(self, conversation_text: str) -> str:
        """Use LLM to generate a summary of the conversation."""
        prompt = (
            "Summarize the following conversation between a user and an AI research assistant. "
            "Focus on:\n"
            "1. Key decisions and findings\n"
            "2. Important tool results and data\n"
            "3. Current research direction and progress\n"
            "4. Any errors or issues encountered\n\n"
            "Be concise but preserve critical details that would be needed to continue the work.\n\n"
            f"Conversation:\n{conversation_text}"
        )

        try:
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a precise summarizer. Output only the summary, no preamble.",
            )
            return response.content or self._simple_summarize(conversation_text)
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}, falling back to simple summary")
            return self._simple_summarize(conversation_text)

    def _simple_summarize(self, conversation_text: str) -> str:
        """Simple extractive summary without LLM."""
        lines = conversation_text.split("\n")
        # Keep first and last portions
        if len(lines) <= 20:
            return conversation_text

        kept = lines[:10] + ["\n... [middle omitted] ...\n"] + lines[-10:]
        return "\n".join(kept)

    def _flatten_content(self, content: list) -> str:
        """Flatten a list of content blocks into text."""
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    parts.append(f"[Tool: {block.get('name', '?')}]")
                elif block.get("type") == "tool_result":
                    result = block.get("content", "")
                    if isinstance(result, str) and len(result) > 200:
                        result = result[:200] + "..."
                    parts.append(f"[Result: {result}]")
        return "\n".join(parts)
