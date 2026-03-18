import os
import httpx
from .base import ToolResult, make_tool_schema

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FRED_BASE = "https://api.stlouisfed.org/fred"

FMP_GET_FINANCIALS_SCHEMA = make_tool_schema(
    name="fmp_get_financials",
    description=(
        "Get structured financial data for a public company: income statement, balance sheet, "
        "cash flow statement, or company profile. Use when you need specific financial figures "
        "like revenue, EBITDA, EPS, P/E ratio, debt levels."
    ),
    properties={
        "ticker": {"type": "string", "description": "Stock ticker, e.g. 'NVDA', 'AAPL'"},
        "statement_type": {
            "type": "string",
            "enum": ["income-statement", "balance-sheet-statement", "cash-flow-statement", "profile", "ratios"],
        },
        "period": {
            "type": "string",
            "enum": ["annual", "quarter"],
            "description": "Annual or quarterly data. Default annual.",
        },
    },
    required=["ticker", "statement_type"],
)

FRED_GET_MACRO_SCHEMA = make_tool_schema(
    name="fred_get_macro",
    description=(
        "Get macroeconomic data from FRED. "
        "Series IDs: GDP, CPIAUCSL (CPI inflation), FEDFUNDS (fed funds rate), UNRATE (unemployment), DGS10 (10yr treasury)"
    ),
    properties={
        "series_id": {
            "type": "string",
            "description": "FRED series ID, e.g. 'GDP', 'CPIAUCSL', 'FEDFUNDS', 'DGS10'",
        },
        "limit": {
            "type": "integer",
            "description": "Number of most recent observations. Default 4.",
        },
    },
    required=["series_id"],
)


def fmp_get_financials(ticker: str, statement_type: str, period: str = "annual") -> ToolResult:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return ToolResult.fail("FMP_API_KEY not set", hint="Add to .env file")

    url = f"{FMP_BASE}/{statement_type}/{ticker.upper()}?period={period}&limit=4&apikey={api_key}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        if not data:
            return ToolResult.fail(
                f"No financial data found for {ticker}",
                hint="Verify the ticker is correct and listed on a major exchange",
            )
        return ToolResult.ok({
            "ticker": ticker.upper(),
            "statement_type": statement_type,
            "period": period,
            "data": data[:2],
        })
    except httpx.HTTPStatusError as e:
        return ToolResult.fail(f"FMP API error: {e.response.status_code}", recoverable=True)
    except Exception as e:
        return ToolResult.fail(f"Financial data fetch failed: {str(e)}", recoverable=False)


def fred_get_macro(series_id: str, limit: int = 4) -> ToolResult:
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return ToolResult.fail("FRED_API_KEY not set", hint="Add to .env file")

    url = (
        f"{FRED_BASE}/series/observations"
        f"?series_id={series_id}&api_key={api_key}&file_type=json"
        f"&sort_order=desc&limit={limit}"
    )
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        observations = data.get("observations", [])
        if not observations:
            return ToolResult.fail(
                f"No FRED data for series {series_id}",
                hint="Check the series ID at fred.stlouisfed.org",
            )
        return ToolResult.ok({
            "series_id": series_id,
            "observations": [
                {"date": o["date"], "value": o["value"]}
                for o in observations
                if o["value"] != "."
            ],
        })
    except Exception as e:
        return ToolResult.fail(f"FRED fetch failed: {str(e)}", recoverable=False)
