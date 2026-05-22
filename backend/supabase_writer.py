"""
SUPABASE WRITER
Centralized batch insert helpers for: signals, trades, positions, logs,
simulations, portfolio_metrics, strategy_performance, visualization_data.
All inserts are parameterized server-side via supabase-py.
"""
from __future__ import annotations
import os
import json
from typing import List, Dict, Optional

try:
    from supabase import create_client, Client
    _has_supabase = True
except ImportError:
    _has_supabase = False


def _client() -> Optional["Client"]:
    if not _has_supabase:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def _insert(table: str, rows: List[Dict]) -> Dict:
    if not rows:
        return {"inserted": 0, "table": table}
    c = _client()
    if c is None:
        # Fallback: write to disk for the Gumloop runner to flush via MCP later
        with open(f"/tmp/solstice_{table}_buffer.jsonl", "a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return {"buffered": len(rows), "table": table}
    res = c.table(table).insert(rows).execute()
    return {"inserted": len(rows), "table": table, "raw": getattr(res, "data", None)}


def write_signals(rows):              return _insert("signals", rows)
def write_trades(rows):               return _insert("trades", rows)
def write_positions(rows):            return _insert("positions", rows)
def write_logs(rows):                 return _insert("logs", rows)
def write_simulations(rows):          return _insert("simulations", rows)
def write_portfolio_metrics(rows):    return _insert("portfolio_metrics", rows)
def write_strategy_performance(rows): return _insert("strategy_performance", rows)
def write_visualization(rows):        return _insert("visualization_data", rows)
