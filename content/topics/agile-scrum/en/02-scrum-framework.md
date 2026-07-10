# Scrum Framework

> Scrum is one way to put the Agile Manifesto's values into practice (see [01-agile-fundamentals](./01-agile-fundamentals.md)). It is not the Manifesto itself. This article covers a specific framework: the roles, artifacts, and five events, as defined in the official Scrum Guide — and, more importantly for a senior/lead-level interview, how to tell working Scrum from a copy of it.

## Roles (Accountabilities)

The 2020 version of the Scrum Guide does not describe "roles." It describes **accountabilities** — areas of responsibility inside one single Scrum Team. Older versions of the guide had a separate "Development Team" with its own internal hierarchy. The current version removed that split: there is a Product Owner, a Scrum Master, and Developers, and all three are equal parts of one team.

### Product Owner (PO)

**Responsible for:** maximizing the value of the product the team builds. This happens through managing the Product Backlog — the single source of requirements for the team's work: setting the Product Goal, ordering the backlog by value, and making sure backlog items are clear and understandable to the team.

**NOT responsible for:**
- Managing the development team — the PO does not assign tasks and does not tell people *how* to do the work. The PO decides *what* matters and *in what order*.
- Being a "project manager" in the classic sense — the PO does not track deadlines and resources the way a traditional PM does. This role is about product value, not project management.
- Being a passive channel for every stakeholder request — if the PO just writes down everything people ask for, without ranking it by value, that is a failure of the role itself. The PO has exactly one voice on backlog priority, even when many stakeholders ask for different things at the same time.

### Scrum Master (SM)

**Responsible for:** making sure Scrum is used effectively, both inside the team and in the wider organization. In practice, this works on three levels: (1) teaching and coaching the team on how to use Scrum, (2) facilitating events and removing impediments (blockers) in the team's way, (3) working with the organization outside the team — removing outside barriers that slow the team down (for example, a dependency on another department that blocks releases).

**NOT responsible for:**
- Being the manager of the Developers — the SM has no formal authority over them. This is a servant-leadership role, not a position of hierarchy.
- Writing down status reports during the standup to send to management — if the SM runs the standup as a "who did what" report meant for management, that directly breaks the purpose of the event (see below).
- Deciding what goes into the backlog — that belongs to the PO, not the SM.

### Developers

**Responsible for:** creating a useful Increment every Sprint. This includes planning the Sprint Backlog (Sprint Planning), keeping quality by following the Definition of Done, adjusting the plan every day (Daily Scrum), and holding each other accountable as professionals. The team is cross-functional — it has enough skills inside it to take a backlog item from idea to a working increment without needing outside people at every step.

**NOT responsible for:** setting backlog priority (that's the PO's job) and "facilitating themselves" in a vacuum — the SM supports the team in following Scrum practices, but the quality and amount of work delivered is on the Developers.

## Artifacts and their commitment

Each of Scrum's three artifacts has a "commitment" — a specific promise that makes the artifact meaningful, not just a list:

```txt
Product Backlog  →  commitment: Product Goal
Sprint Backlog   →  commitment: Sprint Goal
Increment        →  commitment: Definition of Done
```

### Product Backlog

An ordered, constantly changing list of everything the product might need: features, bug fixes, technical debt, experiments. Owned by the PO. The backlog is never "finished" — it's a living document that reflects the team's current understanding of what the product needs. The **Product Goal** is the long-term target the backlog serves — a concrete milestone the team is moving toward through a series of sprints.

### Sprint Backlog

The set of Product Backlog Items (PBIs) chosen at Sprint Planning for the current sprint, plus a plan for building them. Owned by the Developers (it's their plan, not the PO's). The **Sprint Goal** is one connected goal for the sprint. It gives meaning to the set of chosen tasks and lets the team stay flexible about *how* they get there, without losing focus on *what* they're trying to achieve.

### Increment

The sum of every Product Backlog Item finished during the sprint, plus all previous increments — in other words, a working, integrated piece of the product. An increment must be usable (ready to release), regardless of whether the PO actually chooses to release it right away. What counts as "finished" for an increment is set by the **Definition of Done**.

### Definition of Done (DoD) vs Definition of Ready (DoR)

These are two different ideas, and people often mix them up.

**Definition of Done** is a formal, official list of quality standards that any PBI must meet to count as part of the Increment. Example: code has been reviewed, has test coverage, is merged into main, is deployed to staging, and documentation is updated. DoD is an official part of the Scrum Guide (it's the commitment tied to the Increment artifact). Without a clear "when is this actually finished," progress becomes unclear — a task can stay "90% done" forever.

**Definition of Ready** is NOT part of the official Scrum Guide, but it's a very common practice: a set of conditions a backlog item must meet before it can even enter Sprint Planning. For example: clear acceptance criteria exist, an estimate is set, external dependencies are identified, and design (if needed) is ready. DoR protects the team from a situation where a half-formed task gets pulled into a sprint, and on day three nobody is sure what they're actually building.

The core difference: **DoD is about output quality** (what we deliver as the result), while **DoR is about input readiness** (what we agree to work on in the first place). A team can use both at the same time — they don't compete, they cover different ends of the process.

## The five Scrum Events

Every Scrum event is a fixed time window (a time-box) with a clear goal: inspection and adaptation. Below is the real purpose of each event, not just its name, and what it looks like when it's working, compared to what it turns into in practice when it fails.

```txt
Sprint (1–4 weeks, usually 2)
├── Sprint Planning     (at the start of the sprint)
├── Daily Scrum         (every day, 15 minutes)
├── Backlog Refinement  (ongoing during the sprint, ~5–10% of team time)
├── Sprint Review       (at the end of the sprint)
└── Sprint Retrospective (at the end, after the Review)
```

### Sprint — the container event

The Sprint itself is the container event for everything else, a fixed length (usually 1 to 4 weeks, most often 2). Inside a sprint, the Sprint Goal does not change. The amount of work may get clearer as the team learns more, but not in a way that puts the Sprint Goal at risk.

### Sprint Planning

**Real purpose:** answer three questions — *why* is this sprint valuable (set the Sprint Goal), *what* can be done (pick PBIs from the Product Backlog), and *how* will the chosen work get done (break it into tasks). Time-box is usually up to 8 hours for a one-month sprint, and less for shorter sprints.

**When it works:** the PO explains the value and context of the chosen items, the team actively discusses scope and can push back or reshape tasks when it sees risk, and the Sprint Goal is set together and actually makes sense.

**When it turns into theater:** the PO (or management) has already decided what must be done and in what order. "Planning" becomes the developers quietly listening to a list of tickets and giving estimates under pressure, without any real ability to challenge the scope.

### Daily Scrum (Daily Standup)

**Real purpose:** an event *for* the Developers, run *by* the Developers — inspecting progress toward the Sprint Goal and adjusting the Sprint Backlog for the next 24 hours. This is not a status report to a manager.

**When it works:** the team talks about what stands between them and the Sprint Goal, syncs on dependencies between each other, and changes the day's plan when needed. The "what I did / what I'll do / what's blocking me" format is just one way to structure this — it's not the point on its own.

**When it turns into theater:** the standup becomes a round of individual status reports to a tech lead or manager. Everyone talks "for the record," nobody listens to the next person, and blockers get pushed to "let's talk after standup" and then forgotten. The clearest sign of decay: if you remove the manager from the room, the standup stops meaning anything to the team.

### Backlog Refinement (Grooming)

**Real purpose:** an ongoing activity during the sprint — adding detail, estimates, and order to Product Backlog Items so they meet the Definition of Ready before future Sprint Plannings. It is not formally listed as one of the five time-boxed events in the 2020 Scrum Guide, but it's almost always present as a recommended activity (the Scrum Guide mentions refinement as an ongoing process, usually taking around 5–10% of the team's capacity).

**When it works:** the team and PO go through upcoming tasks ahead of time, find unclear points before the task ever enters a sprint, and estimates reflect real understanding of the scope.

**When it turns into theater:** refinement gets skipped, or it becomes the PO reading out a ticket list with no discussion, while the team mechanically assigns story points without really understanding the details — and then the unclear parts surface mid-sprint instead.

### Sprint Review

**Real purpose:** inspect the increment and adapt the Product Backlog based on what was learned. This is a working session with real stakeholders (not just a formal demo), where the team discusses what got done, what didn't, and what that means for future planning.

**When it works:** real users or stakeholders attend and their opinion actually matters; the team shows a working increment (not mockups or slides); the feedback that comes out of it actually changes priorities in the Product Backlog.

**When it turns into theater:** the "demo" is shown to one person (usually a manager) who already knows what's coming; real stakeholders are missing or attend only as a formality; feedback, even when it happens, changes nothing about future work. This is the classic Zombie Scrum example from article 01.

### Sprint Retrospective

**Real purpose:** inspect how the sprint went from the point of view of people, relationships, process, and tools — and plan ways to become more effective. This is the only one of the five events fully focused on the team's own way of working, rather than on the product itself.

**When it works:** the team openly discusses what got in the way, finds one or two concrete, doable actions for the next sprint, someone takes ownership of making them happen, and the next retro checks whether they worked.

**When it turns into theater:** the retro becomes a ritual complaint session — the same problems come up sprint after sprint ("CI is too slow," "requirements arrive too late"), but action items either aren't written down or get forgotten right away. If you look back at six months of retro action items and see the same few items repeating, that's a direct sign that the Manifesto's 12th principle (see article 01) isn't actually being followed.

## Putting it together: how decay spreads across the team

One decayed event rarely stays isolated — it usually drags the others down with it. If the Sprint Review is a formal demo with no real feedback, the Product Backlog doesn't get adapted based on real user experience → Sprint Planning keeps picking tasks whose value nobody has checked → the Daily Scrum turns into reporting on a plan handed down from above, instead of adapting to new information, because there's no real new information → the Retrospective can't offer useful changes, because the root cause (no real connection to users) never gets discussed directly — it just gets disguised as operational complaints ("our CI is slow").

The practical takeaway for a senior/lead: if something isn't working on a team, a good place to start diagnosing is the Sprint Review — that's usually where the connection to reality is lost, the connection that's supposed to feed everything else.

## Common interview traps

- **"The Scrum Master is the team's manager"** — no, this is a servant-leadership role with no formal authority over the Developers. The confusion often comes from the fact that some companies merge the SM role with a tech lead or manager position — but that's a specific company's organizational choice, not part of the Scrum Guide.

- **"The Product Owner decides how the work gets done"** — no, the PO decides *what* has value and *in what order*. *How* to build it is the Developers' decision. A PO who writes out technical implementation details is stepping outside the boundaries of the role.

- **"The Daily Scrum is a status report for the manager"** — the event belongs to the Developers and exists so they can adapt their own plan, not to report upward. If a manager requires attendance at the standup specifically to get a status update, the event has already lost its real purpose.

- **"Definition of Done and Definition of Ready are the same thing"** — DoD describes the quality standards for a finished result (it's officially part of the Scrum Guide, tied to the Increment commitment). DoR describes whether a task is ready to be picked up for work in the first place (an unofficial, but very widely used practice). They apply to different points in the process.

- **"Backlog Refinement is the same as Sprint Planning"** — Refinement is an ongoing prep activity during the sprint, meant to make future items clear and estimated ahead of time. Sprint Planning is a one-time event at the start of the sprint, where a specific amount of work gets chosen from an already-refined backlog. Good refinement makes Sprint Planning fast and predictable; without it, Planning turns into an improvised discussion of unclear tasks.
