import os
import asyncio
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

# Load environment variables
load_dotenv()

class TelegramTradingBot:
    def __init__(self):
        # Configuration
        self.ssid = os.getenv("POCKETOPTION_SSID")
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        self.initial_amount = 1.0
        self.amount = self.initial_amount
        
        # Trading state
        self.client = None
        self.client_initialized = False
        self.initialization_lock = asyncio.Lock()
        self.active_users = {}  # Store user-specific data {user_id: {symbol, candles, monitoring}}
        
        # Enhanced parameters
        self.min_candles = 50
        self.confidence_threshold = 70  # Minimum confidence to signal
        
        # Popular pairs for selection
        self.popular_pairs = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "EURJPY_otc", "USDCAD_otc", "USDCHF_otc", "NZDUSD_otc",
            "GBPJPY_otc", "AUDJPY_otc", "EURGBP_otc", "CHFJPY_otc",
            "EURCHF_otc", "GBPCHF_otc", "CADJPY_otc", "EURCAD_otc"
        ]

    def calculate_demarker(self, df, period=7):
        """Calculate DeMarker indicator"""
        high = df['high'].values
        low = df['low'].values
        
        demax = np.zeros(len(high))
        demin = np.zeros(len(low))
        
        for i in range(1, len(high)):
            demax[i] = max(0, high[i] - high[i-1])
            demin[i] = max(0, low[i-1] - low[i])
        
        demax_ma = pd.Series(demax).rolling(window=period, min_periods=period).mean()
        demin_ma = pd.Series(demin).rolling(window=period, min_periods=period).mean()
        
        demarker = demax_ma / (demax_ma + demin_ma + 1e-10)
        return demarker

    def calculate_rsi(self, df, period=14):
        """Calculate RSI for additional confirmation"""
        rsi = ta.momentum.RSIIndicator(close=df['close'], window=period).rsi()
        return rsi

    def calculate_bollinger_bands(self, df, period=20):
        """Calculate Bollinger Bands for volatility context"""
        bb = ta.volatility.BollingerBands(close=df['close'], window=period, window_dev=2)
        return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()

    def calculate_enhanced_strategy(self, df):
        """
        Enhanced multi-confirmation strategy with confidence scoring
        
        Indicators:
        1. Donchian Channels (6) - Trend
        2. DeMarker (7) - Momentum
        3. OSMA (13,27,10) - Trend strength
        4. RSI (14) - Overbought/Oversold confirmation
        5. Bollinger Bands (20) - Volatility context
        6. Volume analysis - Trade strength
        
        Returns: (signal, confidence, details)
        """
        try:
            # Primary Indicators
            donchian = ta.volatility.DonchianChannel(
                high=df['high'], low=df['low'], close=df['close'],
                window=6, fillna=False
            )
            dc_high = donchian.donchian_channel_hband()
            dc_low = donchian.donchian_channel_lband()
            dc_mid = (dc_high + dc_low) / 2
            
            demarker = self.calculate_demarker(df, period=7)
            
            macd = ta.trend.MACD(
                close=df['close'], window_slow=27, window_fast=13,
                window_sign=10, fillna=False
            )
            osma = macd.macd() - macd.macd_signal()
            
            # Confirmation Indicators
            rsi = self.calculate_rsi(df, period=14)
            bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(df, period=20)
            
            # Price action
            ema_9 = ta.trend.EMAIndicator(close=df['close'], window=9).ema_indicator()
            ema_21 = ta.trend.EMAIndicator(close=df['close'], window=21).ema_indicator()
            
            # Current values
            curr_close = df['close'].iloc[-1]
            curr_high = df['high'].iloc[-1]
            curr_low = df['low'].iloc[-1]
            prev_close = df['close'].iloc[-2]
            
            curr_dc_high = dc_high.iloc[-1]
            curr_dc_low = dc_low.iloc[-1]
            curr_dc_mid = dc_mid.iloc[-1]
            
            curr_demark = demarker.iloc[-1]
            curr_rsi = rsi.iloc[-1]
            
            curr_bb_upper = bb_upper.iloc[-1]
            curr_bb_lower = bb_lower.iloc[-1]
            curr_bb_mid = bb_mid.iloc[-1]
            
            curr_ema9 = ema_9.iloc[-1]
            curr_ema21 = ema_21.iloc[-1]
            
            # OSMA momentum
            curr_osma = osma.iloc[-1]
            prev_osma_1 = osma.iloc[-2]
            prev_osma_2 = osma.iloc[-3]
            
            # Scoring system
            call_score = 0
            put_score = 0
            max_score = 100
            details = []
            
            # === CALL (BUY) ANALYSIS ===
            
            # 1. Donchian Channel (25 points)
            tolerance = abs(curr_dc_high - curr_dc_low) * 0.01  # 1% tolerance
            if curr_close >= curr_dc_high - tolerance:
                call_score += 25
                details.append("✓ Price at upper Donchian band")
            elif curr_close > curr_dc_mid:
                call_score += 10
                details.append("◐ Price above Donchian midline")
            
            # 2. DeMarker (20 points)
            if curr_demark >= 0.7:
                call_score += 20
                details.append(f"✓ DeMarker overbought ({curr_demark:.2f})")
            elif curr_demark >= 0.6:
                call_score += 10
                details.append(f"◐ DeMarker elevated ({curr_demark:.2f})")
            
            # 3. OSMA Momentum (20 points)
            if curr_osma > prev_osma_1 > prev_osma_2 and curr_osma > 0:
                call_score += 20
                details.append("✓ OSMA strong uptrend")
            elif curr_osma > prev_osma_1:
                call_score += 10
                details.append("◐ OSMA rising")
            
            # 4. RSI Confirmation (15 points)
            if curr_rsi >= 70:
                call_score += 15
                details.append(f"✓ RSI overbought ({curr_rsi:.1f})")
            elif curr_rsi >= 60:
                call_score += 8
                details.append(f"◐ RSI bullish ({curr_rsi:.1f})")
            
            # 5. Bollinger Bands (10 points)
            if curr_close >= curr_bb_upper:
                call_score += 10
                details.append("✓ Price at upper BB")
            elif curr_close > curr_bb_mid:
                call_score += 5
            
            # 6. EMA Trend (10 points)
            if curr_ema9 > curr_ema21 and curr_close > curr_ema9:
                call_score += 10
                details.append("✓ EMA bullish alignment")
            
            # === PUT (SELL) ANALYSIS ===
            
            # 1. Donchian Channel (25 points)
            if curr_close <= curr_dc_low + tolerance:
                put_score += 25
                details.append("✓ Price at lower Donchian band")
            elif curr_close < curr_dc_mid:
                put_score += 10
                details.append("◐ Price below Donchian midline")
            
            # 2. DeMarker (20 points)
            if curr_demark <= 0.3:
                put_score += 20
                details.append(f"✓ DeMarker oversold ({curr_demark:.2f})")
            elif curr_demark <= 0.4:
                put_score += 10
                details.append(f"◐ DeMarker weak ({curr_demark:.2f})")
            
            # 3. OSMA Momentum (20 points)
            if curr_osma < prev_osma_1 < prev_osma_2 and curr_osma < 0:
                put_score += 20
                details.append("✓ OSMA strong downtrend")
            elif curr_osma < prev_osma_1:
                put_score += 10
                details.append("◐ OSMA falling")
            
            # 4. RSI Confirmation (15 points)
            if curr_rsi <= 30:
                put_score += 15
                details.append(f"✓ RSI oversold ({curr_rsi:.1f})")
            elif curr_rsi <= 40:
                put_score += 8
                details.append(f"◐ RSI bearish ({curr_rsi:.1f})")
            
            # 5. Bollinger Bands (10 points)
            if curr_close <= curr_bb_lower:
                put_score += 10
                details.append("✓ Price at lower BB")
            elif curr_close < curr_bb_mid:
                put_score += 5
            
            # 6. EMA Trend (10 points)
            if curr_ema9 < curr_ema21 and curr_close < curr_ema9:
                put_score += 10
                details.append("✓ EMA bearish alignment")
            
            # === DETERMINE SIGNAL ===
            if call_score >= self.confidence_threshold and call_score > put_score:
                return "CALL", call_score, details
            elif put_score >= self.confidence_threshold and put_score > call_score:
                return "PUT", put_score, details
            else:
                return "HOLD", max(call_score, put_score), [f"Insufficient confidence (CALL: {call_score}%, PUT: {put_score}%)"]
                
        except Exception as e:
            return "ERROR", 0, [f"Analysis error: {str(e)}"]

    async def initialize_client(self):
        """Initialize and wait for PocketOption client to be ready"""
        async with self.initialization_lock:
            if self.client_initialized:
                return True
            
            try:
                print("🔄 Initializing PocketOption client...")
                self.client = PocketOptionAsync(ssid=self.ssid)
                
                # Wait for client to initialize (give it time to connect)
                await asyncio.sleep(3)
                
                # Try to fetch balance to verify connection
                try:
                    balance = await self.client.balance()
                    print(f"✅ Client initialized. Balance: ${balance:.2f}")
                    self.client_initialized = True
                    return True
                except Exception as e:
                    print(f"⚠️ Balance check failed: {e}")
                    # Continue anyway, client might still work
                    self.client_initialized = True
                    return True
                    
            except Exception as e:
                print(f"❌ Client initialization error: {e}")
                return False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        # Initialize client on first use
        if not self.client_initialized:
            await update.message.reply_text(
                "🔄 *Initializing connection...*\n\n"
                "Please wait a moment...",
                parse_mode='Markdown'
            )
            
            success = await self.initialize_client()
            if not success:
                await update.message.reply_text(
                    "❌ *Connection Failed*\n\n"
                    "Please check your SSID and try again.",
                    parse_mode='Markdown'
                )
                return
        
        welcome_msg = (
            "🤖 *Welcome to Professional Trading Bot*\n\n"
            "📊 *Features:*\n"
            "• Multi-indicator analysis\n"
            "• 70%+ confidence signals\n"
            "• Real-time market monitoring\n"
            "• 92% payout asset selection\n\n"
            "🎯 *Strategy:*\n"
            "• Donchian Channels (Trend)\n"
            "• DeMarker (Momentum)\n"
            "• OSMA (Strength)\n"
            "• RSI (Confirmation)\n"
            "• Bollinger Bands (Volatility)\n\n"
            "⏱ *Timeframe:* 10s candles\n"
            "💰 *Expiry:* 60 seconds\n\n"
            "Use /select to choose asset and start monitoring!"
        )
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def select_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /select command - show asset selection"""
        try:
            # Initialize client if needed
            if not self.client_initialized:
                await update.message.reply_text(
                    "🔄 *Initializing connection...*\n\n"
                    "This may take a few seconds...",
                    parse_mode='Markdown'
                )
                
                success = await self.initialize_client()
                if not success:
                    await update.message.reply_text(
                        "❌ *Connection Failed*\n\n"
                        "Please try /start first or check your credentials.",
                        parse_mode='Markdown'
                    )
                    return
            
            await update.message.reply_text(
                "📡 *Fetching live payouts...*\n\n"
                "Please wait...",
                parse_mode='Markdown'
            )
            
            # Fetch live payouts with retry
            all_payouts = None
            for attempt in range(3):
                try:
                    all_payouts = await self.client.payout()
                    if all_payouts:
                        break
                    await asyncio.sleep(2)
                except Exception as e:
                    if attempt == 2:
                        raise e
                    await asyncio.sleep(2)
            
            if not all_payouts:
                # Fallback to manual selection
                await self.show_fallback_selection(update)
                return
            
            # Filter for 92% payout popular pairs
            valid_pairs = []
            for pair in self.popular_pairs:
                payout_value = all_payouts.get(pair)
                if payout_value:
                    try:
                        payout_int = int(float(payout_value))
                        if payout_int >= 90:  # 90%+ payout
                            valid_pairs.append((pair, payout_int))
                    except (ValueError, TypeError):
                        continue
            
            # If no valid pairs found, try all assets
            if not valid_pairs:
                for pair, payout_value in all_payouts.items():
                    try:
                        payout_int = int(float(payout_value))
                        if payout_int >= 85:  # Lower threshold
                            valid_pairs.append((pair, payout_int))
                    except (ValueError, TypeError):
                        continue
            
            if not valid_pairs:
                await self.show_fallback_selection(update)
                return
            
            # Sort by payout (highest first)
            valid_pairs.sort(key=lambda x: x[1], reverse=True)
            
            # Create inline keyboard (2 columns)
            keyboard = []
            for i in range(0, len(valid_pairs[:16]), 2):
                row = []
                for j in range(2):
                    if i + j < len(valid_pairs):
                        pair, payout = valid_pairs[i + j]
                        # Clean display name
                        display_name = pair.replace("_otc", "").replace("_", "/")
                        row.append(
                            InlineKeyboardButton(
                                f"{display_name} ({payout}%)",
                                callback_data=f"select_{pair}"
                            )
                        )
                keyboard.append(row)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎯 *Select Trading Asset*\n\n"
                "Choose a currency pair with high payout:\n"
                f"(Showing {len(valid_pairs[:16])} assets)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error fetching assets: {str(e)}\n\n"
                "Showing fallback options..."
            )
            await self.show_fallback_selection(update)
    
    async def show_fallback_selection(self, update: Update):
        """Show fallback asset selection when API fails"""
        keyboard = []
        fallback_pairs = [
            ("EURUSD_otc", "EUR/USD"), ("GBPUSD_otc", "GBP/USD"),
            ("USDJPY_otc", "USD/JPY"), ("AUDUSD_otc", "AUD/USD"),
            ("EURJPY_otc", "EUR/JPY"), ("USDCAD_otc", "USD/CAD"),
            ("USDCHF_otc", "USD/CHF"), ("NZDUSD_otc", "NZD/USD"),
            ("GBPJPY_otc", "GBP/JPY"), ("AUDJPY_otc", "AUD/JPY")
        ]
        
        for i in range(0, len(fallback_pairs), 2):
            row = []
            for j in range(2):
                if i + j < len(fallback_pairs):
                    pair, display = fallback_pairs[i + j]
                    row.append(
                        InlineKeyboardButton(display, callback_data=f"select_{pair}")
                    )
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 *Select Trading Asset*\n\n"
            "Choose a currency pair:\n"
            "(Popular major pairs)",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_asset_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle asset selection from inline keyboard"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        selected_asset = query.data.replace("select_", "")
        
        # Initialize user data
        self.active_users[user_id] = {
            'symbol': selected_asset,
            'candles': [],
            'monitoring': True,
            'last_signal_time': None
        }
        
        display_name = selected_asset.replace("_otc", "").replace("_", "/").upper()
        
        await query.edit_message_text(
            f"✅ *Asset Selected: {display_name}*\n\n"
            f"📊 Initializing analysis...\n"
            f"⏳ Collecting candles...\n\n"
            f"You'll receive signals when confidence ≥ 70%\n\n"
            f"Use /stop to pause monitoring",
            parse_mode='Markdown'
        )
        
        # Start monitoring in background
        asyncio.create_task(self.monitor_asset(user_id, context))

    async def monitor_asset(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Monitor asset and send signals to user"""
        try:
            user_data = self.active_users.get(user_id)
            if not user_data:
                return
            
            symbol = user_data['symbol']
            
            # Load historical candles
            historical = await self.client.get_candles(
                asset=symbol, period=10, offset=100
            )
            
            if historical:
                user_data['candles'] = list(historical)
            
            # Subscribe to live updates
            stream = await self.client.subscribe_symbol_timed(
                symbol, timedelta(seconds=10)
            )
            
            candle_count = 0
            async for candle in stream:
                # Check if user stopped monitoring
                if user_id not in self.active_users or not self.active_users[user_id]['monitoring']:
                    break
                
                user_data['candles'].append(candle)
                candle_count += 1
                
                # Maintain rolling window
                if len(user_data['candles']) > 150:
                    user_data['candles'] = user_data['candles'][-150:]
                
                # Wait for minimum candles
                if len(user_data['candles']) < self.min_candles:
                    if candle_count == 10:
                        remaining = self.min_candles - len(user_data['candles'])
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"📊 Collecting data: {len(user_data['candles'])}/{self.min_candles} candles\n"
                                 f"⏳ Need {remaining} more (~{remaining * 10}s)"
                        )
                    continue
                
                # Analyze every 5 candles to reduce spam
                if candle_count % 5 != 0:
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(user_data['candles'])
                
                if df.empty or 'close' not in df.columns:
                    continue
                
                # Calculate signal
                signal, confidence, details = self.calculate_enhanced_strategy(df)
                
                # Send signal if valid
                if signal != "HOLD" and signal != "ERROR":
                    # Cooldown check (60 seconds between signals)
                    last_signal = user_data.get('last_signal_time')
                    if last_signal:
                        elapsed = (datetime.now() - last_signal).total_seconds()
                        if elapsed < 60:
                            continue
                    
                    user_data['last_signal_time'] = datetime.now()
                    
                    # Format signal message
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    display_name = symbol.replace("_otc", "").replace("_", "/").upper()
                    
                    signal_msg = (
                        f"🎯 *TRADE SIGNAL*\n\n"
                        f"📊 *Asset:* {display_name}\n"
                        f"{'🟢' if signal == 'CALL' else '🔴'} *Signal:* {signal}\n"
                        f"💯 *Confidence:* {confidence}%\n"
                        f"⏰ *Entry:* {entry_time}\n"
                        f"⏱ *Expiry:* 1 min (60s)\n\n"
                        f"*Analysis:*\n"
                    )
                    
                    for detail in details[:5]:  # Top 5 reasons
                        signal_msg += f"• {detail}\n"
                    
                    signal_msg += f"\n_Next signal in 60+ seconds_"
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=signal_msg,
                        parse_mode='Markdown'
                    )
                
        except Exception as e:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Monitoring error: {str(e)}\n\nUse /select to restart"
            )

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        user_id = update.effective_user.id
        
        if user_id in self.active_users:
            self.active_users[user_id]['monitoring'] = False
            await update.message.reply_text(
                "⏸ *Monitoring Stopped*\n\n"
                "Use /select to start again",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ No active monitoring\n\n"
                "Use /select to start",
                parse_mode='Markdown'
            )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        if user_id in self.active_users and self.active_users[user_id]['monitoring']:
            user_data = self.active_users[user_id]
            symbol = user_data['symbol']
            candles = len(user_data['candles'])
            
            display_name = symbol.replace("_otc", "").replace("_", "/").upper()
            
            await update.message.reply_text(
                f"📊 *Bot Status: Active*\n\n"
                f"🎯 *Asset:* {display_name}\n"
                f"📈 *Candles:* {candles}\n"
                f"💯 *Confidence Threshold:* {self.confidence_threshold}%\n\n"
                f"_Monitoring for high-probability setups..._",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ *Bot Status: Idle*\n\n"
                "Use /select to start monitoring",
                parse_mode='Markdown'
            )

    def run(self):
        """Run the Telegram bot"""
        if not self.telegram_token:
            print("❌ Error: TELEGRAM_TOKEN not found in .env file")
            return
        
        if not self.ssid:
            print("❌ Error: POCKETOPTION_SSID not found in .env file")
            return
        
        # Create application
        app = Application.builder().token(self.telegram_token).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("select", self.select_command))
        app.add_handler(CommandHandler("stop", self.stop_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CallbackQueryHandler(self.handle_asset_selection, pattern="^select_"))
        
        print("🚀 Telegram Trading Bot Started!")
        print("📱 Send /start to your bot to begin")
        print("⏹  Press Ctrl+C to stop\n")
        
        # Run bot
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = TelegramTradingBot()
    bot.run()