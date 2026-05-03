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
    import os
    from autosci.tools.registry import registry as tool_registry

    # Discover tools from YAML descriptions + Python implementations
    descriptions_dir = os.path.join(os.path.dirname(__file__), "tools", "descriptions")
    impl_packages = [
        "autosci.tools.impl.file_tools",
        "autosci.tools.impl.shell_tools",
        "autosci.tools.impl.web_tools",
        "autosci.tools.impl.pdf_tools",
        "autosci.tools.impl.memory_tools",
        "autosci.tools.impl.skill_tools",
        "autosci.tools.impl.agent_tools",
    ]
    tool_registry.discover_tools(descriptions_dir, impl_packages)

    # Discover agents from YAML definitions
    from autosci.agents.registry import agent_registry
    agent_registry.discover_yaml()


def _init_workspace():
    """Initialize the autosci global workspace."""
    from autosci.config import create_default_config_file

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
    """Delegate to modes.assistant."""
    from autosci.modes.assistant import run_assistant
    run_assistant(args, config)


# ── Scientist mode ─────────────────────────────────────────────────────────────

def _run_scientist(args):
    """Run in scientist mode — thin CLI wrapper around run_scientist()."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from autosci.modes.scientist import run_scientist

    console = Console()

    # Resolve workspace early so we can read task files from it
    workspace = os.path.abspath(args.workspace)
    os.makedirs(workspace, exist_ok=True)

    task = _resolve_task(args, workspace)
    if not task:
        console.print("[red]Error: no task provided. Use a positional argument, "
                      "--from-file, or place task.md in the workspace.[/red]")
        sys.exit(1)

    workflow_name = getattr(args, "workflow", None)

    def on_event(event: str, data: dict):
        if event == "workspace_ready":
            from autosci.config import load_config
            cfg = load_config()
            if args.model:
                cfg["llm"]["model"] = args.model
            mode_label = f"workflow: {workflow_name}" if workflow_name else "agent-driven"
            console.print(Panel(
                f"[bold]AutoSci Scientist Mode[/bold]\n"
                f"Workspace: {data['workspace']}\n"
                f"Model: {cfg['llm']['model']}\n"
                f"Mode: {mode_label}",
                border_style="blue",
            ))
        elif event == "task_plan":
            console.print(f"[dim]Task plan ready — goal: {data.get('goal', '')[:80]}[/dim]")
        elif event == "trajectory":
            console.print(f"[dim]Trajectory report → {data['path']}[/dim]")

    try:
        result = run_scientist(
            task=task,
            workspace=workspace,
            model=getattr(args, "model", None),
            max_iterations=getattr(args, "max_iterations", None),
            workflow_name=workflow_name,
            share_memory=getattr(args, "share_memory", False),
            on_event=on_event,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    status_style = "green" if result.status in ("completed", "budget_exhausted") else "yellow"
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

    subparsers = parser.add_subparsers(dest="mode", required=False)

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

    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Force interactive REPL mode")

    # Detect whether the first non-flag argument is a known subcommand.
    # If not, extract it as the assistant task string before argparse sees it,
    # because argparse subparsers are greedy and would error on unknown choices.
    _SUBCOMMANDS = {"scientist", "workflow", "agent"}
    argv = sys.argv[1:]
    task_str_from_argv = None

    # Find the first positional (non-flag) argument
    first_positional = None
    for a in argv:
        if a.startswith("-"):
            continue
        first_positional = a
        break

    if first_positional and first_positional not in _SUBCOMMANDS:
        # Remove the task string from argv so argparse doesn't choke
        task_str_from_argv = first_positional
        argv = [a for a in argv if a != first_positional]

    args = parser.parse_args(argv)

    # Set task_str from what we extracted
    if task_str_from_argv is not None:
        args.task_str = task_str_from_argv
    elif not hasattr(args, "task_str"):
        args.task_str = None

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
    from autosci.config import load_config
    config = load_config()
    if args.model:
        config["llm"]["model"] = args.model

    _bootstrap()
    _run_assistant(args, config)


if __name__ == "__main__":
    main()
