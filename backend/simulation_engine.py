"""
SIMULATION ENGINE
- Monte Carlo (GBM, configurable up to 100K+ paths) with vectorized numpy
- VaR / CVaR
- Stress tests (volatility shock, regime shock, correlated drawdown)
- Volatility cone projection (rolling realized vol percentiles)
- Portfolio optimization (mean-variance, long-only, weight cap)
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple


def monte_carlo_gbm(spot: float, mu: float, sigma: float,
                    horizon: int = 21, runs: int = 100_000,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """Returns array shape (runs, horizon). Daily steps, mu/sigma daily."""
    rng = rng or np.random.default_rng()
    shocks = rng.standard_normal(size=(runs, horizon))
    drift = (mu - 0.5 * sigma ** 2)
    increments = drift + sigma * shocks
    log_paths = np.cumsum(increments, axis=1)
    return spot * np.exp(log_paths)


def mc_summary(spot: float, mu: float, sigma: float,
               horizon: int = 21, runs: int = 100_000) -> Dict:
    paths = monte_carlo_gbm(spot, mu, sigma, horizon, runs)
    finals = paths[:, -1]
    ret = (finals - spot) / spot
    var95 = float(np.percentile(ret, 5))
    cvar95 = float(ret[ret <= var95].mean()) if np.any(ret <= var95) else var95
    return {
        "runs": int(runs),
        "horizon_days": int(horizon),
        "mean_return": float(ret.mean()),
        "median_return": float(np.median(ret)),
        "std_return": float(ret.std()),
        "var_95": var95,
        "cvar_95": cvar95,
        "prob_up": float((ret > 0).mean()),
        "prob_down": float((ret < 0).mean()),
        "percentiles": {
            "p05": float(np.percentile(ret, 5)),
            "p25": float(np.percentile(ret, 25)),
            "p50": float(np.percentile(ret, 50)),
            "p75": float(np.percentile(ret, 75)),
            "p95": float(np.percentile(ret, 95)),
        },
        # Down-sampled cloud for frontend (Three.js)
        "path_sample": paths[:200].tolist(),
    }


def stress_scenarios(spot: float, mu: float, sigma: float, horizon: int = 21,
                     runs: int = 25_000) -> Dict[str, Dict]:
    """Multiplicative shocks: bear regime, vol blow-up, mean crash."""
    out = {}
    out["base"]    = mc_summary(spot, mu,       sigma,       horizon, runs)
    out["vol_2x"]  = mc_summary(spot, mu,       sigma * 2.0, horizon, runs)
    out["bear"]    = mc_summary(spot, mu - 0.01, sigma * 1.5, horizon, runs)
    out["crash"]   = mc_summary(spot, -0.03,    sigma * 2.5, horizon, runs)
    return out


def volatility_cone(returns: np.ndarray, windows: List[int] = (5, 10, 20, 60, 120)) -> Dict:
    """Realized vol percentile cone for given lookback windows."""
    cone = {}
    for w in windows:
        if len(returns) < w + 5:
            continue
        rolling = np.array([np.std(returns[i:i+w]) * np.sqrt(252.0)
                            for i in range(len(returns) - w)])
        cone[str(w)] = {
            "current": float(rolling[-1]),
            "p05": float(np.percentile(rolling, 5)),
            "p25": float(np.percentile(rolling, 25)),
            "p50": float(np.percentile(rolling, 50)),
            "p75": float(np.percentile(rolling, 75)),
            "p95": float(np.percentile(rolling, 95)),
        }
    return cone


def mean_variance_optimize(expected_returns: np.ndarray, cov: np.ndarray,
                           risk_aversion: float = 5.0,
                           max_weight: float = 0.10) -> np.ndarray:
    """
    Long-only mean-variance with weight cap.
    w = argmax mu'w - 0.5*lambda*w'Σw  subject to sum w = 1, 0 <= w_i <= max_weight.
    Closed-form unconstrained then projection (good enough as starting heuristic).
    """
    n = len(expected_returns)
    try:
        inv = np.linalg.pinv(cov + 1e-6 * np.eye(n))
        w = inv @ expected_returns / risk_aversion
    except np.linalg.LinAlgError:
        w = np.ones(n) / n
    # Project to long-only with cap
    w = np.clip(w, 0.0, max_weight)
    s = w.sum()
    if s <= 0:
        return np.ones(n) / n
    return w / s


def implied_drawdown(paths: np.ndarray) -> float:
    """Across all simulated paths, expected max drawdown."""
    cummax = np.maximum.accumulate(paths, axis=1)
    dd = (paths - cummax) / cummax
    return float(dd.min(axis=1).mean())
