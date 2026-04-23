"""Agent runner — the core while-loop that drives agent execution."""

import logging
import os
import time
import uuid

from autosci.protocols.schemas import RunContext, RunResult, TokenUsage
from autosci.runtime.llm_client import LLMClient
from autosci.runtime.prompt_builder import PromptBuilder
from autosci.runtime.error_handler import ErrorHandler
from autosci.tools.registry import registry as tool_registry
from autosci.agents.registry import agent_registry

logger = logging.getLogger(__name__)


class AgentRunner:
    """Core agent execution loop.

    The runner is agent-agnostic — it can run any BaseAgent subclass
    (main agent or subagent) using the same while-loop.
    """

    def __init__(self, config: dict):
        self.config = config
        self.llm_client = LLMClient(config["llm"])
        self.prompt_builder = PromptBuilder()
        self.error_handler = ErrorHandler()

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

        # Build system prompt
        available_agents = agent_registry.list_available()
        system_prompt = self.prompt_builder.build_system_prompt(
            agent,
            available_agents=available_agents if available_agents else None,
        )

        # Get tool definitions
        tool_defs = self._get_tool_definitions(agent)

        # Initialize messages
        messages = [{"role": "user", "content": task}]

        total_usage = TokenUsage()
        tool_calls_count = 0

        logger.info(f"Starting agent '{agent.name}' (session={session_id})")

        for iteration in range(1, context.iteration_budget + 1):
            self.error_handler.reset()

            # Call LLM with retry
            response = self._call_with_retry(messages, system_prompt, tool_defs)
            if response is None:
                return RunResult(
                    session_id=session_id,
                    response="Error: failed after max retries",
                    status="error",
                    token_usage=total_usage,
                    tool_calls_count=tool_calls_count,
                )

            # Update token usage
            if response.usage:
                total_usage.prompt_tokens += response.usage.prompt_tokens
                total_usage.completion_tokens += response.usage.completion_tokens
                total_usage.total_tokens += response.usage.total_tokens

            # No tool calls → final response
            if not response.tool_calls:
                logger.info(
                    f"Agent '{agent.name}' completed in {iteration} iterations "
                    f"({total_usage.total_tokens} tokens, {tool_calls_count} tool calls)"
                )
                return RunResult(
                    session_id=session_id,
                    response=response.content or "",
                    status="completed",
                    token_usage=total_usage,
                    tool_calls_count=tool_calls_count,
                )

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

            # Execute tool calls
            tool_results = []
            for tc in response.tool_calls:
                tool_calls_count += 1
                logger.info(f"  [{iteration}] Tool: {tc.name}")
                result = tool_registry.dispatch(tc.name, tc.arguments)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        # Budget exhausted
        logger.warning(f"Agent '{agent.name}' exhausted iteration budget ({context.iteration_budget})")
        return RunResult(
            session_id=session_id,
            response="Budget exhausted: reached maximum iterations.",
            status="budget_exhausted",
            token_usage=total_usage,
            tool_calls_count=tool_calls_count,
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
            # Agent specifies which tools it can use
            return tool_registry.get_definitions(names=agent.tools)
        else:
            # Empty tools list = access to all tools
            return tool_registry.get_definitions()
