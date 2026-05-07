import asyncio
import os
import sys
import time

from dotenv import load_dotenv

from aiodeepseek import DeepSeekClient

load_dotenv()


def print_prompt() -> None:
    print("\nYou: ", end="", flush=True)


def print_assistant() -> None:
    print("\nAssistant: ", end="", flush=True)


async def stream_reply(client: DeepSeekClient, prompt: str) -> None:
    total_start = time.perf_counter()
    request_start = time.perf_counter()

    print_assistant()

    first_token = False
    last_len = 0

    async for chunk in client.ask_stream(prompt):
        if not first_token:
            # print(f"\n[first token {time.perf_counter() - request_start:.2f}s]")
            print_assistant()
            first_token = True

        new_part = chunk[last_len:]
        print(new_part, end="", flush=True)
        last_len = len(chunk)

    print(f"\n[done {time.perf_counter() - total_start:.2f}s]")


async def main() -> None:
    token = os.getenv("DEEPSEEK_TOKEN")
    email = os.getenv("DEEPSEEK_EMAIL")
    password = os.getenv("DEEPSEEK_PASSWORD")

    kwargs = {}

    if token:
        kwargs["token"] = token
    else:
        if not email or not password:
            raise RuntimeError(
                "Set DEEPSEEK_TOKEN or DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD in .env"
            )

        kwargs["email"] = email
        kwargs["password"] = password

    async with DeepSeekClient(**kwargs) as client:
        while True:
            print_prompt()

            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                sys.stdin.readline,
            )

            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input.lower() in {"quit", "exit"}:
                break

            await stream_reply(client, user_input)


if __name__ == "__main__":
    asyncio.run(main())