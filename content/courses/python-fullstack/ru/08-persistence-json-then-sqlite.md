# Персистентность: сначала JSON, потом SQLite

## Теория

**JSON-файл: `pathlib` + `json`.** Самый простой способ пережить перезапуск процесса — сохранять данные в файл целиком и перечитывать его при старте:

```python
import json
from pathlib import Path

path = Path("tasks.json")

# запись
data = [{"id": 1, "text": "Buy milk", "priority": "low", "done": False}]
path.write_text(json.dumps(data, indent=2))

# чтение
data = json.loads(path.read_text()) if path.exists() else []
```

`pathlib.Path` объединяет то, что в Node разнесено по двум разным API: манипуляции с путём (`path.join`, `path.resolve`) и файловый ввод-вывод (`fs.readFileSync`, `fs.writeFileSync`, `fs.existsSync`) — в Python это методы одного и того же объекта (`.read_text()`, `.write_text()`, `.exists()`, `.parent.mkdir(...)`).

Именование в модуле `json` — не случайное: `dumps`/`loads` (с "s" — "string") работают со **строками**; `dump`/`load` (без "s") работают сразу с **файловым объектом**, избавляя от ручной связки "прочитать строку → распарсить" в одну операцию:

```python
with path.open("w") as f:
    json.dump(data, f, indent=2)     # пишет прямо в файл, без промежуточной строки

with path.open() as f:
    data = json.load(f)               # читает и парсит прямо из файла
```

`JSON.stringify`/`JSON.parse` в JS — прямой аналог `dumps`/`loads` (строка ↔ объект); аналога `dump`/`load` (файл ↔ объект без ручного шага) в Node нет — там всегда придётся вручную комбинировать `fs.readFileSync` и `JSON.parse`.

**Ограничения JSON-файла как хранилища.** Каждое изменение требует перечитать **весь** файл, изменить данные в памяти и переписать **весь** файл заново — частичного обновления одной записи не существует. Фильтрация/поиск — это "загрузить всё в Python и отфильтровать там", без возможности делегировать запрос хранилищу. И главное: у обычной записи в файл нет защиты от параллельной записи из нескольких процессов — ровно та проблема, для которой в главе 06 был написан `FileLock`. Персистентность на JSON потребовала бы того же самого приёма (или ещё более грубого — например, полной сериализации через один и тот же лок на каждую операцию, не только на логирование).

**SQLite: встроенная в stdlib база данных.** `sqlite3` — часть стандартной библиотеки, ничего дополнительно ставить не нужно. Это файловая (не клиент-серверная) СУБД — один файл на диске (`taskman.db`), без отдельного процесса-сервера, который нужно поднимать и настраивать. Для CLI-инструментов, тестов, встраиваемых приложений — ровно то, что нужно, без инфраструктурных издержек Postgres/MySQL.

```python
import sqlite3

conn = sqlite3.connect("taskman.db")
conn.row_factory = sqlite3.Row   # доступ к колонкам по имени: row["text"], а не row[1]

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

cursor = conn.execute("INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)", ("Buy milk", 0, 0))
conn.commit()
new_id = cursor.lastrowid

rows = conn.execute("SELECT * FROM tasks WHERE done = ?", (0,)).fetchall()
conn.close()
```

Нюанс, специфичный именно для SQLite (не для SQL вообще): у SQLite не строгая типизация колонок, а "type affinity" — база во многих случаях позволит вставить строку в колонку `INTEGER`, не бросив ошибку. Postgres/MySQL в этом смысле гораздо строже — это стоит держать в голове именно потому, что дальнейший рост проекта (глава 18, "куда расти дальше") обычно включает переход с SQLite на Postgres, и там подобные вольности заметно строже караются на этапе `INSERT`.

**Параметризованные запросы и SQL injection.** Это — не языковая особенность Python, а универсальное правило для любой СУБД на любом языке (то же самое верно для `pg`/`mysql2`/Prisma в Node): никогда не собирайте SQL-текст из непроверенных данных через f-строки/конкатенацию:

```python
# ОПАСНО — никогда так не делайте:
user_input = "' OR '1'='1"
cursor.execute(f"SELECT * FROM tasks WHERE text = '{user_input}'")
# итоговый SQL: SELECT * FROM tasks WHERE text = '' OR '1'='1'
# → вернёт ВСЕ строки таблицы, а не то, что искали

# БЕЗОПАСНО — параметризованный запрос:
cursor.execute("SELECT * FROM tasks WHERE text = ?", (user_input,))
# значение передаётся драйверу ОТДЕЛЬНО от текста запроса;
# оно никогда не интерпретируется как часть SQL-синтаксиса
```

`?` — позиционный плейсхолдер в `sqlite3` (есть и именованный вариант, `:name`, со словарём параметров). Это ровно тот интерфейс, который проверяют на собеседовании: "как защититься от SQL injection" — правильный ответ "параметризованные запросы / prepared statements", а не "экранировать кавычки руками".

**Транзакции и неочевидный нюанс `Connection` как context manager.** `sqlite3.Connection`, использованный как `with conn:`, коммитит транзакцию при успешном выходе из блока и откатывает при исключении — но **не закрывает соединение**. Это частая ловушка даже у опытных разработчиков: `with conn:` управляет только транзакцией, а не жизненным циклом самого соединения. Чтобы получить и то, и другое — транзакционность **и** гарантированное закрытие — удобно написать свой генераторный context manager (глава 06 + глава 07 в одном месте):

```python
from contextlib import contextmanager

@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()          # только если блок завершился без исключения
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()            # закрывается ВСЕГДА
```

Это буквально генераторная функция, декорированная `@contextmanager` (глава 07): код до `yield` — открытие соединения (аналог `__enter__`), код после `yield` — коммит/откат/закрытие (аналог `__exit__`), а `try/except/finally` вокруг `yield` — то же самое, что разбирали в главе 06, просто в форме генератора, а не класса.

### Параллели с JS/TS/Node:

- `pathlib.Path` объединяет манипуляции с путём и файловый ввод-вывод в одном объекте; в Node это разнесено между `path` и `fs`.
- `json.dumps`/`json.loads` ~ `JSON.stringify`/`JSON.parse`; у `json.dump`/`json.load` (работа напрямую с файловым объектом) прямого аналога в Node нет — там всегда ручная связка `fs.readFileSync` + `JSON.parse`.
- `sqlite3` — часть stdlib Python, устанавливать ничего не нужно; в Node нет встроенного SQL-драйвера вообще — `better-sqlite3`/`pg`/`mysql2`/Prisma и т.п. всегда внешний пакет. Параметризация запросов (`$1`, `?`) — тот же принцип, что и в Python, это не Python-специфика, а универсальное правило SQL.
- Loose "type affinity" SQLite (в отличие от строгой типизации Postgres/MySQL) — специфика конкретно SQLite, а не SQL вообще; про это стоит помнить при будущем переезде на "настоящую" СУБД.

## Что добавляем в проект

Storage-слой переезжает с in-memory списка (`storage/memory.py`, главы 02–07) на файловую SQLite-базу (`storage/sqlite_storage.py`). Задачи теперь **переживают перезапуск процесса** — то, чего не хватало с самой первой главы. Логика фильтрации/сортировки/пагинации (главы 02 и 07) не меняется вообще: она как принимала, так и принимает обычный `list[Task]`, просто теперь этот список каждый раз загружается из базы, а не хранится как модуль-level переменная.

## Практическое задание

Часть A — потренироваться на простом (не остаётся в финальном проекте):

1. Напишите `storage/json_file.py` с тем же публичным интерфейсом, что у `storage/memory.py` (`add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks`), но данные храните в `tasks.json` через `pathlib.Path` + `json.dumps`/`json.loads`. Каждая операция должна: прочитать весь файл (или начать с пустого списка, если файла нет), изменить данные в памяти, переписать файл целиком.
2. Убедитесь, что задачи переживают перезапуск процесса: `add`, затем в новом вызове `python -m taskman list` — задача должна быть на месте.
3. Оставьте этот файл как есть или удалите — он не понадобится дальше, это просто упражнение на понимание ограничений подхода.

Часть B — то, что реально остаётся в проекте:

1. Создайте `storage/sqlite_storage.py`. Определите `DB_PATH = Path("taskman.db")` и генераторный context manager `db_connection()` (через `@contextmanager`), который открывает соединение, коммитит при успехе, откатывает при исключении и **всегда** закрывает соединение.
2. Напишите `init_db()`, создающую таблицу `tasks` (`id`, `text`, `priority`, `done`), если её ещё нет.
3. Перепишите `add_task`, `find_task`, `get_task`, `mark_done`, `list_tasks` на параметризованные SQL-запросы через `db_connection()`. `list_tasks()` заменяет старый module-level `tasks` — она должна каждый раз обращаться к базе, а не кэшировать список в памяти.
4. `filter_by_status`/`sort_tasks` (главы 02/07) и `paginate`/`get_page` (глава 07) переносятся без изменений — они уже принимают обычный `list[Task]`, им всё равно, откуда он взялся.
5. Обновите `storage/__init__.py`, `cli/commands.py` (замените `memory` на `db`, `memory.tasks` — на вызов `db.list_tasks()`) и `cli/app.py` (вызовите `db.init_db()` в начале `main()`, до разбора аргументов).
6. Убедитесь, что задачи переживают перезапуск процесса — так же, как в части A, но теперь через SQLite.

Вопросы на подумать:

- Почему `mark_done` в SQLite-версии делает два обращения к базе (сначала `get_task`, потом `UPDATE`), а не один `UPDATE ... RETURNING`? Это неоптимально — или оправданный компромисс на этом этапе?
- `with conn:` для `sqlite3.Connection` коммитит/откатывает транзакцию, но не закрывает соединение. Что бы произошло, если бы `db_connection()` использовал только `with conn:` без явного `conn.close()` в `finally` — стал бы код неправильным сразу, или проблема появилась бы только при определённых условиях эксплуатации?

## Разбор решения

Меняются `storage/sqlite_storage.py` (новый, заменяет `memory.py`), `storage/__init__.py`, `cli/commands.py`, `cli/app.py`. Остальное — без изменений с главы 07.

`src/taskman/storage/sqlite_storage.py` (новый файл):

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..models import Priority, Task, TaskNotFoundError

DB_PATH = Path("taskman.db")


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


def paginate(items: list[Task], page_size: int):
    page: list[Task] = []
    for task in items:
        page.append(task)
        if len(page) == page_size:
            yield page
            page = []
    if page:
        yield page


def get_page(items: list[Task], page: int, page_size: int) -> list[Task]:
    import itertools

    pages = itertools.islice(paginate(items, page_size), page - 1, page)
    return next(pages, [])
```

`src/taskman/storage/__init__.py` (обновлён):

```python
from . import sqlite_storage as db

__all__ = ["db"]
```

`src/taskman/cli/commands.py` (обновлён — `memory` → `db`, `memory.tasks` → `db.list_tasks()`):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db

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

`src/taskman/cli/app.py` (обновлён — вызывает `db.init_db()`):

```python
from ..storage import db
from .commands import COMMAND_HANDLERS
from .parser import build_parser


def main() -> None:
    db.init_db()
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    handler(args)
```

Ключевые решения:

- `int(priority)`/`Priority(row["priority"])` — round-trip через обычную SQLite-колонку `INTEGER` работает без единой строчки сериализационной логики именно потому, что в главе 04 `Priority` был выбран как `IntEnum`, а не просто `Enum`: `int(Priority.HIGH) == 2`, и `Priority(2)` возвращает обратно `Priority.HIGH`.
- Отображение SQLite-строки в `Task` (`_row_to_task`) живёт в storage-слое, а не в самом классе `Task` — модель ничего не знает про `sqlite3.Row`, это забота конкретного хранилища; при следующей смене хранилища (глава 18: "куда расти дальше" — Postgres) `Task` снова не тронется.
- `db.list_tasks()` заменяет старый `memory.tasks` (обращение к атрибуту) вызовом функции — по имени сразу видно, что это не бесплатное чтение переменной, а обращение к внешнему хранилищу, которое стоит настоящих затрат (I/O, потенциально сеть при переходе на "настоящую" СУБД).
- `db.init_db()` вызывается явно в начале `main()`, а не как побочный эффект импорта модуля `sqlite_storage` — модуль остаётся "чистым" при импорте (глава 05: импорт не должен иметь неожиданных побочных эффектов), а инициализация схемы происходит там, где это явно видно в коде.
- `mark_done` делает `get_task` и `UPDATE` отдельно, не одним запросом — на этом масштабе это не проблема производительности, а осознанный выбор в пользу переиспользования уже написанного `get_task` (с его `TaskNotFoundError`) вместо дублирования проверки на существование внутри SQL.

## Проверь себя

1. Почему `data = json.loads(path.read_text()) if path.exists() else []` — обязательная проверка, а не паранойя? Что произойдёт без неё при самом первом запуске CLI, когда `tasks.json` ещё не существует?
2. Чем `json.dumps`/`json.loads` отличаются от `json.dump`/`json.load` по сигнатуре и назначению — и как расшифровать букву "s" на конце имени, чтобы не путать их?
3. Распишите по шагам, что происходит с данными в базе, если внутри `with db_connection() as conn:` после успешного `INSERT` происходит необработанное исключение. Коммитится ли вставка? Почему именно так устроено выражение `try/except/finally` вокруг `yield`?
4. Почему параметризованный запрос (`conn.execute("... WHERE text = ?", (value,))`) защищает от SQL injection, а f-строка с тем же значением — нет? Дело в экранировании специальных символов или в чём-то более фундаментальном?
5. Что именно означает "SQLite использует type affinity, а не строгую типизацию колонок" — и почему это не баг, а осознанная особенность SQLite, отличающая его от Postgres/MySQL?

<details>
<summary>Ответы</summary>

1. Без проверки `path.exists()` вызов `path.read_text()` на несуществующем файле бросит `FileNotFoundError` — а при самом первом запуске CLI (до того, как хоть одна задача была сохранена) файла `tasks.json` действительно ещё не существует. Проверка явно кодирует бизнес-правило "нет файла — значит, задач ещё нет, а не ошибка" вместо того, чтобы полагаться на исключение как на неявный сигнал этого состояния.
2. `dumps`/`loads` работают со **строками** в памяти: `dumps` превращает Python-объект в строку JSON, `loads` парсит строку JSON обратно в Python-объект — ни один из них ничего не знает о файлах. `dump`/`load` (без "s") делают то же самое, но пишут/читают сразу **в файловый объект/из файлового объекта** (то, что уже открыто через `open()` или `path.open()|), избавляя от промежуточного шага "сначала прочитать в строку, потом распарсить строку". Мнемоника: "s" в конце — от "string"; функции с "s" работают со строками, без "s" — с файлами.
3. Если исключение происходит после `INSERT`, но до конца блока `with db_connection() as conn:`, то `yield conn` в генераторе `db_connection` не завершается штатно — управление уходит в блок `except Exception:` того же генератора, где вызывается `conn.rollback()`, и исключение перевыбрасывается (`raise`) дальше, наружу вызывающему коду. `conn.commit()`, который стоит сразу после `yield conn`, в этом случае **не выполнится вообще** — он находится на той же "линии выполнения", что и код внутри `with`-блока, и до него просто не доходит очередь, потому что управление уже ушло в `except`. Именно поэтому `INSERT` не коммитится: транзакция целиком откатывается, база остаётся в состоянии "как будто ничего не вставляли".
4. Дело не в экранировании кавычек, а в том, что параметризованный запрос физически разделяет **текст SQL-команды** и **данные** на две разные, независимые вещи, передаваемые драйверу отдельно: сама структура запроса (`SELECT * FROM tasks WHERE text = ?`) фиксируется и компилируется один раз, а значение параметра подставляется туда как данные, а не как текст, который потом ещё раз парсится вместе с остальным SQL. F-строка вместо этого производит один сплошной кусок текста, где значение пользователя становится частью того, что интерпретатор SQL будет разбирать как код — экранирование кавычек снижает риск, но не устраняет саму архитектурную проблему "данные и код перемешаны в одном тексте", и почти всегда найдётся способ обойти конкретную схему экранирования.
5. Type affinity означает, что объявленный тип колонки (`INTEGER`, `TEXT` и т.д.) в SQLite — это **предпочтение**, а не жёсткое ограничение: движок попытается привести вставляемое значение к объявленному типу колонки, но если это не получается сделать однозначно, часто просто сохранит значение как есть, вместо того чтобы отклонить вставку с ошибкой. Это осознанный дизайн SQLite, отражающий его происхождение как встраиваемой, "гибкой" базы для небольших приложений и файлов конфигурации, а не результат недоработки; Postgres/MySQL спроектированы для строгой целостности данных на уровне схемы и в норме отклонят `INSERT` с несовместимым типом на уровне базы, а не тихо примут его.

</details>

## Частая ошибка

Самая частая ошибка на этом материале — понадеяться, что `with conn:` для `sqlite3.Connection` закрывает соединение так же, как это происходит с файлами (`with open(...) as f:`) или с `FileLock` из главы 06. Разработчик, уже усвоивший идею "context manager гарантирует освобождение ресурса", логично ожидает того же самого от `with conn:` — но у `sqlite3.Connection` протокол `__exit__` реализован **только** для управления транзакцией (коммит/откат), а не для закрытия самого соединения. В небольшом скрипте, который сразу завершает процесс, это не проявится как видимая проблема — ОС всё равно закроет файловые дескрипторы при выходе. Но в чём-то более долгоживущем (веб-сервер, воркер, тестовый набор, который создаёт соединения в цикле) соединения будут незаметно накапливаться, пока процесс не упрётся в лимит открытых файловых дескрипторов — ошибка, которая проявляется далеко по времени и по коду от места, где было допущено предположение "`with conn:` закрывает всё".

Вторая типичная ошибка, особенно после глав про строки и f-strings (глава 01) — machinально собрать SQL-запрос через f-строку, потому что "это же просто текст, а f-строки — самый естественный способ подставить значение в текст" в Python. Разница между `f"WHERE text = '{value}'"` и `"WHERE text = ?", (value,)` не видна по поведению на "нормальных" данных — оба варианта работают одинаково для обычного текста без кавычек внутри. Уязвимость становится заметна только тогда, когда кто-то (не обязательно злоумышленник — иногда просто пользователь, у которого в тексте задачи оказался апостроф, как в "don't forget the milk") передаёт значение, содержащее символы, которые ломают предполагаемую структуру запроса — то есть баг molчит ровно до того момента, пока не станет security-инцидентом или просто загадочной ошибкой на проде.
