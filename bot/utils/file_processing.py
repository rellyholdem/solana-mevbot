# -*- coding: utf-8 -*-
import os
import subprocess
import tempfile
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from markdown import markdown
from loguru import logger

import config


def sanitize_filename(name: str) -> str:
    bad = '\\/:*?"<>|\n\r\t'
    for ch in bad:
        name = name.replace(ch, '_')
    return name.strip().strip('.') or 'file'


async def ensure_mp3(path: str) -> str:
    low = path.lower()
    if low.endswith('.mp3'):
        return path
    out = os.path.join(config.UPLOAD_TMP_DIR, sanitize_filename(os.path.splitext(os.path.basename(path))[0]) + '.mp3')
    cmd = ["ffmpeg", "-y", "-i", path, "-vn", "-acodec", "libmp3lame", "-b:a", "192k", out]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out
    except Exception as e:
        logger.error(f"ffmpeg convert failed: {e}")
        return path


async def generate_pdf_from_markdown(md_text: str, title: Optional[str] = None) -> str:
    # Minimal PDF generation: render markdown to plain text preserving basic formatting.
    # For LaTeX formulas, they will appear inline as $...$ in PDF unless later replaced by a more advanced renderer.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.pdf')
    os.close(tmp_fd)

    pdfmetrics.registerFont(TTFont('DejaVu', config.PDF_FONT_PATH))
    pdfmetrics.registerFont(TTFont('DejaVuMono', config.PDF_MONO_FONT_PATH))

    c = canvas.Canvas(tmp_path, pagesize=A4)
    c.setTitle(title or "Конспект")
    width, height = A4

    left = 20 * mm
    top = height - 20 * mm
    max_width = width - 40 * mm

    # Very simple markdown to text: keep headings and bold markup as-is
    text = md_text.replace('\r\n', '\n')

    y = top
    c.setFont('DejaVu', 12)

    for para in text.split('\n'):
        if not para.strip():
            y -= 8
            continue
        wrapped = simpleSplit(para, 'DejaVu', 12, max_width)
        for line in wrapped:
            if y < 30 * mm:
                c.showPage()
                c.setFont('DejaVu', 12)
                y = top
            c.drawString(left, y, line)
            y -= 6.5 * mm / 2
        y -= 4

    c.showPage()
    c.save()
    return tmp_path