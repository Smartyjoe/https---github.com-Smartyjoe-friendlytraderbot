import os
import pytz
import cv2
import pandas as pd
import pandas_ta as ta
import pytesseract
import logging
import platform
import http.server
import socketserver
import threading
import yfinance as yf
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv


def run_dummy_server():
    """Starts a tiny web server to satisfy Render's port check."""
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"📡 Dummy server listening on port {port}")
        httpd.serve_forever()

# --- 1. CONFIGURATION & SECURITY ---
load_dotenv()  # Load variables from .env file for local testing

# Get tokens from environment variables (Render/Local)
TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.nexagi.com/v1" 
NY_TZ = pytz.timezone('America/New_York')

# Critical Check: Ensure tokens exist before starting
if not TOKEN or not DEEPSEEK_KEY:
    print("❌ ERROR: TELEGRAM_TOKEN or DEEPSEEK_API_KEY is missing!")
    exit(1)

# --- 2. TESSERACT SYSTEM CONFIG ---
if platform.system() == "Windows":
    # Update this path if you installed Tesseract elsewhere
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    # Standard Linux path for Render/Cloud servers
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# Initialize DeepSeek Client
ai_client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE_URL)

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 3. UTILS: TIME GUARD ---
def get_market_status():
    now_ny = datetime.now(NY_TZ)
    is_weekend = now_ny.weekday() >= 5
    # Pocket Option OTC often runs on weekends, but Real Markets close.
    # Adjust this logic if you want to allow OTC on weekends.
    is_low_volume = now_ny.hour < 9 or now_ny.hour > 17
    
    if is_weekend: return False, "Weekend - Real Market Closed"
    if is_low_volume: return False, f"Low Volume Hour ({now_ny.strftime('%H:%M')} EST)"
    return True, "Active"

# --- 4. ENGINE: INDICATOR SCORING ---
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
    # Logic for CALL (Buy)
    if latest['Close'] > latest['EMA_50']: score += 25
    if latest['RSI'] < 35: score += 25
    if latest['Close'] <= latest['BBL_20_2.0']: score += 25
    if latest['ADX_14'] > 25: score += 25
    
    return score

# --- 5. ENGINE: AI ANALYSIS ---
async def ai_analyze(data_text):
    try:
        prompt = (
            f"Act as a Senior Technical Analyst. Analyze this market data: {data_text}.\n\n"
            "TASKS:\n"
            "1. Identify immediate Support and Resistance levels.\n"
            "2. Analyze price action relative to the 4-indicator strategy (EMA50, RSI, BBands, ADX).\n"
            "3. Determine if the trend is Overextended or Healthy.\n\n"
            "RESPONSE FORMAT:\n"
            "🚀 **SIGNAL**: [CALL/PUT/HOLD]\n"
            "🎯 **CONFIDENCE**: [X%]\n"
            "📉 **LEVELS**: Support at X, Resistance at Y\n"
            "📝 **REASON**: [Short technical explanation]"
        )
        response = ai_client.chat.completions.create(
            model="deepseek-v3.1-nex-n1",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Analysis Error: {str(e)}"
    
# --- 6. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Real Market", callback_data='market_real')],
        [InlineKeyboardButton("⚠️ OTC Market (Screenshot)", callback_data='market_otc')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚀 **Coding Partner Trading Bot**\n\nPlease select the market type you wish to analyze:", 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

def get_real_market_data(ticker_symbol):
    try:
        # Fetch last 100 periods of 5-minute data
        data = yf.download(ticker_symbol, period="1d", interval="5m", progress=False)
        if data.empty:
            return None
        
        # Format for AI Analysis
        # We take the last few rows to show the trend
        latest_data = data.tail(10).to_string()
        return latest_data
    except Exception as e:
        print(f"Error fetching YFinance data: {e}")
        return None

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data.replace('ignore_', '')

    if action == 'market_otc':
        await query.edit_message_text("📸 **OTC MODE**: Please upload a chart screenshot now.")
    
    elif action == 'market_real':
        # Instead of the error message, ask for a ticker
        await query.edit_message_text(
            "📊 **REAL MARKET MODE**\n\nPlease type the **Ticker Symbol** you want to analyze.\n"
            "Examples:\n"
            "• `EURUSD=X` (Forex)\n"
            "• `AAPL` (Apple Stock)\n"
            "• `BTC-USD` (Bitcoin)"
        )
        # Set a temporary state so the bot knows the next text message is a ticker
        context.user_data['expecting_ticker'] = True
    query = update.callback_query
    await query.answer()
    
    # Check Time Guard
    is_safe, reason = get_market_status()
    
    # Allow bypass if they clicked "Ignore"
    if not is_safe and not query.data.startswith('ignore_'):
        keyboard = [
            [InlineKeyboardButton("✅ Ignore & Continue", callback_data=f"ignore_{query.data}")],
            [InlineKeyboardButton("🔙 Menu", callback_data='start_over')]
        ]
        await query.edit_message_text(
            f"⚠️ **TRADING WARNING**\n\nReason: {reason}\nMarket conditions are currently high-risk.", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    # Clean the data if it was an "ignore" click
    action = query.data.replace('ignore_', '')

    if action == 'market_otc':
        await query.edit_message_text("📸 **OTC MODE**: Please upload a clear screenshot of your Pocket Option chart now.")
    elif action == 'market_real':
        await query.edit_message_text("📊 **REAL MARKET**: Automatic scanning is currently being integrated with Yahoo Finance API. Please use the OTC Screenshot method for now.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('expecting_ticker'):
        ticker = update.message.text.upper()
        msg = await update.message.reply_text(f"🔍 Fetching live data for {ticker}...")
        
        raw_data = get_real_market_data(ticker)
        if raw_data:
            analysis = await ai_analyze(raw_data)
            await msg.edit_text(f"📊 **SFT REAL MARKET REPORT: {ticker}**\n\n{analysis}", parse_mode='Markdown')
        else:
            await msg.edit_text(f"❌ Could not find data for `{ticker}`. Please check the symbol and try again.")
        
        context.user_data['expecting_ticker'] = False

async def process_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📥 Downloading image and performing Vision Analysis...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        os.makedirs("temp", exist_ok=True)
        path = f"temp/chart_{update.message.chat_id}.jpg"
        await photo_file.download_to_drive(path)

        # 1. OCR Extraction (Vision)
        image = cv2.imread(path)
        # Convert to grayscale to improve OCR accuracy
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)
        
        # 2. AI Logic
        analysis = await ai_analyze(text if text.strip() else "Visual chart pattern - Price Action analysis required.")
        
        await msg.edit_text(f"📊 **AI SIGNAL REPORT**\n\n{analysis}", parse_mode='Markdown')
        
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
            
    except Exception as e:
        await msg.edit_text(f"🚨 **Processing Error**: {str(e)}")

# --- 7. MAIN EXECUTION ---
if __name__ == '__main__':
    # 1. Start the dummy server in a separate thread so it doesn't block the bot
    threading.Thread(target=run_dummy_server, daemon=True).start()

    # 2. Build and start your Telegram bot
    app = Application.builder().token(TOKEN).build()

    # Register Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern='^(market_|ignore_|start_over)'))
    app.add_handler(MessageHandler(filters.PHOTO, process_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ SFT Bot is running...")
    app.run_polling(drop_pending_updates=True)