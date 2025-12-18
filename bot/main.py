import asyncio
import logging
from logging.handlers import RotatingFileHandler

from telegram.ext import ApplicationBuilder

from bot.config import load_settings
from bot.telegram_ui import TelegramUI


def setup_logging(log_file: str, level: str = "INFO"):
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Rotating file
    fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)


async def main():
    settings = load_settings()
    setup_logging(settings.log_file, settings.log_level)

    app = ApplicationBuilder().token(settings.telegram_token).build()

    ui = TelegramUI(app)
    ui.setup()

    # Run bot polling until Ctrl+C
    await app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass