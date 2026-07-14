# Тестирование FastAPI: pytest-asyncio, AsyncClient, полный набор тестов

## Теория

**`pytest-asyncio` — наконец, без обходного пути.** С главы 12 асинхронный код тестировался приёмом "обычная синхронная `def test_...():`, а внутри — вложенная `async def scenario(): ...` плюс `asyncio.run(scenario())`" — сознательно, чтобы не тащить лишнюю зависимость раньше времени. Теперь, когда тестов стало заметно больше и появился реальный асинхронный HTTP-клиент, приём становится тяжеловесным, и `pytest-asyncio` окупает себя:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

С `asyncio_mode = "auto"` тестовые функции можно писать прямо как `async def test_...(): await ...` — pytest сам оборачивает их в event loop, без `@pytest.mark.asyncio` над каждой:

```python
async def test_add_task(db):
    task = await db.add_task(user_id=1, text="Buy milk")
    assert task.id == 1
```

Fixtures тоже могут быть асинхронными — через `@pytest_asyncio.fixture` (а не обычный `@pytest.fixture`) с `async def` и `yield` внутри — та же самая генераторная механика (глава 06/07/09), просто теперь и сама fixture, и тест, для которого она готовит данные, выполняются в одном и том же event loop, без разрыва на "loop одной функции" и "loop другой".

**`TestClient` vs `httpx.AsyncClient` — когда какой.** `TestClient` (глава 15) — синхронная обёртка, достаточная почти всегда. `httpx.AsyncClient` с `ASGITransport(app=app)` нужен, когда тест сам должен оставаться корутиной — например, чтобы по-настоящему проверить конкурентную обработку нескольких запросов через `asyncio.gather` (глава 12), а не звать эндпоинты строго один за другим:

```python
from httpx import ASGITransport, AsyncClient

transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://test") as client:
    responses = await asyncio.gather(
        client.post("/tasks", json={"text": "A"}),
        client.post("/tasks", json={"text": "B"}),
    )
```

Неочевидный нюанс: `ASGITransport` сам по себе **не запускает** `lifespan` приложения (в отличие от `TestClient`, где `with TestClient(app) as client:` явно триггерит `startup`/`shutdown`) — если тесту действительно нужен реальный lifespan, его нужно запустить вручную через `async with app.router.lifespan_context(app):`. В нашем случае это не проблема: `db`-fixture сама создаёт схему БД напрямую, не полагаясь на lifespan приложения.

**Override зависимостей — два разных инструмента для двух разных целей.** `app.dependency_overrides[get_current_user] = fake_user` (глава 15) подходит, когда сама аутентификация не является предметом теста — быстро, без единого реального пароля или токена. Но для тестов **самой** аутентификации (регистрация, логин, отказ при неверном пароле) нужен обратный подход — настоящий пользователь, настоящий JWT, без всяких override:

```python
@pytest_asyncio.fixture
async def authenticated_client(client, db):
    user = await users_storage.create_user("alice", hash_password("secret123"))
    token = create_access_token(user.username)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

Оба подхода нужны одновременно, для разных частей набора тестов — override для "мне всё равно, кто залогинен", реальный токен для "я тестирую именно то, как логин работает".

### Параллели с JS/TS/Node:

- `pytest-asyncio` с `asyncio_mode = "auto"` ~ то, что Jest/Vitest делают "из коробки" — `test('...', async () => { await ... })` без отдельного объявления, что тест асинхронный.
- `httpx.AsyncClient` + `ASGITransport` ~ `supertest` в Node-экосистеме, только требует явного триггера lifespan-хуков, если они нужны — в отличие от некоторых JS-инструментов для тестирования, где хуки сервера запускаются автоматически при поднятии тестового инстанса.
- Override одной конкретной зависимости (`dependency_overrides`) ~ mocking одного конкретного провайдера/сервиса в Nest.js-тестах, а не мокирование всего HTTP-слоя целиком.

## Что добавляем в проект

Добавляем `pytest-asyncio` и переписываем тесты в его стиле — без вложенных `async def scenario(): ...; asyncio.run(...)`. Fixtures в `conftest.py` тоже становятся асинхронными (`@pytest_asyncio.fixture`), и рядом с уже знакомым `db` (одно общее in-memory SQLite-соединение на тест) появляются `client` (`httpx.AsyncClient` поверх `ASGITransport`) и `authenticated_client` (тот же клиент, но с настоящим JWT настоящего пользователя). `tests/test_auth_api.py` и `tests/test_tasks_api.py` дают полный набор API-тестов: регистрация, логин, доступ без токена, изоляция задач между пользователями, `404` на чужую/несуществующую задачу, и настоящий конкурентный тест через `asyncio.gather`.

По пути этот более полный набор тестов вскрывает реальный, скрытый с главы 15 баг в `storage/users_storage.py` — не гипотетический, а тот, что действительно ломает тесты при первом же прогоне.

## Практическое задание

1. Добавьте `pytest-asyncio` в `dev`-зависимости и `asyncio_mode = "auto"` в `[tool.pytest.ini_options]`.
2. Перепишите `db`-fixture в `conftest.py` как `@pytest_asyncio.fixture` (`async def` + `yield`), убрав обёртки `asyncio.run(...)` — fixture и код теста должны исполняться в одном event loop.
3. Добавьте `client`-fixture: `httpx.AsyncClient` с `ASGITransport(app=app)`, зависящую от `db` (чтобы схема БД была готова раньше первого запроса).
4. Добавьте `authenticated_client`-fixture: создаёт настоящего пользователя через `users_storage.create_user`, настоящий токен через `create_access_token`, и возвращает `client` с уже выставленным заголовком `Authorization`.
5. Перепишите `tests/test_storage.py`/`tests/test_cli.py` из главы 15 в стиле pytest-asyncio — уберите `asyncio.run(...)`, сделайте сами тестовые функции `async def`.
6. Напишите `tests/test_auth_api.py`: регистрация создаёт пользователя; повторная регистрация того же username — `400`; логин с верным паролем возвращает токен; логин с неверным паролем — `401`.
7. Напишите `tests/test_tasks_api.py`: защищённый роут без токена — `401`; создание и получение списка задач через `authenticated_client`; `404` (не что-то другое) для несуществующей задачи; полная изоляция между двумя разными пользователями (второй не видит задач первого); тест на конкурентность — три одновременных `POST /tasks` через `asyncio.gather`, каждый получает свой уникальный `id`.
8. Прогоните весь набор. Если какой-то тест падает с ошибкой о нарушении уникальности имени пользователя ещё до того, как тело теста вообще выполнилось — не спешите менять имена пользователей в тестах на разные. Разберитесь, почему `db`-fixture, дающая каждому тесту свежее in-memory соединение, не спасает от коллизии.

## Разбор решения

`pyproject.toml` (добавлена секция pytest + `pytest-asyncio`):

```toml
[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "mypy>=1.10", "httpx"]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.11"
strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
disallow_incomplete_defs = false
```

`tests/conftest.py` (новый стиль — асинхронные fixtures):

```python
from contextlib import asynccontextmanager

import aiosqlite
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from taskman.api.app import app
from taskman.auth import create_access_token, hash_password
from taskman.storage import TaskStorage, sqlite_storage, users_storage


@pytest_asyncio.fixture
async def db(monkeypatch):
    """A single in-memory SQLite connection shared for the duration of one test."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row

    @asynccontextmanager
    async def fake_db_connection():
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)
    await sqlite_storage.init_db()
    await users_storage.init_users_table()
    yield sqlite_storage
    await conn.close()


@pytest_asyncio.fixture
async def client(db: TaskStorage):
    """An httpx.AsyncClient talking directly to the ASGI app, no real network involved."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient, db: TaskStorage) -> AsyncClient:
    """A client pre-authenticated as a real, freshly-created user (real JWT, no override)."""
    user = await users_storage.create_user("alice", hash_password("secret123"))
    token = create_access_token(user.username)
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

`tests/test_auth_api.py` (новый файл):

```python
async def test_register_creates_a_user(client):
    response = await client.post(
        "/auth/register", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 201
    assert response.json()["username"] == "alice"


async def test_register_rejects_duplicate_username(client):
    payload = {"username": "alice", "password": "secret123"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 400


async def test_login_returns_a_token(client):
    await client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    response = await client.post(
        "/auth/token", data={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert len(response.json()["access_token"]) > 10


async def test_login_rejects_wrong_password(client):
    await client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    response = await client.post(
        "/auth/token", data={"username": "alice", "password": "WRONG"}
    )
    assert response.status_code == 401
```

`tests/test_tasks_api.py` (новый файл):

```python
import asyncio

from taskman.auth import create_access_token, hash_password
from taskman.storage import users_storage


async def test_protected_route_without_token_is_rejected(client):
    response = await client.get("/tasks")
    assert response.status_code == 401


async def test_create_and_list_task(authenticated_client):
    response = await authenticated_client.post(
        "/tasks", json={"text": "Buy milk", "priority": "high"}
    )
    assert response.status_code == 201
    assert response.json()["priority"] == "high"

    response = await authenticated_client.get("/tasks")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["text"] == "Buy milk"


async def test_mark_missing_task_done_returns_404(authenticated_client):
    response = await authenticated_client.patch("/tasks/999/done")
    assert response.status_code == 404


async def test_users_only_see_their_own_tasks(client, db):
    alice = await users_storage.create_user("alice", hash_password("secret123"))
    bob = await users_storage.create_user("bob", hash_password("hunter22"))
    alice_token = create_access_token(alice.username)
    bob_token = create_access_token(bob.username)

    client.headers["Authorization"] = f"Bearer {alice_token}"
    await client.post("/tasks", json={"text": "Alice task"})

    client.headers["Authorization"] = f"Bearer {bob_token}"
    response = await client.get("/tasks")
    assert response.json() == []


async def test_concurrent_requests_are_handled_independently(authenticated_client):
    responses = await asyncio.gather(
        authenticated_client.post("/tasks", json={"text": "Task A"}),
        authenticated_client.post("/tasks", json={"text": "Task B"}),
        authenticated_client.post("/tasks", json={"text": "Task C"}),
    )
    assert [r.status_code for r in responses] == [201, 201, 201]

    ids = sorted(r.json()["id"] for r in responses)
    assert ids == [1, 2, 3]
```

Теперь — про вопрос из задания 8. Первый реальный прогон полного набора падал так: `test_register_creates_a_user` (самый первый тест во всём наборе!) внезапно проваливался с `400` вместо `201`, будто пользователь `alice` уже существовал — хотя каждый тест получает своё собственное, свежее in-memory соединение через `db`-fixture. Причина оказалась в `storage/users_storage.py`, написанном ещё в главе 15:

```python
# ДО исправления:
from .sqlite_storage import db_connection   # <- имя связывается ОДИН РАЗ, при импорте

async def create_user(username: str, hashed_password: str) -> User:
    async with db_connection() as conn:   # <- всегда вызывает НАСТОЯЩУЮ, не подменённую функцию
        ...
```

`monkeypatch.setattr(sqlite_storage, "db_connection", fake_db_connection)` подменяет атрибут `db_connection` **на самом модуле** `sqlite_storage` — но `users_storage.py` импортировал имя `db_connection` напрямую (`from .sqlite_storage import db_connection`), создав в своём собственном пространстве имён отдельную, независимую привязку к оригинальной функции ещё во время импорта. Подмена атрибута на модуле `sqlite_storage` эту локальную привязку никак не трогает — `users_storage.create_user`/`get_user_by_username` продолжали писать и читать из **настоящего** файла `taskman.db` на диске, полностью в обход in-memory fixture. Именно поэтому `alice`, однажды созданная (даже в отдельном, более раннем ручном прогоне CLI или API), оставалась в реальном файле и мешала каждому следующему тесту.

Это ровно та ловушка с импортом конкретного имени вместо модуля, о которой предупреждала глава 05 (там же объяснялось, почему `cli/commands.py` импортирует `storage` как модуль, а не растаскивает функции по именам) — просто здесь она незаметно закралась в `users_storage.py` и не проявлялась, пока тесты не стали писать в БД по-настоящему требовательно. Исправление:

```python
# ПОСЛЕ исправления:
from . import sqlite_storage   # <- импортируем МОДУЛЬ целиком

async def create_user(username: str, hashed_password: str) -> User:
    async with sqlite_storage.db_connection() as conn:   # <- обращение по атрибуту КАЖДЫЙ РАЗ
        ...
```

Обращение `sqlite_storage.db_connection()` каждый раз идёт через атрибут модуля заново — и видит именно ту версию, что сейчас установлена на `sqlite_storage`, будь то оригинал или fixture-подмена.

Ключевые решения:

- Асинхронные fixtures (`@pytest_asyncio.fixture`) гарантируют, что fixture и тест исполняются в одном и том же event loop — никакой нужды угадывать, переживёт ли объект соединения переход между разными вызовами `asyncio.run()`, как приходилось делать с главы 12 по 15.
- `authenticated_client` строится поверх `client`, а не заменяет его — оба варианта (override и настоящий токен) сосуществуют в одном наборе тестов, каждый — для своей категории проверок.
- `ASGITransport` не запускает lifespan приложения сам по себе — `db`-fixture берёт инициализацию схемы на себя явно, и это ровно та причина, по которой отсутствие lifespan в тестах не является проблемой.
- Тест на конкурентность (`asyncio.gather` из трёх параллельных `POST`) — не просто "для галочки": он проверяет, что три одновременных запроса действительно получают три разных, не пересекающихся `id`, то есть что storage-слой (с его отдельным соединением на каждый вызов, глава 08/12) корректно ведёт себя под настоящей, а не последовательной, нагрузкой.

## Проверь себя

1. Чем `@pytest_asyncio.fixture` с `async def`/`yield` отличается от паттерна "синхронная fixture, внутри которой `asyncio.run(...)` создаёт нужный объект" (главы 12–15)? В чём конкретно был риск второго подхода, который решает первый?
2. Почему `ASGITransport(app=app)` сам по себе не запускает `lifespan` приложения, и почему в этом конкретном проекте это не создаёт проблем?
3. Опишите своими словами, почему `from .sqlite_storage import db_connection` в `users_storage.py` делает `monkeypatch.setattr(sqlite_storage, "db_connection", ...)` бесполезным именно для этого модуля, но не для `cli/commands.py`, который импортирует `storage` целиком.
4. Когда стоит использовать `app.dependency_overrides[get_current_user] = fake_user`, а когда — `authenticated_client` с настоящим токеном? Что каждый из подходов проверяет, а что — нет?
5. Тест на конкурентность создаёт три задачи через `asyncio.gather` и проверяет, что итоговые `id` — `[1, 2, 3]`, без повторов. Какое именно свойство storage-слоя это на самом деле проверяет?

<details>
<summary>Ответы</summary>

1. `@pytest_asyncio.fixture` гарантирует, что настройка (до `yield`), тело теста и очистка (после `yield`) исполняются в буквально одном и том же event loop, созданном и управляемом самим `pytest-asyncio`. Паттерн "синхронная fixture + `asyncio.run(...)` внутри" технически работал (что было эмпирически проверено ещё в главе 12), но полагался на то, что объекты вроде `aiosqlite.Connection`, созданные в одном, уже закрытом `asyncio.run()`-цикле, останутся пригодны для использования в *другом*, отдельном цикле, управляющем самим тестом — это везение конкретной реализации `aiosqlite`, а не гарантия, прописанная где-либо в документации `asyncio`. `pytest-asyncio` убирает саму необходимость полагаться на это везение.
2. `ASGITransport` — это просто транспорт, отправляющий ASGI-запросы напрямую в приложение как функцию, без обвязки, которая обычно занимается стартом/остановкой сервера (в отличие от `TestClient`, чей `with`-блок явно вызывает `lifespan`-протокол). В этом проекте это не проблема, потому что `db`-fixture уже создаёт нужные таблицы (`tasks`, `users`) напрямую, не через `lifespan` приложения — эквивалентная инициализация происходит, просто по другому пути.
3. `from .sqlite_storage import db_connection` в `users_storage.py` создаёт **отдельную, независимую** привязку имени `db_connection` в пространстве имён самого `users_storage` в момент импорта — эта привязка ссылается на конкретный объект функции, существовавший на тот момент, и никак не связана с последующими изменениями атрибута `db_connection` на самом модуле `sqlite_storage`. `cli/commands.py`, наоборот, импортирует `from ..storage import db` — весь МОДУЛЬ (точнее, объект `sqlite_storage`, на который указывает `db`), и обращается к его функциям через `db.add_task(...)` — то есть каждый раз заново ищет атрибут на объекте модуля в момент вызова, а не полагается на привязку, зафиксированную раз и навсегда при импорте.
4. `app.dependency_overrides[get_current_user] = fake_user` уместен, когда сама аутентификация — не предмет проверки: тест про фильтрацию задач по статусу не должен зависеть от того, работает ли логин. `authenticated_client` с настоящим, честно выпущенным токеном нужен ровно тогда, когда тестируется сам механизм аутентификации или что-то, зависящее от его реального прохождения (например, что просроченный или подделанный токен корректно отклоняется) — override в этом случае бесполезен, потому что он вообще обходит код, который нужно проверить.
5. Этот тест проверяет, что при параллельном выполнении нескольких `add_task` через разные, независимо открываемые соединения (глава 08/12: каждый вызов открывает своё собственное соединение к SQLite) присвоение `id` через `AUTOINCREMENT` остаётся корректным и без коллизий — то есть что конкурентный доступ к одной и той же таблице не приводит к тому, что два запроса случайно получат один и тот же `id`, и не роняет ни один из трёх запросов. Это прямая, практическая проверка того, что теоретические гарантии SQLite (сериализация записи на уровне движка) действительно выполняются в связке с нашим конкретным способом открывать соединение на каждый вызов, а не только в теории.

</details>

## Частая ошибка

Самая ценная (и самая незаметная) ошибка этой главы — не гипотетическая, а реально произошедшая при построении полного набора тестов: импортировать конкретное имя функции из модуля (`from .sqlite_storage import db_connection`) вместо самого модуля, в коде, который позже понадобится подменять через `monkeypatch`. Разработчик, уже видевший `monkeypatch.setattr(module, "name", fake)` в предыдущих главах, разумно ожидает, что подмена сработает для **любого** кода, который в итоге вызывает `name()` — но подмена работает только для кода, которое обращается к `name` **через атрибут модуля** (`module.name()`) в момент вызова, а не для кода, зафиксировавшего собственную, локальную привязку к функции ещё на этапе импорта. Ошибка не проявляется сразу — модуль прекрасно работает в реальном приложении (там нет никакого monkeypatch, всё обращается к настоящей функции) — и всплывает только тогда, когда кто-то попытается протестировать этот код изолированно, причём проявляется она не как явная ошибка импорта, а как необъяснимая утечка состояния между тестами (в нашем случае — нарушение уникальности имени пользователя там, где по логике теста пользователь должен создаваться с нуля).

Вторая типичная ошибка — установить `httpx.AsyncClient` с `ASGITransport` и решить, что раз он "просто работает" с обычными запросами, то и `lifespan`-хуки приложения (создание таблиц, подключение к внешним сервисам при старте) тоже выполнились где-то по дороге. Без явного `async with app.router.lifespan_context(app):` этого не происходит вообще — если тестовая инфраструктура не заботится об инициализации состояния каким-то другим способом (как в этом проекте — через `db`-fixture), первый же запрос в тесте упадёт с ошибкой вроде "таблица не существует", и первая мысль будет "наверное, я неправильно написал SQL", а не "я забыл, что `lifespan` в тестах не запускается сам по себе".
