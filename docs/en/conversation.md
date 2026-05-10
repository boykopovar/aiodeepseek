# Conversation

A wrapper for multi-turn conversations. Automatically passes the `parent_message_id` from each response into the next request, keeping the thread inside a single session.

Created via [`DeepSeekClient.new_conversation()`](client.md#new_conversation).

---

## Creation

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()
        print((await chat.ask("What is your name?")).text)
        print((await chat.ask("What can you do?")).text)
        print((await chat.ask("Tell me more")).text)

asyncio.run(main())
```

---

## ask

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()
        reply = await chat.ask("Write a poem about whales")
        print(reply.text)

asyncio.run(main())
```

Sends a message, updates `parent_message_id`, and returns a response object:

```python
class DeepSeekTurnResult:
    text: str
    session_id: str
    message_id: str | None = None
```

| Parameter | Type                                     | Description                      |
|-----------|------------------------------------------|----------------------------------|
| `prompt`  | `str`                                    | User message                     |
| `image`   | `UploadedImage \| bytes \| Path \| None` | Attached image                   |
| `model`   | `str \| None`                            | Override the model for this turn |
| `timeout` | `float \| None`                          | Override the timeout             |

---

## ask_stream

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()

        async for chunk in chat.ask_stream("List the planets"):
            print(chunk, end="", flush=True)

        print()

asyncio.run(main())
```

Streams the response and automatically updates the conversation state after the stream ends.

By default, each yielded chunk contains only the newly generated text fragment.

Use `cumulative=True` to receive the full accumulated response on each iteration.

```python
async for chunk in chat.ask_stream(
    "List the planets",
    cumulative=True,
):
    print(chunk)
```

Takes the same parameters as `ask` plus:

| Parameter    | Type   | Description                                                |
|--------------|--------|------------------------------------------------------------|
| `cumulative` | `bool` | Yield accumulated text instead of incremental fragments    |

---

## parent_message_id

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()
        await chat.ask("First question")
        print(chat.parent_message_id)

asyncio.run(main())
```

Property. The ID of the assistant’s latest response, or `None` before the first turn.

---

## Conversation with an image

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        img = await client.upload_image(Path("chart.png"))
        chat = client.new_conversation()
        print((await chat.ask("What is shown in this chart?", image=img)).text)
        print((await chat.ask("Which bar is the tallest?")).text)

asyncio.run(main())
```

---

## See also

- [DeepSeekClient](client.md)
- [Data types](types.md)
