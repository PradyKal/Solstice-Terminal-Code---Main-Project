"""
META-MODEL / WEIGHTING ENGINE

- Combines strategy outputs into a single alpha + confidence per asset.
- Weights are deterministic, refreshed weekly from strategy_performance attribution.
- Stores per-cycle attribution metrics so the weekly rebalancer can adapt weights safely.

NOT self-modifying mid-run. Weights only change on a scheduled weekly recompute job
that reads recent strategy PnL from Supabase and applies a bounded inverse-volatility
performance-weighted scheme.
"""
from __future__ import annotations
import numpy as np
from typing import Dict


# Default starting weights (updated weekly externally).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "momentum":            0.22,
    "mean_reversion":      0.16,
    "volatility_breakout": 0.10,
    "trend_following":     0.18,
    "relative_strength":   0.12,
    "flow":                0.10,
    "regime_sensitive":    0.12,
}


def normalize(weights: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, w) for w in weights.values())
    if s <= 0:
        return DEFAULT_WEIGHTS.copy()
    return {k: max(0.0, v) / s for k, v in weights.items()}


def combine(strategy_outputs: Dict[str, Dict], weights: Dict[str, float] = None) -> Dict:
    """Returns combined alpha, expected return, confidence, risk, attribution."""
    w = normalize(weights or DEFAULT_WEIGHTS)
    alpha, er, risk, conf_acc = 0.0, 0.0, 0.0, 0.0
    attribution = {}
    for name, out in strategy_outputs.items():
        wt = w.get(name, 0.0)
        a = out["alpha"]
        e = out["expected_return"]
        r = out["risk_estimate"]
        c = out["confidence"]
        alpha += wt * a
        er    += wt * e
        risk  += wt * r
        conf_acc += wt * c
        attribution[name] = {"weight": wt, "alpha": a, "contribution": wt * a}
    # Cross-strategy agreement boosts confidence
    signs = [np.sign(o["alpha"]) for o in strategy_outputs.values() if abs(o["alpha"]) > 0.05]
    agreement = abs(sum(signs)) / max(1, len(signs)) if signs else 0.0
    confidence = float(min(1.0, 0.6 * conf_acc + 0.4 * agreement))
    return {
        "alpha": float(alpha),
        "expected_return": float(er),
        "risk_estimate": float(risk),
        "confidence": confidence,
        "attribution": attribution,
    }


def weekly_rebalance(strategy_pnl: Dict[str, float], strategy_vol: Dict[str, float],
                     min_w: float = 0.05, max_w: float = 0.35) -> Dict[str, float]:
    """
    Recompute weights from last-7-day attributed PnL and realized volatility.
    score_i = max(0, PnL_i) / (vol_i + eps)   -> inverse-vol Sharpe-like
    Bounded into [min_w, max_w]. Renormalized.
    """
    eps = 1e-6
    raw = {}
    for s in DEFAULT_WEIGHTS:
        pnl = strategy_pnl.get(s, 0.0)
        vol = strategy_vol.get(s, 0.0) + eps
        raw[s] = max(0.0, pnl) / vol
    if sum(raw.values()) == 0:
        return DEFAULT_WEIGHTS.copy()
    w = normalize(raw)
    w = {k: max(min_w, min(max_w, v)) for k, v in w.items()}
    return normalize(w)
