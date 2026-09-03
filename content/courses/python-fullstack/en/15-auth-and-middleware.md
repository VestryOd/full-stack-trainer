# Authentication: JWT, OAuth2PasswordBearer, dependency overrides

## Theory

**JWT — stateless authentication.** A JSON Web Token is `header.payload.signature`: three base64url parts. The `payload` holds "claims" such as `sub` (who the token belongs to, usually a username or id) and `exp` (when it expires). The `signature` is a cryptographic signature of the first two parts, keyed by the server's secret.

The server keeps no session state, because everything it needs is already inside the token. The signature guarantees the client hasn't tampered with the `payload`. Changing `sub` to someone else's username without knowing the secret key is impossible: the signature stops matching.

This is the exact same JWT you'd find in the Node ecosystem (`jsonwebtoken`). The idea is identical, and `PyJWT` in Python is just the same API in a different language:

```python
import jwt
from datetime import datetime, timedelta, timezone

payload = {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
token = jwt.encode(payload, "secret-key", algorithm="HS256")

decoded = jwt.decode(token, "secret-key", algorithms=["HS256"])
# decoded["sub"] == "alice"

jwt.decode(token, "WRONG-key", algorithms=["HS256"])  # jwt.InvalidSignatureError
```

**`OAuth2PasswordBearer` — not full OAuth2, a narrow, specific contract.** The name is misleading. This class doesn't implement a redirect-based OAuth2 flow like "Sign in with Google". It models the **password grant**: logging in with a username and password directly against your own server, with no third-party provider.

It solves exactly two narrow problems. The first is how a dependency extracts the value from the `Authorization: Bearer <token>` header. The second is what metadata ends up in the OpenAPI schema. That metadata makes Swagger UI — the user interface for the schema in the browser — show an "Authorize" button with a login form:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    ...  # token -- already extracted as a string from the Authorization header
```

`tokenUrl="auth/token"` isn't magic. It is just the path Swagger UI displays, so that it knows where to POST a login and password to get a token. You write the `/auth/token` endpoint itself by hand, because `OAuth2PasswordBearer` creates nothing ready-made.

**Where authentication lives: a dependency, not a middleware.** Chapter 14 added a request-logging middleware, and a middleware sees every incoming request too. Authentication still belongs in a dependency. The reason is where each of the two sits in the stack.

Starlette assembles the application as nested layers, and your own middleware wraps the router. So a middleware runs **before** route matching. At that point there is no matched route, no path parameters and no resolved dependencies. A middleware would have to re-derive from the raw path which requests need a token, then pass the user onward through `request.state`.

The same stack, from the outside in:

```txt
┌──────────────────────────────────────────────────────────┐
│ your middleware (chapter 14): sees the final status      │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Starlette: turns HTTPException into a response       │ │
│ │ ┌──────────────────────────────────────────────────┐ │ │
│ │ │ router: matches the request to a route           │ │ │
│ │ │ ┌──────────────────────────────────────────────┐ │ │ │
│ │ │ │ Depends(get_current_user) -> User            │ │ │ │
│ │ │ │ route handler: current_user is already typed │ │ │ │
│ │ │ └──────────────────────────────────────────────┘ │ │ │
│ │ └──────────────────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

A dependency runs inside the matched route instead. It returns a typed `User` straight into the handler signature. And `OAuth2PasswordBearer` registers the scheme in the OpenAPI schema, which is what gives Swagger UI its "Authorize" button. A middleware contributes nothing to that schema.

Even "protect the whole application" is a dependency in FastAPI, not a middleware. You pass it once at the top, as `FastAPI(dependencies=[Depends(get_current_user)])`. For one group of routes it is `APIRouter(dependencies=[...])`. This project keeps `Depends(get_current_user)` on each task endpoint, because `/auth/register` and `/auth/token` have to stay open.

The middleware from chapter 14 stays exactly as it was, and authentication changes what it logs. A request with a missing or invalid token never reaches the route, because `get_current_user` raises `HTTPException`.

The Starlette layer that turns that into a response sits **inside** your middleware. So the log line shows an ordinary `401`, in the same form chapter 14 used. The status is already converted by the time the response passes back through your code.

**Password hashing — a real, current-day detail: why not passlib.** Classic FastAPI authentication tutorials almost always recommend `passlib[bcrypt]`. In practice, as of 2025–2026, `passlib` is effectively unmaintained. Its integration with modern `bcrypt` releases (4.x+) breaks on a default install. The cause: `passlib` tries to read an internal version attribute that newer `bcrypt` no longer has.

The working, current fix is to use the `bcrypt` package directly, without the `passlib` layer. Its API is simple enough on its own:

```python
import bcrypt

# the bare API -- still incomplete: see the 72-byte limit right below

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

One limit of that API is easy to miss, and it is a real authorization hole. The `bcrypt` algorithm reads at most **72 bytes** of a password. Everything past byte 72 is ignored. So two different long passwords that share their first 72 bytes end up interchangeable. Each of them passes verification against the other one's hash.

Note that 72 counts **bytes**, not characters. A password made of Cyrillic letters or emoji hits the limit far sooner than a Latin one. In `utf-8` one such character takes two to four bytes.

Library versions differ in how loudly they say this. Up to and including `bcrypt` 4.3.0 the password was truncated silently, matching the original OpenBSD implementation. Version 5.0.0, released in September 2025, raises `ValueError` instead. Silent truncation is the dangerous variant, so never rely on the installed version to catch this for you.

The fix documented by the library itself is to pre-hash the password before `bcrypt` sees it. Hash it with `sha256`, then base64-encode the digest. The base64 step matters, because it removes zero bytes. On a zero byte `bcrypt` would stop reading the password early. A `sha256` digest is 32 bytes and its base64 form is 44, so the result always fits:

```python
import base64
import hashlib

import bcrypt


def _prepare(password: str) -> bytes:
    """sha256 first, then base64: bcrypt reads 72 bytes and stops at a zero byte."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)   # 44 bytes -- always under the 72-byte limit


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_prepare(password), hashed_password.encode("utf-8"))
```

Pre-hashing has to be applied on both sides. Forget it in `verify_password` and no long password verifies any more.

**404, not 403 — a deliberate security decision.** When a different user tries to mark someone else's task done, the right HTTP status is `404 Not Found`, not `403 Forbidden`. A `403` effectively confirms that a task with that id exists and is simply not yours. That leaks information about the existence of someone else's data.

A `404` does not distinguish "no such task at all" from "exists, but not yours". From an unrelated user's point of view, both cases should look identical. We get this for free. The database query already filters by `WHERE id = ? AND user_id = ?`, so someone else's task simply isn't found. `TaskNotFoundError` is then the exact same error as for an id that genuinely doesn't exist.

**Dependency overrides for tests.** FastAPI provides `app.dependency_overrides`, a dict keyed by the original dependency function, whose value replaces it for every test request:

```python
from taskman.auth import get_current_user
from taskman.models import User

def fake_user() -> User:
    return User(id=1, username="test-user")

app.dependency_overrides[get_current_user] = fake_user
```

This spares tests from having to walk the real login flow: register, POST to `/auth/token`, parse the token. All that just to check something unrelated to authentication — say, that `GET /tasks` filters by status correctly. `TestClient` picks up the override automatically. It is a wrapper around `httpx` and is synchronous on its own, so tests going through it need no `pytest-asyncio` and no manual `asyncio.run()`.

### Parallels with JS/TS/Node:

- JWT is the same concept and the same format as Node's `jsonwebtoken`; `PyJWT` is just a different API for the same standard.
- `OAuth2PasswordBearer` isn't a full OAuth2 provider, and not "Sign in with Google". It is a password-grant contract plus metadata for Swagger UI. The closest counterpart in spirit is the plain login endpoint with JWT you'd write by hand in Express or Nest.js. The difference is the built-in integration into the auto-generated docs.
- `app.dependency_overrides` is the counterpart of overriding providers in a Nest.js test module (`overrideProvider`). The idea of "swap one dependency for a fake, just for the test" is universal.
- Express protects routes with a middleware, `app.use(requireAuth)` or a per-route handler, and hangs the user on `req.user`. FastAPI uses a dependency instead, and the user arrives as a typed argument. Nest.js is closer to FastAPI here, because it puts authentication in a guard rather than in middleware.

## What we're adding to the project

Tasks now belong to a specific user. The `tasks` table gets a `user_id` column, and `TaskStorage` gets a `user_id` parameter on every method that reads or writes tasks. A new `auth/` package appears (password hashing, JWT), along with `/auth/register` and `/auth/token` routes. All three existing task endpoints now require `Depends(get_current_user)`.

The CLI (command-line interface) never had a login concept and never will, so it stays a single-user tool. On startup it creates, or reuses, one fixed local account and operates on its behalf. Full login inside the CLI would be overkill for a tool that already runs on one machine for one person.

## Practical exercise

1. Add `pyjwt`, `bcrypt` and `python-multipart>=0.0.18` to `dependencies`. That lower bound is not cosmetic. Versions below 0.0.18 carry a denial-of-service advisory, `CVE-2024-53981`, in the multipart parsing that `/auth/token` relies on.
2. Create `models/user.py` with `@dataclass class User: id: int; username: str`. Add `user_id: int` to `Task` (no default — right after `id`, before the fields that have defaults).
3. Create `storage/users_storage.py` with three functions: `init_users_table()`, `create_user(username, hashed_password) -> User` and `get_user_by_username(username) -> tuple[User, str] | None`. In the last one, the second element of the tuple is the password hash, for later verification.
4. Update `storage/sqlite_storage.py`. The `tasks` schema gets `user_id INTEGER NOT NULL`. The functions `add_task`, `find_task`, `get_task`, `mark_done` and `list_tasks` take `user_id` as their first parameter. They filter by it in SQL — the structured query language the database speaks — with `WHERE ... AND user_id = ?`.
5. Update `storage/protocol.py` — add `user_id: int` to the relevant `TaskStorage` method signatures.
6. Create `auth/security.py` (`hash_password`, `verify_password` via `bcrypt` directly — no `passlib`; `create_access_token`, `decode_access_token` via `PyJWT`) and `auth/dependencies.py` (`OAuth2PasswordBearer(tokenUrl="auth/token")`, `get_current_user`). In both hashing functions, pre-hash the password with `sha256` plus base64, so the 72-byte `bcrypt` limit cannot truncate it. Add `auth/__init__.py` too, re-exporting the five public names of the package through `__all__`.
7. Create `api/routes_auth.py`: `POST /auth/register` (body — JSON `UserCreate`) and `POST /auth/token` (body — `OAuth2PasswordRequestForm`, form-encoded, not JSON — a requirement of `OAuth2PasswordBearer`/Swagger itself).
8. Update `api/routes.py`: every task endpoint gets `current_user: User = Depends(get_current_user)` and passes `current_user.id` into the storage-layer calls.
9. Update `cli/app.py`: implement `ensure_cli_user()`, which creates on first run, or finds, a fixed local user `"cli"`. Thread its `id` into `args.user_id` before dispatching the command.
10. Write `tests/test_api.py` with `TestClient` and `app.dependency_overrides[get_current_user] = fake_user`. Check that creating and listing tasks works with no real login. Check that marking someone else's or a nonexistent task done returns `404`, not `403`. Check that a protected route with no dependency override at all returns `401`.

## Worked solution

`src/taskman/models/user.py` (new file):

```python
from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str
```

`src/taskman/models/task.py` (updated — a `user_id` field added):

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

`src/taskman/storage/users_storage.py` (new file):

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

`src/taskman/storage/sqlite_storage.py` (updated — tasks scoped to `user_id`):

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

`src/taskman/storage/protocol.py` (updated):

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

`src/taskman/auth/security.py` (new file):

```python
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SECRET_KEY = "dev-secret-change-me-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def _prepare(password: str) -> bytes:
    """sha256 first, then base64: bcrypt reads 72 bytes and stops at a zero byte."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)   # 44 bytes -- always under the 72-byte limit


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prepare(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_prepare(password), hashed_password.encode("utf-8"))


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

`src/taskman/auth/dependencies.py` (new file):

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

`src/taskman/auth/__init__.py` (new file):

```python
from .dependencies import get_current_user
from .security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "hash_password",
    "verify_password",
]
```

`src/taskman/api/routes_auth.py` (new file):

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

`src/taskman/api/routes.py` (updated):

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

`src/taskman/api/schemas.py` (updated — `UserCreate`/`UserRead`/`TokenResponse` added):

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

`src/taskman/api/app.py` (updated):

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

`src/taskman/cli/app.py` (updated — a fixed local user):

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

`src/taskman/cli/commands.py` has one change. Every handler now passes `args.user_id` as the first argument to `db.add_task`, `db.list_tasks` and `db.mark_done`. Everything else is unchanged since chapter 12.

`tests/test_api.py` (new file):

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

A real run confirms user isolation. Alice and Bob register, log in, and each creates a task. `GET /tasks` shows each of them only their own. Bob trying to mark Alice's task done gets `{"detail":"Task with id 1 not found"}` with a `404` status. There is no hint that the task exists but belongs to someone else.

Key decisions:

- Password hashing goes through `bcrypt` directly, not `passlib[bcrypt]`. Pairing `passlib` with a modern `bcrypt` (4.x+) genuinely breaks. It tries to read an internal version attribute that no longer exists in newer `bcrypt` releases. On its own, `bcrypt` gives everything needed (`hashpw`/`checkpw`) without that layer.
- The password is pre-hashed with `sha256` and base64 before `bcrypt` sees it. Without that step `bcrypt` reads only the first 72 bytes of the password. Two different long passwords sharing those bytes would then accept each other's hash. Newer `bcrypt` raises `ValueError` here, older 4.x truncated silently, and the same code stays safe on both.
- `find_task`, `get_task` and `mark_done` filter by `user_id` right in the SQL (`WHERE ... AND user_id = ?`), rather than checking ownership in Python after an unfiltered query. Someone else's task simply isn't found at the database level. `TaskNotFoundError` for "not found" and for "found, but not yours" ends up being the exact same code path. There is no risk of forgetting an ownership check somewhere else.
- The CLI doesn't get a login. The function `ensure_cli_user()` creates, or reuses, one fixed account `"cli"` with a one-time password that is never used to log in. This is a deliberate decision not to drag full authentication into a tool that already has exactly one user on one machine.
- The `auth/` package gets an `__init__.py` that re-exports its five public names. That is why the rest of the project writes `from ..auth import get_current_user`, and never `from ..auth.dependencies import get_current_user`. Callers do not have to know which submodule holds a name, and `security.py` could be split later without touching them. The `__all__` list is also what makes the re-export explicit for `mypy --strict`, as chapter 05 described. The `oauth2_scheme` object stays out of `__all__` on purpose: nothing outside `auth/` needs it.
- `TestClient` is a synchronous wrapper. The tests in `test_api.py` need neither `pytest-asyncio` nor a manual `asyncio.run()` for the HTTP calls themselves. The `db` fixture still uses `asyncio.run()` to set up the in-memory connection, as in chapters 09/12.

## Check yourself

1. The payload of a JWT is just plain, unencrypted base64. Why is it still impossible to forge a token by changing `sub` to someone else's username, without knowing the server's secret key?
2. `OAuth2PasswordBearer` is named "OAuth2," but doesn't implement anything resembling "Sign in with Google." What does it actually do, and why is its name misleading?
3. Why is the correct HTTP status `404`, not `403`, when one user tries to mark someone else's task done? What exactly "leaks" if you answer `403`?
4. How does `app.dependency_overrides[get_current_user] = fake_user` spare a test from real registration and login? And what happens to that override if `app.dependency_overrides.clear()` isn't called afterward?
5. Why didn't the CLI get its own login, opting instead for one fixed local account created on first run?
6. A middleware also sees every incoming request, yet `get_current_user` is a dependency. What does a dependency have access to that a middleware does not?

<details>
<summary>Answers</summary>

1. A JWT's `signature` isn't encryption. It is a cryptographic function of `header + payload + a secret key` known only to the server. Anyone can change the `payload` — say, put in someone else's `sub` — because it is just base64-encoded text. But recomputing the **correct** signature for the modified payload without knowing the secret key is impossible. When decoding a token, the server recomputes the signature from the received `header + payload` using its own secret key. It compares that against the signature in the token. If they do not match, `jwt.decode` raises `InvalidSignatureError`, and for a tampered payload without the secret they never will.
2. In practice, `OAuth2PasswordBearer` solves two narrow problems. It extracts the value from the `Authorization: Bearer <token>` header as a string that can be passed further down the `Depends` chain. And it adds metadata to the OpenAPI schema stating that the API uses an OAuth2 password flow with a given `tokenUrl`. That metadata is exactly what makes Swagger UI show an "Authorize" button with a login form. The name is misleading because "OAuth2" in popular usage is associated with redirecting to a third-party provider such as Google or GitHub. The password grant this class models is a direct username and password login against your own server, with no third party involved.
3. `403 Forbidden` means "I understood what you want, the resource exists, but you're not allowed to access it". The mere fact of a `403` response confirms a task with that id exists, even if the requester has nothing to do with it. That is an information leak. An unrelated user can probe ids and watch for `403` versus `404`. That reveals which ids exist in the system at all, without ever accessing the actual data. `404 Not Found` does not distinguish "no such id exists" from "exists, but belongs to someone else". From the point of view of anyone who isn't the owner, both cases should look exactly the same.
4. `app.dependency_overrides` is a dict FastAPI checks **before** calling the real dependency function. If the original dependency (`get_current_user`) is among the dict's keys, the replacement function (`fake_user`) is called instead. The real JWT and token check never happens at all. The test gets a ready-made, known-in-advance user, with not a single real HTTP request to `/auth/token`. If `app.dependency_overrides.clear()` isn't called after the test, the override stays active for **every subsequent** test using the same `app`. That includes tests specifically checking that a protected route with no token responds `401`. Such a test would start passing right past the real authorization check: a false green that masks a real problem if authentication itself ever breaks.
5. Because the CLI is already, by its nature, a single-user tool. It runs on one machine on behalf of one person. There is simply no scenario where different users run the same process and need to be isolated from each other. An HTTP API is different: many clients connect to it at the same time. Full login inside the CLI would mean storing a token, refreshing it and prompting for a password interactively. That is real complexity for a scenario this specific tool never encounters. A fixed local account delivers the exact same benefit — tasks tied to a concrete `user_id`, as the storage layer now requires — without that cost.
6. A dependency runs inside the matched route, and a middleware runs outside it. Starlette wraps the router in your own middleware, so the middleware executes before route matching happens. It therefore has no matched route, no path parameters and no resolved dependencies to work with. A dependency has all three. It also returns a typed `User` into the handler signature. And it feeds the OpenAPI schema, which is what puts the "Authorize" button into Swagger UI. A middleware could still read the `Authorization` header and decode the token by hand. What it would have to reinvent is the mapping from a raw path to the answer: does this request need a token? A middleware would also need a way to hand the user object onward. That mapping is exactly what `Depends` already knows.

</details>

## Common mistake

The most dangerous, and quietest, mistake in this chapter is leaving `SECRET_KEY` hardcoded right in the source code. The examples above do exactly that, with an explicit "change me in production" in the value itself. It is easy to forget to replace it with something that genuinely never ends up in version control.

The JWT secret key is the one thing that stops anyone from signing themselves a token with any `sub` they want. If it leaks, or is simply visible in a public repository, the entire authentication scheme stops proving anything at all. An attacker can issue a token for any user, with not a single real password.

In a real project the secret should come from an environment variable, or from a secrets manager. It should be long enough — `PyJWT` already warns on a too-short key with `InsecureKeyLengthWarning`. And it should never be committed to git alongside the rest of the code. What is acceptable for a course project's simplicity in this chapter is a direct vulnerability in a real service.

The second common mistake is seeing that data is now filtered by `user_id` in the storage layer, and concluding that one ownership check is enough. Say the check lives in `get_task_or_404`, and the rest of the database calls stay unfiltered by user, because "we already checked further up".

Every storage function that reads or writes a specific task needs to filter by `user_id` itself. Not because the calling code is bound to make a mistake. A function's contract needs to be safe on its own terms, regardless of what happens further up the call stack.

If another endpoint or a background job later calls `mark_done` directly, bypassing `get_task_or_404` entirely, the filter inside `mark_done` is all that is left. It is the only thing between one user and someone else's data, accidental or deliberate.
