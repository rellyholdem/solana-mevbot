# -*- coding: utf-8 -*-
import time
import config


def library_text(shares: dict) -> str:
    lines = ["📚 <b>БИБЛИОТЕКА ЛЕКЦИЙ ЭОСО-01-25</b>", ""]
    for d in config.DISCIPLINES:
        url = shares.get(d, "#")
        lines.append(f"🔗 <a href=\"{url}\">{d}</a>")
    lines.append("")
    lines.append(f"📅 Последнее обновление: <code>{time.strftime('%d.%m.%Y %H:%M')}</code>")
    return "\n".join(lines)