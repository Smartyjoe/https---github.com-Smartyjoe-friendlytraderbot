import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from bot.candle_builder import CandleBuilder
from bot.indicators.ema import ema_trend
from bot.indicators.rsi import rsi, rsi_signal
from bot.indicators.atr import atr, atr_filter
from bot.indicators.price_action import recent_breakout, rejection_wick
from bot.ai_confirmation import AIConfirmation

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    asset: str
    expiry_seconds: int
    direction: str
    confidence: float
    meta: Dict

class SignalEngine:
    """Aggregates indicators across multi-timeframe and gates signals via AI confirmation."""

    def __init__(self):
        self.ai = AIConfirmation()

    def _confirm_all(self, df_trade: pd.DataFrame, df_trend: pd.DataFrame) -> Optional[Dict]:
        if df_trade.empty or df_trend.empty or len(df_trade) < 60:
            return None
        close_trade = df_trade["close"]
        close_trend = df_trend["close"]

        ema_info = ema_trend(close_trend)
        rsi_series = rsi(close_trade, 14)
        rsi_info = rsi_signal(rsi_series)
        atr_series = atr(df_trade, 14)
        atr_info = atr_filter(atr_series, close_trade)
        breakout = recent_breakout(df_trade, lookback=20)
        reject = rejection_wick(df_trade, min_ratio=1.5)

        # Direction confluence
        directions = []
        # EMA trend gives directional bias
        directions.append("call" if ema_info["trend"] == "up" else "put")
        if rsi_info["direction"] != "none":
            directions.append(rsi_info["direction"])
        if breakout["break"] and breakout["direction"] != "none":
            directions.append(breakout["direction"])
        if reject["rejection"] and reject["direction"] != "none":
            directions.append(reject["direction"])

        if not atr_info["valid"]:
            return None

        call_votes = sum(1 for d in directions if d == "call")
        put_votes = sum(1 for d in directions if d == "put")

        if call_votes >= 3 and put_votes == 0:
            direction = "CALL"
        elif put_votes >= 3 and call_votes == 0:
            direction = "PUT"
        else:
            return None

        snapshot = {
            "current_price": float(close_trade.iloc[-1]),
            "last20": df_trade.iloc[-20:].to_dict(orient="list"),
            "ema_trend": ema_info["trend"],
            "ema_strength": float(ema_info["strength"]),
            "rsi": float(rsi_series.iloc[-1]),
            "atr_rel": float(atr_info["relative"]),
            "breakout": bool(breakout["break"]),
            "reject": bool(reject["rejection"]),
        }
        return {"direction": direction, "snapshot": snapshot}

    async def evaluate(self, asset: str, expiry_seconds: int, df_trade: pd.DataFrame, df_trend: pd.DataFrame, market_type: str) -> Optional[Signal]:
        """Evaluate indicator confluence; route through AI; return high-confidence signals only."""
        base = self._confirm_all(df_trade, df_trend)
        if not base:
            return None
        direction = base["direction"]
        snapshot = base["snapshot"]
        snapshot.update({
            "market_type": market_type,
            "asset": asset,
            "expiry_seconds": expiry_seconds,
        })
        ai_dir, conf = await self.ai.confirm(snapshot)
        if ai_dir != direction:
            return None
        if conf < 70.0:
            return None
        return Signal(asset=asset, expiry_seconds=expiry_seconds, direction=direction, confidence=conf, meta=snapshot)