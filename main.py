from __future__ import annotations

import asyncio
import logging

from bot import create_bot_and_dispatcher
from config import load_settings


async def run() -> None:
    settings = load_settings()
    bot, dp = create_bot_and_dispatcher(settings)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
