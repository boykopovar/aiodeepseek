# Исключения

Все исключения библиотеки наследуют `AioDeepSeekError`.

---

## Иерархия

```
AioDeepSeekError
└── DeepSeekError
    ├── PowNotSolvedError
    ├── DeepSeekAPIError          (code != 0)
    │   ├── AuthorizationError    (code=40003)
    │   │   └── InvalidToken      (code=40003, msg contains "invalid token")
    │   └── (другие коды API)
    ├── DeepSeekBizError          (code=0, biz_code != 0)
    │   ├── WrongCredentialsError (biz_code=2, biz_msg contains "password_or_user_name_is_wrong")
    │   │── InvalidRefFileIdError (biz_code=9, biz_msg contains "invalid ref file id")
    │   └── (другие коды API)
    ├── EmptyUploadedFileError
    └── VisionUnavailableError    (SSE hint contains "vision is temporarily unavailable")
```

---

## AioDeepSeekError

```python
from aiodeepseek.types.exceptions import AioDeepSeekError
```

Базовый класс. Можно использовать для перехвата любой ошибки библиотеки.

---

## DeepSeekError

```python
from aiodeepseek.types.exceptions import DeepSeekError
```

Общая ошибка запроса к API.

| Атрибут  | Тип           | Описание                                           |
|----------|---------------|----------------------------------------------------|
| `status` | `int \| None` | HTTP-статус ответа, или `None` если ошибка не HTTP |

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import DeepSeekError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Привет")
    except DeepSeekError as e:
        print(e, e.status)

asyncio.run(main())
```

---

## DeepSeekAPIError

```python
from aiodeepseek.types.exceptions import DeepSeekAPIError
```

Сервер вернул ненулевой `code` в JSON-ответе.

| Атрибут | Тип            | Описание                  |
|---------|----------------|---------------------------|
| `code`  | `int`          | Код ошибки из поля `code` |
| `data`  | `dict \| None` | Полный распарсенный ответ |

---

## AuthorizationError

```python
from aiodeepseek.types.exceptions import AuthorizationError
```

Токен недействителен или устарел. Код API: `40003`.

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import AuthorizationError

async def main():
    try:
        async with DeepSeekClient(token="невалидный") as client:
            await client.ask("Привет")
    except AuthorizationError:
        print("Токен недействителен, нужно получить новый")

asyncio.run(main())
```

---

## InvalidToken

```python
from aiodeepseek.types.exceptions import InvalidToken
```

Токен явно отклонён сервером. Подкласс `AuthorizationError`. Выбрасывается при коде `40003` с подстрокой `"invalid token"` в сообщении.

---

## DeepSeekBizError

```python
from aiodeepseek.types.exceptions import DeepSeekError
```

Верхнеуровневый `code=0`, но `biz_code` ненулевой - ошибка прикладного уровня.

| Атрибут    | Тип            | Описание                    |
|------------|----------------|-----------------------------|
| `biz_code` | `int`          | Код из поля `biz_code`      |
| `biz_msg`  | `str`          | Сообщение из поля `biz_msg` |
| `data`     | `dict \| None` | Полный распарсенный ответ   |

---

## WrongCredentialsError

Подкласс `DeepSeekBizError`. Выбрасывается при неверном email или пароле при поптыке входа в аккаунт (`biz_code=2`, `biz_msg` содержит `PASSWORD_OR_USER_NAME_IS_WRONG`).

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import DeepSeekError

async def main():
    try:
        async with DeepSeekClient(email="me@x.com", password="wrong") as client:
            pass
    except DeepSeekError as e:
        print("Неверные учётные данные:", e)

asyncio.run(main())
```

---

## VisionUnavailableError

```python
from aiodeepseek.types.exceptions import VisionUnavailableError
```

DeepSeek временно не обрабатывает машинным зрением (`ModelType.DEFAULT` все еще может распознать изображения с помощью `OCR`). Выбрасывается из SSE-потока при получении hint-события с текстом `"vision is temporarily unavailable"`.

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import VisionUnavailableError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            img = await client.upload_image(Path("photo.jpg"))
            result = await client.ask("Опиши", image=img)
    except VisionUnavailableError:
        print("Vision временно недоступен, попробуйте позже")

asyncio.run(main())
```


---

## PowNotSolvedError

```python
from aiodeepseek.types.exceptions import PowNotSolvedError
```

Solver не нашёл нонс в пределах `difficulty`. Подробнее - в [pow.md](pow.md).

| Атрибут      | Тип   | Описание                              |
|--------------|-------|---------------------------------------|
| `salt`       | `str` | Соль из задачи сервера                |
| `expire_at`  | `str` | Время истечения задачи                |
| `difficulty` | `int` | Максимальное число итераций           |
| `challenge`  | `str` | Ожидаемый хеш (hex)                   |
| `algorithm`  | `str` | Алгоритм, например `"DeepSeekHashV1"` |
| `signature`  | `str` | Подпись задачи от сервера             |

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import PowNotSolvedError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Привет")
    except PowNotSolvedError as e:
        print(f"PoW провалился: difficulty={e.difficulty}, challenge={e.challenge}")

asyncio.run(main())
```

---

## EmptyUploadedFileError

```python
from aiodeepseek.types.exceptions import EmptyUploadedFileError
```

Сервер вернул статус `CONTENT_EMPTY` во время поллинга загруженного файла - файл пустой или не был распознан бэкендом DeepSeek.

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import EmptyUploadedFileError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Опиши", image=Path("empty.jpg"))
    except EmptyUploadedFileError as e:
        print(f"Файл отклонён сервером: {e}")

asyncio.run(main())
```

---

## InvalidRefFileIdError

```python
from aiodeepseek.types.exceptions import InvalidRefFileIdError
```

Подкласс `DeepSeekBizError`. Выбрасывается когда прикреплённый файл не может быть привязан к запросу (`biz_code=9`, `biz_msg` содержит `invalid ref file id`). Обычно означает что файл ещё обрабатывается, был отклонён или его `file_id` уже недействителен.

| Атрибут    | Тип            | Описание             |
|------------|----------------|----------------------|
| `biz_code` | `int`          | `9`                  |
| `biz_msg`  | `str`          | Сообщение от сервера |
| `data`     | `dict \| None` | Полный ответ         |

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import InvalidRefFileIdError

async def main():
    try:
        async with DeepSeekClient(token="...") as client:
            await client.ask("Опиши", image=Path("photo.jpg"))
    except InvalidRefFileIdError as e:
        print(f"Файл не принят: biz_code={e.biz_code}, msg={e.biz_msg}")

asyncio.run(main())
```


## Смотрите также

- [DeepSeekClient](client.md)
- [Типы данных](types.md)
