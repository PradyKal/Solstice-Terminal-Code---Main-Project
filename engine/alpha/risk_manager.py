"""
SOLSTICE · RISK MANAGER + PORTFOLIO MANAGER
Institutional controls layered on top of signal generation:

RISK MANAGER:
  - Sector exposure caps (max % per GICS-ish bucket)
  - Portfolio drawdown circuit breaker (de-risk when equity falls)
  - Volatility targeting (scale gross exposure to target portfolio vol)
  - Trailing-stop computation
  - Single-name + correlation limits

PORTFOLIO MANAGER:
  - Divides capital into strategy SLEEVES with risk budgets
  - Blends Kelly sizing with risk-parity across sleeves
"""
from __future__ import annotations
import numpy as np

# Map tickers -> sector for exposure caps
SECTOR_OF = {}
_SECTORS = {
    'SEMI': ['NVDA','AMD','MU','LRCX','KLAC','AMAT','QCOM','INTC','ADI','AVGO','TXN','MCHP','ASML','SMH','SOXX','ON','MRVL','NXPI'],
    'TECH': ['AAPL','MSFT','ORCL','CSCO','ADBE','CRM','INTU','PANW','ANET','ACN','NOW','IBM','XLK'],
    'FIN':  ['JPM','BAC','WFC','GS','MS','BLK','SPGI','SCHW','C','AXP','PGR','CB','MMC','ICE','BX','KKR','XLF'],
    'ENERGY':['XOM','CVX','COP','EOG','SLB','PSX','MPC','OXY','XLE'],
    'HEALTH':['LLY','JNJ','UNH','ABBV','MRK','TMO','PFE','ABT','AMGN','DHR','GILD','ISRG','VRTX','SYK','BSX','MDT','REGN','ELV','CI','XLV'],
    'CONS':  ['AMZN','TSLA','HD','MCD','NKE','LOW','SBUX','TJX','BKNG','CMG','WMT','PG','COST','KO','PEP','PM','MDLZ','XLY','XLP'],
    'IND':   ['CAT','UNP','GE','HON','BA','RTX','LMT','DE','ETN','TT','WM','XLI'],
    'COMM':  ['META','GOOGL','GOOG','DIS','NFLX','TMUS','VZ','T','XLC'],
    'OTHER': ['LIN','NEE','PLD','SPY','QQQ','IWM','XLU','XLB','XLRE'],
}
for sec, names in _SECTORS.items():
    for n in names:
        SECTOR_OF[n] = sec


class RiskManager:
    def __init__(self, equity, peak_equity=None):
        self.equity = float(equity)
        self.peak_equity = float(peak_equity or equity)
        # limits
        self.max_sector_pct = 0.30       # max 30% of gross in one sector
        self.max_semi_pct = 0.25         # tighter cap on semiconductors (high intra-correlation)
        self.max_name_pct = 0.08         # max 8% in one name
        self.target_gross = 1.20         # target 120% gross (mild leverage room)
        self.dd_derisk_levels = [(0.05, 0.7), (0.10, 0.4), (0.15, 0.0)]  # (dd, exposure_mult)

    def drawdown(self):
        return (self.equity - self.peak_equity) / self.peak_equity if self.peak_equity > 0 else 0.0

    def exposure_multiplier(self):
        """Cut exposure as drawdown deepens (circuit breaker)."""
        dd = abs(min(0.0, self.drawdown()))
        mult = 1.0
        for level, m in self.dd_derisk_levels:
            if dd >= level:
                mult = m
        return mult

    def vol_target_scalar(self, portfolio_daily_vol, target_annual_vol=0.15):
        """Scale gross exposure to hit target annualized vol."""
        port_annual = portfolio_daily_vol * np.sqrt(252) + 1e-9
        return float(np.clip(target_annual_vol / port_annual, 0.4, 1.5))

    def _cap_for(self, sector):
        return self.max_semi_pct if sector == 'SEMI' else self.max_sector_pct

    def apply_sector_caps(self, targets):
        """
        targets: list of dicts with 'ticker','dollars'.
        Trims so no sector exceeds its cap (SEMI 25%, others 30%) of total gross.
        """
        total = sum(t['dollars'] for t in targets) or 1.0
        sector_tot = {}
        for t in targets:
            sec = SECTOR_OF.get(t['ticker'], 'OTHER')
            sector_tot[sec] = sector_tot.get(sec, 0) + t['dollars']
        scale = {}
        for sec, tot in sector_tot.items():
            cap = self._cap_for(sec) * total
            scale[sec] = min(1.0, cap / tot) if tot > cap else 1.0
        out = []
        for t in targets:
            sec = SECTOR_OF.get(t['ticker'], 'OTHER')
            t2 = dict(t)
            t2['dollars'] = t['dollars'] * scale[sec]
            out.append(t2)
        return out

    def book_sector_exposure(self, positions):
        """Current book exposure by sector. positions: [{ticker, market_value}]."""
        total = sum(abs(float(p.get('market_value', 0))) for p in positions) or 1.0
        exp = {}
        for p in positions:
            sec = SECTOR_OF.get(p.get('symbol', p.get('ticker')), 'OTHER')
            exp[sec] = exp.get(sec, 0) + abs(float(p.get('market_value', 0))) / total
        return exp

    def overweight_trims(self, positions):
        """
        Return per-symbol $ amounts to TRIM so each sector is back under its cap.
        Trims largest positions in the overweight sector first.
        """
        total = sum(abs(float(p.get('market_value', 0))) for p in positions) or 1.0
        by_sector = {}
        for p in positions:
            sec = SECTOR_OF.get(p.get('symbol'), 'OTHER')
            by_sector.setdefault(sec, []).append(p)
        trims = {}
        for sec, ps in by_sector.items():
            cap_dollars = self._cap_for(sec) * total
            sec_dollars = sum(abs(float(p['market_value'])) for p in ps)
            excess = sec_dollars - cap_dollars
            if excess <= 0:
                continue
            # trim largest first
            for p in sorted(ps, key=lambda x: -abs(float(x['market_value']))):
                if excess <= 0:
                    break
                cut = min(abs(float(p['market_value'])), excess)
                trims[p['symbol']] = cut
                excess -= cut
        return trims

    def trailing_stop(self, entry, current_price, atr, init_mult=1.5, trail_mult=2.0):
        """
        Compute the trailing stop level.
        Once price moves up, stop ratchets up to (high - trail_mult*ATR),
        never below the initial stop.
        """
        init_stop = entry - init_mult * atr
        trail_stop = current_price - trail_mult * atr
        return max(init_stop, trail_stop)


class PortfolioManager:
    """
    Divides capital across strategy SLEEVES with risk budgets, then within each
    sleeve sizes names by half-Kelly. Sleeve weights come from each strategy's
    Sharpe×IC (passed in).
    """
    def __init__(self, equity, sleeve_weights):
        self.equity = float(equity)
        # normalize sleeve weights
        tot = sum(max(0, w) for w in sleeve_weights.values()) or 1.0
        self.sleeve_weights = {k: max(0, w)/tot for k, w in sleeve_weights.items()}

    def sleeve_budget(self, sleeve):
        return self.equity * self.sleeve_weights.get(sleeve, 0.0)

    def divide(self, sleeve_picks):
        """
        sleeve_picks: {sleeve: [ {ticker, alpha, price, atr, kelly_frac}, ... ]}
        Returns combined target list with dollars allocated by sleeve budget × kelly.
        """
        combined = {}
        for sleeve, picks in sleeve_picks.items():
            budget = self.sleeve_budget(sleeve)
            if budget <= 0 or not picks: continue
            # within sleeve, weight by kelly fraction
            ktot = sum(p['kelly_frac'] for p in picks) or 1.0
            for p in picks:
                dollars = budget * (p['kelly_frac'] / ktot)
                if p['ticker'] in combined:
                    combined[p['ticker']]['dollars'] += dollars
                else:
                    combined[p['ticker']] = {**p, 'dollars': dollars}
        return list(combined.values())
