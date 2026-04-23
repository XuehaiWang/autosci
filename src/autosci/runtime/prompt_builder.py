"""Prompt builder — assembles system prompts from composable blocks."""

import os
import platform
from datetime import datetime


class PromptBuilder:
    """Assembles system prompts from agent identity, memory, skills, and environment."""

    def build_system_prompt(
        self,
        agent,
        available_agents: list[dict] = None,
        memory_block: str = None,
        skills_block: str = None,
    ) -> str:
        """Build the complete system prompt for an agent.

        Args:
            agent: the BaseAgent instance
            available_agents: subagent metadata for delegation
            memory_block: pre-formatted memory summary to inject
            skills_block: pre-formatted skills guidance to inject

        Returns:
            Complete system prompt string.
        """
        parts = []

        # Agent identity and instructions
        agent_prompt = agent.get_system_prompt(available_agents)
        parts.append(agent_prompt)

        # Memory block
        if memory_block:
            parts.append(f"## Relevant Memories\n\n{memory_block}")

        # Skills block
        if skills_block:
            parts.append(f"## Available Skills\n\n{skills_block}")

        # Environment info
        parts.append(self._build_environment_block())

        return "\n\n".join(parts)

    def _build_environment_block(self) -> str:
        return (
            f"## Environment\n\n"
            f"- Platform: {platform.system()} {platform.release()}\n"
            f"- Working directory: {os.getcwd()}\n"
            f"- Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
