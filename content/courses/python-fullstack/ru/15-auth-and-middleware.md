# Аутентификация: JWT, OAuth2PasswordBearer, dependency overrides

## Теория

**JWT — стейтлес-аутентификация.** JSON Web Token — это `header.payload.signature`, три части в base64url, где `payload` содержит утверждения ("claims") вроде `sub` (кому принадлежит токен — обычно username/id) и `exp` (когда токен истекает), а `signature` — криптографическая подпись первых двух частей секретным ключом сервера. Сервер не хранит сессии — вся нужная информация уже внутри токена, а подпись гарантирует, что клиент не подделал `payload` (изменить `sub` на чужой username без знания секретного ключа невозможно — подпись перестанет совпадать). Это тот же самый JWT, что в Node-экосистеме (`jsonwebtoken`) — идея идентична, `PyJWT` в Python лишь предоставляет тот же API на другом языке:

```python
import jwt
from datetime import datetime, timedelta, timezone

payload = {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
token = jwt.encode(payload, "secret-key", algorithm="HS256")

decoded = jwt.decode(token, "secret-key", algorithms=["HS256"])
# decoded["sub"] == "alice"

jwt.decode(token, "WRONG-key", algorithms=["HS256"])  # jwt.InvalidSignatureError
```

**`OAuth2PasswordBearer` — не полноценный OAuth2, а конкретный, узкий контракт.** Название вводит в заблуждение: класс не реализует redirect-based OAuth2-флоу вроде "Sign in with Google" — он моделирует конкретно **password grant** (логин по username+password напрямую на ваш сервер, без стороннего провайдера) и решает две узкие задачи: (1) как dependency извлекает значение из заголовка `Authorization: Bearer <token>`, (2) какие метаданные попадают в OpenAPI-схему, чтобы Swagger UI показал кнопку "Authorize" с формой логина:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    ...  # token — уже извлечённая строка из заголовка Authorization
```

`tokenUrl="auth/token"` — это не магия, а просто путь, который увидит Swagger UI, чтобы понять, куда постить логин/пароль для получения токена; сам эндпоинт `/auth/token` вы пишете руками, ничего готового `OAuth2PasswordBearer` не создаёт.

**Хеширование паролей — реальная, современная деталь: почему не passlib.** Классические туториалы по FastAPI-аутентификации почти всегда советуют `passlib[bcrypt]`. На практике в 2025–2026 `passlib` фактически не поддерживается, и его связка с современными версиями `bcrypt` (4.x+) ломается на ровном месте (`passlib` пытается прочитать внутренний атрибут версии, которого в новом `bcrypt` уже нет). Рабочее, современное решение — использовать пакет `bcrypt` напрямую, без прослойки `passlib`, благо API у него простой:

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

**404, а не 403 — сознательное решение безопасности.** Когда чужой пользователь пытается пометить выполненной чужую задачу, ответ должен быть `404 Not Found`, а не `403 Forbidden`. `403` фактически подтверждает: "задача с таким id существует, но не твоя" — утечка информации о существовании чужих данных. `404` не различает "такой задачи нет вообще" и "есть, но не твоя" — с точки зрения стороннего пользователя это должно выглядеть одинаково. У нас это получается бесплатно: запрос к БД сразу фильтрует по `WHERE id = ? AND user_id = ?`, так что чужая задача просто не находится, и `TaskNotFoundError` — та же самая ошибка, что и для реально несуществующего id.

**Dependency overrides для тестов.** FastAPI даёт словарь `app.dependency_overrides`, где ключ — исходная функция-зависимость, значение — замена, использующаяся вместо неё для всех тестовых запросов:

```python
from taskman.auth import get_current_user
from taskman.models import User

def fake_user() -> User:
    return User(id=1, username="test-user")

app.dependency_overrides[get_current_user] = fake_user
```

Это избавляет тесты от необходимости проходить настоящий флоу логина (регистрация + POST на `/auth/token` + парсинг токена) ради проверки чего-то, что вообще не про аутентификацию — например, что `GET /tasks` фильтрует по статусу. `TestClient` (обёртка над `httpx`, синхронная сама по себе — ни `pytest-asyncio`, ни ручной `asyncio.run()` для тестов через неё не нужны) подхватывает override автоматически.

### Параллели с JS/TS/Node:

- JWT — та же концепция и тот же формат, что `jsonwebtoken` в Node; `PyJWT` — просто другой API для того же стандарта.
- `OAuth2PasswordBearer` — не полноценный OAuth2-провайдер (не "Sign in with Google"), а конкретно password-grant-контракт + метаданные для Swagger UI; ближайший аналог по духу — обычный логин-эндпоинт с JWT, который вы бы и так написали руками в Express/Nest.js, только тут есть встроенная интеграция с автогенерируемой документацией.
- `app.dependency_overrides` ~ то, что в Nest.js делают через переопределение провайдеров в тестовом модуле (`overrideProvider`) — идея "подменить одну зависимость на фейковую для теста" универсальна.

## Что добавляем в проект

Задачи теперь принадлежат конкретному пользователю: таблица `tasks` получает колонку `user_id`, а `TaskStorage` — параметр `user_id` в каждом методе, который читает или пишет задачи. Появляется новый пакет `auth/` (хеширование паролей, JWT) и роуты `/auth/register`/`/auth/token`; все три существующих task-эндпоинта требуют `Depends(get_current_user)`. CLI, у которого никогда не было и не будет концепции логина, остаётся однопользовательским инструментом: при старте он создаёт (или переиспользует) один фиксированный локальный аккаунт и работает от его имени — вводить полноценный логин в CLI было бы избыточно для инструмента, который и так работает на одной машине от одного человека.

## Практическое задание

1. Добавьте `pyjwt`, `bcrypt`, `python-multipart` в `dependencies`.
2. Создайте `models/user.py` с `@dataclass class User: id: int; username: str`. Добавьте `user_id: int` в `Task` (без default — сразу после `id`, до полей с дефолтами).
3. Создайте `storage/users_storage.py`: `init_users_table()`, `create_user(username, hashed_password) -> User`, `get_user_by_username(username) -> tuple[User, str] | None` (второй элемент — хеш пароля, для последующей проверки).
4. Обновите `storage/sqlite_storage.py`: схема `tasks` получает `user_id INTEGER NOT NULL`; `add_task`/`find_task`/`get_task`/`mark_done`/`list_tasks` принимают `user_id` первым параметром и фильтруют по нему в SQL (`WHERE ... AND user_id = ?`).
5. Обновите `storage/protocol.py` — добавьте `user_id: int` в сигнатуры соответствующих методов `TaskStorage`.
6. Создайте `auth/security.py` (`hash_password`, `verify_password` через `bcrypt` напрямую — без `passlib`; `create_access_token`, `decode_access_token` через `PyJWT`) и `auth/dependencies.py` (`OAuth2PasswordBearer(tokenUrl="auth/token")`, `get_current_user`).
7. Создайте `api/routes_auth.py`: `POST /auth/register` (тело — JSON `UserCreate`) и `POST /auth/token` (тело — `OAuth2PasswordRequestForm`, form-encoded, не JSON — это требование самого `OAuth2PasswordBearer`/Swagger).
8. Обновите `api/routes.py`: каждый task-эндпоинт получает `current_user: User = Depends(get_current_user)` и передаёт `current_user.id` в вызовы storage-слоя.
9. Обновите `cli/app.py`: реализуйте `ensure_cli_user()`, создающую (при первом запуске) или находящую фиксированного локального пользователя `"cli"`, и прокиньте его `id` в `args.user_id` перед диспетчеризацией команды.
10. Напишите `tests/test_api.py` с `TestClient` и `app.dependency_overrides[get_current_user] = fake_user`, проверяющий: создание/список задач без реального логина; `404` (не `403`) при попытке пометить выполненной чужую/несуществующую задачу; `401` для защищённого роута без переопределения зависимости вообще.

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
from ..storage import users as users_storage
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
from ..storage import users as users_storage
from .schemas import TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: UserCreate) -> UserRead:
    existing = await users_storage.get_user_by_username(payload.username)
    if existing is not None:
        raise HTTPException(status_code=400, detail="Username already registered")
    user = await users_storage.create_user(payload.username, hash_password(payload.password))
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
from ..storage import db, users as users_storage
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
from ..storage import db, users as users_storage
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
    return await users_storage.create_user(CLI_USERNAME, hash_password(secrets.token_hex(16)))


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

`src/taskman/cli/commands.py` — единственное изменение: каждый обработчик теперь передаёт `args.user_id` первым аргументом в вызовы `db.add_task`/`db.list_tasks`/`db.mark_done` (остальное без изменений с главы 12).

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

Реальный прогон подтверждает изоляцию между пользователями: Алиса и Боб регистрируются, логинятся, каждый создаёт задачу — `GET /tasks` каждому показывает только его собственную; попытка Боба пометить выполненной задачу Алисы даёт `{"detail":"Task with id 1 not found"}` со статусом `404`, а не намёк на то, что задача существует, но принадлежит другому.

Ключевые решения:

- Хеширование пароля — через `bcrypt` напрямую, не через `passlib[bcrypt]`: связка `passlib` + современный `bcrypt` (4.x+) в реальности ломается на попытке прочитать внутренний атрибут версии, которого в новых релизах `bcrypt` больше нет. `bcrypt` сам по себе даёт всё нужное (`hashpw`/`checkpw`) без этой прослойки.
- `find_task`/`get_task`/`mark_done` фильтруют по `user_id` прямо в SQL (`WHERE ... AND user_id = ?`), а не проверяют владельца в Python после отдельного запроса без фильтра — чужая задача просто не находится на уровне базы, и `TaskNotFoundError` для "не найдено" и "найдено, но чужое" оказывается одной и той же веткой кода, без риска случайно забыть проверку владения где-то ещё.
- CLI не получает логин — `ensure_cli_user()` создаёт (или переиспользует) один фиксированный аккаунт `"cli"` с одноразовым, никогда не используемым для входа паролем; это осознанное решение не тащить полноценную аутентификацию в инструмент, у которого и так один пользователь на одной машине.
- `TestClient` — синхронная обёртка; тесты в `test_api.py` не нуждаются ни в `pytest-asyncio`, ни в ручном `asyncio.run()` для самих HTTP-вызовов (хотя `db`-fixture по-прежнему использует `asyncio.run()` для настройки in-memory соединения, как в главе 09/12).

## Проверь себя

1. Почему подделать JWT, изменив `sub` в payload на чужой username, невозможно без знания секретного ключа сервера, хотя сам payload — это просто открытый (незашифрованный) base64?
2. `OAuth2PasswordBearer` называется "OAuth2", но не реализует ничего похожего на "Sign in with Google". Что именно он реально делает, и почему его название вводит в заблуждение?
3. Почему при попытке одного пользователя пометить выполненной чужую задачу правильный HTTP-статус — `404`, а не `403`? Что конкретно "утекает", если ответить `403`?
4. Как `app.dependency_overrides[get_current_user] = fake_user` избавляет тест от необходимости проходить реальный флоу регистрации и логина, и что произойдёт с этим override, если не вызвать `app.dependency_overrides.clear()` после теста?
5. Почему CLI не завели собственный логин, а вместо этого создали один фиксированный локальный аккаунт при первом запуске?

<details>
<summary>Ответы</summary>

1. Подпись (`signature`) JWT — это не шифрование, а криптографическая функция от `header + payload + секретный ключ`, известный только серверу. Изменить `payload` (например, вписать чужой `sub`) может кто угодно — это просто текст в base64 — но пересчитать **правильную** подпись для изменённого payload без знания секретного ключа невозможно. Сервер при декодировании токена заново вычисляет подпись от полученных `header + payload` со своим секретным ключом и сравнивает с той, что пришла в токене — если они не совпадают (как будет всегда при подделанном payload без секрета), `jwt.decode` бросает `InvalidSignatureError`.
2. На практике `OAuth2PasswordBearer` решает две узкие задачи: извлекает значение из заголовка `Authorization: Bearer <token>` как строку, которую можно передать дальше по цепочке `Depends`, и добавляет в OpenAPI-схему метаданные о том, что API использует OAuth2 password-flow с определённым `tokenUrl` — именно эти метаданные заставляют Swagger UI показать кнопку "Authorize" с формой логина. Название вводит в заблуждение, потому что "OAuth2" в массовом сознании ассоциируется с редиректом на сторонний провайдер (Google, GitHub) — а password grant, который моделирует этот класс, это прямой логин по username/паролю на ваш собственный сервер, без какого-либо стороннего участника вообще.
3. `403 Forbidden` — это ответ "я понял, чего ты хочешь, ресурс существует, но тебе туда нельзя" — то есть сам факт ответа `403` подтверждает существование задачи с данным id, даже если запрашивающий не имеет к ней отношения. Это утечка информации: сторонний пользователь, перебирая id, может по разнице `403` vs `404` узнать, какие id вообще существуют в системе, даже не имея доступа к самим данным. `404 Not Found` не различает "такого id нет вообще" и "есть, но принадлежит другому" — с точки зрения любого, кто не является владельцем, оба случая должны выглядеть абсолютно одинаково.
4. `app.dependency_overrides` — это словарь, который FastAPI проверяет **до** вызова настоящей функции-зависимости: если исходная зависимость (`get_current_user`) есть среди ключей словаря, вызывается функция-замена (`fake_user`) вместо неё, и реальная проверка JWT/токена вообще не происходит — тест получает готового, заранее известного пользователя без единого реального HTTP-запроса на `/auth/token`. Если не вызвать `app.dependency_overrides.clear()` после теста, override останется активным для **всех последующих** тестов, использующих тот же `app` — включая те, что специально проверяют, что защищённый роут без токена отвечает `401`: такой тест начнёт неожиданно проходить мимо реальной проверки авторизации, что превращает тест в ложно-зелёный и маскирует реальную проблему, если сама аутентификация вдруг сломается.
5. Потому что CLI по своей природе уже однопользовательский инструмент — он работает на одной машине от имени одного человека, и там просто нет сценария "разные пользователи запускают один и тот же процесс и должны быть изолированы друг от друга" (в отличие от HTTP API, к которому подключаются разные клиенты одновременно). Введение полноценного логина в CLI (хранение токена, его обновление, интерактивный ввод пароля) добавило бы реальную сложность ради сценария, которого у этого конкретного инструмента никогда не возникает — фиксированный локальный аккаунт даётту же самую пользу (задачи привязаны к конкретному `user_id`, как того требует storage-слой) без этой цены.

</details>

## Частая ошибка

Самая опасная и при этом самая "тихая" ошибка в этой главе — оставить `SECRET_KEY` захардкоженным прямо в исходном коде (как в примерах выше, с явной пометкой "change me in production") и забыть заменить его на что-то, что реально не попадает в систему контроля версий. Секретный ключ JWT — это единственное, что не даёт кому угодно подписать себе токен с любым `sub` по желанию; если он утёк (или просто виден в открытом репозитории), вся схема аутентификации перестаёт что-либо доказывать — злоумышленник может выпустить токен от имени любого пользователя без единого реального пароля. В реальном проекте секрет должен приходить из переменной окружения (или секрет-хранилища), генерироваться достаточно длинным (PyJWT уже предупреждает при слишком коротком ключе — `InsecureKeyLengthWarning`) и никогда не попадать в git вместе с остальным кодом — то, что для учебного проекта в этой главе допустимо ради простоты, в реальном сервисе — прямая уязвимость.

Вторая типичная ошибка — увидеть, что данные теперь фильтруются по `user_id` в storage-слое, и решить, что достаточно один раз проверить владение в одном месте (например, в `get_task_or_404`), а остальные вызовы к базе можно оставить "как есть", без фильтрации по пользователю, потому что "мы же уже проверили выше". Каждая storage-функция, которая читает или пишет конкретную задачу, должна сама фильтровать по `user_id` — не потому, что вызывающий код обязательно ошибётся, а потому что контракт функции должен быть безопасным сам по себе, независимо от того, что происходит выше по стеку вызовов. Если позже появится ещё один эндпоинт или фоновая задача, которая вызовет `mark_done` напрямую, без прохождения через `get_task_or_404`, — фильтрация по `user_id` внутри самой функции `mark_done` останется единственной защитой от того, что один пользователь случайно (или намеренно) изменит чужие данные.
