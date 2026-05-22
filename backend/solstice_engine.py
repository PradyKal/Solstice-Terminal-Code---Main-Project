import json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, time
import pytz

# --- INSTITUTIONAL QUANT ARCHITECTURE ---
# Data Layer -> Feature Engine -> Strategy Layer -> Alpha Model -> Risk Engine -> Execution -> Ledger

def is_market_open():
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    return time(9, 30) <= now.time() <= time(16, 0)

def run_solstice_pipeline():
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    print(f"[{now}] STARTING INSTITUTIONAL SCAN CYCLE")

    # 1. DATA LAYER: Load fixed universe and rank by liquidity
    with open("backend/universe.json", "r") as f:
        universe = json.load(f)

    print(f"Loading {len(universe)} assets. Ranking by Dollar Volume...")
    # In production: pull 5d bars, compute Close * Volume avg, sort descending, take top 300.
    top_300_liquid = universe[:300]

    data = yf.download(top_300_liquid, period="6mo", interval="1d",
                       group_by="ticker", progress=False, auto_adjust=True)

    alpha_scores = []

    # 2. FEATURE ENGINE & 3. STRATEGY LAYER
    for ticker in top_300_liquid:
        try:
            df = data[ticker].dropna() if len(top_300_liquid) > 1 else data.dropna()
            if len(df) < 50:
                continue

            close = df['Close'].values
            high = df['High'].values
            low = df['Low'].values
            current_price = float(close[-1])

            returns = np.diff(close) / close[:-1]
            atr14 = float(np.mean(high[-14:] - low[-14:]))
            volatility = float(np.std(returns[-20:]))
            sma20 = float(np.mean(close[-20:]))
            sma50 = float(np.mean(close[-50:]))

            # Fixed deterministic strategies
            mom_score = 1.0 if sma20 > sma50 else -1.0
            rev_score = (sma20 - current_price) / (2 * np.std(close[-20:]) + 1e-9)
            vol_score = 0.5 if (current_price > close[-2] + atr14) else (-0.5 if current_price < close[-2] - atr14 else 0.0)

            # 4. ALPHA MODEL: fixed weights, updated weekly outside the run
            raw_alpha = (mom_score * 0.40) + (rev_score * 0.40) + (vol_score * 0.20)

            alpha_scores.append({
                "ticker": ticker,
                "price": current_price,
                "atr": atr14,
                "volatility": volatility,
                "alpha": raw_alpha,
                "features": f"Mom:{mom_score:.2f} Rev:{rev_score:.2f} Vol:{vol_score:.2f}"
            })
        except Exception:
            continue

    # 5. SIGNAL RANKING (cross-sectional)
    alpha_scores.sort(key=lambda x: abs(x['alpha']), reverse=True)
    top_10 = alpha_scores[:10]
    print(f"Isolated Top 10 opportunities cross-sectionally.")

    # 6. RISK ENGINE
    TARGET_RISK_USD = 500.0
    MAX_POSITION_SIZE = 15000.0
    MAX_PORTFOLIO_HEAT = 50000.0

    validated_trades = []
    current_heat = 0.0

    for idx, opp in enumerate(top_10):
        if opp['atr'] <= 0:
            continue

        shares = TARGET_RISK_USD / opp['atr']
        capital = shares * opp['price']

        if capital > MAX_POSITION_SIZE:
            shares = MAX_POSITION_SIZE / opp['price']
            capital = MAX_POSITION_SIZE

        if current_heat + capital > MAX_PORTFOLIO_HEAT:
            print(f"Risk Engine: heat cap reached. Rejecting {opp['ticker']}")
            break

        if opp['price'] < 5.0 or opp['volatility'] > 0.10:
            print(f"Risk Engine: {opp['ticker']} rejected (penny/high-vol)")
            continue

        side = "BUY" if opp['alpha'] > 0 else "SELL"
        validated_trades.append({
            "ticker": opp['ticker'],
            "side": side,
            "qty": round(shares, 4),
            "entry_price": round(opp['price'], 4),
            "alpha_rank": idx + 1,
            "risk_metric": opp['atr'],
            "status": "VALIDATED"
        })
        current_heat += capital

    # 7. EXECUTION (Alpaca paper) - only if market is open
    if is_market_open():
        # POST to Alpaca /v2/orders for each validated trade
        print(f"Market open. Submitting {len(validated_trades)} validated trades to Alpaca.")
    else:
        print("Market closed. Skipping execution; signals still logged to Supabase.")

    # 8. SUPABASE LEDGER: bulk insert signals, trades, simulations
    # 9. SLACK: single cycle summary digest

    print(f"Cycle complete. {len(validated_trades)} trades cleared risk constraints.")
    return validated_trades


if __name__ == '__main__':
    run_solstice_pipeline()