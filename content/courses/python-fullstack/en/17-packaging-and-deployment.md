# Packaging and deployment: Docker, config from the environment, structured logging

## Theory

**Multi-stage Dockerfile.** The idea is the same as in multi-stage Node builds. Separate the "build stage", which needs compilers and dev headers, from the "runtime stage", which needs only the finished runtime and the installed dependencies. In Node that looks like `FROM node AS builder ... FROM node:alpine AS runtime COPY --from=builder ...`:

```dockerfile
# ---- builder: compile dependencies, including C-extension wheels like bcrypt ----
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --prefix=/install .

# ---- runtime: only the installed packages and application code, no compilers ----
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src ./src

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "taskman.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

The `slim` tag (Debian-based, glibc) is almost always the safe default for Python with C extensions such as `bcrypt` and `aiosqlite`. Most packages ship prebuilt `manylinux` wheels for glibc.

The `alpine` tag (musl libc) gives a smaller image. But sometimes packages have no prebuilt `musllinux` wheels, and pip ends up compiling the extension from source right inside the container.

The saving on image size then turns into dragging the very same compilers into the `alpine` image. Those are exactly the compilers a multi-stage build was supposed to keep out of the final layer.

**Environment variables via `pydantic-settings`.** In chapter 15, `SECRET_KEY` was hardcoded in the code and flagged "change me in production". That chapter named it as its own common mistake: exactly what you cannot leave that way in a real project.

The `pydantic-settings` package is the direct, correct fix. `BaseSettings` is the same Pydantic model as in chapter 13. It just reads field values from environment variables, and optionally from a `.env` file, instead of an HTTP request body. The validation and type coercion are the same:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TASKMAN_")

    secret_key: str                                    # required, no default
    access_token_expire_minutes: int = 30
    database_path: str = "taskman.db"

settings = Settings()
```

With no default for `secret_key`, the app simply won't start if the environment variable isn't set. You get a `pydantic.ValidationError` right at module import time, rather than a quiet run with an empty or predictable secret. That is deliberate: a secret that **has** a safe default can't, by definition, be a secret.

**A real, empirically-found nuance: mypy and `BaseSettings`.** `Settings()` is called with zero arguments, but `secret_key: str` with no default formally requires one.

Running `mypy --strict` honestly complains: `Missing named argument "secret_key" for "Settings"`. Statically there is no way to know the value will come from the environment at runtime. The fix is not to loosen the types. Enable Pydantic's own mypy plugin instead — it understands this case:

```toml
[tool.mypy]
plugins = ["pydantic.mypy"]
strict = true
```

**Structured logging.** Up through the last chapter, API logs went through `print(...)` (chapter 14). That is fine for development, but not for production: logs need to be **machine-parseable**.

Log aggregation systems look for structured fields, not text sliced with regexes. Common ones are CloudWatch, Datadog and ELK — Elasticsearch, Logstash and Kibana used together. The minimal structured format is one JSON string per event, via the standard `logging` module:

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })
```

Extra fields (method, path, status, duration) are passed via `extra={...}` in the `logger.info(...)` call. They get attached as attributes on the `LogRecord` object. The formatter pulls them out via `getattr(record, "field_name", None)`.

**A healthcheck endpoint — not just "is the process alive".** A `GET /health` that unconditionally returns `{"status": "ok"}` is nearly useless. It can never signal a real failure, even if the database is unreachable. A real health check makes a trivial call against the thing the service actually depends on:

```python
@router.get("/health")
async def health_check() -> dict[str, str]:
    await db.ping()   # SELECT 1 -- just confirm the database responds
    return {"status": "ok"}
```

If `ping()` raises, because the database is down or corrupted, the endpoint naturally returns `500`. No special `try/except` is needed. Docker's own `HEALTHCHECK`, or an orchestrator such as Kubernetes with its liveness and readiness probes, will then see the service as "unhealthy".

### Parallels with JS/TS/Node:

- A multi-stage Dockerfile is the same trick used in Node projects: a builder stage with compilers, a runtime stage with only the finished artifacts.
- `pydantic-settings` ~ `dotenv` plus manually coercing types out of `process.env`, except validation and coercion happen automatically instead of by hand for every variable.
- Structured JSON logging is the same principle as `pino`/`winston` with a JSON transport in Node: logs as data, not text meant for a human.
- A healthcheck endpoint is the same concept as `/healthz` and `/readyz` in any Node service behind an orchestrator. The only difference: here it is implemented by hand, not by a library.

## What we're adding to the project

We're fully dockerizing the service: a multi-stage `Dockerfile`, plus a `docker-compose.yml` with a named volume for the SQLite file. Without that volume, the database would be recreated from scratch every time the container is recreated.

`SECRET_KEY` and the database path move from hardcoded constants into a `pydantic-settings`-based `config.py`. Logging in the API layer (`middleware.py`) moves from `print()` to structured JSON via the standard `logging` module. A `GET /health` endpoint appears, one that genuinely checks the database connection instead of unconditionally saying "ok".

## Practical exercise

1. Add `pydantic-settings` to the dependencies. Create `config.py` with `Settings(BaseSettings)`: `secret_key: str` (no default), `access_token_expire_minutes: int = 30`, `database_path: str = "taskman.db"`, `env_prefix="TASKMAN_"`, `env_file=".env"`. Create a module-level `settings = Settings()`.
2. Update `auth/security.py` and `storage/sqlite_storage.py` to use `settings.secret_key`/`settings.access_token_expire_minutes`/`settings.database_path` instead of hardcoded constants.
3. Add `plugins = ["pydantic.mypy"]` to `[tool.mypy]` and confirm `mypy --strict` passes on `config.py` with no errors.
4. In `tests/conftest.py`, set `TASKMAN_SECRET_KEY` via `os.environ.setdefault(...)` **before** the first import of anything from `taskman` — think about why the order matters here.
5. Create `logging_config.py` with `JSONFormatter` and `configure_logging()`. Call `configure_logging()` in the app's `lifespan` (before `await db.init_db()`).
6. Replace `print(...)` in `api/middleware.py` with `logger.info(...)`/`logger.exception(...)`, passing `method`/`path`/`status_code`/`duration_ms` via `extra={...}`.
7. Add `storage/sqlite_storage.py:ping()` (a trivial `SELECT 1`) and `api/routes_health.py` with `GET /health`, calling `db.ping()`.
8. Write a multi-stage `Dockerfile` (builder + runtime), `.dockerignore`, `.env.example` (documenting the needed variables; `.env` itself isn't committed).
9. Write `docker-compose.yml` with an `api` service and a named volume, mounted wherever `TASKMAN_DATABASE_PATH` points.
10. Build the image and bring it up via `docker compose up`. Create a user and a task via `curl`. Then **fully remove and recreate the container** with `docker compose down && docker compose up`, and confirm the task is still there.

## Worked solution

`src/taskman/config.py` (new file):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TASKMAN_")

    secret_key: str
    access_token_expire_minutes: int = 30
    database_path: str = "taskman.db"


settings = Settings()
```

`src/taskman/logging_config.py` (new file):

```python
import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
```

`src/taskman/auth/security.py` (updated — reads settings, not constants):

```python
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..config import settings

ALGORITHM = "HS256"


def _prepare(password: str) -> bytes:
    """sha256 first, then base64: bcrypt reads 72 bytes and stops at a zero byte."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)   # 44 bytes -- always under the 72-byte limit


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prepare(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_prepare(password), hashed_password.encode("utf-8"))


def create_access_token(username: str) -> str:
    minutes = settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    username: str = payload["sub"]
    return username
```

`src/taskman/storage/sqlite_storage.py` (changes — `DB_PATH` from settings, `ping` added; everything else as in chapter 16):

```python
from ..config import settings
# ...
DB_PATH = Path(settings.database_path)
# ...

async def ping() -> None:
    """A trivial query used by the health check to confirm the database is reachable."""
    async with db_connection() as conn:
        await conn.execute("SELECT 1")
```

`src/taskman/storage/protocol.py` — `async def ping(self) -> None: ...` added to `TaskStorage`.

`src/taskman/api/routes_health.py` (new file):

```python
from fastapi import APIRouter

from ..storage import db

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    await db.ping()
    return {"status": "ok"}
```

`src/taskman/api/middleware.py` (updated — structured logs instead of `print`):

```python
import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response

logger = logging.getLogger("taskman.api")


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
            },
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
```

`src/taskman/api/app.py` (updated — `configure_logging()` in lifespan, the new health router):

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..logging_config import configure_logging
from ..models import TaskNotFoundError
from ..storage import db, users as users_storage
from .exceptions import task_not_found_handler
from .middleware import log_requests
from .routes import router
from .routes_auth import router as auth_router
from .routes_health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await db.init_db()
    await users_storage.init_users_table()
    yield


app = FastAPI(title="taskman", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(router)
app.include_router(health_router)
app.middleware("http")(log_requests)
app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
```

`pyproject.toml` (a dependency and the mypy plugin added):

```toml
[project]
dependencies = [
    "aiosqlite>=0.19",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pyjwt>=2.8",
    "bcrypt>=4.0",
    "python-multipart>=0.0.18",
    "pydantic-settings>=2.4",
]

[tool.mypy]
python_version = "3.11"
plugins = ["pydantic.mypy"]
strict = true
```

`tests/conftest.py` (top of the file — the environment variable is set before the app is imported):

```python
import os

os.environ.setdefault("TASKMAN_SECRET_KEY", "test-secret-key-not-for-production")

from contextlib import asynccontextmanager  # noqa: E402
# ... the rest of the taskman-module imports come AFTER setting the variable
```

`Dockerfile` (new file, full text — see the theory section above).

`.env.example` (new file):

```bash
# Copy this file to .env and fill in real values for local development.
# In production, set these as real environment variables instead of a file.
TASKMAN_SECRET_KEY=change-me-to-a-long-random-value
TASKMAN_ACCESS_TOKEN_EXPIRE_MINUTES=30
TASKMAN_DATABASE_PATH=taskman.db
```

`docker-compose.yml` (new file):

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      TASKMAN_SECRET_KEY: ${TASKMAN_SECRET_KEY:?set TASKMAN_SECRET_KEY before starting}
      TASKMAN_DATABASE_PATH: /data/taskman.db
    volumes:
      - taskman-data:/data

volumes:
  taskman-data:
```

A real run confirms it: `docker compose up`, curl, `docker compose down`, then `docker compose up` again. A task created before the container was recreated is still visible afterward. It is stored in the named volume `taskman-data`, mounted at `/data`, not in the container's own filesystem, which is destroyed together with it.

Key decisions:

- The line `TASKMAN_DATABASE_PATH=/data/taskman.db` in `docker-compose.yml` points **inside the volume**, not at the default path. The default is `taskman.db` in the container's working directory. Leave the default path in place, and the database lives in the container's ordinary layer and vanishes when it is recreated. The volume then sits mounted but unused.
- `${TASKMAN_SECRET_KEY:?set TASKMAN_SECRET_KEY before starting}` in the compose file is the "required variable" syntax, not a substitution with a silent default. Without the environment variable set, `docker compose up` fails with a clear message. It does not start the service with an empty or predictable secret.
- `plugins = ["pydantic.mypy"]` matters. Without this line, `mypy --strict` would require passing `secret_key` to `Settings()` as an explicit argument. But the real value only arrives from the environment at runtime. The plugin teaches mypy this specific `BaseSettings` semantics, rather than loosening strictness for the rest of the codebase.
- The test environment variable (`TASKMAN_SECRET_KEY`) is set at the very **top** of `conftest.py`, before a single `from taskman import ...`. The reason: `settings = Settings()` in `config.py` runs once, at the moment that module is **imported**, not on every access to `settings`. If the variable isn't set before the first import of anything that transitively pulls in `config.py`, the app fails with a `ValidationError`. That happens before a single line of the test even runs.

## Check yourself

1. Why is `Settings()` with zero arguments deliberate, desired behavior, rather than an oversight, if `secret_key` has no default value?
2. What exactly does a multi-stage Docker build protect against, and why doesn't installing `gcc` in the builder stage bloat the final image?
3. Why must `os.environ.setdefault("TASKMAN_SECRET_KEY", ...)` sit physically before the rest of the imports in `conftest.py`? Why is "somewhere in the file" not enough?
4. How does a health check calling `db.ping()` differ from one that unconditionally returns `{"status": "ok"}`? In what scenario does the difference actually show up in practice?
5. Why does `docker-compose.yml` specify `TASKMAN_DATABASE_PATH=/data/taskman.db`, rather than just mounting the volume and leaving the database path at its default?

<details>
<summary>Answers</summary>

1. Because `secret_key` is literally the one thing that makes JWT (JSON Web Token) signatures verifiable and un-forgeable (chapter 15). If `Settings` had a safe default for the secret, that default couldn't, by definition, be a secret. It would be identical across every installation of the app, including any copy of the source code. So `Settings()` with no arguments **has to** fail with a validation error if the environment variable isn't set. That is fail-fast, instead of quietly starting with a predictable value that is useless as a secret.
2. A multi-stage build guarantees the final image contains only what's needed **to run** the application: installed Python packages and code. It does not contain the tools needed only **to build** those packages, such as the `gcc` compiler for C extensions like `bcrypt`. The `gcc` package gets installed in the `builder` stage. But `COPY --from=builder /install /usr/local` in the `runtime` stage copies only the directory holding the already-built, finished packages. The `gcc` binary itself, and the apt layer it was installed into, never make it into the final image. The final image is built from scratch starting at `FROM python:3.11-slim AS runtime`, not by inheriting `builder`'s layers.
3. Because `Settings()` — and with it, reading `TASKMAN_SECRET_KEY` from the environment — runs **once**, at the moment the `config.py` module is first imported. It does not run fresh on every access to `settings.secret_key`. Any earlier `from taskman.something import ...` that transitively imports `config.py` locks in `settings` with whatever the environment had at that point. That includes the case where nothing was set at all. Almost everything imports it: `auth/security.py`, `storage/sqlite_storage.py`. Setting the variable later doesn't help, because `Settings()` has already either run successfully with a different or missing value, or already failed.
4. A health check unconditionally returning `{"status": "ok"}` answers only one question: is the process alive enough to accept an HTTP request. It returns `200` even if the database file has been deleted, corrupted, or made unreachable by permissions. A health check calling `db.ping()` answers the more useful question: can the service actually do its job right now. The difference shows up exactly when the process is alive — uvicorn responds to requests — but a dependency the service cannot work without has failed. The first version tells the orchestrator "all good". The second honestly fails, giving the system a chance to restart the container or stop routing traffic to it.
5. Because the default path (`taskman.db`, relative, inside the container's `/app` working directory) physically lives in the container's ordinary, short-lived filesystem layer. That is the very layer destroyed on `docker compose down` or on container recreation. A volume mounted at `/data` survives container recreation, but only if the database file genuinely lives **inside** that mounted path. Setting `TASKMAN_DATABASE_PATH=/data/taskman.db` explicitly guarantees the application writes its file exactly there. Otherwise it writes next to it, at a default path that has no connection to the volume at all.

</details>

## Common mistake

The most common mistake when first dockerizing a stateful service is about paths. You mount a volume in `docker-compose.yml`, but forget to change the path to the database file inside the application. It stays pointed at its default path, somewhere else in the container's filesystem.

On the surface everything looks right: the volume is declared, it is mounted, and `docker compose up` doesn't produce a single error. And yet data is lost every time the container is recreated, because the application never actually wrote to the mounted path.

This mistake is treacherous precisely because it doesn't show up right away. As long as the container is merely restarted (`docker compose restart`) without being fully removed, the file in the ordinary container layer stays put. Everything appears to work.

The data loss is discovered only once the container is genuinely recreated from scratch: a rebuild, `docker compose down && up`, or a new deploy. That is exactly the moment persistence matters most.

The second common mistake is reading environment variables in the wrong place. Instead of constructing `Settings()` once at startup, you scatter `os.getenv(...)` calls throughout the code, wherever a value happens to be needed.

That gives up the one place where missing or invalid configuration could be caught **immediately**, at application startup. Instead of failing honestly on launch with a clear "missing `TASKMAN_SECRET_KEY`" message, the app starts up normally.

The error then surfaces only once that specific bit of code actually runs. It might be a `None` where a string was expected, or a variable that was simply skipped. Sometimes that is days after the deployment, on a rarely-hit request path.
