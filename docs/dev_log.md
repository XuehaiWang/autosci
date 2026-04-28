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

### Phase 5: Skill System (P5) (COMPLETED)

Implemented reusable research procedure templates:

**SkillEngine** (`skills/engine.py`):
- Auto-discovers .md files with YAML frontmatter from configured directories
- Tag + keyword matching for task-relevant skill selection
- Create new skills programmatically (agent can codify learned procedures)
- Prompt injection: only name+description (not full content) to save context

**Skill Tools** (`tools/skill_tools.py`):
- list_skills: show all available skills
- view_skill: read full procedure (agent calls on demand)
- create_skill: create new skill from experience

**3 Built-in Skills** (`skills/`):
- literature_review: systematic literature review procedure
- experiment_design: rigorous experiment design checklist
- data_analysis: structured data analysis workflow

**Runner integration**:
- SkillEngine initialized from config dirs on runner startup
- Skills matched to task and injected into system prompt
- Skill tools connected via module-level injection

## P0-P5 Complete

All planned modules implemented:
- P0: Core agent loop (runner, LLM client, prompt builder, error handler)
- P1: Core tools (file: read/write/list/glob/grep, terminal: execute_command)
- P2: Session storage (SQLite + Markdown export) + Context engine (pluggable compression)
- P3: Delegation (delegate/ask_user + 5 research subagents)
- P4: Memory (file provider, 3-type memory, LLM reflection, pre-compress rescue)
- P5: Skills (engine, 3 built-in skills, create/view/list tools)

### High-priority fixes (COMPLETED)

1. **External config file**: support `~/.autosci/config.yaml` with deep merge over defaults.
   `--init-config` flag creates default config. Priority: overrides > file > defaults.

2. **Web tools**: web_search (ddgs with graceful fallback) + web_fetch (requests + BeautifulSoup).
   Tested: successfully fetched and parsed arXiv paper page.

3. **Delegation state sharing**: MemoryManager now uses a session stack instead of single
   `_current_session_id`. Child delegation pushes, session end pops — parent context restored.

4. **Interactive REPL with TUI**: multi-turn conversation with rich Panel output,
   prompt_toolkit input with history, spinner during LLM calls. Commands: /help /status
   /history /clear /quit. Session saved on exit. Tested: multi-turn context retention works.

## 2026-04-28

### Phase F: TaskUnderstanding Subagent (COMPLETED)

Redesigned task understanding from a single LLM call into a full subagent with tool access.

**New data model** (`task/schemas.py`):
- `TaskContext`: 4-dimension parse — research_subject, data_type, task_goal, known_methods, key_terms
- `RelatedWork`: per-paper extraction — contribution, evidence, boundary/gap, year, authors
- `ResearchQuestion`: derived from context key points + literature gaps; traceable to related works
- `Claim`: typed hypothesis (comparative/existence/improvement/causal); verifiable_by specific experiment
- `TaskPlan`: complete artifact; `to_prompt_block()` for system prompt injection, `to_markdown()` for report

**TaskUnderstandingAgent** (`task/agent.py`):
- Inherits `BaseAgent`; max_iterations=40; tools: web_search, web_fetch, read/write_file, glob, grep
- Two modes with detailed step-by-step prompts:
  - `topic_only`: 5 steps — literature exploration → brainstorm → select → formalize → write files
  - `task_given`: 5 steps — context parse → key point extraction → literature search → synthesis → write files
- Both prompts specify exact JSON format for `task_plan.json`
- Registered in agent_registry; bootstrapped in `cli._bootstrap()`

**TaskUnderstanding orchestrator** (`task/understanding.py`):
- Takes `runner` + `workspace` (NOT llm_client — runs as a full subagent)
- `detect_mode()`: word-boundary regex; ≤200 chars + no method keywords → topic_only
- `analyze()`: runs TaskUnderstandingAgent via runner.run(), reads back written task_plan.json
- Fallback to minimal plan if agent fails to write the file

**CLI integration** (`cli.py`):
- `_bootstrap()` now imports `autosci.task.agent` to register TaskUnderstandingAgent
- `_run_task()`: runner created before TaskUnderstanding (shared); recorder created before runner
- Removed `LLMClient` import from `_run_task()` (no longer needed for understanding)
- Task plan Panel updated to show RQs + Claims counts (no longer references old `subtasks` field)
