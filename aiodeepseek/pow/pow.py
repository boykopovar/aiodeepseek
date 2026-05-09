from __future__ import annotations

from typing import Optional

from aiodeepseek.http._config import _DEV_MODE, _LOG_POW_TIME
import time

from aiodeepseek.log import _log_str
from aiodeepseek.pow._pow import solve as _cpp

def solve_pow(base: str, challenge_hex: str, difficulty: int) -> int:
    """Brute-force a proof-of-work nonce for the DeepSeek API.

    Uses the compiled C++ extension for performance.
    Falls back to pure Python if the extension is unavailable.

    Args:
        base: Salt string prefix shared by the server.
        challenge_hex: Expected hash digest as a hex string.
        difficulty: Maximum number of nonce values to try.

    Returns:
        The first valid nonce, or ``-1`` if none was found.
    """

    total_start: Optional[float] = None
    if _LOG_POW_TIME or _DEV_MODE:
        total_start = time.perf_counter()

    nonce: int = _cpp(base, challenge_hex, difficulty)

    if total_start is not None:
        _log_str(
            f"[pow done {(time.perf_counter() - total_start) * 1000:.2f} ms]: "
            f"{base, challenge_hex, difficulty}"
        )
    return nonce

__all__ = ["solve_pow"]
