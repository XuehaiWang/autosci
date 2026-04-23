"""Skill tools — list, view, and create reusable research procedure templates."""

from autosci.tools.registry import registry

# The SkillEngine instance is set by the runner at startup.
_engine = None


def set_skill_engine(engine) -> None:
    """Called by the runner to inject the SkillEngine instance."""
    global _engine
    _engine = engine


# === List Skills ===

LIST_SKILLS_SCHEMA = {
    "name": "list_skills",
    "description": (
        "List all available research skills (reusable procedure templates). "
        "Shows name and description for each skill. Use view_skill to see "
        "the full procedure."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def list_skills() -> str:
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


registry.register("list_skills", LIST_SKILLS_SCHEMA, list_skills, toolset="skill")


# === View Skill ===

VIEW_SKILL_SCHEMA = {
    "name": "view_skill",
    "description": (
        "View the full content of a research skill (procedure template). "
        "Use list_skills first to see available skills."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the skill to view",
            },
        },
        "required": ["name"],
    },
}


def view_skill(name: str) -> str:
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


registry.register("view_skill", VIEW_SKILL_SCHEMA, view_skill, toolset="skill")


# === Create Skill ===

CREATE_SKILL_SCHEMA = {
    "name": "create_skill",
    "description": (
        "Create a new reusable research skill from an effective procedure "
        "you've learned during this session. Skills persist across sessions "
        "and are suggested when relevant tasks come up."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short identifier for the skill (e.g., 'ablation_study')",
            },
            "description": {
                "type": "string",
                "description": "One-line description of what the skill does",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords for matching (e.g., ['experiment', 'ablation', 'comparison'])",
            },
            "content": {
                "type": "string",
                "description": "Full procedure in Markdown format (steps, tips, checklists)",
            },
        },
        "required": ["name", "description", "tags", "content"],
    },
}


def create_skill(name: str, description: str, tags: list[str], content: str) -> str:
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


registry.register("create_skill", CREATE_SKILL_SCHEMA, create_skill, toolset="skill")
