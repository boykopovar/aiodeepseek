from __future__ import annotations

from dataclasses import dataclass
from typing import Optional



@dataclass(frozen=True)
class DeepSeekTurnResult:
    """The complete result of a single DeepSeek conversation turn.

    Attributes:
        text: The assistant's full response text.
        session_id: DeepSeek chat session identifier.
        message_id: DeepSeek message identifier for this assistant turn.
            Pass as ``parent_message_id`` in the next turn to continue
            the conversation thread. May be ``None`` if the server did
            not emit a message id for this turn.
    """

    text: str
    session_id: str
    message_id: Optional[str] = None


class UploadedImage:
    """Returned by :meth:`~aiodeepseek.DeepSeekClient.upload_image`.

    Pass to :meth:`~aiodeepseek.DeepSeekClient.ask` or
    :meth:`~aiodeepseek.DeepSeekClient.ask_stream` (and their
    :class:`~aiodeepseek.Conversation` counterparts) to attach the
    already-uploaded image to the next message without re-uploading.

    Attributes:
        file_id: Opaque file identifier returned by the upload endpoint.
            Sent as the sole entry in ``ref_file_ids`` of the completion
            request.
        size_bytes: Size of the uploaded file in bytes.
        width: Image width in pixels (measured locally before upload).
        height: Image height in pixels (measured locally before upload).
    """

    def __init__(
        self,
        file_id: str,
        size_bytes: int,
        width: int,
        height: int,
    ) -> None:
        self.file_id = file_id
        self.size_bytes = size_bytes
        self.width = width
        self.height = height

    def __repr__(self) -> str:
        return (
            f"UploadedImage(file_id={self.file_id!r}, "
            f"size_bytes={self.size_bytes}, "
            f"width={self.width}, height={self.height})"
        )
