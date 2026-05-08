from __future__ import annotations

from typing import Optional

from aiodeepseek.http._config import _DEV_MODE
import time

try:
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
        if _DEV_MODE:
            print(f"pow task: {base, challenge_hex, difficulty}")
            total_start = time.perf_counter()

        nonce: int = _cpp(base, challenge_hex, difficulty)

        if total_start is not None:
            print(f"\n[pow done {(time.perf_counter() - total_start) * 1000:.2f} ms]")
        return nonce

except ImportError:
    raise
    from aiodeepseek.pow._pow_py import solve_pow as solve_pow  # noqa: F401

__all__ = ["solve_pow"]
