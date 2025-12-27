import pandas as pd

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=period).mean()

def atr_filter(atr_series: pd.Series, close: pd.Series) -> dict:
    val = atr_series.iloc[-1]
    rel = val / (close.iloc[-1] + 1e-9)  # relative ATR
    ok = 0.0005 < rel < 0.02  # reject too low/high volatility
    return {"atr": val, "relative": rel, "valid": ok}