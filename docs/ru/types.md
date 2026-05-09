# Типы данных

---

## ModelType

```python
from aiodeepseek.types.enums import ModelType
```

Перечисление доступных моделей.

| Значение            | Строка      | Описание                        |
|---------------------|-------------|---------------------------------|
| `ModelType.DEFAULT` | `"default"` | Стандартная языковая модель     |
| `ModelType.EXPERT`  | `"expert"`  | Расширенная модель              |
| `ModelType.VISION`  | `"vision"`  | Модель с поддержкой изображений |

`ModelType` наследует `str`, поэтому `str(ModelType.DEFAULT) == "default"`.

Передаётся в конструктор клиента или в методы `ask` / `ask_stream`:

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.enums import ModelType

async def main():
    async with DeepSeekClient(token="...", model=ModelType.EXPERT) as client:
        result = await client.ask("Сложный вопрос", model=ModelType.VISION)

```

---

## DeepSeekTurnResult

```python
from aiodeepseek.types.models.classes import DeepSeekTurnResult
```

Возвращается методом [`DeepSeekClient.ask()`](client.md#ask). Frozen dataclass.

| Поле         | Тип           | Описание                                                                     |
|--------------|---------------|------------------------------------------------------------------------------|
| `text`       | `str`         | Полный текст ответа ассистента                                               |
| `session_id` | `str`         | Идентификатор сессии DeepSeek                                                |
| `message_id` | `str \| None` | ID сообщения ассистента. Передаётся как `parent_message_id` в следующем ходе |

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import DeepSeekTurnResult


async def main():
    async with DeepSeekClient(token="...") as client:
        result: DeepSeekTurnResult = await client.ask("Привет")
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

Возвращается методом [`DeepSeekClient.upload_image()`](client.md#upload_image). Представляет уже загруженное на сервер изображение.

| Поле         | Тип   | Описание                       |
|--------------|-------|--------------------------------|
| `file_id`    | `str` | Идентификатор файла на сервере |
| `size_bytes` | `int` | Размер файла в байтах          |
| `width`      | `int` | Ширина изображения в пикселях  |
| `height`     | `int` | Высота изображения в пикселях  |

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.models.classes import UploadedImage


async def main():
    async with DeepSeekClient(token="...") as client:
        img: UploadedImage = await client.upload_image(Path("photo.jpg"))
        print(img.file_id, img.width, img.height)
        result = await client.ask("Что на фото?", image=img)
        print(result.text)


asyncio.run(main())
```

`UploadedImage` можно передавать повторно в разные вызовы `ask` / `ask_stream` без повторной загрузки.

---

## Смотрите также

- [DeepSeekClient](client.md)
- [Conversation](conversation.md)
- [Исключения](exceptions.md)
