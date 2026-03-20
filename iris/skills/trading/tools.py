"""
Trading Decision Skill — trade signals and paper portfolio.

Tools:
  generate_trade_signal: Evaluate buy/hold/sell based on hypothesis + valuation
  get_portfolio:         View current paper portfolio with live P&L
"""

import json
from datetime import datetime
from pathlib import Path

from core.config import get_skill_config
from tools.base import Tool, ToolResult, make_tool_schema


# ── Persistent portfolio state ──────────────────────────────

def _portfolio_path() -> Path:
    cfg = get_skill_config("trading")
    paper = cfg.get("paper_trading", {})
    fname = paper.get("portfolio_file", "portfolio.json")
    return Path("memory") / fname


def _load_portfolio() -> dict:
    """Load portfolio from disk, or initialize empty."""
    p = _portfolio_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    cfg = get_skill_config("trading")
    initial = cfg.get("paper_trading", {}).get("initial_capital", 1_000_000)
    return {
        "initial_capital": initial,
        "cash": initial,
        "positions": {},        # ticker -> position dict
        "closed_trades": [],    # list of completed round-trips
        "trade_log": [],        # every buy/sell event
    }


def _save_portfolio(portfolio: dict):
    p = _portfolio_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")


# ── Tool Schemas ─────────────────────────────────────────────

GENERATE_TRADE_SIGNAL_SCHEMA = make_tool_schema(
    name="generate_trade_signal",
    description=(
        "Evaluate whether to BUY, HOLD, TRIM, or SELL a stock based on hypothesis "
        "confidence, DCF fair value, current price, and portfolio constraints. "
        "Returns action, target_weight, reasoning, and constraint checks."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker, e.g. 'NVDA'",
        },
        "current_price": {
            "type": "number",
            "description": "Current market price per share",
        },
        "fair_value": {
            "type": "number",
            "description": "Fair value per share from DCF/valuation",
        },
        "hypothesis_confidence": {
            "type": "number", "minimum": 0, "maximum": 100,
            "description": "Current hypothesis confidence (0-100)",
        },
        "hypothesis_id": {
            "type": "string",
            "description": "Hypothesis ID for linking",
        },
        "sector": {
            "type": "string",
            "description": "Company sector for concentration check",
        },
        "catalyst": {
            "type": "string",
            "description": "Next expected catalyst and approximate timing",
        },
        "kill_criteria_status": {
            "type": "string", "enum": ["clear", "triggered", "at_risk"],
            "description": "Whether any kill criteria have triggered",
        },
    },
    required=[
        "ticker", "current_price", "fair_value",
        "hypothesis_confidence", "hypothesis_id",
        "sector", "kill_criteria_status",
    ],
)

GET_PORTFOLIO_SCHEMA = make_tool_schema(
    name="get_portfolio",
    description=(
        "View current paper portfolio: positions, cost basis, unrealized P&L, "
        "cash balance, and sector weights. Call quote first to get live prices, "
        "then pass them here for P&L calculation."
    ),
    properties={
        "live_prices": {
            "type": "object",
            "description": "Dict of ticker -> current price, e.g. {'NVDA': 142.5, 'AAPL': 195.0}. "
                           "Fetch via quote before calling this tool.",
        },
    },
    required=[],
)

RUN_ATTRIBUTION_SCHEMA = make_tool_schema(
    name="run_attribution",
    description=(
        "Run P&L attribution on a position or closed trade. Compares original "
        "analysis assumptions to actual outcomes. Decomposes return into alpha, "
        "timing, and sizing components.\n\n"
        "Call this after earnings are released or when closing a position."
    ),
    properties={
        "ticker": {"type": "string"},
        "original_assumptions": {
            "type": "object",
            "description": (
                "The key assumptions from the original DCF analysis: "
                "{'revenue_growth': 0.35, 'gross_margin': 0.745, 'opex_ratio': 0.165, ...}"
            ),
        },
        "actual_results": {
            "type": "object",
            "description": (
                "Actual financial results: "
                "{'revenue_growth': 0.42, 'gross_margin': 0.765, 'opex_ratio': 0.158, ...}"
            ),
        },
        "entry_price": {
            "type": "number",
            "description": "Price at which position was entered",
        },
        "current_price": {
            "type": "number",
            "description": "Current or exit price",
        },
        "benchmark_return": {
            "type": "number",
            "description": "Benchmark (e.g. SPY) return over same period, as decimal (0.05 = 5%)",
        },
        "sector_return": {
            "type": "number",
            "description": "Sector ETF return over same period, as decimal",
        },
        "hypothesis_id": {"type": "string"},
        "position_weight": {
            "type": "number",
            "description": "Portfolio weight at entry (e.g. 0.03 = 3%)",
        },
    },
    required=[
        "ticker", "original_assumptions", "actual_results",
        "entry_price", "current_price", "benchmark_return",
        "hypothesis_id",
    ],
)


# ── Tool Implementations ─────────────────────────────────────

def generate_trade_signal(
    ticker: str,
    current_price: float,
    fair_value: float,
    hypothesis_confidence: float,
    hypothesis_id: str,
    sector: str,
    kill_criteria_status: str,
    catalyst: str = "",
) -> ToolResult:
    """Evaluate trade signal from hypothesis + valuation + portfolio state."""
    cfg = get_skill_config("trading")
    min_discount = cfg.get("min_entry_discount", 0.20)
    min_confidence = cfg.get("min_confidence_entry", 60)
    sell_target_pct = cfg.get("sell_target_pct", 0.90)
    sizing_tiers = cfg.get("sizing_tiers", [])
    constraints = cfg.get("constraints", {})
    max_single = constraints.get("max_single_position", 0.05)
    max_sector = constraints.get("max_sector_weight", 0.20)

    portfolio = _load_portfolio()

    discount = (fair_value - current_price) / fair_value if fair_value > 0 else 0
    already_held = ticker.upper() in portfolio.get("positions", {})

    # ── Kill criteria override ──
    if kill_criteria_status == "triggered":
        if already_held:
            return ToolResult.ok({
                "action": "SELL",
                "ticker": ticker.upper(),
                "target_weight": 0.0,
                "reasoning": "Kill criteria triggered — mandatory exit regardless of price.",
                "signal_strength": "MANDATORY",
                "constraint_checks": ["kill_criteria_triggered"],
            })
        else:
            return ToolResult.ok({
                "action": "NO_ENTRY",
                "ticker": ticker.upper(),
                "target_weight": 0.0,
                "reasoning": "Kill criteria triggered — do not enter this position.",
                "signal_strength": "BLOCKED",
                "constraint_checks": ["kill_criteria_triggered"],
            })

    # ── Sell / Trim check for existing positions ──
    if already_held:
        pos = portfolio["positions"][ticker.upper()]
        if current_price >= fair_value * sell_target_pct:
            return ToolResult.ok({
                "action": "SELL",
                "ticker": ticker.upper(),
                "target_weight": 0.0,
                "reasoning": (
                    f"Price ${current_price:.2f} has reached {sell_target_pct*100:.0f}% of "
                    f"fair value ${fair_value:.2f}. Target achieved."
                ),
                "signal_strength": "STRONG",
                "unrealized_pnl_pct": round(
                    (current_price - pos["avg_cost"]) / pos["avg_cost"] * 100, 2
                ),
                "constraint_checks": [],
            })
        if hypothesis_confidence < min_confidence:
            return ToolResult.ok({
                "action": "TRIM",
                "ticker": ticker.upper(),
                "target_weight": 0.005,  # reduce to watch position
                "reasoning": (
                    f"Confidence ({hypothesis_confidence:.0f}) dropped below "
                    f"entry threshold ({min_confidence}). Reduce to watch position."
                ),
                "signal_strength": "MODERATE",
                "constraint_checks": ["confidence_below_threshold"],
            })
        # Hold
        return ToolResult.ok({
            "action": "HOLD",
            "ticker": ticker.upper(),
            "target_weight": pos.get("target_weight", 0),
            "reasoning": (
                f"Fair value ${fair_value:.2f}, current ${current_price:.2f} "
                f"({discount*100:.1f}% discount). Confidence {hypothesis_confidence:.0f}. "
                f"No action triggers met."
            ),
            "signal_strength": "NEUTRAL",
            "constraint_checks": [],
        })

    # ── New position evaluation ──
    constraint_checks = []

    if hypothesis_confidence < min_confidence:
        return ToolResult.ok({
            "action": "WATCH",
            "ticker": ticker.upper(),
            "target_weight": 0.0,
            "reasoning": (
                f"Confidence ({hypothesis_confidence:.0f}) below entry threshold "
                f"({min_confidence}). Add to watchlist, monitor for catalyst."
            ),
            "signal_strength": "WEAK",
            "constraint_checks": ["confidence_below_threshold"],
        })

    if discount < min_discount:
        return ToolResult.ok({
            "action": "WATCH",
            "ticker": ticker.upper(),
            "target_weight": 0.0,
            "reasoning": (
                f"Discount ({discount*100:.1f}%) below minimum entry threshold "
                f"({min_discount*100:.0f}%). Fair value ${fair_value:.2f}, "
                f"price ${current_price:.2f}. Wait for better entry."
            ),
            "signal_strength": "WEAK",
            "constraint_checks": ["insufficient_margin_of_safety"],
        })

    # Determine target weight from sizing tiers
    target_weight = 0.01  # default watch position
    conviction_label = "low_conviction"
    for tier in sizing_tiers:
        if tier["min_confidence"] <= hypothesis_confidence <= tier["max_confidence"]:
            target_weight = tier["target_weight"]
            conviction_label = tier["label"]
            break

    # Check portfolio constraints
    total_invested = sum(
        p.get("market_value", p["shares"] * p["avg_cost"])
        for p in portfolio.get("positions", {}).values()
    )
    total_portfolio_value = portfolio["cash"] + total_invested
    current_invested_pct = total_invested / total_portfolio_value if total_portfolio_value > 0 else 0

    max_total = constraints.get("max_total_invested", 0.90)
    if current_invested_pct + target_weight > max_total:
        adjusted = max(0, max_total - current_invested_pct)
        constraint_checks.append(
            f"total_invested_cap: reduced from {target_weight*100:.1f}% to {adjusted*100:.1f}%"
        )
        target_weight = adjusted

    if target_weight > max_single:
        constraint_checks.append(
            f"single_position_cap: reduced from {target_weight*100:.1f}% to {max_single*100:.1f}%"
        )
        target_weight = max_single

    # Sector concentration check
    sector_weight = sum(
        p.get("target_weight", 0)
        for p in portfolio.get("positions", {}).values()
        if p.get("sector", "").lower() == sector.lower()
    )
    if sector_weight + target_weight > max_sector:
        adjusted = max(0, max_sector - sector_weight)
        constraint_checks.append(
            f"sector_cap ({sector}): reduced from {target_weight*100:.1f}% to {adjusted*100:.1f}%"
        )
        target_weight = adjusted

    if target_weight <= 0:
        return ToolResult.ok({
            "action": "WATCH",
            "ticker": ticker.upper(),
            "target_weight": 0.0,
            "reasoning": "Portfolio constraints prevent new position. Add to watchlist.",
            "signal_strength": "BLOCKED",
            "constraint_checks": constraint_checks,
        })

    return ToolResult.ok({
        "action": "BUY",
        "ticker": ticker.upper(),
        "target_weight": round(target_weight, 4),
        "conviction": conviction_label,
        "discount_pct": round(discount * 100, 1),
        "reasoning": (
            f"Fair value ${fair_value:.2f} vs price ${current_price:.2f} "
            f"({discount*100:.1f}% discount). Confidence {hypothesis_confidence:.0f} "
            f"→ {conviction_label} ({target_weight*100:.1f}% weight). "
            f"Catalyst: {catalyst or 'not specified'}."
        ),
        "signal_strength": "STRONG" if hypothesis_confidence >= 85 else "MODERATE",
        "suggested_shares": _calc_shares(portfolio, target_weight, current_price),
        "constraint_checks": constraint_checks,
    })


def _calc_shares(portfolio: dict, target_weight: float, price: float) -> int:
    """Calculate number of shares for target weight."""
    total_invested = sum(
        p["shares"] * p["avg_cost"]
        for p in portfolio.get("positions", {}).values()
    )
    total_value = portfolio["cash"] + total_invested
    target_value = total_value * target_weight
    return int(target_value / price) if price > 0 else 0


def get_portfolio(live_prices: dict = None) -> ToolResult:
    """View current paper portfolio with P&L."""
    portfolio = _load_portfolio()
    live_prices = live_prices or {}

    positions_summary = []
    total_market_value = 0
    total_cost = 0

    for ticker, pos in portfolio.get("positions", {}).items():
        live_price = live_prices.get(ticker, live_prices.get(ticker.upper()))
        cost_basis = pos["shares"] * pos["avg_cost"]
        market_value = pos["shares"] * live_price if live_price else cost_basis

        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0

        total_market_value += market_value
        total_cost += cost_basis

        positions_summary.append({
            "ticker": ticker,
            "shares": pos["shares"],
            "avg_cost": round(pos["avg_cost"], 2),
            "live_price": live_price,
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "entry_date": pos.get("entry_date"),
            "hypothesis_id": pos.get("hypothesis_id"),
        })

    total_portfolio_value = portfolio["cash"] + total_market_value
    total_unrealized = total_market_value - total_cost
    total_return_pct = (
        (total_portfolio_value - portfolio["initial_capital"])
        / portfolio["initial_capital"] * 100
    ) if portfolio.get("initial_capital") else 0

    # Closed trade stats
    closed = portfolio.get("closed_trades", [])
    realized_pnl = sum(t.get("pnl", 0) for t in closed)
    win_count = sum(1 for t in closed if t.get("pnl", 0) > 0)
    loss_count = sum(1 for t in closed if t.get("pnl", 0) <= 0)

    return ToolResult.ok({
        "cash": round(portfolio["cash"], 2),
        "positions": positions_summary,
        "total_market_value": round(total_market_value, 2),
        "total_portfolio_value": round(total_portfolio_value, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_realized_pnl": round(realized_pnl, 2),
        "total_return_pct": round(total_return_pct, 2),
        "position_count": len(positions_summary),
        "win_loss": f"{win_count}W / {loss_count}L" if closed else "no closed trades",
        "invested_pct": round(total_market_value / total_portfolio_value * 100, 1)
            if total_portfolio_value > 0 else 0,
    })


# ── Registration ─────────────────────────────────────────────

def register(context: dict) -> list[Tool]:
    """Called by skill_loader with shared dependencies."""
    return [
        Tool(generate_trade_signal, GENERATE_TRADE_SIGNAL_SCHEMA),
        Tool(get_portfolio, GET_PORTFOLIO_SCHEMA),
    ]
