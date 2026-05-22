"""
STRATEGY ENGINE
Modular, deterministic strategy modules. Each returns:
  { alpha, confidence, expected_return, risk_estimate }

Strategies:
  - momentum
  - mean_reversion
  - volatility_breakout
  - trend_following
  - stat_arb_pair (cross-sectional residual z-score)
  - flow_model (options + congress + insider, upstream-injected)
  - regime_sensitive (modulates by macro regime)
  - relative_strength
"""
from __future__ import annotations
import math
import numpy as np
from typing import Dict


def _bounded(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    if math.isnan(x):
        return 0.0
    return max(lo, min(hi, x))


def momentum_strategy(f: Dict) -> Dict:
    sma_signal = 1.0 if f.get("sma20", 0) > f.get("sma50", 0) else -1.0
    ret_20 = f.get("ret_20d", 0.0)
    alpha = _bounded(0.5 * sma_signal + 0.5 * np.tanh(ret_20 * 5))
    conf = abs(alpha)
    er = ret_20 * 0.3            # crude unbiased forward expectation
    risk = f.get("realized_vol20", 0.3)
    return {"alpha": alpha, "confidence": conf, "expected_return": er, "risk_estimate": risk}


def mean_reversion_strategy(f: Dict) -> Dict:
    z = f.get("zscore20", 0.0)
    # Reverts to mean -> opposite sign of z
    alpha = _bounded(-np.tanh(z / 2.0))
    conf = min(1.0, abs(z) / 3.0)
    er = -z * 0.005
    risk = f.get("realized_vol20", 0.3)
    return {"alpha": alpha, "confidence": conf, "expected_return": er, "risk_estimate": risk}


def volatility_breakout_strategy(f: Dict) -> Dict:
    g = f.get("gap_atr", 0.0)
    uv = f.get("unusual_vol", 1.0)
    # Breakout if price gapped >1 ATR and volume spike
    score = np.sign(g) if abs(g) > 1.0 and uv > 1.5 else 0.0
    alpha = _bounded(score * min(1.0, abs(g) / 2.0))
    conf = abs(alpha)
    er = alpha * 0.02
    risk = f.get("realized_vol20", 0.3) * 1.2
    return {"alpha": alpha, "confidence": conf, "expected_return": er, "risk_estimate": risk}


def trend_following_strategy(f: Dict) -> Dict:
    # 20d > 50d AND positive 20d return -> long; reverse for short
    s20, s50 = f.get("sma20", 0), f.get("sma50", 0)
    ret_20 = f.get("ret_20d", 0.0)
    if s20 > s50 and ret_20 > 0:
        alpha = _bounded(0.5 + min(0.5, ret_20))
    elif s20 < s50 and ret_20 < 0:
        alpha = _bounded(-0.5 + max(-0.5, ret_20))
    else:
        alpha = 0.0
    conf = abs(alpha)
    er = ret_20 * 0.4
    risk = f.get("realized_vol20", 0.3)
    return {"alpha": alpha, "confidence": conf, "expected_return": er, "risk_estimate": risk}


def relative_strength_strategy(f: Dict, cohort_ret_20d: float = 0.0) -> Dict:
    """RS = ticker 20d return - cohort 20d return."""
    rs = f.get("ret_20d", 0.0) - cohort_ret_20d
    alpha = _bounded(np.tanh(rs * 5))
    conf = abs(alpha)
    er = rs * 0.3
    risk = f.get("realized_vol20", 0.3)
    return {"alpha": alpha, "confidence": conf, "expected_return": er, "risk_estimate": risk}


def flow_strategy(insider_z: float = 0.0, congress_z: float = 0.0, options_z: float = 0.0) -> Dict:
    """
    Flow-based composite. Inputs are normalized z-scores from upstream pipelines.
    Defaults to 0 when flow data unavailable for the cycle.
    """
    flow_score = 0.4 * insider_z + 0.3 * congress_z + 0.3 * options_z
    alpha = _bounded(np.tanh(flow_score))
    conf = min(1.0, abs(flow_score) / 2.5)
    er = alpha * 0.015
    risk = 0.25
    return {"alpha": alpha, "confidence": conf, "expected_return": er, "risk_estimate": risk}


def regime_sensitive_strategy(f: Dict, regime: str) -> Dict:
    """Boost momentum in trending regimes, mean-reversion in choppy."""
    if regime == "trend_up":
        base = momentum_strategy(f)["alpha"]
    elif regime == "trend_down":
        base = -abs(momentum_strategy(f)["alpha"])
    elif regime == "high_vol_chop":
        base = mean_reversion_strategy(f)["alpha"]
    else:
        base = 0.5 * momentum_strategy(f)["alpha"] + 0.5 * mean_reversion_strategy(f)["alpha"]
    alpha = _bounded(base)
    return {"alpha": alpha, "confidence": abs(alpha), "expected_return": alpha * 0.02,
            "risk_estimate": f.get("realized_vol20", 0.3)}


STRATEGIES = [
    "momentum", "mean_reversion", "volatility_breakout", "trend_following",
    "relative_strength", "flow", "regime_sensitive"
]


def run_all(features: Dict, cohort_ret_20d: float, regime: str,
            insider_z: float = 0.0, congress_z: float = 0.0, options_z: float = 0.0) -> Dict[str, Dict]:
    return {
        "momentum": momentum_strategy(features),
        "mean_reversion": mean_reversion_strategy(features),
        "volatility_breakout": volatility_breakout_strategy(features),
        "trend_following": trend_following_strategy(features),
        "relative_strength": relative_strength_strategy(features, cohort_ret_20d),
        "flow": flow_strategy(insider_z, congress_z, options_z),
        "regime_sensitive": regime_sensitive_strategy(features, regime),
    }
