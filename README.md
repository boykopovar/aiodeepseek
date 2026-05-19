# aiodeepseek

<p align="left">
  <img src="docs/assets/icon.svg" width="90">
</p>

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey)
![Async](https://img.shields.io/badge/asyncio-fully%20async-blueviolet)
![DeepSeek](https://img.shields.io/badge/API-DeepSeek-blue)

A high-performance async Python client for the private DeepSeek API. Supports streaming, image uploads, multi-turn conversations, and new account registration.

➡️ Russian documentation: [docs/ru/README.md](docs/ru/README.md)

## Installation

```bash
pip install aiodeepseek
```

A C++ extension build requires a compiler with AVX2 support and `pybind11`. More details are in [docs/en/pow.md](docs/en/pow.md). You can also download a prebuilt [release](https://github.com/boykopovar/aiodeepseek/releases).

---

## Quick start

### Email/password authentication

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(
            email="myname@example.com",
            password="password123"
    ) as client:
        result = await client.ask("Hello!")
        print(result.text)

asyncio.run(main())
```

### Token authentication

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="YOUR_TOKEN") as client:
        result = await client.ask("Hello!")
        print(result.text)

asyncio.run(main())
```

### Streaming a response

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="YOUR_TOKEN") as client:
        async for chunk in client.ask_stream(
                prompt="Tell me about Python"
        ):
            print(chunk, end="", flush=True)

asyncio.run(main())
```

### Multi-turn conversation

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="YOUR_TOKEN") as client:
        chat = client.new_conversation()
        print((await chat.ask("What is your name?")).text)
        print((await chat.ask("What can you do?")).text)

asyncio.run(main())
```

### Image upload

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="YOUR_TOKEN") as client:
        img = await client.upload_image(Path("photo.jpg"))
        result = await client.ask("What is in the photo?", image=img)
        print(result.text)

asyncio.run(main())
```

or by passing `Path | bytes` directly to `ask`:

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="YOUR_TOKEN") as client:
        result = await client.ask(
            prompt="What is in the photo?",
            image=Path("photo.jpg")
        )
        print(result.text)

asyncio.run(main())
```

### New account registration

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    await DeepSeekClient.send_reg_code("myname@example.com")
    code = input("Code from the email: ")
    token = await DeepSeekClient.confirm_reg_code("myname@example.com", "password123", code)
    print("Token:", token)

asyncio.run(main())
```

---

## Model types

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.enums import ModelType

async with DeepSeekClient(token="...", model=ModelType.VISION) as client:
    ...
```

| Value               | Description                       |
|---------------------|-----------------------------------|
| `ModelType.DEFAULT` | Standard language model           |
| `ModelType.EXPERT`  | Deep reasoning model              |
| `ModelType.VISION`  | Model with machine vision support |

---

## Error handling

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import AuthorizationError, DeepSeekError

async def main():
    try:
        async with DeepSeekClient(token="invalid") as client:
            await client.ask("Hello")
    except AuthorizationError:
        print("Token is invalid")
    except DeepSeekError as e:
        print(f"API error: {e}")

asyncio.run(main())
```

---

## Proof-of-Work

Before every request, the client automatically solves the PoW challenge issued by the DeepSeek server. Typical difficulty is **144,000 iterations**. The calculation is implemented in C++ using AVX2, which keeps it barely noticeable in practice. More details are in [docs/en/pow.md](docs/en/pow.md).

---

## Documentation

- [DeepSeekClient - client methods](docs/en/client.md)
- [Conversation - multi-turn dialog](docs/en/conversation.md)
- [Types and data models](docs/en/types.md)
- [Exceptions](docs/en/exceptions.md)
- [Proof-of-Work](docs/en/pow.md)

---

## Requirements

- Python 3.9+
- `aiohttp >= 3.9`
- A C++17 compiler with AVX2 (to build the extension) or manually downloaded wheels.
