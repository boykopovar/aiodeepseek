from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import aiohttp

from aiodeepseek.data.constants import BASE_URL, HEADERS, UPLOAD_PATH
from aiodeepseek.http._config import _DEV_MODE
from aiodeepseek.types.exceptions import DeepSeekError
from aiodeepseek.types.models import UploadedImage
from .chat import _ChatClient

_UPLOAD_PENDING_STATUSES = {"PENDING", "PROCESSING", "UPLOADING", "PARSING"}
_UPLOAD_POLL_INTERVAL = 0.5
_UPLOAD_POLL_TIMEOUT = 30.0


class _FilesClient(_ChatClient):
    """Extends :class:`_ChatClient` with file upload and polling support."""

    async def _fetch_file(
        self,
        token: str,
        file_id: str,
        timeout: Optional[float] = None,
    ) -> dict:
        """Fetch current metadata for a single uploaded file.

        Args:
            token: Valid bearer token.
            file_id: File identifier returned by the upload endpoint.
            timeout: Per-call timeout override; falls back to the instance default.

        Returns:
            File metadata dict containing at least ``id`` and ``status``.

        Raises:
            DeepSeekError: On HTTP error or unexpected response shape.
        """
        assert self._session is not None, "Session not started"
        effective = self._effective_timeout(timeout)

        if _DEV_MODE:
            print(f"\n[DEV] >>> FETCH FILE  file_id={file_id}")

        async with self._session.get(
            BASE_URL + "/api/v0/file/fetch_files",
            params={"file_ids": file_id},
            headers={**HEADERS, "Authorization": f"Bearer {token}"},
            timeout=self._aiohttp_timeout(effective),
        ) as resp:
            raw = await resp.text()

            if _DEV_MODE:
                print(f"[DEV] <<< FETCH FILE RESPONSE  status={resp.status}")
                print("[DEV]     BODY:")
                print(raw)

        if resp.status != 200:
            raise DeepSeekError(
                f"fetch_files HTTP {resp.status}: {raw[:400]}",
                resp.status,
            )

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DeepSeekError(
                f"fetch_files returned non-JSON body: {raw[:400]}"
            ) from exc

        if body.get("code") != 0:
            raise DeepSeekError(f"fetch_files failed: {body}")

        files = body["data"]["biz_data"]["files"]
        if not files:
            raise DeepSeekError(f"fetch_files returned empty list for {file_id}")

        return files[0]

    async def _wait_for_file(
        self,
        token: str,
        file_id: str,
        poll_timeout: float = _UPLOAD_POLL_TIMEOUT,
        poll_interval: float = _UPLOAD_POLL_INTERVAL,
    ) -> str:
        """Poll until the uploaded file leaves pending/processing status.

        Args:
            token: Valid bearer token.
            file_id: File identifier to poll.
            poll_timeout: Maximum seconds to wait before raising.
            poll_interval: Seconds between consecutive poll requests.

        Returns:
            The final status string reported by the server.

        Raises:
            DeepSeekError: If the file reaches an error status or the poll timeout expires.
        """
        deadline = time.monotonic() + poll_timeout

        while True:
            meta = await self._fetch_file(token, file_id)
            status: str = meta.get("status", "")

            if _DEV_MODE:
                print(f"[DEV] file {file_id} status={status!r}")

            if status not in _UPLOAD_PENDING_STATUSES:
                if "ERROR" in status.upper() or "FAIL" in status.upper():
                    raise DeepSeekError(
                        f"File processing failed: status={status!r}  meta={meta}"
                    )
                return status

            if time.monotonic() >= deadline:
                raise DeepSeekError(
                    f"Timed out waiting for file {file_id} to become ready "
                    f"(last status={status!r}, waited {poll_timeout}s)"
                )

            await asyncio.sleep(poll_interval)

    async def _upload_image(
        self,
        token: str,
        data: bytes,
        mime_type: str,
        width: int,
        height: int,
        filename: str,
        model: str = "default",
        timeout: Optional[float] = None,
    ) -> UploadedImage:
        """Upload raw image bytes to DeepSeek and return an :class:`UploadedImage`.

        Fetches and solves a PoW challenge scoped to the upload endpoint, sends
        the multipart request, then polls until the file leaves pending status.

        Args:
            token: Valid bearer token.
            data: Raw image bytes (PNG or JPEG).
            mime_type: MIME type string, e.g. ``"image/png"``.
            width: Image width in pixels.
            height: Image height in pixels.
            filename: Filename sent in the multipart ``Content-Disposition`` header.
            model: Model type string forwarded via the ``x-model-type`` header.
            timeout: Per-call timeout override; falls back to the instance default.

        Returns:
            :class:`UploadedImage` ready to attach to subsequent chat requests.

        Raises:
            DeepSeekError: On HTTP error, failed PoW, processing failure, or poll timeout.
        """
        assert self._session is not None, "Session not started"

        pow_header = await self._build_pow_header(token, UPLOAD_PATH, timeout)
        effective = self._effective_timeout(timeout)

        base_headers = {k: v for k, v in HEADERS.items() if k != "Content-Type"}
        headers = {
            **base_headers,
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-DS-PoW-Response": pow_header,
            "X-Thinking-Enabled": "0",
            "x-file-size": str(len(data)),
            "x-model-type": model,
        }

        form = aiohttp.FormData()
        form.add_field("file", data, filename=filename, content_type=mime_type)

        if _DEV_MODE:
            print("\n[DEV] >>> UPLOAD REQUEST")
            print(f"[DEV]     URL    : {BASE_URL + UPLOAD_PATH}")
            print(f"[DEV]     size={len(data)} bytes  mime={mime_type}  file={filename}")

        async with self._session.post(
            BASE_URL + UPLOAD_PATH,
            data=form,
            headers=headers,
            timeout=self._aiohttp_timeout(effective),
        ) as resp:
            if resp.status != 200:
                raw = await resp.read()
                raise DeepSeekError(
                    f"upload HTTP {resp.status}: {raw.decode('utf-8', errors='replace')[:400]}",
                    resp.status,
                )
            body = await resp.json()

        if _DEV_MODE:
            print(f"[DEV] <<< UPLOAD RESPONSE: {body}")

        if body.get("code") != 0:
            raise DeepSeekError(f"upload failed: {body}")

        biz = body["data"]["biz_data"]
        file_id: str = biz["id"]
        status: str = biz.get("status", "")

        if status in _UPLOAD_PENDING_STATUSES:
            if _DEV_MODE:
                print(f"[DEV] file {file_id} is {status!r} — polling …")
            status = await self._wait_for_file(token, file_id)
            if _DEV_MODE:
                print(f"[DEV] file {file_id} ready: status={status!r}")

        return UploadedImage(
            file_id=file_id,
            size_bytes=len(data),
            width=width,
            height=height,
        )
