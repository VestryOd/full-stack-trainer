# Iterators, generators, itertools, and functools

## Theory

**The iterator protocol.** `for x in obj:` isn't a language primitive on its own — it's sugar over two methods: `iter(obj)` calls `obj.__iter__()` and gets back an **iterator** — an object with a `__next__()` method; `for` then calls `next(iterator)` repeatedly until it hits `StopIteration`, which it catches itself (it never surfaces to your code). You can implement the protocol by hand like this:

```python
class Countdown:
    def __init__(self, start: int) -> None:
        self.current = start

    def __iter__(self):
        return self          # the object is its own iterator

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1

for n in Countdown(3):
    print(n)   # 3, 2, 1
```

`__iter__` returning `self` is a typical pattern for objects meant to be consumed **once**: once `current` hits 0, `Countdown` is exhausted for good — a second `for` over the same object yields nothing (unlike `list`, whose `__iter__` creates a fresh, independent iterator every time, which is why you can loop over a list as many times as you like).

**Generators via `yield`.** Same idea, dramatically more compact:

```python
def countdown(start: int):
    current = start
    while current > 0:
        yield current
        current -= 1

for n in countdown(3):
    print(n)   # 3, 2, 1
```

No manual `__iter__`/`__next__`/`StopIteration`/state tracking (`self.current`) — a function with `yield` doesn't run its body immediately when called (`countdown(3)`); it returns a generator object that already implements the iterator protocol itself. Each `next()` resumes execution exactly where the last `yield` left off, with every local variable exactly as it was — that's what "the function pauses" actually means. This is exactly the generator expression from chapter 02 (`(x for x in items)`), just written as a full function with an arbitrarily complex body instead of a one-line expression.

**Comparison with JS generators.** In JS, `function*`/`yield` are mechanically similar — the same suspend/resume, `.next()` returning `{value, done}`. The difference is how often each language reaches for it. In Python, generators and laziness are baked into everyday code: `range()` isn't a list, it's a lazy sequence; `dict.keys()`/`.values()`/`.items()` are lazy views, not lists; `map()`/`filter()` in Python 3 are also lazy (unlike Python 2, where they returned lists); reading a file line by line (`for line in f:`) is an iterator too, not a list of lines held in memory. In JS, `function*` is a comparatively rare, specialized tool (custom iterables, some pre-`async/await` async patterns), not something you run into in ordinary everyday code.

One more difference worth calling out explicitly: JS has **two different** iteration mechanisms — `for...in` (iterates an object's **keys**, doesn't use the iterator protocol at all) and `for...of` (uses `Symbol.iterator`, the conceptual counterpart of Python's protocol). Mixing them up is a classic JS beginner mistake (`for...in` on an array iterates indices as strings and picks up inherited enumerable properties too). Python has no such fork: `for x in obj` always goes through the same `__iter__`/`__next__` protocol, for anything — a list, a dict, a file, a generator, your own class.

**`itertools`.** A module of building blocks for working with iterators lazily:

```python
import itertools

itertools.islice(iterable, start, stop)   # a lazy slice — works on ANY iterator,
                                            # not just ones supporting [start:stop]
itertools.chain(iter1, iter2)              # stitch several iterables into one, lazily
itertools.count(10)                        # an infinite counter: 10, 11, 12, ...
```

`islice` matters especially: an ordinary slice `seq[start:stop]` requires `seq` to support indexing (`__getitem__`) — a generator doesn't have that. `itertools.islice` works on any iterable at all, including infinite generators, consuming only what's actually needed and nothing more.

One nuance that's easy to trip over: `itertools.groupby(iterable, key)` only groups **consecutive** elements sharing a key — it's not "SQL GROUP BY," it's closer to "collapse adjacent runs." If the input isn't pre-sorted by that key, equal keys scattered across different positions in the sequence end up in **separate** groups.

**`functools`.** Three specific tools:

`reduce(func, iterable, initial)` — the direct answer to the question left open in chapter 02: there's no comprehension form for `.reduce()`, because that's `functools.reduce`:

```python
from functools import reduce

total = reduce(lambda acc, x: acc + x, [1, 2, 3, 4], 0)
# ~ [1, 2, 3, 4].reduce((acc, x) => acc + x, 0)
```

`partial(func, *args, **kwargs)` — pre-binds part of the arguments, returning a new callable:

```python
from functools import partial

print_err = partial(print, file=sys.stderr)
print_err("oops")   # equivalent to print("oops", file=sys.stderr)
```

The closest JS counterpart is `fn.bind(thisArg, ...args)`, but `.bind()` is primarily about fixing `this`, with argument binding as a secondary capability. In Python, `self` was never implicit to begin with (chapter 04), so `partial` is a clean, general-purpose "pin down some arguments" tool, with none of the call-context baggage.

`lru_cache` — a memoization decorator: caches a function's result keyed by its hashable arguments, so a repeat call with the same arguments skips re-running the body:

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
```

Two conditions, without which `lru_cache` is a bad idea: (1) every argument must be **hashable** (a list argument gets you `TypeError: unhashable type: 'list'`, a direct callback to chapter 02's discussion of `dict`-key hashability); (2) the function must be **pure** — its result should depend only on its arguments, not on external mutable state, or the cache will silently start returning stale data. That's exactly why `lru_cache` won't show up in this project's storage functions going forward — they take lists (unhashable) and/or read shared mutable state (`tasks`), either of which makes caching the result incorrect.

### Parallels with JS/TS/Node:

- `for...of` in JS uses `Symbol.iterator` — the conceptual counterpart of `__iter__`/`__next__` — but JS also has a **different** `for...in` (iterates keys, not the iterator protocol) — a classic source of confusion; Python has exactly one iteration protocol, for everything.
- Generators in JS (`function*`) are mechanically similar but stay a niche tool; in Python, laziness is part of everyday idioms (`range`, dict views, `map`/`filter`, reading files).
- `functools.reduce` ~ `.reduce()` — finally, the direct equivalent promised back in chapter 02.
- `functools.partial` ~ `.bind()`, but without the `this`-fixing baggage — there's nothing to fix in Python, since `self` was always explicit anyway.

## What we're adding to the project

We're adding lazy paginated output to the `list` command: `--page`/`--page-size` flags, a `paginate` generator that lazily yields pages as needed, and `itertools.islice` on top of it to grab exactly the requested page without building all the others. Along the way, we tidy up the repeated `print(..., file=sys.stderr)` calls in `cli/commands.py` with `functools.partial`.

## Practical exercise

1. In `storage/memory.py`, write a generator `paginate(items: list[Task], page_size: int)` that uses `yield` to lazily produce successive pages (lists of up to `page_size` tasks each).
2. Write `get_page(items, page, page_size)`, using `itertools.islice` on top of `paginate(...)` to pull out exactly the requested (1-based) page; if the page is out of range, return `[]`, using `next(iterator, default)` rather than `try/except StopIteration`.
3. Add `--page` (default 1) and `--page-size` (default 5) flags to the `list` subcommand.
4. Update `handle_list` so it prints only the requested page, plus a `-- page X of Y --` footer (compute the total page count with integer division).
5. In `cli/commands.py`, replace the repeated `print(..., file=sys.stderr)` calls with a module-level `print_err = functools.partial(print, file=sys.stderr)`.

Things to think through:

- Why can't `lru_cache` be safely applied to `get_page`/`sort_tasks`/any of the current storage functions, even though caching would in principle speed up repeated calls? Name both things working against it here.
- If you call `get_page` on a 100-item list with `page_size=5`, requesting page 1 — how many items does the `for item in items:` loop inside `paginate` actually process? What about page 3? What about a nonexistent page 999?

## Worked solution

Only `storage/memory.py`, `cli/parser.py`, and `cli/commands.py` change; everything else stays the same as in chapter 06.

`src/taskman/storage/memory.py` (updated — `paginate`/`get_page` added, everything else unchanged):

```python
import itertools

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


def paginate(items: list[Task], page_size: int):
    """Lazily yield successive pages of up to page_size tasks."""
    page: list[Task] = []
    for task in items:
        page.append(task)
        if len(page) == page_size:
            yield page
            page = []
    if page:
        yield page


def get_page(items: list[Task], page: int, page_size: int) -> list[Task]:
    pages = itertools.islice(paginate(items, page_size), page - 1, page)
    return next(pages, [])
```

`src/taskman/cli/parser.py` (updated — two new arguments on `list`):

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
    list_parser.add_argument("--page", type=int, default=1, help="Page number (1-based)")
    list_parser.add_argument("--page-size", type=int, default=5, help="Tasks per page")

    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("id", type=int, help="Task id")

    return parser
```

`src/taskman/cli/commands.py` (updated):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import memory

print_err = functools.partial(print, file=sys.stderr)


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print_err(f"[log] running: {namespace.command}")
        append_log(f"running: {namespace.command}")
        result = func(*args, **kwargs)
        print_err(f"[log] done: {namespace.command}")
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
        return
    page = memory.get_page(result, args.page, args.page_size)
    if not page:
        print(f"No tasks on page {args.page}.")
        return
    total_pages = (len(result) + args.page_size - 1) // args.page_size
    for task in page:
        print(task)
    print(f"-- page {args.page} of {total_pages} --")


@log_command
def handle_done(args: argparse.Namespace) -> None:
    try:
        task = memory.mark_done(args.id)
    except TaskNotFoundError as error:
        print_err(f"Error: {error}")
        return
    print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}
```

Key decisions:

- `paginate` is an ordinary generator function: it accumulates items into `page`, yields it once `page_size` items have piled up, resets, and keeps going; the last, partial page is yielded after the loop if anything's left in it.
- `get_page` doesn't write its own "skip N pages" loop — `itertools.islice(paginate(...), page - 1, page)` pulls exactly one item at the right index out of the stream of pages, without ever materializing the full list of all pages.
- `next(pages, [])` instead of `try/except StopIteration` — `next()` with a second, default argument handles "the iterator is empty" declaratively, with no exception involved at all; for a page beyond the available data, `islice` simply never finds an element at the requested index, and `next` returns `[]`.
- `print_err = functools.partial(print, file=sys.stderr)` replaces every spot that used to write `print(..., file=sys.stderr)` directly — twice inside `log_command`, once in `handle_done`; `print` itself isn't overridden or manually wrapped, we just create a version of it with `file` already pinned.
- `lru_cache` doesn't appear anywhere in this file — neither `get_page` nor `sort_tasks` are good candidates: both take `list[Task]` (an unhashable argument), and both implicitly depend on the contents of `tasks` possibly having changed between calls (the `done` flag, new tasks) — caching the result would simply be wrong.

## Check yourself

1. Why is `Countdown.__iter__` returning `self` a fine pattern for a single-use iterator, but a poor choice for a class like `TaskList` that needs to support several independent passes at once (say, two nested `for` loops over the same task list)?
2. What exactly does a generator "remember" between two `next()` calls — and why does `yield` remove the need to write `self.current = ...` by hand, the way the class-based iterator protocol does?
3. How is `itertools.islice(iterable, start, stop)` fundamentally different from a plain slice `seq[start:stop]` — what makes the first work on a generator while the second doesn't?
4. Given `next(some_iterator, "default")`: what happens if the iterator still has items left? What if it's already exhausted? Why is this better than wrapping `next(some_iterator)` in `try/except StopIteration` for the same result?
5. Why does `functools.lru_cache`, applied to a function that takes a `list` as an argument, break before the first call with real data even happens — what error occurs exactly, and why?

<details>
<summary>Answers</summary>

1. `__iter__` returning `self` means the object **is** its own iterator — it has exactly one "current position," shared by everyone iterating it. If two nested `for` loops iterate the same `Countdown` object at once, they'd be advancing the same shared counter, interfering with each other. `list.__iter__()` instead creates a **new** iterator object every time `iter()` is called, with its own independent position — which is why you can loop over the same list in several concurrent loops with no collision. For `TaskList`, if it needs to support several independent passes, `__iter__` should return a fresh helper iterator object each time (or use `yield` — a generator function also creates a new, independent generator object on every call).
2. A generator remembers the function's entire execution frame at the moment of `yield` — the values of every local variable and the exact line where execution paused. `yield` is a capability built into the interpreter to suspend and later resume that specific function from that exact spot; reimplementing the same thing by hand with a class requires explicitly storing every variable that needs to "survive" between calls to `__next__` as a `self` attribute (`self.current` in `Countdown`), because an ordinary method has no automatic "freeze and thaw local variables" — and that's the entire chunk of work `yield` removes.
3. `seq[start:stop]` requires `seq` to have a `__getitem__` method — random access by index — which a generator doesn't provide at all (it only offers "give me the next item," with no "give me item number N directly"). `itertools.islice` doesn't require indexing: it just calls `next()` the right number of times, skipping and discarding items up to `start`, then yielding items up to `stop`, and it works on anything implementing the iterator protocol — including infinite generators, where `seq[start:stop]` is fundamentally impossible (there's no way to know the length of, or index into, an infinite sequence).
4. If the iterator still has items, `next(some_iterator, "default")` returns the next item as usual — the second argument simply goes unused in that case. If the iterator is exhausted, instead of raising `StopIteration`, the call quietly returns `"default"`. This beats `try/except StopIteration` precisely in cases where "the iterator is empty" isn't an error — it's a normal, expected outcome (like "there's no content beyond the last page") — the code reads as a single expression with an explicit fallback value, rather than as handling an exceptional situation that isn't actually exceptional.
5. `lru_cache` caches results keyed by the call's arguments, and for that the arguments must be **hashable** — the cache is internally built like a dict, `{arguments: result}`, and as covered in chapter 02, a mutable object like a `list` can't be a dict key. The error doesn't show up when the function is defined (the decorator applies just fine) — it shows up on the very first **call** with a list argument: `TypeError: unhashable type: 'list'`, because that's exactly the moment `lru_cache` tries to use the passed-in list as part of the key for its own internal cache.

</details>

## Common mistake

The most common mistake when first working with generators is trying to iterate the same generator twice, expecting the second pass to start over from the beginning, the way it would with a list. A developer used to writing `for x of arr` in JS ten times over the same array with no side effects at all carries that expectation into Python — but a generator, unlike a list, **is** a single-use iterator (see question 1 above): once it's exhausted (or once you've explicitly called `next()` all the way through), a repeat `for` over the same object runs zero times, with no error at all — it just silently prints nothing. In the context of `paginate`, this means: if you store the result of `paginate(tasks, 5)` in a variable and try to fetch page 2 first, then page 1 from the same object, the second request won't work, because the generator has already moved forward and can't "rewind." Every new page request needs a fresh call to `paginate(...)` — which is exactly what `get_page` does, creating a brand-new generator on every call.

The second common mistake is using `itertools.groupby` as a "regular" group-by, expecting it to find and group every element sharing a key across the whole sequence, the way SQL's grouping or lodash's `_.groupBy` do. `groupby` only groups **adjacent** elements sharing a key; if the data isn't pre-sorted by that key, equal values that aren't next to each other end up in separate, distinct groups — the code doesn't crash or warn, it just produces more groups than you expected.
