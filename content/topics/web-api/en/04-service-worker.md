# A service worker is a network go-between that outlives the page

A `Service Worker` is code the browser places between a page and the
network, and it survives the tab that started it being closed. Unlike
the background thread from the previous article, it doesn't belong to
one page: a single service worker serves every tab in its scope and
keeps existing once no tab is left at all.

## A service worker sits between the page and the network, not in its thread

A `Worker` dies with the page that created it, while a service worker
lives by the rules of its origin, not a single tab.

| | `Worker` | `Service Worker` |
|---|---|---|
| who creates it | one page | a registration for a whole origin |
| who it talks to | only its own page | every tab inside its scope |
| lifetime | gone once the tab closes | the browser can stop and wake it again |
| sees the network | no | intercepts requests via the `fetch` event |

The `fetch` event is something no other thread in this topic has. A
service worker can answer a request from a cache, change it, or pass
it through to the network untouched, and the page never learns a
go-between was involved at all.

## The lifecycle moves through states in a fixed order

Before it can start intercepting requests, a service worker passes
through several states in a row, and none of them can be skipped.

```txt
Five states of one service worker
┌────────────────────────────────────────────────┐
│ installing: the install handler runs           │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│ installed / waiting: old tabs must close first │
└────────────────────────────────────────────────┘
                         │  skipWaiting() skips the wait
                         ▼
┌────────────────────────────────────────────────┐
│ activating: the activate handler runs          │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│ activated: intercepts new tabs' requests       │
└────────────────────────────────────────────────┘
 waiting only happens if an old worker is still active
```

```ts
// sw.js — a minimal worker: it caches nothing on its own
self.addEventListener('install', (event) => {
  console.log('installing');
});

self.addEventListener('activate', (event) => {
  console.log('activating');
});
```

The `waiting` state isn't a pause by default — it's a safeguard: the
browser won't swap a new version under tabs that still hold the old
one open. A full walkthrough of `skipWaiting()`, `clients.claim()`,
and cache versioning during a deploy lives in Browser / JS Runtime,
the question bank on the service worker lifecycle and zero-downtime
deploys.

## Scope decides which requests a worker ever sees

A worker's `scope` is the path prefix outside of which it never sees
a single request. By default it equals the folder that holds the
worker file.

```ts
// Registered from the root — the worker serves the whole notes feed
await navigator.serviceWorker.register('/sw.js');
console.log((await navigator.serviceWorker.ready).scope);
// http://localhost:3000/
```

Trying to widen the scope past the script's own folder fails right at
registration.

```txt
SecurityError: Failed to register a ServiceWorker for scope
('http://localhost:8934/') with script
('http://localhost:8934/scoped/sw2.js'): The path of the provided
scope ('/') is not under the max scope allowed ('/scoped/'). Adjust
the scope, move the Service Worker script, or use the
Service-Worker-Allowed HTTP header to allow the scope.
```

This message was captured on the same Playwright setup. Only a
response header, `Service-Worker-Allowed`, can widen a scope from the
server side — moving the file doesn't get around the limit unless the
server serves the worker from the root.

## A freshly registered worker isn't intercepting requests yet

The first registration activates the worker, but the page that called
`register` keeps hitting the network directly until it reloads.

```ts
await navigator.serviceWorker.register('/sw.js');
await navigator.serviceWorker.ready;

console.log(!!navigator.serviceWorker.controller);
// false — even after activation: the worker becomes a controller
// only for pages loaded AFTER the registration
```

This isn't a bug or a race, it's part of the specification: the page
that caused a worker to appear must not have its network behavior
change mid-flight. The notes feed's offline mode only kicks in on the
second page load, unless `activate` also calls `clients.claim()`.

## Debugging lives in DevTools, not in a worker's own console

A service worker has no tab of its own, so its `console.log` calls
don't show up in the page's regular console — they land in the
worker's console inside the `Application` panel of your dev tools.

- **The `Update on reload` checkbox.** Forces the browser to install
  a new worker version on every reload, bypassing the usual 24-hour
  check.
- **The `Unregister` button.** Drops the registration entirely — handy
  when an old worker version blocks testing the current one.
- **The `Offline` toggle.** Cuts network access for the tab without
  touching the real connection, so you can test the offline path
  without turning off Wi-Fi.

## Common mistakes

- **Expecting a worker to work right after registration.** Symptom:
  offline mode doesn't kick in on the first page load, even though
  `register()` resolved with no error.
- **Widening scope by moving the worker's file.** Symptom:
  registration fails with a `SecurityError`, even though the file
  path looks correct.
- **Leaving DevTools open without checking `Application`.** Symptom:
  logs from `install` and `activate` seem to vanish, though the
  worker did print them — just into a different console.
- **Confusing a `Service Worker` with a plain `Worker`.** Symptom:
  code expects the worker to die with its tab, but it keeps answering
  requests from another tab of the same origin.

## Related topics

- [Heavy work leaves the main thread](./03-workers.md) — how a plain
  background thread differs from a service worker in lifetime and
  connection to the page.
- [A browser's storages each do a different job](./05-storage.md) —
  Cache Storage, the storage a service worker reaches for most often.
- Web Performance — the caching-strategies article: what to put in
  the cache and when to refresh it, not the worker's own machinery.
- Browser / JS Runtime — the question bank with a full walkthrough of
  `skipWaiting()`, `clients.claim()`, and zero-downtime deploys.
