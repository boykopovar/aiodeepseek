import asyncio
import base64
import json
import os
import struct
import uuid
from typing import AsyncIterator

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://chat.deepseek.com"
COMPLETION_PATH = "/api/v0/chat/completion"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "DeepSeek/2 CFNetwork/1568.100.1 Darwin/24.0.0",
    "x-client-platform": "ios",
    "x-client-version": "2.0.4",
    "x-client-bundle-id": "com.deepseek.chat",
    "x-client-locale": "en_US",
    "x-client-timezone-offset": "3600",
}

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


def _rot(x, n):
    return ((x << n) | (x >> (64 - n))) & _M64


def _keccak_f23(A):
    A = A[:]

    for rc in _RC[1:]:
        C = [A[x] ^ A[x + 5] ^ A[x + 10] ^ A[x + 15] ^ A[x + 20] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rot(C[(x + 1) % 5], 1) for x in range(5)]

        A = [A[x + 5 * y] ^ D[x] for y in range(5) for x in range(5)]

        B = [0] * 25

        for y in range(5):
            for x in range(5):
                B[y + 5 * ((2 * x + 3 * y) % 5)] = _rot(A[x + 5 * y], _ROT[x][y])

        A = [
            B[x + 5 * y]
            ^ (~B[(x + 1) % 5 + 5 * y] & _M64 & B[(x + 2) % 5 + 5 * y])
            for y in range(5)
            for x in range(5)
        ]

        A[0] ^= rc

    return A


def _sha3_23(msg):
    R = 136

    pad = R - len(msg) % R

    m = msg + (
        b"\x86"
        if pad == 1
        else b"\x06" + b"\x00" * (pad - 2) + b"\x80"
    )

    S = [0] * 25

    for i in range(0, len(m), R):
        for j, v in enumerate(struct.unpack_from("<17Q", m, i)):
            S[j] ^= v

        S = _keccak_f23(S)

    return struct.pack("<4Q", S[0], S[1], S[2], S[3])


def solve_pow(base, challenge_hex, difficulty):
    target = bytes.fromhex(challenge_hex)
    b = base.encode()

    for nonce in range(difficulty):
        if _sha3_23(b + str(nonce).encode()) == target:
            return nonce

    return -1


async def login(session, email, password):
    async with session.post(
        BASE_URL + "/api/v0/users/login",
        json={
            "email": email,
            "password": password,
            "device_id": str(uuid.uuid4()).replace("-", ""),
            "os": "ios",
        },
        headers=HEADERS,
    ) as resp:
        data = await resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"login failed: {data}")

    token = data["data"]["biz_data"]["user"]["token"]

    print(f"[+] logged in, token: {token[:20]}...")

    return token


async def create_session(session, token):
    async with session.post(
        BASE_URL + "/api/v0/chat_session/create",
        json={"character_id": 1},
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    ) as resp:
        data = await resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"create_session failed: {data}")

    sid = data["data"]["biz_data"]["chat_session"]["id"]

    print(f"[+] session id: {sid}")

    return sid


async def get_pow_challenge(session, token):
    async with session.post(
        BASE_URL + "/api/v0/chat/create_pow_challenge",
        json={"target_path": COMPLETION_PATH},
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    ) as resp:
        data = await resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"pow challenge failed: {data}")

    ch = data["data"]["biz_data"]

    return ch.get("challenge", ch)


def _extract_token(event: dict) -> str:
    p = event.get("p", "")
    o = event.get("o", "")
    v = event.get("v")

    if o == "APPEND" and isinstance(v, str):
        return v

    if (
        v is not None
        and "p" not in event
        and "o" not in event
        and isinstance(v, str)
    ):
        return v

    if isinstance(v, dict) and "response" in v:
        fragments = v["response"].get("fragments", [])

        return "".join(f.get("content", "") for f in fragments)

    return ""


async def chat(
    session: aiohttp.ClientSession,
    token: str,
    session_id: str,
    prompt: str,
    model: str = "default",
) -> AsyncIterator[str]:
    ch = await get_pow_challenge(session, token)

    salt = ch["salt"]
    expire_at = ch["expire_at"]
    difficulty = int(ch["difficulty"])
    challenge_hex = ch["challenge"]

    print(f"[~] PoW diff={difficulty}, solving...")

    nonce = solve_pow(
        f"{salt}_{expire_at}_",
        challenge_hex,
        difficulty,
    )

    if nonce < 0:
        raise RuntimeError("PoW not solved")

    print(f"[+] PoW nonce={nonce}")

    pow_header_value = base64.b64encode(
        json.dumps(
            {
                "algorithm": ch.get("algorithm", "DeepSeekHashV1"),
                "challenge": challenge_hex,
                "salt": salt,
                "signature": ch.get("signature", ""),
                "answer": nonce,
                "target_path": COMPLETION_PATH,
            },
            separators=(",", ":"),
        ).encode()
    ).decode()

    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "X-DS-PoW-Response": pow_header_value,
    }

    body = {
        "chat_session_id": session_id,
        "parent_message_id": None,
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": False,
        "search_enabled": False,
        "audio_id": None,
        "preempt": False,
        "model_type": model,
    }

    async with session.post(
        BASE_URL + COMPLETION_PATH,
        json=body,
        headers=headers,
    ) as resp:
        if resp.status != 200:
            body_bytes = await resp.read()

            print(
                f"[!] HTTP {resp.status}: "
                f"{body_bytes.decode('utf-8', errors='replace')}"
            )

            raise RuntimeError(f"HTTP {resp.status}")

        async for raw_line in resp.content:
            line = raw_line.decode("utf-8", errors="replace").strip()

            if not line.startswith("data:"):
                continue

            data_str = line[5:].strip()

            if not data_str or data_str == "[DONE]":
                continue

            try:
                event = json.loads(data_str)

            except json.JSONDecodeError:
                continue

            token_text = _extract_token(event)

            if token_text:
                yield token_text


async def main():
    email = os.getenv("DEEPSEEK_EMAIL")
    password = os.getenv("DEEPSEEK_PASSWORD")

    prompt = "Даров бро как сам"

    if not email or not password:
        raise RuntimeError(
            "Set DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD in .env"
        )

    timeout = aiohttp.ClientTimeout(total=None)

    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:
        token = await login(session, email, password)

        session_id = await create_session(session, token)

        print(f"\n[DeepSeek — {prompt!r}]\n" + "─" * 50)

        async for chunk in chat(
            session,
            token,
            session_id,
            prompt,
        ):
            print(chunk, end="", flush=True)

        print("\n" + "─" * 50)


if __name__ == "__main__":
    asyncio.run(main())