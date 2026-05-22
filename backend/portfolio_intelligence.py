"""
PORTFOLIO INTELLIGENCE LAYER
Computes rolling exposure, Sharpe, Sortino, beta-to-SPY, max drawdown,
HHI concentration, sector exposure, factor exposure.
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List


def total_exposures(positions: List[Dict]) -> Dict:
    """positions: [{ticker, qty, mark_price, side}, ...]"""
    longs  = sum(p["qty"] * p["mark_price"] for p in positions if p["qty"] > 0)
    shorts = sum(-p["qty"] * p["mark_price"] for p in positions if p["qty"] < 0)
    return {
        "gross_exposure": float(longs + shorts),
        "net_exposure": float(longs - shorts),
    }


def rolling_sharpe(daily_returns: np.ndarray, rf_daily: float = 0.0) -> float:
    if len(daily_returns) < 10:
        return float("nan")
    excess = daily_returns - rf_daily
    s = float(np.std(excess))
    return float(np.mean(excess)) / s * np.sqrt(252.0) if s > 0 else float("nan")


def rolling_sortino(daily_returns: np.ndarray, rf_daily: float = 0.0) -> float:
    if len(daily_returns) < 10:
        return float("nan")
    excess = daily_returns - rf_daily
    downside = excess[excess < 0]
    d = float(np.std(downside)) if len(downside) else 0.0
    return float(np.mean(excess)) / d * np.sqrt(252.0) if d > 0 else float("nan")


def max_drawdown(equity_curve: np.ndarray) -> float:
    if len(equity_curve) < 2:
        return 0.0
    cummax = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - cummax) / cummax
    return float(dd.min())


def beta_to_market(asset_returns: np.ndarray, market_returns: np.ndarray) -> float:
    n = min(len(asset_returns), len(market_returns))
    if n < 20:
        return float("nan")
    a, m = asset_returns[-n:], market_returns[-n:]
    var_m = float(np.var(m))
    return float(np.cov(a, m, bias=True)[0, 1]) / var_m if var_m > 0 else float("nan")


def hhi_concentration(positions: List[Dict]) -> float:
    """Herfindahl-Hirschman index of position weights."""
    total = sum(abs(p["qty"] * p["mark_price"]) for p in positions)
    if total == 0:
        return 0.0
    weights = [abs(p["qty"] * p["mark_price"]) / total for p in positions]
    return float(sum(w * w for w in weights))


def sector_exposure(positions: List[Dict], sector_map: Dict[str, str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    total = sum(abs(p["qty"] * p["mark_price"]) for p in positions) or 1.0
    for p in positions:
        sec = sector_map.get(p["ticker"], "UNKNOWN")
        out[sec] = out.get(sec, 0.0) + abs(p["qty"] * p["mark_price"]) / total
    return out


def factor_exposure(positions: List[Dict], factor_loadings: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """
    factor_loadings: {ticker: {factor: loading}}
    Returns weighted factor exposure across the book.
    """
    total = sum(abs(p["qty"] * p["mark_price"]) for p in positions) or 1.0
    out: Dict[str, float] = {}
    for p in positions:
        w = abs(p["qty"] * p["mark_price"]) / total
        loadings = factor_loadings.get(p["ticker"], {})
        for f, l in loadings.items():
            out[f] = out.get(f, 0.0) + w * l
    return out
