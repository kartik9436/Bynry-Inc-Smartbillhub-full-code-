# runbooks — Endpoints

**Eighteen routes across four edges.** Source: the Runbooks specification **B4**, which extended
its own first draft with the templates library, adding and cloning a runbook, a row decision,
raising work items on demand, and the cutover plan — *"had screens and cards but no route"*.
`RB-024` is the commitment that carries them.

**Platform conventions, unchanged.** Tenant comes from the first path segment and is resolved by
the existing middleware. **Lists page with `per` clamped to 50/100/200/500/1000, default 50**
(`NFR-3`). Long runs answer **`202` + a job id** and are polled at the existing jobs endpoint;
under 5,000 records a run answers **`200` inline**. **Every one returns the existing error
envelope** `{code, message_key, params, field_errors, br_ref, trace_id}` (`core/errors.py`) —
none invents a response shape. Every refusal is **six words or fewer** (B14 rule 33) and its
`message_key` is in **all eleven catalogues** (`g15`, `g32`).

**Screens are `RBS-001`…`RBS-008`** (PO ruling 2026-09-06). The nav route stays
`/{tenant}/operations` as every wireframe draws it. The backend module is **`apps/runbooks`**;
the specification's own `apps/operations` is superseded for the code by that naming ruling, and
the seam files keep the source's `operations → <module>` pair naming.

⚠ **Nothing below exists in code.** `apps/runbooks` has not been created; these are the routes the
stories need, as B4 declares them.

| Edge | Rows | Screens | Who may call it |
|---|---|---|---|
| Catalogue and definition | **6** | `RBS-002` Templates · `RBS-003` My runbooks · `RBS-004` Runbook detail | Staff reads; **Admin** writes |
| Runs | **10** | `RBS-005` Run wizard · `RBS-006` Run result · `RBS-008` Run history | Staff, except **approve** which is Admin |
| Work list | **1** | `RBS-007` Work list | Staff |
| Cutover plan | **1** | the plan surface (`RB-035`, OPEN decision 8) | Admin |

⚠ **Eighteen ROWS, twenty-one method-and-path pairs.** Two rows bundle their methods the way B4
writes them — `GET · PATCH /work-items[/{id}]` and `GET · POST /cutover-plans · PATCH
/cutover-plans/{id}/items/{seq}`. **Eighteen is the source's count and is kept**; the arithmetic is
recorded so a build lane counting routes in a router does not think it has found a discrepancy.

---

## 1 · Catalogue and definition — 6

| # | Endpoint | Does | Refuses when | Role · returns | Screen |
|---|---|---|---|---|---|
| 1 | `GET /runbooks` | The catalogue with **last-run summary and open-item counts**; filter by `kind` and `category` | — | Staff · `200 · list` | `RBS-001` · `RBS-003` |
| 2 | `GET /runbooks/{key}` | Definition, schedule, caps, guards, **next run** | — | Staff · `200` | `RBS-004.1` |
| 3 | `PUT /runbooks/{key}` | Change schedule, cap, gate or enabled — **writes a new version**. ⚠ **BUILT `CR-075` wave `E1`, AND IT CARRIES TWO THINGS THIS ROW DID NOT NAME.** (a) **`visible_to_roles`**, because `RB-050` says *an Admin may widen or narrow it per runbook* and gives no other route to do it in; (b) **`accept_template_update: true`**, which takes the offered shipped change onto this copy — the *pressed* in `BR-RBS-038`'s *changing nothing until pressed*. **That is deliberately NOT a nineteenth route**: mechanically it is an edit that writes a new version, and minting an address the source does not give would be a build lane widening the contract it is implementing. It is idempotent — accepting an offer that is not there returns the runbook unchanged rather than refusing, because a double click is not an error a clerk should be shown. | **`409 runbooks.refusal.not_editable`** when the body names a field a signed rule freezes — `kind` (`BR-RBS-001`), `key`, `category`, `origin`, `template_key`, `current_version`, `trusted_version`, `subject_type`, `unit_of_work` — refused BY NAME rather than ignored, because silently dropping one leaves the caller believing the change landed · `422` on an unknown field or a cap below 1 (`NFR-5`: there is no cap MAXIMUM and never will be). ⚠ **The edit itself is never refused for the trust ratchet.** `BR-RBS-036` is enforced on the NEXT RUN — `services.open_run` answers `runbooks.refusal.dry_run_first` — because a person narrowing a runbook's scope after a bad run must not be stopped from doing exactly that | **Admin** · `200 · new version` | `RBS-004.3` · `RBS-004.5` · `RBS-004.7` |
| 4 | `GET /runbooks/templates` | The shipped library with **Added, Not added or Unavailable** per tenant, **and the reason when unavailable** | — | Staff · `200 · list` | `RBS-002.1` · `RBS-002.2` |
| 5 | `POST /runbooks` | **Add a template** to My runbooks. Body `{template_key}` | **the template is unavailable** · ⚠ **AND `409 runbooks.refusal.already_added` WHEN THIS TENANT ALREADY HAS IT** — `BR-RBS-043`, ruled by the `CR-075` wave `E1` lane and recorded in `12-governance/02-decision-log.md`, 2026-09-06. B4 names no refusal for a second add and the build had to choose: row 4's whole state vocabulary is **Added · Not added**, which is a statement about ONE runbook, so a second add is a stale screen or a double click and answering `201` over the row that already existed would tell the caller something was created that was not. A second copy is made by CLONING (row 6). ⚠ **`Added` is `template_key` PLUS `origin = shipped`**, because a clone carries the source's `template_key` — that pointer is the only thing that finds a clone's CODE — so a tenant that has only ever cloned still sees **Add** · `422 runbooks.refusal.unknown_template` on a key we do not ship | **Admin** · `201 · the new runbook` | `RBS-002.2` |
| 6 | `POST /runbooks/{key}/clone` | **Clone and vary** (`RB-040`). Body `{name}`; the copy carries `origin = cloned` and **its own version 1** | — | **Admin** · `201 · the copy` | `RBS-003.1` |

**A template needing a switched-off capability is shown DISABLED, not hidden** — a deliberate
departure from *hide what does not apply*, ruled by the specification on 4 September 2026 with the
**PO not asked**. That is why row 4 carries *the reason when unavailable*: the card says why.

**Role visibility defaults from the category** and an Admin may widen or narrow it per runbook
(`RB-050`): a Finance user's Templates page shows Finance, Payments and Collections runbooks and
not Platform.

## 2 · Runs — 10

| # | Endpoint | Does | Refuses when | Role · returns | Screen |
|---|---|---|---|---|---|
| 7 | `POST /runbooks/{key}/runs` | **Start a run.** Body `{mode}`; **an Action always starts dry** | **a run is already in flight for this runbook** → `409 runbooks.refusal.already_running` · **the planned count exceeds the cap** → `422 runbooks.refusal.over_cap` · **a guard is off that policy requires on** → `422 runbooks.refusal.guard_required` | Staff · `200` inline under the async bar, else `202 + job id` | `RBS-005.1` → `RBS-005.2` |
| 8 | `GET /runbooks/runs` | **History across runbooks**, filterable by runbook, category, outcome and date | — | Staff · `200 · paged` | `RBS-008` |
| 9 | `GET /runbooks/runs/{id}` | Run header, counts, status, approver | — | Staff · `200` | `RBS-005` · `RBS-006` |
| 10 | `GET /runbooks/runs/{id}/report` | **The frozen block list** the result renderer draws | — | Staff · `200` | `RBS-006` (and every `RBS-006-Rn`) |
| 11 | `GET /runbooks/runs/{id}/records` | Per-record **plan and outcome**, filter by outcome | — | Staff · `200 · paged` | `RBS-005.3` · `RBS-006` |
| 12 | `POST /runbooks/runs/{id}/approve` | **Approve a plan.** Body `{approved_count}` **must match the current plan** | **the plan moved since Review** → `409 runbooks.refusal.plan_changed`, and **nothing is queued** | **Admin** · `202` · or `409` | `RBS-005.4` |
| 13 | `POST /runbooks/runs/{id}/stop` | **Halt a run in flight**; records already acted **stay acted** | — | Staff · `200` | `RBS-005.5` · `RBS-006.3` |
| 14 | `GET /runbooks/runs/{id}/results/{done\|not-done}.csv` | **The two result files**, each row carrying **its reason and its fix** | — | Staff · `200 · text/csv` | `RBS-006` (Downloads block) |
| 15 | `POST /runbooks/runs/{id}/records/{rid}/decide` | **A row decision** on a queued record: pick account, confirm overpayment, accept theirs, keep ours (runbooks 10 and 20); **performed through the owning module's port** | **the record was not queued for a person** → `422 runbooks.refusal.nothing_to_decide` | Staff · `200 · the record` | `RBS-006` (Row decisions block) |
| 16 | `POST /runbooks/runs/{id}/work-items` | **Raise work items from a Check's findings on demand** — the *Raise work items ✓* button on runbooks 5, 18 and 19 | — | Staff · `202 · count raised` | `RBS-006` (Action block) |

**The engine, not the runbook, writes on 15 and 16.** Row 15 is a decision a person performs from
an Action block and the owning module's port performs the write; row 16 is the engine upserting
findings as work items. **Neither is a runbook writing** (`BR-RBS-022`).

**Row 7 is where three of the six refusals live**, and they are the three that protect a customer:
one run at a time, the cap, and the guards. **The cap refuses the run — it never truncates the
set** (`BR-RBS-006`), and `RBS-005.7` gives the clerk the three choices *Narrow scope · Raise limit
· Send first 400* with **no notice queued until one is pressed**.

## 3 · Work list — 1

| # | Endpoint | Does | Refuses when | Role · returns | Screen |
|---|---|---|---|---|---|
| 17 | `GET · PATCH /work-items[/{id}]` | The work list; **assign, resolve, reopen**. Findings, exceptions and human tasks in one place, **upserted by fingerprint so a repeated finding ages rather than duplicating** | — | Staff · `200 · paged` | `RBS-007` |

## 4 · Cutover plan — 1

| # | Endpoint | Does | Refuses when | Role · returns | Screen |
|---|---|---|---|---|---|
| 18 | `GET · POST /cutover-plans` · `PATCH /cutover-plans/{id}/items/{seq}` | A go-live plan and its items; **PATCH attaches a run as evidence** or **ticks a human task** (`RB-035`, runbook 2's *Attach to plan ✓*) | — | **Admin** · `200 · 201` | the plan surface — ⚠ **OPEN decision 8**: a product screen now, or a spreadsheet for the first two customers |

---

## The six refusals — why they are message keys and not `RBS-nnn` codes

⚠ **THE SOURCE GIVES THESE AS NUMERIC ERROR CODES `RBS-001`…`RBS-006`. THAT FORM IS GONE AND MUST
NOT BE BUILT.** Two independent reasons, either of which is enough:

**1 · It collides, by name, with the screen series.** The PO ruled on 2026-09-06 that runbook
screens are their own series, **`RBS-001` Runbooks home … `RBS-008` Run history**. `RBS-001` is now
a *screen*. The decision log says it in the same row: *"the bare `RBS-001`…`RBS-006` error codes in
the specification are now a collision and are dropped."* A `br_ref` reading `RBS-004` would point
at **Runbook detail**, and the module code is `RBS` as well, so `BR-RBS-004`, `US-RBS-004` and
`TC-RBS-004` all contain the same six characters. That is `DEF-2804`'s shape — an id that resolves,
to the wrong thing, silently.

**2 · This repo has no numeric error codes at all, and `code` is a CLOSED catalogue the envelope
will not let you widen.** Every refusal in the product is a **message key** carried in the
envelope and translated in eleven catalogues — `integrations.refusal.already_connected`,
`integrations.refusal.not_connected`, and 40-odd more. `g15` checks catalogue parity and `g32`
resolves keys at the raise site. Meanwhile the envelope's **`code`** comes from B12 §3's twenty
class codes in `06-backend/core/errors.py` — `AUTH-001`…`003` · `VAL-001`…`005` ·
`BIZ-IMMUTABLE` · `BIZ-IDEMPOTENT` · `BIZ-LOCKED` · `BIZ-WINDOW` · `BIZ-APPROVAL` ·
`BIZ-COMPLETENESS` · `BIZ-CAP` · `BIZ-STATE` · `BIZ-SOD` · `SYS-*` — and the file says of its own
exception hierarchy that *"an endpoint physically cannot raise … a made-up code through any"*.
**`RBS-001` was never a value this envelope could carry.**

**So all six become `runbooks.refusal.<name>`**, and the screen sentence is what the source already
wrote — each already six words or fewer (B14 rule 33):

⚠ **SIX FROM THE SOURCE, AND FIVE MORE THIS BUILD NEEDED — ALL ELEVEN LIVE IN ALL ELEVEN
CATALOGUES.** `CR-075` wave E built the first write routes this module has ever had, and three of
its refusals have no row in the table below because B4 names no refusal for them at all:
`runbooks.refusal.already_added` (*Already added. Open it.*, `409`, `BR-RBS-043`),
`runbooks.refusal.unknown_template` (*That template does not exist.*, `422`),
`runbooks.refusal.not_editable` (*That cannot be changed here.*, `409`, `BR-RBS-001`),
`runbooks.refusal.update_pending` (*Review the update first.*, `409`, `BR-RBS-038` — a run whose
stored version and live module have diverged) and `runbooks.refusal.dry_run_first` (*Run it dry
first.*, `409`, `BR-RBS-036` — the trust ratchet). **The six below are still owed by waves `L`
onwards and this build raises none of them.**

| Was | Message key | HTTP | When | What the screen says |
|---|---|---|---|---|
| `RBS-001` | `runbooks.refusal.plan_changed` | `409` | Approving a plan whose count has changed | **The plan changed. Review it again.** |
| `RBS-002` | `runbooks.refusal.over_cap` | `422` | Planned count exceeds the cap | **Too many for one run. Narrow it.** |
| `RBS-003` | `runbooks.refusal.check_cannot_write` | `403` | **A Check attempted a write** | **Not shown to a clerk** — a defect path: logged and alerted |
| `RBS-004` | `runbooks.refusal.already_running` | `409` | A run is already in flight for this runbook | **Already running. Open it.** |
| `RBS-005` | `runbooks.refusal.guard_required` | `422` | A guard is off that policy requires on | **Turn protections back on first.** |
| `RBS-006` | `runbooks.refusal.nothing_to_decide` | `422` | A row decision on a record the run did not queue for a person | **Nothing to decide here.** |

### The `code` beside each key — and the one HTTP status the source cannot have

**`HTTP_STATUS_BY_CODE` in `core/errors.py` derives the status FROM the code.** A route does not
choose `409` or `422`; it chooses a class code and the status follows. So B4's six statuses have
to be re-derived rather than transcribed. **The mapping below is THIS FILE's derivation, not the
source's** — B4 names no class codes — and it is here so a build lane picks deliberately:

| Message key | Class code (derived) | Status the code forces | B4 said |
|---|---|---|---|
| `runbooks.refusal.plan_changed` | `BIZ-STATE` | `409` | `409` ✓ |
| `runbooks.refusal.over_cap` | `BIZ-CAP` | `422` | `422` ✓ — and `BIZ-CAP → 422` is itself a ruled row (`11b G11`) |
| `runbooks.refusal.check_cannot_write` | `AUTH-002` | `403` | `403` ✓ |
| `runbooks.refusal.already_running` | `BIZ-STATE` | `409` | `409` ✓ |
| `runbooks.refusal.guard_required` | `BIZ-COMPLETENESS` | `422` | `422` ✓ |
| `runbooks.refusal.nothing_to_decide` | **undecided** | — | `422` ⚠ |

⚠ **The last row does not resolve and is left open rather than guessed.** *"A row decision on a
record the run did not queue for a person"* is a **state** fact — the record is not in the state
that admits a decision — and `BIZ-STATE` is `409`, not the `422` B4 wrote. Every code that IS
`422` says something else: `VAL-*` is a malformed field, `BIZ-CAP` a limit, `BIZ-WINDOW` a period,
`BIZ-APPROVAL` a missing approval, `BIZ-COMPLETENESS` something absent, `BIZ-SOD` separation of
duties. **So either the status is `409` or the code is a widening of the catalogue, and both are
decisions above a documentation pass.** Recorded, not resolved.

⚠ **AND AN UNRESOLVED KEY IS NOT UGLY — IT IS SILENT.** PO ruling 2026-08-19: a refusal's words
come from the catalogue entry for its `message_key` **and from nowhere else**, so a key missing
from the catalogues renders as **nothing at all** — the clerk presses the button and the click
appears to do nothing (`core/refusal_catalogue.py`, written after 57 such keys in the Work module
alone on 2026-09-05). **All six keys land in all eleven catalogues in the same commit as the raise
site**, or `test_refusal_keys_resolve_at_raise.py` and `g32` say so.

**`check_cannot_write` is the odd one and is kept deliberately.** The source rules it **out of
scope for any screen** — *"it is a defect path, logged and alerted, and `RB-001` makes it
unreachable"* (specification, 4 September 2026, **PO not asked**). It keeps a key because the
envelope carries a `message_key` on every refusal; **whether a key nothing renders needs eleven
catalogue rows is `g32`'s question to answer at build time, not a licence to leave it blank.**
`BR-RBS-002` is what makes it unreachable: **a Check is constructed with no ports, so the write is
unavailable rather than refused** — if this refusal ever fires in production, the construction
guarantee has broken and that is the alert, not the message.

⚠ **`runbooks.refusal.already_running` is the only one of the six with no rule behind it.** It is
`RBR-08` in the specification's appendix — *"one run per runbook at a time"* — which that appendix
records as having **no home** in this repository. Recorded in `02-business-rules.md`; it is not
minted into `BR-RBS-###` here.

---

## What B4 does not say, recorded rather than filled in

| # | Where | Finding | Disposition |
|---|---|---|---|
| **E-1** | rows 1 and 4 | The catalogue and the templates library return `200 · list` where the run history, the records and the work list return `200 · paged`, though B4's own preamble says *"lists page with `per` clamped…"*. | **Not resolved here.** Both are bounded by the **shipped** catalogue (twelve templates today, twenty-one runbooks defined) rather than by tenant size, so neither is `NFR-3`'s hazard — that is an unpaginated list whose length grows with the tenant, as `GET /outstandings` does. Named so the build lane pages them deliberately rather than by accident. |
| **E-2** | row 3 | `PUT /runbooks/{key}` names **no refusal**, but `BR-RBS-036` (an edited Action re-enters dry run) and `BR-RBS-037` (a composition failing the conformance suite does not save) both bite on a write to a definition. | The trust ratchet is enforced on the **next run**, not on the edit — which is what `RB-051`'s *done looks like* describes (*"Run is dry-run only until one clean dry run is reviewed"*). `BR-RBS-037` belongs to **Compose**, a phase-3 surface B4 gives no route. Both are absences of a route, not of a rule. |
| **E-3** | the module | **No route exists for Compose** (`RB-041`, the specification's own increment **`3`** — ⚠ **read that as the SOURCE's increment, not as this plan's phase 3**, which after the 2026-09-06 re-cut is the integration runbooks; compose is wave `T`, **phase 5**) and none for a step library, because **there is no tenant-facing step library to serve** — `BR-RBS-042` (PO 2026-09-06) puts the library on our side: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*. ⚠ **THIS SENTENCE READ *“and none for the step library it draws from”* UNTIL 2026-09-06**, which implied a route was owed. **What wave `T` actually owes is smaller**: each parameter's **domain**, resolved per tenant, accepting one value, several or *all*. B4 is explicit that it covers the eighteen; the composition surface is later. | Correct as written. Recorded so *"where is the compose endpoint"* has an answer that is not a guess. |
| **E-4** | rows 7–16 | **Three of the eighteen depend on an integration event** (`batch.landed`, `feedback.landed`, `bill_run.completed`) rather than on a caller: `RB-022` is **BLOCKED-BY the integration substrate (`CR-069`)** for the three event kinds. **Manual and schedule wait on nothing.** ⚠ **AND AFTER THE 2026-09-06 RE-CUT THIS IS PHASE 3's BLOCKING DEPENDENCY RATHER THAN PHASE 5's** — `batch.landed` and `feedback.landed` **do not exist anywhere in `06-backend/apps/integrations/`, and no CR-069 wave commissions them.** Under `BR-INT-054` as amended that day they are integrations' half to build. Without them phase 3's four runbooks can only be run by hand. | Not a route change: the event trigger enqueues the same job `POST …/runs` does. Recorded because a lane building row 7 can build it fully today. |
| **E-5** | every row | **`GET /runbooks/runs/{id}/report` serves a FROZEN document.** A build lane that renders from the live definition instead passes every test until a runbook is edited, and then rewrites history (`BR-RBS-020`; `TC-RBS-16` must first fail on a report read live at render). | Named on the endpoint because that is where the mistake gets made. |
