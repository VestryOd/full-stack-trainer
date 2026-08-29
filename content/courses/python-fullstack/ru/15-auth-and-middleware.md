# Аутентификация: JWT, OAuth2PasswordBearer, dependency overrides

## Теория

**JWT — аутентификация без состояния (stateless).** JSON Web Token — это `header.payload.signature`, три части в base64url. В `payload` лежат утверждения ("claims") вроде `sub` (кому принадлежит токен — обычно имя пользователя или id) и `exp` (когда токен истекает). А `signature` — криптографическая подпись первых двух частей секретным ключом сервера.

Сервер не хранит сессии: вся нужная информация уже внутри токена. Подпись гарантирует, что клиент не подделал `payload`. Изменить `sub` на чужое имя пользователя без знания секретного ключа невозможно — подпись перестанет совпадать.

Это тот же самый JWT, что в Node-экосистеме (`jsonwebtoken`). Идея идентична, а `PyJWT` в Python лишь предоставляет тот же API на другом языке:

```python
import jwt
from datetime import datetime, timedelta, timezone

payload = {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
token = jwt.encode(payload, "secret-key", algorithm="HS256")

decoded = jwt.decode(token, "secret-key", algorithms=["HS256"])
# decoded["sub"] == "alice"

jwt.decode(token, "WRONG-key", algorithms=["HS256"])  # jwt.InvalidSignatureError
```

**`OAuth2PasswordBearer` — не полноценный OAuth2, а узкий, конкретный контракт.** Название вводит в заблуждение. Класс не реализует сценарий OAuth2 с редиректом вроде "Sign in with Google". Он моделирует конкретно **password grant** — вход по имени пользователя и паролю напрямую на ваш сервер, без стороннего провайдера.

Он решает ровно две узкие задачи. Первая — как зависимость извлекает значение из заголовка `Authorization: Bearer <token>`. Вторая — какие метаданные попадают в OpenAPI-схему. Именно эти метаданные заставляют Swagger UI (пользовательский интерфейс для схемы в браузере) показать кнопку "Authorize" с формой логина:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    ...  # token — уже извлечённая строка из заголовка Authorization
```

`tokenUrl="auth/token"` — это не магия, а просто путь, который увидит Swagger UI. По нему интерфейс понимает, куда отправлять логин и пароль, чтобы получить токен. Сам эндпоинт `/auth/token` вы пишете руками: ничего готового `OAuth2PasswordBearer` не создаёт.

**Хеширование паролей — реальная, современная деталь: почему не passlib.** Классические туториалы по FastAPI-аутентификации почти всегда советуют `passlib[bcrypt]`. На практике в 2025–2026 `passlib` фактически не поддерживается. Его связка с современными версиями `bcrypt` (4.x+) ломается на обычной установке. Причина: `passlib` пытается прочитать внутренний атрибут версии, которого в новом `bcrypt` уже нет.

Рабочее, современное решение — использовать пакет `bcrypt` напрямую, без прослойки `passlib`. API у него достаточно простой сам по себе:

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

**404, а не 403 — сознательное решение безопасности.** Когда один пользователь пытается пометить выполненной чужую задачу, правильный HTTP-статус — `404 Not Found`, а не `403 Forbidden`. Ответ `403` фактически подтверждает, что задача с таким id существует и просто принадлежит другому. Это утечка информации о существовании чужих данных.

Ответ `404` не различает "такого id нет вообще" и "есть, но принадлежит другому". С точки зрения постороннего пользователя оба случая должны выглядеть одинаково. У нас это получается бесплатно. Запрос к базе данных сразу фильтрует по `WHERE id = ? AND user_id = ?`, так что чужая задача просто не находится. Тогда `TaskNotFoundError` — та же самая ошибка, что и для реально несуществующего id.

**Dependency overrides для тестов.** FastAPI даёт словарь `app.dependency_overrides`, где ключ — исходная функция-зависимость, значение — замена, использующаяся вместо неё для всех тестовых запросов:

```python
from taskman.auth import get_current_user
from taskman.models import User

def fake_user() -> User:
    return User(id=1, username="test-user")

app.dependency_overrides[get_current_user] = fake_user
```

Это избавляет тесты от необходимости проходить настоящий сценарий входа: регистрация, POST на `/auth/token`, разбор токена. И всё это ради проверки чего-то, что вообще не про аутентификацию — например, что `GET /tasks` правильно фильтрует по статусу. `TestClient` подхватывает подмену автоматически. Это обёртка над `httpx`, синхронная сама по себе, поэтому тестам через неё не нужны ни `pytest-asyncio`, ни ручной `asyncio.run()`.

### Параллели с JS/TS/Node:

- JWT — та же концепция и тот же формат, что `jsonwebtoken` в Node; `PyJWT` — просто другой API для того же стандарта.
- `OAuth2PasswordBearer` — не полноценный OAuth2-провайдер и не "Sign in with Google". Это password-grant-контракт плюс метаданные для Swagger UI. Ближайший аналог по духу — обычный логин-эндпоинт с JWT, который вы бы и так написали руками в Express или Nest.js. Разница в том, что здесь есть встроенная интеграция с автогенерируемой документацией.
- `app.dependency_overrides` — аналог переопределения провайдеров в тестовом модуле Nest.js (`overrideProvider`). Идея "подменить одну зависимость на фейковую ради теста" универсальна.

## Что добавляем в проект

Задачи теперь принадлежат конкретному пользователю. Таблица `tasks` получает колонку `user_id`, а `TaskStorage` — параметр `user_id` в каждом методе, который читает или пишет задачи. Появляется новый пакет `auth/` (хеширование паролей, JWT) и роуты `/auth/register` и `/auth/token`. Все три существующих task-эндпоинта требуют `Depends(get_current_user)`.

CLI (интерфейс командной строки) никогда не знал концепции логина и не узнает, поэтому остаётся однопользовательским инструментом. При старте он создаёт (или переиспользует) один фиксированный локальный аккаунт и работает от его имени. Полноценный вход внутри CLI был бы избыточен для инструмента, который и так работает на одной машине от одного человека.

## Практическое задание

1. Добавьте `pyjwt`, `bcrypt`, `python-multipart` в `dependencies`.
2. Создайте `models/user.py` с `@dataclass class User: id: int; username: str`. Добавьте `user_id: int` в `Task` (без default — сразу после `id`, до полей с дефолтами).
3. Создайте `storage/users_storage.py` с тремя функциями: `init_users_table()`, `create_user(username, hashed_password) -> User` и `get_user_by_username(username) -> tuple[User, str] | None`. В последней второй элемент кортежа — хеш пароля, для последующей проверки.
4. Обновите `storage/sqlite_storage.py`. Схема `tasks` получает `user_id INTEGER NOT NULL`. Функции `add_task`, `find_task`, `get_task`, `mark_done` и `list_tasks` принимают `user_id` первым параметром. Они фильтруют по нему в SQL — языке структурированных запросов, на котором говорит база данных, — через `WHERE ... AND user_id = ?`.
5. Обновите `storage/protocol.py` — добавьте `user_id: int` в сигнатуры соответствующих методов `TaskStorage`.
6. Создайте `auth/security.py` (`hash_password`, `verify_password` через `bcrypt` напрямую — без `passlib`; `create_access_token`, `decode_access_token` через `PyJWT`) и `auth/dependencies.py` (`OAuth2PasswordBearer(tokenUrl="auth/token")`, `get_current_user`).
7. Создайте `api/routes_auth.py`: `POST /auth/register` (тело — JSON `UserCreate`) и `POST /auth/token` (тело — `OAuth2PasswordRequestForm`, form-encoded, не JSON — это требование самого `OAuth2PasswordBearer`/Swagger).
8. Обновите `api/routes.py`: каждый task-эндпоинт получает `current_user: User = Depends(get_current_user)` и передаёт `current_user.id` в вызовы storage-слоя.
9. Обновите `cli/app.py`: реализуйте `ensure_cli_user()`, которая при первом запуске создаёт, а дальше находит фиксированного локального пользователя `"cli"`. Прокиньте его `id` в `args.user_id` перед диспетчеризацией команды.
10. Напишите `tests/test_api.py` с `TestClient` и `app.dependency_overrides[get_current_user] = fake_user`. Проверьте, что создание задачи и вывод списка работают без реального входа. Проверьте, что попытка пометить выполненной чужую или несуществующую задачу даёт `404`, а не `403`. Проверьте, что защищённый роут вообще без переопределения зависимости отвечает `401`.

## Разбор решения

`src/taskman/models/user.py` (новый файл):

```python
from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str
```

`src/taskman/models/task.py` (обновлён — добавлено поле `user_id`):

```python
from dataclasses import dataclass
from enum import IntEnum


class Priority(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

    def __str__(self) -> str:
        return self.name.lower()


PRIORITY_CHOICES = [p.name.lower() for p in Priority]


@dataclass
class Task:
    id: int
    user_id: int
    text: str
    priority: Priority = Priority.MEDIUM
    done: bool = False

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Task text cannot be empty")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return (-self.priority, self.id) < (-other.priority, other.id)

    def __str__(self) -> str:
        mark = "x" if self.done else " "
        return f"[{mark}] {self.id} {self.text} ({self.priority})"
```

`src/taskman/storage/users_storage.py` (новый файл):

```python
from ..models import User
from .sqlite_storage import db_connection


async def init_users_table() -> None:
    async with db_connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL
            )
            """
        )


async def create_user(username: str, hashed_password: str) -> User:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
            (username, hashed_password),
        )
        user_id = cursor.lastrowid
        assert user_id is not None
        return User(id=user_id, username=username)


async def get_user_by_username(username: str) -> tuple[User, str] | None:
    """Return (User, hashed_password) for the given username, or None if not found."""
    async with db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return User(id=row["id"], username=row["username"]), row["hashed_password"]
```

`src/taskman/storage/sqlite_storage.py` (обновлён — задачи привязаны к `user_id`):

```python
import itertools
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator, TypeVar

import aiosqlite

from ..models import Priority, Task, TaskNotFoundError

DB_PATH = Path("taskman.db")

T = TypeVar("T")


@asynccontextmanager
async def db_connection() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def init_db() -> None:
    async with db_connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                priority INTEGER NOT NULL,
                done INTEGER NOT NULL
            )
            """
        )


def _row_to_task(row: aiosqlite.Row) -> Task:
    return Task(
        id=row["id"],
        user_id=row["user_id"],
        text=row["text"],
        priority=Priority(row["priority"]),
        done=bool(row["done"]),
    )


async def add_task(user_id: int, text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (user_id, text, priority, done) VALUES (?, ?, ?, ?)",
            (user_id, text, int(priority), 0),
        )
        task_id = cursor.lastrowid
        assert task_id is not None
        return Task(id=task_id, user_id=user_id, text=text, priority=priority, done=False)


async def find_task(user_id: int, task_id: int) -> Task | None:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_task(row)


async def get_task(user_id: int, task_id: int) -> Task:
    task = await find_task(user_id, task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


async def mark_done(user_id: int, task_id: int) -> Task:
    task = await get_task(user_id, task_id)
    async with db_connection() as conn:
        await conn.execute(
            "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?", (task_id, user_id)
        )
    task.done = True
    return task


async def list_tasks(user_id: int) -> list[Task]:
    tasks: list[Task] = []
    async with db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,))
        async for row in cursor:
            tasks.append(_row_to_task(row))
    return tasks


def filter_by_status(items: list[Task], status: str) -> list[Task]:
    if status == "all":
        return items
    want_done = status == "done"
    return [task for task in items if task.done == want_done]


def sort_tasks(items: list[Task], sort_by: str) -> list[Task]:
    if sort_by == "priority":
        return sorted(items)
    return sorted(items, key=lambda t: t.id)


def paginate(items: list[T], page_size: int) -> Iterator[list[T]]:
    page: list[T] = []
    for item in items:
        page.append(item)
        if len(page) == page_size:
            yield page
            page = []
    if page:
        yield page


def get_page(items: list[T], page: int, page_size: int) -> list[T]:
    pages = itertools.islice(paginate(items, page_size), page - 1, page)
    return next(pages, [])
```

`src/taskman/storage/protocol.py` (обновлён):

```python
from typing import Protocol

from ..models import Priority, Task


class TaskStorage(Protocol):
    async def init_db(self) -> None: ...
    async def add_task(self, user_id: int, text: str, priority: Priority = ...) -> Task: ...
    async def find_task(self, user_id: int, task_id: int) -> Task | None: ...
    async def get_task(self, user_id: int, task_id: int) -> Task: ...
    async def mark_done(self, user_id: int, task_id: int) -> Task: ...
    async def list_tasks(self, user_id: int) -> list[Task]: ...
    def filter_by_status(self, items: list[Task], status: str) -> list[Task]: ...
    def sort_tasks(self, items: list[Task], sort_by: str) -> list[Task]: ...
    def get_page(self, items: list[Task], page: int, page_size: int) -> list[Task]: ...
```

`src/taskman/auth/security.py` (новый файл):

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SECRET_KEY = "dev-secret-change-me-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Return the username stored in the 'sub' claim, or raise jwt.PyJWTError."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username: str = payload["sub"]
    return username
```

`src/taskman/auth/dependencies.py` (новый файл):

```python
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..models import User
from ..storage import users_storage
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        username = decode_access_token(token)
    except jwt.PyJWTError:
        raise credentials_error

    result = await users_storage.get_user_by_username(username)
    if result is None:
        raise credentials_error
    user, _ = result
    return user
```

`src/taskman/api/routes_auth.py` (новый файл):

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import create_access_token, hash_password, verify_password
from ..storage import users_storage
from .schemas import TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: UserCreate) -> UserRead:
    existing = await users_storage.get_user_by_username(payload.username)
    if existing is not None:
        raise HTTPException(status_code=400, detail="Username already registered")
    user = await users_storage.create_user(
        payload.username, hash_password(payload.password)
    )
    return UserRead(id=user.id, username=user.username)


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    result = await users_storage.get_user_by_username(form_data.username)
    if result is None:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    user, hashed_password = result
    if not verify_password(form_data.password, hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(user.username)
    return TokenResponse(access_token=token)
```

`src/taskman/api/routes.py` (обновлён):

```python
from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..models import Priority, Task, User
from ..storage import db
from .schemas import TaskCreate, TaskRead

router = APIRouter()


async def get_task_or_404(
    task_id: int, current_user: User = Depends(get_current_user)
) -> Task:
    return await db.get_task(current_user.id, task_id)


@router.post("/tasks", response_model=TaskRead, status_code=201)
async def create_task(
    payload: TaskCreate, current_user: User = Depends(get_current_user)
) -> TaskRead:
    priority = Priority[payload.priority.upper()]
    task = await db.add_task(current_user.id, payload.text, priority)
    return TaskRead.from_task(task)


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(
    current_user: User = Depends(get_current_user),
    status: str = "all",
    sort: str = "id",
    page: int = 1,
    page_size: int = 5,
) -> list[TaskRead]:
    all_tasks = await db.list_tasks(current_user.id)
    filtered = db.sort_tasks(db.filter_by_status(all_tasks, status), sort)
    page_tasks = db.get_page(filtered, page, page_size)
    return [TaskRead.from_task(task) for task in page_tasks]


@router.patch("/tasks/{task_id}/done", response_model=TaskRead)
async def mark_task_done(task: Task = Depends(get_task_or_404)) -> TaskRead:
    updated = await db.mark_done(task.user_id, task.id)
    return TaskRead.from_task(updated)
```

`src/taskman/api/schemas.py` (обновлён — добавлены `UserCreate`/`UserRead`/`TokenResponse`):

```python
from pydantic import BaseModel, field_validator

from ..models import PRIORITY_CHOICES, Task


class TaskCreate(BaseModel):
    text: str
    priority: str = "medium"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in PRIORITY_CHOICES:
            raise ValueError(f"priority must be one of {PRIORITY_CHOICES}")
        return value


class TaskRead(BaseModel):
    id: int
    text: str
    priority: str
    done: bool

    @classmethod
    def from_task(cls, task: Task) -> "TaskRead":
        return cls(id=task.id, text=task.text, priority=str(task.priority), done=task.done)


class UserCreate(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

`src/taskman/api/app.py` (обновлён):

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..models import TaskNotFoundError
from ..storage import db, users_storage
from .exceptions import task_not_found_handler
from .middleware import log_requests
from .routes import router
from .routes_auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.init_db()
    await users_storage.init_users_table()
    yield


app = FastAPI(title="taskman", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(router)
app.middleware("http")(log_requests)
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

`src/taskman/cli/app.py` (обновлён — фиксированный локальный пользователь):

```python
import asyncio
import secrets

from ..auth import hash_password
from ..models import User
from ..storage import db, users_storage
from .commands import COMMAND_HANDLERS
from .parser import build_parser

CLI_USERNAME = "cli"


async def ensure_cli_user() -> User:
    """The CLI is a single-user tool: all locally-created tasks belong to one
    fixed, local account. This account never logs in through the API, so its
    password is a random value that is generated and discarded immediately."""
    existing = await users_storage.get_user_by_username(CLI_USERNAME)
    if existing is not None:
        user, _ = existing
        return user
    return await users_storage.create_user(
        CLI_USERNAME, hash_password(secrets.token_hex(16))
    )


async def async_main() -> None:
    await db.init_db()
    await users_storage.init_users_table()
    cli_user = await ensure_cli_user()
    parser = build_parser()
    args = parser.parse_args()
    args.user_id = cli_user.id
    handler = COMMAND_HANDLERS[args.command]
    await handler(args)


def main() -> None:
    asyncio.run(async_main())
```

В `src/taskman/cli/commands.py` изменение одно. Каждый обработчик теперь передаёт `args.user_id` первым аргументом в вызовы `db.add_task`, `db.list_tasks` и `db.mark_done`. Остальное не менялось с главы 12.

`tests/test_api.py` (новый файл):

```python
from fastapi.testclient import TestClient

from taskman.api.app import app
from taskman.auth import get_current_user
from taskman.models import User


def fake_user() -> User:
    return User(id=1, username="test-user")


def test_create_and_list_task_with_overridden_auth(db):
    app.dependency_overrides[get_current_user] = fake_user
    try:
        with TestClient(app) as client:
            response = client.post("/tasks", json={"text": "Buy milk", "priority": "high"})
            assert response.status_code == 201

            response = client.get("/tasks")
            assert response.status_code == 200
            assert len(response.json()) == 1
    finally:
        app.dependency_overrides.clear()


def test_mark_missing_task_done_returns_404(db):
    app.dependency_overrides[get_current_user] = fake_user
    try:
        with TestClient(app) as client:
            response = client.patch("/tasks/999/done")
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_protected_route_without_token_is_rejected(db):
    with TestClient(app) as client:
        response = client.get("/tasks")
        assert response.status_code == 401
```

Реальный прогон подтверждает изоляцию между пользователями. Алиса и Боб регистрируются, входят и каждый создаёт задачу. `GET /tasks` показывает каждому только его собственную. Попытка Боба пометить выполненной задачу Алисы даёт `{"detail":"Task with id 1 not found"}` со статусом `404`. Никакого намёка на то, что задача существует, но принадлежит другому, нет.

Ключевые решения:

- Хеширование пароля идёт через `bcrypt` напрямую, не через `passlib[bcrypt]`. Связка `passlib` с современным `bcrypt` (4.x+) в реальности ломается. Она пытается прочитать внутренний атрибут версии, которого в новых релизах `bcrypt` больше нет. Сам по себе `bcrypt` даёт всё нужное (`hashpw`/`checkpw`) без этой прослойки.
- Функции `find_task`, `get_task` и `mark_done` фильтруют по `user_id` прямо в SQL (`WHERE ... AND user_id = ?`), а не проверяют владельца в Python после отдельного запроса без фильтра. Чужая задача просто не находится на уровне базы. `TaskNotFoundError` для "не найдено" и для "найдено, но чужое" оказывается одной и той же веткой кода. Риска случайно забыть проверку владения где-то ещё не остаётся.
- CLI не получает логин. Функция `ensure_cli_user()` создаёт (или переиспользует) один фиксированный аккаунт `"cli"` с одноразовым паролем, который никогда не используется для входа. Это осознанное решение не тащить полноценную аутентификацию в инструмент, у которого и так один пользователь на одной машине.
- `TestClient` — синхронная обёртка. Тестам в `test_api.py` не нужны ни `pytest-asyncio`, ни ручной `asyncio.run()` для самих HTTP-вызовов. Фикстура `db` по-прежнему использует `asyncio.run()`, чтобы настроить соединение в памяти, как в главах 09 и 12.

## Проверь себя

1. Поле `payload` в JWT — это просто открытый, незашифрованный base64. Почему тогда подделать токен, изменив `sub` на чужое имя пользователя, всё равно невозможно без знания секретного ключа сервера?
2. `OAuth2PasswordBearer` называется "OAuth2", но не реализует ничего похожего на "Sign in with Google". Что именно он реально делает, и почему его название вводит в заблуждение?
3. Почему при попытке одного пользователя пометить выполненной чужую задачу правильный HTTP-статус — `404`, а не `403`? Что конкретно "утекает", если ответить `403`?
4. Как `app.dependency_overrides[get_current_user] = fake_user` избавляет тест от реальной регистрации и входа? И что произойдёт с этой подменой, если не вызвать `app.dependency_overrides.clear()` после теста?
5. Почему CLI не завели собственный логин, а вместо этого создали один фиксированный локальный аккаунт при первом запуске?

<details>
<summary>Ответы</summary>

1. Подпись (`signature`) в JWT — это не шифрование, а криптографическая функция от `header + payload + секретный ключ`, известный только серверу. Изменить `payload` (например, вписать чужой `sub`) может кто угодно — это просто текст в base64. Но пересчитать **правильную** подпись для изменённого payload без знания секретного ключа невозможно. При декодировании токена сервер заново вычисляет подпись от полученных `header + payload` со своим секретным ключом. Дальше он сравнивает её с той, что пришла в токене. Если они не совпадают, `jwt.decode` бросает `InvalidSignatureError` — а при подделанном payload без секрета они не совпадут никогда.
2. На практике `OAuth2PasswordBearer` решает две узкие задачи. Он извлекает значение из заголовка `Authorization: Bearer <token>` как строку, которую можно передать дальше по цепочке `Depends`. И он добавляет в OpenAPI-схему метаданные о том, что API использует password flow протокола OAuth2 с определённым `tokenUrl`. Именно эти метаданные заставляют Swagger UI показать кнопку "Authorize" с формой логина. Название вводит в заблуждение, потому что "OAuth2" в массовом сознании ассоциируется с редиректом на сторонний провайдер вроде Google или GitHub. А password grant, который моделирует этот класс, — это прямой вход по имени пользователя и паролю на ваш собственный сервер, без какого-либо стороннего участника вообще.
3. Ответ `403 Forbidden` означает "я понял, чего ты хочешь, ресурс существует, но тебе туда нельзя". Сам факт ответа `403` подтверждает существование задачи с данным id, даже если запрашивающий не имеет к ней отношения. Это утечка информации. Посторонний пользователь может перебирать id и смотреть на разницу между `403` и `404`. Так он узнает, какие id вообще существуют в системе, даже не имея доступа к самим данным. `404 Not Found` не различает "такого id нет вообще" и "есть, но принадлежит другому". С точки зрения любого, кто не является владельцем, оба случая должны выглядеть абсолютно одинаково.
4. Словарь `app.dependency_overrides` FastAPI проверяет **до** вызова настоящей функции-зависимости. Если исходная зависимость (`get_current_user`) есть среди ключей словаря, вместо неё вызывается функция-замена (`fake_user`). Реальная проверка JWT и токена вообще не происходит. Тест получает готового, заранее известного пользователя, без единого реального HTTP-запроса на `/auth/token`. Если не вызвать `app.dependency_overrides.clear()` после теста, подмена останется активной для **всех последующих** тестов, использующих тот же `app`. В том числе для тех, что специально проверяют, что защищённый роут без токена отвечает `401`. Такой тест начнёт проходить мимо реальной проверки авторизации: ложно-зелёный результат, который маскирует настоящую проблему, если сама аутентификация вдруг сломается.
5. Потому что CLI по своей природе уже однопользовательский инструмент. Он работает на одной машине от имени одного человека. Просто нет сценария, в котором разные пользователи запускают один и тот же процесс и должны быть изолированы друг от друга. С HTTP API всё иначе: к нему подключаются разные клиенты одновременно. Полноценный вход внутри CLI означал бы хранение токена, его обновление и интерактивный ввод пароля. Это реальная сложность ради сценария, которого у этого конкретного инструмента никогда не возникает. Фиксированный локальный аккаунт даёт ту же самую пользу — задачи привязаны к конкретному `user_id`, как того требует storage-слой — без этой цены.

</details>

## Частая ошибка

Самая опасная и при этом самая "тихая" ошибка в этой главе — оставить `SECRET_KEY` зашитым прямо в исходный код. Примеры выше делают именно так, с явной пометкой "change me in production" прямо в значении. Заменить его на что-то, что реально не попадает в систему контроля версий, легко забыть.

Секретный ключ JWT — это единственное, что не даёт кому угодно подписать себе токен с любым `sub` по желанию. Если он утёк или просто виден в открытом репозитории, вся схема аутентификации перестаёт что-либо доказывать. Злоумышленник может выпустить токен от имени любого пользователя, без единого реального пароля.

В реальном проекте секрет должен приходить из переменной окружения или из хранилища секретов. Он должен быть достаточно длинным — `PyJWT` уже предупреждает о слишком коротком ключе через `InsecureKeyLengthWarning`. И он никогда не должен попадать в git вместе с остальным кодом. То, что в этой главе допустимо ради простоты учебного проекта, в реальном сервисе — прямая уязвимость.

Вторая типичная ошибка — увидеть, что данные теперь фильтруются по `user_id` в storage-слое, и решить, что одной проверки владения достаточно. Скажем, проверка живёт в `get_task_or_404`, а остальные вызовы к базе остаются без фильтра по пользователю, потому что "мы же уже проверили выше".

Каждая storage-функция, которая читает или пишет конкретную задачу, должна сама фильтровать по `user_id`. Не потому, что вызывающий код обязательно ошибётся. А потому что контракт функции должен быть безопасным сам по себе, независимо от того, что происходит выше по стеку вызовов.

Если позже появится ещё один эндпоинт или фоновая задача, которая вызовет `mark_done` напрямую, минуя `get_task_or_404`, останется только фильтр внутри самой `mark_done`. Он и будет единственным, что стоит между одним пользователем и чужими данными — случайно или намеренно.
