from __future__ import annotations

import base64
import json
import random
import time
from typing import Optional

import aiohttp

from aiodeepseek.data.constants import BASE_URL, COMPLETION_PATH, HEADERS, UPLOAD_PATH
from aiodeepseek.data.device_ids import get_device_id
from aiodeepseek.pow.pow import solve_pow
from aiodeepseek.types.exceptions import DeepSeekError


class _BaseClient:
    """Base HTTP client for the DeepSeek API.

    Manages a single ``aiohttp.ClientSession`` and provides shared helpers
    for proof-of-work challenges and chat session creation.  All higher-level
    clients in the hierarchy inherit from this class and therefore always have
    access to ``_session``, ``_timeout``, and the PoW helpers.

    Args:
        timeout: Default total timeout in seconds applied to every request.
            ``None`` means no timeout.
        device_id: Stable device identifier sent to the API.  A random one is
            chosen from the built-in pool when not provided.
    """

    def __init__(
        self,
        timeout: Optional[float] = None,
        device_id: Optional[str] = None,
    ) -> None:
        self._timeout = timeout
        self._device_id = device_id or get_device_id()
        self._session: Optional[aiohttp.ClientSession] = None
        self._rangers_id: str = str(random.randint(10**18, 10**19 - 1))

    def _aiohttp_timeout(self, timeout: Optional[float]) -> Optional[aiohttp.ClientTimeout]:
        """Convert a float *timeout* to ``aiohttp.ClientTimeout``, or ``None``."""
        return aiohttp.ClientTimeout(total=timeout) if timeout is not None else None

    def _effective_timeout(self, timeout: Optional[float]) -> Optional[float]:
        """Return *timeout* when given, otherwise fall back to the instance default."""
        return timeout if timeout is not None else self._timeout

    def _base_headers(self) -> dict[str, str]:
        """Return request headers extended with dynamic per-instance values."""
        offset = -time.timezone if time.daylight == 0 else -time.altzone
        return {
            **HEADERS,
            "x-rangers-id": self._rangers_id,
            "x-client-timezone-offset": str(offset),
        }

    async def open(self) -> None:
        """Open the underlying ``aiohttp.ClientSession``."""
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(enable_cleanup_closed=True)
        )

    async def close(self) -> None:
        """Close the underlying ``aiohttp.ClientSession`` if it is open."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "_BaseClient":
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def create_chat_session(
        self,
        token: str,
        timeout: Optional[float] = None,
    ) -> str:
        """Create a new DeepSeek chat session and return its id.

        Args:
            token: Valid bearer token.
            timeout: Per-call timeout override; falls back to the instance default.

        Returns:
            Chat session id string.

        Raises:
            DeepSeekError: If the API returns a non-zero status code.
        """
        assert self._session is not None, "Session not started"
        effective = self._effective_timeout(timeout)

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
        target_path: str = COMPLETION_PATH,
        timeout: Optional[float] = None,
    ) -> dict:
        """Fetch a fresh proof-of-work challenge from the server.

        Args:
            token: Valid bearer token.
            target_path: API path the PoW will be consumed by.
            timeout: Per-call timeout override; falls back to the instance default.

        Returns:
            Challenge dict with ``salt``, ``expire_at``, ``difficulty``,
            ``challenge``, ``algorithm``, and ``signature``.

        Raises:
            DeepSeekError: If the API returns a non-zero status code.
        """
        assert self._session is not None, "Session not started"
        effective = self._effective_timeout(timeout)

        async with self._session.post(
            BASE_URL + "/api/v0/chat/create_pow_challenge",
            json={"target_path": target_path},
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
        target_path: str = COMPLETION_PATH,
        timeout: Optional[float] = None,
    ) -> str:
        """Solve the PoW challenge and return the base64-encoded header value.

        Fetches a fresh challenge, calls the solver, and encodes the solution
        as a base64 JSON blob suitable for the ``X-DS-PoW-Response`` header.

        Args:
            token: Valid bearer token used to fetch the challenge.
            target_path: API path the PoW will be consumed by.
            timeout: Per-call timeout override; falls back to the instance default.

        Returns:
            Base64-encoded JSON string.

        Raises:
            DeepSeekError: If the solver does not converge within the difficulty limit.
        """
        ch = await self._get_pow_challenge(token, target_path, timeout)
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

        return base64.b64encode(payload).decode()
