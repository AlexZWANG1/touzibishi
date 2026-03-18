from datetime import datetime
from core.schemas import (
    Observation, Driver, KillCriterion, EvidenceCard,
    Hypothesis, ValuationOutput
)


def test_observation_requires_fields():
    obs = Observation(
        id="obs_001",
        subject="NVDA",
        claim="Data center revenue up 78% YoY",
        time=datetime(2026, 2, 21),
        source="NVDA Q4 2026 Earnings",
        fact_or_view="fact",
        relevance=0.95,
        citation="Data Center revenue was $XX billion, up 78%...",
        extracted_at=datetime.now(),
        extracted_by="gpt-4o",
    )
    assert obs.subject == "NVDA"
    assert obs.fact_or_view == "fact"


def test_observation_relevance_range():
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        Observation(
            id="obs_002", subject="NVDA", claim="test",
            time=datetime.now(), source="test", fact_or_view="fact",
            relevance=1.5,
            citation="test", extracted_at=datetime.now(), extracted_by="gpt-4o"
        )


def test_hypothesis_driver_count_limits():
    from pydantic import ValidationError
    import pytest
    drivers = [Driver(name=f"d{i}", description="x", current_assessment="ok")
               for i in range(7)]
    with pytest.raises(ValidationError):
        Hypothesis(
            id="hyp_001", thesis="test", company="NVDA", timeframe="24 months",
            drivers=drivers, kill_criteria=[], confidence=50.0,
            evidence_log=[], created_at=datetime.now(), last_updated=datetime.now()
        )


def test_valuation_output_bull_bear():
    v = ValuationOutput(
        methodology="DCF",
        methodology_reasoning="Stable cash flows",
        fair_value_range=(100.0, 130.0),
        current_price=90.0,
        valuation_gap=0.28,
        key_assumptions=[],
        bull_case={"fair_value": 130.0, "key_assumption": "Revenue 30% growth"},
        bear_case={"fair_value": 100.0, "key_assumption": "Revenue 10% growth"},
    )
    assert v.methodology == "DCF"
    assert v.bull_case["fair_value"] > v.bear_case["fair_value"]
