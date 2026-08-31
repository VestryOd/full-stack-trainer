# Testing with pytest

## Theory

**Plain `assert` — no assertion library needed.** pytest doesn't need `expect(x).toBe(y)` or `self.assertEqual(a, b)` — you write an ordinary Python `assert`:

```python
def test_add():
    assert 2 + 2 == 4

def test_lists_match():
    assert [1, 2, 3] == [1, 2, 4]
    # on failure, pytest shows exactly which element the lists diverged at --
    # not just "AssertionError," a detailed diff
```

This isn't because `assert` in Python is inherently that smart. A plain `assert a == b` without pytest shows nothing but `AssertionError` on failure, with zero detail.

pytest hooks into the import process of the test file and **rewrites the AST** (abstract syntax tree) of test modules. It inserts code that captures intermediate subexpression values for the failure report. That is where the detailed output on a bare `assert` failure comes from.

This is exactly why `unittest` — built into the stdlib, but less popular than pytest — needs `self.assertEqual(...)`, and Jest needs `expect().toBe()`. Both are forced to wrap comparisons in a special call, precisely because neither rewrites the AST on the fly the way pytest does.

**Test discovery.** pytest automatically finds `test_*.py`/`*_test.py` files, `test_*` functions and `Test*` classes. The common case needs no configuration at all, exactly like Jest finding `*.test.js`/`*.spec.js` on its own.

**Fixtures.** `@pytest.fixture` — a function whose result a test function requests **by parameter name**:

```python
import pytest

@pytest.fixture
def sample_list():
    print("setup")
    yield [1, 2, 3]
    print("teardown")

def test_uses_fixture(sample_list):
    assert len(sample_list) == 3
```

`yield` inside a fixture function splits it into "before" (setup) and "after" (teardown). This is literally the same generator pattern as `@contextmanager` from chapters 06 and 08:

- The code before `yield` runs before the test.
- The value after `yield` is handed to the test as a parameter.
- The code after `yield` runs after the test, **whether it passed or failed**.

This is the third use of the same generator idiom across the course, after context managers (chapter 06) and paginated output (chapter 07).

The fundamental difference from Jest is this. In Jest, `beforeEach`/`afterEach` are global hooks, implicitly applied to every test in the enclosing `describe` block. In pytest, a fixture is requested **explicitly**, only by the test that names it as a parameter. Nothing runs "by default" for every test at once.

Fixtures can also request other fixtures, forming a dependency graph much like a dependency injection (DI) container. And they have a configurable scope. The default is `function`: a fresh instance per test. With `module` or `session` the same instance is reused across a whole file, or a whole run.

**`@pytest.mark.parametrize`.** One test, many sets of input data — each becomes a separately reported test case:

```python
@pytest.mark.parametrize("a, b, expected", [
    (1, 2, 3),
    (2, 2, 4),
    (-1, 1, 0),
])
def test_add_pairs(a, b, expected):
    assert a + b == expected
```

The direct counterpart is `test.each([[1, 2, 3], [2, 2, 4]])(...)` in Jest.

**mock and monkeypatch — two different tools, two different jobs.** `unittest.mock` (also stdlib) gives you `Mock`, `MagicMock` and `patch`. They replace a collaborator with a fake object that remembers how it was called and lets you assert on that: `mock.assert_called_once_with(...)`. That is close in spirit to `jest.fn()`/`jest.mock()`.

The `monkeypatch` fixture is a separate thing, built into pytest and not part of `unittest.mock`. It safely and **temporarily overrides state**: a module attribute, an environment variable, a dict entry, `sys.path`. The change is reverted automatically after the test, whether it passed or failed:

```python
def test_uses_monkeypatch(monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setattr(some_module, "CONFIG_VALUE", "test")
    # both changes are automatically reverted after this test
```

The difference is one of emphasis. `Mock`/`patch` answers "what was called, and with what". `monkeypatch` answers "swap this out cleanly, and guarantee it goes back".

**Comparison with Jest.** The two are structurally similar: both ecosystems support setup and teardown, mocking, parametrized tests and readable failure messages. They differ in syntax. pytest gives you free functions, a bare `assert`, and fixtures as function parameters. Jest gives you `describe`/`it`/`test` blocks, `expect().toBe()` chains, and implicit global hooks.

pytest has no equally central counterpart to `describe` for grouping. `TestSomething` classes do exist, but the idiomatic way to structure a test suite is plain functions plus fixtures plus `parametrize`, not nested blocks.

### Parallels with JS/TS/Node:

- pytest gets detailed failure messages from a bare `assert` by rewriting the AST at import time. Jest and `unittest` instead require special comparison methods: `expect().toBe()`, `self.assertEqual()`.
- Fixtures in pytest are explicit, requested by parameter name, and can depend on each other. In Jest, `beforeEach`/`afterEach` are implicit, applied automatically to every test in scope.
- `@pytest.mark.parametrize` ~ `test.each(...)` — a direct counterpart.
- `monkeypatch` is about safely, guaranteed-revertibly overriding state; `unittest.mock`/`jest.fn()` is about a fake object with call introspection. Different jobs, often used together.

## What we're adding to the project

We're adding `pytest` as a dev dependency and writing tests for two layers. One is the storage layer (`storage/sqlite_storage.py`). The other is the set of CLI (command-line interface) handlers in `cli/commands.py`.

The key technical wrinkle is the database. Tests need to run against an **in-memory SQLite database**, not the real `taskman.db` file. But naively setting `DB_PATH = ":memory:"` won't work. Our `db_connection()` opens a new connection on every call, and every fresh `sqlite3.connect(":memory:")` is a separate, unrelated, empty database.

The fix is `monkeypatch`. We replace the `db_connection` function itself with a fixture version that always hands back the same, already-open connection.

Along the way, trying to test the error message in `handle_done` turns up a real bug in chapter 07's code. The function `print_err` was built with `functools.partial(print, file=sys.stderr)`, so it binds the `sys.stderr` object **once**, at creation time. Meanwhile `capsys`, pytest's fixture for capturing output, swaps `sys.stderr` for a new object only for the duration of the test.

So `print_err` keeps writing to the old, no-longer-intercepted `sys.stderr`. We fix it by replacing `partial` with a small function that reads `sys.stderr` fresh on every call.

## Practical exercise

1. Add `[project.optional-dependencies] dev = ["pytest>=8"]` to `pyproject.toml`, install with `pip install -e ".[dev]"`.
2. Create `tests/conftest.py` with a `db` fixture. It should do four things:
    - Open one `sqlite3.connect(":memory:")` connection.
    - Use `monkeypatch.setattr` to replace `sqlite_storage.db_connection` with a context-manager function that always hands back **this same** connection: commit on success, rollback on exception.
    - Call `sqlite_storage.init_db()`, then yield the module.
    - Close the connection during teardown.
3. Before reading the worked solution, think about it: why won't simply setting `DB_PATH = ":memory:"` work, given that `db_connection()` opens a new connection on every call?
4. Write `tests/test_storage.py` covering `add_task` (incrementing ids, default priority), `find_task`/`get_task` (found, missing, exception) and `mark_done` (persists, raises on a missing task). Cover `list_tasks` too, and `filter_by_status` via `@pytest.mark.parametrize`. Add a test for `sort_tasks` that does **not** use the `db` fixture at all — build `Task` objects by hand and confirm the test still passes.
5. Write `tests/test_cli.py`: call handlers (`handle_add`, `handle_list`, `handle_done`) directly with a hand-built `argparse.Namespace`, checking output via `capsys.readouterr()`. Replace `append_log` with a no-op via `monkeypatch` so tests don't write to a real `taskman.log` on disk.

A separate thing to think through. The test for the error message of `handle_done` may unexpectedly fail on `assert "not found" in err`. Meanwhile pytest's own failure report (`Captured stderr call`) clearly shows that the error text was printed.

Don't just swap `capsys` for capfd as a quick fix. That sibling fixture captures at the file-descriptor level, one layer below Python's `sys.stderr`. Work out what is actually going on here, looking closely at how `print_err` was defined back in chapter 07.

## Worked solution

`pyproject.toml` (dev-dependencies section added, everything else unchanged):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

`tests/conftest.py` (new file):

```python
import sqlite3
from contextlib import contextmanager

import pytest

from taskman.storage import sqlite_storage


@pytest.fixture
def db(monkeypatch):
    """Point taskman's storage layer at one shared in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def fake_db_connection():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)
    sqlite_storage.init_db()
    yield sqlite_storage
    conn.close()
```

`tests/test_storage.py` (new file):

```python
import pytest

from taskman.models import Priority, Task, TaskNotFoundError
from taskman.storage.sqlite_storage import sort_tasks


def test_add_task_assigns_incrementing_ids(db):
    first = db.add_task("Buy milk")
    second = db.add_task("Write report")
    assert first.id == 1
    assert second.id == 2


def test_add_task_defaults_to_medium_priority(db):
    task = db.add_task("Buy milk")
    assert task.priority == Priority.MEDIUM
    assert task.done is False


def test_find_task_returns_none_when_missing(db):
    assert db.find_task(999) is None


def test_get_task_raises_when_missing(db):
    with pytest.raises(TaskNotFoundError):
        db.get_task(999)


def test_mark_done_persists_across_reads(db):
    task = db.add_task("Buy milk")
    db.mark_done(task.id)
    reloaded = db.get_task(task.id)
    assert reloaded.done is True


def test_mark_done_raises_for_missing_task(db):
    with pytest.raises(TaskNotFoundError):
        db.mark_done(999)


def test_list_tasks_returns_everything_added(db):
    db.add_task("A")
    db.add_task("B")
    assert [t.text for t in db.list_tasks()] == ["A", "B"]


@pytest.mark.parametrize(
    "status, expected_texts",
    [
        ("all", ["A", "B"]),
        ("done", ["A"]),
        ("pending", ["B"]),
    ],
)
def test_filter_by_status(db, status, expected_texts):
    a = db.add_task("A")
    db.add_task("B")
    db.mark_done(a.id)

    result = db.filter_by_status(db.list_tasks(), status)
    assert [t.text for t in result] == expected_texts


def test_sort_tasks_by_priority_orders_high_first():
    # a pure function -- the db fixture isn't needed at all
    low = Task(id=1, text="low", priority=Priority.LOW)
    high = Task(id=2, text="high", priority=Priority.HIGH)

    result = sort_tasks([low, high], "priority")
    assert result == [high, low]
```

`tests/test_cli.py` (new file):

```python
import argparse

from taskman.cli import commands


def make_args(**kwargs):
    return argparse.Namespace(**kwargs)


def test_handle_add_prints_confirmation(db, capsys, monkeypatch):
    monkeypatch.setattr(commands, "append_log", lambda message: None)
    args = make_args(command="add", text="Buy milk", priority="high")

    commands.handle_add(args)

    out = capsys.readouterr().out
    assert "Added:" in out
    assert "Buy milk" in out


def test_handle_done_reports_missing_task(db, capsys, monkeypatch):
    monkeypatch.setattr(commands, "append_log", lambda message: None)
    args = make_args(command="done", id=999)

    commands.handle_done(args)

    err = capsys.readouterr().err
    assert "not found" in err


def test_handle_list_shows_added_tasks(db, capsys, monkeypatch):
    monkeypatch.setattr(commands, "append_log", lambda message: None)
    db.add_task("Buy milk")

    args = make_args(command="list", status="all", sort="id", page=1, page_size=5)
    commands.handle_list(args)

    out = capsys.readouterr().out
    assert "Buy milk" in out
```

`src/taskman/cli/commands.py` (the only change is `print_err`; everything else is unchanged from chapter 08):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db


def print_err(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print_err(f"[log] running: {namespace.command}")
        append_log(f"running: {namespace.command}")
        result = func(*args, **kwargs)
        print_err(f"[log] done: {namespace.command}")
        append_log(f"done: {namespace.command}")
        return result

    return wrapper


@log_command
def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = db.add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = db.sort_tasks(db.filter_by_status(db.list_tasks(), args.status), args.sort)
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
def handle_done(args: argparse.Namespace) -> None:
    try:
        task = db.mark_done(args.id)
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

Key decisions:

- The `db` fixture doesn't replace the database path — it replaces the `db_connection` function itself. That's the only way to let a `":memory:"` database survive multiple storage-function calls within one test, given that each of them opens its own connection.
- `test_sort_tasks_by_priority_orders_high_first` doesn't request the `db` fixture. Pure functions, with no database access, need no test infrastructure at all — just input and expected output.
- `monkeypatch.setattr(commands, "append_log", lambda message: None)` appears in the CLI tests. Tests shouldn't have side effects such as writing to a file on disk. So `append_log` is swapped for a no-op, since logging isn't what these particular tests are checking.
- `print_err` is a small function instead of `functools.partial(print, file=sys.stderr)`. It reads `sys.stderr` fresh on every call, rather than once at creation time. That fixes testability via `capsys`. It also brings a less visible benefit: correctness in any scenario where `sys.stderr` is legitimately redirected while the program runs, not just in tests.

## Check yourself

1. Why do two back-to-back calls to `sqlite3.connect(":memory:")` in the same process produce two completely independent, unrelated databases? And how exactly does that break a naive `DB_PATH = ":memory:"`, given that `db_connection()` opens a new connection per call?
2. What exactly does the `db` fixture in `conftest.py` replace? Patching the `db_connection` function itself is the only way to let several storage-function calls in one test see the same data. Why is patching just `DB_PATH` not enough?
3. Why did `capsys.readouterr()` return an empty string for `err`? The very same error text is clearly visible in pytest's own failure report (`Captured stderr call`). What does this tell you about `print_err = functools.partial(print, file=sys.stderr)`, compared with a function that reads `sys.stderr` fresh on every call?
4. What's the difference in purpose between `unittest.mock` (`Mock`/`patch`) and pytest's `monkeypatch` fixture? When is it more natural to reach for one over the other?
5. Why doesn't `test_sort_tasks_by_priority_orders_high_first` need the `db` fixture at all, when every other test in `test_storage.py` does? What property of `sort_tasks` specifically makes this possible?

<details>
<summary>Answers</summary>

1. `sqlite3.connect(":memory:")` creates a new, private database. It exists exactly as long as that specific connection object does, and it is tied to nothing but itself. It is not a named, shared resource the way a file path is. Two separate calls to `connect(":memory:")` in the same process produce two fully independent databases, neither able to see the other's data. Our `db_connection()` opens a **new** connection on every call to any storage function — `add_task`, `find_task` and so on. For a file path that is fine: any connection to the same file sees the same data on disk. For `":memory:"` it is fatal. The connection opened inside `init_db()` creates the `tasks` table in its own throwaway in-memory database. The very next call, say `add_task`, opens a **different**, brand-new, empty database with no table at all. It fails immediately: `sqlite3.OperationalError: no such table: tasks`.
2. The `db` fixture doesn't just point the database path somewhere else. It replaces the entire `db_connection` context-manager function with a fake version. That fake **always** hands back the same, already-open connection, captured once before the test runs, no matter how many times it is called. This entirely sidesteps the "every connection is a separate database" problem for `:memory:`. Every storage operation during the test goes through the same fake `db_connection` and gets back the same connection object. So the contents of the in-memory database stay consistent across `add_task` and `list_tasks` calls within one test. Several real connections to the same file would behave the same way.
3. `functools.partial(print, file=sys.stderr)` evaluates `sys.stderr` **once**, at the moment the `partial` object itself is created, which is module import time. It permanently stores that specific object as the `file` keyword argument for every future call. The `capsys` fixture of pytest works by **replacing** `sys.stderr` for the duration of the test. It rebinds the name `sys.stderr` to a new interceptor object. But the `partial` object was created before that. It still holds a reference to the **old** `sys.stderr` object it captured at import time, and it keeps writing there. Rebinding the name afterward has no effect on it. A small wrapper function behaves differently. It looks up `sys.stderr` fresh, by name, on every call: `def print_err(*args, **kwargs): print(*args, file=sys.stderr, **kwargs)`. So it sees whatever `capsys` currently has `sys.stderr` rebound to.
4. `unittest.mock` (`Mock`/`patch`) is about replacing a collaborator with a fake object. That object remembers how it was called and lets you assert on it: `mock.assert_called_once_with(...)`. The emphasis is on the mock object itself and on call introspection. The `monkeypatch` fixture is about safely and temporarily overriding **state**: an attribute, an environment variable, a dict entry. The change is reverted automatically after the test, whatever the outcome. The emphasis is not on recording calls. What matters is swapping something cleanly and guaranteeing it gets put back. So `monkeypatch` is the natural fit when you need to temporarily swap out configuration or an implementation detail. We did exactly that here with `db_connection` and `append_log`. `Mock`/`patch` is the fit when you specifically need to verify how, and how many times, something was called.
5. `sort_tasks` is a pure function. Given the same inputs — a list of `Task` objects and a `sort_by` string — it always returns the same result. It reads and mutates no external state: no database, no file, no global variable, and no side effects. Building `Task` objects directly through the dataclass constructor and calling `sort_tasks` on them tests the function entirely on its own terms. There is nothing to set up and nothing to tear down, because no shared, mutable resource is involved at all. The `db` fixture is only needed by tests that read from or write to the database.

</details>

## Common mistake

The most instructive mistake in this chapter isn't hypothetical. It actually happened while writing these tests. The assumption was that `capsys`, or any output-capturing fixture, is guaranteed to see **everything** printed anywhere in the code during a test. How that code built its `print` call was assumed not to matter.

`print_err`, built in chapter 07 with `functools.partial(print, file=sys.stderr)`, quietly violates that assumption. It binds a specific `sys.stderr` object once, at creation time, instead of reading it fresh on every call. So the substitution of `sys.stderr` by `capsys` is simply invisible to it.

The test then fails even though pytest's own report shows the output with your own eyes. The right response is not to shrug and switch to file-descriptor capture with `capfd` as a workaround. It is to figure out why this specific code doesn't respect the `sys.stderr` substitution at all. Usually, as here, the reason is that an object — not a name — got captured too early.

The second common mistake is assuming that changing `DB_PATH` to `":memory:"` in a test environment will just work. In-memory SQLite, after all, is the simplest storage option there is. It works with no caveats only when the same connection is reused for the whole test.

Our storage layer, from chapter 08, opens a new connection on every call. With a layer like that you need an extra step to make several calls "see" the same in-memory database. A naive one-line config swap is not enough.
