# Agile Fundamentals

## The problem that Agile was trying to solve

To understand why Agile exists, we first need to understand the pain it was solving. This pain has a name: **waterfall**. Waterfall is a development model where a project moves through strict, sequential phases: gather requirements → design → build → test → release. Each phase must finish completely before the next one starts. There is no formal way to go back a step (the name comes from this idea — water flows down, never up).

Here is a historical detail that often comes up in interviews. Waterfall was not invented as the "correct" way to build software that later got broken. Winston Royce's 1970 paper, which people usually credit as the source of waterfall, actually described the strict sequential process as risky and recommended iterative changes to it. But the industry only picked up the diagram of phases from that paper. For the next 25 years, teams built their processes around a strict, sequential reading of it.

By the late 1990s, industry data (the Standish Group's CHAOS Report and similar studies) showed a very low percentage of software projects finishing on time, within budget, and with the promised features. There were three systemic reasons for this, and all three come directly from waterfall's structure.

### Three failure patterns in waterfall

**Late feedback.** Requirements get fixed at the start of the project and signed off by the customer. The customer only sees working software at the very end — often 9 to 18 months later. If the team misunderstood what the business actually needed during the requirements phase (and this happens almost every time — people describe requirements poorly before they see a working prototype), the mistake is found when it is the most expensive to fix: the code is written, the architecture is built around the wrong model, and the tests check the wrong behavior.

**Requirements drift.** Real business needs do not stay still for 12 to 18 months while development happens. The market changes, competitors appear, and management priorities shift. Waterfall has no built-in way to handle this. It only has a "change control" process, and by nature this process is slow and adversarial: any change to a requirement looks like breaking a signed contract, not like a normal part of the work. As a result, the team either ignores the changed reality and delivers something nobody needs anymore, or it drowns in endless approval cycles for change requests.

**Big-bang integration.** In waterfall, different modules of a system are usually built by different sub-teams in parallel, over months. They are put together for the first time only during integration testing, near the end of the project. Interfaces between modules that looked consistent on paper turn out not to match in practice: different assumptions about data formats, different assumptions about call order, different error handling. Integration becomes a last-minute crisis, right when the time budget for fixes is already gone.

All three patterns share one thing: **feedback from reality is delayed until the point where fixing a mistake costs the most.** Agile is not a set of rituals. It is a direct answer to this problem: make feedback loops shorter, so mistakes get caught while they are still cheap.

## The Agile Manifesto — the real text

In February 2001, seventeen developers (including the creators of Scrum, Extreme Programming, DSDM, and other lightweight methods) met in Snowbird, Utah. They wrote down the shared ideas behind their different practices. The result is the **Manifesto for Agile Software Development**. It is short: four values and twelve principles.

The Manifesto does not say "do daily standups" or "use two-week sprints." It does not mention Scrum at all. It describes *values and priorities*. Specific frameworks (Scrum, Kanban, XP) are different ways to *put these values into practice* — they are not the Manifesto itself.

### The four values

> We are uncovering better ways of developing software by doing it and helping others do it. Through this work we have come to value:
>
> **Individuals and interactions** over processes and tools
> **Working software** over comprehensive documentation
> **Customer collaboration** over contract negotiation
> **Responding to change** over following a plan
>
> That is, while there is value in the items on the right, we value the items on the left more.

The last line is the most overlooked part of the Manifesto — and it is the source of a very common interview mistake (see below). The Manifesto does **not** say that documentation, process, contracts, and plans are useless. It says that when they conflict with people, working software, collaboration, or the ability to adapt, the second group wins.

### The twelve principles

The four values are abstract. The twelve principles turn them into something more concrete. It's worth understanding each one, not just memorizing the words:

1. **Our highest priority is to satisfy the customer through early and continuous delivery of valuable software.** Not "deliver on the plan's schedule" — deliver real value, early and often, instead of one big release at the end.
2. **Welcome changing requirements, even late in development.** This is the opposite of change control in waterfall. A changed requirement is not a problem — it's a normal part of the work, and it can give the customer an advantage.
3. **Deliver working software frequently, from a couple of weeks to a couple of months, with a preference for the shorter timescale.** This is the direct mechanism for shortening the feedback loop described above.
4. **Business people and developers must work together daily throughout the project.** Not "sign the requirements doc and meet again at final acceptance" — an ongoing conversation.
5. **Build projects around motivated individuals. Give them the environment and support they need, and trust them to get the job done.** A clear rejection of micromanagement as a management style.
6. **The most efficient way to share information within a team is a face-to-face conversation.** Not "everything must live in Jira" — a recognition that a live conversation is faster and more accurate than written documentation for many kinds of information.
7. **Working software is the primary measure of progress.** Not percent-complete on a plan, not lines of code written, not the number of closed tickets — does the product actually work?
8. **Agile processes promote sustainable development. Sponsors, developers, and users should be able to keep a constant pace forever.** A direct answer to "crunch sprints" and overtime as a normal way of working.
9. **Continuous attention to technical excellence and good design improves agility.** Technical debt is not something you "fix later." It directly reduces the team's ability to respond to change — which undermines the whole point of being agile.
10. **Simplicity — the art of maximizing the amount of work not done — is essential.** Do not build things that might be needed in the future. Build what is needed now.
11. **The best architectures, requirements, and designs come from self-organizing teams.** Decisions are made by the team doing the work, not handed down from management.
12. **At regular intervals, the team reflects on how to become more effective, then adjusts its behavior.** This is the principle behind the retrospective — but notice: it demands *real* behavior change, not just holding a meeting.

## "Being Agile" vs "Doing Agile ceremonies"

This is the key distinction of the whole topic, and it is the most common interview trap for senior/lead-level candidates.

**Being Agile** means actually working according to the values and principles above: short feedback loops with real users, willingness to change the plan when reality changes, a team that decides how to do its own work, and reflection that actually leads to changed behavior.

**Doing Agile ceremonies** means performing the outer shape of a framework (usually Scrum): two-week sprints, a daily standup, a retro at the end of the sprint, a board with To Do / In Progress / Done columns — but without the thing these rituals were built to achieve.

The difference is not abstract. Here is what it looks like in practice:

```txt
Ceremony               │ Working (Agile)                │ Theater (Cargo Cult)
────────────────────────┼──────────────────────────────────┼───────────────────────────────
Sprint Review            │ Real users or stakeholders      │ A demo for a manager who
                          │ watch the working increment     │ already knows what's coming;
                          │ and give feedback that          │ feedback changes nothing
                          │ changes the backlog             │
────────────────────────┼──────────────────────────────────┼───────────────────────────────
Retrospective             │ The team finds 1–2 concrete     │ The same complaints every
                          │ actions, and they actually      │ sprint; nobody tracks the
                          │ get done before the next retro  │ action items
────────────────────────┼──────────────────────────────────┼───────────────────────────────
Daily Standup             │ The team syncs, finds           │ Each person reports status
                          │ blockers, and changes the       │ to the manager in turn;
                          │ day's plan if needed            │ nobody actually listens
────────────────────────┼──────────────────────────────────┼───────────────────────────────
Sprint Planning           │ The sprint goal is really       │ Management already decided
                          │ discussed and shaped by the     │ what must be done;
                          │ team                            │ "planning" is a formality
```

## Cargo Cult Agile and Zombie Scrum

The term **cargo cult** comes from anthropology. After World War II, on some Pacific islands, local people had seen Allied planes bring supplies to airstrips built for the war. After the war, some of them built their own "airstrips" and wooden "radio towers," copying what they had seen — hoping the planes would come back with more supplies. They copied the outer form exactly. They did not reproduce the function that actually brought the planes: the real logistics system behind it.

**Cargo Cult Agile** is the same idea, applied to software teams: a team copies the visible parts of Scrum (sprints, standups, a board, a retro) without understanding or reproducing the mechanism these practices were built for — a short feedback loop with reality. The result looks like Agile in every artifact, and is not Agile at all in substance.

**Zombie Scrum** is a more specific term (coined by Barry Overeem and co-authors) for this exact situation applied to Scrum: the team performs every formal Scrum event, but is "dead inside." There is no real inspection (the Sprint Review reveals nothing new, because no real stakeholders attend). There is no real adaptation (the retro finds the same problems sprint after sprint, and nothing changes). There is no focus on value for the user (the team just closes tickets). On the outside: "we do everything the Scrum Guide says." In substance: a process that gives none of the benefits Scrum was built to provide.

### A scenario: what this looks like from the inside

A team has worked in two-week sprints for six months. Every morning there's a 15-minute standup where each person reports status to the tech lead, one by one. The retro happens every second Friday, 30 minutes, and it usually turns into a list of complaints about slow CI — the same list as three months ago. The Sprint Review is a call where a developer shows their screen to the product owner; real users of the product have never attended this call. A product manager writes the sprint's requirements the day before planning and sends a list of tickets. During planning, the team mostly just clarifies implementation details, not whether the work is even worth doing.

On paper, this is Scrum: all five events happen, roles exist, there's a backlog. In substance, it's waterfall cut into two-week pieces: requirements come from above, there's no feedback loop with real users, and the retro produces no change. This is Zombie Scrum.

What would a working Agile process look like in the same situation? A real user representative (or at least someone who works closely with users) attends the Sprint Review, and their feedback actually reorders the backlog for the next sprint. In the retro, the team picks exactly one change, someone takes ownership of making it happen, and the next retro checks whether it worked. Sprint Planning starts with a discussion of the goal ("why are we doing this"), not with a list of ready-made tickets.

## Common interview traps

- **"Agile is a methodology"** — no. Agile is a set of values and principles (the Manifesto). Scrum, Kanban, Extreme Programming, and DSDM are specific frameworks or methodologies that put these values into practice in different ways. Saying "we use Agile" means nothing without saying which framework, and how.

- **"Agile means no planning and no documentation"** — this misreads the Manifesto. The values are written as priorities ("working software *over* documentation"), not as a rejection ("documentation is useless"). Agile teams plan constantly — just in short cycles, with a willingness to revise the plan, instead of planning once at the start for the whole project.

- **"If we have standups and sprints, we are doing Agile"** — this is exactly the Cargo Cult Agile trap. Having the rituals says nothing about whether a real feedback loop exists. The right question is not "what meetings do you have," but "what actually changes as a result of those meetings."

- **"Agile guarantees faster development"** — Agile optimizes for adaptability and early feedback, not for raw speed. Early iterations can even be slower, because of the overhead of ceremonies and more frequent integration. The payoff is that you avoid the expensive, late-stage rework that waterfall projects are known for.

- **"Waterfall is just planning, and Agile is the absence of planning"** — waterfall's real problem is not that it has structure. It's that its phases are irreversible, and feedback from reality only arrives once, at the very end. A well-run Agile process also plans — it just plans in short cycles and keeps revising the plan as new information arrives.
