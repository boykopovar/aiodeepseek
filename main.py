import asyncio
import os
import sys
import time

from dotenv import load_dotenv

from aiodeepseek import DeepSeekClient, Conversation

load_dotenv()


def print_prompt() -> None:
    print("\nYou: ", end="", flush=True)


async def stream_reply(conversation: Conversation, prompt: str) -> None:
    total_start = time.perf_counter()

    print("\nDeepSeek: ", end="", flush=True)

    last_len = 0

    async for chunk in conversation.ask_stream(prompt):
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
        conversation = client.new_conversation()

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

            await stream_reply(conversation, user_input)

            if not token:
                token = client.token
                print(f"Token: {token}")


if __name__ == "__main__":
    asyncio.run(main())
