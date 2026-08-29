# OOP and dataclasses

## Theory

**class, `__init__`, `self`.** Object-oriented programming (OOP) in Python starts with syntax that looks like JS, with one systematic difference. The first parameter of every method is `self` — the current instance. It is **always explicit**: you write it by hand in every signature:

```python
class Task:
    def __init__(self, text: str) -> None:
        self.text = text

    def mark_done(self) -> None:
        self.done = True
```

In JS, `this` is implicit and notorious for its binding rules. What `this` points to inside a regular method depends on *how* the method was called. Call it as `obj.method()` and you get one `this`. Take the method out first, as in `const fn = obj.method; fn()`, and you get another: `undefined` in strict mode, `window` otherwise. That is why JS needs `.bind()` and arrow functions for callback methods.

Python has no such problem at all. Here `self` is a normal parameter, and it receives its value exactly the way any other function argument does. When you call `instance.method(...)`, Python itself supplies `instance` as the first argument. There's no "unbound method" pain in the JS sense. A method grabbed as `Task.mark_done` just requires you to pass `self` explicitly when you call it.

**Dunder methods — an object's behavioral protocols.** Methods named `__name__` ("double underscore," "dunder") are extension points where your class plugs into the language's built-in operations:

- `__repr__(self) -> str` — the "technical" representation of an object. This is what you see in the REPL (read-eval-print loop, the interactive Python prompt), in a debugger and in logs (`repr(obj)`). It is also what an object formats to by default when `__str__` isn't defined.
- `__eq__(self, other) -> bool` — what "equality" means for this class. Without an override, `==` on a plain class means **identity** comparison (the same object in memory), just like `is`; override `__eq__` and `==` becomes value comparison.
- `__lt__(self, other) -> bool` — "less than". Without it, instances of your class can't be compared with `<`. They also can't go straight into `sorted()`/`.sort()` without an explicit `key=`.

JS has a direct counterpart for only one of these three: `toString()`/`Symbol.toPrimitive`. It is roughly `__str__`, but JS does not split "technical" and "display" representations so explicitly.

Value-based `==` has a partial counterpart too, through overriding `valueOf()`/`Symbol.toPrimitive` for primitive comparisons. JS has no counterpart for the full protocol — "define what equality means for my class", the job `__eq__` does. You'd usually write your own `.equals()` method by hand.

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

Both versions give the same `__init__`/`__repr__`/`__eq__` behavior. Equality compares all fields as a tuple, in declaration order. An important nuance: `@dataclass` generates `__repr__`, but does **not** generate `__str__`. If you want human-readable output for `print(obj)`, you have to write it yourself — without `__str__`, `print(obj)` falls back to `__repr__`.

`@dataclass` also doesn't generate `__lt__`/`__gt__` by default. That's opt-in via `order=True`, which compares all fields in declaration order. If you need a custom comparison order, and not "all fields, in sequence", you write `__lt__` by hand — same as in a plain class.

One more nuance ties back to the mutable-default trap from chapter 03. Here `@dataclass` **won't let** you write `tags: list = []` directly in the class body. It raises a `ValueError` right at class-definition time, instead of silently creating a shared list the way a plain function would. A mutable default in a dataclass needs `field(default_factory=list)`:

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

Syntactically this is pretty close to `get`/`set` in JS classes. The idea itself — a computed property that looks like a plain attribute — isn't new to a JS developer. The main difference is decorator syntax (`@property`/`@x.setter`) instead of the `get`/`set` keywords.

**Inheritance.** `class Child(Parent):`, calling the parent's method via `super().__init__(...)`. The mechanics are nearly identical to `class Child extends Parent { constructor() { super(); } }` in JS/TS. Just like in JS, `super()` must be called before touching `self` in an overridden `__init__`, if the parent initializes anything.

**ABC (Abstract Base Classes).** The `abc` module gives you `ABC` (a base class) and `@abstractmethod`. Together they say "this class has a method, but the implementation must live in a subclass":

```python
from abc import ABC, abstractmethod

class Storage(ABC):
    @abstractmethod
    def save(self, task: "Task") -> None: ...

class JsonStorage(Storage):
    def save(self, task: "Task") -> None:
        ...  # the actual implementation
```

Trying to instantiate `Storage()` directly, without overriding `save`, raises `TypeError` at instantiation time.

An important contrast with TS: an `interface` in TS is **structural** typing. Any object with the right shape qualifies, and no explicit inheritance is needed. `ABC` in Python is **nominal** instead: a class must explicitly inherit from `Storage`, or it isn't considered a subtype of it. That holds even if the class has a method with the exact same name and signature.

The structural counterpart of a TS `interface` in Python is `Protocol`, from the `typing` module. Chapter 10 on typing covers it separately.

### Parallels with JS/TS/Node:

- `self` is an explicit parameter on every method, immune to `this`-binding issues; no `.bind()`/arrow functions needed "so `this` doesn't get lost."
- `__eq__`/`__lt__` — a full-fledged protocol for "what equality and ordering mean for my class", built into the language. In JS you'd typically write your own `.equals()`/`.compareTo()` methods by hand, with no unified protocol for it.
- `@dataclass` saves you exactly the boilerplate that JS/TS never needs for plain objects. Python does need it for a proper class with `__init__`/`__repr__`/`__eq__`.
- `ABC` is nominal typing (mandatory explicit inheritance), unlike structural `interface`s in TS; the structural counterpart in Python is `Protocol` (chapter 10).

## What we're adding to the project

`Task` goes from a plain `dict` to an `@dataclass` with typed fields. The `priority` field goes from a string to `Priority(IntEnum)` with a clear ordering: `LOW < MEDIUM < HIGH`.

`Task` gets two new dunder methods. One is `__lt__`, which sorts by priority and falls back to id on ties. The other is `__str__`, a single output format shared by `add`/`list`/`done`. On top of that, `__post_init__` refuses to create a task with empty text. That closes the "should empty text be allowed?" question left open back in chapter 00.

## Practical exercise

1. Define `class Priority(IntEnum)` with members `LOW`, `MEDIUM`, `HIGH` (values 0, 1, 2). Override `__str__` so that `str(Priority.LOW)` returns `"low"` instead of the enum's technical representation.
2. Replace the task dict with `@dataclass class Task`, with fields `id: int`, `text: str`, `priority: Priority = Priority.MEDIUM`, `done: bool = False`.
3. Add `Task.__post_init__`, raising `ValueError` if `text` is empty or whitespace-only (use `.strip()`).
4. Add `Task.__lt__`. It compares by priority in descending order — a higher priority counts as "less" for sorting, so it comes first. When priorities are equal, it compares by `id` in ascending order.
5. Add `Task.__str__` — a single output format `[mark] id text (priority)`, used across `add`, `list`, and `done`.
6. Update the whole storage layer — `add_task`, `find_task`, `mark_done`, `filter_by_status`, `sort_tasks` — to work with `Task` objects instead of dicts. Then `sort_tasks(items, "priority")` should call `sorted(items)` directly, with no `key=`, relying on `Task.__lt__`.

Things to think through:

- Right now, empty task text makes the process crash with a raw traceback, because nobody catches the `ValueError`. That's expected at this point in the course. But what would you actually want a user of the command-line interface (CLI) to see instead of a traceback? (The fix comes in chapter 06.)
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

- `Priority(IntEnum)` instead of plain `Enum`. `IntEnum` inherits from `int`, so members compare directly — `Priority.LOW < Priority.HIGH` works out of the box. It also makes `-self.priority` in `__lt__` yield a plain `int`. A plain `Enum` doesn't support that comparison without a hand-written `__lt__` on the enum itself.
- `PRIORITY_CHOICES = [p.name.lower() for p in Priority]` — the list argparse uses is built from the enum itself, because an `Enum` is iterable. Nothing is duplicated by hand: if `Priority.URGENT` gets added later, `PRIORITY_CHOICES` picks it up automatically.
- Converting `Priority[args.priority.upper()]` happens in the handler, not in `add_task`. The `add_task` function works with an already-resolved `Priority`, not a raw string, and parsing the string is the CLI layer's job. There's deliberately no check for "what if the string is invalid" here. In argparse, `choices=PRIORITY_CHOICES` already guarantees that only a valid value reaches this point.
- `Task.__str__` is used across all three handlers: `Added: {task}`, the `list` output and `Marked done: {task}`. That is one format instead of three near-identical f-strings, the job the standalone `format_task` function used to do. It does change the `Added:` line's format, which now includes the `[ ]`/`[x]` marker instead of just `[id]`. That is a deliberate trade-off: one source of truth for formatting, instead of copy-pasted f-strings.
- `sort_tasks(items, "priority")` is now just `sorted(items)`, no `key=`. That's the direct practical payoff of `__lt__`. Back in chapters 02–03, "how to compare by priority" was a separate lambda inside `sort_tasks`. Now it's part of the `Task` class itself, and `sorted()` picks it up automatically.

## Check yourself

1. Why does Python never run into the "method lost `this`" situation familiar from JS? In JS, `const fn = obj.method; fn()` ends up with the wrong object, or with `undefined`. What in Python's method-call mechanics rules this out?
2. How is `__repr__` fundamentally different from `__str__` in purpose, and what does `print(task)` use if `__str__` isn't defined but `__repr__` is?
3. Why does `@dataclass class Config: tags: list[str] = []` raise an error right at class-definition time? The `def f(items=[]):` from chapter 03 never raises: it just silently creates a bug. What rule changed?
4. How does `Priority(IntEnum)` differ from `Priority(Enum)` in the context of what we actually needed for sorting tasks?
5. Why is `ABC` in Python called "nominal" typing, while `interface` in TypeScript is called "structural"? Give a concrete example of a class that TS accepts as satisfying an interface. The same class, without explicit inheritance, is not an `ABC` subclass in Python.

<details>
<summary>Answers</summary>

1. The "lost `this`" problem in JS happens because `this` isn't a parameter. It's a value determined **at call time**, based on the syntax of the call: `obj.method()` vs. `fn()` vs. `fn.call(x)`. In Python, `self` is a normal, explicitly declared first parameter, no different from any other parameter. When you write `instance.method(args)`, Python syntactically expands this to `ClassName.method(instance, args)`. The `instance` is passed as the first positional argument, just as predictably as in any other call with explicit arguments. There's no separate substitution that depends on the call site.
2. `__repr__` is meant to be an unambiguous, "debugging" representation of an object. Ideally it tells you what the object is, and even how to recreate it. It's what shows up in the REPL, in a debugger and in `logging`. The `__str__` method is meant for a "human-facing" representation — what an end user sees via `print()`/`str()`. If `__str__` isn't defined, `print(task)` falls back to `__repr__`. So `__repr__` is the fallback for both cases, and `__str__` is an optional refinement for user-facing output.
3. The rule for functions (`def f(items=[])`) hasn't changed since chapter 03. It's still quiet, working — if buggy — code. The interpreter generally can't know whether an object is "meant" to be shared across calls, so it doesn't forbid it. But `@dataclass` is different from a plain function: it **knows what its fields mean**. While generating `__init__`, the decorator reads the declared default values. The authors of `dataclasses` deliberately added a check there for types that have no `__hash__` — lists, dicts and sets. The check runs once, when the class is created, not on every call to the constructor. The reason: in a dataclass, a field with a mutable default shared by every instance is almost certainly a mistake, not a deliberate choice.
4. `Priority(IntEnum)` inherits from `int`, so comparison operators (`<`, `>`, `<=`, `>=`) work between enum members immediately, with no extra code. For example, `Priority.HIGH > Priority.LOW` is `True` out of the box. A plain `Priority(Enum)` only gives you `==`/`!=`, hashing and iteration over members. It doesn't support `<`/`>`, so ordered comparison would have to be written by hand: a custom `__lt__` on the enum itself, or `functools.total_ordering`. We needed an ordering by priority, and `IntEnum` gives it to us for free.
5. "Nominal" typing means that type compatibility is determined by an **explicitly declared name or hierarchy**. A class must explicitly write `class X(Storage):` — having the right methods is not enough. "Structural" means that compatibility is determined by **shape**, the set of methods and fields, with no explicit declaration of the relationship. Here is an example: `class FileLogger: def save(self, task): ...`. This class has a `save` method with the same signature as `Storage`, but it does **not** inherit from `Storage` explicitly. TS would accept this class as satisfying `interface Storage { save(task: Task): void }` automatically, purely by shape. In Python, `isinstance(FileLogger(), Storage)` returns `False`, because `FileLogger` never explicitly wrote `(Storage)` in its list of parents.

</details>

## Common mistake

The most likely mistake when moving from a plain class to `@dataclass` is forgetting that `@dataclass` gives you `__repr__` but not `__str__`. Then `print(task)` prints something like `Task(id=1, text='Buy milk', priority=<Priority.LOW: 0>, done=False)` instead of the expected human-readable output.

In JS an object usually has one way to "present itself": `toString()`, or the default `console.log` output, which already formats objects reasonably. So a JS developer doesn't expect Python to have **two separate** representation protocols with different purposes. The first instinct is to assume that `@dataclass` "didn't work" or "broke repr", when in fact `__str__` simply was never written.

The second common mistake is trying to sort a list of dataclass objects with `sorted(items)`, without implementing `__lt__` at all. The expectation is that "since this is structured data, Python will figure out how to compare it". That comes from JS, where `[].sort()` on objects at least doesn't crash: it just sorts "somehow" via string coercion.

In Python this isn't a silent degradation to some arbitrary order. It's an explicit `TypeError: '<' not supported between instances of 'Task' and 'Task'`. Without `__lt__`, and without `order=True` on `@dataclass`, instances of your class don't support the "less than" operation at all. Python never silently guesses a comparison order on your behalf.
