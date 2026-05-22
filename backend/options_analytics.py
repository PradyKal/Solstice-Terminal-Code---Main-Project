"""
OPTIONS ANALYTICS
- Black-Scholes pricing (call/put)
- Greeks: delta, gamma, vega, theta, rho
- Implied volatility surface (parabolic smile + sqrt(T) term structure)
- Skew term structure
- Greeks exposure map for portfolio-level visualization
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple
import numpy as np
from scipy.stats import norm


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))


def _d2(d1_val: float, sigma: float, T: float) -> float:
    return d1_val - sigma * math.sqrt(T)


def black_scholes(S: float, K: float, T: float, r: float, sigma: float,
                  option_type: str = "call") -> Dict:
    """Returns price + full Greeks. T in years, r and sigma as decimals."""
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0,
                "vega": 0.0, "theta": 0.0, "rho": 0.0}
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    Nd1, Nd2 = norm.cdf(d1), norm.cdf(d2)
    nd1 = norm.pdf(d1)
    sqrtT = math.sqrt(T)

    if option_type.lower() == "call":
        price = S * Nd1 - K * math.exp(-r * T) * Nd2
        delta = Nd1
        theta = (-S * nd1 * sigma / (2 * sqrtT) - r * K * math.exp(-r * T) * Nd2) / 365.0
        rho   = K * T * math.exp(-r * T) * Nd2 / 100.0
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = Nd1 - 1.0
        theta = (-S * nd1 * sigma / (2 * sqrtT) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365.0
        rho   = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100.0

    gamma = nd1 / (S * sigma * sqrtT)
    vega  = S * nd1 * sqrtT / 100.0

    return {
        "price": float(price),
        "delta": float(delta),
        "gamma": float(gamma),
        "vega":  float(vega),
        "theta": float(theta),
        "rho":   float(rho),
    }


def iv_surface(spot: float, atm_iv: float,
               strikes_pct: Tuple[float, ...] = (0.7, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.3),
               maturities_days: Tuple[int, ...] = (7, 14, 30, 60, 90, 180, 365),
               r: float = 0.045) -> Dict:
    """
    Synthetic IV surface with realistic smile + term structure.
    When real options-chain quotes are available, replace this with
    the actual IV grid; the JSON schema below is what Lovable consumes.
    """
    grid = []
    for T_days in maturities_days:
        T = T_days / 365.0
        for k_pct in strikes_pct:
            K = spot * k_pct
            moneyness = math.log(K / spot)
            # Parabolic smile + sqrt-T term structure
            smile = 0.18 * moneyness ** 2 - 0.04 * moneyness     # asymmetric (put skew)
            term  = 0.05 * math.sqrt(T)
            iv = max(0.05, atm_iv + smile + term)
            greeks = black_scholes(spot, K, T, r, iv, "call")
            grid.append({
                "strike": float(K),
                "moneyness": float(k_pct),
                "maturity_days": int(T_days),
                "iv": float(iv),
                "call_price": greeks["price"],
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "vega":  greeks["vega"],
            })
    return {
        "viz_type": "vol_surface_3d",
        "spot": float(spot),
        "atm_iv": float(atm_iv),
        "grid": grid,
        "strikes_pct": list(strikes_pct),
        "maturities_days": list(maturities_days),
    }


def skew_term_structure(spot: float, atm_iv: float,
                        maturities_days: Tuple[int, ...] = (30, 60, 90, 180, 365)) -> Dict:
    """25-delta risk reversal across maturities -> skew over time."""
    series = []
    for T_days in maturities_days:
        T = T_days / 365.0
        # Approximate 25-delta call/put IVs by sampling smile at ±1 stdev moneyness
        sigma_atm = atm_iv + 0.05 * math.sqrt(T)
        delta_move = sigma_atm * math.sqrt(T)
        iv_otm_call = max(0.05, sigma_atm + 0.18 * (delta_move ** 2) - 0.04 * delta_move)
        iv_otm_put  = max(0.05, sigma_atm + 0.18 * (delta_move ** 2) + 0.04 * delta_move)
        series.append({
            "maturity_days": int(T_days),
            "atm_iv": float(sigma_atm),
            "rr_25d": float(iv_otm_call - iv_otm_put),   # call IV minus put IV
            "iv_otm_call_25d": float(iv_otm_call),
            "iv_otm_put_25d": float(iv_otm_put),
        })
    return {"viz_type": "iv_skew_term_structure", "spot": float(spot), "series": series}


def portfolio_greeks(positions: List[Dict], iv_default: float = 0.30) -> Dict:
    """
    Aggregate Δ, Γ, ν, Θ exposure across an equity book treating each share
    as a synthetic ATM 30-day call equivalent for visualization purposes.
    Real options positions would override the synthetic Greeks per leg.
    """
    totals = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
    per_ticker = []
    for p in positions:
        S = float(p.get("mark_price", 0.0))
        qty = float(p.get("qty", 0.0))
        if S <= 0 or qty == 0:
            continue
        g = black_scholes(S, S, 30/365.0, 0.045, iv_default, "call")
        d = g["delta"] * qty
        gam = g["gamma"] * qty
        v = g["vega"] * qty
        th = g["theta"] * qty
        totals["delta"] += d
        totals["gamma"] += gam
        totals["vega"]  += v
        totals["theta"] += th
        per_ticker.append({
            "ticker": p.get("ticker"),
            "delta": d, "gamma": gam, "vega": v, "theta": th,
        })
    return {"viz_type": "portfolio_greeks", "totals": totals, "per_ticker": per_ticker}
