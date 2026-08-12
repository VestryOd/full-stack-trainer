# Shared dependencies and federation pitfalls

## Theory

This is the most "painful" chapter of the course: everything described here is a real incident that happens in MF projects regularly. The good news: the list is finite, and almost everything is diagnosable in minutes once you know the mechanics.

### What Nx shares by default

We wrote nothing about shared in `module-federation.config.ts` — yet the negotiation from chapter 09 works. That's because the Nx plugin does the sharing **by itself**: every npm package from package.json (with `requiredVersion` taken from it; react and its family as singletons) and — an important Nx specialty — **workspace libs too**: `shared-ui`, `shared-util` and the rest land in the shared scope as singleton modules. The tuning knob is the `shared` function in the config:

```ts
const config: ModuleFederationConfig = {
  name: 'catalog',
  exposes: { './Module': './src/remote-entry.ts' },
  // for each candidate: false = don't share, undefined = the Nx default,
  // an object = your own singleton/strictVersion/requiredVersion
  shared: (name, defaults) => {
    if (name === 'react') return { ...defaults, strictVersion: true };
    return undefined;
  },
};
```

### Two reacts: why it's the hooks that break

From chapter 09 we know react is always `singleton: true`. Here's the failure mechanics when that's violated. React keeps state *at the module-instance level*: each react copy has its own internal hooks dispatcher (the very reference `useState` dereferences when called). The host's react renders a component → the dispatcher is set on **its** copy. But the catalog component was compiled against **its own** copy of react — its `useState` looks at the second copy's dispatcher, which is `null`. The result is the famous **"Invalid hook call"**, whose official cause list literally includes "more than one copy of React".

Same story with Context: a `createContext` in copy A and a `useContext` in copy B operate on different objects — the host's theme provider is invisible to the remote's components. The symptom is sneakier than hooks: nothing crashes, the remote just "didn't get the theme", or `useContext` returned the default.

Diagnosing duplicate reacts takes 30 seconds: in the console, `__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers.size` (more than 1 — there they are), and the Network tab: react chunks inside a remote's bundle when it should come from shared.

### Versions: the warning you must not ignore

When the singleton is in place but versions drift (the host built with react 18.3, a remote requiring ^19), the console shows a warning like `Unsatisfied version 19.0.0 ... of shared singleton module react (required ^18.3.0)` — and **the first one to load wins**. The app keeps running on the "wrong" version: maybe it's fine, maybe the remote calls an API that isn't there. `strictVersion: true` turns this into a remote-load error — harsh, but it fails at the boundary (where our chapter 10 RemoteBoundary catches it) instead of deep inside a render. Pragmatics: for react/router/state libraries — strictVersion plus upgrade discipline; production console warnings are not noise but drift telemetry.

### Workspace libs under federation: the subtlest part

Since Nx shares `shared-ui` as a singleton, there's one Button instance per page. Sounds great — until you remember MF's superpower, **independent deploys**:

- on Monday, catalog is deployed — its artifact contains *yesterday's* shared-ui;
- on Wednesday, Button is changed and only checkout is deployed — its artifact carries the *new* shared-ui;
- a user opens the page: the shared scope picks **one** shared-ui instance — whose? Both sides declare the same "version" (a workspace lib has no npm version), so the first to load wins. If catalog loaded first, checkout runs with *yesterday's* Button — one that no longer exists in its own sources.

That's the "remote shows stale/foreign UI" row in the table below. A monorepo *does not protect* you from version skew when deploys are unsynchronized: you *build* from one commit but *live* in production with artifacts from different commits. Three working strategies:

1. **Backward compatibility of shared libs** as the norm: change Button by addition, not reshaping; breaking changes go through a new component/prop with deprecation of the old one.
2. **Coordinated deployment** of the affected parts: shared-ui changed → `nx affected` knows every consumer (chapter 05) → deploy them together. The honest price: the thicker the shared layer, the less independent the deploys.
3. **Don't share** a specific lib (`shared: (n) => n === '@mini-shop/shared-ui' ? false : undefined`): each remote ships its own copy. The price — bundle size and a ban on Context/state inside the lib (there are two copies now); the payoff — full version independence.

Choosing among 1–3 is a team-level architectural decision, not a config line "to taste".

### Typing between host and remote

The `remotes.d.ts` from chapter 10 is a manual promise. Module Federation 2.0 does better: building a remote generates a types package for its exposes (`@mf-types`), and the host pulls them in — the IDE and tsc see the real signature of `catalog/Module`. Be sober about the guarantee: the types match the remote **at generation time**. A production remote deployed later may have changed — compiling the host against fresh types won't catch that. So MF types are a *development* tool, while the *production* contract is guarded by process: contract/e2e tests of the pair and canary deploys of remotes.

### The incident table

```
┌───────────────────────────────┬────────────────────────────┬──────────────────────────────────┐
│ symptom                       │ typical cause              │ first check                      │
├───────────────────────────────┼────────────────────────────┼──────────────────────────────────┤
│ eager consumption error       │ missing async boundary     │ main.ts = import("./bootstrap")? │
├───────────────────────────────┼────────────────────────────┼──────────────────────────────────┤
│ Invalid hook call             │ two react instances        │ devtools: renderers.size > 1?    │
├───────────────────────────────┼────────────────────────────┼──────────────────────────────────┤
│ warning: unsatisfied version  │ shared versions drifted    │ what each remoteEntry declares   │
├───────────────────────────────┼────────────────────────────┼──────────────────────────────────┤
│ 404 / CORS on remoteEntry.js  │ remote's address or deploy │ curl the config/manifest URL     │
├───────────────────────────────┼────────────────────────────┼──────────────────────────────────┤
│ remote shows stale/foreign UI │ workspace lib: first wins  │ when each remote was deployed    │
└───────────────────────────────┴────────────────────────────┴──────────────────────────────────┘
```

On "eager consumption" — the mechanics from chapters 09–10: code that synchronously consumes a shared module executed before negotiation managed to put that module into the shared scope. Cured by restoring the async boundary (`import('./bootstrap')`) — or, for the host's genuinely startup-critical dependencies, by `eager: true` (the module ships in the initial bundle and doesn't wait for negotiation).

## In a real-world monorepo

- Production, browser console: filter for "Unsatisfied" and "shared" — any warnings? That's your federation's version-drift map, free telemetry.
- `__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers.size` in production — the quick duplicate-react test (and check the design system in Network while you're at it: is it arriving in several remotes' chunks?).
- In every app's module-federation.config: is there a `shared` function with overrides, and why (git blame those lines — an incident usually stands behind every `false`).
- Find out the team's strategy for shared workspace libs: compatibility / coordinated deploys / no sharing? If nobody can answer, the strategy is "whatever happens", and the first-wins incident is ahead of you.
- Is MF type generation in place (`@mf-types` in artifacts, dts options in the config), and does CI build the host against the remotes' fresh types — that's the contract check.

## What we're adding to the project

The mini-shop code is unchanged at the end of this chapter — but along the way we break it twice: we reproduce the eager error and the duplicate-react conflict, diagnose both incidents with standard tools, and fix them. Plus we prove that shared-ui really exists in a single instance.

## Practical exercise

**Input:** the federation from chapter 10 (host + catalog + checkout).

**Task:**

1. **Prove shared-ui sharing.** Add a temporary side effect to the Button module (`console.log('[shared-ui] module loaded')`), visit `/catalog` and `/checkout` — how many times did the log fire? Explain. Remove the log.
2. **Reproduce the eager error.** Inline the contents of bootstrap.tsx straight into main.ts (removing `import('./bootstrap')`). Record the exact error text, explain the mechanics, revert.
3. **Reproduce two reacts.** In the catalog's module-federation.config, exclude react from shared (`shared: (name) => name === 'react' ? false : undefined`). Open `/catalog`, record the error. Diagnose: `renderers.size` in the console, the react chunk in Network inside the catalog bundle. Revert.
4. **Tighten the contract.** In the host, declare `strictVersion: true` for react (with requiredVersion from package.json). Verify the federation works as before, and answer in writing: what will now happen instead of the "quiet warning" on version drift, and where will that error be caught?
5. **Dissect first-wins.** In writing, step by step, walk the scenario "catalog deployed Monday, Button changed Tuesday, checkout deployed Wednesday": which Button does the user see on `/checkout` and why? Pick a strategy for mini-shop (compatibility / coordinated deploys / no sharing) and justify it.

**Edge cases to think about:**

- Why is `shared: () => false` for *all* workspace libs a bad default, even though it "removes" first-wins?
- The design system keeps the current theme in a React Context. What happens if you stop sharing it?
- Can strictVersion help against first-wins for workspace libs?

## Worked solution

**Step 1.** The log fires **once**, on the first visit to either remote: shared-ui entered the shared scope as a singleton, and the second remote received the already-initialized module. That's the Nx default for workspace libs in action.

**Step 2.** After inlining bootstrap:

```
Uncaught Error: Shared module is not available for eager consumption: webpack/sharing/consume/default/react/react
```

The mechanics: `createRoot`/JSX execute in the synchronous startup chunk; the shared react hasn't been negotiated yet (negotiation is async). `import('./bootstrap')` gives the bundler the break point: container init and the shared scope first, application code second. The revert = restore the two-file pair.

**Step 3.** The experiment config:

```ts
// apps/catalog/module-federation.config.ts — an EXPERIMENT, do not merge
const config: ModuleFederationConfig = {
  name: 'catalog',
  exposes: { './Module': './src/remote-entry.ts' },
  shared: (name) => (name === 'react' ? false : undefined),
};
```

Now catalog bundles its own react. The host renders CatalogPage with its react, but her code calls `useState` from the catalog's copy — a foreign dispatcher:

```
Uncaught Error: Invalid hook call. Hooks can only be called inside of the body of a function component.
```

The diagnostics confirm it: `__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers.size === 2`, and in Network a react chunk arrives with the catalog bundle. Note: the error was caught by chapter 10's RemoteBoundary — the catalog route failed, not the whole app. Reverting the config restores the singleton.

**Step 4.** The tightening:

```ts
// apps/shell/module-federation.config.ts
const config: ModuleFederationConfig = {
  name: 'shell',
  remotes: ['catalog', 'checkout'],
  shared: (name, defaults) =>
    name === 'react' || name === 'react-dom'
      ? { ...defaults, singleton: true, strictVersion: true }
      : undefined,
};
```

On a future drift (a remote built against react 19), instead of a warning + first-wins there will be an error **at remote load time** — that is, at the boundary, where RemoteBoundary shows the fallback. A deliberate trade-off: an unavailable catalog with a clear error in monitoring versus "works, but unpredictably".

**Step 5.** The user on `/checkout` sees **yesterday's** Button if catalog initialized first (say, the user entered through `/catalog`): its shared-ui claimed the singleton slot, and checkout, deployed with the new version, received someone else's old module. Worse — the behaviour depends on navigation order: straight to `/checkout` — the new button; via the catalog — the old one. For mini-shop we choose strategy 1+2: shared-ui evolves backward-compatibly, and on breaking changes `nx affected` tells us whom to deploy together (chapters 05 and 13 turn that into CI automation).

Answers to the edge cases:

- A blanket `false` for workspace libs cures first-wins at the cost of everything sharing exists for: every remote ships copies of ui/util (size), and — worse — any Context/state in those libs stops being common. Duplication-by-default is microfrontends without the monorepo benefits; a *targeted* `false` for one problematic lib is a legitimate tool.
- A theme in Context + an unshared design system = exactly the "two createContexts" case: the ThemeProvider from the host copy is invisible to the remote copies — remotes get the default theme. Libs with Context/state must be shared (singleton) — or the state must move out of them.
- No: strictVersion compares versions, and workspace libs have none (or everyone's is the same "0.0.0") — *content* drift under an identical "version" is invisible to strictVersion. Against first-wins only the theory's strategies work: compatibility, coordinated deploys, or not sharing.

## Check yourself

1. Describe the chain by which two react instances produce "Invalid hook call" — where exactly does the state that diverges live?
2. Why doesn't a monorepo protect a federation from shared-lib version skew even though everyone builds from one repository? What are the three defence strategies and the price of each?
3. An "Unsatisfied version of shared singleton module" warning in production: what actually happened, what's the risk, and what does strictVersion change?
4. What does MF 2.0 type generation between host and remote guarantee, and what does it NOT guarantee? What complements the contract for production?
5. A developer hit "Invalid hook call" and, following internet advice, deleted node_modules, ran `npm dedupe` and added resolutions. It didn't help. Why were those actions off-target in an MF project, and what's the correct diagnostic sequence?

<details>
<summary>Answers</summary>

1. The react module internally keeps a reference to the current hooks dispatcher, which the renderer sets before invoking a component. The host's react renders the component and sets the dispatcher on **its** copy; the component's code was compiled importing **another** copy — its `useState` reads the dispatcher of the copy where it was never set. Context objects and the scheduler diverge the same way. The "which dispatcher is current" state is per-module, so two module copies = two disconnected worlds.
2. Build and deploy live on different time axes: everything builds from one commit, but the artifacts in production come from different commits (each remote deployed at its own moment). A workspace lib in the shared scope is a singleton without a meaningful version: the first to load wins, and its content may be older than everyone else's. Strategies: (a) backward compatibility of shared libs — price: API evolution discipline; (b) coordinated deployment of everything affected (via affected) — price: less independent deploys; (c) not sharing a given lib — price: bundle duplication and no common Context/state inside it.
3. Negotiation found that one participant's declared range isn't satisfied by the version that landed in the shared scope — but because of singleton it took what was there and moved on. The risk is runtime behaviour of the "wrong" version: from harmless to calling a nonexistent API deep in a render. strictVersion moves the failure to remote load time: an error at the boundary (caught by the error boundary, visible in monitoring as a load failure) instead of unpredictability inside.
4. It guarantees: at type *generation* time, the exposes signatures match the remote's real code — IDE autocomplete and a tsc failure on incompatibility when the host builds. It doesn't guarantee: that the remote running in production at runtime is the same one — it may have been deployed later with a different contract. Complemented by process: CI builds the host against all remotes' fresh types (the contract check), e2e of the pair, canary deploys of remotes.
5. All three actions cure "two react versions in node_modules" — a single-app/npm-world disease. In a federation the second react arrives not from the host's node_modules but **over the network in a remote's bundle**: deduplicating local dependencies can't touch it. The correct sequence: (1) `renderers.size` in the console — confirm the duplicate; (2) Network — whose bundle shipped the second react; (3) that app's module-federation.config — why react isn't shared (excluded, or singleton broken); (4) fix the shared config.

</details>

## Common mistake

"Invalid hook call" trails an enormous internet legacy from the single-app world, where its cause is two react versions in node_modules. A developer coming from there habitually treats it with `npm dedupe`, resolutions and lock-file regeneration — and it doesn't help, because in a federation the second react arrives **over the network from a neighbouring app's bundle**, somewhere npm tooling never looks. The first reflex in an MF project is different: `renderers.size` → Network → the shared config. The diagnostic direction is "what loaded into the browser", not "what's in node_modules".

The second mistake is strategic: the team believes the monorepo automatically protects the federation from drift ("we build everything from one commit"). Build — yes; *live* in production — with artifacts from different commits, because deploys are independent — that's the entire point of MF. While shared workspace libs change backward-compatibly, the illusion holds; the first breaking Button refactor plus unsynchronized remote deploys produces a floating bug that depends on the user's navigation order. The shared-libs strategy (compatibility / coordinated deploys / no sharing) must be chosen and written down before the first incident, not after.
