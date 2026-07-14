# asyncio: корутины, gather, async-протоколы

## Теория

**`async`/`await` синтаксически похож на JS — семантически различий больше, чем кажется.** Первое и самое важное отличие: в JS `async function f() { ... }`, вызванная без `await`, **начинает выполняться немедленно** — Promise создаётся и работа внутри стартует сразу же, просто вызывающий код не ждёт результата. В Python `async def f(): ...`, вызванная без `await`, **не выполняет вообще ничего**:

```python
async def fetch_data():
    print("started")
    return 42

coro = fetch_data()   # ничего не напечаталось! coro — просто объект-корутина
```

Это в точности повторяет механику генераторов из главы 07: вызов функции с `yield` не выполняет тело, а создаёт объект-генератор — вызов `async def`-функции не выполняет тело, а создаёт объект-корутину. Тело реально начинает исполняться только когда корутину **дожидаются** (`await coro`), планируют как `Task` (`asyncio.create_task(coro)`) или передают в `asyncio.run(coro)`. Забытый `await` — не синтаксическая ошибка, а тихий баг: Python выдаст `RuntimeWarning: coroutine 'fetch_data' was never awaited`, и код молча не сделает того, что должен был.

**Кооперативный однопоточный event loop — и почему это ближе к Node, чем что-либо из главы 11.** asyncio-event loop — однопоточный, как в Node, и это принципиально другая модель, чем `threading`/GIL из прошлой главы: там переключение между потоками навязывается интерпретатором принудительно (по таймеру или на блокирующем вызове), здесь же корутина отдаёт управление **только там, где явно написано `await`** — и нигде больше. Корутина, которая никогда не делает `await` внутри долгого цикла, блокирует **весь** event loop целиком, точно так же, как синхронный тяжёлый код блокирует единственный поток Node. Из всего курса именно `asyncio` — тот случай, где интуиция JS-разработчика про "один поток, кооперативное переключение, блокирующий код вредит всем" переносится на Python почти без поправок.

**`asyncio.gather` vs `Promise.all` — похоже, но с двумя конкретными отличиями.**

```python
results = await asyncio.gather(coro1(), coro2(), coro3())
```

Прямой аналог `Promise.all([p1, p2, p3])` — ждёт завершения всех, возвращает список результатов в том же порядке. Отличия проявляются на исключениях:

1. По умолчанию, если хоть одна корутина бросает исключение, `gather` немедленно перевыбрасывает его вызывающему коду — но **остальные корутины не отменяются автоматически** и продолжают выполняться в фоне, просто их результаты уже никто не заберёт напрямую через `gather`. Это можно проверить эмпирически:

```python
import asyncio

async def worker(name, delay, fail=False):
    await asyncio.sleep(delay)
    if fail:
        raise ValueError(f"{name} failed")
    print(f"{name}: done")
    return name

async def main():
    try:
        await asyncio.gather(worker("A", 0.3), worker("B", 0.1, fail=True), worker("C", 0.5))
    except ValueError as e:
        print("gather raised:", e)
    await asyncio.sleep(0.6)

asyncio.run(main())
```

Реальный вывод:

```txt
gather raised: B failed
A: done
C: done
```

Исключение всплывает сразу после падения `B` (через 0.1с), но `A` и `C` печатают "done" уже **после** — они не были отменены, просто доработали в фоне, никуда не передав результат.

2. `gather(..., return_exceptions=True)` меняет поведение целиком: вместо того чтобы бросать исключение, оно кладётся в результирующий список на своё место, наравне с успешными результатами:

```python
results = await asyncio.gather(worker("D", 0.1), worker("E", 0.1, fail=True), return_exceptions=True)
# results == ['D', ValueError('E failed')]
```

Это близко по духу к `Promise.allSettled` (тоже "дай мне все исходы, не падай на первом же"), но форма результата другая: `allSettled` в JS возвращает объекты `{status, value}`/`{status, reason}`, а `gather(..., return_exceptions=True)` — плоский список, где на месте упавшей корутины лежит сам объект исключения.

**`Task` — как что-то стартует немедленно, а не лениво.** `asyncio.create_task(coro)` берёт уже созданную корутину и **сразу** ставит её на выполнение в event loop, не дожидаясь `await` — с этого момента она выполняется конкурентно с остальным кодом:

```python
task = asyncio.create_task(fetch_data())  # уже начало выполняться
# ... другой код ...
result = await task                        # дождаться результата (если ещё не готов)
```

Здесь — забавный поворот: именно `create_task`, а не голая корутина, ближе всего по семантике к "вызвал async-функцию в JS" (немедленный старт), потому что голая корутина в Python, в отличие от JS Promise, **ленива** (см. первый пункт теории).

**Async context managers и async-генераторы — те же протоколы из глав 06/07, только с `await` внутри.** `async with` использует `__aenter__`/`__aexit__` вместо `__enter__`/`__exit__` — нужен, когда открытие/закрытие ресурса само требует `await` (например, асинхронное соединение с БД). `async for` использует `__aiter__`/`__anext__` вместо `__iter__`/`__next__`, и async-генератор — это `async def` с `yield` внутри — то же самое устройство, что в главе 07, но каждый шаг может быть `await`-ed.

### Параллели с JS/TS/Node:

- Python-корутина ленива (не выполняется до `await`/`create_task`), JS Promise — eager (начинает выполняться сразу при создании). `asyncio.create_task` — ближайший аналог "вызвал async-функцию и не подождал сразу".
- Однопоточный кооперативный event loop asyncio — концептуально то же самое, что у Node, в отличие от `threading`/GIL (глава 11): переключение только на явном `await`, ничего принудительного.
- `asyncio.gather` ~ `Promise.all`, но по умолчанию не отменяет "соседей" при падении одной корутины (в отличие от общего впечатления от fail-fast поведения); `return_exceptions=True` близко по духу к `Promise.allSettled`, но возвращает плоский список, а не объекты `{status, value/reason}`.
- `async with`/`async for` — те же протоколы, что context manager (глава 06) и итератор/генератор (глава 07), просто с `await`-точками внутри.

## Что добавляем в проект

Storage-слой переезжает с синхронного `sqlite3` на асинхронный `aiosqlite` — первая настоящая runtime-зависимость проекта (до сих пор `dependencies = []` в `pyproject.toml` было пустым). CLI-обработчики становятся `async def`, декоратор `log_command` учится оборачивать асинхронные функции, а точка входа `main()` остаётся синхронной (это обязательное требование entry point'а в `pyproject.toml`) и просто запускает асинхронный код через `asyncio.run(...)`. Важно: не все функции становятся асинхронными — `filter_by_status`/`sort_tasks`/`paginate`/`get_page` остаются как есть, потому что они ничего не ждут — это чистые, синхронные преобразования уже загруженного списка.

## Практическое задание

1. Установите `aiosqlite`, добавьте его в `dependencies` в `pyproject.toml` (это первая настоящая, не dev-, зависимость проекта).
2. Перепишите `storage/sqlite_storage.py`: `db_connection` — теперь `@asynccontextmanager`-функция с `await aiosqlite.connect(...)`, коммит/откат через `await conn.commit()`/`await conn.rollback()`. `init_db`, `add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks` — все становятся `async def`, каждый вызов к базе — через `await`. В `list_tasks` используйте `async for row in cursor:` вместо `fetchall()` — переберите строки лениво, по одной.
3. `filter_by_status`, `sort_tasks`, `paginate`, `get_page` — **не трогайте**, оставьте синхронными: подумайте, почему это правильно, прежде чем переписывать их "на всякий случай".
4. Обновите `TaskStorage` в `storage/protocol.py` — методы, которые реально `await`-ятся в CLI, должны быть объявлены как `async def method(...) -> ...: ...` в самом протоколе.
5. В `cli/commands.py` сделайте `handle_add`/`handle_list`/`handle_done` асинхронными (`await db.xxx(...)` вместо прямого вызова). Перепишите `log_command`: сама функция-декоратор остаётся обычной (не `async`), но возвращаемый `wrapper` теперь `async def` и делает `await func(args)` вместо `func(args)`.
6. В `cli/app.py` разделите точку входа на `async def async_main()` (реальная логика: `await db.init_db()`, разбор аргументов, `await handler(args)`) и `def main() -> None: asyncio.run(async_main())` — именно `main` остаётся тем, что зарегистрировано в `[project.scripts]`.
7. `append_log`/`FileLock` (глава 06) — оставьте синхронными. Подумайте: раз `log_command`'s `wrapper` теперь `async`, а `append_log` внутри него — блокирующий, синхронный вызов файлового I/O, не блокирует ли это event loop? В каком случае это было бы реальной проблемой, а в каком — нет для этого конкретного CLI?
8. Обновите `tests/conftest.py`/`tests/test_storage.py`/`tests/test_cli.py` под async storage-слой — без добавления `pytest-asyncio` (это отдельный инструмент из главы 16): пусть тестовые функции остаются обычными (`def test_...():`), а асинхронный сценарий внутри каждой оборачивается в `asyncio.run(...)`.

## Разбор решения

`pyproject.toml` (добавлена реальная зависимость):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["aiosqlite>=0.19"]

[project.optional-dependencies]
dev = ["pytest>=8", "mypy>=1.10"]

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.mypy]
python_version = "3.11"
strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
```

`src/taskman/storage/sqlite_storage.py` (полностью асинхронный доступ к БД, синхронные преобразования — без изменений):

```python
import itertools
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator, TypeVar

import aiosqlite

from ..models import Priority, Task, TaskNotFoundError

DB_PATH = Path("taskman.db")

T = TypeVar("T")


@asynccontextmanager
async def db_connection() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def init_db() -> None:
    async with db_connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                priority INTEGER NOT NULL,
                done INTEGER NOT NULL
            )
            """
        )


def _row_to_task(row: aiosqlite.Row) -> Task:
    return Task(
        id=row["id"],
        text=row["text"],
        priority=Priority(row["priority"]),
        done=bool(row["done"]),
    )


async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    return Task(id=task_id, text=text, priority=priority, done=False)


async def find_task(task_id: int) -> Task | None:
    async with db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_task(row)


async def get_task(task_id: int) -> Task:
    task = await find_task(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


async def mark_done(task_id: int) -> Task:
    task = await get_task(task_id)
    async with db_connection() as conn:
        await conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    task.done = True
    return task


async def list_tasks() -> list[Task]:
    tasks: list[Task] = []
    async with db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM tasks")
        async for row in cursor:
            tasks.append(_row_to_task(row))
    return tasks


def filter_by_status(items: list[Task], status: str) -> list[Task]:
    if status == "all":
        return items
    want_done = status == "done"
    return [task for task in items if task.done == want_done]


def sort_tasks(items: list[Task], sort_by: str) -> list[Task]:
    if sort_by == "priority":
        return sorted(items)
    return sorted(items, key=lambda t: t.id)


def paginate(items: list[T], page_size: int) -> Iterator[list[T]]:
    page: list[T] = []
    for item in items:
        page.append(item)
        if len(page) == page_size:
            yield page
            page = []
    if page:
        yield page


def get_page(items: list[T], page: int, page_size: int) -> list[T]:
    pages = itertools.islice(paginate(items, page_size), page - 1, page)
    return next(pages, [])
```

`src/taskman/storage/protocol.py` (обновлён — методы, обращающиеся к базе, теперь `async`):

```python
from typing import Protocol

from ..models import Priority, Task


class TaskStorage(Protocol):
    async def init_db(self) -> None: ...
    async def add_task(self, text: str, priority: Priority = ...) -> Task: ...
    async def find_task(self, task_id: int) -> Task | None: ...
    async def get_task(self, task_id: int) -> Task: ...
    async def mark_done(self, task_id: int) -> Task: ...
    async def list_tasks(self) -> list[Task]: ...
    def filter_by_status(self, items: list[Task], status: str) -> list[Task]: ...
    def sort_tasks(self, items: list[Task], sort_by: str) -> list[Task]: ...
    def get_page(self, items: list[Task], page: int, page_size: int) -> list[Task]: ...
```

(`storage/__init__.py` не меняется — `db: TaskStorage = sqlite_storage` по-прежнему проходит структурную проверку, просто теперь протокол требует async-методы, а `sqlite_storage` их и предоставляет.)

`src/taskman/cli/commands.py` (обновлён — обработчики и `log_command` асинхронны):

```python
import argparse
import functools
import sys
from typing import Any, Callable, Coroutine, TypeVar

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db

R = TypeVar("R")


def print_err(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def log_command(
    func: Callable[[argparse.Namespace], Coroutine[Any, Any, R]]
) -> Callable[[argparse.Namespace], Coroutine[Any, Any, R]]:
    @functools.wraps(func)
    async def wrapper(args: argparse.Namespace) -> R:
        print_err(f"[log] running: {args.command}")
        append_log(f"running: {args.command}")
        result = await func(args)
        print_err(f"[log] done: {args.command}")
        append_log(f"done: {args.command}")
        return result

    return wrapper


@log_command
async def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = await db.add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
async def handle_list(args: argparse.Namespace) -> None:
    all_tasks = await db.list_tasks()
    result = db.sort_tasks(db.filter_by_status(all_tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
        return
    page = db.get_page(result, args.page, args.page_size)
    if not page:
        print(f"No tasks on page {args.page}.")
        return
    total_pages = (len(result) + args.page_size - 1) // args.page_size
    for task in page:
        print(task)
    print(f"-- page {args.page} of {total_pages} --")


@log_command
async def handle_done(args: argparse.Namespace) -> None:
    try:
        task = await db.mark_done(args.id)
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

`src/taskman/cli/app.py` (обновлён — синхронная точка входа поверх асинхронной логики):

```python
import asyncio

from ..storage import db
from .commands import COMMAND_HANDLERS
from .parser import build_parser


async def async_main() -> None:
    await db.init_db()
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    await handler(args)


def main() -> None:
    asyncio.run(async_main())
```

`tests/conftest.py` (обновлён — асинхронный fixture-connection, без `pytest-asyncio`):

```python
import asyncio
from contextlib import asynccontextmanager

import aiosqlite
import pytest

from taskman.storage import sqlite_storage


@pytest.fixture
def db(monkeypatch):
    async def _connect() -> aiosqlite.Connection:
        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        return conn

    conn = asyncio.run(_connect())

    @asynccontextmanager
    async def fake_db_connection():
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)
    asyncio.run(sqlite_storage.init_db())
    yield sqlite_storage
    asyncio.run(conn.close())
```

`tests/test_storage.py` (обновлён — тестовые функции синхронные, сценарии внутри — через `asyncio.run`):

```python
import asyncio

import pytest

from taskman.models import Priority, Task, TaskNotFoundError
from taskman.storage.sqlite_storage import sort_tasks


def test_add_task_assigns_incrementing_ids(db):
    async def scenario():
        first = await db.add_task("Buy milk")
        second = await db.add_task("Write report")
        assert first.id == 1
        assert second.id == 2

    asyncio.run(scenario())


def test_get_task_raises_when_missing(db):
    async def scenario():
        with pytest.raises(TaskNotFoundError):
            await db.get_task(999)

    asyncio.run(scenario())


def test_sort_tasks_by_priority_orders_high_first():
    # чистая синхронная функция -- ни fixture db, ни asyncio.run не нужны
    low = Task(id=1, text="low", priority=Priority.LOW)
    high = Task(id=2, text="high", priority=Priority.HIGH)
    result = sort_tasks([low, high], "priority")
    assert result == [high, low]
```

Ключевые решения:

- `log_command` типизирован через `Coroutine[Any, Any, R]`, а не через более общий `Awaitable[R]`. Первая, более "обобщённая на вид" попытка (`Awaitable[R]`) технически компилировалась, но `asyncio.run(handle_add(args))` в тестах падало с ошибкой типов: `asyncio.run` требует именно `Coroutine`, а не произвольный awaitable-объект (в которые входят, например, `Future`). Поскольку `log_command` оборачивает исключительно `async def`-функции (то есть буквально корутины, не абстрактные awaitable), `Coroutine[Any, Any, R]` — не более узкий, а более **точный** тип.
- `filter_by_status`/`sort_tasks`/`paginate`/`get_page` остались синхронными: превратить их в `async def` "для единообразия" было бы типизацией, не отражающей реальность (глава 10) — они не ждут ничего, только преобразуют уже загруженный в память список.
- `append_log` внутри `log_command`'s `wrapper` остаётся синхронным, блокирующим вызовом (файловый I/O с `fcntl.flock` из главы 06) — технически это блокирует event loop на время записи. Для этого конкретного CLI это не проблема: процесс исполняет ровно одну команду за раз, никакая другая корутина не "ждёт своей очереди" в event loop'е в этот момент — блокировать нечего, кроме самого себя. В по-настоящему конкурентном приложении (веб-сервер, глава 13+) та же самая блокирующая запись в лог была бы реальной проблемой, и её стоило бы обернуть в `asyncio.to_thread(...)`, чтобы не задерживать другие запросы.
- Тесты используют `asyncio.run(...)` внутри обычных, синхронных `def test_...():`, а не `pytest-asyncio` — рабочий, честный способ тестировать асинхронный код без добавления зависимости; `pytest-asyncio` появится в главе 16, когда обычный `asyncio.run()`-подход станет action неудобным при тестировании реального HTTP-сервера.

## Проверь себя

1. Что именно печатает, а что не печатает следующий код, и почему: `coro = some_async_func()` без последующего `await`? Что произойдёт, если так и оставить корутину без `await` до конца программы?
2. В чём разница между "переключение на другой поток по таймеру" (глава 11, GIL) и "переключение на другую корутину только на `await`" (эта глава)? Почему вторая модель ближе к тому, как работает Node?
3. В примере с `asyncio.gather` одна из трёх корутин падает с исключением. Почему `A` и `C` всё равно допечатывают "done" уже после того, как исключение долетело до вызывающего кода — разве `gather` не должен был их остановить?
4. Чем `asyncio.create_task(coro)` отличается от простого вызова `coro = some_async_func()` в терминах того, когда реально начинается выполнение тела корутины?
5. Почему `filter_by_status`/`sort_tasks`/`paginate`/`get_page` в этой главе намеренно НЕ стали `async def`, хотя весь остальной storage-слой стал асинхронным?

<details>
<summary>Ответы</summary>

1. `coro = some_async_func()` не печатает вообще ничего и не выполняет ни строчки тела функции — вызов `async def`-функции создаёт объект-корутину, не запуская её, ровно как вызов функции с `yield` создаёт объект-генератор (глава 07), а не выполняет тело. Если оставить корутину без `await`/`create_task` до конца программы, интерпретатор при сборке мусора обнаружит, что объект-корутина был создан, но никогда не был "довыполнен", и выведет `RuntimeWarning: coroutine '...' was never awaited` — тело так и не выполнится ни на одну строчку, и никакой ошибки, кроме предупреждения, видно не будет.
2. В модели с потоками (глава 11) переключение между потоками навязывается интерпретатором принудительно и не спрашивает разрешения у кода — GIL передаётся другому потоку по таймеру, вне зависимости от того, "готов" ли текущий поток к этому. В asyncio-модели корутина отдаёт управление обратно event loop'у **только** в явно написанном месте — на `await` — и нигде больше; корутина, которая никогда не делает `await`, никогда и не отдаст управление сама. Node устроен точно так же: единственный поток исполняет callback до конца (run-to-completion) и передаёт управление обратно только когда сам код решает подождать чего-то асинхронного — асинхронность в обеих моделях кооперативная, а не навязанная извне.
3. Потому что `gather` по умолчанию не отменяет соседние корутины при падении одной из них — оно лишь перестаёт ждать остальных и немедленно перевыбрасывает первое пойманное исключение вызывающему коду. `A` и `C` в этот момент уже были запланированы на выполнение (через внутренние `Task`, которые `gather` создаёт для каждого аргумента) и продолжают жить своей жизнью в event loop'е независимо от того, что происходит с `gather` — просто их итоговые результаты уже некому передать напрямую через возврат `gather`, потому что вызывающий код уже получил исключение и, скорее всего, пошёл дальше по коду.
4. Простой вызов `some_async_func()` создаёт объект-корутину, полностью ленивый — ни строчки тела не выполняется, пока его не дождутся или не запланируют явно. `asyncio.create_task(coro)`, наоборот, немедленно регистрирует корутину в event loop'е как задачу, которая начинает выполняться конкурентно **сразу**, не дожидаясь, когда до неё дойдёт `await` — с этого момента она "живёт" сама по себе, а `await task` позже лишь забирает её результат (если он уже готов) или ждёт, пока станет готов.
5. Потому что типизация (и, шире, сама структура кода) должна отражать, что функция реально делает (тема главы 10) — ни одна из этих четырёх функций не обращается к базе данных, файлу или сети: они принимают уже загруженный в память `list[Task]` и синхронно его фильтруют/сортируют/нарезают на страницы. Пометить их как `async def` без единого `await` внутри было бы утверждением "эта функция может ждать чего-то", которое не соответствует действительности — а вызывающему коду пришлось бы без всякой причины писать перед ними лишний `await`.

</details>

## Частая ошибка

Самая частая ошибка при переходе с JS на asyncio — забыть `await` перед вызовом `async def`-функции, ожидая, что (как в JS) работа всё равно "как-то начнётся" в фоне. В JS `someAsyncFn()` без `await` действительно запускает Promise немедленно — просто вызывающий код не ждёт его завершения, и это часто вполне рабочий (пусть и не всегда осознанный) паттерн "fire and forget". В Python `some_async_func()` без `await`/`create_task` не делает **вообще ничего** — тело функции не начинает исполняться ни на шаг, программа просто продолжает работу дальше, будто вызова и не было, и единственный след этой ошибки — тихое предупреждение `RuntimeWarning: coroutine ... was never awaited`, которое легко не заметить в потоке остального вывода. Если нужен именно паттерн "запустить и не ждать прямо здесь" — правильный аналог из этой главы — `asyncio.create_task(coro)`, а не голый вызов корутины.

Вторая типичная ошибка — писать `async def` "на всякий случай" для функций, которые ничего не ждут, по инерции от "теперь у нас же асинхронный проект, значит всё должно быть async". Как показала эта глава на `filter_by_status`/`sort_tasks`/`paginate`/`get_page`: если функция не делает ни одного `await` внутри, оборачивание её в `async def` не даёт вообще никакого практического эффекта (async-функция без await исполняется целиком синхронно, как обычная, только чтобы получить результат, её теперь придётся дожидаться через `await` из вызывающего кода) — оно лишь добавляет лишний уровень косвенности и вводит в заблуждение читателя, ожидающего от `async def` реального ожидания чего-то внешнего.
