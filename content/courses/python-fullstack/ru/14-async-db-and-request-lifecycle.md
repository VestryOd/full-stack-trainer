# Request lifecycle: middleware и централизованная обработка ошибок

## Теория

**"Полностью асинхронные эндпоинты" — что здесь на самом деле изменилось.** С главы 12 (aiosqlite) и главы 13 (первые роуты) все три эндпоинта уже были `async def`. Формально пункт "все эндпоинты async" уже выполнен — но важно понимать, ПОЧЕМУ это по-прежнему стоит проговаривать явно: если хоть один обработчик в приложении окажется синхронным и внутри сделает блокирующий вызов (синхронный HTTP-запрос, тяжёлое вычисление, обычный `time.sleep`), он заблокирует единственный поток event loop'а для **всех** остальных запросов, которые в этот момент обслуживаются тем же процессом — ровно то, что разбиралось в главе 12 про кооперативную модель. В CLI это было неважно (один процесс — одна команда), в HTTP-сервере, который держит много запросов "в полёте" одновременно, это критично.

**Async-сессии к БД — концепция, которую этот проект сознательно не берёт себе.** Идиоматичный паттерн для стейтфул ORM (например, SQLAlchemy `AsyncSession`) — открывать **одну** сессию на **весь запрос** через `Depends`-зависимость с `yield`, и переиспользовать её во всех операциях внутри этого запроса, закрывая после того, как ответ отправлен:

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session   # используется во всех местах, где session нужна внутри запроса

@app.post("/orders")
async def create_order(session: AsyncSession = Depends(get_session)):
    ...  # несколько операций над ОДНОЙ session, возможно в одной транзакции
```

Наш storage-слой сознательно **не** переходит на эту модель: каждая функция (`add_task`, `find_task`, `mark_done`, ...) сама открывает и закрывает своё собственное соединение через `db_connection()` (глава 08/12), и ни один из наших трёх эндпоинтов не делает больше одной storage-операции за раз — делить соединение между несколькими вызовами внутри одного запроса здесь просто не с чем. Паттерн "одна сессия на запрос" становится оправданным ровно тогда, когда одному запросу требуется несколько операций с БД, которые обязаны быть частью одной транзакции (например, "списать остаток со склада И создать заказ" — атомарно, вместе или ни то, ни другое) — вот тогда его стоит вводить, а не заранее, "на всякий случай".

**Request/response lifecycle.** Путь запроса через FastAPI/Starlette — "луковичная" модель (та же идея, что у middleware в Koa, а не линейная цепочка `next()` в Express):

```txt
запрос -> [ middleware 1 -> [ middleware 2 -> [ Depends -> route handler ] ] ] -> ответ
          (код "до") (код "до")                              (код "после") (код "после")
```

Каждый middleware оборачивает всё, что внутри него, и видит как запрос на входе, так и **готовый ответ** на выходе — включая ответ, порождённый не самим роутом напрямую, а обработчиком исключения (см. ниже). Если исключение всплывает где угодно внутри — в зависимости (`Depends`), в самом обработчике роута — Starlette ищет зарегистрированный обработчик, соответствующий типу исключения (или его родителю), и, если находит, превращает исключение в обычный HTTP-ответ **до** того, как этот ответ пойдёт обратно через middleware — то есть middleware в норме видит финальный, уже сконвертированный статус-код, а не сырое исключение.

**Middleware.** Функция, оборачивающая `call_next` — вызов, передающий запрос дальше по цепочке и возвращающий ответ:

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    print(f"{request.method} {request.url.path} -> {response.status_code} ({duration*1000:.1f}ms)")
    return response
```

Неочевидный, но реально проверяемый нюанс: если `call_next(request)` бросает исключение, для которого **не** зарегистрирован обработчик, оно продолжает всплывать через саму функцию middleware — и код **после** `call_next` (в примере выше — вычисление `duration` и `print`) просто не выполнится, если `call_next` не обёрнут в `try/except`. Клиент всё равно получит стандартный `500` (это делает более внешний, встроенный слой Starlette), но конкретно ваш middleware пропустит собственную "после"-логику. Если нужно логировать **любой** исход, включая необработанные падения, `call_next` нужно оборачивать явно:

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - start
        print(f"{request.method} {request.url.path} -> unhandled ({duration*1000:.1f}ms)")
        raise
    duration = time.perf_counter() - start
    print(f"{request.method} {request.url.path} -> {response.status_code} ({duration*1000:.1f}ms)")
    return response
```

**Обработка ошибок на уровне приложения — `@app.exception_handler`/`add_exception_handler`.** Вместо того, чтобы в каждом месте, где может вылететь `TaskNotFoundError`, писать свой `try/except`, регистрируется один обработчик на уровне приложения:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

async def task_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskNotFoundError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})

app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

Он сработает для `TaskNotFoundError`, вылетевшей откуда угодно в рамках запроса — из тела роута или из `Depends`-зависимости, которая resolves перед роутом — потому что и то, и другое одинаково часть одного и того же request lifecycle, который Starlette оборачивает в единый обработчик исключений.

### Параллели с JS/TS/Node:

- Middleware в Starlette/FastAPI устроен "луковицей" — как в Koa (`async`-обёртки, каждый уровень видит и запрос, и ответ), а не линейной цепочкой `app.use((req, res, next) => ...)`, как в классическом Express.
- Централизованный обработчик исключений (`add_exception_handler`) ~ Express error-middleware (`(err, req, res, next) => ...`)/Nest.js `@Catch()`-фильтры — идея "одно место конвертации доменных ошибок в HTTP-ответы" универсальна для всех этих фреймворков.
- "Одна сессия на запрос" через `Depends` с `yield` — тот же общий паттерн, что и request-scoped провайдеры в Nest.js (например, request-scoped сервисы с `Scope.REQUEST`).

## Что добавляем в проект

Убираем ручной `try/except TaskNotFoundError` из `get_task_or_404` (глава 13) — вместо него регистрируем один обработчик исключений на уровне приложения (`app.add_exception_handler(TaskNotFoundError, task_not_found_handler)`), который конвертирует `TaskNotFoundError` в `404` для **любого** места, где она может возникнуть, не только для одной конкретной зависимости. Заодно добавляем middleware логирования запросов (`api/middleware.py`) — HTTP-аналог `log_command` из CLI (глава 03), с той же идеей, но другим механизмом, потому что запросы — не функции, которые мы вызываем напрямую, а часть ASGI request/response цикла.

## Практическое задание

1. Создайте `api/exceptions.py` с `task_not_found_handler(request: Request, exc: Exception) -> JSONResponse`, возвращающим `404` с телом `{"detail": str(exc)}`. Подумайте, почему сигнатура принимает `exc: Exception`, а не `exc: TaskNotFoundError`, прежде чем смотреть разбор решения.
2. Зарегистрируйте обработчик через `app.add_exception_handler(TaskNotFoundError, task_not_found_handler)` в `api/app.py`.
3. Упростите `get_task_or_404` в `api/routes.py` — уберите `try/except`, оставьте только `return await db.get_task(task_id)`. Убедитесь, что `PATCH /tasks/999/done` всё равно возвращает `404`, хотя явного перехвата исключения в самой зависимости больше нет.
4. Создайте `api/middleware.py` с middleware, логирующим метод, путь, итоговый статус-код и длительность каждого запроса — с `try/except` вокруг `call_next`, чтобы необработанные исключения тоже попадали в лог.
5. Подключите middleware в `api/app.py` и убедитесь, что лог показывает правильный, уже сконвертированный статус (`404`, а не необработанное исключение) для запроса к несуществующей задаче.

Вопросы на подумать:

- Если убрать `try/except` вокруг `call_next` в middleware, что именно перестанет происходить при необработанном исключении — сам ответ клиенту изменится, или что-то другое?
- Почему обработчик, зарегистрированный на `TaskNotFoundError`, срабатывает и для исключения, брошенного внутри `Depends`-зависимости, а не только внутри тела самого роута?

## Разбор решения

`src/taskman/api/exceptions.py` (новый файл):

```python
from fastapi import Request
from fastapi.responses import JSONResponse

from ..models import TaskNotFoundError


async def task_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskNotFoundError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

`src/taskman/api/middleware.py` (новый файл):

```python
import time
from typing import Awaitable, Callable

from fastapi import Request, Response


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        print(f"[api] {request.method} {request.url.path} -> unhandled ({duration_ms:.1f}ms)")
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    print(f"[api] {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)")
    return response
```

`src/taskman/api/routes.py` (обновлён — `get_task_or_404` упрощён):

```python
from fastapi import APIRouter, Depends

from ..models import Priority, Task
from ..storage import db
from .schemas import TaskCreate, TaskRead

router = APIRouter()


async def get_task_or_404(task_id: int) -> Task:
    return await db.get_task(task_id)


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

`src/taskman/api/app.py` (обновлён):

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..models import TaskNotFoundError
from ..storage import db
from .exceptions import task_not_found_handler
from .middleware import log_requests
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.init_db()
    yield


app = FastAPI(title="taskman", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.middleware("http")(log_requests)
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

Реальный прогон (`uvicorn taskman.api:app`, затем несколько запросов) подтверждает, что middleware видит уже готовый, сконвертированный статус:

```txt
[api] POST /tasks -> 201 (5.8ms)
[api] GET /tasks -> 200 (1.8ms)
[api] PATCH /tasks/1/done -> 200 (3.3ms)
[api] PATCH /tasks/999/done -> 404 (0.9ms)
```

Последняя строка — самая показательная: `get_task_or_404` больше не содержит `try/except`, `TaskNotFoundError` из `db.get_task(999)` летит наружу, её ловит зарегистрированный `task_not_found_handler`, и middleware видит уже финальный `404` — не сырое исключение и не `500`.

Ключевые решения:

- `task_not_found_handler` принимает `exc: Exception`, а не `exc: TaskNotFoundError` — это не ослабление типизации ради удобства, а требование самой сигнатуры `add_exception_handler` в Starlette: `mypy --strict` на попытке типизировать обработчик более узко буквально выдаёт ошибку (`incompatible type`), потому что callback регистрируется в общем реестре обработчиков, статически рассчитанном на `Exception`, а не на конкретный подкласс — вызывающий код (сам Starlette) сам решает, что передать, и типовая система не может статически гарантировать, что придёт именно `TaskNotFoundError`, хотя *в реальности* так и будет (Starlette диспетчеризует по фактическому типу исключения в рантайме). `assert isinstance(exc, TaskNotFoundError)` восстанавливает узкий тип внутри тела функции для тех случаев, когда понадобится, скажем, `exc.task_id`.
- Middleware оборачивает `call_next` в `try/except`, специально чтобы логировать **и** необработанные падения — без этого код после `call_next` просто не выполнился бы при исключении без зарегистрированного обработчика, и в логе появлялись бы только "счастливые" и "аккуратно обработанные" запросы, а не по-настоящему сломанные.
- Async-сессии к БД (общая, request-scoped модель) в проект не добавлены сознательно — ни один из трёх эндпоинтов не делает больше одной storage-операции за вызов, так что делить соединение между несколькими вызовами внутри одного запроса не с чем; вводить этот паттерн сейчас значило бы добавлять абстракцию без реальной необходимости.

## Проверь себя

1. Что именно даёт middleware "луковичная" модель (как в Koa), чего не даёт линейная цепочка `next()` в классическом Express — в контексте того, что происходит с ответом **после** того, как он получен от route handler'а?
2. Если убрать `try/except` вокруг `call_next` в middleware логирования, что конкретно перестанет происходить при необработанном исключении в роуте — изменится ли ответ, который получит клиент?
3. Почему `task_not_found_handler` типизирован как принимающий `exc: Exception`, а не `exc: TaskNotFoundError`, хотя регистрируется он именно для `TaskNotFoundError`? В чём здесь противоречие между "как это используется на практике" и "что может статически гарантировать система типов"?
4. Почему `TaskNotFoundError`, брошенная внутри `get_task_or_404` (Depends-зависимость), перехватывается тем же самым обработчиком исключений, что и такая же ошибка, брошенная прямо в теле роута?
5. Почему этот проект не вводит паттерн "одна сессия на весь запрос" для БД, хотя это стандартная практика для многих реальных FastAPI-приложений?

<details>
<summary>Ответы</summary>

1. В "луковичной" модели каждый middleware — это код, обёртывающий весь остальной pipeline целиком: у него есть код "до" (выполняется, когда запрос идёт внутрь) и код "после" (выполняется, когда ответ уже готов и идёт обратно наружу) — и код "после" видит **готовый, финальный** ответ, каким бы образом он ни был получен (обычный возврат из роута, ответ, порождённый обработчиком исключений, и так далее). Линейная модель `next()` в классическом Express исторически была устроена так, что у большинства middleware нет естественного "после" — `next()` просто передаёт управление дальше, не оборачивая последующий код так, чтобы можно было симметрично что-то сделать после того, как ответ уже готов, без специальных приёмов.
2. Клиент по-прежнему получит стандартный `500 Internal Server Error` — это делает более внешний, встроенный слой Starlette независимо от нашего кода. Изменится другое: код middleware **после** строки с `call_next` (в нашем случае — вычисление длительности и печать лога) просто не выполнится, потому что исключение пролетит прямо через тело функции middleware, не задерживаясь на строке `response = await call_next(request)`. В логе не останется никакой записи об этом запросе вообще — не "ошибка", а полное отсутствие строки.
3. `add_exception_handler` в Starlette регистрирует обработчик в общем реестре, статическая сигнатура которого рассчитана на `Callable[[Request, Exception], ...]` — потому что типовая система не может на этапе проверки кода доказать, что конкретно ЭТОТ обработчик будет вызван только с ЭКЗЕМПЛЯРАМИ `TaskNotFoundError`, а не с чем-то ещё: решение о том, какой обработчик вызвать, принимается динамически, в рантайме, по фактическому типу исключения. На практике Starlette действительно вызовет этот обработчик только для `TaskNotFoundError` (потому что именно так он был зарегистрирован), но статическая типизация не участвует в этой диспетчеризации и не может дать той же гарантии, которую даёт рантайм-логика реестра обработчиков.
4. Потому что и тело роута, и `Depends`-зависимости, resolving перед ним, — часть одного и того же request lifecycle, обёрнутого Starlette в единый механизм обработки исключений. С точки зрения этого механизма неважно, на каком именно шаге обработки запроса вылетело исключение — до вызова функции роута (во время резолва зависимостей) или уже внутри неё — оно в любом случае перехватывается на одном и том же уровне и ищется подходящий зарегистрированный обработчик по типу исключения.
5. Потому что ни один из трёх эндпоинтов проекта не выполняет больше одной storage-операции за один вызов, а значит, ни одному из них не нужно, чтобы несколько операций работали в рамках одной и той же сессии/транзакции — сама причина, по которой паттерн "одна сессия на запрос" существует (гарантировать, что несколько связанных операций видят согласованное состояние БД или откатываются вместе как одно целое), здесь просто не возникает. Вводить его заранее означало бы добавлять инфраструктуру ради инфраструктуры, а не ради решения реальной задачи, стоящей перед проектом прямо сейчас.

</details>

## Частая ошибка

Самая частая ошибка при первом знакомстве с middleware в FastAPI — писать `@app.middleware("http")`-функцию так, будто она гарантированно увидит и залогирует **каждый** запрос, включая полностью сломанные, без единой мысли о `try/except` вокруг `call_next`. Разработчик, привыкший к тому, что логирующий middleware в Express обычно ставится **первым** в цепочке и просто оборачивает `next()` без затей, переносит эту привычку на FastAPI — и обнаруживает (обычно не сразу, а когда реальный прод-инцидент не оставил ни строчки в логах) что необработанные исключения "проскакивают" мимо кода после `call_next`, оставляя логи неполными именно в тот момент, когда они нужнее всего — при настоящем падении, а не при штатной обработке ошибки.

Вторая типичная ошибка — решить, что раз `TaskNotFoundError` теперь ловится централизованно через `add_exception_handler`, то и вообще любую доменную ошибку можно "просто бросать" из глубины кода, и она "как-нибудь" превратится в осмысленный HTTP-ответ сама. Централизация работает только для **зарегистрированных** типов исключений — если в проекте позже появится, скажем, `TaskAlreadyDoneError`, и для неё не будет своего `add_exception_handler`, она полетит наружу как обычное необработанное исключение и превратится в тот же самый общий `500`, что и любая внутренняя ошибка программиста (опечатка, `AttributeError` и так далее) — централизованная обработка ошибок не отменяет необходимости явно регистрировать обработчик для каждого нового вида доменной ошибки, которую вы хотите видеть как осмысленный HTTP-статус, а не как generic `500`.
