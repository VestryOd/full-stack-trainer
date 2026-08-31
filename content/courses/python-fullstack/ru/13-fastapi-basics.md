# FastAPI: роутинг, Pydantic, Depends

## Теория

**Роутинг.** FastAPI связывает HTTP-метод и путь с функцией через декоратор. Параметры пути и запроса он берёт напрямую из **сигнатуры функции**, сопоставляя по имени и типу. Ручной разбор вида `req.params.taskId`, как в Express, не нужен:

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

По духу это ближе к декораторному роутингу Nest.js (`@Get()`, `@Post()` на методах контроллера), чем к цепочкам `app.get(path, handler)` в чистом Express. В Nest.js параметры описываются DTO-классами с `@Body()`/`@Param()`. DTO (data transfer object) — это класс, единственная задача которого описать форму одного запроса или ответа. FastAPI же выводит происхождение параметра (путь, query, тело) прямо из сигнатуры и типов.

**Pydantic-модели — валидация, встроенная в фреймворк глубже, чем zod/yup в Express.** `BaseModel` синтаксически похож на dataclass (глава 04): поля объявляются через type hints. Но, в отличие от dataclass, Pydantic-модель **валидирует входные данные в рантайме** при создании:

```python
from pydantic import BaseModel

class TaskCreate(BaseModel):
    text: str
    priority: str = "medium"
```

Ключевое отличие от `TypedDict` (глава 10) — в том, что происходит в рантайме. `TypedDict` — чисто статическая подсказка, она не проверяет ничего. Pydantic-модель реально парсит и проверяет данные при каждом `model_validate(...)` и бросает структурированную ошибку валидации, если форма не совпадает. FastAPI ловит эту ошибку сама и превращает её в HTTP 422 с точным указанием, какое поле не так.

Сравнение с zod/yup показывает разницу в самом подходе:

- zod/yup — **schema-first**. Вы пишете отдельную схему `z.object({...})`, а TS-тип выводится из неё через `z.infer<>`.
- Pydantic — **type-hint-first**. Вы пишете класс с типизированными полями, и это объявление и есть схема, и тип одновременно. Выводить не из чего: схема и тип — буквально одно и то же.

"Глубже интегрирован во фреймворк" означает конкретно одно. FastAPI использует одно и то же Pydantic-объявление сразу для трёх вещей: валидации тела запроса, сериализации ответа и генерации OpenAPI-схемы. Отдельных деклараций, которые надо синхронизировать вручную, нет.

**Важный, неочевидный нюанс: Pydantic не вызывает ваш `__str__`.** Допустим, поле объявлено как `str`, а источник данных — объект, у которого это поле другого типа. Наш `Priority(IntEnum)` — ровно такой случай: он переопределяет `__str__` так, что тот возвращает `"high"`. Интуитивно кажется, что Pydantic вызовет `str(value)` и получит "high". На практике это не так:

```python
class TaskRead(BaseModel):
    priority: str

TaskRead.model_validate(task, from_attributes=True).model_dump_json()
# {"priority": "2", ...} -- строковое представление ЧИСЛОВОГО value, а не "high"!
```

Приведение типов внутри Pydantic реализовано в pydantic-core — отдельно от обычного протокола `__str__`/`__repr__` самого языка. Поэтому `IntEnum` приводится к `str` через своё числовое значение, а не через вызов `str()`. Единственный надёжный способ получить именно "high" — сконструировать Pydantic-модель явно. Вызовите `str(task.priority)` сами, а не полагайтесь на автоматическое приведение через `from_attributes`.

**`Depends` — dependency injection (DI), то есть внедрение зависимостей, но не такое, как в Nest.js.** В Nest.js DI обычно конструкторный: сервисы регистрируются в модуле и внедряются в конструктор контроллера. В FastAPI DI — на уровне параметров функции-обработчика:

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

FastAPI сам вызывает `get_task_or_404` и подставляет результат в `task`. Аргумент `task_id` он передаёт из пути — по той же логике вывода параметров, что и у самих роутов. Зависимость разрешается заново на каждый запрос, если явно не указано кешировать. Она не создаётся один раз как синглтон при старте приложения, как это обычно бывает с сервисами в Nest.js.

**Автогенерация OpenAPI/Swagger.** `/docs` и `/redoc` появляются автоматически, без единой строчки конфигурации. По адресу `/docs` открывается Swagger UI — пользовательский интерфейс, из которого API можно вызывать прямо из браузера. FastAPI строит OpenAPI-схему прямо из деклараций роутов и Pydantic-моделей и не требует для этого отдельного слоя аннотаций.

- В Express для той же полноты обычно нужен отдельный инструмент: `swagger-jsdoc` и ручные JSDoc-аннотации.
- В Nest.js нужен `@nestjs/swagger` с явными `@ApiProperty()` на каждом поле DTO.

FastAPI обходится без этого слоя ровно потому, что Pydantic-модели уже полностью типизированы, а полная типизация — единственное, что нужно для построения схемы.

### Параллели с JS/TS/Node:

- Декораторный роутинг FastAPI ближе к Nest.js, чем к "голому" Express; параметры выводятся из сигнатуры функции, а не достаются вручную из `req`.
- Pydantic — как zod/yup (рантайм-валидация), но type-hint-first, а не schema-first: класс с аннотациями — это и схема, и тип одновременно.
- `Depends` — DI на уровне параметров функции, резолвится за запрос, а не конструкторный синглтон-DI, как в Nest.js.
- Автогенерация OpenAPI — бесплатная, потому что Pydantic-модели уже полностью типизированы; в Express/Nest.js для той же полноты обычно нужен отдельный слой аннотаций.

## Что добавляем в проект

Оборачиваем `taskman` в REST API поверх **того же самого** storage-слоя. REST (representational state transfer) — обычный стиль HTTP-API: путь называет ресурс, а метод — действие над ним. Ни `models/`, ни `storage/` не меняются ни строкой. Это прямая выплата инвестиций из главы 10 (`TaskStorage`-протокол) и главы 12 (асинхронный storage).

Новый пакет `api/` (`schemas.py`, `routes.py`, `app.py`) добавляет три эндпоинта: `POST /tasks`, `GET /tasks` и `PATCH /tasks/{id}/done`. Он переиспользует `filter_by_status`, `sort_tasks` и `get_page` из storage-слоя без единого изменения.

Они как принимали `list[Task]`, так и принимают, вне зависимости от того, кто их вызывает: CLI (command-line interface, интерфейс командной строки) или HTTP-обработчик.

## Практическое задание

1. Установите `fastapi` и `uvicorn[standard]`, добавьте их в `dependencies` в `pyproject.toml`.
2. Создайте `api/schemas.py` с двумя моделями. `TaskCreate` — это `text: str` и `priority: str = "medium"` плюс валидатор, проверяющий, что значение одно из `PRIORITY_CHOICES`. `TaskRead` — это `id`, `text`, `priority: str`, `done` плюс классметод `from_task(task: Task) -> TaskRead`, явно вызывающий `str(task.priority)`.
3. Создайте `api/routes.py` с `APIRouter` и тремя маршрутами. `POST /tasks` принимает тело `TaskCreate` и возвращает статус 201. `GET /tasks` принимает query-параметры `status`/`sort`/`page`/`page_size`, повторяющие CLI-флаги `list`. `PATCH /tasks/{task_id}/done` идёт через `Depends`-зависимость `get_task_or_404`, конвертирующую `TaskNotFoundError` в `HTTPException(404)`.
4. Создайте `api/app.py`: `FastAPI(...)` с `lifespan` — асинхронным генераторным контекстным менеджером (`@asynccontextmanager`, глава 06/12), вызывающим `await db.init_db()` перед `yield`.
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

Теперь — про вопрос из задания 6. Запустите `uvicorn taskman.api:app`, затем `curl -X POST /tasks -d '{"text": "   "}'`. Реальный прогон даёт `500 Internal Server Error`, и это ожидаемо.

`Task.__post_init__` (глава 04) бросает `ValueError` при пустом тексте, а в маршруте это никто не ловит, так что FastAPI отдаёт общий 500. Полноценная, централизованная конвертация доменных исключений в понятные HTTP-ответы — тема следующей главы.

Но следующий шаг, `GET /tasks`, на неисправленном коде из главы 08 **тоже** возвращал 500. И это уже не про обработку ошибок, а про настоящий баг:

```python
# ДО исправления — так было в storage/sqlite_storage.py с главы 08:
async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    # <- выполняется ВНЕ транзакции, которая уже закоммичена:
    return Task(id=task_id, text=text, priority=priority, done=False)
```

`Task(...)` — а значит, и проверка на пустой текст в `__post_init__` — вызывается **после** того, как `async with db_connection()` уже закрылся и закоммитил транзакцию. Строка с пустым текстом реально попадает в базу, а `ValueError` вылетает уже потом. Дальше каждый следующий `list_tasks()` падает, пытаясь превратить эту "отравленную" строку обратно в `Task`, — и по CLI, и по API.

Баг существовал с главы 08. Просто ни один из прежних сценариев не создавал задачу с пустым текстом через реальный вызов.

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

Перенос `return Task(...)` внутрь блока `async with` — это не косметика. Если `Task.__post_init__` бросит `ValueError`, исключение всплывёт **внутри** тела `db_connection`. Там оно попадёт в его же `except Exception: await conn.rollback(); raise` (глава 08), и INSERT откатится вместо того, чтобы закоммититься.

`GET /tasks` после этого исправления больше никогда не увидит "отравленную" строку, потому что она никогда не попадёт в базу.

Ключевые решения:

- `TaskRead.from_task` вызывает `str(task.priority)` явно. Он не полагается на `model_validate(task, from_attributes=True)` с полем `priority: str`: как показано в теории, автоматическое приведение типов дало бы `"2"`, а не `"high"`.
- `TaskCreate.priority` — обычная строка с ручным `field_validator`, а не поле типа `Priority`. Так значение от клиента естественно выглядит как `"high"`/`"medium"`/`"low"`, а не как магическое число, и обходится тот же нюанс с приведением перечислений (enum).
- `get_task_or_404` — единственное место, где `TaskNotFoundError` явно превращается в HTTP-ответ. Для этой главы этого достаточно. Но повторять этот `try/except` в каждом обработчике, которому нужна задача по id, не масштабируется. Глава 14 покажет, как убрать повторение через единый обработчик исключений на уровне приложения.
- `filter_by_status`, `sort_tasks` и `get_page` вызываются в `routes.py` буквально так же, как в `cli/commands.py`. Ни одна из них не знает и не должна знать, что теперь у неё два вызывающих, а не один: CLI и HTTP.

## Проверь себя

1. Почему `TaskRead.model_validate(task).model_dump_json()` для поля `priority: str` выводит `"2"`, а не `"high"`, если `Priority.__str__` явно возвращает `"high"` для `Priority.HIGH`?
2. Чем Pydantic `BaseModel` отличается от `TypedDict` (глава 10)? Сравните, что происходит при вызове `SomeModel.model_validate(...)` на данных, не соответствующих схеме.
3. Почему баг с пустым текстом задачи проявился именно при тестировании через API, хотя код `add_task`, в котором была ошибка, не менялся с главы 08?
4. В `add_task` перенесите `return Task(...)` внутрь блока `async with db_connection()`. Почему это меняет, коммитится INSERT или откатывается, если конструктор `Task` бросает исключение?
5. Чем `Depends(get_task_or_404)` в FastAPI отличается от конструкторного DI в Nest.js — когда именно вызывается зависимость и как часто она пересоздаётся?

<details>
<summary>Ответы</summary>

1. Потому что приведение типов внутри Pydantic (в pydantic-core) не проходит через обычный протокол `str()`/`__str__` языка Python. Для `IntEnum`-подобных значений при приведении к строковому полю используется числовое `.value`, а не то, что вернул бы `str(value)` в обычном Python-коде. Пользовательский `__str__` полностью игнорируется этим механизмом. Единственный способ получить "high" — вызвать `str()` самостоятельно, до передачи значения в Pydantic-модель.
2. `TypedDict` — чисто статическая аннотация. В рантайме `SomeTypedDict` — обычный `dict`, и передать в место, ожидающее `SomeTypedDict`, можно вообще что угодно. Ничего не проверится, только mypy отметит несоответствие статически. Pydantic `BaseModel.model_validate(data)` реально выполняет проверку в момент вызова. Если данные не соответствуют объявленным полям и типам, бросается `ValidationError` с точным описанием, какое поле и почему не подошло. Это происходит на каждый вызов, в рантайме, независимо от того, гонялся ли когда-либо mypy над этим кодом.
3. Потому что раньше, в CLI, главы 08–12, ни один сценарий тестирования не передавал задаче пустой или состоящий из пробелов текст как реальный аргумент. Все явные вызовы `add_task`/`python -m taskman add ...` в предыдущих главах использовали содержательный текст. API принимает сырой JSON от клиента. Это первое место в проекте, где стало легко и естественно попробовать граничный случай (`{"text": "   "}`) без специальной подготовки. Именно оно впервые довело выполнение до строки кода, которая была неправильной с самого начала.
4. Если `Task(...)` вызывается **после** выхода из `async with db_connection()`, блок уже успешно завершился без исключения. Значит, генератор `db_connection` (глава 08) уже выполнил `await conn.commit()` до того, как исключение из конструктора `Task` вообще произошло. Если же `Task(...)` вызывается **внутри** блока, исключение из `__post_init__` возникает до штатного завершения тела `async with`. Генератор `db_connection` перехватывает его в своём `except Exception:`, вызывает `await conn.rollback()` и перевыбрасывает дальше, так и не дойдя до `await conn.commit()`.
5. В Nest.js DI обычно конструкторный. Сервис регистрируется в модуле один раз и внедряется в конструктор контроллера как готовый, обычно singleton-объект, живущий, пока живёт приложение. `Depends(get_task_or_404)` в FastAPI — это вызов функции-зависимости заново на **каждый HTTP-запрос**, если явно не указано кешировать через `use_cache`. Сама зависимость получает свои параметры (здесь — `task_id`) той же логикой вывода из сигнатуры, что и параметры самого маршрута. Живёт она ровно в рамках одного запроса, а не всего процесса.

</details>

## Частая ошибка

Самая коварная ошибка этой главы — не про синтаксис FastAPI. Она про молчаливое доверие к тому, что Pydantic "просто конвертирует" объект в модель так, как это интуитивно ожидается, включая уважение к пользовательским `__str__`/`__repr__`.

Разработчик, привыкший к классам `dataclass` (глава 04), знает, что `str(obj)` всегда вызывает именно то, что вы написали в `__str__`. Того же он естественно ожидает от `model_validate(obj, from_attributes=True)` с полем `str`. И получает молчаливо неверные данные: `"2"` вместо `"high"`, без единой ошибки или предупреждения на этапе разработки.

Обнаруживается это не при написании кода и не при тестах на "счастливый путь". Проявляется это только тогда, когда кто-то реально посмотрит на фактическое содержимое JSON-ответа. Ровно поэтому эта глава была построена вокруг реального запуска сервера и `curl`, а не только чтения кода.

Вторая ошибка — принять "ну, FastAPI умный, он как-нибудь сам разберётся с доменными исключениями" на веру, не проверив это на практике. Если `TaskNotFoundError` нигде не перехватить явно, она не превращается в аккуратный `404` сама по себе. FastAPI отдаёт её как есть, общим `500 Internal Server Error`, точно так же, как поступил бы с любым другим необработанным исключением.

`get_task_or_404` в этой главе — осознанно локальное, единичное решение: одна зависимость, один маршрут, который в ней нуждается. В следующей главе выяснится, что для каждого нового маршрута, работающего с конкретной задачей, пришлось бы копировать этот же `try/except`, если не централизовать обработку. Именно поэтому тема получает отдельную главу, а не решается здесь заодно.
