# What the browser gives an app, and under what conditions

The browser hands an app access to the camera, the clipboard,
background threads, and dozens of other capabilities — not as a
library you install via a package manager. Each one already lives
inside the browser and only unlocks once its conditions are met. This
topic covers those capabilities: where they come from, what limits
them, and how to check they exist.

## Capabilities arrive as ready-made objects, not imports

When you need clipboard access, you don't run `npm install
clipboard` — you reach for the object `navigator.clipboard`, which
the browser already built for this page. The whole platform works
this way: capabilities live inside two global objects, and none of
them get imported.

The object `window` is the tab itself: its size, its address, its
timers, the windows it can open. The object `navigator` is the
browser and the device it runs on: the network, the battery, the
clipboard, the location. The page inside the tab is a ready-made
object too: the document object model (DOM), reachable through
`window.document`.

```ts
// The "offline" badge on the notes feed — using what navigator
// already gives us, with no import at all
function updateOfflineBadge() {
  const badge = document.querySelector('#offline-badge')!;
  badge.hidden = navigator.onLine; // true — network is up, hide it
}

window.addEventListener('online', updateOfflineBadge);
window.addEventListener('offline', updateOfflineBadge);
updateOfflineBadge();
```

Neither `navigator.onLine` nor the `online`/`offline` events need any
setup. They exist in every tab from the moment it opens, and the code
above just listens to what is already there.

## Three conditions gate every platform capability

A capability can sit right there on `navigator` and still refuse to
work, because one of three platform conditions is not met.

```txt
From the most open tier to the most locked one
┌────────────────────────────────────────────┐
│ Always available: window, navigator, DOM   │
├────────────────────────────────────────────┤
│ + secure context (HTTPS)                   │
│ Service Worker, Web Locks, Clipboard API   │
├────────────────────────────────────────────┤
│ + user gesture                             │
│ fullscreen mode, clipboard write           │
├────────────────────────────────────────────┤
│ + user permission                          │
│ notifications, camera, precise geolocation │
└────────────────────────────────────────────┘
each tier adds its own condition on top of the last
```

Conditions stack instead of branching: a single capability can
require two of them at once. Precise geolocation, for instance, needs
both a secure context and a separate user permission.

| condition | what the browser checks | example capability |
|---|---|---|
| origin | the scheme, domain, and port of the page match whoever is asking | cookies, `postMessage` |
| secure context | the page is served over HTTPS (the encrypted form of HTTP) or from localhost | Service Worker, Web Locks |
| user gesture | the call happens right inside a click or keypress handler | fullscreen mode, clipboard write |

A page's origin stays the same for `https://notes.app` and
`https://notes.app/archive`, but changes for `https://api.notes.app`,
even though it's the same product. A secure context and a user
gesture are simpler: each one is either there or not, and the browser
checks both before it hands over the capability.

## Most capability calls are a promise, not a ready answer

Most methods on `navigator` return not a value but a promise — a
`Promise` that settles later, once the browser finishes asking the
device or the person using it.

```ts
// A reminder for a note — only if the person allows notifications;
// permission can't resolve before a human answers
async function enableReminders(): Promise<boolean> {
  const permission = await Notification.requestPermission();
  return permission === 'granted'; // 'granted' | 'denied' | 'default'
}
```

The reason is that many calls involve a dialog for the person, a
round trip to the operating system, or both at once. Neither one
answers instantly, so `Promise` is not a style choice here — it
follows from the task itself.

## Check whether a capability exists, not which browser this is

A correct check asks the object whether it has what you need, instead
of asking for the browser's name and version.

```ts
// "Copy link" button on a note — not every browser has this
function canCopyLink(): boolean {
  return 'clipboard' in navigator
    && typeof navigator.clipboard.writeText === 'function';
}

async function copyNoteLink(noteId: string) {
  if (!canCopyLink()) {
    return showFallbackPrompt(noteId); // plain-text link to copy by hand
  }
  await navigator.clipboard.writeText(`https://notes.app/n/${noteId}`);
}
```

A browser-name check goes stale the moment any of the three engines
changes its behavior, and the list of names has to live in someone's
head. The check `'clipboard' in navigator` survives that change on
its own, because it asks for a fact, not a name.

## Common mistakes

- **Checking the browser through the `User-Agent` string.** Symptom:
  code works in one browser and breaks in another, even though the
  capability exists there too — the check just looked for the wrong
  name.
- **Forgetting the secure-context rule on a staging server.**
  Symptom: everything works on localhost and silently stops where the
  page is served over plain HTTP.
- **Calling a capability from a gesture too late.** Symptom: the
  click handler ran, but an `await` inside it already passed, and the
  browser no longer counts the call as a result of a human action.
- **Not checking what the capability's `Promise` resolved to.**
  Symptom: the code keeps going as if permission was granted, even
  though the person declined it.

## Related topics

- [The browser reports change on its own](./02-observers.md) — the
  first platform capability that needs neither permission nor a
  gesture.
- [A page is not always alive, and permission is not always granted](./09-lifecycle-and-permissions.md) —
  the three permission states, in detail, and how to check one
  without asking.
- Browser / JS Runtime — the question bank on the browser engine and
  the event loop: the neighboring topic starts where the document
  object model ends.
