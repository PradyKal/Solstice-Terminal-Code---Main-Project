# Solstice Terminal — Quantitative Intelligence Engine

Institutional-grade backend for the Solstice Tool Terminal. Continuous market analysis, deterministic strategy stack, advanced simulations, visualization-ready outputs, and risk-gated paper execution via Alpaca.

## Architecture

```
DATA LAYER (universe, liquidity ranking, OHLCV)
  → REGIME CLASSIFIER (SPY trend + VIX state)
    → FEATURE ENGINE (price / flow / macro / statistical)
      → STRATEGY ENGINE (modular, deterministic)
        → META-MODEL (weighted combiner, weekly rebalanced)
          → SIGNAL RANKING (cross-sectional Top-N)
            → SIMULATION ENGINE (MC 100K+, stress, VaR/CVaR, vol cones)
              → RISK ENGINE (ATR sizing, heat cap, liquidity/cooldown)
                → EXECUTION ENGINE (Alpaca paper, market-hours gated)
                  → PORTFOLIO INTELLIGENCE (Sharpe/Sortino/DD/HHI/exposures)
                    → VISUALIZATION (Three.js-ready JSON)
                      → SUPABASE LEDGER (8 tables)
                        → SLACK CYCLE DIGEST
```

## Modules

| File | Responsibility |
|---|---|
| `backend/data_layer.py` | Universe loader, batched OHLCV fetch, dollar-volume ranker |
| `backend/feature_engine.py` | Returns, MAs, ATR, VWAP dev, realized vol, z-scores, skew/kurt, beta, Sharpe |
| `backend/strategy_engine.py` | Momentum / mean reversion / vol breakout / trend / RS / flow / regime-sensitive |
| `backend/meta_model.py` | Weighted combiner + weekly inverse-vol rebalancer |
| `backend/simulation_engine.py` | Vectorized MC (100K+), VaR/CVaR, stress, vol cones, mean-variance |
| `backend/risk_engine.py` | ATR sizing, heat cap, liquidity floor, cooldown, slippage rejection |
| `backend/execution_engine.py` | Market-hours gate + Alpaca paper order submission |
| `backend/portfolio_intelligence.py` | Sharpe, Sortino, max DD, beta, HHI, sector/factor exposure |
| `backend/visualization.py` | Vol surface, PDF mesh, covariance heatmap, MC path cloud, network graph, etc. |
| `backend/supabase_writer.py` | Batched inserts to 8 ledger tables |
| `backend/slack_reporter.py` | Institutional digest formatting + dispatch |
| `backend/solstice_engine.py` | Orchestrator (single `run_cycle()` entry point) |

## Supabase tables

`signals`, `trades`, `positions`, `logs`, `simulations`, `portfolio_metrics`, `strategy_performance`, `visualization_data`

## Schedule

Cron: `*/15 9-16 * * 1-5` (US/Eastern via Gumloop). Each tick runs `run_cycle()` end-to-end.

## Design boundaries

- Fixed universe, daily liquidity-ranked Top 300 — no random sampling.
- Strategies are deterministic modules. Weights only change via a **weekly** rebalance reading attributed PnL from `strategy_performance`.
- Execution is gated by US equity market hours (9:30–16:00 ET).
- Hard risk constraints: per-trade $ risk, max position, portfolio heat cap, liquidity floor, cooldown.
- No mid-run self-modification, no infinite strategy generation, no live-money deployment.

## Environment

| Variable | Purpose |
|---|---|
| `SOLSTICE_UNIVERSE_PATH` | Path to `universe.json` |
| `SOLSTICE_TOPN` | Cross-sectional rank size (default 25) |
| `SOLSTICE_MC_RUNS` | Monte Carlo paths (default 100000) |
| `SOLSTICE_MC_HORIZON` | MC horizon in trading days (default 21) |
| `SOLSTICE_SCAN_TOP` | Liquidity-ranked scan size (default 300) |
| `SOLSTICE_MIN_CONF` | Execution confidence floor (default 0.75) |
| `SOLSTICE_SLACK_CHANNEL` | Slack channel id for cycle digest |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase auth |
| `ALPACA_*` | Alpaca paper auth (via gumcp MCP) |
