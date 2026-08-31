# Testing FastAPI: pytest-asyncio, AsyncClient, a full test suite

## Theory

**`pytest-asyncio` — finally, no more workaround.** Since chapter 12, async code has been tested with a trick. The test itself stayed an ordinary synchronous `def test_...():`. The async part lived in a nested `async def scenario()`, which the test ran via `asyncio.run(scenario())`.

That was deliberate: it avoided pulling in an extra dependency too early. Now there are noticeably more tests, and a real async HTTP client in the mix. The trick has become heavy, and `pytest-asyncio` is worth adding:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

With `asyncio_mode = "auto"`, test functions can be written directly as `async def test_...(): await ...`. Pytest wraps each one in an event loop itself, so `@pytest.mark.asyncio` is no longer needed on every test.

```python
async def test_add_task(db):
    task = await db.add_task(user_id=1, text="Buy milk")
    assert task.id == 1
```

Fixtures can be async too. You declare them with `@pytest_asyncio.fixture` (not the plain `@pytest.fixture`), using `async def` and a `yield` inside. That is the same generator mechanics as always (chapters 06/07/09).

The gain is that the fixture and the test it feeds now run in the exact same event loop. Before, the fixture had one loop and the test had another.

**`TestClient` vs `httpx.AsyncClient` — when to reach for which.** `TestClient` (chapter 15) is a synchronous wrapper, and it is enough almost all the time.

ASGI (Asynchronous Server Gateway Interface) is the protocol between a Python web application and the server that runs it. `ASGITransport` speaks that protocol and hands requests straight to the app, with no network in between.

Reach for `httpx.AsyncClient` with `ASGITransport(app=app)` when the test itself needs to stay a coroutine. Such a test can verify genuine concurrent handling of several requests via `asyncio.gather` (chapter 12), instead of calling endpoints one after another:

```python
from httpx import ASGITransport, AsyncClient

transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://test") as client:
    responses = await asyncio.gather(
        client.post("/tasks", json={"text": "A"}),
        client.post("/tasks", json={"text": "B"}),
    )
```

A non-obvious nuance: `ASGITransport` on its own does **not** trigger the app's `lifespan`. `TestClient` behaves differently — there, `with TestClient(app) as client:` explicitly triggers `startup` and `shutdown`.

If a test genuinely needs the real lifespan, it has to be driven manually via `async with app.router.lifespan_context(app):`. In our case this isn't a problem: the `db` fixture creates the database schema directly, without relying on the app's lifespan at all.

**Dependency overrides — two different tools for two different purposes.** Use `app.dependency_overrides[get_current_user] = fake_user` (chapter 15) when authentication itself isn't the thing being tested. It is fast, and no real password or token is involved.

Testing authentication **itself** needs the opposite approach: a real user, a real JWT (JSON Web Token), and no overrides at all. That covers registration, login, and rejecting a wrong password:

```python
@pytest_asyncio.fixture
async def authenticated_client(client, db):
    user = await users_storage.create_user("alice", hash_password("secret123"))
    token = create_access_token(user.username)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

Both approaches are needed at once, for different parts of the test suite. An override covers "I don't care who's logged in". A real token covers "I'm testing exactly how login works".

### Parallels with JS/TS/Node:

- `pytest-asyncio` with `asyncio_mode = "auto"` ~ what Jest/Vitest do out of the box. You write `test('...', async () => { await ... })`, with no separate declaration that the test is async.
- `httpx.AsyncClient` + `ASGITransport` ~ `supertest` in the Node ecosystem. The difference: you have to drive the lifespan hooks explicitly if you need them. In some JS testing tools, server hooks fire automatically when the test instance starts.
- Overriding one specific dependency (`dependency_overrides`) ~ mocking one specific provider/service in Nest.js tests, rather than mocking the entire HTTP layer.

## What we're adding to the project

We're adding `pytest-asyncio` and rewriting the tests in its style, with no more nested `async def scenario(): ...; asyncio.run(...)`. Fixtures in `conftest.py` also become async (`@pytest_asyncio.fixture`).

Alongside the familiar `db` (one shared in-memory SQLite connection per test) we add two more fixtures. One is `client`, an `httpx.AsyncClient` over `ASGITransport`. The other is `authenticated_client` — the same client, but carrying a real JWT for a real user.

Two new files, `tests/test_auth_api.py` and `tests/test_tasks_api.py`, give us a full set of API tests:

- registration and login;
- access with no token;
- task isolation between users;
- `404` for someone else's task and for a nonexistent one;
- a genuine concurrency test via `asyncio.gather`.

Along the way, this more thorough test suite turns up a real, hidden bug in `storage/users_storage.py`. It is not hypothetical: it genuinely breaks the tests on the very first run.

## Practical exercise

1. Add `pytest-asyncio` to dev dependencies and `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`.
2. Rewrite the `db` fixture in `conftest.py` as `@pytest_asyncio.fixture` (`async def` + `yield`) and remove the `asyncio.run(...)` wrappers. The fixture and the test's code should run in the same event loop.
3. Add a `client` fixture: an `httpx.AsyncClient` with `ASGITransport(app=app)`, depending on `db` (so the database schema is ready before the first request).
4. Add an `authenticated_client` fixture: creates a real user via `users_storage.create_user`, a real token via `create_access_token`, and returns `client` with the `Authorization` header already set.
5. Rewrite `tests/test_storage.py`/`tests/test_cli.py` from chapter 15 in pytest-asyncio style — drop `asyncio.run(...)`, make the test functions themselves `async def`.
6. Write `tests/test_auth_api.py` with four tests:
   - registration creates a user;
   - registering the same username again gets `400`;
   - logging in with the right password returns a token;
   - logging in with the wrong password gets `401`.
7. Write `tests/test_tasks_api.py` with five tests:
   - a protected route with no token gets `401`;
   - creating and listing tasks through `authenticated_client`;
   - `404` (and nothing else) for a nonexistent task;
   - full isolation between two users — the second sees none of the first's tasks;
   - a concurrency test: three simultaneous `POST /tasks` via `asyncio.gather`, each getting its own unique `id`.
8. Run the whole suite. Some test may fail with a username-uniqueness violation before its body has even run. Don't rush to rename users in the tests. Work out why the `db` fixture, which gives every test a fresh in-memory connection, doesn't save you from the collision.

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
    """Client pre-authenticated as a real, freshly-created user (real JWT)."""
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

Now, about the question from exercise 8. The first real run of the full suite failed like this. The very first test in the whole suite, `test_register_creates_a_user`, suddenly failed with `400` instead of `201`, as if `alice` already existed.

And yet every test gets its own, fresh in-memory connection via the `db` fixture. The cause turned out to be in `storage/users_storage.py`, written back in chapter 15:

```python
# BEFORE the fix:
from .sqlite_storage import db_connection   # <- the name is bound ONCE, at import time

async def create_user(username: str, hashed_password: str) -> User:
    async with db_connection() as conn:   # <- always calls the REAL, un-patched function
        ...
```

The call `monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)` replaces the `db_connection` attribute **on the `sqlite_storage` module itself**. But `users_storage.py` had imported the name directly, as `from .sqlite_storage import db_connection`. That import created a separate, independent binding to the original function in its own namespace.

Patching the attribute on the `sqlite_storage` module doesn't touch that local binding at all. So `users_storage.create_user` and `get_user_by_username` kept reading and writing the **real** `taskman.db` file on disk, completely bypassing the in-memory fixture.

That is exactly why `alice` kept existing. She had been created once in an earlier manual run, through the command-line interface (CLI) or the API. That row stayed in the real file, and every subsequent test then hit it.

This is exactly the "import a specific name instead of the module" trap that chapter 05 warned about. It is also why `cli/commands.py` imports `storage` as a module, rather than pulling functions out by name individually. Here the trap slipped in quietly, and it didn't show up until the tests started hitting the database thoroughly. The fix:

```python
# AFTER the fix:
from . import sqlite_storage   # <- import the MODULE as a whole

async def create_user(username: str, hashed_password: str) -> User:
    async with sqlite_storage.db_connection() as conn:   # <- attribute access, EVERY time
        ...
```

Calling `sqlite_storage.db_connection()` goes through the module's attribute afresh every time. It sees whatever version is currently set on `sqlite_storage` — the original, or a fixture's patch.

Key decisions:

- Async fixtures (`@pytest_asyncio.fixture`) guarantee that the fixture and the test run in the exact same event loop. No more guessing whether a connection object survives the trip between separate `asyncio.run()` calls, as we had to since chapter 12.
- `authenticated_client` is built on top of `client`; it is not a replacement for it. Both approaches — override and a real token — coexist in the same test suite, each for its own category of checks.
- `ASGITransport` doesn't run the app's lifespan on its own. The `db` fixture takes schema initialization on itself explicitly, which is exactly why the missing lifespan isn't a problem in tests.
- The concurrency test (`asyncio.gather` over three parallel `POST`s) isn't just for show. It verifies that three simultaneous requests genuinely get three distinct, non-overlapping `id`s. That means the storage layer, with its own connection per call (chapters 08/12), behaves correctly under real load, not sequential load.

## Check yourself

1. How does `@pytest_asyncio.fixture` with `async def`/`yield` differ from the older pattern (chapters 12–15)? That pattern was a synchronous fixture with `asyncio.run(...)` inside, creating the object we need. What specific risk did it carry that the first approach removes?
2. Why doesn't `ASGITransport(app=app)` on its own trigger the app's `lifespan`, and why doesn't that cause problems in this particular project?
3. In `users_storage.py`, the line `from .sqlite_storage import db_connection` makes `monkeypatch.setattr(sqlite_storage, "db_connection", ...)` useless for that module. Describe in your own words why. Then explain why the patch still works for `cli/commands.py`, which imports `storage` as a whole.
4. When should you use `app.dependency_overrides[get_current_user] = fake_user`, and when `authenticated_client` with a real token? What does each approach actually verify, and what does it not?
5. The concurrency test creates three tasks via `asyncio.gather` and checks that the resulting `id`s are `[1, 2, 3]`, with no repeats. What property of the storage layer does this actually test?

<details>
<summary>Answers</summary>

1. `@pytest_asyncio.fixture` guarantees that setup (before `yield`), the test body and teardown (after `yield`) all run in the literal same event loop. That loop is created and managed by `pytest-asyncio` itself. The older "synchronous fixture + `asyncio.run(...)` inside" pattern technically worked, as verified empirically back in chapter 12. But it relied on luck. An `aiosqlite.Connection` was created inside one `asyncio.run()` loop, which then closed. The object then had to stay usable in a *different*, separate loop — the one managing the test itself. That is an accident of `aiosqlite`'s specific implementation, not a guarantee written down anywhere in `asyncio`'s own documentation. The `pytest-asyncio` plugin removes the need to rely on that luck at all.
2. `ASGITransport` is just a transport. It sends ASGI requests straight into the application as a function call, with none of the wrapper logic that starts and stops a server. `TestClient` is different: its `with` block explicitly invokes the `lifespan` protocol. In this project the missing lifespan is not a problem, because the `db` fixture already creates the needed tables (`tasks`, `users`) directly. The equivalent setup happens, just through a different path.
3. In `users_storage.py`, the line `from .sqlite_storage import db_connection` creates a **separate, independent** binding of the name `db_connection` in that module's namespace. The binding is made at import time, and it points at whatever function object existed at that moment. It has no connection to later changes to the `db_connection` attribute on the `sqlite_storage` module itself. By contrast, `cli/commands.py` writes `from ..storage import db` and imports the **whole module**. More precisely, it imports the `sqlite_storage` object that `db` points at. It then calls functions via `db.add_task(...)`, so it looks up the attribute on the module object fresh, at every call. It never relies on a binding fixed once and for all at import time.
4. Use `app.dependency_overrides[get_current_user] = fake_user` when authentication itself isn't what's being tested. A test about filtering tasks by status shouldn't depend on whether login actually works. The `authenticated_client` fixture, with a real, genuinely issued token, is needed when you test the authentication mechanism itself. It is also needed for anything that depends on authentication genuinely succeeding — for example, checking that an expired or forged token is correctly rejected. An override is useless there, because it bypasses the very code that needs verifying.
5. This test verifies that `id` assignment via `AUTOINCREMENT` stays correct and collision-free under concurrency. Several `add_task` calls run at the same time, each through its own connection (chapters 08/12: every call opens its own connection to SQLite). Concurrent access to the same table must not give two requests the same `id`, and must not drop any of the three requests. So this is a direct, practical check on SQLite's theoretical guarantee of write serialization at the engine level. The check is done in combination with our specific way of opening a connection per call, not in theory alone.

</details>

## Common mistake

The most valuable (and quietest) mistake in this chapter isn't hypothetical. It genuinely happened while building the full test suite. The mistake: importing a specific function name from a module, as in `from .sqlite_storage import db_connection`, instead of importing the module itself. That code would later need to be patched via `monkeypatch`.

A developer who has seen `monkeypatch.setattr(module, "name", fake)` in earlier chapters expects the patch to work for **any** code that calls `name()`. It doesn't. The patch only works for code that reaches `name` **through the module's attribute** (`module.name()`) at call time. Code that fixed its own local binding back at import time keeps calling the original.

The mistake doesn't show up right away. The module works perfectly fine in the real application: there is no monkeypatch there at all, and everything calls the real function. It surfaces only when someone tries to test that code in isolation.

Even then it does not surface as an obvious import error. It surfaces as unexplained state leaking between tests. In our case: a username-uniqueness violation, exactly where the test's logic says the user should be created from scratch.

The second common mistake is about `lifespan`. You set up `httpx.AsyncClient` with `ASGITransport`, it "just works" for ordinary requests, and you assume the app's `lifespan` hooks ran too. Those hooks create tables and connect to external services on startup.

Without an explicit `async with app.router.lifespan_context(app):`, that simply doesn't happen. If the test infrastructure doesn't initialize state some other way, the very first request in a test fails with something like "no such table". This project does initialize it another way, through the `db` fixture.

The first instinct then is to blame your own SQL (Structured Query Language). The real cause is that `lifespan` doesn't run on its own in tests.
