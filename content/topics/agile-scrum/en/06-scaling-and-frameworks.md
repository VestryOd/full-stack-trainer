# Scaling Agile Across Multiple Teams

## Why scaling is a genuinely harder problem

Everything covered in articles 02–05 works at the level of one team: one backlog, one Definition of Done, one board, one velocity number. Once several teams work on one product, or on connected products, new problems show up. These problems simply don't exist for a single team. And "just run Scrum in each team" does not solve them on its own.

**Cross-team dependencies.** Team A's sprint may depend directly on an API that Team B is building. If Team B doesn't finish on time, Team A's Sprint Goal fails for a reason completely outside its control. The same happens if Team B finishes, but with a different API contract than Team A expected. A single team never has this problem — all its dependencies are internal.

**Shared architecture decisions.** No single team owns the whole system's architecture. Each team optimizes for its own local goals: its own speed, its own Sprint Goal. It can make decisions that are locally reasonable but create problems at the system level. Typical results are duplicated functionality, data models that don't match, and conflicting technology choices.

**Release coordination.** If several teams deliver parts of one product, there are two options. Their work is integrated and released together, which needs time-based synchronization between teams. Or each part is released independently, which needs discipline around API contracts and backward compatibility. Without that discipline, one team's release breaks another team's work.

All of this comes directly from Conway's Law (see the Architecture topic): team structure shapes system structure. At the level of one team, Conway's Law causes no problems, because the team's structure is just the structure of one team.

At the level of several teams, how you split people into teams literally becomes your system's architecture. If that split is a bad one, with teams too tightly coupled by dependencies, no process added on top will fix it. Process can only ease the symptoms.

## SAFe (Scaled Agile Framework)

**SAFe** is a prescriptive framework for scaling. It splits the organization into four levels and keeps them in step with one shared rhythm.

```txt
Portfolio          coordinates several ARTs
  Large solution
    Program        one ART: several teams on a shared cadence,
                   usually a Program Increment of 8–12 weeks
      Team         a normal Scrum or Kanban team
```

ART stands for Agile Release Train. It is a group of several teams synchronized on a shared cadence. PI stands for Program Increment: that shared stretch of time, usually 8–12 weeks long.

The key mechanic is **PI Planning**, a large joint planning event. All teams in one ART come together, physically or virtually, for 1–2 days to plan the next 8–12 weeks. Cross-team dependencies get spelled out right there, during planning. The alternative is discovering them later, when a dependency already blocks someone's work.

**An honest assessment:** SAFe is heavy. Many "pure" Agile advocates criticize it for reintroducing top-down, waterfall-like planning under an Agile label. They point at fixed PIs and at the sheer amount of process. They also point at a multi-layer hierarchy of roles: Release Train Engineer, Solution Train Engineer and so on.

There is a fair counterpoint. SAFe gives real, working structure to genuinely large organizations: banks, insurance companies, large regulated enterprises. Such organizations have dozens of teams and need more than flexibility. They need predictable synchronization, and governance — the rules and controls — that satisfies regulatory requirements.

Take an organization with 40 interdependent teams working on one product in a regulated industry. There, "just give each team its own Kanban flow" does not solve the coordination problem. That problem is real and large.

## LeSS (Large-Scale Scrum)

**LeSS** is a framework created by Craig Larman and Bas Vodde. It is built around a clear philosophy: this is just Scrum, applied at scale, with as few extra mechanics as possible. Unlike SAFe, LeSS is deliberately minimalist.

Key mechanics:

- **One Product Backlog** shared by all teams, not one per team.
- **One Product Owner** for the whole product.
- **One shared Definition of Done** across all teams.
- **One shared Sprint**, synchronized across all teams.

The base version of LeSS covers 2–8 teams. For bigger scale there is **LeSS Huge**, with area backlogs: sub-product slices, each with its own Area Product Owner.

Sprint Planning happens in two parts. Part 1 is done together, to coordinate and work through dependencies. Part 2 is done separately, per team, to plan each team's own work.

**An honest characterization:** LeSS keeps Scrum's minimalism and deliberately avoids adding a management layer on top. Coordination complexity gets solved through the teams' own self-management instead. Those are the same self-organization principles as normal Scrum, applied to a more complex, multi-team situation.

This is the opposite instinct from SAFe. SAFe adds structure and roles from the top down. LeSS removes as much structure as it can and leaves teams to work it out themselves. Their main tools are one shared backlog and one shared Definition of Done.

## The "Spotify model" — a well-known interview trap

The widely cited "Spotify model" is **not an official scaling framework**. That diagram of Squad, Tribe, Chapter and Guild is one of the most common traps in senior/lead-level interviews.

Where it comes from: in 2012, Henrik Kniberg and Anders Ivarsson published a white paper. A white paper is a public report; this one described how Spotify's engineering culture was organized at that point in time. The authors were clear that this was a snapshot of a current, imperfect, still-evolving state, not a model meant to be copied.

Spotify itself later changed its organizational structure many times and moved away from parts of what was described. Even Spotify does not treat this diagram as its permanent target structure.

The terms from the white paper:

- **Squad** — a small, autonomous, cross-functional team, similar to a Scrum team, but without strictly required roles.
- **Tribe** — a group of several squads working in a related area.
- **Chapter** — people with similar skills, for example all frontend developers, from different squads within one tribe, brought together to share knowledge. A chapter is led by a chapter lead, who is often also a member of one of the squads.
- **Guild** — an informal, voluntary community of interest that crosses tribe boundaries.

**Why this is a trap:** many companies "adopted the Spotify model" by copying the org-chart labels. They renamed teams "squads" and departments "tribes," and stopped there. What they did not bring over was the deep culture of autonomy, trust and engineering maturity that actually made the structure work at Spotify.

This is a direct match for Cargo Cult Agile from article 01, applied at the level of organizational design instead of a single team's rituals. The form got copied — the names. The function did not: the real autonomy and level of trust that lets squads make decisions on their own, without approval chains.

When an interviewer asks about the "Spotify model," this is often a direct test. Does the candidate know this nuance, or do they just repeat the diagram as if it were a ready-made recipe?

## Scrum of Scrums (SoS) — the lightweight coordination pattern

**Scrum of Scrums** is not a full framework like SAFe or LeSS. It's a lightweight coordination pattern that you can add on top of whatever each individual team already uses (Scrum, Kanban, Scrumban — it doesn't matter which).

The mechanics are simple. Each team sends a representative to a regular sync meeting, usually 2–3 times a week. That is less often than one team's daily standup. The representative is not necessarily the Scrum Master, and the role sometimes rotates.

This meeting covers cross-team dependencies, blockers and integration issues. It is the same idea as a Daily Scrum, raised one level up. It is not about progress inside one team, but about where teams get in each other's way.

**Why most teams actually end up here:** the overhead is far lower than SAFe or LeSS. No company-wide reorganization, no single shared backlog, no new formal roles. All you need is one extra recurring meeting on top of each team's existing process, and you can adopt it gradually.

But this lightness comes at a cost. Scrum of Scrums does not solve deeper problems: shared ownership of architecture, a single backlog, unified prioritization across teams. It is coordination, not the full alignment that LeSS gives you with a single Product Backlog, or that SAFe gives you with PI Planning.

## How to choose: the scale of the problem sets the level of the framework

| Approach | What it is | Scale it targets |
|---|---|---|
| SAFe | A prescriptive framework with four levels and PI Planning. | Dozens of teams, regulated industries. |
| LeSS | Minimalist Scrum at scale: one backlog, one Product Owner, one Definition of Done. | 2–8 teams; LeSS Huge above that. |
| Spotify model | Not a framework at all: a 2012 snapshot of one company. | None: it is a description, not a recipe. |
| Scrum of Scrums | A lightweight coordination pattern, one extra sync meeting. | 2–3 teams with light dependencies. |

- **2–3 teams with light dependencies** — Scrum of Scrums is probably enough. A full scaling framework here is overkill and creates more overhead than benefit.
- **Many teams, a regulated industry (finance, insurance, healthcare), a need for predictable release synchronization and enterprise governance.** SAFe gives real structure that fits these requirements, even with its weight.
- **Teams want to genuinely scale a shared product and shared backlog ownership, while keeping Scrum's minimalism and self-organization culture.** LeSS is closer to this goal. It was explicitly designed as Scrum, not as a new hierarchy.
- **Simply copying the "Spotify model" terminology** (renaming teams "squads," departments "tribes") fixes nothing on its own. The real lesson from Spotify's experience is about a culture of autonomy and trust, not about the names of your organizational units.

## Common interview traps

- **"The Spotify model is an official scaling framework, like SAFe"** — no, it's a snapshot of a specific point in Spotify's history. Its own authors described it as an evolving state, not a prescriptive framework. Spotify itself later moved away from many parts of that structure.

- **"You can just adopt the Spotify model by renaming teams squads and departments tribes"** — this is exactly the Cargo Cult mistake from article 01. Here it is applied at the level of organizational design. The form gets copied, meaning the terminology. The function does not: the culture of autonomy and trust. Without that culture, a "squad" is just a team with a trendy name.

- **"SAFe is just bureaucracy, and LeSS is the 'real' scaled Agile"** — this oversimplification ignores context. SAFe really is heavy, but for large regulated organizations with dozens of interdependent teams, it provides structure that minimalist LeSS deliberately doesn't offer. The right choice depends on the organization's context, not on which framework counts as "more truly Agile."

- **"Scrum of Scrums is a complete scaling framework"** — no, it's a lightweight coordination pattern. It doesn't address shared backlog ownership, unified architecture, or coordinated prioritization across teams — that's what LeSS or SAFe handle, each in its own way.

- **"Scaling problems get solved by adding another process or meeting"** — the deeper point is that many scaling problems are really Conway's Law problems. Team boundaries shape system boundaries. If the boundaries are drawn badly, with teams tightly and constantly dependent on each other, no amount of coordination process will fix it. You need to change the team structure itself, not add another sync meeting on top of the wrong boundaries.
