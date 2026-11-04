# J-RBS-3 — A guarded send (the ladder plans 812, refuses to send them, is approved for 400, is stopped at 120 — and the re-run queues 280 rather than 400, in a browser rather than in a unit test)

---
id: J-RBS-3
tier: 1
rules: [BR-RBS-003, BR-RBS-004, BR-RBS-005, BR-RBS-006, BR-RBS-007, BR-RBS-008, BR-RBS-009, BR-RBS-010, BR-RBS-012, BR-RBS-013, BR-RBS-014, BR-RBS-018, BR-RBS-022, BR-RBS-036]
stories: [US-RBS-010, US-RBS-011, US-RBS-012, US-RBS-013]
# ⚠ **NOT ACTIVATED, and it must not be activated against a live provider.** At HEAD
# there is no `apps/runbooks` and no `J-RBS-3.spec.ts`. Written as the HANDOFF CONTRACT
# before the code, per `CR-075`'s five-phase plan.
# ⚠ **PHASE 4 IS SPLIT AND THIS FILE SPANS BOTH HALVES.** The dry half (steps 1–7) ships
# with no writer bound and runs against real accounts in production for a full cycle; the
# live half (steps 8–12) is a one-line change to a runbook's kind afterwards.
# ⚠ **THE AUDIT-ACTOR GAP THAT USED TO BLOCK STEPS 8 ONWARD IS CLOSED (2026-09-06).**
# This paragraph said an automated action has no identity in this platform, that a blank
# actor means *a system job*, and that *"a person will appear to have personally sent 812
# letters at 07:00 on a Monday."* All three were true and none is now: `US-AUD-010` /
# `BR-AUD-019` gave `audit_log` an actor that is not a person — `actor_kind`,
# `actor_label`, `actor_version` — and a runbook writes through
# `core.audit.AutomationActor("runbook", "<name>", "<version>")`. It CANNOT borrow a staff
# login: the writer refuses a named actor carrying a user id, and so does the table.
# `TC-RBS-12` was shown red first at the pinned tip `a10eae00`, then green.
# ⚠ **WHAT REMAINS IS RUNBOOKS' OWN AND IS NOT A BLOCK ON ANYBODY ELSE:** wave `L` task
# `L2` binds a writer behind each port and passes that actor. Step 9 below still carries
# its ⛔, and it now means *"no port has a writer yet"* — not *"the platform cannot say who
# acted."*
# ⚠ **G12 REFUSES THIS `id:` — `DEF-RBS-4247`.** `VALID_JOURNEY_ID_RE` is
# `^[JT][A-Za-z0-9]*(?:-\d+)?$` and refuses `J-RBS-3`, while the wiring index's own
# `^id: ([JT]\S+)` reads it correctly. G12 is PO-ratified (G1–G16), so a lane may not
# widen it; the row carries the one-line fix.
# ⚠ **AND THE IDEMPOTENCY KEY'S STATED COMPOSITION CONTRADICTS ITS OWN WORKED EXAMPLE —
# `DEF-RBS-4246`.** See *Where two documents disagree* below; it is the single thing most
# likely to make this journey pass for the wrong reason.
#
# `rules:` and `stories:` are `04-flows.md` §5's index for `J-RBS-3` plus the four
# stories whose own frontmatter names it.
---

**Intent.** Everything dangerous about this module lives in the acting half, and this
journey is that half under a microscope. *Dunning and notices* (runbook 8, displayed as
**Collections ladder**) is the first Action and the one that returns the most hours — and
the failure that hurts is not a runbook doing nothing. It is **a misconfigured runbook
queueing three thousand wrong disconnection notices in four minutes, and a notice cannot
be unsent.** The cap, the dry run, the batch approval and the stop button are
first-release requirements, not hardening for later.

**The one assertion that would catch a wrong build is the last one: the re-run queues
280, not 400.** Everything before it — the plan, the cap refusal, the 409, the stop —
passes on a build whose idempotency key is scoped to the RUN instead of to the RECORD.
Only re-running catches that, and only in a browser is it the product's own behaviour
rather than a unit test's fixture. A build that fails this step has, in production, a
retry that sends every notice twice.

**Upstream leaves.** A tenant already past `J-RBS-1` and `J-RBS-2`: billing works, the
grid is clean, and the estate has aged into arrears.

**The ladder set: 1,004 accounts past due**, splitting exactly:

| Branch | Count | What the Review row says, in words |
|---|---|---|
| Due a notice | **812** | *First tier due* |
| On a plan in good standing | **43** | *Plan in good standing* |
| Protected | **31** | *Medical protection* |
| Undeliverable | **23** | *No deliverable address* |
| Over the fee limit — needs a person | **95** | *Over the fee limit* |

**812 to send · 97 skipped · 95 needing a person**, and **97 = 43 + 31 + 23**. Plus the
**guarded accounts**: 2 medical protection · 2 open dispute · **3 sample records**.
Runbook 8's scope: *Past due more than $5.00 · Services Water · Sewer · Cycles All ·
Account types All except Municipal · **Never include: Medical · Dispute · Sample*** —
the last row read-only and Settings-owned. Its parameters: *Ladder tiers* **from
Settings, 5 tiers** · *Grace days* **from Settings, 3** · ***Most per run* 400** ·
*Channels* Email, then post · *Quiet hours* from Settings 20:00–08:00 · *Fees need second
approval* **on** · *Runs* **Mondays 07:00**. Four of the seven are read-only because
**policy lives in Settings and is never duplicated on a card**. Actors: **the schedule**
(07:00 tenant local) · **Dana Whitfield** (approves at 07:14) · **Ray P.** (presses Stop
at 07:02 of the applying pass).

**The journey's clock.** Dry run Monday **07:00**. The cap refuses at **07:01**. Approval
**07:14**. Applying begins; Stop at **07:02** of the applying pass, at record **120 of
400**. The re-run is the same day. The concurrency leg (step 3) is a second **Run ▶**
pressed while the first is still in flight.

**Where two documents disagree, and which one this journey follows.**
* ⚠ **THE IDEMPOTENCY KEY — `DEF-RBS-4246`, and it is the one that decides whether this
  journey means anything.** `03-field-map.md` §4 gives the key as **runbook + run +
  record + action kind**, and four lines later says *"the second run of the ladder on the
  same day queues nothing, because every key it computes is already in this index"* —
  which is only possible if the **run is NOT in the key**. `TC-RBS-4` (248 in total, not
  496) needs the run out; `TC-RBS-012.1` says in terms that the build to catch is *"the
  key scoped to the run rather than to the record"*. **Three statements to one.** This
  journey follows the three and asserts the figures the pack asserts; it does not edit
  the rule, because that is `BR-RBS-008`'s to change through the change process.
* The port is drawn in figure 32 as `notifications.queue_document()` and named in the
  contract's port table as **`queue_notice`** (with `queue_receipt` beside it for a
  receipt document). **One port, two spellings, one document.** `03-field-map.md` §9
  carries the thirteen contract names, and that is the list a build lane implements.
* **Two fixtures, deliberately not reconciled.** The dry half is the **1,004-account**
  arrears set yielding **812 planned**; the idempotency and live cases use **248**. The
  source states both and never says whether they are one fixture in two states or two
  fixtures. **The lane seeds both explicitly and names which is which** — a figure quoted
  from the wrong fixture is a test that passes for the wrong reason. This journey runs on
  the 1,004 set throughout and asserts **280**, never 248; see boundary **c**.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · screen · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **Monday 07:00 · the schedule fires.** `jobs` enqueues `operations.runbook.act` in **tenant local time**, on the platform's existing job runner | One `runbook_runs` row: `trigger = schedule`, `mode = **dry**`, `version` **pinned at start**, `status = running`, and `scope_fingerprint` = **the 1,004 account ids, frozen** | ⛔ **One scheduler, not two** — integration fetches and runbook runs are job kinds on the ONE existing runner. ⛔ `TC-RBS-22`: an account that becomes past due **after** the run starts is **absent from the plan and is not acted on** — scope is resolved once and pinned (`BR-RBS-009`). ⛔ A **missed** schedule firing **RAISES** rather than silently catching up | **BR-RBS-009** · **BR-RBS-016** · `TC-RBS-22` |
| 2 | **Guards are evaluated BEFORE step 1 of the runbook** | The 2 medical-protection, 2 open-dispute and 3 sample accounts are **skipped absolutely**, whatever every later check concludes. Each reads *Skipped · Medical protection* (or its own reason) on Review | ⛔ `TC-RBS-6` **must first fail on** a guard evaluated after the checks — a build in which a "send" conclusion can outrank a protection. ⛔ `BR-RBS-014`: a sample record is **never acted on**. ✅ `RBS-004.4` draws the three guards each reading *Never touched* **with no control beside them** — guards cannot be switched off, and the tab says so rather than hiding the toggle | **BR-RBS-012** · **BR-RBS-014** · `TC-RBS-6` |
| 3 | **A second Run ▶ while the first is in flight (negative)** | **`409 runbooks.refusal.already_running`** — *Already running. Open it.* No second run row | ⛔ `RBR-08`: one run per runbook at a time. **Must first fail on** a build that starts a second run and lets two passes plan the same 1,004 accounts | `RBR-08` · `07-endpoints.md` row 7 |
| 4 | **Evaluate, per record, each in its OWN SAVEPOINT.** No writes | **1,004 `runbook_run_records`** carrying the PLAN: `planned_action` written **at evaluation, before any act**; `decided_by_rule` NOT NULL **on every row, in words a clerk can read**; `outcome` **NULL throughout the dry half, which is itself an assertion** | ⛔ **THE ONE A LANE WILL GET WRONG.** `try: … except IntegrityError: continue` is the obvious way to skip a bad row. **On PostgreSQL it does not work** — the transaction aborts, every later query raises `InFailedSqlTransaction`, and the work is lost at COMMIT. A nested `transaction.atomic()` is not the tidy option, it is the only one, **and the comment must say so or the next lane will simplify it away.** ⛔ `TC-RBS-5` is **PostgreSQL-only**: `config/settings/test.py` hardcodes in-memory SQLite, which has no aborted-transaction state, so the broken version **passes the entire suite green on every machine** (hard-won law 14). One record failing a constraint leaves the other **1,003** committed | **BR-RBS-007** · `TC-RBS-5` |
| 5 | **`RBS-005.3` · Review** | KPI strip and table read **812 to send · 97 skipped · 95 need a person**, columns **account · tier · what would happen · why**, and **every row states the rule that decided it in plain words** — *First tier due* · *Plan in good standing* · *Medical protection* · *Over the fee limit* | ⛔ **The *Why* column is what makes the run auditable by the person approving it rather than by an engineer afterwards.** ⛔ `TC-RBS-14`: no failure reason anywhere without a fix route. ⛔ **The Review table pages on the server** — 1,004 rows is the first place in this module where an unpaginated list would be tempting and would be wrong: **a cap of 400 on the ACT does not cap the PLAN** (`NFR-3`, and it does not copy the four breaches of `DEF-PAY-4221`) | **BR-RBS-004** · **BR-RBS-010** · `NFR-3` |
| 6 | **07:01 · the cap.** 812 planned against *Most per run* = **400** | `status = **awaiting_approval**` and the run **BLOCKS**. `RBS-005.7` draws the refusal card *Too many for one run* with **Narrow scope · Raise limit · Send first 400 →**. A staff alert *"A run needs you"* goes to the in-app bell — **no vendor needed**. **NOT ONE NOTICE IS QUEUED until a clerk presses one of the three** | ⛔ `TC-RBS-3` **must first fail on** a build that truncates to 400. **A cap that silently sends the first 400 is worse than no cap: it looks like it worked.** ⛔ ***Send first 400* is a deliberate choice a clerk makes, never what the system quietly did.** ⚠ `RBS-005.7`'s frame still captions itself `S151.7 · cap refused` — an internal code in clerk-facing copy; **that string must not ship** (B14 rules 31, 32) | **BR-RBS-006** · `TC-RBS-3` · B14 31, 32 |
| 7 | **The stale approval (negative).** The plan moves 812 → 806; Dana presses **Approve** carrying **812** | **`409 runbooks.refusal.plan_changed`** — *The plan changed. Review it again.* — and **nothing is queued** | ⛔ `TC-RBS-8` **must first fail on** an approval that carries no count, or one compared client-side. `approved_count` must equal the **server-side** plan count. *"A clerk who approves a plan that has since changed gets a conflict rather than a surprise."* | **BR-RBS-005** · `TC-RBS-8` |
| 8 | **07:14 · Dana approves 400.** `RBS-005.4`, the danger tier | `POST /runbooks/runs/{id}/approve {approved_count: 400}` → `status = approved` → `acting`. `approved_by` = Dana, `approved_count` = 400. The consequence box sits **directly above the commit and never after it**: *Queue 400 notices now. / Charge no fees. None are due. / **Leave 412 for next run.** / Leave 95 accounts for you.* plus the FACT line *Notices cannot be unsent* | ⛔ **Step 4 of the wizard is the one irreversible act and it uses the DANGER tier** — outlined accent, not the standard primary (B14 rule 6), so nobody is afraid to press Run and everybody reads before pressing Approve. ⛔ **The third line is the one to keep**: the cap means **412 accounts are deliberately left**, and the screen says so rather than letting a clerk discover it afterwards. ⛔ **Every money-bearing action carries a SECOND approval** with no threshold at all until `OQ-RBS-1732` is ruled — a threshold can only widen what is permitted, so shipping without one cannot be wrong in the dangerous direction. Fees this run: **$0.00** | **BR-RBS-005** · **BR-RBS-018** · B14 6, 11 · `OQ-RBS-1732` |
| 9 | **Acting, through the ports.** Each record writes through **`queue_notice`**; **`apply_fee`** is held behind the second approval and charges nothing here | Per record: **one `notifications` queue row**, **one `audit_log` row naming the runbook and its version as the actor**, and an `idempotency_key` on the run record. **The dispatcher sends; the runbook does not.** | ⛔ **BLOCKED, AND IT MUST NOT BE WORKED AROUND:** *the runbook, version 3* as an `audit_log` actor **does not exist in this platform today** (`BR-RBS-015` / `RB-011`). A blank actor means *a system job*, so every automation in the product is indistinguishable and a runbook would have to **borrow a staff login**. This must land before any Action writes anything. ⛔ **The word is *Queued*, never *Sent*** — no delivery provider is connected (PO ruling 17 August 2026) and a screen reading *Sent* is a claim that was not true. ⛔ **No Action may edit an issued invoice, a payment or a journal entry**: a ladder fee is a **new** row through billing's own service. ⚠ The three-column narrowing on `payments` (`confirmation`, `memo`, `method_id` through `POST /payments/{id}/correct-reference`) **is not a port and is not reachable from a runbook** | **BR-RBS-013** · **BR-RBS-015** · **BR-RBS-022** · hard rules 4, 7 |
| 10 | **07:02 · Ray P. presses Stop at record 120 of 400** | `status = **stopped**` (terminal), `stopped_by` = Ray P. **120 queued · 280 untouched.** `RBS-006.3` reads *Stopped by Ray P. 120 queued. 280 untouched.* with *Stopped at · 07:02* and ***Re-run would send · 280*** | ⛔ `TC-RBS-9` **must first fail on** a stop that only sets a flag nothing reads. ⛔ **Stopping halts BEFORE the next record; records already acted STAY acted** and are listed. **There is no rollback and there must not be a claim of one** — a notice already queued is a notice, and a screen saying otherwise would be a lie about the customer's world. ⛔ `TC-RBS-012.2`: the Stop control is **LIVE, not a greyed placeholder over a running run** — hard-won law 2's mirror, which `G13` cannot see. ✅ Stop is reachable at every moment: from `RBS-001`'s in-flight banner, from the wizard's Applying step, and from the result | **BR-RBS-007** · `TC-RBS-9` · `TC-RBS-012.2` |
| 11 | **THE ASSERTION THIS JOURNEY EXISTS FOR — the re-run.** The same day, the ladder runs again | **280 queued, not 400.** The 120 already queued are refused **by the database**: `UNIQUE (tenant_id, idempotency_key)` on a key of **record + action kind** (see `DEF-RBS-4246` on the run's place in it). The Done screen **names what it did not do** rather than silently doing less | ⛔ `TC-RBS-012.1` **must first fail on** *"the key scoped to the run rather than to the record"* — that build queues **400** and every earlier step in this journey still passes. ⛔ `TC-RBS-4`, on its own fixture: the ladder twice on the same day queues **248 in total, not 496**, and the second Done screen reads **0 queued** and names the 248 already sent. ⛔ **It is a UNIQUE INDEX and not application code, on purpose:** a retry arrives concurrently, and two workers each finding no row and each writing one is exactly the race an index refuses and a `SELECT`-then-`INSERT` does not | **BR-RBS-008** · `TC-RBS-012.1` · `TC-RBS-4` · hard rule 6 |
| 12 | **The trust ratchet (negative).** An admin edits the ladder and presses **Run** | A **new `runbook_versions` row**, `current_version` moves — and **Run offers only a DRY run** until one clean dry run of the new version has been reviewed | ⛔ `BR-RBS-036`. **Must first fail on** a build that lets an edited Action go straight to live, which is the exact path by which *"a misconfigured runbook queues three thousand wrong notices in four minutes"* becomes reachable in one click. ✅ A run stores the version it used, so this edit **never rewrites** the stopped run's result (`TC-RBS-13`) | **BR-RBS-036** · `TC-RBS-13` |
| 13 | **ISOLATION** — a second tenant running its own ladder on the same Monday | Two tenants' runs on the same `operations` queue carry two scope keys; **neither dedupes the other**, and neither reads a row of the other. RLS `FORCE` throughout | ⛔ **An idempotency key that omits the tenant would let one utility's run suppress another's notices** — the quietest possible failure, and the index is what refuses it. ⛔ `TC-RBS-7` **must first fail on** a scope function missing the tenant context | hard rule 1 · **BR-RBS-039** · `TC-RBS-7` |
| 14 | **INVARIANCE** | — | **The dry half wrote NOTHING outside this module's seven tables** — run it in production for a full cycle and diff the database; that is the whole point of splitting phase 4. In the live half, every write went through **`queue_notice`** or **`apply_fee`** and through no other door: **zero direct writes by `apps/runbooks/` to `notifications`, `billing`, `customers`, `metering` or `payments`**, and zero rows in `ledger`, `rating`, `tenancy` or `integrations`, which are **read-only to a runbook**. **Every money action wrote `audit_log`** (hard rule 7). Fees charged: **$0.00**, and the tile shows it even at zero, because a clerk who approved a run wants to see that figure without hunting | **BR-RBS-003** · **BR-RBS-039** · `TC-RBS-25` · hard rules 1, 4, 6, 7 |

**This journey leaves (for downstream).** One **stopped** run with 120 queued and 280
untouched, its result frozen and reopening exactly as it drew · one **re-run** that queued
**280** and named the 120 it would not repeat · **412 accounts deliberately left for the
next run**, said on screen before the commit rather than discovered after it · **95
exceptions** on `RBS-007` beside `J-RBS-1`'s findings, in one list, because *a finding
from a Check, an exception from an Action and a human task on a cutover plan are all work
and a two-person utility should read one list* · an `RBS-008` history whose ***By***
column distinguishes **Dana W.** from **Schedule** · one `runbooks` row now at version 4,
**back in dry-run mode** after the edit. **Downstream:** `EP-RBS-05`'s remaining Actions
reuse this gate, this cap, this stop and this key unchanged — *"each runbook a week rather
than a project, and no new screen."*

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | **That anything was SENT.** | Nothing leaves the building. No delivery provider is connected (PO ruling 17 August 2026) and the word on every screen here is **Queued**. A delivery provider is one of phase 4's two outside dependencies; the other is the audit actor |
| b | **The `398 queued · 2 failed` result.** | That is `RBS-006.2`, the result of a run of 400 that was **not** stopped — *Nunes, R. · No deliverable address* and *Sato, Y. · No email or postal address*, each with its fix. This journey stops at 120, so it asserts `RBS-006.3` instead. The two are different runs of the same runbook and must not be conflated |
| c | **The 248 figure.** | It belongs to the OTHER fixture — `TC-RBS-4`'s and `US-RBS-013`'s — and the pack does not say whether the 1,004 set and the 248 set are one estate in two states or two estates. **Both are seeded explicitly and named**; this journey asserts **280** on the 1,004 set and quotes 248 only where the pack does |
| d | **The default cap, the second-approval threshold, and whether a run may go unattended.** | `OQ-RBS-1731`, `OQ-RBS-1732`, `OQ-RBS-1733` — **all three OPEN and none of them blocking.** Built meanwhile, and each chosen so an answer can only WIDEN it: `cap` is a **required field with no default** (an Action cannot be enabled until an admin types one), **every** money-bearing action carries the second approval **with no threshold**, and **every run is approved by a person** with the *Unattended after* parameter drawn read-only so the absence is visible rather than silent. This journey runs on those built-meanwhile values and asserts none of them as ruled |
| e | **The cutover-plan half of the ladder's exceptions.** | `RB-035` waits on `CR-075`'s OPEN decision 7 — whether the cutover plan is a product screen now or a spreadsheet for the first two customers. The 95 exceptions land on `RBS-007` either way |
| f | **Where a fix button goes.** | Same absence as `J-RBS-1` boundary **a**: the pack names the button and never its destination screen |
| g | **That this file can be activated.** | `DEF-RBS-4247`: G12 refuses this `id:`. And phase 4 is blocked on the audit actor before its live half means anything |
