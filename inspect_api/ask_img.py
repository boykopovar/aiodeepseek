import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

from aiodeepseek import DeepSeekClient

load_dotenv()


async def main() -> None:
    token = os.getenv("DEEPSEEK_TOKEN")
    email = os.getenv("DEEPSEEK_EMAIL")
    password = os.getenv("DEEPSEEK_PASSWORD")

    kwargs: Dict = {}
    if token:
        kwargs["token"] = token
    elif email and password:
        kwargs["email"] = email
        kwargs["password"] = password
    else:
        raise RuntimeError(
            "Set DEEPSEEK_TOKEN or both DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD in .env"
        )

    image_path = Path("img.jpg")
    if not image_path.exists():
        print(f"[error] {image_path} not found — place an image named img.jpg next to this script")
        sys.exit(1)

    question = "Что изображено на этой картинке? Опиши подробно."

    async with DeepSeekClient(**kwargs) as client:
        print(f"Uploading {image_path} …", flush=True)
        t0 = time.perf_counter()
        img = await client.upload_image(image_path)
        print(f"Uploaded in {time.perf_counter() - t0:.2f}s — {img}\n", flush=True)

        print(f"Question: {question}")
        print("Answer: ", end="", flush=True)

        last_len = 0
        async for chunk in client.ask_stream(question, image=img):
            new_part = chunk[last_len:]
            print(new_part, end="", flush=True)
            last_len = len(chunk)

        print(f"\n[done {time.perf_counter() - t0:.2f}s]")


if __name__ == "__main__":
    asyncio.run(main())
