# QA Automation

Cross-stack suites owned by the QA Lead (04-docs/06-roles/qa-lead.md). Unit/golden/isolation
suites live in 06-backend/tests (they gate CI); this folder holds what spans the stack.

| Folder | What | Activates |
|---|---|---|
| 01-e2e/stack/ | **The running product, for a browser to click** — `boot_stack.sh` brings up Postgres + Django + the BUILT SPA on one origin, seeded with Brazos Bend and one engine-priced bill. Read its README first | **LIVE 2026-08-11** |
| e2e/ | Playwright journeys — the money journey first: signup → configure → premise → account → read import → bill run → payment → reconcile → export | when the app boots end-to-end |
| contract/ | API responses vs 04-docs/01-spec/11-api-contracts.md shapes | with the first shipped endpoint |
| regression/ | Per-release packs; a pack freezes at each release tag | first release |
| fixtures/ | Test-data builders (tenants, accounts, reads incl. the 7 billing exception cases) | with e2e |

IS conformance: the B9 standards are tested ONCE against a reference table; per-screen conformance tests generate from each epic's capability matrix.

## What actually executes today (2026-08-11) — say the number, not "E2E exists"

The PO ruled on 2026-08-11, verbatim: **"we ahve to prove against human clicking"**,
after the honest measurement that nothing in this repo exercised the running
product (DEF-057). What that ruling has bought so far, stated so nobody reads
more into it than is there:

| | Count | Runs a browser? |
|---|---|---|
| backend tests over the real cross-module chain | 1,651 | no — API and DB, which is genuinely end-to-end for the engine |
| frontend unit tests | 875+ | no — **mocked** API responses |
| journey DOCUMENTS in `01-e2e/journeys/` | 304 (303 indexed + README) | no — they are documents |
| Playwright spec FILES in `07-frontend/e2e/` | 3 | **yes**, against a live stack |
| **ACTIVATED journeys** | **0** | — no spec claims a catalog journey id |
| browser assertions on a passing run | **38** (46 total) | printed by the suite's own census, every run |

**One journey is one journey.** `W3-money-render.spec.ts` proves that the figure
a human SEES on S30 equals GT-1 as finance signed it; `W4-payment-write.spec.ts`
proves a clerk can RECORD that money on S33 and that the issued bill does not
move when they do. Neither proves any of the 303 journeys, and neither claims
one.

**Gate G12 stopped reporting SKIP on 2026-08-11 — it was a hardcoded
`return "SKIP"`, which is a row in a gate table that cannot fail.** It now
checks, per merge, that the generated wiring index is fresh, that a
`<Journey-ID>.spec.ts` claims that journey, that a spec claiming a journey is
named for it, that no spec claims an id the catalog does not define, and that
**no spec claims a journey whose stories the index says are not all built**. With
`--wave-close` it also requires the last Playwright run receipt to record every
activated journey as passed. Six failure modes, each proved RED first (law 7).
It reports PASS with `0 activated` today — which is the honest statement
"nothing claims a journey", not "this gate does not look".

The half that is durable rather than incremental is that a **skipped browser
suite now FAILS** instead of printing "Passing by design" (`07-frontend/e2e/support/census.ts`).

## The rule that stops this gap reopening (PROPOSED 2026-08-11 — not ruled)

> **The lane that finishes a story writes the journey spec that exercises it**,
> in the same packet as the code — not a catch-up sweep later.

304 documents and two executing specs is what the catch-up model produced in
three days. The lane that just built the screen knows its selectors, its fixture
and its figures; a QA sweep three weeks later has to rediscover all three, and
usually discovers instead that the journey can only be half-executed. Recorded
as **PROPOSED** in `12-governance/02-decision-log.md` (2026-08-11) for the PO
batch, and in `07-frontend/e2e/README.md` where the next spec author will hit it.

**What the activation contract still needs from the PO** (both minted 2026-08-11,
both blocking nothing today but shaping every later activation):

- **OQ-172** — what makes a story "built" for activation? The index uses
  Trace-header citation, the only machine-readable signal the repo has; it is
  evidence, not proof (J09 scores 5 of 6 stories "built" with no budget screen
  anywhere).
- **OQ-173** — 207 of the 303 indexed journeys (every generated T3M and T3P
  file) declare no `stories:` frontmatter, so "activates when its last story is
  built" is undefined for two thirds of the catalog.
