# CR-044 — One-time bill · Budget bills · Fix a bill: the three workflows, defined

**Status:** DESIGN — put to the Product Owner 2026-08-27, not yet ratified.
**Change:** `12-governance/11-change-requests.md` → CR-044.
**Lane block:** DEF-1180–1219 · OQ-640–659 · BR-\<MOD\>-270–289
(`12-governance/14-id-reservations.md`).

The PO's sentence, verbatim, and it names five things:

> *"One time bill, budget bill, fix bill, can you define suer friendly process -
> workflows - that take carae of bill generation data, steps, data colelctions,
> impact of such action on finance, reading open balance etc - you also need to
> fien UI for it as per tailwind components - test it it works"*

**bill generation data · steps · data collection · impact on finance · reading
open balance.** Each of the three sections below answers all five, in that order.

---

## 0 · What is true before any of this is built

All three tabs already exist and are partly working — 736 / 491 / 679 lines,
4 / 8 / 9 endpoints wired. **None of them is a stub and none of them is a
workflow.** Each states, in its own shipped copy, the one thing that stops it:

| Tab | Blocked on | Its own words |
|---|---|---|
| One-time bill | **a RULE the PO has not given** | *"The due date comes from the billing cycle's payment terms, and a one-time bill belongs to no cycle — so there is no rule yet for when it falls due, and a guessed due date would decide when a late fee starts."* |
| Budget bills | **what it calls MISSING DATA** | *"No account records which plan it is on, so there is nothing to work through."* |
| Fix a bill | **a SCOPE decision** | *"Cancelling a bill outright is a different act with its own rule and is not offered here."* |

⚠ **ONE OF THOSE THREE SENTENCES IS NO LONGER TRUE, AND THIS DESIGN IS WHERE
THAT SURFACED — see §2.0 and DEF-1180.** The Budget-bills blocker is a WIRING
gap, not a data gap: the account→unit→plan chain is in the schema and both ends
are already published. That changes what has to be asked of the PO from *"what
data do we add"* to *"is derivation the rule"* (OQ-640), which is a much smaller
question and a much larger amount of already-buildable work.

### 0.1 The house shape every one of the three uses

* `WizardFrame` (`07-frontend/src/components/WizardFrame.tsx`) — the numbered
  rail, back-clickable completed steps, values retained on a back-jump.
* **BR-SHL-018** — Continue only when the step is complete. A refused Continue
  **renders a sentence at the button that refused it** (DEF-178/DEF-936): a
  `WizardStep.validate` returning a STRING is what the frame says.
* **BR-SHL-019** — **ONE transactional commit per wizard.** A step that writes
  on Continue writes its OWN step's row (a case, a preview, a draft); the money
  commit is the final ✓ and there is exactly one.
* **B14 rule 2** — one primary control per step.
* **B14 rule 11** — a consequence preview before every money commit.
* **B14 rule 6** — a destructive commit is the danger tier (`commitVariant`).
* **B14 rule 21** — Tailwind utilities only, and ⚠ **only in a file listed in
  `07-frontend/src/styles/route-b-migrated.txt`.** All three tabs ARE listed
  (lines 2284–2286); a NEW file is not until it is added (DEF-974).

### 0.2 The rule that bounds all three data-collection sections

The product already states it on screen, and it is not negotiable here:

> *"Charge lines are never typed by hand on any bill. Every line comes from the
> customer's plan or from one of your charge codes."*
> — BR-BIL-020, repeated by BR-BIL-023 (*computed amounts are NEVER
> hand-editable*).

The enforcement in the shipped code is **structural, not a disabled input**:
`OneTimeBody` has no amount member, the screen has no amount field, and the
server takes no such parameter. **The workflow's job is to make picking a charge
code easy, not to reopen free text.** Concretely, that is the difference between
a clerk typing `1200.00 · "tamper"` and a clerk picking the **TAMPER** charge
code, which carries `$500.00`, its non-taxable treatment and its GL account
(WE-11's `$626.42` bill).

---

## 1 · ONE-TIME BILL — five kinds, one wizard, and the last step is blocked

**Kinds:** interim / ad-hoc (US-BIL-012) · first bill (US-BIL-010) · final bill
(US-BIL-011) · back-bill (US-BIL-013) · penalty / theft (US-BIL-014). Five
complete engines: `single.py`, `first_bill.py`, `final_bill.py`, `backbill.py`,
`penalty.py`.

### 1.1 Bill generation data — what it needs and where each field comes from

| Field | Source | Refused when |
|---|---|---|
| account | **typed** — server-side search, min 2 chars (`getAccounts`) | not chosen |
| kind | **chosen** from `ONE_TIME_KINDS` | — |
| bill date | **typed**, prefilled today (BR-BIL-070, OQ-122 option A) | — the ONLY source of a bill date here; there is no cycle to fall back to |
| period start/end | **typed** (all kinds but back-bill) | either empty |
| sub-periods | **typed, one row per unbilled period** (back-bill only, BR-BIL-018) | any row incomplete |
| reason code | **typed** (back-bill only) | empty |
| unit(s) covered | **derived** — `gather.covered_units(account)`; a MASTER account refuses rather than billing the anchor alone (DEF-571) | seam unpublished + master |
| plan & tariff version | **derived** — account → unit → `units.rate_plan_id` → `plan_rate_schedules`, priced at the version in force **for each sub-period** | no schedule → base only |
| reads / consumption | **derived** from metering, with its unit (hard rule 3); a missing read renders its REASON, never `0` | — |
| deposit held | **derived** — `payments_seam.deposit_paid_for_account` (final bill, BR-BIL-013: the deposit applies FIRST) | seam unreachable → stated absence, never `0.00` |
| charge-code lines | **picked from the charge-code catalogue** (penalty), never typed | — |
| **open balance** | **derived — §4, the shared reader** | seam unreachable → `—`, never `0.00` |
| due date | ⛔ **NO RULE — OQ-241** | always: the bill cannot be ISSUED |

### 1.2 Steps

```
1  Who and what        account · kind                      → Continue
2  When and over what  bill date · period | sub-periods + reason
                       (the shape changes with the kind)   → Continue
3  What they'd owe     preview — prices NOTHING, writes NOTHING
                       + OPEN BALANCE (§4) + deposit + estimates + groups
                                                           → Continue
4  Confirm             consequence preview, then ✓ Create the draft bill
                       ── the ONE transactional commit (BR-SHL-019)
5  Send it             ⛔ NOT BUILT — blocked on OQ-241
```

**Step 3 is where the preview lives and step 4 is where the commit lives, and
they are two steps on purpose.** Today they are two buttons on one screen; the
rule that makes them steps is BR-BIL-020's *preview → exceptions → draft →
issue*, and B14 rule 2's one-primary-per-step is what forbids `[Preview]
[Create]` sitting side by side.

**Step 5 is drawn on the rail as blocked, not omitted.** A rail that ends at 4
tells a clerk the bill is finished when it has not been sent. The step renders
OQ-241's own sentence and no control.

### 1.3 Data collection — typed · derived · refused

* **Typed:** account (search), kind, bill date, period or sub-periods, reason
  code, charge-code SELECTION.
* **Derived:** everything with a price on it. Every line comes from the plan or
  a charge code (§0.2).
* **Refused, and each refusal has a sentence:**
  * an amount, a description, a line — **there is no field, no member and no
    parameter**;
  * a back-bill as ONE span instead of sub-periods — `backbill.py` refuses to
    invent a cadence, and the reason is money: 18 kgal of water priced as one
    period puts 13 kgal in the top tier (**104.50**) where six monthly groups
    put 6 (**79.50**) — **$25.00** on one service, on a bill that foots either
    way;
  * a repeat of a bill already made — BR-BIL-005, refused with who/when/link;
  * a partial window — allowed, but it charges a FULL period's base charge
    (**$13.49** on WE-6's figures) and OQ-242 says so on screen;
  * **ISSUING** — OQ-241.

### 1.4 Impact on finance — what step 4 says before it commits

**A draft is not money (BR-BIL-004).** The consequence preview must say exactly
that, because a clerk who thinks the ✓ posted a bill will not press the button
that does:

> *"This writes a DRAFT bill for **A-11024** of **$184.20 USD** — 3 lines from
> the plan, 1 from a charge code. **Nothing posts to the ledger and the customer
> is not billed until it is issued.** This bill cannot be issued yet: there is no
> rule for when a one-time bill falls due (OQ-241)."*

The **ledger effect of the commit is nil, and that is the whole point.** Posting
happens at ISSUE, in `issue.issue_invoice`, which is where BR-BIL-035's
balance-forward block is stamped, where a carried credit is drawn down
(BR-PAY-010 — a **57.13** credit against a **184.20** bill applies **57.13** and
leaves **0.00**) and where the autopay intent is recorded (BR-PAY-015). None of
that runs on this wizard's ✓.

**Which is why OQ-241 blocks a workflow and not a screen:** the only step that
moves money is the one that cannot be built.

### 1.5 Reading open balances

On **step 3**, above the new charges, from the shared reader (§4):

> Previous balance **45.00** − payments & credits **0.00** = open **45.00**
> · this bill **247.87** → **total due 292.87** (❄️ WE-1)

An unreachable seam prints `—` on all four, never `0.00`. Zero means *this
customer owes nothing from before*; `—` means *nobody could ask* — and a bill
that told a customer in arrears they were square is what BR-BIL-160 was written
for (an account arriving owing **$8,240.00** whose first bill printed a dash).

---

## 2 · BUDGET BILLS — an enrolment workflow, and its blocker has moved

### 2.0 ⚠ The blocker is a WIRING gap, not a data gap (DEF-1180)

The tab says *"no account records which plan it is on, so there is nothing to
work through"*. **The first clause is literally true and the conclusion does not
follow.** The chain exists end to end:

```
accounts.unit_id                    (apps/billing/gather.covered_units reads it today)
  → units.rate_plan_id              (apps/metering/models.py:408 — a reviewed cross-module FK)
    → rate_plans.budget_billing     (apps/rating/models.py:128)
```

and **both ends are already published**: `metering/selectors.py:492` serves
`rate_plan_id` on a unit read, and `rating/selectors.py:421` serves
`budget_billing` on a plan read. What is genuinely missing is one seam function
in `apps/billing/rating_seam.py` — which names no budget callable at all — and
one join. This is **hard-won law 2 ("built is not wired")** and it is what
DEF-476 half-said in August: *"the SEAM and the account-to-plan link are not"*.

**The PO question this leaves is small and is OQ-640:** BR-CUS-029 says the
account plan snapshot has **no table** and *"the account derives its plan from
the unit"* — so is DERIVED eligibility the rule for enrolment, given that a
plan change on the unit then silently changes who is eligible? Registered, not
chosen.

### 2.1 Bill generation data

Budget billing does not generate a bill — **it changes what an already-generated
bill ASKS FOR**, and the distinction is the workflow's whole shape.
BR-BIL-011: *the monthly posting is the ACTUALS posting.* The level is a
**collection schedule, never a price** (WE-8).

| Field | Source |
|---|---|
| account | **typed** today (a raw id in a text box — see §2.3) |
| eligible? | **derived** — §2.0's chain, once wired (today: a staff tick, OQ-237) |
| months of history | **derived** — `getBudgetEligibility` |
| required months | **tenant setting** (BR-BIL-021 — never a default) |
| computed `level` | **derived** — trailing-12 actuals ÷ 12: **$2,904 → $242** (WE-8) |
| `level_override` | **typed**, with a reason, bounded ±30% **of the computed level** |
| `effective_level` | **derived** — what the customer actually pays |
| variance balance | **derived**, signed, carried |
| settle-up month | **tenant setting** |
| yearly-increase cap | **tenant setting**, on S69 — not this tab |

**Three figures, three columns, never collapsed into one.** BR-BIL-017 measures
the ±30% bound against the COMPUTED level, so a screen showing only *what they
pay* leaves a clerk typing an override with no way to know the bound — and three
audited 30% steps chained against each other walk a level to twice what the
trailing twelve months say.

### 2.2 Steps

```
1  Pick the account         search (not a raw uuid)         → Continue
2  Is it eligible           months of history vs required · the plan's budget
                            flag (derived, §2.0) · already enrolled?
                                                            → Continue blocked
                            with the REASON when it is not
3  The level                computed $242.00 · optional override with reason,
                            bound ±30% OF THE COMPUTED figure ($169.40–$314.60)
                                                            → Continue
4  Confirm                  consequence preview, then ✓ Enrol
                            ── the ONE commit
```

and the two **staff acts** that are not enrolment keep their own confirm
dialogs on the list, because each is a single act and not a flow:
**Re-level** (idempotent; *"we looked and it was fine"* is a real outcome and is
reported as one, not as an error), **Override**, **Remove from budget**
(danger tier, B14 rule 6).

⚠ **NOTHING DROPS ANYBODY AUTOMATICALLY.** PO 2026-08-11, verbatim: *"nodrop we
chase for payments until write off"* — BR-BIL-017's two-missed-payments drop-off
is SUPERSEDED. Removal is a staff act with a name on it and the variance balance
is **CARRIED, never dropped**.

### 2.3 Data collection

* **Typed:** the account, the override amount **as a decimal string** — never
  `Number(...)`; a `NUMERIC(18,6)` does not survive an IEEE double and the
  server refuses a float outright (hard rule 2) — and the override reason.
* **Derived:** history, level, variance, settle-up month.
* **Refused:** enrolling with no computed level (a null level renders as an
  absence and **never as `0.00`** — a zero monthly amount is a real, chooseable
  figure); an override with no reason; an override outside ±30% of the computed
  level; enrolling an already-enrolled account.
* ⚠ **A defect this design surfaces (DEF-1181): step 1 is a raw account-id
  text box.** Every other money surface in the product searches. A clerk who
  pastes the wrong uuid enrols the wrong customer at a fixed monthly amount for
  a year, and nothing on the screen would say so — the id is not shown back as a
  name.
* **Bulk enrolment and CSV import stay out** until OQ-640 is ruled. Enrolment
  fixes what a customer pays every month for a year; doing it to 312 accounts
  whose eligibility nothing has read is the expensive version of this mistake.

### 2.4 Impact on finance

The consequence preview, in plain English with the figure:

> *"**A-11024** will be asked for **$242.00 USD** every month instead of what
> they actually use. Their **actual** charges are still what posts to the ledger
> and still what is taxed — the level is a collection schedule, not a price. The
> difference accumulates as a variance balance and is settled in **March**."*

**The ledger effect, stated:** enrolment posts **nothing**. WE-8's three months
show why the variance has to be visible — July actual **292.87** against a
**242.00** level is **−50.87**; August **231.40** is **+10.60**; September
**198.75** is **+43.25**; the running balance walks **−50.87 → −40.27 → +2.98**.
The settle-up month collects or credits that balance as a **non-taxable
AR-timing line**, because revenue and tax were already recognised on the monthly
actuals.

**Removal names the carried figure with its currency.** A bare *"removed"* would
let **−40.27** vanish, and the customer still owes it.

⚠ **Two figures on this path are NOT settled and the screen must not imply they
are.** The final bill of an enrolled account is **the level only** — **$242.00**,
not **$282.27** (PO ruling, OQ-164) — and **which account the settle-up line
touches is OQ-142, OPEN**: the customer CONSUMES **$292.87** and is ASKED for
**$242.00**, and a state taxes what was consumed.

### 2.5 Reading open balances

On **step 2**, beside eligibility, from the same shared reader (§4). It is not
decoration: enrolling an account that is **$450.00** in arrears at a **$242.00**
level is a decision a clerk should make **knowing**, because the level does not
touch the arrears and the customer will carry both.

---

## 3 · FIX A BILL — the correction workflow, entirely inside hard rule 4

**Nothing on this screen edits anything.** `invoices` and `invoice_lines` are
append-only under hard rule 4 and the database refuses the UPDATE with a
trigger. A correction is **new rows**: a credit note plus a rebill, with the
original kept and linked.

### 3.0 The scope decision, proposed

The tab says *"Cancelling a bill outright is a different act with its own rule
and is not offered here."* **The proposal is: keep it out, and stop making a
clerk find that out on this screen.**

* A **correction** restates a bill that is WRONG. Its class is DERIVED from the
  reason (BR-BIL-041) and it always nets to a new pair of rows.
* A **void / cancel** says the bill should never have existed. It is
  **US-BIL-027**, it has no endpoint in this build, and its GL shape is a
  different question from a restatement's.
* They are not the same act and folding them together would put one confirm
  dialog in front of two different ledger consequences.

**What changes:** the tab stops saying it in a paragraph a clerk reads AFTER
choosing a bill, and instead offers *Cancel this bill* on the reason list as a
named, disabled choice carrying US-BIL-027 — so the answer arrives where the
question is asked. **Whether that is right is OQ-641**, because it is a scope
call and a lane may not make one.

### 3.1 Bill generation data

| Field | Source |
|---|---|
| the bill | **from the URL** (`?bill=<id>`) — S30's bill detail links here with it already chosen; also typeable |
| reason code | **chosen** from the server's catalogue |
| correction class | **DERIVED from the reason** (BR-BIL-041) and shown back in the operator's words — never sent, never picked |
| scope | `single` today; bulk is the same row with a wider scope (US-BIL-016) |
| the recomputation | **derived** — the engine re-prices from corrected inputs |
| the nine sections | **derived**, in the SERVER's `section_order` (BR-BIL-044) |
| `preview_hash` | **derived** — what approval BINDS |
| **open balance** | **derived — §4** |

### 3.2 Steps — and these are the rule, not a wizard flourish

BR-BIL-014 is *reason → scope → impact preview → approval → execution*, and
every arrow is a server round trip that writes something different:

```
1  Which bill, and why      bill · reason → the class in words, before anything
                            is sent                          → Continue
2  What it would do         OPEN the case: writes the case, its pinned bill and
                            the impact — and NO credit note, no rebill, no
                            adjustment, NO journal line. The screen says so.
                            The nine sections + the open balance (§4)
                                                             → Continue
3  Approve                  binds the exact figures on screen through
                            `preview_hash`                   → Continue
4  Execute                  consequence preview, then ✓ Execute the correction
                            ── the ONE money commit, idempotent
```

**Approve and execute stay TWO acts and are never one button.** Approval binds
the artifact (BR-BIL-044); execution is separately idempotent so a double click
cannot double-credit anybody. **Abandoning is reasoned** (BR-BIL-047) and is the
secondary control, not the primary.

⚠ **`preview_hash` is what makes step 3 a gate rather than a formality**, and it
is also the one thing a wizard could break: a clerk who back-jumps to step 1 and
re-opens the case gets a NEW hash, and an approval carrying the old one must be
refused rather than silently re-bound.

### 3.3 Data collection

* **Typed:** the bill id (or arrives in the URL), and nothing else that bears on
  money.
* **Chosen:** the reason. **The mechanism is never chosen** — it is derived and
  shown back in words (*"issues a corrected bill: the original is credited in
  full…"*), never as `restatement`.
* **Refused:** editing a line (no control exists — the storage layer would
  refuse it and the clerk would find out after typing); correcting anything but
  the LATEST bill in a chain (BR-BIL-048); executing an unapproved case;
  approving against a stale `preview_hash`; adding your own reason codes (the
  reference table is not built); **cancelling** (§3.0, OQ-641).

### 3.4 Impact on finance — the largest of the three, and the only one that posts

The consequence preview, on WE-9's own frozen figures:

> *"This credits bill **INV-2026-0731** in full — **−$247.87 USD** — and issues a
> corrected bill for **$227.95 USD**. **The customer ends up $19.92 in credit.**
> They have already paid in full, so the $19.92 carries as a credit against their
> next bill. Both are NEW records; the original bill is kept and linked. **This
> cannot be undone** — reversing it is another correction."*

**The ledger effect, in plain English with the figure:** a credit note of
**−247.87** fully reverses the original's GL stamps, and a rebill of **+227.95**
posts its own; the net movement is **$19.92** to the customer's credit. Both
sides post in balanced pairs through the ledger posting service and nothing
else writes a journal line (hard rule 5). Every record is append-only.

**The other two classes are ruled and neither touches those figures:**
**class C (goodwill)** debits a **separate write-off account** so service revenue
is never reversed — a **$25.00** credit against a **$247.30** invoice leaves
**$222.30** owing either way and what moves is the BOOKS; and concessions get
their own account, separate from bad debt (PO, *"Seperate them"*: a year-end
**$4,200** was **$1,700** given + **$2,500** uncollectable) — that account needs
a **finance re-sign** and until it exists concessions land on the seeded "Bad
debt" designation. **Class D (document-only)** reissues a corrected copy, later
reprints render the corrected one, reissues ACCUMULATE, and the balance delta is
exactly **$0.00**.

**And the rollback sentence is the SERVER's**, rendered where an *undo the batch*
button would have been (BR-BIL-047), so the reason cannot drift from the rule.

### 3.5 Reading open balances

On **step 2**, inside the existing `the_customers_balance` section — which
already renders `before → after` when the server sends it. §4's reader is what
lets it send it **for every case**, rather than only where a caller happened to
assemble it.

---

## 4 · READING OPEN BALANCES — ONE piece of work, FOUR surfaces

**This is the part of CR-044 that is not free, and it is shared.** `DEF-1081`
records that the bill run's own step 2 — the pre-flight review before 47
customers are billed — **cannot show what any of them already owes**, because
nothing gathers it. The same gather serves the three workflows above.

### 4.1 It is not a new gather. It is a reader around one that exists.

`apps/billing/payments_seam.prior_position_for_account` already computes exactly
this, and returns it as `PriorPosition`:

```
previous_balance − payments_credits == open_balance          (it FOOTS, by construction)
```

plus `bills`, `opening_balance`, `opening_settled`, `opening_buckets` and
`problems`. It takes three inputs from three modules, each asked for BY NAME
because B1 forbids one module computing another's half:

| Operand | Owner | How it is asked |
|---|---|---|
| gross totals of the account's locked bills | **billing** (its own immutable `invoices.total`) | handed in as `totals_by_invoice_id` |
| what has been allocated against them | **payments** (`allocations` is payments' row) | resolved by name inside the seam |
| the migrated opening balance | **customers** (`account_opening_buckets`) | handed in as `opening` |

**And it has exactly one caller: `issue.py:1306`.** It runs at ISSUE, for one
invoice, to stamp BR-BIL-035's balance-forward block. **Nothing can ask it about
an account** — its totals argument is built by `_prior_bill_totals(invoice)`,
which needs an invoice that does not exist yet on any of the four surfaces.

### 4.2 What to build, and where

**`06-backend/apps/billing/open_balance.py`** — a READ-ONLY module that answers
for an account instead of for an invoice:

```
open_balance_for_account(account_id)        -> AccountOpenBalance
open_balances_for_accounts(account_ids)     -> {account_id: AccountOpenBalance}
```

It assembles the same three operands (billing's locked-status totals **for the
account**, payments' allocations, customers' opening position) and delegates the
arithmetic to `prior_position_for_account` **unchanged**. It writes nothing, it
posts nothing, and it computes no money rule of its own.

**Why in billing and not in payments:** the surfaces that need it are billing's
(three tabs and the run's step 2), the seam that already asks both other modules
is billing's, and payments' own `outstandings.py` answers a different question —
*who owes, worst first*, over its own AR list, which is S34's screen and not a
per-account read.

**The four callers:**

1. `runs.py` / the bill-run step 2 preview — **DEF-1081**, the batch form
   (`open_balances_for_accounts`);
2. `one_time.py`'s preview payload — §1.5;
3. `budget_api.py`'s eligibility payload — §2.5;
4. `corrections_api.py`'s `the_customers_balance` section — §3.5.

### 4.3 The rules it must not break, and one it must state

* **`None` IS NOT `Decimal("0")`.** Zero means the customer owes nothing; None
  means nobody could ask. Every surface renders `—`, never `0.00`.
* **The current bill is never in the set by construction** — payments' read
  covers `issued` and `paid` bills only, so a draft cannot count itself. That is
  stronger than an id filter and cannot rot.
* **A negative credit position is a DEBT and is never floored to zero**
  (BR-PAY-041, PO 2026-08-11: *"Yes, it's a real debt"*).
* **Opening balance moves BOTH middle operands together.** An opening balance
  joining `previous_balance` alone would appear on bill 1, the customer would
  pay it, the payment would allocate against no invoice in the set, and **bill 2
  would ask for it again** — and every bill after it. `opening settled =
  min(credit position, opening balance)`, capped, which is why every
  non-migrated account's four figures are byte-identical to what they were
  before BR-BIL-160 and ❄️ WE-1's `45.00 − 0.00 + 247.87 = 292.87` is untouched.
* ⚠ **SUPERSEDED 2026-10-01 — `OQ-217` CLOSED (PO, option A, BR-BIL-1065): the window is the WHOLE ACCOUNT since the last bill.** What follows is the history. **The WINDOW is the open bills, and that half is UNRULED — OQ-217.**
  BR-BIL-035 signs the arithmetic and names neither operand's window. Reading
  over the still-open bills reproduces ❄️ WE-1 exactly. The consequence a
  reader must know: **a prior bill settled IN FULL leaves the set with its
  payment**, so a customer who paid last month sees `0.00 − 0.00` rather than
  `100.00 − 100.00`. The TOTAL DUE is identical either way — that is what the
  footing guarantee buys — so the question is what the two middle lines SAY, and
  it is the PO's. **Every surface stamps which basis it read under**, exactly as
  the immutable bill does, so a later reader can tell without dating the code.

---

## 5 · What this design needs from the Product Owner

| # | Question | Blocks |
|---|---|---|
| **OQ-241** | **When is a one-time bill due?** *(already open, already asked)* A cycle bill takes its due date from the cycle's payment terms; a one-time bill belongs to no cycle. Worked: a move-out final bill for **$184.20** dated **6 Aug 2026** falls due **27 Aug** under a 21-day term, **5 Sep** under 30 days, or **6 Aug** billed at period end — overdue the day it is printed. The late fee between those readings is **$8.13** (❄️ GT-8). | **§1 step 5.** Everything before it is buildable. |
| **OQ-640** | **Is budget-billing eligibility DERIVED from the unit's plan?** The chain exists and both ends are published (§2.0); BR-CUS-029 says the account plan snapshot has no table and *"the account derives its plan from the unit"*. The cost of deriving: a plan change on the unit silently changes who is eligible, on accounts already enrolled at a fixed monthly amount. | **§2 step 2**, and every bulk enrolment. |
| **OQ-641** | **Is cancelling a bill part of Fix a bill, or its own act?** Proposal in §3.0: its own act (US-BIL-027), named and disabled on the reason list so the answer arrives where the question is asked. | **§3 step 1's copy only** — the correction path itself is unblocked. |

**Nothing else in this design is blocked**, and §4 is blocked by nothing at all.

---

## 6 · Order of work

1. **§4, the shared reader** — one piece of work, four surfaces, no PO input
   needed. Closes the gathering half of DEF-1081.
2. **§2.0's wiring** — `rating_seam` budget read + the account→plan join, behind
   OQ-640 for whether it may DECIDE eligibility; it may always DISPLAY it.
3. **§1 steps 1–4 and §3 steps 1–4** as `WizardFrame` flows, once the shapes
   above are agreed.
4. **§1 step 5** when OQ-241 is ruled.

