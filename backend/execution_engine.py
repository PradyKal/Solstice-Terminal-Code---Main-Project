"""
EXECUTION ENGINE — direct Alpaca REST integration

- Credentials are loaded from Supabase `secrets` table (service-role) so the
  autonomous schedule never has to handle keys directly.
- Hard-gated by US equity market hours via Alpaca's own /v2/clock endpoint
  (avoids holiday-calendar drift).
- All orders are paper. Live trading is intentionally NOT implemented here.
"""
from __future__ import annotations
import os
import time
from typing import Dict, Optional
import requests


_CACHED_SECRETS: Dict[str, str] | None = None


def _load_secrets() -> Dict[str, str]:
    """Load Alpaca creds from Supabase `secrets` table.
    Falls back to env vars when Supabase is unreachable.
    """
    global _CACHED_SECRETS
    if _CACHED_SECRETS is not None:
        return _CACHED_SECRETS
    out: Dict[str, str] = {}
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if url and key:
            client = create_client(url, key)
            res = client.table("secrets").select("key,value").execute()
            for row in (res.data or []):
                out[row["key"]] = row["value"]
    except Exception:
        pass
    # Env fallback
    for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL"):
        if k not in out and os.getenv(k):
            out[k] = os.getenv(k)
    out.setdefault("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
    _CACHED_SECRETS = out
    return out


def _headers() -> Dict[str, str]:
    s = _load_secrets()
    return {
        "APCA-API-KEY-ID": s.get("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": s.get("ALPACA_SECRET_KEY", ""),
        "Content-Type": "application/json",
    }


def _base() -> str:
    return _load_secrets().get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")


def is_market_open() -> bool:
    """Source-of-truth: Alpaca's clock. Handles holidays and half-days."""
    try:
        r = requests.get(f"{_base()}/clock", headers=_headers(), timeout=10)
        if r.ok:
            return bool(r.json().get("is_open", False))
    except Exception:
        pass
    # Conservative fallback: closed if we cannot confirm.
    return False


def get_account() -> Dict:
    r = requests.get(f"{_base()}/account", headers=_headers(), timeout=10)
    return r.json() if r.ok else {"error": r.text}


def get_positions() -> list:
    r = requests.get(f"{_base()}/positions", headers=_headers(), timeout=10)
    return r.json() if r.ok else []


def submit_order(symbol: str, qty: float, side: str,
                 order_type: str = "market", time_in_force: str = "day",
                 limit_price: Optional[float] = None,
                 client_order_id: Optional[str] = None,
                 retries: int = 2) -> Dict:
    """Submit a paper order. Returns Alpaca response or error dict."""
    payload = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side.lower(),
        "type": order_type,
        "time_in_force": time_in_force,
    }
    if limit_price is not None:
        payload["limit_price"] = str(limit_price)
        payload["type"] = "limit"
    if client_order_id:
        payload["client_order_id"] = client_order_id

    last_err: str = ""
    for attempt in range(retries + 1):
        try:
            r = requests.post(f"{_base()}/orders", headers=_headers(),
                              json=payload, timeout=15)
            if r.ok:
                return r.json()
            last_err = f"{r.status_code} {r.text[:300]}"
            # Don't retry on 4xx (bad input, insufficient funds, etc.)
            if 400 <= r.status_code < 500:
                break
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5 * (attempt + 1))
    return {"error": last_err, "id": None}


def execute_validated(trade: Dict) -> Dict:
    """trade: {ticker, side, qty, entry_price, confidence, ...}"""
    if not is_market_open():
        return {**trade, "status": "SKIPPED_MARKET_CLOSED", "broker_order_id": None}
    coid = f"solstice-{int(time.time())}-{trade['ticker']}"
    resp = submit_order(
        symbol=trade["ticker"],
        qty=trade["qty"],
        side=trade["side"],
        order_type="market",
        time_in_force="day",
        client_order_id=coid,
    )
    if resp.get("id") is None:
        return {**trade, "status": "REJECTED_BROKER_ERROR",
                "broker_order_id": None,
                "notes": (resp.get("error") or "")[:300]}
    return {
        **trade,
        "status": "SUBMITTED",
        "broker": "alpaca_paper",
        "broker_order_id": resp.get("id"),
        "filled_avg_price": resp.get("filled_avg_price"),
    }
