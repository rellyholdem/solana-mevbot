import asyncio
import base64
import hashlib
import os
from datetime import datetime
from typing import Dict, Optional

import aiohttp
from urllib.parse import quote

from config import (
    NEXTCLOUD_URL,
    NEXTCLOUD_USERNAME,
    NEXTCLOUD_PASSWORD,
    DISCIPLINES,
    ROOT_FOLDER,
    CONSPECTS_FOLDER,
)


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def today_str() -> str:
    return datetime.now().strftime("%d.%m.%Y")


def sanitize_filename(name: str) -> str:
    return (
        name.replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
        .replace("\n", " ")
        .strip()
    )


def _dav_url(path: str) -> str:
    return f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USERNAME}/{quote(path.strip('/'), safe='/')}"


async def _mkcol(session: aiohttp.ClientSession, path: str) -> None:
    url = _dav_url(path)
    async with session.request("MKCOL", url, auth=aiohttp.BasicAuth(NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)) as resp:
        if resp.status in (201, 405):
            return
        if resp.status == 409:
            return
        body = await resp.text()
        raise RuntimeError(f"MKCOL {path} failed: {resp.status} {body}")


async def _put(session: aiohttp.ClientSession, path: str, data: bytes) -> None:
    url = _dav_url(path)
    async with session.put(url, data=data, auth=aiohttp.BasicAuth(NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)) as resp:
        if resp.status not in (200, 201, 204):
            body = await resp.text()
            raise RuntimeError(f"PUT {path} failed: {resp.status} {body}")


async def _exists(session: aiohttp.ClientSession, path: str) -> bool:
    url = _dav_url(path)
    async with session.head(url, auth=aiohttp.BasicAuth(NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)) as resp:
        return resp.status in (200, 204)


async def ensure_discipline_folders_exist() -> None:
    async with aiohttp.ClientSession() as session:
        await _mkcol(session, ROOT_FOLDER)
        for d in DISCIPLINES:
            base = f"{ROOT_FOLDER}/{d}"
            await _mkcol(session, base)
            await _mkcol(session, f"{base}/{CONSPECTS_FOLDER}")


async def create_folder_structure(discipline: str, date_str: Optional[str] = None, lesson_type: Optional[str] = None) -> str:
    if not date_str:
        date_str = today_str()
    async with aiohttp.ClientSession() as session:
        base = f"{ROOT_FOLDER}/{discipline}/{date_str}"
        await _mkcol(session, base)
        if lesson_type:
            await _mkcol(session, f"{base}/{lesson_type}")
        return base


async def upload_file_to_nextcloud(local_path: str, remote_path: str) -> None:
    async with aiohttp.ClientSession() as session:
        with open(local_path, "rb") as f:
            data = f.read()
        await _put(session, remote_path, data)


async def upload_file_unique(local_path: str, folder_path: str, suggested_name: str) -> str:
    async with aiohttp.ClientSession() as session:
        unique_name = await generate_unique_filename(session, folder_path, suggested_name)
        with open(local_path, "rb") as f:
            data = f.read()
        await _put(session, f"{folder_path}/{unique_name}", data)
        return f"{folder_path}/{unique_name}"


async def generate_unique_filename(session: aiohttp.ClientSession, folder_path: str, base_filename: str) -> str:
    name, ext = os.path.splitext(base_filename)
    candidate = base_filename
    idx = 1
    while await _exists(session, f"{folder_path}/{candidate}"):
        candidate = f"{name}_{idx}{ext}"
        idx += 1
    return candidate


async def get_or_create_public_links() -> Dict[str, str]:
    headers = {"OCS-APIRequest": "true"}
    auth = aiohttp.BasicAuth(NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)
    async with aiohttp.ClientSession(headers=headers) as session:
        # List existing shares
        base_api = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares"
        links: Dict[str, str] = {}

        async with session.get(base_api, params={"format": "json"}, auth=auth) as resp:
            data = await resp.json()
            if resp.status == 200 and data.get("ocs", {}).get("data"):
                for item in data["ocs"]["data"]:
                    path = item.get("path", "")
                    url = item.get("url")
                    if path.startswith(f"/{ROOT_FOLDER}/") and url:
                        # Extract discipline
                        parts = path.strip("/").split("/")
                        if len(parts) >= 2 and parts[1] in DISCIPLINES:
                            links[parts[1]] = url

        # Ensure shares for each discipline root directory
        for d in DISCIPLINES:
            if d in links:
                continue
            share_path = f"/{ROOT_FOLDER}/{d}"
            payload = {
                "path": share_path,
                "shareType": 3,  # public link
                "permissions": 31,  # read+write+create+delete+share
                "publicUpload": "true",
            }
            async with session.post(base_api, data=payload, params={"format": "json"}, auth=auth) as resp:
                data = await resp.json()
                if resp.status in (200, 201) and data.get("ocs", {}).get("data", {}).get("url"):
                    links[d] = data["ocs"]["data"]["url"]
                else:
                    # fallback: point to web path without share
                    links[d] = f"{NEXTCLOUD_URL}/apps/files/?dir=/{ROOT_FOLDER}/{d}"

        return links
