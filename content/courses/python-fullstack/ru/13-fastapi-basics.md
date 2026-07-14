# FastAPI: роутинг, Pydantic, Depends

## Теория

**Роутинг.** FastAPI связывает HTTP-метод и путь с функцией через декоратор, а параметры пути/запроса берёт напрямую из **сигнатуры функции**, сопоставляя по имени и типу — без ручного `req.params.taskId`, как в Express:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/tasks/{task_id}")
async def get_one(task_id: int):        # {task_id} из пути -> параметр task_id: int
    ...

@app.get("/tasks")
async def list_all(status: str = "all"):  # ?status=... из query-строки, с дефолтом
    ...
```

По духу это ближе к декораторному роутингу Nest.js (`@Get()`, `@Post()` на методах контроллера), чем к цепочкам `app.get(path, handler)` в чистом Express — только вместо DTO-классов с `@Body()`/`@Param()` FastAPI выводит происхождение параметра (путь, query, тело) из самой сигнатуры и типов.

**Pydantic-модели — валидация, встроенная в фреймворк глубже, чем zod/yup в Express.** `BaseModel` синтаксически похож на dataclass (глава 04) — поля через type hints — но, в отличие от dataclass, Pydantic-модель **валидирует входные данные в рантайме** при создании:

```python
from pydantic import BaseModel

class TaskCreate(BaseModel):
    text: str
    priority: str = "medium"
```

Ключевое отличие от `TypedDict` (глава 10): `TypedDict` — чисто статическая подсказка, ничего не проверяющая в рантайме; Pydantic-модель, наоборот, реально парсит и проверяет данные при каждом `model_validate(...)`, бросая структурированную ошибку валидации, если форма не совпадает — FastAPI ловит эту ошибку сама и превращает в HTTP 422 с точным указанием, какое поле не так.

Сравнение с zod/yup показывает разницу в самом подходе: zod/yup — **schema-first** (пишете отдельную схему `z.object({...})`, TS-тип выводится из неё через `z.infer<>`); Pydantic — **type-hint-first** (пишете класс с типизированными полями, и это объявление и есть схема, и тип одновременно — выводить не из чего, потому что схема и тип это буквально одно и то же). "Глубже интегрирован во фреймворк" означает конкретно: одно и то же Pydantic-объявление используется FastAPI сразу для трёх вещей — валидации тела запроса, сериализации ответа и генерации OpenAPI-схемы — без отдельных, синхронизируемых вручную деклараций для каждой из них.

**Важный, неочевидный нюанс: Pydantic не вызывает ваш `__str__`.** Если поле объявлено как `str`, а источник данных — объект с полем другого типа (например, наш `Priority(IntEnum)` с переопределённым `__str__`, возвращающим `"high"`), интуитивно кажется, что Pydantic вызовет `str(value)` и получит "high". На практике это не так:

```python
class TaskRead(BaseModel):
    priority: str

TaskRead.model_validate(task, from_attributes=True).model_dump_json()
# {"priority": "2", ...} -- строковое представление ЧИСЛОВОГО value, а не "high"!
```

Внутренняя логика приведения типов в Pydantic (реализованная в pydantic-core, отдельно от обычного протокола `__str__`/`__repr__` языка) коэрсит `IntEnum` в `str` через его числовое значение, а не через `str()`. Единственный надёжный способ получить именно "high" — сконструировать Pydantic-модель явно, самим вызвав `str(task.priority)`, а не полагаться на автоматическую коэрсию через `from_attributes`.

**`Depends` — dependency injection, но не такой, как в Nest.js.** В Nest.js DI обычно конструкторный: сервисы регистрируются в модуле и внедряются в конструктор контроллера. В FastAPI DI — на уровне параметров функции-обработчика:

```python
from fastapi import Depends, HTTPException

async def get_task_or_404(task_id: int) -> Task:
    try:
        return await db.get_task(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

@app.patch("/tasks/{task_id}/done")
async def mark_done(task: Task = Depends(get_task_or_404)):
    ...
```

FastAPI сам вызывает `get_task_or_404` (передавая ему `task_id` из пути — та же логика вывода параметров, что и у самих роутов), и результат подставляет в `task`. Зависимость резолвится заново на каждый запрос (если явно не указано кешировать), а не создаётся один раз как синглтон при старте приложения, как это обычно бывает с сервисами в Nest.js.

**Автогенерация OpenAPI/Swagger.** `/docs` (Swagger UI) и `/redoc` появляются автоматически, без единой строчки конфигурации — FastAPI строит OpenAPI-схему прямо из деклараций роутов и Pydantic-моделей. В Express для этого обычно нужен отдельный инструмент (`swagger-jsdoc` и ручные JSDoc-аннотации) или, в Nest.js, `@nestjs/swagger` с явными `@ApiProperty()` на каждом поле DTO — FastAPI не требует этого отдельного слоя ровно потому, что Pydantic-модели уже полностью типизированы и это единственное, что нужно для построения схемы.

### Параллели с JS/TS/Node:

- Декораторный роутинг FastAPI ближе к Nest.js, чем к "голому" Express; параметры выводятся из сигнатуры функции, а не достаются вручную из `req`.
- Pydantic — как zod/yup (рантайм-валидация), но type-hint-first, а не schema-first: класс с аннотациями — это и схема, и тип одновременно.
- `Depends` — DI на уровне параметров функции, резолвится за запрос, а не конструкторный синглтон-DI, как в Nest.js.
- Автогенерация OpenAPI — бесплатная, потому что Pydantic-модели уже полностью типизированы; в Express/Nest.js для той же полноты обычно нужен отдельный слой аннотаций.

## Что добавляем в проект

Оборачиваем `taskman` в REST API поверх **того же самого** storage-слоя — ни `models/`, ни `storage/` не меняются ни строкой, это прямая выплата инвестиций из главы 10 (`TaskStorage`-протокол) и главы 12 (асинхронный storage). Новый пакет `api/` (`schemas.py`, `routes.py`, `app.py`) добавляет три эндпоинта (`POST /tasks`, `GET /tasks`, `PATCH /tasks/{id}/done`), переиспользуя `filter_by_status`/`sort_tasks`/`get_page` из storage-слоя без единого изменения — они как принимали `list[Task]`, так и принимают, вне зависимости от того, кто их вызывает: CLI или HTTP-обработчик.

## Практическое задание

1. Установите `fastapi` и `uvicorn[standard]`, добавьте их в `dependencies` в `pyproject.toml`.
2. Создайте `api/schemas.py`: `TaskCreate` (`text: str`, `priority: str = "medium"` с валидатором, проверяющим, что значение — одно из `PRIORITY_CHOICES`) и `TaskRead` (`id`, `text`, `priority: str`, `done`) с классметодом `from_task(task: Task) -> TaskRead`, явно вызывающим `str(task.priority)`.
3. Создайте `api/routes.py` с `APIRouter`: `POST /tasks` (тело — `TaskCreate`, статус 201), `GET /tasks` (query-параметры `status`/`sort`/`page`/`page_size`, повторяющие CLI-флаги `list`), `PATCH /tasks/{task_id}/done` через `Depends`-зависимость `get_task_or_404`, конвертирующую `TaskNotFoundError` в `HTTPException(404)`.
4. Создайте `api/app.py`: `FastAPI(...)` с `lifespan` — асинхронным генераторным context manager'ом (`@asynccontextmanager`, глава 06/12), вызывающим `await db.init_db()` перед `yield`.
5. Запустите сервер (`uvicorn taskman.api:app --reload`), откройте `/docs`, создайте задачу, получите список, отметьте выполненной через curl или Swagger UI.
6. Прежде чем читать разбор решения — попробуйте создать задачу с пустым текстом (`{"text": "   "}`) через API. Посмотрите на ответ и код статуса. Затем вызовите `GET /tasks` ещё раз. Результат ожидаемый?

## Разбор решения

`pyproject.toml` (добавлены реальные зависимости):

```toml
[project]
name = "taskman"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["aiosqlite>=0.19", "fastapi>=0.110", "uvicorn[standard]>=0.29"]

[project.optional-dependencies]
dev = ["pytest>=8", "mypy>=1.10", "httpx"]

[project.scripts]
taskman = "taskman.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.mypy]
python_version = "3.11"
strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
```

`src/taskman/api/schemas.py` (новый файл):

```python
from pydantic import BaseModel, field_validator

from ..models import PRIORITY_CHOICES, Task


class TaskCreate(BaseModel):
    text: str
    priority: str = "medium"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in PRIORITY_CHOICES:
            raise ValueError(f"priority must be one of {PRIORITY_CHOICES}")
        return value


class TaskRead(BaseModel):
    id: int
    text: str
    priority: str
    done: bool

    @classmethod
    def from_task(cls, task: Task) -> "TaskRead":
        return cls(id=task.id, text=task.text, priority=str(task.priority), done=task.done)
```

`src/taskman/api/routes.py` (новый файл):

```python
from fastapi import APIRouter, Depends, HTTPException

from ..models import Priority, Task, TaskNotFoundError
from ..storage import db
from .schemas import TaskCreate, TaskRead

router = APIRouter()


async def get_task_or_404(task_id: int) -> Task:
    try:
        return await db.get_task(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/tasks", response_model=TaskRead, status_code=201)
async def create_task(payload: TaskCreate) -> TaskRead:
    priority = Priority[payload.priority.upper()]
    task = await db.add_task(payload.text, priority)
    return TaskRead.from_task(task)


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(
    status: str = "all",
    sort: str = "id",
    page: int = 1,
    page_size: int = 5,
) -> list[TaskRead]:
    all_tasks = await db.list_tasks()
    filtered = db.sort_tasks(db.filter_by_status(all_tasks, status), sort)
    page_tasks = db.get_page(filtered, page, page_size)
    return [TaskRead.from_task(task) for task in page_tasks]


@router.patch("/tasks/{task_id}/done", response_model=TaskRead)
async def mark_task_done(task: Task = Depends(get_task_or_404)) -> TaskRead:
    updated = await db.mark_done(task.id)
    return TaskRead.from_task(updated)
```

`src/taskman/api/app.py` (новый файл):

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..storage import db
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.init_db()
    yield


app = FastAPI(title="taskman", version="0.1.0", lifespan=lifespan)
app.include_router(router)
```

`src/taskman/api/__init__.py` (новый файл):

```python
from .app import app

__all__ = ["app"]
```

Теперь — про вопрос из задания 6. Реальный прогон (`uvicorn taskman.api:app`, затем `curl -X POST /tasks -d '{"text": "   "}'`) даёт `500 Internal Server Error` — и это ожидаемо: `Task.__post_init__` (глава 04) бросает `ValueError` при пустом тексте, а ничего в маршруте это не ловит, так что FastAPI отдаёт общий 500. Полноценная, централизованная конвертация доменных исключений в понятные HTTP-ответы — тема следующей главы. Но следующий шаг — `GET /tasks` — на неисправленном коде из главы 08 **тоже** возвращал 500, и это уже не про обработку ошибок, а про настоящий баг:

```python
# ДО исправления — was в storage/sqlite_storage.py с главы 08:
async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    return Task(id=task_id, text=text, priority=priority, done=False)   # <- ВНЕ транзакции!
```

`Task(...)` (и, следовательно, проверка на пустой текст в `__post_init__`) вызывается **после** того, как `async with db_connection()` уже закрылся и закоммитил транзакцию. Строка с пустым текстом реально попадает в базу, `ValueError` вылетает уже потом — и дальше каждый следующий `list_tasks()` (и по CLI, и по API) падает, пытаясь превратить эту "отравленную" строку обратно в `Task`. Баг существовал с главы 08, просто ни один из прежних сценариев не создавал задачу с пустым текстом через реальный вызов.

Исправление — не про обработку ошибок, а про то, **где заканчивается транзакция**:

```python
async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
        assert task_id is not None
        return Task(id=task_id, text=text, priority=priority, done=False)  # теперь ВНУТРИ
```

Перенос `return Task(...)` внутрь блока `async with` — это не косметика: если `Task.__post_init__` бросит `ValueError`, исключение всплывёт **внутри** тела `db_connection`, попадёт в его же `except Exception: await conn.rollback(); raise` (глава 08) — и INSERT откатится вместо того, чтобы закоммититься. `GET /tasks` после этого исправления больше никогда не увидит "отравленную" строку, потому что она никогда не попадёт в базу.

Ключевые решения:

- `TaskRead.from_task` вызывает `str(task.priority)` явно, а не полагается на `model_validate(task, from_attributes=True)` с полем `priority: str` — как показано в теории, автоматическая коэрсия дала бы `"2"`, а не `"high"`.
- `TaskCreate.priority` — обычная строка с ручным `field_validator`, а не поле типа `Priority` — так значение от клиента естественно выглядит как `"high"`/`"medium"`/`"low"`, а не как магическое число, и обходится тот же самый нюанс с коэрсией enum'ов.
- `get_task_or_404` — единственное место, где `TaskNotFoundError` явно превращается в HTTP-ответ; для этой главы этого достаточно, но повторять этот `try/except` в каждом обработчике, которому нужна задача по id, не масштабируется — глава 14 покажет, как убрать повторение через единый обработчик исключений на уровне приложения.
- `filter_by_status`/`sort_tasks`/`get_page` вызываются в `routes.py` буквально так же, как в `cli/commands.py` — ни одна из них не знает и не должна знать, что теперь у неё два вызывающих (CLI и HTTP), а не один.

## Проверь себя

1. Почему `TaskRead.model_validate(task).model_dump_json()` для поля `priority: str` выводит `"2"`, а не `"high"`, если `Priority.__str__` явно возвращает `"high"` для `Priority.HIGH`?
2. Чем Pydantic `BaseModel` отличается от `TypedDict` (глава 10) в терминах того, что происходит при вызове `SomeModel.model_validate(данные, не соответствующие схеме)`?
3. Почему баг с пустым текстом задачи проявился именно при тестировании через API, хотя код `add_task`, в котором была ошибка, не менялся с главы 08?
4. Перенос `return Task(...)` внутрь блока `async with db_connection()` в `add_task` — почему это меняет, коммитится INSERT или откатывается, если конструктор `Task` бросает исключение?
5. Чем `Depends(get_task_or_404)` в FastAPI отличается от конструкторного DI в Nest.js — когда именно вызывается зависимость и как часто она пересоздаётся?

<details>
<summary>Ответы</summary>

1. Потому что коэрсия типов внутри Pydantic (в pydantic-core) не проходит через обычный протокол `str()`/`__str__` языка Python — для `IntEnum`-подобных значений при приведении к строковому полю используется числовое `.value`, а не то, что вернул бы `str(value)` в обычном Python-коде. Пользовательский `__str__` полностью игнорируется этим механизмом коэрсии — единственный способ получить "high" — вызвать `str()` самостоятельно, до передачи значения в Pydantic-модель.
2. `TypedDict` — чисто статическая аннотация: `SomeTypedDict` в рантайме — обычный `dict`, и передать в место, ожидающее `SomeTypedDict`, можно вообще что угодно — ничего не проверится, только mypy отметит несоответствие статически. Pydantic `BaseModel.model_validate(data)` реально выполняет проверку в момент вызова: если данные не соответствуют объявленным полям/типам, бросается `ValidationError` с точным описанием, какое поле и почему не подошло — это происходит на каждый вызов, в рантайме, независимо от того, гонялся ли когда-либо mypy над этим кодом.
3. Потому что раньше (в CLI, главы 08–12) ни один сценарий тестирования не передавал задаче пустой или состоящий из пробелов текст как реальный аргумент — все явные вызовы `add_task`/`python -m taskman add ...` в предыдущих главах использовали содержательный текст. API, принимающий сырой JSON от клиента, — первое место в проекте, где стало действительно легко и естественно попробовать граничный случай (`{"text": "   "}`) без специальной подготовки, и именно это упражнение впервые довело выполнение до строки кода, которая была неправильной с самого начала.
4. Если `Task(...)` вызывается **после** выхода из `async with db_connection()`, блок `async with` уже успешно завершился без исключения — а значит, генератор `db_connection` (глава 08) уже выполнил `await conn.commit()` до того, как исключение из конструктора `Task` вообще произошло. Если же `Task(...)` вызывается **внутри** блока, исключение из `__post_init__` возникает до штатного завершения тела `async with` — генератор `db_connection` перехватывает его в своём `except Exception:`, вызывает `await conn.rollback()` и перевыбрасывает исключение дальше, так и не дойдя до `await conn.commit()`.
5. В Nest.js DI обычно конструкторный: сервис регистрируется в модуле один раз и внедряется в конструктор контроллера как готовый, обычно singleton-объект, живущий, пока живёт приложение. `Depends(get_task_or_404)` в FastAPI — вызов функции-зависимости заново на **каждый HTTP-запрос** (если явно не указано кешировать через `use_cache`), а не однократно созданный объект — сама зависимость получает свои параметры (здесь — `task_id`) той же логикой вывода из сигнатуры, что и параметры самого маршрута, и живёт ровно в рамках одного запроса, а не всего процесса.

</details>

## Частая ошибка

Самая коварная ошибка этой главы — не про синтаксис FastAPI, а про молчаливое доверие к тому, что Pydantic "просто конвертирует" объект в модель так, как это интуитивно ожидается, включая уважение к пользовательским `__str__`/`__repr__`. Разработчик, привыкший к dataclass'ам (глава 04), где `str(obj)` всегда вызывает именно то, что вы написали в `__str__`, естественно ожидает того же от `model_validate(obj, from_attributes=True)` с полем `str` — и получает молчаливо неверные данные (`"2"` вместо `"high"`), без единой ошибки или предупреждения на этапе разработки. Обнаруживается это не при написании кода и не при тестах на "счастливый путь", а только когда кто-то реально посмотрит на фактическое содержимое JSON-ответа — ровно поэтому эта глава была построена вокруг реального запуска сервера и `curl`, а не только чтения кода.

Вторая ошибка — принять "ну, FastAPI умный, он как-нибудь сам разберётся с доменными исключениями" на веру, не проверив это на практике. `TaskNotFoundError`, если её нигде не перехватить явно, не превращается в аккуратный `404` сама по себе — FastAPI отдаёт её как есть, общим `500 Internal Server Error`, точно так же, как поступил бы с любым другим необработанным исключением. `get_task_or_404` в этой главе — осознанно локальное, единичное решение (одна зависимость, один маршрут, который в ней нуждается); в следующей главе выяснится, что для каждого нового маршрута, работающего с конкретной задачей, пришлось бы копировать этот же `try/except`, если не централизовать обработку — и именно поэтому эта тема получает отдельную главу, а не решается "заодно" здесь.
