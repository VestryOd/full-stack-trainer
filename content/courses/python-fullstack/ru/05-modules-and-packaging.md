# Модули, пакеты и упаковка проекта

## Теория

**Модуль vs пакет.** Модуль в Python — это просто один файл `.py`. При импорте (`import foo`) выполняется код файла `foo.py`, а результат кэшируется в `sys.modules`. Повторный импорт файл заново не выполняет.

Пакет — это директория с другими модулями и пакетами, помеченная файлом `__init__.py` ("regular package"). Начиная с Python 3.3 есть ещё namespace packages — пакеты вообще без `__init__.py`. Но для обычного прикладного проекта явный `__init__.py` — стандарт, и в этом курсе он таковым и остаётся.

**Зачем нужен `__init__.py`, если он может быть пустым.** Ролей две. Первая, историческая и договорная: это маркер "здесь пакет, а не просто папка со скриптами". Вторая, практическая: здесь собирают публичный API пакета через ре-экспорт:

```python
# taskman/models/__init__.py
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = ["Priority", "Task", "PRIORITY_CHOICES"]
```

Это позволяет писать снаружи `from taskman.models import Task`, не зная, что `Task` физически лежит в `taskman/models/task.py`. Ровно ту же работу делает `index.js` в JS-пакете: он собирает и реэкспортирует содержимое внутренних файлов.

Разница принципиальная. В JS `index.js` — это только **соглашение**. Оно работает потому, что резолвер модулей по умолчанию ищет именно `index.js` при импорте директории.

В Python выполнение `__init__.py` при первом импорте любого модуля из пакета — **гарантия языка**, а не соглашение. Поэтому `import taskman.models.task` всегда сначала выполнит `taskman/models/__init__.py`, даже если вы импортировали подмодуль напрямую. Сам пакет по имени импортировать не обязательно.

`__all__` — отдельная тема, и он ничего не прячет. Если написать имя явно, приватное имя всё равно импортируется: `from module import _private_name` сработает. Ограничивает `__all__` только то, что попадёт при `from module import *`. Ещё он служит подсказкой инструментам документации и IDE (среда разработки) о том, что считается официальным публичным API модуля.

**Относительные импорты.** `.` — текущий пакет, `..` — на уровень выше, и так далее:

```python
# taskman/storage/memory.py
from ..models import Priority, Task   # на уровень вверх (taskman/), затем в models
```

```python
# taskman/models/__init__.py
from .task import Task                 # в текущем пакете (models/), модуль task.py
```

Здесь накладываются два разных дерева, а точки идут только по одному из них:

```txt
Внутри src/taskman/storage/memory.py

На диске:          src/ -> taskman/ -> storage/ -> memory.py
Иерархия пакетов:  taskman -> storage -> memory

"src" — это директория, но не уровень пакета. В этом и зазор.

Как читается "from ..models import Task" внутри этого модуля:
  .        = taskman.storage   (пакет, в котором лежит memory.py)
  ..       = taskman           (на один уровень пакета выше)
  ..models = taskman.models
```

Ключевой нюанс — в том, что именно считают точки. Относительные импорты считают уровни **пакетной иерархии**, а не буквальные шаги по файловой системе. И работают они, только если модуль импортирован **как часть пакета**: через `import` откуда-то ещё или через `python -m package.module`.

Если запустить файл напрямую как скрипт (`python taskman/cli/app.py`), у интерпретатора нет информации о том, в каком пакете этот файл находится. Тогда `from .commands import ...` упадёт с `ImportError: attempted relative import with no known parent package`.

Абсолютные импорты (`from taskman.models import Task`) этой проблемы не имеют. Они всегда резолвятся от корня `sys.path` или от установленного пакета, независимо от того, как был запущен текущий файл.

**Разница с ES-модулями.** ES (ECMAScript) — это стандарт, который описывает JavaScript. Импорт ES-модуля, в том числе в Node, — это явный **путь** (`./foo.js`, `../bar.js`), буквально отражающий файловую систему. Относительный импорт в Python — это шаг по **пакетной иерархии**. Она обычно совпадает со структурой папок, но концептуально это разные вещи.

Совпадают они в 99% случаев. А идея "количество точек = уровни пакета", а не "уровни директорий", становится заметна именно на пограничных случаях — вроде запуска файла напрямую.

Есть и второе отличие. Экспорт в JS/TS — явный, по одному символу (`export function foo`), и импортировать можно только то, что экспортировано явно. В Python **всё**, что не начинается с `_`, доступно для импорта по умолчанию. Список `__all__` и ведущее подчёркивание — это соглашение для читателя, а не приватность, которую обеспечивает язык.

**venv — глубже.** Помимо `activate`/`deactivate` (глава 00), для пакета с реальной структурой полезны:

```bash
pip install -e .        # editable install — код пакета подхватывается сразу,
                         # без переустановки после каждого изменения;
                         # аналог npm link / workspace-пакета в монорепо
pip list                # что установлено в текущем venv
pip show taskman        # метаданные конкретного установленного пакета
```

Editable install — не копия файлов в site-packages, а специальный "указатель". Он говорит интерпретатору, где искать модули этого пакета: вот здесь, в этой директории на диске. Поэтому изменения в исходниках видны сразу, без повторного `pip install`.

**requirements.txt vs pyproject.toml + poetry/uv.** `requirements.txt` — плоский список строк вида `requests==2.31.0`. Исторически он либо писался руками, либо генерировался через `pip freeze > requirements.txt`. Двух вещей в нём нет:

- Различия между прямой и транзитивной зависимостью.
- Хешей для верификации целостности.

Поэтому это просто снимок того, что сейчас установлено, а не декларация того, что должно быть установлено.

`pyproject.toml` (глава 00) описывает зависимости декларативно. Но **сам по себе**, с одним только `pip` и `setuptools`, он не создаёт настоящий lock-файл с разрешённым деревом транзитивных зависимостей. Это ограничение было отмечено ещё в главе 00.

Инструменты вроде **poetry** и **uv** добавляют поверх `pyproject.toml` полноценный lock-файл — `poetry.lock` или `uv.lock`. В нём зафиксированы точные версии и хеши всего дерева. Это прямой аналог `package-lock.json`, `yarn.lock` и `pnpm-lock.yaml`.

На 2026 год `uv` — де-факто самый быстрый и рекомендуемый путь. Он написан на Rust и заменяет разом `pip`, `venv` и функциональность poetry. Но для этого курса мы сознательно остаёмся на стандартном `pip`/`venv`, чтобы не зависеть от стороннего инструмента, пока не пройдены основы.

### Параллели с JS/TS/Node:

- Модуль ~ файл с семантикой ES-модуля: единица импорта в обоих языках. Пакет ближе всего к npm-пакету со сборочным `index.js`, который реэкспортирует внутренние файлы. Но исполнение `__init__.py` при импорте подмодуля — гарантия языка, а не конвенция резолвера, как `index.js`.
- Явный `export` в JS/TS против "всё публично по умолчанию" в Python. Список `__all__` и подчёркивание перед именем — это соглашение для читателя и для `import *`, а не приватность, которую обеспечивает язык.
- Точки в относительном импорте (`.`/`..`) — это уровни **пакетной иерархии**, а не буквальные `./`/`../`-шаги по файлам, как в Node. И относительные импорты вообще не работают при запуске файла напрямую как скрипта — только при импорте как части пакета.
- `requirements.txt` ~ старый список без lock-семантики, собранный вручную или через `pip freeze`. Пара `pyproject.toml` + `poetry`/`uv` ~ `package.json` + `package-lock.json`/`uv.lock`, с реальным разрешением зависимостей.

## Что добавляем в проект

Разбиваем монолитный `main.py` на пакет `taskman` с тремя подпакетами:

- `models/` — `Priority` и `Task`.
- `storage/` — хранилище в памяти процесса.
- `cli/` — argparse, обработчики команд и `main()`.

Заодно переезжаем на **src-layout** (`src/taskman/...`), обещанный ещё в главе 00. `pyproject.toml` получает секцию сборки (`[build-system]`, `[tool.setuptools.packages.find]`) и секцию `[project.scripts]`. Тогда после `pip install -e .` команда `taskman` работает как настоящий установленный инструмент с интерфейсом командной строки (CLI), а не только через `python main.py`.

## Практическое задание

1. Создайте структуру:
   ```
   taskman/
     pyproject.toml
     src/
       taskman/
         __init__.py
         __main__.py
         models/
           __init__.py
           task.py
         storage/
           __init__.py
           memory.py
         cli/
           __init__.py
           parser.py
           commands.py
           app.py
   ```
2. Перенесите `Priority`/`Task`/`PRIORITY_CHOICES` в `models/task.py`, ре-экспортируйте их из `models/__init__.py` (с `__all__`).
3. Перенесите `tasks`/`add_task`/`find_task`/`mark_done`/`filter_by_status`/`sort_tasks` в `storage/memory.py`, импортируя `Priority`/`Task` **относительным** импортом (`from ..models import Priority, Task`).
4. Разбейте CLI-часть на три модуля:
   - `cli/parser.py` — `build_parser`.
   - `cli/commands.py` — `log_command`, три обработчика, `COMMAND_HANDLERS`.
   - `cli/app.py` — `main()`, собирающий `parser` + `COMMAND_HANDLERS`.
5. `__main__.py` должен импортировать `main` из `taskman.cli` и вызывать его — это то, что делает возможным `python -m taskman`.
6. Обновите `pyproject.toml`: добавьте `[build-system]` (`setuptools`), `[tool.setuptools.packages.find] where = ["src"]` и `[project.scripts] taskman = "taskman.cli:main"`.
7. Установите пакет в editable-режиме: `pip install -e .` в активированном venv. Затем убедитесь, что работают **оба** способа запуска: `python -m taskman add "Buy milk"` и просто `taskman add "Buy milk"`.
8. Удалите старый плоский `main.py` — он больше не нужен, вся логика переехала в пакет.

Вопросы на подумать:

- Что произойдёт, если запустить `python src/taskman/cli/app.py` напрямую (не через `-m`, не после установки)? Почему это не сработает, и как это связано с тем, что относительные импорты требуют "родительского пакета"?
- Почему `cli/commands.py` импортирует `from ..storage import memory` и обращается к `memory.add_task(...)`, а не `from ..storage.memory import add_task` напрямую? Чем второй вариант хуже для модуля, который держит мутируемое состояние (`tasks: list[Task]`)?

## Разбор решения

`pyproject.toml`:

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

`src/taskman/models/task.py`:

```python
from dataclasses import dataclass
from enum import IntEnum


class Priority(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

    def __str__(self) -> str:
        return self.name.lower()


PRIORITY_CHOICES = [p.name.lower() for p in Priority]


@dataclass
class Task:
    id: int
    text: str
    priority: Priority = Priority.MEDIUM
    done: bool = False

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Task text cannot be empty")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return (-self.priority, self.id) < (-other.priority, other.id)

    def __str__(self) -> str:
        mark = "x" if self.done else " "
        return f"[{mark}] {self.id} {self.text} ({self.priority})"
```

`src/taskman/models/__init__.py`:

```python
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = ["Priority", "Task", "PRIORITY_CHOICES"]
```

`src/taskman/storage/memory.py`:

```python
from ..models import Priority, Task

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


def mark_done(task_id: int) -> Task | None:
    task = find_task(task_id)
    if task is not None:
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
```

`src/taskman/storage/__init__.py`:

```python
from . import memory

__all__ = ["memory"]
```

`src/taskman/cli/commands.py`:

```python
import argparse
import functools
import sys

from ..models import Priority
from ..storage import memory


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        return result

    return wrapper


@log_command
def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = memory.add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    filtered = memory.filter_by_status(memory.tasks, args.status)
    result = memory.sort_tasks(filtered, args.sort)
    if not result:
        print("No tasks yet.")
    else:
        for task in result:
            print(task)


@log_command
def handle_done(args: argparse.Namespace) -> None:
    task = memory.mark_done(args.id)
    if task is None:
        print(f"Task with id {args.id} not found.")
    else:
        print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}
```

`src/taskman/cli/parser.py`:

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

    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("id", type=int, help="Task id")

    return parser
```

`src/taskman/cli/app.py`:

```python
from .commands import COMMAND_HANDLERS
from .parser import build_parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    handler(args)
```

`src/taskman/cli/__init__.py`:

```python
from .app import main

__all__ = ["main"]
```

`src/taskman/__main__.py`:

```python
from taskman.cli import main

if __name__ == "__main__":
    main()
```

`src/taskman/__init__.py` — оставляем пустым. Пакету верхнего уровня пока нечего ре-экспортировать: вся публичная поверхность API уже описана в `models/`, `storage/` и `cli/`.

Ключевые решения:

- `from ..models import Priority, Task` в `storage/memory.py` — относительный импорт на уровень вверх и обратно вниз, в `models/`. Он показывает, что относительный импорт считает уровни пакета (`taskman`), а не файловой системы.
- `from ..storage import memory` в `cli/commands.py`, а не `from ..storage.memory import add_task, tasks, ...`. Здесь `memory` импортируется как модуль-неймспейс, и вызовы выглядят как `memory.add_task(...)`, `memory.tasks`. Это осознанный выбор для модуля с мутируемым состоянием (`tasks: list[Task]`). По месту вызова сразу видно, что состояние живёт в `storage.memory`, а не размазано по неявным импортам отдельных имён.
- `[project.scripts] taskman = "taskman.cli:main"` — после `pip install -e .` в venv появляется исполняемый файл `taskman`, в `.venv/bin/taskman`. Он просто импортирует `taskman.cli` и вызывает `main`. Это ровно то, что `npm` делает с полем `"bin"` в `package.json`.
- `[tool.setuptools.packages.find] where = ["src"]` — говорит setuptools искать пакеты не в корне проекта, а в `src/`. Без этой строчки src-layout не соберётся автоматически: setuptools по умолчанию ищет пакеты рядом с `pyproject.toml`.

## Проверь себя

1. Почему `__init__.py` при импорте подмодуля (`import taskman.models.task`) выполняется **всегда**, даже если вы явно не импортировали сам пакет `taskman.models`? Чем это отличается от того, как `index.js` работает в JS-модуле?
2. Что означают точки в `from ..models import Task` — от чего именно они отсчитывают уровни, и почему это не то же самое, что `../` в пути файловой системы?
3. Запустите `python src/taskman/cli/app.py` напрямую — он упадёт с `ImportError: attempted relative import with no known parent package`. А `python -m taskman` работает. Почему, если оба способа "запускают Python-код из этого файла"?
4. Чем `pip install -e .` отличается от обычного `pip install .` в контексте разработки пакета — что происходит с изменениями в исходном коде после каждой правки?
5. Почему `requirements.txt`, сгенерированный через `pip freeze`, не является настоящим lock-файлом в том смысле, в каком им является `package-lock.json`? Чего в нём принципиально не хватает?

<details>
<summary>Ответы</summary>

1. Пакет в Python — это не просто "папка с файлами", а объект в `sys.modules`. Импорт любого подмодуля пакета **обязан** сначала создать и инициализировать объект самого пакета, а инициализация пакета и есть выполнение его `__init__.py`. Это гарантия, встроенная в механизм импорта самого языка (`importlib`), а не поведение, которое можно отключить. В JS `index.js` — это просто файл, который резолвер модулей ищет по соглашению, когда импортируют директорию как целое. Если импортировать конкретный файл внутри директории напрямую (`import './foo/bar.js'`), `index.js` вообще не будет тронут. В Python аналогичный "обход" невозможен: `__init__.py` пакета выполнится в любом случае.
2. Точки отсчитывают уровни в дереве **пакетов** — в том, что зарегистрировано в `sys.modules` и определено структурой `__init__.py`. Дерево директорий на диске тут ни при чём. На практике эти два дерева почти всегда совпадают один в один, поэтому разница незаметна в 99% случаев. Но концептуально они разные. Смысл записи `from ..models import Task` — "выйти на уровень пакета-родителя от пакета, в котором лежит **текущий модуль**", а не подняться на директорию выше в файловой системе. Отличие становится заметным именно тогда, когда модуль пытаются запустить не как часть пакета (см. вопрос 3). В этой ситуации у файла попросту нет информации о том, в каком пакете он находится.
3. При запуске `python file.py` напрямую интерпретатор загружает этот файл как модуль `__main__`, **без родительского пакета**. У файла нет информации о том, что он физически лежит внутри `taskman/cli/`. Запуск по прямому пути вообще не использует механизм импорта пакетов. А `from .commands import ...` требует знать текущий пакет, от которого нужно отсчитать точку. Родительского пакета нет, значит, отсчитывать не от чего — отсюда и ошибка. Команда `python -m taskman` — это принципиально другой механизм запуска. Она использует `runpy`, находит пакет `taskman` через обычный механизм импорта и определяет `taskman.__main__` как точку входа. Дальше эта точка входа выполняется **как часть пакета** `taskman`, с полностью и корректно инициализированной пакетной иерархией. Поэтому относительные импорты внутри работают.
4. `pip install .` копирует собранные файлы пакета в site-packages venv. После этого изменения в исходном коде проекта никак не влияют на установленную копию, пока пакет не переустановить заново. Editable-режим, `pip install -e .`, вместо копирования кладёт в site-packages лёгкий указатель на директорию с исходниками (`src/`). При импорте `taskman` интерпретатор буквально читает файлы оттуда, где вы их редактируете. Изменения в коде видны немедленно, без повторной установки.
5. `pip freeze` печатает список **всего, что сейчас установлено** в окружении, с версиями. Трёх вещей в этом списке нет. Нет разделения на "то, что я явно запросил" и "то, что подтянулось как транзитивная зависимость". Нет графа зависимостей, то есть непонятно, кто от кого зависит. И нет криптографических хешей, подтверждающих целостность и происхождение скачанного файла. Настоящий lock-файл — `package-lock.json`, `poetry.lock`, `uv.lock` — фиксирует разрешённое дерево зависимостей целиком, с хешами. Генерирует его детерминированный алгоритм разрешения версий. Это не побочный продукт того, что случайно оказалось установлено в конкретном окружении на момент запуска `freeze`.

</details>

## Частая ошибка

Самая частая ошибка на этом этапе — запустить один из файлов пакета напрямую как скрипт во время отладки. Это либо `python src/taskman/cli/app.py`, либо, что ещё чаще, клик "Run" на конкретном файле в IDE. Результат — `ImportError: attempted relative import with no known parent package`.

Разработчик, привыкший к Node, такого не ждёт. Там `node ./src/cli/app.js` работает без всяких дополнительных условий: Node сам резолвит `require`/`import` по пути от места запуска. Ничто в этом опыте не подсказывает, что *способ запуска* файла может менять, будут ли работать импорты внутри него.

Правильная реакция — не убирать относительные импорты в пользу абсолютных "чтобы просто заработало". Запускайте пакет так, как он предназначен для запуска: через `python -m taskman` или, после установки, через сгенерированную команду `taskman`. То есть всегда как часть пакета, а не как одинокий файл.

Второй частый момент — забыть про `[tool.setuptools.packages.find] where = ["src"]` при переходе на src-layout. Тогда после `pip install -e .` получится пустой или неверно собранный пакет. По умолчанию setuptools ищет пакеты рядом с `pyproject.toml`, то есть в корне проекта, а не в `src/`.

Симптом обычно не сразу очевиден. Установка проходит "успешно", без ошибок, но `import taskman` либо не находит пакет вовсе, либо находит не то, что ожидалось. Причина в том, что автоматический поиск пакетов у setuptools по умолчанию рассчитан на flat-layout и не заглядывает внутрь `src/` без явного указания.
