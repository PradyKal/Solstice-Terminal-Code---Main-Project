"""
SOLSTICE ENGINE — main orchestrator

Pipeline per cycle:
  1. DATA LAYER       :: load universe, fetch prices, rank by liquidity (Top 300)
  2. REGIME           :: classify market regime from SPY + VIX
  3. FEATURE ENGINE   :: per-asset features (price/flow/macro/stat)
  4. STRATEGY ENGINE  :: run all modular strategies
  5. META MODEL       :: weight + combine into alpha/confidence/ER/risk
  6. RANKING          :: cross-sectional sort, take Top N
  7. SIMULATION       :: 100K MC + stress + cones + VaR/CVaR for Top N
  8. RISK ENGINE      :: sizing, heat cap, liquidity/cooldown filters
  9. EXECUTION        :: Alpaca paper (market-hours gated)
 10. PORTFOLIO INTEL  :: rolling Sharpe/Sortino/DD/HHI/sector/factor
 11. VISUALIZATIONS   :: vol surface, MC cloud, covariance heatmap, network, etc.
 12. LEDGER           :: write to Supabase (8 tables)
 13. SLACK            :: cycle digest
"""
from __future__ import annotations
import os
import json
import time
import math
from datetime import datetime
import pytz
import numpy as np
import pandas as pd

from backend import data_layer as dl
from backend import feature_engine as fe
from backend import strategy_engine as se
from backend import meta_model as mm
from backend import simulation_engine as sim
from backend import risk_engine as risk
from backend import execution_engine as ex
from backend import portfolio_intelligence as pi
from backend import visualization as viz
from backend import supabase_writer as db
from backend import slack_reporter as slack


# --------- TUNABLES (also surfaced via env) ----------
TOPN_RANK            = int(os.getenv("SOLSTICE_TOPN", "25"))
MC_RUNS              = int(os.getenv("SOLSTICE_MC_RUNS", "100000"))
MC_HORIZON_DAYS      = int(os.getenv("SOLSTICE_MC_HORIZON", "21"))
SCAN_TOP_LIQUIDITY_N = int(os.getenv("SOLSTICE_SCAN_TOP", "300"))
SLACK_CHANNEL        = os.getenv("SOLSTICE_SLACK_CHANNEL", "")
EXECUTE_MIN_CONF     = float(os.getenv("SOLSTICE_MIN_CONF", "0.75"))


def classify_regime(spy_df: pd.DataFrame, vix_df: pd.DataFrame | None) -> dict:
    close = spy_df["Close"].values
    sma20 = float(np.mean(close[-20:]))
    sma50 = float(np.mean(close[-50:]))
    r20 = float((close[-1] / close[-20] - 1)) if len(close) >= 20 else 0.0
    realized = float(np.std(np.diff(close[-20:]) / close[-21:-1])) if len(close) >= 21 else 0.0
    vix_level = None
    if vix_df is not None and "Close" in vix_df.columns:
        vix_level = float(vix_df["Close"].iloc[-1])
    if vix_level is not None and vix_level > 25 and realized > 0.015:
        regime = "high_vol_chop"
    elif sma20 > sma50 and r20 > 0.02:
        regime = "trend_up"
    elif sma20 < sma50 and r20 < -0.02:
        regime = "trend_down"
    else:
        regime = "neutral"
    return {"regime": regime, "vix": vix_level, "realized_vol_20d": realized}


def run_cycle() -> dict:
    tz = pytz.timezone("US/Eastern")
    start = datetime.now(tz)
    cycle = {"timestamp_et": start.isoformat(), "scanned": 0, "topn": 0}

    # 1. DATA LAYER
    universe = dl.load_universe()
    prices = dl.fetch_prices(universe, period="6mo")
    top_liquid = dl.rank_by_dollar_volume(prices, top_n=SCAN_TOP_LIQUIDITY_N)
    cycle["scanned"] = len(prices)
    cycle["topn_liquid"] = len(top_liquid)

    # 2. REGIME (SPY + ^VIX)
    spy_df = prices.get("SPY")
    vix_dict = dl.fetch_prices(["^VIX"], period="3mo")
    vix_df = vix_dict.get("^VIX")
    regime_info = {"regime": "neutral"} if spy_df is None else classify_regime(spy_df, vix_df)
    regime = regime_info["regime"]
    cycle["regime"] = regime
    cycle["vix_state"] = "elevated" if (regime_info.get("vix") or 0) > 22 else "normal"

    # Market returns for beta
    market_returns = None
    if spy_df is not None and len(spy_df) > 30:
        market_returns = np.diff(spy_df["Close"].values) / spy_df["Close"].values[:-1]

    # Cohort 20d return for relative strength
    cohort_20d_returns = []
    for t in top_liquid:
        df = prices.get(t)
        if df is None or len(df) < 21:
            continue
        c = df["Close"].values
        cohort_20d_returns.append(c[-1] / c[-21] - 1.0)
    cohort_ret_20d = float(np.median(cohort_20d_returns)) if cohort_20d_returns else 0.0

    # 3 + 4 + 5. FEATURES -> STRATEGIES -> META
    asset_results = []
    per_strategy_alpha = {s: [] for s in se.STRATEGIES}
    for t in top_liquid:
        df = prices.get(t)
        if df is None or len(df) < 50:
            continue
        feats = fe.compute_features(df, market_returns)
        if not feats:
            continue
        strat_out = se.run_all(feats, cohort_ret_20d, regime)
        combined = mm.combine(strat_out)

        adv_usd = float((df["Close"].tail(5) * df["Volume"].tail(5)).mean()) \
                    if "Volume" in df.columns else 0.0

        asset_results.append({
            "ticker": t,
            "asset_class": dl.asset_class(t),
            "price": feats["price"],
            "atr": feats.get("atr14") or 0.0,
            "realized_vol": feats.get("realized_vol20") or 0.3,
            "adv_usd": adv_usd,
            "features": feats,
            "strategies": strat_out,
            "alpha": combined["alpha"],
            "confidence": combined["confidence"],
            "expected_return": combined["expected_return"],
            "risk_estimate": combined["risk_estimate"],
            "attribution": combined["attribution"],
        })
        for s, out in strat_out.items():
            per_strategy_alpha[s].append({"ticker": t, "alpha": out["alpha"]})

    # 6. RANKING (cross-sectional)
    asset_results.sort(key=lambda r: abs(r["alpha"]), reverse=True)
    topN = asset_results[:TOPN_RANK]
    cycle["topn"] = len(topN)

    # 7. SIMULATION on Top N
    simulations_rows = []
    mc_path_clouds = []
    for r in topN:
        c = prices[r["ticker"]]["Close"].values
        ret = np.diff(c) / c[:-1]
        mu, sigma = float(np.mean(ret[-60:])), float(np.std(ret[-60:]))
        if not (math.isfinite(mu) and math.isfinite(sigma) and sigma > 0):
            continue
        s = sim.mc_summary(r["price"], mu, sigma, MC_HORIZON_DAYS, MC_RUNS)
        s["ticker"] = r["ticker"]
        s["model"] = "GBM_MC_100K"
        s["regime"] = regime
        simulations_rows.append({
            "ticker": r["ticker"],
            "model": s["model"],
            "runs": MC_RUNS,
            "horizon_days": MC_HORIZON_DAYS,
            "mean_return": s["mean_return"],
            "median_return": s["median_return"],
            "std_return": s["std_return"],
            "var_95": s["var_95"],
            "cvar_95": s["cvar_95"],
            "prob_up": s["prob_up"],
            "prob_down": s["prob_down"],
            "regime": regime,
            "payload": {"percentiles": s["percentiles"]},
        })
        # MC cloud for visualization (down-sampled in sim_engine)
        mc_path_clouds.append({
            "viz_type": "mc_path_cloud",
            "ticker": r["ticker"],
            "scope": "topN",
            "payload": {"horizon": MC_HORIZON_DAYS, "paths": s["path_sample"]},
        })

    # 8. RISK ENGINE
    R = risk.RiskEngine()
    validated, rejected = [], []
    for idx, r in enumerate(topN):
        reason = R.can_size(r["ticker"], r["price"], r["atr"], r["realized_vol"], r["adv_usd"])
        if reason:
            rejected.append({"ticker": r["ticker"], "reason": reason, "alpha": r["alpha"]})
            continue
        sized = R.size_position(r["price"], r["atr"])
        if not R.admit(r["ticker"], sized["capital"]):
            rejected.append({"ticker": r["ticker"], "reason": "portfolio_heat_cap", "alpha": r["alpha"]})
            break
        side = "BUY" if r["alpha"] > 0 else "SELL"
        validated.append({
            "ticker": r["ticker"],
            "side": side,
            "qty": round(sized["shares"], 4),
            "entry_price": round(r["price"], 4),
            "alpha_rank": idx + 1,
            "confidence": r["confidence"],
            "notes": f"alpha={r['alpha']:.3f} ER={r['expected_return']:.3f}",
        })

    # 9. EXECUTION — only the highest-confidence subset, market-hours gated inside
    executed = []
    for v in validated:
        if v["confidence"] < EXECUTE_MIN_CONF:
            continue
        res = ex.execute_validated(v)
        executed.append(res)

    # 10. PORTFOLIO INTEL placeholder (live read from Alpaca + Supabase positions
    #     in production; here we summarize the cycle's intended exposure)
    intended_positions = [{"ticker": v["ticker"], "qty": v["qty"] if v["side"]=="BUY" else -v["qty"],
                            "mark_price": v["entry_price"]} for v in validated]
    exposure = pi.total_exposures(intended_positions)
    portfolio_row = {
        "gross_exposure": exposure["gross_exposure"],
        "net_exposure": exposure["net_exposure"],
        "concentration_hhi": pi.hhi_concentration(intended_positions),
        "regime": regime,
    }

    # 11. VISUALIZATION DATA
    # Build returns frame for top-30 to keep payload light
    top_for_viz = [r["ticker"] for r in topN[:30]]
    rets_df_data = {}
    for t in top_for_viz:
        c = prices[t]["Close"].values
        rets_df_data[t] = np.diff(c) / c[:-1]
    minlen = min((len(v) for v in rets_df_data.values()), default=0)
    rets_df = pd.DataFrame({k: v[-minlen:] for k, v in rets_df_data.items()}) if minlen > 5 else pd.DataFrame()
    viz_rows = []
    if not rets_df.empty:
        viz_rows.append({"viz_type": "covariance_heatmap", "ticker": None, "scope": "top30",
                         "payload": viz.covariance_heatmap(rets_df)})
        viz_rows.append({"viz_type": "correlation_network", "ticker": None, "scope": "top30",
                         "payload": viz.correlation_network(rets_df, threshold=0.55)})
    # Risk topology
    viz_rows.append({"viz_type": "risk_topology", "ticker": None, "scope": "topN",
                     "payload": viz.risk_topology([
                         {"ticker": r["ticker"], "alpha": r["alpha"],
                          "expected_return": r["expected_return"],
                          "risk_score": r["risk_estimate"], "liquidity_usd": r["adv_usd"]}
                         for r in topN])})
    # MC path clouds
    viz_rows.extend(mc_path_clouds)
    # PDF mesh for top opp
    if topN:
        c0 = prices[topN[0]["ticker"]]["Close"].values
        r0 = np.diff(c0) / c0[:-1]
        viz_rows.append({"viz_type": "pdf_mesh", "ticker": topN[0]["ticker"], "scope": "top1",
                         "payload": viz.probability_density_mesh(r0)})
    # Signal map
    viz_rows.append({"viz_type": "signal_map", "ticker": None, "scope": "topN",
                     "payload": viz.signal_map(per_strategy_alpha)})

    # 12. SUPABASE WRITES
    signals_rows = [{
        "ticker": r["ticker"], "signal": "BUY" if r["alpha"] > 0.05 else ("SELL" if r["alpha"] < -0.05 else "HOLD"),
        "confidence": round(r["confidence"], 4),
        "expected_return": round(r["expected_return"], 4),
        "risk_score": round(r["risk_estimate"], 4),
        "asset_class": r["asset_class"],
        "price": round(r["price"], 6),
        "regime": regime,
        "volatility": round(r["realized_vol"], 4),
        "mc_runs": MC_RUNS,
        "rationale": "; ".join(f"{k}:{v['alpha']:+.2f}" for k, v in r["strategies"].items()),
    } for r in topN]

    trades_rows = [{
        "ticker": t["ticker"], "side": t["side"], "qty": t["qty"],
        "entry_price": t["entry_price"], "status": t.get("status", "VALIDATED"),
        "broker": t.get("broker", "alpaca_paper"),
        "broker_order_id": t.get("broker_order_id"),
        "confidence": t["confidence"],
        "notes": t.get("notes", "")[:500],
    } for t in (executed if executed else validated)]

    # strategy_performance per cycle: log average alpha emitted as a leading indicator
    strat_perf_rows = []
    for s, items in per_strategy_alpha.items():
        if not items:
            continue
        alphas = np.array([i["alpha"] for i in items])
        strat_perf_rows.append({
            "strategy": s,
            "weight": mm.DEFAULT_WEIGHTS.get(s, 0.0),
            "signals_emitted": int((np.abs(alphas) > 0.05).sum()),
            "avg_return": float(np.mean(alphas)),
            "regime": regime,
            "window_days": 1,
        })

    viz_db_rows = [{"viz_type": v["viz_type"], "ticker": v.get("ticker"),
                    "scope": v.get("scope"), "payload": v["payload"]} for v in viz_rows]

    db.write_signals(signals_rows)
    db.write_trades(trades_rows)
    db.write_simulations(simulations_rows)
    db.write_portfolio_metrics([portfolio_row])
    db.write_strategy_performance(strat_perf_rows)
    db.write_visualization(viz_db_rows)
    db.write_logs([{
        "level": "INFO", "component": "Engine",
        "message": f"Cycle complete | regime={regime} | topN={len(topN)} | executed={len(executed)}",
        "meta": {"scanned": cycle["scanned"]}
    }])

    # 13. SLACK
    cycle.update({
        "top_signals": [{"ticker": r["ticker"], "alpha": r["alpha"], "confidence": r["confidence"],
                          "expected_return": r["expected_return"], "risk_score": r["risk_estimate"]}
                         for r in topN[:10]],
        "rejected": rejected,
        "executed": executed,
        "portfolio": portfolio_row,
        "strategy_attribution": {k: {"weight": mm.DEFAULT_WEIGHTS.get(k, 0.0),
                                      "contribution": float(np.mean([i["alpha"] for i in v])) if v else 0.0}
                                  for k, v in per_strategy_alpha.items()},
    })
    if SLACK_CHANNEL:
        slack.send_to_slack(SLACK_CHANNEL, slack.format_digest(cycle))

    return cycle


if __name__ == "__main__":
    out = run_cycle()
    print(json.dumps({k: v for k, v in out.items() if k != "top_signals"}, indent=2, default=str)[:1500])
