from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
import pandas as pd
import ta
import asyncio
from datetime import timedelta

class PocketOptionBot:
    def __init__(self):                     
        self.amount = 1
        self.symbol = "EURUSD_otc"
        self.martingale_steps = 3

    def calculate_indicators(self, df):
        fast_sma = ta.trend.SMAIndicator(df['close'], window=5).sma_indicator()
        slow_sma = ta.trend.SMAIndicator(df['close'], window=10).sma_indicator()

        if fast_sma.iloc[-1] > slow_sma.iloc[-1]:
            return "CALL"
        elif fast_sma.iloc[-1] < slow_sma.iloc[-1]:
            return "PUT"
        return "HOLD"
    async def main_bot(self, ssid):
        try:

            client = PocketOptionAsync(ssid=ssid)
            await asyncio.sleep(5)

            stream = await client.subscribe_symbol_timed("EURUSD_otc", timedelta(seconds=2)) # Returns a candle obtained from combining candles that are inside a specific time range

            candles_list = []  # Store candles for DataFrame creation
            
            # This should run forever so you will need to force close the program
            async for candle in stream:
                print(f"Candle: {candle}") # Each candle is in format of a dictionary
                candles_list.append(candle)
                
                # Need at least 20 candles for the slow SMA calculation
                if len(candles_list) < 20:
                    continue
                    
                # Keep only the last 50 candles to avoid memory issues
                if len(candles_list) > 50:
                    candles_list = candles_list[-50:]
                
                candles_pd = pd.DataFrame(candles_list)
                signal = self.calculate_indicators(candles_pd)
                if signal == "CALL":
                    print("Placing CALL order")
                    (buy_id, _) = await client.buy(asset=self.symbol, amount=self.amount, time=5, check_win=False)
                    buy_data = await client.check_win(buy_id)
                    print(f"Order result: {buy_data['result']}")
                    if buy_data['result'] == 'loss':
                        self.amount = self.amount * 2
                elif signal == "PUT":
                    print("Placing PUT order")
                    (buy_id, _) = await client.sell(asset=self.symbol, amount=self.amount, time=5, check_win=False)
                    buy_data = await client.check_win(buy_id)
                    print(f"Order result: {buy_data['result']}")
                    if buy_data['result'] == 'loss':
                        self.amount = self.amount * 2
        except KeyboardInterrupt:
            print("Bot stopped by user.")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    bot = PocketOptionBot()
    asyncio.run(bot.main_bot(ssid))