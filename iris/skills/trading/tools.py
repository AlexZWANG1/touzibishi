"""
Trading Skill — trade signals and paper portfolio.

Tools:
  generate_trade_signal: AI outputs its trade recommendation
  execute_trade:         Execute a confirmed trade (called after user approval)
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
        "positions": {},
        "closed_trades": [],
        "trade_log": [],
    }


def _save_portfolio(portfolio: dict):
    p = _portfolio_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(portfolio, indent=2, default=str), encoding="utf-8")


# ── Tool Schemas ─────────────────────────────────────────────

GENERATE_TRADE_SIGNAL_SCHEMA = make_tool_schema(
    name="generate_trade_signal",
    description=(
        "Output your trade recommendation after completing analysis. "
        "Include direction, target price, stop loss, position size, catalysts, and reasoning. "
        "This is a recommendation — execution happens only after user confirms in the UI."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker, e.g. 'NVDA'",
        },
        "action": {
            "type": "string",
            "enum": ["BUY", "SELL", "TRIM", "HOLD", "WATCH"],
            "description": "Trade direction",
        },
        "price": {
            "type": "number",
            "description": "Current market price",
        },
        "target_price": {
            "type": "number",
            "description": "Target price based on valuation analysis",
        },
        "stop_loss": {
            "type": "number",
            "description": "Stop loss price — exit if breached",
        },
        "position_pct": {
            "type": "number",
            "description": "Suggested position size as % of total portfolio (e.g. 5.0 = 5%)",
        },
        "catalysts": {
            "type": "string",
            "description": "Key catalysts and expected timing",
        },
        "reasoning": {
            "type": "string",
            "description": "One-paragraph reasoning for this trade",
        },
    },
    required=["ticker", "action", "price", "reasoning"],
)

EXECUTE_TRADE_SCHEMA = make_tool_schema(
    name="execute_trade",
    description=(
        "Execute a trade in the paper portfolio. Called after user confirms "
        "the trade signal in the UI. Buys or sells shares and updates portfolio."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Stock ticker",
        },
        "action": {
            "type": "string",
            "enum": ["BUY", "SELL"],
            "description": "Buy or sell",
        },
        "shares": {
            "type": "integer",
            "description": "Number of shares to trade",
        },
        "price": {
            "type": "number",
            "description": "Execution price per share",
        },
    },
    required=["ticker", "action", "shares", "price"],
)

GET_PORTFOLIO_SCHEMA = make_tool_schema(
    name="get_portfolio",
    description=(
        "View current paper portfolio: positions, cost basis, unrealized P&L, "
        "cash balance. Call quote first to get live prices, "
        "then pass them here for P&L calculation."
    ),
    properties={
        "live_prices": {
            "type": "object",
            "description": "Dict of ticker -> current price, e.g. {'NVDA': 142.5}",
        },
    },
    required=[],
)


# ── Tool Implementations ─────────────────────────────────────

def generate_trade_signal(
    ticker: str,
    action: str,
    price: float,
    reasoning: str,
    target_price: float = 0,
    stop_loss: float = 0,
    position_pct: float = 0,
    catalysts: str = "",
) -> ToolResult:
    """Record AI's trade recommendation. No execution — just data for the UI."""
    portfolio = _load_portfolio()
    already_held = ticker.upper() in portfolio.get("positions", {})

    # Compute risk/reward ratio
    risk_reward_ratio = None
    if action == "BUY" and target_price > 0 and stop_loss > 0 and price > stop_loss:
        upside = target_price - price
        downside = price - stop_loss
        if downside > 0:
            risk_reward_ratio = round(upside / downside, 2)

    # Soft warnings
    warnings = []
    total_invested = sum(
        p["shares"] * p["avg_cost"]
        for p in portfolio.get("positions", {}).values()
    )
    total_value = portfolio["cash"] + total_invested

    if action == "BUY" and position_pct > 0:
        if position_pct / 100 * total_value > portfolio["cash"]:
            warnings.append(f"Position size ${position_pct/100*total_value:,.0f} exceeds available cash ${portfolio['cash']:,.0f}.")
        if already_held:
            existing_pct = (portfolio["positions"][ticker.upper()]["shares"] * portfolio["positions"][ticker.upper()]["avg_cost"]) / total_value * 100
            warnings.append(f"Already hold {ticker.upper()} at {existing_pct:.1f}% of portfolio. Adding would increase exposure.")

    if risk_reward_ratio is not None and risk_reward_ratio < 1.5:
        warnings.append(f"Risk/reward ratio is {risk_reward_ratio}:1 — below typical 1.5:1 threshold.")

    # Calculate suggested shares if BUY
    suggested_shares = 0
    if action == "BUY" and position_pct > 0 and price > 0:
        target_value = total_value * (position_pct / 100)
        suggested_shares = int(target_value / price)

    # For SELL/TRIM on existing position, suggest all/half shares
    if action in ("SELL", "TRIM") and already_held:
        pos = portfolio["positions"][ticker.upper()]
        suggested_shares = pos["shares"] if action == "SELL" else max(1, pos["shares"] // 2)

    return ToolResult.ok({
        "ticker": ticker.upper(),
        "action": action,
        "price": price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "position_pct": round(position_pct, 2),
        "catalysts": catalysts,
        "reasoning": reasoning,
        "suggested_shares": suggested_shares,
        "already_held": already_held,
        "risk_reward_ratio": risk_reward_ratio,
        "warnings": warnings,
    })


def execute_trade(
    ticker: str,
    action: str,
    shares: int,
    price: float,
) -> ToolResult:
    """Execute trade in paper portfolio."""
    ticker = ticker.upper()
    portfolio = _load_portfolio()

    if action == "BUY":
        cost = shares * price
        if cost > portfolio["cash"]:
            return ToolResult.fail(
                f"Insufficient cash: need ${cost:,.2f}, have ${portfolio['cash']:,.2f}"
            )

        portfolio["cash"] -= cost

        if ticker in portfolio["positions"]:
            pos = portfolio["positions"][ticker]
            total_shares = pos["shares"] + shares
            total_cost = pos["shares"] * pos["avg_cost"] + cost
            pos["avg_cost"] = total_cost / total_shares
            pos["shares"] = total_shares
        else:
            portfolio["positions"][ticker] = {
                "shares": shares,
                "avg_cost": price,
                "entry_date": datetime.now().isoformat(),
            }

        portfolio["trade_log"].append({
            "ticker": ticker,
            "action": "BUY",
            "shares": shares,
            "price": price,
            "timestamp": datetime.now().isoformat(),
        })

    elif action == "SELL":
        if ticker not in portfolio["positions"]:
            return ToolResult.fail(f"No position in {ticker}")

        pos = portfolio["positions"][ticker]
        if shares > pos["shares"]:
            return ToolResult.fail(
                f"Only hold {pos['shares']} shares of {ticker}"
            )

        proceeds = shares * price
        cost_basis = shares * pos["avg_cost"]
        pnl = proceeds - cost_basis
        portfolio["cash"] += proceeds

        if shares == pos["shares"]:
            # Close entire position
            portfolio["closed_trades"].append({
                "ticker": ticker,
                "shares": shares,
                "entry_price": pos["avg_cost"],
                "exit_price": price,
                "pnl": round(pnl, 2),
                "entry_date": pos.get("entry_date"),
                "exit_date": datetime.now().isoformat(),
            })
            del portfolio["positions"][ticker]
        else:
            pos["shares"] -= shares

        portfolio["trade_log"].append({
            "ticker": ticker,
            "action": "SELL",
            "shares": shares,
            "price": price,
            "pnl": round(pnl, 2),
            "timestamp": datetime.now().isoformat(),
        })

    _save_portfolio(portfolio)

    # Compute portfolio summary after trade
    total_invested = sum(
        p["shares"] * p["avg_cost"]
        for p in portfolio.get("positions", {}).values()
    )
    total_value = portfolio["cash"] + total_invested
    closed = portfolio.get("closed_trades", [])
    realized = sum(t.get("pnl", 0) for t in closed)

    return ToolResult.ok({
        "status": "executed",
        "ticker": ticker,
        "action": action,
        "shares": shares,
        "price": price,
        "portfolio_after": {
            "cash": round(portfolio["cash"], 2),
            "position_count": len(portfolio.get("positions", {})),
            "total_value": round(total_value, 2),
            "total_realized_pnl": round(realized, 2),
        },
    })


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
        })

    total_portfolio_value = portfolio["cash"] + total_market_value
    total_unrealized = total_market_value - total_cost
    total_return_pct = (
        (total_portfolio_value - portfolio["initial_capital"])
        / portfolio["initial_capital"] * 100
    ) if portfolio.get("initial_capital") else 0

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


REVIEW_TRADES_SCHEMA = make_tool_schema(
    name="review_trades",
    description=(
        "Review past trading performance: open positions with current P&L, "
        "closed trades with realized P&L, and holding periods. "
        "Use in learning mode to compare predictions with outcomes."
    ),
    properties={
        "ticker": {
            "type": "string",
            "description": "Optional: filter to a specific ticker",
        },
    },
    required=[],
)


def review_trades(ticker: str = None) -> ToolResult:
    """Read-only review of trading history for reflection."""
    portfolio = _load_portfolio()

    # Open positions
    open_positions = []
    for t, pos in portfolio.get("positions", {}).items():
        if ticker and t.upper() != ticker.upper():
            continue
        open_positions.append({
            "ticker": t,
            "shares": pos["shares"],
            "entry_price": round(pos["avg_cost"], 2),
            "entry_date": pos.get("entry_date"),
        })

    # Closed trades
    closed_trades = []
    for trade in portfolio.get("closed_trades", []):
        if ticker and trade.get("ticker", "").upper() != ticker.upper():
            continue
        entry = trade.get("entry_price", 0)
        exit_p = trade.get("exit_price", 0)
        pnl_pct = ((exit_p - entry) / entry * 100) if entry > 0 else 0
        # Compute holding days
        holding_days = None
        if trade.get("entry_date") and trade.get("exit_date"):
            try:
                entry_dt = datetime.fromisoformat(trade["entry_date"].replace("Z", "+00:00"))
                exit_dt = datetime.fromisoformat(trade["exit_date"].replace("Z", "+00:00"))
                holding_days = (exit_dt - entry_dt).days
            except Exception:
                pass
        closed_trades.append({
            "ticker": trade.get("ticker"),
            "entry_price": round(entry, 2),
            "exit_price": round(exit_p, 2),
            "pnl": round(trade.get("pnl", 0), 2),
            "pnl_pct": round(pnl_pct, 1),
            "holding_days": holding_days,
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
        })

    # Summary stats
    total_closed = len(closed_trades)
    wins = sum(1 for t in closed_trades if t["pnl"] > 0)
    losses = total_closed - wins
    total_pnl = sum(t["pnl"] for t in closed_trades)

    return ToolResult.ok({
        "open_positions": open_positions,
        "closed_trades": closed_trades,
        "summary": {
            "open_count": len(open_positions),
            "closed_count": total_closed,
            "win_rate": f"{wins}/{total_closed}" if total_closed > 0 else "N/A",
            "total_realized_pnl": round(total_pnl, 2),
        },
    })


# ── Registration ─────────────────────────────────────────────

def register(context: dict) -> list[Tool]:
    return [
        Tool(generate_trade_signal, GENERATE_TRADE_SIGNAL_SCHEMA),
        Tool(execute_trade, EXECUTE_TRADE_SCHEMA),
        Tool(get_portfolio, GET_PORTFOLIO_SCHEMA),
        Tool(review_trades, REVIEW_TRADES_SCHEMA),
    ]
