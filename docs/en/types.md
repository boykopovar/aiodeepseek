# Data types

---

## ModelType

```python
from aiodeepseek.types.enums import ModelType
```

Enumeration of available models.

| Value               | String      | Description                    |
|---------------------|-------------|--------------------------------|
| `ModelType.DEFAULT` | `"default"` | Standard language model       |
| `ModelType.EXPERT`  | `"expert"`  | Advanced model                |
| `ModelType.VISION`  | `"vision"`  | Model with image support      |

`ModelType` inherits from `str`, so `str(ModelType.DEFAULT) == "default"`.

Passed to the client constructor or to `ask` / `ask_stream` methods:

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.enums import ModelType

async def main():
    async with DeepSeekClient(token="...", model=ModelType.EXPERT) as client:
        result = await client.ask("A difficult question", model=ModelType.VISION)
```

---

## DeepSeekTurnResult

```python
from aiodeepseek.types.models.classes import DeepSeekTurnResult
```

Returned by [`DeepSeekClient.ask()`](client.md#ask). Frozen dataclass.

| Field        | Type          | Description                                                            |
|--------------|---------------|------------------------------------------------------------------------|
| `text`       | `str`         | Full assistant response text                                           |
| `session_id` | `str`         | DeepSeek session identifier                                            |
| `message_id` | `str \| None` | Assistant message ID. Passed as `parent_message_id` in the next turn |

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import DeepSeekTurnResult

async def main():
    async with DeepSeekClient(token="...") as client:
        result: DeepSeekTurnResult = await client.ask("Hello")
        print(result.text)
        print(result.session_id)
        print(result.message_id)

asyncio.run(main())
```

---

## UploadedImage

```python
from aiodeepseek.types.models.classes import UploadedImage
```

Returned by [`DeepSeekClient.upload_image()`](client.md#upload_image). Represents an image already uploaded to the server.

| Field        | Type  | Description                    |
|--------------|-------|--------------------------------|
| `file_id`    | `str` | File identifier on the server  |
| `size_bytes` | `int` | File size in bytes             |
| `width`      | `int` | Image width in pixels          |
| `height`     | `int` | Image height in pixels         |

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import UploadedImage

async def main():
    async with DeepSeekClient(token="...") as client:
        img: UploadedImage = await client.upload_image(Path("photo.jpg"))
        print(img.file_id, img.width, img.height)
        result = await client.ask("What is in the photo?", image=img)
        print(result.text)

asyncio.run(main())
```

`UploadedImage` can be passed repeatedly into different `ask` / `ask_stream` calls without re-uploading.

---

## See also

- [DeepSeekClient](client.md)
- [Conversation](conversation.md)
- [Exceptions](exceptions.md)
