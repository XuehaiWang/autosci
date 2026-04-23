#!/usr/bin/env python3
"""AutoSci CLI entry point — supports both single-shot and interactive mode."""

import argparse
import logging
import sys


def main():
    parser = argparse.ArgumentParser(
        description="AutoSci — an agent for end-to-end scientific research",
    )
    parser.add_argument("task", nargs="?", help="Research task (omit for interactive mode)")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Start interactive REPL mode")
    parser.add_argument("-m", "--model", help="Override LLM model")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Override max iteration budget")
    parser.add_argument("--init-config", action="store_true",
                        help="Create default ~/.autosci/config.yaml and exit")
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Handle --init-config
    if args.init_config:
        from autosci.configs.default import create_default_config_file
        path = create_default_config_file()
        print(f"Created default config at: {path}")
        return

    # Load config
    from autosci.configs.default import load_config
    config = load_config()
    if args.model:
        config["llm"]["model"] = args.model

    # Import and register tools (triggers self-registration)
    import autosci.tools.file_tools  # noqa: F401
    import autosci.tools.terminal_tool  # noqa: F401
    import autosci.tools.agent_tools  # noqa: F401
    import autosci.tools.memory_tools  # noqa: F401
    import autosci.tools.skill_tools  # noqa: F401
    import autosci.tools.web_tools  # noqa: F401

    # Import main agent (triggers self-registration) and discover subagents
    import autosci.agents.main_agent  # noqa: F401
    from autosci.agents.registry import agent_registry
    agent_registry.discover()

    # Create agent and runner
    from autosci.agents.main_agent import MainAgent
    from autosci.runtime.runner import AgentRunner

    agent = MainAgent()
    if args.max_iterations:
        agent.max_iterations = args.max_iterations

    runner = AgentRunner(config)

    # Interactive mode: no task provided, or -i flag
    if args.interactive or not args.task:
        from autosci.runtime.repl import REPL
        repl = REPL(runner, agent)
        repl.run()
        return

    # Single-shot mode
    print(f"Starting AutoSci (model={config['llm']['model']})\n")
    result = runner.run(agent, args.task)

    print(f"\n{'=' * 60}")
    print(f"Status: {result.status}")
    print(f"Tokens: {result.token_usage.total_tokens:,}")
    print(f"Tool calls: {result.tool_calls_count}")
    print(f"{'=' * 60}\n")
    print(result.response)


if __name__ == "__main__":
    main()
