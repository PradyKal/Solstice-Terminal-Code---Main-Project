"""
SLACK REPORTER
Sends institutional-style cycle summary to Slack via gumcp_client.
"""
from __future__ import annotations
import os
import json
from typing import Dict, List


def format_digest(cycle: Dict) -> str:
    lines = []
    lines.append(f"*Solstice Cycle Report — {cycle.get('timestamp_et', '')}*")
    lines.append(f"Regime: `{cycle.get('regime', '?')}`  |  "
                 f"VIX state: `{cycle.get('vix_state', '?')}`  |  "
                 f"Scanned: {cycle.get('scanned', 0)} / Top-N: {cycle.get('topn', 0)}")
    lines.append("")
    lines.append("*Top Opportunities*")
    for s in cycle.get("top_signals", [])[:10]:
        lines.append(f"  {s['ticker']:<8}  alpha={s['alpha']:+.3f}  "
                     f"conf={s['confidence']:.2f}  ER={s['expected_return']:+.3f}  "
                     f"risk={s['risk_score']:.3f}")
    rej = cycle.get("rejected", [])
    if rej:
        lines.append("")
        lines.append("*Risk Rejections*")
        for r in rej[:6]:
            lines.append(f"  {r['ticker']:<8}  reason=`{r['reason']}`")
    ex = cycle.get("executed", [])
    if ex:
        lines.append("")
        lines.append("*Executed Trades*")
        for t in ex:
            lines.append(f"  {t['side']:>4} {t['ticker']:<6}  "
                         f"qty={t['qty']:.2f}  @ ${t['entry_price']:.2f}  "
                         f"status={t['status']}")
    port = cycle.get("portfolio", {})
    if port:
        lines.append("")
        lines.append("*Portfolio*")
        lines.append(f"  Gross ${port.get('gross_exposure',0):,.0f}  "
                     f"Net ${port.get('net_exposure',0):,.0f}  "
                     f"Sharpe60d={port.get('rolling_sharpe','-')}  "
                     f"MaxDD={port.get('max_drawdown','-')}")
    attr = cycle.get("strategy_attribution", {})
    if attr:
        lines.append("")
        lines.append("*Strategy Attribution*")
        for k, v in attr.items():
            lines.append(f"  {k:<22} w={v.get('weight',0):.2f}  contrib={v.get('contribution',0):+.4f}")
    return "\n".join(lines)


def send_to_slack(channel: str, text: str) -> Dict:
    try:
        from gumcp_client import Client
        client = Client(
            user_id=os.getenv("GUMCP_USER_ID"),
            gumcp_api_key=os.getenv("GUMCP_ACCESS_TOKEN") or os.getenv("GUMCP_API_KEY"),
            base_url=os.getenv("GUMCP_BASE_URL"),
        )
        raw = client.call_tool("slack__send_message", {"channel_id": channel, "text": text})
        return json.loads(raw[0]) if raw else {"ok": True}
    except Exception as e:
        return {"error": str(e)}
