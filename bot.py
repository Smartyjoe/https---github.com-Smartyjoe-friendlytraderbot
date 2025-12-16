import os
import pytz
import cv2
import pandas as pd
import pandas_ta as ta
import pytesseract
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# --- CONFIGURATION ---
TOKEN = "YOUR_TELEGRAM_TOKEN"
DEEPSEEK_KEY = "YOUR_DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL = "https://api.nexagi.com/v1" # Example for Nex AGI
NY_TZ = pytz.timezone('America/New_York')

# Initialize DeepSeek Client
ai_client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE_URL)

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- UTILS: TIME GUARD ---
def get_market_status():
    now_ny = datetime.now(NY_TZ)
    is_weekend = now_ny.weekday() >= 5
    is_low_volume = now_ny.hour < 9 or now_ny.hour > 17
    
    if is_weekend: return False, "Weekend - Market Closed"
    if is_low_volume: return False, f"Low Volume Hour ({now_ny.strftime('%H:%M')} EST)"
    return True, "Active"

# --- ENGINE: INDICATOR SCORING ---
def calculate_signals(df):
    """Checks 4 indicators: EMA50, RSI, BBands, ADX"""
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    bbands = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)
    adx = ta.adx(df['High'], df['Low'], df['Close'])
    df = pd.concat([df, adx], axis=1)
    
    latest = df.iloc[-1]
    score = 0
    # Logic for CALL
    if latest['Close'] > latest['EMA_50']: score += 25
    if latest['RSI'] < 35: score += 25
    if latest['Close'] <= latest['BBL_20_2.0']: score += 25
    if latest['ADX_14'] > 25: score += 25
    
    return score

# --- ENGINE: AI ANALYSIS ---
async def ai_analyze(data_text):
    prompt = f"Analyze these trading indicators for a 1-minute binary option trade: {data_text}. Verify the 4-indicator strategy. Provide: Action (CALL/PUT/HOLD), Confidence (%), and Reason."
    response = ai_client.chat.completions.create(
        model="deepseek-v3.1-nex-n1",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Real Market", callback_data='market_real')],
        [InlineKeyboardButton(" OTC Market (Screenshot)", callback_data='market_otc')]
    ]
    await update.message.reply_text("Welcome Coding Partner Bot! Select Market:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    is_safe, reason = get_market_status()
    if not is_safe:
        keyboard = [[InlineKeyboardButton("✅ Ignore & Continue", callback_data=f"ignore_{query.data}"),
                     InlineKeyboardButton("🔙 Menu", callback_data='start_over')]]
        await query.edit_message_text(f"⚠️ Warning: {reason}. Trade at your own risk.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if query.data == 'market_otc':
        await query.edit_message_text("Please upload a clear screenshot of your OTC chart.")

async def process_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📥 Downloading and analyzing screenshot...")
    photo_file = await update.message.photo[-1].get_file()
    path = f"temp_{update.message.chat_id}.jpg"
    await photo_file.download_to_drive(path)

    # Simple OCR extraction
    image = cv2.imread(path)
    text = pytesseract.image_to_string(image)
    
    # Send to DeepSeek for analysis
    analysis = await ai_analyze(text if text else "Visual chart pattern")
    await msg.edit_text(f"🚀 **SIGNAL REPORT**\n\n{analysis}", parse_mode='Markdown')
    os.remove(path)

# --- MAIN ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern='^market_'))
    app.add_handler(MessageHandler(filters.PHOTO, process_image))
    print("Bot is running...")
    app.run_polling()