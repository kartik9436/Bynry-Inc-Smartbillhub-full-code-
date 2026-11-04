# CR-141-BRC07 — A refund's check number is correctable, the way a payment's is

**Raised:** 2026-09-23, by the Product Owner, answering `OQ-PAY-12614`.
**Branch:** `claude/laughing-thompson-kpmwih` (`BRC07`). Number from `allocate.py cr` against the
remote. ⚠ It was **140** when this lane started, and a sibling shipped `CR-140-BRC07` (the Debtors
tab's Write-offs link) before this push — so it was re-allocated as **141** and confirmed with
`allocate.py cr --verify 141` at push time, per law 11's id clause.
**Version:** `2.349.0`.
**Classification:** **CHANGE** — a reversal of a judgment we built the same day. `DEF-PAY-6331`
(`2.346.20`, lane REFUND-MONEY) made `refunds.reference` WRITE-ONCE in `payments/0041` and named
*"write-once rather than amendable"* as an UNSIGNED judgment in its review-ledger row. The PO's
answer reverses it. Not a defect: the product did exactly what was built, and the owner of the rule
has now asked for something different. **Screen-shaped** — it adds a row action and a form to S58.

---

## 0 · What arrived, in the requester's words

> *"One thing needs your sign-off, because it is a money record: (b) Allow a correction, the same
> way you allowed it for payments on 2 September"*

**What was shown, and so all the signature covers** (CLAUDE.md, the 2026-08-11 sign-off rule):
*Dana sends a refund of **$91.60** by check **#10241** but types **#10214**; as built it can never be
changed.* Options: (a) leave it write-once · (b) allow a correction the same way as payments.
**(b) chosen.** Recorded by the coordinator in `02-decision-log.md` (*"SIGNED: A REFUND'S CHECK
NUMBER MAY BE CORRECTED"*) and in `OQ-PAY-12614` (CLOSED).

---

## 1 · What is being reversed — quoted

* `payments/0041`'s docstring: *"`refunds.reference` — the cheque number — may be written **once**,
  from NULL, and may never be changed afterwards."* **Reversed for the correction path only.** It
  stays true for every other writer.
* `refunds.issue_refund`'s docstring: *"a cheque written for the wrong amount, or typed wrong, is
  **VOIDED** … and raised again."* **Half reversed**: a wrong AMOUNT is still voided; a number
  TYPED wrong is corrected.
* `EP-PAY-03` §5, the *Check # / trace* row: *"WRITE-ONCE from `payments/0041`: NULL → set, never
  changed"*. Struck and amended in place.

**Not reversed, and stated because a ruling that names one thing is read as permission for others:**
CLAUDE.md hard rule 4's allow list. `refunds` is NOT one of its tables (`payments/0006` exception
(4)), so `payments/0014` remains the ONLY place the `payments` table's allow list has ever moved, and
`payments_payment_immutable` is not touched. No ❄️ FROZEN B4/B5 figure is involved — nothing here
computes money.

---

## 2 · What the signature does NOT cover, and is therefore refused

The payment rule the PO pointed at (`OQ-1322`, 2026-09-02) lets a **cheque number, a memo and a
tender** change. For a refund only the **check number** was shown. So:

* the **memo** and the **tender** are REFUSED by name at the door — reported here, not built;
* the **amount, account and method** are refused, as they are for a payment;
* a **canceled (void) refund** stays closed — `0006`'s VOID guard is untouched;
* a refund with **no number yet** cannot be "corrected" — the first number is the ISSUE act's.

If a refund's memo should be correctable too, that is a new question for the PO, not this CR.

---

## 3 · Impact across the surfaces

| surface | impact |
|---|---|
| schema | **`payments/0043`** — `payments_refund_immutable` restated: `0041`'s body with exactly three hunks replaced (proved byte-for-byte by a test). No column, no table. |
| API | **ONE new address** — `POST /refunds/{id}/correct-reference`. No PATCH/PUT/DELETE on any refund path (asserted). |
| service | `refunds.correct_refund_reference` — `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`; the only caller that opens the correction window. `_cheque_number_for_issue`'s refusal now names the door instead of saying *"never changed"*. |
| audit | new action code `refund.reference_corrected`, `before`/`after` = the old number and the new. **Not a permanent record** — `audit_log` is pruned on its one schedule (`OQ-1340`). |
| screens | S58 — a ✎ *Correct check number* row action and a small form (new number, reason, consequence box). **Nothing about retention on screen** (B14 rule 33). |
| drawing | **None draws this act** — the PO's ruling postdates `06 Payments Page Blueprint.pdf`. The form is built from the kit (rule 38) and the glyph is the payment row's ✎ for the same act (p030 ⑥). |
| i18n | 12 keys, all eleven catalogues, through `i18n_fanin.py`, US English (*check*, *canceled*). Three payment keys reused (`payments.correct.note`, `.noteRequired`, `.submit`). |
| rules | `BR-PAY-1196` minted (CONFIRMED). `EP-PAY-03` §3 TC-11 and §5 amended. |
| defects | `DEF-PAY-6398` filed and fixed: the Refunds list never refreshed after ANY act, because `refresh()` invalidated a key the list stopped using at `P4.26`. `DEF-PAY-6282` (rule 15's two-plus-overflow cap) is WIDENED from four icons to five, not fixed. |
| demo fixture | none. |
| open questions | none opened; `OQ-PAY-12614` closed by the coordinator. |

---

## 4 · What was already built and is now wrong

* `payments/0041`'s trigger and `issue_refund`'s docstring — superseded by `0043` and amended.
* `test_def_pay_6331__the_trigger_allows_the_write_and_refuses_the_rewrite` — **still right**: a raw
  rewrite is still refused; only the window opens the column.
* **Lanes building now:** the US-English sweep owns the catalogue's existing strings (none touched
  here); REQ-FIX / REQ-FEE / NO-SCAN / BAD-ADDRESS files are not touched.

---

## 5 · The design choice, in one paragraph

The brief offered (a) `0014`'s narrow allow-list change, or (b) write-once kept for the issue write
plus a separately guarded correction. **(b) was built**, because (a) would copy `0014`'s surface and
break its reasoning — `0014`'s own docstring argues *"a Python check is not a guarantee when a repair
script can open a cursor"* — and because under (a) the proof *"changing `reference` by any other
write is refused by the database"* cannot be true. The guard is a transaction-local correction
window (`app.refund_reference_correction` = the refund's id), the same fence `ledger/0004` uses for
the books: *"a fence, not a vault"*.

---

## 6 · Version and rollback

`2.349.0` — a CHANGE level, allocated against the remote at push time.

**Rollback:** `migrate payments 0041` restores `0041`'s function body byte-for-byte (asserted by a
test), which makes the number write-once again; reverting the code removes one route, one service
function, one row action and the form. No data moves either way — a number already corrected stays
corrected, and its audit row stays until the schedule prunes it.

---

## 7 · Proof

`06-backend/tests/test_cr141_refund_check_number_correction.py` — **50 passed, 1 skipped on
PostgreSQL 16** (with `test_def_pay_6331_…`; the skip is the SQLite-tier case). Red first, four
ways, on the same cluster — quoted in `09-human-review-ledger.md`'s row for `payments/0043`.

## 8 · Close

**IN PROGRESS** until a person corrects a check number on S58 in a browser (the closure bar).
