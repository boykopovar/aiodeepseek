# DeepSeekClient

Главный класс библиотеки. Наследует полную цепочку:

```
_BaseClient → _AuthClient → _ChatClient → _FilesClient → DeepSeekClient
```

---

## Конструктор

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

| Параметр    | Тип             | Описание                                                     |
|-------------|-----------------|--------------------------------------------------------------|
| `token`     | `str \| None`   | Bearer-токен. Если не указан - нужны `email` + `password`    |
| `email`     | `str \| None`   | Email аккаунта DeepSeek                                      |
| `password`  | `str \| None`   | Пароль аккаунта                                              |
| `model`     | `ModelType`     | Модель по умолчанию (`ModelType.DEFAULT`)                    |
| `device_id` | `str \| None`   | Идентификатор устройства. Выбирается случайно если не указан |
| `timeout`   | `float \| None` | Таймаут запросов в секундах. `None` - без ограничений        |

Клиент используется как контекстный менеджер:

```python
from aiodeepseek import DeepSeekClient

async with DeepSeekClient(token="...") as client:
    ...
```

Или вручную:

```python
from aiodeepseek import DeepSeekClient

async def main():
    client = DeepSeekClient(token="...")
    await client.open()
    await client.ask("Привет")
    await client.close()
```

---

## Свойство token

```python
from aiodeepseek import DeepSeekClient

async with DeepSeekClient(email="mymail@example.com", password="pass") as client:
    print(client.token)
```

Возвращает текущий Bearer-токен или `None` до открытия сессии.

---

## ask

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import DeepSeekTurnResult


async def main():
    async with DeepSeekClient(token="...") as client:
        result: DeepSeekTurnResult = await client.ask("Что такое Python?")
        print(result.text)
```

Отправляет сообщение и возвращает полный ответ.

| Параметр            | Тип                                      | Описание                                           |
|---------------------|------------------------------------------|----------------------------------------------------|
| `prompt`            | `str`                                    | Сообщение пользователя                             |
| `image`             | `UploadedImage \| bytes \| Path \| None` | Прикреплённое изображение                          |
| `model`             | `ModelType \| None`                      | Переопределить модель для этого вызова             |
| `timeout`           | `float \| None`                          | Переопределить таймаут для этого вызова            |
| `parent_message_id` | `str \| None`                            | ID предыдущего ответа для продолжения нити диалога |

Возвращает [`DeepSeekTurnResult`](types.md#deepseekturnresult).

---

## ask_stream

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        last = 0
        async for chunk in client.ask_stream("Объясни async/await"):
            print(chunk[last:], end="", flush=True)
            last = len(chunk)

asyncio.run(main())
```

Стримит ответ. Каждый yielded-кусок - это **полный накопленный текст** на текущий момент.

Принимает те же параметры, что и `ask`.

---

## upload_image

```python
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import UploadedImage


async def main():
    async with DeepSeekClient(token="...") as client:
        img: UploadedImage = await client.upload_image(Path("photo.png"))
        result = await client.ask("Опиши изображение", image=img)
```

Загружает PNG или JPEG на сервер и возвращает [`UploadedImage`](types.md#uploadedimage).

| Параметр   | Тип             | Описание                      |
|------------|-----------------|-------------------------------|
| `source`   | `Path \| bytes` | Путь к файлу или сырые байты  |
| `filename` | `str \| None`   | Имя файла в multipart-запросе |
| `timeout`  | `float \| None` | Переопределить таймаут        |

---

## new_conversation

```python
from aiodeepseek import DeepSeekClient, Conversation

async def main():
    async with DeepSeekClient(token="...") as client:
        chat: Conversation = client.new_conversation()
        await chat.ask("Привет")
        await chat.ask("Продолжи")
```

Создаёт объект [`Conversation`](conversation.md), который автоматически отслеживает `parent_message_id` между ходами.

---

## Статические методы аутентификации

### send_reg_code

```python
from aiodeepseek import DeepSeekClient

async def main():
    await DeepSeekClient.send_reg_code("mymail@example.com")
```

Отправляет код подтверждения на email для регистрации.

| Параметр    | Тип           | Описание                        |
|-------------|---------------|---------------------------------|
| `email`     | `str`         | Email для регистрации           |
| `locale`    | `str`         | Локаль (`"en_US"` по умолчанию) |
| `device_id` | `str \| None` | Идентификатор устройства        |

### confirm_reg_code

```python
from aiodeepseek import DeepSeekClient

async def main():
    token = await DeepSeekClient.confirm_reg_code(
        "me@example.com",
        "мойпароль",
        "123456",
    )
    print(token)
```

Завершает регистрацию и возвращает Bearer-токен. Перед отправкой автоматически решает [PoW-задачу](pow.md).

| Параметр    | Тип           | Описание                         |
|-------------|---------------|----------------------------------|
| `email`     | `str`         | Email                            |
| `password`  | `str`         | Желаемый пароль                  |
| `code`      | `str`         | Код из письма                    |
| `region`    | `str`         | Код страны (`"BY"` по умолчанию) |
| `locale`    | `str`         | Локаль (`"ru"` по умолчанию)     |
| `device_id` | `str \| None` | Идентификатор устройства         |

### fetch_token

```python
from aiodeepseek import DeepSeekClient

async def main():
    token = await DeepSeekClient.fetch_token("mymail@example.com", "password")
```

Выполняет логин и возвращает Bearer-токен. Не требует открытого экземпляра клиента.

---

## Смотрите также

- [Conversation](conversation.md)
- [Типы данных](types.md)
- [Исключения](exceptions.md)
- [Proof-of-Work](pow.md)
