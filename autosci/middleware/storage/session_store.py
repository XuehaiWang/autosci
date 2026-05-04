"""SQLite-backed session and message storage."""

import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    id: str
    agent_name: str
    task: str
    status: str  # running | completed | error | budget_exhausted
    started_at: str = ""
    ended_at: Optional[str] = None
    parent_session_id: Optional[str] = None
    total_tokens: int = 0
    tool_calls_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class Message:
    id: Optional[int]
    session_id: str
    role: str
    content: str  # JSON-encoded for complex content
    tool_calls: Optional[str] = None  # JSON-encoded
    token_count: int = 0
    created_at: str = ""


class SessionStore:
    """SQLite-backed persistent storage for sessions and messages.

    Uses WAL mode for concurrent read access and FTS5 for full-text search.
    """

    def __init__(self, db_path: str):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                parent_session_id TEXT,
                total_tokens INTEGER DEFAULT 0,
                tool_calls_count INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}',
                FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content_json TEXT NOT NULL,
                tool_calls_json TEXT,
                token_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id);
        """)

        # Create FTS table if not exists
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                USING fts5(content_text, content='messages', content_rowid='id');
            """)
        except sqlite3.OperationalError:
            pass  # FTS5 not available, skip

        self._conn.commit()

    # === Session operations ===

    def create_session(
        self,
        session_id: str,
        agent_name: str,
        task: str,
        parent_session_id: str = None,
        metadata: dict = None,
    ) -> Session:
        """Create a new session."""
        now = datetime.now().isoformat()
        session = Session(
            id=session_id,
            agent_name=agent_name,
            task=task,
            status="running",
            started_at=now,
            parent_session_id=parent_session_id,
            metadata=metadata or {},
        )
        self._conn.execute(
            """INSERT INTO sessions
               (id, agent_name, task, status, started_at, parent_session_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session.id, session.agent_name, session.task, session.status,
             session.started_at, session.parent_session_id,
             json.dumps(session.metadata, ensure_ascii=False)),
        )
        self._conn.commit()
        logger.debug(f"Created session: {session_id}")
        return session

    def end_session(
        self,
        session_id: str,
        status: str,
        total_tokens: int = 0,
        tool_calls_count: int = 0,
    ) -> None:
        """Mark a session as ended."""
        now = datetime.now().isoformat()
        self._conn.execute(
            """UPDATE sessions
               SET status=?, ended_at=?, total_tokens=?, tool_calls_count=?
               WHERE id=?""",
            (status, now, total_tokens, tool_calls_count, session_id),
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    def list_sessions(self, limit: int = 20, agent_name: str = None) -> list[Session]:
        """List recent sessions."""
        query = "SELECT * FROM sessions"
        params = []
        if agent_name:
            query += " WHERE agent_name=?"
            params.append(agent_name)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_child_sessions(self, parent_id: str) -> list[Session]:
        """Get all child sessions of a parent."""
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE parent_session_id=? ORDER BY started_at",
            (parent_id,),
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    # === Message operations ===

    def append_message(
        self,
        session_id: str,
        role: str,
        content,
        tool_calls=None,
        token_count: int = 0,
    ) -> None:
        """Append a message to a session."""
        now = datetime.now().isoformat()
        content_json = json.dumps(content, ensure_ascii=False) if not isinstance(content, str) else content
        tool_calls_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None

        cursor = self._conn.execute(
            """INSERT INTO messages
               (session_id, role, content_json, tool_calls_json, token_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, role, content_json, tool_calls_json, token_count, now),
        )

        # Update FTS index
        content_text = self._extract_text(content)
        if content_text:
            try:
                self._conn.execute(
                    "INSERT INTO messages_fts(rowid, content_text) VALUES (?, ?)",
                    (cursor.lastrowid, content_text),
                )
            except sqlite3.OperationalError:
                pass  # FTS not available

        self._conn.commit()

    def get_messages(self, session_id: str) -> list[Message]:
        """Get all messages for a session in chronological order."""
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    # === Search ===

    def search_sessions(self, query: str, limit: int = 10) -> list[Session]:
        """Full-text search across session messages."""
        try:
            rows = self._conn.execute(
                """SELECT DISTINCT s.* FROM sessions s
                   JOIN messages m ON m.session_id = s.id
                   JOIN messages_fts fts ON fts.rowid = m.id
                   WHERE messages_fts MATCH ?
                   ORDER BY s.started_at DESC LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [self._row_to_session(r) for r in rows]
        except sqlite3.OperationalError:
            # FTS not available, fall back to LIKE search
            rows = self._conn.execute(
                """SELECT DISTINCT s.* FROM sessions s
                   JOIN messages m ON m.session_id = s.id
                   WHERE m.content_json LIKE ?
                   ORDER BY s.started_at DESC LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
            return [self._row_to_session(r) for r in rows]

    # === Helpers ===

    def _row_to_session(self, row) -> Session:
        return Session(
            id=row["id"],
            agent_name=row["agent_name"],
            task=row["task"],
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            parent_session_id=row["parent_session_id"],
            total_tokens=row["total_tokens"],
            tool_calls_count=row["tool_calls_count"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )

    def _row_to_message(self, row) -> Message:
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content_json"],
            tool_calls=row["tool_calls_json"],
            token_count=row["token_count"],
            created_at=row["created_at"],
        )

    def _extract_text(self, content) -> str:
        """Extract plain text from content for FTS indexing."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        c = block.get("content", "")
                        parts.append(c if isinstance(c, str) else json.dumps(c))
            return " ".join(parts)
        return str(content)

    def close(self) -> None:
        self._conn.close()
