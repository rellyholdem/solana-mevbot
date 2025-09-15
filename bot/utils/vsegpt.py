# -*- coding: utf-8 -*-
import asyncio
import time
from typing import Optional

import aiohttp
from loguru import logger

import config


class VseGPTClient:
    def __init__(self, base_url: str, api_key: str, title: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.title = title
        self._last_call_ts = 0.0

    async def _ensure_rate_limit(self):
        delta = time.time() - self._last_call_ts
        wait = max(0.0, config.REQUEST_MIN_INTERVAL_SECONDS - delta)
        if wait > 0:
            await asyncio.sleep(wait)

    async def _session(self) -> aiohttp.ClientSession:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Title": self.title,
        }
        return aiohttp.ClientSession(headers=headers)

    async def transcribe(self, audio_path: str, language: str = "ru") -> Optional[str]:
        await self._ensure_rate_limit()
        async with await self._session() as s:
            url = f"{self.base_url}/audio/transcriptions"
            form = aiohttp.FormData()
            form.add_field("model", config.VSEGPT_STT_MODEL)
            form.add_field("response_format", "json")
            form.add_field("language", language)
            form.add_field("file", open(audio_path, 'rb'), filename="audio.mp3", content_type="audio/mpeg")
            r = await s.post(url, data=form)
            self._last_call_ts = time.time()
            if r.status != 200:
                txt = await r.text()
                logger.error(f"STT failed {r.status}: {txt}")
                return None
            data = await r.json()
            # assume {"text": "..."} compatible
            return data.get("text") or data.get("result") or data.get("content")

    async def structure_text(self, model: str, system_prompt: str, raw_text: str) -> Optional[str]:
        await self._ensure_rate_limit()
        async with await self._session() as s:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text},
                ],
                "max_tokens": 4000,
                "temperature": 0.3,
            }
            r = await s.post(url, json=payload)
            self._last_call_ts = time.time()
            if r.status != 200:
                txt = await r.text()
                logger.error(f"Structure failed {r.status}: {txt}")
                return None
            data = await r.json()
            # OpenAI-compatible
            try:
                return data["choices"][0]["message"]["content"].strip()
            except Exception:
                return None