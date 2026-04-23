# Development Log

## 2026-04-23

### Phase 1: hermes-agent architecture reading (COMPLETED)

- Systematically read hermes-agent's core modules using 4 parallel research agents
- Covered: agent loop, tool system, context management, memory, skills, session storage, subagents, inter-agent communication, configuration, SOUL/prompt system
- Produced comprehensive reading notes: `reference_designs/project_reading/hermes-agent.md`

Key findings:
- hermes-agent is a multi-entry, single-core architecture (CLI/Gateway/ACP/TUI all wrap same AIAgent core)
- Core loop is a synchronous while-loop in `run_agent.py` with pluggable context engine
- Tool system uses self-registration + AST-based discovery
- Memory is a provider orchestration layer (built-in + at most one external provider)
- Skills are discoverable knowledge assets with conditional activation
- Session storage uses SQLite + WAL + FTS5
- Error handling separates classification from recovery logic
- System prompt is composable (identity + memory + skills + platform + environment)

Next: Define autosci overall architecture (Phase 2)

### Phase 2: Session Storage + Context Engine (P2) (COMPLETED)

Implemented two modules and integrated them into the runner:

**Session Storage** (`storage/`):
- `SessionStore`: SQLite-backed storage with WAL mode and FTS5 full-text search
- Tables: sessions (with lineage), messages (with FTS index)
- `SessionExporter`: auto-exports completed sessions to Markdown files
- Markdown output includes YAML frontmatter, chronological messages, tool calls as code blocks

**Context Engine** (`context/`):
- `ContextEngine` ABC: pluggable compression interface
- `SummarizationCompressor`: three-zone protection (head/middle/tail)
  - Tool result pruning for old results
  - LLM-based or fallback extractive summarization
  - Anti-thrashing: skips if recent compressions saved < 10%

**Runner integration**:
- Creates sessions on run start, persists every message
- Checks compression after each turn via context engine
- Finalizes session (end + export) on completion/error/budget exhaustion
- Auto-exports to `./sessions/*.md`

Next: Implement delegation (P3)

### Phase 3: Delegation + Subagents (P3) (COMPLETED)

Implemented agent delegation mechanism and 5 research subagents:

**Delegate tool** (`tools/agent_tools.py`):
- `delegate`: spawns a child agent run with isolated budget and linked session
- `ask_user`: interactive user input during agent execution
- Both are "runner-intercepted" — schemas registered in ToolRegistry for LLM visibility,
  but actual execution handled by AgentRunner

**Runner integration**:
- `_RUNNER_TOOLS` set identifies tools intercepted before registry dispatch
- `_handle_delegate()`: looks up subagent from registry, runs with child context,
  returns result to parent agent
- Child sessions automatically linked to parent via `parent_session_id`
- Each subagent gets its own Markdown export

**5 Subagents** (`agents/subagents/`):
- `research`: literature search, paper reading, knowledge synthesis
- `experiment`: experiment design, parameter selection
- `code`: implementation, debugging, testing (max_iterations=50)
- `analysis`: data analysis, statistical testing
- `write`: paper/report writing

E2E tested: main agent delegated code writing to code subagent, then ran the
produced script. Sessions correctly linked in storage, both exported to Markdown.

Next: Implement memory system (P4)

### Phase 4: Memory System (P4) (COMPLETED)

Implemented three-layer memory system with LLM-based reflection:

**MemoryProvider ABC** (`memory/provider.py`):
- Abstract interface with store/retrieve/lifecycle hooks
- Extensible for future vector DB backend

**FileMemoryProvider** (`memory/file_provider.py`):
- File-system storage: individual .md files per memory, organized by type
- index.json for fast lookup
- Three-signal retrieval: tag_score × 0.4 + keyword_score × 0.4 + recency_score × 0.2
- Recency uses exponential decay (7-day half-life)
- Semantic/procedural conflict detection: >80% tag overlap triggers update instead of new entry

**MemoryManager** (`memory/manager.py`):
- Orchestrates provider + lifecycle hooks
- Post-session reflection: uses LLM to extract episodic/semantic/procedural memories
- Pre-compression rescue: extracts errors from tool results before context compression
- Only reflects on successfully completed sessions

**Memory Tools** (`tools/memory_tools.py`):
- store_memory: explicit memory creation by agent
- recall_memory: semantic search across all memory types
- Connected to MemoryManager via module-level injection

**Runner integration**:
- on_session_start: prefetch + inject memory block into system prompt
- on_pre_compress: rescue info before compression
- on_session_end: trigger LLM reflection (completed sessions only)

Next: Implement skill system (P5)
