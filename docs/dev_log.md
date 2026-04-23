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
