# Тестирование с pytest

## Теория

**Обычный `assert` — без библиотеки утверждений.** В pytest не нужен `expect(x).toBe(y)` или `self.assertEqual(a, b)` — пишете обычный Python `assert`:

```python
def test_add():
    assert 2 + 2 == 4

def test_lists_match():
    assert [1, 2, 3] == [1, 2, 4]
    # при падении pytest покажет, в каком именно элементе разошлись списки —
    # не просто "AssertionError", а детальный дифф
```

Это работает не потому, что `assert` в Python сам по себе такой умный — обычный `assert a == b` без pytest, упав, покажет только `AssertionError` без единой детали. pytest подключается на этапе импорта тестового файла и **переписывает AST** (абстрактное синтаксическое дерево) test-модулей, вставляя код, который сохраняет промежуточные значения подвыражений для отчёта об ошибке — отсюда и подробный вывод при падении голого `assert`. Это причина, по которой `unittest` (встроенный в stdlib, но менее популярный, чем pytest) требует `self.assertEqual(...)`, а Jest — `expect().toBe()`: оба вынуждены оборачивать сравнение в специальный вызов именно потому, что не переписывают AST на лету, как это делает pytest.

**Обнаружение тестов.** pytest сам находит файлы `test_*.py`/`*_test.py`, функции `test_*`, классы `Test*` — конфигурация не нужна для типового случая, ровно как Jest сам находит `*.test.js`/`*.spec.js`.

**Fixtures.** `@pytest.fixture` — функция, результат которой тестовая функция запрашивает **по имени параметра**:

```python
import pytest

@pytest.fixture
def sample_list():
    print("setup")
    yield [1, 2, 3]
    print("teardown")

def test_uses_fixture(sample_list):
    assert len(sample_list) == 3
```

`yield` внутри fixture-функции делит её на "до" (setup) и "после" (teardown) — это буквально тот же генераторный паттерн, что `@contextmanager` из главы 06/08: код до `yield` выполняется перед тестом, значение после `yield` передаётся тесту как параметр, код после `yield` выполняется после теста **независимо от того, прошёл он или упал**. Третье применение одной и той же генераторной идиомы за курс — после context manager'а (глава 06) и постраничной выдачи (глава 07).

Принципиальное отличие от Jest: в Jest `beforeEach`/`afterEach` — глобальные хуки, неявно применяющиеся ко всем тестам в объемлющем `describe`-блоке. В pytest fixture запрашивается **явно**, только тем тестом, который указал её как параметр — ничего не выполняется "по умолчанию" для всех тестов сразу. Fixtures могут запрашивать другие fixtures (граф зависимостей, как в DI-контейнере), и у них есть управляемый scope (`function` по умолчанию — новый экземпляр на каждый тест; `module`/`session` — переиспользуется на весь файл/весь прогон).

**`@pytest.mark.parametrize`.** Один тест, много наборов входных данных — каждый становится отдельным, отдельно отображаемым тестовым случаем:

```python
@pytest.mark.parametrize("a, b, expected", [
    (1, 2, 3),
    (2, 2, 4),
    (-1, 1, 0),
])
def test_add_pairs(a, b, expected):
    assert a + b == expected
```

Прямой аналог — `test.each([[1, 2, 3], [2, 2, 4]])(...)` в Jest.

**mock и monkeypatch — два разных инструмента с разным назначением.** `unittest.mock` (тоже stdlib) даёт `Mock`/`MagicMock`/`patch` — подмену зависимости фейковым объектом, который запоминает, как его вызвали, и позволяет проверить это (`mock.assert_called_once_with(...)`) — по духу близко к `jest.fn()`/`jest.mock()`. `monkeypatch` — отдельный, встроенный в pytest fixture (не из `unittest.mock`) для безопасной **временной подмены состояния**: атрибута модуля, переменной окружения, элемента словаря, `sys.path` — с гарантированным автоматическим откатом после теста, независимо от того, прошёл тест или упал:

```python
def test_uses_monkeypatch(monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setattr(some_module, "CONFIG_VALUE", "test")
    # оба изменения автоматически откатятся после этого теста
```

Разница в акценте: `Mock`/`patch` — про "что вызывалось и с чем"; `monkeypatch` — про "аккуратно подменить и гарантированно вернуть как было".

**Сравнение с Jest.** Структурно похоже: обе экосистемы поддерживают setup/teardown, мокирование, параметризованные тесты, читаемые сообщения об ошибках. Синтаксически — разное: pytest — это свободные функции, голый `assert`, fixtures как параметры функции; Jest — блоки `describe`/`it`/`test`, цепочки `expect().toBe()`, неявные глобальные хуки. У pytest нет настолько же центрального аналога `describe` для группировки — классы `TestSomething` существуют, но идиоматичный способ структурировать тесты — обычные функции + fixtures + `parametrize`, а не вложенные блоки.

### Параллели с JS/TS/Node:

- pytest получает подробные сообщения об ошибках из голого `assert` через переписывание AST на этапе импорта; Jest и `unittest` вместо этого требуют специальных методов сравнения (`expect().toBe()`, `self.assertEqual()`).
- Fixtures в pytest — явные, запрашиваются по имени параметра, могут зависеть друг от друга; `beforeEach`/`afterEach` в Jest — неявные, применяются ко всем тестам в scope автоматически.
- `@pytest.mark.parametrize` ~ `test.each(...)` — прямой аналог.
- `monkeypatch` — про безопасную, гарантированно откатываемую подмену состояния; `unittest.mock`/`jest.fn()` — про фейковый объект с интроспекцией вызовов. Разные задачи, часто используются вместе.

## Что добавляем в проект

Добавляем `pytest` как dev-зависимость и пишем тесты на storage-слой (`storage/sqlite_storage.py`) и на CLI-обработчики (`cli/commands.py`). Ключевая техническая деталь: тесты должны работать с **in-memory SQLite**, а не с реальным файлом `taskman.db` — но наивно поставить `DB_PATH = ":memory:"` не выйдет, потому что `db_connection()` открывает новое соединение на каждый вызов, а каждое новое `sqlite3.connect(":memory:")` — это отдельная, никак не связанная с предыдущей, пустая база. Решение — `monkeypatch`: подменить саму функцию `db_connection` на fixture-версию, которая всегда возвращает одно и то же, уже открытое соединение.

Заодно, пытаясь протестировать сообщение об ошибке в `handle_done`, мы находим настоящий баг в коде из главы 07: `print_err`, собранный через `functools.partial(print, file=sys.stderr)`, связывает объект `sys.stderr` **один раз**, в момент создания — а `capsys` (fixture pytest для перехвата вывода) подменяет `sys.stderr` на новый объект только для длительности теста. `print_err` продолжает писать в старый, уже не перехватываемый `sys.stderr`. Чиним — заменяем `partial` на маленькую функцию, читающую `sys.stderr` заново при каждом вызове.

## Практическое задание

1. Добавьте в `pyproject.toml` секцию `[project.optional-dependencies] dev = ["pytest>=8"]`, установите через `pip install -e ".[dev]"`.
2. Создайте `tests/conftest.py` с fixture `db`: откройте одно соединение `sqlite3.connect(":memory:")`, через `monkeypatch.setattr` подмените `sqlite_storage.db_connection` на функцию-контекстный-менеджер, которая всегда отдаёт **это же** соединение (коммит при успехе, откат при исключении), вызовите `sqlite_storage.init_db()`, отдайте модуль через `yield`, закройте соединение в teardown.
3. Прежде чем читать разбор решения, подумайте: почему просто задать `DB_PATH = ":memory:"` не сработает, если `db_connection()` открывает новое соединение на каждый вызов?
4. Напишите `tests/test_storage.py`: `add_task` (id инкрементируется, дефолтный приоритет), `find_task`/`get_task` (найдена/не найдена + исключение), `mark_done` (сохраняется, бросает исключение на несуществующей задаче), `list_tasks`, `filter_by_status` через `@pytest.mark.parametrize`. Добавьте тест на `sort_tasks`, который **не использует** fixture `db` вообще — соберите `Task` вручную и убедитесь, что тест всё равно проходит.
5. Напишите `tests/test_cli.py`: вызывайте обработчики (`handle_add`, `handle_list`, `handle_done`) напрямую с вручную собранным `argparse.Namespace`, проверяя вывод через `capsys.readouterr()`. Подмените `append_log` на no-op через `monkeypatch`, чтобы тесты не писали в реальный `taskman.log` на диске.

Вопрос на подумать отдельно: если тест на сообщение об ошибке в `handle_done` неожиданно падает с `assert "not found" in err`, хотя в собственном отчёте pytest о падении (`Captured stderr call`) текст ошибки прекрасно виден — не спешите просто заменять `capsys` на `capfd`. Разберитесь, что здесь на самом деле происходит, глядя на то, как `print_err` был определён в главе 07.

## Разбор решения

`pyproject.toml` (добавлена секция dev-зависимостей, остальное без изменений):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

`tests/conftest.py` (новый файл):

```python
import sqlite3
from contextlib import contextmanager

import pytest

from taskman.storage import sqlite_storage


@pytest.fixture
def db(monkeypatch):
    """Point taskman's storage layer at one shared in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def fake_db_connection():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)
    sqlite_storage.init_db()
    yield sqlite_storage
    conn.close()
```

`tests/test_storage.py` (новый файл):

```python
import pytest

from taskman.models import Priority, Task, TaskNotFoundError
from taskman.storage.sqlite_storage import sort_tasks


def test_add_task_assigns_incrementing_ids(db):
    first = db.add_task("Buy milk")
    second = db.add_task("Write report")
    assert first.id == 1
    assert second.id == 2


def test_add_task_defaults_to_medium_priority(db):
    task = db.add_task("Buy milk")
    assert task.priority == Priority.MEDIUM
    assert task.done is False


def test_find_task_returns_none_when_missing(db):
    assert db.find_task(999) is None


def test_get_task_raises_when_missing(db):
    with pytest.raises(TaskNotFoundError):
        db.get_task(999)


def test_mark_done_persists_across_reads(db):
    task = db.add_task("Buy milk")
    db.mark_done(task.id)
    reloaded = db.get_task(task.id)
    assert reloaded.done is True


def test_mark_done_raises_for_missing_task(db):
    with pytest.raises(TaskNotFoundError):
        db.mark_done(999)


def test_list_tasks_returns_everything_added(db):
    db.add_task("A")
    db.add_task("B")
    assert [t.text for t in db.list_tasks()] == ["A", "B"]


@pytest.mark.parametrize(
    "status, expected_texts",
    [
        ("all", ["A", "B"]),
        ("done", ["A"]),
        ("pending", ["B"]),
    ],
)
def test_filter_by_status(db, status, expected_texts):
    a = db.add_task("A")
    db.add_task("B")
    db.mark_done(a.id)

    result = db.filter_by_status(db.list_tasks(), status)
    assert [t.text for t in result] == expected_texts


def test_sort_tasks_by_priority_orders_high_first():
    # чистая функция — fixture db вообще не нужна
    low = Task(id=1, text="low", priority=Priority.LOW)
    high = Task(id=2, text="high", priority=Priority.HIGH)

    result = sort_tasks([low, high], "priority")
    assert result == [high, low]
```

`tests/test_cli.py` (новый файл):

```python
import argparse

from taskman.cli import commands


def make_args(**kwargs):
    return argparse.Namespace(**kwargs)


def test_handle_add_prints_confirmation(db, capsys, monkeypatch):
    monkeypatch.setattr(commands, "append_log", lambda message: None)
    args = make_args(command="add", text="Buy milk", priority="high")

    commands.handle_add(args)

    out = capsys.readouterr().out
    assert "Added:" in out
    assert "Buy milk" in out


def test_handle_done_reports_missing_task(db, capsys, monkeypatch):
    monkeypatch.setattr(commands, "append_log", lambda message: None)
    args = make_args(command="done", id=999)

    commands.handle_done(args)

    err = capsys.readouterr().err
    assert "not found" in err


def test_handle_list_shows_added_tasks(db, capsys, monkeypatch):
    monkeypatch.setattr(commands, "append_log", lambda message: None)
    db.add_task("Buy milk")

    args = make_args(command="list", status="all", sort="id", page=1, page_size=5)
    commands.handle_list(args)

    out = capsys.readouterr().out
    assert "Buy milk" in out
```

`src/taskman/cli/commands.py` (единственное изменение — `print_err`; всё остальное как в главе 08):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import db


def print_err(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


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

Ключевые решения:

- `db` fixture подменяет не путь к базе, а саму функцию `db_connection` — единственный способ дать `":memory:"`-базе пережить несколько вызовов storage-функций внутри одного теста, раз каждая из них открывает своё соединение.
- `test_sort_tasks_by_priority_orders_high_first` не запрашивает fixture `db` — наглядно показывает, что чистым функциям (без обращения к базе) тестовая инфраструктура вообще не нужна, только вход и ожидаемый выход.
- `monkeypatch.setattr(commands, "append_log", lambda message: None)` в тестах CLI — тесты не должны иметь побочных эффектов вроде записи в файл на диске; `append_log` подменяется на no-op, поскольку в этих тестах логирование не является предметом проверки.
- `print_err` — маленькая функция вместо `functools.partial(print, file=sys.stderr)`: читает `sys.stderr` заново при каждом вызове, а не один раз при создании — это чинит и тестируемость через `capsys`, и (менее заметный побочный эффект) корректность в любом сценарии, где `sys.stderr` легитимно переопределяется во время работы программы, не только в тестах.

## Проверь себя

1. Почему два вызова `sqlite3.connect(":memory:")` подряд в одном процессе дают две совершенно независимые, никак не связанные друг с другом базы данных — и как именно это ломает наивную попытку просто выставить `DB_PATH = ":memory:"` при текущем дизайне `db_connection()` (новое соединение на каждый вызов)?
2. Что именно подменяет fixture `db` в `conftest.py` — и почему подмена именно функции `db_connection` (а не просто `DB_PATH`) — единственный способ дать нескольким вызовам storage-функций внутри одного теста видеть одни и те же данные?
3. Почему `capsys.readouterr()` вернул пустую строку для `err`, хотя тот же самый текст ошибки прекрасно виден в собственном отчёте pytest о падении теста (`Captured stderr call`)? Что это говорит о разнице между `print_err = functools.partial(print, file=sys.stderr)` и функцией, которая читает `sys.stderr` заново при каждом вызове?
4. В чём разница в назначении между `unittest.mock` (`Mock`/`patch`) и pytest-fixture `monkeypatch` — когда естественнее потянуться за одним, а когда за другим?
5. Почему `test_sort_tasks_by_priority_orders_high_first` не нуждается в fixture `db` вообще, хотя остальные тесты в `test_storage.py` без неё не обходятся? Какое свойство именно `sort_tasks` это позволяет?

<details>
<summary>Ответы</summary>

1. `sqlite3.connect(":memory:")` создаёт новую, приватную базу данных, которая существует ровно столько, сколько живёт конкретный объект-соединение, и ни с чем, кроме себя самой, не связана — это не именованный, разделяемый ресурс вроде пути к файлу. Два отдельных вызова `connect(":memory:")` в одном и том же процессе дают две полностью независимые базы, ни одна из которых не видит данные другой. Наш `db_connection()` открывает **новое** соединение через `sqlite3.connect(DB_PATH)` при каждом вызове любой storage-функции (`add_task`, `find_task` и т.д.) — для пути к файлу это нормально (любое соединение к тому же файлу видит те же данные на диске), но для `":memory:"` фатально: соединение, открытое внутри `init_db()`, создаст таблицу `tasks` в одной, одноразовой in-memory базе, а следующий вызов, скажем, `add_task`, откроет **другую**, совершенно новую и пустую in-memory базу без единой таблицы — и тут же упадёт с чем-то вроде `sqlite3.OperationalError: no such table: tasks`.
2. Fixture `db` не просто переключает, куда указывает путь к базе — она целиком заменяет саму функцию-контекстный-менеджер `db_connection` на фейковую версию, которая **всегда** отдаёт одно и то же, уже открытое соединение (захваченное один раз, до начала теста), сколько бы раз её ни вызвали за время теста. Это полностью обходит проблему "каждое соединение — отдельная база" для `:memory:`: раз все storage-операции внутри теста проходят через одну и ту же фейковую `db_connection` и получают обратно один и тот же объект-соединение, содержимое in-memory базы остаётся согласованным между вызовами `add_task` → `list_tasks` внутри одного теста — ровно так же, как это происходило бы у нескольких реальных соединений к одному файлу.
3. `functools.partial(print, file=sys.stderr)` вычисляет `sys.stderr` **один раз**, в момент создания самого объекта `partial` (при импорте модуля), и навсегда сохраняет именно этот объект как именованный аргумент `file` для всех будущих вызовов. Fixture `capsys` в pytest работает, временно **подменяя** атрибут `sys.stderr` (перепривязывая имя `sys.stderr` к новому объекту-перехватчику) на время теста — но уже созданный объект `partial` продолжает держать ссылку на СТАРЫЙ объект `sys.stderr`, полученный при импорте, и пишет именно в него, вне зависимости от того, к чему `sys.stderr` привязан позже. Маленькая функция-обёртка (`def print_err(*args, **kwargs): print(*args, file=sys.stderr, **kwargs)`) вместо этого каждый раз при вызове ищет `sys.stderr` заново, по имени — и потому видит именно то, к чему `capsys` его сейчас подменил.
4. `unittest.mock` (`Mock`/`patch`) — про замену зависимости фейковым объектом, который запоминает, как его вызвали, и позволяет это проверить (`mock.assert_called_once_with(...)`); акцент — на самом mock-объекте и интроспекции вызовов. `monkeypatch` — про безопасную, временную подмену **состояния**: атрибута, переменной окружения, элемента словаря — с гарантированным автоматическим откатом после теста, независимо от исхода; акцент не на записи вызовов, а на "аккуратно подменить и гарантированно вернуть как было". `monkeypatch` уместнее, когда нужно временно переключить конфигурацию/реализацию (как в этой главе — подмена `db_connection`, `append_log`); `Mock`/`patch` — когда важно именно проверить, как и сколько раз что-то было вызвано.
5. `sort_tasks` — чистая функция: при одних и тех же входных данных (список `Task` и строка `sort_by`) она всегда возвращает один и тот же результат, не читая и не изменяя никакого внешнего состояния (ни базы, ни файла, ни глобальной переменной) и не производя побочных эффектов. Создание `Task`-объектов напрямую через конструктор dataclass и вызов `sort_tasks` на них тестирует функцию полностью на её собственных условиях — здесь нечего готовить и не за чем убирать, потому что нет вообще никакого разделяемого, изменяемого ресурса; fixture `db` нужна только тем тестам, которые читают или пишут в базу.

</details>

## Частая ошибка

Самая поучительная ошибка этой главы — не гипотетическая, а та, что реально произошла в процессе написания тестов: считать, что `capsys` (или любой другой output-capturing fixture) обязательно увидит **всё**, что было напечатано где угодно в коде во время теста, независимо от того, как именно этот код сконструировал вызов `print`. `print_err`, собранный в главе 07 через `functools.partial(print, file=sys.stderr)`, тихо нарушает это предположение: он связывает конкретный объект `sys.stderr` один раз, в момент создания, а не читает его заново при каждом вызове — так что подмена `sys.stderr` фикстурой `capsys` для него попросту невидима. Правильная реакция на "тест падает, хотя в отчёте pytest вывод виден собственными глазами" — не махнуть рукой и переключиться на fd-level перехват (`capfd`) в качестве обходного пути, а разобраться, почему конкретно этот код не уважает подмену `sys.stderr` — обычно (как и здесь) причина в том, что объект, а не имя, был захвачен слишком рано.

Вторая типичная ошибка — понадеяться, что смена `DB_PATH` на `":memory:"` в тестовом окружении "просто сработает", потому что "in-memory SQLite — это же самый простой вариант хранения". Она работает без всяких оговорок только тогда, когда одно и то же соединение переиспользуется на протяжении всего теста — если storage-слой (как наш, из главы 08) открывает новое соединение на каждый вызов, потребуется дополнительный шаг именно для того, чтобы заставить несколько вызовов "видеть" одну и ту же in-memory базу, а не наивная замена одной строки конфигурации.
