"""Default configuration with external config file support."""

import copy
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "llm": {
        "provider": "anthropic",        # anthropic | openai | openai-responses | gemini
        "model": "claude-opus-4-6",     # change to your preferred model
        "api_key_env": "ANTHROPIC_API_KEY",  # override default env var for the provider
        "base_url": None,               # None = provider default; set for custom endpoints
        "max_tokens": 8192,
        # Provider examples:
        #   provider: openai          → default: api.openai.com/v1/chat/completions
        #   provider: openai-responses→ default: api.openai.com/v1/responses
        #   provider: gemini          → default: generativelanguage.googleapis.com
        #   provider: anthropic       → default: api.anthropic.com/v1/messages
        # Custom endpoint example (vLLM, Ollama, etc.):
        #   provider: openai
        #   base_url: http://localhost:8000
        #   api_key_env: MY_API_KEY
    },
    "runtime": {
        "max_iterations": 100,
        "context_window": 500000,
        "compression_threshold": 0.75,
    },
    "storage": {
        "db_path": "~/.autosci/sessions.db",
        "export_dir": "./sessions/",
        "auto_export": True,
    },
    "memory": {
        "provider": "file",
        "base_dir": "~/.autosci/memory/",
        "share_with_global": False,   # task mode: use workspace memory by default
    },
    "skills": {
        "dirs": ["~/.autosci/skills/", "./skills/"],
        "include_builtin": True,
    },
    "scientist": {
        "workspace": None,            # set by `autosci scientist --workspace`
        "enable_trajectory": True,    # trajectory recording in scientist mode
        "enable_understanding": True, # task understanding pipeline in scientist mode
    },
}

CONFIG_FILE_PATHS = [
    "~/.autosci/config.yaml",
    "./autosci.yaml",
]


def load_config(overrides: dict = None) -> dict:
    """Load configuration from defaults, external file, and overrides.

    Priority (highest wins):
    1. overrides parameter
    2. External config file (~/.autosci/config.yaml or ./autosci.yaml)
    3. DEFAULT_CONFIG
    """
    config = copy.deepcopy(DEFAULT_CONFIG)

    # Try loading external config file
    file_config = _load_config_file()
    if file_config:
        _deep_merge(config, file_config)

    # Apply overrides
    if overrides:
        _deep_merge(config, overrides)

    return config


def _load_config_file() -> dict | None:
    """Load config from the first existing YAML file."""
    try:
        import yaml
    except ImportError:
        return None

    for path in CONFIG_FILE_PATHS:
        filepath = os.path.expanduser(path)
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    logger.info(f"Loaded config from {filepath}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load config from {filepath}: {e}")

    return None


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base (mutates base)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def create_default_config_file(path: str = None) -> str:
    """Create a default config.yaml file for the user to customize."""
    try:
        import yaml
    except ImportError:
        raise ImportError("pyyaml required: pip install pyyaml")

    path = path or os.path.expanduser("~/.autosci/config.yaml")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return path
