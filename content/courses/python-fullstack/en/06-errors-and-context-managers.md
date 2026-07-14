# Exceptions and context managers

## Theory

**`try`/`except`/`else`/`finally`.** Python has one more clause than JS:

```python
try:
    value = risky_call()
except ValueError as e:
    print(f"bad value: {e}")
else:
    print(f"success: {value}")   # runs ONLY if try raised nothing
finally:
    print("cleanup always runs")  # runs ALWAYS — exception or not,
                                    # return inside try/except or not
```

`else` isn't about "otherwise caught an exception" — it's "code that should run only when `try` succeeded, but shouldn't itself be considered part of `try`." This makes it easy to tell apart "this line might raise the thing I'm catching" from "this line uses the result and might raise something else entirely, which I'm not trying to catch here." `finally` in Python behaves exactly like `finally` in JS.

**Exception hierarchy.** All exceptions inherit from `BaseException`, but application code should almost always catch/subclass `Exception` — a direct child of `BaseException` that **excludes** `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`. `except Exception:` won't catch `Ctrl+C` or `sys.exit()` — and that split is deliberate: an overly broad `except BaseException:` (or a bare `except:`) is considered bad practice precisely because it silently swallows process-termination signals that are supposed to propagate to the top.

```python
try:
    ...
except (ValueError, TypeError) as e:   # multiple types in one except — a tuple
    ...
except Exception as e:                  # a broader type — must come AFTER the specific ones
    ...
```

Order matters: `except` clauses are checked top to bottom, and the first one matching via `isinstance` catches the exception — if you write a broad `except Exception:` before a specific `except ValueError:`, the second block never fires (unreachable code, with no warning from the interpreter).

**Custom exceptions.** These inherit from `Exception` (or a more specific built-in where appropriate) and, like any class, can carry extra data:

```python
class TaskManError(Exception):
    """Base class for all taskman domain errors."""


class TaskNotFoundError(TaskManError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id {task_id} not found")
        self.task_id = task_id
```

The base class `TaskManError` gives you a single catch point for "any error from our domain" (`except TaskManError:`) without having to enumerate every concrete subclass — the same thing people often try to emulate in JS with `class AppError extends Error {}` plus an `instanceof AppError` check, except in Python this isn't an emulation — it's using the language's native type-hierarchy-based catching mechanism directly.

**Parallel with JS: `throw`/`catch` aren't typed at the language level.** In JS you can throw *anything* — `throw "boom"`, `throw 42`, `throw { code: 500 }` — and a single `catch (e)` catches it all, with no type-based filtering at all; distinguishing error types inside `catch` means manual `if (e instanceof TypeError)` checks. In Python, `raise` requires an object that's a `BaseException` subclass instance — `raise 42` raises `TypeError: exceptions must derive from BaseException`, enforced by the language, not by convention. And multiple `except SpecificError:` clauses give you type-based dispatch **at the syntax level**, rather than manual `if`/`instanceof` checks inside one catch block.

**Context managers and the `__enter__`/`__exit__` protocol.** `with expr as name:` isn't a new language primitive layered "on top of" `try/finally` — it's an explicit protocol:

```python
class FileLock:
    def __init__(self, path):
        self._path = path
        self._file = None

    def __enter__(self):
        self._file = open(self._path, "a")
        fcntl.flock(self._file, fcntl.LOCK_EX)   # blocks until the file is free
        return self._file

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
        # returns nothing (None is falsy) => any exception that occurred
        # keeps propagating after __exit__ runs

with FileLock("taskman.log") as log_file:
    log_file.write("hello\n")
```

`with` calls `__enter__()` and binds its return value to `name`; when the block exits (normally or via an exception), `__exit__(exc_type, exc_value, traceback)` is called — **always**, exactly like `finally`. An important nuance: if `__exit__` returns a truthy value, an exception that occurred inside the `with` block gets **suppressed** (it never reaches the caller) — that's a deliberate capability of the protocol, not a side effect; by default (returning `None`, or nothing) the exception keeps propagating once `__exit__` has finished.

The value of the protocol is precisely that it's **reusable**: the logic for "how to correctly acquire and release a resource" is written once, in one class, instead of being copy-pasted as `try/finally` at every call site that needs the resource. It's the direct counterpart of `try/finally` in JS in terms of purpose (guaranteed cleanup), but with the cleanup logic itself factored out and made reusable.

**`contextlib`.** For simple cases you don't need a whole class — `@contextmanager` turns a generator into a context manager: the code before `yield` is `__enter__`, `yield` hands back the value for `as`, and the code after `yield` (usually in a `finally`) is `__exit__`:

```python
from contextlib import contextmanager

@contextmanager
def file_lock(path):
    f = open(path, "a")
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        yield f
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
```

This is the same `FileLock`, just without an explicit class — shorter for one-off cases, but less explicit about the protocol itself. In this chapter's project we'll write the class-based version specifically to see the `__enter__`/`__exit__` mechanics directly, rather than hidden behind a generator.

**JS: `using`/`Symbol.dispose`.** With the relatively recent TC39 "Explicit Resource Management" proposal, JS/TS gained a similarly-spirited mechanism — `using resource = getResource();` (and `await using` for async resources), built on `Symbol.dispose`/`Symbol.asyncDispose`. Same idea: deterministic, reusable resource cleanup on scope exit. The difference is mostly historical: `with` has existed in Python since the mid-2000s and permeates the entire standard library (files, locks, DB transactions, network connections), while `using` in JS/TS is a noticeably newer part of the language, not yet as universally adopted across the library ecosystem.

### Parallels with JS/TS/Node:

- JS's `try` has no `else` clause — only `try/catch/finally`.
- JS's `catch` catches everything, with no type-based filtering at the syntax level — distinguishing error types means manual `instanceof` checks; in Python, `except SpecificError:` gives you type filtering built into the language.
- In JS you can throw any value (`throw 42`); in Python, `raise` requires a `BaseException` subclass instance — enforced at runtime.
- `with`/`__enter__`/`__exit__` ~ the newer `using`/`Symbol.dispose` in JS/TS (TC39 Explicit Resource Management) — same idea, but Python has had this for two decades longer and uses it far more pervasively.

## What we're adding to the project

We're replacing the `None` sentinel for "task not found" with a real exception hierarchy — `TaskManError`/`TaskNotFoundError` — and catching it in the CLI handler with `try/except` instead of a manual `if task is None` check. On top of that, `log_command` now not only prints to stderr but also appends a line to `taskman.log`, protected from concurrent writes across processes by a custom `FileLock` context manager implementing the `__enter__`/`__exit__` protocol on top of file locking (`fcntl.flock`).

## Practical exercise

1. In `models/errors.py`, define `TaskManError(Exception)` (the base class for all domain errors) and `TaskNotFoundError(TaskManError)`, storing `task_id` and a human-readable message. Re-export both from `models/__init__.py`.
2. In `storage/memory.py`, add `get_task(task_id) -> Task`, which uses the existing `find_task` (unchanged, still returns `Task | None`) and raises `TaskNotFoundError` if the task isn't found. Change `mark_done` to use `get_task` instead of a manual `None` check, so it now either returns a `Task` or lets `TaskNotFoundError` propagate.
3. In `cli/commands.py`, change `handle_done`: wrap the call to `memory.mark_done(args.id)` in `try/except TaskNotFoundError`, and print a clean error message to `sys.stderr` instead of checking `if task is None`.
4. Create `logging_utils.py` with a `FileLock` class implementing `__enter__`/`__exit__` around `fcntl.flock` (an exclusive write lock), and an `append_log(message: str) -> None` function that uses `FileLock` via `with`.
5. Call `append_log(...)` from `log_command` (alongside the existing `print(..., file=sys.stderr)` calls), so every command run leaves a trace in `taskman.log`.

Things to think through:

- What happens to the file lock if the code inside `with FileLock(...) as f:` raises an exception? Does the file stay locked forever? Why not (assuming `__exit__` is written correctly)?
- Why keep `find_task` (returning `Task | None`) separate from `get_task` (raising an exception), now that we have a custom exception? When is one form more appropriate than the other?

## Worked solution

Only the following files change or get added; `models/task.py`, `storage/__init__.py`, `cli/parser.py`, `cli/app.py`, `cli/__init__.py`, `__main__.py`, and `pyproject.toml` stay the same as in chapter 05.

`src/taskman/models/errors.py` (new file):

```python
class TaskManError(Exception):
    """Base class for all taskman domain errors."""


class TaskNotFoundError(TaskManError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id {task_id} not found")
        self.task_id = task_id
```

`src/taskman/models/__init__.py` (updated):

```python
from .errors import TaskManError, TaskNotFoundError
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = [
    "Priority",
    "Task",
    "PRIORITY_CHOICES",
    "TaskManError",
    "TaskNotFoundError",
]
```

`src/taskman/storage/memory.py` (updated):

```python
from ..models import Priority, Task, TaskNotFoundError

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


def get_task(task_id: int) -> Task:
    task = find_task(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


def mark_done(task_id: int) -> Task:
    task = get_task(task_id)
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

`src/taskman/logging_utils.py` (new file):

```python
import fcntl
from pathlib import Path

LOG_PATH = Path("taskman.log")


class FileLock:
    """Exclusive lock over a file, used to serialize writes across processes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file = None

    def __enter__(self):
        self._file = open(self._path, "a")
        fcntl.flock(self._file, fcntl.LOCK_EX)
        return self._file

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()


def append_log(message: str) -> None:
    with FileLock(LOG_PATH) as log_file:
        log_file.write(message + "\n")
```

`src/taskman/cli/commands.py` (updated):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import memory


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        append_log(f"running: {namespace.command}")
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        append_log(f"done: {namespace.command}")
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
    try:
        task = memory.mark_done(args.id)
    except TaskNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return
    print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}
```

Key decisions:

- `get_task` is built on top of `find_task`, not a replacement for it — `find_task` stays the "soft" lookup (returns `None`, for cases where a missing task is a normal, expected outcome, not an error), while `get_task` is the "hard" one (raises where a missing task is exceptional and the caller must handle it or let the process crash). Real code needs both — settling permanently on just one would close the door on the other usage pattern.
- `TaskNotFoundError` stores `task_id` as an attribute, not just baked into the message text — if this same exception needs to be handled somewhere else later (for example, in the FastAPI chapter, where `TaskNotFoundError` turns into an HTTP 404), `error.task_id` gives structured access to the error's data instead of parsing the message string.
- `FileLock.__exit__` returns nothing (implicit `None`) — a deliberate choice: if writing to the log fails with an exception, that exception should be visible, not silently swallowed by the locking protocol; `__exit__` only guarantees the file gets unlocked and closed, not that errors get hidden.
- `append_log` is called both before and after the wrapped command runs, inside `log_command` — if the command itself crashes with an unhandled exception, the log will contain "running" but not "done," which is itself useful diagnostic information (the command started but didn't finish cleanly).

## Check yourself

1. Given:
   ```python
   try:
       result = compute()
   except ValueError:
       result = None
   else:
       print("no exception, result is valid")
   finally:
       print("always runs")
   ```
   Under what conditions does `print("no exception, result is valid")` run, and under what conditions doesn't it? How is this different from just writing that `print(...)` as the last line inside `try`?
2. Why doesn't `except Exception:` catch `KeyboardInterrupt` (`Ctrl+C`), even though `KeyboardInterrupt` is also an exception? What does that say about the `BaseException` vs. `Exception` hierarchy?
3. What happens if the code has `except Exception as e:` first, followed by `except ValueError as e:`? Why does the second block never run, and why doesn't the interpreter warn about it while parsing the code?
4. Describe in your own words what `with expr as name:` actually does "under the hood" — which two methods get called, exactly when, and what happens if the code inside the block raises an exception?
5. If `__exit__` returns `True`, what happens to an exception raised inside the `with` block? Why is that sometimes useful, and sometimes a dangerous trap?

<details>
<summary>Answers</summary>

1. `print("no exception, result is valid")` only runs if `try` completed **without** an exception — i.e., `compute()` didn't raise `ValueError` (or anything else). If `compute()` raised `ValueError`, the `except` block runs, and `else` is skipped entirely. The difference from "just put `print(...)` as the last line inside `try`" is that in that case, if `print(...)` itself (or anything between a successful `compute()` and the `print`) raised the same type of exception the `except` catches, it would be mistakenly caught by that `except`, even though logically it belongs to the follow-up handling of the result, not the computation itself. `else` explicitly rules out that mix-up: code in `else` is guaranteed to run only after a successful `try`, but exceptions from it are no longer caught by the `except` attached to that same `try`.
2. `KeyboardInterrupt` inherits directly from `BaseException`, not `Exception` — a deliberate language design decision: `Exception` is meant for errors that application code is generally expected to be able to handle itself (a network error, invalid data, and so on), while `BaseException`-only descendants (`KeyboardInterrupt`, `SystemExit`, `GeneratorExit`) are signals for **terminating the process or a generator**, which in the vast majority of cases shouldn't be caught by a broad `except`, or `Ctrl+C`/`sys.exit()` would simply "disappear" inside some incidental `try/except Exception:` buried deep in the code.
3. The second block (`except ValueError as e:`) really never runs, because `ValueError` is a subclass of `Exception`, and any `ValueError` will already be caught by the first, broader `except Exception as e:` before the interpreter even gets to checking the second block — `except` clauses are checked in order, top to bottom, and the first match wins. The interpreter doesn't warn about this at parse time because, syntactically, `except Exception:` and `except ValueError:` are just two independent conditional blocks; proving their mutual unreachability in general would require full-blown type analysis, which CPython doesn't do at this stage (unlike, say, a static analyzer such as mypy, which could in principle catch this — though in practice most linters don't check for it out of the box either).
4. `with expr as name:` first evaluates `expr`, then calls `__enter__()` on the result — whatever it returns gets bound to `name`. Then the body of the `with` block runs. When the block ends — whether normally or via an exception — `__exit__(exc_type, exc_value, traceback)` is called on that same object: if there was no exception, all three arguments are `None`; if there was one, the type, the exception itself, and the traceback are passed in. `__exit__` is called **guaranteed**, even if the block was left via an exception or a `return`/`break`/`continue` — every bit as reliably as `finally`.
5. If `__exit__` returns `True` (any truthy value), an exception that occurred inside the `with` block gets **suppressed** — code after the `with` continues as if no exception happened at all. This is useful when the context manager itself knows how to "normally" handle a specific class of error (for example, a context manager built specifically to ignore one expected, known exception type — which is how `contextlib.suppress` works). The danger is that, by default (when `__exit__` doesn't explicitly return anything, i.e. returns `None`), the exception keeps propagating — if a developer carelessly writes `return True` "for symmetry," or copies code from elsewhere without understanding why the `True` is there, they risk silently swallowing real errors that were supposed to reach the calling code.

</details>

## Common mistake

The most common mistake when first working with exceptions in Python is writing a bare `except:` (with no type at all) or `except Exception:` in places that actually need a specific check, carrying over the reflex from JS, where the single `catch (e)` already catches everything, and the developer is used to "sorting out the error inside catch" rather than picking the right type at the syntax level. In Python, a broad `except:`/`except Exception:` silently swallows errors that were never supposed to happen at that spot in the code (say, a `TypeError` from a typo in an attribute name), masking a real bug behind the appearance of "we handled the error" — and in this project it also gets in the way of growth: if a `TaskAlreadyDoneError` or any other new domain error shows up later, a broad `except Exception:` in `handle_done` will catch it exactly the same way it catches `TaskNotFoundError`, printing the same generic error message, which won't actually help the user understand what went wrong.

The second common mistake is less obvious, but shows up exactly where file handling and locking are involved: assuming that once code is wrapped in `with`, no additional `try/except` around the `with` block is needed at all "because the context manager handles everything." A context manager only guarantees **resource cleanup** (the file gets closed, the lock gets released) — it doesn't swallow or handle the exception automatically unless it was explicitly written to do so (as in the `__exit__` example above, which returns nothing). An error inside `with FileLock(...) as f: f.write(...)` still propagates outward after `__exit__` releases the lock — the file is just guaranteed to end up in a consistent, unlocked state, rather than staying locked forever.
