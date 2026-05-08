from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from aiodeepseek import DeepSeekClient

load_dotenv()


async def main() -> None:
    email = os.environ["REG_EMAIL"]
    password = os.environ["REG_PASSWORD"]

    print(f"Sending verification code to {email} …")
    await DeepSeekClient.send_reg_code(email)
    print("Code sent.")

    code = input("Enter code from email: ").strip()

    print("Registering …")
    token = await DeepSeekClient.confirm_reg_code(email, password, code)

    print(f"\nRegistration successful!")
    print(f"Token: {token}")


if __name__ == "__main__":
    asyncio.run(main())
