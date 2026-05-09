# aiodeepseek

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey)
![License](https://img.shields.io/github/license/boykopovar/aiodeepseek)
![CI](https://img.shields.io/github/actions/workflow/status/boykopovar/aiodeepseek/python.yml?branch=main)
![DeepSeek](https://img.shields.io/badge/API-DeepSeek-black)

Асинхронный Python-клиент для неофициального iOS API DeepSeek. Поддерживает стриминг, загрузку изображений, многоходовые диалоги и регистрацию новых аккаунтов.

## Установка

```bash
pip install git+ssh://git@github.com/boykopovar/aiodeepseek.git -U
```

Для сборки C++-расширения нужен компилятор с поддержкой AVX2 и `pybind11`. Подробнее - в [docs/ru/pow.md](docs/ru/pow.md). Или можно скачать уже собранный [релиз](https://github.com/boykopovar/aiodeepseek/releases).

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
        last_len = 0
        async for chunk in client.ask_stream("Расскажи о Python"):
            print(chunk[last_len:], end="", flush=True)
            last_len = len(chunk)

asyncio.run(main())
```

### Многоходовый диалог

```python
import asyncio
from aiodeepseek import DeepSeekClient

async def main():
    async with DeepSeekClient(token="ВАШ_ТОКЕН") as client:
        chat = client.new_conversation()
        print(await chat.ask("Как тебя зовут?"))
        print(await chat.ask("А что ты умеешь?"))

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

Перед каждым запросом клиент автоматически решает PoW-задачу, выдаваемую сервером DeepSeek. Типичная сложность - **144 000 итераций**. Расчёт реализован на C++ с использованием AVX2, что делает его малозаметным на практике. Подробнее - в [docs/ru/pow.md](docs/ru/pow.md).

---

## Документация

- [DeepSeekClient - методы клиента](docs/ru/client.md)
- [Conversation - многоходовый диалог](docs/ru/conversation.md)
- [Типы и модели данных](docs/ru/types.md)
- [Исключения](docs/ru/exceptions.md)
- [Proof-of-Work](docs/ru/pow.md)

---

## Требования

- Python 3.9+
- `aiohttp >= 3.9`
- Компилятор C++17 с AVX2 (для сборки расширения) или вручную скачанные колеса.
