"""
SOLSTICE v4 · UNIFIED RUNNER
Single entry point that dispatches based on time of day.
"""
from __future__ import annotations
import os, sys, json, time, datetime, pytz
import numpy as np
import requests

sys.path.insert(0, '/home/user/.workspace/solstice/v4')
from alpha import data_cache
from alpha.strategies_v2 import STRATEGIES, backtest_with_costs
from alpha.ensemble import sharpe_weighted_ensemble, estimate_position_params, kelly_position_size
from alpha import news_sentiment as news
from alpha.risk_manager import RiskManager, PortfolioManager, SECTOR_OF

# ─── CONFIG ─────
SUPABASE_URL  = os.environ.get('SUPABASE_URL',  'https://roogtwurdmsdapgvaspk.supabase.co')
SUPABASE_ANON = os.environ.get('SUPABASE_ANON', 'sb_publishable_H2NwQKatFKUfH02dmCP32A_XuXpXykZ')
ALPACA_KEY    = os.environ.get('ALPACA_API_KEY')
ALPACA_SECRET = os.environ.get('ALPACA_SECRET_KEY')
ALPACA_BASE   = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets/v2')
SLACK_CHANNEL = os.environ.get('SOLSTICE_SLACK_CHANNEL', 'C0AV6R5MEKZ')
H_SB = {'apikey': SUPABASE_ANON, 'Authorization': f'Bearer {SUPABASE_ANON}', 'Content-Type':'application/json'}
H_AL = {'APCA-API-KEY-ID': ALPACA_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET, 'Content-Type':'application/json'}

UNIVERSE = (
  "AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO LLY JPM V WMT XOM MA UNH ORCL HD PG "
  "JNJ COST ABBV BAC NFLX KO CRM MRK CVX TMUS AMD PEP ADBE LIN MCD CSCO ACN ABT WFC TMO "
  "PM IBM DHR GE TXN INTU CAT AXP VZ ISRG NOW MS DIS NEE QCOM AMGN GS PFE T BLK SPGI "
  "BKNG NKE RTX UBER UNP LOW SYK HON AMAT BSX PGR ETN LMT C ELV BX VRTX PLD TJX SCHW DE "
  "BA REGN SBUX ADP CB MDLZ MDT MU GILD ANET KKR ADI PANW LRCX KLAC INTC ICE CMG TT WM "
  "SPY QQQ IWM XLK XLF XLE XLV XLY XLP XLI XLU XLB XLRE XLC SMH SOXX"
).split()

TARGET_FILE = '/home/user/.workspace/solstice/v4/cache/target_portfolio.json'

# ─── ALPACA HELPERS ──
def alpaca(method, path, body=None):
    fn = requests.get if method=='GET' else requests.post if method=='POST' else requests.delete
    kw = {'headers': H_AL, 'timeout': 12}
    if body: kw['data'] = json.dumps(body)
    r = fn(f'{ALPACA_BASE}{path}', **kw)
    try: return r.json() if r.text else {}
    except: return {'raw': r.text}

def clock():        return alpaca('GET','/clock')
def account():      return alpaca('GET','/account')
def positions():    r = alpaca('GET','/positions');   return r if isinstance(r,list) else []
def open_orders():  r = alpaca('GET','/orders?status=open&limit=200'); return r if isinstance(r,list) else []
def close_pos(s):   return alpaca('DELETE', f'/positions/{s}')

def submit_bracket(symbol, qty, limit_p, stop_p, profit_p):
    body = {'symbol':symbol,'qty':str(int(qty)),'side':'buy','type':'limit',
            'limit_price':f'{limit_p:.2f}','time_in_force':'day','order_class':'bracket',
            'take_profit':{'limit_price': f'{profit_p:.2f}'},
            'stop_loss':{'stop_price': f'{stop_p:.2f}','limit_price': f'{stop_p*0.997:.2f}'},
            'client_order_id': f'v4-{int(time.time())}-{symbol}'}
    return alpaca('POST', '/orders', body)

# ─── SUPABASE / SLACK ──
def sb_insert(table, rows):
    if not rows: return 0
    r = requests.post(f'{SUPABASE_URL}/rest/v1/{table}',
                      headers={**H_SB,'Prefer':'return=minimal'},
                      data=json.dumps(rows), timeout=20)
    return len(rows) if r.ok else f'FAIL {r.status_code}'

def slack(text):
    if not SLACK_CHANNEL: return
    try:
        from gumcp_client import Client
        c = Client(user_id=os.environ.get('GUMCP_USER_ID'),
                   gumcp_api_key=os.environ.get('GUMCP_ACCESS_TOKEN') or os.environ.get('GUMCP_API_KEY'),
                   base_url=os.environ.get('GUMCP_BASE_URL'))
        c.call_tool('slack__send_message', {'channel': SLACK_CHANNEL, 'text': text})
    except Exception as e: print(f'slack: {e}')

# ─── JOB 1: EOD PREP — generate target portfolio for the day ──
def job_prep():
    print('[PREP] downloading universe (force refresh)')
    data, cached = data_cache.get_universe_data(UNIVERSE, period='2y', force_refresh=True)
    print(f'  data: {len(data)} tickers · cache_hit={cached}')

    # Backtest each strategy (realistic walk-forward with costs + IC)
    sharpes = {}
    ics = {}
    print('[PREP] backtesting strategies (cost-adjusted walk-forward)...')
    for name, fn in STRATEGIES.items():
        bt = backtest_with_costs(fn, data, lookback_days=180, hold_days=5, n_long=5, cost_bps=5)
        sharpes[name] = bt['sharpe']
        ics[name] = bt['ic']
        print(f'  {name:22s} Sharpe {bt["sharpe"]:+.2f}  IC {bt["ic"]:+.3f}  win {bt["win_rate"]*100:.0f}%')

    # Run all strategies on current data
    scores = {name: fn(data) for name, fn in STRATEGIES.items()}

    # STRONG filter: only deploy strategies with Sharpe >= 0.5 AND positive IC
    # (negative-IC strategies like BAB in a momentum regime get zeroed out)
    deployable = {n: s for n, s in scores.items()
                  if sharpes.get(n, 0) >= 0.5 and ics.get(n, 0) > 0}
    if not deployable:
        deployable = scores   # safety fallback
    # Weight by Sharpe × IC (reward both risk-adjusted return and predictive power)
    blend_weights = {n: max(0.01, sharpes[n]) * max(0.01, ics.get(n, 0.01))
                     for n in deployable}
    combined, weights = sharpe_weighted_ensemble(deployable, blend_weights, min_sharpe=0.0)

    # ═══ FULL QUANT DESK PORTFOLIO CONSTRUCTION ═══
    acct = account()
    equity = float(acct.get('equity', 100000))
    peak = float(acct.get('equity', 100000))  # could track high-water externally

    # Top candidates by combined alpha
    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    candidates = [t for t, a in ranked[:20] if a > 0.10]

    # ── NEWS ANALYST: sentiment screen + veto on bad news ──
    print('[PREP] news/sentiment screen...')
    sent_map, vetoed = news.screen_universe(candidates, neg_threshold=-0.15)
    if vetoed:
        print(f'  vetoed (negative news): {sorted(vetoed)}')

    # ── RISK MANAGER: drawdown circuit breaker + vol targeting ──
    rm = RiskManager(equity, peak_equity=peak)
    exp_mult = rm.exposure_multiplier()       # cuts exposure in drawdown
    # portfolio daily vol estimate from candidates' avg vol
    cand_vols = [np.std(data[t]['returns'][-60:]) for t in candidates if t in data]
    port_vol = float(np.mean(cand_vols)) if cand_vols else 0.012
    vol_scalar = rm.vol_target_scalar(port_vol, target_annual_vol=0.15)
    risk_scalar = exp_mult * vol_scalar
    print(f'  risk: dd={rm.drawdown()*100:.1f}% exp_mult={exp_mult:.2f} vol_scalar={vol_scalar:.2f} → {risk_scalar:.2f}')

    # ── PORTFOLIO MANAGER: build strategy SLEEVES ──
    # Each strategy nominates its top names; PM allocates capital across sleeves
    sleeve_picks = {}
    for strat_name, w in weights.items():
        strat_scores = scores.get(strat_name, {})
        top_strat = sorted(strat_scores.items(), key=lambda x: x[1], reverse=True)[:8]
        picks = []
        for ticker, sc in top_strat:
            if sc <= 0.10 or ticker in vetoed: continue
            d = data.get(ticker)
            if d is None: continue
            daily_vol = np.std(d['returns'][-60:])
            er, var = estimate_position_params(sc, daily_vol)
            kf = kelly_position_size(er, var, max_fraction=0.05)
            if kf <= 0.005: continue
            picks.append({'ticker': ticker, 'alpha': sc, 'price': float(d['close'][-1]),
                          'atr': float(np.mean(d['high'][-14:] - d['low'][-14:])),
                          'kelly_frac': kf})
        if picks:
            sleeve_picks[strat_name] = picks

    pm = PortfolioManager(equity * risk_scalar, weights)
    raw_targets = pm.divide(sleeve_picks)

    # ── apply sentiment multiplier to sizing ──
    for t in raw_targets:
        t['dollars'] *= news.sentiment_multiplier(sent_map.get(t['ticker'], 0.0))

    # ── RISK MANAGER: sector exposure caps ──
    capped = rm.apply_sector_caps(raw_targets)

    # ── finalize targets with shares + bracket levels ──
    target = []
    for t in capped:
        if t['dollars'] < 1000: continue
        shares = int(t['dollars'] / t['price'])
        if shares < 1: continue
        # single-name cap
        if shares * t['price'] > equity * rm.max_name_pct:
            shares = int(equity * rm.max_name_pct / t['price'])
        if shares < 1: continue
        atr = t['atr']
        target.append({
            'ticker': t['ticker'], 'shares': shares, 'price': t['price'],
            'alpha': t['alpha'], 'fraction': (shares*t['price'])/equity, 'atr14': atr,
            'sector': SECTOR_OF.get(t['ticker'], 'OTHER'),
            'sentiment': round(sent_map.get(t['ticker'], 0.0), 3),
            'stop': t['price'] - 1.5*atr,        # initial stop
            'profit': t['price'] + 2.5*atr,      # take profit
            'trail_mult': 2.0,                   # trailing stop ATR multiple (for risk-check job)
        })
    target.sort(key=lambda x: x['fraction'], reverse=True)

    # Save target portfolio
    payload = {
        'date': datetime.datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d'),
        'sharpes': sharpes, 'weights': weights,
        'target': target, 'risk_scalar': risk_scalar,
        'drawdown': rm.drawdown(), 'vetoed': sorted(vetoed),
    }
    with open(TARGET_FILE, 'w') as f:
        json.dump(payload, f, default=str, indent=2)

    # Slack EOD report
    msg = [f'📊 *SOLSTICE v5 · EOD PREP · {payload["date"]}*', '']
    msg.append('*Strategy validation (cost-adjusted walk-forward):*')
    for n, s in sorted(sharpes.items(), key=lambda x: -x[1]):
        deployed = n in weights
        flag = '✓' if deployed else '✗'
        msg.append(f'  {flag} {n:22s} Sharpe {s:+.2f} · IC {ics.get(n,0):+.3f}'
                   + (f' · w {weights.get(n,0)*100:.0f}%' if deployed else ' · DROPPED'))
    msg.append('')
    msg.append(f'*Risk desk:* drawdown {rm.drawdown()*100:+.1f}% · exposure ×{risk_scalar:.2f}'
               + (f' · vetoed {", ".join(sorted(vetoed))}' if vetoed else ''))
    msg.append(f'*Target portfolio ({len(target)} positions · sleeves · sector-capped · news-screened):*')
    for t in target[:12]:
        msg.append(f"  ▶ {t['ticker']:6s} ×{t['shares']:>4d}sh @ ${t['price']:.2f}  "
                   f"{t['sector']:6s} α={t['alpha']:+.2f} news={t['sentiment']:+.2f} k={t['fraction']*100:.1f}%")
    slack('\n'.join(msg))
    sb_insert('logs', [{'level':'INFO','component':'PrepV5',
                        'message': f'EOD prep · {len(target)} targets · '
                                   f'deployed {len(weights)} strategies'}])
    return {'ok': True, 'targets': len(target), 'sharpes': sharpes, 'ics': ics}


# ─── JOB 2: REBALANCE TOWARD TARGET ──
def job_rebalance():
    if not clock().get('is_open'):
        slack('⏸ rebalance skipped · market closed')
        return {'skipped': True}
    if not os.path.exists(TARGET_FILE):
        slack('⚠ rebalance skipped · no target portfolio (run prep first)')
        return {'no_target': True}
    with open(TARGET_FILE) as f:
        payload = json.load(f)
    target = payload['target']
    target_symbols = {t['ticker'] for t in target}
    current = positions()
    current_symbols = {p['symbol'] for p in current}

    # Close positions NOT in target
    to_close = current_symbols - target_symbols
    closed = []
    for s in list(to_close)[:5]:   # max 5 closes per cycle to avoid mayhem
        r = close_pos(s)
        if isinstance(r, dict) and r.get('symbol'):
            closed.append(s)

    # Open positions IN target but not held
    to_open = [t for t in target if t['ticker'] not in current_symbols][:3]   # max 3 new per cycle
    opened = []
    for t in to_open:
        r = submit_bracket(t['ticker'], t['shares'],
                           t['price'] * 0.999,   # limit at -0.1%
                           t['stop'], t['profit'])
        if isinstance(r, dict) and r.get('id'):
            opened.append({**t, 'order_id': r['id']})

    msg = [f'🔄 *SOLSTICE v4 · REBALANCE*  ({datetime.datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M")} ET)']
    if closed: msg.append(f'*Closed:* {", ".join(closed)}')
    if opened:
        msg.append(f'*Opened (bracket orders):*')
        for o in opened:
            msg.append(f"  ▶ {o['ticker']} ×{o['shares']}sh entry ${o['price']*0.999:.2f} "
                       f"stop ${o['stop']:.2f} target ${o['profit']:.2f}")
    if not closed and not opened:
        msg.append('(aligned · no changes)')
    slack('\n'.join(msg))
    sb_insert('logs', [{'level':'INFO','component':'RebalanceV4',
                        'message': f'rebalance closed={len(closed)} opened={len(opened)}'}])
    return {'closed': closed, 'opened': len(opened)}


# ─── JOB 3: RISK CHECK (EOD) ──
def job_risk_check():
    """Verify every position has both a stop and a take-profit. Report EOD P&L."""
    pos = positions()
    orders = open_orders()
    by_sym = {}
    for o in orders:
        if o.get('side') != 'sell': continue
        sym = o.get('symbol'); typ = o.get('type')
        by_sym.setdefault(sym, set()).add(typ)
    unprotected = []
    for p in pos:
        legs = by_sym.get(p['symbol'], set())
        if 'stop' not in legs or 'limit' not in legs:
            unprotected.append(p['symbol'])

    acct = account()
    daily_change = float(acct.get('equity',0)) - float(acct.get('last_equity',0))
    msg = ['🛡 *SOLSTICE v4 · RISK CHECK (EOD)*',
           f'Equity ${float(acct.get("equity",0)):,.2f} · Daily P&L ${daily_change:+,.2f}',
           f'Positions {len(pos)} · open orders {len(orders)}']
    if unprotected:
        msg.append(f'⚠ *Unprotected positions:* {", ".join(unprotected)}')
    else:
        msg.append('✓ all positions have stop + take-profit')
    slack('\n'.join(msg))
    return {'unprotected': unprotected, 'daily_pnl': daily_change}


def convert_stops_to_trailing(trail_percent=8.0):
    """
    Ensure every open position has a broker-side TRAILING stop (auto-ratchets
    up daily as price rises → locks profit with ZERO agent runs Tue-Fri).
    Cancels fixed stops/take-profits and replaces with GTC trailing stops.
    """
    pos = positions()
    oo = open_orders()
    # cancel existing sell-side protective orders
    for o in oo:
        if o.get('side') == 'sell' and o.get('type') in ('stop','limit','stop_limit'):
            alpaca('DELETE', f"/orders/{o['id']}")
    time.sleep(1)
    placed = []
    for p in pos:
        qty = int(float(p['qty']))
        if qty <= 0: continue
        body = {'symbol': p['symbol'], 'qty': str(qty), 'side': 'sell',
                'type': 'trailing_stop', 'trail_percent': str(trail_percent),
                'time_in_force': 'gtc',
                'client_order_id': f"trail-{int(time.time())}-{p['symbol']}"}
        r = alpaca('POST', '/orders', body)
        if isinstance(r, dict) and r.get('id'):
            placed.append(p['symbol'])
        time.sleep(0.15)
    return placed


def job_weekly():
    """
    ONE-SHOT WEEKLY: prep + rebalance + trailing-stop protection in a single run.
    Trailing stops then manage risk autonomously Tue-Fri (broker-side, 0 tokens).
    """
    prep = job_prep()
    time.sleep(1)
    rebal = job_rebalance()
    time.sleep(2)   # let new entries fill
    trails = convert_stops_to_trailing(trail_percent=8.0)
    slack(f"🛡 Trailing stops active on {len(trails)} positions (8% trail · auto-ratchets daily)")
    return {'prep': prep, 'rebalance': rebal, 'trailing_stops': len(trails)}


def dispatch():
    """Run job based on current ET time."""
    et = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(et)
    if now.weekday() >= 5: return {'skipped': 'weekend'}
    mins = now.hour * 60 + now.minute
    print(f'[v4 dispatch] now ET = {now.strftime("%H:%M")} ({mins}min)')
    # 08:45 = 525 — prep
    if 510 <= mins <= 540:  return job_prep()
    # 10:00 = 600 — rebalance
    if 590 <= mins <= 620:  return job_rebalance()
    # 12:00 = 720 — rebalance
    if 710 <= mins <= 740:  return job_rebalance()
    # 14:30 = 870 — rebalance
    if 860 <= mins <= 890:  return job_rebalance()
    # 15:45 = 945 — risk check
    if 935 <= mins <= 960:  return job_risk_check()
    return {'skipped': f'no job at {now.strftime("%H:%M")}'}


if __name__ == '__main__':
    print(json.dumps(dispatch(), default=str, indent=2))
