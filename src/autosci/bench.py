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

This adapter:
  1. Changes to the workspace directory.
  2. Wraps the prompt with benchmark-specific instructions so the agent
     knows it must write report/report.md.
  3. Runs MainAgent in single-shot mode via AgentRunner.
  4. Prints structured progress to stdout (captured as _agent_output.jsonl
     by the harness).
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


# ─── CLI bootstrap (mirrors cli._bootstrap) ──────────────────────────────────

def _bootstrap():
    """Register all tools and agents (mirrors cli._bootstrap).

    Must be kept in sync with cli._bootstrap. Any tool or YAML agent
    discovery change there must be reflected here.
    """
    import autosci.tools.file_tools       # noqa: F401
    import autosci.tools.terminal_tool    # noqa: F401
    import autosci.tools.agent_tools      # noqa: F401
    import autosci.tools.memory_tools     # noqa: F401
    import autosci.tools.skill_tools      # noqa: F401
    import autosci.tools.web_tools        # noqa: F401
    import autosci.agents.main_agent      # noqa: F401
    import autosci.agents.assistant_agent # noqa: F401
    import autosci.task.agent             # noqa: F401
    from autosci.agents.registry import agent_registry
    agent_registry.discover_yaml()


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

    # ── Change to workspace directory ──────────────────────────────────────
    workspace = args.workspace or os.getcwd()
    workspace = os.path.abspath(workspace)
    if not os.path.isdir(workspace):
        _emit("error", message=f"Workspace directory not found: {workspace}")
        sys.exit(1)

    os.chdir(workspace)

    # Create .autosci/ internal dirs (mirrors _init_scientist_workspace in cli.py)
    autosci_dir = os.path.join(workspace, ".autosci")
    for sub in ["trajectory", "memory/episodic", "memory/semantic", "memory/procedural", "sessions"]:
        os.makedirs(os.path.join(autosci_dir, sub), exist_ok=True)

    # Ensure required output directories exist
    os.makedirs(os.path.join(workspace, "report", "images"), exist_ok=True)
    os.makedirs(os.path.join(workspace, "code"), exist_ok=True)
    os.makedirs(os.path.join(workspace, "outputs"), exist_ok=True)

    # ── Build task prompt ──────────────────────────────────────────────────
    task = args.message.strip() + _BENCH_ADDENDUM

    _emit("start", agent="autosci", workspace=workspace)

    # ── Load config ────────────────────────────────────────────────────────
    from autosci.configs.default import load_config
    overrides = {}
    if args.model:
        overrides = {"llm": {"model": args.model}}
    config = load_config(overrides)

    # Point storage and memory into .autosci/ (mirrors _build_scientist_config)
    config["storage"]["db_path"] = os.path.join(autosci_dir, "sessions.db")
    config["storage"]["export_dir"] = os.path.join(autosci_dir, "sessions")
    config["memory"]["base_dir"] = os.path.join(autosci_dir, "memory")

    # ── Bootstrap tools and agents ─────────────────────────────────────────
    _bootstrap()

    # ── Create agent and runner ────────────────────────────────────────────
    from autosci.agents.main_agent import MainAgent
    from autosci.runtime.runner import AgentRunner
    from autosci.trajectory.recorder import TrajectoryRecorder

    agent = MainAgent()
    if args.max_iterations:
        agent.max_iterations = args.max_iterations

    # Trajectory recorder — writes to .autosci/trajectory/
    traj_dir = os.path.join(autosci_dir, "trajectory")
    recorder = TrajectoryRecorder(traj_dir)

    runner = AgentRunner(config, trajectory_recorder=recorder)

    _emit(
        "agent_info",
        model=config["llm"]["model"],
        provider=config["llm"]["provider"],
        max_iterations=agent.max_iterations,
    )

    # ── Run ────────────────────────────────────────────────────────────────
    result = runner.run(agent, task)

    # Export trajectory report to .autosci/trajectory/
    traj_report = runner.export_trajectory(task=args.message.strip())
    if traj_report:
        _emit("trajectory", path=traj_report)

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
        # Write agent's final response as a fallback report
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Research Report\n\n")
            f.write(result.response)
        _emit("warn", message="Agent did not create report/report.md — wrote fallback")

    sys.exit(0 if result.status in ("completed", "budget_exhausted") else 1)


if __name__ == "__main__":
    main()
