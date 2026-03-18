import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from core.schemas import Observation, Hypothesis, Driver, KillCriterion
from tools.retrieval import SQLiteRetriever, cosine_similarity


def make_obs(id: str, relevance: float = 0.8) -> Observation:
    return Observation(
        id=id, subject="NVDA",
        claim=f"Claim {id}", time=datetime(2026, 1, 1),
        source="test", fact_or_view="fact",
        relevance=relevance, citation="...",
        extracted_at=datetime.now(), extracted_by="test"
    )


def test_save_and_query_observation(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    r.save_observation(make_obs("obs_001"))
    results = r.query_observations(subject="NVDA")
    assert len(results) == 1
    assert results[0].id == "obs_001"


def test_query_with_min_relevance(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    r.save_observation(make_obs("obs_low", relevance=0.8))
    results = r.query_observations(subject="NVDA", min_relevance=0.9)
    assert len(results) == 0


def test_save_and_get_hypothesis(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    hyp = Hypothesis(
        id="hyp_001", thesis="Test thesis", company="NVDA",
        timeframe="12 months",
        drivers=[
            Driver(name="d1", description="x", current_assessment="ok"),
            Driver(name="d2", description="y", current_assessment="ok"),
            Driver(name="d3", description="z", current_assessment="ok"),
        ],
        kill_criteria=[KillCriterion(description="revenue drops 30%")],
        confidence=60.0,
        created_at=datetime.now(), last_updated=datetime.now()
    )
    r.save_hypothesis(hyp)
    loaded = r.get_hypothesis("hyp_001")
    assert loaded is not None
    assert loaded.company == "NVDA"
    assert len(loaded.drivers) == 3


# ---- Task 1: embeddings table ----

def test_vector_index_creates_table(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
        ).fetchall()
    assert len(tables) == 1


# ---- Task 2: cosine similarity ----

def test_cosine_similarity_identical():
    a = [1.0, 2.0, 3.0]
    assert cosine_similarity(a, a) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_opposite():
    a = [1.0, 2.0, 3.0]
    b = [-1.0, -2.0, -3.0]
    assert cosine_similarity(a, b) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector():
    a = [0.0, 0.0, 0.0]
    b = [1.0, 2.0, 3.0]
    assert cosine_similarity(a, b) == 0.0


# ---- Task 3: _embed, save_embedding, semantic_search ----

def _mock_embed(texts):
    results = []
    for t in texts:
        h = hash(t) % 1000
        results.append([h / 1000, (h * 7 % 1000) / 1000, (h * 13 % 1000) / 1000])
    return results


def test_semantic_search_returns_ranked_results(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed):
        r.save_embedding("obs_1", "NVDA revenue grew 78% in data center", "observation")
        r.save_embedding("obs_2", "AMD launched MI300X competitor chip", "observation")
        r.save_embedding("obs_3", "Federal Reserve held rates steady", "observation")
        results = r.semantic_search("NVDA data center revenue growth", top_k=2)
    assert len(results) <= 2
    assert all("id" in res and "score" in res for res in results)


def test_semantic_search_empty_db(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed):
        results = r.semantic_search("anything", top_k=5)
    assert results == []


def test_save_embedding_stores_row(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed):
        r.save_embedding("emb_1", "test content", "observation")
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        rows = conn.execute("SELECT id, content, source_type FROM embeddings WHERE id = 'emb_1'").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "test content"
    assert rows[0][2] == "observation"


def test_semantic_search_filters_by_source_type(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed):
        r.save_embedding("obs_1", "NVDA revenue data", "observation")
        r.save_embedding("hyp_1", "NVDA bull thesis", "hypothesis")
        results = r.semantic_search("NVDA", top_k=5, source_type="hypothesis")
    assert all(res["source_type"] == "hypothesis" for res in results)


# ---- Task 4: auto-embed on save ----

def test_save_observation_auto_embeds(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed) as mock_emb:
        r.save_observation(make_obs("obs_auto"))
    mock_emb.assert_called_once()
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        rows = conn.execute("SELECT id FROM embeddings WHERE id = 'obs_auto'").fetchall()
    assert len(rows) == 1


def test_save_hypothesis_auto_embeds(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    hyp = Hypothesis(
        id="hyp_auto", thesis="AI spending will accelerate", company="NVDA",
        timeframe="12 months",
        drivers=[
            Driver(name="d1", description="x", current_assessment="ok"),
            Driver(name="d2", description="y", current_assessment="ok"),
            Driver(name="d3", description="z", current_assessment="ok"),
        ],
        kill_criteria=[KillCriterion(description="revenue drops 30%")],
        confidence=70.0,
        created_at=datetime.now(), last_updated=datetime.now()
    )
    with patch.object(r, '_embed', side_effect=_mock_embed) as mock_emb:
        r.save_hypothesis(hyp)
    mock_emb.assert_called_once()
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        rows = conn.execute("SELECT id FROM embeddings WHERE id = 'hyp_auto'").fetchall()
    assert len(rows) == 1
