# Scrum Framework

> Scrum is one way to put the Agile Manifesto's values into practice (see [01-agile-fundamentals](./01-agile-fundamentals.md)). It is not the Manifesto itself. This article covers one specific framework: the roles, the artifacts and the five events, as defined in the official Scrum Guide. It also covers what matters more in a senior/lead interview: how to tell working Scrum from a copy of it.

## Roles (Accountabilities)

The 2020 version of the Scrum Guide does not describe "roles". It describes **accountabilities** — areas of responsibility inside one single Scrum Team. Older versions had a separate "Development Team" with its own internal hierarchy. The current version removed that split. There is a Product Owner, a Scrum Master and Developers, and all three are equal parts of one team.

```txt
Scrum Team — one team, three accountabilities
├── Product Owner  → what gets built, and in what order
├── Scrum Master   → how the team uses Scrum
└── Developers     → how the increment gets built
```

### Product Owner (PO)

**Responsible for** maximizing the value of the product the team builds. That happens through the Product Backlog, the single source of requirements for the team's work. The PO sets the Product Goal, orders the backlog by value, and makes sure backlog items are clear to the team. **Not responsible for:**

- Managing the development team. The PO does not assign tasks and does not tell people *how* to do the work. The PO decides *what* matters and *in what order*.
- Being a "project manager" in the classic sense. The PO does not track deadlines and resources the way a traditional project manager (PM) does. This role is about product value, not project management.
- Being a passive channel for every stakeholder request. If the PO just writes down everything people ask for, without ranking it by value, that is a failure of the role itself. The PO has exactly one voice on backlog priority, even when many stakeholders ask for different things at once.

### Scrum Master (SM)

**Responsible for** making sure Scrum is used effectively, both inside the team and in the wider organization. In practice this works on three levels:

- Teaching and coaching the team on how to use Scrum.
- Facilitating events and removing impediments, the blockers in the team's way.
- Working with the organization outside the team. One example is removing a dependency on another department that blocks releases.

**Not responsible for:**

- Being the manager of the Developers. The SM has no formal authority over them. This is a servant-leadership role, not a position of hierarchy.
- Writing down status reports during the standup to send to management. If the SM runs the standup as a "who did what" report for management, that directly breaks the purpose of the event (see below).
- Deciding what goes into the backlog. That belongs to the PO, not the SM.

### Developers

**Responsible for** creating a useful Increment every Sprint. That covers planning the Sprint Backlog, following the Definition of Done, adjusting the plan at each Daily Scrum, and holding each other accountable as professionals. The team is cross-functional: it takes a backlog item from idea to a working increment without outside help at every step. **Not responsible for:**

- Backlog priority. That is the PO's job.
- "Facilitating themselves" in a vacuum. The SM supports the team in following Scrum practices, but the quality and amount of work delivered is on the Developers.

## Artifacts and their commitment

```txt
Product Backlog  →  commitment: Product Goal
Sprint Backlog   →  commitment: Sprint Goal
Increment        →  commitment: Definition of Done
```

Each of Scrum's three artifacts has a **commitment** — a specific promise that makes the artifact meaningful, and not just a list.

### Product Backlog

An ordered, constantly changing list of everything the product might need: features, bug fixes, technical debt, experiments. Owned by the PO. The backlog is never "finished" — it is a living document that reflects what the product needs today. The **Product Goal** is the long-term target the backlog serves: a concrete milestone the team moves toward through a series of sprints.

### Sprint Backlog

The Product Backlog Items (PBI) chosen at Sprint Planning for the current sprint, plus a plan for building them. Owned by the Developers: it is their plan, not the PO's. The **Sprint Goal** is one connected goal for the sprint. It gives meaning to the set of chosen tasks. The team can stay flexible about *how* it gets there, without losing focus on *what* it is trying to achieve.

### Increment

The sum of every Product Backlog Item finished during the sprint, plus all previous increments. In other words, a working, integrated piece of the product. An increment must be usable, ready to release, whether or not the PO chooses to release it right away. What counts as "finished" for an increment is set by the **Definition of Done**.

### Definition of Done (DoD) vs Definition of Ready (DoR)

| | Definition of Done (DoD) | Definition of Ready (DoR) |
|---|---|---|
| Question it answers | Is the result good enough to count as done? | Is this task clear enough to start? |
| What it is about | Output quality: what we deliver as the result. | Input readiness: what we agree to work on. |
| Official status | Part of the Scrum Guide, tied to the Increment. | Not in the Scrum Guide, but widely used. |

**Definition of Done** is a formal list of quality standards that any PBI must meet to count as part of the Increment. For example: the code has been reviewed, has test coverage, is merged into main, is deployed to staging, and the documentation is updated.

DoD is an official part of the Scrum Guide: it is the commitment tied to the Increment artifact. Without a clear answer to "when is this actually finished", progress becomes unclear, and a task can stay "90% done" forever.

**Definition of Ready** is **not** part of the official Scrum Guide, but it is a very common practice. It is the set of conditions a backlog item must meet before it can enter Sprint Planning:

- Clear acceptance criteria exist.
- An estimate is set.
- External dependencies are identified.
- The design is ready, where a design is needed.

DoR protects the team from pulling a half-formed task into a sprint, where three days in nobody is sure what they are actually building. A team can use DoD and DoR at the same time: they do not compete, they cover different ends of the process.

## The five Scrum Events

```txt
Sprint (1–4 weeks, usually 2)
├── Sprint Planning     (at the start of the sprint)
├── Daily Scrum         (every day, 15 minutes)
├── Backlog Refinement  (ongoing, about 5–10% of team time)
├── Sprint Review       (at the end of the sprint)
└── Sprint Retrospective (at the end, after the Review)
```

Every Scrum event is a fixed time window (a time-box) with a clear goal: inspection and adaptation. Below is the real purpose of each event, not just its name. Each one also gets the two shapes it takes in practice. One column shows the event working; the other shows what it turns into when it fails.

### Sprint — the container event

The Sprint itself is the container event for everything else, and it has a fixed length: usually 1 to 4 weeks, most often 2. Inside a sprint, the Sprint Goal does not change. The amount of work may get clearer as the team learns more, but not in a way that puts the Sprint Goal at risk.

### Sprint Planning

**Real purpose:** answer three questions. *Why* is this sprint valuable — that answer becomes the Sprint Goal. *What* can be done — the team picks Product Backlog Items. *How* will the chosen work get done — the team breaks it into tasks. The time-box is usually up to 8 hours for a one-month sprint, and less for shorter sprints.

| When Sprint Planning works | When it turns into theater |
|---|---|
| The PO explains the value and context of the chosen items. The team discusses scope, and can push back or reshape tasks when it sees risk. The Sprint Goal is set together and makes sense. | The PO or management has already decided what must be done, and in what order. Developers listen to a list of tickets and give estimates under pressure. There is no real way to challenge the scope. |

### Daily Scrum (Daily Standup)

**Real purpose:** an event *for* the Developers, run *by* the Developers. They inspect progress toward the Sprint Goal and adjust the Sprint Backlog for the next 24 hours. This is not a status report to a manager. The "what I did / what I'll do / what's blocking me" format is one way to structure the event, not the point of it.

| When the Daily Scrum works | When it turns into theater |
|---|---|
| The team talks about what stands between it and the Sprint Goal. People sync on dependencies with each other. The team changes the day's plan when it needs to. | The standup becomes a round of status reports to a manager. Everyone talks for the record, and nobody listens. Blockers get pushed to "after the standup" and then forgotten. Take the manager out of the room and the standup stops meaning anything to the team. |

### Backlog Refinement (Grooming)

**Real purpose:** an ongoing activity during the sprint. The team adds detail, estimates and order to Product Backlog Items, so they meet the Definition of Ready before a future Sprint Planning.

Refinement is not one of the five time-boxed events in the 2020 Scrum Guide. It is still almost always present as a recommended activity. The Scrum Guide describes it as an ongoing process, usually around 5–10% of the team's capacity. Capacity here means the hours the team can actually give to sprint work.

| When refinement works | When it turns into theater |
|---|---|
| The team and the PO go through upcoming tasks ahead of time. Unclear points are found before a task ever enters a sprint. Estimates reflect a real understanding of the scope. | Refinement gets skipped, or the PO reads out a ticket list with no discussion. The team assigns story points — its own relative measure of size — without understanding the details. The unclear parts then surface mid-sprint. |

### Sprint Review

**Real purpose:** inspect the increment and adapt the Product Backlog, based on what was learned. This is a working session with real stakeholders, not just a formal demo. The team discusses what got done, what did not, and what that means for future planning.

| When the Sprint Review works | When it turns into theater |
|---|---|
| Real users or stakeholders attend, and their opinion actually matters. The team shows a working increment, not mockups or slides. That feedback changes priorities in the Product Backlog. | The "demo" is shown to one person, usually a manager. That person already knows what is coming. Real stakeholders are missing, or attend only as a formality. Feedback, when it happens at all, changes nothing. This is the classic Zombie Scrum example from article 01. |

### Sprint Retrospective

**Real purpose:** inspect how the sprint went, from the point of view of people, relationships, process and tools. Then plan ways to become more effective. This is the only one of the five events fully focused on the team's own way of working, rather than on the product itself.

| When the retro works | When it turns into theater |
|---|---|
| The team openly discusses what got in the way. It finds one or two concrete, doable actions for the next sprint. Someone takes ownership of making them happen, and the next retro checks whether they worked. | The retro becomes a ritual complaint session. The same problems come up sprint after sprint: slow CI (continuous integration), requirements that arrive too late. The agreed action items are either not written down or forgotten right away. |

Look back at six months of retro action items and count how many repeat. A high number is a direct sign that the Manifesto's 12th principle (see [01-agile-fundamentals](./01-agile-fundamentals.md)) is not being followed.

## Putting it together: how decay spreads across the team

One decayed event rarely stays isolated. It usually drags the others down with it, and the chain runs like this:

1. The Sprint Review is a formal demo with no real feedback.
2. So the Product Backlog is not adapted to real user experience.
3. So Sprint Planning keeps picking tasks whose value nobody has checked.
4. So the Daily Scrum turns into reporting on a plan handed down from above. There is nothing to adapt to, because no new information arrives.
5. So the Retrospective cannot offer useful changes. The root cause — no real connection to users — is never discussed directly. It gets disguised as operational complaints, such as "our CI is slow".

The practical takeaway for a senior/lead: if something is not working, start diagnosing at the Sprint Review. That is usually where the connection to reality is lost, and that connection is supposed to feed everything else.

## Common interview traps

- **"The Scrum Master is the team's manager"** — no, this is a servant-leadership role with no formal authority over the Developers. The confusion often comes from companies that merge the SM role with a tech lead or manager position. That is one company's organizational choice, not part of the Scrum Guide.

- **"The Product Owner decides how the work gets done"** — no, the PO decides *what* has value and *in what order*. *How* to build it is the Developers' decision. A PO who writes out technical implementation details is stepping outside the boundaries of the role.

- **"The Daily Scrum is a status report for the manager"** — the event belongs to the Developers, so they can adapt their own plan. It is not there to report upward. If a manager requires attendance specifically to get a status update, the event has already lost its purpose.

- **"Definition of Done and Definition of Ready are the same thing"** — DoD describes the quality standards for a finished result. It is officially part of the Scrum Guide, tied to the Increment commitment. DoR describes whether a task is ready to be picked up in the first place. It is unofficial, but very widely used. They apply to different points in the process.

- **"Backlog Refinement is the same as Sprint Planning"** — refinement is an ongoing prep activity during the sprint. It makes future items clear and estimated ahead of time. Sprint Planning is a one-time event at the start of the sprint. It picks a specific amount of work from an already refined backlog. Good refinement makes Sprint Planning fast and predictable; without it, Planning turns into an improvised discussion of unclear tasks.
