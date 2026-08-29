# asyncio: coroutines, gather, async protocols

## Theory

**`async`/`await` looks like JS syntactically — there's more semantic difference than it seems.** Here is the first and most important difference. In JS, `async function f() { ... }` called without `await` **starts executing immediately**. The Promise is created and the work inside starts right away, and the caller simply doesn't wait for the result.

In Python, `async def f(): ...` called without `await` **does absolutely nothing**:

```python
async def fetch_data():
    print("started")
    return 42

coro = fetch_data()   # nothing printed! coro is just a coroutine object
```

This is exactly the same mechanic as generators from chapter 07. Calling a function with `yield` doesn't run its body, it creates a generator object. Calling an `async def` function doesn't run its body either, it creates a coroutine object.

The body starts executing only when one of three things happens:

- the coroutine is **awaited** (`await coro`);
- it is scheduled as a `Task` (`asyncio.create_task(coro)`);
- it is passed to `asyncio.run(coro)`.

A forgotten `await` isn't a syntax error, it's a silent bug. Python emits `RuntimeWarning: coroutine 'fetch_data' was never awaited`, and the code quietly doesn't do what it was supposed to.

**A cooperative, single-threaded event loop — and why it's closer to Node than anything from chapter 11.** asyncio's event loop is single-threaded, like Node's. That makes it a fundamentally different model from `threading` and the GIL (Global Interpreter Lock) of the previous chapter.

There, switching between threads is forced by the interpreter, on a timer or on a blocking call. Here, a coroutine yields control **exactly where `await` is explicitly written** — nowhere else.

A coroutine that never awaits inside a long loop blocks the **entire** event loop. That is exactly how a heavy synchronous computation blocks Node's single thread. Of everything in this course, `asyncio` is the one place where a JS developer's intuition carries over to Python almost without adjustment. The intuition is: one thread, cooperative switching, blocking code hurts everyone.

**`asyncio.gather` vs `Promise.all` — similar, with two concrete differences.**

```python
results = await asyncio.gather(coro1(), coro2(), coro3())
```

This is the direct counterpart of `Promise.all([p1, p2, p3])`. It waits for all of them to finish and returns a list of results in the same order. The differences show up around exceptions:

1. By default, if even one coroutine raises, `gather` immediately re-raises it to the caller. But **the other coroutines aren't automatically cancelled**. They keep running in the background, and nobody picks up their results through `gather` anymore. This can be checked empirically:

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
        await asyncio.gather(
            worker("A", 0.3), worker("B", 0.1, fail=True), worker("C", 0.5)
        )
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

The exception surfaces right after `B` fails, at 0.1s. But `A` and `C` still print "done" **afterward**. They weren't cancelled, they just finished in the background, with no one left to take their result.

2. `gather(..., return_exceptions=True)` changes the behavior entirely. Instead of raising, the exception is placed into the result list at its slot, alongside the successful results:

```python
results = await asyncio.gather(
    worker("D", 0.1), worker("E", 0.1, fail=True), return_exceptions=True
)
# results == ['D', ValueError('E failed')]
```

This is close in spirit to `Promise.allSettled`: both say "give me every outcome, don't fail on the first one". The result shape differs, though. In JS, `allSettled` returns `{status, value}` and `{status, reason}` objects. In Python, `gather` returns a flat list, and the exception object itself sits where the failed coroutine's result would have been.

**`Task` — how something starts immediately, instead of lazily.** The call `asyncio.create_task(coro)` takes an already-created coroutine and **immediately** schedules it to run on the event loop, without waiting for `await`. From that point on it runs concurrently with the rest of the code:

```python
task = asyncio.create_task(fetch_data())  # already started running
# ... other code ...
result = await task                        # wait for the result (if not already ready)
```

Here's the twist. The closest match for "called an async function in JS" is `create_task`, not a bare coroutine, because `create_task` starts immediately. A bare coroutine in Python is **lazy**, unlike a JS Promise — see the first theory point above.

**Async context managers and async generators — the same protocols from chapters 06/07, just with `await` inside.** The `async with` statement uses `__aenter__`/`__aexit__` instead of `__enter__`/`__exit__`. You need it when acquiring or releasing the resource itself requires an `await` — an async database connection, for instance.

The `async for` statement uses `__aiter__`/`__anext__` instead of `__iter__`/`__next__`. An async generator is `async def` with `yield` inside. That is the same machinery as chapter 07, just with each step potentially awaiting something.

### Parallels with JS/TS/Node:

- A Python coroutine is lazy: it doesn't run until `await` or `create_task`. A JS Promise is eager and starts running as soon as it's created. The closest counterpart of "called an async function and didn't wait for it right away" is `asyncio.create_task`.
- asyncio's single-threaded cooperative event loop is conceptually the same as Node's, unlike `threading` and the GIL of chapter 11. Switching happens only at an explicit `await`, and nothing forces it.
- `asyncio.gather` matches `Promise.all`, but by default it doesn't cancel the sibling coroutines when one of them fails. That is contrary to the fail-fast behavior most people expect. And `return_exceptions=True` is close in spirit to `Promise.allSettled`, but returns a flat list instead of `{status, value/reason}` objects.
- `async with`/`async for` are the same protocols as the context manager (chapter 06) and iterator/generator (chapter 07), just with `await` points inside.

## What we're adding to the project

The storage layer moves from synchronous `sqlite3` to asynchronous `aiosqlite`. That is the project's first real runtime dependency: until now, `dependencies = []` in `pyproject.toml` was empty.

The handlers of the CLI (command-line interface) become `async def`, and the `log_command` decorator learns to wrap async functions. The entry point `main()` stays synchronous, because `pyproject.toml` requires that, and it simply starts the async code via `asyncio.run(...)`.

Importantly, not every function becomes async. `filter_by_status`, `sort_tasks`, `paginate` and `get_page` stay exactly as they are, because they wait on nothing. They are pure, synchronous transformations of an already-loaded list.

## Practical exercise

1. Install `aiosqlite`, add it to `dependencies` in `pyproject.toml` (the project's first real, non-dev dependency).
2. Rewrite `storage/sqlite_storage.py`. Here `db_connection` becomes an `@asynccontextmanager` function with `await aiosqlite.connect(...)`, committing and rolling back via `await conn.commit()` and `await conn.rollback()`. Every one of `init_db`, `add_task`, `find_task`, `get_task`, `mark_done` and `list_tasks` becomes `async def`, with every database call going through `await`. In `list_tasks`, use `async for row in cursor:` instead of `fetchall()` — iterate rows lazily, one at a time.
3. Leave `filter_by_status`, `sort_tasks`, `paginate`, `get_page` **untouched** — think about why that's correct before rewriting them "just in case."
4. Update `TaskStorage` in `storage/protocol.py`. The methods that are actually awaited in the CLI must be declared as `async def method(...) -> ...: ...` in the protocol itself.
5. In `cli/commands.py`, make `handle_add`, `handle_list` and `handle_done` async: `await db.xxx(...)` instead of calling directly. Rewrite `log_command` too. The decorator function itself stays a normal, non-`async` function. The `wrapper` it returns is now `async def` and does `await func(args)` instead of `func(args)`.
6. In `cli/app.py`, split the entry point in two. The first half is `async def async_main()` and holds the real logic: `await db.init_db()`, argument parsing, `await handler(args)`. The second half is `def main() -> None: asyncio.run(async_main())`, and `main` is the one registered in `[project.scripts]`.
7. Leave `append_log` and `FileLock` (chapter 06) synchronous. Then think about this. The `wrapper` inside `log_command` is now async. But `append_log` inside it still writes to a file with a blocking, synchronous call — that is I/O (input and output). Doesn't that block the event loop? In what scenario would that be a real problem, and in what scenario would it not, for this specific CLI?
8. Update `tests/conftest.py`, `tests/test_storage.py` and `tests/test_cli.py` for the async storage layer. Do it without adding `pytest-asyncio`, a separate tool that arrives in chapter 16. Keep the test functions ordinary (`def test_...():`) and wrap the async scenario inside each one in `asyncio.run(...)`.

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

- `log_command` is typed via `Coroutine[Any, Any, R]`, not the more general `Awaitable[R]`. The first, apparently "more generic" attempt with `Awaitable[R]` compiled fine. But `asyncio.run(handle_add(args))` in the tests failed type-checking: `asyncio.run` requires a `Coroutine`, not an arbitrary awaitable object. That wider category also includes things like `Future`. `log_command` only ever wraps `async def` functions, which are literal coroutines, not abstract awaitables. So `Coroutine[Any, Any, R]` is not a narrower type than reality. It is a more **accurate** one.
- `filter_by_status`, `sort_tasks`, `paginate` and `get_page` stay synchronous. Turning them into `async def` "for consistency" would be typing that doesn't reflect reality (chapter 10). They wait on nothing; they only transform a list that has already been loaded into memory.
- `append_log` inside the `wrapper` of `log_command` stays a synchronous, blocking call. That is file I/O with `fcntl.flock` from chapter 06, and it blocks the event loop for the duration of the write. For this specific CLI that is not a problem. The process runs exactly one command at a time. No other coroutine is waiting its turn on the event loop at that moment, so there is nothing else to block. In a genuinely concurrent application — a web server, chapter 13+ — that same blocking log write would be a real problem. There it would be worth wrapping in `asyncio.to_thread(...)`, so that it doesn't delay other requests.
- Tests use `asyncio.run(...)` inside ordinary, synchronous `def test_...():` functions, rather than `pytest-asyncio`. That is a working, honest way to test async code without adding a dependency. The tool `pytest-asyncio` arrives in chapter 16, once the plain `asyncio.run()` approach becomes genuinely inconvenient for testing a real HTTP server.

## Check yourself

1. What exactly does — and doesn't — the following code print, and why: `coro = some_async_func()` with no subsequent `await`? What happens if the coroutine is simply left un-awaited for the rest of the program?
2. What's the difference between "switching to another thread on a timer" (chapter 11, the GIL) and "switching to another coroutine only at `await`" (this chapter)? Why is the second model closer to how Node works?
3. In the `asyncio.gather` example, one of three coroutines fails with an exception. Why do `A` and `C` still print "done" after the exception has already reached the calling code — shouldn't `gather` have stopped them?
4. How does `asyncio.create_task(coro)` differ from a plain call to `coro = some_async_func()`, in terms of when the coroutine's body actually starts executing?
5. Why did `filter_by_status`/`sort_tasks`/`paginate`/`get_page` deliberately **not** become `async def` in this chapter, even though the rest of the storage layer went fully async?

<details>
<summary>Answers</summary>

1. `coro = some_async_func()` prints nothing at all and runs zero lines of the function's body. Calling an `async def` function creates a coroutine object without running it. That is exactly how calling a function with `yield` creates a generator object (chapter 07) rather than executing its body. Now suppose the coroutine is never awaited and never scheduled for the rest of the program. During garbage collection the interpreter notices that a coroutine object was created but never finished, and it emits `RuntimeWarning: coroutine '...' was never awaited`. The body never runs a single line, and the only visible trace is that warning.
2. In the threading model (chapter 11), switching between threads is forced by the interpreter and does not ask the code's permission. The GIL is handed to another thread on a timer, no matter whether the currently running thread is ready for that. In asyncio, a coroutine hands control back to the event loop **exactly** where that is written down — at `await`, and nowhere else. A coroutine that never awaits never gives up control on its own. Node works the exact same way. The single thread runs a callback to completion (run-to-completion) and hands control back only when the code itself decides to wait on something asynchronous. In both models asynchrony is cooperative, not imposed from outside.
3. Because `gather` by default doesn't cancel the sibling coroutines when one of them fails. It simply stops waiting for the rest and immediately re-raises the first caught exception to the calling code. `A` and `C` were already scheduled to run at that point, through the internal `Task` objects that `gather` creates for each argument. They keep running on the event loop regardless of what happens to `gather`. It is just that nobody is around to receive their results through the return value of `gather` anymore. The calling code already got the exception and most likely moved on.
4. A plain call `some_async_func()` creates a fully lazy coroutine object. Not a single line of the body runs until it is awaited or explicitly scheduled. The call `asyncio.create_task(coro)`, by contrast, immediately registers the coroutine with the event loop as a task. That task starts running concurrently **right away**, without waiting for an `await` to reach it. From that point on it lives on its own. A later `await task` merely picks up its result if it is already ready, or waits until it becomes ready.
5. Because typing, and more broadly the structure of the code itself, should reflect what a function actually does. That is the theme of chapter 10. None of these four functions touch a database, a file, or the network. They take an already-loaded `list[Task]` and synchronously filter, sort or paginate it. Marking them `async def` with not a single `await` inside would claim that the function might wait on something. That claim doesn't match reality. The calling code would also have to write an unnecessary `await` in front of them for no reason at all.

</details>

## Common mistake

The most common mistake moving from JS to asyncio is forgetting `await` before calling an `async def` function. The expectation is that, as in JS, the work will "start somehow" in the background anyway.

In JS, `someAsyncFn()` with no `await` genuinely does start the Promise immediately. The calling code just doesn't wait for it to finish. That is often a perfectly workable, if not always deliberate, "fire and forget" pattern.

In Python, `some_async_func()` with no `await` and no `create_task` does **absolutely nothing**. The function's body doesn't run a single step, and the program carries on as if the call never happened. The only trace of the mistake is a quiet `RuntimeWarning: coroutine ... was never awaited`, easy to miss in a stream of other output.

Do you actually need the "start it and don't wait right here" pattern? The right counterpart from this chapter is `asyncio.create_task(coro)`, not a bare coroutine call.

The second common mistake is writing `async def` "just in case" for functions that wait on nothing. The reflex behind it: this is an async project now, so everything should be async.

This chapter showed the opposite with `filter_by_status`, `sort_tasks`, `paginate` and `get_page`. If a function does zero `await`s inside, wrapping it in `async def` has no practical effect at all. An async function with no `await` inside still runs entirely synchronously. The only change is that callers now have to `await` it to get the result.

So the wrapper only adds an unnecessary layer of indirection. Worse, it misleads the reader, who expects `async def` to mean that the function genuinely waits on something external.
