# J-MVI-NINETEEN — nineteen move-in scenarios, one table, one command

---
id: JMVININETEEN
tier: 1
rules: [BR-CUS-017, BR-CUS-021, BR-CUS-022, BR-CUS-023, BR-CUS-025, BR-CUS-037,
        BR-CUS-050, BR-CUS-055, BR-CUS-056, BR-CUS-089, BR-CUS-090, BR-CUS-670,
        BR-CUS-1022, BR-CUS-1024, BR-CUS-1101, BR-MET-062, BR-RAT-007, BR-SHL-019]
stories: [US-CUS-004, US-CUS-007, US-PAY-002, US-LED-004]
# ⚠ **THIS IS A COMMITMENT, NOT A DESIGN.** The Product Owner specified these
# nineteen scenarios on 2026-09-19 — six money branches, five refusals and eight
# representative shapes — and one design requirement above all of them. It is
# written here rather than left in a chat window because a commitment that lives
# only in a conversation is the context leak hard-won law 10 exists to stop.
# ⚠ **ACTIVE.** It runs today and it is PARTLY RED on purpose; see *What red
# means* below.
---

> ⚠ **PAGE NUMBERS BELOW ARE THE 281-PAGE EDITION** of
> `05-prototype/02 Accounts Menu Blueprint.pdf` (on the branch at `74a2e6b52`).
> The move-in wizard is **p070–p076**. It was p067–p073 in the 242-page edition,
> and the conformance record in `04-docs/05-modules/03-customers/conformance/`
> still cites those older numbers — its READINGS hold, its CITATIONS are stale.
> Read the pages AS IMAGES (B14 rule 42):
> `python3 10-scripts/pdf/pdf_render.py "05-prototype/02 Accounts Menu Blueprint.pdf" <outdir> 2.6 70,71,72,73,74,75,76`

## ⚠ THE WIZARD GAINED A STEP ON 2026-09-25 AND THE NINETEEN DID NOT

`BR-CUS-1101` (PO ruling 2026-09-25) added **step 2 · Services** — *which of
this unit's services does this account take* — so the flow is **seven steps**
and Customer, Start & read, Account preferences, Deposit and Review each moved
along by one. **Nothing in the nineteen below navigates by a step NUMBER**, so
they are unaffected; the page citations above are the blueprint's and the
blueprint draws six, because **no page of it draws a services step at all.**

⛔ **A TWENTIETH SCENARIO IS OWED AND IS NOT HERE.** The nineteen are a PO
commitment and this lane did not add to them on its own authority. What the
services step does have is its own browser walk —
`10-scripts/br_cus_1101_move_in_services_walkthrough.mjs`, nine checks with the
screenshots md5'd against each other — and `US-CUS-004` TC-8..TC-11. **Say so
when the nineteen are next put to the PO**: the subset is proved, and it is
proved somewhere else.

## The design requirement, in the PO's own words

> *"Otherwise scenario twelve gets a check that scenario three doesn't, and
> nobody notices."*

**So this is ONE TABLE THAT A RUNNER ITERATES, not nineteen hand-written walks.**
Every row declares its setup, its inputs and a verdict for **every one of eleven
dimensions**. `declares()` refuses an incomplete row at import time, so a
half-declared scenario cannot be collected, run and counted as a pass over
checks nobody wrote. A row with nothing to say about a dimension says so in a
printed sentence — `Silent("why")` — rather than omitting the key.

The eleven: **outcome · refusal_name · payment_rows · journal_pair ·
deposit_register · readings · unit_occupied · move_record · customer_link ·
field_homes · friction.**

## How to run it

    ./10-scripts/move_in_nineteen.sh                # the nineteen, and the report
    ./10-scripts/move_in_nineteen.sh --prove-red    # break two, show red, restore
    ./10-scripts/move_in_nineteen.sh M4 S5          # named scenarios only

The suite itself is `06-backend/tests/test_move_in_nineteen_scenarios.py`, run
under `--ds=config.settings.pgtest --reuse-db` with `JOBS_EAGER=false`.

## What red means

**This walk is written against what the drawing and the signed rules PROMISE,
not against what the product does today**, so it is a to-do list that runs:
every red row names something that is not built. **An assertion is never
weakened to reach green.** Moving a row needs a ruling behind it, written down
first.

## Safety — and why the beta is never opened

**A move-in COMMITS.** It opens an account, takes money, writes readings and
posts to the ledger. Readings are append-only and payments and journal lines are
under CLAUDE.md hard rule 4, and the database enforces it —
`trg_payment_immutable`, `meter_reads_value_immutable` and eleven more triggers
refuse a DELETE outright. **There is no undo.**

So the throwaway utility is a whole PostgreSQL DATABASE and not a tenant inside
the live one: `config.settings.pgtest` puts the run on
`test_sbh_<checkout>_<digest>`, each scenario provisions its OWN tenant through
the real signup path, and `django_db` rolls the graph back when the scenario
ends. The beta database named in `DATABASE_URL` is opened for exactly one thing
— a READ-ONLY count, before and after, printed both times. Hard-won law 1: a
comment claiming a guarantee is not the guarantee.

## The nineteen

### MONEY — all six, exhaustive, because this is where damage is irreversible

| | Scenario | Must be true afterwards, READ BACK FROM POSTGRESQL |
|---|---|---|
| **M1** | deposit taken now · cash · clearing date today | a payment row · the journal pair **DR undeposited / CR 2300** · `deposit_on_file` matching |
| **M2** | taken now · cheque · **clearing date BLANK** | the payment row is REAL and **the account reads a deposit of $0.00** — p074's own red sentence |
| **M3** | *"No — send it with the first bill"* | **no payment row at all** |
| **M4** | amount taken LESS than the deposit | an open balance — **not a waiver and not a refusal** (`BR-CUS-090`) |
| **M5** | no deposit | no payment, no journal line |
| **M6** | **Waive it** | does it REFUSE a clerk who is not a supervisor? p073 draws *Waive it (needs a supervisor)* |

### REFUSALS — all five, and each must refuse BY NAME rather than silently

| | The product must say no when | It answers |
|---|---|---|
| **R1** | the start date is earlier than the outgoing account's close | `customers.account.start_on_prior_move_day` · `BR-CUS-056`, naming the earliest lawful start |
| **R2** | the unit is already occupied | `customers.account.unit_already_occupied` · `BR-CUS-017`, naming the account that holds it |
| **R3** | the customer carries no identifier | `customers.account.identity_required_person` · `BR-CUS-1024`, listing what it accepts |
| **R4** | the status would not occupy | `customers.account.status_does_not_occupy` · `BR-CUS-055` |
| **R5** | a **weak** match is asked to move money | `no_identity_match_recorded` · `BR-CUS-089`, **and it prints no figure** |

### ONE REPRESENTATIVE EACH — eight

**S1** a person · residential · rental tenant applying · multi-unit · started
from an approved service request · **S2** a **company** · commercial ·
standalone owner-occupied · a different identity test entirely: name + Tax ID,
never a date of birth or an SSN (`BR-CUS-1022`) · **S3** a unit with **no meter
at all** — p070: *"The wizard does not refuse it. Service starts, nothing can be
measured, and no metered bill can be raised until one is fitted"* · **S4** a unit
vacant 94 days, opening reads three months old · **S5** a demand register that
cannot be read AND cannot be estimated — p072: *"A demand peak is never
estimated, because the charge it drives would be disputed"* (`BR-MET-062`) ·
**S6** a builder or developer on `under_construction` · **S7** a returning
customer, **strong** match · **S8** a **senior discount claim** alongside a
deposit — and it must NEVER gate service (B18 §5.3.4).

## The two checks that matter most, on every COMMIT scenario

**1 · FIELD BY FIELD.** Every value the six steps asked for must appear on the
move record at `/moves/{ref}` afterwards. The walk reports **any field with no
home, by name and by the step it was typed on**. A clerk types a receipt number,
a why-this-amount reason, a plot reference — if it has no home, it is gone and
nobody can tell.

**2 · THE FRICTION LIST.** What a clerk has to do that they should not have to:
a field asked twice, a value re-keyed that the product already holds, a refusal
with no way out.

## Four things declared UNTESTABLE — named and printed, never silently skipped

**A scenario that cannot fail is worse than one that is not there** (law 7), so
each of these is printed on every run with its reason.

| | What | Why |
|---|---|---|
| **U1** | Deposit carry-forward | Nothing ACCEPTS one. `carry_deposit_from` is a refused field on every door and the offer carries `no_accept_path`. S7 proves the offer is made and R5 proves it is refused; **neither proves a dollar can move** |
| **U2** | Automatic discounts | `DiscountVersion.eligibility_rule` is advisory and nothing evaluates it |
| **U3** | The five customer messages | p076: ***"Everything here is queued, and nothing is sent."*** The suite counts what is QUEUED and reports the number |
| **U4** | **"Billable"** | **Attempted, and it now passes** — see below |

## U4 — the one nobody had watched happen

*Billable* is the seventh item on the PO's Approve list and the conformance
record calls it *"not proved"*. `test_u4_billable_against_a_fresh_move_in_account`
runs a bill against an account the wizard opened minutes earlier: **ready 1,
blocked none, silent none.**

Two fixture facts had to be got right first and both are recorded in the test
rather than learned twice. A published plan with **no tariff VERSION** is all an
account needs to be OPENED, so the first attempt refused under `BR-RAT-007` — an
absence the check had created itself. And `assign_unit_plan` dates an assignment
from the tenant's **today**, so a plan attached now is not in force across a
period that ended yesterday.

## Proving it can fail

`MOVE_IN_NINETEEN_BREAK=<id>:<dimension>` damages what the runner **observed**
for that one dimension before the checkers see it. Corrupting the observation
rather than the declaration is deliberate: it proves the checker really reads
PostgreSQL's answer and compares it, which inverting a verdict would not. Proved
on two dimensions — `M1:payment_rows` and `R1:refusal_name` — each going red on
exactly its own row and on nothing else, then green again when restored.

## What it found — 2026-09-19, the first run

**Fifteen green, four red**, and each red names something real:

| | What a clerk would see |
|---|---|
| **`DEF-CUS-5908`** · M6 | A billing clerk waives a deposit and the move-in commits. p073 labels the option *Waive it (needs a supervisor)* and nothing in the product names a role |
| **`DEF-CUS-5909`** · M4 | `Still to collect` is measured against the PLAN's standard figure, not against the deposit the clerk assessed. $150.00 assessed, $25.00 taken, $120.00 plan standard → the record reads **$95.00** where the review screen's own arithmetic gives **$125.00** |
| **`DEF-CUS-5910`** · S5 and the field walk | The move record cannot show a reading a clerk typed. `reads_for_unit` publishes CONSUMPTION per register and an opening read has none, so every register reads *Not estimated* and the unread chip counts two where one was unread |
| **`DEF-CUS-5912`** · S7 | A move-in that recognises a returning customer, links them and stores a `strong` tier **still warns `customer_not_linked`** — whose text says the `customers` entity has no table. It has had one since 2026-08-11 |

**Twenty-nine fields have no home on the move record**, the whole of step 4 and
almost the whole of step 5 among them: the deposit decision, the amount
assessed, *why this amount*, the due date, the tender and the receipt number.

**The friction list**, and it carries its own blind spot: every item is derived
from the PAYLOAD and the DATABASE, because this suite never opens a screen.
· One fact reaches the server under two payload keys — `contact.full_name` and
`customer.display_name`, `contact.dob` and `customer.identity.date_of_birth` —
and nothing makes the pair agree on the way in. **The screen asks once**, so
this is a divergence hazard rather than clerk friction. · The whole of step 5's
money detail is keyed and then unreadable. · The refusal
`customers.account.status_does_not_occupy` names no way out. · A move-in that
linked a customer still shows `customer_not_linked` on its confirmation. · A
request-fed move-in re-keys only the SSN and the driving licence, which is
deliberate: a request serves their last four and nothing else.

⚠ **TWO EARLIER FRICTION ITEMS WERE WRONG AND ARE RECORDED RATHER THAN
DELETED.** The first version of this list said the name and the date of birth
were *asked twice on step 2* and that a request-fed move-in *re-keys the
applicant's name* — both inferred from the payload. The screen has one box for
each, and the request prefill landed the same day this ran. **A check that
reasons about a screen it cannot see is hard-won law 7's fourth shape.**

**`billable` proved: ready 1, blocked none, silent none.**

**The beta was unchanged** — 8 service requests, 78 accounts, 74 payments, 751
journal lines and 516 readings, before and after.

## When it runs again

**Whenever the move-in wizard, the deposit capability, the move record or the
identity matcher changes.** The difference between two runs is the report.
