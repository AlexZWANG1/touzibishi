"""news_feed — fetches from curated RSS-Notion sources for IRIS analysis."""

from __future__ import annotations

import asyncio
import importlib
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
        "Fetch from 62+ curated, high-quality information sources. "
        "PROACTIVELY use this during any investment analysis — do not wait for the user to ask. "
        "hackernews: tech sentiment & startup trends. "
        "reddit: community reactions & discussion (LocalLLaMA, MachineLearning). "
        "arxiv: latest AI/ML research papers. "
        "rss: 27 curated news feeds. "
        "youtube: tech video content. "
        "github: trending open-source projects. "
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

    # Pre-flight: check RSS-Notion path exists
    if not os.path.isdir(_RSS_NOTION_PATH):
        return ToolResult.fail(
            f"RSS-Notion project not found at {_RSS_NOTION_PATH}",
            hint="Set RSS_NOTION_PATH env var to the correct path",
        )

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
        if result is not None:
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

    output: dict[str, Any] = {
        "items": final_items,
        "total": len(final_items),
        "sources_queried": sources_queried,
    }
    if all_failed and sources:
        output["_all_failed"] = True
    return output


async def _fetch_source(source_key: str) -> list[dict]:
    """Instantiate and call a single RSS-Notion source."""
    module_path, class_name, _display_name = _SOURCE_MAP[source_key]
    config = dict(_SOURCE_CONFIGS.get(source_key, {}))

    try:
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
