# Web API: interview questions

## How to use this cheat sheet

Each answer below is a compressed version of what this topic's
articles cover in depth. Some questions overlap with the Browser /
JS Runtime bank, but from a different angle: that bank covers how a
capability works, this one covers what actually comes up in an
interview and where the conversation goes next.

Each group ends with a block of follow-up questions. It shows where
the conversation usually goes once the first answer lands well.

| group | about | article |
|---|---|---|
| 1 | the platform model and access conditions | 01 |
| 2 | observers | 02 |
| 3 | workers and the service worker | 03, 04 |
| 4 | storage and cross-tab coordination | 05, 06 |
| 5 | files, the clipboard, streams | 07, 08 |
| 6 | page lifecycle and permissions | 09 |

## Group 1: the platform model and access conditions

**1. Why does Web API have no `import`, only `window` and
`navigator`?**

Because it isn't a library you install — it's part of an environment
that's already running. The browser creates `window` and `navigator`
for every tab on its own, and both objects exist before a single line
of your code has run.

```ts
console.log(typeof navigator.clipboard); // 'object' — already there
```

**2. Which conditions can one capability require at the same time?**

Origin, secure context, and a user gesture stack instead of being
picked one at a time. Precise geolocation, for instance, needs two at
once: a secure context and a separate permission.

| capability | what it requires |
|---|---|
| `Service Worker` | only a secure context |
| a clipboard write | only a gesture |
| precise geolocation | a secure context and permission |

**3. How do you check whether a capability exists without depending
on a specific browser?**

Ask the object directly — `'clipboard' in navigator` — instead of
parsing the `User-Agent` string. A browser-name check goes stale the
moment any engine changes its behavior; the object's presence doesn't.

## Common follow-up questions (group 1)

```txt
"What if the capability sits on navigator but doesn't work?" ->
most likely one condition failed: context, origin, or gesture —
the object's presence alone never checks for those

"Why a Promise instead of a ready value?" -> almost every call
hides a dialog for the person or a round trip to the OS,
and neither answers instantly
```

## Group 2: observers

**4. In what order do a `MutationObserver` callback and a
`setTimeout(0)` callback fire, if both are scheduled in the same
synchronous block?**

`MutationObserver` first: it runs as a microtask right after the
current code, while `setTimeout` waits for the next macrotask.

```txt
sync-end -> microtask -> mutationobserver -> setTimeout0 -> rAF
captured on the same Chromium 153 setup, through Playwright
```

`ResizeObserver` and `IntersectionObserver` come even later — they're
tied not to microtasks but to a rendering step, closer to the frame.

**5. Why is a forgotten observer a leak, not just extra code?**

An observer holds a reference to its element until `disconnect()` or
`unobserve()` is called, and that reference keeps the element from
being freed, even long after it's gone from the page's markup. In
practice, the symptom is a callback still firing for a list that no
longer exists in the interface.

## Common follow-up questions (group 2)

```txt
"How do the four observers differ by job?" -> visibility,
size, markup, technical measurements — each owns one,
and mixing them up is a common mistake

"Does MutationObserver fire on every single change?" ->
no, changes batch up and arrive as one package of records
```

## Group 3: workers and the service worker

**6. How does a `Worker` differ from a `Service Worker` in lifetime?**

A `Worker` dies with the page that created it. A `Service Worker`
lives by the rules of its origin and keeps existing even once no tab
is left at all.

**7. What happens to an `ArrayBuffer` on the sending side after
`postMessage(data, [buf])`?**

It empties out: `buf.byteLength` becomes `0`, because the data wasn't
copied — it was transferred, and the memory moved to the other thread
whole.

```ts
worker.postMessage({ buf }, [buf]);
console.log(buf.byteLength); // 0 — measured on the same setup
```

Without a transfer list as the second argument, a plain
`structuredClone` would have run instead, and the original buffer
would stay untouched.

**8. A service worker is `activated`, but
`navigator.serviceWorker.controller` is `null`. Is that a bug?**

No, it's part of the spec: the page that called `register()` doesn't
get a new controller until it reloads itself. The first registration
activates the worker, but it doesn't swap network behavior under an
already-open tab mid-flight.

## Common follow-up questions (group 3)

```txt
"What can a worker see, and what can't it?" -> self, fetch,
IndexedDB — yes; window, document, localStorage — no, in
neither kind of worker

"How do you make a service worker take control right away?" ->
skipWaiting() in install, and clients.claim() in activate
```

## Group 4: storage and cross-tab coordination

**9. Why is `localStorage` a poor choice for autosaving on every
keystroke?**

Because it's synchronous: `setItem` doesn't return control until it
writes to disk, and that delay adds up with frequent calls.
`IndexedDB` works differently — `open()` returns a request object
right away instead of blocking code while it waits for data.

**10. Tab A calls `localStorage.setItem`. Which tabs get the
`storage` event?**

Every tab of the same origin except tab A itself — the event never
reaches whoever made the change. `BroadcastChannel` behaves the same
way: the sender never hears its own message.

```ts
notesChannel.postMessage({ type: 'note-updated' });
// notesChannel.onmessage never fires in this same tab
```

**11. Why don't `BroadcastChannel` and `localStorage` work as a
mutex between tabs?**

Because they're message channels, not an arbiter: there's a window
between checking a "free" flag and setting it, where two tabs can
both land at once. `Web Locks` closes that window — the browser
itself grants the lock, instead of a homemade protocol built on top
of messages.

## Common follow-up questions (group 4)

```txt
"Which storage can a service worker see?" -> IndexedDB and
Cache Storage, yes; localStorage and sessionStorage, no

"What does navigator.storage.estimate() return?" -> an
approximate quota and usage, rounded, not an exact byte count
```

## Group 5: files, the clipboard, streams

**12. How does a File System Access handle differ from a `File`
object from `<input>`?**

A `File` from `<input>` is one-shot: there's no reading that same
file again without a new dialog. A `FileSystemFileHandle` outlives
the session — it can be saved and asked for permission again next
time, without showing the person a picker dialog twice.

**13. Why do reading the clipboard and writing to it follow
different rules?**

A write is treated as lower risk: a human gesture is usually enough.
A read could expose someone else's data that happens to sit on the
clipboard, so it also needs the `clipboard-read` permission, not just
a click.

**14. What happens to already-processed data if a signal cuts
`pipeTo` in the middle of a pipeline?**

It stays as is: the source gets a `cancel()` call with the abort
reason, but anything that already reached the `WritableStream` isn't
going anywhere. Cancellation stops what hasn't happened yet — it
doesn't roll back what already has.

```ts
await readable.pipeTo(writable, { signal });
// after abort('cancelled') — already-written chunks stay written
```

## Common follow-up questions (group 5)

```txt
"What is backpressure?" -> mutual waiting between pipeline
steps: a fast source never outruns a slow consumer

"Why call URL.revokeObjectURL if there's a garbage collector
anyway?" -> the collector doesn't know about a blob address
on its own; without an explicit revoke the file stays in memory
```

## Group 6: page lifecycle and permissions

**15. Why is `unload` a poor place for a final data save?**

It carries no guarantee of firing — a mobile browser can close a tab
without waiting for it — and merely subscribing to `unload` disables
the back-forward cache (bfcache) for that page. `visibilitychange`
firing into `hidden` is more reliable and doesn't cost the page its
bfcache.

**16. How does the `prompt` state from `navigator.permissions.query`
differ from `'default'` from `Notification.requestPermission()`?**

Not at all, in meaning — both mean "never asked yet." These are two
different interfaces for the same capability, and they name the same
state with different strings — a common source of bugs in code that
compares state directly.

**17. What does `pageshow` with `persisted: true` mean?**

The page came back from bfcache instead of loading fresh: scripts
never restarted, and the JavaScript state stayed exactly as it was
the moment the person left. The data can still be stale — the server
may have updated it while the page sat in cache — so that moment is a
cue to revalidate, not just a fast load to enjoy.

## Common follow-up questions (group 6)

```txt
"What sets frozen apart from hidden?" -> hidden is about
visibility; frozen is Chromium pausing a background tab to
save processor time, and other browsers handle it differently

"Permission is denied — how does it come back?" -> only
through the site's browser settings; asking again in code
opens no dialog at all
```

## Related topics

- [What the browser gives an app, and under what conditions](./01-platform-model.md) —
  group 1, in depth.
- [Heavy work leaves the main thread](./03-workers.md) and
  [A service worker is a network go-between that outlives the page](./04-service-worker.md) —
  group 3, in depth.
- [A page is not always alive, and permission is not always granted](./09-lifecycle-and-permissions.md) —
  group 6, in depth.
- Browser / JS Runtime — the question bank on neighboring topics: the
  event loop, `IndexedDB` pagination, `postMessage` security, and
  Web Locks as a mutex.
