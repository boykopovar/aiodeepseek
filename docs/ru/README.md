# aiodeepseek

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey)
![Async](https://img.shields.io/badge/asyncio-fully%20async-blueviolet)
![DeepSeek](https://img.shields.io/badge/API-DeepSeek-blue)

Высокопроизводительный async Python клиент для приватного API DeepSeek. Поддерживает стриминг, загрузку изображений, многоходовые диалоги, регистрацию новых аккаунтов.

## Установка

```bash
pip install aiodeepseek
```

Для сборки C++-расширения нужен компилятор с поддержкой AVX2 и `pybind11`. Подробнее - в [pow.md](pow.md). Или можно скачать уже собранный [релиз](https://github.com/boykopovar/aiodeepseek/releases).

---

## Быстрый старт

### Авторизация по email/паролю

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(email="myname@example.com", password="password123") as client:
        result = await client.ask("Привет!")
        print(result.text)

asyncio.run(main())
```

### Авторизация по токену

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="ВАШ_ТОКЕН") as client:
        result = await client.ask("Привет!")
        print(result.text)

asyncio.run(main())
```

### Стриминг ответа

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="ВАШ_ТОКЕН") as client:
        async for chunk in client.ask_stream("Расскажи о Python"):
            print(chunk, end="", flush=True)

asyncio.run(main())
```

### Многоходовый диалог

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="ВАШ_ТОКЕН") as client:
        chat = client.new_conversation()
        print((await chat.ask("Как тебя зовут?")).text)
        print((await chat.ask("А что ты умеешь?")).text)

asyncio.run(main())
```

### Загрузка изображения

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="ВАШ_ТОКЕН") as client:
        img = await client.upload_image(Path("photo.jpg"))
        result = await client.ask("Что на фото?", image=img)
        print(result.text)

asyncio.run(main())
```

или передав `Path | bytes` в `ask`:

```python
import asyncio
from pathlib import Path
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="ВАШ_ТОКЕН") as client:
        result = await client.ask(
            prompt="Что на фото?",
            image=Path("photo.jpg")
        )
        print(result.text)

asyncio.run(main())
```

### Регистрация нового аккаунта

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    await DeepSeekClient.send_reg_code("myname@example.com")
    code = input("Код из письма: ")
    token = await DeepSeekClient.confirm_reg_code("myname@example.com", "password123", code)
    print("Токен:", token)

asyncio.run(main())
```

---

## Типы модели

```python
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.enums import ModelType

async with DeepSeekClient(token="...", model=ModelType.VISION) as client:
    ...
```

| Значение            | Описание                             |
|---------------------|--------------------------------------|
| `ModelType.DEFAULT` | Стандартная языковая модель          |
| `ModelType.EXPERT`  | Модель с глубоким мышлением          |
| `ModelType.VISION`  | Модель с поддержкой машинного зрения |

---

## Обработка ошибок

```python
import asyncio
from aiodeepseek import DeepSeekClient
from aiodeepseek.types.exceptions import AuthorizationError, DeepSeekError

async def main():
    try:
        async with DeepSeekClient(token="невалидный") as client:
            await client.ask("Привет")
    except AuthorizationError:
        print("Токен недействителен")
    except DeepSeekError as e:
        print(f"Ошибка API: {e}")

asyncio.run(main())
```

---

## Proof-of-Work

Перед каждым запросом клиент автоматически решает PoW-задачу, выдаваемую сервером DeepSeek. Типичная сложность - **144 000 итераций**. Расчёт реализован на C++ с использованием AVX2, что делает его малозаметным на практике. Подробнее - в [pow.md](pow.md).

---

## Документация

- [DeepSeekClient - методы клиента](client.md)
- [Conversation - многоходовой диалог](conversation.md)
- [Типы и модели данных](types.md)
- [Исключения](exceptions.md)
- [Proof-of-Work](pow.md)

---

## Требования

- Python 3.9+
- `aiohttp >= 3.9`
- Компилятор C++17 с AVX2 (для сборки расширения) или вручную скачанные колеса.
