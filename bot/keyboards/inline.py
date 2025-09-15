from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import DISCIPLINES


def build_group_library_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_library_group")]]
    )


def build_private_library_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_library_private")],
            [InlineKeyboardButton(text="➕ Добавить файл", callback_data="add_file")],
        ]
    )


def build_discipline_select_keyboard() -> InlineKeyboardMarkup:
    rows = []
    buf = []
    for name in DISCIPLINES:
        buf.append(InlineKeyboardButton(text=name, callback_data=f"choose_discipline:{name}"))
        if len(buf) == 2:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_library")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_upload_keyboard(scan_flow: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if not scan_flow:
        rows.append([InlineKeyboardButton(text="📑 Скан", callback_data="scan_mode")])
    if scan_flow:
        rows.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_scan"),
            InlineKeyboardButton(text="✅ Готово", callback_data="scan_done"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_library"),
            InlineKeyboardButton(text="✅ Готово", callback_data="lesson_type"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_lesson_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Лекция", callback_data="lesson:Лекция")],
            [InlineKeyboardButton(text="🔬 Практика", callback_data="lesson:Практика")],
            [InlineKeyboardButton(text="⚗️ Лабораторная работа", callback_data="lesson:Лабораторная работа")],
        ]
    )
