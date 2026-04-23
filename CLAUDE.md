# AUTOSCI Agent Development Rules

You are developing **autosci**, an agent framework for end-to-end scientific research tasks.
Strictly follow the rules below during development.

## 1. Tech Stack

- **Language**: Python 3.10+
- **Package Manager**: pip (with `requirements.txt` for dependencies)
- **Testing**: pytest
- **Code Style**: ruff (lint + format), line length 120
- **Type Annotations**: required for all public interfaces (function signatures, class attributes); internal helpers optional
- **Commit Messages**: English, conventional commits format (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)
- **Git Branching**: `main` (stable) + `feature/*` branches; merge via PR or fast-forward

## 2. Development Methodology

### Core Principle: Design Before Code

For any change involving architecture, module boundaries, protocols, storage, memory, context management, tool system, or skill mechanism:

1. Analyze the problem
2. Design the solution (document in `reference_designs/` or `docs/decisions/`)
3. Present the design for my review
4. Revise based on my feedback
5. Implement in code

**When to skip the full process:** changes under 50 lines within a single file that do not alter any module interface may be implemented directly, with a brief note in the commit message.

### Development Habits

- Commit at appropriate intervals; each commit should be a coherent, reviewable unit
- Keep documentation in sync with code changes
- Design structure first, then code
- Develop module by module; keep modules decoupled

## 3. Project Directory Structure

```text
autosci-2/
├── docs/                                  # Development records
│   ├── architecture.md                    # Architecture overview, module responsibilities, current status
│   ├── decisions/                         # Architecture Decision Records (ADR), numbered: 001-xxx.md
│   └── dev_log.md                         # Append-only development log
│
├── reference_designs/                     # Reference analysis & design decisions
│   ├── project_reading/                   # Reading notes on reference projects
│   └── topics/                            # Per-topic analysis, created as needed
│       └── {topic}_analysis.md            # e.g., agent_loop_analysis.md, context_management_analysis.md
│
├── src/                                   # Framework source code
│   └── autosci/
│       ├── agents/
│       │   ├── main_agent/
│       │   └── subagents/
│       ├── runtime/                       # Agent loop, scheduling, entry point
│       ├── protocols/                     # Inter-agent communication, task schemas
│       ├── tools/                         # Tool registration and invocation
│       ├── context/                       # Context management and compression
│       ├── storage/                       # Session storage, trace storage
│       ├── memory/                        # Short-term / episodic / persistent memory
│       ├── skills/                        # Skill discovery, registration, invocation
│       ├── configs/                       # Configuration files and defaults
│       └── utils/                         # Common utilities
│
├── tests/                                 # Tests (mirrors src/ structure)
├── scripts/                               # Launch, debug, helper scripts
├── requirements.txt
├── README.md
└── CLAUDE.md
```

Rules:

- `docs/` — development records only, no source code
- `reference_designs/` — analysis and design decisions only, no implementation code
- `src/` — framework code only, no process documents
- `tests/` — test code only, mirrors `src/` module structure
- Create files on demand; do not pre-create empty placeholder files

## 4. Reference Projects

| Project | Path | Role |
|---------|------|------|
| hermes-agent | `/mnt/20t/wxh/hermes-agent` | **Primary reference** |
| claude-code-source | `/mnt/20t/wxh/claude-code-source` | Supplementary |
| ResearchClaw | `/mnt/20t/wxh/ResearchClaw` | Supplementary |
| ResearchHarness | `/mnt/20t/wxh/ResearchHarness` | Supplementary |
| EvoScientist | `/mnt/20t/wxh/EvoScientist` | Supplementary |

hermes-agent is the primary reference. Others are used for comparative analysis on specific design topics.

## 5. Analysis & Design Order

### Phase 1: Understand hermes-agent holistically

Before writing any core code, read and understand hermes-agent's:

- Overall framework and module decomposition
- Agent loop organization
- State and context flow
- Memory / storage / tool / skill mechanisms

### Phase 2: Define autosci's overall architecture

Based on Phase 1, determine:

- Module decomposition and directory structure
- Main agent / subagent relationships
- Core runtime organization
- Key interface boundaries

Document in `docs/architecture.md`. Must be reviewed and confirmed before proceeding.

### Phase 3: Topic-by-topic deep design

When entering a specific module, do targeted reading of all 5 reference projects on that topic. Produce a `{topic}_analysis.md` in `reference_designs/topics/` covering:

- How each project handles it
- Pros and cons
- The choice for autosci and rationale

Key topics include (not limited to):

- Agent architecture
- Agent loop
- Inter-agent communication
- Tool system
- Context management
- Session storage
- Memory / evolution
- Skill mechanism

## 6. Architecture Direction

- Primary reference: **hermes-agent style**
- Agent loop: **while-loop**
- Architecture: **main agent + subagents**, dynamically invoked based on task needs
- Research workflow is NOT hardcoded; the agent decides the flow
- Must support:
  - Well-defined tool set and invocation interface
  - Context management with compression
  - Session storage
  - Memory mechanism with evolution capability
  - Skill mechanism
- Design principles: **minimal, decoupled, extensible**

## 7. Execution Checklist

When starting any task:

1. Check current project structure and existing docs
2. Identify which topic / module the task belongs to
3. If needed, read relevant parts of reference projects
4. Update design docs before modifying code (for non-trivial changes)
5. After completion, update `docs/dev_log.md` and commit

## 8. Dependency Policy

- Prefer standard library where sufficient
- Minimize third-party dependencies; each new dependency should be justified
- Pin versions in `requirements.txt`
- No vendored copies of libraries; always install via pip
