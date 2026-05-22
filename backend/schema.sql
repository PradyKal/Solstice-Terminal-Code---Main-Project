-- Solstice Tool Terminal — backend schema
CREATE TABLE IF NOT EXISTS public.signals (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  signal TEXT NOT NULL CHECK (signal IN ('BUY','SELL','HOLD')),
  confidence NUMERIC(6,4) NOT NULL,
  expected_return NUMERIC(8,4) NOT NULL,
  risk_score NUMERIC(6,4) NOT NULL,
  asset_class TEXT,
  price NUMERIC(18,6),
  regime TEXT,
  congressional_score NUMERIC(6,4),
  insider_score NUMERIC(6,4),
  options_flow_score NUMERIC(6,4),
  volatility NUMERIC(8,4),
  mc_runs INT,
  bayesian_posterior NUMERIC(6,4),
  rationale TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS signals_ticker_idx ON public.signals(ticker);
CREATE INDEX IF NOT EXISTS signals_created_idx ON public.signals(created_at DESC);

CREATE TABLE IF NOT EXISTS public.trades (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  qty NUMERIC(18,6) NOT NULL,
  entry_price NUMERIC(18,6),
  exit_price NUMERIC(18,6),
  pnl NUMERIC(18,6),
  status TEXT NOT NULL DEFAULT 'PENDING',
  broker TEXT DEFAULT 'alpaca_paper',
  broker_order_id TEXT,
  signal_id BIGINT REFERENCES public.signals(id) ON DELETE SET NULL,
  confidence NUMERIC(6,4),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  filled_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS trades_ticker_idx ON public.trades(ticker);
CREATE INDEX IF NOT EXISTS trades_status_idx ON public.trades(status);

CREATE TABLE IF NOT EXISTS public.positions (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL UNIQUE,
  qty NUMERIC(18,6) NOT NULL,
  avg_entry NUMERIC(18,6),
  mark_price NUMERIC(18,6),
  unrealized_pnl NUMERIC(18,6),
  asset_class TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.logs (
  id BIGSERIAL PRIMARY KEY,
  level TEXT NOT NULL DEFAULT 'INFO',
  component TEXT,
  message TEXT NOT NULL,
  meta JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS logs_created_idx ON public.logs(created_at DESC);

CREATE TABLE IF NOT EXISTS public.simulations (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  model TEXT NOT NULL,
  runs INT NOT NULL,
  horizon_days INT,
  mean_return NUMERIC(10,6),
  median_return NUMERIC(10,6),
  std_return NUMERIC(10,6),
  var_95 NUMERIC(10,6),
  cvar_95 NUMERIC(10,6),
  prob_up NUMERIC(6,4),
  prob_down NUMERIC(6,4),
  regime TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS sim_ticker_idx ON public.simulations(ticker);
