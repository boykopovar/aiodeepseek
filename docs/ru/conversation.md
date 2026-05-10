# Conversation

Обёртка для многоходового диалога. Автоматически передаёт `parent_message_id` каждого ответа в следующий запрос, сохраняя нить разговора внутри одной сессии.

Получается через [`DeepSeekClient.new_conversation()`](client.md#new_conversation).

---

## Создание

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()
        print((await chat.ask("Как тебя зовут?")).text)
        print((await chat.ask("Что ты умеешь?")).text)
        print((await chat.ask("Расскажи подробнее")).text)

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
        reply = await chat.ask("Напиши стих про китов")
        print(reply.text)

asyncio.run(main())
```

Отправляет сообщение, обновляет `parent_message_id` и возвращает объект ответа:

```python
class DeepSeekTurnResult:
    text: str
    session_id: str
    message_id: str | None = None
```

| Параметр  | Тип                                      | Описание                             |
|-----------|------------------------------------------|--------------------------------------|
| `prompt`  | `str`                                    | Сообщение пользователя               |
| `image`   | `UploadedImage \| bytes \| Path \| None` | Прикреплённое изображение            |
| `model`   | `str \| None`                            | Переопределить модель для этого хода |
| `timeout` | `float \| None`                          | Переопределить таймаут               |

---

## ask_stream

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()

        async for chunk in chat.ask_stream("Перечисли планеты"):
            print(chunk, end="", flush=True)

        print()

asyncio.run(main())
```

Стримит ответ и автоматически обновляет состояние диалога после завершения стрима.

По умолчанию каждый yielded-кусок содержит только новый фрагмент текста.

Используйте `cumulative=True`, чтобы получать полный накопленный ответ на каждой итерации.

```python
async for chunk in chat.ask_stream(
    "Перечисли планеты",
    cumulative=True,
):
    print(chunk)
```

Принимает те же параметры, что и `ask`, плюс:

| Параметр     | Тип    | Описание                                               |
|--------------|--------|--------------------------------------------------------|
| `cumulative` | `bool` | Возвращать накопленный текст вместо новых фрагментов   |

---

## parent_message_id

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        chat = client.new_conversation()
        await chat.ask("Первый вопрос")
        print(chat.parent_message_id)

asyncio.run(main())
```

Свойство. ID последнего ответа ассистента, или `None` до первого хода.

---

## Диалог с изображением

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="...") as client:
        img = await client.upload_image(Path("chart.png"))
        chat = client.new_conversation()
        print((await chat.ask("Что на этом графике?", image=img)).text)
        print((await chat.ask("Какой самый высокий столбец?")).text)

asyncio.run(main())
```

---

## Смотрите также

- [DeepSeekClient](client.md)
- [Типы данных](types.md)
