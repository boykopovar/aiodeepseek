from __future__ import annotations

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
        return _cpp(base, challenge_hex, difficulty)

except ImportError:
    raise
    from aiodeepseek.pow._pow_py import solve_pow as solve_pow  # noqa: F401

__all__ = ["solve_pow"]
