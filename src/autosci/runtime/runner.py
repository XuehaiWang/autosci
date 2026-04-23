"""Agent runner — the core while-loop that drives agent execution."""

import logging
import os
import time
import uuid

from autosci.context.compressor import SummarizationCompressor
from autosci.context.engine import ContextEngine
from autosci.memory.file_provider import FileMemoryProvider
from autosci.memory.manager import MemoryManager
from autosci.protocols.schemas import RunContext, RunResult, TokenUsage
from autosci.runtime.llm_client import LLMClient
from autosci.runtime.prompt_builder import PromptBuilder
from autosci.runtime.error_handler import ErrorHandler
from autosci.storage.session_store import SessionStore
from autosci.storage.exporter import SessionExporter
from autosci.tools.registry import registry as tool_registry
from autosci.agents.registry import agent_registry

logger = logging.getLogger(__name__)


class AgentRunner:
    """Core agent execution loop.

    The runner is agent-agnostic — it can run any BaseAgent subclass
    (main agent or subagent) using the same while-loop.

    Integrates session storage, context compression, and memory system.
    """

    # Tools intercepted by the runner instead of dispatched to the registry
    _RUNNER_TOOLS = {"delegate", "ask_user"}

    def __init__(self, config: dict):
        self.config = config
        self.llm_client = LLMClient(config["llm"])
        self.prompt_builder = PromptBuilder()
        self.error_handler = ErrorHandler()

        # Session storage
        storage_config = config.get("storage", {})
        self.session_store = SessionStore(
            storage_config.get("db_path", "~/.autosci/sessions.db")
        )
        self.session_exporter = SessionExporter(self.session_store)
        self.auto_export = storage_config.get("auto_export", True)
        self.export_dir = storage_config.get("export_dir", "./sessions/")

        # Context engine
        runtime_config = config.get("runtime", {})
        self.context_engine: ContextEngine = SummarizationCompressor(
            context_window=runtime_config.get("context_window", 200000),
            threshold_ratio=runtime_config.get("compression_threshold", 0.75),
            llm_client=self.llm_client,
        )

        # Memory system
        memory_config = config.get("memory", {})
        memory_provider = FileMemoryProvider(
            base_dir=memory_config.get("base_dir", "~/.autosci/memory/"),
        )
        self.memory_manager = MemoryManager(
            provider=memory_provider,
            llm_client=self.llm_client,
        )

        # Inject memory manager into memory tools
        from autosci.tools.memory_tools import set_memory_manager
        set_memory_manager(self.memory_manager)

    def run(
        self,
        agent,
        task: str,
        session_id: str = None,
        parent_context: RunContext = None,
    ) -> RunResult:
        """Run an agent on a task until completion or budget exhaustion.

        Args:
            agent: BaseAgent instance to run
            task: the user's task/query string
            session_id: optional session ID (generated if not provided)
            parent_context: optional parent context for delegated runs

        Returns:
            RunResult with response, status, and usage statistics.
        """
        session_id = session_id or uuid.uuid4().hex[:12]

        context = RunContext(
            session_id=session_id,
            agent=agent,
            workspace=os.getcwd(),
            parent_context=parent_context,
            iteration_budget=agent.max_iterations,
            config=self.config,
        )

        # Create session in storage
        parent_sid = parent_context.session_id if parent_context else None
        self.session_store.create_session(
            session_id=session_id,
            agent_name=agent.name,
            task=task,
            parent_session_id=parent_sid,
        )

        # Initialize context engine
        context_window = self.config.get("runtime", {}).get("context_window", 200000)
        self.context_engine.on_session_start(context_window)

        # Initialize memory
        self.memory_manager.on_session_start(session_id, task)
        memory_block = self.memory_manager.get_system_prompt_block()

        # Build system prompt
        available_agents = agent_registry.list_available()
        system_prompt = self.prompt_builder.build_system_prompt(
            agent,
            available_agents=available_agents if available_agents else None,
            memory_block=memory_block if memory_block else None,
        )

        # Get tool definitions
        tool_defs = self._get_tool_definitions(agent)

        # Initialize messages
        messages = [{"role": "user", "content": task}]

        # Persist the user's initial message
        self.session_store.append_message(session_id, "user", task)

        total_usage = TokenUsage()
        tool_calls_count = 0

        logger.info(f"Starting agent '{agent.name}' (session={session_id})")

        for iteration in range(1, context.iteration_budget + 1):
            self.error_handler.reset()

            # Call LLM with retry
            response = self._call_with_retry(messages, system_prompt, tool_defs)
            if response is None:
                result = RunResult(
                    session_id=session_id,
                    response="Error: failed after max retries",
                    status="error",
                    token_usage=total_usage,
                    tool_calls_count=tool_calls_count,
                )
                self._finalize_session(result, messages)
                return result

            # Update token usage
            if response.usage:
                total_usage.prompt_tokens += response.usage.prompt_tokens
                total_usage.completion_tokens += response.usage.completion_tokens
                total_usage.total_tokens += response.usage.total_tokens
                self.context_engine.update_token_count(response.usage)

            # No tool calls → final response
            if not response.tool_calls:
                logger.info(
                    f"Agent '{agent.name}' completed in {iteration} iterations "
                    f"({total_usage.total_tokens} tokens, {tool_calls_count} tool calls)"
                )
                # Persist final assistant message
                self.session_store.append_message(
                    session_id, "assistant", response.content or "",
                    token_count=response.usage.completion_tokens if response.usage else 0,
                )
                result = RunResult(
                    session_id=session_id,
                    response=response.content or "",
                    status="completed",
                    token_usage=total_usage,
                    tool_calls_count=tool_calls_count,
                )
                self._finalize_session(result, messages)
                return result

            # Build assistant message with tool_use blocks
            assistant_content = []
            if response.content:
                assistant_content.append({"type": "text", "text": response.content})
            for tc in response.tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            messages.append({"role": "assistant", "content": assistant_content})

            # Persist assistant message
            self.session_store.append_message(
                session_id, "assistant", assistant_content,
                tool_calls=[{"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                            for tc in response.tool_calls],
                token_count=response.usage.completion_tokens if response.usage else 0,
            )

            # Execute tool calls
            tool_results = []
            for tc in response.tool_calls:
                tool_calls_count += 1
                logger.info(f"  [{iteration}] Tool: {tc.name}")

                if tc.name in self._RUNNER_TOOLS:
                    result_str = self._handle_agent_tool(
                        tc.name, tc.arguments, context,
                    )
                else:
                    result_str = tool_registry.dispatch(tc.name, tc.arguments)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

            # Persist tool results
            self.session_store.append_message(session_id, "user", tool_results)

            # Check if context compression is needed
            current_tokens = total_usage.prompt_tokens
            if self.context_engine.should_compress(current_tokens):
                logger.info("Context compression triggered")
                # Let memory rescue info before compression
                self.memory_manager.on_pre_compress(messages)
                messages = self.context_engine.compress(messages)

        # Budget exhausted
        logger.warning(f"Agent '{agent.name}' exhausted iteration budget ({context.iteration_budget})")
        result = RunResult(
            session_id=session_id,
            response="Budget exhausted: reached maximum iterations.",
            status="budget_exhausted",
            token_usage=total_usage,
            tool_calls_count=tool_calls_count,
        )
        self._finalize_session(result, messages)
        return result

    def _finalize_session(self, result: RunResult, messages: list[dict] = None) -> None:
        """End the session in storage, trigger memory reflection, and export."""
        self.session_store.end_session(
            session_id=result.session_id,
            status=result.status,
            total_tokens=result.token_usage.total_tokens,
            tool_calls_count=result.tool_calls_count,
        )

        # Memory reflection (only for completed sessions)
        if messages:
            self.memory_manager.on_session_end(
                result.session_id, messages, result.status,
            )

        if self.auto_export:
            self.session_exporter.export_on_session_end(
                result.session_id,
                workspace=os.getcwd(),
            )

    def _call_with_retry(self, messages, system_prompt, tool_defs):
        """Call LLM with retry on transient errors."""
        while True:
            try:
                return self.llm_client.chat(
                    messages=messages,
                    system=system_prompt,
                    tools=tool_defs if tool_defs else None,
                )
            except Exception as e:
                classified = self.error_handler.classify(e)
                if self.error_handler.should_retry(classified):
                    backoff = self.error_handler.get_backoff_seconds()
                    logger.warning(
                        f"Retrying after {classified.reason} "
                        f"(attempt {self.error_handler._retry_count}, "
                        f"backoff {backoff:.1f}s)"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(f"Non-retryable error: {classified.reason}: {classified.message}")
                return None

    def _get_tool_definitions(self, agent) -> list[dict]:
        """Get tool definitions filtered by agent's allowed tools."""
        if agent.tools:
            # Always include agent tools (delegate, ask_user) for the main agent
            names = list(agent.tools)
            for tool_name in self._RUNNER_TOOLS:
                if tool_name not in names:
                    names.append(tool_name)
            return tool_registry.get_definitions(names=names)
        else:
            return tool_registry.get_definitions()

    def _handle_agent_tool(self, name: str, args: dict, context: RunContext) -> str:
        """Handle runner-intercepted tools (delegate, ask_user)."""
        if name == "delegate":
            return self._handle_delegate(args, context)
        elif name == "ask_user":
            return self._handle_ask_user(args)
        return f"Error: unknown agent tool: {name}"

    def _handle_delegate(self, args: dict, parent_context: RunContext) -> str:
        """Spawn a child agent run for delegation.

        Creates a new session linked to the parent, runs the subagent with
        its own iteration budget, and returns the result.
        """
        agent_name = args.get("agent", "")
        task = args.get("task", "")
        extra_context = args.get("context", "")

        if not agent_name or not task:
            return "Error: delegate requires 'agent' and 'task' arguments"

        # Look up the subagent
        try:
            agent_class = agent_registry.get(agent_name)
        except KeyError as e:
            return str(e)

        agent = agent_class()

        # Build the full task with context
        full_task = task
        if extra_context:
            full_task = f"{task}\n\n## Context\n\n{extra_context}"

        logger.info(f"Delegating to '{agent_name}': {task[:80]}")

        # Run the subagent with a child context
        child_result = self.run(
            agent=agent,
            task=full_task,
            parent_context=parent_context,
        )

        # Format the result for the parent agent
        status_note = ""
        if child_result.status != "completed":
            status_note = f"\n[Note: subagent ended with status '{child_result.status}']"

        return (
            f"[Subagent '{agent_name}' result]{status_note}\n\n"
            f"{child_result.response}"
        )

    def _handle_ask_user(self, args: dict) -> str:
        """Ask the user a question via stdin."""
        question = args.get("question", "")
        if not question:
            return "Error: ask_user requires a 'question' argument"

        print(f"\n{'=' * 60}")
        print(f"Agent asks: {question}")
        print(f"{'=' * 60}")
        try:
            answer = input("Your answer: ").strip()
            return answer if answer else "(no answer provided)"
        except (EOFError, KeyboardInterrupt):
            return "(user declined to answer)"
