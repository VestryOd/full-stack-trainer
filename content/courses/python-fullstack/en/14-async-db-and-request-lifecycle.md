# Request lifecycle: middleware and centralized error handling

## Theory

**"Fully async endpoints" — what's actually changed here.** Since chapter 12 (aiosqlite) and chapter 13 (the first routes), all three endpoints were already `async def`. Technically, the "all endpoints async" box is already checked — but it's worth stating explicitly WHY that's still worth saying out loud: if even one handler in the app turned out to be synchronous and did a blocking call inside (a synchronous HTTP request, a heavy computation, a plain `time.sleep`), it would block the event loop's single thread for **every** other request the same process happens to be serving at that moment — exactly the cooperative model covered in chapter 12. In the CLI this didn't matter (one process, one command); in an HTTP server juggling many requests "in flight" at once, it's critical.

**Async DB sessions — a concept this project deliberately doesn't adopt.** The idiomatic pattern for a stateful ORM (SQLAlchemy's `AsyncSession`, for instance) is to open **one** session for the **entire request** via a `Depends` dependency with `yield`, reusing it across every operation inside that request, and closing it once the response has been sent:

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session   # used everywhere the request needs a session

@app.post("/orders")
async def create_order(session: AsyncSession = Depends(get_session)):
    ...  # several operations against the SAME session, possibly one transaction
```

Our storage layer deliberately does **not** move to this model: every function (`add_task`, `find_task`, `mark_done`, ...) opens and closes its own connection via `db_connection()` (chapters 08/12), and none of our three endpoints does more than one storage operation at a time — there's simply nothing to share a connection across within a single request here. The "one session per request" pattern earns its keep exactly when a single request needs several database operations that must be part of one transaction (say, "deduct stock AND create an order" — atomically, both or neither) — that's the point to introduce it, not preemptively, "just in case."

**Request/response lifecycle.** A request's path through FastAPI/Starlette is an "onion" model (the same idea as Koa's middleware, not Express's linear `next()` chain):

```txt
request -> [ middleware 1 -> [ middleware 2 -> [ Depends -> route handler ] ] ] -> response
           ("before" code) ("before" code)                     ("after" code) ("after" code)
```

Every middleware wraps everything inside it, and sees both the incoming request and the **finished response** on the way out — including a response produced not by the route directly, but by an exception handler (see below). If an exception surfaces anywhere inside — in a dependency (`Depends`), in the route handler itself — Starlette looks for a registered handler matching the exception's type (or a parent class), and if it finds one, turns the exception into an ordinary HTTP response **before** that response travels back out through the middleware — meaning middleware normally sees the final, already-converted status code, not a raw exception.

**Middleware.** A function wrapping `call_next` — a call that passes the request further down the chain and returns the response:

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    print(f"{request.method} {request.url.path} -> {response.status_code} ({duration*1000:.1f}ms)")
    return response
```

A non-obvious, but genuinely testable nuance: if `call_next(request)` raises an exception with **no** registered handler, it keeps propagating right through the middleware function itself — and the code **after** `call_next` (in the example above, computing `duration` and printing) simply never runs, unless `call_next` is wrapped in a `try/except`. The client still gets a standard `500` (a more outer, built-in Starlette layer does that), but your own middleware specifically skips its own "after" logic. If you need to log **every** outcome, including unhandled crashes, `call_next` has to be wrapped explicitly:

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

**Application-level error handling — `@app.exception_handler`/`add_exception_handler`.** Instead of a `try/except` at every place `TaskNotFoundError` might be raised, register one handler at the application level:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

async def task_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskNotFoundError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})

app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

This fires for `TaskNotFoundError` raised from anywhere within a request — the route body, or a `Depends` dependency that resolves before the route — because both are equally part of the same request lifecycle, which Starlette wraps in a single exception-handling mechanism.

### Parallels with JS/TS/Node:

- Middleware in Starlette/FastAPI is "onion"-shaped, like Koa (`async` wrappers, each layer sees both the request and the response), not a linear chain of `app.use((req, res, next) => ...)` calls like classic Express.
- A centralized exception handler (`add_exception_handler`) ~ Express error middleware (`(err, req, res, next) => ...`)/Nest.js's `@Catch()` filters — the idea "one place to convert domain errors into HTTP responses" is universal across these frameworks.
- "One session per request" via `Depends` with `yield` is the same general pattern as request-scoped providers in Nest.js (request-scoped services with `Scope.REQUEST`, for instance).

## What we're adding to the project

We're removing the manual `try/except TaskNotFoundError` from `get_task_or_404` (chapter 13) — replacing it with one application-level exception handler (`app.add_exception_handler(TaskNotFoundError, task_not_found_handler)`) that converts `TaskNotFoundError` into a `404` from **anywhere** it might occur, not just from one specific dependency. Alongside that, we add a request-logging middleware (`api/middleware.py`) — the HTTP counterpart of the CLI's `log_command` (chapter 03), same idea, different mechanism, because requests aren't functions we call directly — they're part of the ASGI request/response cycle.

## Practical exercise

1. Create `api/exceptions.py` with `task_not_found_handler(request: Request, exc: Exception) -> JSONResponse`, returning `404` with a `{"detail": str(exc)}` body. Think about why the signature takes `exc: Exception`, not `exc: TaskNotFoundError`, before looking at the worked solution.
2. Register the handler via `app.add_exception_handler(TaskNotFoundError, task_not_found_handler)` in `api/app.py`.
3. Simplify `get_task_or_404` in `api/routes.py` — drop the `try/except`, leave just `return await db.get_task(task_id)`. Confirm that `PATCH /tasks/999/done` still returns `404`, even though there's no explicit exception catch left in the dependency itself.
4. Create `api/middleware.py` with middleware that logs the method, path, final status code, and duration of every request — with a `try/except` around `call_next`, so unhandled exceptions get logged too.
5. Wire the middleware into `api/app.py` and confirm the log shows the correct, already-converted status (`404`, not an unhandled exception) for a request to a missing task.

Things to think through:

- If you remove the `try/except` around `call_next` in the middleware, what exactly stops happening for an unhandled exception — does the client's actual response change, or does something else?
- Why does a handler registered for `TaskNotFoundError` fire for an exception raised inside a `Depends` dependency, and not only for one raised inside the route body itself?

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
        print(f"[api] {request.method} {request.url.path} -> unhandled ({duration_ms:.1f}ms)")
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    print(f"[api] {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)")
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

The last line is the most telling one: `get_task_or_404` no longer contains a `try/except`, `TaskNotFoundError` from `db.get_task(999)` propagates outward, the registered `task_not_found_handler` catches it, and the middleware sees the final `404` — not a raw exception and not a `500`.

Key decisions:

- `task_not_found_handler` takes `exc: Exception`, not `exc: TaskNotFoundError` — this isn't loosening the typing for convenience, it's a requirement of `add_exception_handler`'s own signature in Starlette: trying to type the handler more narrowly makes `mypy --strict` fail outright (`incompatible type`), because the callback is registered in a general handler registry statically typed for `Exception`, not a specific subclass — the caller (Starlette itself) decides what gets passed, and the type system can't statically guarantee it'll only ever be a `TaskNotFoundError`, even though *in practice* it will be (Starlette dispatches by the exception's actual runtime type). `assert isinstance(exc, TaskNotFoundError)` restores the narrower type inside the function body for the cases where you'd need, say, `exc.task_id`.
- The middleware wraps `call_next` in `try/except` specifically to log unhandled failures too — without it, the code after `call_next` simply wouldn't run for an exception with no registered handler, and the log would only ever show "happy" and "neatly handled" requests, never genuinely broken ones.
- Async DB sessions (the general, request-scoped model) were deliberately not added to the project — none of the three endpoints does more than one storage operation per call, so there's nothing to share a connection across within a single request; introducing that pattern now would mean adding an abstraction with no real need behind it.

## Check yourself

1. What does the "onion" middleware model (like Koa's) give you that a linear `next()` chain in classic Express doesn't — specifically regarding what happens to the response **after** it comes back from the route handler?
2. If you remove the `try/except` around `call_next` in the logging middleware, what exactly stops happening for an unhandled exception in a route — does the response the client receives change?
3. Why is `task_not_found_handler` typed to accept `exc: Exception`, not `exc: TaskNotFoundError`, even though it's registered specifically for `TaskNotFoundError`? What's the tension here between "how it's actually used" and "what the type system can statically guarantee"?
4. Why does `TaskNotFoundError`, raised inside `get_task_or_404` (a `Depends` dependency), get caught by the same exception handler as the same error raised directly in a route's body?
5. Why doesn't this project adopt the "one session per request" pattern for the database, even though that's standard practice in many real FastAPI applications?

<details>
<summary>Answers</summary>

1. In the onion model, every middleware is code wrapping the *entire* rest of the pipeline: it has "before" code (runs as the request travels inward) and "after" code (runs once the response is ready and travels back outward) — and the "after" code sees the **finished, final** response, however it was produced (an ordinary return from a route, a response produced by an exception handler, and so on). The linear `next()` model in classic Express historically didn't give most middleware a natural "after" at all — `next()` just hands control onward, without wrapping the following code in a way that lets you symmetrically do something once the response is already built, without special tricks.
2. The client still gets a standard `500 Internal Server Error` — a more outer, built-in Starlette layer produces that regardless of our own code. What changes is that the middleware code **after** the `call_next` line (in our case, computing the duration and printing the log) simply never runs, because the exception flies straight through the middleware function's body without pausing at `response = await call_next(request)`. No log entry for that request survives at all — not an "error" entry, a complete absence of one.
3. `add_exception_handler` in Starlette registers the handler in a general registry, whose static signature is `Callable[[Request, Exception], ...]` — because the type system can't prove, at check time, that this specific handler will only ever be called with instances of `TaskNotFoundError` and nothing else: the decision of which handler to call is made dynamically, at runtime, based on the exception's actual type. In practice Starlette really will only call this handler for `TaskNotFoundError` (since that's exactly how it was registered), but static typing has no part in that dispatch and can't offer the same guarantee the runtime handler-registry logic provides.
4. Because both the route body and the `Depends` dependencies resolving before it are part of the same request lifecycle, which Starlette wraps in a single exception-handling mechanism. From that mechanism's point of view, it doesn't matter exactly which step of request processing the exception came from — before the route function is even called (while resolving dependencies) or inside it — it's caught at the same level either way, and a matching registered handler is looked up by the exception's type.
5. Because none of the project's three endpoints performs more than one storage operation per call, so none of them needs several operations to share the same session/transaction — the very reason the "one session per request" pattern exists (guaranteeing that several related operations see consistent database state, or roll back together as one unit) simply doesn't arise here. Introducing it ahead of time would mean adding infrastructure for its own sake, rather than to solve a problem the project actually has right now.

</details>

## Common mistake

The most common mistake on first meeting FastAPI middleware is writing an `@app.middleware("http")` function as if it's guaranteed to see and log **every** request, including completely broken ones, without a second thought toward a `try/except` around `call_next`. A developer used to a logging middleware in Express, typically placed **first** in the chain and just wrapping `next()` with no fuss, carries that habit over to FastAPI — and discovers (usually not right away, but when a real production incident leaves not a single log line behind) that unhandled exceptions "slip past" the code after `call_next`, leaving the logs incomplete at exactly the moment they matter most — during a genuine crash, not during ordinary, well-handled error flow.

The second common mistake is deciding that since `TaskNotFoundError` is now caught centrally via `add_exception_handler`, any domain error at all can just be "thrown" from deep in the code and will "somehow" turn into a meaningful HTTP response on its own. Centralization only works for **registered** exception types — if the project later adds, say, `TaskAlreadyDoneError`, and there's no `add_exception_handler` for it, it flies out as an ordinary unhandled exception and turns into the same generic `500` as any internal programmer error (a typo, an `AttributeError`, and so on) — centralized error handling doesn't remove the need to explicitly register a handler for every new kind of domain error you want to surface as a meaningful HTTP status, rather than a generic `500`.
