import pandas as pd
from typing import List, Dict, Any
from pocketoptionapi_async.models import Candle

class CandleBuilder:
    """Utility to convert PocketOption candles to pandas DataFrame and build multi-timeframe views."""

    @staticmethod
    def to_dataframe(candles: List[Candle]) -> pd.DataFrame:
        records = [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "asset": c.asset,
            }
            for c in candles
        ]
        df = pd.DataFrame.from_records(records)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df

    @staticmethod
    def last_n(df: pd.DataFrame, n: int) -> pd.DataFrame:
        if df.empty:
            return df
        return df.iloc[-n:].copy()

    @staticmethod
    def aggregate_timeframe(df: pd.DataFrame, seconds: int) -> pd.DataFrame:
        if df.empty:
            return df
        # Ensure integer timestamp and sorted
        df2 = df.copy()
        df2.sort_values("timestamp", inplace=True)
        bucket = (df2["timestamp"] // seconds) * seconds
        df2["bucket"] = bucket
        agg = df2.groupby("bucket").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        ).reset_index().rename(columns={"bucket": "timestamp"})
        return agg