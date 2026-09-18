# Heavy work leaves the main thread

The browser's main thread is one and the same thread for your code,
style recalculation, page layout, and painting a frame. If synchronous
code runs long on it, everything else — clicks, scrolling, animation —
waits its turn. A background thread, called a `Worker`, gives code its
own thread with no access to the page, talking to it only through
messages.

## The main thread handles layout and your code at once

A search over note text is a common source of long synchronous work,
because it grows along with the number of notes.

```ts
// Search right inside the input handler: as the feed grows, every
// keystroke freezes the interface for a little longer
searchInput.addEventListener('input', (e) => {
  const query = (e.target as HTMLInputElement).value;
  const matches = notes.filter((n) => n.body.includes(query));
  renderResults(matches); // at 5,000 notes this is already a pause
});
```

While `filter` walks through five thousand notes, the browser can't
handle the next click and can't paint a frame. One and the same
thread serves both your code and the page's interface.

## A worker is its own environment, not a stripped-down page

A `Worker` runs code on a separate thread with its own environment,
and that environment isn't a copy of the page with fewer rights.

| available in a worker | not available in a worker |
|---|---|
| `self`, `fetch`, `importScripts` | `window`, `document` |
| `navigator`, `setTimeout` | access to page elements |
| `IndexedDB`, `caches`, `crypto.subtle` | `localStorage`, `sessionStorage` |

This list was captured on the same Playwright 1.63.0, Chromium
153.0.8010.12 setup, September 18, 2026. Neither `localStorage` nor
`sessionStorage` is available to a worker by specification, in any
browser — it isn't one engine's quirk.

```ts
// main.ts — types stay here, the heavy part moves to a worker
const searchWorker = new Worker('search-worker.js');
searchWorker.postMessage({ notes }); // hand over the whole list once

searchInput.addEventListener('input', (e) => {
  const query = (e.target as HTMLInputElement).value;
  searchWorker.postMessage({ query });
});
searchWorker.onmessage = (e) => renderResults(e.data.matches);
```

The main thread now only handles the text field and rendering the
result. Walking through five thousand notes moved to a place where
long work bothers nobody else.

## Data between threads is either copied or transferred

`postMessage` offers two different ways to deliver data, and its
second argument picks between them.

```txt
Two routes from the main thread to a worker
┌────────────────────────────────────────────────┐
│ The main thread calls postMessage(data)        │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│ No transfer: structuredClone copies the data   │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│ With transfer: buf changes owner, no copy made │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│ The worker gets it in self.onmessage           │
└────────────────────────────────────────────────┘
    the choice is postMessage's second argument
```

By default `postMessage` copies data with the same structured-clone
algorithm that `IndexedDB` uses. It clones `Map`, `Set`, `Date`,
`Error`, and most built-in types, but throws on functions, nodes of
the document object model (DOM), and `Symbol` — measured on the same
setup. Pass a list of transferable objects as the second argument,
and no copy happens at all.

```ts
// search-worker.js — gets both the notes and the query as messages
let notes: Note[] = [];

self.onmessage = (e) => {
  if (e.data.notes) notes = e.data.notes;
  if (e.data.query !== undefined) {
    const matches = notes.filter((n) => n.body.includes(e.data.query));
    self.postMessage({ matches });
  }
};
```

```ts
// Transferring ownership of a buffer instead of copying: after this
// line, buf.byteLength on the main thread becomes 0
worker.postMessage({ buf }, [buf]);
console.log(buf.byteLength); // 0 — the data now belongs to the worker
```

A transferable object is an `ArrayBuffer`, a `MessagePort`, or a
similar type that can move from one thread to another without copying
memory. The sender pays for that: once transferred, the original
buffer is empty and can no longer be read.

## A SharedWorker gives several tabs one shared environment

A `SharedWorker` is the same kind of background thread, but more than
one tab can connect to it at once, each through its own `MessagePort`.

```ts
// Every tab of the notes feed connects to one SharedWorker — say, to
// keep a single WebSocket for all of them instead of one per tab
const shared = new SharedWorker('sync-worker.js');
shared.port.start();
shared.port.postMessage({ type: 'subscribe' });
shared.port.onmessage = (e) => applyRemoteChange(e.data);
```

As of this writing, `WebKit` (Safari's engine) does not support
`SharedWorker` — check current browser support tables rather than
this text. While that holds, treat `SharedWorker` as progressive
enhancement, not as the only way to get something done.

## Worklets are another kind of thread, but not for messaging

Worklets are lightweight execution threads for specific browser
subsystems: `PaintWorklet`, for instance, runs custom drawing
functions for CSS. They have no `postMessage` channel back to the
page, and code inside them serves a narrow rendering task, not
general computation. This topic doesn't go deeper into worklets —
they sit closer to rendering than to background computation.

## Common mistakes

- **Creating a new `Worker` for every search query.** Symptom: the
  process list keeps growing, and old background threads stay
  resident in memory. Create a worker once and reuse it.
- **Expecting access to `document` inside a worker.** Symptom: the
  code crashes on the first line where the worker tries to read a
  page element — no such object exists there.
- **Reading `buf` on the main thread right after transferring it.**
  Symptom: `byteLength` is unexpectedly zero, because the data already
  moved to the background thread.
- **Relying on `SharedWorker` without checking support.** Symptom:
  the code silently does nothing in one browser and works in another.

## Related topics

- [The browser reports change on its own](./02-observers.md) — not
  all heavy work needs a background thread; observers handle part of
  it.
- [Big data gets processed in chunks, and work can be cancelled](./08-streams-and-cancellation.md) —
  what to do when even a background thread can't keep up with the
  volume.
- [How tabs of the same app coordinate with each other](./06-cross-tab.md) —
  `SharedWorker` as a shared channel for coordination, not only for
  heavy computation.
- JavaScript — covers `AbortController` and `structuredClone` as
  language features, not as part of the browser platform.
