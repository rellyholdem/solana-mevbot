# -*- coding: utf-8 -*-
import asyncio
import base64
import os
import posixpath
from typing import Dict, List, Optional, Iterable

import aiohttp
from loguru import logger

import config


class NextcloudClient:
    def __init__(self, base_url: str, username: str, password: str, base_folder: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.base_folder = base_folder
        self.webdav_base = f"{self.base_url}/remote.php/dav/files/{self.username}"
        self.ocs_base = f"{self.base_url}/ocs/v2.php"
        self._auth = aiohttp.BasicAuth(self.username, self.password)

    async def _session(self) -> aiohttp.ClientSession:
        headers = {"OCS-APIRequest": "true"}
        return aiohttp.ClientSession(auth=self._auth, headers=headers)

    def _join(self, *parts: str) -> str:
        return posixpath.join(*[p.strip('/') for p in parts if p is not None])

    async def ensure_path(self, remote_path: str) -> None:
        async with await self._session() as s:
            url = f"{self.webdav_base}/{remote_path}"
            r = await s.request("MKCOL", url)
            if r.status in (200, 201, 204):
                return
            if r.status == 405:  # already exists
                return
            if r.status == 409:
                parts = remote_path.strip('/').split('/')
                cur = ""
                for p in parts:
                    cur = self._join(cur, p)
                    await s.request("MKCOL", f"{self.webdav_base}/{cur}")
                return
            text = await r.text()
            logger.warning(f"MKCOL {remote_path} status={r.status} body={text}")

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        async with await self._session() as s:
            url = f"{self.webdav_base}/{remote_path}"
            with open(local_path, 'rb') as f:
                r = await s.put(url, data=f)
            if r.status not in (200, 201, 204):
                text = await r.text()
                logger.error(f"PUT {remote_path} failed {r.status}: {text}")

    async def append_or_create(self, remote_path: str, content: str) -> None:
        existing = None
        try:
            existing = await self.download_text(remote_path)
        except Exception:
            existing = None
        combined = (existing or "") + ("\n" + content if existing else content)
        tmp = os.path.join(config.UPLOAD_TMP_DIR, "tmp_append.md")
        os.makedirs(config.UPLOAD_TMP_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(combined)
        await self.upload_file(tmp, remote_path)

    async def download_file(self, remote_path: str, local_path: str) -> None:
        async with await self._session() as s:
            url = f"{self.webdav_base}/{remote_path}"
            r = await s.get(url)
            if r.status != 200:
                text = await r.text()
                logger.error(f"GET {remote_path} failed {r.status}: {text}")
                return
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(await r.read())

    async def download_text(self, remote_path: str) -> str:
        async with await self._session() as s:
            url = f"{self.webdav_base}/{remote_path}"
            r = await s.get(url)
            r.raise_for_status()
            return await r.text()

    async def list_folder(self, remote_path: str) -> List[str]:
        async with await self._session() as s:
            url = f"{self.webdav_base}/{remote_path}"
            r = await s.request("PROPFIND", url, headers={"Depth": "1"})
            if r.status not in (207, 200):
                return []
            xml = await r.text()
            items = []
            base_href = f"/remote.php/dav/files/{self.username}/{remote_path.strip('/')}"
            for line in xml.splitlines():
                if "<d:href>" in line:
                    start = line.find("<d:href>") + 8
                    end = line.find("</d:href>")
                    href = line[start:end]
                    if href.endswith('/'):
                        href = href[:-1]
                    if href and href != base_href:
                        name = href.split('/')[-1]
                        items.append(name)
            return items

    async def move(self, src_remote: str, dst_remote: str) -> bool:
        async with await self._session() as s:
            src_url = f"{self.webdav_base}/{src_remote}"
            dst_url = f"{self.webdav_base}/{dst_remote}"
            r = await s.request("MOVE", src_url, headers={"Destination": dst_url})
            return r.status in (200, 201, 204)

    async def move_all_into(self, src_folder: str, dst_folder: str, exclude: Optional[Iterable[str]] = None) -> None:
        exclude = set(exclude or [])
        names = await self.list_folder(src_folder)
        for name in names:
            if name in exclude:
                continue
            await self.move(f"{src_folder}/{name}", f"{dst_folder}/{name}")

    async def unique_name(self, folder_remote: str, base_name: str) -> str:
        names = set(await self.list_folder(folder_remote))
        if base_name not in names:
            return base_name
        name, ext = os.path.splitext(base_name)
        idx = 1
        while True:
            cand = f"{name}_{idx}{ext}"
            if cand not in names:
                return cand
            idx += 1

    async def ensure_base_structure(self, disciplines: List[str]) -> None:
        await self.ensure_path(self.base_folder)
        for d in disciplines:
            await self.ensure_path(f"{self.base_folder}/{d}")

    async def prepare_date_folder(self, discipline: str) -> str:
        date_str = __import__('time').strftime("%d.%m.%Y")
        remote = f"{self.base_folder}/{discipline}/{date_str}"
        await self.ensure_path(remote)
        return remote

    async def ensure_public_share_path(self, remote_path: str) -> Optional[str]:
        existing = await self._get_public_share(remote_path)
        if existing:
            return existing
        return await self._create_public_share(remote_path)

    async def ensure_public_shares_for_disciplines(self, disciplines: List[str]) -> Dict[str, str]:
        shares: Dict[str, str] = {}
        for d in disciplines:
            path = f"{self.base_folder}/{d}"
            link = await self.ensure_public_share_path(path)
            if link:
                shares[d] = link
        return shares

    async def _get_public_share(self, remote_path: str) -> Optional[str]:
        async with await self._session() as s:
            url = f"{self.ocs_base}/apps/files_sharing/api/v1/shares?path={remote_path}&reshares=true&subfiles=false"
            r = await s.get(url)
            if r.status != 200:
                return None
            data = await r.text()
            if "<url>" in data:
                start = data.find("<url>") + 5
                end = data.find("</url>")
                return data[start:end]
            return None

    async def _create_public_share(self, remote_path: str) -> Optional[str]:
        async with await self._session() as s:
            url = f"{self.ocs_base}/apps/files_sharing/api/v1/shares"
            form = aiohttp.FormData()
            form.add_field("path", remote_path)
            form.add_field("shareType", "3")  # public link
            form.add_field("permissions", "31")  # read, update, create, delete, share
            form.add_field("publicUpload", "true")  # allow anonymous upload/edit
            r = await s.post(url, data=form)
            if r.status != 200:
                return None
            data = await r.text()
            if "<url>" in data:
                start = data.find("<url>") + 5
                end = data.find("</url>")
                return data[start:end]
            return None

    async def ensure_base_and_get_share(self, discipline: str) -> Optional[str]:
        await self.ensure_path(f"{self.base_folder}/{discipline}")
        return await self.ensure_public_share_path(f"{self.base_folder}/{discipline}")