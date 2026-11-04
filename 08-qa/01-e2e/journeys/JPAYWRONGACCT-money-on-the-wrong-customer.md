# J-PAY-WRONG-ACCOUNT — a payment was taken on the wrong customer, and putting it right moves TWO balances

---
id: JPAYWRONGACCT
tier: 1
rules: [BR-PAY-864, BR-PAY-865, BR-PAY-866, BR-PAY-867, BR-PAY-011, BR-PAY-021]
stories: [US-PAY-001, US-CUS-012, US-LED-001]
---

<!-- CR-135 phase 1 `P1.15`, authored 2026-09-22 by lane P1-B.

     WHY THIS JOURNEY DID NOT EXIST UNTIL NOW, and it is not an oversight of the
     QA lane's: the SCREEN did not exist. `POST /payments/{id}/move` and
     `GET /payments/{id}/move-preview` landed 2026-09-03 and, measured on
     2026-09-22, nothing in `07-frontend/src/` called either of them. A journey
     is a clerk's walk; there was no walk to write down.

     ⚠ **THE FILE IS NAMED FOR ITS ID, AND THAT IS A RULE RATHER THAN A STYLE.**
     `G12` check 3 matches a browser spec to a journey BY FILENAME, and the
     catalogue names files after ids — so a file called
     `J-PAY-WRONG-ACCOUNT-…` declaring `id: JPAYWRONGACCT` can never have a
     spec found for it. This file shipped that way on 2026-09-22 and was one of
     the eight `DEF-QAE-6208` names; it is renamed here, while nothing outside
     the register and the generated index cited it and the rename is free.

     ⚠ **NOT ACTIVATED. There is no `JPAYWRONGACCT.spec.ts`, deliberately.**
     G12 fails a spec that claims a journey whose stories are not all built, and
     it is right to — but the honest reason here is narrower and worth stating:
     the two screens landed in `266db24a8` on the day this file was written, and
     a journey first seen green is a journey nobody has proved (hard-won law 7).
     The Playwright spec belongs in the commit that has first RUN this walk
     against a real stack and watched it fail on an older build.

     ⚠ **THE FIXTURE IS DELIBERATELY TWO CUSTOMERS AND NOT ONE.** A move between
     two accounts of the SAME customer is `BR-PAY-864`'s balanced transfer and a
     different act with a different rule. This journey is the harder case the
     drawing names — *"A clerk correcting an account, not an amount"* — where
     the money leaves one person's ledger and arrives on another's. -->

**Fixture.** Tenant `brazos-bend`. Two ACCOUNTS of two DIFFERENT customers:
**AC-2026-00001 · Ana Alvarez** and **AC-2026-00002 · Ben Okafor**. Ana's bill
**BL-2609-000085**, issued 2026-08-25, total **$158.10**, is met in full by
payment **PMT-2609-000418** — a cheque taken at the counter on 2026-09-08 and
cleared 2026-09-10. Ben has one open bill, **BL-2609-000092**, issued
2026-09-12, total **$210.40**, unpaid. **The cheque was Ben's.** Nothing about
the money is in doubt and nothing about the amount changes: the whole act is a
comparison of two accounts.

⚠ **THE FIGURES ABOVE ARE THE FIXTURE'S AND NOT THE BLUEPRINT'S** (B14 rule 37 —
a figure drawn in a wireframe is an ILLUSTRATION). They happen to match p47/p48
because the drawing drew this case; a later fixture may use other numbers and
every assertion below is written against the fixture, not against `$158.10`.

## The walk

| # | Step | Handoff contract to the next step |
|---|---|---|
| 1 | Open **Payments**, find `PMT-2609-000418` | the row is on the list with Ana's account number and her name |
| 2 | Open the row overflow | **Move** and **Reapply** are both offered, each with an accessible name — the blueprint measured *"2 doors — there are none today"* and this step is the proof they exist |
| 3 | Press **Move** | the modal opens saying where the money is NOW: *"It is on AC-2026-00001 · Ana Alvarez now."* |
| 4 | Search the destination by account number, name or address | Ben's account is offered by number and name; **no database id appears anywhere** (B14 rule 31) |
| 5 | Choose Ben, leave **Why** on *Recorded on the wrong account* | the consequence box appears, and NOT before — it is read from `GET /payments/{id}/move-preview?to=`, which needs a destination |
| 6 | Read the consequence box | two sentences, both the SERVER's arithmetic: *"Ana Alvarez owes $158.10 again."* over *"The new account's bills are met."* (BR-PAY-866 makes this part of the rule, not a courtesy) |
| 7 | Press **Move payment** | the commit is DANGER tier, because moving it back is a SECOND move carrying its own date and reason |
| 8 | Read the toast | it names the number the CUSTOMER holds — the original's — so a customer quoting their receipt can still be found |

## What must be TRUE afterwards, and both halves are the point

| # | Check | Why it is here |
|---|---|---|
| A | **Ana owes $158.10 again.** `BL-2609-000085` is open at its full amount | the outcome line of `P1.15`: *"the one that got it wrongly owes again"* |
| B | **Ben's `BL-2609-000092` is met**, in whole or in part, under BEN'S allocation order | `BR-PAY-866` — the destination re-allocates under its OWN rules and may land the money on entirely different bills. **That is correct.** A check that asserted the money met the same bill number would be asserting the opposite of the rule |
| C | **Two balanced journal pairs**, written by the posting service and nothing else | §4 of the blueprint: a move writes *"a reversal on one account and a new payment on the other"*, and hard rule 5 |
| D | **Neither the posting date nor the clearing date is today** | `BR-PAY-865`, and this is the check that earns the journey. Rewriting them to today makes Ben late on a bill he paid on time, on a screen that says only *moved* |
| E | **Ana's original payment row is not edited**, and no row is deleted | hard rule 4 — a correction is NEW ROWS. The original stands and carries its link to the move |
| F | **Two audit rows, and both carry the reason the clerk chose** | hard rule 7. The reason is free text and the screen posts the sentence the clerk selected, or their own words |
| G | **A replay writes nothing.** Pressing Move twice with the same idempotency key answers 200 with the FIRST move and `created: false` | hard rule 6, and a 409 toast for a button that worked is a wrong answer a clerk would act on |

## What must be REFUSED

| # | Check | Why it is here |
|---|---|---|
| H | A move is **refused while the payment sits in a reconciled deposit batch**, and the refusal renders as a SENTENCE, not an error toast | `BR-PAY-867` — the bank has already agreed that total. The way through is to unreconcile the batch, which is a deliberate act by a person |
| I | Where the service asks for an approval, the form asks for one and **this side never predicts it** | `BR-PAY-011`. Only the service knows whether a bill re-opens or a closed month is touched |
| J | A **reversing row** offers no Move at all, disabled with its reason | there is nothing to re-point |

## The trap this journey exists to catch

⚠ **A WALK THAT ENDS AT THE TOAST PASSES OVER THE WHOLE DEFECT.** Every check
above except A–D can be satisfied by a product that moves the row and leaves both
balances where they were. **Read both customers' positions out of the database,
not off the screen that just wrote them** — that is what `P1.15`'s own outcome
sentence asks for, and it is the same discipline `10-scripts/…_readback.py`
applies to every other walk in this folder.
