from __future__ import annotations

from typing import Optional


class AioDeepSeekError(Exception):
    """Base exception AioDeepSeek"""



class DeepSeekError(AioDeepSeekError):
    """Raised when a DeepSeek API request fails.

    Attributes:
        status: The HTTP status code returned by the server, or ``None`` if
            the error did not originate from an HTTP response.
    """

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status: Optional[int] = status
