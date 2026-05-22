"""
FEATURE ENGINE
Per-asset features:
  PRICE:  momentum, rolling returns, MAs, ATR, VWAP deviation, realized vol, gap analysis
  FLOW:   options activity proxy, unusual volume, relative liquidity (insider/congress are upstream)
  MACRO:  SPY regime, VIX state, sector correlation context (injected by caller)
  STAT:   z-scores, rolling beta, Sharpe, skew, kurtosis
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Optional
from scipy import stats


def safe_returns(close: np.ndarray) -> np.ndarray:
    r = np.diff(close) / close[:-1]
    return r[np.isfinite(r)]


def realized_vol(returns: np.ndarray, window: int = 20, annualize: bool = True) -> float:
    if len(returns) < window:
        return float("nan")
    s = float(np.std(returns[-window:]))
    return s * np.sqrt(252.0) if annualize else s


def atr(df: pd.DataFrame, window: int = 14) -> float:
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    if len(close) < window + 1:
        return float("nan")
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])))
    return float(np.mean(tr[-window:]))


def vwap_deviation(df: pd.DataFrame, window: int = 20) -> float:
    if "Volume" not in df.columns or len(df) < window:
        return float("nan")
    sub = df.tail(window)
    typical = (sub["High"] + sub["Low"] + sub["Close"]) / 3.0
    vwap = float((typical * sub["Volume"]).sum() / max(sub["Volume"].sum(), 1.0))
    last_close = float(sub["Close"].iloc[-1])
    return (last_close - vwap) / vwap if vwap else float("nan")


def gap_score(df: pd.DataFrame) -> float:
    """Yesterday's close -> today's open gap, normalized by ATR."""
    if len(df) < 2:
        return 0.0
    prev_close = float(df["Close"].iloc[-2])
    today_open = float(df["Open"].iloc[-1])
    a = atr(df)
    if not a or np.isnan(a) or a == 0:
        return 0.0
    return (today_open - prev_close) / a


def rolling_beta(asset_returns: np.ndarray, market_returns: np.ndarray, window: int = 60) -> float:
    n = min(len(asset_returns), len(market_returns), window)
    if n < 20:
        return float("nan")
    a = asset_returns[-n:]
    m = market_returns[-n:]
    var_m = float(np.var(m))
    if var_m == 0:
        return float("nan")
    cov = float(np.cov(a, m, bias=True)[0, 1])
    return cov / var_m


def rolling_sharpe(returns: np.ndarray, window: int = 60, rf_daily: float = 0.0) -> float:
    if len(returns) < window:
        return float("nan")
    r = returns[-window:] - rf_daily
    s = float(np.std(r))
    if s == 0:
        return float("nan")
    return float(np.mean(r)) / s * np.sqrt(252.0)


def zscore(series: np.ndarray, window: int = 20) -> float:
    if len(series) < window:
        return 0.0
    sub = series[-window:]
    mu, sd = float(np.mean(sub)), float(np.std(sub))
    if sd == 0:
        return 0.0
    return (float(series[-1]) - mu) / sd


def unusual_volume(df: pd.DataFrame, window: int = 20) -> float:
    """Today's volume / 20d avg volume."""
    if "Volume" not in df.columns or len(df) < window + 1:
        return 1.0
    avg = float(df["Volume"].tail(window).mean())
    if avg == 0:
        return 1.0
    return float(df["Volume"].iloc[-1]) / avg


def compute_features(df: pd.DataFrame, market_returns: Optional[np.ndarray] = None) -> Dict:
    close = df["Close"].values.astype(float)
    if len(close) < 50:
        return {}
    r = safe_returns(close)
    out = {
        "price": float(close[-1]),
        "ret_1d": float(r[-1]) if len(r) else 0.0,
        "ret_5d": float(np.prod(1 + r[-5:]) - 1) if len(r) >= 5 else 0.0,
        "ret_20d": float(np.prod(1 + r[-20:]) - 1) if len(r) >= 20 else 0.0,
        "sma20": float(np.mean(close[-20:])),
        "sma50": float(np.mean(close[-50:])),
        "atr14": atr(df),
        "vwap_dev20": vwap_deviation(df, 20),
        "gap_atr": gap_score(df),
        "realized_vol20": realized_vol(r, 20),
        "zscore20": zscore(close, 20),
        "unusual_vol": unusual_volume(df, 20),
        "skew": float(stats.skew(r[-60:])) if len(r) >= 60 else 0.0,
        "kurt": float(stats.kurtosis(r[-60:])) if len(r) >= 60 else 0.0,
        "rolling_sharpe60": rolling_sharpe(r, 60),
    }
    if market_returns is not None and len(market_returns) > 20:
        out["beta_60"] = rolling_beta(r, market_returns, 60)
    return out
