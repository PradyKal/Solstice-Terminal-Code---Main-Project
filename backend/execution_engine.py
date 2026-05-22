"""
EXECUTION ENGINE
- Sends paper orders to Alpaca via gumcp_client (when available) or REST.
- Hard-gated by US equity market hours.
- Returns broker_order_id for ledger reconciliation.
"""
from __future__ import annotations
import os
import json
from datetime import datetime, time
import pytz
from typing import Dict, Optional


def is_market_open() -> bool:
    tz = pytz.timezone("US/Eastern")
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    return time(9, 30) <= now.time() <= time(16, 0)


def submit_alpaca_paper(ticker: str, side: str, qty: float,
                       order_type: str = "market",
                       time_in_force: str = "day") -> Dict:
    """
    Attempts to submit via gumcp_client. Returns broker response or error dict.
    """
    try:
        from gumcp_client import Client
        client = Client(
            user_id=os.getenv("GUMCP_USER_ID"),
            gumcp_api_key=os.getenv("GUMCP_ACCESS_TOKEN") or os.getenv("GUMCP_API_KEY"),
            base_url=os.getenv("GUMCP_BASE_URL"),
        )
        raw = client.call_tool(
            "alpaca_api_paper_trading__create_order",
            {
                "symbol": ticker,
                "qty": qty,
                "side": side.lower(),
                "type": order_type,
                "time_in_force": time_in_force,
            },
        )
        return json.loads(raw[0]) if raw else {"error": "empty response"}
    except Exception as e:
        return {"error": str(e), "broker_order_id": None}


def execute_validated(trade: Dict) -> Dict:
    """trade: {ticker, side, qty, entry_price, ...}; returns enriched record."""
    if not is_market_open():
        return {**trade, "status": "SKIPPED_MARKET_CLOSED", "broker_order_id": None}
    resp = submit_alpaca_paper(trade["ticker"], trade["side"], trade["qty"])
    if "error" in resp and resp.get("broker_order_id") is None:
        return {**trade, "status": "REJECTED_BROKER_ERROR", "broker_order_id": None,
                "notes": resp.get("error", "")[:200]}
    return {
        **trade,
        "status": "SUBMITTED",
        "broker": "alpaca_paper",
        "broker_order_id": resp.get("id") or resp.get("broker_order_id"),
    }
