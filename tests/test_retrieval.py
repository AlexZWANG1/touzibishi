from datetime import datetime
from core.schemas import Observation, Hypothesis, Driver, KillCriterion
from tools.retrieval import SQLiteRetriever


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
