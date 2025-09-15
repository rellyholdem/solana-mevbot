import io
import json
import time
from typing import Optional

import aiohttp
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    VSEGPT_API_KEY,
    VSEGPT_BASE_URL,
    VSEGPT_CHAT_MODEL,
    VSEGPT_STT_MODEL,
    BOT_TITLE,
)


HEADERS_JSON = {
    "Authorization": f"Bearer {VSEGPT_API_KEY}",
    "Content-Type": "application/json",
    "X-Title": BOT_TITLE,
}

HEADERS_MULTI = {
    "Authorization": f"Bearer {VSEGPT_API_KEY}",
    "X-Title": BOT_TITLE,
}


_last_call_ts: float = 0.0


async def _throttle():
    global _last_call_ts
    now = time.time()
    delta = now - _last_call_ts
    if delta < 2.0:
        await asyncio.sleep(2.0 - delta)
    _last_call_ts = time.time()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
async def transcribe_audio(local_mp3_path: str, language: str = "ru") -> str:
    url = f"{VSEGPT_BASE_URL}/audio/transcriptions"
    await _throttle()
    with open(local_mp3_path, "rb") as audio_file:
        data = aiohttp.FormData()
        data.add_field("file", audio_file, filename="audio.mp3", content_type="audio/mpeg")
        data.add_field("model", VSEGPT_STT_MODEL)
        data.add_field("response_format", "json")
        data.add_field("language", language)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=HEADERS_MULTI, data=data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"STT failed {resp.status}: {text}")
                j = await resp.json()
                return j.get("text", "")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
async def structure_text(system_prompt: str, raw_text: str) -> str:
    url = f"{VSEGPT_BASE_URL}/chat/completions"
    await _throttle()
    payload = {
        "model": VSEGPT_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text},
        ],
        "max_tokens": 4000,
        "temperature": 0.3,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=HEADERS_JSON, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"LLM failed {resp.status}: {text}")
            j = await resp.json()
            choice = j.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            return content
