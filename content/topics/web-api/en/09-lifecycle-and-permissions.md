# A page is not always alive, and permission is not always granted

A tab with the notes feed doesn't just toggle between "open" and
"closed": the browser hides it, freezes it in the background, and can
keep it alive in a special cache even after leaving for another site.
Permissions work the same non-binary way — they hold three states,
not two, and getting one requires an explicit human action, not a
check in code.

## A page moves through states you never asked for

Minimizing a tab, switching to another one, or locking a phone's
screen are different, distinguishable events as far as the browser's
code is concerned.

```txt
Page states you never asked for
┌──────────────────────────────────────────────────┐
│ visible: the tab is on screen, business as usual │
└──────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────┐
│ hidden: document.visibilityState becomes hidden  │
└──────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────┐
│ frozen: the browser pauses a background tab      │
└──────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────┐
│ terminated, or the page survives in bfcache      │
└──────────────────────────────────────────────────┘
from hidden onward, the page can return to visible at any time
```

```ts
// Checking the current state at any time, with no subscription
console.log(document.visibilityState); // 'visible' or 'hidden'
```

The `frozen` state is Chromium's way of saving processor time: a
background tab gets its timers and network requests paused, and
`resume` reports that it thawed again. Other browsers pause
background tabs differently, so stop timers and server polling as
early as `hidden`, without waiting for `frozen`.

## `unload` isn't reliable — use `pagehide` or a hidden tab instead

The `unload` event carries no guarantee that it will fire at all: a
mobile browser can close a tab without waiting for it, and merely
subscribing to `unload` turns off the back-forward cache for that
page.

```ts
// How a draft used to be saved — unreliable, and it also costs
// the whole page its back-forward cache
window.addEventListener('unload', () => saveDraftSync());
```

```ts
// A reliable replacement: save the draft as soon as the tab is
// hidden, instead of waiting to close — code is still guaranteed
// alive at that point
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') saveDraft(currentDraft);
});
```

`visibilitychange` firing into `hidden` happens before the browser
ever decides to unload the page for good, and it behaves the same way
on a phone and on a desktop. The `pagehide` event suits the same
purpose: it arrives when leaving the page, whether or not the page
ends up in bfcache.

## The back-forward cache keeps a page alive instead of reloading it

The back-forward cache, or bfcache, is a snapshot of the whole tab in
memory: scripts never restart, and the JavaScript state stays exactly
as it was the moment the person left.

```ts
// pageshow reports where the page came from
window.addEventListener('pageshow', (e) => {
  if (e.persisted) {
    // the page came back from bfcache: revalidate its data,
    // don't trust what it saw a moment ago
    revalidateNotesList();
  }
});
```

An `unload` handler is one reason a page never makes it into bfcache
at all: the browser won't hold a tab in memory once it's subscribed
to an event that's guaranteed to break that snapshot. An open
connection, like an `IndexedDB` transaction still writing, is another
common reason for the refusal.

Bfcache behavior is hard to reproduce under automated browser control
— automation tooling itself often disables it. Test it by hand in a
real browser, not only through automated tests.

## Yielding the main thread means waiting for idle, not setting a timer

`requestIdleCallback` schedules work for whenever the browser
considers itself free, unlike `setTimeout`, which just waits for a
fixed time to pass.

```ts
// Finishing the archive import from the previous article: eat the
// remainder between frames, not as one block that freezes the page
function processRemaining(deadline: IdleDeadline) {
  while (deadline.timeRemaining() > 0 && queue.length) {
    saveNote(queue.pop()!);
  }
  if (queue.length) requestIdleCallback(processRemaining);
}
requestIdleCallback(processRemaining);
```

Here `requestIdleCallback` is only a way to avoid hogging the main
thread, not a full animation scheduler. Choosing between
`requestAnimationFrame`, `requestIdleCallback`, and other ways to
spread work across frames is Browser Animation's topic.

## Permission holds three states, and you can check without asking

`navigator.permissions.query` reports the current state without
showing the person any dialog at all, unlike calling the capability
itself, which changes the state in the same breath.

| state | what to show |
|---|---|
| `granted` | the feature is already on, no "Allow" button needed |
| `prompt` | an "Enable reminders" button that will request permission |
| `denied` | a link to browser settings — asking again in code opens no dialog |

```ts
// A fresh install: geolocation, notifications, camera, and clipboard
// reads all start in the same state
const s = await navigator.permissions.query({ name: 'notifications' });
console.log(s.state); // 'prompt' — measured on the same setup as article one
```

A notable source of confusion: `Notification.requestPermission()`
resolves to the string `'default'` for the very state that
`navigator.permissions.query` calls `'prompt'`. These are two
different interfaces for the same capability, and they use different
names for "never asked yet."

```ts
// Reminders in the notes feed: check state before showing
// the person a button to turn them on
async function reminderButtonState() {
  const s = await navigator.permissions.query({ name: 'notifications' });
  if (s.state === 'granted') return 'enabled';
  if (s.state === 'denied') return 'blocked'; // show a link to settings
  return 'ask'; // show a button that calls requestPermission
}
```

Once denied, the browser generally won't open a dialog again for any
later call to `requestPermission` — the `denied` state only changes
through the site's settings, by hand.

## An event or state, and what to do about it

| event or state | what to do |
|---|---|
| `visibilitychange` to `hidden` | save the draft, stop polling the server |
| `pagehide` | the same final flush as `hidden`, in case the page is leaving |
| `freeze` | pause timers and open connections |
| `pageshow` with `persisted: true` | revalidate data instead of trusting the bfcache snapshot |
| permission `denied` | show a path to settings, not another dialog |

## Common mistakes

- **Saving data only on `unload`.** Symptom: some edits are lost on a
  phone, where a tab can close without firing a single event.
- **Leaving timers running after `hidden`.** Symptom: a phone's
  battery drains faster than it should because of a backgrounded tab.
- **Trusting data on a page restored from bfcache.** Symptom: the
  notes list shows what it looked like an hour ago, even though the
  server's data has since changed.
- **Calling `requestPermission()` again after a denial.** Symptom:
  the button gets clicked, but no dialog ever appears, and the code
  assumes the request is just stuck.

## Related topics

- [What the browser gives an app, and under what conditions](./01-platform-model.md) —
  a user gesture and a secure context as two more conditions on
  platform capabilities.
- [How tabs of the same app coordinate with each other](./06-cross-tab.md) —
  it makes sense to pause server polling on `hidden` regardless of
  which tab currently leads.
- Browser Animation — `requestAnimationFrame` and scheduling work
  across frames, covered in more depth than this article's brief
  mention.
