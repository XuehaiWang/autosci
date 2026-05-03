# AutoSci Configuration Guide

## Overview

AutoSci uses a layered configuration system:

1. **Built-in defaults** — sensible defaults for all settings
2. **Config file** — `~/.autosci/config.yaml` or `./autosci.yaml` (project-level)
3. **CLI arguments** — override specific settings per invocation

Priority: CLI args > config file > defaults.

---

## Quick Start

```bash
# 1. Initialize config
autosci --init

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Run
autosci "Your task here"
```

---

## LLM Provider Configuration

AutoSci supports 4 LLM providers. Each provider connects to its official API by default, or you can point it to a custom endpoint.

### Config File Format

Edit `~/.autosci/config.yaml`:

```yaml
llm:
  provider: anthropic              # anthropic | openai | openai-responses | gemini
  model: claude-opus-4-6           # model name
  api_key_env: ANTHROPIC_API_KEY   # which env var holds the API key
  base_url: null                   # null = use official endpoint
  max_tokens: 8192                 # max output tokens per response
```

### Provider Reference

#### Anthropic (default)

Uses the Anthropic Messages API (`/v1/messages`).

```yaml
llm:
  provider: anthropic
  model: claude-opus-4-6          # or claude-sonnet-4-6, claude-haiku-4-5, etc.
  api_key_env: ANTHROPIC_API_KEY
```

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

If `api_key_env` is not specified, defaults to `ANTHROPIC_API_KEY`.

**Available models**: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`, etc.

---

#### OpenAI (Chat Completions)

Uses the OpenAI Chat Completions API (`/v1/chat/completions`).

```yaml
llm:
  provider: openai
  model: gpt-5.4
  api_key_env: OPENAI_API_KEY
```

```bash
export OPENAI_API_KEY=sk-...
```

If `api_key_env` is not specified, defaults to `OPENAI_API_KEY`.

**Available models**: `gpt-5.4`, `gpt-5.4-mini`, `gpt-4.1`, `o3`, `o4-mini`, etc.

---

#### OpenAI Responses API

Uses the newer OpenAI Responses API (`/v1/responses`).

```yaml
llm:
  provider: openai-responses
  model: gpt-5.4
  api_key_env: OPENAI_API_KEY
```

```bash
export OPENAI_API_KEY=sk-...
```

If `api_key_env` is not specified, defaults to `OPENAI_API_KEY`.

---

#### Google Gemini

Uses the Google Gemini API (`/v1beta/models/{model}:generateContent`).

```yaml
llm:
  provider: gemini
  model: gemini-2.5-flash          # or gemini-2.5-pro
  api_key_env: GEMINI_API_KEY
```

```bash
export GEMINI_API_KEY=AIza...
```

Get your API key from [Google AI Studio](https://aistudio.google.com/apikey).

If `api_key_env` is not specified, defaults to `GEMINI_API_KEY`.

**Available models**: `gemini-2.5-flash`, `gemini-2.5-pro`, etc.

---

### Custom Endpoints

You can use any OpenAI-compatible server (vLLM, Ollama, LiteLLM, etc.) by setting `base_url`:

#### vLLM / Local Server

```yaml
llm:
  provider: openai
  model: Qwen/Qwen3-72B
  base_url: http://localhost:8000
  api_key_env: VLLM_API_KEY       # or set to any non-empty value
```

```bash
export VLLM_API_KEY=dummy          # vLLM doesn't require a real key
```

#### Ollama

```yaml
llm:
  provider: openai
  model: llama3
  base_url: http://localhost:11434/v1
  api_key_env: OLLAMA_KEY
```

```bash
export OLLAMA_KEY=ollama            # Ollama doesn't require a real key
```

#### Anthropic Proxy

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  base_url: https://my-proxy.example.com
  api_key_env: MY_PROXY_KEY
```

#### Gemini Proxy

```yaml
llm:
  provider: gemini
  model: gemini-2.5-flash
  base_url: https://my-gemini-proxy.com
  api_key_env: MY_PROXY_KEY
```

---

## CLI Model Override

You can override the model for a single run without editing the config:

```bash
# Assistant mode
autosci -m claude-sonnet-4-6 "Explain quantum computing"

# Scientist mode
autosci scientist -m gemini-2.5-pro "Analyze this dataset" -w ./workspace

# Bench mode
autosci-bench -m "task instructions" -w ./workspace
```

Note: `-m` only overrides the model name. The provider and base_url still come from the config file.

---

## Full Config Reference

```yaml
# ~/.autosci/config.yaml

llm:
  provider: anthropic              # anthropic | openai | openai-responses | gemini
  model: claude-opus-4-6           # model name (provider-specific)
  api_key_env: ANTHROPIC_API_KEY   # env var name that holds the API key
  base_url: null                   # null = official endpoint; set for custom servers
  max_tokens: 8192                 # max output tokens per LLM response

runtime:
  max_iterations: 100              # max agent loop iterations
  context_window: 500000           # context window size (tokens)
  compression_threshold: 0.75      # compress when usage exceeds this ratio

storage:
  db_path: ~/.autosci/sessions.db  # session database location
  export_dir: ./sessions/          # session export directory
  auto_export: true                # auto-export sessions on completion

memory:
  provider: file                   # memory storage backend
  base_dir: ~/.autosci/memory/     # memory file storage location
  share_with_global: false         # share memory across workspaces

skills:
  dirs:                            # skill search directories
    - ~/.autosci/skills/
    - ./skills/
  include_builtin: true            # include built-in skills

tools:
  mineru_token_env: MINERU_TOKEN   # env var for MinerU PDF parsing token

scientist:
  workspace: null                  # set by --workspace flag
  enable_trajectory: true          # record execution trajectory
  enable_understanding: true       # run task understanding pipeline
```

---

## Environment Variables Summary

| Variable | Used By | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | `anthropic` provider | Anthropic API key |
| `OPENAI_API_KEY` | `openai`, `openai-responses` providers | OpenAI API key |
| `GEMINI_API_KEY` | `gemini` provider | Google AI Studio API key |
| `MINERU_TOKEN` | `read_pdf` tool | MinerU cloud PDF parsing token |

You can use any env var name by setting `api_key_env` (for LLM) or `mineru_token_env` (for PDF) in the config.

---

## Config File Locations

AutoSci searches for config files in this order:

1. `~/.autosci/config.yaml` — global user config
2. `./autosci.yaml` — project-level config (overrides global)

Run `autosci --init` to generate the global config with defaults.