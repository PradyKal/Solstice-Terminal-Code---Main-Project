"""
SOLSTICE v4 · ENSEMBLE + KELLY SIZING
Sharpe-weighted strategy combiner + Kelly position sizing.
"""
from __future__ import annotations
import numpy as np


def sharpe_weighted_ensemble(strategy_scores, strategy_sharpes, min_sharpe=0.3):
    """
    strategy_scores: dict[strategy_name] -> dict[ticker] -> alpha
    strategy_sharpes: dict[strategy_name] -> backtest Sharpe
    Returns dict[ticker] -> combined alpha, only using strategies with Sharpe >= min_sharpe
    """
    # Filter — strategies must have demonstrated positive risk-adjusted returns historically
    eligible = {k: s for k, s in strategy_sharpes.items() if s >= min_sharpe}
    if not eligible:
        # Fallback: use all with equal weights so trader doesn't go dark
        eligible = {k: 1.0 for k in strategy_scores}

    total = sum(eligible.values())
    weights = {k: s/total for k, s in eligible.items()}

    combined = {}
    for strat, w in weights.items():
        for ticker, alpha in strategy_scores.get(strat, {}).items():
            combined[ticker] = combined.get(ticker, 0.0) + w * alpha
    return combined, weights


def kelly_position_size(expected_return, variance, max_fraction=0.05, kelly_multiplier=0.5):
    """
    Half-Kelly criterion: f* = mu / sigma²
    Hard cap at max_fraction (5% of capital) so a single big bet can't wreck us.
    Returns fraction of capital to allocate.
    """
    if variance <= 0 or expected_return <= 0: return 0.0
    full_kelly = expected_return / variance
    fraction = full_kelly * kelly_multiplier   # half-Kelly is standard
    return float(min(max_fraction, max(0.0, fraction)))


def estimate_position_params(alpha, asset_daily_vol, hold_days=5):
    """
    Convert raw alpha + vol estimate into expected return + variance over hold horizon.
    """
    # Crude: assume alpha translates linearly to expected return
    # Cap so Kelly doesn't go nuts
    base_er = np.clip(alpha, -0.06, 0.06)   # ±6% over 5d max
    er = base_er * np.sqrt(hold_days / 1.0) * 0.5
    var = (asset_daily_vol * np.sqrt(hold_days)) ** 2
    return float(er), float(var)
