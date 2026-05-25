"""
WEBHOOK POSTER — direct push to Lovable ingest endpoint.

Mirrors every cycle's output to:
   POST https://project--49480feb-c516-4d8e-9985-7d344698f026.lovable.app/api/public/gumloop/ingest

Authentication: Bearer token stored in Supabase `secrets` table under key
`GUMLOOP_INGEST_TOKEN`. Falls back to env var of the same name.

Batch schema (per Lovable contract):
    {"batch": [{"kind": <kind>, "data": {...}}, ...]}

Recognized kinds: signal | trade | position | log | simulation |
                  portfolio_metric | strategy_performance | visualization |
                  account_state | heartbeat
"""
from __future__ import annotations
import os
import json
import time
from typing import Any, Dict, List, Optional
import requests


WEBHOOK_URL_DEFAULT = (
    "https://project--49480feb-c516-4d8e-9985-7d344698f026.lovable.app"
    "/api/public/gumloop/ingest"
)

_CACHE: Dict[str, Any] = {"token": None, "url": None}


def _load_config() -> Dict[str, str]:
    """Pull token + URL from Supabase secrets, with env fallback."""
    if _CACHE["token"] is not None:
        return {"token": _CACHE["token"], "url": _CACHE["url"]}

    token: Optional[str] = None
    url: Optional[str] = None
    try:
        from supabase import create_client
        sb_url = os.getenv("SUPABASE_URL")
        sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if sb_url and sb_key:
            client = create_client(sb_url, sb_key)
            res = client.table("secrets").select("key,value").execute()
            for row in (res.data or []):
                if row["key"] == "GUMLOOP_INGEST_TOKEN":
                    token = row["value"]
                if row["key"] == "GUMLOOP_INGEST_URL":
                    url = row["value"]
    except Exception:
        pass

    token = token or os.getenv("GUMLOOP_INGEST_TOKEN")
    url = url or os.getenv("GUMLOOP_INGEST_URL") or WEBHOOK_URL_DEFAULT

    _CACHE["token"] = token
    _CACHE["url"] = url
    return {"token": token, "url": url}


def push_batch(records: List[Dict[str, Any]], max_size: int = 500,
               retries: int = 2) -> Dict[str, Any]:
    """
    Send a batch of records to the Lovable ingest endpoint.
    Chunks at max_size (Lovable contract limit). Retries on 5xx.
    """
    cfg = _load_config()
    if not cfg["token"]:
        return {"ok": False, "error": "no_token", "sent": 0}

    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Content-Type": "application/json",
    }

    sent = 0
    errors: List[str] = []
    for i in range(0, len(records), max_size):
        chunk = records[i : i + max_size]
        body = {"batch": chunk}
        for attempt in range(retries + 1):
            try:
                r = requests.post(cfg["url"], headers=headers,
                                  data=json.dumps(body), timeout=20)
                if r.ok:
                    sent += len(chunk)
                    break
                if 400 <= r.status_code < 500:
                    errors.append(f"{r.status_code}: {r.text[:200]}")
                    break
            except Exception as e:
                errors.append(str(e))
            time.sleep(0.5 * (attempt + 1))
    return {"ok": sent > 0, "sent": sent, "errors": errors[:3]}


def heartbeat(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Single heartbeat ping. Frontend uses this to flip the engine-alive dot."""
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **(extra or {}),
    }
    return push_batch([{"kind": "heartbeat", "data": payload}])


def push_cycle(*, account_state: Dict | None = None,
               signals: List[Dict] | None = None,
               trades: List[Dict] | None = None,
               positions: List[Dict] | None = None,
               simulations: List[Dict] | None = None,
               portfolio_metrics: List[Dict] | None = None,
               strategy_performance: List[Dict] | None = None,
               visualizations: List[Dict] | None = None,
               logs: List[Dict] | None = None,
               regime: str | None = None) -> Dict[str, Any]:
    """
    Convenience: pack everything from one engine cycle into a single batch.
    """
    records: List[Dict[str, Any]] = []
    records.append({"kind": "heartbeat",
                    "data": {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "regime": regime}})
    if account_state:
        records.append({"kind": "account_state", "data": account_state})
    for s in (signals or []):
        records.append({"kind": "signal", "data": s})
    for t in (trades or []):
        records.append({"kind": "trade", "data": t})
    for p in (positions or []):
        records.append({"kind": "position", "data": p})
    for sim_row in (simulations or []):
        records.append({"kind": "simulation", "data": sim_row})
    for pm in (portfolio_metrics or []):
        records.append({"kind": "portfolio_metric", "data": pm})
    for sp in (strategy_performance or []):
        records.append({"kind": "strategy_performance", "data": sp})
    for v in (visualizations or []):
        records.append({"kind": "visualization", "data": v})
    for log_row in (logs or []):
        records.append({"kind": "log", "data": log_row})
    return push_batch(records)
