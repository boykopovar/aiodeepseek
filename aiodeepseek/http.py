from __future__ import annotations

import base64
import json
import uuid
from typing import AsyncIterator, Optional

import aiohttp

from aiodeepseek.constants import BASE_URL, COMPLETION_PATH, HEADERS
from aiodeepseek.pow import solve_pow
from aiodeepseek.types.exceptions import DeepSeekError

def _extract_fragment(event: dict) -> str:
    """Extract a text fragment from a single DeepSeek SSE event dict.

    Args:
        event: Parsed JSON object from one SSE data: line.

    Returns:
        The text fragment, or an empty string if the event carries no text.
    """
    o = event.get("o", "")
    v = event.get("v")

    if o == "APPEND" and isinstance(v, str):
        return v

    if v is not None and "p" not in event and "o" not in event and isinstance(v, str):
        return v

    if isinstance(v, dict) and "response" in v:
        fragments = v["response"].get("fragments", [])
        return "".join(f.get("content", "") for f in fragments)

    return ""

class _DeepSeekSession:
    """Manages a single aiohttp.ClientSession and all raw DeepSeek API calls.

    Must be used as an async context manager before calling any methods.

    Args:
        timeout: Default total timeout in seconds applied to every request.
            None means no timeout.
    """

    def __init__(self, timeout: Optional[float] = None) -> None:
        self._timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    def _aiohttp_timeout(self, timeout: Optional[float]) -> Optional[aiohttp.ClientTimeout]:
        """Convert a float timeout to an :class:aiohttp.ClientTimeout or None."""
        return aiohttp.ClientTimeout(total=timeout) if timeout is not None else None

    async def open(self) -> None:
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(enable_cleanup_closed=True)
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "_DeepSeekSession":
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @staticmethod
    async def fetch_token(
        session: aiohttp.ClientSession,
        email: str,
        password: str,
    ) -> str:
        """Authenticate and return a bearer token.

        Args:
            session: An open :class:aiohttp.ClientSession to use for the request.
            email: DeepSeek account e-mail.
            password: DeepSeek account password.

        Returns:
            Bearer token string.

        Raises:
            DeepSeekError: If the API returns a non-zero code.
        """
        async with session.post(
            BASE_URL + "/api/v0/users/login",
            json={
                "email": email,
                "password": password,
                "device_id": str(uuid.uuid4()).replace("-", ""),
                "os": "ios",
            },
            headers=HEADERS,
        ) as resp:
            data = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"login failed: {data}")

        return data["data"]["biz_data"]["user"]["token"]

    async def create_chat_session(
        self,
        token: str,
        timeout: Optional[float] = None,
    ) -> str:
        """Create a new DeepSeek chat session and return its id.

        Args:
            token: Valid bearer token.
            timeout: Override the session-level default timeout.

        Returns:
            Chat session id string.

        Raises:
            DeepSeekError: If the API returns a non-zero code.
        """
        assert self._session is not None, "Session not started"
        effective = timeout if timeout is not None else self._timeout

        async with self._session.post(
            BASE_URL + "/api/v0/chat_session/create",
            json={"character_id": 1},
            headers={**HEADERS, "Authorization": f"Bearer {token}"},
            timeout=self._aiohttp_timeout(effective),
        ) as resp:
            data = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"create_session failed: {data}")

        return data["data"]["biz_data"]["chat_session"]["id"]

    async def _get_pow_challenge(
        self,
        token: str,
        timeout: Optional[float] = None,
    ) -> dict:
        """Fetch a fresh proof-of-work challenge from the server.

        Args:
            token: Valid bearer token.
            timeout: Override the session-level default timeout.

        Returns:
            Challenge dict with keys salt, expire_at, difficulty,
            challenge, algorithm, and signature.

        Raises:
            DeepSeekError: If the API returns a non-zero code.
        """
        assert self._session is not None, "Session not started"
        effective = timeout if timeout is not None else self._timeout

        async with self._session.post(
            BASE_URL + "/api/v0/chat/create_pow_challenge",
            json={"target_path": COMPLETION_PATH},
            headers={**HEADERS, "Authorization": f"Bearer {token}"},
            timeout=self._aiohttp_timeout(effective),
        ) as resp:
            data = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"pow challenge failed: {data}")

        ch = data["data"]["biz_data"]
        return ch.get("challenge", ch)

    async def _build_pow_header(
        self,
        token: str,
        timeout: Optional[float] = None,
    ) -> str:
        """Solve PoW and return the base64-encoded X-DS-PoW-Response value.

        Args:
            token: Valid bearer token used to fetch the challenge.
            timeout: Override the session-level default timeout.

        Returns:
            Base64-encoded JSON string ready to attach as a request header.

        Raises:
            DeepSeekError: If PoW cannot be solved within the difficulty limit.
        """
        ch = await self._get_pow_challenge(token, timeout)
        salt = ch["salt"]
        expire_at = ch["expire_at"]
        difficulty = int(ch["difficulty"])
        challenge_hex = ch["challenge"]

        nonce = solve_pow(f"{salt}_{expire_at}_", challenge_hex, difficulty)
        if nonce < 0:
            raise DeepSeekError("PoW not solved within difficulty limit")

        payload = json.dumps(
            {
                "algorithm": ch.get("algorithm", "DeepSeekHashV1"),
                "challenge": challenge_hex,
                "salt": salt,
                "signature": ch.get("signature", ""),
                "answer": nonce,
                "target_path": COMPLETION_PATH,
            },
            separators=(",", ":"),
        ).encode()

        return base64.b64encode(payload).decode()

    async def stream_chat(
            self,
            token: str,
            session_id: str,
            prompt: str,
            model: str = "default",
            timeout: Optional[float] = None,
            print_answer: bool = False,
    ) -> AsyncIterator[str]:
        """Stream a single chat turn and yield cumulative response text.

        Fetches and solves a PoW challenge before each request, then streams
        the SSE response and yields the response text accumulated so far after
        each received fragment.

        Args:
            token: Valid bearer token.
            session_id: Active chat session id.
            prompt: User message to send.
            model: Model type string passed to the API.
            timeout: Override the session-level default timeout.
            print_answer: Print cumulative response text while streaming.

        Yields:
            Cumulative assistant text — each value is the full response so far.

        Raises:
            DeepSeekError: On HTTP error or failed PoW.
        """
        assert self._session is not None, "Session not started"

        pow_header = await self._build_pow_header(token, timeout)
        effective = timeout if timeout is not None else self._timeout

        headers = {
            **HEADERS,
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "X-DS-PoW-Response": pow_header,
        }

        body = {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": False,
            "search_enabled": False,
            "audio_id": None,
            "preempt": False,
            "model_type": model,
        }

        accumulated = ""

        async with self._session.post(
                BASE_URL + COMPLETION_PATH,
                json=body,
                headers=headers,
                timeout=self._aiohttp_timeout(effective),
        ) as resp:
            if resp.status != 200:
                raw = await resp.read()
                raise DeepSeekError(
                    f"HTTP {resp.status}: {raw.decode('utf-8', errors='replace')[:400]}",
                    resp.status,
                )

            async for raw_line in resp.content:
                line = raw_line.decode("utf-8", errors="replace").strip()
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
                if fragment:
                    accumulated += fragment

                    if print_answer:
                        print(accumulated)

                    yield accumulated