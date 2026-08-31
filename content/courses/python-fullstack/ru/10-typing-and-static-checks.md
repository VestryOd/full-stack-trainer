# Типизация и статические проверки

## Теория

**Type hints (аннотации типов) ничего не проверяют в рантайме — и это роднит их с TS больше, чем кажется.** Аннотации типов в Python — чистые метаданные, и интерпретатор их никак не проверяет:

```python
def add(a: int, b: int) -> int:
    return a + b

add("2", "2")  # выполнится без единой ошибки и вернёт "22" — аннотации не проверяются
```

Это звучит как "типизация не настоящая" по сравнению с TS, но на деле модель почти идентична. TypeScript тоже полностью стирает типы при компиляции в JS: `tsc` — это отдельный шаг, и в момент исполнения скомпилированного кода типов уже нет.

Разница не в том, что "Python не проверяет, а TS проверяет" — типы в рантайме стирают оба. Разница в том, **когда и насколько обязательна** проверка. `tsc` обычно встроен прямо в сборку: без него проект просто не соберётся. А `mypy` для Python — отдельный, необязательный шаг, который нужно осознанно запустить. И по умолчанию он куда снисходительнее, о чём ниже.

**Optional/Union.** `Optional[X]` — это ровно `Union[X, None]`. Современный синтаксис пишет `X | None` и `A | B` вместо `Optional[X]` и `Union[A, B]`. Он появился в Python 3.10 по PEP 604 (Python Enhancement Proposal — нумерованные документы, в которых проектируют изменения языка). Курс использует его повсюду.

Старый синтаксис (`typing.Optional`, `typing.Union`) остаётся нужен в двух случаях. Первый — код должен работать на Python ниже 3.10. Второй — кодовая база ещё не перешла на новый синтаксис.

**TypedDict — типизация словаря с известной формой.** Прямой аналог TS-интерфейса, но конкретно для случая "это `dict` с фиксированным набором ключей", а не произвольный класс:

```python
from typing import TypedDict

class TaskDict(TypedDict):
    id: int
    text: str
    priority: str
    done: bool

def load_from_json(raw: list[TaskDict]) -> list[Task]:
    return [
        Task(
            id=t["id"],
            text=t["text"],
            priority=Priority[t["priority"].upper()],
            done=t["done"],
        )
        for t in raw
    ]
```

Важно: `TypedDict` — **чисто статическая** конструкция, как и всё в этой главе. В рантайме `TaskDict` — обычный `dict`. Никто не проверяет, что там реально есть все нужные ключи нужных типов. Только `mypy` статически убеждается, что код, работающий с `TaskDict`, обращается к нему согласованно.

В главе 13 появятся Pydantic-модели. Они выглядят похоже, но, в отличие от `TypedDict`, **валидируют данные по-настоящему, в рантайме**. Это принципиальная разница, к которой мы вернёмся.

Где же `TypedDict` пригодится в этом курсе? `Task` в этом проекте с главы 04 сознательно сделан не словарём, а dataclass. Так мы бесплатно получили `__eq__`, `__lt__` и валидацию через `__post_init__`.

Поэтому в самом `taskman` естественного места для `TypedDict` не нашлось. А вот отложенное упражнение главы 08 — другое дело: в JSON-файловой версии `storage/json_file.py` данные как раз были `list[dict]` до превращения в `Task`. Если вы сохранили этот файл, `TaskDict` оттуда — подходящее место применить эту главу на практике.

**Protocol — структурная типизация, обещанная в главе 04.** В главе 4 разбирали, что `ABC` — **номинальная** типизация: класс обязан явно унаследоваться, иначе не считается подтипом, даже с полностью совпадающими методами. `Protocol` — прямой структурный аналог `interface` в TS: объект подходит под протокол, если у него есть нужные методы с нужными сигнатурами, **без всякого явного наследования**:

```python
from typing import Protocol

class TaskStorage(Protocol):
    def add_task(self, text: str, priority: Priority = ...) -> Task: ...
    def find_task(self, task_id: int) -> Task | None: ...
    def list_tasks(self) -> list[Task]: ...
```

Любой объект с методами `add_task`, `find_task` и `list_tasks` нужной формы удовлетворяет `TaskStorage`, даже если нигде не написано `class X(TaskStorage):`. В проекте мы увидим, что подходит даже **модуль** — он тоже просто объект с атрибутами.

Это и есть разница между "ABC — обязательство, заявленное заранее" и "Protocol — форма, проверенная постфактум".

**Generics (TypeVar).** Функция, которая работает с любым типом, но связывает вход и выход одним и тем же конкретным типом на каждом конкретном вызове:

```python
from typing import TypeVar

T = TypeVar("T")

def first(items: list[T]) -> T:
    return items[0]

first([1, 2, 3])        # T = int, возвращает int
first(["a", "b"])        # T = str, возвращает str
```

Прямой аналог `function first<T>(items: T[]): T` в TS — сама идея не нова, отличается синтаксис объявления. На Python 3.12+ появился современный синтаксис (PEP 695): `def first[T](items: list[T]) -> T:` — без отдельного объявления `T = TypeVar("T")`, что заметно ближе к `<T>` из TS напрямую. Курс ориентирован на 3.11+, поэтому здесь и далее — классическая форма с явным `TypeVar`, но об этой альтернативе на новых версиях стоит знать.

**`ParamSpec` — специализированный генерик для декораторов.** Отдельный инструмент для случая "написать декоратор, который сохраняет **точную** сигнатуру обёрнутой функции, какой бы она ни была":

```python
from typing import Callable, ParamSpec, TypeVar
import functools

P = ParamSpec("P")
R = TypeVar("R")

def shout(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)
    return wrapper
```

Это честный, годный инструмент — но, как выяснится в разборе решения, применять его нужно только тогда, когда декоратор *действительно* ничего не знает о содержимом своих аргументов. У нашего собственного `log_command` (глава 03) это не так — и именно `mypy` это вскрыл.

**mypy и "gradual typing".** mypy проверяет типы статически, отдельным запуском (`mypy src/`), а не как часть исполнения кода.

По умолчанию mypy **снисходителен**: функция без единой аннотации типов вообще не проверяется строго. Внутри такой функции mypy считает, что все значения имеют неизвестный тип, к которому подходит что угодно. Это принципиально отличается от TS, где даже `.ts`-файл без явных аннотаций получает содержательную проверку через вывод типов (type inference) от `tsc`.

Чтобы получить в Python строгость, сравнимую с обычным `.ts`-файлом, нужно явно включить `strict = true` в конфиге (`[tool.mypy]` в `pyproject.toml`). Одна эта строчка разом включает пачку флагов — `disallow_untyped_defs`, `warn_return_any` и другие, — которые требуют аннотировать буквально всё.

Это осознанный компромисс "gradual typing". Можно типизировать проект постепенно, файл за файлом, не включая строгость сразу для всего. Но если хочется TS-подобной строгости, это нужно явно попросить, а не получить по умолчанию.

### Параллели с JS/TS/Node:

- Модель стирания типов у Python и TS на самом деле очень похожа: оба ничего не проверяют в рантайме сами по себе. Разница в том, что `tsc` обычно обязателен для сборки, а `mypy` — отдельный, необязательный шаг.
- `TypedDict` — аналог TS `interface` конкретно для dict-формы данных. В отличие от Pydantic-моделей главы 13 (и, отчасти, TS-рантайм-валидаторов вроде zod), `TypedDict` не проверяет ничего в рантайме вообще.
- `Protocol` — структурная типизация, прямой аналог `interface` в TS (совместимость по форме); `ABC` из главы 04 — номинальная (совместимость по явному наследованию).
- `TypeVar`/generics — та же идея, что `<T>` в TS, другой синтаксис объявления; PEP 695 (Python 3.12+) заметно приближает синтаксис к TS-шному.
- mypy по умолчанию куда снисходительнее, чем `tsc` по умолчанию — строгость нужно включать явно (`strict = true`), а не получать бесплатно.

## Что добавляем в проект

В этой главе добавляем пять вещей:

- Полную типизацию storage-слоя и моделей.
- `mypy` как dev-зависимость со строгим конфигом (`strict = true`).
- Генерализацию `paginate` и `get_page` через `TypeVar`: они никогда и не были специфичны для `Task`.
- `Protocol TaskStorage`, описывающий форму storage-слоя, — обещание из главы 04, наконец выполненное.
- Заглушку для CI (continuous integration, непрерывная интеграция): минимальный workflow-файл, где `mypy` и `pytest` реально запускаются на сервере после каждого push.

По пути `mypy --strict` находит несколько настоящих пробелов в типизации из предыдущих глав. Чиним их по ходу, не выдумывая искусственных примеров.

## Практическое задание

1. Добавьте `mypy` в `[project.optional-dependencies] dev` в `pyproject.toml`, добавьте секцию `[tool.mypy]` с `python_version = "3.11"` и `strict = true`.
2. Запустите `mypy src` на текущем состоянии проекта (главы 06–09) и посмотрите на реальный список ошибок — не угадывайте заранее, что там будет.
3. Добавьте возвращаемый тип `Iterator[sqlite3.Connection]` к `db_connection`.
4. Генерализуйте `paginate`/`get_page` в `storage/sqlite_storage.py` через `TypeVar` — они принимают/возвращают `list[Task]`, но их логика никогда не трогает специфичные для `Task` поля.
5. Создайте `storage/protocol.py` с `class TaskStorage(Protocol)`, перечислив методы, которые реально использует `cli/` (сверьтесь с `cli/commands.py` и `cli/app.py`, чтобы не забыть ни одного). В `storage/__init__.py` добавьте аннотацию `db: TaskStorage = sqlite_storage`.
6. Дойдите до `cli/commands.py` и посмотрите, что говорит mypy про `log_command`. Прежде чем чинить — подумайте: `log_command` был написан в главе 03 с `*args, **kwargs` специально, чтобы "не зависеть от конкретной сигнатуры обёрнутой функции". Правда ли это по-прежнему так, если заглянуть внутрь `wrapper`?
7. Добавьте `.github/workflows/ci.yml` — минимальный workflow, устанавливающий проект (`pip install -e ".[dev]"`) и запускающий `mypy src` и `pytest` на каждый push/pull request.
8. Добейтесь `mypy src tests` без единой ошибки — для тестового кода добавьте `[[tool.mypy.overrides]]` с ослабленными требованиями (тесты не обязаны быть настолько же строго типизированы, насколько прикладной код).

## Разбор решения

`pyproject.toml` (добавлены dev-зависимость `mypy` и секция `[tool.mypy]`):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

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

`src/taskman/logging_utils.py` (обновлён — `mypy --strict` указал на нетипизированный `self._file`):

```python
import fcntl
from pathlib import Path
from typing import IO, Optional

LOG_PATH = Path("taskman.log")


class FileLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: Optional[IO[str]] = None

    def __enter__(self) -> IO[str]:
        self._file = open(self._path, "a")
        fcntl.flock(self._file, fcntl.LOCK_EX)
        return self._file

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        assert self._file is not None
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()


def append_log(message: str) -> None:
    with FileLock(LOG_PATH) as log_file:
        log_file.write(message + "\n")
```

`src/taskman/storage/sqlite_storage.py` (обновлён — типы у `db_connection`, генерализация `paginate`/`get_page`, `assert` на `lastrowid`):

```python
import itertools
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TypeVar

from ..models import Priority, Task, TaskNotFoundError

DB_PATH = Path("taskman.db")

T = TypeVar("T")


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                priority INTEGER NOT NULL,
                done INTEGER NOT NULL
            )
            """
        )


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        text=row["text"],
        priority=Priority(row["priority"]),
        done=bool(row["done"]),
    )


def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    return Task(id=task_id, text=text, priority=priority, done=False)


def find_task(task_id: int) -> Task | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def get_task(task_id: int) -> Task:
    task = find_task(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


def mark_done(task_id: int) -> Task:
    task = get_task(task_id)
    with db_connection() as conn:
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    task.done = True
    return task


def list_tasks() -> list[Task]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    return [_row_to_task(row) for row in rows]


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

`src/taskman/storage/protocol.py` (новый файл):

```python
from typing import Protocol

from ..models import Priority, Task


class TaskStorage(Protocol):
    def init_db(self) -> None: ...
    def add_task(self, text: str, priority: Priority = ...) -> Task: ...
    def find_task(self, task_id: int) -> Task | None: ...
    def get_task(self, task_id: int) -> Task: ...
    def mark_done(self, task_id: int) -> Task: ...
    def list_tasks(self) -> list[Task]: ...
    def filter_by_status(self, items: list[Task], status: str) -> list[Task]: ...
    def sort_tasks(self, items: list[Task], sort_by: str) -> list[Task]: ...
    def get_page(self, items: list[Task], page: int, page_size: int) -> list[Task]: ...
```

`src/taskman/storage/__init__.py` (обновлён):

```python
from . import sqlite_storage
from .protocol import TaskStorage

db: TaskStorage = sqlite_storage

__all__ = ["db", "TaskStorage"]
```

`src/taskman/cli/commands.py` (обновлён — `print_err` и `log_command` типизированы; сигнатура `log_command` изменилась, см. ниже):

```python
import argparse
import functools
import sys
from typing import Any, Callable, TypeVar

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db

R = TypeVar("R")


def print_err(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def log_command(
    func: Callable[[argparse.Namespace], R],
) -> Callable[[argparse.Namespace], R]:
    @functools.wraps(func)
    def wrapper(args: argparse.Namespace) -> R:
        print_err(f"[log] running: {args.command}")
        append_log(f"running: {args.command}")
        result = func(args)
        print_err(f"[log] done: {args.command}")
        append_log(f"done: {args.command}")
        return result

    return wrapper


@log_command
def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = db.add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = db.sort_tasks(db.filter_by_status(db.list_tasks(), args.status), args.sort)
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
def handle_done(args: argparse.Namespace) -> None:
    try:
        task = db.mark_done(args.id)
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

`.github/workflows/ci.yml` (новый файл — CI-заглушка):

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: mypy src
      - run: pytest
```

Ключевые решения — и что реально нашёл `mypy --strict`:

- **`paginate`/`get_page` стали генериками (`TypeVar("T")`) без единого изменения в теле функций.** Это чистый сигнал того, что их специфичность к `Task` изначально была случайной — код никогда не трогал поля `Task`, только собирал элементы в списки. Побочный эффект: теперь эти функции пригодны для пагинации чего угодно, не только задач.

- **`log_command` пришлось перетипизировать конкретно, а не через `ParamSpec`.** Первая попытка — типизировать декоратор максимально обобщённо, через `Callable[P, R]`/`P.args`/`P.kwargs`, ровно как в примере из теории. `mypy --strict` указал на проблему сразу. При `*args: P.args` элемент `args[0]` имеет тип `object`, а у `object` нет атрибута `.command`.

  Это не баг mypy: mypy честно говорит, что вы противоречите сами себе. Вы утверждаете, что декоратор ничего не знает о сигнатуре обёрнутой функции, но код внутри `wrapper` явно читает `.command` у первого аргумента. Значит, **знает**, что это `argparse.Namespace`.

  Конструкция `*args, **kwargs` в `log_command` с самой главы 03 была не про настоящую полиморфность, а про то, чтобы не хардкодить имя параметра. Сама же функция всегда предполагала ровно один аргумент нужной формы. Честная типизация — это `Callable[[argparse.Namespace], R] -> Callable[[argparse.Namespace], R]`. Она не уже прежней, она **правдивее**.

- **`cursor.lastrowid` типизирован в стабах `sqlite3` как `int | None`**, потому что в общем случае `lastrowid` может быть `None` (если последняя операция не была `INSERT`). Мы точно знаем, что сразу после `INSERT` это невозможно — `assert task_id is not None` явно кодирует это знание и для mypy (сужает тип до `int`), и для читателя.

- **`FileLock._file`** был неявно типизирован как `None`, потому что `__init__` — единственное место присваивания. Это чинят две правки: явная аннотация `Optional[IO[str]]` и `assert self._file is not None` в `__exit__`. Вместе они говорят и mypy, и человеку одно и то же: к моменту `__exit__` файл гарантированно открыт, потому что `__enter__` всегда вызывается раньше.

- **Тестам — отдельный, более мягкий профиль mypy** (`[[tool.mypy.overrides]] module = "tests.*"`). Требовать полной аннотации типов от каждой тестовой функции и фикстуры — плохой размен: читаемость тестов теряет больше, чем выигрывает строгость. Флаги `disallow_untyped_defs` и `disallow_untyped_calls`, выключенные именно для `tests.*`, оставляют строгость там, где она приносит пользу, — в прикладном коде. Тестовый код при этом не наказан за меньшую формальность.

## Проверь себя

1. Почему `add("2", "2")` из первого примера теории не бросает исключение и не падает, хотя оба аргумента аннотированы как `int`? Что именно проверяет (и не проверяет) type hint в этой сигнатуре?
2. В чём разница между `TypedDict` и `Protocol`, если оба — про "форму данных"? Для какого рода данных естественнее одно, а для какого — другое?
3. `db: TaskStorage = sqlite_storage` — но нигде в `sqlite_storage.py` не написано ничего вроде "этот модуль реализует `TaskStorage`". Как mypy вообще проверяет эту строчку, и что случится, если удалить один метод из `TaskStorage` (например, `get_page`)?
4. При первой попытке типизировать `log_command` через `ParamSpec`/`Callable[P, R]` мы получили ошибку на `namespace.command` внутри `wrapper`. Объясните своими словами, почему именно `P.args` не даёт mypy никакой информации о типе `args[0]`, и почему это не недостаток `ParamSpec`, а его осознанное ограничение.
5. Что означает "mypy по умолчанию — gradual typing", и что конкретно меняет флаг `strict = true`? Почему функция без единой аннотации типа по умолчанию не вызывает ошибок mypy, даже если внутри неё явные логические ошибки, связанные с типами?

<details>
<summary>Ответы</summary>

1. Type hints в Python вообще не участвуют в исполнении кода. Интерпретатор их читает и кладёт в `__annotations__` функции, но никак не проверяет соответствие аргументов вызова. Аннотация `int` в сигнатуре — это заявление о намерении для читателя и подсказка для внешнего инструмента вроде mypy, а не контракт времени выполнения, который Python обеспечивает сам. Проверка происходит, только если её **специально запустить**: статически, через `mypy`, отдельно от выполнения программы.
2. `TypedDict` описывает форму значения, которое физически остаётся обычным `dict` в рантайме. Это естественный выбор для JSON-подобных данных без выделенного класса: конфигов, ответов внешних API, "сырых" данных перед превращением во что-то более структурированное. `Protocol` описывает форму **поведения** — какие методы должны быть у объекта, независимо от его реальной иерархии классов. Он уместен, когда важно, что объект умеет делать, а не как устроены его данные. Пересекаются они мало: `Protocol` почти никогда не опишет форму словаря, а `TypedDict` не опишет объект с методами.
3. mypy проверяет присваивание `db: TaskStorage = sqlite_storage` структурно. Он сравнивает **набор атрибутов объекта справа** с набором методов, объявленных в `TaskStorage`. Справа здесь модуль, а у модуля, как и у любого объекта, есть атрибуты — определённые в нём функции. Для каждого метода протокола mypy ищет одноимённый атрибут у `sqlite_storage` с совместимой сигнатурой. Никакого явного "объявления" от `sqlite_storage.py` не требуется: это и есть суть структурной типизации. Если удалить `get_page` из `TaskStorage`, ничего не сломается — протокол лишь перестанет требовать этот метод. Обратный случай интереснее. Удалите `get_page` из самого `sqlite_storage.py`, оставив его в `TaskStorage`, и присваивание `db: TaskStorage = sqlite_storage` перестанет проходить проверку с ошибкой вида `Module has no attribute "get_page"`. Ровно так и произошло на практике с несколькими методами при первой, неполной версии протокола.
4. `P.args` — это не "тип каждого позиционного аргумента по отдельности". Это специальный, намеренно непрозрачный маркер. Он значит "ровно тот набор позиционных аргументов, который примет исходная функция `func`, что бы это ни было". `ParamSpec` создан для одной конкретной задачи и ничего сверх неё: гарантировать, что вызов `func(*args, **kwargs)` внутри обёртки останется типобезопасным независимо от сигнатуры `func`. Поэтому он намеренно не даёт залезть внутрь `args` и опереться на конкретный тип конкретного элемента. Иначе декоратор перестал бы быть по-настоящему универсальным: он работал бы только для функций, чей первый аргумент действительно обладает нужным атрибутом. А объявление через `ParamSpec` заявляет обратное — "для абсолютно любой сигнатуры". Если код внутри обёртки использует конкретное знание о содержимом аргументов, объявлять это знание нужно честно. Протаскивать его через инструмент, специально спроектированный такую информацию не хранить, не стоит.
5. "Gradual typing" означает, что типизация в Python — не всё-или-ничего. Можно типизировать только часть кода, оставив остальное вообще без аннотаций. От нетипизированного кода mypy по умолчанию большего не потребует: функция без единой аннотации типов вообще не анализируется на внутренние несостыковки типов. Её тело трактуется как набор значений неизвестного типа, к которому подходит что угодно. Флаг `strict = true` включает разом набор отдельных строгих флагов — `disallow_untyped_defs`, `warn_return_any` и другие. Вместе они требуют двух вещей: каждая функция должна быть полностью аннотирована, и внутри неё производится настоящая, содержательная проверка типов. Поведение переключается с "не мешаем нетипизированному коду" на "требуем типизации почти везде", и по строгости это сопоставимо с обычным `.ts`-файлом под `tsc`.

</details>

## Частая ошибка

Самая распространённая и самая опасная ошибка — считать, что аннотация сама по себе защищает. Сигнатура вида `def handle(task_id: int) -> Task:` выглядит так, будто Python отвергнет вызов с неверным типом аргумента, как это делает типизированный язык. Он не отвергнет, и разница проявляется не сразу.

Код с аннотациями типов **выглядит** как типизированный, дисциплинированный. Без отдельного запуска mypy он таким не является. Тем более — без `strict = true` и без встраивания этого запуска в CI, как мы сделали в этой главе. До этого аннотации — просто комментарии с более строгим синтаксисом, которые никто не проверяет.

На практике это выглядит так. Разработчик добавил type hints, но никогда не гонял `mypy` — или гонял без `strict`, где половина реальных ошибок молча пропускается для нетипизированного кода. Проект месяцами копит несостыковки типов и ничем не отличается от полностью нетипизированного.

Так продолжается до первого реального прогона строгого mypy. Такой прогон находит вещи, реально стоящие внимания. В этой главе на нашем собственном коде их нашлось три: несоответствие `Optional[int]`/`int`, нетипизированный атрибут и декоратор, который врал о своей универсальности.

Вторая типичная ошибка — противоположная по духу, но родственная. Вы видите код, который выглядит обобщённым, и рефлекторно берёте самый мощный доступный инструмент: `ParamSpec`, сложные вложенные `TypeVar`. А проверить сначала, настолько ли код обобщён, каким кажется, забываете.

Именно это произошло с `log_command`. Попытка типизировать его как "работает с абсолютно любой сигнатурой" была технически возможна, код бы скомпилировался. Но mypy указал на нестыковку в первой же содержательной строке тела функции: на самом деле декоратор никогда не был обобщённым, он всегда неявно предполагал `argparse.Namespace`.

Типизация — не только про то, чтобы заставить mypy замолчать. Она про то, чтобы объявленный тип отражал то, что код **действительно** делает, а не то, чем его хотелось бы видеть.
