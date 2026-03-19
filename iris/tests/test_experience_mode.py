"""Tests for experience mode-awareness and methodology field."""
import json
from pathlib import Path
from unittest.mock import patch

from core.config import register_skill_config, reset_skill_configs


def _setup_experience_config():
    """Register minimal experience skill config."""
    reset_skill_configs()
    register_skill_config("experience", {
        "retrieval": {"top_k": 5, "company_boost": 1.0, "sector_boost": 0.7, "semantic_boost": 0.5, "min_confidence": 0.3},
        "update": {"duplicate_threshold": 0.90, "merge_threshold": 0.70},
        "quality": {"max_library_size": 500},
        "reflection": {"min_error_for_warning": 0.03, "min_accuracy_for_golden": 0.02},
        "distillation": {"cross_company_pattern_threshold": 3},
    })


def test_save_experience_with_methodology(tmp_path):
    """save_experience accepts and stores methodology field."""
    _setup_experience_config()

    from skills.experience.tools import save_experience, _library_path

    with patch("skills.experience.tools._library_path", return_value=tmp_path / "exp.json"):
        result = save_experience(
            zone="warning",
            level="factual",
            content="NVDA DC revenue underestimated",
            companies=["NVDA"],
            confidence=0.8,
            methodology={
                "what_i_did": "linear extrapolation of 3yr CAGR",
                "what_went_wrong": "AI adoption is exponential",
                "what_to_do_next": ["check hyperscaler capex", "apply 1.4-1.8x multiplier"],
            },
        )
        assert result.status == "ok"
        assert result.data["action"] == "inserted"

        # Verify methodology stored
        lib = json.loads((tmp_path / "exp.json").read_text())
        entry = lib["experiences"][0]
        assert entry["methodology"]["what_i_did"] == "linear extrapolation of 3yr CAGR"
        assert len(entry["methodology"]["what_to_do_next"]) == 2


def test_save_experience_analysis_mode_strips_zone(tmp_path):
    """In analysis mode, zone and level are stripped from saved entry."""
    _setup_experience_config()
    register_skill_config("_runtime", {"mode": "analysis"})

    from skills.experience.tools import save_experience

    with patch("skills.experience.tools._library_path", return_value=tmp_path / "exp.json"):
        result = save_experience(
            zone="golden",
            level="pattern",
            content="I used linear extrapolation",
            companies=["NVDA"],
            confidence=0.6,
        )
        assert result.status == "ok"

        lib = json.loads((tmp_path / "exp.json").read_text())
        entry = lib["experiences"][0]
        # zone and level should be None
        assert entry.get("zone") is None
        assert entry.get("level") is None


def test_save_experience_learning_mode_keeps_zone(tmp_path):
    """In learning mode, zone and level are preserved."""
    _setup_experience_config()
    register_skill_config("_runtime", {"mode": "learning"})

    from skills.experience.tools import save_experience

    with patch("skills.experience.tools._library_path", return_value=tmp_path / "exp.json"):
        result = save_experience(
            zone="warning",
            level="factual",
            content="Revenue was underestimated by 43pp",
            companies=["NVDA"],
            confidence=0.8,
        )
        assert result.status == "ok"

        lib = json.loads((tmp_path / "exp.json").read_text())
        entry = lib["experiences"][0]
        assert entry["zone"] == "warning"
        assert entry["level"] == "factual"
