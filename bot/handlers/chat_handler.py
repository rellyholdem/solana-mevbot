import asyncio
from typing import Dict, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from templates.messages import build_library_message
from bot.keyboards.inline import build_group_library_keyboard
from bot.utils.nextcloud import ensure_discipline_folders_exist, get_or_create_public_links
from config import TARGET_GROUP_CHAT_ID


router = Router()
router.message.filter(F.chat.type.in_({"group", "supergroup"}))

_last_message_id_by_chat: Dict[int, int] = {}


async def _post_or_refresh_library(message: Message) -> None:
    await ensure_discipline_folders_exist()
    links = await get_or_create_public_links()
    text = build_library_message(links)
    reply_markup = build_group_library_keyboard()

    last_id: Optional[int] = _last_message_id_by_chat.get(message.chat.id)
    if last_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_id)
        except Exception:
            pass
    sent = await message.answer(text, reply_markup=reply_markup, disable_web_page_preview=True)
    _last_message_id_by_chat[message.chat.id] = sent.message_id


@router.message()
async def on_any_message(message: Message) -> None:
    # Always refresh library message to keep it first
    if message.from_user and getattr(message.from_user, 'is_bot', False):
        return
    if TARGET_GROUP_CHAT_ID and message.chat.id != TARGET_GROUP_CHAT_ID:
        return
    await _post_or_refresh_library(message)


@router.callback_query(F.data == "refresh_library_group")
async def on_refresh_group(cb: CallbackQuery) -> None:
    await cb.answer("Обновляю…")
    await _post_or_refresh_library(cb.message)


def register_chat_handlers(dp):
    dp.include_router(router)
