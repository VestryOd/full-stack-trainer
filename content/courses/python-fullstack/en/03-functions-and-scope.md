# Functions and scope

## Theory

**Functions are full first-class objects**, same as in JS. You can assign one to a variable, pass it as an argument, return it from another function, store it in a list or dict. There's almost no new mechanics here for a JS developer — the difference is mostly syntax (`def name():` instead of `function name() {}` or arrow functions).

```python
def double(x: int) -> int:
    return x * 2

operations = {"double": double}   # a function is just a value in a dict
operations["double"](21)          # 42
```

**`*args`/`**kwargs` in a function definition.** Chapter 02 used `*` in **assignment** (`first, *rest = [...]`) — the same idea works in a function signature, collecting "extra" arguments:

```python
def log(*args, **kwargs):
    print(args)     # a tuple of all positional arguments beyond the declared ones
    print(kwargs)    # a dict of all keyword arguments beyond the declared ones

log(1, 2, a=3, b=4)   # args=(1, 2), kwargs={"a": 3, "b": 4}
```

`*args` is the direct counterpart of JS rest parameters (`function log(...args)`). For `**kwargs` — keyword arguments collected into a `dict` — there is no direct JS equivalent at all. The closest in spirit is destructuring an options object (`function f({a, b}) {}`). But that unpacks one object passed as-is, rather than collecting every keyword argument of the call into a structure on the fly.

**Default parameters and the mutable-default trap.** The syntax looks like JS: `def f(x=5):` against `function f(x = 5) {}`. But the semantics of *when* the default is evaluated are fundamentally different. In JS, a default expression is evaluated **fresh on every call**. In Python, a default value is evaluated **once, at function-definition time**, and that same value is reused on every call:

```python
def add_item(item, bucket=[]):   # bucket is created once, at module import time
    bucket.append(item)
    return bucket

add_item(1)   # [1]
add_item(2)   # [1, 2]  — the same list as the first call!
```

If the default is immutable — `None`, a number, a string — there's no issue, because the value simply cannot be changed by reference. If the default is mutable (`list`, `dict`, `set`), every call that doesn't pass its own argument **shares the same object**. The idiomatic fix is `None` as the default, with a fresh object created inside the function body:

```python
def add_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

**Closures and LEGB scope.** Closures work the same way as in JS: a nested function can see the enclosing function's variables even after the enclosing function has returned. The name-lookup rule for **reads** is LEGB: **L**ocal → **E**nclosing → **G**lobal → **B**uilt-in, checked in that order, from the innermost scope outward.

The key difference from JS is what happens when you **assign** to a name inside a nested function. Python decides this while parsing the whole function body, ahead of execution. If a name is assigned anywhere in the function body, that name is **local to the entire function**, from its very first line. That holds even if the assignment appears physically later:

```python
counter = 0

def increment():
    counter += 1   # UnboundLocalError!
    return counter
```

`counter += 1` is an assignment, so `counter` is treated as local throughout `increment()`. But `+=` first **reads** the current value of `counter` to add 1 — and the local `counter` doesn't exist yet at that point. Hence `UnboundLocalError: local variable 'counter' referenced before assignment`.

You may want to say "this isn't a new local variable, it's modifying the outer one". For that there are two keywords: `global` for a module-level variable, and `nonlocal` for an enclosing function's variable in a closure:

```python
def make_counter():
    count = 0
    def increment():
        nonlocal count   # without this line — the same UnboundLocalError
        count += 1
        return count
    return increment

counter = make_counter()
counter()  # 1
counter()  # 2
```

This ambiguity simply doesn't exist in JS. `let`/`const` declare a variable explicitly, once, at the point of declaration. So any later `counter += 1` inside a nested function unambiguously means "assign to the outer variable that already exists". In JS the question "new local, or modify the outer one?" never comes up. The language always has an explicit declaration keyword: `let`, `const` or `var`.

Python has no separate declaration step at all: there is only assignment. With no explicit declaration, the compiler has to work out a name's "localness" by scanning the whole function body.

**Decorators — mechanics, not magic.** A decorator is just a function that takes a function and returns a function (usually a wrapper that runs code before/after calling the original):

```python
def shout(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result.upper()
    return wrapper

@shout
def greet(name):
    return f"hello, {name}"

greet("max")  # "HELLO, MAX"
```

`@shout` above `def greet` is exactly equivalent to writing `greet = shout(greet)` right after the function definition. There's no separate language mechanism beyond sugar for that one line.

Side effect: without extra care, `greet.__name__` after decorating becomes `"wrapper"`, not `"greet"`. The fix is to apply `functools.wraps(func)` to `wrapper`. It copies `__name__`, `__doc__` and other metadata from the original function. A full chapter on `functools` comes later (itertools/functools); this is the first, minimal introduction.

### Parallels with JS/TS/Node:

- Functions as values, closures — work almost exactly like JS; no new concept here, just different syntax.
- `*args` ~ rest parameters (`...args`). For `**kwargs` — keyword arguments collected into a `dict` — there is no direct JS equivalent. The closest in spirit is destructuring an options-object parameter, but that's a different mechanism.
- **A mutable default parameter is evaluated once**, at function-definition time, and reused on every call — in JS, the default expression is recomputed on every call. This behaves exactly backward from what a JS developer expects.
- Assigning to an outer-scope variable inside a nested function requires an explicit `nonlocal`/`global`. In JS, a variable from an enclosing closure is reassigned with no special syntax. That works because JS always declares a variable explicitly once, via `let`/`const`/`var`.

## What we're adding to the project

We're pulling the three `if/elif` branches out of `main()` into separate handler functions: `handle_add`, `handle_list`, `handle_done`. Each one gets wrapped in a `@log_command` decorator that prints to stderr which command is running and when it finished. That is a first step toward real logging for the command-line interface (CLI).

Full structured logging is out of scope for this course, but "a decorator on every command" is a standard pattern for CLI tools.

At the same time, command dispatch moves from `if/elif` to a dict of `{command name: handler function}`. That is a concrete illustration that functions in Python are values, just like strings or numbers.

## Practical exercise

1. Split the current logic in `main()` into three separate functions: `handle_add(args)`, `handle_list(args)`, `handle_done(args)`. Each takes an `argparse.Namespace` and does whatever the corresponding `if/elif` branch used to do.
2. Write a `log_command` decorator that wraps a handler function and prints two lines to `sys.stderr`. One goes before the call (`[log] running: <command>`), one after (`[log] done: <command>`). Use `*args, **kwargs` in the `wrapper` signature rather than a hardcoded single parameter. That way the decorator isn't tied to all wrapped functions sharing the exact same argument list.
3. Apply `functools.wraps` to `wrapper` so `handle_add.__name__` stays `"handle_add"` after decorating, not `"wrapper"`.
4. Apply `@log_command` to all three handlers.
5. Replace the `if/elif` dispatch in `main()` with a dict, `COMMAND_HANDLERS = {"add": handle_add, "list": handle_list, "done": handle_done}`, and call `COMMAND_HANDLERS[args.command](args)`.

Things to think through:

- `log_command`'s output goes to `sys.stderr`, not `sys.stdout` — why does that matter if someone runs `python main.py list | grep milk`?
- Why is it worth using `*args, **kwargs` in the decorator, even though every handler currently takes exactly one `args` parameter? What breaks if one handler later ends up taking two parameters instead?

## Worked solution

```python
import argparse
import functools
import sys

PRIORITY_ORDER = ["low", "medium", "high"]
PRIORITY_RANK = {name: rank for rank, name in enumerate(PRIORITY_ORDER)}

tasks: list[dict] = []


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        return result

    return wrapper


def add_task(text: str, priority: str = "medium") -> dict:
    task = {"id": len(tasks) + 1, "text": text, "done": False, "priority": priority}
    tasks.append(task)
    return task


def find_task(task_id: int) -> dict | None:
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def mark_done(task_id: int) -> dict | None:
    task = find_task(task_id)
    if task is not None:
        task["done"] = True
    return task


def filter_by_status(items: list[dict], status: str) -> list[dict]:
    if status == "all":
        return items
    want_done = status == "done"
    return [task for task in items if task["done"] == want_done]


def sort_tasks(items: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "priority":
        return sorted(items, key=lambda t: (-PRIORITY_RANK[t["priority"]], t["id"]))
    return sorted(items, key=lambda t: t["id"])


def format_task(task: dict) -> str:
    mark = "x" if task["done"] else " "
    return f"[{mark}] {task['id']} {task['text']} ({task['priority']})"


@log_command
def handle_add(args: argparse.Namespace) -> None:
    task = add_task(args.text, args.priority)
    print(f"Added: [{task['id']}] {task['text']} ({task['priority']})")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = sort_tasks(filter_by_status(tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
    else:
        for task in result:
            print(format_task(task))


@log_command
def handle_done(args: argparse.Namespace) -> None:
    task = mark_done(args.id)
    if task is None:
        print(f"Task with id {args.id} not found.")
    else:
        print(f"Marked done: [{task['id']}] {task['text']}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskman", description="Simple task manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("text", help="Task description")
    add_parser.add_argument(
        "--priority", choices=PRIORITY_ORDER, default="medium", help="Task priority"
    )

    list_parser = subparsers.add_parser("list", help="List all tasks")
    list_parser.add_argument("--status", choices=["all", "done", "pending"], default="all")
    list_parser.add_argument("--sort", choices=["id", "priority"], default="id")

    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("id", type=int, help="Task id")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    handler(args)


if __name__ == "__main__":
    main()
```

Key decisions:

- `wrapper(*args, **kwargs)` instead of `wrapper(args)` — the decorator makes no assumption about the wrapped function's signature. The line `namespace = args[0]` pulls out the first positional argument, which for us is always an `argparse.Namespace`. The decorator itself stays generic, and reusable for functions with a different signature.
- `@functools.wraps(func)` on `wrapper` — without this line, `handle_add.__name__` would become `"wrapper"` after decorating. That breaks debugging (tracebacks, `help()`, introspection) and any code that relies on the function's name.
- Logging goes to `sys.stderr`, not to a `print()` on stdout. The `list` command prints only the tasks themselves to stdout, so `python main.py list | grep milk` keeps working as expected. The logs never enter the pipe, and they don't interfere with parsing the output.
- `COMMAND_HANDLERS` — a "command name → function" dict instead of an `if/elif` chain. Adding a new command later means one new function plus one line in the dict, not one more `elif` branch in an ever-growing `main()`.

## Check yourself

1. Why is `def add_item(item, bucket=[]):` a classic trap rather than just "sloppy but working" code? What exactly happens to `bucket` across different calls to the function?
2. Given:
   ```python
   counter = 0
   def increment():
       counter += 1
       return counter
   ```
   Why does this raise `UnboundLocalError`? At first glance it looks as if `counter` should just be read from the enclosing scope, the way it would in JS.
3. What's the difference between `global` and `nonlocal`, and when do you specifically need `nonlocal` instead of `global`?
4. What does `@decorator` above a function definition actually mean — what does it expand to under the hood?
5. Why is `functools.wraps(func)` needed inside a decorator? What breaks without it, and how would you notice that in practice — name a concrete tool or behavior.

<details>
<summary>Answers</summary>

1. A parameter's default value in Python is evaluated **once**, when the `def add_item(...)` line executes — that is, at module import time. It is not evaluated fresh on every call. Every call to `add_item(x)` without an explicit `bucket=...` therefore gets **the same list object**. If one call mutates it with `.append()`, that change is visible on every later call. It is physically the same object in memory, not a brand-new list created from scratch each time.
2. Python determines a name's "localness" statically, by scanning the **entire function body** before execution. If a name is assigned anywhere in the body, that name is treated as local throughout the whole function, from its very first line. And `counter += 1` is an assignment, equivalent to `counter = counter + 1`. So the attempt to read `counter` in order to compute `counter + 1` sees a local variable that hasn't been initialized yet. It does not see the module-level variable — hence `UnboundLocalError`. JS has no such ambiguity. The variable is explicitly declared once via `let`/`const`, and any later use inside a closure refers to that specific declared variable.
3. `global` tells the interpreter: this name is a module-level (global) variable, not a new local one, so assignment must modify that one. The `nonlocal` keyword does the same thing, but for a variable belonging to the **nearest enclosing function** in a closure, not to the module. You need `nonlocal` specifically when a nested function has to modify a variable from its enclosing function, like `count` in `make_counter`. A `global` declaration would not work there, because the variable you want lives at the level of another function, not at module scope.
4. `@decorator` directly above `def func(): ...` is syntactic sugar, fully equivalent to writing `func = decorator(func)` right after `func` is defined. There is no separate language mechanism for decorators beyond this substitution. The `decorator` is called with the original function as its only argument, and whatever it returns becomes the new value bound to `func`.
5. Without `functools.wraps(func)`, the object bound to the decorated function's name is `wrapper` itself, with `__name__ == "wrapper"`, an empty `__doc__` and so on. In practice that breaks three things:

   - Debugging tracebacks show "wrapper" instead of the real function name, which makes stack traces harder to read.
   - `help(func)` and editor introspection show `wrapper`'s docstring and signature, not the original function's.
   - Any code that checks `func.__name__` explicitly — some test frameworks, or routing systems that match handlers by name.

</details>

## Common mistake

The single most famous Python gotcha for newcomers of any background is the mutable default parameter, `def f(items=[]):`. For a JS developer it is especially treacherous, because the intuition runs exactly backward. In JS, `function f(items = []) {}` creates a **new** empty array on every call where `items` isn't passed explicitly. A JS developer naturally carries that assumption into Python and expects the same behavior.

In reality, Python creates the `[]` list once, at function-definition time, and shares that one object across every "implicit" call.

The bug usually doesn't show up right away. The code works fine in tests where the function is called once. It starts "mysteriously accumulating data from previous calls" in production, or in integration tests. There the function is called many times over the life of the process. That is exactly the situation where it is hardest to connect the symptom to the cause.

The second common problem is trying to assign to an enclosing function's variable inside a closure without `nonlocal`. The JS reflex says "just reassign the outer-scope variable, it's a closure after all".

In Python that is not a compile error — it is a runtime `UnboundLocalError`. And the error message, `local variable referenced before assignment`, does not hint that the fix is `nonlocal` — unless you already know the mechanics.
