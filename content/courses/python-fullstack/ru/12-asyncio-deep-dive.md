# asyncio: корутины, gather, async-протоколы

## Теория

**`async`/`await` синтаксически похож на JS — семантически различий больше, чем кажется.** Вот первое и самое важное отличие. В JS `async function f() { ... }`, вызванная без `await`, **начинает выполняться немедленно**. Promise создаётся, работа внутри стартует сразу же, а вызывающий код просто не ждёт результата.

В Python `async def f(): ...`, вызванная без `await`, **не выполняет вообще ничего**:

```python
async def fetch_data():
    print("started")
    return 42

coro = fetch_data()   # ничего не напечаталось! coro — просто объект-корутина
```

Это в точности повторяет механику генераторов из главы 07. Вызов функции с `yield` не выполняет тело, а создаёт объект-генератор. Вызов `async def`-функции тоже не выполняет тело, а создаёт объект-корутину.

Тело начинает исполняться только в одном из трёх случаев:

- корутину **дожидаются** (`await coro`);
- её планируют как `Task` (`asyncio.create_task(coro)`);
- её передают в `asyncio.run(coro)`.

Забытый `await` — не синтаксическая ошибка, а тихий баг. Python выдаст `RuntimeWarning: coroutine 'fetch_data' was never awaited`, и код молча не сделает того, что должен был.

**Кооперативный однопоточный event loop — и почему это ближе к Node, чем что-либо из главы 11.** Event loop в asyncio однопоточный, как в Node. Это принципиально другая модель, чем `threading` и GIL (Global Interpreter Lock, глобальная блокировка интерпретатора) из прошлой главы.

Там переключение между потоками навязывается интерпретатором принудительно: по таймеру или на блокирующем вызове. Здесь корутина отдаёт управление **только там, где явно написано `await`** — и нигде больше.

Корутина, которая никогда не делает `await` внутри долгого цикла, блокирует **весь** event loop целиком. Точно так же тяжёлый синхронный код блокирует единственный поток Node. Из всего курса именно `asyncio` — тот случай, где интуиция JS-разработчика переносится на Python почти без поправок: один поток, кооперативное переключение, блокирующий код вредит всем.

**`asyncio.gather` vs `Promise.all` — похоже, но с двумя конкретными отличиями.**

```python
results = await asyncio.gather(coro1(), coro2(), coro3())
```

Это прямой аналог `Promise.all([p1, p2, p3])`. Он ждёт завершения всех и возвращает список результатов в том же порядке. Отличия проявляются на исключениях:

1. По умолчанию, если хоть одна корутина бросает исключение, `gather` немедленно перевыбрасывает его вызывающему коду. Но **остальные корутины не отменяются автоматически**. Они продолжают выполняться в фоне, и их результаты уже никто не заберёт напрямую через `gather`. Это можно проверить эмпирически:

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
        await asyncio.gather(
            worker("A", 0.3), worker("B", 0.1, fail=True), worker("C", 0.5)
        )
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

Исключение всплывает сразу после падения `B`, через 0.1с. Но `A` и `C` печатают "done" уже **после**. Они не были отменены, просто доработали в фоне, никуда не передав результат.

2. `gather(..., return_exceptions=True)` меняет поведение целиком. Вместо того чтобы бросать исключение, оно кладётся в результирующий список на своё место, наравне с успешными результатами:

```python
results = await asyncio.gather(
    worker("D", 0.1), worker("E", 0.1, fail=True), return_exceptions=True
)
# results == ['D', ValueError('E failed')]
```

Это близко по духу к `Promise.allSettled`: оба говорят "дай мне все исходы, не падай на первом же". Но форма результата другая. В JS `allSettled` возвращает объекты `{status, value}` и `{status, reason}`. В Python `gather` возвращает плоский список, где на месте упавшей корутины лежит сам объект исключения.

**`Task` — как что-то стартует немедленно, а не лениво.** Вызов `asyncio.create_task(coro)` берёт уже созданную корутину и **сразу** ставит её на выполнение в event loop, не дожидаясь `await`. С этого момента она выполняется конкурентно с остальным кодом:

```python
task = asyncio.create_task(fetch_data())  # уже начало выполняться
# ... другой код ...
result = await task                        # дождаться результата (если ещё не готов)
```

Здесь забавный поворот. Ближе всего по семантике к "вызвал async-функцию в JS" оказывается `create_task`, а не голая корутина, потому что `create_task` стартует немедленно. Голая корутина в Python **ленива**, в отличие от JS Promise — см. первый пункт теории.

**Async context managers и async-генераторы — те же протоколы из глав 06/07, только с `await` внутри.** Конструкция `async with` использует `__aenter__`/`__aexit__` вместо `__enter__`/`__exit__`. Она нужна, когда открытие и закрытие ресурса само требует `await` — например, асинхронное соединение с БД (базой данных).

Конструкция `async for` использует `__aiter__`/`__anext__` вместо `__iter__`/`__next__`. Async-генератор — это `async def` с `yield` внутри. Устройство то же самое, что в главе 07, только на каждом шаге может стоять `await`.

### Параллели с JS/TS/Node:

- Python-корутина ленива: она не выполняется до `await` или `create_task`. JS Promise, наоборот, жадный (eager) — он начинает выполняться сразу при создании. Ближайший аналог фразы "вызвал async-функцию и не подождал сразу" — это `asyncio.create_task`.
- Однопоточный кооперативный event loop asyncio — концептуально то же самое, что у Node, в отличие от `threading` и GIL (глава 11). Переключение происходит только на явном `await`, ничего принудительного здесь нет.
- `asyncio.gather` соответствует `Promise.all`, но по умолчанию не отменяет соседние корутины при падении одной из них. Это расходится с привычным ожиданием поведения fail-fast. А `return_exceptions=True` близко по духу к `Promise.allSettled`, но возвращает плоский список, а не объекты `{status, value/reason}`.
- `async with`/`async for` — те же протоколы, что context manager (глава 06) и итератор/генератор (глава 07), просто с `await`-точками внутри.

## Что добавляем в проект

Слой хранения переезжает с синхронного `sqlite3` на асинхронный `aiosqlite`. Это первая настоящая зависимость, нужная проекту во время работы: до сих пор `dependencies = []` в `pyproject.toml` было пустым.

Обработчики CLI (command-line interface, интерфейс командной строки) становятся `async def`, а декоратор `log_command` учится оборачивать асинхронные функции. Точка входа `main()` остаётся синхронной — этого требует запись в `[project.scripts]` файла `pyproject.toml`. Она просто запускает асинхронный код через `asyncio.run(...)`.

Важно: не все функции становятся асинхронными. `filter_by_status`, `sort_tasks`, `paginate` и `get_page` остаются как есть, потому что они ничего не ждут. Это чистые синхронные преобразования уже загруженного списка.

## Практическое задание

1. Установите `aiosqlite`, добавьте его в `dependencies` в `pyproject.toml`. Это первая настоящая зависимость проекта, а не зависимость для разработки.
2. Перепишите `storage/sqlite_storage.py`. Здесь `db_connection` становится `@asynccontextmanager`-функцией с `await aiosqlite.connect(...)`, а коммит и откат идут через `await conn.commit()` и `await conn.rollback()`. Все функции `init_db`, `add_task`, `find_task`, `get_task`, `mark_done` и `list_tasks` становятся `async def`, каждый вызов к базе — через `await`. В `list_tasks` используйте `async for row in cursor:` вместо `fetchall()` — переберите строки лениво, по одной.
3. `filter_by_status`, `sort_tasks`, `paginate`, `get_page` — **не трогайте**, оставьте синхронными: подумайте, почему это правильно, прежде чем переписывать их "на всякий случай".
4. Обновите `TaskStorage` в `storage/protocol.py`. Методы, которые в CLI реально вызываются через `await`, должны быть объявлены в самом протоколе как `async def method(...) -> ...: ...`.
5. В `cli/commands.py` сделайте `handle_add`, `handle_list` и `handle_done` асинхронными: `await db.xxx(...)` вместо прямого вызова. Перепишите и `log_command`. Сама функция-декоратор остаётся обычной, не `async`. А возвращаемый ею `wrapper` теперь `async def` и делает `await func(args)` вместо `func(args)`.
6. В `cli/app.py` разделите точку входа надвое. Первая половина — `async def async_main()` с реальной логикой: `await db.init_db()`, разбор аргументов, `await handler(args)`. Вторая половина — `def main() -> None: asyncio.run(async_main())`, и именно `main` зарегистрирован в `[project.scripts]`.
7. `append_log` и `FileLock` (глава 06) оставьте синхронными. Дальше подумайте вот о чём. Функция `wrapper` внутри `log_command` теперь `async`, а `append_log` внутри него — блокирующий синхронный вызов файлового I/O (input/output, ввод-вывод). Не блокирует ли это event loop? В каком случае это было бы реальной проблемой, а в каком — нет для этого конкретного CLI?
8. Обновите `tests/conftest.py`, `tests/test_storage.py` и `tests/test_cli.py` под асинхронный слой хранения. Сделайте это без `pytest-asyncio` — это отдельный инструмент, он появится в главе 16. Пусть тестовые функции остаются обычными (`def test_...():`), а асинхронный сценарий внутри каждой оборачивается в `asyncio.run(...)`.

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

`tests/conftest.py` (обновлён — асинхронное соединение внутри фикстуры, без `pytest-asyncio`):

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
    # чистая синхронная функция -- ни фикстура db, ни asyncio.run не нужны
    low = Task(id=1, text="low", priority=Priority.LOW)
    high = Task(id=2, text="high", priority=Priority.HIGH)
    result = sort_tasks([low, high], "priority")
    assert result == [high, low]
```

Ключевые решения:

- `log_command` типизирован через `Coroutine[Any, Any, R]`, а не через более общий `Awaitable[R]`. Первая, более "обобщённая на вид" попытка с `Awaitable[R]` технически компилировалась. Но `asyncio.run(handle_add(args))` в тестах падал с ошибкой типов: `asyncio.run` требует именно `Coroutine`, а не произвольный awaitable-объект, то есть любой объект, которого можно дождаться. В эту более широкую категорию входят, например, `Future`. При этом `log_command` оборачивает исключительно `async def`-функции, то есть буквально корутины, а не абстрактные awaitable. Значит, `Coroutine[Any, Any, R]` — не более узкий, а более **точный** тип.
- `filter_by_status`, `sort_tasks`, `paginate` и `get_page` остались синхронными. Превратить их в `async def` "для единообразия" означало бы типизацию, не отражающую реальность (глава 10). Они ничего не ждут, а только преобразуют уже загруженный в память список.
- `append_log` внутри `wrapper`, возвращаемого из `log_command`, остаётся синхронным, блокирующим вызовом. Это файловый I/O с `fcntl.flock` из главы 06, и он блокирует event loop на время записи. Для этого конкретного CLI это не проблема. Процесс исполняет ровно одну команду за раз. Никакая другая корутина не ждёт своей очереди в event loop в этот момент, блокировать просто нечего. В по-настоящему конкурентном приложении — веб-сервер, глава 13+ — та же самая блокирующая запись в лог была бы реальной проблемой. Там её стоило бы обернуть в `asyncio.to_thread(...)`, чтобы не задерживать другие запросы.
- Тесты используют `asyncio.run(...)` внутри обычных, синхронных `def test_...():`, а не `pytest-asyncio`. Это рабочий, честный способ тестировать асинхронный код без добавления зависимости. Инструмент `pytest-asyncio` появится в главе 16, когда обычный подход с `asyncio.run()` станет по-настоящему неудобным при тестировании реального HTTP-сервера.

## Проверь себя

1. Что именно печатает, а что не печатает следующий код, и почему: `coro = some_async_func()` без последующего `await`? Что произойдёт, если так и оставить корутину без `await` до конца программы?
2. В чём разница между "переключение на другой поток по таймеру" (глава 11, GIL) и "переключение на другую корутину только на `await`" (эта глава)? Почему вторая модель ближе к тому, как работает Node?
3. В примере с `asyncio.gather` одна из трёх корутин падает с исключением. Почему `A` и `C` всё равно допечатывают "done" уже после того, как исключение долетело до вызывающего кода — разве `gather` не должен был их остановить?
4. Чем `asyncio.create_task(coro)` отличается от простого вызова `coro = some_async_func()` в терминах того, когда реально начинается выполнение тела корутины?
5. Почему `filter_by_status`/`sort_tasks`/`paginate`/`get_page` в этой главе намеренно **не** стали `async def`, хотя весь остальной слой хранения стал асинхронным?

<details>
<summary>Ответы</summary>

1. `coro = some_async_func()` не печатает вообще ничего и не выполняет ни строчки тела функции. Вызов `async def`-функции создаёт объект-корутину, не запуская её. Ровно так же вызов функции с `yield` создаёт объект-генератор (глава 07), а не выполняет тело. Теперь допустим, что корутину так и оставили без `await` и без `create_task` до конца программы. Интерпретатор при сборке мусора обнаружит, что объект-корутина был создан, но никогда не был довыполнен, и выведет `RuntimeWarning: coroutine '...' was never awaited`. Тело так и не выполнится ни на одну строчку, и никакой ошибки, кроме предупреждения, видно не будет.
2. В модели с потоками (глава 11) переключение между потоками навязывается интерпретатором принудительно и не спрашивает разрешения у кода. GIL передаётся другому потоку по таймеру, вне зависимости от того, готов ли к этому текущий поток. В модели asyncio корутина отдаёт управление обратно в event loop **только** в явно написанном месте — на `await`, и нигде больше. Корутина, которая никогда не делает `await`, никогда и не отдаст управление сама. Node устроен точно так же. Единственный поток исполняет callback до конца (run-to-completion) и передаёт управление обратно только тогда, когда сам код решает подождать чего-то асинхронного. Асинхронность в обеих моделях кооперативная, а не навязанная извне.
3. Потому что `gather` по умолчанию не отменяет соседние корутины при падении одной из них. Он лишь перестаёт ждать остальных и немедленно перевыбрасывает первое пойманное исключение вызывающему коду. `A` и `C` в этот момент уже были запланированы на выполнение — через внутренние объекты `Task`, которые `gather` создаёт для каждого аргумента. Они продолжают выполняться в event loop независимо от того, что происходит с `gather`. Просто их итоговые результаты уже некому забрать через возврат `gather`: вызывающий код уже получил исключение и, скорее всего, пошёл дальше.
4. Простой вызов `some_async_func()` создаёт полностью ленивый объект-корутину. Ни строчки тела не выполняется, пока его не дождутся или не запланируют явно. Вызов `asyncio.create_task(coro)`, наоборот, немедленно регистрирует корутину в event loop как задачу. Эта задача начинает выполняться конкурентно **сразу**, не дожидаясь, когда до неё дойдёт `await`. С этого момента она живёт сама по себе. Более поздний `await task` лишь забирает её результат, если он уже готов, или ждёт, пока результат станет готов.
5. Потому что типизация — и, шире, сама структура кода — должна отражать, что функция реально делает. Это тема главы 10. Ни одна из этих четырёх функций не обращается к базе данных, файлу или сети. Они принимают уже загруженный в память `list[Task]` и синхронно его фильтруют, сортируют и нарезают на страницы. Пометить их как `async def` без единого `await` внутри значило бы заявить, что функция может чего-то ждать. Это не соответствует действительности. А вызывающему коду пришлось бы без всякой причины писать перед ними лишний `await`.

</details>

## Частая ошибка

Самая частая ошибка при переходе с JS на asyncio — забыть `await` перед вызовом `async def`-функции. Ожидание при этом такое: как в JS, работа всё равно "как-то начнётся" в фоне.

В JS `someAsyncFn()` без `await` действительно запускает Promise немедленно. Просто вызывающий код не ждёт его завершения. Это часто вполне рабочий, пусть и не всегда осознанный, паттерн "fire and forget" — "запустил и забыл".

В Python `some_async_func()` без `await` и без `create_task` не делает **вообще ничего**. Тело функции не начинает исполняться ни на шаг, программа просто продолжает работу дальше, будто вызова и не было. Единственный след этой ошибки — тихое предупреждение `RuntimeWarning: coroutine ... was never awaited`, которое легко не заметить в потоке остального вывода.

Нужен именно паттерн "запустить и не ждать прямо здесь"? Правильный аналог из этой главы — `asyncio.create_task(coro)`, а не голый вызов корутины.

Вторая типичная ошибка — писать `async def` "на всякий случай" для функций, которые ничего не ждут. Рефлекс за этим такой: теперь у нас асинхронный проект, значит всё должно быть асинхронным.

Эта глава показала обратное на `filter_by_status`, `sort_tasks`, `paginate` и `get_page`. Если функция не делает ни одного `await` внутри, оборачивание её в `async def` не даёт вообще никакого практического эффекта. Async-функция без `await` внутри исполняется целиком синхронно, как обычная. Меняется только одно: чтобы получить результат, вызывающему коду теперь придётся написать `await`.

То есть обёртка лишь добавляет лишний уровень косвенности. Хуже того, она вводит в заблуждение читателя, который ждёт от `async def` реального ожидания чего-то внешнего.
