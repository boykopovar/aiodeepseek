def solve(
    base: str,
    challenge_hex: str,
    difficulty: int,
) -> int:
    """
    Brute-force a proof-of-work nonce.

    Args:
        base:
            Salt prefix string shared by the server.

        challenge_hex:
            Expected hash digest as a hexadecimal string.

        difficulty:
            Maximum number of nonce values to try.

    Returns:
        The first matching nonce, or ``-1`` if no solution is found.
    """
    ...