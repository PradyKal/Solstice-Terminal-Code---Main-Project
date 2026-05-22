"""
ADVANCED VISUALIZATION DATA — extends the base visualization module.

Adds:
- PCA factor decomposition (3D scatter + loadings)
- Liquidity heatmap (rank vs realized vol)
- Options flow map (placeholder schema until real options feed wired)
- Portfolio exposure web (network of position -> sector -> factor)
"""
from __future__ import annotations
from typing import Dict, List
import numpy as np
import pandas as pd


def pca_factor_decomposition(returns_df: pd.DataFrame, n_components: int = 3) -> Dict:
    """
    Principal Component Analysis on the returns matrix.
    Returns 3D scatter + factor loadings for the frontend.
    """
    if returns_df.shape[1] < n_components or len(returns_df) < 10:
        return {"viz_type": "pca_factor_decomposition", "components": [], "loadings": []}

    X = returns_df.values
    X = X - X.mean(axis=0)
    # Use SVD for numerical stability
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    explained_var = (S ** 2) / max(1, (X.shape[0] - 1))
    total = explained_var.sum() or 1.0
    explained_ratio = (explained_var / total)[:n_components]
    loadings = Vt[:n_components].T   # (n_tickers, n_components)

    # Project each ticker onto component space using its loadings (already in Vt^T)
    tickers = list(returns_df.columns)
    scatter = [{
        "ticker": tickers[i],
        "pc1": float(loadings[i, 0]),
        "pc2": float(loadings[i, 1]),
        "pc3": float(loadings[i, 2]) if n_components >= 3 else 0.0,
    } for i in range(len(tickers))]

    return {
        "viz_type": "pca_factor_decomposition",
        "explained_variance_ratio": [float(x) for x in explained_ratio],
        "tickers": tickers,
        "scatter": scatter,
        "loadings": loadings.round(6).tolist(),
    }


def liquidity_heatmap(asset_records: List[Dict]) -> Dict:
    """
    asset_records: [{ticker, adv_usd, realized_vol, ...}, ...]
    Bins by liquidity decile and vol decile to produce a heatmap grid.
    """
    if not asset_records:
        return {"viz_type": "liquidity_heatmap", "matrix": [], "ticker_grid": []}

    adv  = np.array([r.get("adv_usd", 0.0) for r in asset_records])
    vol  = np.array([r.get("realized_vol", 0.0) for r in asset_records])
    tick = [r.get("ticker") for r in asset_records]

    adv_bins = np.quantile(adv, np.linspace(0, 1, 11))
    vol_bins = np.quantile(vol, np.linspace(0, 1, 11))
    matrix = np.zeros((10, 10), dtype=int)
    cells: Dict = {}
    for i, t in enumerate(tick):
        x = np.clip(np.searchsorted(adv_bins, adv[i]) - 1, 0, 9)
        y = np.clip(np.searchsorted(vol_bins, vol[i]) - 1, 0, 9)
        matrix[y, x] += 1
        cells.setdefault((int(y), int(x)), []).append(t)

    return {
        "viz_type": "liquidity_heatmap",
        "adv_bins": adv_bins.tolist(),
        "vol_bins": vol_bins.tolist(),
        "matrix": matrix.tolist(),
        "ticker_grid": {f"{y},{x}": v for (y, x), v in cells.items()},
    }


def options_flow_map(activity: List[Dict] | None = None) -> Dict:
    """
    activity: optional list from upstream options provider, e.g.
        [{ticker, call_premium, put_premium, unusual_score, expiry}, ...]
    If empty, emits zero rows — Lovable should render an empty-state panel.
    """
    return {"viz_type": "options_flow_map", "activity": activity or []}


def portfolio_exposure_web(positions: List[Dict], sector_map: Dict[str, str]) -> Dict:
    """
    Tripartite graph: position -> sector -> factor (placeholder until real factor model).
    Lovable renders as a force-directed network.
    """
    if not positions:
        return {"viz_type": "portfolio_exposure_web", "nodes": [], "edges": []}

    total = sum(abs(p["qty"] * p["mark_price"]) for p in positions) or 1.0
    nodes, edges = [], []
    sectors_seen = set()
    factors = ["growth", "value", "momentum", "low_vol", "quality"]
    for p in positions:
        ticker = p["ticker"]
        w = abs(p["qty"] * p["mark_price"]) / total
        sector = sector_map.get(ticker, "UNCLASSIFIED")
        nodes.append({"id": ticker, "type": "position", "weight": float(w)})
        if sector not in sectors_seen:
            nodes.append({"id": sector, "type": "sector", "weight": 0.0})
            sectors_seen.add(sector)
        edges.append({"source": ticker, "target": sector, "weight": float(w)})

    # Connect each sector to factors with synthetic loadings until real factor model lands
    for sec in sectors_seen:
        for f in factors:
            nodes_ids = {n["id"] for n in nodes}
            if f not in nodes_ids:
                nodes.append({"id": f, "type": "factor", "weight": 0.0})
            edges.append({"source": sec, "target": f, "weight": 0.2})

    return {"viz_type": "portfolio_exposure_web", "nodes": nodes, "edges": edges}
