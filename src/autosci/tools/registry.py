"""Tool registry with self-registration pattern."""

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


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

    def dispatch(self, name: str, args: dict) -> str:
        """Execute a tool by name and return the result as a string."""
        if name not in self._tools:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = self._tools[name].handler(**args)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.exception(f"Tool '{name}' failed")
            return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# Singleton instance — all tool modules register against this.
registry = ToolRegistry()
