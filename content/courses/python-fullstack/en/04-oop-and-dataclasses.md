# OOP and dataclasses

## Theory

**class, `__init__`, `self`.** Basic class syntax looks like JS, but with one systematic difference: the first parameter of every method is `self` (the current instance), and it's **always explicit** — you write it by hand in every signature:

```python
class Task:
    def __init__(self, text: str) -> None:
        self.text = text

    def mark_done(self) -> None:
        self.done = True
```

In JS, `this` is implicit and notorious for its binding rules: `this` inside a regular method depends on *how* the method was called (`obj.method()` gives one `this`, `const fn = obj.method; fn()` gives another — `undefined`/`window` in strict/non-strict mode) — hence `.bind()`, arrow functions for callback methods, and so on. Python has no such problem at all: `self` is a normal parameter, receiving a value exactly the way any other function argument does; when you call `instance.method(...)`, Python itself supplies `instance` as the first argument. There's no "unbound method" pain in the JS sense — a method grabbed as `Task.mark_done` simply requires you to pass `self` explicitly when calling it.

**Dunder methods — an object's behavioral protocols.** Methods named `__name__` ("double underscore," "dunder") are extension points where your class plugs into the language's built-in operations:

- `__repr__(self) -> str` — the "technical" representation of an object: what you see in the REPL, in a debugger, in logs (`repr(obj)`), and what an object formats to by default if `__str__` isn't defined.
- `__eq__(self, other) -> bool` — what "equality" means for this class. Without an override, `==` on a plain class means **identity** comparison (the same object in memory), just like `is`; override `__eq__` and `==` becomes value comparison.
- `__lt__(self, other) -> bool` — "less than"; without it, instances of your class can't be compared with `<` and can't be passed directly to `sorted()`/`.sort()` without an explicit `key=`.

JS has a direct counterpart for only one of these three — `toString()`/`Symbol.toPrimitive` (roughly `__str__`, but without such an explicit split between "technical" and "display" representations). Value-based `==` has a partial counterpart in JS through overriding `valueOf()`/`Symbol.toPrimitive` for primitive comparisons, but there's no full "define what equality means for my class" protocol like `__eq__` — you'd usually write your own `.equals()` method by hand.

**`@dataclass` — a compact stand-in for "class + constructor + repr + eq".** A plain class with a few fields needs `__init__`, `__repr__`, and `__eq__` written by hand:

```python
class TaskPlain:
    def __init__(self, id: int, text: str, done: bool = False) -> None:
        self.id = id
        self.text = text
        self.done = done

    def __repr__(self) -> str:
        return f"TaskPlain(id={self.id!r}, text={self.text!r}, done={self.done!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaskPlain):
            return NotImplemented
        return (self.id, self.text, self.done) == (other.id, other.text, other.done)
```

`@dataclass` generates exactly this from the field declarations:

```python
from dataclasses import dataclass

@dataclass
class TaskPlain:
    id: int
    text: str
    done: bool = False
```

Both versions give the same `__init__`/`__repr__`/`__eq__` behavior (equality compares all fields as a tuple, in declaration order). An important nuance: `@dataclass` generates `__repr__`, but does **not** generate `__str__` — if you want human-readable output for `print(obj)`, you have to write it yourself (without `__str__`, `print(obj)` falls back to `__repr__`). `@dataclass` also doesn't generate `__lt__`/`__gt__` by default (that's opt-in via `order=True`, which compares all fields in order) — if you need a custom comparison order (not "all fields, in sequence"), you write `__lt__` by hand, same as in a plain class.

One more nuance, tying back to the mutable-default trap from chapter 03: `@dataclass` **won't let** you write `tags: list = []` directly in the class body — it raises a `ValueError` right at class-definition time, instead of silently creating a shared list the way a plain function would. A mutable default in a dataclass needs `field(default_factory=list)`:

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    tags: list[str] = field(default_factory=list)  # a fresh list per instance
```

**`@property`.** Lets you access a method as if it were an attribute — called without parentheses:

```python
class Temperature:
    def __init__(self, celsius: float) -> None:
        self._celsius = celsius

    @property
    def fahrenheit(self) -> float:
        return self._celsius * 9 / 5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value: float) -> None:
        self._celsius = (value - 32) * 5 / 9

t = Temperature(20)
t.fahrenheit        # 68.0 — no parentheses, even though this is a method call
t.fahrenheit = 100   # calls the setter
```

Syntactically this is pretty close to `get`/`set` in JS classes — the idea itself ("a computed property that looks like a plain attribute") isn't new to a JS developer; the main difference is decorator syntax (`@property`/`@x.setter`) instead of the `get`/`set` keywords.

**Inheritance.** `class Child(Parent):`, calling the parent's method via `super().__init__(...)`. The mechanics are nearly identical to `class Child extends Parent { constructor() { super(); } }` in JS/TS — just like in JS, `super()` must be called before touching `self` in an overridden `__init__`, if the parent initializes anything.

**ABC (Abstract Base Classes).** The `abc` module gives you `ABC` (a base class) and `@abstractmethod` — a way to say "this class has a method, but the implementation must live in a subclass":

```python
from abc import ABC, abstractmethod

class Storage(ABC):
    @abstractmethod
    def save(self, task: "Task") -> None: ...

class JsonStorage(Storage):
    def save(self, task: "Task") -> None:
        ...  # the actual implementation
```

Trying to instantiate `Storage()` directly (without overriding `save`) raises `TypeError` at instantiation time. An important contrast with TS: an `interface` in TS is **structural** typing (any object with the right shape qualifies, no explicit inheritance needed); `ABC` in Python is **nominal**: a class must explicitly inherit from `Storage`, or it isn't considered a subtype of it — even if it has a method with the exact same name and signature. The structural counterpart of a TS `interface` in Python is `Protocol` (from the `typing` module), covered separately in the typing chapter (10).

### Parallels with JS/TS/Node:

- `self` is an explicit parameter on every method, immune to `this`-binding issues; no `.bind()`/arrow functions needed "so `this` doesn't get lost."
- `__eq__`/`__lt__` — a full-fledged protocol for "what equality/ordering means for my class," built into the language; in JS you'd typically write your own `.equals()`/`.compareTo()` methods by hand, with no unified protocol for it.
- `@dataclass` saves you exactly the boilerplate that JS/TS doesn't require for plain objects in the first place, but that Python needs for a proper class with `__init__`/`__repr__`/`__eq__`.
- `ABC` is nominal typing (mandatory explicit inheritance), unlike structural `interface`s in TS; the structural counterpart in Python is `Protocol` (chapter 10).

## What we're adding to the project

`Task` goes from a plain `dict` to an `@dataclass` with typed fields, and `priority` goes from a string to `Priority(IntEnum)` with a clear ordering (`LOW < MEDIUM < HIGH`). `Task` gets `__lt__` (sort by priority, falling back to id on ties) and `__str__` (a single output format shared by `add`/`list`/`done`), and `__post_init__` refuses to create a task with empty text — closing the "should empty text be allowed?" question left open back in chapter 00.

## Practical exercise

1. Define `class Priority(IntEnum)` with members `LOW`, `MEDIUM`, `HIGH` (values 0, 1, 2), and override `__str__` so `str(Priority.LOW)` returns `"low"` instead of the enum's technical representation.
2. Replace the task dict with `@dataclass class Task`, with fields `id: int`, `text: str`, `priority: Priority = Priority.MEDIUM`, `done: bool = False`.
3. Add `Task.__post_init__`, raising `ValueError` if `text` is empty or whitespace-only (use `.strip()`).
4. Add `Task.__lt__`, comparing by priority (descending — higher priority is "less" in sort terms, so it comes first) and by `id` (ascending) when priorities are equal.
5. Add `Task.__str__` — a single output format `[mark] id text (priority)`, used across `add`, `list`, and `done`.
6. Update the whole storage layer (`add_task`, `find_task`, `mark_done`, `filter_by_status`, `sort_tasks`) to work with `Task` objects instead of dicts; `sort_tasks(items, "priority")` should use `sorted(items)` directly (no `key=`), relying on `Task.__lt__`.

Things to think through:

- Right now, empty task text makes the process crash with a raw traceback (nobody catches the `ValueError`). That's expected at this point in the course — but what would you actually want a CLI user to see instead of a traceback? (The fix comes in chapter 06.)
- Why does `Task.__lt__` return `NotImplemented` rather than raising, when `other` isn't a `Task`? What difference does that make to how Python handles the comparison?

## Worked solution

```python
import argparse
import functools
import sys
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


tasks: list[Task] = []


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        return result

    return wrapper


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
        return sorted(items)  # uses Task.__lt__
    return sorted(items, key=lambda t: t.id)


@log_command
def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = sort_tasks(filter_by_status(tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
    else:
        for task in result:
            print(task)


@log_command
def handle_done(args: argparse.Namespace) -> None:
    task = mark_done(args.id)
    if task is None:
        print(f"Task with id {args.id} not found.")
    else:
        print(f"Marked done: {task}")


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
        "--priority", choices=PRIORITY_CHOICES, default="medium", help="Task priority"
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

- `Priority(IntEnum)` instead of plain `Enum` — `IntEnum` inherits from `int`, so members compare directly (`Priority.LOW < Priority.HIGH` works out of the box), and `-self.priority` in `__lt__` yields a plain `int`. A plain `Enum` doesn't support that comparison without a hand-written `__lt__` on the enum itself.
- `PRIORITY_CHOICES = [p.name.lower() for p in Priority]` — the list argparse uses is built from the enum itself (an `Enum` is iterable), rather than duplicated by hand; if `Priority.URGENT` gets added later, `PRIORITY_CHOICES` picks it up automatically.
- Converting `Priority[args.priority.upper()]` happens in the handler, not in `add_task` — `add_task` works with an already-resolved `Priority`, not a raw string; parsing the string is the CLI layer's job. There's deliberately no check for "what if the string is invalid" here: `choices=PRIORITY_CHOICES` in argparse already guarantees only a valid value reaches this point.
- `Task.__str__` is used across all three handlers (`Added: {task}`, the `list` output, `Marked done: {task}`) — one format instead of three near-identical f-strings, the way the standalone `format_task` function used to work. This does change the `Added:` line's format (it now includes the `[ ]`/`[x]` marker instead of just `[id]`) — a deliberate trade-off in favor of one source of truth for formatting over copy-pasted f-strings.
- `sort_tasks(items, "priority")` is now just `sorted(items)`, no `key=`. That's the direct practical payoff of `__lt__`: back in chapters 02–03, "how to compare by priority" was a separate lambda inside `sort_tasks`; now it's part of the `Task` class itself, and `sorted()` picks it up automatically.

## Check yourself

1. Why does Python never run into the "method lost `this`" situation familiar from JS (where `const fn = obj.method; fn()` ends up with the wrong object, or `undefined`)? What about Python's method-call mechanics rules this out?
2. How is `__repr__` fundamentally different from `__str__` in purpose, and what does `print(task)` use if `__str__` isn't defined but `__repr__` is?
3. Why does `@dataclass class Config: tags: list[str] = []` raise an error right at class-definition time, while `def f(items=[]):` from chapter 03 never raises — it just silently creates a bug? What rule changed?
4. How does `Priority(IntEnum)` differ from `Priority(Enum)` in the context of what we actually needed for sorting tasks?
5. Why is `ABC` in Python called "nominal" typing, while `interface` in TypeScript is called "structural"? Give a concrete example of a class TS would accept as satisfying an interface, that Python would not accept as satisfying an `ABC` subclass (without explicit inheritance).

<details>
<summary>Answers</summary>

1. The "lost `this`" problem in JS happens because `this` isn't a parameter — it's a value determined **at call time**, based on the syntax of the call (`obj.method()` vs. `fn()` vs. `fn.call(x)`). In Python, `self` is a normal, explicitly declared first parameter, no different from any other parameter. When you write `instance.method(args)`, Python syntactically expands this to `ClassName.method(instance, args)` — `instance` is passed as the first positional argument just as predictably as any other function call with explicit arguments; there's no separate, call-site-dependent substitution happening.
2. `__repr__` is meant to be an unambiguous, "debugging" representation of an object — ideally one that tells you what the object is and, ideally, how to recreate it; it's what shows up in the REPL, in a debugger, in `logging`. `__str__` is meant for a "human-facing" representation, what an end user sees via `print()`/`str()`. If `__str__` isn't defined, `print(task)` falls back to `__repr__` — so `__repr__` acts as the fallback for both cases, while `__str__` is an optional refinement specifically for user-facing output.
3. The rule for functions (`def f(items=[])`) hasn't changed since chapter 03 — it's still quiet, working (if buggy) code, because the interpreter generally can't know whether an object is "meant" to be shared across calls, and doesn't forbid it. `@dataclass`, unlike a plain function, **knows the semantics of its fields** — the decorator explicitly inspects the declared default values while generating `__init__`, and the `dataclasses` module's authors deliberately added a check specifically for types lacking `__hash__` (lists, dicts, sets) — at class-creation time, not at every call to the constructor — because for a dataclass, "a field with a mutable default shared across every instance" is almost certainly a mistake, not a deliberate choice.
4. `Priority(IntEnum)` inherits from `int`, so comparison operators (`<`, `>`, `<=`, `>=`) work between enum members immediately, with no extra code — `Priority.HIGH > Priority.LOW` is `True` out of the box. `Priority(Enum)` (plain) only gives you `==`/`!=`/hashing and iteration over members, but doesn't support `<`/`>` — ordered comparison would have to be written by hand (a custom `__lt__` on the enum itself, or via `functools.total_ordering`). We needed an ordering by priority — `IntEnum` gives it to us for free.
5. "Nominal" typing means: type compatibility is determined by an **explicitly declared name/hierarchy** (a class must explicitly write `class X(Storage):`), not by whether it happens to have the right methods. "Structural" means: compatibility is determined by **shape** (the set of methods/fields), with no explicit declaration of the relationship at all. Example: a class `class FileLogger: def save(self, task): ...` that has a `save` method with the same signature as `Storage`, but is **not** explicitly inherited from `Storage` — TS would accept this class as satisfying `interface Storage { save(task: Task): void }` automatically, purely by shape; in Python, `isinstance(FileLogger(), Storage)` returns `False`, because `FileLogger` never explicitly wrote `(Storage)` in its list of parents.

</details>

## Common mistake

The most likely mistake when moving from a plain class to `@dataclass` is forgetting that `@dataclass` gives you `__repr__` but not `__str__`, and being surprised when `print(task)` prints something like `Task(id=1, text='Buy milk', priority=<Priority.LOW: 0>, done=False)` instead of the expected human-readable output. A developer used to JS, where an object usually has one way to "present itself" (`toString()`, or the default `console.log` output, which already formats objects reasonably), doesn't expect Python to have **two separate** representation protocols with different purposes, and the first instinct is to assume `@dataclass` "didn't work" or "broke repr," when in fact `__str__` simply was never written.

The second common mistake is trying to sort a list of dataclass objects with `sorted(items)` without implementing `__lt__` at all, expecting that "since this is structured data, Python will figure out how to compare it" (by analogy with JS, where `[].sort()` on objects at least doesn't crash — it just sorts "somehow" via string coercion). In Python this isn't a silent degradation to some arbitrary order — it's an explicit `TypeError: '<' not supported between instances of 'Task' and 'Task'`, because without `__lt__` (and without `order=True` on `@dataclass`), instances of your class don't support the "less than" operation at all — Python never silently guesses a comparison order on your behalf.
