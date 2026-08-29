# Request lifecycle: middleware and centralized error handling

## Theory

**"Fully async endpoints" — what's actually changed here.** One synchronous handler is enough to stall the whole server. A blocking call inside a handler — a synchronous HTTP request, a heavy computation, a plain `time.sleep` — holds the event loop's single thread. **Every** other request this process is serving right now waits for it. That is the cooperative model from chapter 12, seen from the server side.

Our three endpoints have been `async def` since chapter 12 (aiosqlite) and chapter 13 (the first routes), so that box is already ticked. It is worth naming anyway, because nothing in FastAPI stops you from adding a synchronous handler later. In the CLI (command-line interface) this did not matter: one process, one command. In an HTTP server juggling many requests "in flight" at once, it is critical.

**Async database sessions — a concept this project deliberately doesn't adopt.** A stateful ORM (object-relational mapper) such as SQLAlchemy, with its `AsyncSession`, has an idiomatic pattern here. You open **one** session for the **entire request** through a `Depends` dependency with `yield`. You reuse it across every operation inside that request, and close it once the response has been sent:

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session   # used everywhere the request needs a session

@app.post("/orders")
async def create_order(session: AsyncSession = Depends(get_session)):
    ...  # several operations against the SAME session, possibly one transaction
```

Our storage layer deliberately does **not** move to this model. Every function (`add_task`, `find_task`, `mark_done`, ...) opens and closes its own connection via `db_connection()` (chapters 08/12). None of our three endpoints does more than one storage operation at a time. There is simply nothing to share a connection across within a single request here.

The "one session per request" pattern is worth adopting in exactly one case. That case is a single request needing several database operations that must all be part of one transaction. "Deduct stock AND create an order" — atomically, both or neither — is the classic example. That is the point to introduce the pattern, not preemptively, "just in case."

**Request/response lifecycle.** A request's path through FastAPI/Starlette is an "onion" model (the same idea as Koa's middleware, not Express's linear `next()` chain):

```txt
request
  --> middleware 1: "before" code
      --> middleware 2: "before" code
          --> Depends --> route handler  (builds the response)
      <-- middleware 2: "after" code
  <-- middleware 1: "after" code
response
```

Every middleware wraps everything inside it, and sees both the incoming request and the **finished response** on the way out. That includes a response produced not by the route directly, but by an exception handler (see below).

Suppose an exception surfaces anywhere inside — in a dependency (`Depends`), or in the route handler itself. Starlette looks for a registered handler matching the exception's type, or a parent class. If it finds one, the exception becomes an ordinary HTTP response **before** that response travels back out through the middleware. So middleware normally sees the final, already-converted status code, not a raw exception.

**Middleware.** A function wrapping `call_next` — a call that passes the request further down the chain and returns the response:

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    print(
        f"{request.method} {request.url.path}"
        f" -> {response.status_code} ({duration*1000:.1f}ms)"
    )
    return response
```

A non-obvious, but genuinely testable nuance. If `call_next(request)` raises an exception with **no** registered handler, it keeps propagating right through the middleware function itself. The code **after** `call_next` — in the example above, computing `duration` and printing — simply never runs, unless `call_next` is wrapped in a `try/except`.

The client still gets a standard `500`, because a more outer, built-in Starlette layer produces it. But your own middleware skips its own "after" logic. If you need to log **every** outcome, including unhandled crashes, wrap `call_next` explicitly:

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
    print(
        f"{request.method} {request.url.path}"
        f" -> {response.status_code} ({duration*1000:.1f}ms)"
    )
    return response
```

**Application-level error handling — `@app.exception_handler`/`add_exception_handler`.** Instead of a `try/except` at every place `TaskNotFoundError` might be raised, register one handler at the application level:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

async def task_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskNotFoundError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})

app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

This fires for `TaskNotFoundError` raised from anywhere within a request: the route body, or a `Depends` dependency that resolves before the route. Both are equally part of the same request lifecycle, and Starlette wraps that whole lifecycle in a single exception-handling mechanism.

### Parallels with JS/TS/Node:

- Middleware in Starlette/FastAPI is "onion"-shaped, like Koa: `async` wrappers, where each layer sees both the request and the response. Classic Express instead uses a linear chain of `app.use((req, res, next) => ...)` calls.
- A centralized exception handler (`add_exception_handler`) matches Express error middleware (`(err, req, res, next) => ...`) and the `@Catch()` filters of Nest.js. The idea "one place to convert domain errors into HTTP responses" is universal across these frameworks.
- "One session per request" via `Depends` with `yield` is the same general pattern as request-scoped providers in Nest.js. An example there is a request-scoped service with `Scope.REQUEST`.

## What we're adding to the project

We're removing the manual `try/except TaskNotFoundError` from `get_task_or_404` (chapter 13). One application-level exception handler replaces it: `app.add_exception_handler(TaskNotFoundError, task_not_found_handler)`. It converts `TaskNotFoundError` into a `404` from **anywhere** it might occur, not just from one specific dependency.

Alongside that, we add a request-logging middleware (`api/middleware.py`). It is the HTTP counterpart of the CLI's `log_command` (chapter 03) — same idea, different mechanism. Requests aren't functions we call directly; they are part of the ASGI (asynchronous server gateway interface) request/response cycle.

## Practical exercise

1. Create `api/exceptions.py` with `task_not_found_handler(request: Request, exc: Exception) -> JSONResponse`, returning `404` with a `{"detail": str(exc)}` body. Think about why the signature takes `exc: Exception`, not `exc: TaskNotFoundError`, before looking at the worked solution.
2. Register the handler via `app.add_exception_handler(TaskNotFoundError, task_not_found_handler)` in `api/app.py`.
3. Simplify `get_task_or_404` in `api/routes.py` — drop the `try/except`, leave just `return await db.get_task(task_id)`. Confirm that `PATCH /tasks/999/done` still returns `404`, even though there's no explicit exception catch left in the dependency itself.
4. Create `api/middleware.py` with middleware that logs the method, path, final status code and duration of every request. Wrap `call_next` in a `try/except`, so unhandled exceptions get logged too.
5. Wire the middleware into `api/app.py`. Confirm the log shows the correct, already-converted status for a request to a missing task: `404`, not an unhandled exception.

Things to think through:

- Remove the `try/except` around `call_next` in the middleware. What exactly stops happening for an unhandled exception? Does the client's actual response change, or does something else?
- A handler registered for `TaskNotFoundError` also fires for an exception raised inside a `Depends` dependency, not only inside the route body. Why?

## Worked solution

`src/taskman/api/exceptions.py` (new file):

```python
from fastapi import Request
from fastapi.responses import JSONResponse

from ..models import TaskNotFoundError


async def task_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskNotFoundError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

`src/taskman/api/middleware.py` (new file):

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
        print(
            f"[api] {request.method} {request.url.path}"
            f" -> unhandled ({duration_ms:.1f}ms)"
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    print(
        f"[api] {request.method} {request.url.path}"
        f" -> {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response
```

`src/taskman/api/routes.py` (updated — `get_task_or_404` simplified):

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

`src/taskman/api/app.py` (updated):

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

A real run (`uvicorn taskman.api:app`, followed by a few requests) confirms the middleware sees the already-converted final status:

```txt
[api] POST /tasks -> 201 (5.8ms)
[api] GET /tasks -> 200 (1.8ms)
[api] PATCH /tasks/1/done -> 200 (3.3ms)
[api] PATCH /tasks/999/done -> 404 (0.9ms)
```

The last line is the most telling one. There is no `try/except` left in `get_task_or_404`, so `TaskNotFoundError` from `db.get_task(999)` propagates outward. The registered `task_not_found_handler` catches it, and the middleware sees the final `404` — not a raw exception and not a `500`.

Key decisions:

- `task_not_found_handler` takes `exc: Exception`, not `exc: TaskNotFoundError`. This is not loosening the typing for convenience. It is a requirement of the `add_exception_handler` signature in Starlette: typing the handler more narrowly makes `mypy --strict` fail outright, with `incompatible type`. The callback is registered in a general handler registry statically typed for `Exception`, not for a specific subclass. Starlette itself is the caller and decides what gets passed. The type system cannot statically guarantee the argument will only ever be a `TaskNotFoundError`. *In practice* it will be, because Starlette dispatches by the exception's actual runtime type. Inside the function body, `assert isinstance(exc, TaskNotFoundError)` restores the narrower type for the cases where you need, say, `exc.task_id`.
- The middleware wraps `call_next` in `try/except` specifically to log unhandled failures too. Without it, the code after `call_next` would not run for an exception with no registered handler. The log would only ever show "happy" and "neatly handled" requests, never genuinely broken ones.
- Async database sessions, the general request-scoped model, were deliberately not added to the project. None of the three endpoints does more than one storage operation per call. There is nothing to share a connection across within a single request. Introducing that pattern now would mean adding an abstraction with no real need behind it.

## Check yourself

1. What does the "onion" middleware model, like Koa's, give you that a linear `next()` chain in classic Express does not? Look specifically at what happens to the response **after** it comes back from the route handler.
2. Remove the `try/except` around `call_next` in the logging middleware. What exactly stops happening for an unhandled exception in a route, and does the response the client receives change?
3. Why is `task_not_found_handler` typed to accept `exc: Exception`, not `exc: TaskNotFoundError`, even though it's registered specifically for `TaskNotFoundError`? What's the tension here between "how it's actually used" and "what the type system can statically guarantee"?
4. `TaskNotFoundError` raised inside `get_task_or_404` (a `Depends` dependency) is caught by the same exception handler as the same error raised directly in a route's body. Why?
5. Why doesn't this project adopt the "one session per request" pattern for the database, even though that's standard practice in many real FastAPI applications?

<details>
<summary>Answers</summary>

1. In the onion model, every middleware is code wrapping the *entire* rest of the pipeline. It has "before" code, which runs as the request travels inward, and "after" code, which runs once the response is ready and travels back outward. The "after" code sees the **finished, final** response, however it was produced. That could be an ordinary return from a route, or a response produced by an exception handler. The linear `next()` model in classic Express historically didn't give most middleware a natural "after" at all. `next()` just hands control onward. It does not wrap the following code in a way that lets you symmetrically act once the response is already built, without special tricks.
2. The client still gets a standard `500 Internal Server Error`, because a more outer, built-in Starlette layer produces that regardless of our own code. What changes is that the middleware code **after** the `call_next` line — in our case, computing the duration and printing the log — simply never runs. The exception flies straight through the middleware function's body without pausing at `response = await call_next(request)`. No log entry for that request survives at all: not an "error" entry, a complete absence of one.
3. `add_exception_handler` in Starlette registers the handler in a general registry. That registry's static signature is `Callable[[Request, Exception], ...]`. The type system cannot prove, at check time, that this specific handler will only ever be called with instances of `TaskNotFoundError`. The decision of which handler to call is made dynamically, at runtime, from the exception's actual type. In practice Starlette really will only call this handler for `TaskNotFoundError`, since that is exactly how it was registered. But static typing has no part in that dispatch, and cannot offer the same guarantee the runtime handler registry provides.
4. Because both the route body and the `Depends` dependencies resolving before it are part of the same request lifecycle. Starlette wraps that lifecycle in a single exception-handling mechanism. From that mechanism's point of view, it does not matter which step of request processing the exception came from. Whether it came before the route function was even called, while resolving dependencies, or from inside the route, it is caught at the same level. A matching registered handler is then looked up by the exception's type.
5. Because none of the project's three endpoints performs more than one storage operation per call. None of them needs several operations to share the same session or transaction. The "one session per request" pattern exists to guarantee that several related operations see consistent database state, or roll back together as one unit. That need simply does not arise here. Introducing it ahead of time would mean adding infrastructure for its own sake, rather than to solve a problem the project actually has right now.

</details>

## Common mistake

The most common mistake on first meeting FastAPI middleware is writing an `@app.middleware("http")` function with no `try/except` around `call_next`. The assumption is that it is guaranteed to see and log **every** request, including completely broken ones.

In Express, a logging middleware is typically placed **first** in the chain and simply wraps `next()`. A developer carries that habit over to FastAPI.

The discovery comes later, usually when a real production incident leaves not a single log line behind: unhandled exceptions slip past the code after `call_next`. The logs are then incomplete at exactly the moment they matter most — during a genuine crash, not during ordinary, well-handled error flow.

The second common mistake starts from a true premise. `TaskNotFoundError` is now caught centrally via `add_exception_handler`. The wrong conclusion is that any domain error can be "thrown" from deep in the code and will "somehow" turn into a meaningful HTTP response.

Centralization only works for **registered** exception types. Suppose the project later adds `TaskAlreadyDoneError` and there is no `add_exception_handler` for it. It flies out as an ordinary unhandled exception and turns into the same generic `500` as any internal programmer error — a typo, an `AttributeError`.

Centralized error handling does not remove the need to register a handler explicitly. Every new kind of domain error you want to surface as a meaningful HTTP status, rather than a generic `500`, needs its own registration.
