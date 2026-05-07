from __future__ import annotations

from typing import AsyncIterator, Optional

import aiohttp

from aiodeepseek.http import _DeepSeekSession
from aiodeepseek.types.models import DeepSeekTurnResult


class DeepSeekClient:
    """Async client for the DeepSeek iOS API.

    Accepts either a pre-obtained token or credentials (email + password).
    When credentials are provided the token is fetched automatically on
    :meth:`open`::

        async with DeepSeekClient(token="...") as client:
            result = await client.ask("Hello!")

        async with DeepSeekClient(email="me@x.com", password="secret") as client:
            result = await client.ask("Hello!")

    Args:
        email: DeepSeek account e-mail. Required when *token* is not given.
        password: DeepSeek account password. Required when *token* is not given.
        token: Pre-obtained bearer token. Skips login when provided.
        model: Default model string sent to the API.
        timeout: Default total timeout in seconds. ``None`` means no timeout.
    """

    def __init__(
        self,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        model: str = "default",
        timeout: Optional[float] = None,
    ) -> None:
        if token is None and (email is None or password is None):
            raise ValueError("Provide either token or both email and password")

        self._email = email
        self._password = password
        self._token: Optional[str] = token
        self._default_model = model
        self._default_timeout = timeout
        self._http = _DeepSeekSession(timeout=timeout)
        self._session_id: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        """The current bearer token, or ``None`` if not yet authenticated."""
        return self._token

    @classmethod
    async def fetch_token(cls, email: str, password: str) -> str:
        """Obtain a bearer token from the DeepSeek API using credentials.

        This standalone helper does not require an open client instance.
        The returned token can be stored and reused to avoid repeated logins.

        Args:
            email: DeepSeek account e-mail.
            password: DeepSeek account password.

        Returns:
            A bearer token string.
        """
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            return await _DeepSeekSession.fetch_token(session, email, password)

    async def open(self) -> None:
        await self._http.open()

        if self._token is None:
            self._token = await _DeepSeekSession.fetch_token(
                self._http._session, self._email, self._password
            )

        self._session_id = await self._http.create_chat_session(self._token)

    async def close(self) -> None:
        await self._http.close()

    async def __aenter__(self) -> "DeepSeekClient":
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def ask(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> DeepSeekTurnResult:
        """Send *prompt* and return the complete assistant reply.

        Args:
            prompt: The user message to send.
            model: Override the instance-level default model for this turn.
            timeout: Override the client-level default timeout for this call.
                ``None`` falls back to the client default.

        Returns:
            :class:`DeepSeekTurnResult` with the full response text and the
            current session id.
        """
        resolved_model = model if model is not None else self._default_model
        text = ""

        async for cumulative in self._http.stream_chat(
            self._token, self._session_id, prompt, resolved_model, timeout
        ):
            text = cumulative

        return DeepSeekTurnResult(text=text, session_id=self._session_id)

    async def ask_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Stream the assistant reply as cumulative text chunks.

        Each yielded string is the full response accumulated so far.
        The last yielded value is the complete reply.

        Args:
            prompt: The user message to send.
            model: Override the instance-level default model for this turn.
            timeout: Override the client-level default timeout for this call.
                ``None`` falls back to the client default.

        Yields:
            Cumulative assistant text — each value is the full response so far.
        """
        resolved_model = model if model is not None else self._default_model

        async for cumulative in self._http.stream_chat(
            self._token, self._session_id, prompt, resolved_model, timeout
        ):
            yield cumulative
