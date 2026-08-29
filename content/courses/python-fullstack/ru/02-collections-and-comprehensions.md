# Коллекции и comprehensions

## Теория

**list, tuple, dict, set — четыре встроенные коллекции, и когда какую брать.**

- `list` — изменяемый упорядоченный набор, как `Array` в JS: `[1, 2, 3]`.
- `tuple` — **неизменяемый** упорядоченный набор фиксированной длины: `(1, "a", True)`. Ближайший аналог в TS — tuple-тип `[string, number]`, а не просто "readonly массив": длина и порядок типов зафиксированы по смыслу использования. Используется для "маленькой записи из нескольких полей", где отдельный класс/dataclass — избыточен (до главы 04, где для этого появится `@dataclass`).
- `dict` — набор пар ключ-значение: `{"a": 1, "b": 2}`. Важное отличие от объекта в JS: ключом может быть **любой hashable-тип**, не только строка — `{(1, 2): "point", 3: "three"}` валиден. Это делает Python `dict` ближе к JS `Map`, чем к `{}`-литералу объекта.
- `set` — неупорядоченный набор **уникальных** значений: `{1, 2, 3}`. Аналог `Set` в JS. Ловушка: `{}` — это **пустой dict**, а не пустой set, потому что синтаксис `{}` исторически был занят словарём раньше. Пустой set создаётся только через `set()`.

**Срезы (slices).** Работают на `list`, `tuple`, `str` — везде, где есть понятие последовательности: `seq[start:stop:step]`. Отрицательные индексы считают с конца, отрицательный шаг — идёт в обратную сторону:

```python
items = [10, 20, 30, 40, 50]
items[1:3]     # [20, 30]
items[:2]      # [10, 20]
items[-2:]     # [40, 50]
items[::-1]    # [50, 40, 30, 20, 10] — реверс без reverse()
```

Это заметно мощнее, чем `.slice()` в JS: есть третий параметр (шаг), и срезы работают на `str` "из коробки" — `"hello"[::-1]` даёт `"olleh"`. В JS для разворота строки нужно идти через массив и обратно.

**Comprehensions — не просто синтаксический сахар, а базовая идиома Python.** Там, где в JS вы пишете `.map()`/`.filter()`, в Python идиоматично пишут comprehension:

```python
nums = [1, 2, 3, 4, 5]

[n * 2 for n in nums]              # ~ nums.map(n => n * 2)
[n for n in nums if n % 2 == 0]    # ~ nums.filter(n => n % 2 === 0)
[n * 2 for n in nums if n % 2 == 0]  # map + filter в одном выражении
```

То же самое для `dict` и `set`:

```python
{n: n * n for n in nums}     # dict comprehension: {1: 1, 2: 4, 3: 9, ...}
{n % 3 for n in nums}         # set comprehension: {0, 1, 2} — только уникальные
```

Для `.reduce()` прямого аналога в comprehension-синтаксисе нет — это `functools.reduce`, разберём отдельно в главе про itertools/functools.

**List comprehension vs generator expression — eager vs lazy.** `[x for x in items]` (квадратные скобки) строит весь список в памяти немедленно. `(x for x in items)` (круглые скобки, без отдельного вызова функции) создаёт **генератор**. Генератор производит значения по одному, лениво, по мере итерации, и пройти его можно только один раз:

```python
squares_list = [x * x for x in range(1_000_000)]   # сразу занимает память под весь список
squares_gen = (x * x for x in range(1_000_000))    # почти не занимает память

sum(x for x in range(1_000_000) if x % 2 == 0)     # генератор прямо в sum(), без списка
```

Это прямая параллель с тем, зачем в JS вообще нужны генераторы (`function*`/`yield*`), только в Python ленивые выражения — рутинная часть повседневного кода, а не редкий приём. Подробнее про generator/yield — в отдельной главе (07).

**Unpacking (деструктуризация) в присваивании.** Базовый unpacking похож на деструктуризацию массива в JS:

```python
a, b = 1, 2
a, b = b, a          # swap без временной переменной (в JS так же: [a, b] = [b, a])
```

`*` в цели присваивания собирает "остаток" в список — и, в отличие от JS, звёздочка может стоять **не только последней**:

```python
first, *rest = [1, 2, 3, 4, 5]     # first=1, rest=[2, 3, 4, 5]
*head, last = [1, 2, 3, 4, 5]      # head=[1, 2, 3, 4], last=5
a, *middle, z = [1, 2, 3, 4, 5]    # a=1, middle=[2, 3, 4], z=5 — звезда в середине
```

В JS rest-элемент (`...rest`) в деструктуризации массива обязан быть последним (`const [a, ...rest] = arr` — валидно, `const [a, ...rest, z] = arr` — `SyntaxError`). Python это ограничение снимает: интерпретатор просто вычисляет, сколько элементов "лишние", и кладёт их в средний `*rest`.

Отдельно от unpacking в присваивании — распаковка через `**` для словарей, аналог object spread в JS:

```python
defaults = {"priority": "medium", "done": False}
task = {**defaults, "text": "Buy milk"}   # ~ { ...defaults, text: "Buy milk" }
```

(Про `*args`/`**kwargs` в *определении функций* — отдельно, в главе 03; здесь речь только про присваивание/литералы.)

### Параллели с JS/TS/Node:

- `list` ~ `Array`; `tuple` ~ TS-кортеж `[string, number]` (фиксированная длина/типы), не просто "замороженный массив".
- `dict` ближе к `Map` (произвольные hashable ключи), чем к `{}`-литералу объекта JS, где ключи всегда приводятся к строкам.
- List comprehension = `.map()`/`.filter()` в одном выражении. Generator expression — как написанный руками `function*`, только синтаксис делает его основной идиомой, а не редким инструментом.
- Star-unpacking может стоять в середине цели присваивания (`a, *mid, z = ...`) — в JS rest-элемент обязан быть последним.

## Что добавляем в проект

Добавляем `priority` каждой задаче. Пока это просто строка `"low"`, `"medium"` или `"high"`, а `Enum` появится в главе 04 вместе с dataclass.

Ещё расширяем `list` двумя флагами: `--status {all,done,pending}` для фильтрации и `--sort {id,priority}` для сортировки. Именно тут естественно применяются list comprehension (фильтрация) и dict comprehension (таблица приоритет → ранг для сортировки).

## Практическое задание

1. Добавьте к команде `add` необязательный флаг `--priority` со значениями `low`/`medium`/`high` (по умолчанию `medium`). Задача теперь хранит поле `priority`.
2. Добавьте к команде `list` флаг `--status` со значениями `all` (по умолчанию), `done`, `pending` — фильтрует задачи перед выводом.
3. Добавьте к `list` флаг `--sort` со значениями `id` (по умолчанию) и `priority`. При `--sort priority` задачи с высоким приоритетом должны идти первыми, а при равном приоритете — сортировка по `id` по возрастанию. То есть это сортировка по **двум ключам одновременно**, не по одному.
4. Реализуйте фильтрацию через list comprehension, а таблицу "приоритет → числовой ранг для сортировки" — через dict comprehension.

Вопросы на подумать:

- Как отсортировать список по двум критериям сразу (приоритет по убыванию, id по возрастанию) **одним** вызовом `sorted()`, без ручного двойного прохода? Подсказка: `key` может возвращать кортеж.
- Что произойдёт, если вызвать `list --sort priority` на пустом списке задач? Нужно ли это обрабатывать отдельно, или сортировка/фильтрация пустого списка работает "бесплатно"?

## Разбор решения

```python
import argparse

PRIORITY_ORDER = ["low", "medium", "high"]
PRIORITY_RANK = {name: rank for rank, name in enumerate(PRIORITY_ORDER)}

tasks: list[dict] = []


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

    if args.command == "add":
        task = add_task(args.text, args.priority)
        print(f"Added: [{task['id']}] {task['text']} ({task['priority']})")
    elif args.command == "list":
        result = sort_tasks(filter_by_status(tasks, args.status), args.sort)
        if not result:
            print("No tasks yet.")
        else:
            for task in result:
                print(format_task(task))
    elif args.command == "done":
        task = mark_done(args.id)
        if task is None:
            print(f"Task with id {args.id} not found.")
        else:
            print(f"Marked done: [{task['id']}] {task['text']}")


if __name__ == "__main__":
    main()
```

Ключевые решения:

- `PRIORITY_RANK = {name: rank for rank, name in enumerate(PRIORITY_ORDER)}` — dict comprehension строит `{"low": 0, "medium": 1, "high": 2}` один раз при импорте модуля. Написанная руками таблица рисковала бы рассинхронизироваться с `PRIORITY_ORDER`.
- `filter_by_status` — list comprehension `[task for task in items if task["done"] == want_done]` вместо ручного цикла с `.append()`. Читается как "все задачи, где done равно тому, что нам нужно".
- `key=lambda t: (-PRIORITY_RANK[t["priority"]], t["id"])` — сортировка по кортежу решает задачу "два критерия, разное направление" одним вызовом `sorted()`. В Python `sorted()` **устойчив** (stable sort) и сравнивает кортежи поэлементно. Минус перед рангом переворачивает направление только для первого критерия: высокий приоритет идёт раньше, а `id` остаётся по возрастанию.
- Валидация `priority`/`status`/`sort` полностью на стороне `choices=...` в argparse. Внутри бизнес-логики нет `if priority not in {...}: raise ...`. Невалидное значение сюда физически не может дойти: argparse оборвёт процесс раньше и с понятным сообщением.

## Проверь себя

1. Обычный `for x in range(3): pass` оставляет `x` в окружающей области видимости, а list comprehension `[x for x in range(3)]` — нет. Почему, если оба используют одно и то же ключевое слово `for`?
2. Почему `{}` создаёт пустой `dict`, а не пустой `set`, и как на самом деле создать пустой set? Почему для непустых литералов `{1, 2, 3}` конфликта с dict нет?
3. В чём разница между `[x for x in items]` и `(x for x in items)`? Когда вычисляются значения и можно ли пройти результат больше одного раза?
4. Почему ключом `dict` может быть `tuple`, но не может быть `list`? Какое свойство должно выполняться для типа-ключа, и как оно связано с изменяемостью?
5. Дано `a, *b, c = [1, 2, 3, 4, 5]`. Чему равны `a`, `b`, `c`? Опишите механику работы звёздочки, когда она стоит не последней в цели присваивания.

<details>
<summary>Ответы</summary>

1. Comprehension в Python 3 — это фактически неявная функция: у него собственная область видимости, и переменная цикла существует только внутри вычисления comprehension. Обычный оператор `for` — не функция и новой области видимости не создаёт. В главе 01 перечислено, кто её создаёт: `def`, `class` и comprehension. Поэтому переменная цикла остаётся в той области видимости, где `for` был написан, и после цикла видна снаружи.
2. Синтаксис `{}` исторически закреплён за `dict`. Словари появились в Python раньше, чем set как отдельный тип с собственным литералом. К моменту, когда set получил литеральный синтаксис `{1, 2, 3}`, `{}` уже означало "пустой словарь". Менять смысл `{}` задним числом означало бы сломать весь существующий код, поэтому для пустого set пришлось оставить только явный вызов `set()`. Конфликта с непустыми `{1, 2, 3}` нет, потому что наличие `:` внутри (`{"a": 1}`) однозначно отличает dict-литерал от set-литерала на этапе разбора синтаксиса.
3. `[x for x in items]` вычисляет **все** значения сразу и кладёт их в список в памяти. Результат можно проходить сколько угодно раз, у него есть длина и индексация. Выражение `(x for x in items)` создаёт объект-генератор, который вычисляет следующее значение только когда его действительно запрашивают. Это происходит на следующем шаге `for`-цикла или при вызове `next()`. После одного полного прохода генератор исчерпан, и повторная итерация не даст ничего — это его фундаментальное отличие от списка.
4. Ключ `dict` должен быть **hashable**. У него должен быть стабильный `__hash__`, не меняющийся, пока объект существует. На практике это означает "неизменяемый" — или хотя бы не изменяемый в тех полях, что участвуют в хеше. Тип `tuple` неизменяем и hashable, если все его элементы тоже hashable. А `list` изменяем. Если бы список был ключом, а потом кто-то вызвал у него `.append()`, хеш ключа поменялся бы прямо внутри словаря и сломал внутреннюю хеш-таблицу. Поэтому Python явно запрещает списки как ключи и бросает `TypeError: unhashable type`.
5. `a = 1`, `b = [2, 3, 4]`, `c = 5`. Механика такая: интерпретатор сначала резервирует по одному элементу под каждую "обычную", не звёздную цель слева и справа от звезды. Здесь это `a` (первый элемент) и `c` (последний). Всё, что остаётся между ними после этого резервирования, целиком уходит в список, привязанный к цели со звёздочкой (`b`). Именно поэтому звезда может стоять где угодно: остаток вычисляется как "то, что не забрали фиксированные позиции по краям".

</details>

## Частая ошибка

Самая частая и самая незаметная ошибка — попытка создать пустой set через `{}`. Привычка приходит из JS, где `{}` — просто "пустой объект", а для набора уникальных значений там и так пришлось бы явно писать `new Set()`.

В Python `x = {}` молча создаёт **dict**, а не set. Код падает не сразу, а позже и в неожиданном месте. Например, при попытке вызвать `x.add(1)`: у `dict` нет метода `add` (`AttributeError: 'dict' object has no attribute 'add'`).

Ошибка проявляется далеко от места, где был написан `{}`. Трассировка не указывает на реальную причину: тип был выбран неверно ещё при создании переменной.

Вторая типичная ошибка — путать eager и lazy при передаче comprehension или generator в функции, которые проходят коллекцию несколько раз. Возьмём `gen = (t for t in tasks if t["done"])`. Вызов `len(gen)` упадёт с `TypeError: object of type 'generator' has no len()`. А проход по `gen` дважды — сначала для подсчёта, потом для вывода — на второй итерации просто ничего не выведет, без единой ошибки.

Если результат нужно проходить больше одного раза или знать его длину, нужен список `[...]`, а не генератор `(...)`. Генератор оправдан только тогда, когда данные проходятся строго один раз, обычно сразу же и по одному значению за раз.
