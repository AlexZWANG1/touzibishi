import os
import httpx
from .base import ToolResult, make_tool_schema

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

PERPLEXITY_SEARCH_SCHEMA = make_tool_schema(
    name="perplexity_search",
    description=(
        "Search the web for up-to-date financial news, research, and company information. "
        "Use for: recent earnings, analyst opinions, industry trends, company news, macro events. "
        "Returns a summary with cited sources."
    ),
    properties={
        "query": {
            "type": "string",
            "description": "Specific search query. Be precise — e.g. 'NVDA Q4 2026 earnings revenue data center'",
        },
        "focus": {
            "type": "string",
            "enum": ["finance", "news", "general"],
            "description": "Search focus area.",
        },
    },
    required=["query"],
)


def perplexity_search(query: str, focus: str = "finance") -> ToolResult:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return ToolResult.error("PERPLEXITY_API_KEY not set", hint="Add to .env file")

    model = "sonar-pro" if focus == "finance" else "sonar"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a financial research assistant. Provide factual, cited information.",
            },
            {"role": "user", "content": query},
        ],
        "return_citations": True,
        "search_recency_filter": "month",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                PERPLEXITY_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            return ToolResult.ok({
                "query": query,
                "summary": content,
                "sources": citations[:5],
            })
    except httpx.TimeoutException:
        return ToolResult.error("Search timed out", hint="Try a more specific query", recoverable=True)
    except httpx.HTTPStatusError as e:
        return ToolResult.error(f"Search API error: {e.response.status_code}", recoverable=True)
    except Exception as e:
        return ToolResult.error(f"Search failed: {str(e)}", recoverable=False)
