"""
IRIS config loader.

Loads the Context layer (iris_config.yaml) and the Prompt layer (soul/*.md).
No hardcoded parameter values — all tunable numbers live in the yaml.
"""

import os
from pathlib import Path
from typing import Any

import yaml


_CONFIG_CACHE: dict | None = None

FALLBACK_SOUL = "# IRIS Investment Soul\nAnalyze investments rigorously. Every claim needs evidence."


def _find_config_path() -> Path:
    """Find iris_config.yaml relative to this file."""
    return Path(__file__).parent.parent / "iris_config.yaml"


def load_config(path: str = None) -> dict:
    """Load and cache the Context layer from iris_config.yaml."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and path is None:
        return _CONFIG_CACHE

    config_path = Path(path) if path else _find_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if path is None:
        _CONFIG_CACHE = config
    return config


def reset_config_cache():
    """Clear cache — useful for tests."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def get(key_path: str, default: Any = None) -> Any:
    """
    Dot-path access into config.
    Example: get("harness.max_tool_rounds") → 25
    """
    config = load_config()
    keys = key_path.split(".")
    node = config
    for k in keys:
        if isinstance(node, dict) and k in node:
            node = node[k]
        else:
            return default
    return node


def load_soul(soul_dir: Path = None, file_list: list[str] = None) -> str:
    """Load the Prompt layer from soul/*.md files.

    Args:
        soul_dir: Directory containing soul .md files.
        file_list: If provided, only load these filenames (in order).
                   If None, load all .md files (original behavior).
    """
    soul_dir = soul_dir or Path(__file__).parent.parent / "soul"
    if file_list is not None:
        files = [soul_dir / f for f in file_list if (soul_dir / f).exists()]
    else:
        files = sorted(soul_dir.glob("*.md"))
    parts = [f.read_text(encoding="utf-8") for f in files]
    return "\n\n---\n\n".join(parts) if parts else FALLBACK_SOUL


# ── Skill config registry ──

_skill_configs: dict[str, dict] = {}


def register_skill_config(skill_name: str, config: dict):
    _skill_configs[skill_name] = config


def get_skill_config(skill_name: str, key: str = None, default: Any = None) -> Any:
    cfg = _skill_configs.get(skill_name, {})
    if key is None:
        return cfg
    return cfg.get(key, default)


def reset_skill_configs():
    """Clear skill configs — useful for tests."""
    _skill_configs.clear()


DB_PATH = os.getenv("IRIS_DB_PATH", "./iris.db")
