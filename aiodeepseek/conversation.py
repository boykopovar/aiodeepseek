from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Optional, Union

from aiodeepseek.types.models.classes import DeepSeekTurnResult, UploadedImage

if TYPE_CHECKING:
    from aiodeepseek.clients.client import DeepSeekClient


class Conversation:
    """Stateful multi-turn chat wrapper around :class:`~aiodeepseek.DeepSeekClient`.

    Tracks ``parent_message_id`` across turns so each reply is threaded onto
    the previous assistant message within the same session.

    Obtained via :meth:`~aiodeepseek.DeepSeekClient.new_conversation`::

        async with DeepSeekClient(token="...") as client:
            chat = client.new_conversation()
            await chat.ask("Hi!")
            await chat.ask("Tell me more.")

    Args:
        client: The :class:`~aiodeepseek.DeepSeekClient` to delegate requests to.
    """

    def __init__(self, client: DeepSeekClient) -> None:
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
        image: Optional[Union[UploadedImage, bytes, Path]] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> DeepSeekTurnResult:
        """Send *prompt*, update conversation state, and return the reply text.

        Args:
            prompt: The user message to send.
            image: An :class:`~aiodeepseek.types.models.UploadedImage` to attach.
                Obtain one via :meth:`~aiodeepseek.DeepSeekClient.upload_image`.
            model: Override the client-level default model for this turn.
            timeout: Override the client-level default timeout for this call.

        Returns:
            The assistant's full response as a plain string.
        """
        if image is not None and (isinstance(image, bytes) or isinstance(image, Path)):
            image = await self._client.upload_image(image)

        result = await self._client.ask(
            prompt,
            image=image,
            model=model,
            timeout=timeout,
            parent_message_id=self._parent_message_id,
        )
        self._apply_result(result)
        return result

    async def ask_stream(
        self,
        prompt: str,
        *,
        image: Optional[Union[UploadedImage, bytes, Path]] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Stream the reply as cumulative text chunks and update conversation state.

        Conversation state is updated automatically once the stream is fully consumed.

        Args:
            prompt: The user message to send.
            image: An :class:`~aiodeepseek.types.models.UploadedImage` to attach.
            model: Override the client-level default model for this turn.
            timeout: Override the client-level default timeout for this call.

        Yields:
            Cumulative assistant text — each value is the full response so far.
        """
        resolved_model = model if model is not None else self._client._default_model
        last_message_id: Optional[str] = None

        if image is not None and (isinstance(image, bytes) or isinstance(image, Path)):
            image = await self._client.upload_image(image)

        async for cumulative, mid in self._client.stream_chat(
            self._client._token,
            self._client._session_id,
            prompt,
            resolved_model,
            timeout,
            parent_message_id=self._parent_message_id,
            image=image,
        ):
            if mid is not None:
                last_message_id = mid
            yield cumulative

        if last_message_id is not None:
            self._parent_message_id = last_message_id
