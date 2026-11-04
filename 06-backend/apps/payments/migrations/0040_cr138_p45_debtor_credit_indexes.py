# ── Trace ──────────────────────────────────────────────
# Change:  CR-138-BRC07 `P4.5` — indexes for the debtor query.
# Rules:   `NFR-3` · `NFR-5` (an index bounds nothing) · CLAUDE.md hard rule 1
#          (tenant first in every key, because every query filters that way) ·
#          hard rule 4 (`allocations` is append-only — an index is not a write
#          path and this changes none of that) · hard-won law 1 (a comment
#          claiming a guarantee is not the guarantee) · hard-won law 7.
# ───────────────────────────────────────────────────────
"""ONE covering index, because four more were measured and earned nothing.

`P4.5`'s own instruction is *"measure the current figure first, or there is
nothing to beat"*. Five indexes were drafted for it. **Four of them are not in
this migration, and the runs that removed them are written out below**, because
an index nobody's plan chooses is not free: it is write amplification on
`invoices`, `payments`, `allocations` and `refunds` — four of the highest-write
tables in the product — paid for ever, for nothing.

════════════════════════════════════════════════════════════════════════════
WHAT IS HERE, AND WHAT IT BUYS
════════════════════════════════════════════════════════════════════════════
`ix_alloc_invoice_amount` is `(tenant_id, invoice_id) INCLUDE (amount)`. It is
the same key as B2 §4's signed `ix_allocations_invoice`, which stays; the
difference is the payload. The debtor list asks *"what has been allocated
against this bill"* once per open invoice of the tenant, and `amount` is the
only column it wants — so with `amount` in the index the answer never touches
the heap.

**Measured on real PostgreSQL 16 at 40,046 debtors / 80,091 open bills** —
the top of T5 and the top of the ICP — one page of fifty, paired and
interleaved over two rounds (median of 3 after a discarded warm-up, so the
box's own load falls on both arms, 2026-09-23):

    round 1   without  12.047 s        with  9.414 s
    round 2   without  11.735 s        with  8.847 s

**About −24%**, and the plan names the mechanism:

    without   Index Scan using allocations_invoice_id_ced58b96 on allocations
                -> and then the heap: 170,259 buffers on one subplan alone
    with      Index Only Scan using ix_alloc_invoice_amount on allocations
                -> 160,183 buffers, no heap visit

════════════════════════════════════════════════════════════════════════════
THE FOUR THAT ARE NOT HERE, AND THE RUN THAT REMOVED EACH
════════════════════════════════════════════════════════════════════════════
All four were built, all four were measured at 40,046 debtors, and **no plan
this lane captured chose any of them for a statement that costs anything.**
Paired run, the four present against the four absent, two rounds:

    absent   10.256 s · 13.301 s        present   11.974 s · 12.941 s

That is noise in both directions — a −24% index shows up in a paired run and
these do not.

* **`ix_invoices_open_by_acct`** `(tenant, status, account) INCLUDE (due_date,
  total)`, which had its own migration in `billing/0030`. **Removed, and the
  reason is the one that matters: the schema already had it.**
  `ix_invoices_due` is `(tenant_id, status, due_date)` — B2 §4's own signed
  index — and its `(tenant_id, status)` PREFIX is exactly what the open-bill
  scan needs. Proved rather than argued: the seeded tenant has 80,091 open
  bills and ONE closed one, so *"a utility with years of history"* could not
  be tested on it at all. **240,273 `void` bills were inserted** to make three
  quarters of the table closed, and PostgreSQL then switched to
  `Bitmap Index Scan on ix_invoices_due` with
  `Index Cond: (tenant_id = … AND status = ANY ('{issued,paid}'))` — the
  proposed index still unchosen, and the page at 3.715 s with it against
  3.621 s without.
* **`ix_payments_acct_credit`** `(tenant, account, status, purpose) INCLUDE
  (amount)`. The credit leg sums essentially every payment row of the tenant,
  which is a Seq Scan whatever indexes exist, and it stayed a Seq Scan with
  this one present. The only statement that chose it is the last-payment read
  over the page's fifty accounts, which already had `ix_payments_acct` and
  runs in **0.227 ms**.
* **`ix_alloc_payment_amount`** `(tenant, payment) INCLUDE (amount)`. The
  credit leg joins the whole of `allocations` to the whole of `payments`;
  PostgreSQL hash-joins two sequential scans and no per-payment index changes
  that.
* **`ix_refunds_acct_status`** `(tenant, account, status) INCLUDE (amount)`.
  ⚠ **The fixture could not decide this one and that is stated rather than
  hidden** (hard-won law 7: a check that cannot cover its whole subject prints
  what it skipped). It holds ONE refund row, so any plan over it is
  meaningless — **8,000 more were seeded across the four lawful statuses** and
  the plan still read `Seq Scan on refunds`, 4.4 ms of a 3.7-second page,
  because half of a real refunds table matches `issued`/`cleared` and a Seq
  Scan is the right answer to that.

⚠ **NONE OF THIS SAYS THOSE FOUR ARE WRONG FOR EVER.** It says no measurement
taken on 2026-09-23 could show one of them helping, and an index added on a
plan nobody has run is the guess `P4.5` exists to forbid. **Add one back with
a plan that names it**, and this docstring is the shape that proof takes.

⚠ **WHAT MADE THE DRAFT WRONG IS WORTH MORE THAN THE INDEXES.** The rejected
plans an earlier draft of this file quoted — `loops=4,032`, three subplans at
9,109 / 12,238 / 8,759 buffers — were real, and they were the plan of a query
this lane then REWROTE: the credit was three correlated subqueries before it
became three tenant-wide aggregates. The indexes were sized for a statement
that no longer exists, and nobody re-ran the plan afterwards. **A measurement
is about a VERSION, and a rewrite expires it.**

`CONCURRENTLY` is deliberately NOT used: this project's migrations run inside
a transaction and a `CONCURRENTLY` build cannot. On a table of this size the
build is seconds; a utility with years of allocations should schedule it.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

# ⚠ **THIS WAS `0035`, THEN `0038`, AND BOTH WERE TAKEN WHILE IT WAS BEING
# WRITTEN** — `CR-136`'s till migration landed first, then `CR-139` `P5.4-P5.6`
# took `0038` and `0039` for settlements. A migration number is a shared
# register with NO allocator (`allocate.py` covers defects, gates, CRs and
# versions, not these), and two leaves in one graph is the error `DEF-2872`
# records: Django refuses EVERY test in the process with *"multiple leaf nodes
# in the migration graph"*, which names neither lane and reads like a broken
# tree. **Twice in one lane is the evidence, not the anecdote:** re-deriving
# the number against the tip AT PUSH TIME is the only thing that works, and it
# is the same act law 11 prescribes for a blob and for an id.
#
# `dependencies` names `0039` because that is the leaf this one extends, not
# because it needs anything in it — an index on `allocations` and a settlement
# table have nothing to say to each other.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0039_rls_cr139_p5_5_settlements")]

    operations = [
        migrations.AddIndex(
            model_name="allocation",
            index=models.Index(
                fields=["tenant", "invoice"],
                include=["amount"],
                name="ix_alloc_invoice_amount",
            ),
        ),
    ]
