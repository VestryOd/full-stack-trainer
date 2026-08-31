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

`pathlib.Path` unifies what Node splits across two separate APIs. One is path manipulation: `path.join`, `path.resolve`. The other is file input/output: `fs.readFileSync`, `fs.writeFileSync`, `fs.existsSync`. In Python these are all methods on the same object: `.read_text()`, `.write_text()`, `.exists()`, `.parent.mkdir(...)`.

The naming in the `json` module isn't arbitrary. The pair `dumps`/`loads` (with an "s", for "string") works with **strings**. The pair `dump`/`load` (no "s") works directly with a **file object**, skipping the manual "read a string, then parse it" combination:

```python
with path.open("w") as f:
    json.dump(data, f, indent=2)     # writes straight to the file, no intermediate string

with path.open() as f:
    data = json.load(f)               # reads and parses straight from the file
```

`JSON.stringify`/`JSON.parse` in JS are the direct counterpart of `dumps`/`loads` — string to object and back. Node has no built-in equivalent of `dump`/`load`, which go from file to object with no manual step. There you'd always combine `fs.readFileSync` and `JSON.parse` by hand.

**Limitations of a JSON file as storage.** Every change requires reading the **entire** file, mutating the data in memory, and rewriting the **entire** file. There is no such thing as a partial update to a single record. Filtering and search mean "load everything into Python and filter there", with no way to delegate the query to the storage layer.

And critically: a plain file write has no protection against concurrent writes from several processes. That is exactly the problem `FileLock` from chapter 06 was written to solve. JSON-based persistence would need the same treatment, or something even coarser — one serialization lock on every operation, not just on logging.

**SQLite: a database built into the stdlib.** `sqlite3` ships with the standard library — nothing extra to install. It is a file-based, not client-server, database engine: a single file on disk (`taskman.db`), with no separate server process to stand up and configure.

For a CLI (command-line interface) tool, for tests, for an embedded app it is exactly the right fit. None of the infrastructure overhead of Postgres or MySQL comes with it.

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

cursor = conn.execute(
    "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
    ("Buy milk", 0, 0),
)
conn.commit()
new_id = cursor.lastrowid

rows = conn.execute("SELECT * FROM tasks WHERE done = ?", (0,)).fetchall()
conn.close()
```

One word in that schema deserves a note. `AUTOINCREMENT` tells SQLite never to reuse the `id` of a deleted row: every new row gets a number larger than any used before.

One nuance is specific to SQLite, not to SQL (structured query language) in general. SQLite doesn't enforce strict column typing. It uses "type affinity" instead, and in many cases will happily insert a string into an `INTEGER` column without raising. Postgres and MySQL are considerably stricter here.

That is worth keeping in mind precisely because growing the project further (chapter 18, "where to grow next") usually means moving from SQLite to Postgres. There this kind of looseness gets caught much harder, at `INSERT` time.

**Parameterized queries and SQL injection.** This isn't a Python language feature. It is a universal rule for any SQL database in any language, and `pg`, `mysql2` and Prisma in Node follow it too. Never build SQL text out of untrusted data with f-strings or concatenation:

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

`?` is the positional placeholder of `sqlite3`. There is also a named form, `:name`, taking a dict of parameters. Interviews ask about this constantly: how do you prevent SQL injection? The right answer is "parameterized queries, or prepared statements" — not "escape the quotes by hand".

**Transactions, and a non-obvious nuance about `Connection` as a context manager.** Used as `with conn:`, a `sqlite3.Connection` commits the transaction on a clean exit and rolls it back on an exception. But it does **not close the connection**. This is a common trap even for experienced developers: `with conn:` manages only the transaction, not the connection's lifecycle.

To get both transactional behavior **and** guaranteed closing, it's convenient to write your own generator-based context manager. Chapter 06 and chapter 07 come together in one place here:

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("taskman.db")

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

This is literally a generator function decorated with `@contextmanager` (chapter 07). The code before `yield` opens the connection — the `__enter__` counterpart. The code after `yield` commits, rolls back and closes — the `__exit__` counterpart. The `try/except/finally` wrapped around `yield` is exactly what chapter 06 covered, just written as a generator instead of a class.

### Parallels with JS/TS/Node:

- `pathlib.Path` unifies path manipulation and file input/output into one object. Node splits these across `path` and `fs`.
- `json.dumps`/`json.loads` ~ `JSON.stringify`/`JSON.parse`. Node has no direct equivalent of `json.dump`/`json.load`, which work straight with a file object. There it's always a manual `fs.readFileSync` + `JSON.parse` combination.
- `sqlite3` is part of Python's stdlib, with nothing to install. Node has no built-in SQL driver at all: `better-sqlite3`, `pg`, `mysql2`, Prisma and the rest are always external packages. Query parameterization (`$1`, `?`) follows the same principle as in Python — a universal SQL rule, not a Python one.
- The loose "type affinity" of SQLite, unlike the strict typing of Postgres and MySQL, is a SQLite quirk and not a SQL-wide rule. Worth remembering for whenever the project moves to a "real" database.

## What we're adding to the project

The storage layer moves from an in-memory list (`storage/memory.py`, chapters 02–07) to a file-based SQLite database (`storage/sqlite_storage.py`). Tasks now **survive a process restart** — something that's been missing since the very first chapter.

The filtering, sorting and pagination logic (chapters 02 and 07) doesn't change at all. It accepted a plain `list[Task]` before, and it still does. That list is simply loaded from the database each time now, instead of living as a module-level variable.

## Practical exercise

Part A — practice on the simple version (doesn't stay in the final project):

1. Write `storage/json_file.py` with the same public interface as `storage/memory.py`: `add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks`. Store the data in `tasks.json` via `pathlib.Path` plus `json.dumps`/`json.loads`. Every operation reads the whole file, or starts from an empty list if there is no file. Then it mutates the data in memory and rewrites the whole file.
2. Confirm tasks survive a process restart: `add`, then in a fresh call to `python -m taskman list` — the task should still be there.
3. Leave this file as-is or delete it — it isn't needed going forward; it's purely an exercise in understanding the approach's limits.

Part B — what actually stays in the project:

1. Create `storage/sqlite_storage.py`. Define `DB_PATH = Path("taskman.db")` and a generator-based context manager `db_connection()`, built with `@contextmanager`. It opens a connection, commits on success, rolls back on an exception, and **always** closes the connection.
2. Write `init_db()`, creating the `tasks` table (`id`, `text`, `priority`, `done`) if it doesn't already exist.
3. Rewrite `add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks` to use parameterized SQL queries through `db_connection()`. The new `list_tasks()` replaces the old module-level `tasks`. It must hit the database every time, not cache a list in memory.
4. `filter_by_status`/`sort_tasks` (chapters 02/07) and `paginate`/`get_page` (chapter 07) carry over unchanged. They already take a plain `list[Task]` and don't care where it came from.
5. Update three files. In `cli/commands.py` replace `memory` with `db`, and `memory.tasks` with a call to `db.list_tasks()`. In `cli/app.py` call `db.init_db()` at the start of `main()`, before parsing arguments. Update `storage/__init__.py` as well.
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

- `int(priority)`/`Priority(row["priority"])` — the round trip through a plain SQLite `INTEGER` column works with zero serialization logic. That is precisely because chapter 04 chose `Priority` as an `IntEnum`, not a plain `Enum`. So `int(Priority.HIGH) == 2`, and `Priority(2)` gives back `Priority.HIGH`.
- Mapping a SQLite row to a `Task` (`_row_to_task`) lives in the storage layer, not on the `Task` class itself. The model knows nothing about `sqlite3.Row`: that is a concern of whichever storage backend is in use. The next time the backend changes (chapter 18: "where to grow next" — Postgres), `Task` won't need to change again.
- `db.list_tasks()` replaces the old `memory.tasks` attribute access with a function call. The name itself signals that this isn't a free read of a variable. It is a call out to external storage that costs something real: input/output, and potentially network once we're on a "real" database.
- `db.init_db()` is called explicitly at the start of `main()`, not as a side effect of importing the `sqlite_storage` module. The module stays "clean" on import — chapter 05 asked that importing have no surprising side effects. Schema initialization then happens in a place where the code visibly triggers it.
- `mark_done` does `get_task` and `UPDATE` as two separate steps, not one combined query. At this scale that is not a performance concern. It is a deliberate choice to reuse the already-written `get_task`, with its `TaskNotFoundError`, instead of duplicating the existence check inside SQL.

## Check yourself

1. Why is `data = json.loads(path.read_text()) if path.exists() else []` a required check, not just paranoia? What happens without it on the very first CLI run, before `tasks.json` exists?
2. How do `json.dumps`/`json.loads` differ from `json.dump`/`json.load` in signature and purpose? And how do you decode the trailing "s" so you don't mix them up?
3. An unhandled exception occurs inside `with db_connection() as conn:`, right after a successful `INSERT`. Walk through step by step what happens to the data in the database. Does the insert get committed? Why is the `try/except/finally` around `yield` set up exactly this way?
4. Why does a parameterized query (`conn.execute("... WHERE text = ?", (value,))`) protect against SQL injection while an f-string with the same value doesn't? Is it about escaping special characters, or something more fundamental?
5. What exactly does "SQLite uses type affinity, not strict column typing" mean? And why is that a deliberate design choice rather than a bug, setting SQLite apart from Postgres and MySQL?

<details>
<summary>Answers</summary>

1. Without the `path.exists()` check, calling `path.read_text()` on a file that doesn't exist raises `FileNotFoundError`. On the very first CLI run, before any task has ever been saved, `tasks.json` genuinely doesn't exist yet. The check explicitly encodes a business rule: no file means no tasks yet, and that is not an error. It does not lean on an exception as an implicit signal for that state.
2. The pair `dumps`/`loads` works with **strings**. In memory `dumps` turns a Python object into a JSON string, and `loads` parses a JSON string back into a Python object. Neither one knows anything about files. The pair `dump`/`load` (no "s") does the same job. But it writes to and reads from a **file object** directly, something already opened via `open()` or `path.open()`. That skips the intermediate "read into a string first, then parse the string" step. Mnemonic: the trailing "s" stands for "string". The functions with "s" work with strings, the ones without work with files.
3. Say an exception occurs after the `INSERT`, but before the `with db_connection() as conn:` block ends. Then `yield conn` inside the `db_connection` generator doesn't complete normally. Control jumps into that same generator's `except Exception:` block, which calls `conn.rollback()` and re-raises the exception out to the calling code. The `conn.commit()` line sits right after `yield conn`, and in this case it **never runs at all**. It is on the same "line of execution" as the code inside the `with` block. Control never reaches it, because it has already jumped into `except`. That is exactly why the `INSERT` isn't committed: the whole transaction rolls back, and the database ends up as if nothing had been inserted.
4. It isn't about escaping quotes. A parameterized query physically keeps the **SQL command text** and the **data** as two separate, independent things, sent to the driver separately. The structure of the query (`SELECT * FROM tasks WHERE text = ?`) is fixed and compiled once. The parameter value is then substituted in as data, not as text that gets re-parsed together with the rest of the SQL. An f-string instead produces one single blob of text, where the user's value becomes part of what the SQL interpreter will parse as code. Escaping quotes reduces the risk, but it doesn't remove the underlying architectural problem of data and code mixed into one text. There is almost always a way around any specific escaping scheme.
5. Type affinity means that a column's declared type in SQLite — `INTEGER`, `TEXT` and so on — is a **preference**, not a hard constraint. The engine tries to coerce an inserted value to the declared type. If it can't do so unambiguously, it often just stores the value as it is, instead of rejecting the insert with an error. This is a deliberate design choice, not an oversight. It reflects the origins of SQLite as an embeddable, "flexible" database for small applications and configuration files. Postgres and MySQL are designed for strict schema-level data integrity. They will normally reject an `INSERT` with an incompatible type at the database level, rather than quietly accepting it.

</details>

## Common mistake

The most common mistake here is assuming that `with conn:` on a `sqlite3.Connection` closes the connection. That is what happens with files (`with open(...) as f:`) and with the `FileLock` from chapter 06. A developer who has internalized "a context manager guarantees resource release" reasonably expects the same.

But the `__exit__` protocol of `sqlite3.Connection` is implemented **only** for transaction management — commit and rollback — and not for closing the connection itself. In a small script that exits right after running, this won't show up as a visible problem. The operating system closes file descriptors on exit regardless.

Something longer-lived is different: a web server, a worker, a test suite creating connections in a loop. There connections quietly pile up until the process hits its limit on open file descriptors. The failure then surfaces far away in both time and code from the spot where the assumption was made.

The second common mistake is reflexively building a SQL query with an f-string. It comes easily right after the chapter on strings and f-strings (chapter 01). A query is just text, and f-strings are the most natural way to put a value into text in Python.

The difference between `f"WHERE text = '{value}'"` and `"WHERE text = ?", (value,)` isn't visible in behavior on "normal" data. Both work identically for ordinary text with no quotes inside it.

The vulnerability shows up only when someone passes a value with characters that break the intended structure of the query. Not necessarily an attacker: sometimes it is just a user who typed "don't forget the milk" and used an apostrophe. The bug therefore stays silent right up until it turns into a security incident, or just a baffling production error.
