"""Trajectory data structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCallRecord:
    """Record of a single tool invocation."""
    tool_name: str
    arguments: dict
    result_summary: str        # first 300 chars of result
    timestamp: str
    duration_ms: int = 0


@dataclass
class AgentSpan:
    """Complete record of one agent execution (main or subagent)."""
    span_id: str
    agent_name: str
    task: str
    started_at: str

    parent_span_id: Optional[str] = None
    ended_at: Optional[str] = None
    status: str = "running"    # running | completed | error | budget_exhausted

    system_prompt_digest: str = ""   # first 500 chars of system prompt
    output: str = ""                 # final response

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0

    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    memories_loaded: list[str] = field(default_factory=list)   # memory summaries
    memories_stored: list[str] = field(default_factory=list)   # memory summaries
    child_span_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "agent_name": self.agent_name,
            "task": self.task,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "system_prompt_digest": self.system_prompt_digest,
            "output": self.output,
            "token_usage": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens,
            },
            "tool_calls_count": self.tool_calls_count,
            "tool_calls": [
                {
                    "tool_name": tc.tool_name,
                    "arguments": tc.arguments,
                    "result_summary": tc.result_summary,
                    "timestamp": tc.timestamp,
                    "duration_ms": tc.duration_ms,
                }
                for tc in self.tool_calls
            ],
            "memories_loaded": self.memories_loaded,
            "memories_stored": self.memories_stored,
            "child_span_ids": self.child_span_ids,
        }


@dataclass
class TrajectoryEvent:
    """A single timestamped event in the execution stream."""
    event_type: str     # agent_start | agent_end | tool_call | tool_result
                        # delegation | compression | memory_store | task_plan
    timestamp: str
    span_id: str
    agent_name: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "span_id": self.span_id,
            "agent_name": self.agent_name,
            "data": self.data,
        }


def new_span_id() -> str:
    return uuid.uuid4().hex[:12]
