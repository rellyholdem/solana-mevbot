# -*- coding: utf-8 -*-
import json
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command, ChatTypeFilter
from aiogram.enums import ChatType, ContentType
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)

import config
from bot.utils.nextcloud import NextcloudClient
from bot.utils.vsegpt import VseGPTClient
from bot.utils.file_processing import (
    ensure_mp3,
    generate_pdf_from_markdown,
    sanitize_filename,
)

router = Router()
router.message.filter(ChatTypeFilter(chat_type=ChatType.PRIVATE))

CB_REFRESH = "priv_refresh"
CB_ADD = "priv_add"
CB_BACK = "priv_back"
CB_READY = "priv_ready"
CB_PICK_PREFIX = "pick:"
CB_TYPE_LECTURE = "type_lecture"
CB_TYPE_PRACTICE = "type_practice"
CB_TYPE_LAB = "type_lab"


@dataclass
class UserState:
    discipline: Optional[str] = None
    date_folder: Optional[str] = None
    lesson_type: Optional[str] = None
    upload_root_remote: Optional[str] = None
    first_audio_saved: bool = False


_states: Dict[int, UserState] = {}


def _get_state(uid: int) -> UserState:
    if uid not in _states:
        _states[uid] = UserState()
    return _states[uid]


def _reset_state(uid: int):
    if uid in _states:
        _states[uid] = UserState()


def _main_text() -> str:
    shares = {}
    if os.path.exists(config.SHARES_CACHE_FILE):
        with open(config.SHARES_CACHE_FILE, "r", encoding="utf-8") as f:
            shares = json.load(f)
    lines = ["📚 <b>БИБЛИОТЕКА ЛЕКЦИЙ ЭОСО-01-25</b>", ""]
    for d in config.DISCIPLINES:
        url = shares.get(d, "#")
        lines.append(f"🔗 <a href=\"{url}\">{d}</a>")
    lines.append("")
    lines.append(f"📅 Последнее обновление: <code>{time.strftime('%d.%m.%Y %H:%M')}</code>")
    return "\n".join(lines)


def _main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=CB_REFRESH), InlineKeyboardButton(text="➕ Добавить файл", callback_data=CB_ADD)]
    ])


def _disciplines_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, d in enumerate(config.DISCIPLINES, 1):
        row.append(InlineKeyboardButton(text=d, callback_data=CB_PICK_PREFIX + d))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _upload_text(discipline: str) -> str:
    return (
        "📤 <b>ЗАГРУЗКА ФАЙЛОВ</b>\n"
        f"<b>Дисциплина:</b> {discipline}\n\n"
        "Отправьте файлы для загрузки:\n"
        "📎 Документы (PDF, DOC, DOCX, TXT, MD)\n"
        "🎵 Аудиозаписи (MP3, M4A, WAV, OGG)\n"
        "📷 Изображения (JPG, PNG, GIF)\n"
        "📝 Текстовые заметки (отправьте как обычное сообщение)\n\n"
        "💡 <b>Заметки:</b> Если отправите обычное текстовое сообщение, оно будет сохранено как заметка в файле .md"
    )


def _upload_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_BACK), InlineKeyboardButton(text="✅ Готово", callback_data=CB_READY)]
    ])


def _lesson_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Лекция", callback_data=CB_TYPE_LECTURE)],
        [InlineKeyboardButton(text="🔬 Практика", callback_data=CB_TYPE_PRACTICE)],
        [InlineKeyboardButton(text="⚗️ Лабораторная работа", callback_data=CB_TYPE_LAB)],
    ])


async def _show_main(message: Message):
    await message.answer(_main_text(), reply_markup=_main_kb(), disable_web_page_preview=True)


@router.message(Command("start"))
async def on_start(message: Message):
    await _show_main(message)


@router.callback_query(F.data == CB_REFRESH)
async def on_refresh(cb: CallbackQuery):
    await cb.message.edit_text(_main_text(), reply_markup=_main_kb(), disable_web_page_preview=True)
    with suppress(Exception):
        await cb.answer("Обновлено")


@router.callback_query(F.data == CB_ADD)
async def on_add(cb: CallbackQuery):
    _reset_state(cb.from_user.id)
    await cb.message.edit_text("📁 <b>ЗАГРУЗКА МАТЕРИАЛОВ</b>\n\nВыберите дисциплину для загрузки материалов:", reply_markup=_disciplines_kb())


@router.callback_query(F.data == CB_BACK)
async def on_back(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    if st.discipline:
        # back to disciplines
        st.discipline = None
        await cb.message.edit_text("📁 <b>ЗАГРУЗКА МАТЕРИАЛОВ</b>\n\nВыберите дисциплину для загрузки материалов:", reply_markup=_disciplines_kb())
    else:
        await cb.message.edit_text(_main_text(), reply_markup=_main_kb(), disable_web_page_preview=True)


@router.callback_query(F.data.startswith(CB_PICK_PREFIX))
async def on_pick(cb: CallbackQuery):
    disc = cb.data[len(CB_PICK_PREFIX):]
    st = _get_state(cb.from_user.id)
    st.discipline = disc
    st.date_folder = time.strftime("%d.%m.%Y")
    st.first_audio_saved = False

    nc = NextcloudClient(
        base_url=config.NEXTCLOUD_URL,
        username=config.NEXTCLOUD_USERNAME,
        password=config.NEXTCLOUD_PASSWORD,
        base_folder=config.NEXTCLOUD_BASE_FOLDER,
    )
    upload_root = await nc.prepare_date_folder(disc)
    st.upload_root_remote = upload_root

    await cb.message.edit_text(_upload_text(disc), reply_markup=_upload_kb())


@router.message(F.content_type.in_({ContentType.DOCUMENT, ContentType.AUDIO, ContentType.VOICE, ContentType.VIDEO, ContentType.PHOTO, ContentType.TEXT}))
async def on_upload(message: Message):
    st = _get_state(message.from_user.id)
    if not st.discipline:
        return  # ignore if not in upload flow

    nc = NextcloudClient(
        base_url=config.NEXTCLOUD_URL,
        username=config.NEXTCLOUD_USERNAME,
        password=config.NEXTCLOUD_PASSWORD,
        base_folder=config.NEXTCLOUD_BASE_FOLDER,
    )

    # Resolve media
    file_id = None
    file_name = None
    is_audio = False

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "file"
        mime = message.document.mime_type or "application/octet-stream"
        is_audio = mime.startswith("audio/") or (file_name.lower().endswith(('.mp3', '.m4a', '.wav', '.ogg')))
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        is_audio = True
    elif message.voice:
        file_id = message.voice.file_id
        file_name = "voice.ogg"
        is_audio = True
    elif message.photo:
        largest = message.photo[-1]
        file_id = largest.file_id
        file_name = f"photo_{largest.file_unique_id}.jpg"
    elif message.text and message.text.strip():
        # Save note as markdown
        text = message.text.strip()
        md = f"# Заметка\n\n{text}\n"
        remote = f"{st.upload_root_remote}/заметка.md"
        await nc.append_or_create(remote, md)
        await message.answer("📝 Заметка сохранена в заметка.md")
        return

    if not file_id:
        return

    # Download file
    file = await message.bot.get_file(file_id)
    local_path = os.path.join(config.UPLOAD_TMP_DIR, sanitize_filename(file_name))
    os.makedirs(config.UPLOAD_TMP_DIR, exist_ok=True)
    await message.bot.download_file(file.file_path, destination=local_path)

    # Handle audio constraint: only first audio retained
    if is_audio:
        if st.first_audio_saved:
            with suppress(Exception):
                os.remove(local_path)
            await message.answer("🎧 Второй аудиофайл удалён: для расшифровки принимается только первый.")
            return
        st.first_audio_saved = True

    # Upload to Nextcloud
    remote_path = f"{st.upload_root_remote}/{sanitize_filename(os.path.basename(local_path))}"
    await nc.upload_file(local_path, remote_path)
    await message.answer("✅ Загружено")


@router.callback_query(F.data == CB_READY)
async def on_ready(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    if not st.discipline:
        await cb.answer()
        return
    await cb.message.edit_text("🎯 <b>ТИП ЗАНЯТИЯ</b>\n\nВыберите тип занятия для загруженных материалов:", reply_markup=_lesson_type_kb())


def _after_type_text() -> str:
    return (
        "📝 <b>ТЕМА ЗАНЯТИЯ</b>\n\n"
        "Введите краткую тему занятия для именования файлов:\n\n"
        "💡 Например: \"Введение в термодинамику\", \"Системы линейных уравнений\""
    )


@router.callback_query(F.data.in_({CB_TYPE_LECTURE, CB_TYPE_PRACTICE, CB_TYPE_LAB}))
async def on_type(cb: CallbackQuery):
    st = _get_state(cb.from_user.id)
    st.lesson_type = {
        CB_TYPE_LECTURE: "Лекция",
        CB_TYPE_PRACTICE: "Практика",
        CB_TYPE_LAB: "Лабораторная работа",
    }[cb.data]

    # Move all uploaded files into the chosen lesson subfolder, keep notes where they are too
    nc = NextcloudClient(
        base_url=config.NEXTCLOUD_URL,
        username=config.NEXTCLOUD_USERNAME,
        password=config.NEXTCLOUD_PASSWORD,
        base_folder=config.NEXTCLOUD_BASE_FOLDER,
    )
    lesson_dir = f"{st.upload_root_remote}/{st.lesson_type}"
    await nc.ensure_path(lesson_dir)
    await nc.move_all_into(st.upload_root_remote, lesson_dir, exclude={st.lesson_type, "Конспекты"})

    await cb.message.edit_text(_after_type_text())


@router.message(F.text & ChatTypeFilter(chat_type=ChatType.PRIVATE))
async def on_topic(message: Message):
    st = _get_state(message.from_user.id)
    if not (st.discipline and st.lesson_type and st.upload_root_remote):
        return

    topic = sanitize_filename(message.text.strip())

    nc = NextcloudClient(
        base_url=config.NEXTCLOUD_URL,
        username=config.NEXTCLOUD_USERNAME,
        password=config.NEXTCLOUD_PASSWORD,
        base_folder=config.NEXTCLOUD_BASE_FOLDER,
    )

    # ensure conspects dir
    conspects_dir = f"{st.upload_root_remote}/Конспекты"
    await nc.ensure_path(conspects_dir)

    # find first audio inside lesson folder
    lesson_dir = f"{st.upload_root_remote}/{st.lesson_type}"
    remote_files = await nc.list_folder(lesson_dir)
    audio_remote = None
    for name in remote_files:
        low = name.lower()
        if low.endswith((".mp3", ".m4a", ".wav", ".ogg")):
            audio_remote = f"{lesson_dir}/{name}"
            break

    transcript_text = None
    if audio_remote:
        local_dl = os.path.join(config.UPLOAD_TMP_DIR, f"dl_{message.message_id}_{os.path.basename(audio_remote)}")
        await nc.download_file(audio_remote, local_dl)
        local_mp3 = await ensure_mp3(local_dl)
        vsegpt = VseGPTClient(config.VSEGPT_BASE_URL, config.VSEGPT_API_KEY, config.VSEGPT_TITLE)
        transcript_text = await vsegpt.transcribe(local_mp3)

    structured_md = None
    if transcript_text:
        vsegpt = VseGPTClient(config.VSEGPT_BASE_URL, config.VSEGPT_API_KEY, config.VSEGPT_TITLE)
        structured_md = await vsegpt.structure_text(config.VSEGPT_CHAT_MODEL, config.SYSTEM_PROMPT, transcript_text)

    date_for_name = st.date_folder.replace(".", "_")

    if structured_md:
        base_name = f"{topic or 'конспект'}.pdf"
        final_name = await nc.unique_name(lesson_dir, base_name)
        pdf_local = await generate_pdf_from_markdown(structured_md, title=topic or "Конспект")
        await nc.upload_file(pdf_local, f"{lesson_dir}/{final_name}")
        # Copy to conspects with date prefix (upload as new)
        conspect_name = f"{date_for_name}_{topic or 'конспект'}.pdf"
        conspect_name = await nc.unique_name(conspects_dir, conspect_name)
        await nc.upload_file(pdf_local, f"{conspects_dir}/{conspect_name}")

    await nc.ensure_public_share_path(lesson_dir)
    await nc.ensure_public_share_path(conspects_dir)

    await message.answer("✅ Готово! Материалы загружены и структурированы.")
    _reset_state(message.from_user.id)
    await _show_main(message)


def register_private_handlers(dp):
    dp.include_router(router)