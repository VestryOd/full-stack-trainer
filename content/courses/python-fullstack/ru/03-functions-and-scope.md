# Функции и область видимости

## Теория

**Функции — полноценные объекты первого класса**, как и в JS: их можно присвоить переменной, передать аргументом, вернуть из другой функции, положить в список или словарь. Здесь для JS-разработчика почти нет новой механики — разница в основном синтаксическая (`def name():` вместо `function name() {}` / стрелочных функций).

```python
def double(x: int) -> int:
    return x * 2

operations = {"double": double}   # функция — просто значение в словаре
operations["double"](21)          # 42
```

**`*args`/`**kwargs` в определении функции.** В главе 02 `*` использовался при **присваивании** (`first, *rest = [...]`) — здесь та же идея работает в сигнатуре функции, собирая "лишние" аргументы:

```python
def log(*args, **kwargs):
    print(args)     # tuple всех позиционных аргументов сверх объявленных
    print(kwargs)    # dict всех именованных аргументов сверх объявленных

log(1, 2, a=3, b=4)   # args=(1, 2), kwargs={"a": 3, "b": 4}
```

`*args` — прямой аналог rest-параметров в JS (`function log(...args)`). У `**kwargs` (сбор именованных аргументов в `dict`) прямого эквивалента в JS нет вообще. Ближайшее по духу — деструктуризация объекта-параметра (`function f({a, b}) {}`). Но это разбор одного объекта, переданного как есть, а не сбор "всех именованных аргументов вызова" в отдельную структуру на лету.

**Default-параметры и ловушка с мутабельным default.** Синтаксис похож на JS (`def f(x=5):` vs `function f(x = 5) {}`), но семантика вычисления default-значения — принципиально разная. В JS default-выражение вычисляется **заново при каждом вызове**. В Python default-значение вычисляется **один раз, в момент определения функции**, и это же значение переиспользуется при каждом вызове:

```python
def add_item(item, bucket=[]):   # bucket создаётся один раз, при импорте модуля
    bucket.append(item)
    return bucket

add_item(1)   # [1]
add_item(2)   # [1, 2]  — тот же список, что и в первом вызове!
```

Если default — неизменяемый объект (`None`, число, строка) — проблемы нет, значение просто нельзя изменить "по ссылке". Если default — изменяемый объект (`list`, `dict`, `set`) — все вызовы, не передавшие свой аргумент явно, **делят один и тот же объект**. Идиоматичное решение — `None` как default с созданием нового объекта внутри тела функции:

```python
def add_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

**Замыкания и LEGB-scope.** Замыкания работают как в JS: вложенная функция видит переменные внешней функции даже после того, как внешняя функция завершилась. Правило поиска имени при **чтении** — LEGB: **L**ocal → **E**nclosing → **G**lobal → **B**uilt-in, по порядку, снизу вверх по вложенности.

Ключевое отличие от JS — что происходит при **присваивании** имени внутри вложенной функции. В Python интерпретатор решает это на этапе разбора функции целиком, до выполнения. Если имени есть присваивание где-либо в теле функции, это имя **локальное для всей функции**, с самой первой строки — даже если присваивание физически ниже:

```python
counter = 0

def increment():
    counter += 1   # UnboundLocalError!
    return counter
```

`counter += 1` — это присваивание, значит `counter` считается локальной переменной во всей `increment()`. Но `+=` сначала **читает** текущее значение `counter`, чтобы прибавить 1 — а локальная `counter` на этот момент ещё не существует. Отсюда `UnboundLocalError: local variable 'counter' referenced before assignment`.

Чтобы явно сказать "это не новая локальная переменная, а изменение внешней", нужны ключевые слова `global` (для переменной модуля) или `nonlocal` (для переменной внешней функции при замыкании):

```python
def make_counter():
    count = 0
    def increment():
        nonlocal count   # без этой строки — тот же UnboundLocalError
        count += 1
        return count
    return increment

counter = make_counter()
counter()  # 1
counter()  # 2
```

В JS этой проблемы нет вообще. `let`/`const` объявляют переменную явно, один раз, в момент декларации. Поэтому любое последующее `counter += 1` внутри вложенной функции однозначно читается как присваивание уже существующей внешней переменной. Вопроса "новая локальная или изменение внешней" в JS не возникает: ключевое слово объявления (`let`/`const`/`var`) там есть всегда.

В Python объявления как отдельного действия нет — есть только присваивание. Раз явного объявления нет, компилятор вынужден определять "локальность" имени эвристикой, по всему телу функции сразу.

**Декораторы — механика, а не магия.** Декоратор — это просто функция, которая принимает функцию и возвращает функцию (обычно — обёртку, которая перед/после вызывает исходную):

```python
def shout(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result.upper()
    return wrapper

@shout
def greet(name):
    return f"hello, {name}"

greet("max")  # "HELLO, MAX"
```

`@shout` над `def greet` — это ровно то же самое, что написать `greet = shout(greet)` после определения функции. Никакого отдельного языкового механизма, кроме сахара для этой строчки, нет.

Побочный эффект: без дополнительных мер `greet.__name__` после декорирования будет `"wrapper"`, а не `"greet"`. Чинится это декоратором `functools.wraps(func)`, применённым к `wrapper`: он копирует `__name__`, `__doc__` и другие метаданные с исходной функции. Подробно `functools` разберём в главе про itertools/functools, здесь это первое, минимально необходимое знакомство.

### Параллели с JS/TS/Node:

- Функции как значения, замыкания — работают почти так же, как в JS; новой концепции здесь нет, только другой синтаксис.
- `*args` ~ rest-параметры (`...args`); у `**kwargs` (именованные аргументы, собранные в `dict`) прямого эквивалента в JS нет — ближайшее по духу — деструктуризация параметра-объекта, но это другой механизм.
- **Мутабельный default-параметр вычисляется один раз**, при определении функции, и переиспользуется при каждом вызове — в JS default-выражение пересчитывается заново при каждом вызове. Это меняет поведение ровно наоборот тому, что ожидает JS-разработчик.
- Присваивание переменной из внешней области видимости внутри вложенной функции требует явного `nonlocal`/`global`. В JS переменные `let`/`const` из внешнего замыкания переприсваиваются без специального синтаксиса: JS всегда объявляет переменную явно один раз через `let`/`const`/`var`.

## Что добавляем в проект

Выносим три ветки `if/elif` из `main()` в отдельные функции-обработчики: `handle_add`, `handle_list`, `handle_done`. Каждую оборачиваем декоратором `@log_command`, который печатает в stderr, какая команда запускается и когда она завершилась. Это первый шаг к нормальному логированию интерфейса командной строки (CLI).

Полноценное структурное логирование уже за рамками курса, но идиома "декоратор на все команды" — типовой паттерн для CLI-инструментов. Заодно диспетчеризация команд переезжает с `if/elif` на словарь `{имя команды: функция-обработчик}`. Это прямая иллюстрация того, что функции в Python — такие же значения, как строки или числа.

## Практическое задание

1. Разбейте текущую логику `main()` на три отдельные функции: `handle_add(args)`, `handle_list(args)`, `handle_done(args)`. Каждая принимает `argparse.Namespace` и делает то же, что раньше делала соответствующая ветка `if/elif`.
2. Напишите декоратор `log_command`, который оборачивает функцию-обработчик и печатает в `sys.stderr` две строки: одну перед вызовом (`[log] running: <command>`), вторую после (`[log] done: <command>`). Используйте `*args, **kwargs` в сигнатуре `wrapper`, а не жёстко зашитый единственный параметр. Так декоратор не завязан на то, что у всех обёрнутых функций один и тот же набор аргументов.
3. Примените `functools.wraps` к `wrapper`, чтобы `handle_add.__name__` после декорирования оставалось `"handle_add"`, а не `"wrapper"`.
4. Примените `@log_command` ко всем трём обработчикам.
5. Замените диспетчеризацию `if/elif` в `main()` на словарь `COMMAND_HANDLERS = {"add": handle_add, "list": handle_list, "done": handle_done}` и вызов `COMMAND_HANDLERS[args.command](args)`.

Вопросы на подумать:

- Логи от `log_command` печатаются в `sys.stderr`, а не в `sys.stdout` — почему это важно, если кто-то захочет сделать `python main.py list | grep milk`?
- Почему в декораторе стоит использовать `*args, **kwargs`, даже если сейчас все обработчики принимают ровно один параметр `args`? Что изменится, если в будущем один из обработчиков станет принимать два параметра?

## Разбор решения

```python
import argparse
import functools
import sys

PRIORITY_ORDER = ["low", "medium", "high"]
PRIORITY_RANK = {name: rank for rank, name in enumerate(PRIORITY_ORDER)}

tasks: list[dict] = []


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
        return result

    return wrapper


def add_task(text: str, priority: str = "medium") -> dict:
    task = {"id": len(tasks) + 1, "text": text, "done": False, "priority": priority}
    tasks.append(task)
    return task


def find_task(task_id: int) -> dict | None:
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def mark_done(task_id: int) -> dict | None:
    task = find_task(task_id)
    if task is not None:
        task["done"] = True
    return task


def filter_by_status(items: list[dict], status: str) -> list[dict]:
    if status == "all":
        return items
    want_done = status == "done"
    return [task for task in items if task["done"] == want_done]


def sort_tasks(items: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "priority":
        return sorted(items, key=lambda t: (-PRIORITY_RANK[t["priority"]], t["id"]))
    return sorted(items, key=lambda t: t["id"])


def format_task(task: dict) -> str:
    mark = "x" if task["done"] else " "
    return f"[{mark}] {task['id']} {task['text']} ({task['priority']})"


@log_command
def handle_add(args: argparse.Namespace) -> None:
    task = add_task(args.text, args.priority)
    print(f"Added: [{task['id']}] {task['text']} ({task['priority']})")


@log_command
def handle_list(args: argparse.Namespace) -> None:
    result = sort_tasks(filter_by_status(tasks, args.status), args.sort)
    if not result:
        print("No tasks yet.")
    else:
        for task in result:
            print(format_task(task))


@log_command
def handle_done(args: argparse.Namespace) -> None:
    task = mark_done(args.id)
    if task is None:
        print(f"Task with id {args.id} not found.")
    else:
        print(f"Marked done: [{task['id']}] {task['text']}")


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
        "--priority", choices=PRIORITY_ORDER, default="medium", help="Task priority"
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

- `wrapper(*args, **kwargs)` вместо `wrapper(args)` — декоратор не делает предположений о сигнатуре обёрнутой функции. Строка `namespace = args[0]` достаёт первый позиционный аргумент, у нас это всегда `argparse.Namespace`. Сам декоратор при этом остаётся универсальным и переиспользуемым для функций с другой сигнатурой.
- `@functools.wraps(func)` над `wrapper` — без этой строки `handle_add.__name__` после декорирования стало бы `"wrapper"`. Это сломало бы отладку (трейсбеки, `help()`, интроспекцию) и любой код, который полагается на имя функции.
- Логи идут в `sys.stderr`, а не `print()` в stdout. Команда `list` печатает в stdout только сами задачи, поэтому `python main.py list | grep milk` продолжает работать как ожидается. Логи не попадают в конвейер (pipe) и не мешают парсингу вывода.
- `COMMAND_HANDLERS` — словарь "имя команды → функция" вместо цепочки `if/elif`. Добавление новой команды в будущем — это одна новая функция плюс одна строка в словаре, а не ещё одна ветка `elif` в разрастающемся `main()`.

## Проверь себя

1. Почему `def add_item(item, bucket=[]):` — классическая ловушка, а не просто "неаккуратный, но рабочий" код? Что именно происходит с `bucket` между разными вызовами функции?
2. Дано:
   ```python
   counter = 0
   def increment():
       counter += 1
       return counter
   ```
   Почему этот код бросает `UnboundLocalError`, хотя в первый момент кажется, что `counter` должна просто прочитаться из внешней области видимости, как в JS?
3. В чём разница между `global` и `nonlocal`, и в каком случае нужен именно `nonlocal`, а не `global`?
4. Что конкретно означает `@decorator` над определением функции — во что это разворачивается "под капотом"?
5. Зачем нужен `functools.wraps(func)` внутри декоратора — что сломается, если его не использовать, и как это заметить на практике (не абстрактно, а в конкретном инструменте/поведении)?

<details>
<summary>Ответы</summary>

1. Default-значение параметра в Python вычисляется **один раз**, в момент выполнения строки `def add_item(...)`, то есть при импорте модуля, а не заново при каждом вызове функции. Это значит, что все вызовы `add_item(x)` без явного `bucket=...` получают **один и тот же объект списка**. Если один вызов мутирует его через `.append()`, это изменение видно во всех последующих вызовах. Физически это один и тот же объект в памяти, а не новый список "с нуля" для каждого вызова.
2. Python определяет "локальность" имени статически, разбирая **всё тело функции целиком** до выполнения. Если где-либо в теле есть присваивание имени, это имя считается локальным для всей функции, с первой её строки. А `counter += 1` — это присваивание, эквивалентное `counter = counter + 1`. Поэтому попытка прочитать `counter` для вычисления `counter + 1` видит "ещё не инициализированную локальную переменную", а не переменную модуля — отсюда `UnboundLocalError`. В JS такой двусмысленности нет. Переменная явно объявляется один раз через `let`/`const`, и любое последующее использование в замыкании однозначно ссылается на эту конкретную объявленную переменную.
3. `global` говорит интерпретатору: это имя — переменная модуля (глобальная), а не новая локальная, и при присваивании изменять нужно именно её. Ключевое слово `nonlocal` делает то же самое, но для переменной **ближайшей внешней функции** в замыкании, а не модуля. Нужен `nonlocal` именно тогда, когда вложенная функция должна изменить переменную из объемлющей функции — например, `count` в `make_counter`. А `global` там не подойдёт, потому что искомая переменная лежит не на уровне модуля, а на уровне другой функции.
4. `@decorator` непосредственно над `def func(): ...` — это синтаксический сахар, полностью эквивалентный записи `func = decorator(func)` сразу после определения `func`. Никакого отдельного языкового механизма для декораторов, кроме этой подстановки, нет — `decorator` вызывается с оригинальной функцией как единственным аргументом, а то, что он вернёт, становится новым значением имени `func`.
5. Без `functools.wraps(func)` к имени декорированной функции в итоге привязывается сам `wrapper` — со своим `__name__ == "wrapper"`, пустым `__doc__` и так далее. На практике это ломает три вещи:

   - Отладочные трейсбеки: в них фигурирует "wrapper", а не реальное имя функции, и стектрейс становится труднее читать.
   - `help(func)` и интроспекцию в редакторе кода: докстринг и сигнатура окажутся от `wrapper`, а не от исходной функции.
   - Любой код, который явно проверяет `func.__name__` — например, некоторые тестовые фреймворки или системы роутинга, сопоставляющие обработчики по имени.

</details>

## Частая ошибка

Самая известная ловушка Python для новичков любого бэкграунда — мутабельный default-параметр (`def f(items=[]):`). Для JS-разработчика она особенно коварна, потому что интуиция работает ровно наоборот. В JS `function f(items = []) {}` создаёт **новый** пустой массив при каждом вызове, если `items` не передан явно, и JS-разработчик автоматически переносит эту привычку на Python.

В реальности Python создаёт список `[]` один раз, при определении функции, и делится этим одним объектом между всеми "неявными" вызовами.

Баг обычно не проявляется сразу. Код прекрасно работает в тестах, где функция вызывается один раз. А "необъяснимо накапливать данные из предыдущих вызовов" он начинает в продакшене или в интеграционных тестах, где функция вызывается многократно за время жизни процесса. То есть ровно тогда, когда сложнее всего сопоставить симптом с причиной.

Второй частый момент — попытка присвоить значение переменной из объемлющей функции внутри замыкания без `nonlocal`, скопировав JS-рефлекс "просто переприсвой внешнюю переменную, замыкание же".

В Python это не ошибка компиляции, а `UnboundLocalError` в рантайме. Само сообщение об ошибке (`local variable referenced before assignment`) не подсказывает напрямую, что решение — добавить `nonlocal`, если не знать про эту механику заранее.
