# Итераторы, генераторы, itertools и functools

## Теория

**Протокол итератора.** `for x in obj:` — это не примитив языка сам по себе, а сахар над двумя методами: `iter(obj)` вызывает `obj.__iter__()` и получает **итератор** — объект с методом `__next__()`; дальше `for` вызывает `next(iterator)` снова и снова, пока не поймает `StopIteration`, которое сам же и гасит (наружу в ваш код оно не всплывает). Реализовать протокол вручную можно так:

```python
class Countdown:
    def __init__(self, start: int) -> None:
        self.current = start

    def __iter__(self):
        return self          # объект — сам себе итератор

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1

for n in Countdown(3):
    print(n)   # 3, 2, 1
```

`__iter__`, возвращающий `self`, — типичный паттерн для объектов, которые предназначены пройтись **один раз**: как только `current` дойдёт до 0, `Countdown` исчерпан навсегда, повторный `for` по тому же объекту ничего не даст (в отличие от `list`, чей `__iter__` каждый раз создаёт новый, независимый итератор — поэтому список можно проходить сколько угодно раз).

**Generator/`yield`.** То же самое, но на порядок компактнее:

```python
def countdown(start: int):
    current = start
    while current > 0:
        yield current
        current -= 1

for n in countdown(3):
    print(n)   # 3, 2, 1
```

Никакого ручного `__iter__`/`__next__`/`StopIteration`/хранения состояния (`self.current`) — функция с `yield` при вызове (`countdown(3)`) **не выполняет** тело немедленно, а возвращает объект-генератор, который уже сам реализует протокол итератора. Каждый `next()` возобновляет выполнение ровно с того места, где было последнее `yield`, со всеми локальными переменными в неизменном виде — вот что означает "функция приостанавливается". Это ровно генераторное expression из главы 02 (`(x for x in items)`), только записанное как полноценная функция с телом произвольной сложности вместо однострочного выражения.

**Сравнение с генераторами в JS.** В JS `function*`/`yield` механически похожи — то же приостановление/возобновление, `.next()` возвращает `{value, done}`. Разница — в частоте использования. В Python генераторы и ленивость пронизывают повседневный код: `range()` — не список, а ленивая последовательность; `dict.keys()`/`.values()`/`.items()` — ленивые представления, а не списки; `map()`/`filter()` в Python 3 — тоже ленивые (в отличие от Python 2, где они возвращали списки); чтение файла построчно (`for line in f:`) — тоже итератор, не список строк в памяти. В JS `function*` — сравнительно редкий, специализированный инструмент (кастомные iterable, некоторые async-паттерны до `async/await`), а не то, с чем сталкиваешься в обычном повседневном коде.

Ещё одно отличие, о котором стоит явно сказать: в JS есть **два разных** механизма перебора — `for...in` (перебирает **ключи** объекта, не использует протокол итератора вообще) и `for...of` (использует `Symbol.iterator`, концептуальный аналог Python-протокола). Спутать их — классическая ошибка новичка в JS (`for...in` на массиве перебирает индексы как строки и цепляет унаследованные перечисляемые свойства). В Python такой развилки нет: `for x in obj` всегда работает через один и тот же протокол `__iter__`/`__next__`, для чего угодно — списка, словаря, файла, генератора, собственного класса.

**`itertools`.** Модуль "строительных блоков" для работы с итераторами лениво:

```python
import itertools

itertools.islice(iterable, start, stop)   # ленивый срез — работает на ЛЮБОМ итераторе,
                                            # не только на том, что поддерживает [start:stop]
itertools.chain(iter1, iter2)              # склеить несколько итераторов в один, лениво
itertools.count(10)                        # бесконечный счётчик: 10, 11, 12, ...
```

`islice` особенно важен: обычный срез `seq[start:stop]` требует, чтобы `seq` поддерживал индексацию (`__getitem__`) — у генератора её нет. `itertools.islice` работает на любом итерируемом объекте, включая бесконечные генераторы, беря только то, что реально нужно, и не более того.

Отдельный нюанс, о который легко споткнуться: `itertools.groupby(iterable, key)` группирует только **подряд идущие** элементы с одинаковым ключом — это не "SQL GROUP BY", а скорее "схлопнуть соседние повторы". Если вход не отсортирован по нужному ключу заранее, одинаковые ключи, разбросанные по разным местам последовательности, попадут в **разные** группы.

**`functools`.** Три конкретных инструмента:

`reduce(func, iterable, initial)` — прямой ответ на вопрос из главы 02: у comprehension нет аналога `.reduce()`, потому что это `functools.reduce`:

```python
from functools import reduce

total = reduce(lambda acc, x: acc + x, [1, 2, 3, 4], 0)
# ~ [1, 2, 3, 4].reduce((acc, x) => acc + x, 0)
```

`partial(func, *args, **kwargs)` — заранее связывает часть аргументов, возвращая новый вызываемый объект:

```python
from functools import partial

print_err = partial(print, file=sys.stderr)
print_err("oops")   # эквивалент print("oops", file=sys.stderr)
```

Ближайший аналог в JS — `fn.bind(thisArg, ...args)`, но `.bind()` в первую очередь про фиксацию `this`, а связывание аргументов — вторичная возможность. В Python `self` никогда не был неявным (глава 04), поэтому `partial` — чистый, общий инструмент "зафиксировать часть аргументов", без всякого багажа, связанного с контекстом вызова.

`lru_cache` — декоратор мемоизации: кэширует результат функции по хешируемым аргументам, повторный вызов с теми же аргументами не выполняет тело функции заново:

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
```

Два условия, без которых `lru_cache` — плохая идея: (1) все аргументы должны быть **хешируемыми** (список аргументом — `TypeError: unhashable type: 'list'`, прямая связь с главой 02 про хешируемость ключей `dict`); (2) функция должна быть **чистой** — результат зависит только от аргументов, не от внешнего мутируемого состояния, иначе кэш начнёт молча возвращать устаревшие данные. Ровно поэтому `lru_cache` не появится в storage-функциях этого проекта дальше — они принимают списки (нехешируемые) и/или читают общее мутируемое состояние (`tasks`), и то, и другое делает кэширование результата некорректным.

### Параллели с JS/TS/Node:

- `for...of` в JS использует `Symbol.iterator` — концептуальный аналог `__iter__`/`__next__`, но в JS есть ещё и **другой** `for...in` (перебор ключей, не протокол итератора) — источник классической путаницы; в Python протокол перебора один-единственный, для всего.
- Генераторы в JS (`function*`) механически похожи, но остаются нишевым инструментом; в Python ленивость — часть повседневных идиом (`range`, `dict`-представления, `map`/`filter`, чтение файлов).
- `functools.reduce` ~ `.reduce()` — наконец прямой аналог, обещанный ещё в главе 02.
- `functools.partial` ~ `.bind()`, но без "багажа" фиксации `this` — в Python нечего фиксировать, `self` и так всегда явный.

## Что добавляем в проект

Добавляем ленивую постраничную выдачу к команде `list`: флаги `--page`/`--page-size`, генератор `paginate`, который лениво отдаёт страницы по мере надобности, и `itertools.islice` поверх него, чтобы забрать ровно одну нужную страницу, не строя все остальные. Заодно причёсываем повторяющийся `print(..., file=sys.stderr)` в `cli/commands.py` через `functools.partial`.

## Практическое задание

1. В `storage/memory.py` напишите генератор `paginate(items: list[Task], page_size: int)`, который через `yield` лениво отдаёт последовательные страницы (списки до `page_size` задач каждая).
2. Напишите `get_page(items, page, page_size)`, использующую `itertools.islice` поверх `paginate(...)`, чтобы достать ровно нужную (1-based) страницу; если страница за пределами данных — верните `[]`, используя `next(iterator, default)`, а не `try/except StopIteration`.
3. Добавьте к подкоманде `list` флаги `--page` (по умолчанию 1) и `--page-size` (по умолчанию 5).
4. Обновите `handle_list`, чтобы печаталась только запрошенная страница плюс строка `-- page X of Y --` внизу (общее число страниц — через целочисленное деление).
5. В `cli/commands.py` замените повторяющиеся `print(..., file=sys.stderr)` на модульный `print_err = functools.partial(print, file=sys.stderr)`.

Вопросы на подумать:

- Почему `lru_cache` нельзя безопасно навесить на `get_page`/`sort_tasks`/любую из текущих storage-функций, даже если кэширование теоретически ускорило бы повторные вызовы? Что именно здесь мешает — назовите обе причины.
- Если вызвать `get_page` на списке из 100 задач с `page_size=5`, запрашивая страницу 1 — сколько элементов реально пройдёт цикл `for item in items:` внутри `paginate`? А если запросить страницу 3? А несуществующую страницу 999?

## Разбор решения

Меняются только `storage/memory.py`, `cli/parser.py` и `cli/commands.py`; остальные файлы — без изменений с главы 06.

`src/taskman/storage/memory.py` (обновлён — добавлены `paginate`/`get_page`, остальное без изменений):

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

`src/taskman/cli/parser.py` (обновлён — два новых аргумента у `list`):

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

`src/taskman/cli/commands.py` (обновлён):

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

Ключевые решения:

- `paginate` — обычная генераторная функция: копит элементы в `page`, отдаёт её через `yield`, как только накопилось `page_size` штук, обнуляет и продолжает; последняя, неполная страница отдаётся после цикла, если в ней что-то осталось.
- `get_page` не пишет собственный цикл "пропустить N страниц" — `itertools.islice(paginate(...), page - 1, page)` берёт ровно один элемент с нужным индексом из потока страниц, не материализуя список всех страниц целиком.
- `next(pages, [])` вместо `try/except StopIteration` — `next()` со вторым аргументом-дефолтом обрабатывает "итератор пуст" декларативно, без исключения вообще; для страницы за пределами данных `islice` просто не найдёт элемент с нужным индексом, и `next` вернёт `[]`.
- `print_err = functools.partial(print, file=sys.stderr)` — используется во всех местах, где раньше был `print(..., file=sys.stderr)` дважды в `log_command` и один раз в `handle_done`; сам `print` не переопределяется и не оборачивается вручную, просто создаётся его версия с уже зафиксированным `file`.
- `lru_cache` в этом файле не используется нигде — ни `get_page`, ни `sort_tasks` не подходят: обе принимают `list[Task]` (нехешируемый аргумент) и обе неявно зависят от того, что содержимое `tasks` могло измениться между вызовами (флаг `done`, новые задачи) — кэширование результата было бы попросту неверным.

## Проверь себя

1. Почему `Countdown.__iter__`, возвращающий `self`, — это нормальный паттерн для одноразового итератора, но был бы плохим выбором для класса вроде `TaskList`, который должен поддерживать несколько независимых проходов одновременно (например, два вложенных `for`-цикла по одному и тому же списку задач)?
2. Что именно "запоминает" генератор между двумя вызовами `next()` — и почему `yield` избавляет от необходимости писать `self.current = ...` вручную, как в классе на протоколе итератора?
3. Чем `itertools.islice(iterable, start, stop)` принципиально отличается от обычного среза `seq[start:stop]` — из-за чего первое работает на генераторе, а второе — нет?
4. Дано: `next(some_iterator, "default")`. Что произойдёт, если у итератора ещё остались элементы? А если он уже исчерпан? Почему это лучше, чем оборачивать `next(some_iterator)` в `try/except StopIteration` ради того же результата?
5. Почему `functools.lru_cache`, применённый к функции, которая принимает `list` в качестве аргумента, ломается ещё до первого вызова с реальными данными — какая именно ошибка при этом возникает и почему?

<details>
<summary>Ответы</summary>

1. `__iter__`, возвращающий `self`, означает, что объект **является** своим собственным итератором — то есть у него есть только одно "текущее положение" (одно состояние прогресса), общее для всех, кто его перебирает. Если два вложенных `for`-цикла одновременно перебирают один и тот же `Countdown`-объект, они будут двигать один и тот же общий счётчик, мешая друг другу. `list.__iter__()` вместо этого создаёт **новый** объект-итератор при каждом вызове `iter()`, у которого своя, независимая позиция — поэтому список можно перебирать в нескольких одновременных циклах без коллизий. Для `TaskList`, если она должна поддерживать несколько независимых проходов, `__iter__` должен возвращать новый вспомогательный объект-итератор (или использовать `yield` — генераторная функция при каждом вызове тоже создаёт новый, независимый объект-генератор).
2. Генератор запоминает полный "кадр выполнения" функции в момент `yield` — значения всех локальных переменных и точную строку кода, на которой выполнение приостановилось. `yield` — это встроенная в интерпретатор возможность приостановить и позже возобновить именно эту функцию с этого самого места; ручная реализация того же самого через класс требует явно хранить каждую переменную, которая должна "пережить" между вызовами `__next__`, как атрибут `self` (`self.current` в `Countdown`), потому что у обычного метода нет автоматического "заморозить и разморозить локальные переменные" — это и есть весь объём работы, которую убирает `yield`.
3. `seq[start:stop]` требует, чтобы у `seq` был метод `__getitem__`, то есть произвольный доступ по индексу — генератор такого доступа не предоставляет вообще (у него есть только "дай следующий элемент", без "дай элемент номер N напрямую"). `itertools.islice` не требует индексации: он просто вызывает `next()` нужное число раз, пропуская и отбрасывая элементы до `start`, затем отдавая элементы до `stop`, и работает на любом объекте, реализующем протокол итератора — включая бесконечные генераторы, где `seq[start:stop]` в принципе невозможен (не существует способа узнать длину или проиндексировать бесконечную последовательность).
4. Если у итератора есть ещё элементы, `next(some_iterator, "default")` вернёт следующий элемент как обычно — второй аргумент в этом случае просто не используется. Если итератор исчерпан, вместо того чтобы бросить `StopIteration`, функция тихо вернёт `"default"`. Это лучше, чем `try/except StopIteration`, ровно в тех случаях, когда "итератор пуст" — не ошибка, а ожидаемый, штатный исход (как "странице за пределами данных нет содержимого") — код читается как одно выражение с явным запасным значением, а не как обработка исключительной ситуации, которой на самом деле не является.
5. `lru_cache` кэширует результаты по ключу, построенному из аргументов вызова, а для этого аргументы должны быть **хешируемыми** — кэш внутри устроен как словарь `{аргументы: результат}`, а ключом словаря, как разобрано в главе 02, не может быть изменяемый объект вроде `list`. Ошибка возникает не при определении функции (декоратор применяется без проблем), а при первом же **вызове** с аргументом-списком — `TypeError: unhashable type: 'list'`, потому что именно в этот момент `lru_cache` пытается использовать переданный список как часть ключа для собственного внутреннего кэша.

</details>

## Частая ошибка

Самая частая ошибка при первом знакомстве с генераторами — попытаться пройти один и тот же генератор дважды, ожидая, что второй проход снова начнётся с начала, как это происходит со списком. Разработчик, привыкший, что `for x of arr` в JS можно написать хоть десять раз подряд над одним и тем же массивом без побочных эффектов, переносит это ожидание на Python-генератор — но генератор, в отличие от списка, **является** одноразовым итератором (см. вопрос 1 выше): как только он исчерпан (или как только вы явно вызвали `next()` до конца), повторный `for` по тому же объекту не выполнится ни разу, без единой ошибки — просто тихо ничего не напечатает. В контексте `paginate` это означает: если сохранить результат `paginate(tasks, 5)` в переменную и попытаться получить из неё сначала страницу 2, а потом страницу 1 — второй запрос не сработает, потому что генератор уже продвинулся вперёд и не может "отмотаться назад"; для каждого нового запроса страницы нужен новый вызов `paginate(...)`, что как раз и делает `get_page`, создавая свежий генератор при каждом обращении.

Вторая типичная ошибка — использовать `itertools.groupby` как "нормальный" group-by, ожидая, что он сам найдёт и сгруппирует все элементы с одинаковым ключом по всей последовательности, как это делает группировка в SQL или `_.groupBy` в lodash. `groupby` группирует только **соседние** элементы с одинаковым ключом; если данные не отсортированы заранее по этому ключу, одинаковые значения, находящиеся не рядом друг с другом, окажутся в разных, отдельных группах — код при этом не упадёт и не предупредит, просто выдаст больше групп, чем ожидалось.
