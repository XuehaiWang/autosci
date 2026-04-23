# autosci Architecture Design

> Status: DRAFT — Pending review
> Date: 2026-04-23

## 1. Design Goals

autosci is an agent framework for **end-to-end scientific research tasks**. Core goals:

1. **Research-oriented**: support the full research lifecycle (literature → hypothesis → experiment → analysis → writing)
2. **Flexible workflow**: main agent dynamically decides which subagents to invoke; workflow is NOT hardcoded
3. **Minimal & decoupled**: each module has clear boundaries; easy to extend without touching core
4. **Reproducible**: every agent run produces traceable, replayable records
5. **Evolvable**: the agent learns from past research sessions and improves over time

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Entry Points                         │
│                    (CLI / Script / API)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      Runtime Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  AgentRunner  │  │ PromptBuilder│  │  ErrorHandler    │  │
│  │  (while-loop) │  │              │  │                  │  │
│  └──────┬───────┘  └──────────────┘  └──────────────────┘  │
│         │                                                    │
│  ┌──────▼───────┐                                           │
│  │  LLM Client  │  (Anthropic / OpenAI / local)             │
│  └──────────────┘                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     Agent Layer                              │
│  ┌──────────────┐  ┌───────────────────────────────────┐    │
│  │  Main Agent   │  │          Subagent Pool             │    │
│  │  (Orchestrator│──│  ┌─────────┐ ┌─────────┐ ┌─────┐ │    │
│  │   & Planner)  │  │  │Research │ │Experiment│ │Write│ │    │
│  └──────────────┘  │  │  Agent  │ │  Agent   │ │Agent│ │    │
│                     │  └─────────┘ └─────────┘ └─────┘ │    │
│                     │  ┌─────────┐ ┌─────────┐         │    │
│                     │  │Analysis │ │  Code   │         │    │
│                     │  │  Agent  │ │  Agent  │         │    │
│                     │  └─────────┘ └─────────┘         │    │
│                     └───────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Capability Layer                           │
│  ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────┐ ┌──────────┐ │
│  │  Tools   │ │Context │ │ Memory │ │Skills│ │ Storage  │ │
│  │ Registry │ │ Engine │ │Manager │ │Engine│ │ (Session)│ │
│  └──────────┘ └────────┘ └────────┘ └──────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 3. Module Design

### 3.1 Runtime Layer (`src/autosci/runtime/`)

**AgentRunner** — the core while-loop that drives agent execution.

```python
class AgentRunner:
    """Core agent execution loop."""

    def run(self, agent: BaseAgent, task: str, session_id: str = None) -> RunResult:
        """
        1. Initialize session (new or resume)
        2. Build system prompt via PromptBuilder
        3. Preflight context check
        4. while budget_remaining and not interrupted:
            a. Build API messages
            b. Call LLM
            c. If tool_calls: execute tools, append results
            d. If text response: check if done or needs continuation
            e. On error: classify → retry / compress / abort
        5. Finalize session, return result
        """
```

Key design decisions:
- Runner is agent-agnostic — it doesn't know if it's running the main agent or a subagent
- Same runner instance can run any `BaseAgent` subclass
- Runner owns the iteration budget, interrupt handling, and error recovery
- Runner delegates prompt building, tool dispatch, and context compression to pluggable modules

**PromptBuilder** — assembles system prompts from composable blocks.

```python
class PromptBuilder:
    def build_system_prompt(self, agent: BaseAgent, context: RunContext) -> str:
        """Assemble: agent identity + memory + skills + environment + task context"""

    def build_api_messages(self, messages: list, context: RunContext) -> list:
        """Create ephemeral API message copy with injected metadata"""
```

**ErrorHandler** — classifies errors and determines recovery strategy.

```python
class ErrorHandler:
    def classify(self, error: Exception) -> ClassifiedError: ...
    def should_retry(self, classified: ClassifiedError) -> bool: ...
    def should_compress(self, classified: ClassifiedError) -> bool: ...
```

**LLMClient** — unified interface to LLM providers.

```python
class LLMClient:
    def chat(self, messages: list, tools: list = None, **kwargs) -> LLMResponse: ...
```

Single implementation using `litellm` or direct API calls. Provider-specific logic stays inside this class.

### 3.2 Agent Layer (`src/autosci/agents/`)

**BaseAgent** — abstract base class for all agents.

```python
class BaseAgent(ABC):
    name: str
    role: str                    # role description for prompt
    system_prompt: str           # agent-specific identity/instructions
    tools: list[str]             # allowed tool names
    max_iterations: int = 50

    @abstractmethod
    def get_system_prompt(self) -> str: ...
```

**AgentRegistry** — self-registration mechanism for agents (same pattern as ToolRegistry).

```python
class AgentRegistry:
    """Discovers and manages available agents."""

    def register(self, agent_class: type[BaseAgent]) -> None:
        """Register an agent class. Called at module top level."""

    def get(self, name: str) -> type[BaseAgent]:
        """Look up an agent class by name. Used by delegate tool."""

    def list_available(self) -> list[dict]:
        """Return name + role for all registered agents. Injected into
        MainAgent's system prompt so it knows what subagents exist."""

    def discover(self, subagents_dir: str) -> None:
        """Auto-import all modules in subagents/ to trigger self-registration."""

agent_registry = AgentRegistry()  # singleton
```

Adding a new subagent = creating a new file in `agents/subagents/` with a `BaseAgent` subclass
and calling `agent_registry.register()`. No other code changes needed. The MainAgent discovers
available subagents at runtime via `agent_registry.list_available()`, which is injected into its
system prompt.

**MainAgent** (`agents/main_agent.py`) — the orchestrator.

- Receives the research task from the user
- Plans the research workflow dynamically
- Delegates subtasks to subagents via a `delegate` tool
- Synthesizes results from subagents
- Makes high-level decisions about research direction
- Has access to all tools + delegation capability
- **Does NOT hardcode any subagent names** — it reads the available subagent list from its system prompt at runtime

**Subagents** (`agents/subagents/`) — specialized research agents.

Initial set (extensible — add more by creating new files):

| Agent | Role | Core tools |
|-------|------|------------|
| ResearchAgent | Literature search, paper reading, knowledge synthesis | web_search, read_file, write_file |
| ExperimentAgent | Experiment design, parameter selection | write_file, terminal |
| CodeAgent | Implementation, debugging | write_file, terminal, read_file |
| AnalysisAgent | Data analysis, result interpretation | terminal, read_file, write_file |
| WriteAgent | Paper/report writing, formatting | write_file, read_file |

Subagents are NOT hardcoded into the workflow. The main agent decides which subagents to invoke based on the task.

**Delegation mechanism:**

```python
# Main agent uses "delegate" tool:
{
    "tool": "delegate",
    "args": {
        "agent": "code",          # subagent name
        "task": "Implement the ...",
        "context": "...",          # relevant context to pass
        "workspace": "/path/to/..."
    }
}

# Runner creates a child runner with:
# - Isolated iteration budget
# - Shared session storage (child session linked to parent)
# - Subagent's own tool set and system prompt
# - Parent context passed as initial message
```

### 3.3 Tool System (`src/autosci/tools/`)

**Design**: self-registration pattern (inspired by hermes-agent).

```python
# tools/registry.py
class ToolRegistry:
    def register(self, name: str, schema: dict, handler: Callable,
                 toolset: str = "default", check_fn: Callable = None): ...
    def get_definitions(self, toolsets: list[str] = None) -> list[dict]: ...
    def dispatch(self, name: str, args: dict) -> str: ...

registry = ToolRegistry()  # singleton

# tools/file_tools.py
from autosci.tools.registry import registry

def read_file(path: str, offset: int = 0, limit: int = 2000) -> str: ...

registry.register(
    name="read_file",
    schema=READ_FILE_SCHEMA,
    handler=read_file,
    toolset="file",
)
```

**Built-in toolsets:**

| Toolset | Tools | Description |
|---------|-------|-------------|
| file | read_file, write_file, list_dir, glob, grep | File operations |
| terminal | execute_command | Shell command execution |
| web | web_search, web_fetch | Web search and page reading |
| agent | delegate, ask_user | Agent delegation and user interaction |

Tool results that exceed a size threshold are saved to disk with only a summary returned to context (inspired by hermes-agent's result storage pattern).

### 3.4 Context Management (`src/autosci/context/`)

**Design**: strategy pattern with abstract interface.

```python
class ContextEngine(ABC):
    @abstractmethod
    def should_compress(self, token_count: int) -> bool: ...

    @abstractmethod
    def compress(self, messages: list) -> list: ...

class SummarizationCompressor(ContextEngine):
    """Default: LLM-based lossy summarization.

    Algorithm:
    1. Protect head (system prompt, first exchange)
    2. Protect tail (recent N tokens)
    3. Prune old tool results (replace with summaries)
    4. Summarize middle messages via LLM
    5. Anti-thrashing: skip if last 2 compressions saved < 10%
    """
```

### 3.5 Memory System (`src/autosci/memory/`)

**Design**: provider-based orchestration (inspired by hermes-agent), with research-specific evolution.

```python
class MemoryProvider(ABC):
    """Interface for memory backends."""

    @abstractmethod
    def get_system_prompt_block(self) -> str: ...

    @abstractmethod
    def store(self, key: str, content: str, memory_type: str) -> None: ...

    @abstractmethod
    def retrieve(self, query: str, memory_type: str = None) -> list[MemoryEntry]: ...

    def on_session_end(self, session: Session) -> None: ...
    def on_pre_compress(self, messages: list) -> None: ...

class MemoryManager:
    """Orchestrates memory providers."""
    # Built-in file-based provider always active
    # Optional external provider (vector DB, etc.) can be added
```

**Memory types** (research-oriented):

| Type | Purpose | Example |
|------|---------|---------|
| episodic | What happened in past sessions | "In session X, experiment Y failed because of Z" |
| semantic | Domain knowledge accumulated | "Dataset A has known quality issues with column B" |
| procedural | Learned procedures/patterns | "For this type of analysis, use method X then Y" |

**Evolution**: after each session, MemoryManager can optionally run a reflection step to extract and store insights from the session history.

### 3.6 Skill System (`src/autosci/skills/`)

Skills are **reusable research patterns** stored as markdown files with structured metadata.

```
skills/
├── literature_review.md
├── hypothesis_generation.md
├── experiment_template.md
└── statistical_analysis.md
```

**Skill format:**

```markdown
---
name: literature_review
description: Systematic literature review process
required_tools: [web_search, write_file]
applicable_when: "user asks for literature review or survey"
---

## Process
1. Define search terms from the research question
2. Search academic databases...
3. ...
```

**SkillEngine:**

```python
class SkillEngine:
    def discover(self, skills_dir: str) -> list[Skill]: ...
    def match(self, task_description: str, available_skills: list[Skill]) -> list[Skill]: ...
    def get_prompt_block(self, skills: list[Skill]) -> str: ...
```

Skills are injected into the system prompt when relevant. The agent can also create/update skills during execution.

### 3.7 Session Storage (`src/autosci/storage/`)

**Design**: hybrid approach — SQLite for runtime, Markdown export for human consumption.

- **Runtime**: SQLite (fast writes, structured queries, FTS, atomic transactions)
- **Post-session**: auto-export to Markdown (human-readable, git-friendly, reviewable)
- Export is **one-way** (SQLite → Markdown), no reverse sync needed

```python
class SessionStore:
    """SQLite-backed session and message storage."""

    def create_session(self, metadata: dict = None) -> str: ...
    def append_message(self, session_id: str, message: dict) -> None: ...
    def get_messages(self, session_id: str) -> list[dict]: ...
    def search_sessions(self, query: str) -> list[Session]: ...
    def link_child_session(self, parent_id: str, child_id: str) -> None: ...

class SessionExporter:
    """Exports completed sessions to readable Markdown files."""

    def export(self, session_id: str, output_dir: str) -> str:
        """Export a session to Markdown. Returns the output file path.

        Output format:
        - YAML frontmatter (session id, agent, task, timestamp, status, token usage)
        - Chronological message log with role labels
        - Tool calls rendered as fenced code blocks
        - Subagent delegations shown as nested sections
        """

    def export_on_session_end(self, session_id: str) -> str:
        """Auto-called when a session completes. Writes to workspace/sessions/."""
```

**Markdown export example:**

```markdown
---
session_id: "abc123"
agent: main_agent
task: "Investigate attention mechanisms for long-context documents"
started: "2026-04-23T10:00:00"
ended: "2026-04-23T10:45:00"
status: completed
total_tokens: 125000
---

## User
Investigate whether transformer attention mechanisms can be improved...

## Assistant (MainAgent)
I'll break this into phases...

## Tool Call: delegate
```json
{"agent": "research", "task": "Search for recent papers on..."}
```

### Subagent: ResearchAgent
> Found 12 relevant papers...

## Assistant (MainAgent)
Based on the literature review...
```

**Stored data (SQLite):**
- Session metadata (id, timestamp, agent, task, status)
- Messages (role, content, tool_calls, token_count)
- Session lineage (parent-child for delegation)
- Tool call records (for reproducibility)

**Exported data (Markdown):**
- One `.md` file per session in `{workspace}/sessions/`
- Filename: `{timestamp}_{session_id_short}_{task_slug}.md`
- Git-trackable, human-reviewable, can serve as research appendix

### 3.8 Protocols (`src/autosci/protocols/`)

Shared data structures for inter-module communication.

```python
@dataclass
class RunContext:
    session_id: str
    agent: BaseAgent
    workspace: str             # working directory for this run
    parent_context: RunContext | None  # for delegated subagents
    iteration_budget: int
    config: dict

@dataclass
class RunResult:
    session_id: str
    response: str
    status: str                # "completed" | "interrupted" | "error" | "budget_exhausted"
    token_usage: TokenUsage
    tool_calls_count: int

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] | None
    usage: TokenUsage
    finish_reason: str

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class MemoryEntry:
    key: str
    content: str
    memory_type: str           # episodic | semantic | procedural
    timestamp: str
    relevance_score: float | None
```

### 3.9 Configuration (`src/autosci/configs/`)

```python
# configs/default.py
DEFAULT_CONFIG = {
    "llm": {
        "provider": "anthropic",       # anthropic | openai | local
        "model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "max_tokens": 8192,
    },
    "runtime": {
        "max_iterations": 100,
        "context_window": 200000,
        "compression_threshold": 0.75,  # compress at 75% of context window
    },
    "storage": {
        "db_path": "~/.autosci/sessions.db",
        "export_dir": "./sessions/",       # Markdown export directory (relative to workspace)
        "auto_export": True,               # auto-export to Markdown on session end
    },
    "memory": {
        "provider": "file",            # file | (future: vector)
        "base_dir": "~/.autosci/memory/",
    },
    "skills": {
        "dirs": ["~/.autosci/skills/", "./skills/"],
    },
}
```

## 4. Directory Structure

```text
autosci-2/
├── src/
│   └── autosci/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py              # BaseAgent ABC
│       │   ├── registry.py          # AgentRegistry (self-registration)
│       │   ├── main_agent.py        # MainAgent (orchestrator)
│       │   └── subagents/
│       │       ├── __init__.py
│       │       ├── research.py      # ResearchAgent
│       │       ├── experiment.py    # ExperimentAgent
│       │       ├── code.py          # CodeAgent
│       │       ├── analysis.py      # AnalysisAgent
│       │       └── write.py         # WriteAgent
│       ├── runtime/
│       │   ├── __init__.py
│       │   ├── runner.py            # AgentRunner (while-loop)
│       │   ├── prompt_builder.py    # PromptBuilder
│       │   ├── error_handler.py     # ErrorHandler
│       │   └── llm_client.py        # LLMClient
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py          # ToolRegistry
│       │   ├── file_tools.py        # File operations
│       │   ├── terminal_tool.py     # Shell execution
│       │   ├── web_tools.py         # Web search/fetch
│       │   └── agent_tools.py       # delegate, ask_user
│       ├── context/
│       │   ├── __init__.py
│       │   ├── engine.py            # ContextEngine ABC
│       │   └── compressor.py        # SummarizationCompressor
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── provider.py          # MemoryProvider ABC
│       │   ├── manager.py           # MemoryManager
│       │   └── file_provider.py     # File-based memory
│       ├── skills/
│       │   ├── __init__.py
│       │   └── engine.py            # SkillEngine
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── session_store.py     # SessionStore (SQLite)
│       │   └── exporter.py          # SessionExporter (Markdown)
│       ├── protocols/
│       │   ├── __init__.py
│       │   └── schemas.py           # Shared data structures
│       ├── configs/
│       │   ├── __init__.py
│       │   └── default.py           # Default configuration
│       └── utils/
│           ├── __init__.py
│           └── tokens.py            # Token counting utilities
├── tests/
│   ├── test_runner.py
│   ├── test_tools.py
│   ├── test_context.py
│   ├── test_memory.py
│   ├── test_storage.py
│   └── test_skills.py
├── scripts/
│   └── run.py                       # CLI entry point
├── skills/                           # Built-in skill definitions
│   └── ...
├── docs/
├── reference_designs/
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## 5. Execution Flow Example

```
User: "Investigate whether transformer attention mechanisms can be improved
       for long-context scientific document understanding"

MainAgent receives task
  ├─ Plans research phases:
  │   1. Literature review on attention mechanisms + long context
  │   2. Identify promising improvement directions
  │   3. Design experiment
  │   4. Implement & run experiment
  │   5. Analyze results
  │   6. Write report
  │
  ├─ Delegates to ResearchAgent:
  │   "Search for recent papers on efficient attention for long documents"
  │   → ResearchAgent uses web_search, reads papers, produces summary
  │   → Returns structured findings to MainAgent
  │
  ├─ MainAgent reviews findings, decides direction
  │
  ├─ Delegates to ExperimentAgent:
  │   "Design experiment comparing sliding window vs. sparse attention..."
  │   → ExperimentAgent produces experiment plan
  │
  ├─ Delegates to CodeAgent:
  │   "Implement the experiment based on this plan..."
  │   → CodeAgent writes code, runs tests
  │
  ├─ Delegates to AnalysisAgent:
  │   "Analyze the experimental results..."
  │   → AnalysisAgent produces statistical analysis
  │
  ├─ Delegates to WriteAgent:
  │   "Write a research report summarizing findings..."
  │   → WriteAgent produces structured report
  │
  └─ MainAgent synthesizes final output
```

## 6. Key Design Decisions

### 6.1 Why while-loop over graph/DAG?

- Simpler to understand and debug
- Research workflow is inherently exploratory — hard to pre-define as a graph
- Main agent can dynamically re-plan based on intermediate results
- Subagents themselves also use while-loop, keeping the model uniform

### 6.2 Why self-registration for tools?

- No central manifest file to keep in sync
- Adding a new tool = adding a file with handler + schema + `registry.register()`
- Easy to conditionally enable/disable tools via `check_fn`

### 6.3 Why hybrid storage (SQLite + Markdown export)?

- **SQLite** gives the agent fast runtime queries, FTS, structured search, and atomic writes
- **Markdown** gives researchers human-readable, git-friendly session records
- Research process itself is a valuable artifact — researchers may review agent reasoning, annotate sessions, or include them in publications
- One-way export (SQLite → Markdown) keeps the system simple — no sync conflicts
- Alternative: pure Markdown storage would require parsing files for search/query, which is slow at scale and loses atomicity

### 6.4 Why separate ContextEngine interface?

- Compression strategy is likely to evolve (summarization → retrieval-augmented → hybrid)
- Keeping it pluggable means we can swap strategies without touching the runner
- Different agents might need different compression strategies

### 6.5 Why not hardcode the research workflow?

- Different research tasks have fundamentally different structures
- The main agent should be able to skip phases, reorder them, or add new ones
- Human-on-the-loop: user can intervene and redirect at any point

## 7. Dependencies (Initial)

```
anthropic          # Anthropic API client
openai             # OpenAI-compatible API client (for flexibility)
tiktoken           # Token counting
pydantic           # Data validation for schemas
rich               # CLI output formatting
```

## 8. Implementation Priority

| Phase | Scope | Modules |
|-------|-------|---------|
| P0 | Minimal viable loop | protocols, configs, llm_client, runner, base agent, main_agent (simple version) |
| P1 | Core tools | registry, file_tools, terminal_tool, web_tools |
| P2 | Storage + context | session_store, context engine + compressor |
| P3 | Delegation | agent_tools (delegate), subagent implementations |
| P4 | Memory | provider, manager, file_provider |
| P5 | Skills | engine, built-in skills |
