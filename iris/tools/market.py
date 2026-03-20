"""
Market data tools — powered by yfinance.

Provides stock price, historical data, and key stats without an API key.
"""

import yfinance as yf
from .base import ToolResult, make_tool_schema


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


def quote(ticker: str) -> ToolResult:
    """Get current quote and key stats via yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not info or info.get("trailingPegRatio") is None and info.get("regularMarketPrice") is None:
            # Fallback: try fast_info
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
            })

        # Extract key fields, skip None values
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
        }
        return ToolResult.ok({k: v for k, v in fields.items() if v is not None})

    except Exception as e:
        return ToolResult.fail(f"yfinance error: {str(e)}", recoverable=True)


def history(ticker: str, period: str = "6mo", interval: str = "1d") -> ToolResult:
    """Get historical OHLCV data via yfinance."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)

        if df.empty:
            return ToolResult.fail(
                f"No history for '{ticker}' (period={period})",
                hint="Check ticker or try a different period.",
            )

        # Downsample if too many rows to keep context lean
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
        })

    except Exception as e:
        return ToolResult.fail(f"yfinance history error: {str(e)}", recoverable=True)


# Backward-compatible aliases (legacy names)
YF_QUOTE_SCHEMA = QUOTE_SCHEMA
YF_HISTORY_SCHEMA = HISTORY_SCHEMA


def yf_quote(ticker: str) -> ToolResult:
    return quote(ticker=ticker)


def yf_history(ticker: str, period: str = "6mo", interval: str = "1d") -> ToolResult:
    return history(ticker=ticker, period=period, interval=interval)
