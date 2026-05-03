"""Prompt builder — assembles system prompts from composable blocks."""

import os
import platform
from datetime import datetime


_TOOL_GUIDANCE = """\
## Tool Usage Guidelines

### General Rules
- Read a file before editing it. Never edit a file you haven't read in this session.
- Prefer `grep` for searching file contents and `glob` for finding files by name pattern.
  Use `execute_command` only for operations that have no dedicated tool (git, pip, etc.).
- Check that a file or directory exists before operating on it.
- For large outputs, tools may truncate. If you see "[output truncated]", narrow your query
  or use offset/limit parameters.

### Error Handling
- Tool results starting with "Error:" indicate a failure. Read the error message carefully
  before retrying — fix the root cause (wrong path, missing file, bad regex) rather than
  re-running the same call.
- If a tool returns `<tool_use_error>`, the call failed at the framework level (exception,
  unknown tool). Adjust your approach.

### File Operations
- `read_file`: use offset/limit for large files. Don't read entire multi-MB files.
- `write_file`: overwrites completely. For small changes, prefer `edit_file` (patch-based).
- `edit_file`: provide a unified diff patch. Context lines must match exactly.
- `glob`: use `**/*.py` for recursive patterns. Results are capped at 100 entries.
- `grep`: supports regex. Use `file_pattern` to narrow the search scope.

### Terminal
- `execute_command`: for quick, non-interactive commands (git, ls, pip install, python script.py).
  Has a timeout (default 120s). Output is auto-truncated at 50K chars.
- `terminal_start` / `terminal_write` / `terminal_read`: for interactive or long-running
  processes (training loops, servers, debuggers). Use `yield_time_ms` to wait for slow output.

### Web
- `web_search`: returns search result snippets. Follow up with `web_fetch` for full content.
- `web_fetch`: extracts readable text from a URL. Max 20K chars by default.

### Memory & Skills
- Use `store_memory` to persist important findings across sessions.
- Use `recall_memory` before starting work to check for prior relevant knowledge.
- Use `list_skills` to discover reusable research procedures.

### Delegation
- Use `delegate` to hand off focused subtasks to specialist subagents.
- Use `delegate_parallel` when subtasks are independent and can run concurrently.
- Provide clear, self-contained task descriptions — subagents don't share your context.
"""


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

        # Tool guidance
        parts.append(_TOOL_GUIDANCE)

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
