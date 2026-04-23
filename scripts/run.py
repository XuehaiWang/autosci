#!/usr/bin/env python3
"""AutoSci CLI entry point."""

import argparse
import logging
import sys

from autosci.configs.default import load_config


def main():
    parser = argparse.ArgumentParser(
        description="AutoSci — an agent for end-to-end scientific research",
    )
    parser.add_argument("task", nargs="?", help="Research task to execute")
    parser.add_argument("-m", "--model", help="Override LLM model")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="Override max iteration budget",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    config = load_config()
    if args.model:
        config["llm"]["model"] = args.model

    # Import and register tools (triggers self-registration)
    import autosci.tools.file_tools  # noqa: F401
    import autosci.tools.terminal_tool  # noqa: F401
    import autosci.tools.agent_tools  # noqa: F401
    import autosci.tools.memory_tools  # noqa: F401
    import autosci.tools.skill_tools  # noqa: F401

    # Import main agent (triggers self-registration) and discover subagents
    import autosci.agents.main_agent  # noqa: F401
    from autosci.agents.registry import agent_registry
    agent_registry.discover()

    # Get task
    task = args.task
    if not task:
        print("AutoSci Research Agent")
        print("Enter your research task (Ctrl+D to finish):\n")
        try:
            task = sys.stdin.read().strip()
        except KeyboardInterrupt:
            print("\nAborted.")
            return
        if not task:
            print("No task provided.")
            return

    # Create agent and runner
    from autosci.agents.main_agent import MainAgent
    from autosci.runtime.runner import AgentRunner

    agent = MainAgent()
    if args.max_iterations:
        agent.max_iterations = args.max_iterations

    runner = AgentRunner(config)

    # Run
    print(f"Starting AutoSci (model={config['llm']['model']})\n")
    result = runner.run(agent, task)

    # Output
    print(f"\n{'=' * 60}")
    print(f"Status: {result.status}")
    print(f"Tokens: {result.token_usage.total_tokens:,}")
    print(f"Tool calls: {result.tool_calls_count}")
    print(f"{'=' * 60}\n")
    print(result.response)


if __name__ == "__main__":
    main()
