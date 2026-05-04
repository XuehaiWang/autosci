"""Interactive REPL with TUI — multi-turn conversation interface."""

import logging
import os
import signal
import sys
import uuid

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from autosci.agents.base import BaseAgent
from autosci.protocols.schemas import TokenUsage
from autosci.runtime.runner import AgentRunner
from autosci.tools.registry import registry as tool_registry

logger = logging.getLogger(__name__)


class REPL:
    """Interactive multi-turn conversation interface with rich TUI.

    Maintains a continuous session with the agent, supporting
    follow-up questions and persistent context.
    """

    def __init__(self, runner: AgentRunner, agent: BaseAgent, mode: str = "assistant"):
        self.runner = runner
        self.agent = agent
        self.mode = mode  # "assistant" | "scientist"
        self.console = Console()
        self.session_id = uuid.uuid4().hex[:12]
        self.messages: list[dict] = []
        self.system_prompt: str = ""
        self.tool_defs: list[dict] = []
        self.total_usage = TokenUsage()
        self.total_tool_calls = 0
        self.turn_count = 0

        # Setup
        self._init_session()

    def _init_session(self) -> None:
        """Initialize the conversation session."""
        from autosci.agents.registry import agent_registry

        # Create session in storage
        self.runner.session_store.create_session(
            session_id=self.session_id,
            agent_name=self.agent.name,
            task="(interactive session)",
        )

        # Initialize memory
        self.runner.memory_manager.on_session_start(self.session_id, "(interactive session)")
        memory_block = self.runner.memory_manager.get_system_prompt_block()

        # Match skills (assistant: general tasks; scientist: research-focused)
        skill_query = "general tasks" if self.mode == "assistant" else "general research"
        skills_block = self.runner.skill_engine.get_prompt_block(skill_query)

        # Initialize context engine
        context_window = self.runner.config.get("runtime", {}).get("context_window", 200000)
        self.runner.context_engine.on_session_start(context_window)

        # Build system prompt
        available_agents = agent_registry.list_available()
        self.system_prompt = self.runner.prompt_builder.build_system_prompt(
            self.agent,
            available_agents=available_agents if available_agents else None,
            memory_block=memory_block if memory_block else None,
            skills_block=skills_block if skills_block else None,
        )

        # Get tool definitions
        self.tool_defs = self.runner._get_tool_definitions(self.agent)

    def run(self) -> None:
        """Start the REPL loop."""
        self._print_welcome()

        # Setup prompt with history
        history_path = os.path.expanduser("~/.autosci/repl_history")
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        session = PromptSession(history=FileHistory(history_path))

        try:
            while True:
                # Get user input
                try:
                    user_input = session.prompt("\n🔬 You > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ("/quit", "/exit", "/q"):
                    break
                if user_input.lower() == "/help":
                    self._print_help()
                    continue
                if user_input.lower() == "/status":
                    self._print_status()
                    continue
                if user_input.lower() == "/history":
                    self._print_history()
                    continue
                if user_input.lower() == "/clear":
                    self.messages.clear()
                    self.console.print("[dim]Context cleared.[/dim]")
                    continue

                # Process the turn
                self._process_turn(user_input)

        finally:
            self._finalize()

    def _process_turn(self, user_input: str) -> None:
        """Process a single conversation turn."""
        self.turn_count += 1

        # Add user message
        self.messages.append({"role": "user", "content": user_input})
        self.runner.session_store.append_message(self.session_id, "user", user_input)

        iteration = 0
        max_iterations = self.agent.max_iterations

        while iteration < max_iterations:
            iteration += 1

            # Call LLM
            with self.console.status("[bold blue]Thinking...", spinner="dots"):
                response = self.runner._call_with_retry(
                    self.messages, self.system_prompt, self.tool_defs,
                )

            if response is None:
                self.console.print("[red]Error: LLM request failed after retries.[/red]")
                return

            # Update usage
            if response.usage:
                self.total_usage.prompt_tokens += response.usage.prompt_tokens
                self.total_usage.completion_tokens += response.usage.completion_tokens
                self.total_usage.total_tokens += response.usage.total_tokens
                self.runner.context_engine.update_token_count(response.usage)

            # No tool calls → final response
            if not response.tool_calls:
                if response.content:
                    self.messages.append({"role": "assistant", "content": response.content})
                    self.runner.session_store.append_message(
                        self.session_id, "assistant", response.content,
                    )
                    self._print_response(response.content)
                return

            # Build assistant message with tool_use blocks
            assistant_content = []
            if response.content:
                assistant_content.append({"type": "text", "text": response.content})
                self._print_response(response.content)
            for tc in response.tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            self.messages.append({"role": "assistant", "content": assistant_content})
            self.runner.session_store.append_message(
                self.session_id, "assistant", assistant_content,
            )

            # Execute tool calls
            tool_results = []
            for tc in response.tool_calls:
                self.total_tool_calls += 1
                self._print_tool_call(tc.name, tc.arguments)

                if tc.name in self.runner._RUNNER_TOOLS:
                    from autosci.protocols.schemas import RunContext
                    context = RunContext(
                        session_id=self.session_id,
                        agent=self.agent,
                        workspace=os.getcwd(),
                        iteration_budget=self.agent.max_iterations,
                        config=self.runner.config,
                    )
                    result_str = self.runner._handle_agent_tool(tc.name, tc.arguments, context)
                else:
                    result_str = tool_registry.dispatch(tc.name, tc.arguments)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })

            self.messages.append({"role": "user", "content": tool_results})
            self.runner.session_store.append_message(self.session_id, "user", tool_results)

            # Check context compression
            if self.runner.context_engine.should_compress(self.total_usage.prompt_tokens):
                self.console.print("[dim]Compressing context...[/dim]")
                self.runner.memory_manager.on_pre_compress(self.messages)
                self.messages = self.runner.context_engine.compress(self.messages)

    def _finalize(self) -> None:
        """Clean up when REPL exits."""
        self.console.print()

        # End session
        from autosci.protocols.schemas import RunResult
        result = RunResult(
            session_id=self.session_id,
            response="(interactive session ended)",
            status="completed",
            token_usage=self.total_usage,
            tool_calls_count=self.total_tool_calls,
        )
        self.runner._finalize_session(result, self.messages, mode=self.mode)
        self._print_status()
        self.console.print("[dim]Session saved. Goodbye![/dim]")

    # === Display ===

    def _print_welcome(self) -> None:
        if self.mode == "assistant":
            title = "AutoSci Assistant"
            hint = "Ask me anything. Use /help for commands, /quit to exit."
            border = "green"
        else:
            title = "AutoSci Scientist"
            hint = "Describe your research task. Use /help for commands, /quit to exit."
            border = "blue"

        self.console.print()
        self.console.print(Panel(
            f"[bold]{title}[/bold]\n"
            f"Model: {self.runner.config['llm']['model']}  |  "
            f"Session: {self.session_id}\n\n"
            f"[dim]{hint}[/dim]",
            border_style=border,
        ))

    def _print_response(self, content: str) -> None:
        self.console.print()
        self.console.print(Panel(
            Markdown(content),
            title="[bold green]AutoSci[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

    def _print_tool_call(self, name: str, args: dict) -> None:
        # Show a compact tool call indicator
        if name == "delegate":
            label = f"delegate → {args.get('agent', '?')}: {args.get('task', '')[:60]}"
        elif name == "execute_command":
            label = f"$ {args.get('command', '')[:80]}"
        elif name in ("read_file", "write_file"):
            label = f"{name}: {args.get('path', '')}"
        elif name == "web_search":
            label = f"search: {args.get('query', '')[:60]}"
        elif name == "web_fetch":
            label = f"fetch: {args.get('url', '')[:60]}"
        else:
            label = f"{name}"

        self.console.print(f"  [dim]⚙ {label}[/dim]")

    def _print_help(self) -> None:
        self.console.print(Panel(
            "/help    — Show this help\n"
            "/status  — Show session statistics\n"
            "/history — Show conversation history summary\n"
            "/clear   — Clear conversation context\n"
            "/quit    — Exit (session is saved)",
            title="Commands",
            border_style="yellow",
        ))

    def _print_status(self) -> None:
        self.console.print(Panel(
            f"Session:    {self.session_id}\n"
            f"Turns:      {self.turn_count}\n"
            f"Messages:   {len(self.messages)}\n"
            f"Tool calls: {self.total_tool_calls}\n"
            f"Tokens:     {self.total_usage.total_tokens:,}",
            title="Session Status",
            border_style="cyan",
        ))

    def _print_history(self) -> None:
        if not self.messages:
            self.console.print("[dim]No messages yet.[/dim]")
            return
        for msg in self.messages:
            role = msg["role"]
            content = msg["content"]
            if isinstance(content, str):
                preview = content[:100].replace("\n", " ")
            elif isinstance(content, list):
                types = [b.get("type", "?") for b in content if isinstance(b, dict)]
                preview = f"[{', '.join(types)}]"
            else:
                preview = str(content)[:100]
            self.console.print(f"  [dim]{role:>10}[/dim]: {preview}")
