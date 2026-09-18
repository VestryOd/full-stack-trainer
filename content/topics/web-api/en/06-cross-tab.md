# How tabs of the same app coordinate with each other

Every tab is a separate execution context with its own variables, and
opening a second tab of the same app doesn't create anything shared
between them by itself. Editing a note in one tab won't show up in
another until both start listening to the same channel. A browser
offers four such channels, and each has its own reach and its own
cost.

## Tabs of one origin share a disk, but not memory

A variable declared in one tab doesn't exist in another — each tab's
`window` lives in its own execution context.

```ts
// Tab A
let openNoteId = 42; // only exists here

// Tab B of the same app
console.log(typeof openNoteId); // 'undefined' — a different window
```

Both tabs of the same origin still read the same `localStorage`, the
same `IndexedDB`, and the same cookies — that's a shared disk, not
shared memory. For a tab to learn about a change right away, instead
of on its next load, it needs a dedicated notification channel.

## Four channels exist, and each has its own reach

Before picking a channel, it helps to know who actually hears it.

| channel | who hears it | survives the tab closing |
|---|---|---|
| `BroadcastChannel` | tabs of the same origin on the same channel name | no, only while open |
| the `storage` event | every tab of the origin except the one that wrote | no |
| `SharedWorker` | tabs connected to the same worker file | no, the worker dies with no tabs left |
| Web Locks | nobody — it isn't a message channel, it's a queue | no |

Web Locks never passes data between tabs at all: it decides whose
turn it is to act, not what to tell the others. How `SharedWorker`
works — one process, tabs connecting through ports — is covered in
[Heavy work leaves the main thread](./03-workers.md) and isn't
repeated here.

## `BroadcastChannel` never delivers a message back to its sender

Two `BroadcastChannel` instances with the same name in different tabs
hear each other, but the sender doesn't, even while subscribed to
that same channel.

```ts
// Tab A: edits a note and tells the rest about it
const notesChannel = new BroadcastChannel('notes-sync');
notesChannel.onmessage = () => console.log('heard myself');
notesChannel.postMessage({ type: 'note-updated', id: 1 });
// 'heard myself' never prints — measured on two tabs in one
// Chromium profile through Playwright
```

```ts
// Tab B: gets the same message and refreshes its list
const notesChannel = new BroadcastChannel('notes-sync');
notesChannel.onmessage = (e) => {
  if (e.data.type === 'note-updated') refreshNoteInList(e.data.id);
};
```

If the sending tab also needs to react, trigger that reaction
directly at the moment of the change, instead of waiting for its own
message on the channel — it never arrives.

## Every tab hears the `storage` event except the one that fired it

`window.addEventListener('storage', …)` works with no separate
channel at all — the event arrives on its own for any write to
`localStorage`.

```ts
// Tab B sees a draft edit made in tab A
window.addEventListener('storage', (e) => {
  if (e.key === 'draft-42') applyDraftUpdate(e.newValue);
});
```

The event fires in every tab of the origin except the one that called
`setItem` — measured on the same setup, and it matches
`BroadcastChannel`'s behavior. Unlike that channel, `storage` reacts
to any `localStorage` key at all, so filtering by `e.key` is
mandatory, not optional.

## A leader is elected through Web Locks; its findings travel by `BroadcastChannel`

"Only one tab should poll the server" isn't solved with a homemade
protocol — it's a combination of two capabilities: Web Locks decides
who's in charge right now, and `BroadcastChannel` tells the rest what
it found.

```txt
Who becomes the leader, and how the rest find out
┌───────────────────────────────────────────────────┐
│ Tabs A, B, C all call navigator.locks.request     │
└───────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────┐
│ Tab A gets the lock first — it becomes the leader │
└───────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────┐
│ The leader polls the server, finds new notes      │
└───────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────┐
│ BroadcastChannel tells B and C: the list changed  │
└───────────────────────────────────────────────────┘
leadership shifts on its own: the lock lives as long as the tab
```

```ts
// The leader: holds the lock while its tab is open, and shares finds
const syncChannel = new BroadcastChannel('notes-leader-sync');

navigator.locks.request('poll-leader', async () => {
  while (true) {
    const fresh = await fetchNewNotes();
    if (fresh.length) syncChannel.postMessage({ notes: fresh });
    await sleep(30_000);
  }
});

// Every tab, the leader included: applies whatever it found
syncChannel.onmessage = (e) => mergeNotes(e.data.notes);
```

The lock's own mechanics — why `BroadcastChannel` and `localStorage`
can't do mutual exclusion cleanly, what happens when the holding tab
crashes, and how to add a timeout with `AbortSignal` — are covered in
depth by the Browser / JS Runtime question bank. Nothing from that
walkthrough repeats here, only what it leaves out: how the leader
tells everyone else what it found.

## Common mistakes

- **Waiting for a `BroadcastChannel` message from yourself.** Symptom:
  code in the sending tab doesn't react to its own change, even
  though the handler is correctly subscribed to the channel.
- **Not filtering the `storage` event by key.** Symptom: a tab
  re-renders its note list because an unrelated sidebar flag changed
  somewhere else.
- **Building a mutex out of a `localStorage` flag.** Symptom: every
  so often two tabs pass the "free" check at once, and both think
  they're the leader.
- **Holding a `navigator.locks` lock without accounting for a closed
  tab.** Symptom: code assumes leadership changes on a timer, when it
  actually changes the moment the old leader's tab closes.

## Related topics

- [Heavy work leaves the main thread](./03-workers.md) — how
  `SharedWorker` works: ports, `onconnect`, and its lifetime.
- [A browser's storages each do a different job](./05-storage.md) —
  why the `storage` event exists at all and exactly what it reports.
- Browser / JS Runtime — the question bank with a full walkthrough of
  Web Locks as a mutex and `postMessage` between different origins.
- Micro-Frontends — covers `postMessage` and `Web Components` between
  apps sharing one page, not between tabs of one app.
