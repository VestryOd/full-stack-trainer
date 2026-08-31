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

Это работает не потому, что `assert` в Python сам по себе такой умный. Обычный `assert a == b` без pytest, упав, покажет только `AssertionError` без единой детали.

pytest подключается на этапе импорта тестового файла и **переписывает AST** (абстрактное синтаксическое дерево) тестовых модулей. Он вставляет код, который сохраняет промежуточные значения подвыражений для отчёта об ошибке. Отсюда и подробный вывод при падении голого `assert`.

Это же причина, по которой `unittest` — встроенный в stdlib, но менее популярный, чем pytest, — требует `self.assertEqual(...)`, а Jest требует `expect().toBe()`. Оба вынуждены оборачивать сравнение в специальный вызов именно потому, что не переписывают AST на лету, как это делает pytest.

**Обнаружение тестов.** pytest сам находит файлы `test_*.py`/`*_test.py`, функции `test_*` и классы `Test*`. Для типового случая конфигурация не нужна вовсе, ровно как Jest сам находит `*.test.js`/`*.spec.js`.

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

`yield` внутри fixture-функции делит её на "до" (setup) и "после" (teardown). Это буквально тот же генераторный паттерн, что `@contextmanager` из глав 06 и 08:

- Код до `yield` выполняется перед тестом.
- Значение после `yield` передаётся тесту как параметр.
- Код после `yield` выполняется после теста — **независимо от того, прошёл он или упал**.

Это третье применение одной и той же генераторной идиомы за курс, после контекстных менеджеров (глава 06) и постраничной выдачи (глава 07).

Принципиальное отличие от Jest вот в чём. В Jest `beforeEach`/`afterEach` — глобальные хуки, неявно применяющиеся ко всем тестам в объемлющем `describe`-блоке. В pytest fixture запрашивается **явно**, только тем тестом, который указал её как параметр. Ничего не выполняется "по умолчанию" для всех тестов сразу.

Fixtures могут запрашивать другие fixtures, образуя граф зависимостей — как в контейнере внедрения зависимостей (DI). И у них есть управляемая область видимости. По умолчанию это `function`: новый экземпляр на каждый тест. При `module` или `session` один экземпляр переиспользуется на весь файл или на весь прогон.

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

**mock и monkeypatch — два разных инструмента с разным назначением.** `unittest.mock` (тоже stdlib) даёт `Mock`, `MagicMock` и `patch`. Они подменяют зависимость фейковым объектом, который запоминает, как его вызвали, и позволяет это проверить: `mock.assert_called_once_with(...)`. По духу это близко к `jest.fn()`/`jest.mock()`.

Fixture `monkeypatch` — отдельная вещь, встроенная в pytest и не относящаяся к `unittest.mock`. Она нужна для безопасной **временной подмены состояния**: атрибута модуля, переменной окружения, элемента словаря, `sys.path`. Откат происходит автоматически после теста, независимо от того, прошёл тест или упал:

```python
def test_uses_monkeypatch(monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setattr(some_module, "CONFIG_VALUE", "test")
    # оба изменения автоматически откатятся после этого теста
```

Разница в акценте. `Mock`/`patch` отвечает на вопрос "что вызывалось и с чем". `monkeypatch` отвечает за другое: аккуратно подменить и гарантированно вернуть как было.

**Сравнение с Jest.** Структурно похоже: обе экосистемы поддерживают setup и teardown, мокирование, параметризованные тесты, читаемые сообщения об ошибках. Синтаксис разный. pytest — это свободные функции, голый `assert` и fixtures как параметры функции. Jest — это блоки `describe`/`it`/`test`, цепочки `expect().toBe()` и неявные глобальные хуки.

У pytest нет настолько же центрального аналога `describe` для группировки. Классы `TestSomething` существуют, но идиоматичный способ структурировать тесты — обычные функции плюс fixtures плюс `parametrize`, а не вложенные блоки.

### Параллели с JS/TS/Node:

- pytest получает подробные сообщения об ошибках из голого `assert` через переписывание AST на этапе импорта. Jest и `unittest` вместо этого требуют специальных методов сравнения: `expect().toBe()`, `self.assertEqual()`.
- Fixtures в pytest — явные, запрашиваются по имени параметра и могут зависеть друг от друга. А `beforeEach`/`afterEach` в Jest — неявные, применяются ко всем тестам в области видимости автоматически.
- `@pytest.mark.parametrize` ~ `test.each(...)` — прямой аналог.
- `monkeypatch` — про безопасную, гарантированно откатываемую подмену состояния; `unittest.mock`/`jest.fn()` — про фейковый объект с интроспекцией вызовов. Разные задачи, часто используются вместе.

## Что добавляем в проект

Добавляем `pytest` как dev-зависимость и пишем тесты на два слоя. Первый — слой хранения (`storage/sqlite_storage.py`). Второй — обработчики интерфейса командной строки (CLI) в `cli/commands.py`.

Ключевая техническая деталь — база. Тесты должны работать с **SQLite в памяти**, а не с реальным файлом `taskman.db`. Но наивно поставить `DB_PATH = ":memory:"` не выйдет. Наш `db_connection()` открывает новое соединение на каждый вызов, а каждое новое `sqlite3.connect(":memory:")` — это отдельная, никак не связанная с предыдущей, пустая база.

Решение — `monkeypatch`. Мы подменяем саму функцию `db_connection` на fixture-версию, которая всегда возвращает одно и то же, уже открытое соединение.

Заодно, пытаясь протестировать сообщение об ошибке в `handle_done`, мы находим настоящий баг в коде из главы 07. Функция `print_err` собрана через `functools.partial(print, file=sys.stderr)`, поэтому она связывает объект `sys.stderr` **один раз**, в момент создания. А `capsys`, fixture pytest для перехвата вывода, подменяет `sys.stderr` на новый объект только на время теста.

Поэтому `print_err` продолжает писать в старый, уже не перехватываемый `sys.stderr`. Чиним это: заменяем `partial` на маленькую функцию, читающую `sys.stderr` заново при каждом вызове.

## Практическое задание

1. Добавьте в `pyproject.toml` секцию `[project.optional-dependencies] dev = ["pytest>=8"]`, установите через `pip install -e ".[dev]"`.
2. Создайте `tests/conftest.py` с fixture `db`. Она должна сделать четыре вещи:
    - Открыть одно соединение `sqlite3.connect(":memory:")`.
    - Через `monkeypatch.setattr` подменить `sqlite_storage.db_connection` на функцию-контекстный-менеджер, которая всегда отдаёт **это же** соединение: коммит при успехе, откат при исключении.
    - Вызвать `sqlite_storage.init_db()` и отдать модуль через `yield`.
    - Закрыть соединение в teardown.
3. Прежде чем читать разбор решения, подумайте: почему просто задать `DB_PATH = ":memory:"` не сработает, если `db_connection()` открывает новое соединение на каждый вызов?
4. Напишите `tests/test_storage.py` на `add_task` (id инкрементируется, приоритет по умолчанию), `find_task`/`get_task` (найдена, не найдена, исключение) и `mark_done` (сохраняется, бросает исключение на несуществующей задаче). Покройте также `list_tasks` и `filter_by_status` через `@pytest.mark.parametrize`. Добавьте тест на `sort_tasks`, который **не использует** fixture `db` вообще — соберите `Task` вручную и убедитесь, что тест всё равно проходит.
5. Напишите `tests/test_cli.py`: вызывайте обработчики (`handle_add`, `handle_list`, `handle_done`) напрямую с вручную собранным `argparse.Namespace`, проверяя вывод через `capsys.readouterr()`. Подмените `append_log` на no-op через `monkeypatch`, чтобы тесты не писали в реальный `taskman.log` на диске.

Отдельный вопрос на подумать. Тест на сообщение об ошибке в `handle_done` может неожиданно упасть на `assert "not found" in err`. При этом в собственном отчёте pytest о падении (`Captured stderr call`) текст ошибки прекрасно виден.

Не спешите просто заменять `capsys` на capfd. Эта соседняя fixture перехватывает вывод на уровне файловых дескрипторов, слоем ниже питоновского `sys.stderr`. Разберитесь, что здесь происходит на самом деле, глядя на то, как `print_err` был определён в главе 07.

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

- Fixture `db` подменяет не путь к базе, а саму функцию `db_connection`. Это единственный способ дать базе `":memory:"` пережить несколько вызовов функций хранения внутри одного теста, раз каждая из них открывает своё соединение.
- `test_sort_tasks_by_priority_orders_high_first` не запрашивает fixture `db`. Чистым функциям, которые не обращаются к базе, тестовая инфраструктура вообще не нужна — только вход и ожидаемый выход.
- `monkeypatch.setattr(commands, "append_log", lambda message: None)` стоит в тестах CLI. Тесты не должны иметь побочных эффектов вроде записи в файл на диске. Поэтому `append_log` подменяется на no-op: логирование в этих тестах не проверяется.
- `print_err` — маленькая функция вместо `functools.partial(print, file=sys.stderr)`. Она читает `sys.stderr` заново при каждом вызове, а не один раз при создании. Это чинит тестируемость через `capsys`. Есть и менее заметный выигрыш: корректность в любом сценарии, где `sys.stderr` законно переопределяется во время работы программы, а не только в тестах.

## Проверь себя

1. Почему два вызова `sqlite3.connect(":memory:")` подряд в одном процессе дают две совершенно независимые базы данных? И как именно это ломает наивную попытку просто выставить `DB_PATH = ":memory:"`, если `db_connection()` открывает новое соединение на каждый вызов?
2. Что именно подменяет fixture `db` в `conftest.py`? Подмена самой функции `db_connection` — единственный способ дать нескольким вызовам функций хранения внутри одного теста видеть одни и те же данные. Почему подменить только `DB_PATH` недостаточно?
3. Почему `capsys.readouterr()` вернул пустую строку для `err`? Тот же самый текст ошибки прекрасно виден в собственном отчёте pytest о падении теста (`Captured stderr call`). Что это говорит про `print_err = functools.partial(print, file=sys.stderr)` в сравнении с функцией, которая читает `sys.stderr` заново при каждом вызове?
4. В чём разница в назначении между `unittest.mock` (`Mock`/`patch`) и pytest-fixture `monkeypatch`? Когда естественнее потянуться за одним, а когда за другим?
5. Почему `test_sort_tasks_by_priority_orders_high_first` не нуждается в fixture `db` вообще, хотя остальные тесты в `test_storage.py` без неё не обходятся? Какое свойство именно `sort_tasks` это позволяет?

<details>
<summary>Ответы</summary>

1. `sqlite3.connect(":memory:")` создаёт новую, приватную базу данных. Она существует ровно столько, сколько живёт конкретный объект-соединение, и ни с чем, кроме себя самой, не связана. Это не именованный, разделяемый ресурс вроде пути к файлу. Два отдельных вызова `connect(":memory:")` в одном процессе дают две полностью независимые базы, ни одна из которых не видит данные другой. Наш `db_connection()` открывает **новое** соединение при каждом вызове любой функции хранения — `add_task`, `find_task` и так далее. Для пути к файлу это нормально: любое соединение к тому же файлу видит те же данные на диске. Для `":memory:"` это фатально. Соединение, открытое внутри `init_db()`, создаст таблицу `tasks` в своей, одноразовой базе в памяти. Следующий вызов, скажем `add_task`, откроет **другую**, совершенно новую и пустую базу без единой таблицы, и тут же упадёт: `sqlite3.OperationalError: no such table: tasks`.
2. Fixture `db` не просто переключает, куда указывает путь к базе. Она целиком заменяет саму функцию-контекстный-менеджер `db_connection` на фейковую версию. Эта фейковая версия **всегда** отдаёт одно и то же, уже открытое соединение, захваченное один раз до начала теста, сколько бы раз её ни вызвали. Так полностью обходится проблема "каждое соединение — отдельная база" для `:memory:`. Все операции хранения внутри теста проходят через одну и ту же фейковую `db_connection` и получают обратно один и тот же объект-соединение. Поэтому содержимое базы в памяти остаётся согласованным между вызовами `add_task` и `list_tasks` внутри одного теста — ровно так же, как у нескольких реальных соединений к одному файлу.
3. `functools.partial(print, file=sys.stderr)` вычисляет `sys.stderr` **один раз** — в момент создания самого объекта `partial`, то есть при импорте модуля. Дальше он навсегда сохраняет именно этот объект как именованный аргумент `file` для всех будущих вызовов. Fixture `capsys` в pytest работает иначе: на время теста она **подменяет** атрибут `sys.stderr`, перепривязывая это имя к новому объекту-перехватчику. Но объект `partial` был создан раньше. Он продолжает держать ссылку на **старый** объект `sys.stderr`, полученный при импорте, и пишет именно в него. Перепривязка имени позже на него не влияет. Маленькая функция-обёртка ведёт себя по-другому: она каждый раз при вызове ищет `sys.stderr` заново, по имени, и потому видит то, к чему `capsys` его сейчас подменил.
4. `unittest.mock` (`Mock`/`patch`) — про замену зависимости фейковым объектом. Такой объект запоминает, как его вызвали, и позволяет это проверить: `mock.assert_called_once_with(...)`. Акцент здесь — на самом mock-объекте и интроспекции вызовов. Fixture `monkeypatch` — про безопасную, временную подмену **состояния**: атрибута, переменной окружения, элемента словаря. Откат после теста гарантирован, независимо от исхода. Акцент не на записи вызовов, а на том, чтобы аккуратно подменить и гарантированно вернуть как было. Поэтому `monkeypatch` уместнее, когда нужно временно переключить конфигурацию или реализацию — как в этой главе, где подменяются `db_connection` и `append_log`. `Mock`/`patch` уместнее, когда важно проверить, как и сколько раз что-то было вызвано.
5. `sort_tasks` — чистая функция. При одних и тех же входных данных, то есть списке `Task` и строке `sort_by`, она всегда возвращает один и тот же результат. Она не читает и не изменяет никакого внешнего состояния: ни базы, ни файла, ни глобальной переменной, и не производит побочных эффектов. Создание `Task`-объектов напрямую через конструктор dataclass и вызов `sort_tasks` на них тестируют функцию полностью на её собственных условиях. Здесь нечего готовить и не за чем убирать, потому что нет никакого разделяемого, изменяемого ресурса. Fixture `db` нужна только тем тестам, которые читают базу или пишут в неё.

</details>

## Частая ошибка

Самая поучительная ошибка этой главы не гипотетическая: она реально произошла в процессе написания тестов. Предполагалось, что `capsys` — или любая другая fixture перехвата вывода — обязательно увидит **всё**, что печатается где угодно в коде во время теста. Как именно этот код собрал вызов `print`, считалось неважным.

`print_err`, собранный в главе 07 через `functools.partial(print, file=sys.stderr)`, тихо нарушает это предположение. Он связывает конкретный объект `sys.stderr` один раз, в момент создания, а не читает его заново при каждом вызове. Поэтому подмена `sys.stderr` фикстурой `capsys` для него попросту невидима.

Тест падает, хотя в отчёте pytest вывод виден собственными глазами. Правильная реакция — не махнуть рукой и переключиться на перехват уровня файловых дескрипторов через `capfd`. Правильная реакция — разобраться, почему конкретно этот код не уважает подмену `sys.stderr`. Обычно, как и здесь, причина в том, что слишком рано был захвачен объект, а не имя.

Вторая типичная ошибка — понадеяться, что смена `DB_PATH` на `":memory:"` в тестовом окружении просто сработает. SQLite в памяти ведь самый простой вариант хранения, какой бывает. Без оговорок это работает только тогда, когда одно и то же соединение переиспользуется на протяжении всего теста.

Наш слой хранения, из главы 08, открывает новое соединение на каждый вызов. С таким слоем нужен дополнительный шаг, чтобы заставить несколько вызовов "видеть" одну и ту же базу в памяти. Наивной замены одной строки конфигурации не хватит.
