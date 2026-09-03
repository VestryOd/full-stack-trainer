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

`else` is not about "otherwise we caught an exception". It means code that should run only when `try` succeeded, but should not itself count as part of `try`. That makes two things easy to tell apart. One is "this line might raise the thing I am catching". The other is "this line uses the result and might raise something else, which I am not catching here". In Python `finally` behaves exactly like `finally` in JS.

**Exception hierarchy.** All exceptions inherit from `BaseException`. But application code should almost always catch, or subclass, `Exception`. That is a direct child of `BaseException` which **excludes** `SystemExit`, `KeyboardInterrupt` and `GeneratorExit`.

So `except Exception:` will not catch `Ctrl+C` or `sys.exit()`, and that split is deliberate. An overly broad `except BaseException:`, or a bare `except:`, is considered bad practice for one reason. It silently swallows process-termination signals that are supposed to propagate to the top.

```python
try:
    ...
except (ValueError, TypeError) as e:   # multiple types in one except — a tuple
    ...
except Exception as e:                  # a broader type — must come AFTER the specific ones
    ...
```

Order matters. `except` clauses are checked top to bottom, and the first one matching via `isinstance` catches the exception. Write a broad `except Exception:` before a specific `except ValueError:` and the second block never fires. That is unreachable code, and the interpreter gives no warning about it.

**Exception groups and `except*`.** Python 3.11 added a way to raise several exceptions at once. An `ExceptionGroup` wraps a list of exceptions, and the new `except*` clause matches them by type inside the group.

```python
try:
    raise ExceptionGroup("two failures", [ValueError("bad id"), TypeError("bad type")])
except* ValueError as eg:
    print(f"value errors: {eg.exceptions}")   # (ValueError('bad id'),)
except* TypeError as eg:
    print(f"type errors: {eg.exceptions}")    # (TypeError('bad type'),)
```

Both `except*` blocks run here, and that is the point. A plain `except` picks exactly one branch, while `except*` handles every matching subgroup of the same group. A group exposes its contents as the tuple `.exceptions`, plus the methods `.subgroup(condition)` and `.split(condition)` for taking it apart by hand.

The `BaseException` split from above repeats here, one level up. `ExceptionGroup` extends `Exception`, so `except Exception:` catches it. `BaseExceptionGroup` extends `BaseException` and can wrap anything at all, including a `KeyboardInterrupt`. So `except Exception:` does not catch that one, and this is the whole reason there are two classes.

Choosing between them is usually not your job. The `BaseExceptionGroup` constructor returns an `ExceptionGroup` when every wrapped exception is an `Exception` instance. The `ExceptionGroup` constructor is the strict one, and raises `TypeError` if any contained exception is not an `Exception` subclass.

In practice you meet groups through `asyncio.TaskGroup`, also new in 3.11. When several tasks in one group fail, their exceptions are combined into a group and raised together. One task failing no longer hides the others. There is one exception to that. A `KeyboardInterrupt` or a `SystemExit` inside a task is re-raised as itself, not wrapped in a group.

This course uses `asyncio.gather` (chapter 12) rather than `TaskGroup`. The `gather` function predates groups. It raises the first exception, or collects them into an ordinary list with `return_exceptions=True`.

**Custom exceptions.** These inherit from `Exception` (or a more specific built-in where appropriate) and, like any class, can carry extra data:

```python
class TaskManError(Exception):
    """Base class for all taskman domain errors."""


class TaskNotFoundError(TaskManError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id {task_id} not found")
        self.task_id = task_id
```

The base class `TaskManError` gives you a single catch point for "any error from our domain", written as `except TaskManError:`. You never have to enumerate every concrete subclass. People often emulate the same thing in JS with `class AppError extends Error {}` plus an `instanceof AppError` check. In Python this is not an emulation: catching by type hierarchy is the language's own mechanism.

**Parallel with JS: `throw`/`catch` aren't typed at the language level.** In JS you can throw *anything* — `throw "boom"`, `throw 42`, `throw { code: 500 }`. A single `catch (e)` catches all of it, with no type-based filtering. Telling error types apart inside `catch` means manual `if (e instanceof TypeError)` checks.

In Python `raise` requires an object that is an instance of a `BaseException` subclass. Write `raise 42` and you get `TypeError: exceptions must derive from BaseException`. The language enforces that, not a convention. And multiple `except SpecificError:` clauses give you type-based dispatch **at the syntax level**, instead of manual `if`/`instanceof` checks inside one catch block.

**Context managers and the `__enter__`/`__exit__` protocol.** `with expr as name:` is not a new language primitive layered "on top of" `try/finally`. It is an explicit protocol. The example below locks a file with `fcntl.flock`. That is the standard Unix call that stops two processes writing to the same file at once:

```python
import fcntl


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

**`fcntl` is Unix-only.** The standard library documents `fcntl` as available on Unix, so `import fcntl` fails on Windows with `ModuleNotFoundError`. Windows has its own call in the standard library: `msvcrt.locking(fd, mode, nbytes)`. Pass `msvcrt.LK_LOCK` for a blocking lock, and `msvcrt.LK_UNLCK` to release it.

The two calls are not interchangeable. The `flock` call locks the whole file, while `msvcrt.locking` locks a byte range from the current file position.

If you are on Windows, there are two workable paths. Run the exercise inside Windows Subsystem for Linux, or in a Linux container, which is what the rest of the course assumes anyway. Or replace the two `fcntl` calls with the `portalocker` package, a third-party wrapper that hides this platform split behind one API.

The `with` statement calls `__enter__()` and binds its return value to `name`. When the block exits, normally or through an exception, `__exit__(exc_type, exc_value, traceback)` is called. That happens **always**, exactly like `finally`.

An important nuance: if `__exit__` returns a truthy value, an exception raised inside the `with` block gets **suppressed** and never reaches the caller. That is a deliberate capability of the protocol, not a side effect. By default, when `__exit__` returns `None` or nothing at all, the exception keeps propagating once `__exit__` has finished.

The value of the protocol is precisely that it is **reusable**. The logic for "how to correctly acquire and release a resource" is written once, in one class. It is not copy-pasted as `try/finally` at every call site that needs the resource. In purpose this is the direct counterpart of `try/finally` in JS: guaranteed cleanup. The difference is that the cleanup logic itself is factored out and reusable.

**`contextlib`.** For simple cases you don't need a whole class. The `@contextmanager` decorator turns a generator into a context manager. The code before `yield` is `__enter__`, `yield` hands back the value for `as`, and the code after `yield` (usually in a `finally`) is `__exit__`:

```python
import fcntl
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

**JS: `using`/`Symbol.dispose`.** TC39 is the committee that standardises JavaScript. Its fairly recent "Explicit Resource Management" proposal gave JS/TS a mechanism in the same spirit: `using resource = getResource();`. There is also `await using` for async resources.

Both are built on `Symbol.dispose` and `Symbol.asyncDispose`. Same idea: deterministic, reusable resource cleanup on scope exit.

The difference is mostly historical. The `with` statement has existed in Python since the mid-2000s and permeates the entire standard library: files, locks, database transactions, network connections. In JS/TS `using` is a noticeably newer part of the language, not yet as universally adopted across the library ecosystem.

### Parallels with JS/TS/Node:

- JS's `try` has no `else` clause — only `try/catch/finally`.
- JS's `catch` catches everything, with no type-based filtering at the syntax level. Telling error types apart means manual `instanceof` checks. In Python `except SpecificError:` gives you type filtering built into the language.
- In JS you can throw any value (`throw 42`); in Python, `raise` requires a `BaseException` subclass instance — enforced at runtime.
- `with`/`__enter__`/`__exit__` ~ the newer `using`/`Symbol.dispose` in JS/TS, from the TC39 Explicit Resource Management proposal. Same idea, but Python has had this for two decades longer and uses it far more pervasively.
- `ExceptionGroup` plus `except*` (Python 3.11) ~ `AggregateError` in JS, which `Promise.any()` rejects with once every promise has rejected. Both carry a list of errors instead of a single one. JS has no syntax comparable to `except*`, so you loop over `error.errors` by hand.

## What we're adding to the project

We're replacing the `None` sentinel for "task not found" with a real exception hierarchy: `TaskManError` and `TaskNotFoundError`. The command-line interface (CLI) handler catches it with `try/except`, instead of a manual `if task is None` check.

On top of that, `log_command` now also appends a line to `taskman.log`, not just prints to stderr. That file is protected from concurrent writes across processes by a custom `FileLock` context manager. `FileLock` implements the `__enter__`/`__exit__` protocol on top of the file lock `fcntl.flock`.

## Practical exercise

1. In `models/errors.py`, define `TaskManError(Exception)` (the base class for all domain errors) and `TaskNotFoundError(TaskManError)`, storing `task_id` and a human-readable message. Re-export both from `models/__init__.py`.
2. In `storage/memory.py`, add `get_task(task_id) -> Task`. It uses the existing `find_task`, which is unchanged and still returns `Task | None`, and raises `TaskNotFoundError` if the task isn't found. Change `mark_done` to use `get_task` instead of a manual `None` check, so it now either returns a `Task` or lets `TaskNotFoundError` propagate.
3. In `cli/commands.py`, change `handle_done`. Wrap the call to `memory.mark_done(args.id)` in `try/except TaskNotFoundError`. Print a clean error message to `sys.stderr` instead of checking `if task is None`.
4. Create `logging_utils.py` with two things. One is a `FileLock` class implementing `__enter__`/`__exit__` around `fcntl.flock`, an exclusive write lock. The other is an `append_log(message: str) -> None` function that uses `FileLock` via `with`. On Windows, use `msvcrt.locking` or `portalocker` in place of `fcntl`, as the theory section describes.
5. Call `append_log(...)` from `log_command` (alongside the existing `print(..., file=sys.stderr)` calls), so every command run leaves a trace in `taskman.log`.

Things to think through:

- What happens to the file lock if the code inside `with FileLock(...) as f:` raises an exception? Does the file stay locked forever? Why not (assuming `__exit__` is written correctly)?
- Why keep `find_task` (returning `Task | None`) separate from `get_task` (raising an exception), now that we have a custom exception? When is one form more appropriate than the other?

## Worked solution

Only the files below change or get added. Unchanged from chapter 05:

- `models/task.py` and `storage/__init__.py`
- `cli/parser.py`, `cli/app.py`, `cli/__init__.py`
- `__main__.py` and `pyproject.toml`

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
    filtered = memory.filter_by_status(memory.tasks, args.status)
    result = memory.sort_tasks(filtered, args.sort)
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

- `get_task` is built on top of `find_task`, and does not replace it. The `find_task` function stays the "soft" lookup. It returns `None` where a missing task is a normal, expected outcome rather than an error. And `get_task` is the "hard" one. It raises where a missing task is exceptional and the caller must either handle it or let the process crash. Real code needs both, and settling permanently on one would close the door on the other usage pattern.
- `TaskNotFoundError` stores `task_id` as an attribute, not just baked into the message text. Suppose this same exception has to be handled somewhere else later — for example in the FastAPI chapter, where `TaskNotFoundError` turns into an HTTP 404. Then `error.task_id` gives structured access to the error's data, instead of parsing the message string.
- `FileLock.__exit__` returns nothing, an implicit `None`, and that is a deliberate choice. If writing to the log fails with an exception, that exception should be visible, not silently swallowed by the locking protocol. The `__exit__` method only guarantees that the file gets unlocked and closed, not that errors get hidden.
- `append_log` is called both before and after the wrapped command runs, inside `log_command`. If the command itself crashes with an unhandled exception, the log will contain "running" but not "done". That is useful diagnostic information in itself: the command started, but did not finish cleanly.

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
4. Describe in your own words what `with expr as name:` actually does "under the hood". Which two methods get called, and exactly when? And what happens if the code inside the block raises an exception?
5. If `__exit__` returns `True`, what happens to an exception raised inside the `with` block? Why is that sometimes useful, and sometimes a dangerous trap?
6. Python 3.11 added both `ExceptionGroup` and `BaseExceptionGroup`. Why two classes instead of one, and which of the two does `except Exception:` catch?

<details>
<summary>Answers</summary>

1. The `print("no exception, result is valid")` line runs only if `try` completed **without** an exception. That means `compute()` raised neither `ValueError` nor anything else. If `compute()` raised `ValueError`, the `except` block runs and `else` is skipped entirely. Now compare that with putting the `print(...)` as the last line inside `try`. In that version, `print(...)` itself, or anything between a successful `compute()` and the `print`, might raise the same type of exception that `except` catches. It would then be caught by that `except` by mistake. Logically it belongs to the handling of the result, not to the computation. The `else` clause rules out that mix-up. Code in `else` is guaranteed to run only after a successful `try`. But exceptions from it are no longer caught by the `except` attached to that same `try`.
2. `KeyboardInterrupt` inherits directly from `BaseException`, not from `Exception`. That is a deliberate language design decision. `Exception` is meant for errors that application code is generally expected to handle itself: a network error, invalid data and so on. The descendants of `BaseException` alone — `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` — are signals for **terminating the process or a generator**. In the vast majority of cases they should not be caught by a broad `except`. Otherwise `Ctrl+C` or `sys.exit()` would simply "disappear" inside some incidental `try/except Exception:` buried deep in the code.
3. The second block (`except ValueError as e:`) really never runs. `ValueError` is a subclass of `Exception`, so any `ValueError` is already caught by the first, broader `except Exception as e:`. The interpreter never gets to the second block: `except` clauses are checked in order, top to bottom, and the first match wins. There is no warning at parse time either. Syntactically, `except Exception:` and `except ValueError:` are just two independent conditional blocks. Proving that they are mutually unreachable would in general require full type analysis, and CPython does not do that at this stage. A static analyzer such as mypy could catch it in principle. In practice most linters do not check for it out of the box.
4. `with expr as name:` first evaluates `expr`, then calls `__enter__()` on the result. Whatever that call returns gets bound to `name`. Then the body of the `with` block runs. When the block ends, normally or through an exception, `__exit__(exc_type, exc_value, traceback)` is called on that same object. If there was no exception, all three arguments are `None`. If there was one, the type, the exception itself and the traceback are passed in. The call to `__exit__` is **guaranteed**, even if the block was left through an exception or a `return`/`break`/`continue`. It is every bit as reliable as `finally`.
5. If `__exit__` returns `True`, or any truthy value, an exception raised inside the `with` block gets **suppressed**. Code after the `with` continues as if no exception happened at all. This is useful when the context manager itself knows how to handle a specific class of error. An example is a context manager built to ignore one expected, known exception type, which is exactly how `contextlib.suppress` works. The danger sits in the default. When `__exit__` does not explicitly return anything, it returns `None` and the exception keeps propagating. A developer might carelessly write `return True` "for symmetry", or copy code from elsewhere without understanding why the `True` is there. That risks silently swallowing real errors that were supposed to reach the calling code.
6. `except Exception:` catches an `ExceptionGroup` and does not catch a `BaseExceptionGroup`. That is the entire reason for having two classes. `ExceptionGroup` extends `Exception`, while `BaseExceptionGroup` extends `BaseException`. The split repeats the logic of question 2 one level up. A group wrapping a `KeyboardInterrupt` must not be swallowed by a broad `except Exception:`, exactly as a bare `KeyboardInterrupt` must not be. Only `BaseExceptionGroup` is allowed to wrap something that is not an `Exception` at all. The `ExceptionGroup` constructor raises `TypeError` on such an attempt. In the other direction the choice is made for you. The `BaseExceptionGroup` constructor hands back an `ExceptionGroup` whenever everything it wraps is an `Exception` instance.

</details>

## Common mistake

The most common mistake when first working with exceptions in Python is a bare `except:`, with no type at all. The same goes for `except Exception:` where a specific check is needed. It is a reflex carried over from JS. There the single `catch (e)` already catches everything. The developer is used to sorting out the error inside `catch`, rather than picking the right type at the syntax level.

In Python a broad `except:` or `except Exception:` silently swallows errors that were never supposed to happen at that spot in the code. Say, a `TypeError` from a typo in an attribute name. A real bug then hides behind the appearance of "we handled the error".

In this project it also gets in the way of growth. Suppose a `TaskAlreadyDoneError`, or any other new domain error, shows up later. A broad `except Exception:` in `handle_done` will catch it exactly the way it catches `TaskNotFoundError`, and print the same generic message. That will not help the user understand what went wrong.

The second common mistake is less obvious, and it shows up exactly where file handling and locking are involved. It is the assumption that once code is wrapped in `with`, no `try/except` around the block is needed at all. The reason given: "the context manager handles everything".

A context manager only guarantees **resource cleanup**: the file gets closed, the lock gets released. It does not swallow or handle the exception automatically, unless it was explicitly written to do so. The `__exit__` example above returns nothing, so it does not.

An error inside `with FileLock(...) as f: f.write(...)` still propagates outward after `__exit__` releases the lock. The file is simply guaranteed to end up in a consistent, unlocked state, rather than staying locked forever.
