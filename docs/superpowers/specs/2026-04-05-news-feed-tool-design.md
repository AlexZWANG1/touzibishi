# Design: news_feed Tool for IRIS

## Problem

IRIS currently relies solely on `exa_search` for external information. The user maintains a mature, curated set of 62+ information sources in the RSS-Notion project (`D:/项目开发/RSS-Notion`). We want IRIS's AI to actively fetch from these sources during investment analysis — HN for tech sentiment, Reddit for community reactions, arXiv for research trends, etc.

## Approach

One unified IRIS tool (`news_feed`) that directly imports RSS-Notion's source layer via Python path. No HTTP services, no code duplication. RSS-Notion remains the single source of truth for fetcher logic.

## Tool Schema

```
news_feed(
  sources: list[str]   # required — subset of: hackernews, reddit, arxiv, rss, youtube, github
  topic: str = ""      # optional — keyword to filter/search results
  limit: int = 10      # optional — max items per source (default 10)
)
```

Excluded sources (not relevant to investment research): `producthunt`, `xiaohongshu`, `folo` (personal subscriptions), `tavily_search` (overlaps with IRIS's `exa_search`).

### AI Usage Examples

- Analyzing NVDA: `news_feed(sources=["hackernews","reddit","arxiv"], topic="NVIDIA AI chip")`
- Market sentiment: `news_feed(sources=["hackernews","rss"], topic="tariff stock market")`
- Open-source trends: `news_feed(sources=["github","reddit"], topic="LLM inference")`

## Architecture

```
iris/tools/news_feed.py
    │
    │  sys.path.insert → D:/项目开发/RSS-Notion
    │
    ├── imports sources.hackernews.HackerNewsSource
    ├── imports sources.reddit.RedditSource
    ├── imports sources.arxiv_source.ArxivSource
    ├── imports sources.rss_fetcher.RSSFetcher
    ├── imports sources.youtube.YouTubeSource
    └── imports sources.github_trending.GitHubTrendingSource
```

### Data Flow

1. AI calls `news_feed(sources=["hackernews","reddit"], topic="NVIDIA")`
2. Tool instantiates requested source classes with default config (enrichment disabled — see Latency section)
3. Runs all sources concurrently via `asyncio.gather()` inside a fresh event loop
4. Resets RSS-Notion's module-level `content_fetcher._semaphore` before each run (see Async Bridge section)
5. Filters results by `topic` — splits topic into tokens, requires ANY token to match title or description (case-insensitive)
6. Truncates to `limit` per source
7. Returns unified `ToolResult.ok({"items": [...], "total": N, "sources_queried": [...]})`

### Return Format

```json
{
  "items": [
    {
      "title": "Article title",
      "url": "https://...",
      "source": "hackernews",
      "source_name": "Hacker News",
      "summary": "Description or first 500 chars of content",
      "score": 342,
      "author": "username",
      "published": "2026-04-05T10:30:00"
    }
  ],
  "total": 12,
  "sources_queried": ["hackernews", "reddit"]
}
```

### Source Name Mapping

Explicit mapping between tool parameter keys and source classes:

```python
_SOURCE_MAP = {
    "hackernews": ("HackerNewsSource", "Hacker News"),
    "reddit":     ("RedditSource",     "Reddit"),
    "arxiv":      ("ArxivSource",      "arXiv"),
    "rss":        ("RSSFetcher",       "RSS"),
    "youtube":    ("YouTubeSource",    "YouTube"),
    "github":     ("GitHubTrendingSource", "GitHub Trending"),
}
```

## Source Configs

Each source is instantiated with a hardcoded default config dict.

| Source | Config | Required Env Vars | External File Deps |
|--------|--------|-------------------|---------------------|
| `hackernews` | `max_items: 15, enrich: false` | None | None |
| `reddit` | `max_items: 10, subreddits: ["LocalLLaMA","MachineLearning"], enrich: false` | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` (falls back to RSS if missing) | None |
| `arxiv` | `max_items: 10, categories: ["cs.AI","cs.CL","cs.LG"]` | None | None |
| `rss` | `max_items: 30, max_age_days: 3, enrich: false` | None | `D:/项目开发/RSS-Notion/sources.yaml` (feed list) |
| `youtube` | `max_items: 10, max_age_days: 7, enrich: false` | None | None |
| `github` | `max_items: 10, language: "python"` | None | None |

**Note:** The `rss` source depends on `sources.yaml` in the RSS-Notion project root. This file contains the 27 RSS feed URLs. If missing, `rss` source returns an empty list.

## Latency & Enrichment

RSS-Notion sources optionally enrich items via Jina Reader (full article text). This triggers 10-50 HTTP requests per source, causing 30-60s latency.

**For IRIS, enrichment is disabled by default** via `config["enrich"] = False`. The tool returns titles, URLs, descriptions, and scores — enough for the AI to decide what's relevant. If the AI needs the full article text, it can use the existing `web_fetch` tool on specific URLs.

If a source does not support the `enrich` config flag natively, the implementation should monkey-patch or skip the enrichment call.

## Implementation Details

### File: `iris/tools/news_feed.py`

Single file containing:
1. `NEWS_FEED_SCHEMA` — OpenAI function schema
2. `news_feed(sources, topic, limit)` → `ToolResult` — the tool function
3. `_fetch_all(sources, topic, limit)` — async coordinator using `asyncio.gather()`
4. `_fetch_source(name)` — async helper that instantiates and calls source.fetch()
5. `_filter_by_topic(items, topic)` — splits topic into tokens, OR-match on title + description
6. `_to_result_item(source_item, source_key)` — converts SourceItem to output dict

### Async Bridge

RSS-Notion sources are async. IRIS tools are sync (run in thread). The `content_fetcher.py` module uses a global `asyncio.Semaphore` that binds to the event loop at creation time. We must reset it before each invocation to avoid cross-loop errors.

```python
import asyncio

def news_feed(sources, topic="", limit=10):
    # Reset RSS-Notion's module-level semaphore to avoid loop-binding issues
    try:
        from sources import content_fetcher
        content_fetcher._semaphore = None
    except ImportError:
        pass

    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(_fetch_all(sources, topic, limit))
    finally:
        loop.close()
    return ToolResult.ok(results)

async def _fetch_all(sources, topic, limit):
    tasks = [_fetch_source(s) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # merge, filter, truncate
    ...
```

### Python Path

Add RSS-Notion to sys.path at module import time:
```python
import sys, os
_RSS_NOTION_PATH = os.environ.get("RSS_NOTION_PATH", "D:/项目开发/RSS-Notion")
if _RSS_NOTION_PATH not in sys.path:
    sys.path.insert(0, _RSS_NOTION_PATH)
```

Configurable via env var for portability; defaults to local dev path.

### Error Handling

- Individual source failure → log warning, continue with other sources
- All sources fail → `ToolResult.fail("All requested sources failed", recoverable=True)`
- Import failure (RSS-Notion not found) → `ToolResult.fail("RSS-Notion project not found at {path}", hint="Set RSS_NOTION_PATH env var")`
- Invalid source name → `ToolResult.fail("Unknown source: {name}. Valid: hackernews, reddit, arxiv, rss, youtube, github")`
- Topic filter returns 0 items → return empty list with `total: 0` (not an error)

## Registration

In `iris/main.py`, add to `core_tools`:
```python
from tools.news_feed import news_feed, NEWS_FEED_SCHEMA
# ...
core_tools = [
    # ... existing tools ...
    Tool(news_feed, NEWS_FEED_SCHEMA),
]
```

## Tool Exposure

Add to `iris_config.yaml`:

1. Tool triggers:
```yaml
triggers:
  news_feed: ["新闻", "news", "HN", "Reddit", "arXiv", "热点", "trending", "社区反馈"]
```

2. Add `news_feed` to `modes.analysis.always_exposed_tools` and `modes.learning.always_exposed_tools` lists (top-level `always_exposed_tools` is overridden by mode-specific lists).

3. Add compress override for large payloads:
```yaml
tool_compress_overrides:
  news_feed: 6000
```

## Testing

- Unit test: mock each source's `_fetch()`, verify filter + format logic
- Integration test: call with `sources=["hackernews"]` (no auth needed), verify real data returns
- Error test: invalid source name → clear error message

## Dependencies

Requires in the shared Python environment: `feedparser`, `praw`, `arxiv`, `aiohttp`, `pyyaml`, `beautifulsoup4`. These should already be installed. Verify before first run.
