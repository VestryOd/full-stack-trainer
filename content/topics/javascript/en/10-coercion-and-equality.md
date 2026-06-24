# Coercion and Equality

## The Abstract Equality Comparison algorithm (`==`)

`==` is not "weird JS" — it's a deterministic algorithm in the spec. If you know the steps, every result is predictable.

The algorithm for `x == y` (simplified but accurate):

```txt
1. If Type(x) === Type(y):
     return x === y (Strict Equality, no further coercion)
     (NaN !== NaN — even here)

2. null == undefined → true (and undefined == null → true)
   null/undefined == anything_else → false

3. If one is Number and the other is String:
     convert String to Number → retry

4. If one is Boolean:
     convert Boolean to Number (true→1, false→0) → retry

5. If one is Object and the other is String/Number/Symbol/BigInt:
     convert Object to primitive via ToPrimitive → retry

6. Otherwise → false
```

Let's walk through the most confusing cases using this algorithm:

```js
// Predict the output — explain each one through the algorithm:
console.log([] == false);    // ?
console.log([] == 0);        // ?
console.log('' == false);    // ?
console.log(null == 0);      // ?
console.log(null == false);  // ?
console.log('' == 0);        // ?
```

<details>
<summary>Step-by-step breakdown</summary>

```txt
[] == false
  Step 4: false is Boolean → ToNumber(false) = 0 → [] == 0
  Step 5: [] is Object → ToPrimitive([]) = '' → '' == 0
  Step 3: '' is String → ToNumber('') = 0 → 0 == 0
  Step 1: both Number, 0 === 0 → true ✅

[] == 0
  Step 5: [] is Object → ToPrimitive([]) = '' → '' == 0
  Step 3: '' is String → ToNumber('') = 0 → 0 == 0 → true ✅

'' == false
  Step 4: false is Boolean → ToNumber(false) = 0 → '' == 0
  Step 3: '' is String → ToNumber('') = 0 → 0 == 0 → true ✅

null == 0
  Step 2: null == something (not null/undefined) → false ✅
  (the algorithm guarantees: null only equals null and undefined)

null == false
  Step 2: null == something (not null/undefined) → false ✅
  (even though both are "falsy"!)

'' == 0
  Step 3: '' is String → ToNumber('') = 0 → 0 == 0 → true ✅
```

Result: `true, true, true, false, false, true`

Key observation: `null == 0` and `null == false` are false, even though `'' == false`, `'' == 0`, and `[] == false` are true. `null` is special: the algorithm only considers it equal to `null` and `undefined`.

</details>

## ToPrimitive — how objects become primitives

When an object needs to become a primitive, the engine runs the ToPrimitive algorithm with a **hint** (`'number'`, `'string'`, or `'default'`):

```txt
ToPrimitive(obj, hint):
  1. If [Symbol.toPrimitive] exists → call it with hint → return result
  2. If hint = 'string':
       try obj.toString() → if primitive → return it
       try obj.valueOf()  → if primitive → return it
  3. If hint = 'number' or 'default':
       try obj.valueOf()  → if primitive → return it
       try obj.toString() → if primitive → return it
  4. Otherwise → TypeError
```

Built-in objects:

```js
// Array:
[].toString()       // ''
[1,2,3].toString()  // '1,2,3'
[].valueOf()        // [] (not a primitive → falls through to toString)

// Object:
({}).toString()     // '[object Object]'
({}).valueOf()      // {} (not a primitive → falls through to toString)

// Date — 'default' hint is treated as 'string':
new Date().valueOf()  // timestamp (number)
new Date().toString() // 'Tue Jun 24 2026 ...'
```

```js
// Why [] + [] = ''
// hint 'default': valueOf → [] (not primitive), toString → '' → '' + '' = ''
[] + []  // ''

// Why [] + {} = '[object Object]'
// [] → '', {} → '[object Object]' → '' + '[object Object]'
[] + {}  // '[object Object]'

// The famous trap:
{} + []  // 0 (not '[object Object]'!)
// {} is parsed as an empty block; +[] = ToNumber([]) = ToNumber('') = 0
// But only in a statement context (console, standalone line)!
// In an expression context:
({}) + [] // '[object Object]'
```

## The `+` operator — its dual nature

`+` is the only operator with two behaviors: numeric addition OR string concatenation.

```txt
Algorithm for x + y:
  1. lprim = ToPrimitive(x) [hint: 'default']
  2. rprim = ToPrimitive(y) [hint: 'default']
  3. If lprim or rprim is a string → concatenation (ToString both)
  4. Otherwise → ToNumber both, add
```

```js
1 + 2          // 3    — both numbers
1 + '2'        // '12' — string → concatenation
'1' + 2        // '12' — string → concatenation
1 + true       // 2    — true → 1
1 + null       // 1    — null → 0
1 + undefined  // NaN  — undefined → NaN
1 + {}         // '1[object Object]' — {} → '[object Object]' → string
1 + []         // '1'  — [] → '' → string

// Arithmetic operators (-, *, /) always apply ToNumber:
'3' - 1   // 2   — '3' → 3
'3' * '2' // 6
[] - 1    // -1  — [] → 0
```

## `typeof null === 'object'` — the historical bug

In the original JavaScript implementation (Brendan Eich, 1995), values were stored as 32-bit words. The lower 3 bits were a type tag:

```txt
000 → object
001 → integer
010 → double
100 → string
110 → boolean
```

The special value `null` was represented as the **null pointer** (0x00000000 on most platforms). The type tag of the null pointer was `000` → object.

This is a bug, not a feature. There was a proposal to fix it in ES2015, but it was rejected due to compatibility concerns with billions of lines of existing code.

```js
typeof null        // 'object'  ← bug, historical
typeof undefined   // 'undefined'
typeof 42          // 'number'
typeof 'str'       // 'string'
typeof true        // 'boolean'
typeof Symbol()    // 'symbol'
typeof 42n         // 'bigint'
typeof function(){} // 'function' (functions are objects, but typeof gives 'function')
typeof {}          // 'object'
typeof []          // 'object'  ← arrays are objects

// Correct null check:
x === null         // ✅ the only reliable way
typeof x === 'object' && x !== null // ✅ check it's an object and not null
```

## NaN — the number not equal to itself

`NaN` (Not-a-Number) is the only value in JS that is not equal to itself. This is mandated by the IEEE 754 spec.

```js
NaN === NaN  // false
NaN !== NaN  // true
NaN == NaN   // false

typeof NaN   // 'number' ← paradox: "not a number" has type 'number'

// Why: NaN is the result of invalid numeric operations
0 / 0           // NaN
parseInt('abc') // NaN
Math.sqrt(-1)   // NaN
Number(undefined) // NaN
```

### `isNaN` vs `Number.isNaN` — a critical difference

```js
// isNaN() — old global function, applies ToNumber first:
isNaN(NaN)        // true
isNaN('hello')    // true! ('hello' → Number('hello') = NaN)
isNaN(undefined)  // true! (undefined → NaN)
isNaN({})         // true! ({} → '[object Object]' → NaN)
isNaN(null)       // false! (null → 0)
isNaN([])         // false! ([] → '' → 0)

// Number.isNaN() — strict check, does NOT apply ToNumber:
Number.isNaN(NaN)        // true
Number.isNaN('hello')    // false ← it's a string, not NaN
Number.isNaN(undefined)  // false
Number.isNaN(1/0)        // false ← Infinity, not NaN

// How to check for NaN without Number.isNaN:
x !== x  // true only for NaN (exploits the NaN ≠ NaN property)
```

### Number edge cases

```js
Infinity         // exceeds the number range
-Infinity
1 / 0            // Infinity
-1 / 0           // -Infinity
isFinite(Infinity)        // false (applies ToNumber first!)
Number.isFinite(Infinity) // false (strict: only finite numbers)
Number.isFinite('42')     // false (strict: only the number type)
isFinite('42')            // true  (ToNumber('42') = 42)

// Floating-point numbers (IEEE 754):
0.1 + 0.2         // 0.30000000000000004
0.1 + 0.2 === 0.3 // false

// +0 and -0:
+0 === -0         // true (!!!)
1 / +0            // Infinity
1 / -0            // -Infinity (the only way to distinguish +0 and -0 via ===)
Object.is(+0, -0) // false
```

## `===` vs `==` vs `Object.is`

Three different equality algorithms:

```txt
==         Abstract Equality:  type coercion (algorithm above)
===        Strict Equality:    no coercion, but: NaN≠NaN, +0===−0
Object.is  Same Value:         NaN===NaN, +0≠−0 (mathematically precise)
```

```js
// The two === edge cases (counterintuitive):
NaN === NaN  // false  (Object.is → true)
+0 === -0    // true   (Object.is → false)

// Object.is implements the SameValue algorithm from the spec:
Object.is(NaN, NaN)   // true
Object.is(+0, -0)     // false
Object.is(1, 1)       // true
Object.is(null, null) // true

// Where Object.is matters:
// 1. Map/Set implementation — keys are compared via SameValueZero
//    (like Object.is, but +0 === -0)
const map = new Map();
map.set(NaN, 'found');
map.get(NaN); // 'found' ← Map correctly handles NaN as a key

// 2. React.memo, useMemo, useEffect dependencies —
//    React uses Object.is to compare props/deps
Object.is(prevValue, nextValue); // if false → re-render
```

## Truthy/falsy table — the genuinely non-obvious cases

**All falsy values** (only 9 of them):

```js
false
0           // numeric zero
-0          // negative zero (a separate value!)
0n          // BigInt zero
''          // empty string ('' === "" === ``)
null
undefined
NaN
document.all // ← the only object in JS that is falsy (historical bug)
```

**Non-obvious truthy values**:

```js
// All of the following are truthy:
[]               // empty array — truthy!
{}               // empty object — truthy!
'0'              // non-empty string — truthy!
'false'          // non-empty string — truthy!
new Boolean(false) // a Boolean object (not a primitive) — truthy!
function(){}     // any function — truthy
Infinity         // truthy
-Infinity        // truthy
```

```js
// Predict the output:
if ([]) console.log('array truthy');            // ?
if ({}) console.log('object truthy');           // ?
if ('0') console.log('string truthy');          // ?
if (new Boolean(false)) console.log('bool obj truthy'); // ?
if ([] == false) console.log('array == false'); // ?
```

<details>
<summary>Answer</summary>

```
array truthy     // [] is a truthy object
object truthy    // {} is a truthy object
string truthy    // '0' is a non-empty string, truthy
bool obj truthy  // new Boolean(false) is an object, always truthy
array == false   // true! [] == false via the == algorithm (see above)
```

This is what makes `==` dangerous: `[]` is truthy in a boolean context (`if`), yet `[] == false` is `true` via the abstract equality algorithm. The apparent contradiction is because `if` uses ToBoolean (no coercion), while `==` uses AbstractEquality (with coercion via step 4: Boolean → Number, then step 5: Object → String).

</details>

### `document.all` — the one object exception

```js
// document.all — HTMLAllCollection, a special case for IE compatibility
typeof document.all // 'undefined' (even though it's an object!)
Boolean(document.all) // false (even though it's an object!)
document.all == null  // true

// This is explicitly described in the HTML spec as a "willful violation of the
// ECMAScript spec" for compatibility with old sites that checked for document.all
```

## ToNumber, ToString, ToBoolean — quick reference

```txt
ToNumber:
  undefined  → NaN
  null       → 0
  true       → 1
  false      → 0
  ''         → 0
  '   '      → 0  (whitespace is ignored)
  '42'       → 42
  '0x1A'     → 26 (hex)
  'Infinity' → Infinity
  '42abc'    → NaN (not a valid number)
  []         → 0  (via ToPrimitive: [] → '' → 0)
  [1]        → 1  (via ToPrimitive: [1] → '1' → 1)
  [1,2]      → NaN (via ToPrimitive: [1,2] → '1,2' → NaN)
  {}         → NaN (via ToPrimitive: {} → '[object Object]' → NaN)

ToString:
  undefined  → 'undefined'
  null       → 'null'
  true       → 'true'
  false      → 'false'
  0          → '0'
  -0         → '0'  (!)
  NaN        → 'NaN'
  Infinity   → 'Infinity'
  []         → ''
  [1,2,3]    → '1,2,3'
  {}         → '[object Object]'

ToBoolean (no computation, just a lookup table):
  falsy: false, 0, -0, 0n, '', null, undefined, NaN, document.all
  everything else → true (including [], {}, '0', 'false', new Boolean(false))
```

## Connection to other topics

```txt
[Proxy/Symbol]          — Symbol.toPrimitive intercepts ToPrimitive;
                           without it — the valueOf/toString chain runs
[Modern JS]             — Object.hasOwn, Number.isNaN, Number.isFinite —
                           strict versions of the old functions without
                           implicit ToNumber
[Memory Management]     — typeof is used for type checks, but
                           typeof null === 'object' requires a separate check
```

## Common interview traps

- **"`==` is unpredictable"** — 100% predictable if you know the algorithm. The problem isn't "JS weirdness" but that the algorithm is non-linear (7 steps with retries). Knowing the algorithm lets you explain any result.

- **"To check for NaN, use `isNaN`"** — `isNaN` applies `ToNumber` to its argument, so `isNaN('hello')` = true. Use `Number.isNaN` (strict check) or `x !== x`.

- **"`===` is absolutely precise comparison"** — no, two exceptions: `NaN !== NaN` and `+0 === -0`. For mathematically correct comparison — `Object.is`.

- **"An empty array `[]` is falsy"** — no! `[]` is truthy. But `[] == false` is true (via the == algorithm). This is one of the most common confusions in interviews.

- **"`typeof null === 'object'` is correct behavior"** — no, it's a recognized bug from 1995, left unfixed for backward compatibility.

- **"The `+` operator is always addition"** — no. If at least one operand becomes a string after ToPrimitive, `+` is concatenation. That's why `1 + []` = `'1'` (not `1`).

- **"Not knowing the difference between `Object.is`, `===`, and `==`"** — for senior roles, all three must be clear. `Object.is` is used in React for dependency comparison and in the spec for Map/Set (SameValueZero — a variant of Object.is where +0 === -0).
