# Agile Fundamentals

## The problem that Agile was trying to solve

Agile is an answer to one specific problem: in **waterfall**, feedback from reality arrives too late to act on. Waterfall is a development model where a project moves through strict, sequential phases. Each phase must finish completely before the next one starts, and there is no formal way to go back a step. The name comes from that image: water flows down, never up.

Here is a historical detail that often comes up in interviews. Waterfall was not invented as the "correct" way to build software that later got broken. Winston Royce's 1970 paper is usually credited as the source of waterfall. That paper actually described the strict sequential process as risky, and recommended iterative changes to it.

The industry took only the diagram of phases from that paper. For the next 25 years, teams built their processes around a strict, sequential reading of it.

By the late 1990s, industry data showed a very low share of software projects finishing on time, within budget, and with the promised features. The best-known source is CHAOS (the name of a report series the Standish Group has published since 1994). There were three systemic reasons behind those numbers, and all three come directly from waterfall's structure.

### Three failure patterns in waterfall

```txt
requirements → design → build → test → release
                                             │
                                             ▼
                                    the first real feedback
                                    from reality, 9 to 18
                                    months into the project
```

**Late feedback.** Requirements get fixed at the start and signed off by the customer. The customer sees working software only at the very end, often 9 to 18 months later. Teams almost always misread what the business needs at that stage: people describe requirements poorly before they see a working prototype. The mistake then surfaces where it is most expensive to fix:

- The code is already written.
- The architecture is built around the wrong model.
- The tests check the wrong behavior.

**Requirements drift.** Real business needs do not stay still for 12 to 18 months. The market changes, competitors appear, and management priorities shift. Waterfall has no built-in way to absorb that — only a "change control" procedure, which is slow and adversarial by design.

A change to a requirement looks like breaking a signed contract, not a normal part of the work. The team is then left with two bad options:

- Ignore the changed reality and deliver something nobody needs anymore.
- Drown in endless approval cycles for change requests.

**Big-bang integration.** Different modules are usually built by different sub-teams in parallel, over months. They are put together for the first time only during integration testing, near the end of the project. Integration becomes a last-minute crisis, right when the time budget for fixes is already gone. Interfaces that looked consistent on paper turn out not to match:

- Different assumptions about data formats.
- Different assumptions about call order.
- Different error handling.

| Failure pattern | What waterfall delays | What it costs |
|---|---|---|
| Late feedback | The customer sees working software only at the end. | Rework of code, architecture and tests. |
| Requirements drift | Change goes through a slow approval procedure. | The product no longer matches the market. |
| Big-bang integration | Modules meet for the first time near the end. | A crisis with no time budget left. |

All three patterns share one thing: **feedback from reality is delayed until the point where fixing a mistake costs the most.** Agile is not a set of rituals. It is a direct answer to this problem: make feedback loops shorter, so mistakes get caught while they are still cheap.

## The Agile Manifesto — the real text

In February 2001, seventeen developers met in Snowbird, Utah. Among them were the creators of Scrum, Extreme Programming (XP), DSDM (Dynamic Systems Development Method) and other lightweight methods. They wrote down the shared ideas behind their different practices. The result is the **Manifesto for Agile Software Development**: four values and twelve principles.

The Manifesto does not say "do daily standups" or "use two-week sprints" anywhere. It does not mention Scrum at all. It describes *values and priorities*. Specific frameworks such as Scrum, Kanban and Extreme Programming are different ways to *put these values into practice* — they are not the Manifesto itself.

### The four values

> We are uncovering better ways of developing software by doing it and helping others do it. Through this work we have come to value:

| We value more | over |
|---|---|
| **Individuals and interactions** | processes and tools |
| **Working software** | comprehensive documentation |
| **Customer collaboration** | contract negotiation |
| **Responding to change** | following a plan |

One more line closes the Manifesto: *while there is value in the items on the right, we value the items on the left more*. It is the most overlooked line, and the source of a common interview mistake (see below). The Manifesto does **not** call documentation, process, contracts and plans useless. It says that when they conflict with people, working software, collaboration or adaptability, the second group wins.

### The twelve principles

The four values are abstract. The twelve principles turn them into something concrete. Each one is worth understanding, not just memorizing:

1. **Our highest priority is to satisfy the customer through early and continuous delivery of valuable software.** Not "deliver on the plan's schedule" — deliver real value, early and often, instead of one big release at the end.
2. **Welcome changing requirements, even late in development.** This is the opposite of change control in waterfall. A changed requirement is not a problem — it's a normal part of the work, and it can give the customer an advantage.
3. **Deliver working software frequently, from a couple of weeks to a couple of months, with a preference for the shorter timescale.** This is the direct mechanism for shortening the feedback loop described above.
4. **Business people and developers must work together daily throughout the project.** Not "sign the requirements doc and meet again at final acceptance" — an ongoing conversation.
5. **Build projects around motivated individuals. Give them the environment and support they need, and trust them to get the job done.** A clear rejection of micromanagement as a management style.
6. **The most efficient way to share information within a team is a face-to-face conversation.** Not "everything must live in Jira" — a live conversation is faster and more accurate than written documentation for many kinds of information.
7. **Working software is the primary measure of progress.** Not percent-complete on a plan, not lines of code written, not the number of closed tickets — does the product actually work?
8. **Agile processes promote sustainable development. Sponsors, developers, and users should be able to keep a constant pace forever.** A direct answer to "crunch sprints" and overtime as a normal way of working.
9. **Continuous attention to technical excellence and good design improves agility.** Technical debt is not something you can fix later. It directly reduces the team's ability to respond to change, which undermines the whole point of being agile.
10. **Simplicity — the art of maximizing the amount of work not done — is essential.** Do not build things that might be needed in the future. Build what is needed now.
11. **The best architectures, requirements, and designs come from self-organizing teams.** Decisions are made by the team doing the work, not handed down from management.
12. **At regular intervals, the team reflects on how to become more effective, then adjusts its behavior.** This is the principle behind the retrospective. Notice that it demands *real* behavior change, not just holding a meeting.

## "Being Agile" vs "Doing Agile ceremonies"

**Being Agile** means actually working according to the values and principles above:

- Short feedback loops with real users.
- Willingness to change the plan when reality changes.
- A team that decides how to do its own work.
- Reflection that actually changes behavior.

**Doing Agile ceremonies** means performing the outer shape of a framework, usually Scrum. That shape is two-week sprints, a daily standup, a retro at the end of the sprint, and a To Do / In Progress / Done board. What those rituals were built to achieve is missing. This distinction is the most common interview trap at senior/lead level, and here is what it looks like in practice:

| Ceremony | Working (Agile) | Theater (cargo cult) |
|---|---|---|
| Sprint Review | Real users or stakeholders watch the working increment. Their feedback changes the backlog. | A demo for a manager who already knows what is coming. Feedback changes nothing. |
| Retrospective | The team finds one or two concrete actions. They get done before the next retro. | The same complaints every sprint. Nobody tracks the action items. |
| Daily Standup | The team syncs and finds blockers. The day's plan changes when it needs to. | Each person reports status to the manager in turn. Nobody actually listens. |
| Sprint Planning | The sprint goal is really discussed and shaped by the team. | Management already decided what must be done. "Planning" is a formality. |

## Cargo Cult Agile and Zombie Scrum

The term **cargo cult** comes from anthropology. After the Second World War, on some Pacific islands, local people had seen Allied planes bring supplies to airstrips built for the war. Some of them then built their own "airstrips" and wooden "radio towers", copying what they had seen. They hoped the planes would come back with more supplies.

They copied the outer form exactly. They did not reproduce the function that actually brought the planes: the real logistics system behind it.

**Cargo Cult Agile** is the same idea applied to software teams. A team copies the visible parts of Scrum: sprints, standups, a board, a retro. What it does not copy is the mechanism those practices were built for — a short feedback loop with reality. The result looks like Agile in every artifact, and is not Agile at all in substance.

**Zombie Scrum** is a more specific term for this exact situation applied to Scrum, coined by Barry Overeem and co-authors. The team performs every formal Scrum event, but is dead inside.

| What Scrum promises | What Zombie Scrum delivers |
|---|---|
| Real inspection | The Sprint Review reveals nothing new. No real stakeholders attend. |
| Real adaptation | The retro finds the same problems sprint after sprint. Nothing changes. |
| Focus on user value | The team just closes tickets. |

On the outside, the team does everything the Scrum Guide says. In substance, the process gives none of the benefits Scrum was built to provide.

### A scenario: what this looks like from the inside

A team has worked in two-week sprints for six months. Here is what a sprint actually looks like there:

- Every morning, a 15-minute standup where each person reports status to the tech lead, one by one.
- Every second Friday, a 30-minute retro that turns into complaints about the slow CI (continuous integration) pipeline — the same list as three months ago.
- A Sprint Review where a developer shows their screen to the product owner. Real users of the product have never attended.
- Requirements written by a product manager the day before planning, and sent over as a list of tickets.
- Planning where the team mostly clarifies implementation details, not whether the work is worth doing.

On paper, this is Scrum: all five events happen, roles exist, there is a backlog. In substance, it is waterfall cut into two-week pieces. Requirements come from above, there is no feedback loop with real users, and the retro produces no change. This is Zombie Scrum.

What would a working Agile process look like in the same situation?

- A real user representative attends the Sprint Review, or at least someone who works closely with users. Their feedback actually reorders the backlog for the next sprint.
- In the retro, the team picks exactly one change. Someone takes ownership of making it happen, and the next retro checks whether it worked.
- Sprint Planning starts with a discussion of the goal ("why are we doing this"), not with a list of ready-made tickets.

## Common interview traps

- **"Agile is a methodology"** — no. Agile is a set of values and principles (the Manifesto). Scrum, Kanban, Extreme Programming and DSDM are specific frameworks that put these values into practice in different ways. Saying "we use Agile" means nothing without saying which framework, and how.

- **"Agile means no planning and no documentation"** — this misreads the Manifesto. The values are written as priorities ("working software *over* documentation"), not as a rejection ("documentation is useless"). Agile teams plan constantly, just in short cycles. They revise the plan as they go, instead of planning once at the start for the whole project.

- **"If we have standups and sprints, we are doing Agile"** — this is exactly the Cargo Cult Agile trap. Having the rituals says nothing about whether a real feedback loop exists. The right question is not "what meetings do you have", but "what actually changes as a result of those meetings".

- **"Agile guarantees faster development"** — Agile optimizes for adaptability and early feedback, not for raw speed. Early iterations can even be slower, because ceremonies and more frequent integration both take time. The payoff is that you avoid the expensive, late-stage rework that waterfall projects are known for.

- **"Waterfall is just planning, and Agile is the absence of planning"** — waterfall's real problem is not that it has structure. It is that its phases are irreversible, and feedback from reality only arrives once, at the very end. A well-run Agile process also plans, just in short cycles, and keeps revising the plan as new information arrives.
