from __future__ import annotations

import base64
import json
import os
import time
import uuid
from typing import Any

import aiohttp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


ORG_ID = "P9usCUBauxft8eAmUXaZ"
APP_ID = "default"

PUBLIC_KEY_CERT = """
MIIDLzCCAhegAwIBAgIBMDANBgkqhkiG9w0BAQUFADAyMQswCQYDVQQGEwJDTjELMAkGA1UECwwCU00xFjAUBgNVBAMMDWUuaXNodW1laS5jb20wHhcNMjQwNjA3MDMwMDAzWhcNNDQwNjAyMDMwMDAzWjAyMQswCQYDVQQGEwJDTjELMAkGA1UECwwCU00xFjAUBgNVBAMMDWUuaXNodW1laS5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCKfwaYlymHTceYtmqrrmToS9l2p7YTSHULqjOdVEqGlyB+I36vkxL+EnKaiMm2BXuIYP1u/Qthi20s1urH/a0EublyCdp2iuX2gn2zzBSmNaUd0OgLxBAF8VnlU0eUblDnuHemZ6Jl4AWWzAJJ96UrWjUFNLW5jnnuWWvPlzTJeOUCRYLJJlyelZ0yKTbKFxeHg3bXpl2kubJX4mxI4aAoFf/o3o4EmuZJlRFXSEEZNy2f48zHN3KnKw35LBZ/0ZKWo99d8jbe/5nGYyjBVXqHdysPTqDT8SjhC/e3D1EV8eUA0LdPbFJeqdtw8gt42GtMu220vYoxZFEPd5TMUWUnAgMBAAGjUDBOMB0GA1UdDgQWBBTI2FDJXm6+ZzH+14fKyE6HeA/jPTAfBgNVHSMEGDAWgBTI2FDJXm6+ZzH+14fKyE6HeA/jPTAMBgNVHRMEBTADAQH/MA0GCSqGSIb3DQEBBQUAA4IBAQB5a9tIKmwYZcoGAsU3AddF+mWLjdhmlzN5ixgoJErNmm4DMMV8yv8NXsAHe+KLn8viC1SSUhJAy0wPHenETXPIKnpBApPyxpD2jPkaRmuisUA5l6lIRJ9Z6KYfigl20oQWHByFz8t+wTq04ahIyJvGUZAmSdLeD4UAtN2UXwuxYsemerU9QP5aQzsOIcp3bDyz1zzKPRYt0gGAk8AkTlTokstekWxLAQFMqOM0Ob0zatQmlMDVBT51m2clobgLB9pYBCdi+gXKDaddz3oNnvFrFx2oFEe6wA9neHONAjxBs9m8MyrU32TcA8ZiECpzCTcvD2RXWw6v1oD07XQmZudy
""".strip()

DEVICEPROFILE_URL = "https://fp-it.fengkongcloud.com/deviceprofile/v4"

IV = b"0102030405060708"


def pkcs7_pad(data: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    return padder.update(data) + padder.finalize()


def aes_encrypt(key: bytes, data: bytes) -> str:
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(IV),
    )

    encryptor = cipher.encryptor()

    encrypted = encryptor.update(pkcs7_pad(data)) + encryptor.finalize()

    return base64.b64encode(encrypted).decode()


def rsa_encrypt(cert_b64: str, data: bytes) -> str:
    cert_der = base64.b64decode(cert_b64)

    cert = x509.load_der_x509_certificate(cert_der)

    public_key = cert.public_key()

    encrypted = public_key.encrypt(
        data,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    return base64.b64encode(encrypted).decode()


def random_session_id() -> str:
    return uuid.uuid4().hex


def build_wevent() -> list[dict[str, Any]]:
    now = int(time.time() * 1000)

    return [
        {
            "eventId": "device_profile",
            "timestamp": now,
            "a1": "Google",
            "a2": "Pixel 7",
            "a3": "google/panther/panther:14/UQ1A.240205.002/11224170:user/release-keys",
            "a4": "android",
            "a5": "14",
            "a6": "1080x2400",
            "a7": "arm64-v8a",
            "a8": "en_US",
            "a9": "Europe/Berlin",
            "a10": str(now),
        }
    ]


def build_inner_payload() -> dict[str, Any]:
    return {
        "smid": "",
        "appId": APP_ID,
        "appname": "com.deepseek.chat",
        "sessionId": random_session_id(),
        "wevent": build_wevent(),
    }


def build_outer_payload() -> dict[str, Any]:
    aes_key = os.urandom(32)

    inner_payload = build_inner_payload()

    inner_json = json.dumps(
        inner_payload,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()

    encrypted_data = aes_encrypt(aes_key, inner_json)

    encrypted_key = rsa_encrypt(PUBLIC_KEY_CERT, aes_key)

    return {
        "organization": ORG_ID,
        "os": "android",
        "appId": APP_ID,
        "encode": 3,
        "data": encrypted_data,
        "ep": encrypted_key,
    }


async def register_device() -> dict[str, Any]:
    payload = build_outer_payload()

    headers = {
        "User-Agent": "okhttp/4.9.2",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            DEVICEPROFILE_URL,
            json=payload,
            headers=headers,
        ) as response:
            text = await response.text()
            print(f"text: {text}")

            try:
                data = json.loads(text)
            except Exception:
                return {
                    "status": response.status,
                    "raw": text,
                }

            return {
                "status": response.status,
                "response": data,
                "device_id": data.get("deviceId"),
                "sid": data.get("sid"),
            }


async def main() -> None:
    result = await register_device()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())