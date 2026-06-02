"""
SOLSTICE v4 · STRATEGY LIBRARY
Each strategy returns dict[ticker] -> alpha score in [-1, +1].
Backtest is callable for each strategy → returns rolling Sharpe.
"""
from __future__ import annotations
import numpy as np
import math
from itertools import combinations


# ─── 1. CROSS-SECTIONAL MOMENTUM (Jegadeesh-Titman 12-1) ───
def momentum_12_1(data):
    """Past 12-month return minus most recent month. Standardized across universe."""
    scores = {}
    for t, d in data.items():
        c = d['close']
        if len(c) < 252: continue
        ret_12m = c[-21] / c[-252] - 1.0          # 12-month return, lag 1 month
        ret_1m  = c[-1]  / c[-21]  - 1.0          # most-recent month
        scores[t] = ret_12m - ret_1m              # JT factor
    if not scores: return {}
    vals = np.array(list(scores.values()))
    mean, std = vals.mean(), vals.std() + 1e-9
    return {t: float(np.clip((v - mean) / std / 2, -1, 1)) for t, v in scores.items()}


# ─── 2. LOW-VOLATILITY ANOMALY (Frazzini-Pedersen "betting against beta") ───
def low_volatility(data):
    """Inverse of trailing realized volatility, normalized."""
    scores = {}
    for t, d in data.items():
        r = d['returns']
        if len(r) < 60: continue
        vol = np.std(r[-60:]) * np.sqrt(252)
        scores[t] = -vol     # negative because we want LOW vol = HIGH score after normalization
    if not scores: return {}
    vals = np.array(list(scores.values()))
    mean, std = vals.mean(), vals.std() + 1e-9
    return {t: float(np.clip((v - mean) / std / 2, -1, 1)) for t, v in scores.items()}


# ─── 3. SHORT-TERM MEAN REVERSION ───
def mean_reversion(data):
    """Negative z-score of recent return → buy oversold, sell overbought."""
    scores = {}
    for t, d in data.items():
        r = d['returns']
        if len(r) < 21: continue
        z = (r[-1] - np.mean(r[-21:])) / (np.std(r[-21:]) + 1e-9)
        scores[t] = float(np.clip(-z / 2, -1, 1))
    return scores


# ─── 4. TREND FOLLOWING (SMA crossover normalized) ───
def trend_following(data):
    scores = {}
    for t, d in data.items():
        c = d['close']
        if len(c) < 50: continue
        sma20, sma50 = np.mean(c[-20:]), np.mean(c[-50:])
        rel = (sma20 - sma50) / sma50
        scores[t] = float(np.clip(np.tanh(rel * 20), -1, 1))
    return scores


# ─── 5. SECTOR MOMENTUM (rotates into top-performing sector) ───
SECTOR_ETFS = ['XLK','XLF','XLE','XLV','XLY','XLP','XLI','XLU','XLB','XLRE','XLC']
SECTOR_MAP = {
    'XLK': ['AAPL','MSFT','NVDA','AVGO','ORCL','CSCO','ADBE','CRM','AMD','TXN','QCOM','INTU','PANW','LRCX','KLAC','ANET','INTC','ACN','MU','NOW'],
    'XLF': ['JPM','BAC','WFC','GS','MS','BLK','SPGI','SCHW','C','AXP','PGR','CB','MMC','ICE','AON','ADP'],
    'XLE': ['XOM','CVX','COP','EOG','SLB','PSX','MPC','OXY','HES'],
    'XLV': ['LLY','JNJ','UNH','ABBV','MRK','TMO','PFE','ABT','AMGN','DHR','BMY','GILD','ISRG','VRTX','SYK','BSX','MDT','BIIB','HCA','REGN','ELV','CI'],
    'XLY': ['AMZN','TSLA','HD','MCD','NKE','LOW','SBUX','TJX','BKNG','MAR','CMG','ABNB','DPZ','DECK'],
    'XLP': ['WMT','PG','COST','KO','PEP','PM','MO','MDLZ','CL','TGT','KMB','MNST','HSY','STZ'],
    'XLI': ['CAT','UNP','GE','HON','BA','RTX','LMT','UPS','DE','MMM','EMR','ETN','CSX','NSC','PCAR','FDX','WM','ITW','PH'],
    'XLU': ['NEE','SO','DUK','AEP','EXC','SRE','XEL','PEG','ED','D'],
    'XLB': ['LIN','APD','SHW','ECL','FCX','NUE','DOW','DD','VMC','MLM'],
    'XLRE':['PLD','AMT','EQIX','CCI','WELL','PSA','O','SPG','VICI','CBRE','EXR','AVB','DLR'],
    'XLC': ['META','GOOGL','GOOG','DIS','NFLX','TMUS','VZ','T','EA','TTWO','CMCSA','WBD','CHTR'],
}

def sector_momentum(data):
    """Score = sector ETF's 3-month momentum, applied to each member ticker."""
    sector_score = {}
    for etf in SECTOR_ETFS:
        d = data.get(etf)
        if d is None or len(d['close']) < 63: continue
        c = d['close']
        sector_score[etf] = c[-1] / c[-63] - 1.0   # 3-month return

    if not sector_score: return {}
    # Normalize sector scores
    vals = np.array(list(sector_score.values()))
    mean, std = vals.mean(), vals.std() + 1e-9
    norm = {etf: float(np.clip((v - mean) / std / 2, -1, 1)) for etf, v in sector_score.items()}

    out = {}
    for etf, score in norm.items():
        for ticker in SECTOR_MAP.get(etf, []):
            out[ticker] = score
    return out


# ─── 6. PAIRS TRADING (cointegrated spread z-score) ───
KNOWN_PAIRS = [
    ('KO', 'PEP'),    ('XOM','CVX'),  ('JPM','BAC'),   ('GOOG','META'),
    ('MSFT','GOOGL'), ('NVDA','AMD'), ('V','MA'),      ('HD','LOW'),
    ('UNH','CI'),     ('LMT','RTX'), ('CAT','DE'),     ('AVGO','QCOM'),
    ('MCD','SBUX'),   ('CRM','ORCL'), ('AAPL','MSFT'),
]

def pairs_trading(data, lookback=120):
    """
    For each known pair, compute spread z-score.
    If spread > +2σ → short A buy B (negative alpha for A, positive for B)
    If spread < -2σ → buy A short B (positive alpha for A, negative for B)
    Returns dict[ticker] -> aggregated alpha across pairs containing it.
    """
    scores = {}
    counts = {}
    for a, b in KNOWN_PAIRS:
        da, db = data.get(a), data.get(b)
        if da is None or db is None: continue
        if min(len(da['close']), len(db['close'])) < lookback + 1: continue
        ca = da['close'][-lookback:]
        cb = db['close'][-lookback:]
        # log spread
        log_a, log_b = np.log(ca), np.log(cb)
        # hedge ratio via simple regression
        beta = float(np.cov(log_a, log_b, bias=True)[0,1] / (np.var(log_b) + 1e-9))
        spread = log_a - beta * log_b
        mu, sd = float(np.mean(spread)), float(np.std(spread) + 1e-9)
        z = (spread[-1] - mu) / sd
        # convert to bounded alpha
        # spread high → A overvalued vs B → short A, long B
        scores[a] = scores.get(a, 0) + float(np.clip(-z / 3, -1, 1))
        scores[b] = scores.get(b, 0) + float(np.clip(+z / 3, -1, 1))
        counts[a] = counts.get(a, 0) + 1
        counts[b] = counts.get(b, 0) + 1
    return {t: scores[t] / counts[t] for t in scores}


# ─── REGISTRY ───
STRATEGIES = {
    'momentum_12_1':   momentum_12_1,
    'low_volatility':  low_volatility,
    'mean_reversion':  mean_reversion,
    'trend_following': trend_following,
    'sector_momentum': sector_momentum,
    'pairs_trading':   pairs_trading,
}


# ─── BACKTEST (walk-forward Sharpe per strategy) ───
def backtest_strategy_sharpe(strategy_fn, data, lookback_days=120, hold_days=5):
    """
    Compute rolling out-of-sample Sharpe for a strategy.
    At each step:
      - Run strategy on data UP TO that point
      - Take top 5 alpha tickers, equal-weighted
      - Forward 5-day return = strategy realized return
    Returns annualized Sharpe over the test window.
    """
    universe = list(data.keys())
    # Snapshots — use last lookback_days as test window
    rets = []
    end = min(d['n'] for d in data.values())
    for i in range(end - lookback_days, end - hold_days, hold_days):
        snap = {t: {'close': d['close'][:i], 'high': d['high'][:i], 'low': d['low'][:i],
                    'volume': d['volume'][:i], 'returns': d['returns'][:i-1], 'n': i}
                for t, d in data.items() if d['n'] >= i}
        scores = strategy_fn(snap)
        if not scores: continue
        # Pick top 5 by score
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        # 5-day forward return for each, equal weighted
        period_ret = 0.0; valid = 0
        for t, s in top:
            d = data.get(t)
            if d is None or i + hold_days >= d['n']: continue
            r = d['close'][i + hold_days] / d['close'][i] - 1.0
            period_ret += r; valid += 1
        if valid > 0:
            rets.append(period_ret / valid)
    if not rets: return 0.0
    rets = np.array(rets)
    # Annualize (252 / hold_days periods per year)
    periods_per_year = 252 / hold_days
    mu = rets.mean() * periods_per_year
    sd = rets.std() * np.sqrt(periods_per_year) + 1e-9
    return float(mu / sd)
