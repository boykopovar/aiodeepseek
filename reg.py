from __future__ import annotations

import base64
import json
import os
import random
import time
from typing import Any

import aiohttp
from dotenv import load_dotenv

from aiodeepseek.data.constants import BASE_URL, HEADERS
from aiodeepseek.data.device_ids import get_device_id
from aiodeepseek.pow.pow import solve_pow
from aiodeepseek.types.exceptions import DeepSeekError

load_dotenv()

REGISTER_PATH = "/api/v0/users/register"

_rangers_id: str = str(random.randint(10**18, 10**19 - 1))


def _timezone_offset_seconds() -> int:
    return -time.timezone if time.daylight == 0 else -time.altzone


def _base_headers() -> dict[str, str]:
    return {
        **HEADERS,
        "x-rangers-id": _rangers_id,
        "x-client-timezone-offset": str(
            _timezone_offset_seconds()
        ),
    }


async def _fetch_guest_pow(
    session: aiohttp.ClientSession,
) -> str:
    async with session.post(
        BASE_URL + "/api/v0/users/create_guest_challenge",
        json={
            "target_path": REGISTER_PATH,
        },
        headers=_base_headers(),
    ) as resp:
        data = await resp.json()

    if data.get("code") != 0:
        raise DeepSeekError(
            f"guest challenge failed: {data}"
        )

    ch = data["data"]["biz_data"]["guest_challenge"]

    salt = ch["salt"]
    expire_at = ch["expire_at"]
    difficulty = int(ch["difficulty"])
    challenge = ch["challenge"]

    nonce = solve_pow(
        f"{salt}_{expire_at}_",
        challenge,
        difficulty,
    )

    if nonce < 0:
        raise DeepSeekError(
            "failed to solve guest pow"
        )

    payload = {
        "algorithm": ch["algorithm"],
        "challenge": challenge,
        "salt": salt,
        "signature": ch["signature"],
        "answer": nonce,
        "target_path": REGISTER_PATH,
    }

    encoded = base64.b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
        ).encode()
    ).decode()

    return encoded


async def send_register_code(
    email: str,
    *,
    locale: str = "en_US",
    device_id: str | None = None,
) -> dict[str, Any]:
    device_id = device_id or get_device_id()

    body = {
        "email": email,
        "locale": locale,
        "shumei_verification": None,
        "hcaptcha_token": None,
        "turnstile_token": "",
        "device_id": device_id,
        "scenario": "register",
    }

    connector = aiohttp.TCPConnector(
        ssl=False,
    )

    async with aiohttp.ClientSession(
        connector=connector,
    ) as session:
        headers = _base_headers()

        async with session.post(
            BASE_URL
            + "/api/v0/users/create_email_verification_code",
            json=body,
            headers=headers,
        ) as resp:
            data: dict = await resp.json()

    if data.get("code") != 0:
        raise DeepSeekError(
            f"send_register_code failed: {data}"
        )

    return data


async def confirm_register(
    email: str,
    password: str,
    code: str,
    *,
    region: str = "BY",
    locale: str = "ru",
    device_id: str | None = None,
) -> str:
    device_id = device_id or get_device_id()

    body = {
        "region": region,
        "locale": locale,
        "device_id": device_id,
        "payload": {
            "email": email,
            "email_verification_code": code,
            "password": password,
        },
        "os": "ios"
    }

    connector = aiohttp.TCPConnector(
        ssl=False,
    )

    async with aiohttp.ClientSession(
        connector=connector,
    ) as session:
        guest_pow = await _fetch_guest_pow(
            session
        )

        headers = {
            **_base_headers(),
            "x-ds-guest-pow-response": guest_pow,
        }

        async with session.post(
            BASE_URL + REGISTER_PATH,
            json=body,
            headers=headers,
        ) as resp:
            text = await resp.text()

            print(text)
            print(resp.headers)

            data: dict = json.loads(text)

    if data.get("code") != 0:
        raise DeepSeekError(
            f"confirm_register failed: {data}"
        )

    return (
        data["data"]["biz_data"]["user"]["token"]
    )


if __name__ == "__main__":
    import asyncio

    async def _demo() -> None:
        email = os.environ["REG_EMAIL"]
        password = os.environ["REG_PASSWORD"]

        print("Sending code...")

        resp = await send_register_code(
            email
        )

        print(resp)

        code = input(
            "Enter code from email: "
        ).strip()

        print("Registering...")

        token = await confirm_register(
            email,
            password,
            code,
        )

        print(token)

    asyncio.run(_demo())