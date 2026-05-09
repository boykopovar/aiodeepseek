from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple, Type


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


class PowNotSolvedError(DeepSeekError):
    """Raised when the PoW solver fails to find a nonce within the difficulty limit.

    Attributes:
        salt: Salt string received from the server.
        expire_at: Challenge expiry timestamp.
        difficulty: Maximum number of iterations the solver attempted.
        challenge: Expected hash digest as a hex string.
        algorithm: Hash algorithm name, e.g. ``"DeepSeekHashV1"``.
        signature: Challenge signature from the server.
    """

    def __init__(
            self,
            salt: str,
            expire_at: str,
            difficulty: int,
            challenge: str,
            algorithm: str,
            signature: str
    ) -> None:
        super().__init__(f"PoW not solved within difficulty limit ({difficulty})")
        self.salt = salt
        self.expire_at = expire_at
        self.difficulty = difficulty
        self.challenge = challenge
        self.algorithm = algorithm
        self.signature = signature


class DeepSeekAPIError(DeepSeekError):
    """Raised when the DeepSeek JSON API returns a non-zero ``code`` field.

    Attributes:
        code: The integer error code from the ``code`` field of the response.
        data: The full parsed response dict.
    """

    def __init__(self, message: str, code: int, data: Optional[dict] = None) -> None:
        super().__init__(message)
        self.code: int = code
        self.data: Optional[dict] = data


class DeepSeekBizError(DeepSeekError):
    """Raised when the API returns ``code=0`` but a non-zero ``biz_code``.

    Attributes:
        biz_code: The integer error code from the ``biz_code`` field.
        biz_msg: The raw ``biz_msg`` string from the response.
        data: The full parsed response dict.
    """

    def __init__(self, message: str, biz_code: int, biz_msg: str, data: Optional[dict] = None) -> None:
        super().__init__(message)
        self.biz_code: int = biz_code
        self.biz_msg: str = biz_msg
        self.data: Optional[dict] = data

class EmptyUploadedFileError(DeepSeekError):
    """Raised when DeepSeek marks an uploaded file as invalid or empty."""

_API_ERROR_REGISTRY: Dict[int, Type[DeepSeekAPIError]] = {}
_API_ERROR_SPECIFIC_REGISTRY: List[Tuple[int, str, Type[DeepSeekAPIError]]] = []
_BIZ_ERROR_REGISTRY: Dict[int, Type[DeepSeekBizError]] = {}
_BIZ_ERROR_SPECIFIC_REGISTRY: List[Tuple[int, str, Type[DeepSeekBizError]]] = []
_SSE_HINT_REGISTRY: List[Tuple[str, Type[DeepSeekError]]] = []


def _register_api_error(code: int) -> Callable[[Type[DeepSeekAPIError]], Type[DeepSeekAPIError]]:
    """Decorator that registers an exception class for a specific API error code.

    Args:
        code: The integer ``code`` value from the DeepSeek JSON response that
            should map to the decorated exception class.
    """
    def decorator(cls: Type[DeepSeekAPIError]) -> Type[DeepSeekAPIError]:
        _API_ERROR_REGISTRY[code] = cls
        return cls
    return decorator


def _register_api_error_specific(
    code: int,
    msg_pattern: str,
) -> Callable[[Type[DeepSeekAPIError]], Type[DeepSeekAPIError]]:
    """Decorator that registers an exception class for a specific API error code
    combined with a message substring match.

    Args:
        code: The integer ``code`` value from the DeepSeek JSON response.
        msg_pattern: Lowercase substring that must appear in ``msg`` field.
    """
    def decorator(cls: Type[DeepSeekAPIError]) -> Type[DeepSeekAPIError]:
        _API_ERROR_SPECIFIC_REGISTRY.append((code, msg_pattern, cls))
        return cls
    return decorator


def _register_biz_error(biz_code: int) -> Callable[[Type[DeepSeekBizError]], Type[DeepSeekBizError]]:
    """Decorator that registers an exception class for a specific ``biz_code`` value.

    Used for responses where the top-level ``code`` is 0 but ``biz_code`` signals
    an application-level error.

    Args:
        biz_code: The integer ``biz_code`` value that should map to the decorated
            exception class.
    """
    def decorator(cls: Type[DeepSeekBizError]) -> Type[DeepSeekBizError]:
        _BIZ_ERROR_REGISTRY[biz_code] = cls
        return cls
    return decorator


def _register_biz_error_specific(
    biz_code: int,
    biz_msg_pattern: str,
) -> Callable[[Type[DeepSeekBizError]], Type[DeepSeekBizError]]:
    """Decorator that registers an exception class for a specific ``biz_code``
    combined with a ``biz_msg`` substring match.

    Args:
        biz_code: The integer ``biz_code`` value from the DeepSeek JSON response.
        biz_msg_pattern: Lowercase substring that must appear in the ``biz_msg`` field.
    """
    def decorator(cls: Type[DeepSeekBizError]) -> Type[DeepSeekBizError]:
        _BIZ_ERROR_SPECIFIC_REGISTRY.append((biz_code, biz_msg_pattern, cls))
        return cls
    return decorator


def _register_sse_hint(pattern: str) -> Callable[[Type[DeepSeekError]], Type[DeepSeekError]]:
    """Decorator that registers an exception class for an SSE hint content pattern.

    Args:
        pattern: Lowercase substring that must appear in the hint ``content`` field
            to trigger the decorated exception class.
    """
    def decorator(cls: Type[DeepSeekError]) -> Type[DeepSeekError]:
        _SSE_HINT_REGISTRY.append((pattern, cls))
        return cls
    return decorator


@_register_api_error(40003)
class AuthorizationError(DeepSeekAPIError):
    """Raised when the bearer token is invalid or expired (API code 40003)."""


@_register_api_error_specific(40003, "invalid token")
class InvalidToken(AuthorizationError):
    """Raised when the bearer token is explicitly rejected as invalid
    (API code 40003 with ``'invalid token'`` in the message)."""


@_register_biz_error_specific(2, "password_or_user_name_is_wrong")
class WrongCredentialsError(DeepSeekBizError):
    """Raised when login fails due to incorrect e-mail or password
    (``biz_code=2``, ``biz_msg`` contains ``PASSWORD_OR_USER_NAME_IS_WRONG``)."""


@_register_sse_hint("vision is temporarily unavailable")
class VisionUnavailableError(DeepSeekError):
    """Raised when DeepSeek vision processing is temporarily unavailable."""

@_register_biz_error_specific(9, "invalid ref file id")
class InvalidRefFileIdError(DeepSeekBizError):
    """Raised when an uploaded file cannot be attached to a chat request.

    Usually indicates that the uploaded file is invalid, empty, still processing,
    or rejected by DeepSeek file parsing backend.
    """

