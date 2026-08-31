# Capstone: reviewing the project and where to grow next

## Theory

**The road so far, briefly.** `taskman` started in chapter 00 as an `argparse` skeleton, printing an in-memory list to the console. Along the way it picked up, in order:

- typed models instead of bare dicts (`@dataclass`, chapter 04);
- a package structure instead of a single file (chapter 05);
- real persistence instead of process memory (SQLite, chapter 08);
- static type checking as part of everyday development (`mypy --strict`, chapter 10);
- fully asynchronous data access (chapter 12);
- a REST (Representational State Transfer) API on top of the **exact same** storage layer, never touched for that purpose (chapters 13–14);
- multi-user authentication (chapter 15);
- a thorough test suite (chapter 16);
- packaging into a container with configuration from the environment (chapter 17).

The key architectural bet that paid off across all of this was the `TaskStorage` protocol (chapter 10). Both the command-line interface (CLI) and the API called the same set of functions across all 8 later chapters. Neither ever knew whether those functions were backed by `sqlite3` or `aiosqlite`, by a file or by something else entirely.

It's worth naming another thread that ran through the whole course. Almost every chapter that added something new also had something it **deliberately didn't add**. Not out of oversight, but because the project's current scale didn't call for it.

Chapter 06 didn't add locking around task writes, because chapter 08 hadn't introduced them yet. Chapter 14 didn't add a session-per-request, because no endpoint did more than one database operation per call. Chapter 15 didn't add login to the CLI, because the CLI is a single-user tool by nature.

These aren't coincidences. They are one consistent line of reasoning: infrastructure should answer a real need, not a hypothetical one. This final chapter returns to that theme, now at the scale of the whole project.

One more thing is worth stating plainly at the end. Several times during the course, tests and `mypy --strict` caught **real** bugs, not textbook hypotheticals.

Tests found two: `capsys` can't see `print_err` (chapter 09), and `monkeypatch` doesn't touch `users_storage.py` because of a bad import (chapter 16). Static checking found two more: `log_command` mistyped via `ParamSpec` (chapter 10), and `Settings()` without the plugin (chapter 17).

That is the practical case for why chapters 09/10/16 exist at all, rather than being a course formality.

**The "senior polish" checklist.**

*Configuration* — done in chapter 17 (`pydantic-settings`, a required `SECRET_KEY` with no default). Three things are still missing for a genuinely mature project:

- separate configuration profiles for dev, staging and prod (right now the same `.env` and environment variables apply everywhere);
- validation of the secret's content, not just its type — an explicit minimum-length check on `SECRET_KEY`, not just the warning from the `PyJWT` library;
- a way to rotate secrets without downtime.

*Logging* — structured as JSON (chapter 17), but missing a **request id**. Right now, if two requests run concurrently (chapters 12/16), their log lines interleave in the same output stream. Nothing tells you which line belongs to which request.

The real fix has three parts. Generate a unique id when a request enters the middleware. Store it in context, via `contextvars` for instance. Attach it to every log entry produced within that request.

Structured logs written to `stdout` are also only the first half of the job. In production they still need to be **collected** and shipped somewhere you can search them. That is two separate pieces: a collector agent that reads the container's output, and a log store it feeds.

```txt
app -> stdout (JSON lines)
  -> collector agent   (Fluentd, Vector or Promtail)
  -> log store         (Loki, CloudWatch or ELK)
  -> you search it
```

In that list, ELK stands for Elasticsearch, Logstash and Kibana used together. Logs becoming JSON does not by itself mean they are going anywhere.

*Graceful shutdown* — a topic the project hasn't touched at all yet. Our `lifespan` (chapters 13/17) does nothing after `yield` today.

That is not an oversight. It is a direct consequence of chapter 08's architectural choice. The storage layer opens and closes a **separate** connection on every call, rather than holding one long-lived pool. So there is simply nothing to close in an orderly way when the process stops.

If a connection pool were used instead — which becomes necessary when moving to Postgres, see below — code after `yield` would be mandatory. It would call `await pool.close()` and wait for already-started database calls to finish before closing the pool.

The server itself already helps. ASGI (Asynchronous Server Gateway Interface) is the protocol between a Python web application and the server running it. Our ASGI server is `uvicorn`.

When `uvicorn` receives SIGTERM, it finishes the HTTP requests already in flight instead of cutting them off mid-response. SIGTERM is the "please stop" signal an orchestrator sends before killing a process.

But an orchestrator such as Kubernetes needs one more thing from your app. It gives a stopping process a grace period: a few seconds to wind down. During that window it keeps sending new requests, unless something tells it not to.

That something is the **readiness** check. It must start failing the moment the stop signal arrives, so new traffic goes to other replicas while the requests already here finish.

```txt
SIGTERM arrives
  -> /readyz starts returning 503  (new traffic stops arriving)
  -> in-flight requests finish     (uvicorn handles this)
  -> pool.close(), process exits
```

Our one `/health` endpoint (chapter 17) covers both liveness ("the process is alive") and readiness ("ready to accept new traffic") at once. In real production these are usually two separate endpoints with different logic.

*Rate limiting* — also entirely absent. The idea is simple: don't let more than N requests per unit of time through from one client or token. The complexity is in where to keep the counter.

For a single process instance, an in-memory counter is enough. Two standard algorithms for it are the token bucket and the sliding window; both count requests over a moving time span.

Real traffic eventually demands several replicas running at once. From that moment, an in-memory counter on one process knows nothing about requests that landed on a different replica. The limit's state then has to move into shared storage, usually Redis.

The FastAPI ecosystem has ready-made libraries for this, `slowapi` being one, built on Starlette middleware. Implementing the limiting algorithm from scratch is almost never worth it.

**Where to grow next.**

*Postgres instead of SQLite.* Swapping the database isn't about SQL (Structured Query Language) syntax, which barely changes. It is about SQLite being an embedded file, while Postgres is a separate network service.

That carries three consequences:

1. A real async driver for Postgres specifically is needed — `asyncpg`, or `psycopg` in async mode — replacing `aiosqlite`.
2. Opening a new TCP (Transmission Control Protocol) connection on **every** storage-function call is our current pattern since chapter 08. Against a network service it becomes expensive and does not scale. This is exactly where a **connection pool** pays off, the one deferred back in chapter 14 because it wasn't needed then.
3. `CREATE TABLE IF NOT EXISTS` on every startup stops being a sufficient way to manage the schema. A migration tool such as Alembic is needed: it versions table-structure changes explicitly and lets you roll them back.

*Celery for background work.* Anything that shouldn't hold up the HTTP response is a candidate for moving off to the background. Examples: sending an email notification when a task is completed, generating a daily summary, heavy batch processing.

We already have `asyncio` and FastAPI's `BackgroundTasks` for lightweight, one-off work that doesn't need to outlive the process. A full task broker is needed when the work must do one of three things:

- survive a process restart;
- automatically retry on failure;
- run on a machine physically separate from the web server.

Celery in that role is a queue, with Redis or RabbitMQ as the message broker, plus separate worker processes. Those workers pull jobs off the queue independently of whether the web server that enqueued them is even still alive.

### Parallels with JS/TS/Node:

- Request ids in logs are the same pattern as `express-request-id`/`AsyncLocalStorage` in Node, for tracing one request through every log line it produces.
- Graceful shutdown in Node services is the same idea: finish active connections on `SIGTERM`, don't cut them off abruptly. It is just implemented via `server.close()` instead of an ASGI lifespan.
- Celery ~ Bull/BullMQ in the Node ecosystem — a queue with a broker (Redis) and separate worker processes. The meaning and architectural role are identical; only the specific library differs.
- Moving from SQLite to Postgres with a pool is the same logic as moving from `better-sqlite3` to `pg` or Prisma in Node. In both cases an embedded file becomes a network service with a limited number of simultaneous connections.

## What we're adding to the project

Nothing — this is a review chapter, with no new code. Its job isn't to bolt one more feature onto `taskman`. It is to honestly assess what "serious, mature" infrastructure is already there, and what has been deliberately deferred until a real need justifies it.

## Practical exercise

Instead of code — a written audit of your own copy of the project, free-form, but following a specific structure:

1. Walk through the "senior polish" checklist (configuration, logging, graceful shutdown, rate limiting) against `taskman` as it stands after chapter 17. For each item — one or two sentences: what's already done, what's missing for real production use.
2. Pick **one** item from the checklist you'd add to the project first, if it went into real production with real users tomorrow. Justify the choice — not abstractly ("this matters"), but through a concrete failure scenario that item closes off.
3. Sketch a plan for migrating to Postgres — no code, just prose or a step list. Cover four things:
   - what changes in `pyproject.toml`;
   - what changes in `storage/sqlite_storage.py`;
   - what is genuinely new (a pool, migrations);
   - what stays untouched thanks to the `TaskStorage` protocol.
4. Name one concrete background task for this project that would be a legitimate candidate for Celery, rather than `asyncio.create_task` or `BackgroundTasks`. Then say which of Celery's three properties is critical for it: surviving a restart, retrying on failure, or running on a different machine.
5. Find at least one moment in your own work on this course where the intuition "this surely works" turned out to be wrong. It should be a case that only got caught by a test, by mypy, or by a real run. What would have happened if that check had never been made?

## Worked solution

An example of such an audit — not the only correct one, but a sample of the kind of reasoning expected here.

**1. Checklist against the current state:**

- *Configuration*: done (`pydantic-settings`, `SECRET_KEY` with no default, `.env.example` committed). Missing: separate dev/prod profiles, explicit validation of the secret's length.
- *Logging*: JSON structure is there (chapter 17). Missing: a request id to trace one request across several log lines, and actually shipping logs anywhere beyond the container's `stdout`.
- *Graceful shutdown*: not implemented, deliberately, and at today's scale (SQLite, a connection per call) that's justified: there's simply nothing to close after `yield`.
- *Rate limiting*: entirely absent. For a single instance with no external traffic, not critical; becomes necessary the moment the service gets real, untrusted clients.

**2. What to add first, and why.** Out of the whole list — a request id in the logs, not rate limiting or Postgres.

Justification, as a concrete failure scenario. A user reports "my task didn't get created". The container's logs for that second show a dozen interleaved lines from different requests. Chapter 16's concurrency test explicitly showed that parallel requests aren't hypothetical, they're the norm.

Without a request id, there's no reliable way to reconstruct what happened to **this** specific request, short of guessing from matching timestamps. This is a cheap change — one line in the middleware plus `contextvars` — and it closes a concrete, already-observed blind spot. Rate limiting and Postgres solve no real problem the project has today.

**3. A Postgres migration sketch:**

- `pyproject.toml`: `aiosqlite` gets replaced with `asyncpg` (or `psycopg[binary,pool]`); the driver is added to `dependencies`, and probably `alembic` to `dev` dependencies.
- `storage/sqlite_storage.py`, or its renamed counterpart `postgres_storage.py`: `db_connection()` stops opening a new connection on every call. Instead, one pool is created at app startup, in `lifespan`, before `yield`. Then `db_connection()` borrows a connection **from the pool** for the duration of the operation and returns it, rather than closing it. `DB_PATH` is replaced with `DATABASE_URL`, a network connection string rather than a file path.
- `CREATE TABLE IF NOT EXISTS` in `init_db()` is replaced with running Alembic migrations at startup. They can also run as a separate deploy step, before the app itself starts.
- Unchanged: `models/`, and all the code in `cli/` and `api/` that accesses data only through the `TaskStorage` protocol (chapter 10). That is exactly what the protocol was introduced for.

**4. A Celery candidate.** Sending an email notification when a `high`-priority task is created ("you have an urgent task"). The critical property is "retries on failure".

Suppose the external mail service is briefly unavailable at the exact moment of the HTTP request. `BackgroundTasks` simply loses that attempt without a trace. A Celery task stays queued and gets retried per the worker's policy, so the user gets the email a bit later rather than never.

**5. A moment where intuition was wrong.** Chapter 16: the `db` fixture, with its in-memory connection and `monkeypatch`, seemed to isolate the tests fully from the real file on disk. It looked obvious, and the code looked correct on read.

Only a real run of the full test suite showed that `users_storage.py` was writing to the actual `taskman.db`. It had imported the function by name instead of the module as a whole (chapter 05).

Without running the tests, this bug would have stayed unnoticed. It doesn't show up reading the code, and it doesn't show up in the real running application, where there is no monkeypatch at all. It only shows up when you try to test, in isolation, code that had never been checked that rigorously before.

## Check yourself

1. Why doesn't today's `lifespan` in `taskman` need any code after `yield`, even though "graceful shutdown" in general means exactly that? What specifically about the storage layer's architecture makes this unnecessary right now?
2. Why does in-memory rate limiting on a single process stop working correctly the moment the app runs as several replicas? What does that imply about where the limit's state needs to live?
3. What's the fundamental difference between `asyncio.create_task` or FastAPI's `BackgroundTasks` and a full task broker like Celery? Which of the three properties settles the choice in a given case: surviving a restart, retrying on failure, or running on a separate machine?
4. Why does the `TaskStorage` protocol (chapter 10) mean moving to Postgres shouldn't require a single line of changes in `models/`, `cli/`, or `api/`?
5. State, in your own words, why "add X just in case we need it later" is generally a poor architectural heuristic. Draw on at least one example from the course itself, where that heuristic was explicitly rejected in favor of the opposite one.

<details>
<summary>Answers</summary>

1. Because the storage layer (chapters 08/12) opens a **separate** database connection for every individual call and closes it immediately when it's done. There is simply no long-lived, shared resource in the system that would need explicit closing when the process stops. No connection pool, no background worker, no file descriptor outliving one request. "Graceful shutdown = code after `yield`" is the general template for systems that **do** have such a resource. Our specific architectural choice doesn't, so the template formally applies, but has nothing to fill it with.
2. Each app replica is a separate process with its own memory. A request counter held in one replica's memory has no visibility into requests served by other replicas of the same service. Usually a limit needs to apply to a client regardless of which replica handled their request. So the counter's state can't live in one process's memory. It has to live in storage shared across all replicas. That is why Redis is the typical choice: a single source of truth every replica consults equally.
3. `asyncio.create_task` and `BackgroundTasks` live strictly within the lifetime of the process that started them. If the process restarts or crashes before the task finishes, the task is simply lost without a trace, and there is no retry. Celery stores tasks in a separate, persistent broker, Redis or RabbitMQ. They survive both the web server and any specific worker crashing. They can automatically retry per a configured policy on failure, and they run on a machine physically separate from the web server process. The choice depends on which of these three properties the specific piece of work actually needs. If it's lightweight, not critical if lost, and fits within one request's lifecycle, `BackgroundTasks` is enough. If even one of the three is genuinely required, a full broker is needed.
4. Because `TaskStorage` describes the **shape** of interacting with the storage layer, not how those methods are implemented underneath. The shape is which methods exist, and what types they take and return. Code in `cli/` and `api/` calls `db.add_task(...)`, `db.list_tasks(...)` and so on, never looking inside the concrete implementation `sqlite_storage.py`. Swap that implementation for a module talking to Postgres through a connection pool, and nothing changes for the calling code. The new module only has to satisfy the same protocol. That is the direct, practical payoff of an investment made in chapter 10, long before the question of switching databases ever came up.
5. General statement: infrastructure added "for later" carries a real cost today — more moving parts, more code to maintain, more surface for bugs. In exchange you get a benefit that may never materialize, and if it does, often not in the shape you predicted in advance. A concrete example from the course: chapter 14 explicitly declined to introduce the "one session per request" pattern for the database. That pattern is standard practice in many real FastAPI applications. The justification was precisely that none of the project's three endpoints at that point did more than one storage operation per call. The very reason that would justify the pattern's complexity simply didn't exist. The same move shows up in chapter 11. It explicitly demonstrated that `multiprocessing` isn't "better" than `threading` by default. It is only justified when there is a genuine need for parallelism on work bound by the CPU (central processing unit).

</details>

## Common mistake

Two opposite, equally real mistakes close out this course.

The first is seeing a checklist like this one and wanting to adopt all of it at once, whether or not it's needed now. Adding Postgres because "it's more serious". Standing up Celery because "that's what real projects do". Turning on rate limiting because "what if we need it".

Every one of these adds real operational complexity: more services to deploy, more configuration to keep in sync, more places something can break. At the project's current scale, none of that complexity buys anything back.

The whole course demonstrated the opposite principle. Chapter 05 said: don't over-complicate the package structure ahead of time. Chapter 14 said: don't introduce a session-per-request without a real multi-step transaction. Infrastructure gets introduced once its absence is already causing concrete, observable pain — not before.

The second mistake is the mirror image, and no less real. You get the project to a "it works" state, walk through a checklist like this one exactly once, and never come back to it. The matter feels permanently settled.

A pet project serving one user on one machine today might suddenly be serving a hundred tomorrow. That is exactly when every item that seemed irrelevant "for now" surfaces at once.

This checklist isn't a single formality to complete before the first deployment. It is a set of questions worth revisiting every time the project's real scale or context of use changes.

That is the same discipline as writing tests or running `mypy --strict`. Not because some formality demands it, but because that is precisely how this course, more than once, found real problems instead of imagined ones.
