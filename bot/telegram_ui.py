import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

from bot.config import load_settings
from bot.market_stream import MarketStream
from bot.candle_builder import CandleBuilder
from bot.signal_engine import SignalEngine

logger = logging.getLogger(__name__)

# Conversation states
MARKET_TYPE, ASSET_CLASS, ASSET_SELECTION, EXPIRY_SELECTION = range(4)

REAL_ASSETS_FOREX = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","EURGBP","EURJPY","GBPJPY","NZDUSD"
]
OTC_ASSETS_FOREX = [
    "EURUSD OTC","GBPUSD OTC","USDJPY OTC","AUDUSD OTC","USDCAD OTC","USDCHF OTC","EURGBP OTC","EURJPY OTC","GBPJPY OTC","NZDUSD OTC"
]
CRYPTO_ASSETS = [
    "BTCUSD","ETHUSD","BNBUSD","SOLUSD","XRPUSD","ADAUSD","DOGEUSD","LTCUSD","DOTUSD","AVAXUSD"
]

EXPIRIES_SECONDS = {
    "5 seconds": 5,
    "15 seconds": 15,
    "30 seconds": 30,
    "1 minute": 60,
    "2 minutes": 120,
    "3 minutes": 180,
    "5 minutes": 300,
}


def higher_timeframe_seconds(s: int) -> int:
    if s <= 5:
        return 15
    if s <= 15:
        return 30
    if s <= 30:
        return 60
    if s <= 60:
        return 300
    if s <= 120:
        return 300
    if s <= 180:
        return 300
    return 900


def symbol_to_pocket_option(symbol: str) -> str:
    # Simple mapping; adjust if API expects specific codes for OTC
    return symbol


@dataclass
class RuntimeSession:
    market_type: str
    asset_class: str
    asset: str
    expiry_seconds: int
    stream: Optional[MarketStream] = None
    engine: Optional[SignalEngine] = None
    task: Optional[asyncio.Task] = None
    df_trade: pd.DataFrame = pd.DataFrame()


def format_signal_telegram(sig) -> str:
    lines = [
        "\ud83d\udcca POCKET OPTION SIGNAL",
        f"Market: {sig.meta.get('market_type')}",
        f"Asset: {sig.asset}",
        f"Expiry: {int(sig.expiry_seconds/60) if sig.expiry_seconds>=60 else sig.expiry_seconds} {'MIN' if sig.expiry_seconds>=60 else 'SEC'}",
        f"Direction: {'\ud83d\udcc8 CALL' if sig.direction=='CALL' else '\ud83d\udcc9 PUT'}",
        f"Confidence: {int(sig.confidence)}%",
        "",
        "Strategy Confluence:",
        "\u2714 EMA Trend",
        "\u2714 RSI Momentum",
        "\u2714 ATR Volatility",
        "\u2714 Price Action Breakout",
        "\u2714 AI Confirmation",
        "",
        f"\u23f0 Signal Time: {pd.Timestamp.utcnow().strftime('%H:%M:%S')} UTC",
    ]
    return "\n".join(lines)


class TelegramUI:
    def __init__(self, application: Application):
        self.app = application
        self.settings = load_settings()

    def setup(self):
        conv = ConversationHandler(
            entry_points=[CommandHandler("start", self.cmd_start)],
            states={
                MARKET_TYPE: [CallbackQueryHandler(self.choose_market_type)],
                ASSET_CLASS: [CallbackQueryHandler(self.choose_asset_class)],
                ASSET_SELECTION: [CallbackQueryHandler(self.choose_asset)],
                EXPIRY_SELECTION: [CallbackQueryHandler(self.choose_expiry)],
            },
            fallbacks=[CommandHandler("stop", self.cmd_stop)],
        )
        self.app.add_handler(conv)
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("status", self.cmd_status))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\ud83d\udcc8 Real Market", callback_data="REAL")],
            [InlineKeyboardButton("\ud83c\udf19 OTC Market", callback_data="OTC")],
        ])
        await update.message.reply_text("STEP 1 – Market Type", reply_markup=kb)
        return MARKET_TYPE

    async def choose_market_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        market_type = q.data
        context.user_data["market_type"] = market_type
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\ud83d\udcb1 Forex", callback_data="Forex")],
            [InlineKeyboardButton("\u20bf Crypto", callback_data="Crypto")],
        ])
        await q.edit_message_text("STEP 2 – Asset Class", reply_markup=kb)
        return ASSET_CLASS

    async def choose_asset_class(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        asset_class = q.data
        context.user_data["asset_class"] = asset_class
        market_type = context.user_data.get("market_type", "REAL")
        if asset_class == "Forex":
            assets = REAL_ASSETS_FOREX if market_type == "REAL" else OTC_ASSETS_FOREX
        else:
            assets = CRYPTO_ASSETS
        rows = [[InlineKeyboardButton(a, callback_data=a)] for a in assets]
        kb = InlineKeyboardMarkup(rows)
        await q.edit_message_text("STEP 3 – Asset Selection", reply_markup=kb)
        return ASSET_SELECTION

    async def choose_asset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        asset = q.data
        context.user_data["asset"] = asset
        rows = [[InlineKeyboardButton(k, callback_data=str(v))] for k, v in EXPIRIES_SECONDS.items()]
        kb = InlineKeyboardMarkup(rows)
        await q.edit_message_text("STEP 4 – Expiry Selection", reply_markup=kb)
        return EXPIRY_SELECTION

    async def choose_expiry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        expiry_seconds = int(q.data)
        context.user_data["expiry_seconds"] = expiry_seconds
        market_type = context.user_data.get("market_type", "REAL")
        asset = context.user_data.get("asset")

        # Start session
        session = RuntimeSession(
            market_type=market_type,
            asset_class=context.user_data.get("asset_class","Forex"),
            asset=asset,
            expiry_seconds=expiry_seconds,
            stream=MarketStream(asset=symbol_to_pocket_option(asset), timeframe_seconds=expiry_seconds),
            engine=SignalEngine(),
        )
        context.user_data["session"] = session
        await q.edit_message_text(f"Streaming {asset} ({market_type}) @ {expiry_seconds}s. Generating signals only when all strategies agree.")
        session.task = asyncio.create_task(self._run_stream_loop(update.effective_chat.id, context))
        return ConversationHandler.END

    async def _run_stream_loop(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        session: RuntimeSession = context.user_data.get("session")
        if not session:
            return
        assert session.stream and session.engine
        # Candle callback to keep DF updated and evaluate
        def candle_cb(candles):
            df = CandleBuilder.to_dataframe(candles)
            session.df_trade = CandleBuilder.last_n(df, 300)
        session.stream.add_candle_callback(candle_cb)

        async def stream_cb(data: Dict):
            # Evaluate on stream updates if we have enough candles
            if session.df_trade is None or session.df_trade.empty:
                return
            confirm_sec = higher_timeframe_seconds(session.expiry_seconds)
            df_trend = CandleBuilder.aggregate_timeframe(session.df_trade, confirm_sec)
            sig = await session.engine.evaluate(
                asset=session.asset,
                expiry_seconds=session.expiry_seconds,
                df_trade=session.df_trade,
                df_trend=df_trend,
                market_type=session.market_type,
            )
            if sig:
                text = format_signal_telegram(sig)
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                except Exception:
                    logger.exception("Failed to send signal message")
        session.stream.add_stream_callback(stream_cb)

        try:
            await session.stream.run()
        except Exception:
            logger.exception("Stream loop crashed")

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        session: RuntimeSession = context.user_data.get("session")
        if session and session.task:
            session.task.cancel()
            try:
                await session.stream.disconnect()  # type: ignore
            except Exception:
                pass
            await update.message.reply_text("Stopped streaming.")
        else:
            await update.message.reply_text("No active session.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        session: RuntimeSession = context.user_data.get("session")
        if not session:
            await update.message.reply_text("Idle. Use /start to begin.")
            return
        count = 0 if session.df_trade is None else len(session.df_trade)
        await update.message.reply_text(
            f"Session: {session.asset} {session.market_type} @ {session.expiry_seconds}s | candles={count}"
        )