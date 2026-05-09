from __future__ import annotations

from aiodeepseek.types.exceptions._classes import (
    DeepSeekAPIError,
    DeepSeekBizError,
    DeepSeekError,
    _API_ERROR_REGISTRY,
    _API_ERROR_SPECIFIC_REGISTRY,
    _BIZ_ERROR_REGISTRY,
    _BIZ_ERROR_SPECIFIC_REGISTRY,
    _SSE_HINT_REGISTRY,
)


def raise_for_api_response(context: str, data: dict) -> None:
    """Raise the appropriate exception for a non-zero DeepSeek API response.

    When the top-level ``code`` is non-zero, checks ``_API_ERROR_SPECIFIC_REGISTRY``
    for a (code, msg_pattern) match, then falls back to ``_API_ERROR_REGISTRY`` for a
    code-only match, and finally falls back to :class:`DeepSeekAPIError`.

    When ``code`` is 0 but the nested ``biz_code`` is non-zero, checks
    ``_BIZ_ERROR_SPECIFIC_REGISTRY`` for a (biz_code, biz_msg_pattern) match, then
    ``_BIZ_ERROR_REGISTRY`` for a biz_code-only match, and finally falls back to
    :class:`DeepSeekBizError`.

    Args:
        context: Short label included in the exception message to identify the
            failing operation (e.g. ``"create_session"``).
        data: Full parsed JSON response body containing at least a ``code`` field.

    Raises:
        DeepSeekAPIError: When top-level ``code`` is non-zero.
        DeepSeekBizError: When top-level ``code`` is 0 but ``biz_code`` is non-zero.
    """
    code: int = data.get("code", -1)
    msg: str = data.get("msg", "")

    if code != 0:
        msg_lower = msg.lower()

        exc_cls = None
        for ec, pattern, specific_cls in _API_ERROR_SPECIFIC_REGISTRY:
            if ec == code and pattern in msg_lower:
                exc_cls = specific_cls
                break

        if exc_cls is None:
            exc_cls = _API_ERROR_REGISTRY.get(code, DeepSeekAPIError)

        raise exc_cls(
            f"{context} failed: code={code} msg={msg!r}",
            code=code,
            data=data,
        )

    nested = data.get("data") or {}
    biz_code: int = nested.get("biz_code", 0)
    biz_msg: str = nested.get("biz_msg", "")

    if biz_code != 0:
        biz_msg_lower = biz_msg.lower()

        biz_exc_cls = None
        for bc, pattern, specific_cls in _BIZ_ERROR_SPECIFIC_REGISTRY:
            if bc == biz_code and pattern in biz_msg_lower:
                biz_exc_cls = specific_cls
                break

        if biz_exc_cls is None:
            biz_exc_cls = _BIZ_ERROR_REGISTRY.get(biz_code, DeepSeekBizError)

        raise biz_exc_cls(
            f"{context} failed: biz_code={biz_code} biz_msg={biz_msg!r}",
            biz_code=biz_code,
            biz_msg=biz_msg,
            data=data,
        )


def raise_for_sse_hint(event: dict) -> None:
    """Raise the appropriate exception for a DeepSeek SSE ``hint`` error event.

    Called when an SSE stream emits ``event: hint`` with ``{"type": "error", ...}``.
    Checks the ``content`` field against known error patterns and raises a
    registered exception; falls back to :class:`DeepSeekError` for unrecognised hints.

    Args:
        event: Parsed JSON object from the hint ``data:`` line.

    Raises:
        DeepSeekError: Always — either a registered hint subclass or the base class.
    """
    content: str = event.get("content", "")
    finish_reason: str = event.get("finish_reason", "")
    content_lower = content.lower()

    for pattern, exc_cls in _SSE_HINT_REGISTRY:
        if pattern in content_lower:
            raise exc_cls(content)

    raise DeepSeekError(
        f"SSE hint error: finish_reason={finish_reason!r} content={content!r}"
    )
