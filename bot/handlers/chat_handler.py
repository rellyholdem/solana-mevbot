# -*- coding: utf-8 -*-
import json
import os
import time
from typing import Dict

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import ChatTypeFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import config

router = Router()
router.message.filter(ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]))


LIB_CB_REFRESH = "lib_refresh"


def _load_shares() -> Dict[str, str]:
    if os.path.exists(config.SHARES_CACHE_FILE):
        with open(config.SHARES_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_msg_cache() -> Dict[str, int]:
    if os.path.exists(config.MESSAGES_CACHE_FILE):
        with open(config.MESSAGES_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_msg_cache(cache: Dict[str, int]) -> None:
    os.makedirs(os.path.dirname(config.MESSAGES_CACHE_FILE), exist_ok=True)
    with open(config.MESSAGES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _build_library_text() -> str:
    shares = _load_shares()
    lines = [
        "📚 <b>БИБЛИОТЕКА ЛЕКЦИЙ ЭОСО-01-25</b>",
        "",
    ]
    for d in config.DISCIPLINES:
        url = shares.get(d, "#")
        lines.append(f"🔗 <a href=\"{url}\">{d}</a>")
    lines.append("")
    lines.append(f"📅 Последнее обновление: <code>{time.strftime('%d.%m.%Y %H:%M')}</code>")
    return "\n".join(lines)


def _library_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Обновить", callback_data=LIB_CB_REFRESH)]])


async def _post_or_update_library(message: Message):
    chat_key = str(message.chat.id)
    cache = _load_msg_cache()
    old_id = cache.get(chat_key)
    if old_id:
        from contextlib import suppress
        with suppress(Exception):
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old_id)
    sent = await message.bot.send_message(chat_id=message.chat.id, text=_build_library_text(), reply_markup=_library_keyboard(), disable_web_page_preview=True)
    cache[chat_key] = sent.message_id
    _save_msg_cache(cache)


@router.message()
async def on_any_message(message: Message):
    if message.from_user and message.from_user.is_bot:
        return
    await _post_or_update_library(message)


@router.callback_query(F.data == LIB_CB_REFRESH)
async def on_refresh(cb: CallbackQuery):
    await _post_or_update_library(cb.message)
    from contextlib import suppress
    with suppress(Exception):
        await cb.answer("Обновлено")


def register_group_handlers(dp):
    dp.include_router(router)