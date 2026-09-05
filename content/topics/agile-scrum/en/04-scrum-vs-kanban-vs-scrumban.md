# Scrum vs Kanban vs Scrumban — how to choose

> This article builds on the structural differences covered in [02-scrum-framework](./02-scrum-framework.md) and [03-kanban-and-flow](./03-kanban-and-flow.md). Here we move from "how each method works" to the question of which method fits which kind of work. We also name the cases honestly: sometimes the choice of method is driven by fashion and recruiter expectations, not by fit.

## The question you actually need to ask

The wrong question is: "Is Scrum better, or is Kanban better?" The right question is: **how predictable and "batchable" is the team's incoming work?**

- If work can be grouped into meaningful batches 1–2 weeks ahead, a time-boxed structure (Scrum) gives real benefits. You get a sync point, a rhythm, and a reason to show value regularly. This holds while priorities rarely change sharply enough to break the batch.
- If work arrives continuously and unpredictably, an artificial sprint boundary does not protect it. It only creates friction between the plan and reality. Such work cannot wait for the next sprint boundary without losing its point: a support ticket, an incident, an urgent bug report from a client.

This axis is how predictable and "batchable" the incoming flow is. It decides the right fit far more accurately than labels like "we're a product team" or "we're a support team."

## When Scrum fits

Scrum is useful where **forced cadence** and **clear closure points** actually add value:

- The team works on a product with distinct features that have a clear start and end within weeks, not hours.
- There are outside stakeholders (marketing, sales, leadership) who need a predictable sync point. A promise like "every two weeks there's a demo and an updated plan" is valuable on its own, for coordination outside the dev team.
- The team's work naturally allows planning for a fixed time horizon. The team can meaningfully promise "in the next two weeks we will do X," and that promise is unlikely to get broken by unexpected priorities.

**Where Scrum breaks down:** in work that gets interrupted all the time — support, operations, on-call duty. If 40–60% of the Sprint Backlog regularly gets replaced by unplanned work, the whole idea of a two-week fixed plan becomes fiction. That unplanned work is incidents and urgent client bugs.

The team then has two options, and both are bad. It keeps "reopening" the sprint, or it keeps a Sprint Goal on paper and ignores it in practice. The result is Zombie Scrum (see article 01). The cause is not bad execution: the structure itself does not match the nature of the work.

## When Kanban fits

Kanban is useful where the incoming flow is **unpredictable by nature**, and forcing it into fixed iterations creates friction instead of value:

- Support queues. Tickets arrive continuously, and each one has its own priority and SLA (service-level agreement — an agreed response time). Making them wait for the next sprint defeats the whole point of support.
- Operations (ops) teams — infrastructure work, incidents, monitoring. Priorities are set by what's happening to the system right now, not by a two-week plan.
- Teams with a high share of maintenance work: bug fixes, technical debt, small changes. A single task there rarely needs a two-week planning horizon, but the flow of tasks is constant.

**What Kanban gives you in these conditions:**

- **WIP limits.** WIP is work in progress: the number of tasks open at the same time. The limit keeps that number under control, no matter how many tickets arrive on a given day.
- **Flow metrics.** These measure the work stream itself. Cycle time is how long one task takes from start to done; throughput is how many tasks finish per week.
- **Probability-based forecasts.** Flow metrics let you promise an SLA like "85% of tickets of this type close within 2 days" without forcing work into artificial sprints.
- **No required iteration.** Priority can shift the moment reality changes, not only at a sprint boundary.

**Where Kanban creates friction:** there is no built-in, mandatory sync point with stakeholders. Outside parties often need to see progress regularly and to get a clear forecast: "this will be ready by date X."

A team on pure Kanban has to build that communication deliberately, through Kanban Cadences — the regular review meetings described in article 03. Scrum gives the same thing for free, as part of the framework.

## Comparison by team profile

| Dimension | Scrum | Kanban |
|---|---|---|
| Nature of incoming work | Batchable, predictable 1–2 weeks ahead. | Continuous, unpredictable. |
| Sync point with stakeholders | Built in: a Sprint Review every N weeks. | Not built in by default, set up separately. |
| Reaction to an urgent, unplanned priority | Breaks the Sprint Goal, needs a sprint re-plan. | Instant: just change the order of the queue. |
| Forecasting | Velocity via story points, which is a subjective estimate. | Probability-based, from real flow metrics. |
| Typical team profile | Product development with distinct features. | Support, ops, maintenance-heavy teams. |

## Scrumban — the pragmatic hybrid

**Scrumban** is not a formal framework with one official definition (unlike the Scrum Guide or David Anderson's Kanban Method). It's a label for a family of pragmatic combinations. Many teams land on them in practice, through trial and error rather than by following a textbook.

Here is the typical shape Scrumban takes in practice. The team keeps a Scrum-like meeting rhythm: regular planning and a retrospective every one or two weeks. That rhythm gives a useful sync point with stakeholders and a reason to reflect. But the team **drops the hard commitment to a fixed Sprint Backlog**.

Instead it uses a board with WIP limits and continuous flow, which is Kanban's mechanics. The queue gets replenished whenever capacity opens up, not only at Sprint Planning. An urgent task does not require a formal sprint re-plan. It simply enters the queue at its real priority, as long as the WIP limit is respected.

This fits teams with a mixed profile, and in practice that is most teams. Take a product team with a main stream of planned feature work: Scrum's cadence is useful there. The same team also gets production incidents, urgent bugs from big clients and unplanned technical blockers, and there pure Scrum creates friction.

Scrumban gives a predictable communication rhythm without pretending that a two-week plan will stay unchanged.

## An honest note: many teams "do Scrum" not because it fits

This is an observation a senior/lead should be able to state directly, not quietly avoid. Scrum became the industry's default partly because it structurally fits most teams. But other reasons have nothing to do with the actual nature of the work:

- **Recruiting filters on the checkbox "Agile/Scrum experience."** A line like "we work in Scrum" sounds clear and checkable to a hiring manager. That stays true even if the team's real work fits the Scrum structure poorly.
- **Certifications create an industry incentive to standardize on Scrum.** CSM (Certified ScrumMaster) and similar certifications built a whole industry around Scrum specifically. Whether it fits a given team's actual work does not enter into it.
- **Management needs a familiar framework name to report upward.** The phrase "we do Scrum" is a clear, well-known answer when leadership asks how your team works. Saying "we run a Kanban flow with weekly replenishment" requires an explanation that not everyone is willing to give.

**How to spot the mismatch:** look for a support team, or any constantly interrupted team, forced into two-week sprints. In such a team, 50–60% of the Sprint Backlog regularly gets replaced by unplanned work.

Formally this is still called "Scrum": all five events happen, the roles exist. In substance, the team spends its energy maintaining the fiction of a fixed plan that systematically fails. The team does not work badly. The method's structure does not match the nature of the work.

**What a senior/lead actually does about it:** not an abstract argument like "Kanban is better," but a conversation grounded in the team's own data. Collect two concrete numbers:

- How many Sprint Backlog items get displaced by unplanned work, on average, over the last 5–6 sprints.
- How many Sprint Goals were actually met, versus formally "extended" or quietly dropped.

These numbers are a far more convincing argument for changing the process than an article that says "Kanban is better for support teams."

## Scenario: diagnosing a mismatch

A product support team has worked in two-week sprints for a year. At a retro, the tech lead raises the issue:

> **Tech lead:** I looked at the last six sprints. On average, 55% of the tasks we take into Sprint Planning have one of two outcomes. They either don't finish by the end of the sprint, or get displaced by incidents that arrive during it. We formally hold all five Scrum events. But in practice the Sprint Goal almost never stays the same from the start of the sprint to the end.

> **PM (product manager):** But we need predictability to report to leadership.

> **Tech lead:** The predictability you get now is an illusion. We promise a two-week plan and deliver about 45% of it on average. I'd like to try Scrumban for one quarter.

> Keep the two-week planning and retro rhythm for syncing with you. But move to a WIP-limited board with continuous queue replenishment, instead of a fixed Sprint Backlog. Then our forecast rests on real throughput, not on a plan we systematically miss.

Notice the tech lead doesn't say "Scrum is bad" as a general claim. They show a specific structural mismatch using the team's own data, and propose an experiment with a measurable outcome, instead of switching processes on faith.

## Common interview traps

- **"Kanban is for ops, Scrum is for product development"** — this oversimplifies by team label instead of by the nature of the work. Think of a product team that depends heavily on unpredictable changes in a partner's external API. It might fit Kanban better than a "pure ops" team that maintains a stable, well-understood system with a predictable stream of planned improvements. The right axis is how predictable the incoming work is, not what the team is called.

- **"Scrumban is just Scrum with a Kanban board"** — this misses the point: a board exists in pure Scrum too. The core of Scrumban is dropping the hard commitment to a fixed Sprint Backlog. Scrumban keeps the cadence (meeting rhythm) but drops the fixed-scope commitment.

- **"If Scrum isn't working, just switch to Kanban"** — changing frameworks without looking at flow data is the same cargo-cult mistake, pointed the other way. You swap a label without understanding what is actually broken and why. Argue any switch with the team's own metrics: how much work gets displaced, what percent of Sprint Goals get met. An abstract preference for one framework over another is not an argument.

- **"Which framework you choose doesn't matter, as long as you deliver"** — partly true, since results do matter more than the label. But it misses the point of the interview question. The interviewer wants to hear *specifically how* a framework that does not match the work causes harm. It breaks promises to stakeholders, creates fake predictability, and exhausts the team with constant re-planning. A declaration that you do not care about process is not that answer.
