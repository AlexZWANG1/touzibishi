# news_feed Tool Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `news_feed` tool to IRIS that fetches from the user's curated RSS-Notion sources (HN, Reddit, arXiv, RSS, YouTube, GitHub Trending) during investment analysis.

**Architecture:** Single file `iris/tools/news_feed.py` imports RSS-Notion source classes via `sys.path`, runs them concurrently with `asyncio.gather()`, filters by topic keyword, and returns unified results. Enrichment disabled for speed. Registered as a standard IRIS tool.

**Tech Stack:** Python asyncio, RSS-Notion source layer (feedparser, praw, arxiv, aiohttp, beautifulsoup4)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `iris/tools/news_feed.py` | Tool function, schema, async fetch coordinator, topic filter |
| Create | `iris/tests/test_news_feed.py` | Unit tests for filter, format, validation, error handling |
| Modify | `iris/main.py:13-31` | Add import + register tool in `core_tools` |
| Modify | `iris/iris_config.yaml:18-20` | Add `news_feed: 6000` to `tool_compress_overrides` |
| Modify | `iris/iris_config.yaml:43-59` | Add `news_feed` triggers |
| Modify | `iris/iris_config.yaml:145-166` | Add `news_feed` to analysis mode `always_exposed_tools` |
| Modify | `iris/iris_config.yaml:172-190` | Add `news_feed` to learning mode `always_exposed_tools` |

---

## Chunk 1: Core Implementation

### Task 1: Write unit tests for topic filter and result formatting

**Files:**
- Create: `iris/tests/test_news_feed.py`

- [ ] **Step 1: Write test file with filter and format tests**

```python
"""Tests for news_feed tool — filter logic, formatting, validation."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
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
```

- [ ] **Step 2: Run tests to verify they fail (module not found)**

Run: `cd D:/项目开发/二级投研自动化/iris && python -m pytest tests/test_news_feed.py -v 2>&1 | head -30`
Expected: ModuleNotFoundError for `tools.news_feed`

### Task 2: Implement `iris/tools/news_feed.py`

**Files:**
- Create: `iris/tools/news_feed.py`

- [ ] **Step 3: Create the tool file**

```python
"""news_feed — fetches from curated RSS-Notion sources for IRIS analysis."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any

from tools.base import ToolResult, make_tool_schema

logger = logging.getLogger(__name__)

# ── RSS-Notion path ──
_RSS_NOTION_PATH = os.environ.get("RSS_NOTION_PATH", "D:/项目开发/RSS-Notion")
if _RSS_NOTION_PATH not in sys.path:
    sys.path.insert(0, _RSS_NOTION_PATH)

# ── Source map: key → (module, class_name, display_name) ──
_SOURCE_MAP: dict[str, tuple[str, str, str]] = {
    "hackernews": ("sources.hackernews", "HackerNewsSource", "Hacker News"),
    "reddit":     ("sources.reddit",     "RedditSource",     "Reddit"),
    "arxiv":      ("sources.arxiv_source", "ArxivSource",    "arXiv"),
    "rss":        ("sources.rss_fetcher", "RSSFetcher",      "RSS"),
    "youtube":    ("sources.youtube",     "YouTubeSource",    "YouTube"),
    "github":     ("sources.github_trending", "GitHubTrendingSource", "GitHub Trending"),
}

# ── Default configs per source (enrichment disabled for speed) ──
_SOURCE_CONFIGS: dict[str, dict] = {
    "hackernews": {"max_items": 15, "enrich": False},
    "reddit":     {"max_items": 10, "subreddits": ["LocalLLaMA", "MachineLearning"], "enrich": False},
    "arxiv":      {"max_items": 10, "categories": ["cs.AI", "cs.CL", "cs.LG"]},
    "rss":        {"max_items": 30, "max_age_days": 3, "enrich": False},
    "youtube":    {"max_items": 10, "max_age_days": 7, "enrich": False},
    "github":     {"max_items": 10, "language": "python"},
}

VALID_SOURCES = list(_SOURCE_MAP.keys())

# ── Schema ──
NEWS_FEED_SCHEMA = make_tool_schema(
    name="news_feed",
    description=(
        "Fetch recent items from curated information sources. "
        "Use this during analysis to gather tech sentiment (hackernews), "
        "community reactions (reddit), research trends (arxiv), "
        "news articles (rss), video content (youtube), or open-source trends (github). "
        f"Valid sources: {', '.join(VALID_SOURCES)}."
    ),
    properties={
        "sources": {
            "type": "array",
            "items": {"type": "string", "enum": VALID_SOURCES},
            "description": f"Which sources to query. Choose from: {', '.join(VALID_SOURCES)}",
        },
        "topic": {
            "type": "string",
            "description": "Optional keyword(s) to filter results (OR-matched against title and summary)",
            "default": "",
        },
        "limit": {
            "type": "integer",
            "description": "Max items to return per source (default 10)",
            "default": 10,
        },
    },
    required=["sources"],
)


# ── Public tool function ──

def news_feed(sources: list[str], topic: str = "", limit: int = 10) -> ToolResult:
    """Fetch from RSS-Notion sources, filter by topic, return unified results."""
    if not sources:
        return ToolResult.fail("sources list is empty. Provide at least one source.")

    # Validate source names
    invalid = [s for s in sources if s not in _SOURCE_MAP]
    if invalid:
        return ToolResult.fail(
            f"Unknown source: {', '.join(invalid)}. Valid: {', '.join(VALID_SOURCES)}"
        )

    # Reset RSS-Notion's module-level semaphore to avoid cross-loop errors
    try:
        from sources import content_fetcher
        content_fetcher._semaphore = None
    except ImportError:
        pass

    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(_fetch_all(sources, topic, limit))
    except Exception as e:
        logger.exception("news_feed failed")
        return ToolResult.fail(f"news_feed error: {e}", recoverable=True)
    finally:
        loop.close()

    if results.get("_all_failed"):
        return ToolResult.fail(
            "All requested sources failed. Check logs for details.",
            recoverable=True,
        )

    return ToolResult.ok(results)


# ── Async internals ──

async def _fetch_all(
    sources: list[str], topic: str, limit: int
) -> dict[str, Any]:
    tasks = [_fetch_source(s) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[dict] = []
    sources_queried: list[str] = []
    all_failed = True

    for source_key, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.warning("news_feed source %s failed: %s", source_key, result)
            continue
        if result:
            all_failed = False
            sources_queried.append(source_key)
            all_items.extend(result)

    # Filter by topic
    filtered = _filter_by_topic(all_items, topic)

    # Truncate per source
    per_source_counts: dict[str, int] = {}
    final_items: list[dict] = []
    for item in filtered:
        src = item.get("source", "")
        per_source_counts.setdefault(src, 0)
        if per_source_counts[src] < limit:
            final_items.append(item)
            per_source_counts[src] += 1

    output = {
        "items": final_items,
        "total": len(final_items),
        "sources_queried": sources_queried,
    }
    if all_failed and sources:
        output["_all_failed"] = True
    return output


async def _fetch_source(source_key: str) -> list[dict]:
    """Instantiate and call a single RSS-Notion source."""
    module_path, class_name, display_name = _SOURCE_MAP[source_key]
    config = dict(_SOURCE_CONFIGS.get(source_key, {}))

    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
    except (ImportError, AttributeError) as e:
        raise RuntimeError(
            f"Cannot import {class_name} from {module_path}. "
            f"Is RSS-Notion at {_RSS_NOTION_PATH}? Error: {e}"
        )

    source = cls(config)
    source_result = await source.fetch()

    # source_result is a SourceResult with .items list
    items = getattr(source_result, "items", [])
    return [_to_result_item(item, source_key) for item in items]


def _filter_by_topic(items: list[dict], topic: str) -> list[dict]:
    """OR-match: any whitespace-split token in title or summary (case-insensitive)."""
    if not topic or not topic.strip():
        return items

    tokens = topic.lower().split()
    filtered = []
    for item in items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        if any(tok in text for tok in tokens):
            filtered.append(item)
    return filtered


def _to_result_item(source_item: Any, source_key: str) -> dict:
    """Convert a SourceItem to a flat dict for the tool result."""
    published = getattr(source_item, "published", None)
    pub_str = ""
    if isinstance(published, datetime):
        pub_str = published.isoformat()
    elif published:
        pub_str = str(published)

    description = getattr(source_item, "description", "") or ""
    summary = description[:500] if len(description) > 500 else description

    return {
        "title": getattr(source_item, "title", ""),
        "url": getattr(source_item, "url", ""),
        "source": source_key,
        "source_name": getattr(source_item, "source_name", _SOURCE_MAP.get(source_key, ("", "", ""))[2]),
        "summary": summary,
        "score": getattr(source_item, "score", None),
        "author": getattr(source_item, "author", ""),
        "published": pub_str,
    }
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `cd D:/项目开发/二级投研自动化/iris && python -m pytest tests/test_news_feed.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit core implementation + tests**

```bash
cd D:/项目开发/二级投研自动化
git add iris/tools/news_feed.py iris/tests/test_news_feed.py
git commit -m "feat: add news_feed tool — fetches from curated RSS-Notion sources"
```

---

## Chunk 2: Registration and Config

### Task 3: Register news_feed in main.py

**Files:**
- Modify: `iris/main.py:13-31` (imports) and `iris/main.py:103-112` (core_tools)

- [ ] **Step 6: Add import**

After line 31 (`from tools.transcripts import transcript, TRANSCRIPT_SCHEMA`), add:
```python
from tools.news_feed import news_feed, NEWS_FEED_SCHEMA
```

- [ ] **Step 7: Add to core_tools list**

After line 112 (`Tool(transcript, TRANSCRIPT_SCHEMA),`), add:
```python
        Tool(news_feed, NEWS_FEED_SCHEMA),
```

### Task 4: Update iris_config.yaml

**Files:**
- Modify: `iris/iris_config.yaml`

- [ ] **Step 8: Add compress override**

In `tool_compress_overrides:` (line 18), add:
```yaml
    news_feed: 6000
```

- [ ] **Step 9: Add tool triggers**

In `tool_triggers:` (line 43), add:
```yaml
    news_feed: ["新闻", "news", "HN", "Reddit", "arXiv", "热点", "trending", "社区反馈", "信息源"]
```

- [ ] **Step 10: Add to analysis mode always_exposed_tools**

In `modes.analysis.always_exposed_tools` (after `- transcript` at line 163), add:
```yaml
      - news_feed
```

- [ ] **Step 11: Add to learning mode always_exposed_tools**

In `modes.learning.always_exposed_tools` (after `- transcript` at line 189), add:
```yaml
      - news_feed
```

- [ ] **Step 12: Add to top-level always_exposed_tools**

In top-level `always_exposed_tools` (after `- transcript` at line 40), add:
```yaml
    - news_feed
```

- [ ] **Step 13: Verify IRIS loads without errors**

Run: `cd D:/项目开发/二级投研自动化/iris && python -c "from main import build_harness; h, r = build_harness(); print(f'Tools: {[t.name for t in h.tools]}'); assert 'news_feed' in [t.name for t in h.tools]"`
Expected: Tool list includes `news_feed`

- [ ] **Step 14: Commit registration + config**

```bash
cd D:/项目开发/二级投研自动化
git add iris/main.py iris/iris_config.yaml
git commit -m "feat: register news_feed tool in harness and config"
```

---

## Chunk 3: Integration Test

### Task 5: Integration smoke test

- [ ] **Step 15: Run a live integration test with hackernews (no auth required)**

Run: `cd D:/项目开发/二级投研自动化/iris && python -c "from tools.news_feed import news_feed; r = news_feed(sources=['hackernews'], topic='AI', limit=3); print(r.status, r.data if r.status == 'ok' else r.error)"`
Expected: `ok` status with items from Hacker News matching "AI"

- [ ] **Step 16: Run full test suite to check for regressions**

Run: `cd D:/项目开发/二级投研自动化/iris && python -m pytest tests/ -v --tb=short`
Expected: All tests pass, no regressions
