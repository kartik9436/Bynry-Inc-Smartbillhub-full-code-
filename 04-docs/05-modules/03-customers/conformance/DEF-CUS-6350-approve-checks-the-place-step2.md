# DEF-CUS-6350 · Approve checks the property and the unit before it is pressed — step 2

**Lane:** APPROVE-CHECKS · **Date:** 2026-09-23 · **Defects:** `DEF-CUS-6350` (the
checks), `DEF-CUS-6352` (a move-in told it raises a build; the fee line at 4 dp),
`DEF-CUS-6420` (the fee gates approval again), `DEF-CUS-6421` (a move-in approved on PostgreSQL raised no job) · **Rule:** `BR-CUS-1095`

**Rulings built, all PO 2026-09-23, verbatim in the decision log:** §4 of *"THE FEE
TABLE'S COLUMNS … AND *APPROVE* CHECKS THE PROPERTY AND UNIT BEFORE IT IS PRESSED"* ·
*"THE *APPROVE* WINDOW'S TWO LAYOUTS, APPROVED"* · *"RULED: A NEW CONNECTION ONLY WHERE
THE ADDRESS IS NOT IN PREMISES — IN ANY STATUS"* (`OQ-CUS-12615`) · *"RULED: THE MOVE-IN
APPROVAL FLOW, SIX STEPS"* (`OQ-CUS-12616`, steps 1 and 6 and the *where it went* line)
· `OQ-CUS-12617` (*"either fee is paid or waived - no other condition"*).

---

## 1 · What a clerk sees now, in plain words

Pressing **Approve** opens a window that lists every check the product runs before it
lets the request through, one line each — a tick, a cross or an exclamation mark, the
name of the check, and what it found:

```
Approve SR-26-0016 · David, Tim
What kind   [ Move-in | New connection ]
CHECKS
 ✓  Property       highland park, Ottumwa
 ✓  Unit           U-00003 · 1
 ✗  Unit free      Occupied · AC-2026-00012
 ✓  Other move-in  None waiting
 ✓  Arrears        None owed
 !  Documents      2 not checked
 ✓  Fee            $70.00 paid
 [What happens]  Opens a move-in job.
                 The account opens on move day.
                          Cancel   [ Approve ]  ← off, with "Not yet: Unit free."
```

A **new connection** shows *Address* and *Open request* instead of the four unit
checks — there is no *Unit free* row — and its button reads *Approve and raise the
build*. An address that only LOOKS like one in Premises (`highland pk` against
`highland park`) asks the clerk *Same property* or *It's a new address* before Approve
can be pressed. An unpaid fee is *✗ Fee · $45.00 unpaid — Take payment or waive it
first.* After Approve, a move-in lands the clerk on its own record (`/moves/MVI-…`), a
new connection lands in its build's wizard, and the request page says *Approved →
Move-in MVI-26-0115* as a link.

## 2 · The conditions, and the sentence each one gives

| Kind | Check (label) | ✓ fact | ✗ / ! fact | Refusal sentence (server) |
|---|---|---|---|---|
| Move-in | Property | *highland park, Ottumwa* | *Not in Premises* | *This address is not in Premises.* |
| Move-in | Unit | *U-00003 · 1* | *Not chosen yet* · *No units at this property* | *Pick the unit first.* · *This property has no units.* |
| Move-in | Unit free | *Free* | *Occupied · AC-2026-00012* | *AC-2026-00012 already occupies this unit.* |
| Move-in | Other move-in | *None waiting* | *SR-26-0013 already waiting* | *SR-26-0013 is already moving in here.* |
| New connection | Address | *New · the build adds it* (the PO's words, 2026-09-23) | *In Premises · use a move-in* · ! *"highland pk" looks like Highland Park, 58502* | *highland park is in Premises. Use a move-in.* · *This looks like …. Same place or new?* |
| New connection | Open request | *None for this address* | *SR-26-0013 already open here* | *SR-26-0013 is already open here.* |
| both | Fee | *$70.00 paid* · *Nothing owed* | *$45.00 unpaid* | *The fee is not paid. Take payment or waive it.* |

A check that cannot be asked because an earlier one failed reads **–** *Needs the
property first* / *Needs the unit first* — one problem told once, not three blockers
for one cause.

## 3 · Refusals on the processing path — counted, before and after

Counted over the catalogue keys each step can refuse with (script in this lane's
report; every key checked in `en.json` at `d28fd5c2e` and now):

| Step | Refusals | In words before | In words now |
|---|---|---|---|
| Approve (the press) | 21 | 10 existed; **1 printed a raw key** (`conditionsNotClear`), **2 printed money at 4 dp with a code and a false *"Approval is not blocked"*** (the fee pair) → **7 honest** | **21** (11 are new checks that did not exist) |
| After approval — the job could not be raised | 6 | 5; **`move_in_job_already_raised` printed its raw key** | **6** |
| Move day — the move-in wizard's commit | 8 | 8 (all rendered by the wizard's commit strip) | 8 — unchanged, not this lane's |
| **Total** | **35** | **20 of the 24 that existed; 11 of today's 35 did not exist at all** | **35 of 35** |

⚠ **What the 11 new ones replace is the important half:** before this, an occupied unit,
a second move-in for one unit and a new connection at an address already in Premises
were not refused at Approve at all — the first failed on move day as *"Another account
already occupies this unit"* (which does not say which), the second failed the same
way, and the third built a duplicate premises.

⚠ **Found and NOT changed (another lane's string):** the move-day sentence
`customers.account.unit_already_occupied` does not name the occupier though the server
sends `account_no` beside it. The US-ENGLISH lane owns existing English strings.

## 4 · Kit components — used, extended, created

* **`components/Chain.tsx` — EXTENDED** with a `noted` state (amber, `border-t-warning-500
  bg-warning-100`), with its own test. It is the shared state vocabulary.
* **`components/CheckList.tsx` — NEW kit component.** `Chain` draws a run of numbered
  STEPS in a wrapping grid with a coloured top border; a list of independent checks
  read top to bottom with a control beside a row is a different shape, and a `layout`
  prop on `Chain` would be two visual decisions under one name (B14 rule 36's
  collision). `CheckList` imports `Chain`'s `ChainCellState` so there is one
  vocabulary.
* **`SegmentedControl` (`purpose="choice"`)** for the kind — B14 names hand-rolled
  segmented controls as a breach (rule 36) and hands a form's construction to the kit
  (rule 38); no B14 rule picks a radio over a segment for two options. A refused kind
  is disabled WITH its reason (`BR-SHL-025`), none hidden.
* **`ConsequenceBox`** (staff shape, tone `check`) for the two lines (B14 rule 11).
* **`FormModal`** for the shell — its `commitBlocked` renders Approve disabled with the
  reason as announced text.
* **`RecapBox` — considered, not used:** the fee is one fact among the checks, and a
  second box repeating it would say it twice (B14 rule 32).
* `ApproveChecksModal.tsx` and `ServiceRequestJobLink.tsx` — own files (rule 43); the
  page carries only the mount. All three new files are on `route-b-migrated.txt`.

## 5 · The duplicate guard — where it lives and why

The premises a new connection creates is **metering's write** (the wizard's last button,
`BR-MET-112`), so *"is this address already in Premises?"* is metering's to answer:
`apps/metering/address_match.py` holds the one matcher (`exact` / `near` / `none`, the
owner-match shape of PO decision 3). It **reuses** `apps.integrations.gis_layer`'s street
and ZIP tidy rather than writing a third one. Customers reaches it through five seam
doors in `apps/customers/seams.py`; an unwired seam refuses to certify (*Could not check
Premises*), never reads as *not on file*. **The duplicate-unit-label guard was dropped
for new connections** — under the ruling a new connection always creates a NEW premises,
which has no units yet — and no other path in this lane needed it.

## 6 · Proof

**RED first, in pytest, the harness that runs it.** `tests/test_def_cus_6350_approve_checks.py`
run against `286458b98` (the tip without this change) in its own worktree: **25 of 25
FAILED** — 11 × `Failed: DID NOT RAISE BizError` (the product approved an occupied unit,
a second move-in, a new connection in Premises in each of four statuses, an exact match,
a near match, a second open application, and the no-unit cases), 5 × `KeyError` (no place
condition served), and the matcher cases because `apps.metering.address_match` did not
exist. On this change: **25 passed**.

**On PostgreSQL (hard-won law 14, `config.settings.pgtest`):** the check file and the fee
file — **35 passed, 1 xfailed** (the strict hold below). `DEF-CUS-6421`'s case went RED
there without the fix, verbatim: *`{'not_raised': {'code': 'job_door_refused', … 'The
move_in could not be raised: TransactionManagementError: select_for_update cannot be used
outside of a transaction.'}}`* — the same sentence the browser showed — and green with it,
beside the requested-date case (2 passed). On SQLite the affected suites: **196 passed, 1
skipped, 1 xfailed**, then **54 passed** after the move-in fix.

**Frontend:** `ApproveChecksModal.dom.test.tsx`, `ServiceRequestApproveLanding.dom.test.tsx`
(both kinds' landing asserted by ADDRESS and by the SCREEN id the route opens, under
`/:tenant/…`), `CheckList.test.tsx`, `Chain.test.tsx`, and the rewritten approve cases in
`ServiceRequestDetailPage*.test.tsx` and `serviceRequestApproveVerdicts.dom.test.tsx` —
**136 passed across 8 files** with `routeBUtilities.test.ts`; `tsc` clean.

**Cases that stated a superseded rule, FLIPPED rather than deleted (2026-09-23):**

| File | Was | Now |
|---|---|---|
| `test_cr094_approval_raises_the_job.py` | a new connection at a resolved address raised a draft against it | refused naming the property; nothing raised; no second premises |
| same | `DEF-CUS-5399`'s $130 / $25 case approved over $105.00 | refused naming **$105.00**; waiving the line releases it (leaves **−$25.00**, the counter's overage) |
| same | the move record case approved a move-in onto an occupied unit | it is a move-out request now — the one that names the leaving account |
| same (five more) | new connections at an address in Premises | the same cases at an address nobody has on file |
| `test_po20260921_application_fee_optional.py` | an unpaid $20 fee approved | refused naming $20.00; waive → approves |
| same | — | new: $130 / $25 refused naming $105.00; waive → approves |
| same | — | new, **strict xfail**: taking the $105.00 remainder → approves. Today a second collection is refused (*already collected*, one receipt per request) — the fee lanes' code; the case goes red the day it is accepted |
| `test_cr031_service_request.py` (two) | the fee reported and did not block | refused naming $25.00 / $105.00 |
| `test_def_cus_6109_an_application_becomes_a_build.py` | a resolved address raised a draft against it | refused; the two wizard-commit cases now raise their draft through metering's door directly |
| `test_br_cus_1077` / `1090` (one each) | approved a move-in before the occupant left | the occupant leaves first |

**The seed.** `sample_data._drive_cr030_request` ran submit, the decision and
the approval in ONE savepoint, so a refused approval rolled the whole row back to
`draft`. The decision and the approval now each have their own: a row the rules
refuse stops at `submitted` with its outcome decided and a log line naming why.
`Kwan, Michael` (a move-in at `88 Pine Vista`, not in a fresh tenant's Premises)
is the case; the seed test asserts it.

**The requested date.** `test_the_approved_move_in_job_carries_the_requested_date`
opens the job's own page by its `MVI-` number and reads the applicant's requested
date through the link. The CAPTURE screen writing that date is lane `REQ-FIX`'s
and had not landed at `07d75275b` — pending on it by name.

**The browser walk, on a PostgreSQL clone of the demo tenant (`sbh_clone_approvechecks`,
template `d7b6b8e5` plus one unrelated payments migration), at 1440×900, 1280×900 and
390 wide.** Planted through the product's own service doors: a move-in onto an occupied
unit, a move-in onto a free unit with a $45.00 fee not taken, a new connection at a new
address, one at `101 Silver Creek Rx` (a near match for `101 Silver Creek Rd`), and the
seeded `SR-26-0005` at `500 Main St` (in Premises). What was seen:

* every window fits 900 px high (tallest 32–747 px) and 390 px wide with no sideways scroll;
* *✗ Unit free · Occupied · AC-2026-00001* → Approve off, *Not yet: Unit free.*;
* *✗ Fee · $45.00 unpaid — Take payment or waive it first.* → Approve off; waived through
  *Record what was handed over → Waived* → *✓ Fee · Nothing owed*, Approve live;
* pressed → landed on `/moves/MVI-26-0004`, which shows *Moved in 10/01/2026* — the date
  the request asked for; back on the request, *Approved → Move-in MVI-26-0004* as a link;
* the near match asks *Same property* / *It's a new address* with Approve off (*Answer the
  address question first.*); after *It's a new address* the row reads *✓ Address · New ·
  the build adds it*;
* `500 Main St` reads *✗ Address · In Premises · use a move-in* and *– Open request ·
  Needs the address first*;
* a new connection at a new address, pressed → the New connect wizard (`NCT-01`) opened
  on its draft, applicant carried.

**It found a defect no test could, `DEF-CUS-6421`:** the first move-in pressed was
approved and raised NO job — *The job could not be opened.* The job's number was taken
with `SELECT … FOR UPDATE` after the approval had committed, which PostgreSQL refuses
outside a transaction; SQLite has no `FOR UPDATE` and every pytest case runs inside a
wrapping transaction. Fixed in `move_in_jobs.raise_for_request` (its own transaction),
with a PostgreSQL case that stands in for the committed state.

## 7 · Left, named

* The move-in wizard's first-occupant dead end (`DEF-CUS-6353`, with the PO) — the
  checks pass on a unit that has never had an account and the wizard then refuses it.
* The seeded demo rows `SR-26-0043` (a new connection at `500 Main St`, now in Premises)
  and `SR-26-0045` (a move-in with $105.00 of its fee unpaid) no longer reach *approved*
  when a tenant is seeded; the seed logs each by name and leaves it where the product
  allowed. Changing the demo fixture is its own change.
* `unit_already_occupied`'s move-day sentence does not name the account (above).
* **Taking the rest of a part-paid fee.** The window names *Take payment* as a way
  out, and the server takes ONE collection per request, so on a part-paid request
  only *Waive* works today. The fee code is lanes `REQ-FIX` / `REQ-FEE`'s; the
  strict xfail above is the hold.
* **The kind option stays offered at an address in Premises.** The *New
  connection* segment is not greyed there; the *Address* check row says *In
  Premises · use a move-in* and Approve is off with that reason. The verdict
  logic (`service_request.verdict_for`) was not changed.
* **Seen on neighbouring screens during the walk, not this lane's:** the move-in job page's
  back link reads *← The register* (the PO ruled *register* is not a clerk's word); the
  fee panel after a waiver reads *Application fee $0.00 waived. BILLERR* — a raw reason
  code and $0.00 where $45.00 was waived (the fee lanes' component).
* **`request_jobs._raise_connection`'s resolved-premises branch** is no longer
  reached from Approve (the check refuses first). It is kept because metering's
  door still takes a premises and live drafts from before today carry one.
