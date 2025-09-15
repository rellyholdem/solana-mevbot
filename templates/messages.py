from datetime import datetime
from typing import Dict, Optional


def build_library_message(links: Dict[str, str], include_updated_at: bool = False) -> str:
    lines = ["📚 <b>БИБЛИОТЕКА ЛЕКЦИЙ ЭОСО-01-25</b>", ""]
    for name, url in links.items():
        lines.append(f"🔗 <a href=\"{url}\">{name}</a>")
    if include_updated_at:
        lines.append("")
        lines.append(f"📅 Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)


def build_upload_intro(discipline: Optional[str] = None) -> str:
    if discipline:
        head = f"📤 <b>ЗАГРУЗКА ФАЙЛОВ</b>\n<b>Дисциплина:</b> {discipline}"
    else:
        head = "📁 <b>ЗАГРУЗКА МАТЕРИАЛОВ</b>\n\nВыберите дисциплину для загрузки материалов:"
    body = (
        "\n\nОтправьте файлы для загрузки:\n"
        "📎 Документы (PDF, DOC, DOCX, TXT, MD)\n"
        "🎵 Аудиозаписи (MP3, M4A, WAV, OGG)\n"
        "📷 Изображения (JPG, PNG, GIF)\n"
        "📝 Текстовые заметки (отправьте как обычное сообщение)\n\n"
        "💡 <b>Заметки:</b> Если отправите обычное текстовое сообщение, оно будет сохранено как заметка в файле .md"
    )
    return f"{head}\n\n{body}"


def build_scan_intro() -> str:
    return (
        "📑 <b>СКАН КОНСПЕКТА</b>\n\n"
        "Отправьте 1 или несколько фотографий конспекта. По кнопке \"✅ Готово\" мы соберём PDF со снимков и вернёмся в загрузку занятия."
    )
