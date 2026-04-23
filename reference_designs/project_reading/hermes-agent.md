# Hermes-Agent Architecture Reading Notes

> Source: `/mnt/20t/wxh/hermes-agent`
> Date: 2026-04-23

## 1. Overall Architecture

Hermes-agent is a **multi-entry, single-core** agent platform. The core conversation loop lives in `run_agent.py` (`AIAgent` class), while CLI, Gateway, ACP adapter, and TUI are all I/O frontends that wrap the same core.

### Layer decomposition

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| Core runtime | `run_agent.py` | Conversation loop, tool dispatch, error recovery, context compression |
| Agent internals | `agent/` | Prompt building, context engine, memory, model metadata, error classification |
| Tools | `tools/` | Tool definitions, registry, file/terminal/web/skill tools, approval, result storage |
| CLI | `hermes_cli/` | Configuration, commands, auth, profiles, setup, skin engine |
| Gateway | `gateway/` | Multi-platform messaging (Telegram/Discord/Slack/WhatsApp/etc.) |
| ACP adapter | `acp_adapter/` | Editor/IDE integration via stdio protocol |
| TUI | `ui-tui/` + `tui_gateway/` | Terminal UI via JSON-RPC |
| Skills | `skills/` + `optional-skills/` | Procedural knowledge assets |
| Scheduling | `cron/` | Background scheduled tasks |
| Environments | `environments/` | RL/benchmark environments |

### Key design principle

**Core agent logic is unified; I/O protocols are diversified via adapters.**

---

## 2. Agent Loop (run_agent.py)

### Control flow

```
main() → AIAgent.__init__() → run_conversation()
                                    │
                                    ├─ Initialize session state
                                    ├─ Build/cache system prompt
                                    ├─ Preflight context compression
                                    │
                                    └─ while (budget remaining & not interrupted):
                                         ├─ Build API messages (ephemeral copy)
                                         ├─ Call LLM
                                         ├─ If tool_calls:
                                         │    ├─ _execute_tool_calls()
                                         │    ├─ Append tool results to messages
                                         │    └─ Continue loop
                                         ├─ If no tool_calls:
                                         │    ├─ Handle empty/thinking-only responses
                                         │    └─ Return final response
                                         └─ On error:
                                              ├─ Classify error
                                              └─ Retry / compress / rotate credential / fallback / abort
```

### Key session state

- `_cached_system_prompt` — stable across turns for prompt cache friendliness
- `iteration_budget` — controls max iterations per conversation
- `_memory_manager` — orchestrates memory providers
- `context_compressor` — pluggable context engine
- `_fallback_chain` — provider/model fallback sequence
- `_interrupt_requested` — user interrupt flag

### Stop conditions

1. Model returns no tool_calls → final response
2. Iteration budget exhausted
3. User interrupt
4. Error recovery exhausted
5. Empty response recovery sequence exhausted

### Message management

Two separate message lists:
- `messages` — session facts (persistent)
- `api_messages` — per-turn API copy (ephemeral, with injected metadata, cleaned fields)

---

## 3. Tool System

### Registration & discovery

- **Self-registration**: each `tools/*.py` calls `registry.register()` at module top level
- **AST-based discovery**: `discover_builtin_tools()` scans files for `registry.register()` calls via AST before importing, avoids unnecessary imports
- **ToolEntry** fields: name, toolset, schema, handler, check_fn, requires_env, is_async, description, emoji, max_result_size_chars
- **Schema format**: OpenAI chat-completions style `{"type": "function", "function": {...}}`

### Execution pipeline

```
LLM returns tool_calls
  → _execute_tool_calls()
    → Parallelization check (_should_parallelize_tool_batch)
    → For each tool:
        → _invoke_tool()
          → Plugin pre_tool_call hook
          → Safety checks (approval, file protection)
          → Dispatch: built-in agent tools vs registry.dispatch()
          → Plugin post_tool_call hook
          → transform_tool_result hook
    → Append tool results as role:tool messages
```

### Special tool categories

- **Agent loop tools** (`todo`, `memory`, `session_search`, `delegate_task`): handled directly by agent loop, not via registry dispatch
- **MCP tools**: dynamically registered from remote MCP servers
- **Conflict protection**: MCP tools cannot shadow built-in tools

### Safety mechanisms

1. **Tool availability check** — `check_fn` determines if tool appears in schema
2. **Toolset-level control** — enable/disable entire toolsets
3. **File safety** — protected paths, safe root directory constraints
4. **Dangerous command approval** — regex patterns + optional LLM-based risk assessment
5. **Result budget control** — large results spill to disk files, only preview + path in context

### Parallel execution

- Read-only tools with non-overlapping paths can run in parallel (thread pool)
- Results collected in original order for API message consistency

---

## 4. Context Management

### Architecture: strategy pattern

- **ContextEngine** (abstract interface): `should_compress()`, `compress()`, lifecycle hooks
- **ContextCompressor** (default implementation): lossy summarization compression

### Compression algorithm

1. Prune old tool results (replace with summaries, deduplicate, truncate long args)
2. Protect head messages (system prompt, first exchange)
3. Protect tail messages (recent context by token budget)
4. LLM-summarize middle messages
5. Iterative summary updates if previously compressed

### Trigger conditions

- `prompt_tokens > threshold_tokens`
- Anti-thrashing: if last 2 compressions saved < 10%, pause compression
- Preflight compression before entering main loop (useful when switching to smaller model)
- Turn-level compression after each response

---

## 5. Error Handling

### Classification → Recovery separation

**ErrorClassifier** produces structured `ClassifiedError`:
- `reason` (FailoverReason enum)
- `retryable`, `should_compress`, `should_rotate_credential`, `should_fallback`

**Runner** decides recovery action:

| Error type | Recovery |
|-----------|---------|
| auth (401) | Credential refresh |
| rate_limit | Credential rotation / fallback model |
| context_overflow | Compress context |
| payload_too_large | Compress context |
| thinking_signature | Remove reasoning_details, retry |
| long_context_tier | Downgrade context_length (1M→200k), compress |
| timeout/transport | Backoff + retry |
| unknown | Default retryable + backoff |

---

## 6. Memory System

### Architecture

- **MemoryManager**: orchestrator, enforces "built-in + at most one external provider"
- **MemoryProvider**: pluggable interface with lifecycle hooks

### Provider interface

| Hook | Purpose |
|------|---------|
| `initialize()` | Setup |
| `system_prompt_block()` | Inject into system prompt |
| `prefetch()` / `queue_prefetch()` | Pre-load relevant memories |
| `sync_turn()` | Post-turn synchronization |
| `get_tool_schemas()` | Expose memory tools to LLM |
| `handle_tool_call()` | Handle memory-related tool calls |
| `on_turn_start()` | Turn lifecycle |
| `on_session_end()` | Session cleanup |
| `on_pre_compress()` | Pre-compression hook |
| `on_delegation()` | Subagent delegation |

### Design principle

Memory is not a monolithic store but a **provider orchestration layer** with rich lifecycle hooks.

---

## 7. Skill System

### Three-layer design

1. **Discovery/Read** (`tools/skills_tool.py`): `skills_list()`, `skill_view()`
2. **Authoring/Maintenance** (`tools/skill_manager_tool.py`): create, edit, patch, delete
3. **Configuration** (`hermes_cli/skills_config.py`): global + per-platform enable/disable
4. **Hub** (`hermes_cli/skills_hub.py`): search, install, publish, update, audit

### Skill format

- `SKILL.md` files with frontmatter metadata
- Platform/environment/toolset dependency declarations
- Conditional activation based on available tools and platform

---

## 8. Session Storage

### Implementation

- **SQLite + WAL + FTS5** (`hermes_state.py`)
- Stores: sessions, messages (with tool_calls serialization), full-text search index
- Supports: session lineage, compression continuation, token counts, metadata
- Capabilities: create/reopen/end sessions, search, export, prune, delete

### Key design

- Session history is **database-backed**, not just chat logs
- Persistent state is separated from ephemeral execution state

---

## 9. Subagent / Delegation

### Mechanism

- `delegate_task` is an agent loop tool
- Delegation creates isolated execution context:
  - Separate depth tracking
  - Isolated iteration budget
  - Optional memory skipping (e.g., for cron jobs)
  - Active child agent tracking

### Design principle

Subagents are **not independent services** but isolated execution contexts within the same runtime.

---

## 10. System Prompt / SOUL

### Architecture

- **SOUL.md**: hot-reloadable persona file, re-read on each message
- **default_soul.py**: fallback template if no SOUL.md exists
- **Prompt assembly** (`_build_system_prompt()`): composable layers

### Prompt layers (in order)

1. Agent identity (SOUL.md or default)
2. User/gateway system_message
3. Persistent memory
4. Skills guidance
5. Context files (AGENTS.md, workspace instructions)
6. Current timestamp
7. Platform hints (CLI/Telegram/Discord/etc.)
8. Environment hints (WSL, etc.)
9. Model-specific execution instructions

### Design principle

**Stable system prompt + per-turn ephemeral injection** — optimized for prompt caching.

---

## 11. Configuration & Provider System

### Configuration layers

| Source | Content |
|--------|---------|
| `~/.hermes/config.yaml` | Main config (models, toolsets, compression, skins) |
| `~/.hermes/.env` | API keys, secrets |
| `~/.hermes/auth.json` | OAuth tokens |
| Gateway YAML | Platform-specific config |

### Provider system

- Dynamic model context length detection (10-level fallback chain)
- Supports: Anthropic, OpenAI, OpenRouter, local servers (Ollama, vLLM, llama.cpp, LM Studio)
- Provider-aware routing (throughput/latency/price sorting)

---

## 12. Key Design Patterns for autosci Reference

1. **Runner orchestration + module extraction**: complex flow in runner, pure functions extracted to modules
2. **ContextEngine plugin pattern**: abstract interface + default implementation, swappable
3. **Stable system prompt + ephemeral injection**: prompt cache friendly
4. **Classification → Recovery separation**: error taxonomy decoupled from recovery logic
5. **Self-registration for tools**: no central manifest to maintain
6. **Task-local session context**: ContextVar for concurrent safety
7. **Result overflow to disk**: large tool outputs stored as files, only preview in context
8. **Provider-agnostic core**: adapter pattern for different LLM backends
