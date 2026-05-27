# SOLSTICE TERMINAL — Frontend

Pure static HTML/JS terminal that connects directly to Supabase realtime. No build step, no framework, no Lovable dependency.

## Files

```
solstice_terminal/
├── index.html         landing — full-bleed 3D probability surface
├── login.html         Prady0901 / @Prady0901
├── terminal.html      10-tab Bloomberg-style dashboard
├── css/styles.css     institutional dark theme
├── js/
│   ├── config.js      Supabase client + formatters
│   ├── auth.js        login via verify_user RPC
│   ├── router.js      hash-based tab routing
│   ├── viz.js         Three.js + D3 renderers (all viz_types)
│   ├── app.js         bootstrap, KPI bar, heartbeat, clock
│   └── tabs/
│       ├── analyze.js        live signals table
│       ├── portfolio.js      positions + portfolio metrics
│       ├── trades.js         Alpaca paper trade history
│       ├── models.js         strategy performance + weights
│       ├── simulations.js    MC results + 3D path clouds
│       ├── risk.js           risk topology + liquidity heatmap
│       ├── regime.js         regime classifier history
│       ├── attribution.js    per-strategy signal map
│       ├── engine.js         full 3D visualization grid
│       └── logs.js           streaming log viewer
└── assets/hero.jpeg   landing image
```

## Deploy

```bash
# Option A: Vercel (60 seconds, free)
npm i -g vercel
cd solstice_terminal && vercel --prod

# Option B: Netlify drag-and-drop
zip -r solstice.zip . && upload at app.netlify.com/drop

# Option C: GitHub Pages
git push to gh-pages branch and enable Pages
```

## Live data sources (Supabase tables)

| Tab | Reads from |
|---|---|
| Header KPIs | `account_state`, `signals.regime` |
| Analyze | `signals` |
| Portfolio | `positions`, `portfolio_metrics` |
| Trades | `trades` |
| Models | `strategy_performance` |
| Simulations | `simulations`, `visualization_data` (mc_path_cloud) |
| Risk Engine | `portfolio_metrics`, `visualization_data` (risk_topology, liquidity_heatmap) |
| Market Regime | `signals.regime` |
| Strategy Attribution | `visualization_data` (signal_map) |
| Engine View | `visualization_data` (all 10 viz_types) |
| Logs | `logs` |

All tabs use Supabase realtime — every insert from the Gumloop backend updates the terminal the same tick. No polling.
