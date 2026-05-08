from __future__ import annotations

import base64
import json
import random
import time
from typing import Any, Optional

import aiohttp

from aiodeepseek.data.constants import BASE_URL, HEADERS
from aiodeepseek.data.device_ids import get_device_id
from aiodeepseek.pow.pow import solve_pow
from aiodeepseek.types.exceptions import DeepSeekError
from .base import _BaseClient

_REGISTER_PATH = "/api/v0/users/register"


def _make_guest_headers() -> dict[str, str]:
    offset = -time.timezone if time.daylight == 0 else -time.altzone
    return {
        **HEADERS,
        "x-rangers-id": str(random.randint(10**18, 10**19 - 1)),
        "x-client-timezone-offset": str(offset),
    }


class _AuthClient(_BaseClient):
    """Extends :class:`_BaseClient` with authentication and registration.

    All three public methods are classmethods and create temporary sessions
    internally, so they can be called without an open client instance.
    """

    @staticmethod
    def _extract_token(data: dict) -> str:
        """Extract the bearer token string from a login or register API response.

        Args:
            data: Parsed JSON response body returned by the login or register endpoint.

        Returns:
            Bearer token string.
        """
        return data["data"]["biz_data"]["user"]["token"]

    @classmethod
    async def fetch_token(
        cls,
        email: str,
        password: str,
        device_id: Optional[str] = None,
    ) -> str:
        """Authenticate with e-mail and password and return a bearer token.

        Opens a short-lived session internally, so a client instance does not
        need to be open before calling this method.

        Args:
            email: DeepSeek account e-mail address.
            password: DeepSeek account password.
            device_id: Optional stable device identifier sent to the API.

        Returns:
            Bearer token string.

        Raises:
            DeepSeekError: If the API returns a non-zero status code.
        """
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                BASE_URL + "/api/v0/users/login",
                json={
                    "email": email,
                    "password": password,
                    "device_id": device_id or get_device_id(),
                    "os": "ios",
                },
                headers=HEADERS,
            ) as resp:
                data = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"login failed: {data}")

        return cls._extract_token(data)

    @classmethod
    async def send_reg_code(
        cls,
        email: str,
        *,
        locale: str = "en_US",
        device_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a registration verification code to *email*.

        Args:
            email: E-mail address to register.
            locale: Locale string forwarded to the API (e.g. ``"en_US"``).
            device_id: Optional stable device identifier.

        Returns:
            Raw API response dict (code 0 on success).

        Raises:
            DeepSeekError: If the API returns a non-zero status code.
        """
        headers = _make_guest_headers()
        body = {
            "email": email,
            "locale": locale,
            "shumei_verification": None,
            "hcaptcha_token": None,
            "turnstile_token": "",
            "device_id": device_id or get_device_id(),
            "scenario": "register",
        }

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                BASE_URL + "/api/v0/users/create_email_verification_code",
                json=body,
                headers=headers,
            ) as resp:
                data: dict = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"send_reg_code failed: {data}")

        return data

    @classmethod
    async def confirm_reg_code(
        cls,
        email: str,
        password: str,
        code: str,
        *,
        region: str = "BY",
        locale: str = "ru",
        device_id: Optional[str] = None,
    ) -> str:
        """Complete registration with the e-mail verification code and return a token.

        Fetches and solves a guest proof-of-work challenge before submitting the
        registration payload, then extracts and returns the bearer token from the
        API response.

        Args:
            email: E-mail address being registered.
            password: Desired account password.
            code: Verification code received via e-mail.
            region: Two-letter region code forwarded to the API.
            locale: Locale string forwarded to the API.
            device_id: Optional stable device identifier.

        Returns:
            Bearer token string for the newly created account.

        Raises:
            DeepSeekError: If the guest PoW, registration request, or token
                extraction fails.
        """
        used_device_id = device_id or get_device_id()
        base_headers = _make_guest_headers()

        body = {
            "region": region,
            "locale": locale,
            "device_id": used_device_id,
            "payload": {
                "email": email,
                "email_verification_code": code,
                "password": password,
            },
            "os": "ios",
        }

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            guest_pow = await cls._fetch_guest_pow(session, base_headers)
            headers = {**base_headers, "x-ds-guest-pow-response": guest_pow}

            async with session.post(
                BASE_URL + _REGISTER_PATH,
                json=body,
                headers=headers,
            ) as resp:
                data: dict = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"confirm_reg_code failed: {data}")

        return cls._extract_token(data)

    @staticmethod
    async def _fetch_guest_pow(
        session: aiohttp.ClientSession,
        headers: dict[str, str],
    ) -> str:
        """Fetch and solve a guest PoW challenge for the registration endpoint.

        Args:
            session: An already-open ``aiohttp.ClientSession``.
            headers: Base request headers including ``x-rangers-id``.

        Returns:
            Base64-encoded JSON solution string for the
            ``x-ds-guest-pow-response`` header.

        Raises:
            DeepSeekError: If the challenge request fails or the solver does
                not converge.
        """
        async with session.post(
            BASE_URL + "/api/v0/users/create_guest_challenge",
            json={"target_path": _REGISTER_PATH},
            headers=headers,
        ) as resp:
            data = await resp.json()

        if data.get("code") != 0:
            raise DeepSeekError(f"guest challenge failed: {data}")

        ch = data["data"]["biz_data"]["guest_challenge"]
        salt = ch["salt"]
        expire_at = ch["expire_at"]
        difficulty = int(ch["difficulty"])
        challenge = ch["challenge"]

        nonce = solve_pow(f"{salt}_{expire_at}_", challenge, difficulty)
        if nonce < 0:
            raise DeepSeekError("failed to solve guest pow")

        payload = {
            "algorithm": ch["algorithm"],
            "challenge": challenge,
            "salt": salt,
            "signature": ch["signature"],
            "answer": nonce,
            "target_path": _REGISTER_PATH,
        }

        return base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()
