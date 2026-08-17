# Dev Server and HMR

## What HMR really is: swapping a module in a running application

The formulation worth holding on to: **hot module replacement swaps one module's code inside an already running application, without losing its state.** Not "a fast reload" and not "auto-refresh the page" — a fundamentally different operation.

```txt
                 Hot reloading and a page reload are different things
┌─────────────────────────┬────────────────────────────┬─────────────────────────────┐
│ criterion               │ live reload                │ HMR                         │
├─────────────────────────┼────────────────────────────┼─────────────────────────────┤
│ what it does            │ reloads the page           │ swaps the module in place   │
├─────────────────────────┼────────────────────────────┼─────────────────────────────┤
│ application state       │ lost                       │ preserved                   │
├─────────────────────────┼────────────────────────────┼─────────────────────────────┤
│ scroll, an open modal   │ lost                       │ preserved                   │
├─────────────────────────┼────────────────────────────┼─────────────────────────────┤
│ what goes over the wire │ a "reload yourself" signal │ the changed module's code   │
├─────────────────────────┼────────────────────────────┼─────────────────────────────┤
│ code support required   │ no                         │ yes: an accept boundary     │
├─────────────────────────┼────────────────────────────┼─────────────────────────────┤
│ if no boundary exists   │ —                          │ falls back to a full reload │
└─────────────────────────┴────────────────────────────┴─────────────────────────────┘
          the point of HMR is not speed as such but that application state —
             a filled-in form, an open wizard step — survives the change
```

The difference is clearest in a real scenario: you are debugging the third step of a checkout wizard. Live reload puts you back on step one with an empty form, and every CSS tweak costs you a re-fill. HMR swaps the styles and leaves you where you were. That is the value — not the milliseconds saved.

An important consequence: **HMR requires support in the code.** Somebody has to tell the runtime what to do with the new version of a module: recreate the component, repaint the styles, re-attach the listener. It does not happen by itself.

## The accept boundary and bubbling up the graph

The mechanism rests on one primitive — a module can declare that it knows how to accept its own new version:

```ts
// Vite
if (import.meta.hot) {
  import.meta.hot.accept((newModule) => {
    // the updated module arrives here; we decide what to do with it
    applyTheme(newModule.theme);
  });
}
```

```js
// Webpack — the same idea, a different vocabulary
if (module.hot) {
  module.hot.accept('./theme', () => {
    applyTheme(require('./theme').theme);
  });
}
```

A module that declares `accept` is an update **boundary**. From there a simple rule applies:

```txt
     How an update bubbles up the graph to a boundary
┌───────────────────────────────────────────────────────┐
│ ui/Button.tsx changed — the new module code is ready  │
│                           ↓                           │
│ does the module itself accept? no                     │
│                           ↓                           │
│ move up to the importer: routes/Orders.tsx            │
│                           ↓                           │
│ it does accept — Fast Refresh put it there → BOUNDARY │
│                           ↓                           │
│ the module is swapped, component state intact         │
└───────────────────────────────────────────────────────┘
 if no importer provides a boundary, the bubbling reaches
   the entry point — and that means a full page reload
```

Why it bubbles up rather than down is a matter of logic, not implementation. If a module changed but does not know how to reinstall itself, the only party that can do it is whoever imported it: that module holds the reference and can pick up the new version. If it cannot either, we move on to its importer. Reaching the entry point without a boundary, the runtime honestly gives up and reloads the page.

Hence **the main practical takeaway of this article**: a full reload instead of HMR almost never means "HMR is broken". It means that nowhere between the changed file and the entry point was there a module willing to accept the update.

Besides `accept`, three more primitives are worth knowing:

```ts
if (import.meta.hot) {
  // clean up after the previous version: timers, listeners, subscriptions
  import.meta.hot.dispose(() => clearInterval(timer));

  // carry data across into the new version of the module
  import.meta.hot.data.scrollTop = el.scrollTop;

  // "I accepted the update but cannot handle it" — pass it upward
  if (!canHandle(newModule)) import.meta.hot.invalidate();
}
```

`dispose` is the most underrated of them. If a module starts a timer or subscribes to an event at top level and no `dispose` is written, every hot replacement leaves the previous version running. The symptom is recognizable: after ten edits a request fires ten times instead of once. That is not an "HMR bug" but an unreleased resource.

## How this works in Webpack and in Vite

```txt
  WEBPACK: rebuild what was touched              VITE: one file on request
┌────────────────────────────────────┐    ┌─────────────────────────────────────┐
│ after a file is saved              │    │ after a file is saved               │
│                                    │    │                                     │
│ 1   the watcher noticed a change   │    │ 1   the watcher noticed a change    │
│ 2   affected modules are rebuilt   │    │ 2   the module is marked stale      │
│ 3   hot-update files are generated │    │ 3   a message over the WebSocket    │
│ 4   a message over the WebSocket   │    │ 4   the browser asks for ONE module │
│ 5   the browser fetches hot-update │    │ 5   one file is transformed         │
│ 6   the runtime swaps the module   │    │ 6   the accept boundary applies it  │
└────────────────────────────────────┘    └─────────────────────────────────────┘
     the work depends on how many           the work does not depend on project
     modules the rebuild touched              size: it is always a single file
```

The update model is identical in both cases — an `accept` boundary, bubbling, a fallback reload. What differs is **how much work is needed for the update to arrive.**

**Webpack** keeps the built graph in memory and, after a file changes, rebuilds the affected portion. The affected portion is not one file: if the changed module belongs to a chunk, the chunk has to be recomputed, and with module concatenation enabled, its neighbours too. The result is written into hot-update files (`.hot-update.json` and `.hot-update.js`), which the browser is told about over the WebSocket. Hence an important property: reaction time grows with the project, because the amount of rebuilding grows.

**Vite** holds no bundle, so there is nothing to rebuild. It marks the module stale, sends a message to the browser, and the browser requests **exactly one** module — which is transformed on demand like any other dev-mode request ([The Vite Model]). The amount of work depends neither on project size nor on which chunk the module would have landed in for production.

That, not the implementation language, is why Vite's updates are nearly instant on both small and large projects. The interview phrasing: **Webpack rebuilds what was affected, Vite invalidates one module and serves it on request.**

Worth noting what does *not* differ: if your code contains no `accept` boundary at all, both tools will simply reload the page. There is no such thing as "HMR out of the box" — it comes from framework integration, and for React that means Fast Refresh.

## React Fast Refresh and its rules

Fast Refresh is a plugin (`@vitejs/plugin-react` in Vite, `react-refresh-webpack-plugin` in Webpack) that automatically inserts `accept` into files containing React components and knows how to recreate a component while preserving its state. In other words, it is the mechanism that creates update boundaries on your behalf.

But it works by rules, and when the rules are broken, state is lost — with no error message whatsoever.

```txt
                          Fast Refresh: why component state was lost
┌──────────────────────────┬───────────────────────┬─────────────────────────────────────────┐
│ what is in the file      │ what happens          │ why                                     │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ function Button() { … }  │ state is preserved    │ the component is found by name          │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ export default () => …   │ state is lost         │ an anonymous function is unrecognizable │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ function example() { … } │ state is lost         │ the name is not PascalCase              │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ class Button extends …   │ state is reset        │ classes are not supported               │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ a hook added or removed  │ state is reset        │ the hook order changed                  │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ a non-component export   │ the update bubbles up │ the file is no longer a boundary        │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────────┤
│ export * from …          │ not supported         │ the set of exports is invisible         │
└──────────────────────────┴───────────────────────┴─────────────────────────────────────────┘
               the practical rule: one file, one component declared as a named
                    function; keep constants and helpers in separate files
```

Three rules from that table deserve a closer look, because they come up daily.

**The component must be recognizable.** Fast Refresh ties state to a component's identity, and it derives identity from the name. An anonymous function has no such identity:

```tsx
// ❌ state will be lost on every edit
export default () => <OrdersTable />;

// ✅ the same thing, with a name
function Orders() {
  return <OrdersTable />;
}
export default Orders;
```

For the same reason the name must be PascalCase: to React, `function orders()` is not a component but an ordinary function.

**A file must export only components.** This is the least obvious rule and the most common cause of surprise full reloads:

```tsx
// ❌ Orders.tsx stops being an update boundary
export const ORDERS_PER_PAGE = 20;
export function Orders() { /* ... */ }
```

Fast Refresh cannot guarantee that swapping the module is safe when a constant is exported from it: anyone could be using that constant, and merely recreating the component is not enough. So the boundary disappears and the update bubbles higher. The fix is moving non-components into their own file; `eslint-plugin-react-refresh` warns about exactly this and catches such places up front.

**Changing hooks resets state.** And rightly so: hook state is stored positionally, so if you add a `useState` in the middle of a component, the old state no longer corresponds to the new code. Fast Refresh honestly resets it rather than feeding values into the wrong variables. Class components always remount for the same reason: Fast Refresh cannot preserve their state at all.

## Proxying to the backend, and CORS in dev

In production the frontend and the API usually share a domain (or the API sits behind the same CDN), so CORS never comes up. In dev the app runs on `localhost:5173` while the API runs on `localhost:3000` — different origins, and the browser starts demanding CORS headers from the backend.

The right answer is not to allow CORS for the sake of development but to eliminate the cross-origin situation: the dev server proxies API requests itself.

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,                            // rewrite the Host header
        rewrite: (path) => path.replace(/^\/api/, ''), // if the backend has no /api prefix
      },
    },
  },
});
```

```js
// webpack.config.js — the same job; note the shape of the value
module.exports = {
  devServer: {
    port: 8080,
    // in webpack-dev-server 5, proxy is an ARRAY; the v4 object form no longer works
    proxy: [
      {
        context: ['/api'],
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    ],
    historyApiFallback: true,   // SPA: serve index.html instead of a 404
    hot: true,                  // on by default
  },
};
```

The shape of `proxy` is a practical upgrade trap: it was an object in `webpack-dev-server` 4 and an array of objects in 5, so an old config simply stops working.

Two neighbouring settings deserve a mention, because they get asked about:

- **`historyApiFallback`** (Vite enables this behaviour for SPAs by default) — serve `index.html` for any path. Without it, reloading the page on `/orders/42` gives a 404: no file with that path exists, because routing lives in the client.
- **`hot: 'only'`** in Webpack — do not fall back to a full reload when an update cannot be applied. Useful when preserving state matters more than the screen being current.

Separately, what proxying does *not* solve: **it is dev-only.** If your production app calls an API on a different domain, CORS has to be configured on the backend for real, and the dev proxy hides that work rather than doing it. The classic "works in dev, CORS in prod" bug belongs to the same family as the other dev/prod differences ([The Vite Model]). The CORS headers themselves are covered in the HTTP/REST and Security topics.

## Source maps in dev

In dev, source maps have a different priority than in production: what matters is not completeness but **rebuild** speed — the map is regenerated on every save.

```js
// webpack.config.js — a sensible dev default
module.exports = {
  mode: 'development',
  devtool: 'eval-cheap-module-source-map',
};
```

Decoding the name: `eval` means module code runs through `eval` with a source annotation (fast), `cheap` means line-only mappings with no columns, and `module` means loader-produced maps are honoured, so stack traces show your TypeScript rather than the result of transpiling it. The full table of options and trade-offs is in [Tree Shaking and Optimization].

Vite has no separate dev setting: maps are on in dev, because one file is transformed at a time and producing them is cheap. Only production is configurable, through `build.sourcemap`.

One practical check worth doing once per project: set a breakpoint in a TSX file and confirm the debugger shows your source with real names. If you see transpiled code instead, the chosen variant lacks `module`, and debugging will be miserable.

## Diagnosing: HMR is not firing

```txt
                                               Diagnosing: HMR is not firing
┌───────────────────────────────┬─────────────────────────────────────────┬───────────────────────────────────────────────┐
│ symptom                       │ likely cause                            │ what to check                                 │
├───────────────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ the whole page reloads        │ no accept boundary on the way up        │ the file exports more than a component        │
├───────────────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ state lost, page not reloaded │ Fast Refresh did not recognize it       │ anonymous default export, class, hooks        │
├───────────────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ nothing happens at all        │ the watcher misses the file change      │ Docker, WSL, network drive: polling vs events │
├───────────────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ new code, old behaviour       │ the previous effect was not cleaned up  │ timers, listeners, subscriptions in dispose   │
├───────────────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ new dependency optimized      │ a dependency was discovered late        │ list it in optimizeDeps.include               │
├───────────────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ a WebSocket error in console  │ the connection never reached the server │ proxy, https, HMR client port and host        │
└───────────────────────────────┴─────────────────────────────────────────┴───────────────────────────────────────────────┘
                              the order to work through: first "did the update arrive at all",
                             then "was a boundary found", and only then the Fast Refresh rules
```

The order matters, because the symptoms look alike while the causes sit at different levels. The right sequence:

**1. Did the update reach the browser?** Open the console and see whether an update message appears after a save. Silence means the problem is not HMR but file watching or the connection. Typical culprits: code inside a Docker container or on a mounted drive, where file system events are not propagated — cured by switching to polling (`server.watch.usePolling` in Vite, `watchOptions.poll` in Webpack, with the caveat that polling burns CPU). The second culprit is a WebSocket that never connected: the app is opened through your own proxy or over https, and the client needs to be told where to knock (`server.hmr.clientPort`, `server.hmr.protocol`).

**2. Was a boundary found?** If the message appears but the page reloads entirely, the bubbling reached the root. Start not with settings but with the changed file: does it export anything besides components, is there a barrel file in the chain, was the changed file one that everybody imports (a theme config, say) — updating such a module naturally leads to a reload.

**3. The Fast Refresh rules.** If the page does not reload yet state is still lost, the issue is component recognition: an anonymous `export default`, a name that is not PascalCase, a class component, a changed set of hooks.

**4. Unreleased resources.** A distinct symptom: the code updated but behaves oddly — requests are duplicated, handlers fire several times. That is a missing `dispose`.

A closing caveat worth saying out loud: **HMR is a development tool, not a correctness check.** An application that has lived in the browser for two hours under a hundred hot replacements is in a state no user ever reaches. If behaviour looks inexplicable, the first thing to do is reload the page and see whether the problem reproduces from a clean start.

## Relation to other topics

```txt
[Why Bundlers Exist]                — the dev-versus-prod frame: why feedback
                                       speed is what matters in dev
[The Module Graph and Resolution]   — the graph an update bubbles up through
[The Webpack Core Model]            — the devServer section and the model of
                                       one build for both modes
[The Vite Model]                    — transform-on-request, from which HMR's
                                       independence from project size follows
[Tree Shaking and Optimization]     — the full table of source map options
[Ecosystem and Choosing a Tool]     — what to measure when the dev server drags
React topic                          — Fast Refresh from the component side,
                                       and the rules of hooks
HTTP/REST and Security topics        — CORS for real, rather than via a proxy
Angular course                        — the Angular CLI dev server
```

## Common interview traps

- **"HMR is when the page reloads automatically"** — that is live reload, and the confusion is common. The key difference is one word: **state**. HMR swaps a module inside a running application; live reload restarts the application entirely.

- **Not knowing why a full reload happens instead of HMR.** The expected answer is about bubbling: the update searches up the graph for a module with `accept`, and if it finds none before the entry point, it falls back to a reload. "HMR must not be configured" without the mechanism is weak.

- **"Vite updates faster because it is written in Rust"** — again beside the point. The reason is the amount of work: Webpack rebuilds the affected part of the graph, Vite invalidates one module and transforms it on request. Hence the independence from project size.

- **"Fast Refresh is part of React"** — it is a separate bundler integration (a plugin) that inserts `accept` boundaries automatically. Without it, HMR in a React project would amount to reloading the page.

- **Being unable to explain why component state was lost.** The most practical question in this topic, and a good answer lists concrete causes: an anonymous `export default`, a non-PascalCase name, a class component, a changed set of hooks, a non-component export from the file. The last one is the least known and the most frequently hit.

- **Enabling CORS on the backend for the sake of local development** — a working but wrong solution: it weakens production for dev's benefit. The expected answer is a dev-server proxy, plus the awareness that a proxy hides rather than solves CORS in production.

- **Not knowing about `dispose`.** The question "after ten edits the request fires ten times — why?" cleanly separates people who have written HMR handlers by hand from people who have only used ready-made ones. The answer: previous versions of the module left timers and subscriptions behind.

- **Treating behaviour under HMR as equivalent to a clean load.** A long-lived application after many hot replacements is in a state no user ever sees. Before serious debugging, reload the page.
