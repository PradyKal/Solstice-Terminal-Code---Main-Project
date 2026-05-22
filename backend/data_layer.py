"""
DATA LAYER
- Loads fixed asset universe
- Pulls market data via yfinance (batched, resilient)
- Ranks universe by dollar volume to produce daily Top 300-500 scan list
- Tags asset class (equity / etf / crypto / future)
"""
from __future__ import annotations
import json
import os
import time
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, List, Optional


UNIVERSE_PATH = os.environ.get("SOLSTICE_UNIVERSE_PATH", "backend/universe.json")


def asset_class(ticker: str) -> str:
    if ticker.endswith("-USD"):
        return "crypto"
    if ticker.endswith("=F"):
        return "future"
    if ticker in {"SPY","QQQ","IWM","DIA","VTI","VOO","XLK","XLF","XLE","XLV","XLY","XLP","XLI","XLU","XLB","XLRE","XLC",
                  "SMH","SOXX","XBI","IBB","ARKK","TLT","IEF","SHY","HYG","LQD","GLD","SLV","USO","UNG","DBC","GDX","GDXJ",
                  "VNQ","EFA","EEM","FXI","EWZ","EWJ","EWG","MCHI","INDA","VWO","BIL","UUP","FXE","FXY"}:
        return "etf"
    return "equity"


def load_universe(path: str = UNIVERSE_PATH) -> List[str]:
    with open(path, "r") as f:
        return json.load(f)


def _chunked(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


def fetch_prices(tickers: List[str], period: str = "6mo", interval: str = "1d",
                 batch_size: int = 120) -> Dict[str, pd.DataFrame]:
    """Return dict[ticker] -> OHLCV DataFrame. Skips delisted/empty series."""
    out: Dict[str, pd.DataFrame] = {}
    for batch in _chunked(tickers, batch_size):
        try:
            df = yf.download(batch, period=period, interval=interval,
                             auto_adjust=True, progress=False, threads=True,
                             group_by="ticker")
            if isinstance(df.columns, pd.MultiIndex):
                for t in batch:
                    try:
                        sub = df[t].dropna()
                        if len(sub) >= 30:
                            out[t] = sub
                    except Exception:
                        continue
            else:
                # single ticker
                sub = df.dropna()
                if len(sub) >= 30:
                    out[batch[0]] = sub
        except Exception:
            continue
    return out


def rank_by_dollar_volume(price_data: Dict[str, pd.DataFrame], top_n: int = 300) -> List[str]:
    """Compute 5-day average dollar volume; return top N tickers."""
    rankings = []
    for t, df in price_data.items():
        if "Close" not in df.columns or "Volume" not in df.columns:
            continue
        recent = df.tail(5)
        if recent.empty:
            continue
        adv = float((recent["Close"] * recent["Volume"]).mean())
        if not np.isfinite(adv):
            continue
        rankings.append((t, adv))
    rankings.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in rankings[:top_n]]
