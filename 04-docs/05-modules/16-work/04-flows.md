# 16 · Work — the eight end-to-end journeys

**Ids `J60` … `J67`.** `J1`–`J29` are the existing cross-module journeys (files exist),
`J30`–`J47` are the portal's (`CR-068`, described, files not written), `J48`–`J59` are
the integration substrate's (`CR-069`), and **the next free id was `J60`**, verified
2026-09-03. **Reserved for this module by the parent lane: `J60`–`J67`.**

⚠ **THE JOURNEY FILES IN `08-qa/01-e2e/journeys/` ARE NOT WRITTEN YET.** This file is the
authoritative description of all eight and the reservation of their ids; the executable
journey files are the next step and are named in the id-reservation row drafted for
`12-governance/14-id-reservations.md`. **A story's `journeys:` frontmatter cites an id
described here — do not read that as a file that exists** (hard-won law 1: a citation
claiming a guarantee is not the guarantee).

**Every journey below crosses modules, so every one has a handoff contract**: what
upstream leaves in the database for it, and what it must leave for downstream. Coding a
story without its journeys loaded is a prime-directive violation. **`J61` EXTENDS `J27`**
(`J27-new-connect-to-service-live.md`, which exists): where `J27` stops at *"if a job
somehow reaches Completed"*, `J61` puts a technician between the raise and the completion.

**One actor set throughout:** Brazos Bend Utilities (`brazosbend`) · M. Torres (supervisor
and dispatcher) · Alex Reed (System Admin) · D. Ortiz, M. Chen, R. Patel, J. Kaur
(technicians) · Sarah Miller (`A-10688`, `221 Oak Ave · Unit 3`) · Lone Star Ridge WSC (the
isolation tenant every journey asserts against).

---

## Phase 1

### `J60` · Settings → a published template, and the wizard proposes it
**Actor:** Alex Reed, then M. Torres · **Screens:** `Work-018` → `Work-013` → `Work-014`
→ `Work-015` → `Work-016` → `Work-017` → `Work-022` → `Work-004` · **Modules:** tenancy
(reference data) → work → customers (New Connect)
**Upstream leaves:** the 24 seeded starters; the six lookups seeded with the cards' sample
copy; `MTR-E1P`, `SEAL-01`, `GSKT-STD` in the parts register.
**The journey:** add the skill *Backflow* and the type *Backflow test* on `Work-018`; open
`Work-013` and read *6 templates · 4 published · 1 draft · 1 inactive*; press *New
template*, start from the *Meter exchange* pack, walk eight steps, Publish; `Work-022`
reads *v1 · Current*; open New Connect for Electric + Water and step 6 proposes **5**
orders.
**This journey leaves:** `ST-0001` published with 3 safety · 7 tasks · 3 materials · 3
readings · 3 help; a template proposal at step 6; **no work order** (nothing is written
until step 9, `BR-MET-112`). *(2026-09-03, `DEF-WRK-3572`: `J60` starts from the phase-1 seed BEFORE this template exists — `Work-019` reads `ST` next 1 — so its first publish takes `ST-0001` and the pack's 7 tasks. `J67` starts from a LATER state of the same tenant, where *Meter exchange — residential* is already published as v1 with 6 tasks and four orders and is numbered `ST-0002` as `Work-022` draws. The two do not chain, and the number is the series' to allocate: a spec asserts a template by name, version and task count, never by its drawn `ST-` string. `US-WRK-006` §4 states the three fixture states once.)*
**Assertions:** *arrives with Work* appears on no card · the Contents column counts the
bundle · publishing twice quickly makes one version · the Water service holds two
templates at once · Lone Star Ridge sees none of it.
**Stories:** `US-WRK-007`–`010`, `012`–`017`, `019`. *(2026-09-03, `DEF-WRK-3571`: `US-WRK-018` — the v2 publish — was listed here and is `J67`'s; `J60` publishes a FIRST version and never exercises it. `US-WRK-007`, `008` and `017` ARE exercised here — steps 2, 3 and 11 — and their frontmatter now cites `J60` too.)*

## Phase 2

### `J61` · Connect → field → accept → live (extends `J27`)
**Actor:** a clerk, D. Ortiz, M. Torres · **Screens:** `Work-004` → `Work-002` →
`Work-010` → `Work-011` → `Work-012` → `Work-009` → `Work-003` → Customer · Messages ·
**Modules:** customers → work → metering → notifications
**Upstream leaves (`J27`):** `CON-26-0129` committed at step 9 with four orders from the
utility's own templates, the gate on *Meter set*; D. Ortiz has a login and a technician
profile; `WO-4902`-shaped gate order assigned to D. Ortiz for 09:15.
**The journey:** the push lands the job on the phone; D. Ortiz ticks safety, works the
tasks, records the opening read with its photograph, the customer signs, *Close job*;
`Work-009` shows it *Passed · 1 day*; M. Torres opens `Work-003`, reads *Nobody has
accepted this yet*, presses Accept.
**This journey leaves:** `accepted_by` = M. Torres; a `meter_reads` row written by
metering's own door, dated to the completion; the Electric **service** *activated* and the connection re-derived to ***Partly activated*** — Water's gate `WO-4914` is still open; *activated* names a service, and the connection's word comes from `derive_connection_state()` (this said the connection was *Activated* until 2026-09-03 — `DEF-WRK-3574`);
one audit row per act; **the letter queued and refused with its reason** (`OQ-376`).
**Assertions:** the service state does not move at Close, only at Accept (`BR-MET-110`) ·
the read carries its unit · accepting twice does nothing · the letter is not sent as
`notice` · a Billing Clerk's Accept succeeds today and the permission stub says so
(`OQ-WRK-1492`) · Lone Star Ridge's queue is empty.
**Stories:** `US-WRK-002`, `003`, `017`, `022`, `023`, `035`, `040`–`043`, `045`, `046`. *(2026-09-03, `DEF-WRK-3571`: `US-WRK-044` — the offline close — was listed here and is `J65`'s; every step of `J61` runs online.)*

### `J62` · A one-off job end to end, including the report
**Actor:** M. Torres, D. Ortiz · **Screens:** `Work-007` (New order wizard) → `Work-021`
→ `Work-010` → `Work-011` → `Work-012` → `Work-009` → `Work-032` → `Work-027` ·
**Modules:** work → customers (read) → metering (read) → tenancy (documents)
**Upstream leaves:** `77 Cedar Ct` (`A-10891`) with no build; the *Leak investigation*
template published; the rate table with Field technician `48.5000`; `Work-030`.
**The journey:** raise `WO-4832 · Leak investigation · High · due today 17:00` from the
dispatcher — **impossible today because `connection_id` is NOT NULL**; it appears Queued;
assign to D. Ortiz for 15:30 on `Work-021`; the phone gets it; the job is worked 52
minutes; closed *Passed*; accepted; the report generates.
**This journey leaves:** an order with `connection_id` NULL and `premises_id` set; an
append-only assignment history of `assign · depart · arrive`; `WO-4832-v1.pdf` reading
*0.87 h × 48.50 = 42.20* and a total that is **the sum of the rounded lines with no tax
line**; the performance tab's Leak investigation row moved by one.
**Assertions:** the anchor CHECK refuses an order with nothing · the Change effects box
precedes Save · the report is generated by Accept and never by Close · a second Accept
produces no v2 · **no journal line anywhere** (`OQ-WRK-1491`) · Lone Star Ridge's
dispatcher is empty.
**Stories:** `US-WRK-001`, `007`, `008`, `011`, `020`, `021`, `024`–`031`, `032`, `033`,
`036`, `040`–`043`, `045`–`047`, `050`, `051`, `053`, `054`.

### `J63` · A rule raises the order, and the Assets door raises another
**Actor:** the system, then a clerk · **Screens:** `Work-026` → `Work-007` → `Work-028` →
`Work-020` → Asset detail › Maintenance history · **Modules:** assets (read) → work
**Upstream leaves:** `AST-04412` · Electric meter · 1φ AMI · certification life ends Mar
2026, plus two more meters past theirs; the rule *Meter exchange programme* On.
**The journey:** the nightly sweep raises three orders *Raised by: Asset age rule*; the
next night raises none; a clerk on `AST-04412` presses *Raise work order*, picks *Meter
exchange — residential* (the only template whose asset types include this one), leaves it
unassigned.
**This journey leaves:** three rule-raised orders with `rule_id`; `WO-4908` with
`asset_id = AST-04412`, `connection_id` NULL, source *Assets*; the Maintenance history's
Work order column reading `WO-4908` where every row read a dash.
**Assertions:** the sweep is idempotent per (rule, meter) · a rule switched Off raises
nothing · `apps/assets/**` writes nothing to `work_orders` · the four `RaiseWorkOrderCheckbox`
ticks are enabled and their *Work R5* note gone (renamed and a fourth added by wave M — `DEF-WRK-4125`) · Lone Star Ridge's assets raise
nothing on Brazos Bend.
**Stories:** `US-WRK-020`, `037`, `038`.

### `J64` · A move-out's field visit, and the final read posts through the same door
**Actor:** a clerk, D. Ortiz, M. Torres · **Screens:** `Work-029` → `Work-007` →
`Work-012` → `Work-009` → the meter's history · **Modules:** customers → work → metering
**Upstream leaves:** `A-10688` · Miller, Sarah · Electric · move-out 28 Mar 2026; the
deposit on file.
**The journey:** ⚠ **STEP `date` — *Date & final reads*, the SECOND step, corrected
2026-09-05 (`DEF-WRK-3725`).** This read *"step 4"* until then, and step 4 is
`MOVE_OUT_STEPS[3]`, the SHORTFALL step: it carries `conditional: true` and renders greyed
and *skipped* whenever the account settles, so the control would have been invisible on
the ordinary move-out. **The step is named by its ID here and not by its ordinal**, which
is the defect's own wider prevention — an ordinal is what let one sentence mean two
different steps at once. Step `date` asks *Does somebody have to attend?*; the clerk ticks
the final read; step `review` closes and settles the account **exactly as today**; the
visit arrives in the dispatcher stamped *Move-out · A-10688*; the read is taken and closed; accepted; it
posts dated to the completion.
**This journey leaves:** a closed, settled account whose close did not wait; an order with
`account_id = A-10688` and `connection_id` NULL; a `field_visit` choice recorded on the
disconnect case; a `meter_reads` row dated to the visit's completion.
**Assertions:** if the raise fails the move-out still completes and says so · the visit
never re-opens or re-settles the account · *No visit needed* is a recorded value, not an
unticked box · `apps/customers/**` writes nothing to `work_orders` · the drawn copy says
*deactivate*, never *de-energise* (`CR-032`).
**Stories:** `US-WRK-003`, `039`, `046`.

### `J68` · An approved application is routed, and it closes itself when the work is done
**Actor:** a clerk, two crews, M. Torres · **Screens:** `REQ-04` → `Work-029` (the *Route*
modal) → `Work-007` → `Work-009` · **Modules:** customers → work → metering
**Upstream leaves:** an APPROVED service request at an address that resolved, with water
ticked at step 5.
**The journey:** the clerk presses *Route*; the panel offers the utility's own published
jobs for water that are NOT part of the connection sequence's build set — a request is an
application to build, so it is offered the build jobs; the clerk raises three; the request
reads *In fulfilment* and names them; each is completed and accepted over the following
days; **the request closes itself on the THIRD acceptance and not the first.**
**This journey leaves:** three orders anchored on the resolved premises, each
`source = service_request` and `source_ref = SR-…`; a request in `completed` with a
`service_request.completed_by_field_work` audit row.
**Assertions:** the request is ROUTED even when every raise fails, and says so · a request
whose address never resolved is refused before any row is written, with a five-word
sentence · closing on the first acceptance is a failure, asserted at all three.
**Stories:** `US-WRK-039`, `017`.

### `J69` · A move-in, a transfer, and a reconnect that can finally book its visit
**Actor:** a clerk · **Screens:** `MVI-01` step `start` → `TRF-01` step `finalReads` →
(the reconnect has NO screen — see below) · **Modules:** customers → work
**Upstream leaves:** a unit whose occupant has just left; a property being sold; a cut
account that has paid $8,315.00.
**The journey:** the move-in's *Start date & reads* step offers the turn-on and the new
account gets its supply booked; the transfer's *Final reads* step offers the changeover
read, anchored on the SAME account because a sale reassigns rather than creates; the
reconnect books its visit through `mark_reconnecting`.
**This journey leaves:** orders stamped `move_in` / `MVI-…`, `transfer` / `TRF-…` and
`reconnect` / `DSC-…`, each on an anchor the flow already had.
⚠ **NOT ACTIVATED, AND THE RECONNECT LEG IS NOT REACHABLE AT ALL** — `DEF-WRK-4003`:
`markReconnecting` has no client function and no caller in `07-frontend`, so the
disconnect ladder on screen stops at *schedule the cut*. The backend door is open and
tested; the leg activates when the disconnect surface builds its reconnect action.
**Assertions:** each flow completes when its raise fails and says so · `apps/customers/**`
writes no `work_orders` row · one utility's flows raise nothing on another's.
**Stories:** `US-WRK-039`, `006`.

### `J65` · The offline day, and one sync
**Actor:** D. Ortiz · **Screens:** `Work-010` → `Work-011` → `Work-012` → `Work-033` ·
**Modules:** work → tenancy (documents)
**Upstream leaves:** four jobs assigned to D. Ortiz for Sun 15 Mar (the prototype's *Wed*; 15 March 2026 is a Sunday — `DEF-WRK-3576`); the phone synced at
08:12; then no signal all day.
**The journey:** the day list reads *◍ offline · synced 08:12*; three jobs are worked and
closed with nine photographs and one out-of-range reading; the marker reads *3 jobs to
send*; the phone comes online at 17:40 and syncs once; the supervisor opens `Work-033`.
**This journey leaves:** three completed orders; nine `work_order_photo` documents, once
each, at 1,600 px; one reading flagged `in_range = false` and accepted; the sync receipts
for every item.
**Assertions:** a second sync adds nothing · a duplicate key inside the batch does not
poison the rest — **proved on PostgreSQL** · safety ticks are applied before the close
they gate · the required-photograph rule and the out-of-range rule read differently on
`Work-033` · a link to a photograph expires in four hours · Lone Star Ridge cannot fetch
one.
**Stories:** `US-WRK-023`, `040`, `041`, `044`, `045`, `048`, `049`.

### `J66` · A failed outcome → a follow-up order and a hold
**Actor:** an external crew, M. Torres · **Screens:** `Work-009` → `Work-002` →
`Work-001` · **Modules:** work → metering
**Upstream leaves:** `CON-26-0117` · `500 Main St` · 25 units · Partly activated; `WO-4907
· Pressure test and light-up 🚩 · Gas · External · waits for WO-4906`.
**The journey:** the crew's result arrives *Failed · pressure test failed at 2.1 bar*;
M. Torres accepts it.
**This journey leaves:** `WO-4909` on `CON-26-0117`, `blocked_by = WO-4907`, source
*Failed outcome*; the connection **On hold** with the reason in Waiting on; `Work-002`
reading *5 of 8*.
**Assertions:** a *passed* outcome raises nothing · the follow-up failing rolls the whole
acceptance back and the order stays in the queue · hold outranks progress in the derived
state (§9.1) · a failed one-off job with no connection gets a follow-up and no hold.
**Stories:** `US-WRK-034`.

### `J67` · Template v2 leaves the field work untouched
**Actor:** M. Torres · **Screens:** `Work-022` → `Work-017` → `Work-008` · **Modules:** work
**Upstream leaves:** `ST-0002` *Meter exchange — residential* v1 (6 tasks) with four orders
in the field, one of them on D. Ortiz's phone. *(2026-09-03, `DEF-WRK-3572`: the seed's v1-only state, not `J60`'s output — see `J60`'s note and `US-WRK-006` §4. The drawn *v2 · 31* below is a month of raises AFTER the publish; at the moment of publish v2 holds **0** orders and the count moves with `J63`'s and `J62`'s raises — `J67` steps 5–6.)*
**The journey:** publish v2 adding *Apply tamper seal*; the Versions tab reads *v2 · 31 ·
Current* over *v1 · 4 · Superseded*; open one of the four v1 orders.
**This journey leaves:** two versions; 35 orders each stamped with the version it was
raised from; **the four v1 orders still show six tasks**; D. Ortiz's phone still shows six.
**Assertions:** Delete is refused while any version is referenced · Deactivate stops new
orders and leaves the 35 readable · a v1 order's task table has no FK to the template's ·
the consequence box on `Work-017` says it before the button.
**Stories:** `US-WRK-015`, `016`, `018`, `032`.

---

## Journey → phase → story index

| J | Journey | Phase | Stories |
|---|---|---|---|
| `J60` | Settings → published template → proposed at step 6 | 1 | `US-WRK-007`–`010`, `012`–`017`, `019` |
| `J61` | Connect → field → accept → live (extends `J27`) | 2 | `US-WRK-002`, `003`, `017`, `022`, `023`, `035`, `040`–`043`, `045`, `046` |
| `J62` | A one-off job end to end, with the report | 2 | `US-WRK-001`, `007`, `008`, `011`, `020`, `021`, `024`–`033`, `036`, `040`–`043`, `045`–`047`, `050`, `051`, `053`, `054` |
| `J63` | Rule-raised order + the Assets door | 2 | `US-WRK-020`, `037`, `038` |
| `J64` | Move-out field visit → the read posts | 2 | `US-WRK-003`, `039`, `046` |
| `J65` | The offline day and one sync | 2 | `US-WRK-023`, `040`, `041`, `044`, `045`, `048`, `049` |
| `J66` | Failed outcome → follow-up and hold | 2 | `US-WRK-034` |
| `J67` | Template v2 leaves field work untouched | 2 | `US-WRK-015`, `016`, `018`, `032` |

**Phase 0 has no journey of its own** — its exit test (*a clerk records a leak
investigation on an existing meter, holds it, releases it, and it appears in the approval
queue*) is the first half of `J62` and the last screen of `J61`, and `CR-070` §11 says it
is proved *"on a deployed build, not a green suite."* *(The CR's sentence put hold and release on the leak investigation, which has no connection to hold; it was amended 2026-09-03 to name the two proofs — `DEF-WRK-3600`.)*
