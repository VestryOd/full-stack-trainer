# Modules, packages, and packaging the project

## Theory

**Module vs package.** A module in Python is simply a single `.py` file. Importing it (`import foo`) runs the code of `foo.py` once and caches the result in `sys.modules`. A repeated import does not re-run the file.

A package is a directory that holds other modules and packages, marked with an `__init__.py` file (a "regular package"). Since Python 3.3 there are also namespace packages — packages with no `__init__.py` at all. For an ordinary application project the explicit `__init__.py` is the standard, and it stays that way throughout this course.

**Why `__init__.py` matters, even when it's empty.** It plays two roles. First, historically and by convention, it marks "this is a package, not just a folder of scripts". Second, in practice it is the place to curate a package's public API through re-exports:

```python
# taskman/models/__init__.py
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = ["Priority", "Task", "PRIORITY_CHOICES"]
```

This lets outside code write `from taskman.models import Task` without knowing that `Task` physically lives in `taskman/models/task.py`. A barrel file `index.js` in a JS package does exactly the same job: it re-exports the contents of internal files.

The difference is fundamental. In JS, `index.js` is only a **convention**. It works because the default module resolver happens to look for `index.js` when you import a directory.

In Python, running `__init__.py` on the first import of any module from the package is a **language guarantee**, not a convention. So `import taskman.models.task` always runs `taskman/models/__init__.py` first, even if you imported the submodule directly. The package itself never has to be imported by name.

`__all__` is a separate concern, and it hides nothing. Naming a private name explicitly still works: `from module import _private_name` imports it. At runtime what `__all__` limits is `from module import *`, and nothing else. It also acts as a hint to documentation tools and to the IDE (integrated development environment) about the module's "official" public surface.

For a type checker, though, `__all__` in an `__init__.py` carries real weight. A line like `from .task import Task` inside `__init__.py` is an **implicit** re-export. Under `no_implicit_reexport`, a flag that `mypy --strict` turns on, that import from the package stops type-checking. The message is `Module "taskman.models" does not explicitly export attribute "Task"`, under the error code `attr-defined`.

Two forms make a re-export explicit. List the name in `__all__`, as the snippet above does. Or write the redundant-looking `from .task import Task as Task`. This course puts an `__all__` list in every `__init__.py`. That is why the strict mypy run in chapter 10 has nothing to say about these imports.

**Relative imports.** `.` means the current package, `..` means one level up, and so on:

```python
# taskman/storage/memory.py
from ..models import Priority, Task   # up one level (into taskman/), then into models
```

```python
# taskman/models/__init__.py
from .task import Task                 # in this package (models/), the task.py module
```

Two trees overlap here, and the dots walk only one of them:

```txt
Inside src/taskman/storage/memory.py

On disk:            src/ -> taskman/ -> storage/ -> memory.py
Package hierarchy:  taskman -> storage -> memory

"src" is a directory, not a package level. That is the gap.

So "from ..models import Task", read inside this module:
  .        = taskman.storage   (the package holding memory.py)
  ..       = taskman           (one package level up)
  ..models = taskman.models
```

The key nuance is what the dots count. Relative imports count levels of the **package hierarchy**, not literal filesystem steps. They also work only when the module is imported **as part of a package** — through `import` from elsewhere, or through `python -m package.module`.

Run the file directly as a script (`python taskman/cli/app.py`), and the interpreter has no idea which package that file belongs to. Then `from .commands import ...` fails with `ImportError: attempted relative import with no known parent package`.

Absolute imports (`from taskman.models import Task`) do not have this problem. They always resolve from the root of `sys.path`, or from the installed package, no matter how the current file was launched.

**How this differs from ES modules.** ES (ECMAScript) is the standard that defines JavaScript. An ES module import, in Node too, is an explicit **path** (`./foo.js`, `../bar.js`) that literally mirrors the filesystem. A Python relative import is a step through the **package hierarchy**. That hierarchy usually matches the directory structure, but conceptually it is a different thing.

The two coincide 99% of the time. The idea "number of dots = package levels", not "directory levels", becomes visible exactly at the edge cases, such as running a file directly.

There is a second difference. Exports in JS/TS are explicit and per-symbol (`export function foo`), so you can import only what was exported. In Python **everything** without a leading `_` is importable by default. The `__all__` list and the underscore convention are curation for the reader, not privacy enforced by the language.

**venv — going deeper.** Beyond `activate`/`deactivate` (chapter 00), a package with real structure benefits from:

```bash
pip install -e .        # editable install — the package's code is picked up live,
                         # no reinstall needed after every edit;
                         # the counterpart of npm link / a workspace package in a monorepo
pip list                # what's installed in the current venv
pip show taskman        # metadata for one specific installed package
```

An editable install is not a copy of files into site-packages. It is a special "pointer" that tells the interpreter where to look for this package's modules: right here, on disk, at this path. Changes to the source are visible immediately, with no need to re-run `pip install`.

**requirements.txt vs pyproject.toml + poetry/uv.** `requirements.txt` is a flat list of lines like `requests==2.31.0`. Historically it was either hand-written or generated with `pip freeze > requirements.txt`. Two things it does not have:

- Any notion of "direct dependency" versus "transitive dependency".
- Hashes for integrity verification.

So it is a snapshot of what happens to be installed right now, not a declaration of what should be installed.

`pyproject.toml` (chapter 00) declares dependencies. But **on its own**, with just `pip` and `setuptools`, it does not produce a real lockfile with a resolved transitive dependency graph. Chapter 00 already flagged that limitation.

Tools like **poetry** and **uv** add a proper lockfile on top of `pyproject.toml` — `poetry.lock` or `uv.lock`. It pins exact versions and hashes for the whole tree. That is the direct counterpart of `package-lock.json`, `yarn.lock` and `pnpm-lock.yaml`.

As of 2026, `uv` is by far the fastest and most commonly recommended path. It is written in Rust and replaces `pip`, `venv` and much of poetry's functionality at once. This course deliberately sticks to plain `pip` and `venv`, so that you do not depend on a third-party tool before the fundamentals are solid.

### Parallels with JS/TS/Node:

- A module ~ a file with ES-module semantics: the unit of import in both languages. A package is closest to an npm package with an `index.js` barrel file. But executing `__init__.py` on submodule import is a language guarantee, not a resolver convention like `index.js`.
- Explicit `export` in JS/TS vs. "everything public by default" in Python. The `__all__` list and the leading underscore are a curation convention for the reader and for `import *`, not privacy enforced by the language. Under `mypy --strict` that same `__all__` also decides what a package re-exports, which brings it closer to a real `export` list.
- Dots in a relative import (`.`/`..`) are levels of the **package hierarchy**, not literal `./`/`../` filesystem steps like in Node. Relative imports simply do not work when the file is run directly as a script. They work only when it is imported as part of a package.
- `requirements.txt` ~ an old list with no lock semantics, hand-maintained or produced by `pip freeze`. The pair `pyproject.toml` + `poetry`/`uv` ~ `package.json` + `package-lock.json`/`uv.lock`, with real dependency resolution.

## What we're adding to the project

We're splitting the monolithic `main.py` into a `taskman` package with three subpackages:

- `models/` — `Priority` and `Task`.
- `storage/` — the in-memory store.
- `cli/` — argparse, the command handlers and `main()`.

At the same time the project moves to a **src layout** (`src/taskman/...`), the move promised back in chapter 00. Then `pyproject.toml` gets a build section (`[build-system]`, `[tool.setuptools.packages.find]`) and a `[project.scripts]` section. After `pip install -e .` the `taskman` command then works as a real installed command-line interface (CLI) tool, not only through `python main.py`.

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
4. Split the CLI layer into three modules:
   - `cli/parser.py` — `build_parser`.
   - `cli/commands.py` — `log_command`, the three handlers, `COMMAND_HANDLERS`.
   - `cli/app.py` — `main()`, wiring `parser` and `COMMAND_HANDLERS` together.
5. `__main__.py` should import `main` from `taskman.cli` and call it — this is exactly what makes `python -m taskman` possible.
6. Update `pyproject.toml`: add `[build-system]` (`setuptools`), `[tool.setuptools.packages.find] where = ["src"]`, and `[project.scripts] taskman = "taskman.cli:main"`.
7. Install the package in editable mode: `pip install -e .` inside an activated venv. Then confirm that **both** ways of running it work: `python -m taskman add "Buy milk"` and plain `taskman add "Buy milk"`.
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
    filtered = memory.filter_by_status(memory.tasks, args.status)
    result = memory.sort_tasks(filtered, args.sort)
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

`src/taskman/__init__.py` — left empty. The top-level package has nothing to re-export yet: the entire public surface is already described inside `models/`, `storage/` and `cli/`.

Key decisions:

- `from ..models import Priority, Task` in `storage/memory.py` — a relative import that goes up one level and back down into `models/`. It demonstrates that a relative import counts package levels (`taskman`), not literal filesystem steps.
- `from ..storage import memory` in `cli/commands.py`, rather than `from ..storage.memory import add_task, tasks, ...`. Here `memory` is imported as a namespace module, so calls read as `memory.add_task(...)` and `memory.tasks`. This is a deliberate choice for a module carrying mutable state (`tasks: list[Task]`). At the call site it is immediately obvious that the state lives in `storage.memory`, and not scattered across implicitly imported individual names.
- `[project.scripts] taskman = "taskman.cli:main"` — after `pip install -e .` in a venv, an executable `taskman` shows up at `.venv/bin/taskman`. It simply imports `taskman.cli` and calls `main`. This is exactly what npm does with the `"bin"` field in `package.json`.
- `[tool.setuptools.packages.find] where = ["src"]` — tells setuptools to look for packages under `src/`, not in the project root. Without this line a src layout is not auto-discovered: setuptools by default looks for packages right next to `pyproject.toml`.

## Check yourself

1. Why does `__init__.py` always run when you import a submodule, as in `import taskman.models.task`? You never explicitly imported the `taskman.models` package itself. How is that different from how `index.js` works in a JS module?
2. What do the dots in `from ..models import Task` actually count? What are they levels *of*, and why is that not the same thing as `../` in a filesystem path?
3. Run `python src/taskman/cli/app.py` directly and it fails with `ImportError: attempted relative import with no known parent package`. Yet `python -m taskman` works. Why, when both "run the Python code in this file" in some sense?
4. How does `pip install -e .` differ from a plain `pip install .` while you develop a package? What happens to source-code edits after each change?
5. Why isn't a `requirements.txt` generated via `pip freeze` a real lockfile in the sense that `package-lock.json` is one? What's fundamentally missing from it?

<details>
<summary>Answers</summary>

1. A package in Python isn't just "a folder of files". It is an object in `sys.modules`. Importing any submodule of a package **requires** first creating and initializing the package object itself, and initializing a package means running its `__init__.py`. This is a guarantee baked into the import machinery of the language itself (`importlib`), not a behavior you can opt out of. In JS, `index.js` is just a file the module resolver looks for by convention when a directory is imported as a whole. Import a specific file inside that directory directly (`import './foo/bar.js'`) and `index.js` is never touched at all. In Python the equivalent "bypass" is impossible: the package's `__init__.py` runs no matter what.
2. The dots count levels in the **package** tree — what is registered in `sys.modules` and defined by the `__init__.py` structure. They do not count the directory tree on disk. In practice these two trees almost always line up exactly, which is why the difference is invisible 99% of the time. Conceptually they differ. `from ..models import Task` means "go up one level from the package that holds **the current module**". It does not mean "go up one directory on disk". The distinction becomes visible precisely when a module is run outside of its package context (see question 3). In that situation the file simply has no information about which package it belongs to.
3. Running `python file.py` directly loads that file as the `__main__` module, **with no parent package**. The file has no information that it physically lives inside `taskman/cli/`. Running a file by its direct path does not go through the package-import machinery at all. And `from .commands import ...` needs to know the current package to count the dot from. There is no parent package, so there is nothing to count from, hence the error. The command `python -m taskman` is a fundamentally different launch mechanism. It uses `runpy`, finds the `taskman` package through the normal import machinery, and resolves `taskman.__main__` as the entry point. Then it executes that entry point **as part of** the `taskman` package, with a fully and correctly initialized package hierarchy. That is why relative imports inside it work.
4. `pip install .` copies the package's built files into the venv's site-packages. After that, edits to the project's source code have no effect on the installed copy until you reinstall the package. Editable mode, `pip install -e .`, instead places a lightweight pointer in site-packages that references the source directory (`src/`). When `taskman` is imported, the interpreter literally reads the files from wherever you are editing them. Changes are visible immediately, with no reinstall step.
5. `pip freeze` prints a list of **everything currently installed** in the environment, with versions. Three things are missing from that list. There is no distinction between "what I explicitly asked for" and "what got pulled in as a transitive dependency". There is no dependency graph, so you cannot tell what depends on what. And there are no cryptographic hashes confirming the integrity and origin of the downloaded files. A real lockfile — `package-lock.json`, `poetry.lock`, `uv.lock` — pins the entire resolved dependency tree, with hashes. A deterministic version-resolution algorithm generates it. It is not a side effect of whatever happened to be installed in this particular environment when `freeze` ran.

</details>

## Common mistake

The most common mistake at this stage is running one of the package's files directly as a script while debugging. That means `python src/taskman/cli/app.py`, or, even more often, hitting "Run" on a specific file in an IDE. The result is `ImportError: attempted relative import with no known parent package`.

A developer used to Node does not expect this. There `node ./src/cli/app.js` works with no extra conditions, because Node resolves `require`/`import` relative to wherever it was launched from. Nothing in that experience suggests that *how* you launch a file can change whether the imports inside it work at all.

The right fix isn't to swap relative imports for absolute ones "just to make it run". Run the package the way it is meant to be run: through `python -m taskman`, or, once installed, through the generated `taskman` command. Always as part of the package, never as a standalone file.

The second common trip-up is forgetting `[tool.setuptools.packages.find] where = ["src"]` when moving to a src layout. You then get an empty or incorrectly assembled package after `pip install -e .`. By default setuptools looks for packages right next to `pyproject.toml`, that is, in the project root, not inside `src/`.

The symptom usually isn't obvious right away. The install "succeeds" with no errors, but `import taskman` either cannot find the package at all, or finds the wrong thing. The reason: setuptools' default package auto-discovery is built for a flat layout, and it does not look inside `src/` unless told to explicitly.
