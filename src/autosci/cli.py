"""AutoSci CLI — main entry point.

Modes:
    autosci                            Interactive REPL (assistant mode)
    autosci "task"                     Single-shot assistant task
    autosci scientist "..." -w DIR     Scientist mode with workspace
    autosci scientist --from-file F -w Read task from file
    autosci --init                     Initialize ~/.autosci/ workspace
    autosci -m MODEL "task"            Override model
"""

import argparse
import logging
import os
import sys


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def _bootstrap():
    """Auto-register all built-in tools and agents."""
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


def _init_workspace():
    """Initialize the autosci global workspace."""
    from autosci.configs.default import create_default_config_file

    home = os.path.expanduser("~/.autosci")
    created = []

    config_path = os.path.join(home, "config.yaml")
    if not os.path.exists(config_path):
        create_default_config_file(config_path)
        created.append(config_path)

    for subdir in ["memory/episodic", "memory/semantic", "memory/procedural", "skills", "agents"]:
        path = os.path.join(home, subdir)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            created.append(path + "/")

    if created:
        print("Initialized autosci workspace:")
        for p in created:
            print(f"  {p}")
    else:
        print(f"Workspace already exists at {home}")

    print(f"\nEdit {home}/config.yaml to configure your LLM provider and API key.")


# ── Workspace setup ────────────────────────────────────────────────────────────

def _init_scientist_workspace(workspace: str) -> tuple[str, str]:
    """Create scientist workspace structure. Returns (workspace, autosci_dir).

    .autosci/ holds all internal files (db, trajectory, memory, sessions).
    Research directories (data/, code/, outputs/, report/) stay at the workspace root.
    """
    workspace = os.path.abspath(workspace)
    autosci_dir = os.path.join(workspace, ".autosci")

    # Internal dirs inside .autosci/
    for sub in ["trajectory", "memory/episodic", "memory/semantic", "memory/procedural", "sessions"]:
        os.makedirs(os.path.join(autosci_dir, sub), exist_ok=True)

    # User-facing research dirs at workspace root
    for sub in ["data", "code", "outputs", "report/images"]:
        os.makedirs(os.path.join(workspace, sub), exist_ok=True)

    return workspace, autosci_dir


def _build_scientist_config(base_config: dict, autosci_dir: str, share_memory: bool = False) -> dict:
    """Build config overrides for scientist mode (.autosci/ local paths)."""
    import copy
    config = copy.deepcopy(base_config)

    # Storage: .autosci/-local SQLite + sessions/
    config["storage"]["db_path"] = os.path.join(autosci_dir, "sessions.db")
    config["storage"]["export_dir"] = os.path.join(autosci_dir, "sessions")

    # Memory: .autosci/-local unless --share-memory
    if not share_memory:
        config["memory"]["base_dir"] = os.path.join(autosci_dir, "memory")

    # Scientist flags
    config["scientist"]["workspace"] = os.path.dirname(autosci_dir)  # the actual project root
    config["scientist"]["enable_trajectory"] = True
    config["scientist"]["enable_understanding"] = True

    return config


# ── Assistant mode ─────────────────────────────────────────────────────────────

def _run_assistant(args, config):
    """Run in assistant mode (REPL or single-shot)."""
    from autosci.agents.assistant_agent import AssistantAgent
    from autosci.runtime.runner import AgentRunner

    agent = AssistantAgent()
    if args.max_iterations:
        agent.max_iterations = args.max_iterations

    runner = AgentRunner(config)

    if args.interactive or not getattr(args, "task_str", None):
        from autosci.runtime.repl import REPL
        repl = REPL(runner, agent, mode="assistant")
        repl.run()
    else:
        from rich.console import Console
        from rich.markdown import Markdown
        console = Console()
        console.print(f"[dim]AutoSci assistant (model={config['llm']['model']})[/dim]\n")
        result = runner.run(agent, args.task_str)
        console.print(f"\n[dim]Status: {result.status} | "
                      f"Tokens: {result.token_usage.total_tokens:,} | "
                      f"Tool calls: {result.tool_calls_count}[/dim]\n")
        console.print(Markdown(result.response))


# ── Scientist mode ─────────────────────────────────────────────────────────────

def _run_scientist(args):
    """Run in scientist mode with workspace (agent-driven or workflow-driven)."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    console = Console()

    # Load config
    from autosci.configs.default import load_config
    base_config = load_config()
    if args.model:
        base_config["llm"]["model"] = args.model

    # Resolve workspace and .autosci/ dir
    workspace = os.path.abspath(args.workspace)
    workspace, autosci_dir = _init_scientist_workspace(workspace)

    # Resolve task string
    task = _resolve_task(args, workspace)
    if not task:
        console.print("[red]Error: no task provided. Use a positional argument, "
                      "--from-file, or place task.md in the workspace.[/red]")
        sys.exit(1)

    # Build scientist-mode config
    config = _build_scientist_config(base_config, autosci_dir, share_memory=args.share_memory)

    # Bootstrap
    _bootstrap()

    from autosci.agents.main_agent import MainAgent
    from autosci.runtime.runner import AgentRunner
    from autosci.trajectory.recorder import TrajectoryRecorder
    from autosci.task.understanding import TaskUnderstanding
    from autosci.task.schemas import save_task_plan

    # Resolve workflow (if --workflow flag given)
    workflow_def = None
    workflow_name = getattr(args, "workflow", None)
    if workflow_name:
        from autosci.workflow.engine import load_workflow, find_workflow
        wf_path = find_workflow(workflow_name)
        if not wf_path:
            console.print(f"[red]Workflow '{workflow_name}' not found. "
                          f"Run `autosci workflow list` to see available workflows.[/red]")
            sys.exit(1)
        workflow_def = load_workflow(wf_path)

    # Determine mode label
    mode_label = f"workflow: {workflow_def.name}" if workflow_def else "agent-driven"

    console.print(Panel(
        f"[bold]AutoSci Scientist Mode[/bold]\n"
        f"Workspace: {workspace}\n"
        f"Model: {config['llm']['model']}\n"
        f"Mode: {mode_label}",
        border_style="blue",
    ))

    # Trajectory recorder (inside .autosci/trajectory/)
    recorder = None
    if config["scientist"]["enable_trajectory"]:
        import datetime
        from autosci.trajectory.schemas import TrajectoryEvent
        traj_dir = os.path.join(autosci_dir, "trajectory")
        recorder = TrajectoryRecorder(traj_dir)
        if workflow_def:
            recorder.record_event(TrajectoryEvent(
                event_type="workflow_start",
                timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
                span_id="",
                agent_name="system",
                data={"workflow": workflow_def.name, "phases": [p.id for p in workflow_def.phases]},
            ))

    # Runner is created early — shared by TaskUnderstanding and main agent
    runner = AgentRunner(config, trajectory_recorder=recorder)

    # Task understanding
    task_plan = None
    if config["scientist"]["enable_understanding"]:
        console.print("[dim]Analyzing task...[/dim]")
        understanding = TaskUnderstanding(runner, workspace)
        task_plan = understanding.analyze(task)
        plan_path = save_task_plan(task_plan, autosci_dir)  # saved into .autosci/
        console.print(f"[dim]Task plan saved → {plan_path}[/dim]")
        console.print(Panel(
            f"**Goal**: {task_plan.goal}\n\n"
            + (f"**RQs**: {len(task_plan.research_questions)}\n" if task_plan.research_questions else "")
            + (f"**Claims**: {len(task_plan.claims)}\n" if task_plan.claims else "")
            + (f"**Agents**: {', '.join(task_plan.suggested_agents)}" if task_plan.suggested_agents else ""),
            title="Task Plan",
            border_style="cyan",
        ))
        if recorder:
            recorder.record_event(TrajectoryEvent(
                event_type="task_plan",
                timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
                span_id="",
                agent_name="system",
                data=task_plan.to_dict(),
            ))
    os.chdir(workspace)

    # ── Workflow-driven mode ──────────────────────────────────────────────────
    if workflow_def:
        from autosci.workflow.engine import WorkflowEngine
        engine = WorkflowEngine(runner)

        console.print(f"\n[bold]Workflow phases:[/bold] "
                      f"{' → '.join(p.id for p in workflow_def.phases)}\n")

        wf_result = engine.run(workflow_def, task, task_plan=task_plan, console=console)

        result_path = engine.save_result(wf_result, workspace)
        console.print(f"\n[dim]Workflow result → {result_path}[/dim]")

        status_style = "green" if wf_result.status == "completed" else "yellow"
        console.print(
            f"\n[{status_style}]Workflow {wf_result.status}[/{status_style}] | "
            f"Tokens: {wf_result.total_tokens:,} | "
            f"Tool calls: {wf_result.total_tool_calls}"
        )
        console.print(Markdown(wf_result.final_output))
        return

    # ── Agent-driven mode ─────────────────────────────────────────────────────
    full_task = task
    if task_plan:
        full_task = task + "\n\n" + task_plan.to_prompt_block()

    agent = MainAgent()
    if args.max_iterations:
        agent.max_iterations = args.max_iterations

    result = runner.run(agent, full_task)

    if recorder:
        report_path = runner.export_trajectory(
            task=task,
            task_plan=task_plan.to_dict() if task_plan else None,
        )
        if report_path:
            console.print(f"[dim]Trajectory report → {report_path}[/dim]")

    status_style = "green" if result.status == "completed" else "yellow"
    console.print(f"\n[{status_style}]Status: {result.status}[/{status_style}] | "
                  f"Tokens: {result.token_usage.total_tokens:,} | "
                  f"Tool calls: {result.tool_calls_count}")
    console.print(Markdown(result.response))


def _resolve_task(args, workspace: str) -> str:
    """Resolve task string from CLI args, file, or workspace task.md."""
    # Explicit positional task
    if getattr(args, "task_str", None):
        return args.task_str.strip()

    # --from-file
    if getattr(args, "from_file", None):
        path = os.path.abspath(args.from_file)
        if not os.path.exists(path):
            print(f"Error: task file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    # Workspace task.md
    task_md = os.path.join(workspace, "task.md")
    if os.path.exists(task_md):
        with open(task_md, "r", encoding="utf-8") as f:
            return f.read().strip()

    # Workspace INSTRUCTIONS.md (ResearchClawBench convention)
    instructions = os.path.join(workspace, "INSTRUCTIONS.md")
    if os.path.exists(instructions):
        with open(instructions, "r", encoding="utf-8") as f:
            return f.read().strip()

    return ""


# ── Workflow management commands ────────────────────────────────────────────────

def _run_workflow_cmd(args):
    """Handle `autosci workflow` subcommands."""
    from pathlib import Path

    templates_dir = Path(__file__).parent / "workflow" / "templates"
    user_workflows_dir = Path("~/.autosci/workflows").expanduser()

    if args.workflow_cmd == "list":
        print("Built-in workflow templates:")
        for f in sorted(templates_dir.glob("*.yaml")):
            print(f"  {f.stem}")
        user_yamls = list(user_workflows_dir.glob("*.yaml")) if user_workflows_dir.is_dir() else []
        if user_yamls:
            print("\nUser-defined workflows (~/.autosci/workflows/):")
            for f in sorted(user_yamls):
                print(f"  {f.stem}")

    elif args.workflow_cmd == "show":
        from autosci.workflow.engine import find_workflow, load_workflow
        name = args.workflow_name
        path = find_workflow(name)
        if not path:
            print(f"Workflow '{name}' not found.")
            sys.exit(1)
        wf = load_workflow(path)
        print(f"# {path}\n")
        print(f"name: {wf.name}")
        print(f"description: {wf.description}")
        print(f"phases ({len(wf.phases)}):")
        for p in wf.phases:
            deps = f"  depends_on: {p.depends_on}" if p.depends_on else ""
            print(f"  - {p.id} (agent: {p.agent}){deps}")

    elif args.workflow_cmd == "add":
        name = args.workflow_name
        src = templates_dir / f"{name}.yaml"
        if not src.exists():
            available = [f.stem for f in templates_dir.glob("*.yaml")]
            print(f"Unknown built-in workflow '{name}'.")
            print(f"Available templates: {', '.join(available)}")
            sys.exit(1)
        user_workflows_dir.mkdir(parents=True, exist_ok=True)
        dst = user_workflows_dir / f"{name}.yaml"
        if dst.exists() and not args.force:
            print(f"Workflow '{name}' already exists at {dst}")
            print("Use --force to overwrite.")
            sys.exit(1)
        import shutil
        shutil.copy(src, dst)
        print(f"Added workflow '{name}' → {dst}")
        print(f"Edit {dst} to customize.")


# ── Agent management commands ──────────────────────────────────────────────────

def _run_agent_cmd(args):
    """Handle `autosci agent` subcommands."""
    from pathlib import Path

    templates_dir = Path(__file__).parent / "agents" / "templates"
    user_agents_dir = Path("~/.autosci/agents").expanduser()

    if args.agent_cmd == "list":
        _bootstrap()
        from autosci.agents.registry import agent_registry
        agents = agent_registry.list_available()
        if not agents:
            print("No agents registered.")
            return
        print(f"{'Name':<20} {'Role'}")
        print("-" * 60)
        for a in agents:
            print(f"{a['name']:<20} {a['role']}")

    elif args.agent_cmd == "add":
        agent_name = args.agent_name
        src = templates_dir / f"{agent_name}.yaml"
        if not src.exists():
            available = [f.stem for f in templates_dir.glob("*.yaml")]
            print(f"Unknown built-in agent '{agent_name}'.")
            print(f"Available templates: {', '.join(available)}")
            sys.exit(1)
        user_agents_dir.mkdir(parents=True, exist_ok=True)
        dst = user_agents_dir / f"{agent_name}.yaml"
        if dst.exists() and not args.force:
            print(f"Agent '{agent_name}' already exists at {dst}")
            print("Use --force to overwrite.")
            sys.exit(1)
        import shutil
        shutil.copy(src, dst)
        print(f"Added agent '{agent_name}' → {dst}")
        print(f"Edit {dst} to customize, then run `autosci agent list` to verify.")

    elif args.agent_cmd == "show":
        agent_name = args.agent_name
        # Check user agents first, then built-in templates
        for search_dir in [user_agents_dir, templates_dir]:
            candidate = search_dir / f"{agent_name}.yaml"
            if candidate.exists():
                print(f"# {candidate}\n")
                print(candidate.read_text())
                return
        print(f"Agent '{agent_name}' not found.")
        sys.exit(1)

    elif args.agent_cmd == "templates":
        print("Built-in agent templates:")
        for f in sorted(templates_dir.glob("*.yaml")):
            print(f"  {f.stem}")
        print(f"\nInstall with: autosci agent add <name>")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="autosci",
        description="AutoSci — AI scientist platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  autosci                            Start interactive REPL (assistant)\n"
            "  autosci \"explain this paper\"       Single-shot assistant task\n"
            "  autosci scientist \"reproduce X\" -w ./exp  Scientist mode with workspace\n"
            "  autosci scientist --from-file t.md -w ./exp\n"
            "  autosci --init                     Initialize ~/.autosci/ workspace\n"
        ),
    )

    parser.add_argument("-m", "--model", help="Override LLM model")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--init", action="store_true", help="Initialize autosci workspace and exit")
    parser.add_argument("--max-iterations", type=int, default=None)

    subparsers = parser.add_subparsers(dest="mode")

    # ── scientist subcommand ──
    scientist_parser = subparsers.add_parser(
        "scientist",
        help="Run a scientific research task with workspace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scientist_parser.add_argument("task_str", nargs="?", default=None, help="Task description")
    scientist_parser.add_argument("-w", "--workspace", required=True, help="Workspace directory")
    scientist_parser.add_argument("--from-file", dest="from_file", default=None,
                                  help="Read task from a file")
    scientist_parser.add_argument("--share-memory", action="store_true",
                                  help="Share memory with global ~/.autosci/memory/")
    scientist_parser.add_argument("--workflow", default=None,
                                  help="Use workflow-driven mode (e.g. reproduce, survey)")
    scientist_parser.add_argument("-m", "--model", help="Override LLM model")
    scientist_parser.add_argument("--max-iterations", type=int, default=None)

    # ── workflow subcommand ──
    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Manage workflow definitions",
    )
    workflow_sub = workflow_parser.add_subparsers(dest="workflow_cmd")

    workflow_sub.add_parser("list", help="List available workflows")

    wf_show = workflow_sub.add_parser("show", help="Show a workflow's phases")
    wf_show.add_argument("workflow_name", help="Workflow name (e.g. reproduce, survey)")

    wf_add = workflow_sub.add_parser("add", help="Install a built-in workflow template")
    wf_add.add_argument("workflow_name", help="Template name")
    wf_add.add_argument("--force", action="store_true", help="Overwrite existing")

    # ── agent subcommand ──
    agent_parser = subparsers.add_parser(
        "agent",
        help="Manage YAML-defined agents",
    )
    agent_sub = agent_parser.add_subparsers(dest="agent_cmd")

    agent_sub.add_parser("list", help="List all registered agents")
    agent_sub.add_parser("templates", help="List built-in agent templates")

    add_parser = agent_sub.add_parser("add", help="Install a built-in agent template")
    add_parser.add_argument("agent_name", help="Template name (e.g. researcher, coder)")
    add_parser.add_argument("--force", action="store_true", help="Overwrite existing")

    show_parser = agent_sub.add_parser("show", help="Show an agent's YAML definition")
    show_parser.add_argument("agent_name", help="Agent name")

    # ── assistant positional (default) ──
    parser.add_argument("task_str", nargs="?", default=None,
                        help="Assistant task (omit for interactive REPL)")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Force interactive REPL mode")

    args = parser.parse_args()

    # --init
    if args.init:
        _init_workspace()
        return

    # Logging
    log_level = logging.DEBUG if args.verbose else (
        logging.INFO if (getattr(args, "task_str", None) and args.mode != "task") else logging.WARNING
    )
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Scientist mode
    if args.mode == "scientist":
        _run_scientist(args)
        return

    # Workflow management mode
    if args.mode == "workflow":
        _run_workflow_cmd(args)
        return

    # Agent management mode
    if args.mode == "agent":
        _run_agent_cmd(args)
        return

    # Assistant mode
    from autosci.configs.default import load_config
    config = load_config()
    if args.model:
        config["llm"]["model"] = args.model

    _bootstrap()
    _run_assistant(args, config)


if __name__ == "__main__":
    main()
