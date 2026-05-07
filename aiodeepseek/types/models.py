from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

ImageSource = Union[bytes, Path]


def _detect_mime(data: bytes) -> str:
    """Detect MIME type from raw image bytes.

    Args:
        data: Raw image bytes.

    Returns:
        ``"image/png"`` or ``"image/jpeg"``.

    Raises:
        ValueError: If the bytes do not match a supported format.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    raise ValueError("Unsupported image format; only PNG and JPEG are accepted")


def _png_dimensions(data: bytes) -> Tuple[int, int]:
    """Return ``(width, height)`` from PNG IHDR bytes 16-23.

    Args:
        data: Raw PNG bytes.

    Returns:
        A ``(width, height)`` tuple in pixels.
    """
    return struct.unpack(">II", data[16:24])


def _jpeg_dimensions(data: bytes) -> Tuple[int, int]:
    """Return ``(width, height)`` by scanning JPEG SOF markers.

    Args:
        data: Raw JPEG bytes.

    Returns:
        A ``(width, height)`` tuple in pixels, or ``(0, 0)`` if not found.
    """
    i = 2
    while i + 4 < len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h = struct.unpack(">H", data[i + 5 : i + 7])[0]
            w = struct.unpack(">H", data[i + 7 : i + 9])[0]
            return w, h
        segment_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        i += 2 + segment_len
    return 0, 0


def load_image(source: ImageSource) -> Tuple[bytes, str, int, int]:
    """Load image data from a path or raw bytes and extract metadata.

    Args:
        source: Either a :class:`pathlib.Path` to a PNG/JPEG file or raw
            image bytes.

    Returns:
        A ``(data, mime_type, width, height)`` tuple where *data* is the
        raw bytes, *mime_type* is ``"image/png"`` or ``"image/jpeg"``, and
        *width*/*height* are pixel dimensions.

    Raises:
        ValueError: If the image format is not recognised.
    """
    data: bytes = source.read_bytes() if isinstance(source, Path) else source
    mime = _detect_mime(data)
    w, h = _png_dimensions(data) if mime == "image/png" else _jpeg_dimensions(data)
    return data, mime, w, h


@dataclass(frozen=True)
class TurnResult:
    """The complete result of a single ChatGPT conversation turn.

    Attributes:
        text: The assistant's full response text.
        conversation_id: OpenAI conversation identifier.
        parent_message_id: The message-id of the assistant reply.
            Must be passed as ``parent_message_id`` in the next turn
            so the model has correct threading context.
    """

    text: str
    conversation_id: str
    parent_message_id: str


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
