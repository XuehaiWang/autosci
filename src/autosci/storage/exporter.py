"""Session exporter — converts sessions from SQLite to readable Markdown files."""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

from autosci.storage.session_store import SessionStore, Session, Message

logger = logging.getLogger(__name__)


class SessionExporter:
    """Exports completed sessions to human-readable Markdown files.

    Output format:
    - YAML frontmatter with session metadata
    - Chronological message log with role labels
    - Tool calls rendered as fenced code blocks
    - Subagent delegations shown as nested sections
    """

    def __init__(self, store: SessionStore):
        self.store = store

    def export(self, session_id: str, output_dir: str) -> str:
        """Export a session to a Markdown file.

        Args:
            session_id: the session to export
            output_dir: directory to write the file to

        Returns:
            Path to the exported file.
        """
        session = self.store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        messages = self.store.get_messages(session_id)
        child_sessions = self.store.get_child_sessions(session_id)

        # Build Markdown content
        md = self._build_markdown(session, messages, child_sessions)

        # Write to file
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        filename = self._build_filename(session)
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)

        logger.info(f"Exported session {session_id} to {filepath}")
        return filepath

    def export_on_session_end(self, session_id: str, workspace: str) -> Optional[str]:
        """Auto-export a session when it ends. Called by the runner."""
        try:
            export_dir = os.path.join(workspace, "sessions")
            return self.export(session_id, export_dir)
        except Exception as e:
            logger.warning(f"Failed to export session {session_id}: {e}")
            return None

    def _build_markdown(
        self,
        session: Session,
        messages: list[Message],
        child_sessions: list[Session],
    ) -> str:
        parts = []

        # YAML frontmatter
        parts.append(self._build_frontmatter(session))

        # Messages
        for msg in messages:
            parts.append(self._format_message(msg))

        # Child sessions summary
        if child_sessions:
            parts.append("\n---\n")
            parts.append("## Subagent Sessions\n")
            for child in child_sessions:
                parts.append(
                    f"- **{child.agent_name}** ({child.id[:8]}): "
                    f"{child.task[:100]} — {child.status}\n"
                )

        return "\n".join(parts)

    def _build_frontmatter(self, session: Session) -> str:
        lines = [
            "---",
            f'session_id: "{session.id}"',
            f"agent: {session.agent_name}",
            f'task: "{self._escape_yaml(session.task[:200])}"',
            f"started: \"{session.started_at}\"",
        ]
        if session.ended_at:
            lines.append(f"ended: \"{session.ended_at}\"")
        lines.extend([
            f"status: {session.status}",
            f"total_tokens: {session.total_tokens}",
            f"tool_calls: {session.tool_calls_count}",
        ])
        if session.parent_session_id:
            lines.append(f"parent_session: \"{session.parent_session_id}\"")
        lines.append("---\n")
        return "\n".join(lines)

    def _format_message(self, msg: Message) -> str:
        content = msg.content
        role = msg.role

        # Try to parse JSON content
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = content

        # User message
        if role == "user":
            return self._format_user_message(parsed)

        # Assistant message
        if role == "assistant":
            return self._format_assistant_message(parsed)

        return f"\n**{role}**\n{content}\n"

    def _format_user_message(self, content) -> str:
        # Simple string user message
        if isinstance(content, str):
            return f"\n## User\n\n{content}\n"

        # Tool results
        if isinstance(content, list):
            parts = ["\n### Tool Results\n"]
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    result = block.get("content", "")
                    # Truncate long results in export
                    if isinstance(result, str) and len(result) > 2000:
                        result = result[:2000] + "\n... (truncated)"
                    parts.append(f"**Result** (`{tool_id[:8]}`):\n```\n{result}\n```\n")
            return "\n".join(parts)

        return f"\n## User\n\n{content}\n"

    def _format_assistant_message(self, content) -> str:
        # Simple string
        if isinstance(content, str):
            return f"\n## Assistant\n\n{content}\n"

        # List of blocks (text + tool_use)
        if isinstance(content, list):
            parts = ["\n## Assistant\n"]
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(f"\n{block['text']}\n")
                    elif block.get("type") == "tool_use":
                        name = block.get("name", "unknown")
                        args = block.get("input", {})
                        args_str = json.dumps(args, indent=2, ensure_ascii=False)
                        parts.append(
                            f"\n**Tool Call: `{name}`**\n"
                            f"```json\n{args_str}\n```\n"
                        )
            return "\n".join(parts)

        return f"\n## Assistant\n\n{content}\n"

    def _build_filename(self, session: Session) -> str:
        """Build a human-readable filename for the exported session."""
        # Parse timestamp
        try:
            dt = datetime.fromisoformat(session.started_at)
            ts = dt.strftime("%Y%m%d_%H%M%S")
        except ValueError:
            ts = "unknown"

        # Slug from task
        slug = re.sub(r"[^\w\s-]", "", session.task[:50]).strip()
        slug = re.sub(r"[\s]+", "_", slug).lower()
        if not slug:
            slug = "session"

        return f"{ts}_{session.id[:8]}_{slug}.md"

    def _escape_yaml(self, text: str) -> str:
        return text.replace('"', '\\"').replace("\n", " ")
