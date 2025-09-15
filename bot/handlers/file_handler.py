import os
import time
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.handlers.private_handler import UploadStates
from bot.utils.file_processing import (
    download_telegram_file,
    convert_to_mp3_if_needed,
    ensure_single_audio_policy,
    save_text_note_to_md,
)


router = Router()


@router.message(UploadStates.uploading_files, F.document)
@router.message(UploadStates.uploading_files, F.audio)
@router.message(UploadStates.uploading_files, F.voice)
@router.message(UploadStates.uploading_files, F.photo)
@router.message(UploadStates.uploading_scan, F.photo)
@router.message(UploadStates.uploading_files, F.text)
async def on_file_or_text(message: Message, state: FSMContext):
    data = await state.get_data()
    discipline: Optional[str] = data.get("discipline")
    if not discipline:
        await message.answer("Сначала выберите дисциплину.")
        return

    # Download
    local_path, original_name = await download_telegram_file(message)
    if not local_path:
        # Save text notes separately
        if message.text:
            await save_text_note_to_md(state, message.text)
        return

    # Single audio rule in a session: keep only the first audio, delete later ones
    original_ext = os.path.splitext(local_path)[1].lower()
    if original_ext in {".mp3", ".m4a", ".wav", ".ogg"}:
        keep = await ensure_single_audio_policy(state, local_path)
        if not keep:
            try:
                os.remove(local_path)
            except Exception:
                pass
            return

    # If in scan state, collect images only
    if await state.get_state() == UploadStates.uploading_scan.state:
        if message.photo:
            scan_images = data.get("scan_images", [])
            scan_images.append(local_path)
            await state.update_data(scan_images=scan_images)
            await message.answer("Фото добавлено к скану 📑")
            return
        else:
            await message.answer("В режиме скана принимаются только фотографии.")
            return

    # Convert audio to mp3 for STT
    converted_path = await convert_to_mp3_if_needed(local_path)
    if original_ext in {".mp3", ".m4a", ".wav", ".ogg"} and converted_path != local_path:
        # Update first_audio_path to point to mp3 if this was the first audio
        data = await state.get_data()
        if data.get("first_audio_path") == local_path:
            await state.update_data(first_audio_path=converted_path)
    local_path = converted_path

    # Save text notes into md file
    if message.text and not message.document and not message.photo and not message.audio and not message.voice:
        await save_text_note_to_md(state, message.text)
        return

    await message.answer("Файл принят ✅")

    # Store file into session 'files'
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"path": local_path, "name": original_name or os.path.basename(local_path), "kind": "file"})
    await state.update_data(files=files)


def register_file_handlers(dp):
    dp.include_router(router)
