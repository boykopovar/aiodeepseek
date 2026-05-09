import base64
import json
import random
import time
from typing import Any, Dict, Optional

import aiohttp

from aiodeepseek.data.constants import BASE_URL, HEADERS
from aiodeepseek.data.device_ids import get_device_id
from aiodeepseek.pow.pow import solve_pow
from aiodeepseek.types.exceptions import DeepSeekError, raise_for_api_response
from aiodeepseek.clients.base import _BaseClient
from aiodeepseek.log import _log_request

_REGISTER_PATH: str = "/api/v0/users/register"


def _make_guest_headers() -> Dict[str, str]:
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
    def _extract_token(data: Dict) -> str:
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
        url = BASE_URL + "/api/v0/users/login"
        req_body = {
            "email": email,
            "password": password,
            "device_id": device_id or get_device_id(),
            "os": "ios",
        }

        _log_request("LOGIN REQUEST", url, HEADERS, req_body)

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=req_body, headers=HEADERS) as resp:
                data = await cls._read_json(resp, "LOGIN RESPONSE")

        raise_for_api_response("login", data)

        return cls._extract_token(data)

    @classmethod
    async def send_reg_code(
        cls,
        email: str,
        *,
        locale: str = "en_US",
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        url = BASE_URL + "/api/v0/users/create_email_verification_code"
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

        _log_request("SEND REG CODE REQUEST", url, headers, body)

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=body, headers=headers) as resp:
                data = await cls._read_json(resp, "SEND REG CODE RESPONSE")

        raise_for_api_response("send_reg_code", data)

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
            req_headers = {**base_headers, "x-ds-guest-pow-response": guest_pow}

            _log_request("CONFIRM REG CODE REQUEST", BASE_URL + _REGISTER_PATH, req_headers, body)

            async with session.post(
                BASE_URL + _REGISTER_PATH,
                json=body,
                headers=req_headers,
            ) as resp:
                data = await cls._read_json(resp, "CONFIRM REG CODE RESPONSE")

        raise_for_api_response("confirm_reg_code", data)

        return cls._extract_token(data)

    @staticmethod
    async def _fetch_guest_pow(
        session: aiohttp.ClientSession,
        headers: Dict[str, str],
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
        url = BASE_URL + "/api/v0/users/create_guest_challenge"
        req_body = {"target_path": _REGISTER_PATH}

        _log_request("GUEST CHALLENGE REQUEST", url, headers, req_body)

        async with session.post(url, json=req_body, headers=headers) as resp:
            data = await _BaseClient._read_json(resp, "GUEST CHALLENGE RESPONSE")

        raise_for_api_response("guest_challenge", data)

        ch = data["data"]["biz_data"]["guest_challenge"]
        salt: str = ch["salt"]
        expire_at: str = ch["expire_at"]
        difficulty: int = int(ch["difficulty"])
        challenge: str = ch["challenge"]

        nonce: int = solve_pow(f"{salt}_{expire_at}_", challenge, difficulty)
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
