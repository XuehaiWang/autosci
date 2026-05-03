"""Tool registry with self-registration pattern."""

import json
import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Framework-level output limits ─────────────────────────────────────────────

MAX_TOOL_OUTPUT_CHARS = 50_000
"""Hard cap on tool output returned to the LLM (per tool call)."""


@dataclass
class ToolResult:
    """Structured tool execution result.

    Attributes:
        content: The tool output string.
        is_error: True if the tool execution failed.
    """
    content: str
    is_error: bool = False


def _detect_error(output: str) -> bool:
    """Heuristic: treat output as an error if it starts with 'Error:'."""
    if not output:
        return False
    first_line = output.split("\n", 1)[0].strip()
    return first_line.startswith("Error:")


def _truncate_output(output: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate tool output, keeping head + tail with a truncation marker."""
    if len(output) <= max_chars:
        return output
    half = max_chars // 2
    omitted = len(output) - max_chars
    return (
        output[:half]
        + f"\n\n... [output truncated: {omitted:,} chars omitted] ...\n\n"
        + output[-half:]
    )


class ToolEntry:
    """Metadata and handler for a registered tool."""

    def __init__(
        self,
        name: str,
        schema: dict,
        handler: Callable,
        toolset: str = "default",
        check_fn: Optional[Callable] = None,
    ):
        self.name = name
        self.schema = schema
        self.handler = handler
        self.toolset = toolset
        self.check_fn = check_fn


class ToolRegistry:
    """Central registry for all tools.

    Tools self-register by calling registry.register() at module top level.
    The runner uses get_definitions() to build the tool list for the LLM,
    and dispatch() to execute tool calls.
    """

    def __init__(self):
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        schema: dict,
        handler: Callable,
        toolset: str = "default",
        check_fn: Optional[Callable] = None,
    ) -> None:
        """Register a tool. Called at module import time."""
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, overwriting")
        self._tools[name] = ToolEntry(name, schema, handler, toolset, check_fn)
        logger.debug(f"Registered tool: {name} (toolset={toolset})")

    def get_definitions(
        self,
        toolsets: Optional[list[str]] = None,
        names: Optional[list[str]] = None,
    ) -> list[dict]:
        """Return tool schemas for the LLM.

        Args:
            toolsets: filter by toolset names. None = all toolsets.
            names: filter by tool names. None = all tools.

        Returns:
            List of tool schemas in Anthropic format.
        """
        definitions = []
        for entry in self._tools.values():
            if toolsets and entry.toolset not in toolsets:
                continue
            if names and entry.name not in names:
                continue
            if entry.check_fn:
                try:
                    if not entry.check_fn():
                        continue
                except Exception:
                    continue
            definitions.append(entry.schema)
        return definitions

    def dispatch(self, name: str, args: dict) -> ToolResult:
        """Execute a tool by name and return a structured ToolResult.

        Error detection:
        - Exceptions during execution → is_error=True, wrapped in <tool_use_error>
        - Unknown tool name → is_error=True
        - Output starting with "Error:" → is_error=True (convention-based)

        Output truncation:
        - All outputs are capped at MAX_TOOL_OUTPUT_CHARS (head + tail preserved).
        """
        if name not in self._tools:
            return ToolResult(
                content=f"<tool_use_error>Unknown tool: {name}</tool_use_error>",
                is_error=True,
            )
        try:
            result = self._tools[name].handler(**args)
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            is_error = _detect_error(result)
            return ToolResult(
                content=_truncate_output(result),
                is_error=is_error,
            )
        except Exception as e:
            logger.exception(f"Tool '{name}' failed")
            error_msg = f"{type(e).__name__}: {e}"
            return ToolResult(
                content=f"<tool_use_error>{error_msg}</tool_use_error>",
                is_error=True,
            )

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# Singleton instance — all tool modules register against this.
registry = ToolRegistry()
