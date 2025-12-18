import numpy as np
import pandas as pd

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def ema_trend(close: pd.Series) -> dict:
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    trend = "up" if ema50.iloc[-1] > ema200.iloc[-1] else "down"
    strength = abs(ema50.iloc[-1] - ema200.iloc[-1]) / (ema200.iloc[-1] + 1e-9)
    return {"ema50": ema50, "ema200": ema200, "trend": trend, "strength": strength}