# Performance

## Theory

### Measure first

```
                                     Where to look when "Angular is slow"
┌────────────────────────────────┬───────────────────────────────────────┬───────────────────────────────────┐
│ symptom                        │ the usual cause                       │ the tool                          │
├────────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ the list jumps on refresh      │ track by index or by object           │ DevTools Profiler                 │
├────────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ lag on every keystroke         │ a method or impure pipe in a template │ Profiler: check duration          │
├────────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ more checks than changes       │ an Eager component on a hot path      │ Profiler: cycle count             │
├────────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ slow first render              │ all the code in the initial bundle    │ stats.json + esbuild analyze      │
├────────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ layout jumps while loading     │ images without width/height           │ Lighthouse: CLS                   │
├────────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ scrolling a long list stutters │ no virtual scrolling                  │ the browser's performance profile │
└────────────────────────────────┴───────────────────────────────────────┴───────────────────────────────────┘
                    measure first, optimize second: half of all eyeballed "optimizations"
                              complicate the code without moving a single number
```

An Angular application's performance breaks in two different places, and they are fixed differently: **runtime** (how much work change detection and rendering do per interaction) and **loading** (how much code and how many images must arrive before the first screen). The profiler answers the first, bundle analysis the second.

**Angular DevTools, the Profiler tab**: a recording shows change detection cycles, which components took part, how many times, and how many milliseconds each check took. It is the only way to see what the code does not show: an expression in a template running hundreds of times, or a component checked on every keystroke happening in another corner of the screen.

### Runtime: what is already done for you

By v22 the three main runtime optimizations became defaults (chapters 03 and 02): zoneless since v21, `OnPush` since v22, and signals as the notification mechanism. So the modern checklist looks different from three years ago: instead of "turn on OnPush" it is "do not break what is already on".

What breaks the built-in optimizations:

- **An explicit `ChangeDetectionStrategy.Eager`** in a decorator — the component is checked on every traversal. After migrating to v22 it stayed in older components automatically (chapter 03), and on a hot path that is a real cost.
- **Method and getter calls in templates** — they run on every check with no caching. This is the most common cause of "lag on every keystroke": search updates a signal, the template is checked, and `getTotal()`, `formatDate()` and `filterTickets()` are recomputed along with it.
- **Impure pipes** (`pure: false`) — the same story (chapter 06).
- **Mutation instead of `set`** — not slow as such, but it produces "it does not update", which then invites "fixes" made of extra checks.

### track and the cost of getting it wrong

`track` in `@for` is not about elegance but about whether Angular reuses existing DOM nodes. Three variants:

```html
@for (t of tickets(); track t.id) { … }      <!-- correct: a stable key -->
@for (t of tickets(); track $index) { … }    <!-- position: breaks on sorting -->
@for (t of tickets(); track t) { … }         <!-- reference: breaks after an HTTP refresh -->
```

`track $index` ties a node to a position: after sorting, position 0 holds a different object, and Angular rewrites the content of **every** node instead of reordering. `track t` (by reference) works while the array stays in memory, but after a reload from HTTP every object is new — so the whole list is recreated along with the components inside it, their state, the focus and the scroll position.

In practice: a list of 200 cards with `track $index` re-runs 200 templates and every nested component on a sort; with `track t.id` it moves nodes and runs no extra templates at all.

### @defer: deferring blocks

```
                            @defer: when to load the block
┌──────────────────┬─────────────────────────────────────┬───────────────────────────┐
│ trigger          │ what it means                       │ typical case              │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ on idle          │ the browser went idle (the default) │ anything below the fold   │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ on viewport      │ the block entered the viewport      │ charts, comments          │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ on interaction   │ a click or keydown on an element    │ an editor, a heavy form   │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ on hover         │ mouseover or focusin                │ a preview, a data tooltip │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ on timer(2s)     │ after the given delay               │ a banner, a hint          │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ on immediate     │ right after the main render         │ shrink the initial bundle │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ when expr        │ the condition became true           │ by role, by feature flag  │
├──────────────────┼─────────────────────────────────────┼───────────────────────────┤
│ prefetch on idle │ fetch the code early, show later    │ almost always worth it    │
└──────────────────┴─────────────────────────────────────┴───────────────────────────┘
         only standalone dependencies can be deferred, and only those with no
      direct references outside the block (otherwise they join the main bundle)
```

`@defer` moves the block's content into a **separate chunk** and loads it on a trigger:

```html
@defer (on viewport; prefetch on idle) {
  <app-ticket-analytics [tickets]="tickets()" />
} @placeholder (minimum 300ms) {
  <div class="skeleton skeleton--chart"></div>
} @loading (after 150ms; minimum 300ms) {
  <p>Loading analytics…</p>
} @error {
  <p>Could not load analytics</p>
}
```

What the parameters mean: `@placeholder (minimum 300ms)` — do not flicker when loading is instant; `@loading (after 150ms)` — do not show an indicator at all if everything arrives quickly; `minimum 300ms` — once shown, keep it for at least 300 ms. Those are exactly the two visual defects usually patched by hand.

The main constraint: only **standalone** dependencies can be deferred, and only those with no direct references outside the block. If the same component is listed in `imports` and used in ordinary markup (or queried through `viewChild`), it lands in the main bundle and `@defer` merely defers rendering — no code is saved. That is the first thing to check when "I added `@defer` and the bundle did not shrink".

For SSR, `@defer` has its own family of `hydrate on …` triggers (incremental hydration): the server renders the block's content and the browser leaves it "dehydrated" until the trigger — hydration happens in portions (chapter 15).

### Loading: lazy routes and budgets

Lazy routes (`loadComponent`/`loadChildren`, chapter 07) are the primary code-splitting tool; `@defer` complements them inside a page. To stop the result from degrading over time, sizes are pinned by budgets in `angular.json`:

```
┌───────────────────────┬───────────────────────────────────────┬────────────────────────────────────┐
│ budget type           │ what it measures                      │ why watch it                       │
├───────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ initial               │ everything loaded before first render │ the key startup metric             │
├───────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ bundle (+ name)       │ one named bundle                      │ a lazy section staying slim        │
├───────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ anyComponentStyle     │ any single component stylesheet       │ catches an accidental theme import │
├───────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ anyScript / allScript │ any one / all scripts                 │ an overall JS ceiling              │
├───────────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
│ any / all             │ any one / all output files            │ images, fonts, templates           │
└───────────────────────┴───────────────────────────────────────┴────────────────────────────────────┘
```

Every budget has `maximumWarning` and `maximumError` (plus `minimum*` and `baseline` for comparing against a reference). `maximumError` fails the build — which turns a budget into a CI check rather than a suggestion.

Bundle analysis with the new build system: `ng build --stats-json` produces a `stats.json` you upload to **esbuild-analyze** (`https://esbuild.github.io/analyze/`), which shows which module weighs what and why it ended up in the bundle. Webpack tooling (`webpack-bundle-analyzer`) does not work with the application builder: the build runs on esbuild.

### Images

`NgOptimizedImage` from `@angular/common` is a directive that forces you to do it right:

```html
<img
  ngSrc="/assets/hero.jpg"
  width="1200" height="630"
  priority                     <!-- the LCP image: fetchpriority=high, loading=eager -->
  alt="Support desk overview"
/>
```

What you get: mandatory `width`/`height` (or `fill` with a positioned parent) removes layout shift, `priority` marks the LCP image, every other image gets `loading="lazy"` automatically, and `srcset` plus `preconnect` are generated for you. In dev mode it also warns about the classic mistakes: an LCP image without `priority`, distorted aspect ratios, wrong dimensions, a missing preconnect. Ready-made CDN loaders exist: `provideImgixLoader`, `provideCloudflareLoader`, `provideCloudinaryLoader`, `provideImageKitLoader`, `provideNetlifyLoader` — or your own through the `IMAGE_LOADER` token.

### Virtualizing long lists

Past a few hundred rows, `@for` stops being the answer: DOM nodes cost memory and layout time. `cdk/scrolling` (`<cdk-virtual-scroll-viewport>` + `*cdkVirtualFor`) renders only the visible items. The decision threshold is not a row count but the profile: if template checks take single-digit milliseconds and it is the scrolling that stutters, the DOM is the problem and virtualization will help.

## React parallels

- **`@defer` ≈ `React.lazy` + `Suspense`, but more declarative.** In React you write `lazy(() => import(...))` and wrap it in `<Suspense fallback>`; the load trigger is the render itself. `@defer` separates the **trigger** from the place: `on viewport`, `on interaction`, `prefetch on idle` — the things React does by hand with an Intersection Observer and manual prefetching.
- **`track` ≈ `key`, but mandatory.** The identity mechanics are the same, and the consequences of a wrong key are identical: recreated nodes and lost state. The difference is discipline: React settles for a console warning, Angular will not compile a `@for` without `track`.
- **`OnPush` versus `memo`.** In React memoization is something you add (`memo`, `useMemo`, `useCallback`) and easily forget. In Angular since v22 the "memoization" is on by default (`OnPush` plus signals), and the work is reduced to not switching it off with `Eager` components and template computations.
- **Budgets are something the React stack usually lacks out of the box.** The equivalent is assembled from `bundlesize`/`size-limit` in CI; in Angular it is a field in `angular.json`, and `maximumError` fails the build with no extra tooling.
- **Where the habit breaks:** the habit of memoizing everything. `useMemo` is a reflex in React, and it carries over into `computed` for trivial expressions: `computed(() => this.count() + 1)` around arithmetic adds a graph node and saves nothing. Signals are already fine-grained; optimize what the profiler pointed at, not everything in sight.

## What you will see in legacy code

- **An explicit `ChangeDetectionStrategy.OnPush` in every component** — before v22 that was a deliberate optimization, now it is the default. Its neighbour marker is a `ChangeDetectionStrategy.Default`/`Eager` left behind by a migration.
- **`trackBy: trackById`** — a class method with the signature `(index, item)` next to `*ngFor`; in the new control flow that is the expression `track item.id`.
- **`runOutsideAngular`** around animations, scroll handlers and `requestAnimationFrame` (chapter 03): in the zone model that was how extra checks were silenced. In zoneless it is unnecessary — and `NgZone` does not work there anyway.
- **`webpack-bundle-analyzer`** in devDependencies with an `analyze` script using webpack's `--stats-json`. With the application builder the same `stats.json` is read by esbuild-analyze.
- **Hand-rolled image lazy-loading:** an `IntersectionObserver` in a directive, a manual `loading="lazy"`, custom placeholders — all pre-`NgOptimizedImage`.
- **`ChangeDetectorRef.detach()`/`reattach()`** as a way to "switch off" a heavy component — it works, but it means the cause was never found.

## What we add to the project

We profile the ticket list, find and remove computations from templates, move the heavy blocks (analytics, ticket history) onto `@defer` with sensible triggers, add budgets to `angular.json` and bring the images onto `NgOptimizedImage`.

## Exercise

**Input:** the project from chapter 11 (the table, the modal, the HTTP layer).
**Output:** measured, justified improvements rather than eyeballed "optimizations".

Requirements:

1. Profiling: generate 500 tickets, open the Angular DevTools Profiler and record typing three characters into the search box. Write the numbers down: how many CD cycles, which components were checked, how many milliseconds. That is the baseline you will keep returning to.
2. Find and remove computations from templates (methods, getters, `filter`/`map` in markup, impure pipes). Re-measure and compare against the baseline.
3. A `track` experiment: build three versions of the `@for` (`track t.id`, `track $index`, `track t`), sort the list and compare the number of executed templates in the profiler. Explain the difference.
4. `@defer`: pick two heavy blocks — an analytics panel (a chart) and the ticket change history. Load analytics with `on viewport; prefetch on idle` and the history with `on interaction` on a button. Add `@placeholder` and `@loading` with parameters so nothing flickers.
5. Verify with `stats.json` that the chunks were really split out: build with `--stats-json`, upload it to esbuild-analyze and find the deferred chunks. If the code stayed in the main bundle, find the direct reference that caused it.
6. Budgets: add `initial` (warning/error with roughly 20% headroom over the current size) and `anyComponentStyle` budgets to `angular.json`. Confirm that exceeding them fails the build: temporarily import something heavy and look at the error.
7. Images: move avatars and the logo onto `NgOptimizedImage`, set `priority` where it is the LCP, and check in Lighthouse that CLS does not grow.

Edge cases to think about:

- You wrapped a component in `@defer` but the main bundle size did not change. What are the two most likely causes?
- `@defer (on viewport)` inside a block that is itself hidden by `@if`. When does the trigger fire?
- `@placeholder` without `minimum` on a fast connection — what does the user see?
- A list with `track t.id`, but new (unsaved) items have `id === undefined`. What happens?
- The `initial` budget is set to 500 kB and the application grew because of a lazy section. Will the budget catch it?

## Solution walkthrough

Removing computations from templates is the cheapest win:

```ts
// BEFORE: three calls per template check, no caching
// <p>{{ getVisibleCount() }} of {{ getTotal() }} · {{ formatDate(ticket.createdAt) }}</p>

// AFTER: computed is memoized by its signals, the pipe caches by its input
protected readonly visibleCount = computed(() => this.board.tickets().length);
protected readonly totalCount = computed(() => this.store.totalCount());
// in the template: {{ ticket.createdAt | date: 'short' }}
```

`@defer` on the heavy blocks:

```html
<!-- Analytics sit below the fold, so we load on viewport entry and prefetch
     the code while the browser idles — by the time the user scrolls it is there -->
@defer (on viewport; prefetch on idle) {
  <app-ticket-analytics [tickets]="board.tickets()" />
} @placeholder (minimum 300ms) {
  <!-- minimum, so the skeleton does not flicker on a fast connection -->
  <div class="skeleton skeleton--chart" aria-hidden="true"></div>
} @loading (after 150ms; minimum 300ms) {
  <!-- after: no indicator at all if loading finishes within 150 ms -->
  <p class="hint">Loading analytics…</p>
} @error {
  <p class="error">Could not load analytics</p>
}

<!-- History is on demand. The trigger is interaction with the button:
     the code is fetched on the first click, not before -->
<button type="button" #historyToggle>Show history</button>

@defer (on interaction(historyToggle)) {
  <app-ticket-history [ticketId]="ticket().id" />
} @placeholder {
  <p class="hint">History is loaded on demand</p>
}
```

An important detail that is easy to miss: `TicketAnalytics` and `TicketHistory` must **not** appear in the component's `imports` and must not be used anywhere else in its template. The compiler adds them as the block's lazy dependencies itself; with a direct reference they move into the main bundle and `@defer` becomes deferred rendering only.

Budgets in `angular.json`:

```json
{
  "projects": {
    "support-desk": {
      "architect": {
        "build": {
          "configurations": {
            "production": {
              "budgets": [
                {
                  "type": "initial",
                  "maximumWarning": "420kB",
                  "maximumError": "500kB"
                },
                {
                  "type": "anyComponentStyle",
                  "maximumWarning": "4kB",
                  "maximumError": "8kB"
                },
                {
                  "type": "bundle",
                  "name": "admin",
                  "maximumWarning": "150kB",
                  "maximumError": "250kB"
                }
              ]
            }
          }
        }
      }
    }
  }
}
```

`maximumError` is what makes a budget useful: the build fails, so the bundle can no longer grow unnoticed. Set the values with modest headroom over the current size, otherwise the budget either never fires or fires constantly.

Bundle analysis:

```bash
# stats.json is produced by the application builder (esbuild), not webpack
npx ng build --stats-json

# the report opens at https://esbuild.github.io/analyze/ — upload dist/.../stats.json
# look for: what landed in the initial chunk, which chunks @defer and lazy routes created
```

Images:

```ts
@Component({
  selector: 'app-ticket-detail',
  imports: [NgOptimizedImage],
  // …
})
```

```html
<!-- width/height are mandatory: the browser reserves space and layout does not jump -->
<img ngSrc="/assets/logo.svg" width="120" height="32" alt="Support Desk" priority />

<!-- avatars are not the LCP: no priority needed, the directive adds loading="lazy" -->
@for (ticket of board.tickets(); track ticket.id) {
  <img [ngSrc]="ticket.assigneeAvatar" width="32" height="32" [alt]="ticket.assignee ?? ''" />
}
```

Virtualization, if the profile showed the DOM is the bottleneck:

```html
<cdk-virtual-scroll-viewport itemSize="72" class="ticket-list__viewport">
  <!-- only the visible rows plus a small buffer are rendered -->
  <app-ticket-card *cdkVirtualFor="let ticket of board.tickets(); templateCacheSize: 20" [ticket]="ticket" />
</cdk-virtual-scroll-viewport>
```

Answers to the edge cases:

- Two causes, both about direct references. First: the component is listed in this component's `imports` or used in ordinary markup outside the block — then it is a static dependency and lands in the main bundle. Second: a `viewChild`/`contentChild` refers to it, or it is imported in the component's TS code (for a type you instantiate, say) — the compiler must have it available on first load. Verify with `stats.json`: if the chunk is missing, look for the reference.
- It will not fire while the outer `@if` is false: the `@defer` content does not exist, so there is no element for the Intersection Observer to watch. The trigger starts working once the block enters the DOM. In other words nested conditions "shift" the load moment, which is worth accounting for: in that situation prefetch helps more than the trigger itself.
- Flicker: the placeholder appears and vanishes almost immediately — a visual "blink" that reads as a layout bug. `@placeholder (minimum 300ms)` guarantees that once shown it stays for at least that long; the paired technique is `@loading (after 150ms)`, so the indicator never appears on a fast load.
- `undefined` as a key for several items produces duplicate keys — Angular throws about a duplicated `track` (chapter 01). Unsaved items need a temporary unique key: a local negative id, `crypto.randomUUID()`, or a composite `t.id ?? t.tempId`.
- No: the `initial` budget counts only what loads before the first render, and a lazy chunk is not part of it. That is exactly why the example adds a second budget with `type: "bundle"` and `name: "admin"` — so the lazy section has a ceiling of its own. Overall growth is watched with `allScript`/`all`.

## Check yourself

1. Why is `track $index` in a sortable list not merely "a less precise key" but a source of real work for the framework?
2. What exactly does `@defer` do with the block's code, and in which two cases will it fail to shrink the main bundle?
3. Why do `@placeholder (minimum …)` and `@loading (after …)` exist if you could just show a spinner?
4. Which runtime optimizations are on by default in Angular 22, and what in your code can switch them off?
5. How are budgets in `angular.json` more useful than "eyeballing the bundle size after a build"?

<details>
<summary>Answers</summary>

1. Because `track` decides which DOM node corresponds to which data item. With `track $index` the identity becomes the position: after sorting, position 0 holds a different object, but Angular treats it as "the same" item and rewrites the node's content instead of moving the node — and so on down the list. Instead of N reorders you get N template updates together with every nested component. Plus the side effects: focus is lost, scroll position inside rows resets, transition animations break, and component state inside a row (open menus, drafts) drifts onto different data.
2. `@defer` splits the block's content and its dependencies into a **separate chunk** loaded only on a trigger. It will not shrink the main bundle in two cases: (a) the deferred component is listed in `imports` or used in ordinary markup outside the block — then it is a static dependency; (b) the component's code references it, for example through `viewChild`/`contentChild` or a TS import for a type you instantiate. In both cases the compiler must include it in the first load, and `@defer` degenerates into deferred rendering. Additionally, only standalone dependencies can be deferred.
3. Because "just a spinner" produces two visual defects on a fast connection. If loading takes 40 ms, the spinner blinks and disappears — the user sees a flash and reads it as a glitch; `@loading (after 150ms)` shows no indicator at all in that case. The reverse situation: a placeholder appears and vanishes after 20 ms — `@placeholder (minimum 300ms)` keeps it long enough for the transition to look intentional. This is managing perceived performance: the numbers are the same, the feeling is not.
4. On by default: zoneless change detection (since v21) — checks happen only on explicit notifications instead of walking the whole tree on every async operation; `OnPush` for components (since v22) — a component is checked only when its inputs changed, an event occurred, or a signal read in its template changed; and signals as the fine-grained notification mechanism. Your own code can switch them off: an explicit `ChangeDetectionStrategy.Eager` (checked on every traversal), method/getter calls in templates and impure pipes (evaluated on every check with no cache), mutation instead of `set` (no notification arrives at all), and manual `detectChanges()` calls in handlers.
5. Because a budget is an automated check and a glance is not. `maximumError` fails the build, so a regression is caught in CI before the merge rather than six months later during a performance review. Budgets also separate concerns: `initial` watches startup weight, a named `bundle` watches one lazy section, and `anyComponentStyle` catches a theme accidentally imported into a single component. And they give numbers pinned to the project's configuration rather than to a developer's memory of "how big it was last time".

</details>

## Common mistake

The first is optimizing without measuring. It comes from React experience where memoization is routine: the developer wraps every expression in a `computed`, splits components "so less re-renders", and sprinkles `@defer` where there is nothing to load. In Angular 22 that is almost always pointless: `OnPush` and signals already provide fine-grained updates, and extra `computed` values around arithmetic only grow the dependency graph. Worse, such edits mask the real cause — usually one method in a hot component's template, or an `Eager` strategy left over from a migration. The order is the opposite: take a profile, find the most expensive CD cycle, see whose template runs most often inside it — fix that, then measure again.

The second is a `@defer` that deferred nothing. The block is written, the placeholder looks nice, and the `initial` chunk is the same size. In 90% of cases the cause is singular: the same component is mentioned in this component's `imports` or used elsewhere in the template (sometimes in a hidden `@if` branch), so it remains a static dependency. Less often it is a `viewChild` reference. This is verified not by reasoning but by `stats.json` in esbuild-analyze: if there is no separate chunk, the compiler could not split the code. And the symmetric mistake is `@defer` on everything, including small components: each block is a separate request with its own latency, so split what actually weighs something and keep the rest in the main chunk.
