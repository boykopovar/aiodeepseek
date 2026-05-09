from pathlib import Path
from typing import AsyncIterator, Optional, Union

from aiodeepseek.conversation import Conversation
from aiodeepseek.types.enums import ModelType
from aiodeepseek.types.models.classes import DeepSeekTurnResult, UploadedImage
from aiodeepseek.types.models._model_utils import load_image
from aiodeepseek.clients.files import _FilesClient


class DeepSeekClient(_FilesClient):
    """Async client for the DeepSeek iOS API.

    Inherits the full class hierarchy:
    ``_BaseClient → _AuthClient → _ChatClient → _FilesClient → DeepSeekClient``.

    Accepts either a pre-obtained token or credentials (email + password).
    When credentials are provided the token is fetched automatically on
    :meth:`open`::

        async with DeepSeekClient(token=\"...\") as client:
            result = await client.ask(\"Hello!\")

        async with DeepSeekClient(email=\"me@x.com\", password=\"secret\") as client:
            result = await client.ask(\"Hello!\")

    Args:
        email: DeepSeek account e-mail. Required when *token* is not given.
        password: DeepSeek account password. Required when *token* is not given.
        token: Pre-obtained bearer token. Skips login when provided.
        model: Default model string sent to the API.
        device_id: Optional stable device identifier.
        timeout: Default total timeout in seconds. ``None`` means no timeout.
    """

    def __init__(
        self,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        model: ModelType = ModelType.DEFAULT,
        device_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        if token is None and (email is None or password is None):
            raise ValueError("Provide either token or both email and password")

        super().__init__(timeout=timeout, device_id=device_id)

        self._email = email
        self._password = password
        self._token: Optional[str] = token
        self._default_model = model
        self._session_id: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        """The current bearer token, or ``None`` if not yet authenticated."""
        return self._token

    async def open(self) -> None:
        """Open the HTTP session and authenticate if needed."""
        await super().open()

        if self._token is None:
            self._token = await self.fetch_token(
                self._email,
                self._password,
                self._device_id,
            )

        self._session_id = await self.create_chat_session(self._token)

    async def __aenter__(self) -> "DeepSeekClient":
        await self.open()
        return self

    async def upload_image(
        self,
        source: Union[bytes, Path],
        *,
        filename: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> UploadedImage:
        """Upload a PNG or JPEG image and return an :class:`~aiodeepseek.types.models.UploadedImage`.

        The returned object can be passed directly to :meth:`ask` or
        :meth:`ask_stream` to attach the image without re-uploading it.

        Args:
            source: A :class:`pathlib.Path` to a PNG/JPEG file, or raw image bytes.
            filename: Override the filename sent in the multipart request.
                Defaults to the file's name for paths, or ``"image.jpg"`` /
                ``"image.png"`` for raw bytes based on detected format.
            timeout: Per-call timeout override; falls back to the client default.

        Returns:
            :class:`~aiodeepseek.types.models.UploadedImage` ready to attach
            to the next :meth:`ask` / :meth:`ask_stream` call.

        Raises:
            ValueError: If the image format is not PNG or JPEG.
            DeepSeekError: On HTTP or API error.
        """
        data, mime, width, height = load_image(source)

        if filename is None:
            if isinstance(source, Path):
                filename = source.name
            else:
                filename = "image.png" if mime == "image/png" else "image.jpg"

        return await self._upload_image(
            self._token,
            data=data,
            mime_type=mime,
            width=width,
            height=height,
            filename=filename,
            model=self._default_model,
            timeout=timeout if timeout is not None else self._timeout,
        )

    async def ask(
        self,
        prompt: str,
        *,
        image: Optional[Union[UploadedImage, bytes, Path]] = None,
        model: Optional[ModelType] = None,
        timeout: Optional[float] = None,
        parent_message_id: Optional[str] = None,
    ) -> DeepSeekTurnResult:
        """Send *prompt* and return the complete assistant reply.

        Args:
            prompt: The user message to send.
            image: An :class:`~aiodeepseek.types.models.UploadedImage` to attach.
                Obtain one via :meth:`upload_image`.
            model: Override the instance-level default model for this turn.
            timeout: Override the client-level default timeout for this call.
            parent_message_id: Message id of the previous assistant turn.

        Returns:
            :class:`DeepSeekTurnResult` with full response text, session id, and
            the assistant message id for this turn.
        """
        resolved_model = model if model is not None else self._default_model
        text = ""
        message_id: Optional[str] = None

        if image is not None and (isinstance(image, bytes) or isinstance(image, Path)):
            image = await self.upload_image(image)

        async for cumulative, mid in self.stream_chat(
            self._token,
            self._session_id,
            prompt,
            resolved_model,
            timeout,
            parent_message_id=parent_message_id,
            image=image,
        ):
            text = cumulative
            if mid is not None:
                message_id = mid

        return DeepSeekTurnResult(
            text=text,
            session_id=self._session_id,
            message_id=message_id,
        )

    async def ask_stream(
        self,
        prompt: str,
        *,
        image: Optional[Union[UploadedImage, bytes, Path]] = None,
        model: Optional[ModelType] = None,
        timeout: Optional[float] = None,
        parent_message_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream the assistant reply as cumulative text chunks.

        Each yielded string is the full response accumulated so far.
        The last yielded value is the complete reply.

        Args:
            prompt: The user message to send.
            image: An :class:`~aiodeepseek.types.models.UploadedImage` to attach.
            model: Override the instance-level default model for this turn.
            timeout: Override the client-level default timeout for this call.
            parent_message_id: Message id of the previous assistant turn.

        Yields:
            Cumulative assistant text — each value is the full response so far.
        """
        resolved_model = model if model is not None else self._default_model

        if image is not None and (isinstance(image, bytes) or isinstance(image, Path)):
            image = await self.upload_image(image)

        async for cumulative, _ in self.stream_chat(
            self._token,
            self._session_id,
            prompt,
            resolved_model,
            timeout,
            parent_message_id=parent_message_id,
            image=image,
        ):
            yield cumulative

    def new_conversation(self) -> Conversation:
        """Return a new :class:`~aiodeepseek.Conversation` bound to this client.

        The returned object tracks ``parent_message_id`` automatically across
        turns so that each reply is threaded onto the previous one.
        """
        return Conversation(self)
