import logging
import os
import httpx
import yfinance as yf
from .base import ToolResult, make_tool_schema

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"
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
    # Try FMP first
    result = _fmp_fetch(ticker, statement_type, period)
    if result.status == "ok":
        return result

    # FMP failed — fallback to yfinance
    logger.info("FMP failed (%s), falling back to yfinance for %s %s", result.error, ticker, statement_type)
    yf_result = _yf_financials_fallback(ticker, statement_type, period)
    if yf_result is not None:
        return yf_result

    # Both failed — return original FMP error
    return result


def _fmp_fetch(ticker: str, statement_type: str, period: str) -> ToolResult:
    """Try fetching from FMP API."""
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return ToolResult.fail("FMP_API_KEY not set", hint="Will fallback to Yahoo Finance")

    url = f"{FMP_BASE}/{statement_type}?symbol={ticker.upper()}&period={period}&limit=4&apikey={api_key}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        if not data:
            return ToolResult.fail(f"No FMP data for {ticker}")
        return ToolResult.ok({
            "ticker": ticker.upper(),
            "statement_type": statement_type,
            "period": period,
            "data": data[:2],
        })
    except httpx.HTTPStatusError as e:
        return ToolResult.fail(f"FMP API error: {e.response.status_code}", recoverable=True)
    except Exception as e:
        return ToolResult.fail(f"FMP fetch failed: {str(e)}", recoverable=True)


# ── yfinance field mapping ────────────────────────────────────

_YF_INCOME_FIELDS = {
    "revenue": "Total Revenue",
    "costOfRevenue": "Cost Of Revenue",
    "grossProfit": "Gross Profit",
    "operatingExpenses": "Operating Expense",
    "operatingIncome": "Operating Income",
    "netIncome": "Net Income",
    "ebitda": "EBITDA",
    "eps": "Basic EPS",
    "epsdiluted": "Diluted EPS",
    "researchAndDevelopmentExpenses": "Research And Development",
    "sellingGeneralAndAdministrativeExpenses": "Selling General And Administration",
    "interestExpense": "Interest Expense",
    "incomeBeforeTax": "Pretax Income",
    "incomeTaxExpense": "Tax Provision",
}

_YF_BALANCE_FIELDS = {
    "totalAssets": "Total Assets",
    "totalLiabilities": "Total Liabilities Net Minority Interest",
    "totalEquity": "Stockholders Equity",
    "cashAndShortTermInvestments": "Cash And Cash Equivalents",
    "totalDebt": "Total Debt",
    "netDebt": "Net Debt",
    "commonStock": "Common Stock",
    "retainedEarnings": "Retained Earnings",
    "totalCurrentAssets": "Current Assets",
    "totalCurrentLiabilities": "Current Liabilities",
}

_YF_CASHFLOW_FIELDS = {
    "operatingCashFlow": "Operating Cash Flow",
    "capitalExpenditure": "Capital Expenditure",
    "freeCashFlow": "Free Cash Flow",
    "dividendsPaid": "Cash Dividends Paid",
    "commonStockRepurchased": "Repurchase Of Capital Stock",
    "debtRepayment": "Repayment Of Debt",
    "debtIssuance": "Issuance Of Debt",
}

_STATEMENT_MAP = {
    "income-statement": ("income_stmt", "quarterly_income_stmt", _YF_INCOME_FIELDS),
    "balance-sheet-statement": ("balance_sheet", "quarterly_balance_sheet", _YF_BALANCE_FIELDS),
    "cash-flow-statement": ("cashflow", "quarterly_cashflow", _YF_CASHFLOW_FIELDS),
}


def _yf_financials_fallback(ticker: str, statement_type: str, period: str) -> ToolResult | None:
    """Fallback to yfinance for financial statements. Returns None if unsupported."""
    if statement_type == "profile":
        return _yf_profile_fallback(ticker)
    if statement_type == "ratios":
        return _yf_ratios_fallback(ticker)

    mapping = _STATEMENT_MAP.get(statement_type)
    if not mapping:
        return None

    annual_attr, quarterly_attr, field_map = mapping
    try:
        t = yf.Ticker(ticker)
        attr_name = quarterly_attr if period == "quarter" else annual_attr
        df = getattr(t, attr_name, None)
        if df is None or df.empty:
            return None

        # Take up to 4 most recent periods
        df = df.iloc[:, :4]

        rows = []
        for col in df.columns:
            row = {
                "date": col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col),
                "calendarYear": str(col.year) if hasattr(col, "year") else "",
            }
            for fmp_key, yf_key in field_map.items():
                if yf_key in df.index:
                    val = df.loc[yf_key, col]
                    row[fmp_key] = round(float(val), 2) if val == val else None  # NaN check
                else:
                    row[fmp_key] = None
            rows.append(row)

        if not rows:
            return None

        return ToolResult.ok({
            "ticker": ticker.upper(),
            "statement_type": statement_type,
            "period": period,
            "data": rows[:2],
            "_source": "yfinance",
        })
    except Exception as e:
        logger.warning("yfinance fallback failed for %s %s: %s", ticker, statement_type, e)
        return None


def _yf_profile_fallback(ticker: str) -> ToolResult | None:
    """Fallback for profile using yfinance info."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info:
            return None

        profile = {
            "symbol": ticker.upper(),
            "companyName": info.get("longName") or info.get("shortName", ""),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "mktCap": info.get("marketCap"),
            "pe": info.get("trailingPE"),
            "beta": info.get("beta"),
            "dividendYield": info.get("dividendYield"),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "exchange": info.get("exchange", ""),
            "currency": info.get("currency", "USD"),
            "description": (info.get("longBusinessSummary") or "")[:500],
        }
        return ToolResult.ok({
            "ticker": ticker.upper(),
            "statement_type": "profile",
            "period": "annual",
            "data": [profile],
            "_source": "yfinance",
        })
    except Exception as e:
        logger.warning("yfinance profile fallback failed for %s: %s", ticker, e)
        return None


def _yf_ratios_fallback(ticker: str) -> ToolResult | None:
    """Fallback for ratios using yfinance computed values."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        inc = t.income_stmt
        bs = t.balance_sheet

        if inc is None or inc.empty:
            return None

        def _safe(df, key, col):
            try:
                v = df.loc[key, col]
                return float(v) if v == v else None
            except (KeyError, IndexError):
                return None

        rows = []
        for col in inc.columns[:2]:
            revenue = _safe(inc, "Total Revenue", col)
            gross = _safe(inc, "Gross Profit", col)
            op_income = _safe(inc, "Operating Income", col)
            net_income = _safe(inc, "Net Income", col)

            equity = _safe(bs, "Stockholders Equity", col) if bs is not None and not bs.empty and col in bs.columns else None
            debt = _safe(bs, "Total Debt", col) if bs is not None and not bs.empty and col in bs.columns else None

            row = {
                "date": col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col),
                "calendarYear": str(col.year) if hasattr(col, "year") else "",
                "grossProfitMargin": round(gross / revenue, 4) if gross and revenue else None,
                "operatingProfitMargin": round(op_income / revenue, 4) if op_income and revenue else None,
                "netProfitMargin": round(net_income / revenue, 4) if net_income and revenue else None,
                "returnOnEquity": round(net_income / equity, 4) if net_income and equity else None,
                "debtEquityRatio": round(debt / equity, 4) if debt and equity else None,
            }
            rows.append(row)

        if not rows:
            return None

        return ToolResult.ok({
            "ticker": ticker.upper(),
            "statement_type": "ratios",
            "period": "annual",
            "data": rows,
            "_source": "yfinance",
        })
    except Exception as e:
        logger.warning("yfinance ratios fallback failed for %s: %s", ticker, e)
        return None


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
