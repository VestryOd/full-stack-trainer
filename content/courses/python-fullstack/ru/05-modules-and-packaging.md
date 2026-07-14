# Модули, пакеты и упаковка проекта

## Теория

**Модуль vs пакет.** Модуль в Python — это просто один файл `.py`; при импорте (`import foo`) выполняется код файла `foo.py`, и результат кэшируется в `sys.modules`, так что повторный импорт не выполняет файл заново. Пакет — это директория, содержащая другие модули/пакеты, помеченная файлом `__init__.py` ("regular package"). Начиная с Python 3.3 есть ещё namespace packages — пакеты без `__init__.py` вовсе, но для обычного прикладного проекта явный `__init__.py` — стандарт и остаётся таковым в этом курсе.

**Зачем нужен `__init__.py`, если он может быть пустым.** Две роли: (1) исторически и по соглашению — маркер "это пакет, а не просто папка со скриптами"; (2) практически — место, где curates публичный API пакета через ре-экспорт:

```python
# taskman/models/__init__.py
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = ["Priority", "Task", "PRIORITY_CHOICES"]
```

Это позволяет писать `from taskman.models import Task` снаружи, не зная, что `Task` физически лежит в `taskman/models/task.py`, — ровно то же, что делает `index.js` в JS-пакете, реэкспортирующий содержимое внутренних файлов. Разница принципиальная: в JS `index.js` — это **соглашение**, работающее только потому, что резолвер модулей по умолчанию ищет именно `index.js` при импорте директории. В Python выполнение `__init__.py` при первом импорте любого модуля из пакета — **гарантия языка**, а не соглашение: `import taskman.models.task` всегда сначала выполнит `taskman/models/__init__.py`, даже если вы импортировали не сам пакет, а его подмодуль напрямую.

`__all__` — отдельная тема: он не "прячет" остальные имена (`from module import _private_name` всё равно сработает, если вы напишете имя явно), а лишь ограничивает, что попадёт при `from module import *`, и служит подсказкой для документации/IDE о "официальном" публичном API модуля.

**Относительные импорты.** `.` — текущий пакет, `..` — на уровень выше, и так далее:

```python
# taskman/storage/memory.py
from ..models import Priority, Task   # на уровень вверх (taskman/), затем в models
```

```python
# taskman/models/__init__.py
from .task import Task                 # в текущем пакете (models/), модуль task.py
```

Ключевой нюанс: относительные импорты считают уровни **пакетной иерархии**, а не буквальные шаги по файловой системе, и они работают, только если модуль импортирован **как часть пакета** — то есть через `import` откуда-то ещё, или через `python -m package.module`. Если запустить файл напрямую как скрипт (`python taskman/cli/app.py`), у интерпретатора нет информации о том, в каком пакете этот файл находится, и `from .commands import ...` упадёт с `ImportError: attempted relative import with no known parent package`. Абсолютные импорты (`from taskman.models import Task`) этой проблемы не имеют — они всегда резолвятся от корня `sys.path`/установленного пакета, независимо от того, как был запущен текущий файл.

**Разница с ES-модулями.** У ES-модулей (и Node) импорты — это явные **пути** (`./foo.js`, `../bar.js`), они буквально отражают файловую систему; у Python относительный импорт — это шаги по **пакетной иерархии**, которая обычно совпадает со структурой папок, но концептуально это разные вещи (99% времени они совпадают, но идея "количество точек = уровни пакета", а не "уровни директорий", становится заметна именно на пограничных случаях, вроде запуска файла напрямую). Плюс: экспорт в JS/TS — явный per-symbol (`export function foo`), импортировать можно только то, что явно экспортировано; в Python **всё**, что не имеет ведущего `_`, по умолчанию доступно для импорта — `__all__`/подчёркивание — это соглашение и curation для читателя, а не enforced-приватность на уровне языка.

**venv — глубже.** Помимо `activate`/`deactivate` (глава 00), для пакета с реальной структурой полезны:

```bash
pip install -e .        # editable install — код пакета подхватывается сразу,
                         # без переустановки после каждого изменения;
                         # аналог npm link / workspace-пакета в монорепо
pip list                # что установлено в текущем venv
pip show taskman        # метаданные конкретного установленного пакета
```

Editable install — не копия файлов в site-packages, а специальный "указатель", говорящий интерпретатору: "искать модули этого пакета вот в этой директории на диске" — поэтому изменения в исходниках видны сразу, без повторного `pip install`.

**requirements.txt vs pyproject.toml + poetry/uv.** `requirements.txt` — плоский список строк вида `requests==2.31.0`, исторически либо писался руками, либо генерировался через `pip freeze > requirements.txt`. У него нет структуры "прямая зависимость vs транзитивная", нет хешей для верификации целостности — это просто снимок того, что сейчас установлено, а не декларация того, что должно быть установлено. `pyproject.toml` (глава 00) описывает зависимости декларативно, но **сам по себе**, с одним только `pip`/`setuptools`, не создаёт настоящий lock-файл с разрешённым деревом транзитивных зависимостей — это было ограничение, отмеченное ещё в главе 00. Инструменты вроде **poetry** и **uv** добавляют поверх `pyproject.toml` полноценный lock-файл (`poetry.lock`, `uv.lock`) с точными версиями и хешами всего дерева — прямой аналог `package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`. На 2026 год `uv` — де-факто самый быстрый и рекомендуемый путь (написан на Rust, заменяет разом `pip` + `venv` + функциональность poetry), но для этого курса мы сознательно остаёмся на стандартном `pip`/`venv`, чтобы не зависеть от стороннего инструмента, пока не пройдены основы.

### Параллели с JS/TS/Node:

- Модуль ~ файл с ES-module семантикой (единица импорта в обоих языках); пакет ближе всего к npm-пакету с `index.js`-барелем — но исполнение `__init__.py` при импорте подмодуля — гарантия языка, а не конвенция резолвера, как `index.js`.
- Явный `export` в JS/TS против "всё публично по умолчанию" в Python — `__all__`/подчёркивание перед именем — это curation-соглашение для читателя и `import *`, а не языковой enforcement приватности.
- Точки в относительном импорте (`.`/`..`) — это уровни **пакетной иерархии**, не буквальные `./`/`../`-шаги по файлам, как в Node; и относительные импорты вообще не работают при запуске файла напрямую как скрипта — только при импорте как части пакета.
- `requirements.txt` ~ старый, вручную/`pip freeze`-собранный список без lock-семантики; `pyproject.toml` + `poetry`/`uv` ~ `package.json` + `package-lock.json`/`uv.lock` с реальным разрешением зависимостей.

## Что добавляем в проект

Разбиваем монолитный `main.py` на пакет `taskman` с тремя подпакетами — `models/` (Priority, Task), `storage/` (in-memory хранилище) и `cli/` (argparse, обработчики команд, `main()`) — и переезжаем на **src-layout** (`src/taskman/...`), обещанный ещё в главе 00. `pyproject.toml` получает секцию сборки (`[build-system]`, `[tool.setuptools.packages.find]`) и `[project.scripts]`, чтобы после `pip install -e .` команда `taskman` работала как настоящий установленный CLI-инструмент, а не только через `python main.py`.

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
4. Разбейте CLI-часть на `cli/parser.py` (`build_parser`), `cli/commands.py` (`log_command`, три обработчика, `COMMAND_HANDLERS`) и `cli/app.py` (`main()`, собирающий `parser` + `COMMAND_HANDLERS`).
5. `__main__.py` должен импортировать `main` из `taskman.cli` и вызывать его — это то, что делает возможным `python -m taskman`.
6. Обновите `pyproject.toml`: добавьте `[build-system]` (`setuptools`), `[tool.setuptools.packages.find] where = ["src"]` и `[project.scripts] taskman = "taskman.cli:main"`.
7. Установите пакет в editable-режиме (`pip install -e .` в активированном venv) и убедитесь, что работают **оба** способа запуска: `python -m taskman add "Buy milk"` и просто `taskman add "Buy milk"`.
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
    result = memory.sort_tasks(memory.filter_by_status(memory.tasks, args.status), args.sort)
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

`src/taskman/__init__.py` — оставляем пустым: пакету верхнего уровня пока нечего ре-экспортировать, вся публичная поверхность API уже описана в `models/`, `storage/`, `cli/`.

Ключевые решения:

- `from ..models import Priority, Task` в `storage/memory.py` — относительный импорт на уровень вверх и обратно вниз в `models/`; демонстрирует, что относительный импорт считает уровни пакета (`taskman`), а не файловой системы буквально.
- `from ..storage import memory` (а не `from ..storage.memory import add_task, tasks, ...`) в `cli/commands.py` — `memory` импортируется как модуль-неймспейс, и вызовы выглядят как `memory.add_task(...)`, `memory.tasks`. Это осознанный выбор для модуля с мутируемым состоянием (`tasks: list[Task]`): по месту вызова сразу видно, что состояние живёт в `storage.memory`, а не размазано по неявным импортам отдельных имён.
- `[project.scripts] taskman = "taskman.cli:main"` — после `pip install -e .` в venv появляется исполняемый файл `taskman` (в `.venv/bin/taskman`), который просто импортирует `taskman.cli` и вызывает `main`; это ровно то, что `npm` делает с полем `"bin"` в `package.json`.
- `[tool.setuptools.packages.find] where = ["src"]` — говорит setuptools искать пакеты не в корне проекта, а в `src/`; без этой строчки src-layout не соберётся автоматически (setuptools по умолчанию ищет пакеты рядом с `pyproject.toml`).

## Проверь себя

1. Почему `__init__.py` при импорте подмодуля (`import taskman.models.task`) выполняется **всегда**, даже если вы явно не импортировали сам пакет `taskman.models`? Чем это отличается от того, как `index.js` работает в JS-модуле?
2. Что означают точки в `from ..models import Task` — от чего именно они отсчитывают уровни, и почему это не то же самое, что `../` в пути файловой системы?
3. Почему `python src/taskman/cli/app.py`, запущенный напрямую, падает с `ImportError: attempted relative import with no known parent package`, а `python -m taskman` — работает, хотя оба способа "запускают Python-код из этого файла"?
4. Чем `pip install -e .` отличается от обычного `pip install .` в контексте разработки пакета — что происходит с изменениями в исходном коде после каждой правки?
5. Почему `requirements.txt`, сгенерированный через `pip freeze`, не является настоящим lock-файлом в том смысле, в каком им является `package-lock.json`? Чего в нём принципиально не хватает?

<details>
<summary>Ответы</summary>

1. Пакет в Python — это не просто "папка с файлами", а объект в `sys.modules`, и импорт любого подмодуля пакета **обязан** сначала создать и инициализировать объект самого пакета — а инициализация пакета и есть выполнение его `__init__.py`. Это гарантия, встроенная в механизм импорта самого языка (`importlib`), а не поведение, которое можно отключить. `index.js` в JS — это просто файл, который резолвер модулей ищет по соглашению, когда импортируют директорию как целое; если импортировать конкретный файл внутри директории напрямую (`import './foo/bar.js'`), `index.js` вообще не будет тронут — в Python аналогичный "обход" невозможен: `__init__.py` пакета выполнится в любом случае.
2. Точки отсчитывают уровни в дереве **пакетов** (то, что зарегистрировано в `sys.modules` и определено структурой `__init__.py`), а не в дереве директорий на диске. На практике эти деревья почти всегда совпадают один в один, поэтому разница незаметна в 99% случаев — но концептуально `from ..models import Task` означает "выйти на уровень пакета-родителя от пакета, в котором лежит **текущий модуль**", а не "подняться на директорию выше в файловой системе"; это отличие становится заметным именно тогда, когда модуль пытаются запустить не как часть пакета (см. вопрос 3), — в этой ситуации у файла попросту нет информации о том, в каком пакете он "находится".
3. При запуске `python file.py` напрямую интерпретатор загружает этот файл как модуль `__main__` **без родительского пакета** — у него нет информации о том, что он физически лежит внутри `taskman/cli/`, потому что запуск по прямому пути не использует механизм импорта пакетов вообще. `from .commands import ...` требует знать "текущий пакет, от которого нужно отсчитать точку" — а раз родительского пакета нет, посчитать точку не от чего, отсюда ошибка. `python -m taskman` — это принципиально другой механизм запуска: он использует `runpy`, находит пакет `taskman` через обычный механизм импорта, определяет `taskman.__main__` как точку входа и выполняет его **как часть пакета** `taskman`, с полностью корректно инициализированной пакетной иерархией — поэтому относительные импорты внутри работают.
4. `pip install .` копирует собранные файлы пакета в site-packages venv — после этого изменения в исходном коде проекта никак не влияют на установленную копию, пока не переустановить пакет заново. `pip install -e .` (editable/"развивающий" режим) вместо копирования кладёт в site-packages лёгкий указатель на директорию с исходниками (`src/`), так что при импорте `taskman` интерпретатор буквально читает файлы оттуда, где вы их редактируете — изменения в коде видны немедленно, без повторной установки.
5. `pip freeze` печатает список **всего, что сейчас установлено** в окружении, с версиями, но без разделения на "то, что я явно запросил" и "то, что подтянулось как транзитивная зависимость", без графа зависимостей (кто от кого зависит) и без криптографических хешей, подтверждающих целостность и происхождение скачанного файла. Настоящий lock-файл (`package-lock.json`, `poetry.lock`, `uv.lock`) фиксирует именно разрешённое дерево зависимостей целиком, с хешами, и генерируется детерминированным алгоритмом разрешения версий — а не является побочным продуктом "что уже случайно оказалось установлено в этом конкретном окружении на момент запуска `freeze`".

</details>

## Частая ошибка

Самая частая ошибка на этом этапе — попытаться запустить один из файлов пакета напрямую как скрипт во время отладки (`python src/taskman/cli/app.py` или, что ещё чаще, клик "Run" на конкретном файле в IDE) и получить `ImportError: attempted relative import with no known parent package`. Разработчик, привыкший к Node, где `node ./src/cli/app.js` работает без всяких дополнительных условий (Node сам резолвит `require`/`import` по пути от места запуска), не ожидает, что *способ запуска* файла в Python в принципе меняет, будут ли работать импорты внутри него. Правильная реакция — не убирать относительные импорты в пользу абсолютных "чтобы просто заработало", а запускать пакет так, как он предназначен для запуска: через `python -m taskman` (или, после установки, через сгенерированную команду `taskman`) — то есть всегда как часть пакета, а не как одинокий файл.

Второй частый момент — забыть про `[tool.setuptools.packages.find] where = ["src"]` при переходе на src-layout и получить на `pip install -e .` пустой или неверно собранный пакет (setuptools по умолчанию ищет пакеты рядом с `pyproject.toml`, то есть в корне проекта, а не в `src/`). Симптом обычно не сразу очевиден: установка проходит "успешно", без ошибок, но `import taskman` либо не находит пакет вовсе, либо находит не то, что ожидалось — потому что дефолтная автообнаружение пакетов setuptools рассчитано на flat-layout и не заглядывает внутрь `src/` без явного указания.
