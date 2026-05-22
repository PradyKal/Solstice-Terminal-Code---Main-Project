"""
VISUALIZATION DATA GENERATION
All outputs are JSON-serializable structures optimized for Three.js / WebGL rendering.

Produces:
  - 3D volatility surface (strike x maturity x IV)
  - Probability density mesh (return distribution surface)
  - Covariance heatmap
  - Monte Carlo path cloud
  - Risk topology map (alpha vs risk scatter, sized by liquidity)
  - Portfolio network graph (correlation > threshold edges)
  - Regime state transitions
  - Rolling correlation matrix
  - Sector flow diagram
  - Signal map (per-strategy alpha grid)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List


def vol_surface_synthetic(spot: float, atm_iv: float,
                          strikes_pct=(0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2),
                          maturities=(7, 30, 60, 90, 180, 365)) -> Dict:
    """
    Synthetic IV surface with smile + term structure. When real options-chain
    data is available, replace with actual quotes; structure is identical.
    """
    surface = []
    for T in maturities:
        for k in strikes_pct:
            moneyness = k - 1.0
            smile = 0.20 * moneyness * moneyness     # parabolic smile
            term = 0.05 * np.sqrt(T / 30.0)          # term structure
            iv = max(0.05, atm_iv + smile + term)
            surface.append({
                "strike": float(spot * k),
                "maturity_days": int(T),
                "iv": float(iv),
            })
    return {"viz_type": "vol_surface_3d", "spot": float(spot), "grid": surface}


def probability_density_mesh(returns: np.ndarray, bins: int = 60) -> Dict:
    if len(returns) < 20:
        return {"viz_type": "pdf_mesh", "x": [], "y": []}
    hist, edges = np.histogram(returns, bins=bins, density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return {"viz_type": "pdf_mesh", "x": centers.tolist(), "y": hist.tolist()}


def covariance_heatmap(returns_df: pd.DataFrame) -> Dict:
    """returns_df: columns = tickers, rows = daily returns."""
    if returns_df.shape[1] < 2:
        return {"viz_type": "covariance_heatmap", "tickers": [], "matrix": []}
    cov = returns_df.cov().fillna(0.0)
    return {
        "viz_type": "covariance_heatmap",
        "tickers": list(cov.columns),
        "matrix": cov.values.round(6).tolist(),
    }


def mc_path_cloud(paths: np.ndarray, sample: int = 200) -> Dict:
    """Down-sample to keep payload light for the frontend."""
    n = min(sample, paths.shape[0])
    idx = np.random.choice(paths.shape[0], n, replace=False)
    return {
        "viz_type": "mc_path_cloud",
        "horizon": int(paths.shape[1]),
        "paths": paths[idx].round(4).tolist(),
    }


def risk_topology(signals: List[Dict]) -> Dict:
    """
    signals: [{ticker, alpha, expected_return, risk_score, liquidity_usd}, ...]
    Frontend renders as 3D scatter: x=alpha, y=expected_return, z=risk, size=liquidity.
    """
    points = [
        {
            "ticker": s["ticker"],
            "x": float(s.get("alpha", 0.0)),
            "y": float(s.get("expected_return", 0.0)),
            "z": float(s.get("risk_score", 0.0)),
            "size": float(s.get("liquidity_usd", 0.0)),
        }
        for s in signals
    ]
    return {"viz_type": "risk_topology", "points": points}


def correlation_network(returns_df: pd.DataFrame, threshold: float = 0.6) -> Dict:
    """Edges where |corr| > threshold. Nodes are tickers."""
    if returns_df.shape[1] < 2:
        return {"viz_type": "correlation_network", "nodes": [], "edges": []}
    corr = returns_df.corr().fillna(0.0)
    nodes = [{"id": t} for t in corr.columns]
    edges = []
    for i, a in enumerate(corr.columns):
        for j, b in enumerate(corr.columns):
            if j <= i:
                continue
            c = float(corr.iloc[i, j])
            if abs(c) >= threshold:
                edges.append({"source": a, "target": b, "weight": c})
    return {"viz_type": "correlation_network", "nodes": nodes, "edges": edges}


def regime_transitions(regime_series: List[Dict]) -> Dict:
    """regime_series: [{date, regime}, ...]"""
    return {"viz_type": "regime_transitions", "series": regime_series}


def signal_map(per_strategy: Dict[str, List[Dict]]) -> Dict:
    """per_strategy: {strategy_name: [{ticker, alpha}, ...]} -> grid for heatmap."""
    return {"viz_type": "signal_map", "strategies": per_strategy}


def sector_flow(sector_changes: Dict[str, float]) -> Dict:
    """sector_changes: {sector_name: delta_pct_today}"""
    return {
        "viz_type": "sector_flow",
        "sectors": [{"name": k, "flow": float(v)} for k, v in sector_changes.items()],
    }
