"""Skill tools — list, view, and create reusable research procedure templates."""

import threading

# Thread-local storage so each child runner (thread) has its own SkillEngine
# reference without interfering with the parent or sibling runners.
_local = threading.local()


def set_skill_engine(engine) -> None:
    """Called by the runner to inject the SkillEngine instance for this thread."""
    _local.engine = engine


def _get_engine():
    return getattr(_local, "engine", None)


# === List Skills ===


def list_skills() -> str:
    _engine = _get_engine()
    if _engine is None:
        return "Error: skill system not initialized"
    skills = _engine.list_all()
    if not skills:
        return "No skills available."
    lines = [f"Available skills ({len(skills)}):\n"]
    for s in skills:
        tags = ", ".join(s.tags) if s.tags else "none"
        lines.append(f"- **{s.name}**: {s.description}\n  Tags: {tags}")
    return "\n".join(lines)


# === View Skill ===


def view_skill(name: str) -> str:
    _engine = _get_engine()
    if _engine is None:
        return "Error: skill system not initialized"
    skill = _engine.get(name)
    if not skill:
        available = [s.name for s in _engine.list_all()]
        return f"Skill '{name}' not found. Available: {available}"
    return (
        f"# Skill: {skill.name}\n\n"
        f"**Description**: {skill.description}\n"
        f"**Tags**: {', '.join(skill.tags)}\n\n"
        f"{skill.content}"
    )


# === Create Skill ===


def create_skill(name: str, description: str, tags: list[str], content: str) -> str:
    _engine = _get_engine()
    if _engine is None:
        return "Error: skill system not initialized"
    try:
        filepath = _engine.create(
            name=name,
            description=description,
            tags=tags,
            content=content,
        )
        return f"Skill '{name}' created at {filepath}"
    except Exception as e:
        return f"Error creating skill: {e}"


