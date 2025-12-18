import pandas as pd

# Simple structure rules: recent high/low break and rejection wick logic

def recent_breakout(df: pd.DataFrame, lookback: int = 10) -> dict:
    if df.empty or len(df) < lookback + 1:
        return {"break": False, "direction": "none"}
    recent = df.iloc[-lookback - 1 : -1]
    last = df.iloc[-1]
    high_break = last["close"] > recent["high"].max() and last["close"] > last["open"]
    low_break = last["close"] < recent["low"].min() and last["close"] < last["open"]
    direction = "call" if high_break else ("put" if low_break else "none")
    return {"break": high_break or low_break, "direction": direction}

def rejection_wick(df: pd.DataFrame, min_ratio: float = 1.5) -> dict:
    if df.empty:
        return {"rejection": False, "direction": "none"}
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"]) + 1e-9
    upper_wick = last["high"] - max(last["close"], last["open"]) + 1e-9
    lower_wick = min(last["close"], last["open"]) - last["low"] + 1e-9
    # Rejection if wick >= min_ratio * body
    bull_reject = lower_wick / body >= min_ratio and last["close"] > last["open"]
    bear_reject = upper_wick / body >= min_ratio and last["close"] < last["open"]
    direction = "call" if bull_reject else ("put" if bear_reject else "none")
    return {"rejection": bull_reject or bear_reject, "direction": direction}