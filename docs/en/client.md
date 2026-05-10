# DeepSeekClient

## Constructor

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.enums import ModelType

client = DeepSeekClient(
    token="...",
    model=ModelType.DEFAULT,
    device_id=None,
    timeout=None,
)
```

| Parameter   | Type            | Description                                                 |
|-------------|-----------------|-------------------------------------------------------------|
| `token`     | `str \| None`   | Bearer token. If omitted, `email` + `password` are required |
| `email`     | `str \| None`   | DeepSeek account email                                      |
| `password`  | `str \| None`   | Account password                                            |
| `model`     | `ModelType`     | Default model (`ModelType.DEFAULT`)                         |
| `device_id` | `str \| None`   | Device identifier. Chosen randomly if omitted               |
| `timeout`   | `float \| None` | Request timeout in seconds. `None` means unlimited          |

The client can be used as an async context manager:

```python
from aiodeepseek import DeepSeekClient

async with DeepSeekClient(token="...") as client:
    ...
```

Or manually:

```python
from aiodeepseek import DeepSeekClient

async def main():
    client = DeepSeekClient(token="...")
    await client.open()
    await client.ask("Hello")
    await client.close()
```

---

## token property

```python
from aiodeepseek import DeepSeekClient

async with DeepSeekClient(email="mymail@example.com", password="pass") as client:
    print(client.token)
```

Returns the current Bearer token or `None` before the session is opened.

---

## ask

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import DeepSeekTurnResult


async def main():
    async with DeepSeekClient(token="...") as client:
        result: DeepSeekTurnResult = await client.ask("What is Python?")
        print(result.text)
```

Sends a message and returns the full response.

| Parameter           | Type                                     | Description                                      |
|---------------------|------------------------------------------|--------------------------------------------------|
| `prompt`            | `str`                                    | User message                                     |
| `image`             | `UploadedImage \| bytes \| Path \| None` | Attached image                                   |
| `model`             | `ModelType \| None`                      | Override the model for this call                 |
| `timeout`           | `float \| None`                          | Override the timeout for this call               |
| `parent_message_id` | `str \| None`                            | Previous response ID for continuing the thread   |

Returns [`DeepSeekTurnResult`](types.md#deepseekturnresult).

---

## ask_stream

```python
import asyncio
from aiodeepseek import DeepSeekClient


async def main():
    async with DeepSeekClient(token="...") as client:
        async for chunk in client.ask_stream("Explain async/await"):
            print(chunk, end="", flush=True)


asyncio.run(main())
```

Streams the response.

By default, each yielded chunk contains only the newly generated text fragment.

Use `cumulative=True` to receive the full accumulated response on each iteration.

```python
async for chunk in client.ask_stream(
    "Explain async/await",
    cumulative=True,
):
    print(chunk)
```

Takes the same parameters as `ask` plus:

| Parameter    | Type   | Description                                                |
|--------------|--------|------------------------------------------------------------|
| `cumulative` | `bool` | Yield accumulated text instead of incremental fragments    |

---

## upload_image

```python
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import UploadedImage


async def main():
    async with DeepSeekClient(token="...") as client:
        img: UploadedImage = await client.upload_image(Path("photo.png"))
        result = await client.ask("Describe the image", image=img)
```

Uploads a PNG or JPEG to the server and returns [`UploadedImage`](types.md#uploadedimage).

| Parameter  | Type            | Description                       |
|------------|-----------------|-----------------------------------|
| `source`   | `Path \| bytes` | File path or raw bytes            |
| `filename` | `str \| None`   | Filename in the multipart request |
| `timeout`  | `float \| None` | Override the timeout              |

---

## new_conversation

```python
from aiodeepseek import DeepSeekClient, Conversation

async def main():
    async with DeepSeekClient(token="...") as client:
        chat: Conversation = client.new_conversation()
        await chat.ask("Hello")
        await chat.ask("Continue")
```

Creates a [`Conversation`](conversation.md) object that automatically tracks `parent_message_id` between turns.

---

## Static authentication methods

### send_reg_code

```python
from aiodeepseek import DeepSeekClient

async def main():
    await DeepSeekClient.send_reg_code("mymail@example.com")
```

Sends a confirmation code to the registration email.

| Parameter   | Type          | Description                   |
|-------------|---------------|-------------------------------|
| `email`     | `str`         | Registration email            |
| `locale`    | `str`         | Locale (`"en_US"` by default) |
| `device_id` | `str \| None` | Device identifier             |

### confirm_reg_code

```python
from aiodeepseek import DeepSeekClient

async def main():
    token = await DeepSeekClient.confirm_reg_code(
        "me@example.com",
        "mypassword",
        "123456",
    )
    print(token)
```

Completes registration and returns a Bearer token. Before sending, it automatically solves the [PoW challenge](pow.md).

| Parameter   | Type          | Description                      |
|-------------|---------------|----------------------------------|
| `email`     | `str`         | Email                            |
| `password`  | `str`         | Desired password                 |
| `code`      | `str`         | Code from the email              |
| `region`    | `str`         | Country code (`"US"` by default) |
| `locale`    | `str`         | Locale (`"en_US"` by default)    |
| `device_id` | `str \| None` | Device identifier                |

### fetch_token

```python
from aiodeepseek import DeepSeekClient

async def main():
    token = await DeepSeekClient.fetch_token("mymail@example.com", "password")
    print(token)
```

Performs login and returns a Bearer token. Does not require an open client instance.

---

## See also

- [Conversation](conversation.md)
- [Data types](types.md)
- [Exceptions](exceptions.md)
- [Proof-of-Work](pow.md)
