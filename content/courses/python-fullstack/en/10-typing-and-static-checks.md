# Typing and static checks

## Theory

**Type hints check nothing at runtime — and that makes Python closer to TS than it looks.** Type annotations in Python are pure metadata; the interpreter doesn't enforce them:

```python
def add(a: int, b: int) -> int:
    return a + b

add("2", "2")  # runs with no error at all and returns "22" -- the hints aren't checked
```

That sounds like "the typing isn't real" compared to TS. The underlying model is nearly identical, though. TypeScript also erases types completely when it compiles to JS. The compiler `tsc` is a separate step, and types no longer exist at the moment the compiled code runs.

So the difference isn't "Python doesn't check, TS does" — both erase types at runtime. The difference is **when and how mandatory** the check is. In TS, `tsc` is usually baked directly into the build: skip it and the project simply won't build. In Python, `mypy` is a separate, optional step you have to run deliberately. It is also far more lenient by default, and we come back to that below.

**Optional/Union.** `Optional[X]` is exactly `Union[X, None]`. The modern syntax writes `X | None` and `A | B` instead of `Optional[X]` and `Union[A, B]`. It arrived in Python 3.10 through PEP 604 (Python Enhancement Proposal — the numbered documents in which changes to the language are designed). This course uses it throughout.

The old syntax (`typing.Optional`, `typing.Union`) is still needed in two cases only. One is code that must run on Python below 3.10. The other is a codebase that hasn't migrated off it yet.

**TypedDict — typing a dict with a known shape.** The direct counterpart of a TS interface, specifically for the case "this is a `dict` with a fixed set of keys," not an arbitrary class:

```python
from typing import TypedDict

class TaskDict(TypedDict):
    id: int
    text: str
    priority: str
    done: bool

def load_from_json(raw: list[TaskDict]) -> list[Task]:
    return [
        Task(
            id=t["id"],
            text=t["text"],
            priority=Priority[t["priority"].upper()],
            done=t["done"],
        )
        for t in raw
    ]
```

Important: `TypedDict` is a **purely static** construct, like everything else in this chapter. At runtime a `TaskDict` is just a plain `dict`. Nothing checks that it actually has all the required keys with the right types. Only `mypy` statically confirms that code working with a `TaskDict` treats it consistently.

Chapter 13 introduces Pydantic models. They look similar, but unlike `TypedDict` they **actually validate data at runtime**. That is a fundamental difference, and we come back to it.

Where does `TypedDict` fit in this course? Since chapter 04, `Task` in this project has deliberately been a dataclass, not a dict. That choice gives us `__eq__`, `__lt__` and validation via `__post_init__` for free.

So there is no natural spot for `TypedDict` inside `taskman` itself. The optional chapter 08 exercise is a different matter. Its JSON-file version, `storage/json_file.py`, really did work with `list[dict]`-shaped data before converting it into `Task` objects. If you kept that file, `TaskDict` is exactly the place to apply this chapter in practice.

**Protocol — the structural typing promised in chapter 04.** Chapter 4 covered `ABC` as **nominal** typing: a class must explicitly inherit, or it doesn't count as a subtype, even with identically matching methods. `Protocol` is the direct structural counterpart of TS's `interface`. An object satisfies the protocol if it has the right methods with the right signatures, **with no explicit inheritance at all**:

```python
from typing import Protocol

class TaskStorage(Protocol):
    def add_task(self, text: str, priority: Priority = ...) -> Task: ...
    def find_task(self, task_id: int) -> Task | None: ...
    def list_tasks(self) -> list[Task]: ...
```

Any object with `add_task`, `find_task` and `list_tasks` methods of the right shape satisfies `TaskStorage`. Nowhere does it have to say `class X(TaskStorage):`. In the project we will see that even a **module** qualifies, because a module is also just an object with attributes.

That's exactly the difference between "ABC — a commitment declared up front" and "Protocol — a shape verified after the fact."

**Generics (TypeVar).** A function that works with any type, but ties its input and output to the same specific type on each individual call:

```python
from typing import TypeVar

T = TypeVar("T")

def first(items: list[T]) -> T:
    return items[0]

first([1, 2, 3])        # T = int, returns an int
first(["a", "b"])        # T = str, returns a str
```

This is a direct counterpart of `function first<T>(items: T[]): T` in TS. The idea itself isn't new; only the declaration syntax differs.

Python 3.12+ introduced a modern syntax, PEP 695: `def first[T](items: list[T]) -> T:`. There is no separate `T = TypeVar("T")` declaration, which is noticeably closer to TS's own `<T>`. This course targets 3.11+, so we use the classic explicit `TypeVar` form throughout. It is still worth knowing the alternative exists on newer versions.

**`ParamSpec` — a specialized generic for decorators.** A separate tool for the specific case "write a decorator that preserves the **exact** signature of whatever it wraps":

```python
from typing import Callable, ParamSpec, TypeVar
import functools

P = ParamSpec("P")
R = TypeVar("R")

def shout(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)
    return wrapper
```

This is a legitimate, genuinely useful tool. As the worked solution below shows, though, it only belongs in a decorator that *genuinely* knows nothing about the contents of its arguments. Our own `log_command` from chapter 03 turns out not to fit that description, and `mypy` is exactly what caught it.

**mypy and "gradual typing".** mypy checks types statically, in a separate run (`mypy src/`), not as part of executing the code.

By default mypy is **lenient**. A function with zero type annotations isn't strictly checked at all: inside it, mypy treats every value as having an unknown type that accepts anything. This is fundamentally different from TS, where even a `.ts` file with no explicit annotations gets meaningful checking from `tsc`'s type inference.

To get Python checking comparable to an ordinary `.ts` file, turn on `strict = true` in the config (`[tool.mypy]` in `pyproject.toml`). That one line flips on a whole bundle of flags at once — `disallow_untyped_defs`, `warn_return_any` and others — and together they require annotating essentially everything.

This is the deliberate "gradual typing" trade-off. You can type a project incrementally, file by file, without turning on strictness for everything at once. But if you want TS-like rigor, you have to ask for it explicitly instead of getting it by default.

### Parallels with JS/TS/Node:

- Python's and TS's type-erasure models are actually quite similar: neither checks anything at runtime on its own. The difference is that `tsc` is usually mandatory for a build, while `mypy` is a separate, optional step.
- `TypedDict` is the counterpart of a TS `interface`, specifically for dict-shaped data. Unlike the Pydantic models of chapter 13 (and, to some extent, JS runtime validators like zod), `TypedDict` checks nothing at runtime at all.
- `Protocol` is structural typing, the direct counterpart of `interface` in TS (shape-based compatibility); `ABC` from chapter 04 is nominal (compatibility via explicit inheritance).
- `TypeVar` and generics are the same idea as `<T>` in TS, just a different declaration syntax. PEP 695 (Python 3.12+) brings the syntax noticeably closer to TS's own.
- mypy by default is considerably more lenient than `tsc`'s default — strictness has to be turned on explicitly (`strict = true`), not received for free.

## What we're adding to the project

This chapter adds five things:

- Full typing for the storage layer and the models.
- `mypy` as a dev dependency, with a strict config (`strict = true`).
- Generic `paginate` and `get_page` via `TypeVar`. They were never really specific to `Task` to begin with.
- A `Protocol TaskStorage` describing the shape of the storage layer — the promise from chapter 04, finally delivered on.
- A stub for CI (continuous integration): a minimal workflow file that really runs `mypy` and `pytest` on the server after every push.

Along the way `mypy --strict` turns up several genuine typing gaps left over from earlier chapters. We fix them as we go, with no invented examples needed.

## Practical exercise

1. Add `mypy` to `[project.optional-dependencies] dev` in `pyproject.toml`, add a `[tool.mypy]` section with `python_version = "3.11"` and `strict = true`.
2. Run `mypy src` against the current state of the project (chapters 06–09). Look at the real list of errors, and don't guess ahead of time what will be in it.
3. Add the return type `Iterator[sqlite3.Connection]` to `db_connection`.
4. Genericize `paginate`/`get_page` in `storage/sqlite_storage.py` via `TypeVar` — they take/return `list[Task]`, but their logic never touches anything specific to `Task`'s fields.
5. Create `storage/protocol.py` with `class TaskStorage(Protocol)`, listing the methods that `cli/` actually uses. Check both `cli/commands.py` and `cli/app.py` so you don't miss any. In `storage/__init__.py`, add the annotation `db: TaskStorage = sqlite_storage`.
6. Get to `cli/commands.py` and see what mypy says about `log_command`. Before fixing anything, think about it. The decorator `log_command` was written in chapter 03 with `*args, **kwargs` for one stated reason: not to depend on the wrapped function's exact signature. Is that still true once you look inside `wrapper`?
7. Add `.github/workflows/ci.yml`, a minimal workflow file. It installs the project with `pip install -e ".[dev]"`, then runs `mypy src` and `pytest` on every push and pull request.
8. Get `mypy src tests` down to zero errors. For the test code, add a `[[tool.mypy.overrides]]` section with relaxed requirements: tests don't need to be typed as strictly as application code.

## Worked solution

`pyproject.toml` (added the `mypy` dev dependency and a `[tool.mypy]` section):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

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

`src/taskman/logging_utils.py` (updated — `mypy --strict` flagged an untyped `self._file`):

```python
import fcntl
from pathlib import Path
from typing import IO, Optional

LOG_PATH = Path("taskman.log")


class FileLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: Optional[IO[str]] = None

    def __enter__(self) -> IO[str]:
        self._file = open(self._path, "a")
        fcntl.flock(self._file, fcntl.LOCK_EX)
        return self._file

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        assert self._file is not None
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()


def append_log(message: str) -> None:
    with FileLock(LOG_PATH) as log_file:
        log_file.write(message + "\n")
```

`src/taskman/storage/sqlite_storage.py` (updated — types on `db_connection`, `paginate`/`get_page` genericized, `assert` on `lastrowid`):

```python
import itertools
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TypeVar

from ..models import Priority, Task, TaskNotFoundError

DB_PATH = Path("taskman.db")

T = TypeVar("T")


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                priority INTEGER NOT NULL,
                done INTEGER NOT NULL
            )
            """
        )


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        text=row["text"],
        priority=Priority(row["priority"]),
        done=bool(row["done"]),
    )


def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    return Task(id=task_id, text=text, priority=priority, done=False)


def find_task(task_id: int) -> Task | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def get_task(task_id: int) -> Task:
    task = find_task(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


def mark_done(task_id: int) -> Task:
    task = get_task(task_id)
    with db_connection() as conn:
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    task.done = True
    return task


def list_tasks() -> list[Task]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    return [_row_to_task(row) for row in rows]


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

`src/taskman/storage/protocol.py` (new file):

```python
from typing import Protocol

from ..models import Priority, Task


class TaskStorage(Protocol):
    def init_db(self) -> None: ...
    def add_task(self, text: str, priority: Priority = ...) -> Task: ...
    def find_task(self, task_id: int) -> Task | None: ...
    def get_task(self, task_id: int) -> Task: ...
    def mark_done(self, task_id: int) -> Task: ...
    def list_tasks(self) -> list[Task]: ...
    def filter_by_status(self, items: list[Task], status: str) -> list[Task]: ...
    def sort_tasks(self, items: list[Task], sort_by: str) -> list[Task]: ...
    def get_page(self, items: list[Task], page: int, page_size: int) -> list[Task]: ...
```

`src/taskman/storage/__init__.py` (updated):

```python
from . import sqlite_storage
from .protocol import TaskStorage

db: TaskStorage = sqlite_storage

__all__ = ["db", "TaskStorage"]
```

`src/taskman/cli/commands.py` (updated — `print_err` and `log_command` are now typed; `log_command`'s signature changed, see below):

```python
import argparse
import functools
import sys
from typing import Any, Callable, TypeVar

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db

R = TypeVar("R")


def print_err(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def log_command(
    func: Callable[[argparse.Namespace], R],
) -> Callable[[argparse.Namespace], R]:
    @functools.wraps(func)
    def wrapper(args: argparse.Namespace) -> R:
        print_err(f"[log] running: {args.command}")
        append_log(f"running: {args.command}")
        result = func(args)
        print_err(f"[log] done: {args.command}")
        append_log(f"done: {args.command}")
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

`.github/workflows/ci.yml` (new file — a CI stub):

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: mypy src
      - run: pytest
```

Key decisions — and what `mypy --strict` actually found:

- **`paginate`/`get_page` became generic (`TypeVar("T")`) with zero changes to the function bodies.** That's a clean signal that their `Task`-specificity was accidental to begin with. The code never touched any `Task` field; it only ever collected items into lists. Side benefit: these functions are now reusable for paginating anything, not just tasks.

- **`log_command` had to be retyped concretely, not via `ParamSpec`.** The first attempt was to type the decorator as generically as possible, via `Callable[P, R]`/`P.args`/`P.kwargs`, exactly like the theory example. Running `mypy --strict` flagged it immediately. With `*args: P.args`, `args[0]` has type `object`, and `object` has no attribute `.command`.

  That's not a mypy shortcoming. mypy is honestly saying that you contradict yourself. You claim the decorator knows nothing about the wrapped function's signature, yet the code inside `wrapper` reads `.command` off the first argument. So it **does** know the argument is an `argparse.Namespace`.

  The `*args, **kwargs` in `log_command` since chapter 03 were never really about polymorphism. They were about not hardcoding a parameter name, while the function itself always assumed exactly one argument of a specific shape. The honest typing is `Callable[[argparse.Namespace], R] -> Callable[[argparse.Namespace], R]`. That is not a narrower claim than before, it is a more **truthful** one.

- **`cursor.lastrowid` is typed in the `sqlite3` stubs as `int | None`**, because in general `lastrowid` can be `None` (if the last operation wasn't an `INSERT`). Right after an `INSERT` we know for certain that's impossible. The line `assert task_id is not None` encodes that knowledge explicitly, both for mypy (which narrows the type to `int`) and for the reader.

- **`FileLock._file`** was implicitly typed as `None`, because `__init__` is its only assignment site. Two changes fix that: an explicit `Optional[IO[str]]` annotation, and `assert self._file is not None` in `__exit__`. Together they tell mypy and a human reader the same thing. By the time `__exit__` runs, the file is guaranteed open, because `__enter__` always runs first.

- **Tests get their own, more relaxed mypy profile** (`[[tool.mypy.overrides]] module = "tests.*"`). Demanding full type annotations on every test function and fixture costs more in test readability than it returns. Turning off `disallow_untyped_defs` and `disallow_untyped_calls` for `tests.*` keeps the strictness where it is worth most, in application code. Test code is not punished for being less formal.

## Check yourself

1. Why doesn't `add("2", "2")` from the first theory example raise or crash, even though both arguments are annotated as `int`? What exactly does — and doesn't — the type hint in that signature check?
2. What's the difference between `TypedDict` and `Protocol`, if both are about "the shape of data"? What kind of data is each more naturally suited to?
3. The line `db: TaskStorage = sqlite_storage` works, but nowhere in `sqlite_storage.py` does it say anything like "this module implements `TaskStorage`". How does mypy check this line at all? And what happens if you remove one method from `TaskStorage`, say `get_page`?
4. The first attempt at typing `log_command` via `ParamSpec`/`Callable[P, R]` produced an error on `namespace.command` inside `wrapper`. Why does `P.args` give mypy no information about the type of `args[0]`? Explain in your own words why that is a deliberate limitation, not a shortcoming of `ParamSpec`.
5. What does "mypy is gradual typing by default" mean, and what exactly does the `strict = true` flag change? Why doesn't a function with zero type annotations trigger mypy errors by default, even if it contains obvious, type-related logic errors inside?

<details>
<summary>Answers</summary>

1. Type hints in Python don't participate in code execution at all. The interpreter reads them and stores them in the function's `__annotations__`, but never checks that call arguments actually match. The `int` in the signature is a statement of intent for the reader and a hint for an external tool like mypy. It is not a runtime contract that Python itself enforces. Checking happens only if you **specifically run** it: statically, via `mypy`, separately from running the program.
2. `TypedDict` describes the shape of a value that physically remains an ordinary `dict` at runtime. That is a natural fit for JSON-like data with no dedicated class. Think of configs, external API responses, and "raw" data before it is turned into something more structured. `Protocol` describes the shape of **behavior**: what methods an object must have, regardless of its actual class hierarchy. It fits when what matters is what the object can do, not how its data is laid out. The two overlap little. `Protocol` almost never describes a dict's shape, and `TypedDict` never describes an object with methods.
3. mypy checks the assignment `db: TaskStorage = sqlite_storage` structurally. It compares **the set of attributes on the object on the right** against the set of methods declared on `TaskStorage`. The object on the right is a module, and a module — like any object — has attributes: the functions defined in it. For each protocol method, mypy looks for a same-named attribute on `sqlite_storage` with a compatible signature. No explicit "declaration" from `sqlite_storage.py` is required, and that is the whole point of structural typing. Removing `get_page` from `TaskStorage` breaks nothing: the protocol simply stops requiring that method. The opposite case is more interesting. Remove `get_page` from `sqlite_storage.py` while leaving it in `TaskStorage`, and the assignment fails type-checking with something like `Module has no attribute "get_page"`. That is exactly what happened in practice with several methods on the first, incomplete version of the protocol.
4. `P.args` isn't "the type of each positional argument individually". It is a special, deliberately opaque marker. It means "exactly whatever set of positional arguments the original function `func` accepts, whatever that turns out to be". `ParamSpec` exists for one specific job and nothing more: guaranteeing that the call `func(*args, **kwargs)` inside the wrapper stays type-safe regardless of `func`'s signature. So it deliberately won't let you reach inside `args` and rely on the concrete type of a specific element. Otherwise the decorator would stop being genuinely universal. It would work only for functions whose first argument really has the needed attribute, while the `ParamSpec` declaration claims the opposite: "for absolutely any signature". If the code inside the wrapper relies on specific knowledge about the arguments, that knowledge has to be declared honestly. Do not smuggle it through a tool designed not to carry that information.
5. "Gradual typing" means typing in Python isn't all-or-nothing. You can type only part of a codebase and leave the rest with no annotations at all. By default mypy won't demand more from the untyped parts: a function with zero type annotations isn't analyzed for internal type mismatches at all. Inside such a function mypy treats every value as having an unknown type that accepts anything. The flag `strict = true` turns on a whole bundle of individually stricter flags at once — `disallow_untyped_defs`, `warn_return_any` and others. Together they require two things: every function must be fully annotated, and its body gets genuine, meaningful type checking. That flips the posture from "don't get in untyped code's way" to "require typing almost everywhere". The result is comparable in rigor to an ordinary `.ts` file under `tsc`.

</details>

## Common mistake

The most common and most dangerous mistake is to assume that an annotation protects you. Take a signature like `def handle(task_id: int) -> Task:`. It looks as if Python itself will reject a call with the wrong argument type, the way a typed language would. It won't, and the gap doesn't show up right away.

Code with type annotations **looks** like typed, disciplined code. Without a separate mypy run it isn't. That is doubly true without `strict = true`, and without wiring the run into CI as we did in this chapter. Until then the annotations are just comments with stricter syntax that nothing checks.

In practice it goes like this. A developer adds type hints but never runs `mypy`, or runs it without `strict`, where half the real errors are silently skipped for untyped code. The project can then accumulate type mismatches for months and behave no differently from a fully untyped one.

That lasts right up until the first real strict-mypy run. That run finds things genuinely worth fixing. The chapter showed three on our own code: an `Optional[int]`/`int` mismatch, an untyped attribute, and a decorator lying about its own generality.

The second common mistake runs in the opposite direction, but it is closely related. You see generic-looking code and reach for the most powerful tool available: `ParamSpec`, or deeply nested `TypeVar`s. What you skip is the first check — is the code really as generic as it looks?

That's exactly what happened with `log_command`. Typing it as "works with absolutely any signature" was technically possible, and the code would have compiled. But mypy flagged a mismatch on the very first meaningful line inside the function body, because the decorator was never really generic. It always implicitly assumed `argparse.Namespace`.

Typing isn't just about making mypy stop complaining. It is about making the declared type reflect what the code **actually** does, not what you'd like it to be.
