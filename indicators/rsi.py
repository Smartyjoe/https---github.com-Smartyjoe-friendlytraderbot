import pandas as pd

# Standard RSI(14)
def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def rsi_signal(rsi_series: pd.Series) -> dict:
    r = rsi_series.iloc[-1]
    direction = "call" if r > 50 and r > rsi_series.iloc[-2] else ("put" if r < 50 and r < rsi_series.iloc[-2] else "none")
    return {"rsi": r, "direction": direction}