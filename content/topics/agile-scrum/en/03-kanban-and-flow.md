# Kanban and Flow

## Where Kanban comes from

Kanban (Japanese 看板, meaning "signboard" or "signal card") comes from the Toyota Production System, Toyota's manufacturing system from the 1940s and 50s. Toyota used signal cards to control the flow of parts on the assembly line: the next stage of production would pull parts from the previous stage only when it actually had the capacity to work on them — not whenever the previous stage happened to produce them. David Anderson brought this idea into software development in the mid-2000s (his key book is *Kanban: Successful Evolutionary Change for Your Technology Business*, 2010), adapting the manufacturing flow principles for software teams.

Unlike Scrum, Kanban is not a framework with a fixed set of roles and required rituals. It is a method for managing the flow of work, and you can apply it on top of almost any existing process.

## Visualizing work

The first and most recognizable part of Kanban is the board, where columns represent stages of the workflow (for example: Backlog → In Progress → In Review → Done), and cards represent units of work. This is not just a nice way to display things. The point is to make invisible work — discussions, waiting for review, blockers — visible to the whole team at the same time.

```txt
Backlog     │  To Do    │  In Progress │  In Review │  Done
────────────┼───────────┼──────────────┼────────────┼─────────
[item]       │  [item]   │  [item] [item]│  [item]    │ [item]
[item]       │  [item]   │              │            │ [item]
[item]       │           │              │            │
```

Visualizing work does not solve problems on its own — it exposes them. A team that keeps the board honest quickly notices things they couldn't see before, like the fact that the "In Review" column is always full, even though before this, each developer only knew about their own tasks.

## Pull vs Push — the core difference

A **push system** moves work forward to the next stage no matter whether that stage actually has the capacity to take it. A classic example: a manager assigns tasks to developers at the start of the week according to a plan, without checking how many tasks each developer already has in progress. Or: an analyst finishes a spec and "hands it over" to development, without checking whether the dev team is ready to start on it.

A **pull system** works the other way: the next stage requests (pulls) new work only when it has free capacity. A developer picks up a new task from "To Do" only after finishing the previous one — or after a slot physically opens up, limited by a WIP limit (see below).

The difference looks small, but the consequences are very different. Push creates hidden queues: work piles up in front of a bottleneck, but nobody notices, because each stage reports "I passed the task along" — what happens to it after that isn't tracked by whoever passed it. Pull makes the bottleneck visible right away: if the next stage can't take the work, it simply stays where it is, and that's visible on the board.

## WIP limits — not a board hygiene rule, but a queueing-theory argument

The most common mistake about WIP limits (Work In Progress limits — limits on how many tasks can be in progress at the same time) is thinking they're just an arbitrary rule for keeping the board tidy ("don't take more than three tasks into this column so it doesn't look messy"). In fact, there is real math behind WIP limits.

### Little's Law

This is a formula from queueing theory. It applies to any stable system where things enter and leave:

```txt
WIP = Throughput × Cycle Time

which means:

Cycle Time = WIP / Throughput
```

Here, **WIP** is the number of work items currently in the system, **Throughput** is how many items finish per unit of time, and **Cycle Time** is how long it takes one item to move through the system.

The practical result of this formula: if WIP grows but the team's throughput does not grow along with it (and it almost never grows linearly — a team cannot handle twice as many tasks at once, twice as fast), then **Cycle Time has to grow.** More tasks "in progress at the same time" mathematically means each individual task waits longer on average. It does not mean the work gets done faster.

### The cost of context switching

There's a second reason WIP limits work, and it's not just a result of the formula — it's a separate, well-documented effect: switching between tasks has a real cognitive cost. A developer holding the context of five tasks at once spends time and mental energy "reloading" context every time they switch. That time doesn't add value to any of the five tasks. Limiting WIP forces the team to focus on fewer tasks at a time, which cuts down these hidden costs.

### WIP limits as a bottleneck-finding tool

Here's the practical mechanism: if the "In Review" column has a limit of 3, and it already has three cards, developers physically cannot start a new task until someone finishes reviewing a card and moves it out of "In Review." This pushes the team to switch to reviewing code instead of starting new work — the WIP limit naturally redirects effort to wherever the real bottleneck is, instead of letting people pile up more unfinished work.

### Scenario: a WIP-limit conversation with a product manager

*Situation:* the "In Progress" column has a WIP limit of 4, and all four slots are full. A PM shows up with an "urgent" ticket and asks the team to start it right away.

> **PM:** This is blocking a client, we need to start on it now.
> **Tech lead:** I understand it's urgent. We already have four tasks in progress, and our limit is four. If we add a fifth on top of the limit, none of the five actually gets faster — they just wait on each other longer. Here's what we can do: either we decide together which of the current four tasks should be paused and swapped for yours, or someone finishes one of the current tasks as top priority, and that frees up a slot. Which matters more — this new task, or one of the ones already in progress?

This shows the key point: a WIP limit is not a bureaucratic obstacle. It's an honest conversation about the team's real capacity. The alternative — quietly adding a fifth task "on top" — does not increase the team's capacity. It just hides the overload until it shows up later as longer delays across all five tasks at once.

## Flow metrics

### Cycle Time

The time from when work on an item *actually starts* (for example, when a card moves into "In Progress") until it finishes ("Done"). This is an internal, team-facing metric — it measures how fast the team finishes work once it has started.

### Lead Time

The time from when a request *arrives* (a card is created or enters the Backlog) until it finishes. Lead Time includes all the waiting time *before* work actually starts, plus the Cycle Time itself. This is a customer-facing metric — it answers "how long from the moment I asked for this, to the moment I get it," not "how much time did the team actually spend working on it."

```txt
Request created         Work starts               Work finishes
      │                        │                          │
      │◄──────── Lead Time ────────────────────────────►│
      │                        │◄──── Cycle Time ───────►│
      │◄── waiting time ──────►│
```

### Throughput

The number of work items finished in a fixed period (for example, 8 items per week). Unlike velocity in Scrum, which is measured in story points and depends on the team's own estimates, throughput is measured in actual completed items — this makes it a more direct metric, and harder to manipulate.

All three metrics are connected through Little's Law: if you know any two, you can calculate the third. The practical value is this: throughput and cycle time, collected over time, let a team build a probability-based forecast ("there's an 85% chance this task finishes in 6 days or less") without needing story-point estimates at all. This is the basis of an approach called **probabilistic forecasting**.

## The Cumulative Flow Diagram (CFD) — how to read it and find the bottleneck

A CFD is a stacked area chart. Time runs along the X axis, and the Y axis shows the total number of cards that have ever entered each stage of the workflow. Each stage is its own band on the chart.

```txt
Number
of cards
    │                                    ┌── Done (cumulative)
    │                              ┌─────┘
    │                        ┌─────┘  ┌── In Review (cumulative)
    │                  ┌─────┘  ╱─────┘
    │            ┌─────┘  ╱────┘        ┌── In Progress (cumulative)
    │      ┌─────┘  ╱────┘  ╱───────────┘
    │┌─────┘  ╱─────┘──────┘
    └──────────────────────────────────────────► Time
```

How to read this kind of chart:

- **The vertical distance** between two neighboring lines at a given moment in time equals the number of cards in that stage at that moment (that stage's WIP). If the "In Review" band keeps getting wider over time, that's a direct visual signal that code review is becoming a bottleneck: work enters that stage faster than it leaves it.
- **The horizontal distance** between the line where a stage starts and the line where it ends, for the same card, roughly equals the cycle time for that stage.
- **The slope** of a line shows throughput: if the "Done" line flattens out (grows more slowly), the team's throughput is dropping.
- **A flat section** at the top of a line (for example, "Done" doesn't grow for several days) signals a stall — nothing is finishing, even though work may still be coming in from below.

A diagnostic example: if the band between "In Progress" and "In Review" stays narrow, but the band between "In Review" and "Done" keeps widening, the bottleneck is not development — it's code review. The right management action isn't "hire more developers." It's "figure out why review can't keep up" (not enough reviewers, PRs are too large, review isn't a team priority).

## Evolutionary change (Kanban) vs fixed-length iterations (Scrum) — a real structural difference

This is not a matter of taste. It's a real, structural difference in how process change happens.

**Scrum** requires a "revolutionary" adoption: the team takes on a whole package at once — a set of roles, artifacts, and five events. Priority changes mostly happen at sprint boundaries — the Sprint Backlog is locked for the length of the sprint and shouldn't change in a way that threatens the Sprint Goal. This gives a predictable rhythm (cadence), which is useful for coordinating with stakeholders ("every two weeks, a new release or demo"), but it creates a delay between a new priority showing up and the team being able to respond to it.

**Kanban** is explicitly built on the principle "start with what you do now." The method doesn't ask you to replace your existing process, roles, or events. It sits on top of them and changes them gradually, based on flow data. Work flows continuously, with no fixed iterations. Priorities can change at any moment, because there's no artificial "sprint boundary" that needs protecting.

This creates a real trade-off, not just "Kanban is a more flexible Scrum." Continuous flow with no fixed iterations fits well where incoming work is naturally unpredictable — support, operations, incident response. There, the whole idea of "lock the plan for two weeks" doesn't match reality. But continuous flow fits less well where a predictable sync point with stakeholders has real value. Article 04 covers this fit-for-purpose comparison in detail with concrete scenarios.

One more important detail: Kanban also has optional rhythmic meetings, called **Kanban Cadences** (a replenishment meeting for the backlog, delivery planning, a service delivery review, a risk review). But unlike Scrum's events, none of these are mandatory, and how often they happen is set by the team's real needs — not fixed by the framework.

## Common interview traps

- **"Kanban has no process and no discipline"** — false. Kanban actually demands a lot of discipline: honestly respecting WIP limits (not going over "just this once"), constantly tracking flow metrics, regularly reading the CFD. Having no fixed roles or ceremonies is not the same thing as having no discipline.

- **"A WIP limit is just a number on the board for tidiness"** — WIP limits come from Little's Law: growing WIP without growing throughput mathematically stretches out cycle time. This is a quantitative argument, not an aesthetic one.

- **"Cycle Time and Lead Time are the same thing"** — Lead Time is measured from the moment of the request to completion (matters to the customer). Cycle Time is measured from when work actually starts to completion (matters to the team, for judging its own speed). Lead Time is always ≥ Cycle Time, because it includes the waiting time before work starts.

- **"Kanban is just Scrum without sprints"** — this oversimplification hides the main difference: Scrum is iterative and "revolutionary" in how it handles change (you adopt a whole framework at once). Kanban is flow-based and evolutionary (you gradually change your existing process). This is not a cosmetic difference — it's a different answer to the question "how should process change even happen on a team."

- **"Higher throughput always means the team is doing better"** — throughput on its own, without looking at WIP and cycle time, can be misleading. A team can close a lot of small, trivial tasks and show high throughput, while large, valuable tasks sit stuck in the queue for months. All three metrics — WIP, cycle time, throughput — need to be read together, not one at a time.
