"""
Web search & fetch tools — powered by Exa Search + Jina Reader.

Replaces the previous Perplexity-only search with a two-tool approach:
  • exa_search  — semantic web search (free 1000 req/month)
  • web_fetch   — fetch any URL as markdown via Jina Reader (free, unlimited)

Integration inspired by Agent-Reach architecture:
  https://github.com/Panniantong/Agent-Reach
"""

import os
import httpx
from .base import ToolResult, make_tool_schema

# ── Exa Search ───────────────────────────────────────────────

EXA_API_URL = "https://api.exa.ai/search"

EXA_SEARCH_SCHEMA = make_tool_schema(
    name="exa_search",
    description=(
        "Semantic web search for up-to-date financial news, research, and company information. "
        "Use for: recent earnings, analyst opinions, industry trends, company news, macro events. "
        "Returns a list of results with titles, URLs, and optional text snippets."
    ),
    properties={
        "query": {
            "type": "string",
            "description": "Specific search query. Be precise — e.g. 'NVDA Q4 2026 earnings revenue data center'",
        },
        "num_results": {
            "type": "integer",
            "description": "Number of results to return (1-10). Default 5.",
        },
        "use_autoprompt": {
            "type": "boolean",
            "description": "Let Exa optimize the query for better results. Default true.",
        },
    },
    required=["query"],
)


def exa_search(query: str, num_results: int = 5, use_autoprompt: bool = True) -> ToolResult:
    """Semantic search via Exa API. Returns titles, URLs, and text snippets."""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return ToolResult.error("EXA_API_KEY not set", hint="Get free key at https://exa.ai — 1000 req/month free")

    num_results = max(1, min(10, num_results))

    payload = {
        "query": query,
        "num_results": num_results,
        "use_autoprompt": use_autoprompt,
        "type": "auto",
        "text": {"max_characters": 1000},
        "highlights": {"num_sentences": 3},
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                EXA_API_URL,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("results", []):
                item = {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "published_date": r.get("publishedDate", ""),
                }
                # Add text snippet if available
                text = r.get("text", "")
                if text:
                    item["snippet"] = text[:500]
                # Add highlights if available
                highlights = r.get("highlights", [])
                if highlights:
                    item["highlights"] = highlights[:3]
                results.append(item)

            return ToolResult.ok({
                "query": query,
                "autoprompt_query": data.get("autopromptString", query),
                "results": results,
                "sources": [r["url"] for r in results],
            })

    except httpx.TimeoutException:
        return ToolResult.error("Search timed out", hint="Try a more specific query", recoverable=True)
    except httpx.HTTPStatusError as e:
        return ToolResult.error(f"Exa API error: {e.response.status_code}", recoverable=True)
    except Exception as e:
        return ToolResult.error(f"Search failed: {str(e)}", recoverable=False)


# ── Jina Reader (web fetch) ─────────────────────────────────

JINA_READER_PREFIX = "https://r.jina.ai/"

WEB_FETCH_SCHEMA = make_tool_schema(
    name="web_fetch",
    description=(
        "Fetch any web page and return its content as clean markdown. "
        "Use after exa_search to read full articles, earnings reports, SEC filings, etc. "
        "Powered by Jina Reader — free, no API key required."
    ),
    properties={
        "url": {
            "type": "string",
            "description": "The full URL to fetch (e.g. 'https://example.com/article').",
        },
        "max_chars": {
            "type": "integer",
            "description": "Maximum characters to return. Default 5000. Use lower for summaries, higher for detailed reading.",
        },
    },
    required=["url"],
)


def web_fetch(url: str, max_chars: int = 5000) -> ToolResult:
    """Fetch a URL as markdown via Jina Reader. Free, no key needed."""
    if not url or not url.startswith(("http://", "https://")):
        return ToolResult.error("Invalid URL — must start with http:// or https://")

    max_chars = max(500, min(20000, max_chars))
    jina_url = JINA_READER_PREFIX + url

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(
                jina_url,
                headers={
                    "Accept": "text/markdown",
                    "X-No-Cache": "true",
                },
            )
            response.raise_for_status()
            content = response.text.strip()

            if not content:
                return ToolResult.error("Page returned empty content", hint="URL may be behind a paywall or require login")

            truncated = len(content) > max_chars
            content = content[:max_chars]

            return ToolResult.ok({
                "url": url,
                "content": content,
                "char_count": len(content),
                "truncated": truncated,
            })

    except httpx.TimeoutException:
        return ToolResult.error("Fetch timed out", hint="Page may be slow or blocking automated requests", recoverable=True)
    except httpx.HTTPStatusError as e:
        return ToolResult.error(f"Fetch error: {e.response.status_code}", recoverable=True)
    except Exception as e:
        return ToolResult.error(f"Fetch failed: {str(e)}", recoverable=False)
