# The browser reports change on its own

Instead of polling an element for its size or visibility every
hundred milliseconds, you can ask the browser to report that change
itself — such a subscription is called an observer. Observers solve
four jobs: element visibility, element size, markup changes, and
performance measurements. This article covers when each observer's
callback fires, and how to avoid leaving one running for nothing.

## Polling in a loop loses to subscribing to change

Polling spends processor time asking a question whose answer is
almost always the same: "nothing changed."

```ts
// How the notes feed used to load more items: ask the last note's
// position 10 times a second, even if nobody scrolled at all
setInterval(() => {
  const last = document.querySelector('.note:last-child');
  const rect = last?.getBoundingClientRect();
  if (rect && rect.top < window.innerHeight) {
    loadMoreNotes();
  }
}, 100);
```

Every call to `getBoundingClientRect` forces the browser to recompute
the page layout if it has changed. Doing that ten times a second for
an event that happens a few times a minute is pure waste.

```ts
// The same behavior through an observer: the browser tells us
// itself once the last note enters view
const io = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting) loadMoreNotes();
});
io.observe(document.querySelector('.note:last-child')!);
```

The observer's callback fires only when the intersection actually
changes. Polling disappears along with `setInterval`, and so does the
extra load on the page's layout.

## Four observers solve four different jobs

Each observer owns one job, and mixing them up is a common interview
mistake.

| observer | what it sees | job in the notes feed |
|---|---|---|
| `IntersectionObserver` | an element's intersection with the window or a container | loading more notes at the end of the feed |
| `ResizeObserver` | changes to an element's content size | reflowing the sidebar as it gets resized |
| `MutationObserver` | added or removed nodes and changed attributes | noticing a third-party widget inserted its own markup |
| `PerformanceObserver` | technical measurements: timings, long tasks | collecting real numbers without manual polling |

The first three watch the page's markup and layout, while the fourth
watches the browser's own work. A deep look at long tasks and how
they affect responsiveness belongs to Browser / JS Runtime, not to
this article.

## An observer callback never fires inside your own code

An observer's callback never runs inside the same synchronous
function that caused the change.

```txt
When the browser calls an observer's callback
┌────────────────────────────────────────────┐
│ Your synchronous code                      │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ Microtasks: the MutationObserver callback  │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ Layout, then ResizeObserver                │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ IntersectionObserver, then the frame (rAF) │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ The frame is painted on screen             │
└────────────────────────────────────────────┘
  no callback ever runs inside your own code
```

This order was captured on Chromium 153 through Playwright 1.63.0 on
macOS, September 18, 2026: `MutationObserver` fires as a microtask,
right after the current synchronous code, while `ResizeObserver` and
`IntersectionObserver` fire during the next rendering step, before
the frame is painted. Another browser's rendering steps may differ in
detail, but a microtask always runs before rendering.

```ts
// Three synchronous attribute changes produce ONE callback call
// carrying three records — measured on the same setup
const mo = new MutationObserver((records) => {
  console.log(records.length); // 3
});
mo.observe(el, { attributes: true });
el.setAttribute('data-a', '1');
el.setAttribute('data-b', '2');
el.setAttribute('data-c', '3');
```

An observer batches changes and hands them over as one package,
instead of calling back for each one. That protects the page from a
flood of calls when code changes markup inside a loop.

## An observer that never unsubscribes is a leak

An observer keeps a reference to its element until you explicitly
tell it to stop.

```ts
// Loading more notes: the observer disconnects itself once the
// list component is unmounted
function watchLastNote(el: Element, onReach: () => void) {
  const io = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) onReach();
  });
  io.observe(el);
  return () => io.disconnect(); // call this on unmount
}
```

`disconnect()` drops every observed element at once, while
`unobserve(el)` drops just one. Without either call, the observer
keeps holding the element and firing its callback long after the
notes feed is closed.

## Common mistakes

- **Creating a new observer on every render.** Symptom: the number of
  active observers grows faster than the number of elements on the
  page, and it grows with every list update.
- **Expecting `MutationObserver` to fire immediately.** Symptom: code
  reads the markup right after changing it and misses what the
  observed script just inserted.
- **Confusing `ResizeObserver`'s `contentRect` with the whole box.**
  Symptom: calculations drift by the padding and border, because
  `contentRect` covers only the content area.
- **Never calling `disconnect()` on unmount.** Symptom: the observer's
  callback keeps firing for an element that no longer exists on the
  page.

## Related topics

- [What the browser gives an app, and under what conditions](./01-platform-model.md) —
  observers need neither permission nor a user gesture.
- [Heavy work leaves the main thread](./03-workers.md) — where a
  search over a large text body goes when no observer is responsible
  for it.
- Browser / JS Runtime — the question bank compares three markup
  observers and covers main-thread long tasks in more depth.
