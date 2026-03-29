"""
IRIS config loader.

Loads the Context layer (iris_config.yaml) and the Prompt layer (soul/*.md).
No hardcoded parameter values — all tunable numbers live in the yaml.

Prompt 优先级:
  1. Langfuse 平台 (label=production) — 如果配置了且可用
  2. iris_config.yaml prompts 段 — 本地兜底
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

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
    """Load the Prompt layer — Langfuse first, local files as fallback.

    优先级:
      1. Langfuse: iris-soul-{name} with label=production
      2. 本地 soul/{name}.md 文件

    Args:
        soul_dir: Directory containing soul .md files.
        file_list: If provided, only load these filenames (in order).
                   If None, load all .md files (original behavior).
    """
    soul_dir = soul_dir or Path(__file__).parent.parent / "soul"

    if file_list is not None:
        names = [f.removesuffix(".md") for f in file_list]
    else:
        names = [f.stem for f in sorted(soul_dir.glob("*.md"))]

    parts: list[str] = []
    for name in names:
        # Try Langfuse first
        lf_prompt = get_langfuse_prompt(f"iris-soul-{name}")
        if lf_prompt:
            log.debug("Soul '%s' loaded from Langfuse", name)
            parts.append(lf_prompt)
            continue

        # Fallback to local file
        local = soul_dir / f"{name}.md"
        if local.exists():
            log.debug("Soul '%s' loaded from local file", name)
            parts.append(local.read_text(encoding="utf-8"))

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


# ── Langfuse Prompt Management ──
#
# 工作方式:
#   get_langfuse_prompt("iris-ticker-extraction")
#     → 先从 Langfuse 云端拉 production 版本的 prompt (SDK 内部有缓存，不加延迟)
#     → 拉不到 → 返回 None，调用方用 yaml 兜底
#
# 这样你可以:
#   1. 在 Langfuse 网页上直接改 prompt
#   2. 给新版本打 production 标签 → 线上自动生效
#   3. 不打标签 → 线上继续用旧版本，不受影响

_langfuse_client = None


def _get_langfuse():
    """Lazy-init Langfuse client. Returns None if not configured."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    try:
        from core.tracing import is_enabled
        if not is_enabled():
            return None
        from langfuse import get_client
        _langfuse_client = get_client()
        return _langfuse_client
    except Exception:
        return None


def get_langfuse_prompt(name: str, label: str = "production") -> str | None:
    """Fetch a text prompt from Langfuse by name and label.

    Returns the prompt string, or None if unavailable (not configured,
    network error, prompt doesn't exist, etc.).

    SDK 内部会缓存 prompt，所以这个调用不会给每次请求加延迟。
    """
    client = _get_langfuse()
    if client is None:
        return None
    try:
        prompt = client.get_prompt(name, label=label, type="text")
        return prompt.prompt
    except Exception as e:
        log.debug("Langfuse prompt '%s' fetch failed: %s", name, e)
        return None


def get_prompt(langfuse_name: str, yaml_key: str, default: str = "") -> str:
    """统一的 prompt 获取入口。

    优先级: Langfuse production → yaml → default

    Args:
        langfuse_name: Langfuse 上的 prompt 名字，如 "iris-ticker-extraction"
        yaml_key: iris_config.yaml 里的 dot-path，如 "prompts.ticker_extraction"
        default: 都没有时的硬编码兜底
    """
    # 1. Try Langfuse
    prompt = get_langfuse_prompt(langfuse_name)
    if prompt:
        return prompt

    # 2. Fall back to yaml
    yaml_val = get(yaml_key)
    if yaml_val:
        return str(yaml_val).strip()

    # 3. Hardcoded default
    return default


DB_PATH = os.getenv("IRIS_DB_PATH", "./iris.db")
