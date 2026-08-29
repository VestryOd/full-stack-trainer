# Syntax and types

## Theory

**Indentation as syntax.** A block after `if`, `for`, `def`, `class` and so on starts with a `:` and consists of lines sharing the same indentation. Four spaces is the convention, fixed by PEP 8 — one of the numbered Python Enhancement Proposal documents. Mixing tabs and spaces within one block isn't a warning, it's a `TabError`. There are no `{}`: there's no closing brace, the block ends when the indentation drops back.

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

That's what "strict but dynamic" means. Type checking happens at runtime, not at compile time like in TS. The interpreter never tries to guess type compatibility on your behalf.

**Core types.** `int` has arbitrary precision — no overflow, and no need for a `BigInt` equivalent. The `float` type is an IEEE754 double: the same 64-bit floating-point format that JS uses for `number`. Then come `bool` (`True`/`False`, capitalized), `str` and `None`.

Important: Python has **only one** "empty" value — `None`. There's no `null`/`undefined` split here: an uninitialized variable simply doesn't exist in Python (referencing it raises `NameError`), rather than holding an `undefined` value.

**f-strings.** The direct counterpart of template literals:

```python
name = "Max"
count = 3
print(f"{name} has {count} tasks")        # interpolation
print(f"{3.14159:.2f}")                    # "3.14" — format spec after ":"
print(f"{count=}")                         # "count=3" — debug shortcut, no JS equivalent
```

**Operators.** `==` in Python compares **values** by calling `__eq__`. There is no separate "strict" comparison operator like JS's `===`. Python does not need one: `==` never does the implicit coercions that a strict variant would have to bypass.

The `is` operator compares object **identity** — the same address in memory, not the value. It is used almost exclusively for `x is None`, and that is an idiom rather than a style preference. There is no `++`/`--`, only `x += 1`. The language designers decided the pre/post-increment ambiguity wasn't worth the syntax: "explicit is better than implicit".

Chained comparisons work: `0 < x < 10` is equivalent to `0 < x and x < 10`. In JS, `0 < x < 10` also "works", but it evaluates left to right through boolean-to-number coercion, and gives wrong results for many values.

**Truthy/falsy — gotcha #1 coming from JS.** Python has a small, fixed set of falsy values: `False`, `None`, `0`, `0.0`, `""`, `[]`, `{}`, `set()`, `()`. That means **every empty collection is falsy**.

In JS, an empty array and an empty object are always truthy: `Boolean([]) === true`, `Boolean({}) === true`. The only falsy values there are `0`, `""`, `null`, `undefined`, `NaN` and `false`. This is the exact opposite behavior for the single most common real-world check — `if tasks:`.

### Parallels with JS/TS/Node:

- **No block scope** — `if`/`for`/`while` don't create a new scope, unlike `let`/`const` inside `{}`. Scope is only function/module-level.
- **`==` never coerces** between incompatible types (unlike JS's `==`, notorious for its coercion rules); `"5" == 5` in Python is just `False` — not a `TypeError`, not `True`.
- **Empty collections are falsy**, not truthy like in JS: `if []:` in Python won't run; `if ([])` in JS always will.
- **Only `None`** — no `null`/`undefined` pair.

## What we're adding to the project

We're adding `list` (print all tasks with a done marker) and `done <id>` (mark a task as done). This is where searching an in-memory list first shows up, together with formatted output built from f-strings. Persistence is still far off. Even so, the command-line interface (CLI) is already useful within a single process run.

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

- `dict | None` (PEP 604, Python 3.10+) — a union type written directly with `|`. It is the counterpart of `dict | null` in TS. You no longer need `Optional[dict]` or `Union[dict, None]` from the old `typing` module.
- `find_task` returns `None` when nothing matches — the usual "search and return Optional" idiom rather than raising. Exceptions for domain errors (`TaskNotFoundError`) show up in chapter 06, once there's a proper context for them (error hierarchy, context managers).
- `if not tasks:` — relies directly on the falsiness of an empty list, more idiomatic than `if len(tasks) == 0:`.
- `type=int` on `add_argument` — argparse validates the string and converts it to `int` itself. It also prints a clear error on invalid input, so there is no need to catch `ValueError` by hand at this level.

## Check yourself

1. Why is `if []:` `False` in Python, while `if ([])` in JS is always `true`? What's the fundamental difference in truthy/falsy rules for collections between the two languages?
2. What happens to a variable created inside an `if` block, not inside a function, after the block ends? Why is that different from `let`/`const` in JS with their block scoping?
3. Why does `"3" + 3` raise a `TypeError` in Python, while `"3" + 3` in JS returns `"33"`? What does that tell you about the difference between Python's "dynamic but strict" typing and JS's typing?
4. What's the difference between `==` and `is` in Python? Why is `x is None` idiomatic while `x == None` isn't (even though both technically work for `None`)?
5. Why doesn't Python have `++`/`--`? What does that say about the language's philosophy compared to the C-like syntax JS inherited?

<details>
<summary>Answers</summary>

1. In Python, truthy/falsy for collections is based on **length**. Any collection — list, dict, set, tuple, string — is falsy if empty and truthy if it holds at least one element. Under the hood that goes through `__bool__` and `__len__`. In JS the rules for primitives and for objects are separate, and historically fixed. Falsy there is only `0`, `""`, `null`, `undefined`, `NaN` and `false`. Any object is truthy simply because it is an object, and its contents do not matter — an empty array and an empty object included.
2. The variable stays accessible after the `if` block. Python's units of scope are only function, module and class. More precisely: `def`, `class` and comprehensions create a new scope, while `if`, `for`, `while`, `with` and `try` do not. In JS, `let`/`const` are additionally confined to the nearest `{}`. A variable declared inside `if { let x = 5 }` is not accessible outside it, and reading it raises a `ReferenceError`.
3. Python's `+` for `str` requires matching operand types, aside from numeric types among themselves. Adding a `str` and an `int` is explicitly disallowed and raises. The interpreter does not guess your intent. JS's `+` is historically overloaded: if either operand is a `string`, both get coerced to strings and concatenated. That decision dates back to the earliest versions of the language, and it is behind many classic JS "wat" bugs.
4. `==` compares values via `__eq__`, which a class can override. The `is` operator compares identity — the same object in memory, equivalent to a pointer comparison. Using `is` is idiomatic for `None` because `None` is a singleton: exactly one `None` object exists at runtime. Comparing with `is` says "this exact single object", not "a value that equals None". That matters if some class overrides `__eq__` so that `obj == None` returns `True` for a non-empty object.
5. Increment and decrement via `++`/`--` in C-like languages carry ambiguous pre/post semantics: `x++` against `++x`. That has historically been a source of confusion, and of bugs tied to expression evaluation order. Python follows "explicit is better than implicit", a line from the Zen of Python. With `x += 1` there is no question about when exactly the increment happens relative to the rest of the expression. The cost is one extra character.

</details>

## Common mistake

A JS developer whose mental model of `"5" == 5` says "true, because JS coerces types" usually expects one of two things from Python. Either Python behaves the same way and coerces too. Or it raises at runtime, because "Python is strict, so it must throw on comparing different types".

What actually happens is a third thing: `"5" == 5` in Python is simply `False`, with no warning at all. Different types with no shared comparison protocol are just considered "not equal" — not an error, and not a candidate for coercion.

This is especially dangerous in CLI code like this project. Say `args.id` somehow ends up a string, through a parsing bug where `type=int` got dropped. Then the comparison `task["id"] == args.id` is silently always `False`. The task "won't be found", and there is no traceback to point at the cause.

The practical takeaway: rely on `type=int`/`type=str` in argparse and on type hints. Do not rely on the hope that Python will coerce types for you during comparison, because it won't.
