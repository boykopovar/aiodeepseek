from __future__ import annotations

import logging
import sys

from aiodeepseek.http._config import _DEV_MODE, _LOG_POW_TIME

_log: logging.Logger = logging.getLogger("aiodeepseek")
_log.propagate = False

_handler: logging.Handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("[DEV] %(message)s"))

if _DEV_MODE:
    _handler.setLevel(logging.DEBUG)
    _log.setLevel(logging.DEBUG)
    _log.addHandler(_handler)

elif _LOG_POW_TIME:
    _handler.setLevel(logging.INFO)
    _log.setLevel(logging.INFO)
    _log.addHandler(_handler)

def _log_str(msg: str) -> None:
    _log.info(msg)

def _log_request(label: str, url: str, headers: dict, body: object = None) -> None:
    """Emit a structured DEBUG entry for an outgoing HTTP request.

    Args:
        label: Short tag shown in the ``>>>`` banner (e.g. ``"REQUEST"``).
        url: Full request URL.
        headers: Headers dict that will be emitted key-by-key.
        body: Optional body object printed with :func:`repr`.
    """
    if not _DEV_MODE:
        return
    _log.debug(">>> %s", label)
    _log.debug("    URL    : %s", url)
    _log.debug("    HEADERS:")
    for k, v in headers.items():
        _log.debug("      %s: %s", k, str(v)[:200])
    if body is not None:
        _log.debug("    BODY   : %r", body)


def _log_response(label: str, status: int, headers: object, raw: str) -> None:
    """Emit a structured DEBUG entry for an incoming HTTP response.

    Logs status, every response header, and the full raw body text immediately
    — before any JSON parsing — so nothing is lost when parse errors occur.

    Args:
        label: Short tag shown in the ``<<<`` banner (e.g. ``"RESPONSE"``).
        status: HTTP status code.
        headers: Mapping of response headers (``aiohttp.CIMultiDictProxy`` or plain dict).
        raw: Raw response body string.
    """
    if not _DEV_MODE:
        return
    _log.debug("<<< %s  status=%s", label, status)
    _log.debug("    HEADERS:")
    for k, v in headers.items():
        _log.debug("      %s: %s", k, v)
    _log.debug("    BODY:")
    _log.debug("%s", raw)