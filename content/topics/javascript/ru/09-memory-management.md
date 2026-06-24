# Управление памятью

## Жизненный цикл памяти в JS

Независимо от языка, память проходит три стадии:

```txt
1. Аллокация   — движок выделяет память при создании значения
2. Использование — чтение и запись данных
3. Освобождение — GC возвращает память, когда объект недостижим
```

В JS аллокация и использование происходят явно (вы пишете `{}`, `[]`, `new`), а освобождение — **автоматически через сборщик мусора**. Утечка памяти происходит тогда, когда объект, который больше не нужен программе, остаётся **достижимым** с точки зрения GC — то есть программа случайно удерживает на него ссылку.

## Как работает GC в V8 — концептуальный уровень

### Поколенческая гипотеза

V8 использует **поколенческий сборщик мусора**, основанный на наблюдении: **большинство объектов умирают молодыми**. Временные объекты (результаты вычислений, промежуточные данные) живут очень недолго. Долгоживущие объекты (DOM, кеши, синглтоны) — редкость.

Это позволяет разделить кучу на два поколения и применять разные стратегии:

```txt
V8 Heap
├── Young Generation (Новое поколение) — ~1–8 MB
│   ├── Nursery (Семь простанство) — новые аллокации
│   └── Intermediate — пережили один Minor GC
└── Old Generation (Старое поколение) — сотни MB
    ├── Old Space — объекты, пережившие несколько Minor GC
    ├── Code Space — скомпилированный код
    └── Large Object Space — объекты > порога (не перемещаются)
```

### Minor GC (Scavenge) — быстрый, частый

Работает только с Young Generation. Алгоритм **Cheney's copying**:

```txt
1. Разделить Young Generation на два полупространства (From, To)
2. Аллокировать новые объекты в From-пространство
3. Когда From заполнено — запустить Minor GC:
   a. От GC roots обойти граф объектов в From-пространстве
   b. Живые объекты скопировать в To-пространство (компактно)
   c. Объекты, пережившие 2 Minor GC → переместить в Old Generation
   d. From-пространство целиком считается свободным (не надо "чистить" — просто переключаем роли)
4. Поменять From и To местами
```

**Почему это быстро**: не нужно обходить весь Old Generation. Объекты, умершие молодыми, просто не копируются — их память освобождается автоматически при переключении ролей.

### Major GC (Mark-Sweep-Compact) — медленный, редкий

Запускается когда Old Generation близок к порогу. Три фазы:

```txt
Фаза 1: Маркировка (Mark)
  Начиная с GC Roots, обойти граф объектов и отметить все достижимые.
  GC Roots:
    - Глобальные переменные (window, globalThis)
    - Стек вызовов (локальные переменные активных функций)
    - Живые замыкания (Environment Records, на которые ссылаются живые функции)
    - Внутренние ссылки V8

Фаза 2: Удаление (Sweep)
  Пройти по кучe. Объекты без метки — недостижимы → их память возвращается в пул.

Фаза 3: Уплотнение (Compact) — опционально
  Переместить живые объекты плотно вместе → устранить фрагментацию.
  Дорого: нужно обновить все ссылки на перемещённые объекты.
```

### Инкрементальная и конкурентная маркировка (Orinoco)

Полная маркировка всего Old Generation — это пауза главного потока (stop-the-world). V8 применяет несколько техник для снижения пауз:

```txt
Incremental marking  — маркировка делается маленькими порциями между задачами JS
Concurrent marking   — маркировка выполняется в фоновых потоках параллельно с JS
Lazy sweeping        — удаление неживых объектов происходит постепенно
```

В продакшн Node.js-приложениях пики GC-пауз видны как всплески latency. `--trace-gc` флаг показывает паузы в логах.

## Что вызывает утечки памяти в JS

Утечка = объект недостижим **логически** (программа больше его не использует), но достижим **для GC** (есть живая ссылка). GC не умеет читать намерения разработчика — только граф ссылок.

### 1. Отсоединённые DOM-узлы

```js
// ❌ Классическая утечка:
let detachedTree;

function createTree() {
  const root = document.createElement('div');
  for (let i = 0; i < 100; i++) {
    root.appendChild(document.createElement('span'));
  }
  detachedTree = root; // глобальная ссылка удерживает всё дерево
}

createTree();
document.body.appendChild(detachedTree);
document.body.removeChild(detachedTree);
// Узлы удалены из DOM, но detachedTree всё ещё жива → 101 элемент в памяти
detachedTree = null; // ✅ явно разрываем ссылку
```

Типичный паттерн: event listeners, созданные на DOM-элементах и хранимые в замыканиях, удерживают элементы в памяти после их удаления:

```js
function setupButton() {
  const button = document.getElementById('btn');
  const cache = new Array(100_000).fill('data');

  button.addEventListener('click', () => {
    console.log(cache.length); // замыкается на cache
  });

  // Позже где-то:
  button.remove(); // удалили из DOM
  // Но listener с cache всё ещё жив, если button доступен в другом месте
  // или listener не удалён через removeEventListener
}
```

**Решение**: `removeEventListener` при удалении элемента, или `AbortController`:

```js
const controller = new AbortController();
button.addEventListener('click', handler, { signal: controller.signal });

// При уничтожении:
controller.abort(); // автоматически удаляет все listeners с этим сигналом
```

### 2. Забытые таймеры и интервалы

```js
class DataPoller {
  constructor() {
    this.data = new Array(50_000).fill('payload');
    // ❌ setInterval удерживает callback, callback замыкается на this,
    //    this удерживает data — весь граф живёт пока таймер жив
    this.interval = setInterval(() => {
      this.refresh();
    }, 1000);
  }

  refresh() { /* ... */ }

  destroy() {
    clearInterval(this.interval); // ✅ обязательно при teardown
    this.data = null;
  }
}

// Особенно опасно в React-компонентах:
useEffect(() => {
  const interval = setInterval(tick, 1000);
  return () => clearInterval(interval); // cleanup function — обязательна
}, []);
```

### 3. Накапливающиеся Map/Set без очистки

```js
// ❌ Неограниченный кеш — утечка пропорциональна числу уникальных аргументов
const cache = new Map();

function memoize(key, fn) {
  if (!cache.has(key)) {
    cache.set(key, fn(key));
  }
  return cache.get(key);
}

// Если key — объекты (например, request объекты) и они всё новые —
// Map удерживает все из них бесконечно
```

### 4. Замыкания, удерживающие большие scope

Разобрано в [Замыкания: механика]. Ключевое: несколько замыканий на одном ER в V8 создают общий Context object, удерживающий все переменные, используемые хотя бы одним из них.

```js
function problem() {
  const huge = new Array(1_000_000).fill(0); // 8MB
  const small = 'ok';

  const a = () => huge; // использует huge
  const b = () => small; // использует только small, но...
  // a и b создаются в одном scope → общий Context → huge удерживается пока жива b
  return b; // возвращаем только b — но huge не будет собран
}
```

## WeakMap, WeakSet, WeakRef — зачем они нужны

### Проблема обычного Map/Set

`Map` удерживает **сильную ссылку** на ключи и значения. Если вы кешируете данные, ассоциированные с DOM-узлами или объектами запросов, Map предотвратит их GC:

```js
const nodeData = new Map();

function process(domNode) {
  nodeData.set(domNode, computeExpensiveMetadata(domNode));
}

// После удаления domNode из DOM:
document.body.removeChild(domNode);
// domNode всё ещё жив! Map удерживает сильную ссылку на него как на ключ
// nodeData.delete(domNode) — нужна явная очистка, которую легко забыть
```

### WeakMap — слабые ключи

`WeakMap` удерживает ключи **слабо** — если на ключ-объект нет других ссылок, GC может его собрать и автоматически удалит запись из WeakMap.

```txt
WeakMap:
  ✅ Ключи — только объекты (не примитивы)
  ✅ Ключи удерживаются слабо (не препятствуют GC)
  ✅ Автоматическая очистка при сборе ключа GC
  ❌ Не итерируется (.forEach, .keys(), .values() — отсутствуют)
  ❌ Нет .size
  ❌ Значения удерживаются сильно (пока жив ключ)
```

```js
// ✅ Кеш метаданных для DOM-узлов — не препятствует GC
const metadata = new WeakMap();

function attachMetadata(node, data) {
  metadata.set(node, data);
}

function getMetadata(node) {
  return metadata.get(node);
}

// Когда node удаляется из DOM и других ссылок нет —
// GC собирает node + WeakMap автоматически удаляет запись
// Явной очистки не требуется
```

**Приватные данные класса через WeakMap** (паттерн до `#` private fields):

```js
const _private = new WeakMap();

class SecureAccount {
  constructor(balance) {
    _private.set(this, { balance, transactions: [] });
  }

  deposit(amount) {
    const data = _private.get(this);
    data.balance += amount;
    data.transactions.push({ type: 'deposit', amount });
  }

  get balance() {
    return _private.get(this).balance;
  }
}

const acc = new SecureAccount(100);
acc.deposit(50);
acc.balance; // 150
// _private.get(acc) — недоступно снаружи модуля (WeakMap — closure-private)
// При уничтожении acc — GC собирает и acc, и запись в WeakMap
```

### WeakSet — слабые значения

`WeakSet` удерживает объекты слабо. Используется для отслеживания "посещённости" объектов без предотвращения GC:

```js
// Отслеживать "обработанные" запросы без удержания их в памяти:
const processedRequests = new WeakSet();

function handleRequest(request) {
  if (processedRequests.has(request)) {
    return; // уже обработан
  }
  processedRequests.add(request);
  // ... обработка
}

// Когда request выходит из scope — WeakSet не удерживает его
```

```js
// Защита от циклов при рекурсивном обходе объектов:
function deepClone(obj, seen = new WeakSet()) {
  if (seen.has(obj)) return '[Circular]';
  if (typeof obj !== 'object' || obj === null) return obj;

  seen.add(obj);
  const clone = Array.isArray(obj) ? [] : {};
  for (const key of Object.keys(obj)) {
    clone[key] = deepClone(obj[key], seen);
  }
  return clone;
}
```

### WeakRef (ES2021) — слабая ссылка на объект

`WeakRef` позволяет хранить ссылку на объект, **не препятствуя его GC**. `.deref()` возвращает объект или `undefined` (если собран):

```js
// ✅ Кеш, который "сам очищается" при нехватке памяти:
class Cache {
  #store = new Map();

  set(key, value) {
    this.#store.set(key, new WeakRef(value));
  }

  get(key) {
    const ref = this.#store.get(key);
    if (!ref) return undefined;

    const value = ref.deref();
    if (value === undefined) {
      this.#store.delete(key); // прибираем мёртвую запись
      return undefined;
    }
    return value;
  }
}
```

**Критически важно**: спецификация НЕ гарантирует когда и будет ли вообще собран объект с WeakRef. GC — деталь реализации. Нельзя полагаться на WeakRef для бизнес-логики или гарантий. Используйте только там, где потеря значения является допустимым поведением (кеши, оптимизации).

```js
// ❌ Неправильное использование:
const ref = new WeakRef(importantData);
// ... много операций ...
const data = ref.deref();
if (data === undefined) {
  throw new Error('Critical data was GC\'d'); // это неверная архитектура
}
```

### FinalizationRegistry (ES2021) — callback при сборке GC

Позволяет зарегистрировать callback, который вызовется (возможно) при сборке объекта GC:

```js
const registry = new FinalizationRegistry((heldValue) => {
  // heldValue — то, что передали при регистрации (не сам объект!)
  console.log(`Object with id ${heldValue} was GC'd`);
  cleanupExternalResource(heldValue);
});

function createTracked(id) {
  const obj = { id, data: new Array(10_000).fill(0) };

  registry.register(
    obj,         // отслеживаемый объект (слабая ссылка)
    id,          // heldValue — передаётся в callback (не должен ссылаться на obj!)
    obj          // токен для отмены регистрации (опционально)
  );

  return obj;
}

// Можно отменить регистрацию:
const obj = createTracked('user-42');
registry.unregister(obj); // отменить callback для этого объекта
```

**Ограничения `FinalizationRegistry`**:
- Callback **не гарантирован** — спецификация допускает, что GC может не вызвать его
- Callback вызывается **асинхронно**, не в момент сборки
- Нельзя воскресить объект в callback — нет доступа к самому объекту
- Не использовать для критической логики очистки

## Инструменты диагностики утечек

```js
// Node.js: мониторинг использования памяти
const { heapUsed, heapTotal, external, rss } = process.memoryUsage();

// Проверка роста кучи под нагрузкой:
function checkMemoryLeak(fn, iterations = 1000) {
  const before = process.memoryUsage().heapUsed;
  for (let i = 0; i < iterations; i++) fn();

  // Принудительный GC (только с --expose-gc флагом):
  if (global.gc) global.gc();

  const after = process.memoryUsage().heapUsed;
  const delta = after - before;
  console.log(`Memory delta: ${(delta / 1024 / 1024).toFixed(2)} MB`);
  return delta;
}
```

В браузере: Chrome DevTools → Memory → Heap Snapshot. Сравнить два снимка (до/после нагрузки). Объекты, оставшиеся в разнице — кандидаты на утечку. Поиск "Detached HTMLElement" — верный признак детачед-DOM утечки.

## Predict the output — WeakRef + FinalizationRegistry

```js
let obj = { name: 'tracked' };
const ref = new WeakRef(obj);
const registry = new FinalizationRegistry(name => {
  console.log(`Cleaned up: ${name}`);
});

registry.register(obj, obj.name);

console.log(ref.deref()?.name); // ?

obj = null; // убираем сильную ссылку

// Сразу после:
console.log(ref.deref()?.name); // ?

// После GC (неопределённое время):
// Cleaned up: tracked  ← может быть вызвано, а может и нет
```

<details>
<summary>Ответ</summary>

```
'tracked'    // deref() возвращает объект, пока он жив
'tracked'    // объект ещё НЕ собран — GC не гарантирует немедленную сборку
             // (даже после obj = null, GC может не запуститься сразу)

// В момент реального GC (неопределённое время спустя):
// 'Cleaned up: tracked'  — но это не гарантировано спецификацией
```

Ключевой урок: `obj = null` делает объект *eligible* для GC, но не гарантирует немедленную сборку. `ref.deref()` сразу после `obj = null` вполне может вернуть объект — GC ещё не запустился.

</details>

## Связь с другими темами

```txt
[Замыкания]           — замыкания на общий ER удерживают все переменные scope;
                         механизм shared Context в V8 подробно в статье 03
[Прокси]              — Proxy удерживает target сильно; revocable proxy —
                         способ явно разорвать граф ссылок при завершении работы
[Генераторы]          — незавершённый генератор удерживает весь свой ER (все
                         локальные переменные) пока объект-генератор жив
[Современный JS]      — AbortController для listeners без ручного removeEventListener
```

## Типичные ошибки на интервью

- **"GC запускается сразу, когда объект больше не нужен"** — нет. GC запускается по расписанию/пороговым значениям, не детерминированно. Присваивание `null` делает объект eligible для сборки, но сборка произойдёт позже.

- **"WeakMap/WeakSet — это то же самое что Map/Set, только слабее"** — ключевые отличия: не итерируемы, нет `.size`, только объекты как ключи/значения. Они решают принципиально другую задачу: ассоциировать данные с объектом не удерживая объект живым.

- **"WeakRef гарантирует, что объект будет в памяти до явного удаления"** — нет. `WeakRef` — слабая ссылка, GC может собрать объект в любое время. `deref()` может вернуть `undefined`. Это "оппортунистический" кеш.

- **"FinalizationRegistry надёжна для очистки ресурсов"** — нет. Callback не гарантирован. Для надёжного освобождения ресурсов — явный `dispose` / `close` / `destroy` паттерн, или `using` (Explicit Resource Management, ES2025).

- **Не знать что Minor GC (Scavenge) не трогает Old Generation** — понимание поколенческого GC важно для объяснения, почему краткоживущие объекты дёшевы (быстрый Minor GC), а долгоживущие — дороже (Major GC с маркировкой всего графа).

- **"Утечка = undefined behaviour"** — нет. Утечка в JS строго определена: объект остаётся достижимым через граф ссылок, хотя программная логика больше не обращается к нему. Понимание GC roots (стек, глобальные, замыкания) позволяет точно определить, что удерживает объект.
