# Authentication: JWT, OAuth2PasswordBearer, dependency overrides

## Theory

**JWT — stateless authentication.** A JSON Web Token is `header.payload.signature`, three base64url parts, where the `payload` holds "claims" like `sub` (who the token belongs to — usually a username/id) and `exp` (when it expires), and `signature` is a cryptographic signature of the first two parts, keyed by the server's secret. The server keeps no session state — everything needed is already inside the token, and the signature guarantees the client hasn't tampered with the `payload` (changing `sub` to someone else's username without knowing the secret key is impossible — the signature stops matching). This is the exact same JWT you'd find in the Node ecosystem (`jsonwebtoken`) — the idea is identical; `PyJWT` in Python is just the same API in a different language:

```python
import jwt
from datetime import datetime, timedelta, timezone

payload = {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
token = jwt.encode(payload, "secret-key", algorithm="HS256")

decoded = jwt.decode(token, "secret-key", algorithms=["HS256"])
# decoded["sub"] == "alice"

jwt.decode(token, "WRONG-key", algorithms=["HS256"])  # jwt.InvalidSignatureError
```

**`OAuth2PasswordBearer` — not full OAuth2, a narrow, specific contract.** The name is misleading: this class doesn't implement a redirect-based OAuth2 flow like "Sign in with Google" — it specifically models the **password grant** (logging in with a username+password directly against your own server, no third-party provider), and solves two narrow problems: (1) how a dependency extracts the value from the `Authorization: Bearer <token>` header, (2) what metadata ends up in the OpenAPI schema so Swagger UI shows an "Authorize" button with a login form:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    ...  # token -- already extracted as a string from the Authorization header
```

`tokenUrl="auth/token"` isn't magic — it's just the path Swagger UI shows so it knows where to POST a login/password to get a token; you write the `/auth/token` endpoint itself by hand — `OAuth2PasswordBearer` doesn't create anything ready-made.

**Password hashing — a real, current-day detail: why not passlib.** Classic FastAPI authentication tutorials almost always recommend `passlib[bcrypt]`. In practice, as of 2025–2026, `passlib` is effectively unmaintained, and its integration with modern `bcrypt` releases (4.x+) breaks out of the box (`passlib` tries to read an internal version attribute that newer `bcrypt` no longer has). The working, current fix is to use the `bcrypt` package directly, without the `passlib` layer — its API is simple enough on its own:

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

**404, not 403 — a deliberate security decision.** When a different user tries to mark someone else's task done, the right HTTP status is `404 Not Found`, not `403 Forbidden`. `403` effectively confirms: "a task with that id exists, it's just not yours" — leaking information about the existence of someone else's data. `404` doesn't distinguish "no such task at all" from "exists, but not yours" — from an unrelated user's point of view, both cases should look identical. We get this for free: the database query already filters by `WHERE id = ? AND user_id = ?`, so someone else's task simply isn't found, and `TaskNotFoundError` is the exact same error as for an id that genuinely doesn't exist.

**Dependency overrides for tests.** FastAPI provides `app.dependency_overrides`, a dict keyed by the original dependency function, whose value replaces it for every test request:

```python
from taskman.auth import get_current_user
from taskman.models import User

def fake_user() -> User:
    return User(id=1, username="test-user")

app.dependency_overrides[get_current_user] = fake_user
```

This spares tests from having to walk the real login flow (register + POST to `/auth/token` + parse the token) just to check something entirely unrelated to authentication — say, that `GET /tasks` filters by status correctly. `TestClient` (a wrapper around `httpx`, synchronous on its own — no `pytest-asyncio`, no manual `asyncio.run()` needed for tests going through it) picks up the override automatically.

### Parallels with JS/TS/Node:

- JWT is the same concept and the same format as Node's `jsonwebtoken`; `PyJWT` is just a different API for the same standard.
- `OAuth2PasswordBearer` isn't a full OAuth2 provider (not "Sign in with Google") — it's specifically a password-grant contract plus metadata for Swagger UI; the closest counterpart in spirit is the plain login endpoint with JWT you'd write by hand in Express/Nest.js anyway, just with built-in integration into the auto-generated docs.
- `app.dependency_overrides` ~ what Nest.js does by overriding providers in a test module (`overrideProvider`) — the idea of "swap one dependency for a fake, just for the test" is universal.

## What we're adding to the project

Tasks now belong to a specific user: the `tasks` table gets a `user_id` column, and `TaskStorage` gets a `user_id` parameter on every method that reads or writes tasks. A new `auth/` package appears (password hashing, JWT), along with `/auth/register`/`/auth/token` routes; all three existing task endpoints now require `Depends(get_current_user)`. The CLI, which never had and never will have a login concept, stays a single-user tool: on startup it creates (or reuses) one fixed local account and operates on its behalf — introducing full login into the CLI would be overkill for a tool that already runs on one machine for one person.

## Practical exercise

1. Add `pyjwt`, `bcrypt`, `python-multipart` to `dependencies`.
2. Create `models/user.py` with `@dataclass class User: id: int; username: str`. Add `user_id: int` to `Task` (no default — right after `id`, before the fields that have defaults).
3. Create `storage/users_storage.py`: `init_users_table()`, `create_user(username, hashed_password) -> User`, `get_user_by_username(username) -> tuple[User, str] | None` (the second element is the password hash, for later verification).
4. Update `storage/sqlite_storage.py`: the `tasks` schema gets `user_id INTEGER NOT NULL`; `add_task`/`find_task`/`get_task`/`mark_done`/`list_tasks` take `user_id` as their first parameter and filter by it in SQL (`WHERE ... AND user_id = ?`).
5. Update `storage/protocol.py` — add `user_id: int` to the relevant `TaskStorage` method signatures.
6. Create `auth/security.py` (`hash_password`, `verify_password` via `bcrypt` directly — no `passlib`; `create_access_token`, `decode_access_token` via `PyJWT`) and `auth/dependencies.py` (`OAuth2PasswordBearer(tokenUrl="auth/token")`, `get_current_user`).
7. Create `api/routes_auth.py`: `POST /auth/register` (body — JSON `UserCreate`) and `POST /auth/token` (body — `OAuth2PasswordRequestForm`, form-encoded, not JSON — a requirement of `OAuth2PasswordBearer`/Swagger itself).
8. Update `api/routes.py`: every task endpoint gets `current_user: User = Depends(get_current_user)` and passes `current_user.id` into the storage-layer calls.
9. Update `cli/app.py`: implement `ensure_cli_user()`, which creates (on first run) or finds a fixed local user `"cli"`, and thread its `id` into `args.user_id` before dispatching the command.
10. Write `tests/test_api.py` with `TestClient` and `app.dependency_overrides[get_current_user] = fake_user`, checking: creating/listing tasks with no real login; `404` (not `403`) when trying to mark someone else's/a nonexistent task done; `401` on a protected route with no dependency override at all.

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

`src/taskman/auth/dependencies.py` (new file):

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

`src/taskman/api/routes_auth.py` (new file):

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

`src/taskman/cli/app.py` (updated — a fixed local user):

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

`src/taskman/cli/commands.py` — the only change: every handler now passes `args.user_id` as the first argument to `db.add_task`/`db.list_tasks`/`db.mark_done` (everything else unchanged since chapter 12).

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

A real run confirms user isolation: Alice and Bob register, log in, each creates a task — `GET /tasks` shows each of them only their own; Bob trying to mark Alice's task done returns `{"detail":"Task with id 1 not found"}` with a `404` status, with no hint that the task exists but belongs to someone else.

Key decisions:

- Password hashing goes through `bcrypt` directly, not `passlib[bcrypt]`: pairing `passlib` with a modern `bcrypt` (4.x+) genuinely breaks trying to read an internal version attribute that no longer exists in newer `bcrypt` releases. `bcrypt` on its own gives everything needed (`hashpw`/`checkpw`) without that layer.
- `find_task`/`get_task`/`mark_done` filter by `user_id` right in the SQL (`WHERE ... AND user_id = ?`), rather than checking ownership in Python after an unfiltered query — someone else's task simply isn't found at the database level, and `TaskNotFoundError` for "not found" and "found, but not yours" ends up being the exact same code path, with no risk of accidentally forgetting an ownership check somewhere else.
- The CLI doesn't get a login — `ensure_cli_user()` creates (or reuses) one fixed account `"cli"` with a one-time, never-logged-in-with password; a deliberate decision not to drag full authentication into a tool that already has exactly one user on one machine.
- `TestClient` is a synchronous wrapper — the tests in `test_api.py` need neither `pytest-asyncio` nor a manual `asyncio.run()` for the HTTP calls themselves (though the `db` fixture still uses `asyncio.run()` to set up the in-memory connection, as in chapters 09/12).

## Check yourself

1. Why is it impossible to forge a JWT by changing `sub` in the payload to someone else's username without knowing the server's secret key, given that the payload itself is just plain (unencrypted) base64?
2. `OAuth2PasswordBearer` is named "OAuth2," but doesn't implement anything resembling "Sign in with Google." What does it actually do, and why is its name misleading?
3. Why is the correct HTTP status `404`, not `403`, when one user tries to mark someone else's task done? What exactly "leaks" if you answer `403`?
4. How does `app.dependency_overrides[get_current_user] = fake_user` spare a test from having to walk through real registration and login, and what happens to that override if `app.dependency_overrides.clear()` isn't called afterward?
5. Why didn't the CLI get its own login, opting instead for one fixed local account created on first run?

<details>
<summary>Answers</summary>

1. A JWT's `signature` isn't encryption — it's a cryptographic function of `header + payload + a secret key` known only to the server. Anyone can change the `payload` (say, put in someone else's `sub`) — it's just base64-encoded text — but recomputing the **correct** signature for the modified payload without knowing the secret key is impossible. When decoding a token, the server recomputes the signature from the received `header + payload` using its own secret key and compares it against the one in the token — if they don't match (which they never will for a tampered payload without the secret), `jwt.decode` raises `InvalidSignatureError`.
2. In practice, `OAuth2PasswordBearer` solves two narrow problems: it extracts the value from the `Authorization: Bearer <token>` header as a string that can be passed further down the `Depends` chain, and it adds metadata to the OpenAPI schema stating that the API uses an OAuth2 password flow with a given `tokenUrl` — that metadata is exactly what makes Swagger UI show an "Authorize" button with a login form. The name is misleading because "OAuth2" in popular usage is associated with redirecting to a third-party provider (Google, GitHub) — while the password grant this class models is a direct username/password login against your own server, with no third party involved at all.
3. `403 Forbidden` means "I understood what you want, the resource exists, but you're not allowed to access it" — the mere fact of a `403` response confirms a task with that id exists, even if the requester has nothing to do with it. That's an information leak: an unrelated user, by probing ids and watching for `403` vs `404`, can learn which ids exist in the system at all, without ever accessing the actual data. `404 Not Found` doesn't distinguish "no such id exists" from "exists, but belongs to someone else" — from the point of view of anyone who isn't the owner, both cases should look exactly the same.
4. `app.dependency_overrides` is a dict FastAPI checks **before** calling the real dependency function: if the original dependency (`get_current_user`) is among the dict's keys, the replacement function (`fake_user`) is called instead, and the real JWT/token check never happens at all — the test gets a ready-made, known-in-advance user with not a single real HTTP request to `/auth/token`. If `app.dependency_overrides.clear()` isn't called after the test, the override stays active for **every subsequent** test using the same `app` — including tests specifically checking that a protected route with no token responds `401`: such a test would unexpectedly start passing right past the real authorization check, turning it into a false green and masking a real problem if authentication itself ever breaks.
5. Because the CLI is already, by its nature, a single-user tool — it runs on one machine on behalf of one person, and there's simply no scenario of "different users run the same process and need to be isolated from each other" (unlike an HTTP API, which different clients connect to simultaneously). Introducing full login into the CLI (storing a token, refreshing it, interactively prompting for a password) would add real complexity for a scenario this specific tool never actually encounters — a fixed local account delivers the exact same benefit (tasks tied to a concrete `user_id`, as the storage layer now requires) without that cost.

</details>

## Common mistake

The most dangerous, and quietest, mistake in this chapter is leaving `SECRET_KEY` hardcoded right in the source code (as in the examples above, explicitly flagged "change me in production") and forgetting to replace it with something that genuinely never ends up in version control. The JWT secret key is the one thing standing between "anyone" and "signing themselves a token with any `sub` they want" — if it leaks (or is simply visible in a public repository), the entire authentication scheme stops proving anything at all: an attacker can issue a token for any user, with not a single real password. In a real project, the secret should come from an environment variable (or a secrets manager), be generated long enough (PyJWT already warns on a too-short key — `InsecureKeyLengthWarning`), and never be committed to git alongside the rest of the code — what's acceptable for a course project's simplicity in this chapter is a direct vulnerability in a real service.

The second common mistake is seeing that data is now filtered by `user_id` in the storage layer and deciding that checking ownership once, in one place (say, `get_task_or_404`), is enough — leaving the rest of the database calls unfiltered by user, because "we already checked further up." Every storage function that reads or writes a specific task needs to filter by `user_id` itself — not because the calling code is bound to make a mistake, but because a function's contract needs to be safe on its own terms, regardless of what happens further up the call stack. If another endpoint or a background job later calls `mark_done` directly, bypassing `get_task_or_404` entirely, filtering by `user_id` inside `mark_done` itself remains the only thing standing between one user accidentally (or deliberately) modifying someone else's data.
