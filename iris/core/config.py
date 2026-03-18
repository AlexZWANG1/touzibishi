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
    Example: get("scoring.weights.fundamental_quality") → 0.25
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


def load_soul() -> str:
    """Load the Prompt layer from soul/*.md files."""
    soul_dir = Path(__file__).parent.parent / "soul"
    parts = []
    for filename in ("v0.1.md", "role.md", "analysis_guide.md"):
        path = soul_dir / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    if not parts:
        return "# IRIS Investment Soul\nAnalyze investments rigorously. Every claim needs evidence."
    return "\n\n---\n\n".join(parts)


DB_PATH = os.getenv("IRIS_DB_PATH", "./iris.db")
