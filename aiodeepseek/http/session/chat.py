from __future__ import annotations

import json
import pprint
from typing import AsyncIterator, Optional, Tuple

from aiodeepseek.data.constants import BASE_URL, COMPLETION_PATH, HEADERS
from aiodeepseek.types.exceptions import DeepSeekError
from aiodeepseek.types.models import UploadedImage

from .._config import _DEV_MODE
from .._sse import _coerce_message_id, _extract_fragment, _extract_message_id
from ...types.enums import ModelType


class _DeepSeekChatMixin:
    async def stream_chat(
            self,
            token: str,
            session_id: str,
            prompt: str,
            model: ModelType = ModelType.DEFAULT,
            timeout: Optional[float] = None,
            parent_message_id: Optional[str] = None,
            image: Optional[UploadedImage] = None,
    ) -> AsyncIterator[Tuple[str, Optional[str]]]:
        """Stream a single chat turn and yield ``(cumulative_text, message_id)`` pairs.

        Fetches and solves a PoW challenge before each request, then consumes
        the SSE response. Each yielded tuple contains the assistant reply
        accumulated so far and the assistant message id.

        Args:
            token: Valid bearer token.
            session_id: Active chat session id.
            prompt: User message to send.
            model: Model type string forwarded to the API.
            timeout: Per-call timeout override; falls back to the instance default.
            parent_message_id: Previous assistant message id.
            image: Optional uploaded image attached to the request.

        Yields:
            Tuple of ``(accumulated_text, message_id)``.

        Raises:
            DeepSeekError: On HTTP error or failed PoW.
        """
        assert self._session is not None, "Session not started"

        pow_header = await self._build_pow_header(
            token,
            COMPLETION_PATH,
            timeout,
        )

        effective = timeout if timeout is not None else self._timeout

        headers = {
            **HEADERS,
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "X-DS-PoW-Response": pow_header,
        }

        body = {
            "chat_session_id": session_id,
            "parent_message_id": _coerce_message_id(parent_message_id),
            "prompt": prompt,
            "ref_file_ids": [image.file_id] if image is not None else [],
            "thinking_enabled": False,
            "search_enabled": False,
            "audio_id": None,
            "preempt": False,
            "model_type": model,
        }

        if _DEV_MODE:
            print("\n[DEV] >>> REQUEST")
            print(f"[DEV]     URL    : {BASE_URL + COMPLETION_PATH}")

            print("[DEV]     HEADERS:")
            for k, v_h in headers.items():
                print(f"[DEV]       {k}: {v_h[:120]}")

            print("[DEV]     BODY   :")
            pprint.pprint(body, width=120, indent=4)

        accumulated = ""
        last_yielded = ""
        message_id: Optional[str] = None

        async with self._session.post(
                BASE_URL + COMPLETION_PATH,
                json=body,
                headers=headers,
                timeout=self._aiohttp_timeout(effective),
        ) as resp:
            if _DEV_MODE:
                print(f"\n[DEV] <<< RESPONSE  status={resp.status}")

                print("[DEV]     HEADERS:")
                for k, v_h in resp.headers.items():
                    print(f"[DEV]       {k}: {v_h}")

            if resp.status != 200:
                raw = await resp.read()

                raise DeepSeekError(
                    f"HTTP {resp.status}: "
                    f"{raw.decode('utf-8', errors='replace')[:400]}",
                    resp.status,
                )

            async for raw_line in resp.content:
                line = raw_line.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if _DEV_MODE and line:
                    print(f"[DEV] SSE: {line}")

                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()

                if not data_str or data_str == "[DONE]":
                    continue

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                fragment = _extract_fragment(event)

                updated = False

                if fragment:
                    accumulated += fragment
                    updated = True

                if message_id is None:
                    new_mid = _extract_message_id(event)

                    if new_mid is not None and _DEV_MODE:
                        print(
                            "[DEV] message_id extracted: "
                            f"{new_mid!r}  (from event: {event})"
                        )

                    message_id = new_mid

                if updated and accumulated != last_yielded:
                    last_yielded = accumulated
                    yield accumulated, message_id

        if _DEV_MODE:
            print(
                "\n[DEV] stream done — "
                f"final message_id={message_id!r}"
            )

