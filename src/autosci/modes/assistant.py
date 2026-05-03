"""Assistant mode — personal AI assistant for everyday tasks."""

from autosci.agents.registry import agent_registry
from autosci.runtime.runner import AgentRunner


def run_assistant(args, config):
    """Run in assistant mode (REPL or single-shot)."""
    agent = agent_registry.get("assistant")
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