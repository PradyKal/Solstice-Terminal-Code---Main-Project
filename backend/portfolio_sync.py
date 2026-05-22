"""
PORTFOLIO SYNC
Pulls live Alpaca state every cycle and mirrors it into Supabase so Lovable
reads directly from Supabase realtime (never from Alpaca directly).
"""
from __future__ import annotations
import time
from typing import Dict, List
import requests
from .execution_engine import _headers, _base


def fetch_account() -> Dict:
    r = requests.get(f"{_base()}/account", headers=_headers(), timeout=10)
    return r.json() if r.ok else {}


def fetch_positions() -> List[Dict]:
    r = requests.get(f"{_base()}/positions", headers=_headers(), timeout=10)
    return r.json() if r.ok else []


def fetch_open_orders() -> List[Dict]:
    r = requests.get(f"{_base()}/orders?status=open", headers=_headers(), timeout=10)
    return r.json() if r.ok else []


def build_account_state_row(account: Dict, positions: List[Dict],
                             open_orders: List[Dict]) -> Dict:
    """Single row that captures the current Alpaca state for the terminal header."""
    return {
        "account_number": account.get("account_number"),
        "status": account.get("status"),
        "equity": float(account.get("equity", 0) or 0),
        "cash": float(account.get("cash", 0) or 0),
        "buying_power": float(account.get("buying_power", 0) or 0),
        "portfolio_value": float(account.get("portfolio_value", 0) or 0),
        "long_market_value": float(account.get("long_market_value", 0) or 0),
        "short_market_value": float(account.get("short_market_value", 0) or 0),
        "pattern_day_trader": bool(account.get("pattern_day_trader", False)),
        "open_orders": open_orders,
        "open_positions": positions,
    }


def build_positions_rows(positions: List[Dict]) -> List[Dict]:
    """Normalized rows for the `positions` table."""
    out = []
    for p in positions:
        try:
            qty = float(p.get("qty", 0))
            mp = float(p.get("market_value", 0)) / qty if qty else 0.0
            out.append({
                "ticker": p.get("symbol"),
                "qty": qty,
                "avg_entry": float(p.get("avg_entry_price", 0) or 0),
                "mark_price": float(p.get("current_price", mp) or mp),
                "unrealized_pnl": float(p.get("unrealized_pl", 0) or 0),
                "asset_class": p.get("asset_class"),
            })
        except Exception:
            continue
    return out
