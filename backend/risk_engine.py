"""
RISK ENGINE
- ATR-based volatility sizing
- Portfolio heat cap
- Per-position cap
- Liquidity filter (5d ADV)
- Spread / penny / volatility rejection
- Cooldown per ticker (no over-trading)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import time


@dataclass
class RiskConfig:
    target_risk_usd: float = 500.0
    max_position_usd: float = 15_000.0
    max_portfolio_heat_usd: float = 100_000.0
    min_price: float = 5.0
    max_realized_vol: float = 0.10        # daily
    min_adv_usd: float = 5_000_000.0
    cooldown_seconds: int = 60 * 30       # 30 minutes between same-ticker trades


class RiskEngine:
    def __init__(self, cfg: RiskConfig | None = None):
        self.cfg = cfg or RiskConfig()
        self._last_trade_ts: Dict[str, float] = {}
        self.current_heat: float = 0.0

    def reset_heat(self):
        self.current_heat = 0.0

    def can_size(self, ticker: str, price: float, atr: float, realized_vol: float,
                 adv_usd: float) -> Optional[str]:
        """Return rejection reason string, or None if eligible."""
        if price < self.cfg.min_price:
            return "price_below_floor"
        if realized_vol > self.cfg.max_realized_vol:
            return "vol_above_ceiling"
        if adv_usd < self.cfg.min_adv_usd:
            return "insufficient_liquidity"
        if atr <= 0:
            return "atr_invalid"
        last = self._last_trade_ts.get(ticker)
        if last and (time.time() - last) < self.cfg.cooldown_seconds:
            return "cooldown_active"
        return None

    def size_position(self, price: float, atr: float) -> Dict:
        shares = self.cfg.target_risk_usd / atr
        capital = shares * price
        if capital > self.cfg.max_position_usd:
            shares = self.cfg.max_position_usd / price
            capital = self.cfg.max_position_usd
        return {"shares": shares, "capital": capital}

    def admit(self, ticker: str, capital: float) -> bool:
        """Charge against portfolio heat. Returns False if cap exceeded."""
        if self.current_heat + capital > self.cfg.max_portfolio_heat_usd:
            return False
        self.current_heat += capital
        self._last_trade_ts[ticker] = time.time()
        return True
