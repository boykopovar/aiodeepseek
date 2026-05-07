from dataclasses import dataclass


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
    """

    text: str
    session_id: str


class UploadedImage:
    """Returned by upload_image; pass to ask or ask_stream to skip re-uploading."""

    def __init__(
        self,
        asset_pointer: str,
        size_bytes: int,
        width: int,
        height: int,
    ) -> None:
        self.asset_pointer = asset_pointer
        self.size_bytes = size_bytes
        self.width = width
        self.height = height
