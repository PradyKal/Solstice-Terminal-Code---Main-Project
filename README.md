# Solstice Terminal — Main Project

Autonomous quant backend + Supabase ledger + Lovable frontend.

## Architecture

```
DATA LAYER (yfinance / congress / options flow)
  -> FEATURE ENGINE (returns, vol, momentum, regime)
     -> STRATEGY LAYER (momentum, mean reversion, vol breakout, flow)
        -> ALPHA MODEL (fixed-weight meta-model, cross-sectional rank)
           -> RISK ENGINE (ATR sizing, heat cap, slippage filter)
              -> EXECUTION (Alpaca paper)
                 -> SUPABASE LEDGER (signals/trades/positions/logs/simulations)
                    -> LOVABLE FRONTEND (real-time terminal)
```

## Backend
- `backend/solstice_engine.py` — core quant decision engine
- `backend/universe.json` — fixed asset universe (~794 tickers)
- `backend/schema.sql` — Supabase schema (signals, trades, positions, logs, simulations)

## Schedule
Deployed on Gumloop with cron `*/15 9-16 * * 1-5` (Mon–Fri, every 15 min during market hours).

## Reality boundaries
- Fixed universe, ranked liquidity — no random sampling
- Fixed strategies; weights adjusted on a weekly performance cadence — not mid-run
- Hard portfolio constraints (heat cap, position cap, slippage filter)
- Execution gated on market hours
- Supabase is the single source of truth
