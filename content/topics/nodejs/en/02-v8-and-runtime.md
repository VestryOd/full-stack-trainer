# V8 and Node.js Runtime

## V8 is a pipeline, not "one compiler"

V8 doesn't compile code entirely up front, and it doesn't interpret it line by line forever. It is a multi-stage pipeline. The pipeline **progressively raises compilation quality for hot code**, and it falls back if its assumptions about that code turn out to be wrong.

```txt
Source code
    ↓
Parser → AST (Abstract Syntax Tree)
    ↓
Ignition (baseline interpreter) → Bytecode
    ↓ (if the function is called often — "hot")
TurboFan (optimizing JIT compiler, JIT = just-in-time)
    → optimized machine code
    ↑ ↓
    └── Deoptimization (if assumptions are violated —
        falls back to bytecode, see below)
```

The main practical takeaway from this diagram: V8 optimizes code **based on observed behavior**, not on static type analysis. TypeScript, for example, works the other way round — it analyses types at compile time.

So the same code can run at different speeds depending on what data has flowed through it before. That is why "warm-up" is a real phenomenon, and why it is worth accounting for when you load-test a Node service.

## Ignition and TurboFan: baseline vs optimized

```txt
Ignition:
  - starts running the function immediately, no compile delay
  - generates compact bytecode
  - collects feedback (a profile of argument types, object shapes)

TurboFan:
  - kicks in once V8 sees a function is "hot"
    (called many times with the same "profile")
  - uses Ignition's feedback to generate machine code
    specialized for the types it has observed
  - the result is machine code several times faster than
    interpreted code, but valid only for that type profile
```

```ts
function add(a: number, b: number) {
  return a + b;
}

// If add is called thousands of times, always with numbers —
// TurboFan generates machine code that expects numbers
// (e.g., an unboxed SMI representation; SMI = small integer)
for (let i = 0; i < 100_000; i++) add(i, i + 1);

// A sudden call with a different type — the TurboFan code is
// no longer valid for this case → deoptimization
add('5', '10'); // V8 falls back to Ignition bytecode for this
                 // call site (at minimum, for it)
```

## Deoptimization — the flip side of JIT that's rarely discussed

Deoptimization isn't an "error" — it's a normal V8 mechanism. JIT here means just-in-time: V8 compiles while the program runs, based on assumptions about the code it has seen.

Sometimes optimized code hits a situation it wasn't specialized for: a different argument type, a changed object shape, a deleted property. Then V8 **falls back** to bytecode execution for that part of the code, and loses TurboFan's benefits on that path.

```ts
// ❌ A polymorphic function — called with objects of different "shapes"
function getArea(shape) {
  return shape.width * shape.height;  // Circle has no height!
}

getArea({ width: 10, height: 5 });          // Rectangle-like shape
getArea({ width: 10, radius: 5 });          // a different "shape" → polymorphic call site
```

Senior nuance: one or two polymorphic types at a call site (bimorphic) is fine. V8 handles a small number of shapes reasonably well.

The problem starts with **megamorphic** call sites — many different object shapes flowing through the same function. There V8 stops trying to specialize the code and falls back to the slowest generic path.

On a hot path, then, the shape of the objects flowing through a function genuinely matters for performance. A hot path here means parsing thousands of records in a loop, or middleware handlers that run on every request.

## Hidden Classes (Shapes) and why an object's shape matters

V8 doesn't store objects as a "property name → value" hash map — that would be too slow for property access. Instead, each object is associated with a **Hidden Class**, called a "Map" or a "Shape" inside the engine. The Hidden Class describes the in-memory layout of the properties, much the way a C++ compiler knows the field offsets of a struct.

```ts
// Both objects are created with the same order and set of properties
const user1 = { name: 'Alice', age: 30 };
const user2 = { name: 'Bob', age: 25 };
// → user1 and user2 share the same Hidden Class
// → functions operating on such objects can be monomorphic and fast

// ❌ Changing the shape of an object after creation —
// creates a new Hidden Class for this specific object
const user3 = { name: 'Carol', age: 28 };
user3.address = 'London';  // a new Hidden Class, different from user1/user2

// ❌ Deleting a property — also creates a new (and often
// "slow", dictionary-mode) Hidden Class
delete user3.age;
```

```txt
Practical consequence — constructors and factories should
always initialize every field of an object, even when the
value isn't known yet:

  ❌ class User {
       constructor(name) {
         this.name = name;
         // address is added later, in a different method
       }
     }

  ✅ class User {
       constructor(name, address = null) {
         this.name = name;
         this.address = address;  // the field exists from the
                                   // start, even if null
       }
     }
```

This isn't a "micro-optimization for enthusiasts". Take code that creates thousands of same-shaped objects on a hot path — mapping database rows to DTOs, for example. A DTO (data transfer object) is a plain object whose only job is to carry data between layers.

There, consistent object shapes decide something concrete: whether V8 stays in its "fast" mode, or falls back to dictionary-mode property storage.

## Inline Caches — a cache of "where to find this property"

Inline Cache (IC) is a mechanism that complements Hidden Classes. Take any place in the code where a property is accessed, such as `obj.name`. V8 remembers the object's Hidden Class and the property's offset **right at that code site**.

```txt
function getName(obj) {
  return obj.name;  // ← V8 creates an Inline Cache here
}

First call getName(user1):
  - V8 sees user1's Hidden Class
  - remembers: "for this Hidden Class, name is at offset 0"
  - the IC becomes monomorphic (1 remembered shape)

Subsequent calls with objects of the same Hidden Class:
  - V8 reads offset 0 directly, no property lookup — very fast

A call with an object of a different Hidden Class:
  - the IC becomes polymorphic (remembers 2-4 shapes)
  - past the shape limit → megamorphic, the IC stops helping,
    a generic lookup is used
```

Hidden Classes and Inline Caches are two sides of the same idea. JS is dynamic: any property can be added or removed at any time. V8 tries to turn that into static, predictable structures, like the ones compiled languages have. It only works as long as the code actually behaves predictably.

## The Heap: where V8 stores objects, and why it matters for GC

Two areas hold your data: the stack and the heap. Where an object lands on the heap decides how the GC (garbage collector — the part of V8 that frees unused memory) will treat it.

```txt
Stack:
  - primitives, references, function call frames
  - managed automatically on function enter/exit

Heap — split into "generations" (the generational hypothesis:
most objects die young):

  New Space (Young Generation):
    - new objects are created here
    - small size → garbage collection here (Scavenger) —
      frequent but fast (most objects are already dead)

  Old Space (Old Generation):
    - objects that "survive" several Scavenger cycles get
      "promoted" here
    - collection here (Mark-Compact/Mark-Sweep) — less often,
      but expensive (a full traversal of the object graph)
```

GC algorithms, practical memory-leak patterns and heap snapshots are covered in full in [Memory, Heap, Stack, and Garbage Collection](./08-memory-garbage-collection.md). The connection worth fixing here is narrower.

Whether an object created in New Space dies quickly or gets "promoted" to Old Space is tied directly to Hidden Classes and object shapes. So reusing same-shaped objects in hot loops does two things at once. It speeds up property access, and it reduces the pressure on the GC.

## Runtime = V8 + Node APIs + libuv

```txt
V8 can:           V8 cannot (and that's fine — it's not
  - run JS           its responsibility):
  - manage the heap    - read files
  - JIT/deopt           - open sockets
  - GC                   - work with operating system timers
                         - resolve DNS names (Domain
                           Name System)
```

Node fills this gap:

```txt
fs, net, http, crypto, timers, dgram, ...
    ↓ (C++ bindings)
libuv — provides the event loop and thread pool
    ↓
operating system calls: epoll (Linux), kqueue (macOS),
IOCP (I/O completion ports, Windows), read a file, ...
```

One line of code crosses all three layers. When you write `await fs.promises.readFile(...)`:

1. V8 runs your async code and manages the Promise.
2. The Node API wraps the call into a form libuv understands.
3. libuv decides how to actually perform it — on the thread pool, or through an async API of the operating system (OS).

The layers themselves are covered in [Event Loop](./03-event-loop.md) and [libuv and the Thread Pool]. The Promise part is in [Microtasks, Macrotasks, and process.nextTick](./04-microtasks-macrotasks-nexttick.md).

## Practical takeaway: when V8 internals actually matter

```txt
Matters:
  - hot paths with thousands/millions of iterations (parsing,
    data mapping, computation in a loop)
  - libraries/frameworks that all traffic flows through:
    row-to-object mapping in an ORM (object-relational
    mapper), validators, serializers
  - data structure choices for frequently mutated objects
    with unpredictable shape (a Map instead of a plain object,
    if keys are dynamic)

Almost never matters:
  - "handle one HTTP request" business logic — a nanosecond
    difference in property access disappears next to
    milliseconds of I/O (a database call, the network)
  - micro-optimizations that hurt readability for the sake of
    "monomorphism" at a call site invoked 10 times in the
    process's entire lifetime
```

This calibration is deliberate, and it is worth voicing in an interview. Knowing about Hidden Classes and ICs shows that you understand the engine. Applying that knowledge as a blanket rule is a different thing.

Take the rule "always initialize every field in the constructor, even the unused ones". In code that is not a hot path, that is optimizing where nothing needs optimizing. In a senior interview that is a signal too, and a negative one.

## Common interview mistakes

- **"V8 interprets JS"** — with no mention of Ignition (baseline bytecode) or TurboFan (the optimizing JIT). Modern V8 is a multi-stage pipeline, not a pure interpreter.

- **Hidden Classes as "just a Wikipedia fact"** — with no concrete consequence attached. The consequence: inconsistent field initialization, or adding and removing properties at run time, creates new Hidden Classes and can deoptimize hot functions.

- **Not knowing about deoptimization** — treating JIT as "compiled once, always fast" without understanding that V8 can fall back to bytecode if type assumptions are violated.

- **Confusing V8 and Node** — attributing fs/net/http capabilities to V8 when they're actually provided by Node via libuv and C++ bindings.

- **Applying micro-optimizations in the wrong place** — over-engineering ordinary business code "for V8's sake" when the real bottleneck is I/O, not property access.
