"""
SOLSTICE · PROFIT-TAKING ENGINE
Active profit realization layered on top of trailing stops.

Philosophy: "sell into strength, let a runner ride."
  - Scale OUT a fraction at profit milestones (locks real cash)
  - TIGHTEN the trailing stop as gains grow (protects the rest)
  - Keep a core runner so we still capture big trends

Tiers (by unrealized gain %):
   >= 20%  -> take 40% off the table, trail remaining at 5%
   >= 10%  -> take 25% off, trail at 6%
   >=  5%  -> hold, trail at 7%
   <   5%  -> hold, trail at 8%
"""
from __future__ import annotations
import time, json
import requests

PROFIT_TIERS = [
    # (min_gain, scale_out_fraction, trail_percent)
    (0.20, 0.40, 5.0),
    (0.10, 0.25, 6.0),
    (0.05, 0.00, 7.0),
    (0.00, 0.00, 8.0),
]


def tier_for(gain_pct):
    for min_gain, scale, trail in PROFIT_TIERS:
        if gain_pct >= min_gain:
            return scale, trail
    return 0.0, 8.0


def manage_profits(alpaca_base, headers, dry_run=False):
    """
    For every open position:
      - determine profit tier
      - queue a partial scale-out sell if the tier calls for it
      - (re)place a trailing stop at the tier's trail %
    Returns a list of actions taken.
    """
    def alp(method, path, body=None):
        fn = requests.get if method=='GET' else requests.post if method=='POST' else requests.delete
        kw = {'headers': headers, 'timeout': 12}
        if body: kw['data'] = json.dumps(body)
        r = fn(f'{alpaca_base}{path}', **kw)
        try: return r.json() if r.text else {}
        except: return {'raw': r.text}

    positions = alp('GET', '/positions')
    if not isinstance(positions, list):
        return []

    # cancel existing sell orders so we can re-place cleanly
    oo = alp('GET', '/orders?status=open&limit=200')
    if isinstance(oo, list):
        for o in oo:
            if o.get('side') == 'sell':
                alp('DELETE', f"/orders/{o['id']}")
    time.sleep(1.0)

    actions = []
    for p in positions:
        sym = p['symbol']
        qty = int(float(p['qty']))
        if qty < 1: continue
        gain = float(p['unrealized_plpc'])
        scale, trail = tier_for(gain)

        scale_qty = int(qty * scale)
        remaining = qty - scale_qty

        if scale_qty >= 1 and not dry_run:
            # scale-out: market sell a fraction (locks profit)
            alp('POST', '/orders', {'symbol': sym, 'qty': str(scale_qty), 'side': 'sell',
                                     'type': 'market', 'time_in_force': 'day'})
            actions.append({'symbol': sym, 'action': 'scale_out', 'qty': scale_qty,
                            'gain_pct': round(gain*100, 1)})
            time.sleep(0.3)

        if remaining >= 1 and not dry_run:
            # trailing stop on the runner at tier trail %
            alp('POST', '/orders', {'symbol': sym, 'qty': str(remaining), 'side': 'sell',
                                     'type': 'trailing_stop', 'trail_percent': str(trail),
                                     'time_in_force': 'gtc'})
            actions.append({'symbol': sym, 'action': 'trail', 'qty': remaining,
                            'trail_pct': trail, 'gain_pct': round(gain*100, 1)})
            time.sleep(0.2)
    return actions
