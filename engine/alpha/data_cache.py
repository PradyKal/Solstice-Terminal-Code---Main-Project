"""
SOLSTICE v4 · DATA CACHE
Single yfinance pull per day, cached to disk in /home/user/.workspace/solstice/v4/cache/.
Intraday cycles read from cache instead of re-downloading.
"""
from __future__ import annotations
import os, json, time, pickle, datetime
import numpy as np
import yfinance as yf

CACHE_DIR = '/home/user/.workspace/solstice/v4/cache'
os.makedirs(CACHE_DIR, exist_ok=True)


def _today_key():
    return datetime.datetime.now().strftime('%Y-%m-%d')


def get_universe_data(universe, period='2y', force_refresh=False):
    """
    Returns dict[ticker] -> {close, high, low, volume, returns, n} numpy arrays.
    Caches on disk. Refreshes once per calendar day.
    """
    key = _today_key()
    path = f'{CACHE_DIR}/universe_{key}.pkl'
    if not force_refresh and os.path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f), True   # cache hit

    import warnings; warnings.filterwarnings('ignore')
    data = yf.download(universe, period=period, interval='1d', group_by='ticker',
                       progress=False, threads=True, auto_adjust=True)
    out = {}
    for t in universe:
        try:
            df = data[t].dropna()
            if len(df) < 60: continue
            close = df['Close'].values.astype(float)
            out[t] = {
                'close': close,
                'high':  df['High'].values.astype(float),
                'low':   df['Low'].values.astype(float),
                'volume':df['Volume'].values.astype(float),
                'returns': np.diff(close) / close[:-1],
                'n': len(close),
            }
        except Exception:
            continue
    with open(path, 'wb') as f:
        pickle.dump(out, f, protocol=pickle.HIGHEST_PROTOCOL)
    # Cleanup old caches
    for fn in os.listdir(CACHE_DIR):
        if fn.startswith('universe_') and fn != f'universe_{key}.pkl':
            try: os.remove(f'{CACHE_DIR}/{fn}')
            except: pass
    return out, False   # cache miss


def get_spy_returns(data):
    return data.get('SPY', {}).get('returns')
