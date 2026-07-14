# The GIL, threads, and processes — a conceptual bridge to asyncio

## Theory

**What the GIL is.** The Global Interpreter Lock is a single mutex in CPython (this is specifically a CPython implementation detail, not a requirement of the Python language spec — Jython/IronPython don't have one, and CPython 3.13+ has an experimental "free-threaded" build without it, PEP 703, not yet the default) that guarantees exactly **one** thread executes Python bytecode at any given instant, even on a multi-core machine. The GIL dates back to CPython's early days as a simple fix for a specific problem: CPython's garbage collection is reference-counting based, and incrementing/decrementing a reference count isn't thread-safe on its own without some kind of lock. Instead of fine-grained, per-object locking (complex, and shown by early experiments to slow down single-threaded code), CPython settled on one global lock for the whole interpreter.

In practice this means: you can create as many threads as you like (`threading.Thread`), and the OS will genuinely context-switch between them at the kernel level — but only the thread currently "holding" the GIL will be executing Python bytecode at any given moment. CPython periodically forces the running thread to hand off the GIL — on a timer (configurable via `sys.setswitchinterval`, roughly every ~5ms by default) and, crucially, **immediately on entering a blocking call** (a network request, a file read, `time.sleep`) — the GIL is explicitly released for the duration of the wait, and another thread can pick it up.

**Why this is NOT the same as Node's single-threaded event loop — a common point of confusion for JS developers.** Hearing "only one thread executes at any given moment" it's tempting to conclude: "oh, that's the same thing Node does — one thing at a time, just under a different name." That's not the case, and the difference is fundamental:

```txt
Node:
  Exactly one OS thread runs your JS code. Period. There is no
  switching between multiple threads for your code at all —
  concurrency for I/O comes from the event loop + libuv (see the
  Node.js chapters in content/topics), not from several threads
  competing for a turn.

Python (CPython) with the GIL:
  There GENUINELY are several OS threads (threading.Thread), and the
  OS genuinely context-switches between them at the kernel level
  (preemptive scheduling). The GIL is an ADDITIONAL mutex layered ON
  TOP of an already genuinely multithreaded model, restricting which
  single thread gets to execute bytecode at a time — it's not "Python
  is architecturally single-threaded," the way Node is.
```

The practical consequence of this difference shows up exactly where the two models behave *differently*, not the same: if you accidentally write synchronous, CPU-heavy code in a Node handler, it blocks **absolutely everything**, the entire process, because there's no other thread for anything else to run on at all. Do the same thing in Python across several `threading.Thread`s, and CPython will still periodically switch the GIL between threads (on its timer) — other threads get **some** slices of time, they just don't get any real speedup from it (see below) — this isn't "the same blocking behavior as Node," it's an architecturally different situation that happens to look superficially similar but isn't identical.

**When the GIL gets in the way (CPU-bound), and when it doesn't (I/O-bound).**

For **CPU-bound** work (pure computation in Python bytecode: loops, arithmetic, parsing), the GIL genuinely gets in the way: no matter how many threads you create, only one of them executes bytecode at any instant, so the total amount of work doesn't get done any faster — and you also pay for the overhead of switching the GIL between threads. `threading` is not a speedup tool for CPU-bound work in Python.

For **I/O-bound** work (network, disk, waiting on a database response), the GIL **doesn't** get in the way, because CPython explicitly releases it for the duration of a blocking call — another thread can run while the first one waits for the OS to respond. Here `threading` gives a real, measurable win: the total time for several concurrent I/O waits approaches the time of the **slowest** one, not the sum of all of them.

An important caveat for completeness: some C extensions (heavy computational parts of numpy, for instance) explicitly release the GIL themselves during long C-level loops — so "CPU-bound = the GIL gets in the way" holds for pure Python bytecode, but isn't absolute for every CPU-bound workload if there's C code underneath managing the GIL on its own.

**`threading` vs `multiprocessing` — different tools for different jobs.**

```python
import threading

t = threading.Thread(target=fn, args=(...,))
t.start()
t.join()
```

Lightweight, shares the process's memory (every thread sees the same objects) — a good fit for I/O-bound concurrency; gives no parallelism for CPU-bound work because of the GIL.

```python
import multiprocessing

p = multiprocessing.Process(target=fn, args=(...,))
p.start()
p.join()
```

Heavier (a separate process, a separate interpreter, a separate GIL — the GIL simply doesn't get in the way, because each process has its **own**), genuinely runs in parallel across cores — a good fit for CPU-bound work; data isn't shared between processes by default, it's passed via serialization (pickle) rather than shared memory.

A useful parallel for a JS developer: Node's Worker Threads are also separate threads with their own V8 isolate and heap — data between them isn't directly shared by default either, it's passed via messages/serialization — conceptually this is closer to Python's `multiprocessing.Process` than the word "thread" might suggest. Both Node and Python ultimately land on the same architectural answer for real CPU-bound parallelism: an isolated execution context plus message-passing, rather than freely shared mutable memory.

### Parallels with JS/TS/Node:

- Node has, in principle, exactly one OS thread for JS; Python with the GIL genuinely has several OS threads, but only one executes bytecode at a given instant. Similar surface effect ("one at a time"), different architecture.
- Synchronous CPU-bound code in Node blocks the entire process (there's simply no other thread); the same code in Python across several `threading.Thread`s will still periodically switch between them — just with no real speedup.
- I/O-bound concurrency: Node achieves it via a single-threaded event loop; Python achieves it via several genuine threads, with the GIL handed off during blocking calls. Different mechanisms, similar practical outcome.
- `multiprocessing.Process` in Python and Worker Threads in Node solve the same problem (real parallelism for CPU-bound work) in a similar way: an isolated context plus messages, instead of shared memory.

## What we're adding to the project

Nothing — `taskman` doesn't change by a single line this chapter. This is a conceptual bridge to chapter 12 (`asyncio`): a CLI, invoked fresh for every command, doesn't benefit from multithreading or multiprocessing right now — there's nothing inside a single invocation that needs to run concurrently. The point of this chapter is to build a correct mental model of "what threading in Python can and can't actually speed up," before the storage layer goes async (not multithreaded) in the next chapter — and it matters to understand in advance why that's a deliberate, meaningful choice, not just "another way to do the same thing."

## Practical exercise

Instead of changes to `taskman` — three small, standalone experiment scripts (write them anywhere outside the package, in scratch space). For each one, predict the result first, then measure and compare against your prediction.

1. **CPU-bound + threading.** A function running a plain Python loop (`for i in range(N): total += i * i`) with `N` large enough that it takes a couple of seconds. Time calling the function twice, sequentially, in one thread, then time calling it via two `threading.Thread`s. Do you expect close to a 2x speedup?

2. **CPU-bound + multiprocessing.** The same function, but via two `multiprocessing.Process`es instead of threads. Measure and compare against experiment 1.

3. **I/O-bound + threading.** A function simulating blocking I/O via `time.sleep(1)`. Time calling it twice sequentially, and via two threads.

Things to think through before looking at the worked solution:

- In experiment 1, compare the numbers: are they the same, roughly twice as fast, or somewhere in between? Whatever it turns out to be — how is that explained by the GIL's mechanics, rather than just "thread overhead"?
- Why does `time.sleep` let threads "run at the same time" at all in experiment 3, if the GIL only ever lets one thread execute bytecode at a time?

## Worked solution

Experiment 1 — CPU-bound work via `threading`:

```python
import threading
import time


def cpu_bound_work(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total


N = 80_000_000

start = time.perf_counter()
cpu_bound_work(N)
cpu_bound_work(N)
print(f"sequential (2x, one thread):  {time.perf_counter() - start:.2f}s")

start = time.perf_counter()
t1 = threading.Thread(target=cpu_bound_work, args=(N,))
t2 = threading.Thread(target=cpu_bound_work, args=(N,))
t1.start()
t2.start()
t1.join()
t2.join()
print(f"two threads (same work):      {time.perf_counter() - start:.2f}s")
```

Real measurement (an 11-core machine):

```txt
sequential (2x, one thread):  6.17s
two threads (same work):      5.66s
```

Two threads do NOT produce anything close to a 2x speedup — the ~8% difference falls within scheduler noise and incidental overlap windows around GIL handoffs, not real parallelism. The GIL still only lets one thread execute bytecode at any given moment — both threads just take turns getting short slices of time.

Experiment 2 — the same CPU-bound work via `multiprocessing`:

```python
import multiprocessing
import time


def cpu_bound_work(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total


N = 80_000_000

if __name__ == "__main__":
    start = time.perf_counter()
    cpu_bound_work(N)
    cpu_bound_work(N)
    print(f"sequential (2x, one process): {time.perf_counter() - start:.2f}s")

    start = time.perf_counter()
    p1 = multiprocessing.Process(target=cpu_bound_work, args=(N,))
    p2 = multiprocessing.Process(target=cpu_bound_work, args=(N,))
    p1.start()
    p2.start()
    p1.join()
    p2.join()
    print(f"two processes (same work):   {time.perf_counter() - start:.2f}s")
```

Real measurement:

```txt
sequential (2x, one process): 6.31s
two processes (same work):   3.26s
```

A ~48% reduction in time — close to the theoretical 2x for two genuinely parallel processes on separate cores. The difference from experiment 1 isn't in the task's code (it's identical) — it's purely that each process has its own interpreter and its own GIL, which doesn't compete with the other process's GIL at all.

Experiment 3 — I/O-bound work via `threading`:

```python
import threading
import time


def io_bound_work() -> None:
    time.sleep(1)  # stands in for a blocking network/disk wait


start = time.perf_counter()
io_bound_work()
io_bound_work()
print(f"sequential (2x, one thread): {time.perf_counter() - start:.2f}s")

start = time.perf_counter()
t1 = threading.Thread(target=io_bound_work)
t2 = threading.Thread(target=io_bound_work)
t1.start()
t2.start()
t1.join()
t2.join()
print(f"two threads (same work):     {time.perf_counter() - start:.2f}s")
```

Real measurement:

```txt
sequential (2x, one thread): 2.01s
two threads (same work):     1.01s
```

Nearly perfect overlap — exactly because `time.sleep` (and any blocking call that drops down to the OS) explicitly releases the GIL for the duration of the wait. While one thread is "asleep," the GIL is free, and the other thread can run — both waits overlap, and the total time approaches the time of a single wait, not the sum of two.

## Check yourself

1. Why doesn't spinning up ten `threading.Thread`s in Python give a tenfold speedup on a purely computational task, even on a ten-core machine?
2. What's the actual, fundamental difference between "Node runs one thread at any given moment" and "CPython's bytecode is executed by one thread at any given moment," when both statements sound nearly identical?
3. Why does a blocking call like `time.sleep()` or a network request let the GIL be "released," while a plain Python loop doesn't? What specifically about the nature of a blocking call makes that possible?
4. If a task is CPU-bound, why does `multiprocessing.Process` give a real speedup while `threading.Thread` doesn't, given that both technically create something that looks like "a unit of work running in parallel"?
5. How is `multiprocessing.Process` in Python conceptually similar to Worker Threads in Node, rather than to "just another thread in the same sense as threading.Thread"?

<details>
<summary>Answers</summary>

1. Because the GIL guarantees that exactly one thread executes Python bytecode at any given moment, regardless of how many cores are available or how many threads exist. Ten threads simply take turns getting short slices of CPU time on one core (as far as executing Python bytecode specifically goes) — the total amount of computational work that needs doing doesn't shrink or spread across cores, so the overall time ends up roughly equal to running the same work sequentially, plus a bit of overhead from switching between threads.
2. In Node, "one thread at a time" literally means there's only one OS thread for your code in existence — there's nothing else to switch to; no other threads are competing for a turn at all. In CPython, "bytecode is executed by one thread" describes a mutex layered on top of **genuinely multiple** OS threads that the OS truly context-switches at the kernel level (preemptive scheduling) — the GIL only restricts which one of them has the right to execute Python bytecode right now. On the surface, both statements about "one at a time" sound similar, but they describe fundamentally different architectures, with different practical consequences (see question 4 and the I/O-bound experiment).
3. A blocking call hands control to the operating system and waits for its response (data from disk, a network packet, a timer expiring) — during that wait, the Python interpreter physically has nothing to execute for that thread, so CPython explicitly releases the GIL for the duration of the wait, handing it to another thread that actually has bytecode to run. A plain Python loop, by contrast, is constantly doing real bytecode-level computation the whole time — the GIL can only be released from it forcibly, on the switch-interval timer, not because the thread "has nothing to do."
4. `multiprocessing.Process` creates a completely separate process with its own instance of the Python interpreter and, therefore, its own GIL — one process's GIL physically cannot stop another process's bytecode from executing simultaneously on a different core, because they're two independent mutexes in two independent address spaces. `threading.Thread` creates threads **within the same** process, sharing one single GIL among all of them — no matter how many threads exist, only one of them at a time has the right to execute Python bytecode.
5. Both solve the problem "get real parallelism for CPU-heavy work" via the same architectural approach: an isolated execution context (a separate process with its own memory for Python, a separate thread with its own V8 isolate and heap for Node) plus exchanging data via messages/serialization, rather than freely shared mutable memory. Neither `threading.Thread` in Python nor plain single-threaded code in Node itself fits that description — both share one single execution context (shared memory, and in Python's case, a shared GIL), rather than isolating computations from each other.

</details>

## Common mistake

The most common mistake a JS developer makes on first meeting the GIL is drawing exactly the conclusion spelled out above: "Python has a GIL, so it's just as single-threaded as Node, only under a different name" — and from there, deciding that `threading` in Python is useless altogether, since "only one thread runs at a time anyway." That's a dead end on both sides: `threading` in Python **genuinely is** useless for speeding up CPU-bound work (the instinct isn't wrong there), but it's a perfectly working, idiomatic tool for I/O-bound concurrency — exactly the kind of task a JS developer is used to reaching for Node's single-threaded event loop to handle. Conflating the architectural detail (the GIL) with the blanket conclusion "multithreading is pointless in Python" makes it easy to miss that `threading` for I/O-bound code in Python produces a result that's practically indistinguishable in spirit from what Node's event loop produces — just through a different mechanism.

The second common mistake, a mirror image of the first, is seeing that `multiprocessing` gives a real speedup on a CPU-bound task and concluding it's "just a beefier version of threading" that should be reached for always, including for I/O-bound work. `multiprocessing` isn't "threading, but better": each process is a separate interpreter with its own memory, spinning up a process is noticeably more expensive than spinning up a thread, and data isn't shared directly between processes by default — it's pickled on every handoff. That overhead is well worth paying for heavy, infrequent CPU-bound tasks, but becomes pure waste for lightweight, frequent I/O-bound operations, where `threading` (or, even more fittingly, `asyncio` from the next chapter) ends up both faster and considerably lighter on resources.
