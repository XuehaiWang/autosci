"""AutoSci CLI — main entry point.

Usage:
    autosci                    # Interactive REPL (default)
    autosci "research task"    # Single-shot execution
    autosci --init             # Initialize workspace (~/.autosci/ + config)
    autosci -m gpt-4o "task"   # Override model
"""

import argparse
import logging
import sys


def _bootstrap():
    """Auto-register all built-in tools and agents."""
    import autosci.tools.file_tools  # noqa: F401
    import autosci.tools.terminal_tool  # noqa: F401
    import autosci.tools.agent_tools  # noqa: F401
    import autosci.tools.memory_tools  # noqa: F401
    import autosci.tools.skill_tools  # noqa: F401
    import autosci.tools.web_tools  # noqa: F401
    import autosci.agents.main_agent  # noqa: F401
    from autosci.agents.registry import agent_registry
    agent_registry.discover()


def _init_workspace():
    """Initialize the autosci workspace."""
    import os
    from autosci.configs.default import create_default_config_file

    home = os.path.expanduser("~/.autosci")
    created = []

    # Config
    config_path = os.path.join(home, "config.yaml")
    if not os.path.exists(config_path):
        create_default_config_file(config_path)
        created.append(config_path)

    # Directories
    for subdir in ["memory/episodic", "memory/semantic", "memory/procedural", "skills"]:
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


def main():
    parser = argparse.ArgumentParser(
        prog="autosci",
        description="AutoSci — an agent for end-to-end scientific research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  autosci                          Start interactive REPL\n"
            "  autosci \"analyze this dataset\"   Single-shot task\n"
            "  autosci --init                   Initialize workspace\n"
            "  autosci -m gpt-4o \"task\"         Use specific model\n"
        ),
    )
    parser.add_argument("task", nargs="?", help="Research task (omit for interactive mode)")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Force interactive REPL mode")
    parser.add_argument("-m", "--model", help="Override LLM model")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Override max iteration budget")
    parser.add_argument("--init", action="store_true",
                        help="Initialize autosci workspace and exit")
    args = parser.parse_args()

    # Handle --init
    if args.init:
        _init_workspace()
        return

    # Logging: quiet by default for REPL, show info for single-shot
    if args.verbose:
        log_level = logging.DEBUG
    elif args.task and not args.interactive:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    from autosci.configs.default import load_config
    config = load_config()
    if args.model:
        config["llm"]["model"] = args.model

    # Bootstrap tools and agents
    _bootstrap()

    # Create agent and runner
    from autosci.agents.main_agent import MainAgent
    from autosci.runtime.runner import AgentRunner

    agent = MainAgent()
    if args.max_iterations:
        agent.max_iterations = args.max_iterations

    runner = AgentRunner(config)

    # Interactive mode (default when no task given)
    if args.interactive or not args.task:
        from autosci.runtime.repl import REPL
        repl = REPL(runner, agent)
        repl.run()
        return

    # Single-shot mode
    from rich.console import Console
    console = Console()
    console.print(f"[dim]AutoSci (model={config['llm']['model']})[/dim]\n")

    result = runner.run(agent, args.task)

    console.print(f"\n[dim]Status: {result.status} | "
                  f"Tokens: {result.token_usage.total_tokens:,} | "
                  f"Tool calls: {result.tool_calls_count}[/dim]\n")
    from rich.markdown import Markdown
    console.print(Markdown(result.response))


if __name__ == "__main__":
    main()
