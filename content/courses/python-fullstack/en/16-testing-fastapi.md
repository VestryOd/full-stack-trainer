# Testing FastAPI: pytest-asyncio, AsyncClient, a full test suite

## Theory

**`pytest-asyncio` — finally, no more workaround.** Since chapter 12, async code has been tested with the trick "an ordinary synchronous `def test_...():`, with a nested `async def scenario(): ...` inside plus `asyncio.run(scenario())`" — deliberately, to avoid pulling in an extra dependency too early. Now that there are noticeably more tests and a real async HTTP client in the mix, the trick gets heavy, and `pytest-asyncio` earns its keep:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

With `asyncio_mode = "auto"`, test functions can be written directly as `async def test_...(): await ...` — pytest wraps them in an event loop itself, with no `@pytest.mark.asyncio` needed on every one.

```python
async def test_add_task(db):
    task = await db.add_task(user_id=1, text="Buy milk")
    assert task.id == 1
```

Fixtures can be async too — via `@pytest_asyncio.fixture` (not the plain `@pytest.fixture`) with `async def` and `yield` inside — the same generator mechanics as always (chapters 06/07/09), just now both the fixture and the test it feeds run in the exact same event loop, instead of "one function's loop" and "a different function's loop."

**`TestClient` vs `httpx.AsyncClient` — when to reach for which.** `TestClient` (chapter 15) is a synchronous wrapper, sufficient almost all the time. `httpx.AsyncClient` with `ASGITransport(app=app)` is needed when the test itself needs to stay a coroutine — for example, to genuinely verify concurrent handling of several requests via `asyncio.gather` (chapter 12), rather than calling endpoints strictly one after another:

```python
from httpx import ASGITransport, AsyncClient

transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://test") as client:
    responses = await asyncio.gather(
        client.post("/tasks", json={"text": "A"}),
        client.post("/tasks", json={"text": "B"}),
    )
```

A non-obvious nuance: `ASGITransport` on its own does **not** trigger the app's `lifespan` (unlike `TestClient`, where `with TestClient(app) as client:` explicitly triggers `startup`/`shutdown`) — if a test genuinely needs the real lifespan, it has to be driven manually via `async with app.router.lifespan_context(app):`. In our case this isn't a problem: the `db` fixture creates the database schema directly, without relying on the app's lifespan at all.

**Dependency overrides — two different tools for two different purposes.** `app.dependency_overrides[get_current_user] = fake_user` (chapter 15) is the right fit when authentication itself isn't the thing being tested — fast, with no real password or token involved. But testing authentication **itself** (registration, login, rejecting a wrong password) needs the opposite approach — a real user, a real JWT, no overrides at all:

```python
@pytest_asyncio.fixture
async def authenticated_client(client, db):
    user = await users_storage.create_user("alice", hash_password("secret123"))
    token = create_access_token(user.username)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

Both approaches are needed at once, for different parts of the test suite — an override for "I don't care who's logged in," a real token for "I'm testing exactly how login works."

### Parallels with JS/TS/Node:

- `pytest-asyncio` with `asyncio_mode = "auto"` ~ what Jest/Vitest do out of the box — `test('...', async () => { await ... })` with no separate declaration that the test is async.
- `httpx.AsyncClient` + `ASGITransport` ~ `supertest` in the Node ecosystem, except it requires explicitly driving lifespan hooks if you need them — unlike some JS testing tools where server hooks fire automatically when the test instance spins up.
- Overriding one specific dependency (`dependency_overrides`) ~ mocking one specific provider/service in Nest.js tests, rather than mocking the entire HTTP layer.

## What we're adding to the project

We're adding `pytest-asyncio` and rewriting the tests in its style — no more nested `async def scenario(): ...; asyncio.run(...)`. Fixtures in `conftest.py` also become async (`@pytest_asyncio.fixture`), and alongside the familiar `db` (one shared in-memory SQLite connection per test), we add `client` (an `httpx.AsyncClient` over `ASGITransport`) and `authenticated_client` (the same client, but with a real JWT for a real user). `tests/test_auth_api.py` and `tests/test_tasks_api.py` give us a full set of API tests: registration, login, access with no token, task isolation between users, `404` for someone else's/a nonexistent task, and a genuine concurrency test via `asyncio.gather`.

Along the way, this more thorough test suite turns up a real, hidden bug in `storage/users_storage.py` — not hypothetical, one that genuinely breaks the tests on the very first run.

## Practical exercise

1. Add `pytest-asyncio` to dev dependencies and `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`.
2. Rewrite the `db` fixture in `conftest.py` as `@pytest_asyncio.fixture` (`async def` + `yield`), removing the `asyncio.run(...)` wrappers — the fixture and the test's code should run in the same event loop.
3. Add a `client` fixture: an `httpx.AsyncClient` with `ASGITransport(app=app)`, depending on `db` (so the database schema is ready before the first request).
4. Add an `authenticated_client` fixture: creates a real user via `users_storage.create_user`, a real token via `create_access_token`, and returns `client` with the `Authorization` header already set.
5. Rewrite `tests/test_storage.py`/`tests/test_cli.py` from chapter 15 in pytest-asyncio style — drop `asyncio.run(...)`, make the test functions themselves `async def`.
6. Write `tests/test_auth_api.py`: registration creates a user; registering the same username again gets `400`; logging in with the right password returns a token; logging in with the wrong password gets `401`.
7. Write `tests/test_tasks_api.py`: a protected route with no token gets `401`; creating and listing tasks through `authenticated_client`; `404` (nothing else) for a nonexistent task; full isolation between two different users (the second sees none of the first's tasks); a concurrency test — three simultaneous `POST /tasks` via `asyncio.gather`, each getting its own unique `id`.
8. Run the whole suite. If some test fails with a username-uniqueness violation before the test body has even run — don't rush to rename users in the tests to something different. Work out why the `db` fixture, which gives every test a fresh in-memory connection, doesn't save you from the collision.

## Worked solution

`pyproject.toml` (a pytest section and `pytest-asyncio` added):

```toml
[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "mypy>=1.10", "httpx"]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.11"
strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
disallow_incomplete_defs = false
```

`tests/conftest.py` (new style — async fixtures):

```python
from contextlib import asynccontextmanager

import aiosqlite
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from taskman.api.app import app
from taskman.auth import create_access_token, hash_password
from taskman.storage import TaskStorage, sqlite_storage, users_storage


@pytest_asyncio.fixture
async def db(monkeypatch):
    """A single in-memory SQLite connection shared for the duration of one test."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row

    @asynccontextmanager
    async def fake_db_connection():
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)
    await sqlite_storage.init_db()
    await users_storage.init_users_table()
    yield sqlite_storage
    await conn.close()


@pytest_asyncio.fixture
async def client(db: TaskStorage):
    """An httpx.AsyncClient talking directly to the ASGI app, no real network involved."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient, db: TaskStorage) -> AsyncClient:
    """A client pre-authenticated as a real, freshly-created user (real JWT, no override)."""
    user = await users_storage.create_user("alice", hash_password("secret123"))
    token = create_access_token(user.username)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

`tests/test_auth_api.py` (new file):

```python
async def test_register_creates_a_user(client):
    response = await client.post(
        "/auth/register", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 201
    assert response.json()["username"] == "alice"


async def test_register_rejects_duplicate_username(client):
    payload = {"username": "alice", "password": "secret123"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 400


async def test_login_returns_a_token(client):
    await client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    response = await client.post(
        "/auth/token", data={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert len(response.json()["access_token"]) > 10


async def test_login_rejects_wrong_password(client):
    await client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    response = await client.post(
        "/auth/token", data={"username": "alice", "password": "WRONG"}
    )
    assert response.status_code == 401
```

`tests/test_tasks_api.py` (new file):

```python
import asyncio

from taskman.auth import create_access_token, hash_password
from taskman.storage import users_storage


async def test_protected_route_without_token_is_rejected(client):
    response = await client.get("/tasks")
    assert response.status_code == 401


async def test_create_and_list_task(authenticated_client):
    response = await authenticated_client.post(
        "/tasks", json={"text": "Buy milk", "priority": "high"}
    )
    assert response.status_code == 201
    assert response.json()["priority"] == "high"

    response = await authenticated_client.get("/tasks")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["text"] == "Buy milk"


async def test_mark_missing_task_done_returns_404(authenticated_client):
    response = await authenticated_client.patch("/tasks/999/done")
    assert response.status_code == 404


async def test_users_only_see_their_own_tasks(client, db):
    alice = await users_storage.create_user("alice", hash_password("secret123"))
    bob = await users_storage.create_user("bob", hash_password("hunter22"))
    alice_token = create_access_token(alice.username)
    bob_token = create_access_token(bob.username)

    client.headers["Authorization"] = f"Bearer {alice_token}"
    await client.post("/tasks", json={"text": "Alice task"})

    client.headers["Authorization"] = f"Bearer {bob_token}"
    response = await client.get("/tasks")
    assert response.json() == []


async def test_concurrent_requests_are_handled_independently(authenticated_client):
    responses = await asyncio.gather(
        authenticated_client.post("/tasks", json={"text": "Task A"}),
        authenticated_client.post("/tasks", json={"text": "Task B"}),
        authenticated_client.post("/tasks", json={"text": "Task C"}),
    )
    assert [r.status_code for r in responses] == [201, 201, 201]

    ids = sorted(r.json()["id"] for r in responses)
    assert ids == [1, 2, 3]
```

Now, about the question from exercise 8. The first real run of the full suite failed like this: `test_register_creates_a_user` (the very first test in the whole suite!) suddenly failed with `400` instead of `201`, as if `alice` already existed — even though every test gets its own, fresh in-memory connection via the `db` fixture. The cause turned out to be in `storage/users_storage.py`, written back in chapter 15:

```python
# BEFORE the fix:
from .sqlite_storage import db_connection   # <- the name is bound ONCE, at import time

async def create_user(username: str, hashed_password: str) -> User:
    async with db_connection() as conn:   # <- always calls the REAL, un-patched function
        ...
```

`monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)` replaces the `db_connection` attribute **on the `sqlite_storage` module itself** — but `users_storage.py` had imported the name `db_connection` directly (`from .sqlite_storage import db_connection`), creating a separate, independent binding to the original function in its own namespace, right at import time. Patching the attribute on the `sqlite_storage` module doesn't touch that local binding at all — `users_storage.create_user`/`get_user_by_username` kept reading and writing the **real** `taskman.db` file on disk, completely bypassing the in-memory fixture. That's exactly why `alice`, once created (even in an earlier, separate manual CLI or API run), stayed in the real file and got in the way of every subsequent test.

This is exactly the "import a specific name instead of the module" trap chapter 05 warned about (which is also why `cli/commands.py` imports `storage` as a module rather than pulling functions out by name individually) — it just quietly slipped into `users_storage.py` and didn't show up until tests started genuinely, thoroughly hitting the database. The fix:

```python
# AFTER the fix:
from . import sqlite_storage   # <- import the MODULE as a whole

async def create_user(username: str, hashed_password: str) -> User:
    async with sqlite_storage.db_connection() as conn:   # <- attribute access, EVERY time
        ...
```

Calling `sqlite_storage.db_connection()` goes through the module's attribute afresh every time — and sees whatever version is currently set on `sqlite_storage`, whether that's the original or a fixture's patch.

Key decisions:

- Async fixtures (`@pytest_asyncio.fixture`) guarantee that the fixture and the test run in the exact same event loop — no more guessing whether a connection object will survive the trip between separate `asyncio.run()` calls, as we had to since chapter 12.
- `authenticated_client` is built on top of `client`, not a replacement for it — both approaches (override and a real token) coexist in the same test suite, each for its own category of checks.
- `ASGITransport` doesn't run the app's lifespan on its own — the `db` fixture takes schema initialization on itself explicitly, which is exactly why the missing lifespan isn't a problem in tests.
- The concurrency test (`asyncio.gather` over three parallel `POST`s) isn't just for show: it verifies that three simultaneous requests genuinely get three distinct, non-overlapping `id`s — that the storage layer (with its own connection per call, chapters 08/12) behaves correctly under real, not sequential, load.

## Check yourself

1. How does `@pytest_asyncio.fixture` with `async def`/`yield` differ from the pattern "a synchronous fixture, with `asyncio.run(...)` inside creating the object we need" (chapters 12–15)? What specific risk did the second approach carry that the first one removes?
2. Why doesn't `ASGITransport(app=app)` on its own trigger the app's `lifespan`, and why doesn't that cause problems in this particular project?
3. Describe in your own words why `from .sqlite_storage import db_connection` in `users_storage.py` makes `monkeypatch.setattr(sqlite_storage, "db_connection", ...)` useless specifically for that module, but not for `cli/commands.py`, which imports `storage` as a whole.
4. When should you use `app.dependency_overrides[get_current_user] = fake_user`, and when `authenticated_client` with a real token? What does each approach actually verify, and what does it not?
5. The concurrency test creates three tasks via `asyncio.gather` and checks that the resulting `id`s are `[1, 2, 3]`, with no repeats. What property of the storage layer does this actually test?

<details>
<summary>Answers</summary>

1. `@pytest_asyncio.fixture` guarantees that setup (before `yield`), the test body, and teardown (after `yield`) all run in the literal same event loop, created and managed by `pytest-asyncio` itself. The "synchronous fixture + `asyncio.run(...)` inside" pattern technically worked (as verified empirically back in chapter 12), but relied on objects like `aiosqlite.Connection`, created inside one, already-closed `asyncio.run()` loop, remaining usable in a *different*, separate loop managing the test itself — that's a lucky accident of `aiosqlite`'s specific implementation, not a guarantee written down anywhere in `asyncio`'s own documentation. `pytest-asyncio` removes the need to rely on that luck at all.
2. `ASGITransport` is just a transport that sends ASGI requests directly into the application as a function call, with none of the wrapper logic that usually handles starting/stopping a server (unlike `TestClient`, whose `with` block explicitly invokes the `lifespan` protocol). In this project that's not a problem, because the `db` fixture already creates the needed tables (`tasks`, `users`) directly, not through the app's `lifespan` — the equivalent setup happens, just through a different path.
3. `from .sqlite_storage import db_connection` in `users_storage.py` creates a **separate, independent** binding of the name `db_connection` in `users_storage`'s own namespace, at import time — that binding points at whatever function object existed at that moment, and has no connection to later changes to the `db_connection` attribute on the `sqlite_storage` module itself. `cli/commands.py`, by contrast, imports `from ..storage import db` — the entire MODULE (more precisely, the `sqlite_storage` object that `db` points at), and calls its functions via `db.add_task(...)` — meaning it looks up the attribute on the module object fresh, every time it's called, rather than relying on a binding fixed once and for all at import time.
4. `app.dependency_overrides[get_current_user] = fake_user` is the right fit when authentication itself isn't what's being tested — a test about filtering tasks by status shouldn't depend on whether login actually works. `authenticated_client` with a real, genuinely issued token is needed exactly when testing the authentication mechanism itself, or something that depends on it genuinely succeeding (say, that an expired or forged token is correctly rejected) — an override is useless there, because it bypasses entirely the code that needs verifying.
5. This test verifies that when several `add_task` calls run concurrently, each through its own, independently opened connection (chapters 08/12: every call opens its own connection to SQLite), `id` assignment via `AUTOINCREMENT` stays correct and collision-free — that concurrent access to the same table doesn't result in two requests accidentally getting the same `id`, and doesn't drop any of the three requests. It's a direct, practical check that SQLite's theoretical guarantees (write serialization at the engine level) actually hold in combination with our specific way of opening a connection per call — not just in theory.

</details>

## Common mistake

The most valuable (and quietest) mistake in this chapter isn't hypothetical — it genuinely happened while building the full test suite: importing a specific function name from a module (`from .sqlite_storage import db_connection`) instead of the module itself, in code that would later need to be patched via `monkeypatch`. A developer who's already seen `monkeypatch.setattr(module, "name", fake)` in earlier chapters reasonably expects the patch to work for **any** code that eventually calls `name()` — but the patch only works for code that reaches `name` **through the module's attribute** (`module.name()`) at call time, not for code that fixed its own, local binding to the function back at import time. The mistake doesn't show up right away — the module works perfectly fine in the real application (there's no monkeypatch there at all, everything calls the real function) — and only surfaces once someone tries to test that code in isolation, and even then, not as an obvious import error but as unexplained state leaking between tests (in our case, a username-uniqueness violation exactly where the test's logic says the user should be created from scratch).

The second common mistake is setting up `httpx.AsyncClient` with `ASGITransport` and assuming that, since it "just works" for ordinary requests, the app's `lifespan` hooks (creating tables, connecting to external services on startup) must have run somewhere along the way too. Without an explicit `async with app.router.lifespan_context(app):`, that simply doesn't happen — if the test infrastructure doesn't handle state initialization some other way (as in this project, via the `db` fixture), the very first request in a test fails with something like "no such table," and the first instinct is "I must have gotten the SQL wrong," not "I forgot that `lifespan` doesn't run on its own in tests."
