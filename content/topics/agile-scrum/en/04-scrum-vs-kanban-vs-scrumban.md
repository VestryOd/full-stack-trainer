# Scrum vs Kanban vs Scrumban — how to choose

> This article builds on the structural differences covered in [02-scrum-framework](./02-scrum-framework.md) and [03-kanban-and-flow](./03-kanban-and-flow.md). Here we move from "how each method works" to "which method fits which kind of work" — and we honestly name the cases where the choice of method is driven by fashion and recruiter expectations, not by fit.

## The question you actually need to ask

The wrong question is: "Is Scrum better, or is Kanban better?" The right question is: **how predictable and "batchable" is the team's incoming work?**

- If work can be grouped into meaningful batches 1–2 weeks ahead, and priorities rarely change so sharply that they break that batch, a time-boxed structure (Scrum) gives real benefits: a sync point, a rhythm, a reason to regularly show value.
- If work arrives continuously and unpredictably, and it can't wait for the next sprint boundary without breaking the point of the work itself (a support ticket, an incident, an urgent bug report from a client), an artificial sprint boundary doesn't protect the work — it just creates friction between the plan and reality.

This axis — how predictable and "batchable" the incoming flow is — decides the right fit far more accurately than labels like "we're a product team" or "we're a support team."

## When Scrum fits

Scrum is useful where **forced cadence** and **clear closure points** actually add value:

- The team works on a product with distinct features that have a clear start and end within weeks, not hours.
- There are outside stakeholders (marketing, sales, leadership) who need a predictable sync point — "every two weeks there's a demo and an updated plan" is valuable on its own, for coordination outside the dev team.
- The team's work naturally allows planning for a fixed time horizon: you can meaningfully say "in the next two weeks we will do X," and that promise is unlikely to get broken by unexpected priorities.

**Where Scrum breaks down:** in highly interrupt-driven work (support, operations, on-call). If 40–60% of the Sprint Backlog regularly gets replaced by unplanned work (incidents, urgent client bugs), the whole idea of a plan fixed for two weeks becomes fiction. The team either keeps "reopening" the sprint, or keeps a Sprint Goal on paper while ignoring it in practice — which produces Zombie Scrum (see article 01), not because of bad execution, but because the structure itself doesn't match the nature of the work.

## When Kanban fits

Kanban is useful where the incoming flow is **unpredictable by nature**, and forcing it into fixed iterations creates friction instead of value:

- Support queues — tickets arrive continuously, each has its own priority and SLA (service-level agreement — an agreed response time), and making them "wait for the next sprint" defeats the whole point of support.
- Operations (ops) teams — infrastructure work, incidents, monitoring. Priorities are set by what's happening to the system right now, not by a two-week plan.
- Teams with a high share of maintenance work — bug fixes, technical debt, small changes, where a single task rarely needs a two-week planning horizon, but the flow of tasks is constant.

**What Kanban gives you in these conditions:** WIP limits keep the amount of work in progress under control no matter how many tickets actually arrive on a given day; flow metrics (cycle time, throughput) let you build probability-based SLA forecasts ("85% of tickets of this type close within 2 days") without needing to force work into artificial sprints; no required iteration means priority can shift instantly when reality changes, not only at a sprint boundary.

**Where Kanban creates friction:** there is no built-in, mandatory sync point with stakeholders. If outside parties need to regularly see progress and get a clear forecast like "this will be ready by date X," a team on pure Kanban has to deliberately build that communication itself (through Kanban Cadences — see article 03), rather than getting it "for free" as part of the framework.

## Comparison by team profile

```txt
┌─────────────────────────┬───────────────────────────┬──────────────────────────┐
│                         │ Scrum                     │ Kanban                   │
├─────────────────────────┼───────────────────────────┼──────────────────────────┤
│ Nature of incoming work │ Batchable, predictable    │ Continuous,              │
│                         │ 1–2 weeks ahead           │ unpredictable            │
├─────────────────────────┼───────────────────────────┼──────────────────────────┤
│ Sync point with         │ Built in (Sprint Review   │ Not built in by default, │
│ stakeholders            │ every N weeks)            │ set up separately        │
├─────────────────────────┼───────────────────────────┼──────────────────────────┤
│ Reaction to an urgent,  │ Breaks the Sprint Goal,   │ Instant —                │
│ unplanned priority      │ needs a sprint re-plan    │ just changes queue order │
├─────────────────────────┼───────────────────────────┼──────────────────────────┤
│ Forecasting             │ Velocity via story points │ Probability-based, from  │
│                         │ (a subjective estimate)   │ real flow metrics        │
├─────────────────────────┼───────────────────────────┼──────────────────────────┤
│ Typical team profile    │ Product development with  │ Support, ops,            │
│                         │ distinct features         │ maintenance-heavy teams  │
└─────────────────────────┴───────────────────────────┴──────────────────────────┘
```

## Scrumban — the pragmatic hybrid

**Scrumban** is not a formal framework with one official definition (unlike the Scrum Guide or David Anderson's Kanban Method). It's a label for a family of pragmatic combinations that many teams actually land on in practice, through trial and error rather than by following a textbook.

Here is the typical shape Scrumban takes in practice: the team keeps a Scrum-like meeting rhythm — regular planning and a retrospective every one or two weeks, because that gives a useful sync point with stakeholders and a reason to reflect — but **drops the hard commitment to a fixed Sprint Backlog**. Instead, the team uses a board with WIP limits and continuous flow (Kanban's mechanics): the queue gets replenished whenever capacity opens up, not only at Sprint Planning, and an urgent task doesn't require a formal "sprint re-plan" — it simply enters the queue at its real priority, as long as the WIP limit is respected.

This fits teams with a mixed profile — and in practice, that's most teams: a product team that has a main stream of planned feature work (where Scrum's cadence is useful), but also regularly gets hit with production incidents, urgent bugs from big clients, or unplanned technical blockers (where pure Scrum creates friction). Scrumban gives a predictable communication rhythm without pretending that a two-week plan will stay unchanged.

## An honest note: many teams "do Scrum" not because it fits

This is an observation a senior/lead should be able to state directly, not quietly avoid. Scrum became the industry's default not only because it structurally fits most teams, but also for reasons that have nothing to do with the actual nature of the work:

- **Recruiting filters on the checkbox "Agile/Scrum experience"** — a line like "we work in Scrum" sounds clear and checkable to a hiring manager, even if the team's real work fits the Scrum structure poorly.
- **Certifications create an industry incentive to standardize on Scrum** — CSM (Certified ScrumMaster) and similar certifications built a whole industry around Scrum specifically, regardless of whether it fits any given team's actual work.
- **Management needs a familiar framework name to report upward** — "we do Scrum" sounds like a clear, well-known answer to "how does your team work," while "we run a Kanban flow with weekly replenishment" requires an explanation not everyone is willing to give.

**How to spot the mismatch:** the clearest sign is a support team or a highly interrupt-driven team forced into two-week sprints, where 50–60% of the Sprint Backlog regularly gets replaced by unplanned work. Formally, this is still called "Scrum" — all five events happen, the roles exist — but in substance, the team spends its energy keeping up the fiction of a fixed plan that systematically fails, not because the team works badly, but because the method's structure doesn't match the nature of the work.

**What a senior/lead actually does about it:** not an abstract argument like "Kanban is better," but a conversation grounded in the team's own data. Collect concrete numbers: how many Sprint Backlog items get displaced by unplanned work, on average, over the last 5–6 sprints; how many Sprint Goals were actually met versus formally "extended" or quietly dropped. These numbers are a far more convincing argument for changing the process than pointing to an article that says "Kanban is better for support teams."

## Scenario: diagnosing a mismatch

A product support team has worked in two-week sprints for a year. At a retro, the tech lead raises the issue:

> **Tech lead:** I looked at the last six sprints. On average, 55% of the tasks we take into Sprint Planning either don't finish by the end of the sprint, or get displaced by incidents that come in during the sprint. We formally hold all five Scrum events, but in practice, the Sprint Goal almost never stays the same from the start of the sprint to the end.
> **PM:** But we need predictability to report to leadership.
> **Tech lead:** The predictability our current process gives you is an illusion — we promise a two-week plan and deliver about 45% of it on average. I'd like to try Scrumban for one quarter: keep the two-week planning and retro rhythm for syncing with you, but move to a WIP-limited board with continuous queue replenishment instead of a fixed Sprint Backlog. Then the forecast we give you will be based on our real throughput, instead of a plan we're systematically not delivering.

Notice the tech lead doesn't say "Scrum is bad" as a general claim. They show a specific structural mismatch using the team's own data, and propose an experiment with a measurable outcome, instead of switching processes on faith.

## Common interview traps

- **"Kanban is for ops, Scrum is for product development"** — this oversimplifies by team label instead of by the nature of the work. A product team that depends heavily on unpredictable changes in a partner's external API might actually fit Kanban better than a "pure ops" team that maintains a stable, well-understood system with a predictable stream of planned improvements. The right axis is how predictable the incoming work is, not what the team is called.

- **"Scrumban is just Scrum with a Kanban board"** — this misses the point: a board exists in pure Scrum too. The core of Scrumban is dropping the hard commitment to a fixed Sprint Backlog. Scrumban keeps the cadence (meeting rhythm) but drops the fixed-scope commitment.

- **"If Scrum isn't working, just switch to Kanban"** — changing frameworks without looking at flow data is the same cargo-cult mistake, just pointed the other way: swapping a label without understanding what's actually broken and why. Any switch should be argued using the team's own metrics (how much work gets displaced, what percent of Sprint Goals get met), not an abstract preference for one framework over another.

- **"Which framework you choose doesn't matter, as long as you deliver"** — partly true (results do matter more than the label), but this misses the point of the interview question. The interviewer wants to hear that you understand *specifically how* a mismatch between the framework and the nature of the work causes harm — broken promises to stakeholders, fake predictability, a team worn down by constantly re-planning — not a declaration that you don't care about process at all.
