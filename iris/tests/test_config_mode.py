"""Tests for mode-aware config loading (load_soul file_list, load_skills skill_names)."""
import tempfile
from pathlib import Path

import yaml

from core.config import load_soul, reset_skill_configs


def test_load_soul_all_files():
    """Without file_list, load_soul returns all .md files."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "a.md").write_text("# A", encoding="utf-8")
        (p / "b.md").write_text("# B", encoding="utf-8")
        result = load_soul(soul_dir=p)
        assert "# A" in result
        assert "# B" in result


def test_load_soul_filtered():
    """With file_list, only specified files are loaded."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "a.md").write_text("# A", encoding="utf-8")
        (p / "b.md").write_text("# B", encoding="utf-8")
        (p / "c.md").write_text("# C", encoding="utf-8")
        result = load_soul(soul_dir=p, file_list=["a.md", "c.md"])
        assert "# A" in result
        assert "# C" in result
        assert "# B" not in result


def test_load_soul_missing_file_ignored():
    """file_list entries that don't exist on disk are silently skipped."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "a.md").write_text("# A", encoding="utf-8")
        result = load_soul(soul_dir=p, file_list=["a.md", "nonexistent.md"])
        assert "# A" in result


# ── load_skills tests ────────────────────────────────────────

from core.skill_loader import load_skills


def _create_skill(base: Path, name: str, tool_name: str):
    """Helper: create a minimal skill directory."""
    skill_dir = base / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f"# {name} skill", encoding="utf-8")
    (skill_dir / "config.yaml").write_text(
        yaml.dump({"name": name}), encoding="utf-8"
    )
    (skill_dir / "tools.py").write_text(
        f"""
from tools.base import Tool, ToolResult, make_tool_schema

SCHEMA = make_tool_schema(
    name="{tool_name}",
    description="test tool",
    properties={{}},
    required=[],
)

def {tool_name}():
    return ToolResult.ok({{}})

def register(context):
    return [Tool({tool_name}, SCHEMA)]
""",
        encoding="utf-8",
    )


def test_load_skills_all():
    """Without skill_names, all skills are loaded."""
    reset_skill_configs()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        _create_skill(p, "alpha", "tool_alpha")
        _create_skill(p, "beta", "tool_beta")
        tools, soul = load_skills(str(p))
        assert len(tools) == 2
        assert "alpha" in soul.lower()
        assert "beta" in soul.lower()


def test_load_skills_filtered():
    """With skill_names, only specified skills are loaded."""
    reset_skill_configs()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        _create_skill(p, "alpha", "tool_alpha")
        _create_skill(p, "beta", "tool_beta")
        _create_skill(p, "gamma", "tool_gamma")
        tools, soul = load_skills(str(p), skill_names=["alpha", "gamma"])
        tool_names = [t.name for t in tools]
        assert "tool_alpha" in tool_names
        assert "tool_gamma" in tool_names
        assert "tool_beta" not in tool_names
        assert "beta" not in soul.lower()
