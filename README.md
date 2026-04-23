# AutoSci

An agent framework for end-to-end scientific research tasks.

AutoSci is an AI research agent that can plan research workflows, search literature, design experiments, write code, analyze data, and generate reports — all through natural language interaction.

## Quick Start

### 1. Install

```bash
git clone https://github.com/yourname/autosci.git
cd autosci
pip install -e .
```

### 2. Initialize

```bash
autosci --init
```

This creates `~/.autosci/` with:
- `config.yaml` — LLM provider, model, API key configuration
- `memory/` — persistent memory across sessions
- `skills/` — custom research procedure templates

### 3. Configure

Edit `~/.autosci/config.yaml` to set your LLM provider:

```yaml
llm:
  provider: openai          # openai (OpenAI-compatible) or anthropic
  model: gpt-4o             # model name
  api_key_env: OPENAI_API_KEY  # environment variable containing API key
  base_url: null             # custom endpoint URL (for proxies/local models)
  max_tokens: 8192
```

Set your API key:

```bash
export OPENAI_API_KEY="sk-..."
```

### 4. Run

```bash
# Interactive REPL (default)
autosci

# Single-shot task
autosci "Analyze the performance of ResNet vs ViT on CIFAR-10"

# Override model
autosci -m gpt-4o "your task"
```

## Features

### Interactive REPL

Start `autosci` without arguments for a multi-turn conversation interface:

```
🔬 You > Search for papers on efficient attention mechanisms
┌─────────── AutoSci ───────────┐
│ Found 3 relevant approaches:  │
│ 1. Linear Attention ...       │
│ 2. Flash Attention ...        │
│ 3. Sparse Attention ...       │
└───────────────────────────────┘

🔬 You > Design an experiment to compare them
  ⚙ delegate → experiment: Design comparison experiment...
┌─────────── AutoSci ───────────┐
│ Experiment plan:              │
│ ...                           │
└───────────────────────────────┘
```

REPL commands: `/help`, `/status`, `/history`, `/clear`, `/quit`

### Research Subagents

AutoSci has 5 specialized subagents that the main agent can delegate to:

| Agent | Role |
|-------|------|
| `research` | Literature search, paper reading, knowledge synthesis |
| `experiment` | Experiment design, parameter selection |
| `code` | Implementation, debugging, testing |
| `analysis` | Data analysis, statistical testing |
| `write` | Paper/report writing and formatting |

The main agent decides which subagents to use based on the task — the workflow is not hardcoded.

### 15 Built-in Tools

| Category | Tools |
|----------|-------|
| File | `read_file`, `write_file`, `list_dir`, `glob`, `grep` |
| Terminal | `execute_command` |
| Web | `web_search`, `web_fetch` |
| Agent | `delegate`, `ask_user` |
| Memory | `store_memory`, `recall_memory` |
| Skills | `list_skills`, `view_skill`, `create_skill` |

### Memory System

AutoSci remembers across sessions:

- **Episodic**: What happened (experiment results, failures)
- **Semantic**: Domain knowledge (dataset properties, method comparisons)
- **Procedural**: Learned workflows (effective procedures)

Memories are automatically extracted via LLM reflection after each session, and relevant memories are injected into the system prompt at the start of each new session.

### Skill System

Skills are reusable research procedure templates. 3 built-in:

- `literature_review` — systematic review process
- `experiment_design` — rigorous experiment design checklist
- `data_analysis` — structured analysis workflow

The agent can also create new skills during research (`create_skill` tool).

### Session Storage

Every session is stored in two formats:
- **SQLite** (`~/.autosci/sessions.db`) — for fast queries and search
- **Markdown** (`./sessions/`) — human-readable, git-friendly

## Architecture

```
Entry (CLI/REPL)
    │
    ├── Runtime: AgentRunner (while-loop), LLMClient, PromptBuilder, ErrorHandler
    │
    ├── Agents: MainAgent + 5 subagents (self-registering)
    │
    └── Capabilities: Tools (15), Context compression, Memory, Skills, Storage
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## Project Structure

```
~/.autosci/                    # User workspace (created by autosci --init)
├── config.yaml                # LLM and runtime configuration
├── memory/                    # Persistent memories
│   ├── episodic/
│   ├── semantic/
│   └── procedural/
├── skills/                    # Custom skills
└── sessions.db                # Session database

./sessions/                    # Markdown session exports (per project)
```

## Requirements

- Python 3.10+
- An LLM API key (OpenAI, Anthropic, or compatible)

## License

MIT
