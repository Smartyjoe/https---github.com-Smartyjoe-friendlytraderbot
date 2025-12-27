# Telegram Trading Bot

A sophisticated Telegram bot that integrates with PocketOption API for automated trading signals. The bot uses multi-timeframe analysis, technical indicators, and AI confirmation to generate high-confidence trading signals.

## Features

- **Real-time Market Streaming**: Connects to PocketOption WebSocket for live market data
- **Multi-Timeframe Analysis**: Analyzes price action across different timeframes
- **Technical Indicators**: Uses EMA, RSI, ATR, and Price Action for signal generation
- **AI Confirmation**: Leverages DeepSeek AI for signal validation
- **Telegram UI**: Interactive conversation-based interface for asset selection and trading
- **Persistent Connections**: Automatic reconnection and keep-alive mechanisms

## Project Structure

```
telegram bot/
├── main.py                 # Main bot entry point
├── config.py              # Configuration management
├── telegram_ui.py         # Telegram conversation handlers
├── market_stream.py       # PocketOption WebSocket streaming
├── signal_engine.py       # Trading signal generation logic
├── candle_builder.py      # Candle data processing
├── ai_confirmation.py     # AI-based signal confirmation
├── indicators/            # Technical indicator implementations
│   ├── ema.py
│   ├── rsi.py
│   ├── atr.py
│   └── price_action.py
└── PocketOptionAPI/       # PocketOption API client library
```

## Prerequisites

- Python 3.8+
- Telegram Bot Token (get from @BotFather)
- PocketOption Account with valid SSID
- OpenRouter API Key (for AI confirmation)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd telegram-bot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r PocketOptionAPI/requirements.txt
   pip install python-telegram-bot pandas python-dotenv
   ```

3. **Configure environment variables**:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your actual values:
   ```env
   TELEGRAM_TOKEN=your_telegram_bot_token_here
   POCKET_OPTION_SSID=your_pocketoption_ssid_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   PO_IS_DEMO=true
   ```

4. **Get your PocketOption SSID**:
   - Open PocketOption in your browser
   - Press F12 to open Developer Tools
   - Go to Network tab → WebSocket
   - Look for authentication message starting with `42["auth",{...}]`
   - Copy the complete message and extract the session ID
   - Paste just the session ID (not the full message) in `.env`

## Usage

1. **Start the bot**:
   ```bash
   python main.py
   ```

2. **Interact with the bot**:
   - Open Telegram and find your bot
   - Send `/start` to begin
   - Follow the conversation steps:
     - Choose Market Type (Real/OTC)
     - Select Asset Class (Forex/Crypto)
     - Pick an Asset
     - Select Expiry Time
   - The bot will stream market data and send signals when all strategies agree

3. **Monitor the bot**:
   - Check logs in `bot.log`
   - Use `/status` to see current session info
   - Use `/stop` to stop streaming

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_TOKEN` | Telegram Bot API token | Required |
| `POCKET_OPTION_SSID` | PocketOption session ID | Required |
| `PO_IS_DEMO` | Use demo account (true/false) | true |
| `OPENROUTER_API_KEY` | OpenRouter API key for AI | Required |
| `DEEPSEEK_MODEL` | AI model to use | deepseek/deepseek-chat |
| `LOG_LEVEL` | Logging level | INFO |
| `AI_QPS` | AI API rate limit | 0.33 |

### Trading Parameters

The bot uses these expiry options:
- 5 seconds
- 15 seconds
- 30 seconds
- 1 minute
- 2 minutes
- 3 minutes
- 5 minutes

### Supported Assets

**Forex (Real & OTC)**:
- EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD
- USDCHF, EURGBP, EURJPY, GBPJPY, NZDUSD

**Crypto**:
- BTCUSD, ETHUSD, BNBUSD, SOLUSD, XRPUSD
- ADAUSD, DOGEUSD, LTCUSD, DOTUSD, AVAXUSD

## Signal Generation Logic

The bot uses a confluence of multiple strategies:

1. **EMA Trend**: Identifies overall market direction
2. **RSI Momentum**: Measures overbought/oversold conditions
3. **ATR Filter**: Validates volatility for trade entry
4. **Price Action**: Detects breakouts and rejection wicks
5. **AI Confirmation**: Final validation using DeepSeek AI

A signal is only generated when ALL strategies agree on direction.

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Verify your SSID is valid and not expired
   - Check if PocketOption is accessible in your region
   - Ensure you're using the correct demo/live mode

2. **WebSocket Version Issues**:
   If you see `extra_headers` errors, run:
   ```bash
   pip uninstall websockets
   pip install websockets==11.0
   ```

3. **Missing Dependencies**:
   ```bash
   pip install -r PocketOptionAPI/requirements.txt
   ```

4. **API Rate Limiting**:
   - The bot respects rate limits automatically
   - Adjust `AI_QPS` if needed for your OpenRouter plan

### Logging

Check `bot.log` for detailed error messages and debugging information:
```bash
tail -f bot.log
```

## API Integration Details

The bot uses the PocketOptionAPI library located in the `PocketOptionAPI/` directory. Key features:

- **Persistent Connections**: Automatic keep-alive and reconnection
- **Multi-Region Support**: Fallback to different regions if one fails
- **Real-time Streaming**: WebSocket-based market data
- **Order Management**: Place and track orders
- **Balance Monitoring**: Real-time account balance updates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Disclaimer

This bot is for educational purposes only. Trading binary options involves significant risk of loss. Past performance does not guarantee future results. Always test thoroughly in demo mode before using real money.

## License

See LICENSE file for details.

## Support

For issues and questions:
- Check the logs for error details
- Review the PocketOptionAPI documentation
- Open an issue in the repository
