from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime

from bot.keyboards.inline import (
    build_private_library_keyboard,
    build_discipline_select_keyboard,
    build_upload_keyboard,
    build_lesson_type_keyboard,
)
from templates.messages import build_library_message, build_upload_intro, build_scan_intro
from bot.utils.nextcloud import ensure_discipline_folders_exist, get_or_create_public_links
from bot.utils.nextcloud import create_folder_structure, upload_file_to_nextcloud, upload_file_unique
from bot.utils.vsegpt import transcribe_audio, structure_text
from bot.utils.file_processing import make_pdf_from_text, make_pdf_from_images, make_pdf_from_structured_text
from config import CONSPECTS_FOLDER, ROOT_FOLDER
import json
import os


class UploadStates(StatesGroup):
    choosing_discipline = State()
    uploading_files = State()
    choosing_lesson_type = State()
    entering_topic = State()
    uploading_scan = State()


router = Router()
router.message.filter(F.chat.type == "private")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await ensure_discipline_folders_exist()
    links = await get_or_create_public_links()
    text = build_library_message(links, include_updated_at=True)
    await message.answer(text, reply_markup=build_private_library_keyboard(), disable_web_page_preview=True)


@router.callback_query(F.data == "refresh_library_private")
async def refresh_private(cb: CallbackQuery):
    await cb.answer("Обновлено")
    links = await get_or_create_public_links()
    text = build_library_message(links, include_updated_at=True)
    try:
        await cb.message.edit_text(text, reply_markup=build_private_library_keyboard(), disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(text, reply_markup=build_private_library_keyboard(), disable_web_page_preview=True)


@router.callback_query(F.data == "add_file")
async def add_file(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(UploadStates.choosing_discipline)
    # Capture session date once per upload flow
    await state.update_data(session_date_str=datetime.now().strftime('%d.%m.%Y'))
    await cb.message.answer(build_upload_intro(), reply_markup=build_discipline_select_keyboard())


@router.callback_query(F.data == "back_to_library")
async def back_to_library(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    links = await get_or_create_public_links()
    text = build_library_message(links, include_updated_at=True)
    await cb.message.answer(text, reply_markup=build_private_library_keyboard(), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("choose_discipline:"))
async def choose_discipline(cb: CallbackQuery, state: FSMContext):
    discipline = cb.data.split(":", 1)[1]
    await state.update_data(discipline=discipline, files=[], first_audio_path=None, text_notes=[], scan_images=[])
    await state.set_state(UploadStates.uploading_files)
    await cb.message.answer(
        build_upload_intro(discipline),
        reply_markup=build_upload_keyboard(),
    )


@router.callback_query(F.data == "scan_mode")
async def scan_mode(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(UploadStates.uploading_scan)
    await state.update_data(scan_images=[])
    await cb.message.answer(build_scan_intro(), reply_markup=build_upload_keyboard(scan_flow=True))


@router.callback_query(F.data == "cancel_scan")
async def cancel_scan(cb: CallbackQuery, state: FSMContext):
    await cb.answer("Отмена сканирования")
    await state.set_state(UploadStates.uploading_files)
    # Delete the scan prompt message
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "scan_done")
async def scan_done(cb: CallbackQuery, state: FSMContext):
    await cb.answer("Скан готов")
    await state.set_state(UploadStates.uploading_files)
    # Delete the scan prompt message
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "lesson_type")
async def after_files_ready(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(UploadStates.choosing_lesson_type)
    await cb.message.answer("🎯 <b>ТИП ЗАНЯТИЯ</b>\n\nВыберите тип занятия для загруженных материалов:", reply_markup=build_lesson_type_keyboard())


@router.callback_query(F.data.startswith("lesson:"))
async def lesson_selected(cb: CallbackQuery, state: FSMContext):
    lesson_type = cb.data.split(":", 1)[1]
    await state.update_data(lesson_type=lesson_type)
    await state.set_state(UploadStates.entering_topic)
    await cb.message.answer(
        "📝 <b>ТЕМА ЗАНЯТИЯ</b>\n\nВведите краткую тему занятия для именования файлов:\n\n💡 Например: \"Введение в термодинамику\", \"Системы линейных уравнений\"",
    )


@router.message(UploadStates.entering_topic, F.text)
async def got_topic(message: Message, state: FSMContext):
    user_topic = message.text.strip()
    data = await state.get_data()
    discipline = data.get("discipline")
    lesson_type = data.get("lesson_type")
    date_str = data.get("session_date_str")
    base_folder = await create_folder_structure(discipline, date_str, lesson_type)
    lesson_folder = f"{base_folder}/{lesson_type}"

    # Consolidate collected files
    first_audio = data.get("first_audio_path")
    text_notes = data.get("text_notes", [])
    scan_images = data.get("scan_images", [])
    files = data.get("files", [])

    # Save notes to md
    md_name = "заметка.md"
    md_content = "\n\n".join(text_notes) if text_notes else ""
    if md_content:
        local_md = f"/tmp/note_{message.from_user.id}.md"
        with open(local_md, "w", encoding="utf-8") as f:
            f.write(f"# Заметка\n\n{md_content}\n")
        await upload_file_to_nextcloud(local_md, f"{lesson_folder}/{md_name}")

    # Transcribe audio if present
    structured_text = None
    if first_audio and os.path.exists(first_audio):
        raw_text = await transcribe_audio(first_audio, language="ru")
        # Load system prompt
        from pathlib import Path
        prompt_path = Path("templates/processing_prompt.json")
        system_prompt = json.loads(prompt_path.read_text(encoding="utf-8"))['system_prompt']
        structured_text = await structure_text(system_prompt, raw_text)
        # Make PDF
        audio_pdf_local = f"/tmp/{message.from_user.id}_lecture.pdf"
        title = user_topic
        await make_pdf_from_structured_text(structured_text, audio_pdf_local, title=title)
        # Upload to lesson folder with unique name rule handled at nextcloud layer if needed
        safe_topic = user_topic.replace(' ', '_')
        pdf_name = f"{safe_topic}.pdf"
        await upload_file_unique(audio_pdf_local, lesson_folder, pdf_name)
        # Also copy to conspects folder with date prefix
        conspects_path = f"{discipline}/{CONSPECTS_FOLDER}"
        date_prefix = datetime.now().strftime('%d_%m_%Y')
        conspect_name = f"{date_prefix}_{safe_topic}.pdf"
        await upload_file_unique(audio_pdf_local, f"{ROOT_FOLDER}/{conspects_path}", conspect_name)

    # Build scan PDF if images collected
    if scan_images:
        scan_pdf_local = f"/tmp/{message.from_user.id}_scan.pdf"
        await make_pdf_from_images(scan_images, scan_pdf_local)
        safe_topic = user_topic.replace(' ', '_')
        scan_name = f"ФОТО_{safe_topic}.pdf"
        await upload_file_unique(scan_pdf_local, lesson_folder, scan_name)
        date_prefix = datetime.now().strftime('%d_%m_%Y')
        conspect_scan_name = f"ФОТО_{date_prefix}_{safe_topic}.pdf"
        await upload_file_unique(scan_pdf_local, f"{ROOT_FOLDER}/{discipline}/{CONSPECTS_FOLDER}", conspect_scan_name)

    # Upload all other files as-is
    for f in files:
        path = f.get('path')
        name = f.get('name')
        kind = f.get('kind')
        # Skip the first audio here if already processed, still upload original audio
        if path and os.path.exists(path):
            try:
                await upload_file_unique(path, lesson_folder, name)
            except Exception:
                pass

    await state.clear()
    await message.answer("✅ Готово! Материалы загружены в NextCloud.")


def register_private_handlers(dp):
    dp.include_router(router)


@router.message(Command("health"))
async def cmd_health(message: Message):
    await message.answer("✅ Бот онлайн")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer("ℹ️ Статистика будет добавлена позже")
