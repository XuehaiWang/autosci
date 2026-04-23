"""Shared data structures for inter-module communication."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from autosci.agents.base import BaseAgent


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    usage: Optional[TokenUsage] = None
    finish_reason: str = ""


@dataclass
class RunContext:
    session_id: str
    agent: "BaseAgent"
    workspace: str
    parent_context: Optional["RunContext"] = None
    iteration_budget: int = 100
    config: dict = field(default_factory=dict)


@dataclass
class RunResult:
    session_id: str
    response: str
    status: str  # completed | interrupted | error | budget_exhausted
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    tool_calls_count: int = 0


@dataclass
class MemoryEntry:
    id: str
    content: str
    memory_type: str  # episodic | semantic | procedural
    tags: list[str] = field(default_factory=list)
    source_session: Optional[str] = None
    timestamp: str = ""
    relevance_score: Optional[float] = None
