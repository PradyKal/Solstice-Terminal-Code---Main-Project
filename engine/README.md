# Solstice Quant Engine — Full Systematic Desk

One agent running a complete quant team on a **weekly** schedule (token-efficient).

## Roles
- **Researcher** (`alpha/strategies_v2.py`): 7 factors incl. novel Convexity Capture. Cost-adjusted walk-forward backtest + Information Coefficient.
- **Portfolio Manager** (`alpha/risk_manager.py`): strategy sleeves, Sharpe×IC risk budgeting, half-Kelly sizing.
- **Risk Manager** (`alpha/risk_manager.py`): sector caps (35%), name caps (8%), drawdown circuit breaker, 15% vol targeting, trailing stops.
- **News Analyst** (`alpha/news_sentiment.py`): yfinance headlines + finance-lexicon/TextBlob sentiment, bad-news veto, sentiment-scaled sizing.
- **Execution Trader** (`runner.py`): Alpaca bracket orders (limit entry + broker-enforced stop-loss + take-profit, OCO).

## Strategies (cost-adjusted, IC-gated)
| Factor | Basis |
|---|---|
| residual_momentum | Blitz-Huij-Martens market-neutral momentum |
| vol_managed_momentum | Moreira-Muir 2017 |
| quality_stability | Calmar-ratio quality proxy |
| cointegrated_pairs | Engle-Granger + ADF test |
| short_term_reversal | Lo-MacKinlay |
| convexity_capture | ★ NOVEL — downside-capture premium |
| betting_against_beta | Frazzini-Pedersen (auto-dropped when IC<0) |

Only strategies with Sharpe≥0.5 AND IC>0 deploy; weighted by Sharpe×IC.

## Schedule
Single weekly run (Mon 9:35 ET): backtest → news screen → allocate → place bracket orders.
Alpaca enforces all stops/targets the rest of the week. ~4 agent runs/month.

## Data flow
yfinance (cached daily) → strategies → ensemble → news/risk/PM → Alpaca → Supabase ledger → Slack #trading
