# Асинхронные паттерны

## Callback Hell — почему это структурная проблема, а не эстетическая

Callback hell часто объясняют как "некрасивый код с глубокой вложенностью". Это поверхностно. Настоящая проблема — **инверсия управления (inversion of control)**.

Когда вы передаёте callback в функцию, вы отдаёте ей контроль над частью своей программы. Вы больше не контролируете:

```js
// Вы не можете гарантировать, что thirdPartyApi:
thirdPartyApi.fetchData(userId, function(err, data) {
  // 1. Вызовет callback ровно один раз (а не 0 или 2+ раз)
  // 2. Не вызовет его синхронно (раньше, чем вы ожидаете)
  // 3. Не вызовет его и с err, и с data одновременно
  // 4. Не проглотит брошенный внутри exception
  // 5. Не вызовет его через несколько секунд или никогда
});
```

Кроме IoC, есть структурные проблемы с компоновкой:

```js
// Задача: получить user, потом его orders, потом первый product из orders
// Каждый шаг зависит от результата предыдущего

fetchUser(userId, function(err, user) {
  if (err) return handleError(err);   // обработка ошибки — вручную везде

  fetchOrders(user.id, function(err, orders) {
    if (err) return handleError(err); // дублирование

    fetchProduct(orders[0].productId, function(err, product) {
      if (err) return handleError(err); // ещё раз

      // Наконец-то данные — но мы на третьем уровне вложенности.
      // Хотите добавить четвёртый шаг? Ещё один уровень.
      // Хотите параллельно запустить несколько запросов? Удачи.
      console.log(product);
    });
  });
});
```

**Структурные проблемы:**
- Обработка ошибок — ручная на каждом уровне, легко пропустить
- Возврат значений невозможен (callback — не return)
- Параллельные операции требуют счётчиков вручную
- Код читается не сверху вниз, а снаружи внутрь

## Promise: внутренняя механика

### Состояния и внутренние слоты

Promise — объект с тремя внутренними слотами:

```txt
Promise {
  [[PromiseState]]            → 'pending' | 'fulfilled' | 'rejected'
  [[PromiseResult]]           → undefined | value | reason
  [[PromiseFulfillReactions]] → список reaction-объектов
  [[PromiseRejectReactions]]  → список reaction-объектов
}
```

Переход состояний — **односторонний и необратимый**:

```txt
pending ──→ fulfilled (с value)
       └──→ rejected  (с reason)
```

После перехода `[[PromiseState]]` меняется один раз — повторные вызовы `resolve`/`reject` игнорируются:

```js
const p = new Promise((resolve, reject) => {
  resolve(1);
  resolve(2);   // игнорируется
  reject('err'); // игнорируется
});

p.then(v => console.log(v)); // 1
```

### Функции `resolve` и `reject`

При `new Promise(executor)` движок создаёт две функции, замкнутые на объект промиса:

```txt
resolve(value):
  1. Если [[PromiseState]] !== 'pending' → выход (уже settled)
  2. Если value — thenable (имеет .then метод):
       → Promise Resolution Procedure: подписаться на value.then
       (промис "следует" за переданным thenable)
  3. Иначе:
       [[PromiseState]] = 'fulfilled'
       [[PromiseResult]] = value
       → Добавить все [[PromiseFulfillReactions]] в Microtask Queue

reject(reason):
  1. Если [[PromiseState]] !== 'pending' → выход
  2. [[PromiseState]] = 'rejected'
     [[PromiseResult]] = reason
     → Добавить все [[PromiseRejectReactions]] в Microtask Queue
```

**Promise Resolution Procedure** — механизм, который позволяет чейнинг работать с любым thenable, а не только с Promise:

```js
// Это работает, потому что resolve вызывает Promise Resolution Procedure:
Promise.resolve({
  then(resolve) { resolve(42); } // произвольный thenable
}).then(v => console.log(v)); // 42
```

### Механика `.then()` — каждый вызов создаёт новый Promise

```js
const p1 = Promise.resolve(1);

const p2 = p1.then(v => v + 1); // новый Promise
const p3 = p2.then(v => v * 2); // ещё новый Promise

// p1, p2, p3 — три отдельных объекта Promise
// p1 fulfilled(1) → p2 fulfilled(2) → p3 fulfilled(4)
```

Что определяет состояние нового промиса:

```txt
p2 = p1.then(onFulfilled, onRejected)

Если p1 fulfilled:
  → вызвать onFulfilled(value)
  → если вернул thenable → p2 следует за ним
  → если вернул обычное значение → p2 fulfilled(value)
  → если бросил исключение → p2 rejected(error)

Если p1 rejected:
  → если есть onRejected → вызвать onRejected(reason)
     (аналогичная логика для результата)
  → если onRejected нет → p2 rejected(reason) (пробрасывается дальше)
```

```js
Promise.reject(new Error('oops'))
  .then(v => v * 2)          // onRejected нет → ошибка пробрасывается
  .then(v => v + 1)          // тоже нет → пробрасывается
  .catch(err => {
    console.log(err.message); // 'oops' — поймано здесь
    return 'recovered';
  })
  .then(v => console.log(v)); // 'recovered' — .catch восстановил цепочку
```

## `async/await` — что это концептуально компилируется в

`async function` всегда возвращает Promise. `await` приостанавливает выполнение генераторо-подобной функции и возобновляет её как callback Promise.

```js
// async/await версия:
async function fetchUserData(id) {
  const user = await fetchUser(id);
  const orders = await fetchOrders(user.id);
  return { user, orders };
}

// Концептуальный эквивалент через Promise (упрощённо):
function fetchUserData(id) {
  return fetchUser(id).then(user => {
    return fetchOrders(user.id).then(orders => {
      return { user, orders };
    });
  });
}
```

С обработкой ошибок:

```js
// async/await:
async function safeFetch(url) {
  try {
    const data = await fetch(url);
    return await data.json();
  } catch (err) {
    console.error('Failed:', err);
    return null;
  }
}

// Концептуальный эквивалент:
function safeFetch(url) {
  return fetch(url)
    .then(data => data.json())
    .catch(err => {
      console.error('Failed:', err);
      return null;
    });
}
```

**Важная деталь**: каждый `await` добавляет по меньшей мере **одну** микрозадачу в очередь. Несколько последовательных `await` на уже resolved промисах всё равно добавляют микрозадачи — это влияет на порядок выполнения.

```js
// Predict the output:
async function a() {
  console.log('a1');
  await Promise.resolve();
  console.log('a2');
  await Promise.resolve();
  console.log('a3');
}

async function b() {
  console.log('b1');
  await Promise.resolve();
  console.log('b2');
}

a();
b();
console.log('sync');
```

<details>
<summary>Разбор</summary>

```txt
Синхронно:
  a(): 'a1' → await → приостановлена
  b(): 'b1' → await → приостановлена
  'sync'

Microtask Queue после синхронного кода: [resumeA, resumeB]

  resumeA: 'a2' → await → приостановлена → добавляет resumeA2
  Microtask Queue: [resumeB, resumeA2]

  resumeB: 'b2' → b() завершена
  Microtask Queue: [resumeA2]

  resumeA2: 'a3' → a() завершена

Итог: a1, b1, sync, a2, b2, a3
```

Ключевой момент: каждый `await` делает "паузу" — другие задачи из очереди успевают выполниться между `await` внутри одной async-функции.

</details>

## Сравнение обработки ошибок

### Callbacks — проблемы

```js
// Конвенция err-first — но это только конвенция, не гарантия:
fs.readFile('file.txt', (err, data) => {
  if (err) { /* обработать */ return; }
  // data здесь

  // ❌ Если код внутри callback бросает исключение —
  // оно НЕ перехватывается снаружи никаким try/catch
  JSON.parse(data); // SyntaxError → уйдёт в глобальный обработчик (или crash)
});

try {
  fs.readFile('file.txt', callback); // try/catch здесь БЕСПОЛЕЗЕН —
} catch (e) {                        // исключение из callback произойдёт позже
  // сюда никогда не придём из-за async ошибки
}
```

### Promises — улучшения и ловушки

```js
fetch('/api/data')
  .then(res => res.json())
  .then(data => processData(data))
  .catch(err => console.error(err)); // поймает ошибки из всей цепочки

// ❌ Ловушка: возвращать промис из then без return
fetch('/api/data')
  .then(res => {
    fetch('/api/other'); // ← без return! Этот промис "потерян"
  })
  .then(data => console.log(data)) // data = undefined
  .catch(err => console.error(err)); // НЕ поймает ошибки из fetch('/api/other')

// ✅ Правильно:
fetch('/api/data')
  .then(res => fetch('/api/other')) // return неявный в стрелке
  .then(res => res.json())
  .catch(err => console.error(err));
```

```js
// ❌ Unhandled Promise Rejection:
async function dangerous() {
  throw new Error('boom');
}
dangerous(); // Error не перехвачена — UnhandledPromiseRejection

// ✅ Обязательно await или .catch():
await dangerous().catch(err => console.error(err));
```

### async/await — чище, но свои подводные камни

```js
// ✅ try/catch работает естественно:
async function loadData() {
  try {
    const user = await fetchUser();
    const orders = await fetchOrders(user.id);
    return orders;
  } catch (err) {
    // Поймает отклонение из fetchUser ИЛИ fetchOrders
    console.error(err);
    throw err; // перебросить, если нужно
  } finally {
    // Выполнится в любом случае (как обычный finally)
    cleanup();
  }
}

// ❌ Классическая ошибка: await в цикле = последовательно, а не параллельно
async function sequential() {
  const results = [];
  for (const id of ids) {
    results.push(await fetchItem(id)); // каждый запрос ждёт предыдущего!
  }
  return results;
}

// ✅ Параллельно через Promise.all:
async function parallel() {
  return Promise.all(ids.map(id => fetchItem(id)));
}
```

## Promise Combinators — точная семантика каждого

### `Promise.all` — все или ничего

```js
// Resolves: когда ВСЕ промисы fulfilled → массив значений (в порядке входных)
// Rejects:  на ПЕРВОМ rejected → с его reason, остальные игнорируются

const [user, orders, products] = await Promise.all([
  fetchUser(id),
  fetchOrders(id),
  fetchProducts(id),
]);

// Ловушка: если один реджектится, уже resolved промисы "потеряны"
// Они выполнились, но их результаты недоступны
Promise.all([
  Promise.resolve(1),
  Promise.reject('error'),
  Promise.resolve(3),
]).catch(err => console.log(err)); // 'error'
// Значения 1 и 3 недоступны
```

### `Promise.allSettled` — все результаты, независимо от исхода (ES2020)

```js
// ВСЕГДА resolves (никогда не rejects)
// Результат: массив объектов { status, value | reason }

const results = await Promise.allSettled([
  fetchUser(id),       // может упасть
  fetchOrders(id),     // может упасть
  fetchProducts(id),   // может упасть
]);

results.forEach(result => {
  if (result.status === 'fulfilled') {
    console.log('OK:', result.value);
  } else {
    console.log('FAIL:', result.reason);
  }
});
// Подходит, когда нужны все результаты независимо от частичных ошибок
```

### `Promise.race` — первый финишировавший, любой исход

```js
// Resolves OR rejects: как только ПЕРВЫЙ промис settled (fulfilled или rejected)

// Timeout pattern:
function withTimeout(promise, ms) {
  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Timeout')), ms)
  );
  return Promise.race([promise, timeout]);
}

await withTimeout(fetchSlowData(), 3000);
// Если fetchSlowData займёт > 3s → rejection с 'Timeout'

// Ловушка: "проигравшие" промисы продолжают выполняться —
// Promise.race не отменяет их, только игнорирует их результаты
```

### `Promise.any` — первый успешный (ES2021)

```js
// Resolves: когда ПЕРВЫЙ fulfilled → с его value
// Rejects:  только когда ВСЕ rejected → AggregateError со списком всех reason

// Паттерн: запросить данные из нескольких источников, взять быстрейший
const data = await Promise.any([
  fetchFromCDN1('/data'),
  fetchFromCDN2('/data'),
  fetchFromCDN3('/data'),
]);
// Вернёт результат первого успешного CDN

// Все провалились:
Promise.any([
  Promise.reject('err1'),
  Promise.reject('err2'),
]).catch(err => {
  console.log(err instanceof AggregateError); // true
  console.log(err.errors); // ['err1', 'err2']
});
```

### Сводная таблица

```txt
Комбинатор        Resolves                 Rejects
──────────────────────────────────────────────────────────
Promise.all       Все fulfilled            Первый rejected
Promise.allSettled Всегда (никогда reject) —
Promise.race      Первый settled           Первый settled
Promise.any       Первый fulfilled         Все rejected → AggregateError
```

## Predict the output — async/await + Promise combinators

```js
async function delay(ms, value) {
  await new Promise(resolve => setTimeout(resolve, ms));
  return value;
}

async function main() {
  console.log('start');

  const [a, b] = await Promise.all([
    delay(100, 'A'),
    delay(50, 'B'),
  ]);
  console.log(a, b); // ?

  try {
    await Promise.any([
      Promise.reject('err1'),
      Promise.reject('err2'),
    ]);
  } catch (e) {
    console.log(e instanceof AggregateError, e.errors); // ?
  }

  const result = await Promise.race([
    delay(200, 'slow'),
    delay(10, 'fast'),
  ]);
  console.log(result); // ?

  console.log('end');
}

main();
```

<details>
<summary>Ответ</summary>

```
start
A B            // Promise.all ждёт оба (100ms), порядок = порядок входных
true ['err1', 'err2']  // AggregateError, все rejection reasons в .errors
fast           // Promise.race → быстрейший (10ms)
end
```

`Promise.all` возвращает значения **в порядке входного массива**, а не в порядке завершения. `delay(100, 'A')` медленнее, но `a` = 'A'.

</details>

## Паттерны обработки ошибок в реальном коде

```js
// Паттерн 1: оборачивание в [error, data] — Go-стиль
async function tryCatch(promise) {
  try {
    return [null, await promise];
  } catch (err) {
    return [err, null];
  }
}

const [err, user] = await tryCatch(fetchUser(id));
if (err) { /* обработать */ return; }
// user гарантированно не null

// Паттерн 2: цепочка .catch на каждом шаге для разной обработки
await fetchUser(id)
  .catch(err => { throw new UserNotFoundError(err.message); })
  .then(user => fetchOrders(user.id))
  .catch(err => { throw new OrdersUnavailableError(err.message); });

// Паттерн 3: AbortController для отмены (подробно в статье 12)
const controller = new AbortController();
setTimeout(() => controller.abort(), 5000);

try {
  const res = await fetch('/api/data', { signal: controller.signal });
} catch (err) {
  if (err.name === 'AbortError') console.log('Cancelled');
  else throw err;
}
```

## Связь с другими темами

```txt
[Event Loop]          — Promise.then всегда добавляет микрозадачу;
                         порядок выполнения определяется Microtask Queue
[Генераторы]          — async/await — это генераторы + автоматический runner;
                         детально разобрано в следующей статье
[Современный JS]      — AbortController для отмены промисов — в статье 12
[Node.js потоки]      — async iteration над streams через for-await-of
```

## Типичные ошибки на интервью

- **"Callback hell — это про вложенность"** — главная проблема не визуальная, а структурная: инверсия управления, невозможность возвращать значения, ручная обработка ошибок на каждом уровне.

- **"Promise.all падает, если один Promise медленный"** — нет. `Promise.all` ждёт ВСЕХ. Падает (`reject`) при первом rejected. Медленный, но не упавший Promise просто замедлит `Promise.all`.

- **"async/await не Promise"** — `async function` всегда возвращает Promise. `await` — это `.then()`. Они полностью интероперабельны.

- **"Ошибки в async функции обработает внешний try/catch"** — нет, если функцию не `await`. `asyncFn()` без `await` — это промис в полёте; внешний `try/catch` его не поймает.

- **Не знать разницу `Promise.race` vs `Promise.any`** — `race` завершается на ПЕРВОМ settled (включая rejection); `any` завершается на ПЕРВОМ fulfilled. `race` с одним rejecting промисом сразу реджектится; `any` — нет.

- **"Promise.allSettled появился вместе с Promise"** — нет, ES2020. `Promise.any` — ES2021. На интервью важно знать что из этого может быть недоступно в старых окружениях.

- **await в цикле = sequential** — классическая ошибка производительности. Если итерации независимы — всегда `Promise.all(items.map(...))`.
