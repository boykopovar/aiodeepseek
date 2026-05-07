from __future__ import annotations

from typing import Optional, Union

_MESSAGE_ID_PATHS = frozenset({"message_id", "chat_message_id", "id", "response_message_id"})


def _extract_fragment(event: dict) -> str:
    """Extract a text fragment from a single DeepSeek SSE event dict.

    The stream uses at least three event shapes to carry text:
    an ``{"o": "APPEND", "v": "<fragment>"}`` patch operation, a bare
    ``{"v": "<fragment>"}`` shorthand with no operation or path keys, and the
    initial ``{"v": {"response": {"fragments": [...]}}}`` bulk object that
    opens each turn.

    Args:
        event: Parsed JSON object from one SSE ``data:`` line.

    Returns:
        The text fragment carried by this event, or an empty string if the
        event carries no text.
    """
    o = event.get("o", "")
    v = event.get("v")

    if o == "APPEND" and isinstance(v, str):
        return v

    if v is not None and "p" not in event and "o" not in event and isinstance(v, str):
        return v

    if isinstance(v, dict) and "response" in v:
        fragments = v["response"].get("fragments", [])
        return "".join(f.get("content", "") for f in fragments)

    return ""


def _extract_message_id(event: dict) -> Optional[str]:
    """Extract the assistant message id from a single DeepSeek SSE event dict.

    The stream delivers the message id in several different shapes depending
    on the event type.  The ``ready`` event carries it as a top-level
    ``response_message_id`` integer.  The initial bulk response object nests it
    at ``v["response"]["message_id"]``.  Hypothetical JSON-patch events use
    ``{"o": "SET", "p": "/message_id", "v": <id>}`` where the path may be an
    absolute JSON-pointer such as ``/chat_session_message/0/message_id``.
    All numeric ids are normalised to strings before being returned.

    This API is reverse-engineered from the iOS client and has no public
    schema contract, so all four lookup strategies are retained to guard
    against format drift.

    Args:
        event: Parsed JSON object from one SSE ``data:`` line.

    Returns:
        The message id as a string, or ``None`` if this event does not carry
        one.
    """
    o = event.get("o", "")
    p = event.get("p", "")
    v = event.get("v")

    p_tail = p.rsplit("/", 1)[-1] if p else ""
    if o == "SET" and (p in _MESSAGE_ID_PATHS or p_tail in _MESSAGE_ID_PATHS):
        if isinstance(v, str) and v:
            return v
        if isinstance(v, int):
            return str(v)

    for key in _MESSAGE_ID_PATHS:
        candidate = event.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, int):
            return str(candidate)

    if isinstance(v, dict):
        for key in _MESSAGE_ID_PATHS:
            candidate = v.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
            if isinstance(candidate, int):
                return str(candidate)

        inner = v.get("response")
        if isinstance(inner, dict):
            for key in _MESSAGE_ID_PATHS:
                candidate = inner.get(key)
                if isinstance(candidate, str) and candidate:
                    return candidate
                if isinstance(candidate, int):
                    return str(candidate)

    return None


def _coerce_message_id(value: Optional[str]) -> Optional[Union[str, int]]:
    """Return *value* as an int when it is a pure numeric string, otherwise as-is.

    The DeepSeek API expects ``parent_message_id`` as an integer when the id
    originated from an integer SSE field, so the round-trip must preserve the
    original type.

    Args:
        value: Message id string, or ``None``.

    Returns:
        ``None``, the original string, or the integer equivalent of the string.
    """
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return value
