# Современные возможности JavaScript

## Optional chaining (`?.`) — точная семантика

`?.` — оператор **безопасного доступа**: возвращает `undefined`, если левая часть равна `null` или `undefined`, иначе продолжает вычисление.

### Три формы

```js
obj?.prop           // доступ к свойству
obj?.[expr]         // вычисляемый доступ
func?.()            // вызов функции
```

### Short-circuit: чёткая граница

Ключевое: `?.` прерывает **всю оставшуюся цепочку** справа от себя, а не только следующий шаг.

```js
const obj = null;

obj?.a.b.c   // undefined — вся цепочка прервана на ?.
             // .b.c НЕ вычисляется (не ошибка "Cannot read properties of undefined")

obj?.a?.b    // undefined — два отдельных guard-а
obj?.a.b     // если a существует но b нет → TypeError (guard только на obj)
```

```js
// ?.() — guard на вызов:
const api = { getUser: null };
api.getUser?.(); // undefined (не бросает TypeError)
api.missing?.(); // undefined

// Отличие от обычного вызова:
api.getUser();   // TypeError: api.getUser is not a function

// Вложенная опциональная цепочка:
const data = {
  users: [{ name: 'Alice', address: null }]
};

data.users[0]?.address?.city // undefined (не TypeError)
data.users[0]?.address.city  // TypeError! address = null, но guard только на users[0]
```

### Что `?.` НЕ защищает

`?.` срабатывает только на `null` / `undefined`. Falsy-значения (0, `''`, `false`) **не** срабатывают:

```js
const obj = { count: 0 };
obj?.count      // 0 — guard не срабатывает, 0 — не null/undefined
obj?.count ?? 'default' // 0 — ?? тоже не срабатывает

// Ловушка:
const config = { timeout: 0 };
config?.timeout || 5000  // 5000 ← 0 falsy, || срабатывает!
config?.timeout ?? 5000  // 0    ← ?? видит 0 как не-null/undefined
```

## Nullish coalescing (`??`) и логические присваивания

### `??` vs `||`

```js
// || — срабатывает на любое falsy (0, '', false, null, undefined, NaN)
// ?? — срабатывает только на null/undefined

const port = userConfig.port ?? 3000;  // 0 → 0 (хранит порт 0)
const port2 = userConfig.port || 3000; // 0 → 3000 (ошибочно заменяет 0!)

const name = user.name ?? 'Anonymous'; // '' → '' (пустое имя — валидное!)
const name2 = user.name || 'Anonymous'; // '' → 'Anonymous' (может быть неверно)
```

### Логические операторы присваивания (ES2021)

```js
// ??= — присвоить только если null/undefined:
config.timeout ??= 5000;
// эквивалент: config.timeout = config.timeout ?? 5000;

// ||= — присвоить если falsy:
cache.value ||= computeExpensive();
// Ловушка: если cache.value = 0 — вычислит computeExpensive() лишний раз!

// &&= — присвоить если truthy:
user.profile &&= sanitize(user.profile);
// эквивалент: if (user.profile) user.profile = sanitize(user.profile);
```

### Predict the output — `?.` + `??` + `||`

```js
const settings = {
  theme: '',
  timeout: 0,
  debug: false,
  nested: null,
};

console.log(settings.theme    ?? 'dark');           // ?
console.log(settings.theme    || 'dark');           // ?
console.log(settings.timeout  ?? 3000);             // ?
console.log(settings.timeout  || 3000);             // ?
console.log(settings.debug    ?? true);             // ?
console.log(settings.missing  ?? 'default');        // ?
console.log(settings.nested?.value ?? 'fallback');  // ?
console.log(settings.nested?.value || 'fallback');  // ?
```

<details>
<summary>Ответ</summary>

```
''         // '' не null/undefined → ?? возвращает ''
'dark'     // '' falsy → || даёт 'dark'
0          // 0 не null/undefined → ?? возвращает 0
3000       // 0 falsy → || даёт 3000
false      // false не null/undefined → ?? возвращает false
'default'  // settings.missing = undefined → ?? даёт 'default'
'fallback' // nested = null → ?. даёт undefined → ?? даёт 'fallback'
'fallback' // undefined falsy → || даёт 'fallback' (здесь ??, || дают одинаковый результат)
```

</details>

## `structuredClone` vs JSON-методы

### Что умеет JSON и почему недостаточно

```js
const clone = JSON.parse(JSON.stringify(original));

// ❌ JSON теряет/искажает:
JSON.stringify({ fn: () => {} })     // '{}' — функции удалены
JSON.stringify({ x: undefined })     // '{}' — undefined удалено
JSON.stringify({ re: /regex/g })     // '{"re":{}}' — RegExp → пустой объект
JSON.stringify(new Date())           // строка ISO (Date → string, не Date!)
JSON.parse(JSON.stringify(new Date())) // string, не Date

// ❌ Циклические ссылки:
const obj = {};
obj.self = obj;
JSON.stringify(obj); // TypeError: Converting circular structure to JSON

// ❌ Специальные числа:
JSON.stringify({ a: NaN, b: Infinity, c: -Infinity })
// '{"a":null,"b":null,"c":null}' — превращаются в null!

// ❌ Map/Set теряют структуру:
JSON.stringify(new Map([[1, 'a']])); // '{}' — Map → пустой объект
JSON.stringify(new Set([1, 2, 3])); // '{}' — Set → пустой объект
```

### `structuredClone` — настоящий deep clone

```js
// ✅ structuredClone поддерживает:
const original = {
  date: new Date(),
  regex: /hello/gi,
  map: new Map([[1, 'one']]),
  set: new Set([1, 2, 3]),
  buffer: new ArrayBuffer(8),
  nested: { arr: [1, [2, [3]]] },
  undef: undefined,
};

const clone = structuredClone(original);

clone.date instanceof Date;    // true (Date, не строка)
clone.regex instanceof RegExp; // true
clone.map instanceof Map;      // true
clone.map.get(1);              // 'one'
clone.set.has(2);              // true
clone.undef;                   // undefined (не удалено!)

// ✅ Циклические ссылки:
const circular = { a: 1 };
circular.self = circular;
const cloned = structuredClone(circular);
cloned.self === cloned; // true (цикл восстановлен корректно)

// ✅ Поддерживаемые типы:
// Date, RegExp, Map, Set, Array, Object, ArrayBuffer, TypedArrays,
// Blob, File, ImageData, undefined, null, boolean, number, string, BigInt
```

### Что structuredClone НЕ поддерживает

```js
// ❌ Функции — бросит DataCloneError:
structuredClone({ fn: () => {} }); // DataCloneError

// ❌ DOM-узлы:
structuredClone(document.body); // DataCloneError

// ❌ Прототипы теряются (class instances становятся plain objects):
class User {
  constructor(name) { this.name = name; }
  greet() { return `Hi, ${this.name}`; }
}
const user = new User('Alice');
const clone = structuredClone(user);

clone.name;    // 'Alice' — данные скопированы
clone.greet;   // undefined — метод потерян (нет прототипа)
clone instanceof User; // false

// ❌ Symbol как свойства — теряются:
structuredClone({ [Symbol('key')]: 'value' });
// {} — Symbol-ключи не клонируются

// ❌ Error — частично (только message и некоторые поля):
const err = new TypeError('bad');
const clonedErr = structuredClone(err);
clonedErr.message; // 'bad' ✅
clonedErr instanceof TypeError; // true ✅ (в большинстве реализаций)
```

### Производительность

`structuredClone` медленнее `JSON.parse(JSON.stringify())` для простых plain объектов без специальных типов. Для сложных структур или когда JSON недопустим — `structuredClone` единственный корректный вариант.

## AbortController — отмена асинхронных операций

`AbortController` — стандартный механизм отмены операций, поддерживаемый `fetch`, `EventListener`, и кастомным async-кодом.

```js
const controller = new AbortController();
const { signal } = controller;

// Отмена fetch:
const response = await fetch('/api/data', { signal });

// Отмена через таймаут:
setTimeout(() => controller.abort('timeout'), 5000);

try {
  const res = await fetch('/api/slow', { signal });
  const data = await res.json();
} catch (err) {
  if (err.name === 'AbortError') {
    console.log('Cancelled:', err.message); // reason из abort()
  } else {
    throw err; // другие ошибки пробрасываем
  }
}
```

### `AbortSignal.timeout` — встроенный таймаут (ES2022)

```js
// Без AbortController — одной строкой:
const res = await fetch('/api/data', {
  signal: AbortSignal.timeout(5000), // отмена через 5s
});
```

### `AbortSignal.any` — объединение сигналов (ES2023)

```js
const userController = new AbortController();
const timeoutSignal = AbortSignal.timeout(10_000);

// Отменить если пользователь нажал Cancel ИЛИ timeout:
const signal = AbortSignal.any([userController.signal, timeoutSignal]);

fetch('/api/upload', { signal });
```

### Кастомная отмена в своём async-коде

```js
function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);

    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException(signal.reason ?? 'Aborted', 'AbortError'));
    }, { once: true });
  });
}

const controller = new AbortController();
setTimeout(() => controller.abort('user cancelled'), 1000);

try {
  await delay(5000, controller.signal); // ждём 5s, но отменяется через 1s
} catch (err) {
  console.log(err.message); // 'user cancelled'
}
```

### AbortController для удаления listeners

```js
const controller = new AbortController();
const { signal } = controller;

document.addEventListener('click', onClick, { signal });
document.addEventListener('keydown', onKeydown, { signal });
window.addEventListener('resize', onResize, { signal });

// Удалить все три одной строкой:
controller.abort();
```

## Tagged Template Literals — реальный use case

Тегированные шаблоны позволяют перехватить интерполяцию и написать DSL прямо в JS.

```js
// Сигнатура tag-функции:
function tag(strings, ...values) {
  // strings — массив строковых частей (заморожен, имеет .raw)
  // values  — вычисленные выражения
  return /* что угодно */;
}

tag`Hello ${name}, you are ${age} years old`
// strings = ['Hello ', ', you are ', ' years old']
// values  = [name, age]
```

### Безопасный SQL query builder

```js
function sql(strings, ...values) {
  const query = strings.reduce((acc, str, i) => {
    const placeholder = i < values.length ? `$${i + 1}` : '';
    return acc + str + placeholder;
  }, '');

  return { query, params: values };
}

const userId = 42;
const role = 'admin';

const { query, params } = sql`
  SELECT * FROM users
  WHERE id = ${userId} AND role = ${role}
`;

// query:  'SELECT * FROM users WHERE id = $1 AND role = $2'
// params: [42, 'admin']
// Никакой SQL-инъекции: значения никогда не интерполируются в строку напрямую
```

### HTML sanitization

```js
function html(strings, ...values) {
  const escape = (str) =>
    String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');

  return strings.reduce((acc, str, i) => {
    const value = i < values.length ? escape(values[i]) : '';
    return acc + str + value;
  }, '');
}

const userInput = '<script>alert("xss")</script>';
const safeHtml = html`<div class="message">${userInput}</div>`;
// '<div class="message">&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</div>'
```

### `String.raw` — встроенный тег для raw строк

```js
// String.raw — отключает обработку escape-последовательностей:
String.raw`C:\Users\name\Documents`  // 'C:\\Users\\name\\Documents'
// Без String.raw: 'C:\Users\name\Documents' (\ интерпретируется)

// Практично для регулярных выражений и Windows-путей:
const winPath = String.raw`C:\Program Files\App`;
const regex = new RegExp(String.raw`\d+\.\d+`);
```

## Новые методы Array и Object

### `Array.prototype.at()` — отрицательные индексы (ES2022)

```js
const arr = [1, 2, 3, 4, 5];

arr.at(0)   // 1  — как arr[0]
arr.at(-1)  // 5  — последний элемент
arr.at(-2)  // 4  — предпоследний

// До at(): arr[arr.length - 1] — неудобно
// String.prototype.at() тоже работает:
'hello'.at(-1) // 'o'
```

### `Array.prototype.findLast` / `findLastIndex` (ES2023)

```js
const events = [
  { id: 1, type: 'click' },
  { id: 2, type: 'scroll' },
  { id: 3, type: 'click' },
];

// findLast — ищет с конца:
events.findLast(e => e.type === 'click');      // { id: 3, type: 'click' }
events.findLastIndex(e => e.type === 'click'); // 2

// До findLast:
[...events].reverse().find(e => e.type === 'click'); // создаёт копию + reverse
```

### Иммутабельные методы массивов (ES2023)

```js
const arr = [3, 1, 4, 1, 5];

// toSorted — возвращает отсортированную КОПИЮ (не мутирует):
const sorted = arr.toSorted((a, b) => a - b); // [1, 1, 3, 4, 5]
arr; // [3, 1, 4, 1, 5] — не изменился

// toReversed — копия в обратном порядке:
const reversed = arr.toReversed(); // [5, 1, 4, 1, 3]

// toSpliced — копия с splice-операцией:
const spliced = arr.toSpliced(1, 2, 99); // [3, 99, 1, 5]

// with — копия с заменой элемента:
const withNew = arr.with(2, 99); // [3, 1, 99, 1, 5]
arr.with(-1, 0); // [3, 1, 4, 1, 0]

// Важно для React / иммутабельного состояния:
setItems(items.toSorted()); // не мутирует исходный массив — корректно в React
```

### `Object.hasOwn` — безопасная проверка собственного свойства (ES2022)

```js
// Старый способ — ненадёжен:
obj.hasOwnProperty('key'); // ❌ если obj = Object.create(null) — нет метода!

// Object.hasOwn — работает везде:
Object.hasOwn({}, 'toString');        // false (toString — из прототипа)
Object.hasOwn({ x: 1 }, 'x');        // true
Object.hasOwn(Object.create(null), 'x'); // false — работает даже на null-прототипе
```

### `Object.groupBy` / `Map.groupBy` (ES2024)

```js
const products = [
  { name: 'Apple', category: 'fruit' },
  { name: 'Carrot', category: 'vegetable' },
  { name: 'Banana', category: 'fruit' },
];

const grouped = Object.groupBy(products, p => p.category);
// {
//   fruit: [{ name: 'Apple', ... }, { name: 'Banana', ... }],
//   vegetable: [{ name: 'Carrot', ... }]
// }

// Map.groupBy — когда ключи не строки:
const byLength = Map.groupBy([1, 2, 3, 4, 5], n => n % 2 === 0 ? 'even' : 'odd');
byLength.get('even'); // [2, 4]
byLength.get('odd');  // [1, 3, 5]
```

### `Promise.withResolvers` (ES2024)

```js
// До withResolvers — resolve/reject нельзя было вынести из конструктора:
let resolve, reject;
const promise = new Promise((res, rej) => {
  resolve = res;
  reject = rej;
});

// С withResolvers — чисто:
const { promise, resolve, reject } = Promise.withResolvers();

// Например, для создания deferred:
function createDeferred() {
  return Promise.withResolvers();
}

const { promise: ready, resolve: markReady } = createDeferred();
setTimeout(() => markReady('done'), 1000);
await ready; // 'done'
```

### `Array.fromAsync` (ES2024)

```js
// Создать массив из async iterable:
async function* asyncNumbers() {
  yield 1;
  yield 2;
  yield 3;
}

const arr = await Array.fromAsync(asyncNumbers()); // [1, 2, 3]

// С маппером:
const doubled = await Array.fromAsync(asyncNumbers(), n => n * 2); // [2, 4, 6]
```

## Связь с другими темами

```txt
[Генераторы]          — Array.fromAsync потребляет async iterables;
                         for-await-of как альтернатива
[Асинхронные паттерны] — AbortController интегрируется с Promise через
                         signal.addEventListener('abort', ...)
[Замыкания]           — tag-функции — обычные функции с замыканием
                         на strings.raw и переданные значения
[Coercion]            — ?? vs || — принципиальная разница через понимание
                         ToBoolean (falsy) vs nullish
```

## Типичные ошибки на интервью

- **"`?.` защищает от всех falsy"** — нет. Только от `null` и `undefined`. `(0)?.toString()` — работает нормально (возвращает `'0'`). `false?.toString()` — тоже.

- **"`??` и `||` взаимозаменяемы"** — нет. `||` срабатывает на любой falsy (0, `''`, `false`). `??` — только на `null`/`undefined`. Использование `||` для значений по умолчанию часто баг: `config.retries || 3` заменяет `retries: 0` на 3.

- **"JSON.parse(JSON.stringify(x)) — универсальный deep clone"** — нет. Теряет функции, undefined, Map/Set, RegExp, Date (в строку), зацикливается на circular refs. `structuredClone` для серьёзного клонирования.

- **"structuredClone клонирует class instances полностью"** — нет. Прототип теряется. Данные копируются, методы — нет. `clone instanceof MyClass` — false.

- **"AbortController отменяет fetch на сервере"** — нет. `abort()` отменяет **клиентский** запрос (браузер закрывает соединение), но сервер может не знать об этом и продолжить обработку. Для серверной отмены нужен отдельный API (cancellation token в запросе).

- **"Tagged templates — это просто синтаксический сахар для строк"** — нет. tag-функция получает strings и values раздельно и может вернуть что угодно — не обязательно строку. `styled.div\`color: red\`` возвращает React-компонент, `gql\`query ...\`` возвращает AST.

- **"Object.groupBy доступен давно"** — ES2024. В Node.js с v21. До этого — `_.groupBy` из lodash или ручная реализация через `reduce`. На интервью важно знать версии.
