# Exceptions

All library exceptions inherit from `AioDeepSeekError`.

---

## Hierarchy

```
AioDeepSeekError
└── DeepSeekError
    ├── PowNotSolvedError
    ├── DeepSeekAPIError          (code != 0)
    │   ├── AuthorizationError    (code=40003)
    │   │   └── InvalidToken      (code=40003, msg contains "invalid token")
    │   └── (other API codes)
    ├── DeepSeekBizError          (code=0, biz_code != 0)
    │   ├── WrongCredentialsError (biz_code=2, biz_msg contains "password_or_user_name_is_wrong")
    │   │── InvalidRefFileIdError (biz_code=9, biz_msg contains "invalid ref file id")
    │   └── (other API codes)
    ├── EmptyUploadedFileError
    └── VisionUnavailableError    (SSE hint contains "vision is temporarily unavailable")
```

---

## AioDeepSeekError

```python
from aiodeepseek.types.exceptions import AioDeepSeekError
```

Base class. Can be used to catch any library error.

---

## DeepSeekError

```python
from aiodeepseek.types.exceptions import DeepSeekError
```

General API request error.

| Attribute | Type          | Description                                      |
|----------|---------------|--------------------------------------------------|
| `status` | `int \| None` | HTTP response status, or `None` if not HTTP     |

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import DeepSeekError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Hello")
    except DeepSeekError as e:
        print(e, e.status)

asyncio.run(main())
```

---

## DeepSeekAPIError

```python
from aiodeepseek.types.exceptions import DeepSeekAPIError
```

The server returned a non-zero `code` in the JSON response.

| Attribute | Type           | Description          |
|----------|----------------|----------------------|
| `code`   | `int`          | Error code from `code` |
| `data`   | `dict \| None` | Full parsed response  |

---

## AuthorizationError

```python
from aiodeepseek.types.exceptions import AuthorizationError
```

The token is invalid or expired. API code: `40003`.

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import AuthorizationError

async def main():
    try:
        async with DeepSeekClient(token="invalid") as client:
            await client.ask("Hello")
    except AuthorizationError:
        print("Token is invalid, a new one is required")

asyncio.run(main())
```

---

## InvalidToken

```python
from aiodeepseek.types.exceptions import InvalidToken
```

The token was explicitly rejected by the server. Subclass of `AuthorizationError`. Raised for code `40003` with the substring `"invalid token"` in the message.

---

## DeepSeekBizError

```python
from aiodeepseek.types.exceptions import DeepSeekError
```

Top-level `code=0`, but `biz_code` is non-zero — an application-level error.

| Attribute  | Type           | Description              |
|-----------|----------------|--------------------------|
| `biz_code` | `int`          | Code from `biz_code`     |
| `biz_msg`  | `str`          | Message from `biz_msg`   |
| `data`     | `dict \| None` | Full parsed response     |

---

## WrongCredentialsError

Subclass of `DeepSeekBizError`. Raised for an incorrect email or password when signing in (`biz_code=2`, `biz_msg` contains `PASSWORD_OR_USER_NAME_IS_WRONG`).

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import DeepSeekError

async def main():
    try:
        async with DeepSeekClient(email="me@x.com", password="wrong") as client:
            pass
    except DeepSeekError as e:
        print("Invalid credentials:", e)

asyncio.run(main())
```

---

## VisionUnavailableError

```python
from aiodeepseek.types.exceptions import VisionUnavailableError
```

DeepSeek is temporarily not processing machine vision (`ModelType.DEFAULT` can still recognize images using OCR). Raised from the SSE stream when a hint event with the text `"vision is temporarily unavailable"` is received.

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import VisionUnavailableError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            img = await client.upload_image(Path("photo.jpg"))
            result = await client.ask("Describe it", image=img)
    except VisionUnavailableError:
        print("Vision is temporarily unavailable, try again later")

asyncio.run(main())
```

---

## PowNotSolvedError

```python
from aiodeepseek.types.exceptions import PowNotSolvedError
```

The solver did not find a nonce within `difficulty`. More details in [pow.md](pow.md).

| Attribute    | Type           | Description                               |
|-------------|----------------|-------------------------------------------|
| `salt`      | `str`          | Salt from the server challenge            |
| `expire_at` | `str`          | Challenge expiration time                 |
| `difficulty`| `int`          | Maximum number of iterations              |
| `challenge` | `str`          | Expected hash (hex)                       |
| `algorithm` | `str`          | Algorithm, for example `"DeepSeekHashV1"` |
| `signature`  | `str`          | Server challenge signature                |

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import PowNotSolvedError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Hello")
    except PowNotSolvedError as e:
        print(f"PoW failed: difficulty={e.difficulty}, challenge={e.challenge}")

asyncio.run(main())
```

---

## EmptyUploadedFileError

```python
from aiodeepseek.types.exceptions import EmptyUploadedFileError
```

The server returned `CONTENT_EMPTY` while polling an uploaded file — the file is empty or was not recognized by the DeepSeek backend.

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import EmptyUploadedFileError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Describe it", image=Path("empty.jpg"))
    except EmptyUploadedFileError as e:
        print(f"File rejected by server: {e}")

asyncio.run(main())
```

---

## InvalidRefFileIdError

```python
from aiodeepseek.types.exceptions import InvalidRefFileIdError
```

Subclass of `DeepSeekBizError`. Raised when the attached file cannot be bound to the request (`biz_code=9`, `biz_msg` contains `invalid ref file id`). Usually means the file is still being processed, was rejected, or its `file_id` is no longer valid.

| Attribute  | Type           | Description        |
|-----------|----------------|--------------------|
| `biz_code` | `int`          | `9`                |
| `biz_msg`  | `str`          | Server message     |
| `data`     | `dict \| None` | Full response      |

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import InvalidRefFileIdError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Describe it", image=Path("photo.jpg"))
    except InvalidRefFileIdError as e:
        print(f"File not accepted: biz_code={e.biz_code}, msg={e.biz_msg}")

asyncio.run(main())
```

---

## See also

- [DeepSeekClient](client.md)
- [Data types](types.md)
