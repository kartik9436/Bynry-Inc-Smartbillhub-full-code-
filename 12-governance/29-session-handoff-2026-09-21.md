# 29 · Session handoff — 2026-09-21

**Written because this session may end in a different chat**, and because law 10's test is
not *"was a decision made"* but ***"would the next agent, with only the repo, build the
same thing?"*** Eight lanes ran today; everything below is here so nobody reconstructs it
from a conversation that no longer exists.

⚠ **THIS FILE IS A SNAPSHOT AND IT ROTS.** Version `2.320.0`, branch
`claude/kind-wozniak-rl0uzt`. **The decision log, the registers and the change requests
outrank it the moment they disagree.** Read it once for orientation, then work the live
files.

---

## 0 · DO THESE BEFORE YOU READ ANYTHING ELSE

1. **`./10-scripts/check_head_current.sh`** — first command, before reading a file or
   believing a grep.
2. **`ls 10-scripts/`** before writing any helper that touches a shared file. Four tools
   there exist because the damage already happened.
3. **Read `12-governance/change-requests/CR-125-BRC07-...md`** — it is the spec four
   lanes built to today, and it carries both PO rulings verbatim.
4. ⚠ **`--reuse-db` ON POSTGRESQL DOES NOT REBUILD WHEN A MIGRATION CHANGES**
   (`DEF-GOV-6029`). It reuses by a PER-CHECKOUT name, not a migration digest —
   `CLAUDE.md` law 14 says otherwise and is true only of the SQLite path. **Drop
   `test_sbh_<checkout>_<hash>` after any migration** or your code hits columns that do
   not exist and the failure reads as `current transaction is aborted`, which looks
   exactly like a code bug. It cost one lane two full runs.

---

## 1 · WHAT SHIPPED

**Transfer — the PO's five items are COMPLETE.** The contacts seam and the
sale-to-the-current-owner refusal landed before today. This session added: the seller's
link ENDED rather than deleted (`customers/0060`, 40 checks), the commit queueing three
messages (81 checks), and `GET /transfers/{ref}` (19 checks).

**Measured on real PostgreSQL, both numbers, quote both:**

| | |
|---|---|
| NO FAILURE TODAY | **23 of 25** |
| COMPLETE TODAY | **0 of 25** |

`COMPLETE` stays at 0 because `premises_units_meters_assets_on_step_3` still holds all
25 rows. **The 2 failures are `RF2` and `PR2`, both SUITE-FIXTURE defects** already filed
(`DEF-CUS-6020`, `DEF-CUS-6021`) — one declares two keys opposite that its own fixture
makes the same expression, the other asserts "every asset names the buyer" on a unit with
no assets. **They were not weakened, and must not be.**

⚠ **AND THE FLOW WAS WALKED IN A BROWSER, FOUR REAL SALES.** Three of the PO's four
original checks now answer YES — the name changes, two people keep two numbers, the unit,
meters and plan all follow, no second account is made, the money is right and the debt
rides the property. **The fourth is NO and cannot be yes**: nothing is told, because
**373 messages are queued product-wide and not one has ever been sent.**

**Disconnect — all four surfaces, one CR.** The wizard rebuilt to its drawing with the
PO's two actions (2,091 lines → 673, five addressable step components); the list built to
p142; **the case record built from nothing, routed, registered and walked**; and the
backend serving three new reads plus step 2's write side. **A clerk can now record a
medical certificate, which was impossible anywhere in this product over an endpoint
mounted 2026-08-28.**

**New Connect — MEASURED, NOT BUILT.** `12-governance/28-new-connect-measured-2026-09-21.md`,
both halves. Building is blocked on §3 below.

**Document capture is a component** — it was 330 lines of JSX and eight state hooks inline
in a 4,324-line page, importable by nothing.

---

## 2 · WHAT THE PO MUST RULE — nothing here may be settled by a lane

⚠ **FOUR OF THE SEVEN ROWS BELOW WERE RULED ON 2026-09-21 AND ARE STRUCK THROUGH.
PUTTING A STRUCK ROW TO THE PO AGAIN IS CLAUDE.md LAW 13'S NAMED FAILURE** — the PO
on re-asking: *"this is very exzuating and taxing as a human. Icant keep consistency
if you keep asking."* **Three rows are still genuinely theirs: `OQ-CUS-12522`,
`OQ-CUS-12524`, `OQ-CUS-12517`.** Checked against the register's STATUS column on
2026-09-21, which is the authority (CLAUDE.md prime directive: the status column
decides and a body contradicting it is stale).

| Question | Why it is theirs |
|---|---|
| ~~**`OQ-CUS-12518` — the reconnection fee.**~~ ✅ **CLOSED 2026-09-21 — the fee is `$75.00` and the code is `RECON`.** Do not ask again. The question as it stood: `$75.00` drawn AND signed (PO 2026-08-25, *"does reconnection need $8,315.00 - this is correct"*); the seed spells the code `RECON` at **`$45.00`**; `commit_cut` looks up **`CC-RECON`**. ⚠ **`ledger/chart.py` maps `RECON` to a GL account, so the LEDGER agrees with the catalogue and not the code.** **Fixing only the spelling starts charging `$45.00` against a signed `$75.00`.** | A money figure, and **every cut on every tenant refuses today** |
| ~~**`OQ-MET-12520` — does the six-tab New Connect build record exist at all?**~~ ✅ **CLOSED 2026-09-21 — ONE DESTINATION, MADE COMPLETE.** The PO chose option C: **no second screen at its own `/connections/…` address** (the 2026-09-04 ruling STANDS), and the property's Build tab gains what the six drawn tabs carry **as SECTIONS**. Blueprint p100–p107 stay the **content** contract; only their ADDRESS and TAB STRIP are superseded. ⚠ **It does NOT unblock building** — the four stoppers in `28-new-connect-measured-2026-09-21.md` §2 are untouched. | ~~A ruling colliding with a signed rule~~ — ruled |
| **`OQ-CUS-12522` — where do a buyer's identity papers go before a sale commits?** Filing them at step 2 writes them onto the **seller's live account**, and an abandoned wizard leaves them there. | Personal data on another person's record |
| ~~**`OQ-NOT-12521` — may a connection letter be filed?**~~ ✅ **CLOSED 2026-09-21 — a connection letter gets ITS OWN message kind**, with its own template group and retention. Reusing `notice` was the explicitly REJECTED option. ⚠ Queued is not sent: there is no provider adapter, so a queued row is still the finished state. | ~~A customer-visible classification~~ — ruled |
| **`OQ-CUS-12524` — the three transfer letters' wording.** Defaults written and marked `_LANE_AUTHORED` so a reviewer sees which three nobody signed; the question quotes all three in full. | Nobody but the PO holds it |
| **`OQ-CUS-12517`** — `Case raised by` has **no column**; the actor is in `audit_log`, which is **pruned**. | A schema change on a regulator-facing record |
| ~~**"Units energise one at a time"**~~ ✅ **RULED TWICE AND CLOSED 2026-09-21 — the word is `activate`.** PO, verbatim: *"we ahe to say activate"*, then *"3 · Energise or activated? activated"* — and it was ALREADY ruled 2026-08-25 (`CR-032`, shipped `2.46.0`). This was a MISSED INSTANCE of an old ruling, not a new question. ⚠ Four of the eleven catalogues carried the old word; Spanish, French, Italian, Portuguese, Hindi and Korean already avoid it and are LEFT ALONE (`B14` rule 35). | ~~Already ruled once~~ — ruled twice; the repair is the grep, not the ask |

---

## 3 · WHAT MAKES THE NEW CONNECT DRAWING MOOT UNTIL FIXED — all measured

* ⛔ **NOTHING CAN BE ACTIVATED.** `transition_service` is the only code that can, and no
  screen calls it. **A build can never reach *Activated* through the product**; the four
  showing that state are seeded rows.
* ⛔ **THE COMPLETION PATH HAS NEVER RUN.** Nine `created`, eight `submitted`, **ZERO
  `committed`**. The commit door answered *not found* for days and **both suites stayed
  green, because each tested its own side of the gap.**
* ⛔ **NO BUILD MADE THROUGH THE WIZARD CAN EVER RAISE A CHARGE.** The payload always
  sends the application reference EMPTY and the server's first pricing test asks for one.
  Step 6's payer, terms and posting date are **read by nothing, ever.**
* ⛔ **`?step=8` OPENS THE REVIEW ON AN EMPTY DRAFT WITH THE COMMIT BUTTON LIVE.** A fence
  exists (`clampStepToReached`) and this wizard never calls it. **ALL FIVE customer-flow
  wizards share the hole** — one fix in one place, not five.
* ⛔ **A SINGLE HOUSE CANNOT BE BUILT** — unticking the common-area unit makes the commit
  refuse, after all eight steps.
* ⛔ **STEP 4 OFFERS ELEVEN SERVICES AND THE UTILITY SELLS TWO**; step 2 asks the same
  question with the right list.

---

## 4 · WHAT IS OWED, IN ORDER

1. ⛔ **`customers/0060` IS ONLY PARTLY FINISHED — THREE FILES OF ~FORTY CHECKED.** Ending
   the seller's link instead of deleting it hands every reader of `customer_accounts` a
   second row it was never written to expect. **Found so far:** portal sign-in, where the
   seller could enrol on a house they sold and a buyer's password could be filed against
   the seller (`DEF-CUS-6048`, fixed); a second sale naming the FIRST seller; and a seller
   buying back being REFUSED at the guard the partial constraint exists to allow
   (`DEF-CUS-6046`, fixed). ⚠ **The remaining ~37 are unaudited.** `CustomerAccount.live()`
   is the sentence a caller uses when it means NOW; `objects` is deliberately unfiltered
   (the model says why).
2. **`DEF-SHL-6047` — twelve routed screens are absent from the screen-id registry**
   (router 163, registry 150), including `/:tenant/transfers/:ref` and `/:tenant/moves/:ref`.
   **The check that says so exists, is well built, and is red and unread.**
3. **Backend for the disconnect list:** an export resource, a way to ask *is this row
   held* (the drawn `On hold` chip cannot exist without it), and shorter tier labels.
4. **Two nullable money columns** on `transfers` (`balance_at_sale`, `deposit_at_sale`) and
   `buyer_was_matched`, written once at commit. **No back-fill** — nothing can say what a
   past sale's balance was.
5. **`openapi/schema.json`** does not describe the new routes.

---

## 5 · TRAPS LIVE RIGHT NOW

**(a) THE MIGRATION GRAPH IS READ BY NOTHING (`DEF-CUS-6041`).** `customers` carried TWO
LEAF NODES for about forty minutes today and **every pytest run in the repository died
before collection**, naming neither lane. The cause was a lane holding `0060` unpushed
while a sibling authored against `0059`. **Push a migration promptly, and check
`git ls-tree` for a sibling's before choosing a parent.**

**(b) `allocate.py defect --verify` COUNTS AN ID AS TAKEN WHEN IT APPEARS IN PUSHED CODE
OR A COMMIT MESSAGE**, not only in a register row. One lane pushed code citing four ids,
then verify reported all four taken *"by a sibling"* — the sibling was itself. **The order
is the fix: land the register row BEFORE, or in, the commit that cites it.** The alarm was
real on other occasions the same day, so do not learn to ignore it — check the registers
directly.

**(c) IDS COLLIDED REPEATEDLY.** One lane hit three collisions in twenty minutes. Every
lane's arithmetic was right; what was wrong was *which world the maximum came from*. **The
unconditional re-derivation at push time caught every one.**

**(d) `push_paths.sh` REFUSED CORRECTLY, REPEATEDLY** — on moved registers and stale bases,
including a register revert-by-subtraction that every other law-11 check passes over.
**Rebuild a register as the tip's bytes plus your row and prove the prefix byte-identical.**

**(e) `G120` PRINTS *"no interpreter on this machine can import Django"* AND THAT SENTENCE
IS FALSE** (`DEF-GOV-5925`). `06-backend/.venv/bin/python` does.

---

## 6 · THE PATTERN OF THE DAY — read this before trusting any green

**The checks that do not check outnumbered the bugs they were written to catch, by a wide
margin, across eight independent lanes.** Counted from today alone:

* a front-end test asserting its own constant back to itself, hiding **two cut reasons
  that can never commit** (`DEF-CUS-6023`);
* a hold-expiry test reading the **wrong route registry**, leaving a finished screen
  unreachable (`DEF-CUS-6042`) — and the general form, **twelve screens**
  (`DEF-SHL-6047`);
* **four checks that could not pass** in the transfer suite (`DEF-CUS-6043`), each honest
  the day it was written;
* **six walkthrough assertions measuring the wrong thing**, one of which FAILED THE
  PRODUCT FOR OBEYING A RULE;
* a cleanup step whose selector matched nothing and **silently no-opped** — which looks
  identical to one that ran and was refused;
* a fixture whose short string **hid a payload's 24-word paragraph** that rendered a table
  row 280px tall on live data;
* ⚠ **AND A RED PROOF THAT PROVED NOTHING** — a mutation swallowed by a shell quoting
  layer, so the case passed and *"proved red"* would have been reported in good faith and
  been false. **Assert the edit landed before running the proof.**

**The common cure was the same every time: make the check fail on purpose, in the harness
that will actually run it, before trusting it green.**

⚠ **AND THE ONE STRUCTURAL THING STANDING IN THE WAY IS THE BASELINE.** `run_gates` sits
at roughly **74 PASS / 53 FAIL**. `DEF-SHL-6047`'s check has been red and unread precisely
because **a true red among fifty others has the protective colouring of a known one.**
The ratchet that brings the count down is worth more than any individual fix on this list.
