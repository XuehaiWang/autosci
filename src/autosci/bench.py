"""AutoSci ResearchClawBench adapter.

Entry point for running autosci as an agent inside the ResearchClawBench
evaluation harness.

Usage (as invoked by the benchmark runner):
    autosci-bench -m <PROMPT> -w <WORKSPACE>

The runner copies task data into <WORKSPACE>, writes the task prompt to
<WORKSPACE>/INSTRUCTIONS.md, then launches this command with:
  - cwd set to <WORKSPACE>
  - <PROMPT> expanded to the instructions string (via shell $(cat ...))
  - <WORKSPACE> as the absolute workspace path

This adapter delegates entirely to ``run_scientist()`` — the same function
used by ``autosci scientist`` — so bench and CLI share identical logic.
"""

import argparse
import json
import logging
import os
import sys
import time


# ─── Benchmark-specific system addendum ──────────────────────────────────────

_BENCH_ADDENDUM = """\

## ResearchClawBench Instructions

You are running inside the ResearchClawBench evaluation harness.

Workspace layout (relative to your current directory):
- `data/`         — input datasets and files for this task
- `related_work/` — reference papers and background materials
- `code/`         — place generated code here
- `outputs/`      — place intermediate result files here
- `report/`       — **final deliverable directory**
  - `report/report.md`   — required final report (Markdown)
  - `report/images/`     — figures referenced in the report

Your goal:
1. Read and understand the task from this prompt and any files in `data/`.
2. Examine related work in `related_work/` as needed.
3. Conduct the research: write code in `code/`, save outputs in `outputs/`.
4. Write a comprehensive final report to `report/report.md`.
   - The report must directly address every aspect of the task.
   - Include quantitative results, figures (saved to `report/images/`),
     and conclusions.
   - Reference figures as `![caption](images/filename.png)` (relative path).
5. Do NOT ask for user confirmation — proceed autonomously.
"""


# ─── Stdout emitter (captured as _agent_output.jsonl by the harness) ─────────

def _emit(event: str, **kwargs):
    """Print a JSON log line to stdout for the harness to capture."""
    record = {"event": event, "ts": time.time(), **kwargs}
    print(json.dumps(record, ensure_ascii=False), flush=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="autosci-bench",
        description="AutoSci adapter for the ResearchClawBench evaluation harness",
    )
    parser.add_argument(
        "-m", "--message",
        required=True,
        help="Task prompt (contents of INSTRUCTIONS.md, passed by the harness)",
    )
    parser.add_argument(
        "-w", "--workspace",
        default=None,
        help="Absolute path to the task workspace (optional; defaults to cwd)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM model",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Override max iteration budget (default: agent default)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # ── Logging ────────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,  # keep stderr separate from the captured stdout
    )

    # ── Validate workspace ─────────────────────────────────────────────────
    workspace = os.path.abspath(args.workspace or os.getcwd())
    if not os.path.isdir(workspace):
        _emit("error", message=f"Workspace directory not found: {workspace}")
        sys.exit(1)

    # ── Build task prompt ──────────────────────────────────────────────────
    task = args.message.strip() + _BENCH_ADDENDUM

    _emit("start", agent="autosci", workspace=workspace)

    # ── on_event callback: forward progress to stdout as JSONL ────────────
    def on_event(event: str, data: dict):
        if event == "task_plan":
            _emit("task_understanding", status="done",
                  goal=data.get("goal", ""),
                  claims=data.get("claims", 0),
                  rqs=data.get("rqs", 0))
        elif event == "agent_start":
            _emit("agent_info",
                  model=data.get("model", ""),
                  max_iterations=data.get("max_iterations"))
        elif event == "agent_done":
            pass  # emitted after run_scientist returns
        elif event == "trajectory":
            _emit("trajectory", path=data.get("path", ""))

    # ── Delegate to run_scientist() ────────────────────────────────────────
    from autosci.scientist import run_scientist

    result = run_scientist(
        task=task,
        workspace=workspace,
        model=args.model,
        max_iterations=args.max_iterations,
        on_event=on_event,
    )

    # ── Emit final stats ───────────────────────────────────────────────────
    if result.token_usage:
        _emit(
            "usage",
            prompt_tokens=result.token_usage.prompt_tokens,
            completion_tokens=result.token_usage.completion_tokens,
            total_tokens=result.token_usage.total_tokens,
            tool_calls=result.tool_calls_count,
        )

    _emit("done", status=result.status)

    # ── Ensure report exists ───────────────────────────────────────────────
    report_path = os.path.join(workspace, "report", "report.md")
    if not os.path.exists(report_path):
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Research Report\n\n")
            f.write(result.response)
        _emit("warn", message="Agent did not create report/report.md — wrote fallback")

    sys.exit(0 if result.status in ("completed", "budget_exhausted") else 1)


if __name__ == "__main__":
    main()
