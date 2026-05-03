"""TrajectoryRecorder — writes events and spans to the trajectory directory."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

from autosci.middleware.trajectory.schemas import AgentSpan, ToolCallRecord, TrajectoryEvent, new_span_id

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TrajectoryRecorder:
    """Records agent execution trajectory to a workspace directory.

    Thread-safe: protected by a single lock so parallel subagents can share
    one recorder instance without corrupting spans or event files.

    Directory layout:
        {trajectory_dir}/
            events.jsonl   — append-only event stream
            spans.json     — all AgentSpan objects (rewritten on each update)
    """

    def __init__(self, trajectory_dir: str):
        self.trajectory_dir = trajectory_dir
        os.makedirs(trajectory_dir, exist_ok=True)

        self._events_path = os.path.join(trajectory_dir, "events.jsonl")
        self._spans_path = os.path.join(trajectory_dir, "spans.json")

        # In-memory state (all protected by _lock)
        self._lock = threading.Lock()
        self._spans: dict[str, AgentSpan] = {}          # span_id → AgentSpan
        self._span_stack: list[str] = []                 # active span stack (for timing)
        self._tool_start_times: dict[str, float] = {}   # tool call id → start time

    # ── Span lifecycle ────────────────────────────────────────────────────────

    def start_span(
        self,
        agent_name: str,
        task: str,
        system_prompt: str = "",
        memories_loaded: list[str] = None,
        parent_span_id: str = None,
    ) -> str:
        """Open a new AgentSpan and return its span_id."""
        span_id = new_span_id()
        span = AgentSpan(
            span_id=span_id,
            parent_span_id=parent_span_id,
            agent_name=agent_name,
            task=task,
            started_at=_now(),
            system_prompt_digest=system_prompt[:500],
            memories_loaded=memories_loaded or [],
        )
        with self._lock:
            self._spans[span_id] = span
            self._span_stack.append(span_id)
            if parent_span_id and parent_span_id in self._spans:
                self._spans[parent_span_id].child_span_ids.append(span_id)

        self._write_event(TrajectoryEvent(
            event_type="agent_start",
            timestamp=span.started_at,
            span_id=span_id,
            agent_name=agent_name,
            data={"task": task[:200], "parent_span_id": parent_span_id},
        ))
        self._flush_spans()
        return span_id

    def end_span(
        self,
        span_id: str,
        status: str,
        output: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        memories_stored: list[str] = None,
    ) -> None:
        """Close an AgentSpan."""
        with self._lock:
            span = self._spans.get(span_id)
            if not span:
                return
            span.ended_at = _now()
            span.status = status
            span.output = output[:1000]
            span.prompt_tokens = prompt_tokens
            span.completion_tokens = completion_tokens
            span.total_tokens = total_tokens
            span.memories_stored = memories_stored or []
            if span_id in self._span_stack:
                self._span_stack.remove(span_id)
            agent_name = span.agent_name
            tool_calls_count = span.tool_calls_count
            ended_at = span.ended_at

        self._write_event(TrajectoryEvent(
            event_type="agent_end",
            timestamp=ended_at,
            span_id=span_id,
            agent_name=agent_name,
            data={
                "status": status,
                "total_tokens": total_tokens,
                "tool_calls_count": tool_calls_count,
                "output_preview": output[:200],
            },
        ))
        self._flush_spans()

    # ── Tool call recording ───────────────────────────────────────────────────

    def record_tool_start(self, span_id: str, call_id: str, tool_name: str, arguments: dict) -> None:
        """Record the start of a tool call (for timing)."""
        with self._lock:
            self._tool_start_times[call_id] = time.time()
            agent_name = self._spans[span_id].agent_name if span_id in self._spans else ""
        self._write_event(TrajectoryEvent(
            event_type="tool_call",
            timestamp=_now(),
            span_id=span_id,
            agent_name=agent_name,
            data={"tool_name": tool_name, "call_id": call_id, "arguments": _safe_args(arguments)},
        ))

    def record_tool_end(
        self,
        span_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict,
        result: str,
    ) -> None:
        """Record the completion of a tool call."""
        with self._lock:
            start_time = self._tool_start_times.pop(call_id, None)
            duration_ms = int((time.time() - start_time) * 1000) if start_time is not None else 0
            span = self._spans.get(span_id)
            agent_name = span.agent_name if span else ""

        result_summary = result[:300] if isinstance(result, str) else str(result)[:300]
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=_safe_args(arguments),
            result_summary=result_summary,
            timestamp=_now(),
            duration_ms=duration_ms,
        )

        with self._lock:
            if span:
                span.tool_calls.append(record)
                span.tool_calls_count += 1

        self._write_event(TrajectoryEvent(
            event_type="tool_result",
            timestamp=record.timestamp,
            span_id=span_id,
            agent_name=agent_name,
            data={
                "tool_name": tool_name,
                "call_id": call_id,
                "duration_ms": duration_ms,
                "result_summary": result_summary,
            },
        ))
        self._flush_spans()

    # ── Misc events ───────────────────────────────────────────────────────────

    def record_delegation(self, parent_span_id: str, child_agent: str, task: str) -> None:
        with self._lock:
            parent = self._spans.get(parent_span_id)
            agent_name = parent.agent_name if parent else ""
        self._write_event(TrajectoryEvent(
            event_type="delegation",
            timestamp=_now(),
            span_id=parent_span_id,
            agent_name=agent_name,
            data={"child_agent": child_agent, "task": task[:200]},
        ))

    def record_compression(self, span_id: str, before_tokens: int, after_tokens: int) -> None:
        with self._lock:
            span = self._spans.get(span_id)
            agent_name = span.agent_name if span else ""
        self._write_event(TrajectoryEvent(
            event_type="compression",
            timestamp=_now(),
            span_id=span_id,
            agent_name=agent_name,
            data={"before_tokens": before_tokens, "after_tokens": after_tokens,
                  "reduction": f"{(1 - after_tokens/max(before_tokens,1)):.0%}"},
        ))

    def record_memory_store(self, span_id: str, memory_type: str, summary: str) -> None:
        with self._lock:
            span = self._spans.get(span_id)
            agent_name = span.agent_name if span else ""
        self._write_event(TrajectoryEvent(
            event_type="memory_store",
            timestamp=_now(),
            span_id=span_id,
            agent_name=agent_name,
            data={"memory_type": memory_type, "summary": summary[:120]},
        ))

    # ── Current span helper ───────────────────────────────────────────────────

    @property
    def current_span_id(self) -> Optional[str]:
        with self._lock:
            return self._span_stack[-1] if self._span_stack else None

    def get_span(self, span_id: str) -> Optional[AgentSpan]:
        with self._lock:
            return self._spans.get(span_id)

    def all_spans(self) -> list[AgentSpan]:
        with self._lock:
            return list(self._spans.values())

    # ── I/O ──────────────────────────────────────────────────────────────────

    def record_event(self, event: TrajectoryEvent) -> None:
        """Public API for recording arbitrary trajectory events."""
        self._write_event(event)

    def _write_event(self, event: TrajectoryEvent) -> None:
        try:
            with open(self._events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Trajectory event write failed: {e}")

    def _flush_spans(self) -> None:
        with self._lock:
            data = {sid: span.to_dict() for sid, span in self._spans.items()}
        try:
            with open(self._spans_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Trajectory spans flush failed: {e}")


def _safe_args(arguments: dict) -> dict:
    """Truncate large argument values to keep trajectory files manageable."""
    result = {}
    for k, v in arguments.items():
        if isinstance(v, str) and len(v) > 200:
            result[k] = v[:200] + "... [truncated]"
        else:
            result[k] = v
    return result
