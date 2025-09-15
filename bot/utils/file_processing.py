import os
import io
import asyncio
import tempfile
from datetime import datetime
from typing import Optional, Tuple, List

from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from pydub import AudioSegment
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import pdfkit

from config import TEMP_DIR, MAX_AUDIO_BYTES, ALLOWED_AUDIO_EXT


pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))


async def download_telegram_file(message: Message) -> Tuple[Optional[str], Optional[str]]:
    file_id = None
    filename = None
    if message.document:
        file_id = message.document.file_id
        filename = message.document.file_name
    elif message.audio:
        file_id = message.audio.file_id
        filename = (message.audio.file_name or 'audio.mp3')
    elif message.voice:
        file_id = message.voice.file_id
        filename = 'voice.ogg'
    elif message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        filename = f"photo_{photo.file_unique_id}.jpg"
    elif message.text:
        # text note will be saved separately
        return None, None

    if not file_id:
        return None, None

    bot = message.bot
    file = await bot.get_file(file_id)
    dest = os.path.join(TEMP_DIR, filename)
    await bot.download_file(file.file_path, destination=dest)
    return dest, filename


async def convert_to_mp3_if_needed(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if ext not in ALLOWED_AUDIO_EXT:
        return path
    if ext == 'mp3':
        return path
    # Convert to mp3
    mp3_path = os.path.splitext(path)[0] + '.mp3'
    audio = AudioSegment.from_file(path)
    audio.export(mp3_path, format='mp3', bitrate='192k')
    return mp3_path


async def ensure_single_audio_policy(state: FSMContext, new_audio_path: str) -> bool:
    data = await state.get_data()
    first_audio = data.get('first_audio_path')
    if first_audio:
        return False
    await state.update_data(first_audio_path=new_audio_path)
    return True


async def save_text_note_to_md(state: FSMContext, text: str) -> None:
    data = await state.get_data()
    notes: List[str] = data.get('text_notes', [])
    notes.append(text)
    await state.update_data(text_notes=notes)


def _draw_markdown_like(canvas_obj: canvas.Canvas, text: str, title: Optional[str] = None):
    canvas_obj.setFont('DejaVu', 12)
    width, height = A4
    x = 20 * mm
    y = height - 20 * mm
    if title:
        canvas_obj.setFont('DejaVu', 16)
        canvas_obj.drawString(x, y, title)
        y -= 10 * mm
        canvas_obj.setFont('DejaVu', 12)
    for line in text.splitlines():
        if y < 20 * mm:
            canvas_obj.showPage()
            canvas_obj.setFont('DejaVu', 12)
            y = height - 20 * mm
        canvas_obj.drawString(x, y, line)
        y -= 7 * mm


async def make_pdf_from_text(text: str, out_path: str, title: Optional[str] = None) -> str:
    c = canvas.Canvas(out_path, pagesize=A4)
    _draw_markdown_like(c, text, title=title)
    c.save()
    return out_path


async def make_pdf_from_images(image_paths: List[str], out_path: str) -> str:
    c = canvas.Canvas(out_path, pagesize=A4)
    for img_path in image_paths:
        img = Image.open(img_path)
        img_width, img_height = img.size
        page_width, page_height = A4
        # Fit image to page preserving aspect
        ratio = min(page_width / img_width, page_height / img_height)
        draw_width = img_width * ratio
        draw_height = img_height * ratio
        x = (page_width - draw_width) / 2
        y = (page_height - draw_height) / 2
        c.drawImage(img_path, x, y, draw_width, draw_height)
        c.showPage()
    c.save()
    return out_path


async def make_pdf_from_structured_text(structured_text: str, out_path: str, title: Optional[str] = None) -> str:
    # Build HTML with MathJax support for LaTeX rendering
    html = f"""
<!DOCTYPE html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\">
  <title>{title or 'Конспект'}</title>
  <script>
    window.MathJax = {{ tex: {{inlineMath: [['$', '$'], ['\\\(', '\\\)']]}} }};
  </script>
  <script src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js\"></script>
  <style>
    body {{ font-family: DejaVu Sans, Arial, sans-serif; font-size: 14px; line-height: 1.5; }}
    h1, h2, h3 {{ font-weight: 700; }}
    code, pre {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
    .title {{ font-size: 20px; font-weight: 700; margin-bottom: 16px; }}
  </style>
  </head>
<body>
  <div class=\"title\">{title or ''}</div>
  <div>
    {structured_text.replace('\n', '<br/>')}
  </div>
</body>
</html>
"""
    try:
        options = {
            'encoding': 'UTF-8',
            'enable-local-file-access': None,
            'javascript-delay': '1200',
            'no-outline': None,
        }
        pdfkit.from_string(html, out_path, options=options)
        return out_path
    except Exception:
        # Fallback to plain PDF
        return await make_pdf_from_text(structured_text, out_path, title=title)
