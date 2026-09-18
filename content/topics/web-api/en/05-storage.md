# A browser's storages each do a different job

A browser ships several different storages, and they aren't
interchangeable: one reads instantly but blocks code while it does;
another is asynchronous and handles megabytes with ease; a third is
visible only to a service worker. Picking the wrong storage for a
note's draft is a common cause of interface stutter and data loss
that was easy to avoid.

## Each storage has its own rules: speed, size, and visibility

Before picking a storage, it helps to line their rules up in one
table.

| storage | synchronous | survives a reload | visible to a service worker |
|---|---|---|---|
| `localStorage` | yes | yes | no |
| `sessionStorage` | yes | no, tab only | no |
| `IndexedDB` | no | yes | yes |
| Cache Storage | no | yes | yes |

The difference between `localStorage` and `sessionStorage`, plus
where cookies fit into this list, is covered in depth by Browser /
JS Runtime — that comparison already exists there, so repeating it
here would add nothing. This table adds what that comparison
doesn't: `IndexedDB` and Cache Storage next to Web Storage, and which
of them a service worker can see.

## `localStorage` blocks the main thread because it reads disk right away

`localStorage.getItem` returns a value on the same line that called
it — which means the browser must finish reading from disk right
now, not at some later point.

```ts
const t0 = performance.now();
localStorage.setItem('draft', body);
const saved = localStorage.getItem('draft');
console.log(performance.now() - t0); // 0.8 — barely visible for one key
```

One operation costs under a millisecond, but notes aren't a single
key: autosaving a draft on every keystroke multiplies that cost by
typing speed. `IndexedDB` works differently — `indexedDB.open()`
returns a request object right away, not the data, and the result
arrives later through an event.

```ts
const isRequest = indexedDB.open('notes') instanceof IDBRequest;
console.log(isRequest); // true — opening blocks nothing at all
```

Storing an access token in `localStorage` is a separate question of
security, not speed — Browser / JS Runtime covers it, along with what
actually reduces the risk of theft through cross-site scripting
(XSS).

## Quota is an estimate, not an exact number

The method `navigator.storage.estimate()` returns not a hard limit
but an approximate reading of free space.

```ts
const { quota, usage } = await navigator.storage.estimate();
console.log(quota, usage);
```

```txt
Run 1, same setup:   quota 3,221,225,472   usage 0
Run 2, same setup:   quota 4,294,967,296   usage 0
```

Both numbers came from the same Chromium 153 on the same machine, on
different days. Quota depends on free disk space and browser policy,
so it can't be baked into code as a constant — only asked for again.

```ts
// After writing ~1MB to IndexedDB, usage grows, but not by exactly
// 1,000,000 bytes: the estimate is rounded, and that's expected,
// not a bug in your code
const before = await navigator.storage.estimate();
await saveDraftBlob(bigDraft);
const after = await navigator.storage.estimate();
console.log(after.usage - before.usage); // roughly 1MB, not exact
```

## Persistent storage guards data from eviction, but doesn't promise it

Once a device runs low on space, the browser may evict data from an
origin nobody has used in a while — that's called eviction.

```txt
Two storage modes: default and protected
┌────────────────────────────────────────────────┐
│ Best-effort — the default mode                 │
│ space runs low — the browser evicts data       │
├────────────────────────────────────────────────┤
│ Persistent — after navigator.storage.persist() │
│ the browser usually leaves data alone          │
└────────────────────────────────────────────────┘
the browser decides on its own — a heuristic, not a guarantee
```

```ts
console.log(await navigator.storage.persisted()); // false
console.log(await navigator.storage.persist());   // false on this setup
console.log(await navigator.storage.persisted()); // false
```

On a setup with no real browsing history, the browser refused
persistent mode — and that's expected: the decision rests on a
heuristic of user engagement, not on the call itself. Persistent mode
lowers the risk of eviction, but doesn't remove it entirely — a
person can still clear a site's data by hand at any time.

## What to pick for a note's draft

This topic's running example is the notes feed, and a new note's
draft needs saving on every change without blocking typing.

| scenario | fitting storage |
|---|---|
| One flag: is the sidebar collapsed | `localStorage` — a small value, read rarely |
| A note's draft text, saved on every keystroke | `IndexedDB` — asynchronous, never blocks typing |
| An attachment captured from the camera | `IndexedDB` — can store a whole `Blob` |
| A half-filled login form | `sessionStorage` — shouldn't outlive the closed tab |
| An offline copy of the server's responses | Cache Storage — a service worker reads it |

```ts
// Autosaving a draft: IndexedDB never blocks the text field
noteBody.addEventListener('input', async (e) => {
  const text = (e.target as HTMLTextAreaElement).value;
  await saveDraft({ id: currentNoteId, text, savedAt: Date.now() });
});
```

## Common mistakes

- **Saving a note's draft to `localStorage` on every keystroke.**
  Symptom: typing stutters on long notes, even though the code looks
  short and simple.
- **Hardcoding quota as a number from one measurement.** Symptom: the
  code fails a space check on another device, or even on the same one
  a month later.
- **Treating `persist()` like a notification-style permission.**
  Symptom: the code waits for an Allow/Deny dialog, while the browser
  decides silently, without asking the person at all.
- **Forgetting `localStorage` is invisible to a service worker.**
  Symptom: code in a `fetch` handler tries to read `localStorage` and
  crashes, because no such object exists in that scope.

## Related topics

- [A service worker is a network go-between that outlives the page](./04-service-worker.md) —
  Cache Storage, the one it reaches for most.
- [How tabs of the same app coordinate with each other](./06-cross-tab.md) —
  the `storage` event reports a `localStorage` change only to other
  tabs, never to the one that made it.
- Browser / JS Runtime — the question bank: `localStorage` versus
  `sessionStorage` versus cookies, token security, and a
  cursor-pagination pattern for `IndexedDB`.
- React — the task bank with component-level `localStorage` practice,
  not platform mechanics.
