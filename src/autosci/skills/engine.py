"""Skill engine — discovers, matches, and manages reusable research procedure templates."""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A reusable research procedure template."""
    name: str
    description: str
    tags: list[str]
    content: str  # full markdown body (below frontmatter)
    required_tools: list[str] = field(default_factory=list)
    filepath: str = ""


class SkillEngine:
    """Discovers, matches, and manages skill files.

    Skills are Markdown files with YAML frontmatter containing metadata.
    The engine scans configured directories on init and provides
    tag/keyword-based matching for prompt injection.
    """

    def __init__(self, skill_dirs: list[str], include_builtin: bool = True):
        self.skill_dirs = [os.path.expanduser(d) for d in skill_dirs]
        if include_builtin:
            builtin_dir = os.path.join(os.path.dirname(__file__), "builtin")
            builtin_dir = os.path.normpath(builtin_dir)
            if os.path.isdir(builtin_dir) and builtin_dir not in self.skill_dirs:
                self.skill_dirs.append(builtin_dir)
        self.skills: dict[str, Skill] = {}
        self._discover()

    def _discover(self) -> None:
        """Scan skill directories for .md files and parse them."""
        for skill_dir in self.skill_dirs:
            if not os.path.isdir(skill_dir):
                continue
            for filename in sorted(os.listdir(skill_dir)):
                if not filename.endswith(".md"):
                    continue
                filepath = os.path.join(skill_dir, filename)
                try:
                    skill = self._parse_skill_file(filepath)
                    if skill:
                        self.skills[skill.name] = skill
                        logger.debug(f"Discovered skill: {skill.name}")
                except Exception as e:
                    logger.warning(f"Failed to parse skill {filepath}: {e}")

        if self.skills:
            logger.info(f"Discovered {len(self.skills)} skills")

    def match(self, task: str, limit: int = 3) -> list[Skill]:
        """Find skills relevant to a task description.

        Scoring: tag matches + keyword matches in description.
        """
        if not self.skills:
            return []

        task_keywords = self._extract_keywords(task)
        scored = []

        for skill in self.skills.values():
            tag_set = {t.lower() for t in skill.tags}
            desc_lower = skill.description.lower()

            # Tag overlap
            tag_hits = len(task_keywords & tag_set)
            # Keyword matches in description
            kw_hits = sum(1 for kw in task_keywords if kw in desc_lower)

            score = tag_hits + kw_hits * 0.5
            if score > 0:
                scored.append((skill, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:limit]]

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self.skills.get(name)

    def list_all(self) -> list[Skill]:
        """List all available skills."""
        return list(self.skills.values())

    def create(
        self,
        name: str,
        description: str,
        tags: list[str],
        content: str,
        skill_dir: str = None,
    ) -> str:
        """Create a new skill file. Returns the filepath."""
        if not skill_dir:
            # Use the first writable skill dir
            for d in self.skill_dirs:
                os.makedirs(d, exist_ok=True)
                skill_dir = d
                break

        if not skill_dir:
            raise ValueError("No skill directory available")

        os.makedirs(skill_dir, exist_ok=True)

        # Build filename from name
        filename = re.sub(r"[^\w]+", "_", name.lower()).strip("_") + ".md"
        filepath = os.path.join(skill_dir, filename)

        # Build file content
        tags_str = ", ".join(tags)
        md = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"tags: [{tags_str}]\n"
            f"---\n\n"
            f"{content}\n"
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)

        # Register in engine
        skill = Skill(
            name=name,
            description=description,
            tags=tags,
            content=content,
            filepath=filepath,
        )
        self.skills[name] = skill
        logger.info(f"Created skill: {name} at {filepath}")
        return filepath

    def get_prompt_block(self, task: str) -> str:
        """Build a skills summary block for system prompt injection.

        Only injects name + description, not full content.
        The agent should use view_skill to read full procedures.
        """
        matched = self.match(task)
        if not matched:
            return ""

        lines = [
            "The following skills may be relevant to your current task.",
            "Use the `view_skill` tool to read the full procedure before following it.\n",
        ]
        for skill in matched:
            lines.append(f"- **{skill.name}**: {skill.description}")

        return "\n".join(lines)

    # === Helpers ===

    def _parse_skill_file(self, filepath: str) -> Optional[Skill]:
        """Parse a skill Markdown file with YAML frontmatter."""
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        # Extract frontmatter
        if not text.startswith("---"):
            return None

        end = text.find("---", 3)
        if end == -1:
            return None

        frontmatter = text[3:end].strip()
        body = text[end + 3:].strip()

        # Simple YAML parsing (no pyyaml dependency)
        meta = {}
        for line in frontmatter.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # Parse list values: [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                items = value[1:-1].split(",")
                value = [item.strip().strip("'\"") for item in items if item.strip()]

            meta[key] = value

        name = meta.get("name", "")
        if not name:
            # Derive from filename
            name = os.path.splitext(os.path.basename(filepath))[0]

        return Skill(
            name=name,
            description=meta.get("description", ""),
            tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
            content=body,
            required_tools=meta.get("required_tools", []) if isinstance(meta.get("required_tools"), list) else [],
            filepath=filepath,
        )

    def _extract_keywords(self, text: str) -> set:
        """Extract keywords for matching."""
        words = re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower())
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
            "to", "for", "of", "with", "and", "or", "not", "this", "that",
            "it", "be", "has", "have", "had", "do", "does", "did", "will",
            "can", "could", "would", "should", "i", "you", "we", "they",
            "my", "your", "our", "their", "what", "how", "when", "where",
        }
        return {w for w in words if w not in stopwords and len(w) > 1}
