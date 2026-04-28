"""TrajectoryExporter — generates human-readable Markdown report from spans."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from autosci.trajectory.schemas import AgentSpan, ToolCallRecord

logger = logging.getLogger(__name__)


class TrajectoryExporter:
    """Generates trajectory/report.md from recorded spans and events."""

    def __init__(self, trajectory_dir: str):
        self.trajectory_dir = trajectory_dir

    def export(
        self,
        task: str = "",
        task_plan: dict = None,
    ) -> str:
        """Generate and write report.md. Returns the output path."""
        spans_path = os.path.join(self.trajectory_dir, "spans.json")
        if not os.path.exists(spans_path):
            logger.warning("No spans.json found, skipping trajectory export")
            return ""

        with open(spans_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Reconstruct spans
        spans: dict[str, dict] = raw

        # Find root spans (no parent)
        roots = [s for s in spans.values() if not s.get("parent_span_id")]

        lines = self._build_report(task, task_plan, spans, roots)
        report = "\n".join(lines)

        out_path = os.path.join(self.trajectory_dir, "report.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)

        return out_path

    def _build_report(
        self,
        task: str,
        task_plan: Optional[dict],
        spans: dict[str, dict],
        roots: list[dict],
    ) -> list[str]:
        lines = ["# Trajectory Report", ""]

        # Header
        if task:
            lines += [f"**Task**: {task}", ""]

        # Timing summary from root spans
        for root in roots:
            started = root.get("started_at", "")
            ended = root.get("ended_at", "")
            status = root.get("status", "")
            total_tokens = root.get("token_usage", {}).get("total", 0)
            lines += [
                f"**Started**: {started}  |  **Ended**: {ended}  "
                f"|  **Status**: {status}  |  **Total tokens**: {total_tokens:,}",
                "",
            ]

        lines += ["---", ""]

        # Task plan section
        if task_plan:
            lines += ["## Task Plan", ""]
            if task_plan.get("goal"):
                lines += [f"**Goal**: {task_plan['goal']}", ""]
            claims = task_plan.get("claims", [])
            if claims:
                lines += ["**Claims**:"]
                for c in claims:
                    if isinstance(c, dict):
                        lines.append(
                            f"- [{c.get('id', '?')}] {c.get('statement', '')} "
                            f"— *{c.get('status', 'unverified')}*"
                        )
                    else:
                        lines.append(f"- {c}")
                lines.append("")
            rqs = task_plan.get("research_questions", [])
            if rqs:
                lines += ["**Research Questions**:"]
                for rq in rqs:
                    if isinstance(rq, dict):
                        lines.append(f"- [{rq.get('id', '?')}] {rq.get('question', '')}")
                    else:
                        lines.append(f"- {rq}")
                lines.append("")
            lines += ["---", ""]

        # Execution tree
        lines += ["## Execution Tree", ""]
        for root in roots:
            self._render_span_tree(root, spans, lines, indent=0)

        lines += ["", "---", ""]

        # Memory summary (aggregate across all spans)
        all_loaded = []
        all_stored = []
        for s in spans.values():
            all_loaded.extend(s.get("memories_loaded", []))
            all_stored.extend(s.get("memories_stored", []))

        if all_loaded or all_stored:
            lines += ["## Memory Activity", ""]
            if all_loaded:
                lines.append(f"**Loaded** ({len(all_loaded)}):")
                for m in all_loaded:
                    lines.append(f"  - {m}")
            if all_stored:
                lines.append(f"**Stored** ({len(all_stored)}):")
                for m in all_stored:
                    lines.append(f"  - {m}")
            lines.append("")

        return lines

    def _render_span_tree(
        self,
        span: dict,
        all_spans: dict[str, dict],
        lines: list[str],
        indent: int,
    ) -> None:
        prefix = "    " * indent
        agent = span.get("agent_name", "?")
        status = span.get("status", "")
        usage = span.get("token_usage", {})
        total_tok = usage.get("total", 0)
        tc_count = span.get("tool_calls_count", 0)
        started = span.get("started_at", "")
        ended = span.get("ended_at", "")
        duration = _duration_str(started, ended)
        task_preview = span.get("task", "")[:120]

        # Span header
        lines.append(
            f"{prefix}### {'└── ' if indent > 0 else ''}**{agent}** "
            f"({duration}, {total_tok:,} tokens, {tc_count} tool calls, {status})"
        )
        lines.append(f"{prefix}*Task*: {task_preview}")
        lines.append("")

        # System prompt digest
        digest = span.get("system_prompt_digest", "")
        if digest:
            lines.append(f"{prefix}<details><summary>System prompt (first 500 chars)</summary>")
            lines.append("")
            lines.append(f"{prefix}```")
            lines.append(digest)
            lines.append(f"{prefix}```")
            lines.append(f"{prefix}</details>")
            lines.append("")

        # Tool calls
        tool_calls = span.get("tool_calls", [])
        if tool_calls:
            lines.append(f"{prefix}**Tool calls**:")
            for tc in tool_calls:
                name = tc.get("tool_name", "?")
                args = tc.get("arguments", {})
                result = tc.get("result_summary", "")
                dur = tc.get("duration_ms", 0)
                arg_str = _format_args(name, args)
                lines.append(f"{prefix}  - `{name}`{arg_str} → {result[:100]!r}  _{dur}ms_")
            lines.append("")

        # Output
        output = span.get("output", "")
        if output:
            lines.append(f"{prefix}**Output**: {output[:300]}")
            if len(output) > 300:
                lines.append(f"{prefix}... _(truncated, {len(output)} chars total)_")
            lines.append("")

        # Recurse into children
        for child_id in span.get("child_span_ids", []):
            if child_id in all_spans:
                self._render_span_tree(all_spans[child_id], all_spans, lines, indent + 1)


def _duration_str(started: str, ended: str) -> str:
    if not started or not ended:
        return "?"
    try:
        from datetime import datetime
        s = datetime.fromisoformat(started)
        e = datetime.fromisoformat(ended)
        secs = int((e - s).total_seconds())
        if secs < 60:
            return f"{secs}s"
        return f"{secs // 60}m {secs % 60}s"
    except Exception:
        return "?"


def _format_args(tool_name: str, args: dict) -> str:
    """Format tool arguments as a compact string."""
    if tool_name in ("read_file", "write_file"):
        return f"({args.get('path', '')})"
    if tool_name == "execute_command":
        cmd = args.get("command", "")
        return f"($ {cmd[:60]})"
    if tool_name in ("web_search",):
        return f"({args.get('query', '')[:60]})"
    if tool_name in ("web_fetch",):
        return f"({args.get('url', '')[:60]})"
    if tool_name == "delegate":
        return f"(→ {args.get('agent', '')})"
    return ""
