import struct

_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]

_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]

_M64 = (1 << 64) - 1


def _rot(x: int, n: int) -> int:
    """Rotate a 64-bit integer left by *n* bits.

    Args:
        x: 64-bit integer value.
        n: Number of bits to rotate left.

    Returns:
        Rotated 64-bit integer.
    """
    return ((x << n) | (x >> (64 - n))) & _M64


def _keccak_f(state: list) -> list:
    """Apply the Keccak-f[1600] permutation to *state*.

    Args:
        state: List of 25 64-bit lane values.

    Returns:
        New list of 25 permuted 64-bit lane values.
    """
    A = state[:]

    for rc in _RC[1:]:
        C = [A[x] ^ A[x + 5] ^ A[x + 10] ^ A[x + 15] ^ A[x + 20] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rot(C[(x + 1) % 5], 1) for x in range(5)]
        A = [A[x + 5 * y] ^ D[x] for y in range(5) for x in range(5)]

        B = [0] * 25
        for y in range(5):
            for x in range(5):
                B[y + 5 * ((2 * x + 3 * y) % 5)] = _rot(A[x + 5 * y], _ROT[x][y])

        A = [
            B[x + 5 * y] ^ (~B[(x + 1) % 5 + 5 * y] & _M64 & B[(x + 2) % 5 + 5 * y])
            for y in range(5)
            for x in range(5)
        ]
        A[0] ^= rc

    return A


def _sha3_256(msg: bytes) -> bytes:
    """Compute a SHA3-256-like (Keccak) digest of *msg*.

    Args:
        msg: Input bytes to hash.

    Returns:
        32-byte digest.
    """
    R = 136
    pad = R - len(msg) % R
    m = msg + (b"\x86" if pad == 1 else b"\x06" + b"\x00" * (pad - 2) + b"\x80")

    S = [0] * 25
    for i in range(0, len(m), R):
        for j, v in enumerate(struct.unpack_from("<17Q", m, i)):
            S[j] ^= v
        S = _keccak_f(S)

    return struct.pack("<4Q", S[0], S[1], S[2], S[3])


def solve_pow(base: str, challenge_hex: str, difficulty: int) -> int:
    """Brute-force a proof-of-work nonce for the DeepSeek API.

    Iterates nonce values starting from 0 until
    ``sha3_256(base + str(nonce)) == bytes.fromhex(challenge_hex)``
    or *difficulty* attempts are exhausted.

    Args:
        base: Salt string prefix shared by the server.
        challenge_hex: Expected hash digest as a hex string.
        difficulty: Maximum number of nonce values to try.

    Returns:
        The first valid nonce, or ``-1`` if none was found.
    """
    target = bytes.fromhex(challenge_hex)
    b = base.encode()

    for nonce in range(difficulty):
        if _sha3_256(b + str(nonce).encode()) == target:
            return nonce

    return -1
