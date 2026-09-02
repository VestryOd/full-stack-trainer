# Kanban and Flow

## What Kanban is

Kanban is a method for managing the flow of work. It limits how many tasks are in progress at the same time, and it makes bottlenecks visible. Unlike Scrum, it is not a framework with a fixed set of roles and required rituals. You can apply it on top of almost any existing process.

### Where the name comes from

Kanban (Japanese 看板 — "signboard", "signal card") comes from the Toyota Production System, Toyota's manufacturing system from the 1940s and 50s. Signal cards there controlled the flow of parts on the assembly line. The next stage of production pulled parts from the previous stage only when it had the capacity to work on them. It did not take them whenever the previous stage happened to produce them.

David Anderson brought this idea into software development in the mid-2000s. He adapted the manufacturing flow principles for software teams; his key book is *Kanban: Successful Evolutionary Change for Your Technology Business* (2010).

## Visualizing work

The first and most recognizable part of Kanban is the board. Columns represent stages of the workflow, for example Backlog → In Progress → In Review → Done, and cards represent units of work. This is not just a nice way to display things. The point is to make invisible work — discussions, waiting for review, blockers — visible to the whole team at the same time.

```txt
Backlog     │  To Do    │  In Progress │  In Review │  Done
────────────┼───────────┼──────────────┼────────────┼─────────
[item]       │  [item]   │  [item] [item]│  [item]    │ [item]
[item]       │  [item]   │              │            │ [item]
[item]       │           │              │            │
```

Visualizing work does not solve problems on its own — it exposes them. A team that keeps the board honest quickly notices things it could not see before. One example: the "In Review" column is always full. Before the board, each developer only knew about their own tasks.

## Pull vs Push — the core difference

A **push system** moves work forward to the next stage no matter whether that stage has the capacity to take it. Two classic examples:

- A manager assigns tasks to developers at the start of the week, following a plan. Nobody checks how many tasks each developer already has in progress.
- An analyst finishes a spec and "hands it over" to development, without checking whether the dev team is ready to start on it.

A **pull system** works the other way: the next stage requests (pulls) new work only when it has free capacity. A developer picks up a new task from "To Do" only after finishing the previous one, or after a slot opens up. The number of those slots is set by a **WIP limit**. WIP is work in progress: the tasks a team has started but not yet finished.

| | Push | Pull |
|---|---|---|
| What triggers the move | The previous stage finished its part. | The next stage has free capacity. |
| Where the queue lives | Hidden in front of a bottleneck. | Visible on the board. |
| What a stage reports | "I passed the task along." | "I can take one more", or "I cannot". |

The difference looks small, but the consequences are not. Push creates hidden queues: work piles up in front of a bottleneck, and nobody notices. Each stage reports "I passed the task along", and nobody tracks what happens after that. Pull makes the bottleneck visible at once. If the next stage cannot take the work, it stays where it is, and the board shows that.

## WIP limits — not a board hygiene rule, but a queueing-theory argument

The most common mistake about WIP limits is to read them as an arbitrary tidiness rule. The rule then sounds like "do not take more than three tasks into this column, so it does not look messy". In fact there is real math behind the limits.

### Little's Law

This is a formula from queueing theory. It applies to any stable system where things enter and leave:

```txt
WIP = Throughput × Cycle Time

which means:

Cycle Time = WIP / Throughput
```

Here, **WIP** is the number of work items currently in the system. **Throughput** is how many items finish per unit of time. **Cycle Time** is how long it takes one item to move through the system.

The practical result: if WIP grows and the team's throughput does not grow with it, then **Cycle Time has to grow.** Throughput almost never grows linearly — a team cannot handle twice as many tasks at once, twice as fast. More tasks "in progress at the same time" mathematically means each individual task waits longer on average. It does not mean the work gets done faster.

### The cost of context switching

The second reason WIP limits work is separate from the formula: switching between tasks has a real cognitive cost, and the effect is well documented. A developer holding the context of five tasks spends time and energy reloading context at every switch. That time adds no value to any of the five tasks. Limiting WIP means fewer tasks at a time, which cuts these hidden costs.

### WIP limits as a bottleneck-finding tool

The "In Review" column below has a limit of 3, and it already holds three cards. Developers cannot start a new task until someone reviews a card and moves it out of "In Review". That pushes the team to switch to reviewing code instead of starting new work. The WIP limit redirects effort to wherever the real bottleneck is, instead of letting people pile up unfinished work.

```txt
In Progress   │ In Review (limit 3) │ Done
──────────────┼─────────────────────┼──────────
[A] [B]       │ [C] [D] [E]  ← full │ [F]
              │                     │
no new card can enter In Review until one leaves it
```

### Scenario: a WIP-limit conversation with a product manager

*Situation:* the "In Progress" column has a WIP limit of 4, and all four slots are full. A product manager (PM) shows up with an "urgent" ticket and asks the team to start it right away.

> **PM:** This is blocking a client, we need to start on it now.
>
> **Tech lead:** I understand it is urgent. We already have four tasks in progress, and our limit is four. A fifth task on top of the limit does not make any of the five finish sooner. They just wait on each other longer.

> **Tech lead:** So there are two options. Either we decide together which of the current four to pause and swap for yours. Or someone finishes one of the current tasks as top priority, which frees a slot. Which matters more — this new task, or one of the ones already in progress?

This shows the key point: a WIP limit is not a bureaucratic obstacle. It is an honest conversation about the team's real capacity. The alternative — quietly adding a fifth task "on top" — does not increase capacity. It just hides the overload until it shows up later as longer delays across all five tasks at once.

## Flow metrics

| Metric | What it measures | Who cares most |
|---|---|---|
| Cycle Time | From the moment work actually starts to the moment it is done. | The team, judging its own speed. |
| Lead Time | From the moment the request arrives to the moment it is done. | The customer, waiting for the result. |
| Throughput | How many items finish in a fixed period. | Both, for forecasting. |

### Cycle Time

The time from when work on an item *actually starts*, for example when a card moves into "In Progress", until it finishes in "Done". This is an internal, team-facing metric: it measures how fast the team finishes work once it has started.

### Lead Time

The time from when a request *arrives* — a card is created or enters the Backlog — until it finishes. Lead Time includes all the waiting time *before* work starts, plus the Cycle Time itself. This is a customer-facing metric. It answers "how long from my request to the result", not "how much time the team actually spent working on it".

```txt
Request created         Work starts               Work finishes
      │                        │                          │
      │◄──────── Lead Time ────────────────────────────►│
      │                        │◄──── Cycle Time ───────►│
      │◄── waiting time ──────►│
```

### Throughput

The number of work items finished in a fixed period, for example 8 items per week. Velocity in Scrum is measured in story points and depends on the team's own estimates. Throughput is measured in actual completed items, which makes it a more direct metric, and harder to manipulate.

All three metrics are connected through Little's Law: if you know any two, you can calculate the third.

Throughput and cycle time, collected over time, let a team build a probability-based forecast. An example: "there is an 85% chance this task finishes in 6 days or less". No story-point estimates are needed for it. This is the basis of an approach called **probabilistic forecasting**.

## The Cumulative Flow Diagram (CFD) — how to read it and find the bottleneck

A CFD is a stacked area chart. Time runs along the X axis. The Y axis shows the total number of cards that have ever entered each stage of the workflow. Each stage is its own band on the chart.

```txt
Number
of cards
    │                                    ╱── Done (cumulative)
    │                              ╱────╱
    │                        ╱────╱  ╱── In Review (cumulative)
    │                  ╱────╱  ╱────╱
    │            ╱────╱  ╱────╱    ╱── In Progress (cumulative)
    │      ╱────╱  ╱────╱  ╱──────╱
    │╱────╱  ╱────╱  ╱────╱
    └──────────────────────────────────────► Time
```

How to read this kind of chart:

- **The vertical distance** between two neighboring lines at a given moment equals the number of cards in that stage right then. That is the stage's WIP. A band that keeps getting wider — "In Review", say — is a direct visual signal. Code review is becoming a bottleneck: work enters that stage faster than it leaves it.
- **The horizontal distance** between where a stage starts and where it ends, for the same card, roughly equals that stage's cycle time.
- **The slope** of a line shows throughput. If the "Done" line flattens out, the team's throughput is dropping.
- **A flat section** at the top of a line signals a stall. For example, "Done" does not grow for several days: nothing is finishing, even though work may still be coming in from below.

A diagnostic example: the band between "In Progress" and "In Review" stays narrow, while the band between "In Review" and "Done" keeps widening. The bottleneck is not development, it is code review. The right management action is not "hire more developers". It is "figure out why review cannot keep up": too few reviewers, oversized pull requests, review that is not a team priority.

## Evolutionary change (Kanban) vs fixed-length iterations (Scrum)

This is not a matter of taste. It is a real, structural difference in how process change happens.

| | Scrum | Kanban |
|---|---|---|
| How it is adopted | The whole package at once: roles, artifacts, five events. | Start with what you do now, then change it gradually. |
| When priorities can change | Mostly at sprint boundaries. | At any moment. |
| What drives a change | The cadence of the sprint. | Data about the flow. |

**Scrum** requires a "revolutionary" adoption: the team takes on a whole package at once, a set of roles, artifacts and five events. Priority changes mostly happen at sprint boundaries. The Sprint Backlog is locked for the length of the sprint, and should not change in a way that threatens the Sprint Goal.

The fixed rhythm (cadence) is useful for coordinating with stakeholders: "every two weeks, a new release or demo". The cost is a delay between a new priority appearing and the team being able to respond to it.

**Kanban** is built on the principle "start with what you do now". The method does not replace your existing process, roles or events. It sits on top of them and changes them gradually, based on flow data. Work flows continuously, and priorities can change at any moment: there is no artificial "sprint boundary" to protect.

This is a real trade-off, not just "Kanban is a more flexible Scrum". Continuous flow fits work that is naturally unpredictable: support, operations, incidents. There, "lock the plan for two weeks" does not match reality. It fits less well where a predictable sync point with stakeholders has value. Article 04 compares the two on concrete scenarios.

```txt
Kanban Cadences — optional, not required by the method
├── Replenishment meeting   (refill the backlog)
├── Delivery planning       (plan the next delivery)
├── Service delivery review (how well the service performs)
└── Risk review             (what threatens the flow)
```

Kanban also has optional rhythmic meetings, the **Kanban Cadences** above. Unlike Scrum's events, none of them are mandatory. How often they happen is set by the team's real needs, not fixed by the framework.

## Common interview traps

- **"Kanban has no process and no discipline"** — false. Kanban actually demands a lot of discipline. Respect the WIP limits honestly, and do not go over them "just this once". Track flow metrics constantly, and read the CFD regularly. Having no fixed roles or ceremonies is not the same thing as having no discipline.

- **"A WIP limit is just a number on the board for tidiness"** — WIP limits come from Little's Law. Growing WIP without growing throughput mathematically stretches out cycle time. This is a quantitative argument, not an aesthetic one.

- **"Cycle Time and Lead Time are the same thing"** — Lead Time runs from the request to completion, which matters to the customer. Cycle Time runs from the moment work actually starts to completion, which matters to the team judging its own speed. Lead Time is always ≥ Cycle Time, because it includes the waiting time before work starts.

- **"Kanban is just Scrum without sprints"** — this oversimplification hides the main difference. Scrum is iterative and "revolutionary" about change: you adopt a whole framework at once. Kanban is flow-based and evolutionary: you gradually change your existing process. That is a different answer to the question "how should process change happen on a team".

- **"Higher throughput always means the team is doing better"** — throughput on its own, without WIP and cycle time, can mislead. A team can close many small, trivial tasks and show high throughput, while large, valuable tasks sit in the queue for months. All three metrics — WIP, cycle time, throughput — need to be read together, not one at a time.
