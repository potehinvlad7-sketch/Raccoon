from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

import admin_handlers
import user_handlers
from config import Settings
from storage import ensure_storage


def create_bot_and_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    if settings.proxy_url:
        session = AiohttpSession(proxy=settings.proxy_url)
        bot = Bot(
            token=settings.bot_token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    else:
        bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()
    dp["settings"] = settings
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)

    ensure_storage()
    return bot, dp
