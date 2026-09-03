# Упаковка и деплой: Docker, конфиг из окружения, структурированное логирование

## Теория

**Multi-stage Dockerfile.** Идея та же, что в многостадийных сборках Node (`FROM node AS builder ... FROM node:alpine AS runtime COPY --from=builder ...`) — разделить "стадию сборки" (нужны компиляторы, dev-заголовки) от "стадии рантайма" (нужен только готовый рантайм и уже установленные зависимости):

```dockerfile
# ---- builder: компилируем зависимости, включая C-расширения вроде bcrypt ----
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --prefix=/install .

# ---- runtime: только установленные пакеты и код приложения, без компиляторов ----
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src ./src

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "taskman.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

`slim` (Debian-based, glibc) — практически всегда безопасный выбор по умолчанию для Python с C-расширениями (`bcrypt`, `aiosqlite`): у большинства пакетов есть готовые `manylinux`-колёса под glibc.

`alpine` (musl libc) даёт меньший образ. Но иногда у пакетов нет готовых `musllinux`-колёс, и pip пытается собрать расширение из исходников прямо в контейнере.

Экономия на размере образа тогда оборачивается необходимостью тащить в `alpine`-образ те же компиляторы, которые multi-stage сборка как раз пытается исключить из финального слоя.

**Переменные окружения через `pydantic-settings`.** В главе 15 `SECRET_KEY` был явно захардкожен в коде с пометкой "change me in production". Та глава прямо назвала это своей "частой ошибкой": так нельзя оставлять в реальном проекте.

Пакет `pydantic-settings` — прямой, правильный способ это исправить. `BaseSettings` — та же самая Pydantic-модель, что в главе 13. Она только читает значения полей не из тела HTTP-запроса, а из переменных окружения и, при желании, из `.env`-файла. Валидация и приведение типов те же самые:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TASKMAN_")

    secret_key: str                                    # обязательное, без дефолта
    access_token_expire_minutes: int = 30
    database_path: str = "taskman.db"

settings = Settings()
```

Без дефолта у `secret_key` приложение просто не запустится, если переменная окружения не задана. Вы получите `pydantic.ValidationError` прямо при импорте модуля, а не тихий запуск с пустым или предсказуемым секретом. Это осознанно: секрет, у которого **есть** безопасный дефолт, по определению не может быть секретом.

**Реальный, эмпирически найденный нюанс: mypy и `BaseSettings`.** `Settings()` вызывается без единого аргумента, но `secret_key: str` без дефолта формально требует передать значение.

Команда `mypy --strict` на это честно ругается: `Missing named argument "secret_key" for "Settings"`. Статически неоткуда знать, что значение появится из окружения в рантайме. Решение — не ослаблять типы, а подключить mypy-плагин самого Pydantic, который умеет это понимать:

```toml
[tool.mypy]
plugins = ["pydantic.mypy"]
strict = true
```

**Структурированное логирование.** До этой главы логи API шли через `print(...)` (глава 14). Для разработки это годится, но не для продакшена: логи нужно **парсить** машиной.

Системы агрегации логов ищут структурированные поля, а не режут текст регулярками. Самые известные — CloudWatch, Datadog и ELK (Elasticsearch, Logstash и Kibana в связке). Минимальный структурированный формат — JSON-строка на событие, через стандартный `logging`:

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })
```

Дополнительные поля (метод, путь, статус, длительность) передаются через `extra={...}` в вызове `logger.info(...)` — они прикрепляются как атрибуты объекта `LogRecord`, и форматтер достаёт их через `getattr(record, "field_name", None)`.

**Healthcheck-эндпоинт — не просто "жив ли процесс".** `GET /health`, возвращающий `{"status": "ok"}` безусловно, почти бесполезен: он никогда не сможет просигналить о поломке, даже если база данных недоступна. Настоящий healthcheck делает тривиальный запрос к тому, от чего реально зависит сервис:

```python
@router.get("/health")
async def health_check() -> dict[str, str]:
    await db.ping()   # SELECT 1 — просто подтвердить, что БД отвечает
    return {"status": "ok"}
```

Если `ping()` бросит исключение, потому что БД (база данных) недоступна или повреждена, эндпоинт вернёт `500` естественным образом. Специальный `try/except` не нужен. Собственный `HEALTHCHECK` Docker или оркестратор — например, Kubernetes с его liveness- и readiness-пробами — увидят это как "нездоров".

### Параллели с JS/TS/Node:

- Multi-stage Dockerfile — тот же приём, что в Node-проектах: builder-стадия с компиляторами, runtime-стадия — только готовые артефакты.
- `pydantic-settings` ~ `dotenv` + ручное приведение типов из `process.env`, только валидация и приведение происходят автоматически, а не вручную на каждой переменной.
- Structured JSON logging — тот же принцип, что `pino`/`winston` с JSON-транспортом в Node: логи как данные, а не как текст для человека.
- Healthcheck-эндпоинт — тот же концепт, что `/healthz`/`/readyz` в любом Node-сервисе за оркестратором; разница только в том, что реализуется он вручную, а не библиотекой.

## Что добавляем в проект

Полностью докеризуем сервис: multi-stage `Dockerfile` и `docker-compose.yml` с именованным volume под файл SQLite. Без volume база пересоздавалась бы с нуля при каждом пересоздании контейнера.

`SECRET_KEY` и путь к базе переезжают из захардкоженных констант в `config.py` на основе `pydantic-settings`. Логирование в API-слое (`middleware.py`) переходит с `print()` на структурированный JSON через стандартный `logging`. Появляется `GET /health`, реально проверяющий соединение с БД, а не просто отвечающий "ок" безусловно.

## Практическое задание

1. Добавьте `pydantic-settings` в зависимости. Создайте `config.py` с `Settings(BaseSettings)`: `secret_key: str` (без дефолта), `access_token_expire_minutes: int = 30`, `database_path: str = "taskman.db"`, `env_prefix="TASKMAN_"`, `env_file=".env"`. Создайте модуль-level `settings = Settings()`.
2. Обновите `auth/security.py` и `storage/sqlite_storage.py`, чтобы использовать `settings.secret_key`/`settings.access_token_expire_minutes`/`settings.database_path` вместо захардкоженных констант.
3. Добавьте `plugins = ["pydantic.mypy"]` в `[tool.mypy]` и убедитесь, что `mypy --strict` проходит на `config.py` без ошибок.
4. В `tests/conftest.py` установите `TASKMAN_SECRET_KEY` через `os.environ.setdefault(...)` **до** первого импорта чего-либо из `taskman` — подумайте, почему порядок здесь принципиален.
5. Создайте `logging_config.py` с `JSONFormatter` и `configure_logging()`. Вызовите `configure_logging()` в `lifespan` приложения (до `await db.init_db()`).
6. Замените `print(...)` в `api/middleware.py` на `logger.info(...)`/`logger.exception(...)` с полями `method`/`path`/`status_code`/`duration_ms` через `extra={...}`.
7. Добавьте `storage/sqlite_storage.py:ping()` (тривиальный `SELECT 1`) и `api/routes_health.py` с `GET /health`, вызывающим `db.ping()`.
8. Напишите multi-stage `Dockerfile` (builder + runtime), `.dockerignore`, `.env.example` (документирует нужные переменные, сам `.env` — не коммитится).
9. Напишите `docker-compose.yml` с сервисом `api` и именованным volume, смонтированным туда, куда указывает `TASKMAN_DATABASE_PATH`.
10. Соберите образ и поднимите его через `docker compose up`. Создайте пользователя и задачу через `curl`. Затем **полностью удалите и пересоздайте контейнер** командой `docker compose down && docker compose up` и убедитесь, что задача никуда не делась.

## Разбор решения

`src/taskman/config.py` (новый файл):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TASKMAN_")

    secret_key: str
    access_token_expire_minutes: int = 30
    database_path: str = "taskman.db"


settings = Settings()
```

`src/taskman/logging_config.py` (новый файл):

```python
import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
```

`src/taskman/auth/security.py` (обновлён — читает настройки, а не константы):

```python
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..config import settings

ALGORITHM = "HS256"


def _prepare(password: str) -> bytes:
    """Сначала sha256, затем base64: bcrypt читает 72 байта и встаёт на нулевом."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)   # 44 байта -- всегда меньше лимита в 72


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prepare(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_prepare(password), hashed_password.encode("utf-8"))


def create_access_token(username: str) -> str:
    minutes = settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    username: str = payload["sub"]
    return username
```

`src/taskman/storage/sqlite_storage.py` (изменения — `DB_PATH` из настроек, добавлен `ping`; остальное как в главе 16):

```python
from ..config import settings
# ...
DB_PATH = Path(settings.database_path)
# ...

async def ping() -> None:
    """A trivial query used by the health check to confirm the database is reachable."""
    async with db_connection() as conn:
        await conn.execute("SELECT 1")
```

`src/taskman/storage/protocol.py` — добавлен `async def ping(self) -> None: ...` в `TaskStorage`.

`src/taskman/api/routes_health.py` (новый файл):

```python
from fastapi import APIRouter

from ..storage import db

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    await db.ping()
    return {"status": "ok"}
```

`src/taskman/api/middleware.py` (обновлён — структурированные логи вместо `print`):

```python
import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response

logger = logging.getLogger("taskman.api")


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
            },
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
```

`src/taskman/api/app.py` (обновлён — `configure_logging()` в lifespan, новый роутер здоровья):

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..logging_config import configure_logging
from ..models import TaskNotFoundError
from ..storage import db, users as users_storage
from .exceptions import task_not_found_handler
from .middleware import log_requests
from .routes import router
from .routes_auth import router as auth_router
from .routes_health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await db.init_db()
    await users_storage.init_users_table()
    yield


app = FastAPI(title="taskman", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(router)
app.include_router(health_router)
app.middleware("http")(log_requests)
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

`pyproject.toml` (добавлены зависимость и mypy-плагин):

```toml
[project]
dependencies = [
    "aiosqlite>=0.19",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pyjwt>=2.8",
    "bcrypt>=4.0",
    "python-multipart>=0.0.18",
    "pydantic-settings>=2.4",
]

[tool.mypy]
python_version = "3.11"
plugins = ["pydantic.mypy"]
strict = true
```

`tests/conftest.py` (начало файла — переменная окружения устанавливается до импорта приложения):

```python
import os

os.environ.setdefault("TASKMAN_SECRET_KEY", "test-secret-key-not-for-production")

from contextlib import asynccontextmanager  # noqa: E402
# ... остальные импорты taskman-модулей идут ПОСЛЕ установки переменной
```

`Dockerfile` (новый файл, полный текст — см. теорию выше).

`.env.example` (новый файл):

```bash
# Copy this file to .env and fill in real values for local development.
# In production, set these as real environment variables instead of a file.
TASKMAN_SECRET_KEY=change-me-to-a-long-random-value
TASKMAN_ACCESS_TOKEN_EXPIRE_MINUTES=30
TASKMAN_DATABASE_PATH=taskman.db
```

`docker-compose.yml` (новый файл):

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      TASKMAN_SECRET_KEY: ${TASKMAN_SECRET_KEY:?set TASKMAN_SECRET_KEY before starting}
      TASKMAN_DATABASE_PATH: /data/taskman.db
    volumes:
      - taskman-data:/data

volumes:
  taskman-data:
```

Реальный прогон это подтверждает: `docker compose up`, curl, `docker compose down`, затем `docker compose up` заново. Задача, созданная до пересоздания контейнера, видна и после. Она хранится в именованном volume `taskman-data`, смонтированном в `/data`, а не в файловой системе самого контейнера, которая уничтожается вместе с ним.

Ключевые решения:

- Строка `TASKMAN_DATABASE_PATH=/data/taskman.db` в `docker-compose.yml` указывает на путь **внутри volume**, а не на путь по умолчанию. По умолчанию это `taskman.db` в рабочей директории контейнера. Если оставить путь по умолчанию, база будет жить в обычном слое контейнера и исчезнет при его пересоздании, а volume останется пустым и бесполезным.
- `${TASKMAN_SECRET_KEY:?set TASKMAN_SECRET_KEY before starting}` в compose-файле — синтаксис "обязательная переменная", а не подстановка с тихим дефолтом. Без установленной переменной окружения `docker compose up` падает с понятным сообщением, а не запускает сервис с пустым или предсказуемым секретом.
- `plugins = ["pydantic.mypy"]` — без этой строчки `mypy --strict` требовал бы передавать `secret_key` в `Settings()` явным аргументом. А реальное значение приходит из окружения только в рантайме. Плагин учит mypy этой семантике `BaseSettings`, вместо того чтобы ослаблять строгость проверки в остальном коде.
- Переменная окружения для тестов (`TASKMAN_SECRET_KEY`) устанавливается **в самом начале** `conftest.py`, до единого `from taskman import ...`. Причина: `settings = Settings()` в `config.py` выполняется один раз, в момент **импорта** этого модуля, а не при каждом обращении к `settings`. Если переменная не установлена до первого импорта чего-либо, транзитивно тянущего `config.py`, приложение упадёт с `ValidationError`. Это случится ещё до того, как успеет выполниться хоть одна строчка теста.

## Проверь себя

1. Почему `Settings()` без единого аргумента — это осознанное, желаемое поведение, а не недосмотр, если `secret_key` не имеет дефолтного значения?
2. Что именно проверяет multi-stage сборка Docker-образа, и почему установка `gcc` в builder-стадии не увеличивает размер финального образа?
3. Почему `os.environ.setdefault("TASKMAN_SECRET_KEY", ...)` должен стоять физически раньше остальных импортов в `conftest.py`, а не просто "где-то в файле"?
4. Чем healthcheck, вызывающий `db.ping()`, отличается от healthcheck, безусловно возвращающего `{"status": "ok"}`, — в каком сценарии разница становится видна на практике?
5. Почему `docker-compose.yml` указывает `TASKMAN_DATABASE_PATH=/data/taskman.db`, а не просто монтирует volume и оставляет путь к базе по умолчанию?

<details>
<summary>Ответы</summary>

1. Потому что `secret_key` — это буквально то единственное, что делает подписи JWT (JSON Web Token) проверяемыми и недоступными для подделки (глава 15). Если бы у `Settings` был безопасный дефолт для секрета, этот дефолт по определению не мог бы быть секретом. Он был бы одинаковым во всех установках приложения, включая любую копию исходного кода. Поэтому `Settings()` без аргументов **обязан** упасть с ошибкой валидации, если переменная окружения не задана. Это "fail fast" вместо тихого запуска с предсказуемым, бесполезным в качестве секрета значением.
2. Multi-stage сборка гарантирует, что финальный образ содержит только то, что нужно **для исполнения** приложения: установленные Python-пакеты и код. Инструментов, нужных только для **сборки** этих пакетов, там нет — например, компилятора `gcc` для C-расширений вроде `bcrypt`. Пакет `gcc` устанавливается в стадии `builder`. Но `COPY --from=builder /install /usr/local` в стадии `runtime` копирует только каталог с уже собранными, готовыми пакетами. Сам `gcc` и слой apt, в котором он был установлен, попросту не попадают в финальный образ. Финальный образ строится с нуля от `FROM python:3.11-slim AS runtime`, а не наследует слои `builder`.
3. Потому что `Settings()` — и, соответственно, чтение `TASKMAN_SECRET_KEY` из окружения — выполняется **один раз**, в момент первого импорта модуля `config.py`. Заново при каждом обращении к `settings.secret_key` это не происходит. Любой более ранний `from taskman.something import ...`, который транзитивно импортирует `config.py`, зафиксирует `settings` с уже прочитанным или отсутствующим значением переменной. А импортирует его почти всё: `auth/security.py`, `storage/sqlite_storage.py`. Если переменную установить позже, это уже не поможет: `Settings()` к этому моменту либо успешно выполнился с другим или отсутствующим значением, либо уже упал с ошибкой.
4. Healthcheck, безусловно возвращающий `{"status": "ok"}`, отвечает только на один вопрос: жив ли процесс, способный принять HTTP-запрос. Он ответит `200` даже если файл базы данных удалён, повреждён или недоступен по правам доступа. Healthcheck с `db.ping()` отвечает на более полезный вопрос: может ли сервис реально выполнить свою работу прямо сейчас. Разница видна ровно в сценарии, когда процесс жив (uvicorn отвечает на запросы), но зависимость, без которой сервис бесполезен, отказала. Первый вариант скажет оркестратору "всё в порядке". Второй честно провалится и даст системе шанс перезапустить контейнер или не пускать на него трафик.
5. Потому что путь по умолчанию (`taskman.db`, относительный, в рабочей директории `/app` контейнера) физически лежит в обычном, недолговечном слое файловой системы контейнера. Это тот самый слой, что уничтожается при `docker compose down` или пересоздании контейнера. Volume, смонтированный в `/data`, переживает пересоздание контейнера, но только если файл базы данных реально находится **внутри** этого смонтированного пути. Явное указание `TASKMAN_DATABASE_PATH=/data/taskman.db` гарантирует, что приложение пишет файл именно туда. Иначе оно пишет рядом, в путь по умолчанию, который никак не связан с volume.

</details>

## Частая ошибка

Самая распространённая ошибка при первой докеризации stateful-сервиса связана с путями. Volume в `docker-compose.yml` подключён, но путь к файлу базы внутри приложения не поменяли. Он так и смотрит на путь по умолчанию где-то ещё в файловой системе контейнера.

Внешне всё выглядит правильно: volume объявлен, смонтирован, `docker compose up` не выдаёт ни единой ошибки. А данные всё равно теряются при каждом пересоздании контейнера, потому что приложение никогда и не писало в смонтированный путь.

Эта ошибка коварна именно тем, что не проявляется сразу. Пока контейнер просто перезапускается (`docker compose restart`) без полного удаления, файл в обычном слое контейнера остаётся на месте, и всё работает.

Потеря данных обнаруживается только тогда, когда контейнер реально пересоздаётся с нуля: пересборка образа, `docker compose down && up`, деплой новой версии. То есть именно в тот момент, когда персистентность нужна больше всего.

Вторая типичная ошибка — читать переменные окружения не в одном месте. Вместо того чтобы создать `Settings()` один раз при старте, `os.getenv(...)` рассыпают по разным местам кода, там, где значение фактически понадобилось.

Это лишает единственного места, где можно **сразу**, при запуске приложения, обнаружить отсутствующую или некорректную конфигурацию. Вместо честного падения на старте с понятным сообщением "не хватает `TASKMAN_SECRET_KEY`" приложение запускается штатно.

Ошибка всплывает только тогда, когда конкретный участок кода реально исполнится. Это может быть `None` там, где ожидалась строка, или пропущенная переменная. Иногда — через несколько дней после деплоя, на редко используемом пути запроса.
