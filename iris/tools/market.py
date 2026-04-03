"""
Market data tools — httpx Yahoo primary, FMP secondary, yfinance last resort.

Provides stock price, historical data, and key stats.
httpx Yahoo is primary because it's thread-safe (enables true concurrency).
FMP is secondary (rate-limited on free tier, auto-skipped after 429).
yfinance is last resort (has a global lock, not concurrent-safe).
"""

import os
import logging
import threading
import time as _time
from datetime import datetime, timedelta

import httpx
import yfinance as yf

from .base import ToolResult, make_tool_schema

logger = logging.getLogger(__name__)

# yfinance's curl_cffi is not thread-safe; serialize all yf calls
_yf_lock = threading.Lock()

_FMP_BASE = "https://financialmodelingprep.com/stable"
_FMP_TIMEOUT = 10

# ── Quote cache (TTL-based, avoids duplicate fetches) ─────────
_quote_cache: dict[str, tuple[float, ToolResult]] = {}  # ticker → (expiry_ts, result)
_QUOTE_CACHE_TTL = 60  # seconds

# ── FMP 429 cooldown ──────────────────────────────────────────
_fmp_cooldown_until: float = 0.0  # timestamp; skip FMP until this time


def _fmp_key() -> str:
    """Lazy read so dotenv has time to load before first use."""
    return os.getenv("FMP_API_KEY", "")


QUOTE_SCHEMA = make_tool_schema(
    name="quote",
    description=(
        "Get current stock quote and key statistics: price, market cap, P/E, 52-week range, "
        "volume, dividend yield, beta, etc. Use when you need real-time price or valuation snapshot."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker, e.g. 'NVDA', 'AAPL', '600519.SS' (A-share)",
        },
    },
    required=["ticker"],
)


HISTORY_SCHEMA = make_tool_schema(
    name="history",
    description=(
        "Get historical price data for a stock. Returns OHLCV (open, high, low, close, volume). "
        "Use for price trend analysis, drawdown calculation, or chart data."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker, e.g. 'NVDA', 'AAPL'",
        },
        "period": {
            "type": "string",
            "enum": ["1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd"],
            "description": "Time period. Default '6mo'.",
        },
        "interval": {
            "type": "string",
            "enum": ["1d", "1wk", "1mo"],
            "description": "Data interval. Default '1d'.",
        },
    },
    required=["ticker"],
)


# ── FMP helpers ──────────────────────────────────────────────

def _fmp_get(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Call an FMP stable endpoint. Returns parsed JSON or None on failure."""
    global _fmp_cooldown_until
    if _time.time() < _fmp_cooldown_until:
        return None  # skip during cooldown
    key = _fmp_key()
    if not key:
        logger.debug(f"FMP key empty, skipping {endpoint}")
        return None
    try:
        p = {"apikey": key, **(params or {})}
        r = httpx.get(f"{_FMP_BASE}/{endpoint}", params=p, timeout=_FMP_TIMEOUT)
        if r.status_code == 429:
            _fmp_cooldown_until = _time.time() + 300  # 5 min cooldown
            logger.info("FMP 429 rate-limited, cooling down for 5 minutes")
            return None
        if r.status_code != 200:
            logger.debug(f"FMP {endpoint} {p.get('symbol','')} returned {r.status_code}")
            return None
        data = r.json()
        if isinstance(data, dict) and "Error Message" in data:
            return None
        return data
    except Exception as e:
        logger.debug(f"FMP {endpoint} failed: {e}")
        return None


def _fmp_quote(ticker: str) -> ToolResult | None:
    """Try to build a quote from FMP stable/quote + stable/ratios-ttm."""
    # 1. Basic quote (price, market cap, 52w range)
    quote_data = _fmp_get("quote", {"symbol": ticker})
    if not quote_data or not isinstance(quote_data, list) or not quote_data:
        return None

    q = quote_data[0]
    price = q.get("price")
    if not price:
        return None

    fields = {
        "ticker": ticker.upper(),
        "name": q.get("name"),
        "price": price,
        "currency": "USD",
        "market_cap": q.get("marketCap"),
        "52w_high": q.get("yearHigh"),
        "52w_low": q.get("yearLow"),
        "50d_avg": q.get("priceAvg50"),
        "200d_avg": q.get("priceAvg200"),
        "avg_volume": int(q["volume"]) if q.get("volume") else None,
    }

    # 2. Ratios TTM (P/E, P/B, P/S, EV/EBITDA, dividend yield)
    ratios = _fmp_get("ratios-ttm", {"symbol": ticker})
    if ratios and isinstance(ratios, list) and ratios:
        rt = ratios[0]
        fields["pe_trailing"] = _round(rt.get("priceToEarningsRatioTTM"))
        fields["pe_forward"] = None  # FMP ratios-ttm doesn't have forward PE
        fields["ps"] = _round(rt.get("priceToSalesRatioTTM"))
        fields["pb"] = _round(rt.get("priceToBookRatioTTM"))
        fields["dividend_yield"] = _round(rt.get("dividendYieldTTM"), 4)

    # 3. Key metrics TTM (EV/EBITDA, beta)
    metrics = _fmp_get("key-metrics-ttm", {"symbol": ticker})
    if metrics and isinstance(metrics, list) and metrics:
        mt = metrics[0]
        fields["ev_ebitda"] = _round(mt.get("evToEBITDATTM"))

    # 4. Company profile for sector/industry/beta
    profile = _fmp_get("profile", {"symbol": ticker})
    if profile and isinstance(profile, list) and profile:
        pr = profile[0]
        fields["sector"] = pr.get("sector")
        fields["industry"] = pr.get("industry")
        fields["beta"] = _round(pr.get("beta"))

    fields["_source"] = "fmp"
    return ToolResult.ok({k: v for k, v in fields.items() if v is not None})


def _fmp_history(ticker: str, period: str, interval: str) -> ToolResult | None:
    """Try to get historical OHLCV from FMP."""
    # Convert period to date range
    today = datetime.now()
    period_days = {
        "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825, "ytd": (today - datetime(today.year, 1, 1)).days,
    }
    days = period_days.get(period, 180)
    from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    data = _fmp_get("historical-price-eod/full", {
        "symbol": ticker, "from": from_date, "to": to_date,
    })

    if not data or not isinstance(data, list) or not data:
        return None

    # Sort by date ascending
    data.sort(key=lambda x: x.get("date", ""))

    # Downsample for weekly/monthly intervals
    if interval == "1wk":
        data = data[::5]
    elif interval == "1mo":
        data = data[::21]

    # Cap at 60 rows
    max_rows = 60
    if len(data) > max_rows:
        step = len(data) // max_rows
        data = data[::step]

    records = []
    for row in data:
        records.append({
            "date": row.get("date", ""),
            "open": round(row.get("open", 0), 2),
            "high": round(row.get("high", 0), 2),
            "low": round(row.get("low", 0), 2),
            "close": round(row.get("close", 0), 2),
            "volume": int(row.get("volume", 0)),
        })

    return ToolResult.ok({
        "ticker": ticker.upper(),
        "period": period,
        "interval": interval,
        "count": len(records),
        "data": records,
        "_source": "fmp",
    })


def _round(val, digits=2):
    """Round a value if it's a number, else return None."""
    if val is None:
        return None
    try:
        return round(float(val), digits)
    except (ValueError, TypeError):
        return None


# ── yfinance fallback ────────────────────────────────────────

def _yf_quote(ticker: str) -> ToolResult:
    """Fallback quote via yfinance (serialized to avoid curl_cffi TLS errors)."""
    with _yf_lock:
        return _yf_quote_inner(ticker)


def _yf_quote_inner(ticker: str) -> ToolResult:
    t = yf.Ticker(ticker)
    info = t.info

    if not info or info.get("trailingPegRatio") is None and info.get("regularMarketPrice") is None:
        fi = t.fast_info
        if fi is None:
            return ToolResult.fail(
                f"No data for ticker '{ticker}'",
                hint="Check ticker symbol. A-shares use suffix .SS (Shanghai) or .SZ (Shenzhen).",
            )
        return ToolResult.ok({
            "ticker": ticker.upper(),
            "price": round(fi.last_price, 2) if fi.last_price else None,
            "market_cap": fi.market_cap,
            "currency": fi.currency,
            "_source": "yfinance",
        })

    fields = {
        "ticker": ticker.upper(),
        "name": info.get("shortName"),
        "price": info.get("regularMarketPrice") or info.get("currentPrice"),
        "currency": info.get("currency"),
        "market_cap": info.get("marketCap"),
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "ps": info.get("priceToSalesTrailing12Months"),
        "pb": info.get("priceToBook"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "50d_avg": info.get("fiftyDayAverage"),
        "200d_avg": info.get("twoHundredDayAverage"),
        "avg_volume": info.get("averageDailyVolume10Day"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "_source": "yfinance",
    }
    return ToolResult.ok({k: v for k, v in fields.items() if v is not None})


def _yf_history(ticker: str, period: str, interval: str) -> ToolResult:
    """Fallback history via yfinance (serialized to avoid curl_cffi TLS errors)."""
    with _yf_lock:
        return _yf_history_inner(ticker, period, interval)


def _yf_history_inner(ticker: str, period: str, interval: str) -> ToolResult:
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)

    if df.empty:
        return ToolResult.fail(
            f"No history for '{ticker}' (period={period})",
            hint="Check ticker or try a different period.",
        )

    max_rows = 60
    if len(df) > max_rows:
        step = len(df) // max_rows
        df = df.iloc[::step]

    records = []
    for date, row in df.iterrows():
        records.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
        })

    return ToolResult.ok({
        "ticker": ticker.upper(),
        "period": period,
        "interval": interval,
        "count": len(records),
        "data": records,
        "_source": "yfinance",
    })


# ── httpx Yahoo Finance fallback (when curl_cffi fails) ──────

def _httpx_yf_quote(ticker: str) -> ToolResult | None:
    """Last-resort quote via Yahoo Finance chart API (pure httpx)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        r = httpx.get(url, params={"range": "1d", "interval": "1d"},
                      headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return None
        meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if not price:
            return None
        fields = {
            "ticker": ticker.upper(), "name": meta.get("shortName"),
            "price": price, "currency": meta.get("currency"),
            "52w_high": meta.get("fiftyTwoWeekHigh"), "52w_low": meta.get("fiftyTwoWeekLow"),
            "50d_avg": meta.get("fiftyDayAverage"), "200d_avg": meta.get("twoHundredDayAverage"),
            "_source": "yahoo-httpx",
        }
        return ToolResult.ok({k: v for k, v in fields.items() if v is not None})
    except Exception as e:
        logger.debug(f"httpx Yahoo fallback failed for {ticker}: {e}")
        return None


# ── Public API: cache → httpx Yahoo → FMP → yfinance ─────────

def quote(ticker: str) -> ToolResult:
    """Get current quote with 60s cache. httpx Yahoo first (thread-safe), then FMP, then yfinance."""
    ticker = ticker.strip()

    # 0. Cache hit
    cached = _quote_cache.get(ticker.upper())
    if cached and _time.time() < cached[0]:
        return cached[1]

    # 1. httpx Yahoo (thread-safe, fast, enables true concurrency)
    result = _httpx_yf_quote(ticker)
    if result and result.status == "ok":
        _quote_cache[ticker.upper()] = (_time.time() + _QUOTE_CACHE_TTL, result)
        return result

    # 2. FMP (richer data but rate-limited on free tier)
    result = _fmp_quote(ticker)
    if result and result.status == "ok":
        _quote_cache[ticker.upper()] = (_time.time() + _QUOTE_CACHE_TTL, result)
        return result

    # 3. yfinance (last resort — global lock, slow)
    logger.info(f"quote({ticker}): httpx+FMP failed, trying yfinance")
    try:
        result = _yf_quote(ticker)
        if result and result.status == "ok":
            _quote_cache[ticker.upper()] = (_time.time() + _QUOTE_CACHE_TTL, result)
            return result
    except Exception as e:
        logger.info(f"quote({ticker}): yfinance failed: {e}")

    return ToolResult.fail(f"All sources failed for quote({ticker})", recoverable=True)


def history(ticker: str, period: str = "6mo", interval: str = "1d") -> ToolResult:
    """Get historical OHLCV. Tries FMP first, falls back to yfinance."""
    # Try FMP
    result = _fmp_history(ticker, period, interval)
    if result and result.status == "ok" and result.data and result.data.get("count", 0) > 0:
        logger.debug(f"history({ticker}): FMP success")
        return result

    # Fallback to yfinance
    logger.info(f"history({ticker}): FMP failed, falling back to yfinance")
    try:
        return _yf_history(ticker, period, interval)
    except Exception as e:
        return ToolResult.fail(f"All sources failed for history({ticker}): {e}", recoverable=True)


# Backward-compatible aliases
YF_QUOTE_SCHEMA = QUOTE_SCHEMA
YF_HISTORY_SCHEMA = HISTORY_SCHEMA


def yf_quote(ticker: str) -> ToolResult:
    return quote(ticker=ticker)


def yf_history(ticker: str, period: str = "6mo", interval: str = "1d") -> ToolResult:
    return history(ticker=ticker, period=period, interval=interval)
