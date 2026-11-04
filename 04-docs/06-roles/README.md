# Build-Phase Role Profiles

Four operating profiles for the SMARTBillHub build. Each defines the **skills, responsibilities, decision rights, and quality bar** of a role so those skills can be leveraged on demand — by a human filling the seat or by an AI session instructed to operate per the profile.

| File | Role | One-line mission |
|---|---|---|
| [product-manager.md](product-manager.md) | Product Manager | Own *what* gets built and in what order; keep the spec, backlog, and open questions honest |
| [forward-deployed-engineer.md](forward-deployed-engineer.md) | Forward Deployed Engineer (FDE) | Turn spec into working, demonstrable increments at customer-context speed |
| [fullstack-engineering-lead.md](fullstack-engineering-lead.md) | Full Stack Engineering Lead | Own *how* it's built; guard the architecture, module boundaries, and money-critical code |
| [qa-lead.md](qa-lead.md) | QA Lead / Director | Own the release gates; prove correctness and isolation before anything ships |

## How to invoke a profile in a working session

State the role and the task; the session adopts that profile's skills, scope, and decision rights:

- *"Act as the **PM** — turn A2's account-detail fields into user stories for the customers module."*
- *"Act as the **FDE** — build S17 accounts list end to end against the contract in A11."*
- *"Act as the **Eng Lead** — review this PR for module-boundary and RLS violations."*
- *"Act as **QA** — write the tenant-isolation test plan for the payments endpoints."*

A session may switch hats mid-task, but must say so — decision rights differ per role.

## Build-phase RACI (money-critical activities)

R = Responsible · A = Accountable · C = Consulted · I = Informed

| Activity | PM | FDE | Eng Lead | QA | Finance (ext) |
|---|---|---|---|---|---|
| Backlog & priorities (build order) | **A/R** | C | C | C | I |
| A17 open-questions burn-down | **A/R** | C | C | I | C |
| Module scaffolding & feature code | I | **R** | **A** | C | — |
| RLS / tenancy code (🔒) | I | C | **A/R** (human) | C | — |
| Rating math / money rounding (🔒) | I | C | **A/R** (human) | C | **Sign-off** |
| Migrations & schema changes | I | R | **A** | I | C |
| Golden tests (GT-1…11) definition | C | C | C | **A/R** | **Sign-off** |
| Tenant-isolation & immutability gates | I | C | C | **A/R** | — |
| Release go / no-go | C | I | C | **A/R** | I |
| Weekly governance report (12.1) | **A/R** | C | C | C | I |
| Change management (CR records, cutover) | **A** | C | R | C | I |

Non-negotiables that override every role: the seven hard rules in `/CLAUDE.md`, and the 🔒 human-only file list — no profile authorizes an AI session to *decide* those areas alone.
