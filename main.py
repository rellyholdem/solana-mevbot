# -*- coding: utf-8 -*-
import asyncio
import json
import os
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

import config
from bot.handlers.chat_handler import register_group_handlers
from bot.handlers.private_handler import register_private_handlers
from bot.utils.nextcloud import NextcloudClient


async def on_startup(bot: Bot):
    os.makedirs(config.STATE_DIR, exist_ok=True)
    os.makedirs(config.UPLOAD_TMP_DIR, exist_ok=True)

    nc = NextcloudClient(
        base_url=config.NEXTCLOUD_URL,
        username=config.NEXTCLOUD_USERNAME,
        password=config.NEXTCLOUD_PASSWORD,
        base_folder=config.NEXTCLOUD_BASE_FOLDER,
    )
    await nc.ensure_base_structure(config.DISCIPLINES)
    shares = await nc.ensure_public_shares_for_disciplines(config.DISCIPLINES)
    with open(config.SHARES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(shares, f, ensure_ascii=False, indent=2)


async def main():
    logger.add("/workspace/bot.log", rotation="5 MB", retention=5)

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    register_group_handlers(dp)
    register_private_handlers(dp)

    await on_startup(bot)

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())