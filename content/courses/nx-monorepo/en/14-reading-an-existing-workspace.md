# Capstone: auditing an unfamiliar Nx monorepo

## Theory

The final chapter targets the very task this course was built for. You land in an existing Nx monorepo — your work project — and within an hour or two you build an accurate picture of it. Not "as intended" per the wiki, but "as is" per the derived data.

### The principle: ask the tools, not the people

Wikis go stale, old-timers remember selectively, and the `README` was written three majors ago. The tools don't lie: `nx report` shows the actual versions, `nx graph` the actual relationships, `nx show project` the actual configuration after all the layers. This entire course has been building exactly these skills; the audit is their application along a top-down route:

```
┌────────────┬────────────────────────────┐
│ layer      │ source of truth            │
├────────────┼────────────────────────────┤
│ versions   │ nx report                  │
├────────────┼────────────────────────────┤
│ nx.json    │ cat nx.json                │
├────────────┼────────────────────────────┤
│ graph      │ nx graph + graph.json      │
├────────────┼────────────────────────────┤
│ targets    │ nx show project X --web    │
├────────────┼────────────────────────────┤
│ boundaries │ the root eslint config     │
├────────────┼────────────────────────────┤
│ federation │ module-federation.config.* │
├────────────┼────────────────────────────┤
│ CI         │ .github/workflows etc.     │
└────────────┴────────────────────────────┘

┌────────────┬───────────────────────────────────────────────────┐
│ layer      │ what to look for (chapter)                        │
├────────────┼───────────────────────────────────────────────────┤
│ versions   │ core/plugin drift, age (00, 13)                   │
├────────────┼───────────────────────────────────────────────────┤
│ nx.json    │ plugins, targetDefaults, namedInputs (01, 03, 04) │
├────────────┼───────────────────────────────────────────────────┤
│ graph      │ domains, bridges, dumping-ground libs (02, 05)    │
├────────────┼───────────────────────────────────────────────────┤
│ targets    │ each target's origin (01, 03, 08)                 │
├────────────┼───────────────────────────────────────────────────┤
│ boundaries │ real depConstraints or a placeholder (06)         │
├────────────┼───────────────────────────────────────────────────┤
│ federation │ host/remotes, shared, types (09–11)               │
├────────────┼───────────────────────────────────────────────────┤
│ CI         │ affected? base? remote cache? (05, 13)            │
└────────────┴───────────────────────────────────────────────────┘
```

The route isn't arbitrary: each layer builds on the previous one. Until you know the version, you don't know if it's crystal or fat configs. Until you've seen the graph, the boundary rules won't make sense. And until you've read the targets, there is nothing to look for in continuous integration (CI).

### The checklist: seven steps with commands

1. **Versions.** `npx nx report`. Do `nx` and all `@nx/*` match? How many majors behind latest? Then `git log --oneline -- package.json | head` — regular updates, or a frozen repo (migration debt, chapter 13)?
2. **nx.json.** A `plugins` block means the repo runs on crystal. In parallel, check project.json weight: `find . -name project.json -not -path '*/node_modules/*' -exec wc -l {} + | sort -n | tail`. Read `targetDefaults` (what pipeline is declared) and `namedInputs` (is there a `production` set — chapter 04). Peek at `tasksRunnerOptions` if present — a custom runner means a legacy remote-cache layer.
3. **The graph.** Run `npx nx graph`: how many projects, do domains read as groups, do cross-domain edges bypass shared? Then `nx graph --file=graph.json` plus the incoming-edge count (the chapter 02 one-liner) shows who sits at the repo's center. Also `grep -rn implicitDependencies --include=project.json .` — how many manual edges, and why.
4. **Targets.** For the main app — `npx nx show project <app> --web`: which targets exist, which are inferred, which come from project.json, what's in dependsOn. For the suspicious ones (deploy, migrate, custom executors) — find the impl (chapter 08) and `git log` the config: a living target or a fossil.
5. **Boundaries.** The root eslint config → `enforce-module-boundaries`: real depConstraints or the `'*' → '*'` placeholder? Tags: `grep -h '"tags"' **/project.json | sort | uniq -c` — which axes are in use and is every project covered. And the decisive check: does lint block merges in CI.
6. **Federation** (if present). Run `find . -name "module-federation.config.*"`. Who is the host, who are the remotes, and what do they expose — whole pages, or a scatter of components? Are there shared overrides, and why (git blame)? And are the types remotes.d.ts, or module federation 2.0 types?
7. **CI.** The pipeline config: `nx affected` or run-many/manual lists? How is the base computed (nx-set-shas or a hardcode)? Is there a remote cache (log markers) and how are the tokens split? Deploys — through affected, or "everything at once"?

### Archaeological finds: the catalogue

The typical fossils of a legacy monorepo — with a diagnosis and a direction of treatment:

- **Dead targets.** Executors whose configs are long deleted; a deploy last run two years ago (`git log` on the file + a CI search). Treatment: delete, after announcing it to the team.
- **A disabled cache.** `--skip-nx-cache` in CI "because the cache lied once", `cache: false` on build, no `production` in namedInputs. That's chapter 04: fixed by the inputs contract, not by the off switch; re-enabling the cache is the cheapest CI-time win available.
- **Decorative boundaries.** Tags assigned, the rule a placeholder, or lint not a required check on a pull request (PR). The illusion of boundaries from chapter 06; treatment — warn → backlog → error.
- **Microfrontends without the benefit.** module-federation.config exists, but CI builds and deploys everything in one pipeline. The team pays the full price of module federation (MF): runtime risks, shared negotiation, complexity. And it never receives the only benefit — independent deploys. The most expensive find in the catalogue; the honest options: finish building independent deploys, or roll back to build-time composition.
- **A double source of truth.** Fat project.json files with executors in a repo where crystal plugins are enabled: manual targets silently shadow the inferred ones (chapter 01). Treatment — migrations + purging the overrides.
- **A forest of buildable libs.** The legacy of tsc setups (chapter 12); with modern bundlers it's superfluous orchestration. Treatment is gradual: new libs non-buildable, old ones converted as touched.
- **implicitDependencies by the dozen.** The graph doesn't reflect reality and the team fights it by hand (chapter 02). Every manual edge asks: "which relationship is missing from the code?"
- **A frozen Nx version.** Three majors behind, upgrades "too scary". Migration debt grows nonlinearly (chapter 13); treatment — one major per PR, with migrations.json.

An important caveat: a find is neither a verdict nor grounds for condescension. The buildable forest was a *necessity* of its time; the community cache runner was the best available option. The audit records "as is" and the cost; whether to fix it is a separate conversation about risks and priorities.

## In a real-world monorepo

This whole chapter is this block; here — how to package the result so it outlives the audit:

- The audit artifact is a document with the 10 answers (the exercise below) + the top-3 finds with an effect estimate. Put it next to the repo (docs/ or a dated wiki page): the next newcomer starts from it, not from zero.
- Give every find a marker. Use 🔴 for losing money or safety right now: a write token in the repo, a disabled CI cache. Use 🟡 for growing debt: placeholder boundaries, a frozen version. Use 🟢 for a conscious trade-off, which you document and close.
- Finds become backlog items strictly one per PR — with a measurable before/after (CI time, violation count, buildable count).
- Re-run the checklist quarterly or after every major upgrade — audits go stale just like wikis.

## What we're adding to the project

The mini-shop code doesn't change. It becomes the reference instead: we run the checklist against it, with all the answers already known from chapters 00–13. That calibrates the format before you walk into a production repo.

## Practical exercise

**The main assignment of the course.** Apply the checklist to **your own work** Nx monorepo and write out the answers to the 10 questions — with the commands that produced each answer:

1. What Nx version is it, do all `@nx/*` plugin versions match, and when was the version last updated?
2. Is the repo on crystal (plugins in nx.json + thin project.json files) or on explicit executors? Is there a double source of truth?
3. What's in `targetDefaults` and `namedInputs`? Does a `production` set exist — and does a spec edit invalidate the build?
4. How many projects are in the graph, which domains/scopes are readable, and which three projects collect the most incoming edges?
5. Which tag axes are in use, are there real depConstraints, and does lint with them block merges in CI?
6. Which libs are buildable, and does each have a reason (incrementality / publishing / legacy)?
7. Is there a federation: who's the host, who are the remotes, what do they expose, are there shared overrides — and why?
8. Are the remotes actually deployed independently (per the CI config, not per what people say)?
9. CI: affected or run-many? Where does the base come from? Is there a remote cache, and how are read/write tokens separated?
10. How is Nx upgraded: is there a migrations.json in the history, and how many majors is the repo behind latest?

**Output:** a document with the 10 answers + the top-3 finds (🔴/🟡/🟢) with a one-per-PR plan.

**Edge cases to think about:**

- The answers to questions 3 and 9 contradict each other (production is configured, but CI runs run-many with no cache). Which layer "wins" for pipeline time?
- The repo answers "no" to question 8, yet the team is sure it has microfrontends. How do you raise that conversation tactfully?
- The repo shows not a single red flag. What do you double-check before believing it?

## Worked solution

The reference run against mini-shop (abridged — the format your production audit should follow):

1. **Versions:** nx and every @nx/* — one exact version (the chapter 00 pinning); recently updated. 🟢
2. **Crystal:** plugins in nx.json (@nx/vite → later the rspack chain, @nx/eslint), thin project.json files; the exceptions are the deliberate typecheck/deploy targets. No double source of truth. 🟢
3. **Cache:** targetDefaults declare the build/test/typecheck pipeline; namedInputs with production (specs subtracted), the SHOP_BANNER env input declared (chapter 04). A spec edit → build from cache. 🟢
4. **Graph:** apps + libs + api. The catalog / checkout / shared / api domains read as folders. At the center sit shared-ui and shared-api-types, as expected for a design system and a contract lib. 🟢
5. **Boundaries:** two axes (scope, type), real depConstraints (chapter 06), lint a required CI check (chapter 13). 🟢
6. **Buildable:** not a single buildable lib — with vite/rspack/esbuild the need never arose (chapter 12). 🟢
7. **Federation:** host shell, remotes catalog/checkout, page-granularity exposes. Shared uses the Nx default plus strictVersion for react (chapter 11). The workspace-lib strategy is written down: compatibility plus coordinated deploys via affected. 🟢
8. **Independent deploys:** yes — `nx affected -t deploy` on main deploys only the affected apps (chapter 13). 🟢
9. **CI:** one affected command, base via nx-set-shas; a remote cache isn't connected in the course project — recorded as a conscious trade-off. 🟡
10. **Upgrades:** the version is fresh; the process is migrate (chapter 13). 🟢

That's what a "healthy" map looks like. In a production repo, 3–4 🟡 and a couple of 🔴 are normal. The audit's value is precisely that they are now named, localized and priced.

Answers to the edge cases:

- The layers multiply rather than add. A perfect production set is useless if CI doesn't invoke nx with affected and the cache. Pipeline time is set by the weakest layer. Hence the fixing order runs top-down along the execution chain: first how CI calls Nx (affected + base), then the remote cache, then fine-tuning inputs.
- Raise it without accusations and without "you're doing it all wrong". Show the CI config and ask the question in terms of price. We pay for federation with runtime risks and shared negotiation, yet we deploy everything together. Do we want to finish independent deploys, or simplify to build-time composition? Both answers are legitimate (chapter 09). Only the current "price without the benefit" is not, and that is a team-level decision, not the auditor's.
- A too-green picture usually means the auditor checked declarations, not facts. The rule exists, but does it run in CI? The production set is declared, but does a spec edit produce a hit? The remotes deploy separately, but do they roll back separately? Every "yes" from a config should be confirmed by at least one observed run.

## Check yourself

1. Why does the audit start with `nx report` rather than reading the `README` and the wiki? State the principle.
2. The "remotes without independent deploys" find — why is it the worst price-to-benefit ratio in the whole catalogue, and what are the two honest ways out?
3. A repo has fat project.json files with executors and crystal plugins in nx.json at the same time. How do you determine, for a specific target, which layer actually executes — and why is the hybrid dangerous?
4. You have 15 minutes to assess the cache health of someone else's repo. Which three checks yield the most information?
5. The audit produced five finds: placeholder boundaries, run-many in CI, no production set, a frozen Nx version (−2 majors), a buildable forest. In what order do you fix them, and why?

<details>
<summary>Answers</summary>

1. The principle is "derived data over intentions". The `README` describes what was planned; the tools describe what is. The output of `nx report`, the graph and show project is computed from the repo's actual state and cannot go stale. The wiki is useful afterwards, as a source of "why is it like this?" questions rather than a source of facts. A divergence between the wiki and tool output is itself a find.
2. Because the team carries every MF cost: runtime integration, shared negotiation, version management, infrastructure for N artifacts. Meanwhile the single benefit — independent team release cycles — never materializes, because the release is still collective. There are two ways out. (a) Finish building independent deploys: affected -t deploy, canaries, the chapter 11 shared-lib strategy. Pick this one if the organizational need is real. (b) Roll back to build-time composition: the federation goes away, and the apps stay in the monorepo. The choice follows chapter 09's question about whether independent teams exist, not fashion.
3. Run `nx show project <name> --web`. It prints the final configuration with every option's source annotated, so you can see whether project.json shadowed an inferred target. The hybrid is dangerous for three reasons. Edits to the tool config (vite.config) get partially ignored, because the manual executor wins. Behaviour diverges between projects. And during upgrades the migrations update one layer while leaving the other, widening the gap.
4. (a) Run a large project's build twice in a row: is the second run `[local cache]` in milliseconds? (b) Edit any spec file and run build: a hit (a production set exists) or a miss (every test commit rebuilds the world)? (c) Check the CI log of a fresh PR: are there remote hits, or does every agent compute from scratch. Three checks covering the local contract, namedInputs and the team level.
5. Order them by payoff and by dependencies:

   - **First, CI on affected with a correct base.** It changes how pipeline time scales, and it requires nothing else to be in place.
   - **Second, the production set in namedInputs.** It amplifies both the local cache and the freshly enabled affected CI.
   - **Third, boundaries from warn to error.** This stops the *growth* of architectural debt. It is cheap to start and long to burn down, which is why it goes early.
   - **Fourth, the Nx upgrade, one major per PR.** It unlocks modern mechanisms and de-risks every following step.
   - **Fifth, the buildable forest.** It is the most work for the least effect, and it is dismantled as the libs are touched.

   The general principle: first what's cheap and changes the slope of the curve, then what's expensive and removes a level.

</details>

## Common mistake

The auditor's first mistake is conducting the audit through interviews and documentation. People sincerely retell the state of two years ago. The wiki describes a target picture that never shipped. And the audit records mythology instead of reality. Anything you can't obtain with a command, or read from a config with git blame, is a hypothesis rather than a fact.

The correct route is the reverse. Tools come first: report → nx.json → graph → show project → eslint → MF configs → CI. People come second, now with specific "why is it like this here?" questions. Those get answered willingly and precisely, because the question shows you know the context.

The second mistake is opening an epic "clean up the monorepo" PR after the audit. It flips boundaries to error, rewrites CI, dismantles the buildable libs and upgrades two majors in one go. Such a PR spends weeks in review, conflicts with all ongoing work and eventually dies, discrediting the very ideas it carried.

Finds are fixed one at a time. Each gets its own PR with a measurable effect: CI time on a typical PR going from 24 min to 9 min. Disruptive switches are turned on gradually — warn → error, one major at a time. An audit is a map of debt, not a mandate for revolution. The winner is whoever converts it into a dozen small, boring victories.
