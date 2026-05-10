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

Базовый класс. Можно использовать для перехвата любой ошибки библиотеки.

---

## DeepSeekError

```python
from aiodeepseek.types.exceptions import DeepSeekError
```

Общая ошибка запроса к API.

| Атрибут  | Тип           | Описание                                           |
|----------|----------------|----------------------------------------------------|
| `status` | `int \| None` | HTTP-статус ответа, или `None` если ошибка не HTTP |

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

---

## VisionUnavailableError

```python
from aiodeepseek.types.exceptions import VisionUnavailableError
```

DeepSeek временно не обрабатывает машинным зрением (`ModelType.DEFAULT` все еще может распознать изображения с помощью `OCR`). Выбрасывается из SSE-потока при получении hint-события с текстом `"vision is temporarily unavailable"`.

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

---

## EmptyUploadedFileError

```python
from aiodeepseek.types.exceptions import EmptyUploadedFileError
```

Сервер вернул статус `CONTENT_EMPTY` во время поллинга загруженного файла - файл пустой или не был распознан бэкендом DeepSeek.

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

---

## Смотрите также

- [DeepSeekClient](client.md)
- [Типы данных](types.md)
