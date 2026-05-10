import json
from typing import AsyncIterator, Dict, Optional, Tuple

from aiodeepseek.data.constants import BASE_URL, COMPLETION_PATH, HEADERS
from aiodeepseek.http._config import _DEV_MODE
from aiodeepseek.http._sse import _coerce_message_id, _extract_fragment, _extract_message_id
from aiodeepseek.log import _log, _log_request
from aiodeepseek.types.enums import ModelType
from aiodeepseek.types.exceptions import DeepSeekError, raise_for_sse_hint
from aiodeepseek.types.models.classes import UploadedImage
from aiodeepseek.clients.auth import _AuthClient


class _ChatClient(_AuthClient):
    """Extends :class:`_AuthClient` with SSE-based chat streaming."""

    async def stream_chat(
            self,
            token: str,
            session_id: str,
            prompt: str,
            model: ModelType = ModelType.DEFAULT,
            timeout: Optional[float] = None,
            parent_message_id: Optional[str] = None,
            image: Optional[UploadedImage] = None,
            cumulative: bool = True,
    ) -> AsyncIterator[Tuple[str, Optional[str]]]:
        """Stream a single chat turn and yield text/message_id pairs.

        Fetches and solves a PoW challenge before each request, then consumes
        the SSE response line by line.

        Args:
            token: Valid bearer token.
            session_id: Active chat session id.
            prompt: User message to send.
            model: Model type string forwarded to the API.
            timeout: Per-call timeout override; falls back to the instance default.
            parent_message_id: Previous assistant message id for threading.
            image: Optional uploaded image attached to the request.
            cumulative: Yield the full accumulated response on each chunk.
                If ``False``, yields only newly generated text fragments.

        Yields:
            ``(text, message_id)`` tuples.
            If ``cumulative=True``, ``text`` contains the full response so far.
            If ``cumulative=False``, ``text`` contains only the latest fragment.

        Raises:
            DeepSeekError: On HTTP error, failed PoW, or fatal SSE hint event.
        """
        assert self._session is not None, "Session not started"

        pow_header = await self._build_pow_header(token, COMPLETION_PATH, timeout)
        effective = self._effective_timeout(timeout)

        headers: Dict[str, str] = {
            **HEADERS,
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "X-DS-PoW-Response": pow_header,
        }

        body: Dict = {
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

        _log_request("STREAM CHAT REQUEST", BASE_URL + COMPLETION_PATH, headers, body)

        accumulated: str = ""
        message_id: Optional[str] = None

        async with self._session.post(
                BASE_URL + COMPLETION_PATH,
                json=body,
                headers=headers,
                timeout=self._aiohttp_timeout(effective),
        ) as resp:
            if _DEV_MODE:
                _log.debug("<<< STREAM CHAT RESPONSE  status=%s", resp.status)
                _log.debug("    HEADERS:")
                for k, v in resp.headers.items():
                    _log.debug("      %s: %s", k, v)

            if resp.status != 200:
                raw = await resp.text()
                _log.debug("    BODY:")
                _log.debug("%s", raw)
                raise DeepSeekError(
                    f"HTTP {resp.status}: {raw[:400]}",
                    resp.status,
                )

            current_event: str = "message"

            async for raw_line in resp.content:
                line: str = raw_line.decode("utf-8", errors="replace").strip()

                if _DEV_MODE and line:
                    _log.debug("SSE: %s", line)

                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    continue

                if not line.startswith("data:"):
                    current_event = "message"
                    continue

                data_str: str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    current_event = "message"
                    continue

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    current_event = "message"
                    continue

                if (
                        current_event == "hint"
                        and isinstance(event, dict)
                        and event.get("type") == "error"
                ):
                    raise_for_sse_hint(event)

                current_event = "message"

                fragment: str = _extract_fragment(event)

                if message_id is None:
                    new_mid: Optional[str] = _extract_message_id(event)
                    if new_mid is not None:
                        _log.debug(
                            "message_id extracted: %r  (from event: %r)",
                            new_mid,
                            event,
                        )
                    message_id = new_mid

                if not fragment:
                    continue

                accumulated += fragment

                if cumulative:
                    yield accumulated, message_id
                else:
                    yield fragment, message_id

        if _DEV_MODE:
            _log.debug("stream done — final message_id=%r", message_id)
