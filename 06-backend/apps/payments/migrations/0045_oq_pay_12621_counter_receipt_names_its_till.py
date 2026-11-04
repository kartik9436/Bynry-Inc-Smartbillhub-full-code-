# ── Trace ──────────────────────────────────────────────
# Question: OQ-PAY-12621 — CLOSED 2026-09-24, option (a). PO, verbatim: *"p1 a"*
#           — *a cash application fee taken at a counter counts toward that
#           counter's expected cash; the drawer balances and the books are
#           unchanged.*
# Defect:   DEF-PAY-6375 — measured by lane REQ-FEE on 2026-09-23 and built
#           against by nobody until this.
# Rules:    CLAUDE.md hard rule 2 (money to four decimals) · hard rule 4 (this
#           writes NO payment row and moves NO allow list) · hard rule 7 ·
#           `NFR-3`/`NFR-5` (the drawer figure is one indexed read, never a
#           scan and never a Python fold) · decision log 2026-09-19 option A2 ·
#           decision log 2026-09-23 *a drawer difference reaches the books*
# Tests:    06-backend/tests/test_oq_pay_12621_fee_in_the_drawer.py
# Impacts:  apps/payments/counter_receipt_models.CounterReceipt ·
#           apps/payments/counter_receipts.record_counter_receipt (the only
#           writer) · apps/payments/counters.running_split (the reader)
# ───────────────────────────────────────────────────────
"""payments 0045 — ONE nullable pointer on `counter_receipts`, and its index.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this column changes
a figure a clerk counts a drawer against). HUMAN-REVIEW-PENDING — AI-authored
2026-09-24 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); row in 12-governance/09-human-review-ledger.md.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
A counter receipt now records **which till was open when the money was taken**,
so the cash a clerk is holding for an application fee is part of what the Close
screen expects them to count.

═══════════════════════════════════════════════════════════════════════════════
WHY — TWO RULINGS MET AND PRODUCED A WRONG POSTING
═══════════════════════════════════════════════════════════════════════════════
**2026-09-19, option A2:** an application fee posts at collection and writes
**no payment row**. The PO accepted the stated cost — *"the counter clerk's
drawer doesn't balance on the day"*.

**2026-09-23:** a drawer difference at close **reaches the books**. An over or
short now posts.

Together those two make one fee into two bookings. `running_split` computes the
expected drawer from `payments`, and a fee is not a payment row — so the cash is
in the drawer and not in the expectation, the close reads OVER by the fee, and
that over posts a second time.

**Worked, and it is the ruling's own figure:** Dana opens her counter, takes
Sarah Miller's **$70.00** application fee in cash (`DR 1010 · CR 2400` at
collection — correct, and untouched by this), counts **$470.00** at close
against an expected **$400.00** → **$70.00 over**, posted again. After this
migration the expected count is **$470.00** and the difference is **$0.00**.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS DOES **NOT** DO, SAID PLAINLY (hard-won law 1)
═══════════════════════════════════════════════════════════════════════════════
* **No payment row is invented.** A2's design is untouched: a request fee still
  writes a `counter_receipts` row and no `payments` row, and the PO's ruling
  says *"the books are unchanged"* in as many words.
* **No posting changes.** The collection entry is the same entry on the same
  day to the same two accounts.
* **No deposit batch changes.** A receipt joins no batch; it joins a DRAWER
  FIGURE, which is a different thing — `cut_deposit_batches` reads `payments`
  and is not touched.
* **Hard rule 4's allow list does not move.** `payments/0014` is still the only
  place it ever has.

═══════════════════════════════════════════════════════════════════════════════
WHY NULLABLE, AND WHY THAT IS NOT A DEFAULT
═══════════════════════════════════════════════════════════════════════════════
`till_refusal` — the rule that a hand-recorded tender needs an open till — is
called at the ENDPOINT and not inside `record_counter_receipt`, for `P2.23`'s
reason: the sample fixture seeds a counter collection for a utility that has no
clerks, and a guard in the service would stop every fixture seeding. So a
receipt can lawfully exist with no till, and every row taken before today has
none. A `NOT NULL` would refuse the fixture and the history together.

**A null means this receipt joins no drawer.** That is the honest answer and it
is not a zero (`DEF-127`).

═══════════════════════════════════════════════════════════════════════════════
THE ROLLBACK, STATED BEFORE SHIPPING
═══════════════════════════════════════════════════════════════════════════════
The reverse drops the column and its index. **Nothing is lost that was not
derivable:** the column holds the till that was open when a receipt was taken,
and `taken_by` plus `taken_at` still name the person and the moment. What comes
back is the defect — a fee in the drawer that the close does not expect — so a
rollback must be paired with backing out the reader in `running_split`, or the
close screen will simply stop seeing fees again.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0044_oq_pay_12608_drop_settlement_pointer"),
    ]

    operations = [
        migrations.AddField(
            model_name="counterreceipt",
            name="counter_session_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="counterreceipt",
            index=models.Index(
                fields=["tenant", "counter_session_id"],
                name="ix_counter_receipts_session",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-PAY-12621 (CLOSED 2026-09-24, option (a)) · DEF-PAY-6375 ·
#   decision log 2026-09-19 (A2) · decision log 2026-09-23 (the drawer
#   difference reaches the books) · payments/0031 (counter_sessions) ·
#   payments/0035 (the sibling pointer this copies in shape)
# generated: 2026-09-24 by LANE RULINGS-0924
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING)
# gates: makemigrations --check · migrate forwards and backwards on PostgreSQL
#   16 · the worked $70.00 figure asserted on PostgreSQL and on SQLite
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
