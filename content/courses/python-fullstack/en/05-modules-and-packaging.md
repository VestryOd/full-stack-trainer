# Modules, packages, and packaging the project

## Theory

**Module vs package.** A module in Python is simply a single `.py` file; importing it (`import foo`) runs `foo.py`'s code once and caches the result in `sys.modules`, so a repeated import doesn't re-run the file. A package is a directory containing other modules/packages, marked with an `__init__.py` file (a "regular package"). Since Python 3.3 there are also namespace packages — packages with no `__init__.py` at all — but for an ordinary application project, an explicit `__init__.py` is the standard, and stays that way throughout this course.

**Why `__init__.py` matters, even when it's empty.** It plays two roles: (1) historically and by convention, it marks "this is a package, not just a folder of scripts"; (2) practically, it's the place to curate a package's public API through re-exports:

```python
# taskman/models/__init__.py
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = ["Priority", "Task", "PRIORITY_CHOICES"]
```

This lets outside code write `from taskman.models import Task` without knowing that `Task` physically lives in `taskman/models/task.py` — exactly what an `index.js` barrel file does in a JS package, re-exporting the contents of internal files. The difference is fundamental: in JS, `index.js` is a **convention** that only works because the default module resolver happens to look for `index.js` when you import a directory. In Python, running `__init__.py` the first time any module from the package gets imported is a **language guarantee**, not a convention: `import taskman.models.task` will always execute `taskman/models/__init__.py` first, even if you imported the submodule directly rather than the package itself.

`__all__` is a separate concern: it doesn't "hide" other names (`from module import _private_name` still works if you name it explicitly) — it only limits what `from module import *` pulls in, and serves as a hint for documentation/IDE tooling about the module's "official" public surface.

**Relative imports.** `.` means the current package, `..` means one level up, and so on:

```python
# taskman/storage/memory.py
from ..models import Priority, Task   # up one level (into taskman/), then into models
```

```python
# taskman/models/__init__.py
from .task import Task                 # in the current package (models/), the task.py module
```

The key nuance: relative imports count levels of the **package hierarchy**, not literal filesystem steps, and they only work when the module is imported **as part of a package** — via `import` from somewhere else, or via `python -m package.module`. If you run the file directly as a script (`python taskman/cli/app.py`), the interpreter has no information about which package that file belongs to, and `from .commands import ...` fails with `ImportError: attempted relative import with no known parent package`. Absolute imports (`from taskman.models import Task`) don't have this problem — they always resolve from the root of `sys.path`/the installed package, regardless of how the current file was launched.

**How this differs from ES modules.** ES module (and Node) imports are explicit **paths** (`./foo.js`, `../bar.js`) that literally mirror the filesystem; Python's relative imports are steps through the **package hierarchy**, which usually matches the directory structure but is conceptually a different thing (99% of the time they coincide, but the idea "number of dots = package levels," not "directory levels," becomes visible exactly at the edge cases, like running a file directly). Also: exports in JS/TS are explicit, per-symbol (`export function foo`) — you can only import what was explicitly exported. In Python, **everything** without a leading `_` is importable by default — `__all__`/the underscore convention is curation for the reader, not language-enforced privacy.

**venv — going deeper.** Beyond `activate`/`deactivate` (chapter 00), a package with real structure benefits from:

```bash
pip install -e .        # editable install — the package's code is picked up live,
                         # no reinstall needed after every edit;
                         # the counterpart of npm link / a workspace package in a monorepo
pip list                # what's installed in the current venv
pip show taskman        # metadata for one specific installed package
```

An editable install isn't a copy of files into site-packages — it's a special "pointer" telling the interpreter: "look for this package's modules right here, on disk, at this path" — so changes to the source are visible immediately, with no re-running `pip install`.

**requirements.txt vs pyproject.toml + poetry/uv.** `requirements.txt` is a flat list of lines like `requests==2.31.0`, historically either hand-written or generated with `pip freeze > requirements.txt`. It has no notion of "direct dependency vs. transitive dependency," no hashes for integrity verification — it's just a snapshot of what happens to be installed right now, not a declaration of what should be installed. `pyproject.toml` (chapter 00) declares dependencies, but **on its own**, with just `pip`/`setuptools`, it doesn't produce a real lockfile with a resolved transitive dependency graph — a limitation already flagged back in chapter 00. Tools like **poetry** and **uv** add a proper lockfile on top of `pyproject.toml` (`poetry.lock`, `uv.lock`) with exact pinned versions and hashes for the whole tree — the direct counterpart of `package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`. As of 2026, `uv` is by far the fastest and most commonly recommended path (written in Rust, replaces `pip` + `venv` + much of poetry's functionality at once), but this course deliberately sticks to plain `pip`/`venv` so you're not depending on a third-party tool before the fundamentals are solid.

### Parallels with JS/TS/Node:

- A module ~ a file with ES-module semantics (the unit of import in both languages); a package is closest to an npm package with an `index.js` barrel — but executing `__init__.py` on submodule import is a language guarantee, not a resolver convention like `index.js`.
- Explicit `export` in JS/TS vs. "everything public by default" in Python — `__all__`/the leading underscore is a curation convention for the reader and `import *`, not language-enforced privacy.
- Dots in a relative import (`.`/`..`) are levels of the **package hierarchy**, not literal `./`/`../` filesystem steps like in Node; and relative imports simply don't work when the file is run directly as a script — only when imported as part of a package.
- `requirements.txt` ~ an old, hand-maintained or `pip freeze`-produced list with no lock semantics; `pyproject.toml` + `poetry`/`uv` ~ `package.json` + `package-lock.json`/`uv.lock` with real dependency resolution.

## What we're adding to the project

We're splitting the monolithic `main.py` into a `taskman` package with three subpackages — `models/` (Priority, Task), `storage/` (the in-memory store), and `cli/` (argparse, command handlers, `main()`) — and moving to a **src layout** (`src/taskman/...`), the move promised back in chapter 00. `pyproject.toml` gets a build section (`[build-system]`, `[tool.setuptools.packages.find]`) and `[project.scripts]`, so that after `pip install -e .` the `taskman` command works as a real installed CLI tool, not just via `python main.py`.

## Practical exercise

1. Create this structure:
   ```
   taskman/
     pyproject.toml
     src/
       taskman/
         __init__.py
         __main__.py
         models/
           __init__.py
           task.py
         storage/
           __init__.py
           memory.py
         cli/
           __init__.py
           parser.py
           commands.py
           app.py
   ```
2. Move `Priority`/`Task`/`PRIORITY_CHOICES` into `models/task.py`, re-export them from `models/__init__.py` (with `__all__`).
3. Move `tasks`/`add_task`/`find_task`/`mark_done`/`filter_by_status`/`sort_tasks` into `storage/memory.py`, importing `Priority`/`Task` with a **relative** import (`from ..models import Priority, Task`).
4. Split the CLI layer into `cli/parser.py` (`build_parser`), `cli/commands.py` (`log_command`, the three handlers, `COMMAND_HANDLERS`), and `cli/app.py` (`main()`, wiring `parser` and `COMMAND_HANDLERS` together).
5. `__main__.py` should import `main` from `taskman.cli` and call it — this is exactly what makes `python -m taskman` possible.
6. Update `pyproject.toml`: add `[build-system]` (`setuptools`), `[tool.setuptools.packages.find] where = ["src"]`, and `[project.scripts] taskman = "taskman.cli:main"`.
7. Install the package in editable mode (`pip install -e .` inside an activated venv) and confirm **both** ways of running it work: `python -m taskman add "Buy milk"` and plain `taskman add "Buy milk"`.
8. Delete the old flat `main.py` — it's no longer needed, all its logic has moved into the package.

Things to think through:

- What happens if you run `python src/taskman/cli/app.py` directly (not via `-m`, not after installing)? Why doesn't that work, and how does it connect to relative imports needing a "parent package"?
- Why does `cli/commands.py` import `from ..storage import memory` and call `memory.add_task(...)`, rather than `from ..storage.memory import add_task` directly? What's worse about the second option for a module that holds mutable state (`tasks: list[Task]`)?

## Worked solution

`pyproject.toml`:

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

`src/taskman/models/task.py`:

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

`src/taskman/models/__init__.py`:

```python
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = ["Priority", "Task", "PRIORITY_CHOICES"]
```

`src/taskman/storage/memory.py`:

```python
from ..models import Priority, Task

tasks: list[Task] = []


def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    task = Task(id=len(tasks) + 1, text=text, priority=priority)
    tasks.append(task)
    return task


def find_task(task_id: int) -> Task | None:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def mark_done(task_id: int) -> Task | None:
    task = find_task(task_id)
    if task is not None:
        task.done = True
    return task


def filter_by_status(items: list[Task], status: str) -> list[Task]:
    if status == "all":
        return items
    want_done = status == "done"
    return [task for task in items if task.done == want_done]


def sort_tasks(items: list[Task], sort_by: str) -> list[Task]:
    if sort_by == "priority":
        return sorted(items)
    return sorted(items, key=lambda t: t.id)
```

`src/taskman/storage/__init__.py`:

```python
from . import memory

__all__ = ["memory"]
```

`src/taskman/cli/commands.py`:

```python
import argparse
import functools
import sys

from ..models import Priority
from ..storage import memory


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        return result

    return wrapper


@log_command
def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = memory.add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = memory.sort_tasks(memory.filter_by_status(memory.tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
    else:
        for task in result:
            print(task)


@log_command
def handle_done(args: argparse.Namespace) -> None:
    task = memory.mark_done(args.id)
    if task is None:
        print(f"Task with id {args.id} not found.")
    else:
        print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}
```

`src/taskman/cli/parser.py`:

```python
import argparse

from ..models import PRIORITY_CHOICES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskman", description="Simple task manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("text", help="Task description")
    add_parser.add_argument(
        "--priority", choices=PRIORITY_CHOICES, default="medium", help="Task priority"
    )

    list_parser = subparsers.add_parser("list", help="List all tasks")
    list_parser.add_argument("--status", choices=["all", "done", "pending"], default="all")
    list_parser.add_argument("--sort", choices=["id", "priority"], default="id")

    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("id", type=int, help="Task id")

    return parser
```

`src/taskman/cli/app.py`:

```python
from .commands import COMMAND_HANDLERS
from .parser import build_parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    handler(args)
```

`src/taskman/cli/__init__.py`:

```python
from .app import main

__all__ = ["main"]
```

`src/taskman/__main__.py`:

```python
from taskman.cli import main

if __name__ == "__main__":
    main()
```

`src/taskman/__init__.py` — left empty: the top-level package has nothing to re-export yet, since the entire public surface is already described inside `models/`, `storage/`, and `cli/`.

Key decisions:

- `from ..models import Priority, Task` in `storage/memory.py` — a relative import that goes up one level and back down into `models/`; it demonstrates that a relative import counts package levels (`taskman`), not literal filesystem steps.
- `from ..storage import memory` (rather than `from ..storage.memory import add_task, tasks, ...`) in `cli/commands.py` — `memory` is imported as a namespace module, and calls read as `memory.add_task(...)`, `memory.tasks`. This is a deliberate choice for a module carrying mutable state (`tasks: list[Task]`): at the call site, it's immediately obvious that the state lives in `storage.memory`, rather than being scattered across implicitly imported individual names.
- `[project.scripts] taskman = "taskman.cli:main"` — after `pip install -e .` in a venv, an executable `taskman` shows up (at `.venv/bin/taskman`), which simply imports `taskman.cli` and calls `main`; this is exactly what npm does with the `"bin"` field in `package.json`.
- `[tool.setuptools.packages.find] where = ["src"]` — tells setuptools to look for packages under `src/`, not the project root; without this line, a src layout won't be auto-discovered (setuptools by default looks for packages right next to `pyproject.toml`).

## Check yourself

1. Why does `__init__.py` always run when you import a submodule (`import taskman.models.task`), even if you never explicitly imported the `taskman.models` package itself? How is that different from how `index.js` works in a JS module?
2. What do the dots in `from ..models import Task` actually count — what are they levels *of*, and why isn't that the same thing as `../` in a filesystem path?
3. Why does `python src/taskman/cli/app.py`, run directly, fail with `ImportError: attempted relative import with no known parent package`, while `python -m taskman` works, even though both "run the Python code in this file" in some sense?
4. How does `pip install -e .` differ from a plain `pip install .` when it comes to developing a package — what happens to source-code edits after each change?
5. Why isn't a `requirements.txt` generated via `pip freeze` a real lockfile in the sense that `package-lock.json` is one? What's fundamentally missing from it?

<details>
<summary>Answers</summary>

1. A package in Python isn't just "a folder of files" — it's an object in `sys.modules`, and importing any submodule of a package **requires** first creating and initializing the package object itself — and initializing a package means running its `__init__.py`. This is a guarantee baked into the import machinery of the language itself (`importlib`), not a behavior you can opt out of. `index.js` in JS is just a file the module resolver looks for by convention when a directory is imported as a whole; if you import a specific file inside that directory directly (`import './foo/bar.js'`), `index.js` is never touched at all — in Python, the equivalent "bypass" is impossible: the package's `__init__.py` runs regardless.
2. The dots count levels in the **package** tree (what's registered in `sys.modules` and defined by the `__init__.py` structure), not the directory tree on disk. In practice these two trees almost always line up exactly, which is why the difference is invisible 99% of the time — but conceptually, `from ..models import Task` means "go up one level from the package that contains **the current module**," not "go up one directory on disk"; the distinction becomes visible precisely when a module is run outside of its package context (see question 3) — in that situation, the file simply has no information about which package it "belongs to."
3. Running `python file.py` directly loads that file as the `__main__` module **with no parent package** — it has no information that it physically lives inside `taskman/cli/`, because running a file by its direct path doesn't go through the package-import machinery at all. `from .commands import ...` needs to know "the current package to count the dot from" — and since there's no parent package, there's nothing to count from, hence the error. `python -m taskman` is a fundamentally different launch mechanism: it uses `runpy`, finds the `taskman` package through the normal import machinery, resolves `taskman.__main__` as the entry point, and executes it **as part of** the `taskman` package, with a fully and correctly initialized package hierarchy — which is why relative imports inside it work.
4. `pip install .` copies the package's built files into the venv's site-packages — after that, edits to the project's source code have no effect on the installed copy until you reinstall the package. `pip install -e .` (editable mode) instead places a lightweight pointer in site-packages, referencing the source directory (`src/`), so that when `taskman` is imported, the interpreter literally reads the files from wherever you're editing them — changes are visible immediately, with no reinstall step.
5. `pip freeze` prints a list of **everything currently installed** in the environment, with versions, but with no distinction between "what I explicitly asked for" and "what got pulled in as a transitive dependency," no dependency graph (what depends on what), and no cryptographic hashes confirming the integrity and origin of the downloaded files. A real lockfile (`package-lock.json`, `poetry.lock`, `uv.lock`) pins the entire resolved dependency tree, with hashes, generated by a deterministic version-resolution algorithm — it isn't a side effect of "whatever happened to be installed in this particular environment at the moment `freeze` ran."

</details>

## Common mistake

The most common mistake at this stage is trying to run one of the package's files directly as a script while debugging (`python src/taskman/cli/app.py`, or even more commonly, hitting "Run" on a specific file in an IDE) and hitting `ImportError: attempted relative import with no known parent package`. A developer used to Node, where `node ./src/cli/app.js` works with no extra conditions (Node resolves `require`/`import` relative to wherever it was launched from), doesn't expect that *how* you launch a file in Python can change whether the imports inside it work at all. The right fix isn't to swap relative imports for absolute ones "just to make it run" — it's to run the package the way it's meant to be run: via `python -m taskman` (or, once installed, via the generated `taskman` command) — always as part of the package, never as a standalone file.

The second common trip-up is forgetting `[tool.setuptools.packages.find] where = ["src"]` when moving to a src layout, and ending up with an empty or incorrectly assembled package after `pip install -e .` (setuptools by default looks for packages right next to `pyproject.toml`, i.e. the project root, not inside `src/`). The symptom usually isn't obvious right away: the install "succeeds" with no errors, but `import taskman` either can't find the package at all, or finds the wrong thing — because setuptools' default package auto-discovery is built for a flat layout and doesn't look inside `src/` unless told to explicitly.
