"""Memory manager — orchestrates memory providers and lifecycle hooks."""

import json
import logging
from typing import Optional

from autosci.memory.provider import MemoryEntry, MemoryProvider

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrates memory providers and manages the memory lifecycle.

    Coordinates between the runner and the active memory provider,
    handling session start/end, pre-compression rescue, and post-session
    reflection.
    """

    def __init__(self, provider: MemoryProvider, llm_client=None, trajectory=None):
        self.provider = provider
        self.llm_client = llm_client
        self.trajectory = trajectory
        self._session_stack: list[tuple[str, str]] = []  # stack of (session_id, task)

    @property
    def _current_session_id(self) -> Optional[str]:
        return self._session_stack[-1][0] if self._session_stack else None

    @property
    def _current_task(self) -> Optional[str]:
        return self._session_stack[-1][1] if self._session_stack else None

    # === Lifecycle hooks (called by the runner) ===

    def on_session_start(self, session_id: str, task: str) -> None:
        """Called at the beginning of an agent run. Supports nested delegation."""
        self._session_stack.append((session_id, task))
        self.provider.on_session_start(session_id, task)

    def on_session_end(self, session_id: str, messages: list[dict], status: str,
                       mode: str = "scientist") -> list[str]:
        """Called when an agent run completes. Triggers reflection if successful.

        Args:
            mode: "assistant" or "scientist". Assistant mode biases reflection
                  toward extracting user preferences and habits.

        Returns summaries of memories stored (for trajectory).
        """
        stored_summaries = []
        if status == "completed" and self.llm_client:
            stored_summaries = self._reflect_on_session(session_id, messages, mode=mode)
        self.provider.on_session_end(session_id, messages)
        if self._session_stack and self._session_stack[-1][0] == session_id:
            self._session_stack.pop()
        return stored_summaries

    def on_pre_compress(self, messages_to_compress: list[dict]) -> None:
        """Called before context compression. Rescues key info from tool results."""
        self._rescue_from_messages(messages_to_compress)
        self.provider.on_pre_compress(messages_to_compress)

    # === Public API (used by memory tools) ===

    def store(
        self,
        content: str,
        memory_type: str,
        tags: list[str] = None,
        summary: str = None,
    ) -> str:
        """Store a memory. Delegates to the provider."""
        return self.provider.store(
            content=content,
            memory_type=memory_type,
            tags=tags,
            summary=summary,
            source_session=self._current_session_id,
        )

    def recall(self, query: str, memory_type: str = None, limit: int = 5) -> list[MemoryEntry]:
        """Retrieve relevant memories. Delegates to the provider."""
        return self.provider.retrieve(query, memory_type=memory_type, limit=limit)

    def get_system_prompt_block(self) -> str:
        """Get memory block for system prompt injection."""
        return self.provider.get_system_prompt_block(task=self._current_task)

    def get_recent_entries(self, limit: int = 10) -> list:
        """Return recently retrieved memory entries (for trajectory logging)."""
        if not self._current_task:
            return []
        return self.provider.retrieve(self._current_task, limit=limit)

    # === Post-session reflection ===

    def _reflect_on_session(self, session_id: str, messages: list[dict],
                            mode: str = "scientist") -> list[str]:
        """Use LLM to extract memories from the session history.
        Returns summaries of stored memories (for trajectory)."""
        session_text = self._condense_messages(messages)
        if not session_text or len(session_text) < 100:
            return []

        if mode == "assistant":
            mode_instruction = (
                "Focus especially on:\n"
                "- User preferences and habits (preferred tools, languages, style)\n"
                "- Recurring tasks or workflows the user frequently requests\n"
                "- Personal context (projects, domain, timezone, terminology)\n"
                "- Things the user explicitly asked to remember\n"
            )
        else:
            mode_instruction = (
                "Focus especially on:\n"
                "- Reusable workflows and methodologies that worked well (type: procedural)\n"
                "- Environment/library quirks discovered (e.g. 'cvxpy fails here, use scipy') (type: procedural)\n"
                "- General domain knowledge that applies beyond this specific task (type: semantic)\n"
                "- Do NOT save task-specific numbers (exact metric values, dataset statistics) — "
                "those are in the trajectory, not worth keeping as memories\n"
            )

        prompt = (
            "Review this session and extract memories worth keeping for future sessions.\n\n"
            "Output a JSON array of memories. Each memory should have:\n"
            '- "type": "episodic" (what happened), "semantic" (knowledge learned), '
            'or "procedural" (effective workflow or preference)\n'
            '- "tags": list of lowercase keywords for retrieval\n'
            '- "summary": one-line summary (under 120 chars)\n'
            '- "content": detailed description (1-3 sentences)\n\n'
            f"{mode_instruction}\n"
            "Rules:\n"
            "- Only extract genuinely useful insights, not trivial observations\n"
            "- Skip warnings, deprecation notices, and routine tool outputs\n"
            "- If nothing is worth saving, output []\n"
            "- Limit to at most 5 memories per session\n\n"
            f"Session:\n{session_text}"
        )

        try:
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You extract structured memories from research sessions. Output only valid JSON.",
            )

            if not response.content:
                return []

            memories = self._parse_memories_json(response.content)
            stored_summaries = []
            for mem in memories:
                self.provider.store(
                    content=mem.get("content", ""),
                    memory_type=mem.get("type", "episodic"),
                    tags=mem.get("tags", []),
                    summary=mem.get("summary", ""),
                    source_session=session_id,
                )
                stored_summaries.append(
                    f"[{mem.get('type','?')}] {mem.get('summary','')}"
                )

            if memories:
                logger.info(f"Reflection: extracted {len(memories)} memories from session {session_id}")

            return stored_summaries

        except Exception as e:
            logger.warning(f"Session reflection failed: {e}")
            return []

    # === Pre-compression rescue ===

    def _rescue_from_messages(self, messages: list[dict]) -> None:
        """Extract genuine errors from tool results before they get compressed.

        Only saves real errors (Exception/Error), not warnings or routine output.
        Deduplicates by error prefix within the session.
        """
        seen_prefixes: set[str] = set()

        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue

                result_text = block.get("content", "")
                if not isinstance(result_text, str) or len(result_text) < 200:
                    continue

                text_lower = result_text.lower()

                # Only save genuine errors — must have traceback or explicit Error/Exception
                is_genuine_error = any(kw in text_lower for kw in ["traceback (most recent", "exception:", "error:"])
                # Skip anything that is primarily a warning (even if it mentions "error" in passing)
                is_warning = any(kw in text_lower for kw in [
                    "warning:", "deprecat", "userwarning", "convergencewarning",
                    "futurewarning", "runtimewarning", "warnings.warn",
                ])
                if not is_genuine_error or is_warning:
                    continue

                # Deduplicate by first 80 chars of error
                prefix = result_text[:80].strip()
                if prefix in seen_prefixes:
                    continue
                seen_prefixes.add(prefix)

                error_summary = result_text[:200].replace("\n", " ")
                self.provider.store(
                    content=f"Tool error encountered:\n{result_text[:500]}",
                    memory_type="episodic",
                    tags=["error", "tool-result"],
                    summary=f"Error: {error_summary[:100]}",
                    source_session=self._current_session_id,
                )

    # === Helpers ===

    def _condense_messages(self, messages: list[dict]) -> str:
        """Build a condensed text representation of messages for reflection."""
        parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            text_parts.append(f"[Tool: {block.get('name', '?')}]")
                        elif block.get("type") == "tool_result":
                            r = block.get("content", "")
                            if isinstance(r, str) and len(r) > 300:
                                r = r[:300] + "..."
                            text_parts.append(f"[Result: {r}]")
                text = "\n".join(text_parts)
            else:
                text = str(content)

            if text.strip():
                # Truncate individual messages
                if len(text) > 500:
                    text = text[:500] + "..."
                parts.append(f"[{role}]: {text}")

        return "\n\n".join(parts)

    def _parse_memories_json(self, text: str) -> list[dict]:
        """Parse LLM output to extract memories JSON array."""
        # Find JSON array in the response
        text = text.strip()

        # Try direct parse
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result[:5]
            return []
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in markdown code block
        import re
        match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result[:5]
            except json.JSONDecodeError:
                pass

        # Try to find bare JSON array
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return result[:5]
            except json.JSONDecodeError:
                pass

        return []
