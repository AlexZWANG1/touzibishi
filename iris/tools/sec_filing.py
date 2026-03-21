"""
SEC Filing tool — wraps edgartools for 10-K/10-Q text sections and financial data.

Provides structured access to:
- Filing text sections (Business, Risk Factors, MD&A, Financial Statements, etc.)
- Key financial metrics from XBRL (revenue, operating income, etc.)
- Filing metadata and search
"""

import logging
import os
from .base import ToolResult, make_tool_schema

logger = logging.getLogger(__name__)

SEC_FILING_SCHEMA = make_tool_schema(
    name="sec_filing",
    description=(
        "Access SEC EDGAR filings (10-K, 10-Q) for US public companies. "
        "Can extract specific text sections like MD&A (which contains segment revenue/operating "
        "income discussion), Business description, Risk Factors, Financial Statements notes. "
        "Also provides key XBRL financial metrics. "
        "Use this when you need official company disclosures that web_fetch struggles to retrieve, "
        "especially segment-level discussions from MD&A or Financial Statement notes."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker, e.g. 'MSFT', 'GOOGL'",
        },
        "action": {
            "type": "string",
            "enum": ["section", "metrics", "filing_list"],
            "description": (
                "'section' — extract a text section from the latest filing (see section_name). "
                "'metrics' — key XBRL financial metrics (revenue, operating income, etc.). "
                "'filing_list' — list recent filings for this company."
            ),
        },
        "filing_type": {
            "type": "string",
            "enum": ["10-K", "10-Q"],
            "description": "Filing type. Default '10-K'.",
        },
        "section_name": {
            "type": "string",
            "enum": [
                "Business", "Risk Factors", "MD&A", "Financial Statements",
                "Controls", "Properties", "Legal",
            ],
            "description": (
                "For action='section': which section to extract. "
                "'MD&A' is best for segment revenue/income discussion. "
                "'Financial Statements' for notes including segment tables."
            ),
        },
        "max_chars": {
            "type": "integer",
            "description": "Max characters to return for text sections. Default 8000.",
        },
    },
    required=["ticker", "action"],
)


def _ensure_edgar():
    """Check edgartools is installed."""
    try:
        import edgar
        return edgar, None
    except ImportError:
        return None, "edgartools not installed. Run: pip install edgartools"


def sec_filing(
    ticker: str,
    action: str,
    filing_type: str = "10-K",
    section_name: str = None,
    max_chars: int = 8000,
) -> ToolResult:
    """Main entry point for SEC filing tool."""
    edgar, err = _ensure_edgar()
    if err:
        return ToolResult.fail(err, hint="pip install edgartools", recoverable=False)

    # Set identity for SEC EDGAR (required)
    identity = os.getenv("SEC_EDGAR_IDENTITY", "IRIS ResearchBot admin@iris-research.local")
    try:
        edgar.set_identity(identity)
    except Exception:
        pass

    ticker_upper = ticker.upper()

    try:
        if action == "filing_list":
            return _filing_list(edgar, ticker_upper, filing_type)
        elif action == "metrics":
            return _xbrl_metrics(edgar, ticker_upper, filing_type)
        elif action == "section":
            return _filing_section(edgar, ticker_upper, filing_type, section_name, max_chars)
        else:
            return ToolResult.fail(f"Unknown action: {action}")
    except Exception as e:
        logger.exception("sec_filing error for %s/%s", ticker, action)
        return ToolResult.fail(f"SEC filing error: {str(e)}", recoverable=True)


def _filing_list(edgar, ticker: str, filing_type: str) -> ToolResult:
    """List recent filings for a company."""
    company = edgar.Company(ticker)
    filings = company.get_filings(form=filing_type)

    results = []
    for f in filings.latest(5):
        results.append({
            "form": f.form,
            "filed": str(f.filing_date),
            "accession": f.accession_no,
        })

    return ToolResult.ok({
        "ticker": ticker,
        "filing_type": filing_type,
        "filings": results,
    })


def _xbrl_metrics(edgar, ticker: str, filing_type: str) -> ToolResult:
    """Extract key XBRL financial metrics from the latest filing."""
    company = edgar.Company(ticker)
    filing = company.get_filings(form=filing_type).latest(1)
    if not filing:
        return ToolResult.fail(f"No {filing_type} filing found for {ticker}")

    obj = filing.obj()
    fins = obj.financials

    metrics = {"ticker": ticker, "filing_type": filing_type, "filed": str(filing.filing_date)}

    # Extract key metrics
    extractors = {
        "revenue": fins.get_revenue,
        "operating_income": fins.get_operating_income,
        "net_income": fins.get_net_income,
        "operating_cash_flow": fins.get_operating_cash_flow,
        "capex": fins.get_capital_expenditures,
        "free_cash_flow": fins.get_free_cash_flow,
        "total_assets": fins.get_total_assets,
        "total_liabilities": fins.get_total_liabilities,
        "shareholders_equity": fins.get_stockholders_equity,
        "shares_outstanding_basic": fins.get_shares_outstanding_basic,
        "shares_outstanding_diluted": fins.get_shares_outstanding_diluted,
    }

    for name, fn in extractors.items():
        try:
            result = fn()
            if result is not None:
                # UnitResult has .value attribute
                val = getattr(result, 'value', result)
                if val is not None:
                    metrics[name] = val
        except Exception:
            pass

    # Try to get financial metrics (ratios)
    try:
        fm = fins.get_financial_metrics()
        if fm:
            metrics["financial_metrics"] = {k: v for k, v in fm.items() if v is not None} if isinstance(fm, dict) else str(fm)[:500]
    except Exception:
        pass

    return ToolResult.ok(metrics)


# Map user-friendly section names to 10-K item numbers and TenK attributes
_SECTION_MAP = {
    "business": ("Item 1", "business"),
    "risk factors": ("Item 1A", "risk_factors"),
    "properties": ("Item 2", None),
    "legal": ("Item 3", None),
    "md&a": ("Item 7", "management_discussion"),
    "financial statements": ("Item 8", None),
    "controls": ("Item 9A", None),
}


def _filing_section(edgar, ticker: str, filing_type: str, section_name: str, max_chars: int) -> ToolResult:
    """Extract a specific text section from the filing."""
    if not section_name:
        return ToolResult.fail(
            "section_name is required for action='section'",
            hint="Use one of: Business, Risk Factors, MD&A, Financial Statements, Controls",
        )

    company = edgar.Company(ticker)
    filing = company.get_filings(form=filing_type).latest(1)
    if not filing:
        return ToolResult.fail(f"No {filing_type} filing found for {ticker}")

    obj = filing.obj()
    search_key = section_name.lower().strip()
    item_key, attr_name = _SECTION_MAP.get(search_key, (None, None))

    content = None

    # Try direct attribute access first (fast path)
    if attr_name:
        try:
            val = getattr(obj, attr_name, None)
            if val:
                content = str(val)
        except Exception:
            pass

    # Try item-based access
    if not content and item_key:
        try:
            val = obj.get_item_with_part(item_key, None)
            if val:
                content = str(val)
        except Exception:
            pass

    # Fallback: search in available items
    if not content:
        available_items = getattr(obj, 'items', [])
        for item in available_items:
            if item_key and item.lower() == item_key.lower():
                try:
                    val = obj.get_item_with_part(item, None)
                    if val:
                        content = str(val)
                        break
                except Exception:
                    continue

    if not content:
        available = getattr(obj, 'items', [])
        return ToolResult.fail(
            f"Could not extract section '{section_name}' from {ticker} {filing_type}",
            hint=f"Available items: {available}. Try a different section_name.",
        )

    # Truncate
    truncated = len(content) > max_chars
    full_length = len(content)
    content = content[:max_chars]

    return ToolResult.ok({
        "ticker": ticker,
        "filing_type": filing_type,
        "filed": str(filing.filing_date),
        "section": section_name,
        "content": content,
        "truncated": truncated,
        "char_count": len(content),
        "total_chars": full_length,
    })
