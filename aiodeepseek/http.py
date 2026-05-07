from __future__ import annotations

import base64
import json
import time
import uuid
from typing import AsyncIterator, Dict, Optional, Tuple

import aiohttp

from aiodeepseek.constants import BASE_URL, COMPLETION_PATH, HEADERS
from aiodeepseek.pow import solve_pow
from aiodeepseek.types.exceptions import DeepSeekError

_ImageInfo = Tuple[str, int, int, int]

_PowCacheEntry = Tuple[str, int]


def _extract_fragment(event: dict) -> str:
    """Extract a text fragment from a single DeepSeek SSE event dict.

    Args:
        event: Parsed JSON object from one SSE ``data:`` line.

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
    """Manages a single ``aiohttp.ClientSession`` and all raw DeepSeek API calls.

    Must be used as an async context manager before calling any methods.
    Solved PoW responses are cached per target path and reused until they expire,
    avoiding redundant challenge fetches and hash computation.

    Args:
        timeout: Default total timeout in seconds applied to every request.
            ``None`` means no timeout.
    """

    def __init__(self, timeout: Optional[float] = None) -> None:
        self._timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._pow_cache: Dict[str, _PowCacheEntry] = {}

    def _aiohttp_timeout(self, timeout: Optional[float]) -> Optional[aiohttp.ClientTimeout]:
        """Convert a float timeout to an :class:`aiohttp.ClientTimeout` or ``None``."""
        return aiohttp.ClientTimeout(total=timeout) if timeout is not None else None

    async def open(self) -> None:
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False, enable_cleanup_closed=True)
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._pow_cache.clear()

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
            session: An open :class:`aiohttp.ClientSession` to use for the request.
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
            Challenge dict with keys ``salt``, ``expire_at``, ``difficulty``,
            ``challenge``, ``algorithm``, and ``signature``.

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

    def _cached_pow_header(self, target_path: str) -> Optional[str]:
        """Return a cached PoW header for *target_path* if it has not expired.

        ``expire_at`` from the server is a Unix timestamp in milliseconds.

        Args:
            target_path: API endpoint path the PoW was issued for.

        Returns:
            Base64-encoded PoW header string, or ``None`` if no valid cache entry
            exists for *target_path*.
        """
        entry = self._pow_cache.get(target_path)
        if entry is None:
            return None
        pow_header, expire_at_ms = entry
        if time.time() * 1000 < expire_at_ms:
            return pow_header
        del self._pow_cache[target_path]
        return None

    async def _build_pow_header(
        self,
        token: str,
        target_path: str = COMPLETION_PATH,
        timeout: Optional[float] = None,
    ) -> str:
        """Return a valid base64-encoded ``X-DS-PoW-Response`` header value.

        If a solved response for *target_path* is cached and its ``expire_at``
        has not passed, it is returned immediately without contacting the server.
        Otherwise a fresh challenge is fetched, solved, cached, and returned.

        Args:
            token: Valid bearer token used to fetch the challenge.
            target_path: API endpoint path to obtain the challenge for.
            timeout: Override the session-level default timeout.

        Returns:
            Base64-encoded JSON string ready to attach as a request header.

        Raises:
            DeepSeekError: If PoW cannot be solved within the difficulty limit.
        """
        cached = self._cached_pow_header(target_path)
        if cached is not None:
            return cached

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
                "target_path": target_path,
            },
            separators=(",", ":"),
        ).encode()

        pow_header = base64.b64encode(payload).decode()
        self._pow_cache[target_path] = (pow_header, int(expire_at))
        return pow_header

    async def stream_chat(
            self,
            token: str,
            session_id: str,
            prompt: str,
            model: str = "default",
            timeout: Optional[float] = None,
            logs_on: bool = False,
    ) -> AsyncIterator[str]:
        """Stream a single chat turn and yield cumulative response text.

        Reuses a cached PoW solution when possible; fetches and solves a fresh
        challenge only when the cached entry has expired.

        Args:
            token: Valid bearer token.
            session_id: Active chat session id.
            prompt: User message to send.
            model: Model type string passed to the API.
            timeout: Override the session-level default timeout.
            logs_on: Print raw SSE events.

        Yields:
            Cumulative assistant text — each value is the full response so far.

        Raises:
            DeepSeekError: On HTTP error or failed PoW.
        """
        assert self._session is not None, "Session not started"

        pow_header = await self._build_pow_header(token, COMPLETION_PATH, timeout)
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
                decoded = raw_line.decode("utf-8", errors="replace")

                if logs_on:
                    print(decoded, end="")

                line = decoded.strip()

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
                    yield accumulated