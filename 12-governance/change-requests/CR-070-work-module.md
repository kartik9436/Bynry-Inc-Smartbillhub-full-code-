## CR-070 — The Work module: forty-nine specifications, thirty-three screens, three phases, and fifteen finished actions that no screen calls

> **⚠ READ THIS FIRST IF YOU ARE A NEW SESSION.** Built from the *SMARTBillHub Work Module Blueprint*,
> **read at `2.128.2` / `47108051` on 2026-09-03 — the version this branch is on.** That makes it the
> freshest of the three blueprints this repository works from. Everything a lane needs is here or is
> cited by a path you can open. **A fact you need and cannot find is a defect in this CR — file it,
> do not guess.**

### CR-070 · 0 · CAPTURE — the Product Owner's words, verbatim

> *"we need to build next CR"* · *"can you read this document first tell me what all changes you will
> capture and once I confirm build the CR"* · *"our priority is to write this new CR"* — 2026-09-03

**Two rulings arrived while the change list was being shown, and both are in
`12-governance/02-decision-log.md` with their full reasoning:**

1. **The module question — the one thing blocking the whole dispatcher.** Asked exactly as the
   blueprint phrases it, with no ids in it: *"Field work needs somewhere to live... (a) It becomes its
   own section of the product, owning its own records — crews, jobs, parts, schedules. (b) It becomes
   extra tabs on Assets..."* **PO verbatim: *"it will become the module itself"* — option (a).**
2. **The screen series.** **PO verbatim: *"Use Work-nnn - code for this"*.** §9 is that allocation.

### CR-070 · 0b · THE VERDICT, IN THE DOCUMENT'S OWN WORDS

> *"Forty-three requirements checked against the code, sixty-six stated absences each given a
> decision, and thirty-eight specifications nobody has started. **Almost all of it was already
> designed by the Product Owner and never built.**"*

**43 requirements checked: 12 built · 4 partly · 27 missing.**

**Same honesty discipline as the other two blueprints, arrived at independently:** 66 statements that
something does not exist, **every one given either a specification id or an out-of-scope ruling with
its reason, and no unresolved row left.** So §8 is the scope and a lane may build from it.

### CR-070 · 0c · STEP 0 — WHAT MOVED UNDER THE DOCUMENT

**Much less than for the other two, because it was read today at the version we are on.** Its own
staleness note says it could not establish the current version because this repository has no
`main` or `master` branch — **it could: we are on `2.128.2`, and both branches it saw carried that
figure.** What it could not know is that the branch has moved several times *since* its read on the
same day: today alone landed the lockbox import, multi-property payments, the landlord-paying-tenants
case, partial reversals and the screen-badge allocation. **None of those touch Work**, so its
"as built" statements about this module stand — **but re-verify each one before acting on it**, which
is what its own warning asks for and what §8's `UNVERIFIED` column exists to record.

⚠ **ONE THING IT SAYS THAT IS ALREADY OUT OF DATE:** *"Allocate screen ids beyond S90"* appears in its
decision list. **That was settled this morning** — the band was re-opened by PO ruling, `S115`–`S135`
allocated and `S136`–`S140` reserved. And it is moot for this module anyway, because ruling 2 gives
Work its own series (§9).

### CR-070 · 1 · CLASSIFY

**A new capability on a module that exists in name only.** Not a defect — nothing is broken. But
**three items inside it are defects in the precise sense of hard-won law 2, *built is not wired*, and
they are the cheapest work in this CR:**

* **Fifteen finished write actions exist in the code and no screen calls any of them** — raise an
  order, add a service, hold, release, cancel, set waiting-on, mark and close outstanding work.
* **Twenty-four starter template rows are seeded and inert**, because nothing reads them and the
  write service they need is recorded by the seeder itself as **OWED**.
* **Four Work controls ship disabled on the Assets screen.**

### CR-070 · 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**(a) The module map.** CLAUDE.md names nine code modules. **PO ruling 2026-09-03 makes `work` the
eleventh** (`portal` is the tenth under `CR-068`). Amend the module map, dated, in the same commit as
the first migration — not before, and not after.

**(b) Nothing else.** No signed figure moves. **No B4 or B5 figure is touched**: a work order captures
cost and — following the precedent asset maintenance already sets — **deliberately posts nothing to
the ledger.** That precedent is one of the five open decisions in §6; **until it is ruled, build the
capture and not the posting.**

### CR-070 · 3 · IMPACT — the ten surfaces

| Surface | Impact |
|---|---|
| **Rules** | New module rules under `BR-WRK-#####`. `BR-MET-109` already says templates are the utility's own and are developed *"in work order section"* — that is a signed rule this CR finally satisfies |
| **Schema (B2)** | **23 new tables**, plus **one change to an existing one** — see §5. All tenant-scoped, RLS policy in the same migration |
| **API (A11)** | Roughly **30 endpoints** |
| **Screens** | **33** — 9 already drawn, 24 proposed. Own series (§9) |
| **Enums (A5)** | Dispatch statuses · priorities · skills · certification types · parts categories · the three lifecycles |
| **Glossary (A16)** | *work order*, *template*, *bundle*, *crew*, *technician*, *dispatch*, *safety gate*, *approval* |
| **Open questions** | **6 decisions**, one answered today (§6) |
| **Demo fixture** | Crews, technicians with certifications, a template with tasks and readings, jobs in each lifecycle state |
| **Journeys (08-qa)** | Field → accept → live, and the phone's day |
| **Gates** | See §13 |

### CR-070 · 4 · WHAT IS ALREADY BUILT — and the one column that unblocks it

**The blueprint's highest-value sentence, and it is one migration:**

> **`connection_id` must become NULLABLE.** *"The structural blocker. Today no job can exist without a
> build above it."*

**Consequence today: *"a leak investigation or a meter exchange on an existing meter cannot be
recorded at all."*** One column. Nothing breaks; everything downstream unblocks.

**Also already there:** the fifteen write actions · the twenty-four seeded starter rows · nine drawn
screens · `BR-MET-109` · the tax table a work-order tax flag hangs off · the numbering machinery the
four Work series need · the document-generation path three document kinds reuse.

### CR-070 · 5 · SIZE

| | This CR | `CR-069` | `CR-068` |
|---|---|---|---|
| Specifications | **49** | 36 | 56 |
| Screens | **33** | 6 | 75 |
| New tables | **23** + 1 change | 5 | ~10 |
| Endpoints | ~**30** | — | — |
| Decisions needed | **6** (1 answered) | 8 (3 answered) | 9 open |
| Phases | **3** | 5 | 5 |

**Three phases rather than five, because the blueprint's own sequencing is right and phase 0 is
genuinely free.**

### CR-070 · 6 · THE SIX DECISIONS — one answered today, five open

| The decision | Blocks | Cost of getting it wrong | Status |
|---|---|---|---|
| **Own module, or tabs on Assets?** | **All of phase 2** | Table ownership and every cross-module link. ***"Moving it later is a migration across nine modules."*** | ✅ **RULED 2026-09-03: *"it will become the module itself"*** |
| **Can a parts stock table exist?** | Stock levels, reorder points | Currently parked by the Assets design. **The parts register can ship without it** | **OPEN** |
| **Does a job's cost post to the ledger?** | Parts and labour becoming money | **Asset maintenance already captures cost and deliberately never posts it — follow that precedent unless told otherwise** | **OPEN** |
| **Who can approve a work order?** | `WM-26` | **Today anyone who can reach the endpoint can approve; there is no work permission in the identity module at all** | **OPEN** |
| **Is a connection letter its own message kind?** | `WM-27` | Filing it as a notice **misclassifies it in every monthly report** | **OPEN** |
| **Screen ids beyond the band** | The nine untagged screens | Low, but grows with every screen | ✅ **MOOT — ruling 2 gives Work its own series (§9)** |

⚠ **RAISE THE FOUR OPEN ONES IN `12-governance/01-open-questions.md` WITH REAL `OQ-` NUMBERS BEFORE
ANY CODE THAT WOULD GUESS** (prime directive). None blocks phase 0. **`WM-26`'s approval question
blocks nothing until phase 2**, but the gap it names is live *now*: anyone who can reach the endpoint
can approve a job today.

### CR-070 · 7 · WHAT THE MODULE OWNS, AND WHAT IT MUST NOT TOUCH

**Under the PO's ruling, `work` owns:** crews · technicians · skills · certifications · parts
categories and the parts register · work orders and their dispatch columns · templates and their
seven child tables · assignments as an append-only history · schedules · the rules engine.

⚠ **CROSS-MODULE WRITES ARE FORBIDDEN FROM THE FIRST COMMIT** (CLAUDE.md hard rule, B2 §2). **Work
READS assets, connections, accounts and meter reads through published seams and writes none of them.**
The one place money-adjacent data crosses: **a reading captured on a job posts as a meter read — and
it goes through metering's own writer, never around it** (`WM-29`).

### CR-070 · 8 · THE FORTY-NINE SPECIFICATIONS — `WM-01`–`WM-49`

**This table is the scope.** Every status reads `UNVERIFIED` and that is deliberate — the blueprint's
own rule, and the one this repository has now met from three independent sources: **a status is filled
in from the code, never from a task list, a merged branch, or a memory of having written something.**

| Spec | Specification, and what it waits on |
|---|---|
| **WM-01** | A leak investigation or a meter exchange on an existing meter cannot be recorded at all. |
| **WM-02** | Mount the fifteen finished write actions waits on nothing |
| **WM-03** | The approval queue, across every connection waits on WM-02 |
| **WM-04** | A work order type catalogue waits on nothing |
| **WM-05** | The Settings card exists and renders arrives with Work . |
| **WM-06** | Wire the three parked Settings cards waits on nothing |
| **WM-07** | The parts register waits on WM-06 · stock levels are out of scope |
| **WM-08** | Template header columns, and one relaxed key waits on WM-04 · WM-06 |
| **WM-09** | A screen to author a template |
| **WM-10** | The seeder records that create_work_order_template is OWED. |
| **WM-11** | A service to write a template |
| **WM-12** | The only caller stamps a template id the caller supplies. |
| **WM-13** | Crews, technicians and their skills waits on WM-06 |
| **WM-14** | The dispatch columns on a work order waits on WM-01 · WM-04 · WM-05 · WM-13 |
| **WM-15** | Assignment, as an append-only history waits on WM-14 |
| **WM-16** | One list of every work order, with six filters waits on WM-01 · WM-14 |
| **WM-17** | The dispatcher screen, with bulk actions waits on WM-16 |
| **WM-18** | The order's own copies of its template waits on WM-09 · WM-14 |
| **WM-19** | The six-tab work order detail waits on WM-18 |
| **WM-20** | The three-step New order wizard waits on WM-14 · WM-16 |
| **WM-21** | The crews screen and the skills wizard waits on WM-13 |
| **WM-22** | Parts against a job waits on WM-07 · WM-18 |
| **WM-23** | The map waits on WM-16 |
| **WM-24** | One trap that will pass every test and lose data |
| **WM-25** | The shape of the gap, in one sentence |
| **WM-26** | A Work permission in the identity module waits on a PO ruling on who may approve (§15.1) |
| **WM-27** | The platform's source vocabulary has no connection in it. |
| **WM-28** | The dispatcher needs it for the Area filter. |
| **WM-29** | Readings that post as meter reads waits on WM-09 · WM-18 |
| **WM-30** | Attachments and the customer's signature waits on WM-19 |
| **WM-31** | A technician who can sign in reaches everything a clerk can. |
| **WM-32** | Today's jobs on the phone waits on WM-31 · WM-36 |
| **WM-33** | The job on the phone waits on WM-18 · WM-32 |
| **WM-34** | Safety checks block the task list — on the phone and on the server waits on WM-33 |
| **WM-35** | Out-of-range readings flag, and never refuse waits on WM-29 · WM-33 |
| **WM-36** | The only offline in the codebase is network-error handling in the API client. |
| **WM-37** | Push the order to the technician's phone on assignment waits on WM-15 · WM-32 |
| **WM-38** | The technician closes the job from the phone waits on WM-33 · WM-35 · WM-36 |
| **WM-39** | The work-order edit screen — assign, reschedule, cancel waits on WM-14 · WM-13 |
| **WM-40** | Template versions, and what v2 means waits on WM-08 · WM-10 |
| **WM-41** | The performance tab, and the Finance arrow that is refused waits on WM-14 · WM-19 · WM-22 |
| **WM-42** | Wire the four Work settings cards and the four Work number series waits on WM-05 · WM-06 · WM-07 · WM-22 |
| **WM-43** | The Assets door — one form, four ways in waits on WM-01 · WM-09 |
| **WM-44** | The Customers door — two calls from one wizard step waits on WM-01 · WM-14 |
| **WM-45** | Labour rates — per hour, overtime, dated waits on WM-13 |
| **WM-46** | Tax on a work order — one base flag, on the tax table that already ships waits on WM-45 · WM-22 |
| **WM-47** | The work-order report — generated on approval, frozen, versioned waits on WM-45 · WM-46 · WM-30 · WM-48 |
| **WM-48** | The customer's signature |
| **WM-49** | A reading’s photograph — the rule and the file are different columns waits on WM-09 · WM-30 · WM-48 |

### CR-070 · 9 · THE THIRTY-THREE SCREENS — `Work-001`–`Work-033`

**PO ruling 2026-09-03: *"Use Work-nnn - code for this"*.** Allocation is **1:1 with the blueprint's
own `WS-` labels, in its own order**, and those labels are kept as the mapping key so every
cross-reference in the source still resolves.

**`Work-` is a new id family.** Pattern `Work-\d{3,5}(?!\d)`; the five-digit ceiling of 2026-08-31
applies from birth and the lookahead is load-bearing. Zero-padded to three, chosen at birth.

⚠ **`S147` REMAINS THE NEXT FREE `S` NUMBER — this CR consumes none of them.**

| Work | Blueprint | Screen |
|---|---|---|
| **Work-001** | `WS-01` | New connects |
| **Work-002** | `WS-02` | Connection detail · Work orders tab |
| **Work-003** | `WS-03` | Work order drawer |
| **Work-004** | `WS-04` | New Connect wizard · step 6 |
| **Work-005** | `WS-05` | Work order templates |
| **Work-006** | `WS-06` | Work rail entry |
| **Work-007** | `WS-07` | Work · Orders — the dispatcher |
| **Work-008** | `WS-08` | Work · Order detail · Checklist |
| **Work-009** | `WS-09` | Work · Awaiting approval |
| **Work-010** | `WS-10` | Today · the job list on a phone |
| **Work-011** | `WS-11` | The job · safety gate, then the work |
| **Work-012** | `WS-12` | The job · readings, parts, signature, close |
| **Work-013** | `WS-13` | Work · Templates — the list |
| **Work-014** | `WS-14` | New template · step 1 of 8 — Details |
| **Work-015** | `WS-15` | New template · step 3 of 8 — Tasks |
| **Work-016** | `WS-16` | New template · step 5 of 8 — Readings |
| **Work-017** | `WS-17` | New template · step 8 of 8 — Review and publish |
| **Work-018** | `WS-18` | Settings › Configure › Reference data — the Work group |
| **Work-019** | `WS-19` | Settings › Numbering — the Work group |
| **Work-020** | `WS-20` | Assets — the four Work controls that ship disabled |
| **Work-021** | `WS-21` | Work order · Edit — assign, reschedule, cancel |
| **Work-022** | `WS-22` | Template detail — Overview · Usage · Versions · Audit |
| **Work-023** | `WS-23` | Work · Crews — the list and the certification watch |
| **Work-024** | `WS-24` | Technician detail — Overview · Jobs · Certifications · Audit |
| **Work-025** | `WS-25` | Work · Parts — stock register and issue log |
| **Work-026** | `WS-26` | Work · Rules — what raises an order without a person |
| **Work-027** | `WS-27` | Work · Performance — did the field keep its promises |
| **Work-028** | `WS-28` | Assets › Asset detail › Raise work order |
| **Work-029** | `WS-29` | Accounts › Move-out › Field visit — raising the job from Customers |
| **Work-030** | `WS-30` | Settings › Work › Labour rates |
| **Work-031** | `WS-31` | Settings › Work › Taxes that apply to a work order |
| **Work-032** | `WS-32` | The work order report — generated on approval |
| **Work-033** | `WS-33` | Work order detail › Readings — the photograph that came back |

**Next free: `Work-034`.** **Nine of the thirty-three are already drawn** (`WS-01`–`WS-09`); the other
twenty-four are proposed.

⚠ **WHETHER A `Work-` NUMBER IS EVER RENDERED ON SCREEN IS UNRULED.** The staff app's visible badge
shows r10's module id and never an `S`-id (PO ruling 2026-08-19). r10 draws nine of these and none of
the rest. **Do not point `g29_screen_ids.py` at them without a ruling.**

### CR-070 · 10 · FOLDER STRUCTURE AND HOW THIS ENTERS THE REPOSITORY

**A new Django app, `06-backend/apps/work/`** — the eleventh module, per the PO's ruling.

```
06-backend/apps/work/
  models.py          the 23 tables — orders, templates + 7 children, crews,
                     technicians, skills, certifications, parts, assignments
  migrations/        0001_initial onward. RLS FORCE in the SAME migration as
                     each table, never a follow-up
  api.py             ~30 endpoints
  services.py        writes. The 15 finished actions move here or are called
                     from here — read them before rewriting them
  selectors.py       reads
  templates_svc.py   the write service the seeder already records as OWED
  dispatch.py        assignment, scheduling, the dispatch statuses
  rules.py           what raises an order without a person
  seams/             assets_seam · metering_seam · customers_seam ·
                     tenancy_seam — READ ONLY, one file each
  sample_data.py     crews, technicians, a published template, jobs per state
```

**Frontend:** `07-frontend/src/features/work/` — the staff app's existing furniture, plus a phone
surface for `Work-010`–`Work-012`. ⚠ **Add both to `07-frontend/src/styles/route-b-migrated.txt` in
the first commit** or every Tailwind class renders as **nothing at all** while `tsc` and the tests
pass (B14 rule 21).

**Identifiers:** `BR-WRK-#####` · `EP-WRK-##` · `US-WRK-#####` · `Work-###` for screens. `WM-` and
`WS-` are kept as the document's own handles and minted into no product series, exactly as `CR-068`
keeps `CP-` and `CR-069` keeps `C-`. Docs module `04-docs/05-modules/17-work/`.

### CR-070 · 11 · THE IMPLEMENTATION PLAN — three phases, each one launchable

#### PHASE 0 — **LAUNCH: a clerk can raise, hold, cancel and close a job this week** · *no decision needed*

**The free wins, and the blueprint calls them that.** Every one is code that already exists and no
screen calls.

| # | Task |
|---|---|
| 0.1 | **Make `connection_id` NULLABLE (`WM-01`).** One migration. **Nothing breaks; everything downstream unblocks** |
| 0.2 | **Mount the fifteen finished write actions (`WM-02`)** — raise, add a service, hold, release, cancel, set waiting-on, mark and close outstanding work. ⚠ **Read them before rewriting them; they are written and tested** |
| 0.3 | **Build the approval queue (`WM-03`)** — one list of every order where `accepted_by` is null, across all connections. **No new table** |
| 0.4 | Create `apps/work/`, the docs module, the id families; add the frontend paths to the migrated list |
| 0.5 | Raise the four open decisions as real `OQ-` rows (§6) |
| 0.6 | **The click-through on a deployed build**, not a green suite |

**Exit test:** a clerk records a leak investigation on an existing meter — **which is impossible
today** — holds it, releases it, and it appears in the approval queue. ⚠ *Amended 2026-09-03 (`DEF-WRK-3600`): this sentence put two records' verbs on one subject — `hold_connection` / `release_connection` act on a CONNECTION, and a leak investigation on an existing meter has none (that is the point of `WM-01`). Read it as two proofs on one deployed build: **(a)** the leak investigation is raised on the meter, its field result arrives, and it appears in the approval queue; **(b)** a build (`CON-26-0117`) is held and released from `Work-002`. `04-flows.md` reads it as the first half of `J62` and the last screen of `J61`; demo B in `10-execution-plan.md` shows both.*

#### PHASE 1 — **LAUNCH: a utility authors its own job templates, and the wizard proposes them** · *no decision needed*

**Nothing here needs a new PO decision.** `BR-MET-109` already says templates are the utility's own
and are developed *"in work order section"*; the design exists; **the seeder itself records that the
write service is OWED.**

Six lookup tables · the parts register · the seven template child tables · the **eight-step builder
the PO designed and nobody built** · and the wizard finally reading templates so **step 6 proposes the
jobs it is named after**.

**This is where the twenty-four inert starter rows become the thing they were seeded to be.**

Specifications: `WM-04`–`WM-12`, `WM-40`, `WM-42`. Screens: `Work-013`–`Work-019`, `Work-022`.

#### PHASE 2 — **LAUNCH: a dispatcher assigns work to a crew, and the technician works it on a phone**

**The bulk of the work, and it is unblocked as of today's ruling.**

Workforce tables · assignment as append-only history · scheduling · dispatch statuses · the six-tab
order detail · bulk actions · the map · the rules engine · **the technician's phone** — the day list,
the safety gate that blocks the task list *on the phone and on the server*, readings that post as
meter reads, parts, the customer's signature, and closing the job.

Specifications: `WM-13`–`WM-39`, `WM-41`, `WM-43`–`WM-49`. Screens: `Work-007`–`Work-012`,
`Work-020`–`Work-021`, `Work-023`–`Work-033`.

⚠ **`WM-24` IS NAMED BY THE BLUEPRINT AS *"one trap that will pass every test and lose data"*.** Read
that specification in full before writing the offline queue. ⚠ **And `WM-34`'s safety gate must be
enforced on the SERVER as well as the phone** — a gate only the phone honours is not a gate.

### CR-070 · 12 · GATES

| Gate | What it asserts |
|---|---|
| **Work writes no other module's tables** | The PO's ruling made concrete. Prove it RED by adding a direct write to `assets` |
| **The safety gate is enforced server-side** | `WM-34`. A check only the client honours is not a check |
| **Every seeded starter row has a reader** | The defect this CR fixes, turned into a guard so it cannot recur |

**Existing gates that will bite:** `g13` built-is-not-wired · `g31` declared classes · `g32` refusal
keys, **baseline 0** · `g33` five-or-six words · `g07` for any 🔒 path · `g15` i18n parity.

### CR-070 · 13 · NOT IN SCOPE

**Of the 66 stated absences, those ruled out of scope carry their reason and who ruled it — read §18
of the source before proposing any of them.** Explicitly out: **stock levels and reorder points**
(parked by the Assets design; the register ships without them) and **posting a job's cost to the
ledger** (follow asset maintenance's precedent until ruled otherwise).

### CR-070 · 14 · VERSION · 15 · ROLLBACK

Change **70**. Each phase gets its own version and changelog entry.

**Phase 0 rolls back cleanly** — a nullable column and some mounted buttons. **Phase 1 onward does
not**: a utility that has authored templates has content that matters. From phase 1, rollback is
*hide the section and keep the data*, never *drop the tables*.

### CR-070 · 16 · HANDOVER

**Not in this CR and you will need it:** the source blueprint's 62 tables of detail, its nine drawn
screens, the field-by-field data model in its §8, and the three lifecycles in its §9. **Read it before
phase 1.**

**Relied on and verified:** the module ruling and the screen-series ruling are in the decision log with
their reasoning · `S147` is untouched · the fifteen actions and the twenty-four seeded rows are the
blueprint's own findings and are the first thing to re-verify in phase 0.

---

## Where the module lives — written 2026-09-03

**`04-docs/05-modules/16-work/`** — not the `17-work/` §10 names (`DEF-WRK-3547`; the text above is left
standing and stamped here rather than edited). Delivered against the approved count table: 10 epics, 54 stories,
57 rules (+22 inherited, cited), 352 test cases, 95 endpoints (94 until 2026-09-03 — `DEF-WRK-3579`), 8 journeys `J60`–`J67`, 33 screens `Work-001`–`033`,
21 wireframe images with `08-screen-layouts.md` and `09-component-inventory.md`. Eight questions `OQ-WRK-1490`–`1497`.

**Eight record errors in this CR were found while building from it and are filed, not fixed in place:**
`DEF-WRK-3542` (thirty-eight over forty-nine) · `3543` (§9's nine drawn screens are `WS-01`–`06` and `18`–`20`,
so the dispatcher, the order detail and the approval queue are NEW) · `3544` (nineteen §8 titles are not the
card's) · `3545` (§11's offline-queue warning points at `WM-24`, the rules engine; the queue is `WM-36`) · `3546`
(four changed tables, ~28 columns, not one) · `3547` (the folder) · `3548` (§6's fourth question is `OQ-376`,
already open) · `3549` (dispatched with no reservation row). Two source contradictions in the blueprint itself:
`DEF-WRK-3550` (stock levels) and `3551` (lapsed certification) — each now an open question.

**PO ruling of the day, applied:** *"Dont add Tax on work order - for now"* — `WM-46` is `US-WRK-052`
`status: blocked`, `Work-031` is not drawn, and the work-order report totals `$138.42` with no tax line.

### CR-070 · 17 · EXECUTION PLAN — written 2026-09-03

**Where it is:** `04-docs/05-modules/16-work/10-execution-plan.md`. The three phases of §11 are kept with their
launch sentences — *a clerk can raise, hold, cancel and close a job this week* · *a utility authors its own job
templates, and the wizard proposes them* · *a dispatcher assigns work to a crew, and the technician works it on a
phone*. **14 waves (A–N) · 105 tasks**, each task one r11 part (`2a` backend · `2b` frontend · `2c` tests + data ·
`2d` prove it, plus ground / gate / doc / review / version), each wave ending in a **five-to-eight-step
demonstration clicked in the running product** and a version bump (PO 2026-09-03: *"each phase/wave should produce
tangila eoutcome"*). Every one of the 54 stories `US-WRK-001`–`054` is placed in exactly one wave, the three blocked
by a question and the one closed by the tax ruling included — a boundary is demonstrated like anything else.
**Definition of done (PO 2026-09-03, *"based on actual code, and rules that we place … web walkthorugh before you
sign off"*):** every task's *touches* was verified against the code at HEAD `f02400b3` (the plan's §1 lists where
the documentation and the code disagreed — the code won); every wave's exit test asserts a rule; every wave's `2d`
task is a Playwright walkthrough `10-scripts/render-checks/cr070-<wave>-<slug>.mjs` asserting the on-screen
sentences against this module's own `wireframes/` (PO: *"refer to screenshot we build and not just r10"*), with the
two drawings that contradict their cards (`DEF-WRK-3550`, `DEF-WRK-3551`) asserted for what they must NOT show.
**Critical path:** A → B reaches the phase-0 launch (about three and a half weeks, two people); A → C → D → E the
phase-1 launch (about seven and a half weeks); A → C → F → G → H → J → K → L the phase-2 launch (about fourteen and
a half weeks along the spine, with B, D, E, I, M and N off it). **Blocked to a boundary and still demonstrated:**
`022 · 023 · 035 · 052`, and one branch each of `010 · 021 · 031 · 048 · 050 · 054`; six tasks (`C7`, `F8`, `I6`,
`K7`, `L9`, `N9`) wait for a ruling before they can start. Eight record errors in this CR (`DEF-WRK-3542`–`3549`)
are corrected in the module's own documents, which the plan builds from; the tax card `WM-46` is not planned.
The TSV rows for `20-wave-tasks.tsv` were generated from the plan file and handed to the merging lane; the plan is
not yet reflected in `19-execution-sequence.md`.


---

# CR-070 · §W — the connection ruling, FOLDED IN HERE BY PO RULING 2026-09-04

**PO verbatim, on being shown this written up as a change request of its own:**

> *"why are you wirting Cr 72 - it should be part of CR 70 itself - all changes related to work orders"*

**Taken, and it is right for a reason worth stating rather than just obeying.** The ruling below is
about where a person goes to see a build's progress, its units, its work orders and its charges. The
answer — *the account, not a parallel screen* — is a statement about **where a work order is reached
from**, and that is this change request's subject. A second CR would have split one decision across
two records, and the next agent reading `CR-070` would have found the plan without the ruling that
reshapes it.

**What that changes mechanically:** `CR-072` was allocated as a file and **was never entered in the
change register** — so the register's *"next free number"* is still `CR-072`, untouched, and the id
is neither reused nor renumbered. `12-governance/change-requests/CR-072-connection-equals-account.md`
is gone; everything it held is below, word for word, as **§W**. The four files that cited it are
updated in the same commit.

**What it does NOT change:** every ruling below stands exactly as the PO made it. Folding is a filing
decision, not a re-opening — `CR-070 §W.8`'s supersession of B18, `§W.10`'s *one screen too many, not
one table too many*, and `§W.12`'s standing instruction are all in force and are all quoted verbatim.

## CR-070 · W — *"There is nothing called connections; Connection = Account"* — and what that collides with

**Status: RULED. `B18 §5.4` IS SUPERSEDED.** The design document is not the authority here; the product is.

#### CR-070 · W · 0 · CAPTURE — the Product Owner's words, verbatim

Four messages, 2026-09-04, in the working session, while looking at the **Work orders list (`WRK-01`)** and the
**connection detail (`NCT-02`, `/connections/<uuid>`, `CON-26-0117`)** side by side:

> *"youa re duplcaiting this - there is nothing called as conenctions; Connection = Account only - you cannot
> have two differnt screen - this is an integration problem"*

> *"Work module is within the platform/product and it interact with premsies, Units, Assets, Accoutns, plan &
> rates etc"*

> *"It also conenct to Servcie request, it also conenct to new connect, MOve out meter reads wtc"*

#### CR-070 · W · 1 · WHAT THE PRODUCT ACTUALLY HAS TODAY

`06-backend/apps/metering/connections.py:460`, the model's own docstring, verbatim:

> *"One build — B18 §5.4. **Creates infrastructure; may finish with no account.**"*

So in the built product a `connection` is **a construction job at an address** — a developer's twenty-five-unit
build, tracked from request through units, meters, plans and activation — and it is deliberately NOT an account:
the whole point of the sentence above is that a build can complete and leave no account behind.

An `Account`, by contrast, is a customer's billing relationship. Since `CR-056` W1 it need not even name a unit:
a **Master Account is the owner's account at an address**.

**These are two different things in the code.** Whether they should be two different things in the PRODUCT is
exactly what this change request is about, and it is not ours to decide.

#### CR-070 · W · 2 · THE SIGNED STATEMENT THIS WOULD REVERSE

⚠ **WE DID NOT INVENT `connection`. It comes from a signed design document** —
`04-docs/02-decisions/18-cr030-onboarding-design.md`, **B18 · CR-030 Consumer onboarding**, whose §5.4 specifies
the entity, its eight tabs, its numbering series and its per-service state machine. Every screen the PO is
looking at was built to that document.

**So this is a reversal of B18, not a correction of a mistake we made**, and the change process (§2) says a
reversal must be stated with its supersedes chain rather than assumed. That is why this file exists before any
code moves.

#### CR-070 · W · 3 · IMPACT, MEASURED RATHER THAN ESTIMATED

Counted at the branch tip on 2026-09-04:

| Surface | Reach |
|---|---|
| Backend Python files naming `Connection` | **29** |
| Front-end files naming `connection` | **108** |
| Database tables | **3** (`connections`, `connection_services`, `connection_todos`) |
| Epic files whose stories mention it | **47** |
| Screens | the New Connect wizard (`NCT-01`), the connection detail and its six tabs (`NCT-02`), and a `CONNECTION` column on the Work orders list |
| Work module | `work_orders.connection_id` is one of the four anchors `CR-070` wave A added, and wave B's fourteen acts are all acts **on a connection** |

#### CR-070 · W · 4 · THE TWO READINGS, AND WHY THE DIFFERENCE IS THE WHOLE QUESTION

**Reading A — one screen, not two.** The objection is the DUPLICATE SCREEN. A person looking at *Silver Creek
Water* sees a `CON-26-0117` detail with Overview · Units · Work orders · Assets · Charges · History, and an
Account detail that shows much the same. Whatever the tables are called underneath, **a user should reach all of
it from the account**, and the build's progress becomes a section or a tab there rather than a parallel
destination. *"This is an integration problem"* reads naturally this way: we bolted a second screen on instead of
integrating into the one that existed.

**Reading B — the record should not exist.** `connections` is not a real thing in this business; what B18 called
a build is an account from the moment it starts, and the table, its numbering and its state machine should be
folded into `accounts`.

**A is a screen and navigation change. B is a data-model migration across 3 tables, 137 files and 47 epics**, and
it also reopens what `CR-070` wave A settled last night — that a work order may stand on a connection, an
address, an account or a meter.

#### CR-070 · W · 5 · WHAT IS TRUE OF BOTH READINGS, AND IS BEING ACTED ON NOW

The Work module must integrate with the platform's own entities rather than with a private one. The PO named
them: **premises · units · assets · accounts · plans & rates · service requests · New Connect · move-out · meter
reads.** `CR-070`'s own design already says Work reads every one of those through one read-only seam file per
module and writes none of them — so this half is not a reversal, it is a direction to finish what is started and
not to deepen the `connection` dependency while the question is open.

#### CR-070 · W · 6 · WHAT IS ON HOLD

`CR-070` wave B's connection-detail action row — eight acts on a build — is the screen under discussion. Its
backend (fourteen routes) and its approval queue are unaffected and stand. The lane has been told.

**Nothing else stops.** No screen has been deleted, no table dropped, no story rewritten.

#### CR-070 · W · 7 · THE ONE QUESTION

Put to the PO in plain English, with the figure, because it is a reversal of a signed design and the two readings
differ by two orders of magnitude of work: **is this one screen too many, or one table too many?**


---

### CR-070 · W · 8 · THE RULING, AND THE STANDING INSTRUCTION THAT CAME WITH IT

**PO, 2026-09-04, answering §7 directly:**

> *"yes document may have provided it like that - but it is not correct and we have to see this in current
> context, please apply critical thinking while developing Work, Customer portal and Integration, they are part
> of product and itneract with existing fucntionalities and pull push data amousgt existing modules endpoints,
> data bases - if you ahve questions you can always ask me"*

Three things are settled by that sentence:

1. **`B18 §5.4` IS SUPERSEDED.** *"The document may have provided it like that, but it is not correct."* A signed
   design is evidence of what was agreed, not proof that it is right, and this one is being read in a context it
   was not written for. **`CR-030`'s `connection` entity does not survive as a first-class, user-facing record.**
2. **The three new modules are PART OF THE PRODUCT.** Work, the customer portal and integrations *"interact with
   existing functionalities and pull push data amongst existing modules endpoints, databases."* A new module
   that stands up its own parallel world is wrong even when the world is internally consistent.
3. **A question is cheaper than a wrong build.** *"If you have questions you can always ask me."* That does not
   licence re-asking what is already ruled (hard-won law 13); it removes the excuse for guessing at something
   only the PO knows.

### CR-070 · W · 9 · THE CRITICAL THINKING, DONE ON THE TABLE RATHER THAN THE DOCUMENT

**What a `connections` row actually holds**, read off the live database:

| Column | What it really is |
|---|---|
| `request_id` | a pointer to the **service request** |
| `premises_id` | a pointer to the **place** |
| `owner_account_id` | a pointer to the **account** |
| `state` · `submitted_at` · `held_at` · `waiting_on` · `cancelled_at` · `cancel_reason` · `activated_at` | **the request's own lifecycle**, kept a second time |
| `connection_no` | a second number for a thing that already has one |
| `mode` · `target_activation` · `quote_total` | three genuine attributes |

**Three pointers, a duplicated state machine, a duplicated number, and three real columns.** `ServiceRequest`'s
own docstring reads *"One numbered application, whatever channel it arrived by"* — which is what the state
machine above is describing. The entity is not carrying its own weight; it is carrying the request's.

**And nothing in the domain needs it.** A utility's real nouns are the **premises** and its **units**, the
**assets** on them, the **account** that is billed, the **service request** that starts things, and the **work
orders** that get them done. *New connection* is a **process over those nouns**, not a seventh noun. A
developer's twenty-five-unit build is one request, one premises, twenty-five units, many work orders and
twenty-five accounts — every one of which already exists.

**The screen follows from that.** Overview · Units · Work orders · Assets · Charges · History are all views a
person should reach from the **account** (or, for a multi-unit build, the **premises**), which is exactly the
PO's *"you cannot have two different screens."*

⚠ **AND THE PRODUCT HAD ALREADY STARTED WALKING THIS WAY WITHOUT NOTICING.** `CR-070` wave A widened a work
order last night so it can stand on **a connection, a premises, an account or an asset** — because a leak
investigation on a meter that has been in the ground for years has no build. Three of those four anchors are the
real nouns. The fourth is the one now in question.

### CR-070 · W · 10 · THE SCOPE, RULED — IT IS ONE SCREEN TOO MANY, NOT ONE TABLE TOO MANY

**PO, 2026-09-04, choosing between the two readings of §4 and naming where the work already lives:**

> *"check out new services, new connect move in move out, transfer - you will see all these requirements are
> handled their , we had a missing element work order - now it go and fit in it"*

and, adopting §4's Reading A in full:

> *"One screen too many. The objection is the duplicate destination — a person should reach the build's progress,
> its units, its work orders and its charges from the account, not from a parallel screen. Whatever the tables
> are called underneath, there is one place to look."*

⚠ **THIS SUPERSEDES THE PROPOSAL THIS FILE CARRIED FOR TWENTY MINUTES.** §9's analysis stands as analysis and is
kept — the entity really is three pointers and a duplicated lifecycle — but the conclusion it was heading for,
retiring the table and migrating 3 tables and 137 files, is **NOT what was ruled and must not be cited as if it
were.** *"Whatever the tables are called underneath"* is explicit: **`connections` survives as plumbing.** No
migration, no data question, no reopening of `CR-070` wave A's four anchors.

### What was actually missing, in the PO's words

**The flows already exist and already carry these requirements** — and they do, verified in the code:
`ServiceRequest` (`customers/models.py:1320`), `MoveRecord` (`customers/moves.py:209`), `DisconnectCase`
(`customers/disconnects.py:1259`), plus the New Connect, Move-in and Move-out wizards and their tabs in
`features/customers/`. **The missing element was the WORK ORDER**, and it *"now goes and fits in"* to them.

That is why the Work module felt like a parallel world: it was given a parallel host. The jobs belong inside
new service, new connect, move-in, move-out and transfer — where the person already is.

### CR-070 · W · 11 · WHAT THIS MEANS FOR THE WORK, CONCRETELY

**One destination.** `NCT-02` at `/connections/<uuid>` stops being a place a person navigates to. Its six tabs —
Overview · Units · Work orders · Assets · Charges · History — are reached from the **account**, and from the
**premises** where a build spans units. What the URL and the table are called underneath is not the point and is
not being changed.

**The work orders go where the work is.** Each flow gains its jobs rather than pointing at a connection screen:
new service and new connect raise and show the install jobs; move-out shows the final read and the disconnect
visit; move-in the reconnect; transfer whatever the pair needs. `CR-070` wave A already made this possible — a
work order stands on a premises, a unit, an asset or an account — so this is wiring, not new capability.

**What does NOT change:** the `connections`, `connection_services` and `connection_todos` tables; the fourteen
routes wave B landed; the approval queue; the four anchors; the New Connect wizard, which the PO named as
something Work still connects to.

**What stops:** wave B's eight-act row on `NCT-02` as a standalone destination. The acts themselves are still
wanted — on the account, where the person is.

### CR-070 · W · 12 · THE STANDING INSTRUCTION THIS LEAVES BEHIND

*"They are part of product and interact with existing functionalities and pull push data amongst existing
modules endpoints, databases."*

**Before a new module builds a screen, find the flow that already owns that moment.** Work did not need a host;
new connect, move-in, move-out and transfer were already the hosts and were already built. The failure was not
the entity — it was reaching for a new destination instead of the existing one, and it is the same failure the
PO named on the style guide an hour earlier: consistency is not a coat of paint, it is using what is there.


---

## Rulings — 2026-09-04 · shipped in `2.144.0`

**Seven closed, one answered with a question back, one not understood.** The register rows
`OQ-WRK-1490`–`1497` and `OQ-WRK-1561` carry each ruling verbatim. What changes for a lane:

* **Nothing is gated on a field visit** (`OQ-WRK-1561`). All six flows — new service, new
  connect, move-in, move-out, transfer, reconnect — complete as they do today; what is ADDED
  is a **reason the clerk types**, stored and audited. The PO's reasoning is the design:
  *"we cant stop them - it is assumed that they ahndled it manually off the record and we
  capture it in product"*. A lane must not read *reason required* as *refuse when blank*.
* **Two contradictions between the wireframes and the cards resolve in the cards' favour.**
  `DEF-WRK-3550`: no parts stock, ever — the *On hand 184 · Reorder at 60* columns and the
  reorder banner are not rendered. `DEF-WRK-3551`: a lapsed certification is a **per-tenant
  setting defaulting to warn**, so both sides are built and *blocked from 4 template types*
  renders only where blocking is on.
* **A platform constant moves.** `OQ-WRK-1495`: a rescheduled visit sends on a new source
  kind, **appointment** — ten kinds become eleven, which moves the enum, its migration, the
  eleven catalogues and every count that groups by kind. `OQ-376` is a different question and
  is not closed by this one.
* **`OQ-WRK-1496` is three rulings and only the first was asked:** twelve months' retention,
  an **export before deletion**, and **compression at capture to 100 KB**. The blueprint's
  59 GB over seven years becomes about 3.4 GB standing. ⚠ An export that does not exist is
  not a retention policy — the pruning job is written LAST and refuses while the download
  path is absent.
* **`OQ-WRK-1494` came with a question back and we answered it:** one `users` table with a
  `surface_scope` column. The web refusal ships as **“Sign in on the field app.”** — six
  words, because B14 rule 33 caps a refusal at five or six and `r10`'s seven-word sentence
  does not fit.
* **`OQ-WRK-1492` is the one that did not land** — *"I did not understand"*. It was put with
  an endpoint path, a rule id and a meter serial to ask who may press a button. The
  plain-English form is in the register verbatim and is what goes back. Nothing waits.

**Rollback:** every ruling above is recorded rather than built, except `stock_position()`'s
refusal message, which names the ruling instead of a question. Reverting `2.144.0` restores
the previous message and changes no behaviour a user can see.
