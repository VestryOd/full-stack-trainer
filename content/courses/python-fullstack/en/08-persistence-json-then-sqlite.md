# Persistence: JSON first, then SQLite

## Theory

**A JSON file: `pathlib` + `json`.** The simplest way to survive a process restart is to save data to a file in full, and read it back on startup:

```python
import json
from pathlib import Path

path = Path("tasks.json")

# write
data = [{"id": 1, "text": "Buy milk", "priority": "low", "done": False}]
path.write_text(json.dumps(data, indent=2))

# read
data = json.loads(path.read_text()) if path.exists() else []
```

`pathlib.Path` unifies what Node splits across two separate APIs: path manipulation (`path.join`, `path.resolve`) and file I/O (`fs.readFileSync`, `fs.writeFileSync`, `fs.existsSync`) — in Python these are all methods on the same object (`.read_text()`, `.write_text()`, `.exists()`, `.parent.mkdir(...)`).

The naming in the `json` module isn't arbitrary: `dumps`/`loads` (with an "s" — "string") work with **strings**; `dump`/`load` (no "s") work directly with a **file object**, skipping the manual "read a string, then parse it" combination:

```python
with path.open("w") as f:
    json.dump(data, f, indent=2)     # writes straight to the file, no intermediate string

with path.open() as f:
    data = json.load(f)               # reads and parses straight from the file
```

`JSON.stringify`/`JSON.parse` in JS are the direct counterpart of `dumps`/`loads` (string ↔ object); there's no built-in Node equivalent of `dump`/`load` (file ↔ object with no manual step) — there you'd always combine `fs.readFileSync` and `JSON.parse` by hand.

**Limitations of a JSON file as storage.** Every change requires reading the **entire** file, mutating the data in memory, and rewriting the **entire** file — there's no such thing as a partial update to a single record. Filtering/search means "load everything into Python and filter there," with no way to delegate the query to the storage layer. And critically: a plain file write has no protection against concurrent writes from multiple processes — exactly the problem `FileLock` from chapter 06 was written to solve. JSON-based persistence would need the same treatment (or something even coarser — a full serialization lock on every operation, not just logging).

**SQLite: a database built into the stdlib.** `sqlite3` ships with the standard library — nothing extra to install. It's a file-based (not client-server) database engine — a single file on disk (`taskman.db`), with no separate server process to stand up and configure. For CLI tools, tests, embedded apps, it's exactly the right fit, with none of Postgres/MySQL's infrastructure overhead.

```python
import sqlite3

conn = sqlite3.connect("taskman.db")
conn.row_factory = sqlite3.Row   # access columns by name: row["text"], not row[1]

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

cursor = conn.execute("INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)", ("Buy milk", 0, 0))
conn.commit()
new_id = cursor.lastrowid

rows = conn.execute("SELECT * FROM tasks WHERE done = ?", (0,)).fetchall()
conn.close()
```

A nuance specific to SQLite (not to SQL in general): SQLite doesn't enforce strict column typing — it uses "type affinity" instead, and in many cases will happily insert a string into an `INTEGER` column without raising. Postgres/MySQL are considerably stricter here — worth keeping in mind precisely because growing the project further (chapter 18, "where to grow next") typically means moving from SQLite to Postgres, where this kind of looseness gets caught much harder at `INSERT` time.

**Parameterized queries and SQL injection.** This isn't a Python language feature — it's a universal rule for any SQL database in any language (the same is true of `pg`/`mysql2`/Prisma in Node): never build SQL text out of untrusted data via f-strings/concatenation:

```python
# DANGEROUS — never do this:
user_input = "' OR '1'='1"
cursor.execute(f"SELECT * FROM tasks WHERE text = '{user_input}'")
# the resulting SQL: SELECT * FROM tasks WHERE text = '' OR '1'='1'
# → returns EVERY row in the table, not what was intended

# SAFE — a parameterized query:
cursor.execute("SELECT * FROM tasks WHERE text = ?", (user_input,))
# the value is sent to the driver SEPARATELY from the query text;
# it's never interpreted as part of the SQL syntax
```

`?` is `sqlite3`'s positional placeholder (there's also a named form, `:name`, with a parameter dict). This is exactly the thing that comes up in interviews: "how do you prevent SQL injection" — the right answer is "parameterized queries / prepared statements," not "escape the quotes by hand."

**Transactions, and a non-obvious nuance about `Connection` as a context manager.** `sqlite3.Connection`, used as `with conn:`, commits the transaction on a clean exit and rolls it back on an exception — but it does **not close the connection**. This is a common trap even for experienced developers: `with conn:` only manages the transaction, not the connection's lifecycle. To get both — transactional behavior **and** guaranteed closing — it's convenient to write your own generator-based context manager (chapter 06 and chapter 07, in one place):

```python
from contextlib import contextmanager

@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()          # only if the block finished with no exception
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()            # closes ALWAYS
```

This is literally a generator function decorated with `@contextmanager` (chapter 07): the code before `yield` opens the connection (the `__enter__` counterpart), the code after `yield` commits/rolls back/closes (the `__exit__` counterpart), and the `try/except/finally` wrapped around `yield` is exactly what chapter 06 covered — just written as a generator instead of a class.

### Parallels with JS/TS/Node:

- `pathlib.Path` unifies path manipulation and file I/O into one object; Node splits these across `path` and `fs`.
- `json.dumps`/`json.loads` ~ `JSON.stringify`/`JSON.parse`; there's no direct Node equivalent of `json.dump`/`json.load` (working straight with a file object) — there it's always a manual `fs.readFileSync` + `JSON.parse` combination.
- `sqlite3` is part of Python's stdlib, nothing to install; Node has no built-in SQL driver at all — `better-sqlite3`/`pg`/`mysql2`/Prisma, etc. are always external packages. Query parameterization (`$1`, `?`) follows the same principle as Python — this isn't Python-specific, it's a universal SQL rule.
- SQLite's loose "type affinity" (unlike Postgres/MySQL's strict typing) is a SQLite-specific quirk, not a SQL-wide one — worth remembering for whenever the project eventually moves to a "real" database.

## What we're adding to the project

The storage layer moves from an in-memory list (`storage/memory.py`, chapters 02–07) to a file-based SQLite database (`storage/sqlite_storage.py`). Tasks now **survive a process restart** — something that's been missing since the very first chapter. The filtering/sorting/pagination logic (chapters 02 and 07) doesn't change at all: it accepted a plain `list[Task]` before, and it still does — that list is just loaded from the database each time now, instead of living as a module-level variable.

## Practical exercise

Part A — practice on the simple version (doesn't stay in the final project):

1. Write `storage/json_file.py` with the same public interface as `storage/memory.py` (`add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks`), but store the data in `tasks.json` via `pathlib.Path` + `json.dumps`/`json.loads`. Every operation should: read the whole file (or start from an empty list if it doesn't exist), mutate the data in memory, rewrite the whole file.
2. Confirm tasks survive a process restart: `add`, then in a fresh call to `python -m taskman list` — the task should still be there.
3. Leave this file as-is or delete it — it isn't needed going forward; it's purely an exercise in understanding the approach's limits.

Part B — what actually stays in the project:

1. Create `storage/sqlite_storage.py`. Define `DB_PATH = Path("taskman.db")` and a generator-based context manager `db_connection()` (via `@contextmanager`) that opens a connection, commits on success, rolls back on an exception, and **always** closes the connection.
2. Write `init_db()`, creating the `tasks` table (`id`, `text`, `priority`, `done`) if it doesn't already exist.
3. Rewrite `add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks` to use parameterized SQL queries through `db_connection()`. `list_tasks()` replaces the old module-level `tasks` — it needs to hit the database every time, not cache a list in memory.
4. `filter_by_status`/`sort_tasks` (chapters 02/07) and `paginate`/`get_page` (chapter 07) carry over unchanged — they already take a plain `list[Task]`; they don't care where it came from.
5. Update `storage/__init__.py`, `cli/commands.py` (replace `memory` with `db`, and `memory.tasks` with a call to `db.list_tasks()`), and `cli/app.py` (call `db.init_db()` at the start of `main()`, before parsing arguments).
6. Confirm tasks survive a process restart — same as in Part A, but through SQLite this time.

Things to think through:

- Why does `mark_done` in the SQLite version make two round trips to the database (`get_task`, then `UPDATE`) instead of one `UPDATE ... RETURNING`? Is that suboptimal, or a reasonable trade-off at this stage?
- `with conn:` on a `sqlite3.Connection` commits/rolls back the transaction but doesn't close the connection. What would happen if `db_connection()` only used `with conn:`, with no explicit `conn.close()` in a `finally`? Would the code be immediately broken, or would the problem only show up under specific operating conditions?

## Worked solution

`storage/sqlite_storage.py` (new, replacing `memory.py`), `storage/__init__.py`, `cli/commands.py`, and `cli/app.py` change. Everything else stays the same as in chapter 07.

`src/taskman/storage/sqlite_storage.py` (new file):

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..models import Priority, Task, TaskNotFoundError

DB_PATH = Path("taskman.db")


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


def paginate(items: list[Task], page_size: int):
    page: list[Task] = []
    for task in items:
        page.append(task)
        if len(page) == page_size:
            yield page
            page = []
    if page:
        yield page


def get_page(items: list[Task], page: int, page_size: int) -> list[Task]:
    import itertools

    pages = itertools.islice(paginate(items, page_size), page - 1, page)
    return next(pages, [])
```

`src/taskman/storage/__init__.py` (updated):

```python
from . import sqlite_storage as db

__all__ = ["db"]
```

`src/taskman/cli/commands.py` (updated — `memory` → `db`, `memory.tasks` → `db.list_tasks()`):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db

print_err = functools.partial(print, file=sys.stderr)


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

`src/taskman/cli/app.py` (updated — calls `db.init_db()`):

```python
from ..storage import db
from .commands import COMMAND_HANDLERS
from .parser import build_parser


def main() -> None:
    db.init_db()
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    handler(args)
```

Key decisions:

- `int(priority)`/`Priority(row["priority"])` — round-tripping through a plain SQLite `INTEGER` column works with zero serialization logic precisely because chapter 04 chose `Priority` as an `IntEnum`, not a plain `Enum`: `int(Priority.HIGH) == 2`, and `Priority(2)` gives back `Priority.HIGH`.
- Mapping a SQLite row to a `Task` (`_row_to_task`) lives in the storage layer, not on the `Task` class itself — the model knows nothing about `sqlite3.Row`; that's a concern specific to whichever storage backend is in use. The next time the storage backend changes (chapter 18: "where to grow next" — Postgres), `Task` won't need to change again.
- `db.list_tasks()` replaces the old `memory.tasks` attribute access with a function call — the name itself signals that this isn't a free read of a variable, but a call out to external storage that costs something real (I/O, potentially network once we're on a "real" database).
- `db.init_db()` is called explicitly at the start of `main()`, rather than as a side effect of importing the `sqlite_storage` module — the module stays "clean" on import (chapter 05: importing shouldn't have surprising side effects), and schema initialization happens somewhere it's visibly, explicitly triggered in the code.
- `mark_done` does `get_task` and `UPDATE` as two separate steps, not one combined query — at this scale that's not a performance concern, it's a deliberate choice to reuse the already-written `get_task` (with its `TaskNotFoundError`) instead of duplicating the existence check inside SQL.

## Check yourself

1. Why is `data = json.loads(path.read_text()) if path.exists() else []` a required check, not just paranoia? What happens without it on the very first CLI run, before `tasks.json` exists?
2. How do `json.dumps`/`json.loads` differ from `json.dump`/`json.load` in signature and purpose — and how do you decode the trailing "s" so you don't mix them up?
3. Walk through, step by step, what happens to the data in the database if an unhandled exception occurs inside `with db_connection() as conn:` right after a successful `INSERT`. Does the insert get committed? Why is the `try/except/finally` wrapped around `yield` set up exactly this way?
4. Why does a parameterized query (`conn.execute("... WHERE text = ?", (value,))`) protect against SQL injection while an f-string with the same value doesn't? Is it about escaping special characters, or something more fundamental?
5. What exactly does "SQLite uses type affinity, not strict column typing" mean — and why is that a deliberate SQLite design choice rather than a bug, setting it apart from Postgres/MySQL?

<details>
<summary>Answers</summary>

1. Without the `path.exists()` check, calling `path.read_text()` on a file that doesn't exist raises `FileNotFoundError` — and on the very first CLI run (before any task has ever been saved), `tasks.json` genuinely doesn't exist yet. The check explicitly encodes the business rule "no file means no tasks yet, not an error," instead of relying on an exception as an implicit signal for that state.
2. `dumps`/`loads` work with **strings** in memory: `dumps` turns a Python object into a JSON string, `loads` parses a JSON string back into a Python object — neither one knows anything about files. `dump`/`load` (no "s") do the same job but write to/read from a **file object** directly (something already opened via `open()` or `path.open()`), skipping the intermediate "read into a string first, then parse the string" step. Mnemonic: the trailing "s" stands for "string" — the "s" functions work with strings, the ones without work with files.
3. If an exception occurs after the `INSERT` but before the `with db_connection() as conn:` block ends, then `yield conn` inside the `db_connection` generator doesn't complete normally — control jumps into that same generator's `except Exception:` block, which calls `conn.rollback()` and re-raises (`raise`) the exception onward, out to the calling code. `conn.commit()`, which sits right after `yield conn`, **never runs at all** in this case — it's on the same "line of execution" as the code inside the `with` block, and control simply never reaches it, because it has already jumped into `except`. That's exactly why the `INSERT` isn't committed: the whole transaction rolls back, and the database ends up as if nothing had been inserted.
4. It isn't about escaping quotes — it's that a parameterized query physically keeps the **SQL command text** and the **data** as two separate, independent things, sent to the driver separately: the query's structure (`SELECT * FROM tasks WHERE text = ?`) is fixed and compiled once, and the parameter value is substituted in as data, not as text that then gets re-parsed together with the rest of the SQL. An f-string instead produces one single blob of text, where the user's value becomes part of what the SQL interpreter will parse as code — escaping quotes reduces the risk but doesn't eliminate the underlying architectural problem of "data and code mixed into the same text," and there's almost always a way around any specific escaping scheme.
5. Type affinity means a column's declared type (`INTEGER`, `TEXT`, etc.) in SQLite is a **preference**, not a hard constraint: the engine tries to coerce an inserted value to the column's declared type, but if it can't do so unambiguously, it often just stores the value as-is instead of rejecting the insert with an error. This is a deliberate SQLite design choice, reflecting its origins as an embeddable, "flexible" database for small applications and config files — not an oversight; Postgres/MySQL are designed for strict schema-level data integrity, and will normally reject an `INSERT` with an incompatible type at the database level rather than quietly accepting it.

</details>

## Common mistake

The most common mistake with this material is assuming `with conn:` on a `sqlite3.Connection` closes the connection the same way it does for files (`with open(...) as f:`) or the `FileLock` from chapter 06. A developer who's already internalized "a context manager guarantees resource release" reasonably expects the same from `with conn:` — but `sqlite3.Connection`'s `__exit__` protocol is implemented **only** for transaction management (commit/rollback), not for closing the connection itself. In a small script that exits right after running, this won't show up as a visible problem — the OS closes file descriptors on exit regardless. But in something longer-lived (a web server, a worker, a test suite creating connections in a loop), connections quietly pile up until the process hits its open-file-descriptor limit — a failure that surfaces far away in both time and code from the spot where the "`with conn:` closes everything" assumption was made.

The second common mistake, especially fresh off the strings/f-strings chapter (chapter 01), is reflexively building a SQL query with an f-string, because "it's just text, and f-strings are the most natural way to interpolate a value into text" in Python. The difference between `f"WHERE text = '{value}'"` and `"WHERE text = ?", (value,)` isn't visible in behavior on "normal" data — both work identically for ordinary text with no quotes inside it. The vulnerability only becomes visible once someone (not necessarily an attacker — sometimes just a user whose task text happens to contain an apostrophe, like "don't forget the milk") passes a value containing characters that break the query's intended structure — meaning the bug stays silent right up until it turns into a security incident, or just a baffling production error.
