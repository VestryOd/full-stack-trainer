# Исключения и контекстные менеджеры

## Теория

**`try`/`except`/`else`/`finally`.** У Python на один блок больше, чем у JS:

```python
try:
    value = risky_call()
except ValueError as e:
    print(f"bad value: {e}")
else:
    print(f"success: {value}")   # выполняется, ТОЛЬКО если try не бросил исключение
finally:
    print("cleanup always runs")  # выполняется ВСЕГДА — было исключение или нет,
                                    # был return внутри try/except или нет
```

`else` — не про "иначе поймали исключение", а про "код, который должен выполниться только при успехе `try`, но не должен считаться частью самого `try`" — так проще отличить "эта строка может бросить то, что я ловлю" от "эта строка использует результат и сама может бросить что-то другое, что я ловить не собирался". `finally` в Python работает так же, как `finally` в JS.

**Иерархия исключений.** Все исключения наследуются от `BaseException`, но пользовательский код почти всегда должен ловить/наследоваться от `Exception` — прямого потомка `BaseException`, который **не** включает `SystemExit`, `KeyboardInterrupt`, `GeneratorExit`. `except Exception:` не перехватит `Ctrl+C` или `sys.exit()` — и это осознанное разделение: слишком широкий `except BaseException:` (или голый `except:`) считается плохой практикой именно потому, что тихо глотает сигналы завершения процесса, которые должны доходить до верха.

```python
try:
    ...
except (ValueError, TypeError) as e:   # несколько типов в одном except — кортеж
    ...
except Exception as e:                  # более общий тип — обязательно ПОСЛЕ частных
    ...
```

Порядок важен: `except` проверяются сверху вниз, и первый подходящий по `isinstance` перехватывает исключение — если написать общий `except Exception:` раньше частного `except ValueError:`, второй блок никогда не сработает (недостижимый код, причём без предупреждения интерпретатора).

**Кастомные исключения.** Наследуются от `Exception` (или более специфичного builtin-класса, где это уместно) и, как и любой класс, могут нести дополнительные данные:

```python
class TaskManError(Exception):
    """Базовый класс для всех доменных ошибок taskman."""


class TaskNotFoundError(TaskManError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id {task_id} not found")
        self.task_id = task_id
```

Базовый класс `TaskManError` даёт единую точку перехвата "любая ошибка нашего домена" (`except TaskManError:`) без необходимости перечислять все конкретные подклассы — то же самое, что часто пытаются эмулировать в JS через `class AppError extends Error {}` и проверку `instanceof AppError`, но в Python это не эмуляция, а прямое использование родного механизма перехвата по иерархии типов.

**Параллель с JS: `throw`/`catch` не типизированы на уровне языка.** В JS можно бросить *что угодно* — `throw "boom"`, `throw 42`, `throw { code: 500 }` — и `catch (e)` ловит это единым блоком без всякой типовой фильтрации; различать типы ошибок внутри `catch` приходится вручную, через `if (e instanceof TypeError)`. В Python `raise` требует объект-наследник `BaseException` — `raise 42` бросает `TypeError: exceptions must derive from BaseException`, это проверяется языком, а не соглашением. А множественные `except SpecificError:` дают диспетчеризацию по типу исключения **на уровне синтаксиса**, а не через ручные `if/instanceof` внутри одного catch-блока.

**Context manager и протокол `__enter__`/`__exit__`.** `with expr as name:` — это не новый языковой примитив "поверх" `try/finally", а явный протокол:

```python
class FileLock:
    def __init__(self, path):
        self._path = path
        self._file = None

    def __enter__(self):
        self._file = open(self._path, "a")
        fcntl.flock(self._file, fcntl.LOCK_EX)   # блокирует, пока файл не освободится
        return self._file

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
        # ничего не возвращаем (None — falsy) => исключение, если было,
        # продолжит распространяться после __exit__

with FileLock("taskman.log") as log_file:
    log_file.write("hello\n")
```

`with` вызывает `__enter__()` и привязывает его результат к `name`; при выходе из блока (нормальном или через исключение) вызывается `__exit__(exc_type, exc_value, traceback)` — **всегда**, ровно как `finally`. Важный нюанс: если `__exit__` возвращает truthy-значение, исключение, произошедшее внутри `with`, **подавляется** (не долетает наружу) — это осознанная возможность протокола, а не побочный эффект; по умолчанию (`return None`/ничего не возвращать) исключение продолжает распространяться после того, как `__exit__` отработал.

Ценность протокола именно в том, что он **переиспользуем**: логика "как правильно захватить и освободить ресурс" пишется один раз в классе, а не копируется как `try/finally` в каждое место, где ресурс нужен. Это прямой аналог `try/finally` в JS по назначению (гарантированная очистка), но с вынесенной наружу, переиспользуемой реализацией самой очистки.

**`contextlib`.** Для простых случаев не обязательно писать целый класс — `@contextmanager` превращает генератор в context manager: код до `yield` — это `__enter__`, `yield` отдаёт значение для `as`, код после `yield` (обычно в `finally`) — это `__exit__`:

```python
from contextlib import contextmanager

@contextmanager
def file_lock(path):
    f = open(path, "a")
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        yield f
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
```

Это тот же `FileLock`, но без явного класса — короче для одноразовых случаев, но менее явно показывает сам протокол. В проекте этой главы мы напишем class-based вариант — ровно чтобы увидеть механику `__enter__`/`__exit__` напрямую, а не спрятанную за генератором.

**JS: `using`/`Symbol.dispose`.** С relatively недавним предложением TC39 "Explicit Resource Management" в JS/TS появился похожий по духу механизм — `using resource = getResource();` (и `await using` для асинхронных ресурсов), опирающийся на `Symbol.dispose`/`Symbol.asyncDispose`. Идея та же: детерминированная, переиспользуемая очистка ресурса при выходе из скоупа. Разница — в основном историческая: `with` в Python существует с середины 2000-х и пронизывает всю стандартную библиотеку (файлы, локи, транзакции БД, сетевые соединения), тогда как `using` в JS/TS — заметно более новая часть языка, ещё не настолько повсеместно принятая в экосистеме библиотек.

### Параллели с JS/TS/Node:

- В JS нет блока `else` у `try` — только `try/catch/finally`.
- JS `catch` ловит вообще всё, без типовой фильтрации на уровне синтаксиса — различать типы ошибок нужно вручную через `instanceof`; в Python `except SpecificError:` — фильтрация по типу встроена в язык.
- В JS можно бросить любое значение (`throw 42`); в Python `raise` требует экземпляр `BaseException`-наследника — это проверяется рантаймом.
- `with`/`__enter__`/`__exit__` ~ новый `using`/`Symbol.dispose` в JS/TS (TC39 Explicit Resource Management) — та же идея, но в Python эта возможность существует на 20 лет дольше и используется гораздо шире.

## Что добавляем в проект

Заменяем сигнальное значение `None` при "задача не найдена" на настоящую иерархию исключений — `TaskManError`/`TaskNotFoundError` — и ловим её в CLI-обработчике через `try/except` вместо ручной проверки `if task is None`. Плюс — `log_command` теперь не только печатает в stderr, но и дописывает строку в файл `taskman.log`, защищённый от одновременной записи из нескольких процессов через собственный context manager `FileLock`, реализующий протокол `__enter__`/`__exit__` поверх файловой блокировки (`fcntl.flock`).

## Практическое задание

1. В `models/errors.py` определите `TaskManError(Exception)` (базовый класс всех доменных ошибок) и `TaskNotFoundError(TaskManError)`, хранящий `task_id` и человекочитаемое сообщение. Ре-экспортируйте оба из `models/__init__.py`.
2. В `storage/memory.py` добавьте `get_task(task_id) -> Task`, которая использует существующий `find_task` (он остаётся как есть, возвращает `Task | None`) и бросает `TaskNotFoundError`, если задача не найдена. Измените `mark_done`, чтобы она использовала `get_task` вместо ручной проверки на `None`, и теперь либо возвращала `Task`, либо пробрасывала `TaskNotFoundError`.
3. В `cli/commands.py` измените `handle_done`: оберните вызов `memory.mark_done(args.id)` в `try/except TaskNotFoundError`, напечатайте понятное сообщение об ошибке в `sys.stderr` вместо проверки `if task is None`.
4. Создайте `logging_utils.py` с классом `FileLock`, реализующим `__enter__`/`__exit__` вокруг `fcntl.flock` (эксклюзивная блокировка на запись), и функцией `append_log(message: str) -> None`, использующей `FileLock` через `with`.
5. Вызывайте `append_log(...)` из `log_command` (в дополнение к существующим `print(..., file=sys.stderr)`), чтобы каждый запуск команды оставлял след в `taskman.log`.

Вопросы на подумать:

- Что произойдёт с блокировкой файла, если код внутри `with FileLock(...) as f:` бросит исключение? Останется ли файл заблокированным навсегда? Почему нет (если `__exit__` написан правильно)?
- Зачем оставлять `find_task` (возвращающую `Task | None`) отдельно от `get_task` (бросающую исключение), если у нас теперь есть кастомное исключение? В каких ситуациях уместнее одна форма, а в каких — другая?

## Разбор решения

Меняются/добавляются только следующие файлы; `models/task.py`, `storage/__init__.py`, `cli/parser.py`, `cli/app.py`, `cli/__init__.py`, `__main__.py` и `pyproject.toml` остаются такими же, как в главе 05.

`src/taskman/models/errors.py` (новый файл):

```python
class TaskManError(Exception):
    """Base class for all taskman domain errors."""


class TaskNotFoundError(TaskManError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id {task_id} not found")
        self.task_id = task_id
```

`src/taskman/models/__init__.py` (обновлён):

```python
from .errors import TaskManError, TaskNotFoundError
from .task import Priority, Task, PRIORITY_CHOICES

__all__ = [
    "Priority",
    "Task",
    "PRIORITY_CHOICES",
    "TaskManError",
    "TaskNotFoundError",
]
```

`src/taskman/storage/memory.py` (обновлён):

```python
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
```

`src/taskman/logging_utils.py` (новый файл):

```python
import fcntl
from pathlib import Path

LOG_PATH = Path("taskman.log")


class FileLock:
    """Exclusive lock over a file, used to serialize writes across processes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file = None

    def __enter__(self):
        self._file = open(self._path, "a")
        fcntl.flock(self._file, fcntl.LOCK_EX)
        return self._file

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()


def append_log(message: str) -> None:
    with FileLock(LOG_PATH) as log_file:
        log_file.write(message + "\n")
```

`src/taskman/cli/commands.py` (обновлён):

```python
import argparse
import functools
import sys

from ..logging_utils import append_log
from ..models import Priority, TaskNotFoundError
from ..storage import memory


def log_command(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        namespace = args[0]
        print(f"[log] running: {namespace.command}", file=sys.stderr)
        append_log(f"running: {namespace.command}")
        result = func(*args, **kwargs)
        print(f"[log] done: {namespace.command}", file=sys.stderr)
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
    else:
        for task in result:
            print(task)


@log_command
def handle_done(args: argparse.Namespace) -> None:
    try:
        task = memory.mark_done(args.id)
    except TaskNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return
    print(f"Marked done: {task}")


COMMAND_HANDLERS = {
    "add": handle_add,
    "list": handle_list,
    "done": handle_done,
}
```

Ключевые решения:

- `get_task` построена поверх `find_task`, а не заменяет её — `find_task` остаётся "мягким" поиском (возвращает `None`, для мест, где отсутствие задачи — нормальный, ожидаемый исход, не ошибка), а `get_task` — "жёстким" (бросает исключение там, где отсутствие задачи — исключительная ситуация, которую вызывающий код обязан обработать или уронить процесс). Оба варианта нужны в реальном коде — выбор одного из них навсегда закрыл бы дорогу другому сценарию использования.
- `TaskNotFoundError` хранит `task_id` как атрибут, а не только текст сообщения — если этот же except-блок понадобится где-то ещё (например, в главе про FastAPI, где `TaskNotFoundError` превратится в HTTP 404), `error.task_id` даёт структурированный доступ к данным об ошибке, а не парсинг текста сообщения.
- `FileLock.__exit__` ничего не возвращает (implicit `None`) — это осознанный выбор: если запись в лог упадёт с исключением, это исключение должно быть видно, а не молча проглочено протоколом блокировки; `__exit__` гарантирует только то, что файл будет разблокирован и закрыт, а не то, что ошибки будут скрыты.
- `append_log` вызывается и до, и после выполнения обёрнутой команды внутри `log_command` — если сама команда упадёт с необработанным исключением, в логе останется только "running", без "done", что само по себе полезная диагностическая информация (команда стартовала, но не завершилась штатно).

## Проверь себя

1. Дан код:
   ```python
   try:
       result = compute()
   except ValueError:
       result = None
   else:
       print("no exception, result is valid")
   finally:
       print("always runs")
   ```
   В каких условиях выполнится строка `print("no exception, result is valid")`, а в каких — нет? Чем это отличается от того, если бы вы просто написали `print(...)` последней строкой внутри `try`?
2. Почему `except Exception:` не перехватывает `KeyboardInterrupt` (`Ctrl+C`), хотя `KeyboardInterrupt` — тоже исключение? Что это говорит об иерархии `BaseException` vs `Exception`?
3. Что произойдёт, если в коде сначала стоит `except Exception as e:`, а следующим блоком — `except ValueError as e:`? Почему второй блок никогда не выполнится, и почему интерпретатор не предупреждает об этом на этапе разбора кода?
4. Опишите своими словами, что именно делает `with expr as name:` "под капотом" — какие два метода вызываются, когда именно, и что произойдёт, если код внутри блока бросит исключение?
5. Если `__exit__` вернёт `True`, что произойдёт с исключением, возникшим внутри `with`-блока? Почему это иногда полезно, а иногда — опасная ловушка?

<details>
<summary>Ответы</summary>

1. `print("no exception, result is valid")` выполнится, только если `try` завершился **без** исключения — то есть `compute()` не бросил `ValueError` (и вообще ничего). Если `compute()` бросил `ValueError`, выполнится `except`-блок, а `else` будет пропущен целиком. Разница с "просто написать `print(...)` последней строкой в `try`" в том, что в этом случае, если сам `print(...)` (или что-то между успешным `compute()` и `print`) бросит исключение того же типа, что ловит `except`, оно будет по ошибке перехвачено этим `except`, хотя логически относится уже не к вычислению, а к последующей обработке результата. `else` явно исключает это смешение: код в `else` гарантированно выполняется после успешного `try`, но исключения из него `except`, стоящий над этим же `try`, уже не ловит.
2. `KeyboardInterrupt` наследуется напрямую от `BaseException`, а не от `Exception` — это осознанное решение дизайна языка: `Exception` предназначен для ошибок, которые прикладной код обычно должен уметь обработать сам (сетевая ошибка, невалидные данные и т.д.), тогда как `BaseException`-только-потомки (`KeyboardInterrupt`, `SystemExit`, `GeneratorExit`) — это сигналы **завершения процесса или генератора**, которые в подавляющем большинстве случаев не должны перехватываться широким `except`, иначе `Ctrl+C` или `sys.exit()` просто "потеряются" внутри случайного `try/except Exception:` где-то в глубине кода.
3. Второй блок (`except ValueError as e:`) действительно никогда не выполнится, потому что `ValueError` — подкласс `Exception`, и любой `ValueError` уже будет перехвачен первым, более общим `except Exception as e:`, до того как интерпретатор дойдёт до проверки второго блока — `except`-блоки проверяются по порядку сверху вниз, и срабатывает первый подходящий. Интерпретатор не предупреждает об этом на этапе разбора кода, потому что теоретически `except Exception:` и `except ValueError:` — это просто два независимых условных блока с точки зрения синтаксиса; статически доказать их взаимную недостижимость в общем случае потребовало бы полноценного анализа типов, которого CPython на этом этапе не делает (в отличие от, например, статического анализатора вроде mypy, который такую ошибку теоретически мог бы поймать, хотя на практике большинство линтеров тоже это не проверяют "из коробки").
4. `with expr as name:` сначала вычисляет `expr`, затем вызывает у результата метод `__enter__()` — то, что он возвращает, привязывается к `name`. Дальше выполняется тело блока `with`. Когда блок завершается — неважно, нормально или через исключение — вызывается `__exit__(exc_type, exc_value, traceback)` того же объекта: если исключения не было, все три аргумента — `None`; если было — туда передаются тип, само исключение и traceback. `__exit__` вызывается **гарантированно**, даже если внутри блока было исключение или `return`/`break`/`continue`, покидающие блок — то есть точно так же надёжно, как `finally`.
5. Если `__exit__` вернёт `True` (любое truthy-значение), исключение, произошедшее внутри `with`-блока, будет **подавлено** — код после `with` продолжит выполняться так, как будто исключения не было вовсе. Это полезно, когда context manager сам знает, как "нормально" обработать определённый класс ошибок (например, context manager для игнорирования конкретного, ожидаемого исключения — так устроен, например, `contextlib.suppress`). Опасность в том, что по умолчанию (когда `__exit__` ничего явно не возвращает, то есть возвращает `None`) исключение продолжает распространяться — если разработчик по невнимательности напишет `return True` "для симметрии" или скопирует чужой код, не поняв, зачем там `True`, он рискует незаметно проглотить реальные ошибки, которые должны были дойти до вызывающего кода.

</details>

## Частая ошибка

Самая частая ошибка при первом знакомстве с исключениями в Python — писать голый `except:` (без указания типа) или `except Exception:` там, где на самом деле нужна конкретная проверка, копируя рефлекс из JS, где единственный `catch (e)` и так ловит всё подряд, и разработчик привык "разбираться с ошибкой внутри catch", а не выбирать нужный тип на уровне синтаксиса. В Python широкий `except:`/`except Exception:` тихо глотает ошибки, которые вообще не должны были случиться в этом месте кода (например, `TypeError` из-за опечатки в имени атрибута), маскируя реальный баг под видом "мы же обработали ошибку" — а в проекте это ещё и мешает росту: если позже появится `TaskAlreadyDoneError` или любая другая новая доменная ошибка, широкий `except Exception:` в `handle_done` перехватит её точно так же, как `TaskNotFoundError`, и напечатает то же самое сообщение об ошибке, которое пользователю не поможет понять, что произошло на самом деле.

Вторая типичная ошибка — не так очевидная, но встречающаяся ровно там, где есть работа с файлами и блокировками: думать, что раз код обёрнут в `with`, дополнительная защита через `try/except` вокруг самого `with`-блока больше не нужна "потому что context manager сам всё обработает". Context manager гарантирует только **очистку ресурса** (файл будет закрыт, лок будет снят) — он не глотает и не обрабатывает исключение автоматически, если явно не написан для этого (как в примере с `__exit__`, ничего не возвращающим). Ошибка внутри `with FileLock(...) as f: f.write(...)` по-прежнему вылетит наружу после того, как `__exit__` снимет блокировку — просто файл при этом гарантированно останется в консистентном, разблокированном состоянии, а не будет висеть залоченным навсегда.
