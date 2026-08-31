# Collections and comprehensions

## Theory

**list, tuple, dict, set — four built-in collections, and when to reach for which.**

- `list` — a mutable, ordered collection, like JS's `Array`: `[1, 2, 3]`.
- `tuple` — an **immutable**, fixed-length ordered collection: `(1, "a", True)`. The closest TS counterpart is a tuple type `[string, number]`, not just a "readonly array" — the length and per-position types are fixed by convention. Used for "a small record of a few fields" where a full class/dataclass would be overkill (until chapter 04 introduces `@dataclass` for exactly that).
- `dict` — a collection of key-value pairs: `{"a": 1, "b": 2}`. Key difference from a JS object: keys can be **any hashable type**, not just strings — `{(1, 2): "point", 3: "three"}` is valid. This makes Python's `dict` closer to JS's `Map` than to an object literal.
- `set` — an unordered collection of **unique** values: `{1, 2, 3}`. The counterpart of JS's `Set`. The gotcha: `{}` is an **empty dict**, not an empty set, because the `{}` syntax was claimed by dict first. An empty set can only be created with `set()`.

**Slices.** Work on `list`, `tuple`, `str` — anywhere the notion of a sequence applies: `seq[start:stop:step]`. Negative indices count from the end; a negative step walks backward:

```python
items = [10, 20, 30, 40, 50]
items[1:3]     # [20, 30]
items[:2]      # [10, 20]
items[-2:]     # [40, 50]
items[::-1]    # [50, 40, 30, 20, 10] — reversed, no .reverse() needed
```

This is noticeably more powerful than JS's `.slice()`. There is a third parameter, the step. And slicing works on `str` out of the box: `"hello"[::-1]` gives `"olleh"`. In JS, reversing a string means routing through an array and back.

**Comprehensions — not sugar, a core idiom.** Where you'd write `.map()`/`.filter()` in JS, Python idiomatically reaches for a comprehension:

```python
nums = [1, 2, 3, 4, 5]

[n * 2 for n in nums]              # ~ nums.map(n => n * 2)
[n for n in nums if n % 2 == 0]    # ~ nums.filter(n => n % 2 === 0)
[n * 2 for n in nums if n % 2 == 0]  # map + filter in one expression
```

Same idea for `dict` and `set`:

```python
{n: n * n for n in nums}     # dict comprehension: {1: 1, 2: 4, 3: 9, ...}
{n % 3 for n in nums}         # set comprehension: {0, 1, 2} — unique only
```

There's no comprehension form for `.reduce()` — that's `functools.reduce`, covered separately in the itertools/functools chapter.

**List comprehension vs generator expression — eager vs lazy.** `[x for x in items]`, with square brackets, builds the entire list in memory immediately. `(x for x in items)`, with parentheses and no function call, creates a **generator**. A generator produces values one at a time, lazily, as they are consumed, and it can be iterated only once:

```python
squares_list = [x * x for x in range(1_000_000)]   # allocates the whole list now
squares_gen = (x * x for x in range(1_000_000))    # almost no memory, computes on demand

sum(x for x in range(1_000_000) if x % 2 == 0)     # generator into sum(), no list
```

This is the direct reason JS has generators at all (`function*`/`yield*`) — except in Python, lazy expressions are routine, everyday code, not a rare technique. More on generators/yield in a later chapter (07).

**Unpacking in assignment.** Basic unpacking mirrors array destructuring in JS:

```python
a, b = 1, 2
a, b = b, a          # swap without a temp variable (same idea as JS's [a, b] = [b, a])
```

A `*` in the assignment target collects the "leftover" into a list — and unlike JS, the star can appear **anywhere, not just last**:

```python
first, *rest = [1, 2, 3, 4, 5]     # first=1, rest=[2, 3, 4, 5]
*head, last = [1, 2, 3, 4, 5]      # head=[1, 2, 3, 4], last=5
a, *middle, z = [1, 2, 3, 4, 5]    # a=1, middle=[2, 3, 4], z=5 — star in the middle
```

In JS, the rest element `...rest` in array destructuring must be last. So `const [a, ...rest] = arr` is valid, and `const [a, ...rest, z] = arr` is a `SyntaxError`. Python drops that restriction: the interpreter just works out how many elements are "extra" and stuffs them into the starred target, wherever it sits.

Separate from assignment unpacking, `**` spreads dicts, the counterpart of object spread in JS:

```python
defaults = {"priority": "medium", "done": False}
task = {**defaults, "text": "Buy milk"}   # ~ { ...defaults, text: "Buy milk" }
```

(`*args`/`**kwargs` in *function definitions* is a separate topic, covered in chapter 03 — here we're only talking about assignment and literals.)

### Parallels with JS/TS/Node:

- `list` ~ `Array`; `tuple` ~ a TS tuple type `[string, number]` (fixed length/types), not just a "frozen array."
- `dict` is closer to `Map` (arbitrary hashable keys) than to a JS object literal, whose keys always coerce to strings.
- List comprehension = `.map()`/`.filter()` fused into one expression. A generator expression is like a manually written `function*`, except the syntax makes it the default idiom rather than a rare tool.
- Star-unpacking can sit in the middle of an assignment target (`a, *mid, z = ...`) — in JS, the rest element must be last.

## What we're adding to the project

We're adding a `priority` to every task. For now it is just a string — `"low"`, `"medium"` or `"high"`. An `Enum` shows up in chapter 04 alongside the dataclass.

We're also extending `list` with two flags: `--status {all,done,pending}` for filtering and `--sort {id,priority}` for sorting. This is exactly where a list comprehension (filtering) and a dict comprehension (priority-to-rank lookup for sorting) fit naturally.

## Practical exercise

1. Add an optional `--priority` flag to `add`, accepting `low`/`medium`/`high` (default `medium`). A task now carries a `priority` field.
2. Add a `--status` flag to `list`: `all` (default), `done`, `pending` — filters tasks before printing.
3. Add a `--sort` flag to `list`: `id` (default) and `priority`. With `--sort priority`, higher-priority tasks come first, and tasks with equal priority fall back to ascending `id`. That is a sort by **two keys at once**, not one.
4. Implement the filtering with a list comprehension, and the "priority → numeric rank for sorting" lookup with a dict comprehension.

Things to think through:

- How do you sort by two criteria at once (priority descending, id ascending) in a **single** `sorted()` call, without a manual two-pass approach? Hint: `key` can return a tuple.
- What happens if you run `list --sort priority` on an empty task list? Does that need special handling, or does sorting/filtering an empty list just work "for free"?

## Worked solution

```python
import argparse

PRIORITY_ORDER = ["low", "medium", "high"]
PRIORITY_RANK = {name: rank for rank, name in enumerate(PRIORITY_ORDER)}

tasks: list[dict] = []


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

    if args.command == "add":
        task = add_task(args.text, args.priority)
        print(f"Added: [{task['id']}] {task['text']} ({task['priority']})")
    elif args.command == "list":
        result = sort_tasks(filter_by_status(tasks, args.status), args.sort)
        if not result:
            print("No tasks yet.")
        else:
            for task in result:
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

- `PRIORITY_RANK = {name: rank for rank, name in enumerate(PRIORITY_ORDER)}` — a dict comprehension builds `{"low": 0, "medium": 1, "high": 2}` once, at module import time. Writing that mapping by hand would risk drifting out of sync with `PRIORITY_ORDER`.
- `filter_by_status` — the list comprehension `[task for task in items if task["done"] == want_done]` replaces a manual loop with `.append()`. It reads as "every task where done matches what we asked for".
- `key=lambda t: (-PRIORITY_RANK[t["priority"]], t["id"])` — sorting by a tuple solves "two criteria, different directions" in a single `sorted()` call. Python's `sorted()` is **stable**, and it compares tuples element by element. The minus sign in front of the rank flips direction only for the first criterion, so high priority comes first and `id` stays ascending.
- Validating `priority`/`status`/`sort` is delegated entirely to `choices=...` in argparse. There is no `if priority not in {...}: raise ...` inside the business logic. An invalid value physically can't reach it: argparse aborts the process earlier, with a clear message.

## Check yourself

1. A plain `for x in range(3): pass` leaks `x` into the enclosing scope. The list comprehension `[x for x in range(3)]` does not. Why, when both use the same `for` keyword?
2. Why does `{}` create an empty `dict` rather than an empty `set`, and how do you actually create an empty set? Why is there no conflict for non-empty literals like `{1, 2, 3}`?
3. What is the difference between `[x for x in items]` and `(x for x in items)`? Think about when the values get computed, and whether you can iterate the result more than once.
4. Why can a `dict` key be a `tuple` but not a `list`? What property must a key type satisfy, and how does that relate to mutability?
5. Given `a, *b, c = [1, 2, 3, 4, 5]`, what are `a`, `b`, `c`? Describe the mechanics of the star when it isn't the last element of the assignment target.

<details>
<summary>Answers</summary>

1. A comprehension in Python 3 is effectively an implicit function. It has its own scope, and the loop variable exists only while the comprehension is being evaluated. A plain `for` statement is not a function and does not create a new scope. Chapter 01 lists the ones that do: `def`, `class` and comprehensions. Its loop variable therefore stays in whatever scope the `for` was written in, and remains visible after the loop ends.
2. The `{}` syntax was historically claimed by `dict`. Dicts existed in Python before `set` became its own type with a dedicated literal. By the time `set` got its `{1, 2, 3}` literal syntax, `{}` already meant "empty dict". Changing what `{}` means retroactively would have broken all existing code, so an empty set is only ever created with the explicit `set()` call. There is no conflict for non-empty literals: the `:` inside `{"a": 1}` tells dict and set literals apart during parsing.
3. `[x for x in items]` computes **all** the values right away and stores them in a list in memory. The result can be iterated as many times as you like, and it has a length and supports indexing. A generator expression `(x for x in items)` computes the next value only when it is actually requested. That happens on the next step of a `for` loop, or on a call to `next()`. After one full pass the generator is exhausted, and iterating it again yields nothing. That is its fundamental difference from a list.
4. A `dict` key must be **hashable**. It needs a stable `__hash__` that does not change while the object exists. In practice that means immutable, or at least not mutated in the fields that feed the hash. A `tuple` is immutable and hashable, as long as all its elements are too. A `list` is mutable. Suppose a list were used as a key, and someone later called `.append()` on it. The key's hash would then change, and the dict's internal hash table would break. Python therefore forbids lists as keys, and raises `TypeError: unhashable type`.
5. `a = 1`, `b = [2, 3, 4]`, `c = 5`. The mechanics: the interpreter first reserves exactly one element for each plain, non-starred target on either side of the star. Here that is `a`, the first element, and `c`, the last one. Everything left over after that reservation goes, as a whole list, to the starred target `b`. That is why the star can go anywhere in the target: the leftover is whatever the fixed edge positions didn't claim."

</details>

## Common mistake

The most common and least visible mistake is trying to create an empty set with `{}`. The habit comes from JS, where `{}` is just an empty object, and a set of unique values would already need an explicit `new Set()`.

In Python, `x = {}` silently creates a **dict**, not a set. The code doesn't fail right away. It fails later and somewhere unexpected — for example on `x.add(1)`, because `dict` has no `add` method (`AttributeError: 'dict' object has no attribute 'add'`).

The failure surfaces far from where `{}` was written. The traceback gives no hint about the real cause: the wrong type was picked when the variable was created.

The second common mistake is confusing eager and lazy when passing a comprehension or generator into code that walks the collection more than once. Take `gen = (t for t in tasks if t["done"])`. Calling `len(gen)` fails with `TypeError: object of type 'generator' has no len()`. Iterating `gen` twice — once to count, once to print — silently prints nothing on the second pass, with no error at all.

If the result needs more than one pass, or you need its length, use a list `[...]` rather than a generator `(...)`. A generator only pays off when the data is consumed exactly once, usually immediately and one value at a time.
