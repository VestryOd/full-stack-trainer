# ООП и dataclasses

## Теория

**class, `__init__`, `self`.** Базовый синтаксис класса похож на JS, но с одним систематическим отличием: первый параметр каждого метода — `self` (текущий инстанс), и он **всегда явный**, вы пишете его руками в каждой сигнатуре:

```python
class Task:
    def __init__(self, text: str) -> None:
        self.text = text

    def mark_done(self) -> None:
        self.done = True
```

В JS `this` — implicit и печально известен своими правилами биндинга: `this` в обычном методе зависит от того, *как* метод был вызван (`obj.method()` — один `this`, `const fn = obj.method; fn()` — другой, `undefined`/`window` в strict/non-strict), поэтому существуют `.bind()`, стрелочные функции для методов-колбэков и т.п. В Python такой проблемы нет вообще: `self` — обычный параметр, он получает значение так же, как любой другой аргумент функции, при вызове через `instance.method(...)` Python сам подставляет `instance` первым аргументом. "Отвязанного метода" в том смысле, в котором это боль в JS, не существует — метод, взятый как `Task.mark_done`, просто требует явно передать `self` при вызове.

**Dunder-методы — протоколы поведения объекта.** Методы вида `__name__` ("double underscore", "dunder") — это точки расширения, через которые ваш класс подключается к встроенным операциям языка:

- `__repr__(self) -> str` — "техническое" представление объекта, то, что видно в REPL, в отладчике, в логах (`repr(obj)`), и то, во что по умолчанию форматируется объект, если не определён `__str__`.
- `__eq__(self, other) -> bool` — что значит "равенство" для этого класса. Без переопределения `==` для обычного класса — это сравнение **идентичности** (тот же объект в памяти), как `is`; переопределив `__eq__`, вы делаете `==` сравнением по значению.
- `__lt__(self, other) -> bool` — "меньше чем"; без него объекты вашего класса нельзя сравнивать через `<` и нельзя напрямую передавать в `sorted()`/`.sort()` без явного `key=`.

Прямой аналог в JS есть только для одного из этих трёх — `toString()`/`Symbol.toPrimitive` (примерно как `__str__`, но не разделено на "техническое" и "для показа" представление так явно). У `==`-сравнения по значению в JS есть частичный аналог — переопределение `valueOf()`/`Symbol.toPrimitive` для примитивных сравнений, но полноценного "определи, что значит равенство для моего класса" протокола, как `__eq__`, в JS нет — обычно пишут отдельный метод `.equals()` руками.

**`@dataclass` — компактный аналог "class + конструктор + repr + eq".** Обычный класс с несколькими полями требует писать `__init__`, `__repr__` и `__eq__` руками:

```python
class TaskPlain:
    def __init__(self, id: int, text: str, done: bool = False) -> None:
        self.id = id
        self.text = text
        self.done = done

    def __repr__(self) -> str:
        return f"TaskPlain(id={self.id!r}, text={self.text!r}, done={self.done!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaskPlain):
            return NotImplemented
        return (self.id, self.text, self.done) == (other.id, other.text, other.done)
```

`@dataclass` генерирует ровно это по объявлению полей:

```python
from dataclasses import dataclass

@dataclass
class TaskPlain:
    id: int
    text: str
    done: bool = False
```

Оба варианта дают одинаковое поведение `__init__`/`__repr__`/`__eq__` (сравнение по кортежу всех полей, в порядке объявления). Важный нюанс: `@dataclass` генерирует `__repr__`, но **не** генерирует `__str__` — если вам нужен человекочитаемый вывод для `print(obj)`, его придётся написать самим (без `__str__` `print(obj)` использует `__repr__` как fallback). `@dataclass` также не генерирует `__lt__`/`__gt__` по умолчанию (это включается флагом `order=True`, сравнивающим все поля по порядку) — если нужен свой порядок сравнения (не "по всем полям подряд"), `__lt__` пишется вручную, как в обычном классе.

Ещё один нюанс, продолжающий тему ловушки с мутабельным default из главы 03: `@dataclass` **не разрешит** написать `tags: list = []` прямо в теле класса — это бросит `ValueError` уже на этапе определения класса, а не тихо создаст расшаренный список, как это было с обычной функцией. Для мутабельного default в dataclass нужен `field(default_factory=list)`:

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    tags: list[str] = field(default_factory=list)  # новый список на каждый инстанс
```

**`@property`.** Позволяет обращаться к методу как к атрибуту — вызывается без скобок:

```python
class Temperature:
    def __init__(self, celsius: float) -> None:
        self._celsius = celsius

    @property
    def fahrenheit(self) -> float:
        return self._celsius * 9 / 5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value: float) -> None:
        self._celsius = (value - 32) * 5 / 9

t = Temperature(20)
t.fahrenheit        # 68.0 — без скобок, хотя это вызов метода
t.fahrenheit = 100   # вызывает сеттер
```

Синтаксически это довольно близко к `get`/`set` в классах JS — сама идея "вычисляемое свойство, выглядящее как обычный атрибут" не нова для JS-разработчика, отличается в основном декоратор-синтаксис (`@property`/`@x.setter`) вместо ключевых слов `get`/`set`.

**Наследование.** `class Child(Parent):`, вызов родительского метода — `super().__init__(...)`. Механика почти идентична `class Child extends Parent { constructor() { super(); } }` в JS/TS — как и в JS, `super()` должен быть вызван до обращения к `self` в переопределённом `__init__`, если родитель что-то инициализирует.

**ABC (Abstract Base Classes).** Модуль `abc` даёт `ABC` (базовый класс) и `@abstractmethod` — способ сказать "у этого класса есть метод, но реализация обязана быть в наследнике":

```python
from abc import ABC, abstractmethod

class Storage(ABC):
    @abstractmethod
    def save(self, task: "Task") -> None: ...

class JsonStorage(Storage):
    def save(self, task: "Task") -> None:
        ...  # реальная реализация
```

Попытка создать `Storage()` напрямую (без переопределения `save`) бросит `TypeError` при инстанцировании. Важное отличие от TS: `interface` в TS — это **структурная** типизация (любой объект с нужной формой подходит, явно ничего наследовать не нужно); `ABC` в Python — **номинальная**: класс обязан явно унаследоваться от `Storage`, иначе он не считается его подтипом, даже если у него есть метод с таким же именем и сигнатурой. Структурный аналог TS `interface` в Python — это `Protocol` (модуль `typing`), который разберём отдельно в главе про типизацию (10).

### Параллели с JS/TS/Node:

- `self` — явный параметр каждого метода, не подвержен проблемам биндинга `this`; не нужны `.bind()`/стрелочные функции "чтобы `this` не терялся".
- `__eq__`/`__lt__` — полноценный протокол "что значит равенство/порядок для моего класса", встроенный в язык; в JS для этого обычно пишут собственные методы `.equals()`/`.compareTo()` вручную, единого протокола нет.
- `@dataclass` экономит ровно тот боилерплейт, который в JS/TS вообще не нужно писать для plain-объектов, но который нужен в Python для полноценного класса с `__init__`/`__repr__`/`__eq__`.
- `ABC` — номинальная типизация (обязательное явное наследование), в отличие от структурных `interface` в TS; структурный аналог в Python — `Protocol` (глава 10).

## Что добавляем в проект

`Task` из обычного `dict` становится `@dataclass` с типизированными полями, а `priority` — из строки становится `Priority(IntEnum)` с чёткой упорядоченностью (`LOW < MEDIUM < HIGH`). `Task` получает `__lt__` (сортировка по приоритету, при равенстве — по id) и `__str__` (единый формат вывода для `add`/`list`/`done`), а `__post_init__` не даёт создать задачу с пустым текстом — закрывает вопрос "разрешать ли пустой текст", подвешенный ещё в главе 00.

## Практическое задание

1. Определите `class Priority(IntEnum)` с членами `LOW`, `MEDIUM`, `HIGH` (значения 0, 1, 2) и переопределите `__str__`, чтобы `str(Priority.LOW)` возвращало `"low"`, а не техническое представление enum.
2. Замените словарь-задачу на `@dataclass class Task` с полями `id: int`, `text: str`, `priority: Priority = Priority.MEDIUM`, `done: bool = False`.
3. Добавьте `Task.__post_init__`, бросающий `ValueError`, если `text` — пустая строка или строка из одних пробелов (используйте `.strip()`).
4. Добавьте `Task.__lt__`, сравнивающий по приоритету (по убыванию — высокий приоритет "меньше" в смысле сортировки, значит идёт раньше) и по `id` (по возрастанию) при равном приоритете.
5. Добавьте `Task.__str__` — единый формат вывода `[mark] id text (priority)`, используемый и в `add`, и в `list`, и в `done`.
6. Обновите весь storage-слой (`add_task`, `find_task`, `mark_done`, `filter_by_status`, `sort_tasks`) под `Task`-объекты вместо словарей; `sort_tasks(items, "priority")` должен использовать `sorted(items)` напрямую (без `key=`), полагаясь на `Task.__lt__`.

Вопросы на подумать:

- Сейчас пустой текст задачи приводит к тому, что процесс падает с сырым traceback'ом (`ValueError` никто не ловит). Это ожидаемо на этом этапе курса — но что бы вы хотели увидеть вместо traceback'а с точки зрения пользователя CLI? (Решение — в главе 06.)
- Почему `Task.__lt__` возвращает `NotImplemented`, а не бросает исключение, если `other` — не `Task`? Что это меняет для того, как Python обрабатывает сравнение?

## Разбор решения

```python
import argparse
import functools
import sys
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


tasks: list[Task] = []


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        return result

    return wrapper


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
        return sorted(items)  # использует Task.__lt__
    return sorted(items, key=lambda t: t.id)


@log_command
def handle_add(args: argparse.Namespace) -> None:
    priority = Priority[args.priority.upper()]
    task = add_task(args.text, priority)
    print(f"Added: {task}")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = sort_tasks(filter_by_status(tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
    else:
        for task in result:
            print(task)


@log_command
def handle_done(args: argparse.Namespace) -> None:
    task = mark_done(args.id)
    if task is None:
        print(f"Task with id {args.id} not found.")
    else:
        print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}


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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_HANDLERS[args.command]
    handler(args)


if __name__ == "__main__":
    main()
```

Ключевые решения:

- `Priority(IntEnum)` вместо просто `Enum` — `IntEnum` наследует от `int`, поэтому члены сравниваются между собой (`Priority.LOW < Priority.HIGH` работает "из коробки"), и `-self.priority` в `__lt__` даёт обычный `int`. Обычный `Enum` такого сравнения не даёт без ручного `__lt__` на самом enum'е.
- `PRIORITY_CHOICES = [p.name.lower() for p in Priority]` — список для argparse строится из самого enum'а (Enum — итерируемый), а не дублируется вручную; если позже добавится `Priority.URGENT`, `PRIORITY_CHOICES` подхватит его автоматически.
- Конвертация `Priority[args.priority.upper()]` происходит в обработчике, а не в `add_task` — `add_task` работает с уже готовым `Priority`, а не парсит строки; парсинг строки — забота CLI-слоя. Никакой проверки на "а вдруг строка невалидна" здесь нет специально: `choices=PRIORITY_CHOICES` в argparse уже гарантирует, что сюда дойдёт только валидное значение.
- `Task.__str__` используется во всех трёх обработчиках (`Added: {task}`, вывод в `list`, `Marked done: {task}`) — единый формат вместо трёх похожих f-строк, как было раньше с отдельной функцией `format_task`. Это меняет формат строки `Added:` (теперь она включает отметку `[ ]`/`[x]`, а не просто `[id]`) — осознанный компромисс в пользу одного источника правды для форматирования вместо копипасты.
- `sort_tasks(items, "priority")` теперь — просто `sorted(items)`, без `key=`. Это прямой практический эффект от `__lt__`: раньше (главы 02–03) логика "как сравнивать по приоритету" была отдельной lambda в `sort_tasks`, теперь она — часть самого класса `Task`, и `sorted()` использует её автоматически.

## Проверь себя

1. Почему в Python не бывает ситуации "метод потерял `this`", знакомой по JS (когда `const fn = obj.method; fn()` внутри выдаёт не тот объект или `undefined`)? Что в механике вызова метода в Python исключает эту проблему?
2. Чем `__repr__` принципиально отличается от `__str__` по назначению, и что использует `print(task)`, если `__str__` не определён, а `__repr__` — определён?
3. Почему `@dataclass class Config: tags: list[str] = []` бросает ошибку прямо при определении класса, а `def f(items=[]):` из главы 03 — не бросает ошибку никогда, просто тихо создаёт баг? Что изменилось в правилах?
4. Чем `Priority(IntEnum)` отличается от `Priority(Enum)` в контексте того, что нам было нужно для сортировки задач?
5. Почему `ABC` в Python называют "номинальной" типизацией, а `interface` в TypeScript — "структурной"? Приведите конкретный пример класса, который TS признал бы соответствующим интерфейсу, а Python — не признал бы соответствующим `ABC`-подклассом (без явного наследования).

<details>
<summary>Ответы</summary>

1. Проблема "потерянного `this`" в JS возникает потому, что `this` — это не параметр функции, а значение, которое определяется **в момент вызова**, в зависимости от синтаксиса вызова (`obj.method()` против `fn()` против `fn.call(x)`). В Python `self` — обычный, явно объявленный первый параметр метода, ничем не отличающийся от любого другого параметра функции. Когда вы пишете `instance.method(args)`, Python синтаксически разворачивает это в `ClassName.method(instance, args)` — `instance` передаётся как первый позиционный аргумент так же предсказуемо, как любой другой вызов функции с явными аргументами; никакой отдельной, зависимой от контекста подстановки не происходит.
2. `__repr__` предназначен для однозначного, "отладочного" представления объекта — в идеале такого, по которому можно понять, что это за объект и (в лучшем случае) как его пересоздать; это то, что видно в REPL, в отладчике, в `logging`. `__str__` предназначен для представления "для человека", которое видит конечный пользователь через `print()`/`str()`. Если `__str__` не определён, `print(task)` использует `__repr__` как запасной вариант — то есть `__repr__` работает как fallback для обоих случаев, а `__str__` — это опциональное уточнение только для пользовательского вывода.
3. Правило для функций (`def f(items=[])`) не изменилось со времён главы 03 — это по-прежнему тихий, работающий (хоть и багованный) код, потому что интерпретатор в общем случае не может знать, "предназначен" ли объект для расшаривания между вызовами или нет, и не запрещает это. `@dataclass`, в отличие от обычной функции, **знает семантику своих полей** — decorator явно анализирует объявленные default-значения при генерации `__init__`, и разработчики `dataclasses` сознательно добавили проверку именно для типов, у которых `__hash__` отсутствует (списки, словари, множества) — на этапе создания класса, а не на этапе каждого вызова конструктора, потому что для dataclass "поле с изменяемым default, расшаренное между всеми инстансами" почти гарантированно ошибка, а не осознанный выбор.
4. `Priority(IntEnum)` наследуется от `int`, поэтому операторы сравнения (`<`, `>`, `<=`, `>=`) работают между членами enum'а сразу, без дополнительного кода — `Priority.HIGH > Priority.LOW` — `True` "из коробки". `Priority(Enum)` (обычный) даёт только `==`/`!=`/хеш и итерацию по членам, но не поддерживает `<`/`>` — сравнение по порядку пришлось бы писать вручную (например, свой `__lt__` на самом enum'е или через `functools.total_ordering`). Нам был нужен порядок по приоритету — `IntEnum` даёт его бесплатно.
5. "Номинальная" типизация означает: совместимость типа определяется по **явно заявленному имени/иерархии** (класс должен явно написать `class X(Storage):`), а не по факту наличия нужных методов. "Структурная" — совместимость определяется по **форме** (набору методов/полей), без всякого явного объявления связи. Пример: класс `class FileLogger: def save(self, task): ...`, у которого есть метод `save` с той же сигнатурой, что и в `Storage`, но который **не** унаследован от `Storage` явно — в TS такой класс признали бы соответствующим `interface Storage { save(task: Task): void }` автоматически, просто по форме; в Python `isinstance(FileLogger(), Storage)` вернёт `False`, потому что `FileLogger` нигде явно не написал `(Storage)` в списке родителей.

</details>

## Частая ошибка

Наиболее вероятная ошибка при переходе от plain-класса к `@dataclass` — забыть, что `@dataclass` даёт `__repr__`, но не `__str__`, и удивиться, когда `print(task)` печатает что-то вроде `Task(id=1, text='Buy milk', priority=<Priority.LOW: 0>, done=False)` вместо ожидаемого человекочитаемого вывода. Разработчик, привыкший, что в JS у объекта обычно один способ "показать себя" (`toString()`, или дефолтный вывод `console.log`, который сам по себе неплохо форматирует объекты), не ожидает, что в Python есть **два раздельных** протокола представления с разным назначением, и первый инстинкт — решить, что `@dataclass` "не сработал" или "сломался repr", хотя на деле просто не был написан отдельный `__str__`.

Вторая типичная ошибка — попытаться отсортировать список dataclass-объектов через `sorted(items)` без реализации `__lt__` вообще, ожидая, что "раз это структурированные данные, Python сам придумает, как их сравнивать" (по аналогии с тем, как в JS `[].sort()` на объектах хотя бы не падает, просто сортирует "как попало" по строковому приведению). В Python это не тихая деградация до непредсказуемого порядка — это явный `TypeError: '<' not supported between instances of 'Task' and 'Task'`, потому что без `__lt__` (и без `order=True` в `@dataclass`) объекты вашего класса вообще не поддерживают операцию "меньше чем" — Python не пытается угадать порядок сравнения молча.
