"""Default configuration for autosci."""

import copy


DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "claude-sonnet-4-20250514",
        "api_key_env": "TUZI_API_KEY",
        "base_url": "https://coding.tu-zi.com/v1",
        "max_tokens": 8192,
    },
    "runtime": {
        "max_iterations": 100,
        "context_window": 200000,
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
    },
    "skills": {
        "dirs": ["~/.autosci/skills/", "./skills/"],
    },
}


def load_config(overrides: dict = None) -> dict:
    """Load configuration with optional overrides.

    Overrides are merged at the section level (one level deep).
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    if overrides:
        for section, values in overrides.items():
            if section in config and isinstance(config[section], dict) and isinstance(values, dict):
                config[section].update(values)
            else:
                config[section] = values
    return config
