import asyncio
import os

from dotenv import load_dotenv

from aiodeepseek import DeepSeekClient
from aiodeepseek.types.enums import ModelType

load_dotenv()

async def ask_deepseek(client: DeepSeekClient):
    result = await client.ask(
        prompt="Как сам?",
        model=ModelType.EXPERT
    )
    print(f"Deepseek: {result.text}\n")

async def main():
    token = os.getenv("DEEPSEEK_TOKEN")
    async with DeepSeekClient(token=token) as client:
        await asyncio.gather(
            *[ask_deepseek(client) for _ in range(2)]
        )


if __name__ == "__main__":
    asyncio.run(main())