# Modern JavaScript Features

## Optional chaining (`?.`) — precise semantics

`?.` is a **safe access operator**: it returns `undefined` if the left-hand side is `null` or `undefined`, otherwise continues the evaluation.

### Three forms

```js
obj?.prop           // property access
obj?.[expr]         // computed access
func?.()            // optional call
```

### Short-circuit: the exact boundary

The key point: `?.` short-circuits the **entire remaining chain** to its right, not just the next step.

```js
const obj = null;

obj?.a.b.c   // undefined — the entire chain is short-circuited at ?.
             // .b.c is NOT evaluated (no "Cannot read properties of undefined")

obj?.a?.b    // undefined — two separate guards
obj?.a.b     // if a exists but b doesn't → TypeError (guard only on obj)
```

```js
// ?.() — guard on a call:
const api = { getUser: null };
api.getUser?.(); // undefined (doesn't throw TypeError)
api.missing?.(); // undefined

// Contrast with a regular call:
api.getUser();   // TypeError: api.getUser is not a function

// Nested optional chaining:
const data = {
  users: [{ name: 'Alice', address: null }]
};

data.users[0]?.address?.city // undefined (no TypeError)
data.users[0]?.address.city  // TypeError! address = null, but the guard is only on users[0]
```

### What `?.` does NOT guard against

`?.` only triggers on `null` / `undefined`. Falsy values (0, `''`, `false`) do **not** trigger it:

```js
const obj = { count: 0 };
obj?.count      // 0 — guard doesn't fire, 0 is not null/undefined
obj?.count ?? 'default' // 0 — ?? doesn't fire either

// Trap:
const config = { timeout: 0 };
config?.timeout || 5000  // 5000 ← 0 is falsy, || fires!
config?.timeout ?? 5000  // 0    ← ?? treats 0 as non-nullish
```

## Nullish coalescing (`??`) and logical assignments

### `??` vs `||`

```js
// || — fires on any falsy (0, '', false, null, undefined, NaN)
// ?? — fires only on null/undefined

const port = userConfig.port ?? 3000;  // 0 → 0 (preserves port 0)
const port2 = userConfig.port || 3000; // 0 → 3000 (incorrectly replaces 0!)

const name = user.name ?? 'Anonymous'; // '' → '' (empty name is valid!)
const name2 = user.name || 'Anonymous'; // '' → 'Anonymous' (may be wrong)
```

### Logical assignment operators (ES2021)

```js
// ??= — assign only if null/undefined:
config.timeout ??= 5000;
// equivalent: config.timeout = config.timeout ?? 5000;

// ||= — assign if falsy:
cache.value ||= computeExpensive();
// Trap: if cache.value = 0 — computeExpensive() runs unnecessarily!

// &&= — assign if truthy:
user.profile &&= sanitize(user.profile);
// equivalent: if (user.profile) user.profile = sanitize(user.profile);
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
<summary>Answer</summary>

```
''         // '' is not null/undefined → ?? returns ''
'dark'     // '' is falsy → || gives 'dark'
0          // 0 is not null/undefined → ?? returns 0
3000       // 0 is falsy → || gives 3000
false      // false is not null/undefined → ?? returns false
'default'  // settings.missing = undefined → ?? gives 'default'
'fallback' // nested = null → ?. gives undefined → ?? gives 'fallback'
'fallback' // undefined is falsy → || gives 'fallback' (same result here)
```

</details>

## `structuredClone` vs JSON methods

### What JSON can do — and where it falls short

```js
const clone = JSON.parse(JSON.stringify(original));

// ❌ JSON loses/distorts:
JSON.stringify({ fn: () => {} })     // '{}' — functions removed
JSON.stringify({ x: undefined })     // '{}' — undefined removed
JSON.stringify({ re: /regex/g })     // '{"re":{}}' — RegExp → empty object
JSON.stringify(new Date())           // ISO string (Date → string, not Date!)
JSON.parse(JSON.stringify(new Date())) // string, not Date

// ❌ Circular references:
const obj = {};
obj.self = obj;
JSON.stringify(obj); // TypeError: Converting circular structure to JSON

// ❌ Special numbers:
JSON.stringify({ a: NaN, b: Infinity, c: -Infinity })
// '{"a":null,"b":null,"c":null}' — all become null!

// ❌ Map/Set lose their structure:
JSON.stringify(new Map([[1, 'a']])); // '{}' — Map → empty object
JSON.stringify(new Set([1, 2, 3])); // '{}' — Set → empty object
```

### `structuredClone` — a real deep clone

```js
// ✅ structuredClone handles:
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

clone.date instanceof Date;    // true (Date, not string)
clone.regex instanceof RegExp; // true
clone.map instanceof Map;      // true
clone.map.get(1);              // 'one'
clone.set.has(2);              // true
clone.undef;                   // undefined (not dropped!)

// ✅ Circular references:
const circular = { a: 1 };
circular.self = circular;
const cloned = structuredClone(circular);
cloned.self === cloned; // true (cycle is correctly preserved)

// ✅ Supported types:
// Date, RegExp, Map, Set, Array, Object, ArrayBuffer, TypedArrays,
// Blob, File, ImageData, undefined, null, boolean, number, string, BigInt
```

### What `structuredClone` does NOT support

```js
// ❌ Functions — throws DataCloneError:
structuredClone({ fn: () => {} }); // DataCloneError

// ❌ DOM nodes:
structuredClone(document.body); // DataCloneError

// ❌ Prototypes are lost (class instances become plain objects):
class User {
  constructor(name) { this.name = name; }
  greet() { return `Hi, ${this.name}`; }
}
const user = new User('Alice');
const clone = structuredClone(user);

clone.name;        // 'Alice' — data is copied
clone.greet;       // undefined — method is lost (no prototype)
clone instanceof User; // false

// ❌ Symbol keys are lost:
structuredClone({ [Symbol('key')]: 'value' });
// {} — Symbol-keyed properties are not cloned

// ❌ Error — partial support (only message and some fields):
const err = new TypeError('bad');
const clonedErr = structuredClone(err);
clonedErr.message;          // 'bad' ✅
clonedErr instanceof TypeError; // true ✅ (in most implementations)
```

### Performance

`structuredClone` is slower than `JSON.parse(JSON.stringify())` for simple plain objects with no special types. For complex structures or where JSON is incorrect, `structuredClone` is the only correct option.

## AbortController — cancelling async operations

`AbortController` is the standard cancellation mechanism supported by `fetch`, `EventListener`, and custom async code.

```js
const controller = new AbortController();
const { signal } = controller;

// Cancel a fetch:
const response = await fetch('/api/data', { signal });

// Cancel with a timeout:
setTimeout(() => controller.abort('timeout'), 5000);

try {
  const res = await fetch('/api/slow', { signal });
  const data = await res.json();
} catch (err) {
  if (err.name === 'AbortError') {
    console.log('Cancelled:', err.message); // reason from abort()
  } else {
    throw err; // rethrow other errors
  }
}
```

### `AbortSignal.timeout` — built-in timeout (ES2022)

```js
// Without AbortController — one line:
const res = await fetch('/api/data', {
  signal: AbortSignal.timeout(5000), // cancel after 5s
});
```

### `AbortSignal.any` — combining signals (ES2023)

```js
const userController = new AbortController();
const timeoutSignal = AbortSignal.timeout(10_000);

// Cancel if user clicks Cancel OR timeout fires:
const signal = AbortSignal.any([userController.signal, timeoutSignal]);

fetch('/api/upload', { signal });
```

### Custom cancellation in your own async code

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
  await delay(5000, controller.signal); // wait 5s, but cancelled after 1s
} catch (err) {
  console.log(err.message); // 'user cancelled'
}
```

### AbortController for removing listeners

```js
const controller = new AbortController();
const { signal } = controller;

document.addEventListener('click', onClick, { signal });
document.addEventListener('keydown', onKeydown, { signal });
window.addEventListener('resize', onResize, { signal });

// Remove all three with one line:
controller.abort();
```

## Tagged Template Literals — a real use case

Tagged templates let you intercept interpolation and write a DSL directly in JS.

```js
// Tag function signature:
function tag(strings, ...values) {
  // strings — frozen array of string parts (has .raw property)
  // values  — evaluated expressions
  return /* anything */;
}

tag`Hello ${name}, you are ${age} years old`
// strings = ['Hello ', ', you are ', ' years old']
// values  = [name, age]
```

### SQL-injection-safe query builder

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
// No SQL injection: values are never interpolated directly into the string
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

### `String.raw` — the built-in tag for raw strings

```js
// String.raw — disables escape sequence processing:
String.raw`C:\Users\name\Documents`  // 'C:\\Users\\name\\Documents'
// Without String.raw: 'C:\Users\name\Documents' (\ is interpreted)

// Useful for regex patterns and Windows paths:
const winPath = String.raw`C:\Program Files\App`;
const regex = new RegExp(String.raw`\d+\.\d+`);
```

## New Array and Object methods

### `Array.prototype.at()` — negative indices (ES2022)

```js
const arr = [1, 2, 3, 4, 5];

arr.at(0)   // 1  — like arr[0]
arr.at(-1)  // 5  — last element
arr.at(-2)  // 4  — second to last

// Before at(): arr[arr.length - 1] — awkward
// String.prototype.at() also works:
'hello'.at(-1) // 'o'
```

### `Array.prototype.findLast` / `findLastIndex` (ES2023)

```js
const events = [
  { id: 1, type: 'click' },
  { id: 2, type: 'scroll' },
  { id: 3, type: 'click' },
];

// findLast — searches from the end:
events.findLast(e => e.type === 'click');      // { id: 3, type: 'click' }
events.findLastIndex(e => e.type === 'click'); // 2

// Before findLast:
[...events].reverse().find(e => e.type === 'click'); // creates a copy + reverses
```

### Immutable array methods (ES2023)

```js
const arr = [3, 1, 4, 1, 5];

// toSorted — returns a sorted COPY (does not mutate):
const sorted = arr.toSorted((a, b) => a - b); // [1, 1, 3, 4, 5]
arr; // [3, 1, 4, 1, 5] — unchanged

// toReversed — copy in reverse order:
const reversed = arr.toReversed(); // [5, 1, 4, 1, 3]

// toSpliced — copy with a splice operation:
const spliced = arr.toSpliced(1, 2, 99); // [3, 99, 1, 5]

// with — copy with a replaced element:
const withNew = arr.with(2, 99); // [3, 1, 99, 1, 5]
arr.with(-1, 0); // [3, 1, 4, 1, 0]

// Crucial for React / immutable state:
setItems(items.toSorted()); // doesn't mutate the original — correct in React
```

### `Object.hasOwn` — safe own property check (ES2022)

```js
// The old way — unreliable:
obj.hasOwnProperty('key'); // ❌ if obj = Object.create(null) — no method!

// Object.hasOwn — works everywhere:
Object.hasOwn({}, 'toString');           // false (toString is inherited)
Object.hasOwn({ x: 1 }, 'x');           // true
Object.hasOwn(Object.create(null), 'x'); // false — works on null-prototype objects
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

// Map.groupBy — when keys aren't strings:
const byParity = Map.groupBy([1, 2, 3, 4, 5], n => n % 2 === 0 ? 'even' : 'odd');
byParity.get('even'); // [2, 4]
byParity.get('odd');  // [1, 3, 5]
```

### `Promise.withResolvers` (ES2024)

```js
// Before withResolvers — resolve/reject couldn't be extracted from the constructor:
let resolve, reject;
const promise = new Promise((res, rej) => {
  resolve = res;
  reject = rej;
});

// With withResolvers — clean:
const { promise, resolve, reject } = Promise.withResolvers();

// Example: creating a deferred:
function createDeferred() {
  return Promise.withResolvers();
}

const { promise: ready, resolve: markReady } = createDeferred();
setTimeout(() => markReady('done'), 1000);
await ready; // 'done'
```

### `Array.fromAsync` (ES2024)

```js
// Create an array from an async iterable:
async function* asyncNumbers() {
  yield 1;
  yield 2;
  yield 3;
}

const arr = await Array.fromAsync(asyncNumbers()); // [1, 2, 3]

// With a mapper:
const doubled = await Array.fromAsync(asyncNumbers(), n => n * 2); // [2, 4, 6]
```

## Connection to other topics

```txt
[Generators]            — Array.fromAsync consumes async iterables;
                           for-await-of as an alternative
[Async Patterns]        — AbortController integrates with Promises via
                           signal.addEventListener('abort', ...)
[Closures]              — tag functions are ordinary functions that close
                           over the strings.raw and interpolated values
[Coercion]              — ?? vs || — the critical difference stems from
                           understanding ToBoolean (falsy) vs nullish
```

## Common interview traps

- **"`?.` guards against all falsy values"** — no. Only `null` and `undefined`. `(0)?.toString()` works fine (returns `'0'`). So does `false?.toString()`.

- **"`??` and `||` are interchangeable"** — no. `||` fires on any falsy (0, `''`, `false`). `??` fires only on `null`/`undefined`. Using `||` for defaults is often a bug: `config.retries || 3` replaces `retries: 0` with 3.

- **"`JSON.parse(JSON.stringify(x))` is a universal deep clone"** — no. It drops functions, undefined, Map/Set, RegExp; converts Dates to strings; throws on circular refs. Use `structuredClone` for serious cloning.

- **"`structuredClone` fully clones class instances"** — no. The prototype is lost. Data is copied, methods are not. `clone instanceof MyClass` returns false.

- **"AbortController cancels the fetch on the server"** — no. `abort()` cancels the **client-side** request (the browser closes the connection), but the server may not know about it and can continue processing. Server-side cancellation requires a separate mechanism (a cancellation token in the request body/headers).

- **"Tagged templates are just syntactic sugar for strings"** — no. The tag function receives strings and values separately and can return anything — not necessarily a string. `styled.div\`color: red\`` returns a React component; `gql\`query ...\`` returns an AST.

- **"`Object.groupBy` has been around for a long time"** — ES2024. In Node.js from v21. Before that: `_.groupBy` from lodash or a manual `reduce`. Knowing the version matters in interviews.
