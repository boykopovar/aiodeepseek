from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Optional

from aiodeepseek.types.models import DeepSeekTurnResult

if TYPE_CHECKING:
    from aiodeepseek.client import DeepSeekClient


class Conversation:
    """Stateful multi-turn chat wrapper around :class:`~aiodeepseek.DeepSeekClient`.

    Tracks the ``parent_message_id`` across turns so each reply is threaded
    onto the previous assistant message within the same session.

    Obtained via :meth:`~aiodeepseek.DeepSeekClient.new_conversation`::

        async with DeepSeekClient(token="...") as client:
            chat = client.new_conversation()
            await chat.ask("Hi!")
            await chat.ask("Tell me more.")

    Args:
        client: The :class:`~aiodeepseek.DeepSeekClient` to delegate requests to.
    """

    def __init__(self, client: "DeepSeekClient") -> None:
        self._client = client
        self._parent_message_id: Optional[str] = None

    @property
    def parent_message_id(self) -> Optional[str]:
        """Last assistant message id, or ``None`` before the first turn."""
        return self._parent_message_id

    def _apply_result(self, result: DeepSeekTurnResult) -> None:
        if result.message_id is not None:
            self._parent_message_id = result.message_id

    async def ask(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """Send *prompt*, update conversation state, and return the reply text.

        Args:
            prompt: The user message to send.
            model: Override the client-level default model for this turn.
            timeout: Override the client-level default timeout for this call.
                ``None`` falls back to the client default.

        Returns:
            The assistant's full response as a plain string.
        """
        result = await self._client.ask(
            prompt,
            model=model,
            timeout=timeout,
            parent_message_id=self._parent_message_id,
        )
        self._apply_result(result)
        return result.text

    async def ask_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Stream the reply as cumulative text chunks and update conversation state.

        Conversation state is updated automatically once the stream is
        fully consumed.

        Args:
            prompt: The user message to send.
            model: Override the client-level default model for this turn.
            timeout: Override the client-level default timeout for this call.
                ``None`` falls back to the client default.

        Yields:
            Cumulative assistant text — each value is the full response so far.
        """
        resolved_model = model if model is not None else self._client._default_model
        last_message_id: Optional[str] = None

        async for cumulative, mid in self._client._http.stream_chat(
            self._client._token,
            self._client._session_id,
            prompt,
            resolved_model,
            timeout,
            parent_message_id=self._parent_message_id,
        ):
            if mid is not None:
                last_message_id = mid
            yield cumulative

        if last_message_id is not None:
            self._parent_message_id = last_message_id
