# Syntax and types

## Theory

**Indentation as syntax.** A block after `if`, `for`, `def`, `class`, etc. starts with a `:` and consists of lines sharing the same indentation — conventionally 4 spaces (PEP 8). Mixing tabs and spaces within one block isn't a warning, it's a `TabError`. There are no `{}`: there's no closing brace, the block ends when the indentation drops back.

```python
if age >= 18:
    print("adult")       # part of the if block — 4-space indent
    print("can vote")    # also part of the block
print("done")             # indentation back to 0 — this is outside if
```

**Variables — no `let`/`const`/`var`.** Assignment is just `name = value`, no declaration keyword. The more important difference: Python has **no block scope** for `if`/`for`/`while` — only function and module scope exist. A variable created inside an `if` stays alive after it ends, unlike `let`/`const` in JS, which are confined to `{}`:

```python
if True:
    x = 5
print(x)  # 5 — still accessible here; with let in JS this would be a ReferenceError
```

`def` and `class` create their own scope; `if`/`for`/`while`/`with` do not. This regularly trips up JS developers used to `let i` inside a `for` not leaking past the loop.

**Dynamic but strict typing.** In JS, types exist at runtime without declarations (`typeof x`), but many operations coerce implicitly (`"3" + 3 === "33"`, `"3" - 3 === 0`). In Python, types also exist at runtime without declarations, but there's **almost no implicit coercion between incompatible types**:

```python
"3" + 3        # TypeError: can only concatenate str (not "int") to str
"3" + str(3)   # "33" — coercion only happens explicitly
```

That's what "strict but dynamic" means: type checking happens at runtime (not at compile time, like TS), but the interpreter never tries to guess type compatibility on your behalf.

**Core types.** `int` (arbitrary precision — no overflow, no need for a `BigInt` equivalent), `float` (IEEE754 double, same as JS's `number`), `bool` (`True`/`False`, capitalized), `str`, `None`. Important: Python has **only one** "empty" value — `None`. There's no `null`/`undefined` split here: an uninitialized variable simply doesn't exist in Python (referencing it raises `NameError`), rather than holding an `undefined` value.

**f-strings.** The direct counterpart of template literals:

```python
name = "Max"
count = 3
print(f"{name} has {count} tasks")        # interpolation
print(f"{3.14159:.2f}")                    # "3.14" — format spec after ":"
print(f"{count=}")                         # "count=3" — debug shortcut, no JS equivalent
```

**Operators.** `==` in Python compares **values** (calls `__eq__`) — there's no separate "strict" comparison operator like JS's `===`, because Python's `==` never does the implicit coercions that a strict variant would need to bypass. `is` compares object **identity** (same address in memory), not value; it's used almost exclusively for `x is None` (an idiom, not a style preference). There's no `++`/`--` — only `x += 1` ("explicit is better than implicit": the language designers decided pre/post-increment ambiguity wasn't worth the syntax). Chained comparisons work: `0 < x < 10` is equivalent to `0 < x and x < 10` — in JS, `0 < x < 10` also "works" but evaluates left-to-right through boolean-to-number coercion, giving wrong results for many values.

**Truthy/falsy — gotcha #1 coming from JS.** Python has a small, fixed set of falsy values: `False`, `None`, `0`, `0.0`, `""`, `[]`, `{}`, `set()`, `()` — meaning **every empty collection is falsy**. In JS, an empty array and empty object are always truthy (`Boolean([]) === true`, `Boolean({}) === true`); the only falsy values there are `0`, `""`, `null`, `undefined`, `NaN`, `false`. This is the exact opposite behavior for the single most common real-world check — `if tasks:`.

### Parallels with JS/TS/Node:

- **No block scope** — `if`/`for`/`while` don't create a new scope, unlike `let`/`const` inside `{}`. Scope is only function/module-level.
- **`==` never coerces** between incompatible types (unlike JS's `==`, notorious for its coercion rules); `"5" == 5` in Python is just `False` — not a `TypeError`, not `True`.
- **Empty collections are falsy**, not truthy like in JS: `if []:` in Python won't run; `if ([])` in JS always will.
- **Only `None`** — no `null`/`undefined` pair.

## What we're adding to the project

We're adding `list` (print all tasks with a done marker) and `done <id>` (mark a task as done). This is where searching an in-memory list and building meaningful formatted output with f-strings first show up — persistence is still far off, but the CLI is already genuinely useful within a single process run.

## Practical exercise

1. Add a `list` subcommand — prints every task as `[ ] 1 Buy milk` (space instead of `x` if not done) or `[x] 2 Clean house` (if done). If there are no tasks, print `No tasks yet.`
2. Add a `done <id>` subcommand — takes a numeric id, finds the task with that id, and sets `done = True`. On success, print `Marked done: [id] text`. If no task with that id exists, print `Task with id <id> not found.` (no crash — no exceptions yet, those come in chapter 06).
3. Confirm `id` in `done` is parsed as `int` — what happens if you pass `python main.py done abc`? Look closely at argparse's error message.

Things to think through:

- What happens if you call `done` twice with the same id? Is that a bug, or reasonable behavior — how would you justify either answer?
- If you wrote `if tasks:` instead of `if len(tasks) > 0:` to check "the list isn't empty" — coming from JS habits, that would look suspicious. Does it actually work correctly in Python, and why?

## Worked solution

```python
import argparse

tasks: list[dict] = []


def add_task(text: str) -> dict:
    task = {"id": len(tasks) + 1, "text": text, "done": False}
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


def format_task(task: dict) -> str:
    mark = "x" if task["done"] else " "
    return f"[{mark}] {task['id']} {task['text']}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskman", description="Simple task manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("text", help="Task description")

    subparsers.add_parser("list", help="List all tasks")

    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("id", type=int, help="Task id")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        task = add_task(args.text)
        print(f"Added: [{task['id']}] {task['text']}")
    elif args.command == "list":
        if not tasks:
            print("No tasks yet.")
        else:
            for task in tasks:
                print(format_task(task))
    elif args.command == "done":
        task = mark_done(args.id)
        if task is None:
            print(f"Task with id {args.id} not found.")
        else:
            print(f"Marked done: [{task['id']}] {task['text']}")


if __name__ == "__main__":
    main()
```

Key decisions:

- `dict | None` (PEP 604, Python 3.10+) — a union type written directly with `|`, the counterpart of `dict | null` in TS, without needing `Optional[dict]`/`Union[dict, None]` from the old `typing` module.
- `find_task` returns `None` when nothing matches — the usual "search and return Optional" idiom rather than raising. Exceptions for domain errors (`TaskNotFoundError`) show up in chapter 06, once there's a proper context for them (error hierarchy, context managers).
- `if not tasks:` — relies directly on the falsiness of an empty list, more idiomatic than `if len(tasks) == 0:`.
- `type=int` on `add_argument` — argparse validates and converts the string to `int` itself, and prints a clear error on invalid input; no need to catch `ValueError` by hand at this level.

## Check yourself

1. Why is `if []:` `False` in Python, while `if ([])` in JS is always `true`? What's the fundamental difference in truthy/falsy rules for collections between the two languages?
2. What happens to a variable created inside an `if` block (not inside a function) after the block ends — and why is that fundamentally different from `let`/`const` in JS with their block scoping?
3. Why does `"3" + 3` raise a `TypeError` in Python, while `"3" + 3` in JS returns `"33"`? What does that tell you about the difference between Python's "dynamic but strict" typing and JS's typing?
4. What's the difference between `==` and `is` in Python? Why is `x is None` idiomatic while `x == None` isn't (even though both technically work for `None`)?
5. Why doesn't Python have `++`/`--`? What does that say about the language's philosophy compared to the C-like syntax JS inherited?

<details>
<summary>Answers</summary>

1. In Python, truthy/falsy for collections is based on **length**: any collection (list, dict, set, tuple, string) is falsy if empty and truthy if it has at least one element — implemented via `__bool__`/`__len__` under the hood. In JS, truthy/falsy for primitives vs. objects follows separate, historically fixed rules: falsy is only `0`, `""`, `null`, `undefined`, `NaN`, `false`, and any object (including an empty array/object) is truthy simply because it's an object, regardless of its contents.
2. The variable stays accessible after the `if` block because Python's units of scope are only `function`/`module`/`class` (more precisely: `def`/`class`/comprehensions create a new scope; `if`/`for`/`while`/`with`/`try` do not). In JS, `let`/`const` are additionally confined to the nearest `{}`, so a variable declared inside `if { let x = 5 }` is inaccessible outside it and raises a `ReferenceError`.
3. Python's `+` for `str` is implemented to require matching operand types (aside from numeric types among themselves) — attempting to add a `str` and an `int` is explicitly disallowed and raises, rather than the interpreter guessing intent. JS's `+` is historically overloaded so that if either operand is a `string`, both get coerced to strings and concatenated — a decision that dates back to the language's earliest versions and is behind many classic JS "wat" bugs.
4. `==` compares values via `__eq__` (which a class can override); `is` compares identity — the same object in memory (equivalent to a pointer comparison). `is` is idiomatic for `None` because `None` is a singleton (exactly one `None` object exists at runtime), and comparing with `is` explicitly says "this exact single object," not "a value that equals None" — which matters if some class overrides `__eq__` such that `obj == None` returns `True` for a non-empty object.
5. Increment/decrement via `++`/`--` in C-like languages carries ambiguous pre/post semantics (`x++` vs `++x`), which has historically been a source of confusion and bugs tied to expression evaluation order. Python follows "explicit is better than implicit" (from the Zen of Python) — `x += 1` leaves no question about exactly when the increment happens relative to the rest of the expression, at the cost of one extra character.

</details>

## Common mistake

A JS developer whose mental model of `"5" == 5` says "true, because JS coerces types" usually expects Python to do one of two things: either behave the same way ("surely Python coerces too"), or raise at runtime ("Python is strict — so it must throw on comparing different types"). What actually happens is a third thing: `"5" == 5` in Python is simply `False`, with no warning at all. Different types with no shared comparison protocol are just considered "not equal," not an error and not a coercion candidate. This is especially sneaky in CLI code like this project: if `args.id` somehow ends up a string (say, a parsing bug where `type=int` got dropped), the comparison `task["id"] == args.id` will silently and always be `False` — the task "won't be found," and there's no traceback to flag it. The practical takeaway: rely on `type=int`/`type=str` in argparse and on type hints, not on the hope that Python will coerce types for you during comparison — it won't.
