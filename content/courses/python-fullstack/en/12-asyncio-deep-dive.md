# asyncio: coroutines, gather, async protocols

## Theory

**`async`/`await` looks like JS syntactically — there's more semantic difference than it seems.** The first, most important difference: in JS, `async function f() { ... }`, called without `await`, **starts executing immediately** — the Promise is created and the work inside starts right away; the caller just doesn't wait for the result. In Python, `async def f(): ...`, called without `await`, **does absolutely nothing**:

```python
async def fetch_data():
    print("started")
    return 42

coro = fetch_data()   # nothing printed! coro is just a coroutine object
```

This is exactly the same mechanic as generators from chapter 07: calling a function with `yield` doesn't run its body, it creates a generator object — calling an `async def` function doesn't run its body, it creates a coroutine object. The body only actually starts executing once the coroutine is **awaited** (`await coro`), scheduled as a `Task` (`asyncio.create_task(coro)`), or passed to `asyncio.run(coro)`. A forgotten `await` isn't a syntax error — it's a silent bug: Python emits `RuntimeWarning: coroutine 'fetch_data' was never awaited`, and the code quietly doesn't do what it was supposed to.

**A cooperative, single-threaded event loop — and why it's closer to Node than anything from chapter 11.** asyncio's event loop is single-threaded, like Node's, and this is a fundamentally different model from `threading`/the GIL (previous chapter): there, switching between threads is forced by the interpreter (on a timer, or on a blocking call); here, a coroutine only yields control **exactly where `await` is explicitly written** — nowhere else. A coroutine that never awaits inside a long loop blocks the **entire** event loop, exactly the way a heavy synchronous computation blocks Node's single thread. Of everything in this course, `asyncio` is the one place where a JS developer's intuition — "one thread, cooperative switching, blocking code hurts everyone" — carries over to Python almost without adjustment.

**`asyncio.gather` vs `Promise.all` — similar, with two concrete differences.**

```python
results = await asyncio.gather(coro1(), coro2(), coro3())
```

The direct counterpart of `Promise.all([p1, p2, p3])` — waits for all of them to finish, returns a list of results in the same order. The differences show up around exceptions:

1. By default, if even one coroutine raises, `gather` immediately re-raises it to the caller — but **the other coroutines aren't automatically cancelled** and keep running in the background; nobody's just picking up their results through `gather` anymore. This can be checked empirically:

```python
import asyncio

async def worker(name, delay, fail=False):
    await asyncio.sleep(delay)
    if fail:
        raise ValueError(f"{name} failed")
    print(f"{name}: done")
    return name

async def main():
    try:
        await asyncio.gather(worker("A", 0.3), worker("B", 0.1, fail=True), worker("C", 0.5))
    except ValueError as e:
        print("gather raised:", e)
    await asyncio.sleep(0.6)

asyncio.run(main())
```

Real output:

```txt
gather raised: B failed
A: done
C: done
```

The exception surfaces right after `B` fails (at 0.1s), but `A` and `C` print "done" **afterward** — they weren't cancelled, they just finished up in the background, with nowhere left to hand their result to.

2. `gather(..., return_exceptions=True)` changes the behavior entirely: instead of raising, the exception is placed into the result list at its slot, alongside the successful results:

```python
results = await asyncio.gather(worker("D", 0.1), worker("E", 0.1, fail=True), return_exceptions=True)
# results == ['D', ValueError('E failed')]
```

This is close in spirit to `Promise.allSettled` (also "give me every outcome, don't fail on the first one"), but the result shape differs: JS's `allSettled` returns `{status, value}`/`{status, reason}` objects, while `gather(..., return_exceptions=True)` returns a flat list, with the exception object itself sitting where the failed coroutine's result would have been.

**`Task` — how something starts immediately, instead of lazily.** `asyncio.create_task(coro)` takes an already-created coroutine and **immediately** schedules it to run on the event loop, without waiting for `await` — from that point on, it runs concurrently with the rest of the code:

```python
task = asyncio.create_task(fetch_data())  # already started running
# ... other code ...
result = await task                        # wait for the result (if not already ready)
```

Here's the twist: it's `create_task`, not a bare coroutine, that's actually closest in semantics to "called an async function in JS" (starts immediately), because a bare coroutine in Python, unlike a JS Promise, is **lazy** (see the first theory point above).

**Async context managers and async generators — the same protocols from chapters 06/07, just with `await` inside.** `async with` uses `__aenter__`/`__aexit__` instead of `__enter__`/`__exit__` — needed when acquiring/releasing the resource itself requires an `await` (an async database connection, for instance). `async for` uses `__aiter__`/`__anext__` instead of `__iter__`/`__next__`, and an async generator is `async def` with `yield` inside — the same machinery as chapter 07, just with each step potentially awaiting something.

### Parallels with JS/TS/Node:

- A Python coroutine is lazy (doesn't run until `await`/`create_task`); a JS Promise is eager (starts running as soon as it's created). `asyncio.create_task` is the closest counterpart of "called an async function and didn't wait for it right away."
- asyncio's single-threaded cooperative event loop is conceptually the same as Node's, unlike `threading`/the GIL (chapter 11): switching happens only at an explicit `await`, nothing forces it.
- `asyncio.gather` ~ `Promise.all`, but by default it doesn't cancel the "siblings" when one coroutine fails (contrary to the impression of fail-fast behavior); `return_exceptions=True` is close in spirit to `Promise.allSettled`, but returns a flat list instead of `{status, value/reason}` objects.
- `async with`/`async for` are the same protocols as the context manager (chapter 06) and iterator/generator (chapter 07), just with `await` points inside.

## What we're adding to the project

The storage layer moves from synchronous `sqlite3` to asynchronous `aiosqlite` — the project's first real runtime dependency (until now, `dependencies = []` in `pyproject.toml` was empty). The CLI handlers become `async def`, the `log_command` decorator learns to wrap async functions, and the entry point `main()` stays synchronous (a hard requirement of the `pyproject.toml` entry point) and simply kicks off the async code via `asyncio.run(...)`. Importantly, not every function becomes async — `filter_by_status`/`sort_tasks`/`paginate`/`get_page` stay exactly as they are, because they're not waiting on anything — they're pure, synchronous transformations of an already-loaded list.

## Practical exercise

1. Install `aiosqlite`, add it to `dependencies` in `pyproject.toml` (the project's first real, non-dev dependency).
2. Rewrite `storage/sqlite_storage.py`: `db_connection` becomes an `@asynccontextmanager` function with `await aiosqlite.connect(...)`, committing/rolling back via `await conn.commit()`/`await conn.rollback()`. `init_db`, `add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks` all become `async def`, with every database call going through `await`. In `list_tasks`, use `async for row in cursor:` instead of `fetchall()` — iterate rows lazily, one at a time.
3. Leave `filter_by_status`, `sort_tasks`, `paginate`, `get_page` **untouched** — think about why that's correct before rewriting them "just in case."
4. Update `TaskStorage` in `storage/protocol.py` — the methods that are actually awaited in the CLI need to be declared as `async def method(...) -> ...: ...` in the protocol itself.
5. In `cli/commands.py`, make `handle_add`/`handle_list`/`handle_done` async (`await db.xxx(...)` instead of calling directly). Rewrite `log_command`: the decorator function itself stays a normal (non-`async`) function, but the `wrapper` it returns is now `async def` and does `await func(args)` instead of `func(args)`.
6. In `cli/app.py`, split the entry point into `async def async_main()` (the real logic: `await db.init_db()`, argument parsing, `await handler(args)`) and `def main() -> None: asyncio.run(async_main())` — `main` is the one registered in `[project.scripts]`.
7. Leave `append_log`/`FileLock` (chapter 06) synchronous. Think about it: since `log_command`'s `wrapper` is now async, and `append_log` inside it is a blocking, synchronous file I/O call, doesn't that block the event loop? In what scenario would that actually be a real problem, and in what scenario is it not, for this specific CLI?
8. Update `tests/conftest.py`/`tests/test_storage.py`/`tests/test_cli.py` for the async storage layer — without adding `pytest-asyncio` (a separate tool from chapter 16): keep test functions ordinary (`def test_...():`), wrapping the async scenario inside each one in `asyncio.run(...)`.

## Worked solution

`pyproject.toml` (a real dependency added):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["aiosqlite>=0.19"]

[project.optional-dependencies]
dev = ["pytest>=8", "mypy>=1.10"]

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.mypy]
python_version = "3.11"
strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
```

`src/taskman/storage/sqlite_storage.py` (fully async database access; the synchronous transforms are unchanged):

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
                text TEXT NOT NULL,
                priority INTEGER NOT NULL,
                done INTEGER NOT NULL
            )
            """
        )


def _row_to_task(row: aiosqlite.Row) -> Task:
    return Task(
        id=row["id"],
        text=row["text"],
        priority=Priority(row["priority"]),
        done=bool(row["done"]),
    )


async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    return Task(id=task_id, text=text, priority=priority, done=False)


async def find_task(task_id: int) -> Task | None:
    async with db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_task(row)


async def get_task(task_id: int) -> Task:
    task = await find_task(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


async def mark_done(task_id: int) -> Task:
    task = await get_task(task_id)
    async with db_connection() as conn:
        await conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    task.done = True
    return task


async def list_tasks() -> list[Task]:
    tasks: list[Task] = []
    async with db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM tasks")
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

`src/taskman/storage/protocol.py` (updated — the database-touching methods are now `async`):

```python
from typing import Protocol

from ..models import Priority, Task


class TaskStorage(Protocol):
    async def init_db(self) -> None: ...
    async def add_task(self, text: str, priority: Priority = ...) -> Task: ...
    async def find_task(self, task_id: int) -> Task | None: ...
    async def get_task(self, task_id: int) -> Task: ...
    async def mark_done(self, task_id: int) -> Task: ...
    async def list_tasks(self) -> list[Task]: ...
    def filter_by_status(self, items: list[Task], status: str) -> list[Task]: ...
    def sort_tasks(self, items: list[Task], sort_by: str) -> list[Task]: ...
    def get_page(self, items: list[Task], page: int, page_size: int) -> list[Task]: ...
```

(`storage/__init__.py` doesn't change — `db: TaskStorage = sqlite_storage` still passes the structural check; the protocol now just requires async methods, and `sqlite_storage` provides them.)

`src/taskman/cli/commands.py` (updated — the handlers and `log_command` are now async):

```python
import argparse
import functools
import sys
from typing import Any, Callable, Coroutine, TypeVar

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db

R = TypeVar("R")


def print_err(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def log_command(
    func: Callable[[argparse.Namespace], Coroutine[Any, Any, R]]
) -> Callable[[argparse.Namespace], Coroutine[Any, Any, R]]:
    @functools.wraps(func)
    async def wrapper(args: argparse.Namespace) -> R:
        print_err(f"[log] running: {args.command}")
        append_log(f"running: {args.command}")
        result = await func(args)
        print_err(f"[log] done: {args.command}")
        append_log(f"done: {args.command}")
        return result

    return wrapper


@log_command
async def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = await db.add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
async def handle_list(args: argparse.Namespace) -> None:
    all_tasks = await db.list_tasks()
    result = db.sort_tasks(db.filter_by_status(all_tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
        return
    page = db.get_page(result, args.page, args.page_size)
    if not page:
        print(f"No tasks on page {args.page}.")
        return
    total_pages = (len(result) + args.page_size - 1) // args.page_size
    for task in page:
        print(task)
    print(f"-- page {args.page} of {total_pages} --")


@log_command
async def handle_done(args: argparse.Namespace) -> None:
    try:
        task = await db.mark_done(args.id)
    except TaskNotFoundError as error:
        print_err(f"Error: {error}")
        return
    print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}
```

`src/taskman/cli/app.py` (updated — a synchronous entry point on top of the async logic):

```python
import asyncio

from ..storage import db
from .commands import COMMAND_HANDLERS
from .parser import build_parser


async def async_main() -> None:
    await db.init_db()
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    await handler(args)


def main() -> None:
    asyncio.run(async_main())
```

`tests/conftest.py` (updated — an async fixture connection, no `pytest-asyncio`):

```python
import asyncio
from contextlib import asynccontextmanager

import aiosqlite
import pytest

from taskman.storage import sqlite_storage


@pytest.fixture
def db(monkeypatch):
    async def _connect() -> aiosqlite.Connection:
        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        return conn

    conn = asyncio.run(_connect())

    @asynccontextmanager
    async def fake_db_connection():
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)
    asyncio.run(sqlite_storage.init_db())
    yield sqlite_storage
    asyncio.run(conn.close())
```

`tests/test_storage.py` (updated — test functions stay synchronous, the async scenario inside each goes through `asyncio.run`):

```python
import asyncio

import pytest

from taskman.models import Priority, Task, TaskNotFoundError
from taskman.storage.sqlite_storage import sort_tasks


def test_add_task_assigns_incrementing_ids(db):
    async def scenario():
        first = await db.add_task("Buy milk")
        second = await db.add_task("Write report")
        assert first.id == 1
        assert second.id == 2

    asyncio.run(scenario())


def test_get_task_raises_when_missing(db):
    async def scenario():
        with pytest.raises(TaskNotFoundError):
            await db.get_task(999)

    asyncio.run(scenario())


def test_sort_tasks_by_priority_orders_high_first():
    # a pure, synchronous function -- no db fixture, no asyncio.run needed
    low = Task(id=1, text="low", priority=Priority.LOW)
    high = Task(id=2, text="high", priority=Priority.HIGH)
    result = sort_tasks([low, high], "priority")
    assert result == [high, low]
```

Key decisions:

- `log_command` is typed via `Coroutine[Any, Any, R]`, not the more general `Awaitable[R]`. The first, apparently "more generic" attempt (`Awaitable[R]`) compiled fine, but `asyncio.run(handle_add(args))` in the tests failed type-checking: `asyncio.run` specifically requires a `Coroutine`, not an arbitrary awaitable object (a category that also includes things like `Future`). Since `log_command` only ever wraps `async def` functions (i.e., literal coroutines, not abstract awaitables), `Coroutine[Any, Any, R]` isn't a narrower type than reality — it's a more **accurate** one.
- `filter_by_status`/`sort_tasks`/`paginate`/`get_page` stay synchronous: turning them into `async def` "for consistency" would be typing that doesn't reflect reality (chapter 10) — they wait on nothing, they only transform a list that's already been loaded into memory.
- `append_log` inside `log_command`'s `wrapper` stays a synchronous, blocking call (file I/O with `fcntl.flock` from chapter 06) — technically this blocks the event loop for the duration of the write. For this specific CLI, that's not a problem: the process runs exactly one command at a time, and no other coroutine is "waiting its turn" on the event loop at that moment — there's nothing else to block. In a genuinely concurrent application (a web server, chapter 13+), that same blocking log write would be a real problem, and it would be worth wrapping in `asyncio.to_thread(...)` so it doesn't hold up other requests.
- Tests use `asyncio.run(...)` inside ordinary, synchronous `def test_...():` functions, rather than `pytest-asyncio` — a working, honest way to test async code without adding a dependency; `pytest-asyncio` shows up in chapter 16, once the plain `asyncio.run()` approach becomes genuinely inconvenient for testing a real HTTP server.

## Check yourself

1. What exactly does — and doesn't — the following code print, and why: `coro = some_async_func()` with no subsequent `await`? What happens if the coroutine is simply left un-awaited for the rest of the program?
2. What's the difference between "switching to another thread on a timer" (chapter 11, the GIL) and "switching to another coroutine only at `await`" (this chapter)? Why is the second model closer to how Node works?
3. In the `asyncio.gather` example, one of three coroutines fails with an exception. Why do `A` and `C` still print "done" after the exception has already reached the calling code — shouldn't `gather` have stopped them?
4. How does `asyncio.create_task(coro)` differ from a plain call to `coro = some_async_func()`, in terms of when the coroutine's body actually starts executing?
5. Why did `filter_by_status`/`sort_tasks`/`paginate`/`get_page` deliberately NOT become `async def` in this chapter, even though the rest of the storage layer went fully async?

<details>
<summary>Answers</summary>

1. `coro = some_async_func()` prints nothing at all and runs zero lines of the function's body — calling an `async def` function creates a coroutine object without running it, exactly the way calling a function with `yield` creates a generator object (chapter 07) rather than executing its body. If the coroutine is left un-awaited/un-scheduled for the rest of the program, the interpreter, during garbage collection, notices that a coroutine object was created but never "finished," and emits `RuntimeWarning: coroutine '...' was never awaited` — the body never runs a single line, and the only visible trace is that warning.
2. In the threading model (chapter 11), switching between threads is forced by the interpreter and doesn't ask the code's permission — the GIL is handed to another thread on a timer, regardless of whether the currently running thread is "ready" for that. In the asyncio model, a coroutine only hands control back to the event loop **exactly** where it's explicitly written to — at `await` — and nowhere else; a coroutine that never awaits never voluntarily gives up control on its own. Node works the exact same way: the single thread runs a callback to completion (run-to-completion) and only hands control back when the code itself decides to wait on something asynchronous — in both models, asynchrony is cooperative, not imposed from outside.
3. Because `gather`, by default, doesn't cancel the sibling coroutines when one of them fails — it simply stops waiting for the rest and immediately re-raises the first caught exception to the calling code. `A` and `C` were already scheduled to run at that point (via the internal `Task`s `gather` creates for each argument) and keep living their own life on the event loop regardless of what happens to `gather` — it's just that nobody's around to directly receive their eventual results through `gather`'s return value anymore, since the calling code already got the exception and, most likely, moved on.
4. A plain call `some_async_func()` creates a fully lazy coroutine object — not a single line of the body runs until it's awaited or explicitly scheduled. `asyncio.create_task(coro)`, by contrast, immediately registers the coroutine with the event loop as a task that starts running concurrently **right away**, without waiting for an `await` to reach it — from that point on it "lives" on its own, and a later `await task` merely picks up its result (if it's already ready) or waits until it becomes ready.
5. Because typing (and, more broadly, the code's structure itself) should reflect what a function actually does (chapter 10's theme) — none of these four functions touch a database, a file, or the network: they take an already-loaded `list[Task]` and synchronously filter/sort/paginate it. Marking them `async def` with not a single `await` inside would be a claim — "this function might wait on something" — that doesn't match reality, and the calling code would have to write an unnecessary `await` in front of them for no reason at all.

</details>

## Common mistake

The most common mistake moving from JS to asyncio is forgetting `await` before calling an `async def` function, expecting that (as in JS) the work will "start somehow" in the background anyway. In JS, `someAsyncFn()` with no `await` genuinely does start the Promise immediately — the calling code just doesn't wait for it to finish, and this is often a perfectly workable (if not always deliberate) "fire and forget" pattern. In Python, `some_async_func()` with no `await`/`create_task` does **absolutely nothing** — the function's body doesn't run a single step, the program just carries on as if the call never happened, and the only trace of the mistake is a quiet `RuntimeWarning: coroutine ... was never awaited`, easy to miss in a stream of other output. If what's actually needed is the "start it and don't wait right here" pattern — the right counterpart from this chapter is `asyncio.create_task(coro)`, not a bare coroutine call.

The second common mistake is writing `async def` "just in case" for functions that wait on nothing, out of the reflex "this is an async project now, so everything should be async." As this chapter showed with `filter_by_status`/`sort_tasks`/`paginate`/`get_page`: if a function does zero `await`s inside, wrapping it in `async def` has no practical effect at all (an async function with no await inside still runs entirely synchronously — the only change is that callers now have to `await` it to get the result) — it only adds an unnecessary layer of indirection and misleads the reader into expecting `async def` to mean the function genuinely waits on something external.
