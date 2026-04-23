"""File-based memory provider — stores memories as Markdown files with an index."""

import json
import logging
import math
import os
import re
import time
import uuid
from datetime import datetime
from typing import Optional

from autosci.memory.provider import MemoryEntry, MemoryProvider

logger = logging.getLogger(__name__)

# Recency half-life in seconds (7 days)
RECENCY_HALF_LIFE = 7 * 24 * 3600


class FileMemoryProvider(MemoryProvider):
    """File-system-based memory storage.

    Memories are stored as individual Markdown files organized by type.
    An index.json file provides fast lookup without reading all files.

    Retrieval uses a three-signal scoring:
      score = tag_score * 0.4 + keyword_score * 0.4 + recency_score * 0.2
    """

    def __init__(self, base_dir: str):
        self.base_dir = os.path.expanduser(base_dir)
        self._ensure_dirs()
        self._index = self._load_index()

    def _ensure_dirs(self) -> None:
        for subdir in ["episodic", "semantic", "procedural"]:
            os.makedirs(os.path.join(self.base_dir, subdir), exist_ok=True)

    # === Core operations ===

    def store(
        self,
        content: str,
        memory_type: str,
        tags: list[str] = None,
        summary: str = None,
        source_session: str = None,
    ) -> str:
        if memory_type not in ("episodic", "semantic", "procedural"):
            raise ValueError(f"Invalid memory type: {memory_type}")

        tags = tags or []
        now = datetime.now().isoformat()
        mem_id = f"mem_{uuid.uuid4().hex[:8]}"

        # For semantic/procedural: check for conflicts (high tag overlap)
        if memory_type in ("semantic", "procedural") and tags:
            existing = self._find_conflicting(memory_type, tags)
            if existing:
                logger.info(f"Updating existing memory {existing.id} (tag overlap)")
                self._update_entry(existing.id, content, tags, summary, now)
                return existing.id

        # Auto-generate summary if not provided
        if not summary:
            summary = content[:120].replace("\n", " ")

        entry = MemoryEntry(
            id=mem_id,
            type=memory_type,
            tags=tags,
            summary=summary,
            content=content,
            source_session=source_session,
            created=now,
            updated=now,
        )

        # Write file
        self._write_memory_file(entry)

        # Update index
        self._index[mem_id] = {
            "id": mem_id,
            "type": memory_type,
            "tags": tags,
            "summary": summary,
            "source_session": source_session,
            "created": now,
            "updated": now,
        }
        self._save_index()

        logger.info(f"Stored {memory_type} memory: {mem_id} ({summary[:60]})")
        return mem_id

    def retrieve(
        self,
        query: str,
        memory_type: str = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        query_keywords = self._extract_keywords(query)
        scored = []

        for mem_id, meta in self._index.items():
            if memory_type and meta["type"] != memory_type:
                continue

            tag_score = self._tag_score(query_keywords, meta.get("tags", []))
            keyword_score = self._keyword_score(query_keywords, meta.get("summary", ""))
            recency_score = self._recency_score(meta.get("updated", meta.get("created", "")))

            total = tag_score * 0.4 + keyword_score * 0.4 + recency_score * 0.2

            if total > 0.01:
                scored.append((mem_id, meta, total))

        scored.sort(key=lambda x: x[2], reverse=True)
        top = scored[:limit]

        results = []
        for mem_id, meta, score in top:
            content = self._read_memory_content(mem_id, meta["type"])
            results.append(MemoryEntry(
                id=mem_id,
                type=meta["type"],
                tags=meta.get("tags", []),
                summary=meta.get("summary", ""),
                content=content,
                source_session=meta.get("source_session"),
                created=meta.get("created", ""),
                updated=meta.get("updated", ""),
                relevance_score=score,
            ))

        return results

    def get_system_prompt_block(self, task: str = None) -> str:
        if not self._index:
            return ""

        if task:
            memories = self.retrieve(task, limit=10)
        else:
            # Get most recent memories
            all_mems = sorted(
                self._index.values(),
                key=lambda m: m.get("updated", ""),
                reverse=True,
            )[:10]
            memories = [
                MemoryEntry(
                    id=m["id"], type=m["type"], tags=m.get("tags", []),
                    summary=m.get("summary", ""), content="",
                    created=m.get("created", ""), updated=m.get("updated", ""),
                )
                for m in all_mems
            ]

        if not memories:
            return ""

        lines = []

        # Group by type
        by_type = {"episodic": [], "semantic": [], "procedural": []}
        for mem in memories:
            by_type.get(mem.type, []).append(mem)

        if by_type["episodic"] or by_type["semantic"]:
            lines.append("### Past experience & knowledge:")
            for mem in by_type["episodic"] + by_type["semantic"]:
                date = mem.created[:10] if mem.created else ""
                lines.append(f"- [{mem.type}] {mem.summary} ({date})")

        if by_type["procedural"]:
            lines.append("\n### Learned procedures:")
            for mem in by_type["procedural"]:
                lines.append(f"- {mem.summary}")

        lines.append(
            f"\n({len(memories)} memories shown. Use `recall_memory` tool for more.)"
        )

        return "\n".join(lines)

    def list_all(self, memory_type: str = None) -> list[MemoryEntry]:
        results = []
        for mem_id, meta in self._index.items():
            if memory_type and meta["type"] != memory_type:
                continue
            results.append(MemoryEntry(
                id=mem_id,
                type=meta["type"],
                tags=meta.get("tags", []),
                summary=meta.get("summary", ""),
                content="",  # Don't load content for listing
                source_session=meta.get("source_session"),
                created=meta.get("created", ""),
                updated=meta.get("updated", ""),
            ))
        return results

    def delete(self, memory_id: str) -> bool:
        if memory_id not in self._index:
            return False
        meta = self._index.pop(memory_id)
        filepath = self._memory_filepath(memory_id, meta["type"])
        if os.path.exists(filepath):
            os.remove(filepath)
        self._save_index()
        logger.info(f"Deleted memory: {memory_id}")
        return True

    def update(self, memory_id: str, content: str = None, tags: list[str] = None) -> bool:
        if memory_id not in self._index:
            return False
        now = datetime.now().isoformat()
        self._update_entry(memory_id, content, tags, None, now)
        return True

    # === Scoring functions ===

    def _tag_score(self, query_keywords: set, tags: list[str]) -> float:
        if not tags or not query_keywords:
            return 0.0
        tag_set = {t.lower() for t in tags}
        overlap = query_keywords & tag_set
        return len(overlap) / max(len(query_keywords), 1)

    def _keyword_score(self, query_keywords: set, text: str) -> float:
        if not query_keywords or not text:
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for kw in query_keywords if kw in text_lower)
        return matches / max(len(query_keywords), 1)

    def _recency_score(self, timestamp: str) -> float:
        if not timestamp:
            return 0.0
        try:
            dt = datetime.fromisoformat(timestamp)
            age_seconds = (datetime.now() - dt).total_seconds()
            return math.exp(-age_seconds * math.log(2) / RECENCY_HALF_LIFE)
        except (ValueError, TypeError):
            return 0.0

    def _extract_keywords(self, text: str) -> set:
        """Extract keywords from text for matching."""
        words = re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower())
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
            "to", "for", "of", "with", "and", "or", "not", "this", "that",
            "it", "be", "has", "have", "had", "do", "does", "did", "will",
            "can", "could", "would", "should", "i", "you", "we", "they",
            "my", "your", "our", "their", "what", "how", "when", "where",
        }
        return {w for w in words if w not in stopwords and len(w) > 1}

    # === Conflict detection ===

    def _find_conflicting(self, memory_type: str, tags: list[str]) -> Optional[MemoryEntry]:
        """Find an existing memory with > 80% tag overlap."""
        if not tags:
            return None
        tag_set = {t.lower() for t in tags}
        for mem_id, meta in self._index.items():
            if meta["type"] != memory_type:
                continue
            existing_tags = {t.lower() for t in meta.get("tags", [])}
            if not existing_tags:
                continue
            overlap = len(tag_set & existing_tags)
            union = len(tag_set | existing_tags)
            if union > 0 and overlap / union > 0.8:
                content = self._read_memory_content(mem_id, memory_type)
                return MemoryEntry(
                    id=mem_id, type=memory_type,
                    tags=meta.get("tags", []),
                    summary=meta.get("summary", ""),
                    content=content,
                    created=meta.get("created", ""),
                    updated=meta.get("updated", ""),
                )
        return None

    def _update_entry(
        self, mem_id: str, content: str = None,
        tags: list[str] = None, summary: str = None, updated: str = None,
    ) -> None:
        if mem_id not in self._index:
            return
        meta = self._index[mem_id]
        if tags is not None:
            meta["tags"] = tags
        if summary is not None:
            meta["summary"] = summary
        if updated:
            meta["updated"] = updated
        self._save_index()

        if content is not None:
            entry = MemoryEntry(
                id=mem_id, type=meta["type"], tags=meta.get("tags", []),
                summary=meta.get("summary", ""), content=content,
                source_session=meta.get("source_session"),
                created=meta.get("created", ""),
                updated=meta.get("updated", ""),
            )
            self._write_memory_file(entry)

    # === File I/O ===

    def _memory_filepath(self, mem_id: str, memory_type: str) -> str:
        return os.path.join(self.base_dir, memory_type, f"{mem_id}.md")

    def _write_memory_file(self, entry: MemoryEntry) -> None:
        filepath = self._memory_filepath(entry.id, entry.type)
        tags_str = ", ".join(entry.tags) if entry.tags else ""
        md = (
            f"---\n"
            f"id: {entry.id}\n"
            f"type: {entry.type}\n"
            f"tags: [{tags_str}]\n"
            f'summary: "{entry.summary}"\n'
        )
        if entry.source_session:
            md += f"source_session: {entry.source_session}\n"
        md += (
            f"created: \"{entry.created}\"\n"
            f"updated: \"{entry.updated}\"\n"
            f"---\n\n"
            f"{entry.content}\n"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)

    def _read_memory_content(self, mem_id: str, memory_type: str) -> str:
        filepath = self._memory_filepath(mem_id, memory_type)
        if not os.path.exists(filepath):
            return ""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            # Skip YAML frontmatter
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    return text[end + 3:].strip()
            return text
        except Exception:
            return ""

    def _load_index(self) -> dict:
        index_path = os.path.join(self.base_dir, "index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_index(self) -> None:
        index_path = os.path.join(self.base_dir, "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)
