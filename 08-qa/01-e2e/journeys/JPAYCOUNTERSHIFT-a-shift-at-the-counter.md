# J-PAY-counter-shift — one clerk, one drawer, one day: 08:55 open · seventeen payments · 17:30 count · close · and it ends on Finance → Deposits

---
id: JPAYCOUNTERSHIFT
tier: 1
rules: [BR-PAY-1160, BR-PAY-1184, BR-PAY-1186, BR-PAY-025, BR-LED-025, BR-LED-796, BR-SHL-025, BR-TEN-043]
stories: [US-PAY-001, US-PAY-020, US-PAY-023]
---

<!-- `CR-136-BRC07` phase 2 `P2.17`, authored 2026-09-23 by LANE P2-TESTS.

     ⚠ **THE FILE IS NAMED FOR ITS ID AND THAT IS A RULE RATHER THAN A STYLE.**
     `G12` check 3 matches a browser spec to a journey BY FILENAME and the
     catalogue names files after ids, so a file called `J-PAY-counter-shift-…`
     declaring `id: J-PAY-counter-shift` would be unreachable by the only
     mechanism that ever activates a journey — and the id itself is not even a
     journey id under `G12`'s grammar (`^[JT][A-Za-z0-9]*(?:-\d+)?$`). Eight
     files already carry that fault (`DEF-QAE-6208`); this one does not.
     `JPAYWRONGACCT` and `JPAYLOCKBOX` set the convention: the human name is the
     TITLE line, the id is the squeezed form, the filename carries the id.

     ⚠ **EVERY FIGURE BELOW WAS MEASURED, NOT PLANNED.**
     `10-scripts/cr136_p2_17_counter_shift_readback.py` performs this exact
     shift on PostgreSQL 16 and prints what each step leaves. `J19` is in this
     catalogue as the warning: it was written from a plan, and on 2026-08-15 it
     went red at step 1 — *not on a wrong figure, on the absence of anything to
     click* (`DEF-112`). -->

**Intent.** The phase's own *done when*, walked: **a clerk opens a counter at
08:55, takes seventeen payments, closes it at 17:30 with a counted drawer**, and
the money arrives at Finance as a deposit somebody can match. It is the one
journey that touches every act in flow 3 and then leaves the module.

**Fixture.** Tenant brazos-bend · Dana Whitfield at the **Main office** counter ·
opening float **$200.00** · seventeen payments in three tenders:

| Tender | Payments | Total | Where it lands |
|---|---|---|---|
| Cash | 6 | **$510.00** | Dana's till, cash batch |
| Cheque | 8 | **$1,284.60** | Dana's till, **a SECOND batch** |
| Card | 3 | **$402.15** | **no till at all** — the day's system till |

⚠ **THE CARD THREE ARE NOT AN AWKWARD EDGE, THEY ARE THE RULING** (`CR-136-BRC07`
§3.4). Only money that passes through a person's hands — cash, cheques, money
orders — belongs to a drawer that gets counted. `record_payment` **refuses by
name** if a card is offered a till: *"putting a card swipe in a drawer would
make the close count disagree with what is physically there."*

⚠ **AND EVERY AMOUNT IS TWO DECIMAL PLACES BECAUSE THE LEDGER INSISTS.**
`BR-LED-025` (PO 2026-08-12, verbatim *"Refuse and make the caller round"*)
refuses a posting carrying more than two, and it refuses the whole payment with
it. A draft of this fixture used `$160.5750` a cheque to reach the drawn
`$1,284.60` and the FIRST cheque was refused. Eight cheques of `$160.58` and one
of `$160.54` reach the same total and can actually be taken.

| # | Time · action | Handoff contract (what this step leaves) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | **08:55** — Dana presses **Start counter →**, types the **$200.00** float and picks *Main office* (3·3a) | ONE act: a `counter_sessions` row **and its cash deposit batch**, inside one transaction. Measured: batch `DEP-260923-0021`, tender `cash`, `created=True` | `opening_float` = **200.0000**; `closed_at` NULL; the batch NAMES the session; a **second** open by Dana is refused naming the till already open | **BR-PAY-1184** · BR-PAY-1160 |
| 2 | **09:10–17:05** — seventeen payments at the window | Every cash and cheque payment carries `counter_session_id` **and** the till's batch for ITS tender, written at INSERT. Measured: cash 6 → **1** batch · cheque 8 → a **different** batch · card 3 → **0** batches, **no till** | The drawer is NOT empty at close, which is the whole of `DEF-PAY-6226`; a card taken at the same window carries neither | **BR-PAY-1186** · §3.4 |
| 3 | **17:20** — Dana opens **My counter** (3·2) to see what the system says | `by_method`: cash **$710.00** (countable), cheque **$1,284.60** (countable), card served but `countable: false`. `taken` **$1,794.60** · `countable_expected` **$1,994.60** | ⚠ **THE FLOAT IS INSIDE THE CASH LINE AND IS NOT NETTED OUT** — p056, built as drawn: a clerk counts what is in the drawer and the float is in the drawer. `$510.00` taken + `$200.00` float = the `$710.00` cash line | **BR-PAY-1160** |
| 4 | **17:30** — Dana counts and closes (3·3b): `cash 710.00`, `check 1284.60` | `close_kind` **`counted`** · `difference` **0.0000** · no note required · **no journal line** | A card total may not be typed into the count — refused, p056 ③. A count that is SHORT would need a note, and would post (step 4a) | **BR-PAY-1160** |
| 4a | *(the other ending, not this walk's)* — the drawer is **$12.00 short** | `difference` **−12.0000**, a note is REQUIRED, and the books take it: **DR `6850 Cash over and short` / CR `1010 Undeposited funds`** | ⚠ **THE BLUEPRINT SAYS THE OPPOSITE AND IS SUPERSEDED.** p059: *"The ledger: Nothing — counting is not a posting."* PO ruling 2026-09-23 §3.3: *"(b) Post it."* An OVER posts the mirror | **BR-LED-796** · §3.3 |
| 5 | **17:32** — the till's batches become bankable | Both batches seal at the closed till's totals — cash **$510.00**, cheque **$1,284.60**. **The float was never a payment and is not in the batch** | `recorded_total` on the cash batch is 510.000000, not 710.000000 | **BR-PAY-025** |
| 6 | **17:40** — Finance opens **Deposits** (S37) | Both batches are on the list, status **`in_transit`**, ready to match against the bank | Measured: `DEP-260923-0021` cash 510.000000 and `DEP-260923-0022` cheque 1284.600000, both served by `GET /deposit-batches` | US-PAY-023 |
| 7 | **INVARIANCE** — the drawer is one person's, for one shift, at one window | A second clerk at a second window opens their own till and their money never joins Dana's; the card three bank under the day's system till, which is openly nobody's | `uq_counter_sessions_open_owner` refuses a second OPEN till per PERSON, not per tenant | BR-PAY-1160 · hard rule 6 |

---

## What a browser can actually drive, as of 2026-09-23 — and where this walk STOPS

**Measured, not assumed**, by `10-scripts/cr136_p2_17_counter_shift_readback.py`
against PostgreSQL 16.13 on a migrated clone. Steps 1–6 all have a control and
an endpoint behind them, and **the walk reaches the end** — `P2.10` landed in
`7611d80d2`, two commits after this file was written, and the section below
records what that changed and what it did not.

| # | Where | The control | What the server does |
|---|---|---|---|
| 1 | Any payments screen → the page head | **`Start counter →`** — the slot `P2.7` put on all seven screens; with a till open the same slot reads **`Your counter · CTR-… · open`** and is the door back to 3·2 | `POST /counters` → **201**, the session and its cash batch in one transaction |
| 2 | Payments → **Record payment** (2·3a) | the banner names the batch this money goes into, or says ***Start your counter first.*** and carries the door | `POST /accounts/{id}/payments`. A `cash`/`check`/`money_order` with no open till is **refused at the endpoint** (`P2.23`), not by hiding a button — `BR-SHL-025` |
| 3 | Payments → **Counter** → the till's own page (3·2) | the four tiles and the SYSTEM SAYS column | `GET /counters/{code}` — reached by the till's **CODE**, never its id (B14 rule 31) |
| 4 | 3·2 → **Close counter** (3·3b) | one countable row per tender, and a **Why** field that appears when the difference is not zero | `POST /counters/{id}/close` → **200** with the sealed row and `posted` |
| 5 | — | (no control — closing seals the batches) | `counters._seal_batches` |
| 6 | Finance → **Deposits** (S37) | the batch list, with **Match** on each row | `GET /deposit-batches` → the batch IS there, `status: in_transit` |

### STEP 6, AND WHAT `P2.10` TURNED OUT TO BE

⚠ **THIS SECTION SAID `P2.10` WAS *NOT STARTED* UNTIL IT LANDED TWO COMMITS
LATER (`7611d80d2`), AND THE AMENDMENT IS THE POINT.** A journey is read as a
specification; one that names a gap which has closed sends a lane to build
something twice. Amended by its own author on the day, which is the only version
of this that is cheap.

**What this walk measured stands, and the task pointed the OTHER WAY.**
`bankrec_read.batch_queryset` filtered on the tenant alone, so a counter batch
was on the Deposits list from the moment `P2.1` cut one — and since `P0.6` a
batch exists from the moment the drawer **opens**. So the defect was not a batch
that failed to arrive; it was **an OPEN till's batch sitting on Finance →
Deposits, `in_transit`, matchable and lockable** (`DEF-PAY-6266`). `P2.10` is
`bankrec_models.BANKABLE` — `session_id IS NULL OR session.closed_at IS NOT
NULL` — with eight readers, and the money still in an open drawer is served as a
FIGURE (`still_open`) rather than as a silence.

**This walk is unaffected because it closes the till first.** Step 4 is 17:30;
Finance looks at 17:40. Both batches are `BANKABLE` by then and both are on the
list, exactly as measured.

⚠ **WHAT IS STILL ABSENT, AND IT IS NOT `P2.10`'s — SO IT IS SAID PLAINLY
RATHER THAN FILED AGAINST A CLOSED TASK.** The served row carries twelve keys,
measured:

    bank_total · code · currency · deposited_on · difference · id · locked
    method_code · method_name · payment_count · recorded_total · status

**Nothing in it says WHOSE TILL IT WAS.** A finance lead looking at
`DEP-260923-0021` cannot tell Dana's `$510.00` from Marcus's. The blueprint's
task line asks only that a closed till's batch *appear ready to match*, and it
does — so a till column is a REQUEST nobody has made, not a defect. It is
recorded here because this is the file somebody reads when the Deposits list
looks anonymous, and because `P0.6`'s whole argument was that *"Dana's $1,240 of
cheques and Sam's $880 were one row neither clerk could be held to"* — they are
two rows now, and the screen still does not say which is whose.

### Two things this walk proved that nothing had asserted

1. **A card taken at the counter carries no till and no batch.** Measured:
   `card 3 payment(s) 402.150000 · on THIS till: 0 · distinct batches: 0`. The
   three land on the day's system till at the nightly cut. This is §3.4 working
   and it is the negative that makes step 2's positive worth anything — a test
   that only stamps a till and finds it there passes just as happily with the
   tender filter inverted.
2. **A till is TWO batches, not one.** One per tender, per `P0.6`'s re-key
   (`UNIQUE (tenant, session, method)`). ⚠ The blueprint conflates the two:
   p030 prints `CTR-260921-DW` in 2·1's **Batch** column and p037 prints the
   same string in 2·3a's banner, as though a till had one batch. It has up to
   seven, and before a clerk picks a tender there is no single batch code to
   name. Recorded in `CR-136-BRC07` §7 and repeated here because this is the
   file somebody reads when the column looks wrong.
