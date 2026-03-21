"""
Earnings call transcript tool.

Provider chain: Finnhub (if key set) → FMP (if key set) → Exa+Jina web scrape (always available).
"""

import logging
import os
from datetime import datetime

import httpx

from .base import ToolResult, make_tool_schema

logger = logging.getLogger(__name__)

TRANSCRIPT_SCHEMA = make_tool_schema(
    name="transcript",
    description=(
        "Get earnings call transcripts for a public company. Returns full text with speaker "
        "identification (CEO, CFO, analysts). Use when you need management commentary, guidance, "
        "segment discussion, Q&A insights, or qualitative context that financial statements don't capture. "
        "Specify year and quarter, or omit for the most recent available."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker, e.g. 'MSFT', 'AAPL'",
        },
        "year": {
            "type": "integer",
            "description": "Fiscal year (e.g. 2024). Omit for most recent.",
        },
        "quarter": {
            "type": "integer",
            "description": "Quarter (1-4). Omit for most recent.",
            "enum": [1, 2, 3, 4],
        },
        "max_chars": {
            "type": "integer",
            "description": "Max characters to return. Default 10000. Use higher for full transcript.",
        },
    },
    required=["ticker"],
)


def transcript(
    ticker: str,
    year: int = None,
    quarter: int = None,
    max_chars: int = 10000,
) -> ToolResult:
    """Fetch earnings call transcript. Tries Finnhub → FMP → Exa+Jina scrape."""
    ticker_upper = ticker.upper()

    # Try Finnhub first (needs paid plan for transcripts)
    if os.getenv("FINNHUB_API_KEY"):
        result = _finnhub_transcript(ticker_upper, year, quarter, max_chars)
        if result.status == "ok":
            return result
        logger.info("Finnhub transcript failed (%s) for %s", result.error, ticker_upper)

    # Try FMP (needs paid plan for transcripts)
    if os.getenv("FMP_API_KEY"):
        result = _fmp_transcript(ticker_upper, year, quarter, max_chars)
        if result.status == "ok":
            return result
        logger.info("FMP transcript failed (%s) for %s", result.error, ticker_upper)

    # Fallback: Exa search + Jina web fetch (always available)
    result = _exa_jina_transcript(ticker_upper, year, quarter, max_chars)
    if result.status == "ok":
        return result

    return ToolResult.fail(
        f"No transcript found for {ticker_upper}",
        hint="Try specifying year and quarter explicitly, or use sec_filing with section_name='MD&A' for management commentary.",
        recoverable=True,
    )


# ── Finnhub ──────────────────────────────────────────────────

def _finnhub_transcript(ticker: str, year: int, quarter: int, max_chars: int) -> ToolResult:
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return ToolResult.fail("FINNHUB_API_KEY not set")

    try:
        with httpx.Client(timeout=20.0) as client:
            if year is None or quarter is None:
                list_url = f"https://finnhub.io/api/v1/stock/transcripts/list?symbol={ticker}&token={api_key}"
                resp = client.get(list_url)
                resp.raise_for_status()
                data = resp.json()
                transcripts = data.get("transcripts", [])
                if not transcripts:
                    return ToolResult.fail(f"No transcripts on Finnhub for {ticker}")
                latest = transcripts[0]
                year = latest.get("year", year)
                quarter = latest.get("quarter", quarter)

            url = f"https://finnhub.io/api/v1/stock/transcripts?id={ticker}_{year}_{quarter}&token={api_key}"
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

            if not data or not data.get("transcript"):
                return ToolResult.fail(f"No Finnhub transcript for {ticker} Q{quarter} {year}")

            parts = []
            for entry in data["transcript"]:
                speaker = entry.get("name", "Unknown")
                text = entry.get("speech", "").strip()
                if text:
                    parts.append(f"**{speaker}**: {text}")

            full_text = "\n\n".join(parts)
            truncated = len(full_text) > max_chars

            return ToolResult.ok({
                "ticker": ticker, "year": year, "quarter": quarter,
                "source": "finnhub",
                "content": full_text[:max_chars],
                "truncated": truncated,
                "char_count": min(len(full_text), max_chars),
                "total_chars": len(full_text),
                "speaker_count": len(set(e.get("name", "") for e in data["transcript"])),
            })
    except httpx.HTTPStatusError as e:
        return ToolResult.fail(f"Finnhub error: {e.response.status_code}", recoverable=True)
    except Exception as e:
        return ToolResult.fail(f"Finnhub failed: {e}", recoverable=True)


# ── FMP ──────────────────────────────────────────────────────

def _fmp_transcript(ticker: str, year: int, quarter: int, max_chars: int) -> ToolResult:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return ToolResult.fail("FMP_API_KEY not set")

    fmp_base = "https://financialmodelingprep.com/stable"

    try:
        with httpx.Client(timeout=20.0) as client:
            if year is None or quarter is None:
                now = datetime.now()
                year = year or now.year
                for y in [year, year - 1]:
                    for q in range(4, 0, -1):
                        r = _fmp_fetch_single(client, fmp_base, api_key, ticker, y, q, max_chars)
                        if r.status == "ok":
                            return r
                return ToolResult.fail(f"No FMP transcript for {ticker}")
            else:
                return _fmp_fetch_single(client, fmp_base, api_key, ticker, year, quarter, max_chars)
    except Exception as e:
        return ToolResult.fail(f"FMP transcript failed: {e}", recoverable=True)


def _fmp_fetch_single(client, fmp_base, api_key, ticker, year, quarter, max_chars) -> ToolResult:
    url = f"{fmp_base}/earning-call-transcript?symbol={ticker}&year={year}&quarter={quarter}&apikey={api_key}"
    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return ToolResult.fail(f"Empty for {ticker} Q{quarter} {year}")

        entry = data[0] if isinstance(data, list) else data
        content = entry.get("content", "")
        if not content:
            return ToolResult.fail(f"Empty for {ticker} Q{quarter} {year}")

        truncated = len(content) > max_chars
        return ToolResult.ok({
            "ticker": ticker, "year": year, "quarter": quarter,
            "source": "fmp",
            "content": content[:max_chars],
            "truncated": truncated,
            "char_count": min(len(content), max_chars),
            "total_chars": len(content),
        })
    except httpx.HTTPStatusError:
        return ToolResult.fail(f"FMP API error for {ticker} Q{quarter} {year}")


# ── Exa + Jina (free fallback) ───────────────────────────────

JINA_READER_PREFIX = "https://r.jina.ai/"


def _exa_jina_transcript(ticker: str, year: int, quarter: int, max_chars: int) -> ToolResult:
    """Search for transcript via Exa, then fetch full text via Jina Reader."""
    exa_key = os.getenv("EXA_API_KEY")
    if not exa_key:
        return ToolResult.fail("EXA_API_KEY not set for web transcript fallback")

    # Build search query
    now = datetime.now()
    y = year or now.year
    q = quarter
    if q:
        query = f"{ticker} Q{q} {y} earnings call transcript full text"
    else:
        query = f"{ticker} latest earnings call transcript full text {y}"

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            # Step 1: Exa search
            exa_resp = client.post(
                "https://api.exa.ai/search",
                headers={"Authorization": f"Bearer {exa_key}", "Content-Type": "application/json"},
                json={
                    "query": query,
                    "num_results": 3,
                    "type": "auto",
                    "text": {"max_characters": 200},
                },
            )
            exa_resp.raise_for_status()
            results = exa_resp.json().get("results", [])

            if not results:
                return ToolResult.fail(f"No transcript search results for {ticker}")

            # Step 2: Try to fetch the best transcript URL via Jina
            # Prefer Motley Fool, SeekingAlpha, MarketScreener (they have full transcripts)
            preferred_domains = ["fool.com", "seekingalpha.com", "marketscreener.com", "gurufocus.com"]
            sorted_results = sorted(
                results,
                key=lambda r: any(d in r.get("url", "") for d in preferred_domains),
                reverse=True,
            )

            for result in sorted_results:
                url = result.get("url", "")
                if not url:
                    continue

                try:
                    jina_resp = client.get(
                        JINA_READER_PREFIX + url,
                        headers={"Accept": "text/markdown", "X-No-Cache": "true"},
                        timeout=25.0,
                    )
                    jina_resp.raise_for_status()
                    content = jina_resp.text.strip()

                    if len(content) < 500:
                        continue  # Too short, probably blocked

                    truncated = len(content) > max_chars
                    return ToolResult.ok({
                        "ticker": ticker,
                        "year": y,
                        "quarter": q,
                        "source": f"web ({url})",
                        "content": content[:max_chars],
                        "truncated": truncated,
                        "char_count": min(len(content), max_chars),
                        "total_chars": len(content),
                        "source_url": url,
                    })
                except Exception as e:
                    logger.debug("Jina fetch failed for %s: %s", url, e)
                    continue

            return ToolResult.fail(
                f"Found transcript URLs but couldn't fetch content for {ticker}",
                hint="Try using web_fetch directly on a transcript URL.",
            )

    except Exception as e:
        return ToolResult.fail(f"Exa+Jina transcript search failed: {e}", recoverable=True)
