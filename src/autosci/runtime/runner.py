"""Agent runner — the core while-loop that drives agent execution."""

import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from autosci.middleware.context.compressor import SummarizationCompressor, _estimate_message_tokens
from autosci.middleware.context.engine import ContextEngine
from autosci.middleware.memory.file_provider import FileMemoryProvider
from autosci.middleware.memory.manager import MemoryManager
from autosci.protocols.schemas import RunContext, RunResult, TokenUsage
from autosci.runtime.llm_client import LLMClient
from autosci.runtime.prompt_builder import PromptBuilder
from autosci.runtime.error_handler import ErrorHandler
from autosci.skills.engine import SkillEngine
from autosci.middleware.storage.session_store import SessionStore
from autosci.middleware.storage.exporter import SessionExporter
from autosci.tools.registry import registry as tool_registry
from autosci.agents.registry import agent_registry
from autosci.middleware.trajectory.recorder import TrajectoryRecorder
from autosci.middleware.trajectory.exporter import TrajectoryExporter

logger = logging.getLogger(__name__)


class AgentRunner:
    """Core agent execution loop.

    The runner is agent-agnostic — it can run any BaseAgent subclass
    (main agent or subagent) using the same while-loop.

    Integrates session storage, context compression, memory system,
    and optional trajectory recording.

    Child runners created via _make_child_runner() share the parent's
    llm_client, memory_manager, skill_engine, session_store, and trajectory
    recorder, but each get their own context_engine so context state is
    fully isolated. This allows parallel subagent execution via
    ThreadPoolExecutor without shared mutable state conflicts.
    """

    # Tools intercepted by the runner instead of dispatched to the registry
    _RUNNER_TOOLS = {"delegate", "delegate_parallel", "ask_user", "create_agent", "update_claim"}

    # Maximum number of subagents that can run in parallel
    MAX_PARALLEL_SUBAGENTS = 8

    def __init__(self, config: dict, trajectory_recorder: Optional[TrajectoryRecorder] = None):
        self.config = config
        self.llm_client = LLMClient(config["llm"])
        self.prompt_builder = PromptBuilder()
        self.error_handler = ErrorHandler()

        # Trajectory (optional — None in assistant mode)
        self.trajectory = trajectory_recorder

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
            trajectory=self.trajectory,
        )

        # Inject memory manager into memory tools
        from autosci.tools.impl.memory_tools import set_memory_manager
        set_memory_manager(self.memory_manager)

        # Inject tools config (for MINERU_TOKEN resolution etc.)
        from autosci.tools.impl.pdf_tools import set_tools_config
        set_tools_config(config.get("tools", {}))

        # Skill engine
        skills_config = config.get("skills", {})
        self.skill_engine = SkillEngine(
            skill_dirs=skills_config.get("dirs", ["~/.autosci/skills/", "./skills/"]),
            include_builtin=skills_config.get("include_builtin", True),
        )

        # Inject skill engine into skill tools
        from autosci.tools.impl.skill_tools import set_skill_engine
        set_skill_engine(self.skill_engine)

    def _make_child_runner(self) -> "AgentRunner":
        """Create a lightweight child runner for subagent execution.

        The child shares the parent's heavy resources (llm_client, memory_manager,
        skill_engine, session_store, trajectory) to avoid redundant initialisation
        and to keep all subagents writing to the same session DB and trajectory.

        Each child gets its own context_engine so context-window state is fully
        isolated — this is the only mutable per-run resource that must not be shared.

        The child does NOT call set_memory_manager / set_skill_engine globally;
        instead it sets them on the current thread via threading.local so parallel
        children never overwrite each other's references.
        """
        child = object.__new__(AgentRunner)
        child.config = self.config
        child.llm_client = self.llm_client          # shared, stateless per-call
        child.prompt_builder = PromptBuilder()
        child.error_handler = ErrorHandler()
        child.trajectory = self.trajectory           # shared, thread-safe writes
        child.session_store = self.session_store     # shared, SQLite WAL is concurrent-safe
        child.session_exporter = self.session_exporter
        child.auto_export = self.auto_export
        child.export_dir = self.export_dir
        child.memory_manager = self.memory_manager  # shared, file-based provider is safe
        child.skill_engine = self.skill_engine       # shared, read-only after init

        # Each child gets its own context engine (mutable per-session state)
        runtime_config = self.config.get("runtime", {})
        child.context_engine = SummarizationCompressor(
            context_window=runtime_config.get("context_window", 200000),
            threshold_ratio=runtime_config.get("compression_threshold", 0.75),
            llm_client=self.llm_client,
        )
        return child

    def _inject_thread_locals(self) -> None:
        """Inject memory_manager and skill_engine into thread-local storage.

        Must be called at the start of any thread that will execute tool calls,
        so that memory_tools and skill_tools resolve the correct instances for
        this thread rather than a stale reference from another thread.
        """
        from autosci.tools.impl.memory_tools import set_memory_manager
        from autosci.tools.impl.skill_tools import set_skill_engine
        from autosci.tools.impl.pdf_tools import set_tools_config
        set_memory_manager(self.memory_manager)
        set_skill_engine(self.skill_engine)
        set_tools_config(self.config.get("tools", {}))

    def run(
        self,
        agent,
        task: str,
        session_id: str = None,
        parent_context: RunContext = None,
    ) -> RunResult:
        """Run an agent on a task until completion or budget exhaustion."""
        session_id = session_id or uuid.uuid4().hex[:12]
        # Derive mode from agent name for mode-aware memory reflection
        mode = "assistant" if agent.name == "assistant" else "scientist"

        # Ensure this thread's tool globals point to our instances (needed for
        # child runners executing in worker threads).
        self._inject_thread_locals()

        # Initialize memory
        self.memory_manager.on_session_start(session_id, task)
        memory_entries = self.memory_manager.get_recent_entries()
        memory_block = self.memory_manager.get_system_prompt_block()

        # Match relevant skills
        skills_block = self.skill_engine.get_prompt_block(task)

        # Build system prompt
        available_agents = agent_registry.list_available()
        system_prompt = self.prompt_builder.build_system_prompt(
            agent,
            available_agents=available_agents if available_agents else None,
            memory_block=memory_block if memory_block else None,
            skills_block=skills_block if skills_block else None,
        )

        # Start trajectory span
        span_id = None
        if self.trajectory:
            parent_span_id = parent_context.span_id if parent_context else None
            memory_summaries = [e.summary for e in memory_entries] if memory_entries else []
            span_id = self.trajectory.start_span(
                agent_name=agent.name,
                task=task,
                system_prompt=system_prompt,
                memories_loaded=memory_summaries,
                parent_span_id=parent_span_id,
            )

        context = RunContext(
            session_id=session_id,
            agent=agent,
            workspace=os.getcwd(),
            parent_context=parent_context,
            iteration_budget=agent.max_iterations,
            config=self.config,
            span_id=span_id,
            trajectory=self.trajectory,
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

        # Get tool definitions
        tool_defs = self._get_tool_definitions(agent)

        # Initialize messages
        messages = [{"role": "user", "content": task}]
        self.session_store.append_message(session_id, "user", task)

        total_usage = TokenUsage()
        tool_calls_count = 0

        logger.info(f"Starting agent '{agent.name}' (session={session_id}, span={span_id})")

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
                self._finalize_session(result, messages, span_id, mode=mode)
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
                self._finalize_session(result, messages, span_id, mode=mode)
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

                # Record tool start in trajectory
                if self.trajectory and span_id:
                    self.trajectory.record_tool_start(span_id, tc.id, tc.name, tc.arguments)

                if tc.name in self._RUNNER_TOOLS:
                    result_str = self._handle_agent_tool(tc.name, tc.arguments, context)
                    from autosci.tools.registry import _detect_error, _truncate_output
                    is_error = _detect_error(result_str)
                    result_str = _truncate_output(result_str)
                else:
                    from autosci.tools.registry import ToolResult as _ToolResult
                    tool_result: _ToolResult = tool_registry.dispatch(tc.name, tc.arguments)
                    result_str = tool_result.content
                    is_error = tool_result.is_error

                # Record tool end in trajectory
                if self.trajectory and span_id:
                    self.trajectory.record_tool_end(
                        span_id, tc.id, tc.name, tc.arguments, result_str,
                    )

                block = {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                }
                if is_error:
                    block["is_error"] = True
                tool_results.append(block)

            messages.append({"role": "user", "content": tool_results})
            self.session_store.append_message(session_id, "user", tool_results)

            # Check if context compression is needed.
            # Use the current-round prompt tokens (from LLM response) as a proxy for
            # context size — more accurate than accumulating all response tokens.
            current_tokens = response.usage.prompt_tokens if response.usage else total_usage.prompt_tokens
            if self.context_engine.should_compress(current_tokens):
                logger.info("Context compression triggered")
                before_tokens = current_tokens
                self.memory_manager.on_pre_compress(messages)
                messages = self.context_engine.compress(messages)
                after_tokens = sum(_estimate_message_tokens(m) for m in messages)
                if self.trajectory and span_id:
                    self.trajectory.record_compression(span_id, before_tokens, after_tokens)

        # Budget exhausted
        logger.warning(f"Agent '{agent.name}' exhausted iteration budget ({context.iteration_budget})")
        result = RunResult(
            session_id=session_id,
            response="Budget exhausted: reached maximum iterations.",
            status="budget_exhausted",
            token_usage=total_usage,
            tool_calls_count=tool_calls_count,
        )
        self._finalize_session(result, messages, span_id, mode=mode)
        return result

    def _finalize_session(
        self,
        result: RunResult,
        messages: list[dict] = None,
        span_id: str = None,
        mode: str = "scientist",
    ) -> None:
        """End the session in storage, trigger memory reflection, export, and close trajectory span."""
        self.session_store.end_session(
            session_id=result.session_id,
            status=result.status,
            total_tokens=result.token_usage.total_tokens,
            tool_calls_count=result.tool_calls_count,
        )

        # Memory reflection (only for completed sessions)
        stored_summaries = []
        if messages:
            stored_summaries = self.memory_manager.on_session_end(
                result.session_id, messages, result.status, mode=mode,
            )

        # Close trajectory span
        if self.trajectory and span_id:
            self.trajectory.end_span(
                span_id=span_id,
                status=result.status,
                output=result.response,
                prompt_tokens=result.token_usage.prompt_tokens,
                completion_tokens=result.token_usage.completion_tokens,
                total_tokens=result.token_usage.total_tokens,
                memories_stored=stored_summaries,
            )

        if self.auto_export:
            self.session_exporter.export(
                result.session_id,
                output_dir=self.export_dir,
            )

    def export_trajectory(self, task: str = "", task_plan: dict = None) -> str:
        """Generate trajectory report.md. Returns path or empty string."""
        if not self.trajectory:
            return ""
        exporter = TrajectoryExporter(self.trajectory.trajectory_dir)
        return exporter.export(task=task, task_plan=task_plan)

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
        """Get tool definitions filtered by agent's allowed tools.

        If agent.tools is empty, all tools are returned (unrestricted).
        If agent.tools is non-empty, only those tools are returned.
        Runner-intercepted tools (delegate, ask_user, etc.) are included
        only if they appear in the agent's explicit tool list (or the agent
        is unrestricted).
        """
        if agent.tools:
            # Restricted: include only what the agent declared
            names = list(agent.tools)
            return tool_registry.get_definitions(names=names)
        else:
            # Unrestricted: all tools
            return tool_registry.get_definitions()

    def _handle_agent_tool(self, name: str, args: dict, context: RunContext) -> str:
        """Handle runner-intercepted tools (delegate, delegate_parallel, ask_user, create_agent, update_claim)."""
        if name == "delegate":
            return self._handle_delegate(args, context)
        elif name == "delegate_parallel":
            return self._handle_delegate_parallel(args, context)
        elif name == "ask_user":
            return self._handle_ask_user(args)
        elif name == "create_agent":
            return self._handle_create_agent(args, context)
        elif name == "update_claim":
            return self._handle_update_claim(args, context)
        return f"Error: unknown agent tool: {name}"

    def _handle_delegate(self, args: dict, parent_context: RunContext) -> str:
        """Spawn a child runner for a single delegated subtask."""
        agent_name = args.get("agent", "")
        task = args.get("task", "")
        extra_context = args.get("context", "")

        if not agent_name or not task:
            return "Error: delegate requires 'agent' and 'task' arguments"

        try:
            agent = agent_registry.get(agent_name)
        except KeyError as e:
            return str(e)

        full_task = task
        if extra_context:
            full_task = f"{task}\n\n## Context\n\n{extra_context}"

        logger.info(f"Delegating to '{agent_name}': {task[:80]}")

        if self.trajectory and parent_context.span_id:
            self.trajectory.record_delegation(parent_context.span_id, agent_name, task)

        child_runner = self._make_child_runner()
        child_result = child_runner.run(
            agent=agent,
            task=full_task,
            parent_context=parent_context,
        )

        status_note = ""
        if child_result.status != "completed":
            status_note = f"\n[Note: subagent ended with status '{child_result.status}']"

        return (
            f"[Subagent '{agent_name}' result]{status_note}\n\n"
            f"{child_result.response}"
        )

    def _handle_delegate_parallel(self, args: dict, parent_context: RunContext) -> str:
        """Spawn multiple child runners in parallel via ThreadPoolExecutor.

        Args schema:
            tasks: list of {agent, task, context?} dicts — each becomes one subagent run.
        """
        tasks = args.get("tasks")
        if not tasks or not isinstance(tasks, list):
            return "Error: delegate_parallel requires a 'tasks' list"
        if len(tasks) > self.MAX_PARALLEL_SUBAGENTS:
            return (
                f"Error: too many parallel tasks ({len(tasks)}); "
                f"maximum is {self.MAX_PARALLEL_SUBAGENTS}"
            )

        # Resolve agents up-front so we fail fast before spawning threads
        resolved = []
        for i, t in enumerate(tasks):
            agent_name = t.get("agent", "")
            task_text = t.get("task", "")
            if not agent_name or not task_text:
                return f"Error: tasks[{i}] missing 'agent' or 'task'"
            try:
                agent = agent_registry.get(agent_name)
            except KeyError as e:
                return str(e)
            extra_context = t.get("context", "")
            full_task = task_text
            if extra_context:
                full_task = f"{task_text}\n\n## Context\n\n{extra_context}"
            resolved.append((i, agent_name, agent, full_task))

        logger.info(f"delegate_parallel: launching {len(resolved)} subagents in parallel")

        if self.trajectory and parent_context.span_id:
            for _, agent_name, _, task_text in resolved:
                self.trajectory.record_delegation(parent_context.span_id, agent_name, task_text)

        results_by_index: dict[int, str] = {}

        def _run_child(idx: int, agent_name: str, agent, full_task: str) -> tuple[int, str]:
            child_runner = self._make_child_runner()
            child_result = child_runner.run(
                agent=agent,
                task=full_task,
                parent_context=parent_context,
            )
            status_note = ""
            if child_result.status != "completed":
                status_note = f"\n[Note: subagent ended with status '{child_result.status}']"
            return idx, f"[Subagent '{agent_name}' result]{status_note}\n\n{child_result.response}"

        with ThreadPoolExecutor(max_workers=len(resolved)) as executor:
            futures = {
                executor.submit(_run_child, idx, agent_name, agent, full_task): idx
                for idx, agent_name, agent, full_task in resolved
            }
            for future in as_completed(futures):
                try:
                    idx, result_str = future.result()
                    results_by_index[idx] = result_str
                except Exception as exc:
                    idx = futures[future]
                    results_by_index[idx] = f"[Subagent {idx} error]: {exc}"

        # Return results in original task order
        parts = [results_by_index[i] for i in range(len(resolved))]
        return "\n\n---\n\n".join(parts)

    def _handle_create_agent(self, args: dict, parent_context: RunContext) -> str:
        """Instantiate a DynamicAgent from inline definition and run it."""
        from autosci.agents.dynamic_agent import DynamicAgent

        name = args.get("name", "").strip().lower().replace(" ", "_")
        if not name:
            return "Error: create_agent requires 'name'"
        task = args.get("task", "").strip()
        if not task:
            return "Error: create_agent requires 'task'"

        agent = DynamicAgent(
            name=name,
            role=args.get("description", ""),
            system_prompt=args.get("system_prompt", f"You are the {name} agent."),
            tools=args.get("tools", []),
            max_iterations=int(args.get("max_iterations", 30)),
        )

        # Optionally persist the agent YAML to the workspace/agents/ directory
        workspace = self.config.get("scientist", {}).get("workspace", "")
        if workspace:
            self._save_agent_yaml(agent, workspace)

        # Register temporarily so it can be listed/reused in this session
        agent_registry.register_instance(agent)

        logger.info(f"create_agent: spawning '{name}' for task: {task[:80]}")

        if self.trajectory and parent_context.span_id:
            self.trajectory.record_delegation(parent_context.span_id, name, task)

        child_runner = self._make_child_runner()
        child_result = child_runner.run(
            agent=agent,
            task=task,
            parent_context=parent_context,
        )

        status_note = ""
        if child_result.status != "completed":
            status_note = f"\n[Note: agent ended with status '{child_result.status}']"

        return f"[Agent '{name}' result]{status_note}\n\n{child_result.response}"

    def _save_agent_yaml(self, agent, workspace: str) -> None:
        """Save a DynamicAgent definition as YAML to workspace/agents/."""
        import yaml  # optional — skip gracefully if unavailable
        agents_dir = os.path.join(workspace, "agents")
        os.makedirs(agents_dir, exist_ok=True)
        path = os.path.join(agents_dir, f"{agent.name}.yaml")
        data = {
            "name": agent.name,
            "description": agent.role,
            "system_prompt": agent._system_prompt,
            "tools": agent.tools,
            "max_iterations": agent.max_iterations,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            logger.debug(f"Saved agent YAML: {path}")
        except Exception as e:
            logger.warning(f"Could not save agent YAML: {e}")

    def _handle_update_claim(self, args: dict, context: RunContext) -> str:
        """Update a Claim's status in workspace/task_plan.json and record in trajectory."""
        import datetime
        from autosci.protocols.task_plan import load_task_plan, save_task_plan
        from autosci.middleware.trajectory.schemas import TrajectoryEvent

        claim_id = args.get("claim_id", "").strip()
        new_status = args.get("status", "").strip()
        evidence = args.get("evidence", "").strip()

        if not claim_id or not new_status:
            return "Error: update_claim requires 'claim_id' and 'status'"

        valid_statuses = {"supported", "refuted", "partial", "unverified"}
        if new_status not in valid_statuses:
            return f"Error: status must be one of {sorted(valid_statuses)}"

        workspace = context.workspace or self.config.get("scientist", {}).get("workspace", "")
        if not workspace:
            return "Error: update_claim requires a task workspace (not available in assistant mode)"

        plan = load_task_plan(workspace)
        if plan is None:
            return f"Error: task_plan.json not found in workspace '{workspace}'"

        # Find and update the claim
        matched = False
        for claim in plan.claims:
            if claim.id.upper() == claim_id.upper():
                old_status = claim.status
                claim.status = new_status
                matched = True
                break

        if not matched:
            available = [c.id for c in plan.claims]
            return f"Error: claim '{claim_id}' not found. Available: {available}"

        # Persist updated plan
        save_task_plan(plan, workspace)

        # Record in trajectory
        if self.trajectory and context.span_id:
            self.trajectory.record_event(TrajectoryEvent(
                event_type="claim_update",
                timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
                span_id=context.span_id,
                agent_name=context.agent.name,
                data={
                    "claim_id": claim_id,
                    "old_status": old_status,
                    "new_status": new_status,
                    "evidence": evidence,
                },
            ))

        logger.info(f"Claim {claim_id}: {old_status} → {new_status}")
        return (
            f"Claim {claim_id} updated: {old_status} → {new_status}\n"
            f"Evidence recorded: {evidence}"
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
