# FastAPI: routing, Pydantic, Depends

## Theory

**Routing.** FastAPI ties an HTTP method and a path to a function via a decorator, and pulls path/query parameters directly from the **function's signature**, matching by name and type — no manual `req.params.taskId` the way you'd do in Express:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/tasks/{task_id}")
async def get_one(task_id: int):        # {task_id} from the path -> the task_id: int parameter
    ...

@app.get("/tasks")
async def list_all(status: str = "all"):  # ?status=... from the query string, with a default
    ...
```

In spirit this is closer to Nest.js's decorator-based routing (`@Get()`, `@Post()` on controller methods) than to Express's `app.get(path, handler)` chains — except instead of DTO classes with `@Body()`/`@Param()`, FastAPI infers where a parameter comes from (path, query, body) straight from the signature and its types.

**Pydantic models — validation baked into the framework more deeply than zod/yup in Express.** `BaseModel` looks syntactically like a dataclass (chapter 04) — fields declared via type hints — but unlike a dataclass, a Pydantic model **validates input data at runtime** on construction:

```python
from pydantic import BaseModel

class TaskCreate(BaseModel):
    text: str
    priority: str = "medium"
```

The key difference from `TypedDict` (chapter 10): `TypedDict` is a purely static hint that checks nothing at runtime; a Pydantic model, by contrast, genuinely parses and validates data on every `model_validate(...)`, raising a structured validation error if the shape doesn't match — FastAPI catches that error itself and turns it into an HTTP 422 pinpointing exactly which field is wrong.

Comparing to zod/yup highlights a difference in the approach itself: zod/yup are **schema-first** (you write a separate schema, `z.object({...})`, and the TS type is derived from it via `z.infer<>`); Pydantic is **type-hint-first** (you write a class with typed fields, and that declaration *is* the schema and the type at the same time — there's nothing to derive from, because the schema and the type are literally the same thing). "Deeper framework integration" specifically means: the same Pydantic declaration is used by FastAPI for three things at once — validating the request body, serializing the response, and generating the OpenAPI schema — with no separate, manually-synchronized declarations for each.

**An important, non-obvious nuance: Pydantic doesn't call your `__str__`.** If a field is declared as `str`, and the data source is an object with a differently-typed field (say, our `Priority(IntEnum)` with an overridden `__str__` returning `"high"`), it's intuitive to assume Pydantic will call `str(value)` and get "high". In practice, that's not what happens:

```python
class TaskRead(BaseModel):
    priority: str

TaskRead.model_validate(task, from_attributes=True).model_dump_json()
# {"priority": "2", ...} -- the string form of the NUMERIC value, not "high"!
```

Pydantic's internal type-coercion logic (implemented in pydantic-core, separate from the language's usual `__str__`/`__repr__` protocol) coerces an `IntEnum` into `str` via its numeric value, not via `str()`. The only reliable way to actually get "high" is to construct the Pydantic model explicitly, calling `str(task.priority)` yourself, rather than relying on automatic coercion via `from_attributes`.

**`Depends` — dependency injection, but not the Nest.js kind.** In Nest.js, DI is usually constructor-based: services are registered in a module and injected into a controller's constructor. In FastAPI, DI happens at the level of a handler function's parameters:

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

FastAPI calls `get_task_or_404` itself (passing it `task_id` from the path — the same parameter-inference logic as the routes themselves), and substitutes the result into `task`. The dependency is resolved fresh on every request (unless explicitly told to cache), rather than being created once as a singleton at application startup, the way services usually work in Nest.js.

**Automatic OpenAPI/Swagger generation.** `/docs` (Swagger UI) and `/redoc` appear automatically, with zero lines of configuration — FastAPI builds the OpenAPI schema straight from the route declarations and Pydantic models. In Express, this usually needs a separate tool (`swagger-jsdoc` and manual JSDoc annotations), or in Nest.js, `@nestjs/swagger` with explicit `@ApiProperty()` on every DTO field — FastAPI doesn't need that separate layer precisely because Pydantic models are already fully typed, and that's the only thing needed to build the schema.

### Parallels with JS/TS/Node:

- FastAPI's decorator-based routing is closer to Nest.js than to bare Express; parameters are inferred from the function signature, not pulled manually off `req`.
- Pydantic is like zod/yup (runtime validation), but type-hint-first rather than schema-first: an annotated class is the schema and the type at once.
- `Depends` is DI at the level of function parameters, resolved per request, rather than the constructor-based singleton DI you'd find in Nest.js.
- Automatic OpenAPI generation is free because Pydantic models are already fully typed; Express/Nest.js usually need a separate annotation layer for the same completeness.

## What we're adding to the project

We're wrapping `taskman` in a REST API on top of the **exact same** storage layer — neither `models/` nor `storage/` change by a single line; this is the direct payoff of chapter 10 (the `TaskStorage` protocol) and chapter 12 (the async storage layer). A new `api/` package (`schemas.py`, `routes.py`, `app.py`) adds three endpoints (`POST /tasks`, `GET /tasks`, `PATCH /tasks/{id}/done`), reusing `filter_by_status`/`sort_tasks`/`get_page` from the storage layer with zero changes — they took a `list[Task]` before, and they still do, regardless of who's calling: the CLI or an HTTP handler.

## Practical exercise

1. Install `fastapi` and `uvicorn[standard]`, add them to `dependencies` in `pyproject.toml`.
2. Create `api/schemas.py`: `TaskCreate` (`text: str`, `priority: str = "medium"` with a validator confirming the value is one of `PRIORITY_CHOICES`) and `TaskRead` (`id`, `text`, `priority: str`, `done`) with a classmethod `from_task(task: Task) -> TaskRead` that explicitly calls `str(task.priority)`.
3. Create `api/routes.py` with an `APIRouter`: `POST /tasks` (body — `TaskCreate`, status 201), `GET /tasks` (query params `status`/`sort`/`page`/`page_size`, mirroring the CLI's `list` flags), `PATCH /tasks/{task_id}/done` via a `Depends`-based dependency `get_task_or_404` that converts `TaskNotFoundError` into `HTTPException(404)`.
4. Create `api/app.py`: `FastAPI(...)` with a `lifespan` — an async generator-based context manager (`@asynccontextmanager`, chapters 06/12) that calls `await db.init_db()` before `yield`.
5. Run the server (`uvicorn taskman.api:app --reload`), open `/docs`, create a task, list tasks, mark one done via curl or the Swagger UI.
6. Before reading the worked solution — try creating a task with blank text (`{"text": "   "}`) through the API. Look at the response and status code. Then call `GET /tasks` again. Is the result what you'd expect?

## Worked solution

`pyproject.toml` (real dependencies added):

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

`src/taskman/api/schemas.py` (new file):

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

`src/taskman/api/routes.py` (new file):

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

`src/taskman/api/app.py` (new file):

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

`src/taskman/api/__init__.py` (new file):

```python
from .app import app

__all__ = ["app"]
```

Now, about the question from exercise 6. A real run (`uvicorn taskman.api:app`, then `curl -X POST /tasks -d '{"text": "   "}'`) gives `500 Internal Server Error` — and that's expected: `Task.__post_init__` (chapter 04) raises `ValueError` for blank text, and nothing in the route catches it, so FastAPI hands back a generic 500. Proper, centralized conversion of domain exceptions into meaningful HTTP responses is next chapter's topic. But the next step — `GET /tasks` — on the unfixed code from chapter 08 **also** returned 500, and that's not about error handling anymore, it's a genuine bug:

```python
# BEFORE the fix -- as it was since chapter 08, in storage/sqlite_storage.py:
async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
    assert task_id is not None
    return Task(id=task_id, text=text, priority=priority, done=False)   # <- OUTSIDE the transaction!
```

`Task(...)` (and, therefore, the blank-text check in `__post_init__`) is called **after** `async with db_connection()` has already closed and committed the transaction. The blank-text row genuinely lands in the database, `ValueError` only fires afterward — and every subsequent `list_tasks()` call (from either the CLI or the API) then crashes trying to turn that "poisoned" row back into a `Task`. The bug has existed since chapter 08; no previous scenario ever happened to create a task with blank text through a real call.

The fix isn't about error handling — it's about **where the transaction ends**:

```python
async def add_task(text: str, priority: Priority = Priority.MEDIUM) -> Task:
    async with db_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (text, priority, done) VALUES (?, ?, ?)",
            (text, int(priority), 0),
        )
        task_id = cursor.lastrowid
        assert task_id is not None
        return Task(id=task_id, text=text, priority=priority, done=False)  # now INSIDE
```

Moving `return Task(...)` inside the `async with` block isn't cosmetic: if `Task.__post_init__` raises `ValueError`, the exception now surfaces **inside** `db_connection`'s body, hits its own `except Exception: await conn.rollback(); raise` (chapter 08) — and the `INSERT` rolls back instead of committing. After this fix, `GET /tasks` never sees the "poisoned" row again, because it never makes it into the database at all.

Key decisions:

- `TaskRead.from_task` explicitly calls `str(task.priority)`, rather than relying on `model_validate(task, from_attributes=True)` with a `priority: str` field — as shown in the theory, the automatic coercion would produce `"2"`, not `"high"`.
- `TaskCreate.priority` is a plain string with a manual `field_validator`, not a field typed `Priority` — this way, a client's value naturally looks like `"high"`/`"medium"`/`"low"`, not a magic number, and sidesteps the same enum-coercion nuance.
- `get_task_or_404` is the one and only place where `TaskNotFoundError` is explicitly turned into an HTTP response — that's enough for this chapter, but repeating this same `try/except` in every handler that needs a task by id doesn't scale — chapter 14 shows how to remove that repetition with a single, application-level exception handler.
- `filter_by_status`/`sort_tasks`/`get_page` are called in `routes.py` exactly the way they're called in `cli/commands.py` — none of them knows, or needs to know, that they now have two callers (the CLI and HTTP) instead of one.

## Check yourself

1. Why does `TaskRead.model_validate(task).model_dump_json()` for a `priority: str` field print `"2"`, not `"high"`, if `Priority.__str__` explicitly returns `"high"` for `Priority.HIGH`?
2. How does a Pydantic `BaseModel` differ from `TypedDict` (chapter 10) in terms of what happens when you call `SomeModel.model_validate(data that doesn't match the schema)`?
3. Why did the blank-task-text bug surface specifically while testing through the API, even though the `add_task` code containing the mistake hadn't changed since chapter 08?
4. Moving `return Task(...)` inside the `async with db_connection()` block in `add_task` — why does that change whether the `INSERT` commits or rolls back, if the `Task` constructor raises an exception?
5. How does `Depends(get_task_or_404)` in FastAPI differ from constructor-based DI in Nest.js — exactly when is the dependency called, and how often is it recreated?

<details>
<summary>Answers</summary>

1. Because type coercion inside Pydantic (in pydantic-core) doesn't go through Python's usual `str()`/`__str__` protocol — for `IntEnum`-like values being coerced to a string field, it uses the numeric `.value`, not whatever `str(value)` would return in ordinary Python code. A custom `__str__` is entirely ignored by this coercion mechanism — the only way to actually get "high" is to call `str()` yourself, before the value ever reaches the Pydantic model.
2. `TypedDict` is a purely static annotation: a `SomeTypedDict` at runtime is just a plain `dict`, and you can pass literally anything to a spot expecting one — nothing gets checked; only mypy flags the mismatch, statically. Pydantic's `BaseModel.model_validate(data)` genuinely runs a check at call time: if the data doesn't match the declared fields/types, it raises a `ValidationError` with a precise description of which field failed and why — this happens on every single call, at runtime, regardless of whether mypy was ever run over that code at all.
3. Because previously (in the CLI, chapters 08–12), no test scenario ever passed a blank or whitespace-only text as a real argument to a task — every explicit call to `add_task`/`python -m taskman add ...` in earlier chapters used meaningful text. The API, accepting raw JSON from a client, is the first place in the project where it became genuinely easy and natural to try an edge case (`{"text": "   "}`) with no special setup — and that's exactly what finally drove execution into the line of code that had been wrong from the start.
4. If `Task(...)` is called **after** exiting `async with db_connection()`, the `async with` block has already completed successfully with no exception — meaning the `db_connection` generator (chapter 08) has already run `await conn.commit()` before the exception from the `Task` constructor even happens. If `Task(...)` is called **inside** the block instead, the exception from `__post_init__` occurs before the `async with` body finishes normally — the `db_connection` generator catches it in its own `except Exception:`, calls `await conn.rollback()`, and re-raises, never reaching `await conn.commit()` at all.
5. In Nest.js, DI is usually constructor-based: a service is registered in a module once and injected into a controller's constructor as an already-built, usually singleton object that lives for as long as the application does. `Depends(get_task_or_404)` in FastAPI is a function call, made fresh on **every HTTP request** (unless explicitly told to cache via `use_cache`), not a once-created object — the dependency itself gets its own parameters (here, `task_id`) through the same signature-inference logic as the route itself, and lives exactly within the scope of one request, not the whole process.

</details>

## Common mistake

The most treacherous mistake in this chapter isn't about FastAPI syntax — it's silently trusting that Pydantic "just converts" an object into a model the way you'd intuitively expect, including respecting custom `__str__`/`__repr__`. A developer used to dataclasses (chapter 04), where `str(obj)` always calls exactly what you wrote in `__str__`, naturally expects the same from `model_validate(obj, from_attributes=True)` with a `str` field — and gets silently wrong data (`"2"` instead of `"high"`) with no error or warning at development time at all. This isn't caught while writing the code, and it isn't caught by "happy path" tests — it's only caught when someone actually looks at the real contents of the JSON response, which is exactly why this chapter was built around actually running the server and hitting it with `curl`, not just reading code.

The second mistake is taking "well, FastAPI is smart, it'll figure out domain exceptions somehow" on faith, without checking it in practice. `TaskNotFoundError`, if nothing explicitly catches it, doesn't turn into a clean `404` on its own — FastAPI hands it back as-is, as a generic `500 Internal Server Error`, exactly the way it would treat any other unhandled exception. `get_task_or_404` in this chapter is a deliberately local, one-off fix (one dependency, for the one route that needs it); the next chapter reveals that every new route working with a specific task would need this same `try/except` copy-pasted, unless the handling is centralized — which is exactly why that topic gets its own chapter, rather than being folded in here "while we're at it."
