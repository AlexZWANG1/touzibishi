"""
Unified Valuation Skill.

Single tool:
  valuation(mode="dcf"|"comps"|"full", ticker, assumptions, peers)
"""

from __future__ import annotations

from tools.base import Tool, ToolResult, make_tool_schema


VALUATION_SCHEMA = make_tool_schema(
    name="valuation",
    description=(
        "Unified valuation tool. "
        "mode='dcf': run DCF model from assumptions. "
        "mode='comps': run peer multiples comparison. "
        "mode='full': run both and provide a cross-check summary."
    ),
    properties={
        "mode": {
            "type": "string",
            "enum": ["dcf", "comps", "full"],
            "description": "Valuation mode. Use 'full' for DCF + peer cross-check in one call.",
        },
        "ticker": {
            "type": "string",
            "description": "Target ticker, e.g. 'NVDA'. For dcf mode, can also be provided inside assumptions.",
        },
        "assumptions": {
            "type": "object",
            "description": "DCF assumptions object. Required for mode='dcf' and mode='full'.",
        },
        "peers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Peer tickers for comps mode, e.g. ['AMD', 'AVGO', 'INTC'].",
        },
    },
    required=["mode"],
)


def _first_error(result: ToolResult, default: str) -> str:
    return result.error or default


def _infer_ticker(ticker: str | None, assumptions: dict | None) -> str:
    if ticker:
        return str(ticker).upper()
    if assumptions and assumptions.get("ticker"):
        return str(assumptions["ticker"]).upper()
    return ""


def _cross_check(dcf_data: dict | None, comps_data: dict | None) -> dict | None:
    if not dcf_data or not comps_data:
        return None

    implied = (dcf_data.get("implied_multiples") or {}).get("fwd_pe")
    peer_median = (comps_data.get("median") or {}).get("fwd_pe")
    if implied is None or peer_median in (None, 0):
        return {
            "status": "insufficient_data",
            "message": "Could not compare DCF implied Fwd P/E with peer median.",
        }

    ratio = implied / peer_median
    premium = ratio - 1

    if ratio >= 2:
        status = "stretched"
        msg = "DCF implied Fwd P/E is >= 2x peer median. Re-check assumptions."
    elif ratio <= 0.5:
        status = "conservative"
        msg = "DCF implied Fwd P/E is <= 0.5x peer median. Assumptions may be too conservative."
    else:
        status = "aligned"
        msg = "DCF implied Fwd P/E is broadly aligned with peer median."

    return {
        "status": status,
        "message": msg,
        "implied_fwd_pe": round(implied, 2),
        "peer_median_fwd_pe": round(peer_median, 2),
        "premium_vs_peers": round(premium, 4),
    }


def valuation(
    mode: str,
    ticker: str = "",
    assumptions: dict | None = None,
    peers: list[str] | None = None,
) -> ToolResult:
    from skills.dcf.tools import build_dcf, get_comps

    mode = (mode or "").lower().strip()
    if mode not in {"dcf", "comps", "full"}:
        return ToolResult.fail(
            f"Invalid mode: {mode}",
            hint="Use one of: dcf, comps, full",
        )

    assumptions = assumptions or {}
    peers = peers or []
    target = _infer_ticker(ticker, assumptions)

    run_dcf = mode in {"dcf", "full"}
    run_comps = mode in {"comps", "full"}

    if run_dcf and not assumptions:
        return ToolResult.fail(
            "assumptions is required for dcf/full mode",
            hint="Provide the full DCF assumptions object.",
        )

    if run_comps and not target:
        return ToolResult.fail(
            "ticker is required for comps/full mode",
            hint="Provide ticker directly or inside assumptions.ticker.",
        )

    if run_comps and not peers:
        return ToolResult.fail(
            "peers is required for comps/full mode",
            hint="Provide at least 1 peer ticker.",
        )

    dcf_data = None
    comps_data = None

    if run_dcf:
        # Respect explicit ticker if provided.
        if target and not assumptions.get("ticker"):
            assumptions = dict(assumptions)
            assumptions["ticker"] = target
        dcf_result = build_dcf(assumptions=assumptions)
        if dcf_result.status != "ok":
            return ToolResult.fail(_first_error(dcf_result, "DCF valuation failed"))
        dcf_data = dcf_result.data
        target = _infer_ticker(target, assumptions)

    if run_comps:
        comps_result = get_comps(ticker=target, peers=peers)
        if comps_result.status != "ok":
            return ToolResult.fail(_first_error(comps_result, "Comps valuation failed"))
        comps_data = comps_result.data

    payload: dict = {
        "mode": mode,
        "ticker": target,
        "dcf": dcf_data,
        "comps": comps_data,
        "cross_check": _cross_check(dcf_data, comps_data),
    }

    # Flatten key outputs for easier downstream consumption.
    if dcf_data:
        payload["fair_value_per_share"] = dcf_data.get("fair_value_per_share")
        payload["current_price"] = dcf_data.get("current_price")
        payload["gap_pct"] = dcf_data.get("gap_pct")
        payload["implied_multiples"] = dcf_data.get("implied_multiples")
        payload["year_by_year"] = dcf_data.get("year_by_year")
        payload["sensitivity"] = dcf_data.get("sensitivity")

    if comps_data:
        payload["peers"] = comps_data.get("peers")
        payload["median"] = comps_data.get("median")
        payload["target_vs_median"] = comps_data.get("target_vs_median")

    return ToolResult.ok(payload)


def register(context: dict) -> list[Tool]:
    return [Tool(valuation, VALUATION_SCHEMA)]
