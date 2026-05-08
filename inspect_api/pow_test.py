import asyncio
import os
import statistics
import time

from dotenv import load_dotenv

from aiodeepseek import DeepSeekClient
from aiodeepseek.data.constants import COMPLETION_PATH
from aiodeepseek.pow.pow import solve_pow

load_dotenv()

async def solve_single_pow(client: DeepSeekClient, token: str, index: int):
    challenge = await client._get_pow_challenge(
        token,
        COMPLETION_PATH,
    )

    salt = challenge["salt"]
    expire_at = challenge["expire_at"]
    difficulty = int(challenge["difficulty"])
    challenge_hex = challenge["challenge"]

    started = time.perf_counter()
    nonce = solve_pow(
        f"{salt}_{expire_at}_",
        challenge_hex,
        difficulty,
    )

    elapsed = time.perf_counter() - started

    return {
        "index": index,
        "difficulty": difficulty,
        "nonce": nonce,
        "elapsed": elapsed,
    }


async def main():
    token = os.environ.get("DEEPSEEK_TOKEN")

    async with DeepSeekClient(token=token) as client:
        tasks = [
            solve_single_pow(client, token, i + 1)
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

    times = []
    difficulties = []

    for result in results:
        times.append(result["elapsed"])
        difficulties.append(result["difficulty"])

        print(
            f"[{result['index']}] "
            f"difficulty={result['difficulty']} "
            f"nonce={result['nonce']} "
            f"time={result['elapsed'] * 1000:.4f} ms"
        )

    unique_difficulties = sorted(set(difficulties))

    if len(unique_difficulties) == 1:
        diff_output = str(unique_difficulties[0])
    else:
        diff_output = " ".join(map(str, unique_difficulties))

    print()
    print(f"Difficulties: {diff_output}")
    print(f"Average time: {statistics.mean(times) * 1000:.4f} ms")
    print(f"Min time: {min(times) * 1000:.4f} ms")
    print(f"Max time: {max(times) * 1000:.4f} ms")

if __name__ == "__main__":
    asyncio.run(main())