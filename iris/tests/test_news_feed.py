"""Tests for news_feed tool — filter logic, formatting, validation."""
import pytest
from datetime import datetime


# ── Topic filter tests ──

def test_filter_by_topic_single_token_match():
    from tools.news_feed import _filter_by_topic

    items = [
        {"title": "NVIDIA launches new AI chip", "summary": "Details inside"},
        {"title": "Apple releases iOS update", "summary": "Bug fixes"},
        {"title": "AMD competes in GPU market", "summary": "NVIDIA rival"},
    ]
    result = _filter_by_topic(items, "NVIDIA")
    assert len(result) == 2
    assert result[0]["title"] == "NVIDIA launches new AI chip"
    assert result[1]["title"] == "AMD competes in GPU market"


def test_filter_by_topic_multi_token_or_match():
    from tools.news_feed import _filter_by_topic

    items = [
        {"title": "NVIDIA earnings beat", "summary": "Strong quarter"},
        {"title": "Apple AI strategy", "summary": "New models"},
        {"title": "Tesla delivery numbers", "summary": "Record quarter"},
    ]
    # OR logic: matches "NVIDIA" OR "Apple"
    result = _filter_by_topic(items, "NVIDIA Apple")
    assert len(result) == 2


def test_filter_by_topic_case_insensitive():
    from tools.news_feed import _filter_by_topic

    items = [{"title": "nvidia gpu sales", "summary": ""}]
    result = _filter_by_topic(items, "NVIDIA")
    assert len(result) == 1


def test_filter_by_topic_empty_returns_all():
    from tools.news_feed import _filter_by_topic

    items = [{"title": "A", "summary": ""}, {"title": "B", "summary": ""}]
    result = _filter_by_topic(items, "")
    assert len(result) == 2


def test_filter_by_topic_no_match_returns_empty():
    from tools.news_feed import _filter_by_topic

    items = [{"title": "Apple news", "summary": "iOS update"}]
    result = _filter_by_topic(items, "NVIDIA")
    assert len(result) == 0


# ── Result item formatting ──

def test_to_result_item_full_fields():
    from tools.news_feed import _to_result_item

    class FakeItem:
        title = "Test Article"
        url = "https://example.com"
        source_name = "Hacker News"
        description = "A test article"
        author = "testuser"
        score = 42
        published = datetime(2026, 4, 5, 10, 30)
        extra = {}

    result = _to_result_item(FakeItem(), "hackernews")
    assert result["title"] == "Test Article"
    assert result["url"] == "https://example.com"
    assert result["source"] == "hackernews"
    assert result["source_name"] == "Hacker News"
    assert result["score"] == 42
    assert result["author"] == "testuser"
    assert "2026-04-05" in result["published"]


def test_to_result_item_truncates_long_summary():
    from tools.news_feed import _to_result_item

    class FakeItem:
        title = "Test"
        url = "https://example.com"
        source_name = "Reddit"
        description = "x" * 1000
        author = ""
        score = None
        published = None
        extra = {}

    result = _to_result_item(FakeItem(), "reddit")
    assert len(result["summary"]) <= 500


# ── Validation ──

def test_invalid_source_returns_error():
    from tools.news_feed import news_feed

    result = news_feed(sources=["invalid_source"])
    assert result.status == "error"
    assert "Unknown source" in result.error


def test_empty_sources_returns_error():
    from tools.news_feed import news_feed

    result = news_feed(sources=[])
    assert result.status == "error"
