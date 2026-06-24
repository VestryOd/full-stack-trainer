# Execution Context and Scope

## What an Execution Context actually is — the spec definition

When the JavaScript engine runs code, it creates an **Execution Context** — an abstract container defined by the ECMAScript specification. It's not a vague "environment" — it has a precise internal structure:

```txt
Execution Context
├── code evaluation state    — where execution "is" (relevant for generators/async)
├── Function                 — reference to the Function Object, or null (for global)
├── Realm                    — the set of built-ins (Array, Object, …)
├── LexicalEnvironment       — where identifiers are looked up (let/const + catch)
├── VariableEnvironment      — where var and function declarations live
└── ThisBinding              — the value of this
```

Many contexts can exist on the stack simultaneously. The one at the top is the **Running Execution Context**.

```txt
         ┌───────────────────────────┐
         │  baz()  execution context │  ← running (current)
         ├───────────────────────────┤
         │  bar()  execution context │
         ├───────────────────────────┤
         │  foo()  execution context │
         ├───────────────────────────┤
         │  global execution context │  ← always at the bottom
         └───────────────────────────┘
                   Call Stack
```

## Two phases: creation vs execution

Every time a function is called (or a script starts), the engine goes through **two distinct phases**:

### Creation Phase

The engine scans the function body (or global code) and does the following **before executing any line of code**:

1. Creates an **Environment Record**
2. Sets the **outer reference** — a pointer to the lexically enclosing Environment Record (this is the scope chain mechanism)
3. Determines **`this`**
4. Processes declarations:
   - `var x` → creates a binding in VariableEnvironment, initializes to `undefined`
   - `function foo() {}` → creates a binding in VariableEnvironment, initializes to the **full function object**
   - `let y` / `const z` → creates a binding in LexicalEnvironment, does NOT initialize (TDZ)

### Execution Phase

The engine runs the code line by line. Assignments happen here.

```js
// What the engine sees during creation phase for this code:
console.log(a); // ?
console.log(b); // ?
console.log(c); // ?

var a = 1;
let b = 2;
function c() {}

// Creation phase result:
// a → undefined      (var: created, initialized to undefined)
// b → <TDZ>          (let: created, NOT initialized)
// c → function c(){} (function declaration: created and fully initialized)

// Execution phase:
// console.log(a) → undefined   ✅ (var exists, value is still undefined)
// console.log(b) → ReferenceError: Cannot access 'b' before initialization
// console.log(c) → function c(){} ✅ (fully initialized)
```

**Hoisting is not "code being moved to the top."** It's a consequence of the two-phase model: bindings are created during the creation phase, code runs during the execution phase. No magic — just the order of operations mandated by the spec.

## Environment Records — what they actually are

The spec defines a hierarchy of Environment Records:

```txt
Environment Record (abstract)
├── Declarative ER          — let, const, function, class, import
│   ├── Function ER         — same, + arguments object
│   └── Module ER           — import bindings (always live bindings)
├── Object ER               — var at global scope (properties of globalThis)
└── Global ER               — composite: Declarative ER + Object ER
```

**Function Environment Record** — the most common in practice. Stores local variables, `arguments`, and `this` binding (for regular functions).

**Global Environment Record** — composite:
- `ObjectEnvironmentRecord` (wraps `globalThis`) — stores `var` variables and function declarations as properties of the global object
- `DeclarativeEnvironmentRecord` — stores top-level `let`/`const` (they do NOT become properties of `globalThis`)

```js
var x = 1;
let y = 2;

console.log(globalThis.x); // 1  — var became a property of globalThis
console.log(globalThis.y); // undefined — let did NOT become a property
```

## LexicalEnvironment vs VariableEnvironment — why there are two

Before ES2015 they were the same. ES2015 introduced `let`/`const` with block scope, which needed to be separated from `var`.

```txt
function outer() {
  var a = 1;   // → VariableEnvironment (ignores blocks)
  let b = 2;   // → LexicalEnvironment (block-aware)

  if (true) {
    var c = 3; // → VariableEnvironment of outer() (var ignores the block)
    let d = 4; // → LexicalEnvironment of the new block (not visible outside if)
  }

  console.log(a); // 1
  console.log(b); // 2
  console.log(c); // 3 — var "leaked" out of the block
  console.log(d); // ReferenceError
}
```

When the engine encounters `{` (a block), it creates a new Declarative Environment Record for the block's `let`/`const`, sets it as the new `LexicalEnvironment`, but `VariableEnvironment` stays the same (belonging to the function or global context).

## Scope Chain — the identifier resolution mechanism

The scope chain is not a separate data structure. It's the **chain of `outer` references** between Environment Records. Each record has an `[[OuterEnv]]` field pointing to the lexically enclosing record.

```js
const globalVar = 'global';

function outer() {
  const outerVar = 'outer';

  function inner() {
    const innerVar = 'inner';
    console.log(innerVar);  // found in inner's ER
    console.log(outerVar);  // found in outer's ER (via [[OuterEnv]])
    console.log(globalVar); // found in global ER (via [[OuterEnv]].[[OuterEnv]])
    console.log(missing);   // traversed entire chain → ReferenceError
  }

  inner();
}
```

**The key insight**: `[[OuterEnv]]` is determined **lexically** (where the function is written in the source code), not **dynamically** (from where it's called). This is called **lexical scoping**.

```js
// Predict the output:
const x = 'global';

function makeGetter() {
  const x = 'closure';
  return function get() {
    return x;
  };
}

const get = makeGetter();

function runner() {
  const x = 'runner';
  return get(); // which 'x' does 'get' see?
}

console.log(runner()); // ?
```

<details>
<summary>Answer</summary>

**`'closure'`**

`get` closes over the Environment Record of `makeGetter` (established when it was created). When `get()` is called inside `runner()`, `runner`'s scope is not accessible to `get` — it's not lexically enclosing. The lookup follows the `[[OuterEnv]]` chain from `get` → `makeGetter` → global. `x = 'runner'` in `runner()` is an entirely separate scope, invisible to `get`.

</details>

## The global execution context

The global context is created once when the script starts. Notable properties:

```txt
Global Execution Context:
  ThisBinding    → globalThis (window in browser, global in Node.js)
  LexicalEnv    → Global Environment Record
    ObjectEnvRec → the global object (window/global)
    DeclaEnvRec  → top-level let/const/class
  VariableEnv   → same Global Environment Record
  OuterEnv      → null (nothing outside)
```

```js
// In a browser:
var a = 1;
let b = 2;
function foo() {}

window.a;    // 1
window.b;    // undefined (let doesn't go into the Object ER)
window.foo;  // function foo() {} (function declaration does)

// globalThis works in both environments:
globalThis.a; // 1 (browser and Node.js)
```

## Temporal Dead Zone — what actually happens

The TDZ is not a "protection mechanism" or a special memory region. It's a **state of a binding** in the Environment Record: **created but not yet initialized**.

The spec prohibits reading or writing a binding in this state. Any attempt throws a `ReferenceError`.

```js
// Predict the output:
let x = 'outer';

{
  console.log(x); // ?
  let x = 'inner';
}
```

<details>
<summary>Answer</summary>

**`ReferenceError: Cannot access 'x' before initialization`**

This is a trap. The intuition says: "the block started, `let x` hasn't been encountered yet — so we should see the outer `x = 'outer'`." That's wrong.

During the creation phase of the block, the engine scans the entire block and creates a TDZ binding for the inner `let x`. This binding **shadows the outer `x` from the very start of the block**. So `console.log(x)` resolves to the inner (TDZ) `x`, not the outer one — and throws a ReferenceError.

</details>

## Function scope vs block scope — the mechanics

```js
// var — function scope, not block scope
function example() {
  if (true) {
    var result = 'found'; // created in the function's VariableEnvironment
  }
  console.log(result); // 'found' — var leaked out of the if block
}

// let/const — block scope
function example2() {
  if (true) {
    let result = 'found'; // created in the block's LexicalEnvironment
  }
  console.log(result); // ReferenceError — result is not visible here
}

// for loop: var vs let
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0); // 3, 3, 3
  // var i — one shared variable; by the time callbacks run, the loop is done
}

for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0); // 0, 1, 2
  // let i — a new binding is created per iteration; each callback
  // closes over its own separate i
}
```

Why does `let i` in a `for` loop create a new binding per iteration? The spec explicitly requires it: at the start of each iteration, the loop creates a new copy of the LexicalEnvironment with the current counter value.

## Connection to other topics

```txt
[Closures]              — a closure = a function + a reference to an
                           Environment Record (not a snapshot of variables —
                           a live reference)
[this binding]          — ThisBinding is a separate part of the Execution
                           Context, unrelated to the Scope Chain
[Generators]            — a generator stores execution state inside its
                           Execution Context (the code evaluation state field)
[ESM vs CJS modules]    — Module Environment Record: import bindings are live
                           bindings in the LexicalEnvironment
```

## Common interview traps

- **"Hoisting moves code to the top"** — code doesn't move. Bindings are created during the creation phase; code runs during the execution phase. Different steps, not relocation.

- **"let and const aren't hoisted"** — they are hoisted, but land in the TDZ. The engine knows about them from the start of the block — otherwise a variable with the same name from an outer scope would be visible before the `let` declaration (see the TDZ example above).

- **"The scope chain is a dynamic lookup up the call stack"** — no. `[[OuterEnv]]` is fixed at the moment the function is created (lexically), not when it's called. This is exactly what makes closures work.

- **"var in an if/for/while block is block-scoped"** — no. `var` is always function-scoped (or global-scoped). Blocks are transparent to `var`.

- **"Top-level let/const are accessible via window"** — no. `var` at the top level → property of `globalThis`; `let`/`const` at the top level → only in the DeclarativeEnvironmentRecord of the global context, not accessible via `window`.

- **Not knowing the difference between `LexicalEnvironment` and `VariableEnvironment`** — for a senior interview this matters: one context, two references to different Environment Records. `var`/`function` → VE; `let`/`const`/`catch` → LE. This is what allows `let` to be block-scoped while `var` is function-scoped — both coexisting in the same function context simultaneously.
