"""
IRIS Skill Loader — auto-discovers skill folders and registers tools + soul text.

Each skill folder contains:
  - SKILL.md  → soul text (instructions for the AI)
  - tools.py  → register(context) -> list[Tool]  OR  TOOLS: list[Tool]
  - config.yaml → skill-specific parameters
"""

import logging
from pathlib import Path
from typing import Any

import importlib.util
import yaml

from core.config import register_skill_config, get_langfuse_prompt
from tools.base import Tool

log = logging.getLogger(__name__)


class SkillLoadError(Exception):
    pass


def load_skills(
    skills_dir: str,
    context: dict | None = None,
    skill_names: list[str] | None = None,
) -> tuple[list[Tool], str]:
    """
    Scan skills/ folder. For each subfolder:
      - SKILL.md → collected into skill_soul text
      - tools.py → register(context) or TOOLS list → tools
      - config.yaml → loaded into skill-specific config namespace

    Args:
        skill_names: If provided, only load these skill directories.
                     If None, load all (original behavior).

    Returns (all_skill_tools, combined_skill_soul_text).
    """
    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return [], ""

    all_tools: list[Tool] = []
    soul_parts: list[str] = []
    seen_tool_names: set[str] = set()

    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
            continue
        if skill_names is not None and skill_dir.name not in skill_names:
            continue

        skill_name = skill_dir.name

        # Load SKILL.md — Langfuse first, local file fallback
        lf_prompt = get_langfuse_prompt(f"iris-skill-{skill_name}")
        if lf_prompt:
            log.debug("Skill '%s' SKILL.md loaded from Langfuse", skill_name)
            soul_parts.append(lf_prompt)
        else:
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                log.debug("Skill '%s' SKILL.md loaded from local file", skill_name)
                soul_parts.append(skill_md.read_text(encoding="utf-8"))

        # Load config.yaml
        config_yaml = skill_dir / "config.yaml"
        if config_yaml.exists():
            with open(config_yaml, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            register_skill_config(skill_name, cfg)

        # Load tools.py
        tools_py = skill_dir / "tools.py"
        if tools_py.exists():
            tools = _load_skill_tools(tools_py, skill_name, context)
            for tool in tools:
                if tool.name in seen_tool_names:
                    raise SkillLoadError(
                        f"Duplicate tool name '{tool.name}' in skill '{skill_name}'"
                    )
                seen_tool_names.add(tool.name)
            all_tools.extend(tools)

    combined_soul = "\n\n---\n\n".join(soul_parts) if soul_parts else ""
    return all_tools, combined_soul


def _load_skill_tools(
    tools_py: Path, skill_name: str, context: dict | None
) -> list[Tool]:
    """Import a skill's tools.py and extract Tool instances."""
    spec = importlib.util.spec_from_file_location(
        f"skills.{skill_name}.tools", str(tools_py)
    )
    if spec is None or spec.loader is None:
        return []

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise SkillLoadError(f"Failed to load skill '{skill_name}': {e}") from e

    # Prefer register(context) function over static TOOLS list
    if hasattr(module, "register") and callable(module.register):
        tools = module.register(context or {})
        if not isinstance(tools, list):
            raise SkillLoadError(
                f"Skill '{skill_name}' register() must return list[Tool], got {type(tools)}"
            )
        return tools

    if hasattr(module, "TOOLS"):
        tools = module.TOOLS
        if not isinstance(tools, list):
            raise SkillLoadError(
                f"Skill '{skill_name}' TOOLS must be list[Tool], got {type(tools)}"
            )
        return tools

    return []
