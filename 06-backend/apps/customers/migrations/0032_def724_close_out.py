"""customers 0032 — the CLOSE-OUT act: three columns and two widened constraints.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. The marker is here because the PATH is the category, not
because the body is large (DEF-808). A row in
`12-governance/09-human-review-ledger.md` is OWED and this lane does not own
that file — it is REPORTED rather than written.

WHAT THIS CLOSES
================
`DEF-724` (high). PO ruling 2026-08-27, verbatim and in full: *"A disconnected
customer can never be closed - Add a separate close-out act — Cleaner in the
record"*. The rules are `BR-CUS-430` (the PO's) and `BR-CUS-431` (the BUILD's,
and it says so): a close-out is a SEPARATE door from a move-out, and it writes
the date SERVICE ended — the cut date — into `accounts.closed_at`, never the day
the clerk performed it.

Before this migration `apps/customers/services.move_out` was the only terminal
path in the product and it refuses a non-occupant by name. `BR-CUS-110` (PO
2026-08-26) ends occupancy at the cut while leaving the account open, so from
that ruling onward **an account cut for non-payment could not be finished by
anybody**: `A-11488`, cut 2026-08-18 owing $612.75 with 12 Foundry Row already
re-let, had no terminal state available to it.

════════════════════════════════════════════════════════════════════════════
⚠ THIS IS `0032` AND `0029` IS STILL FREE. THAT IS STILL DELIBERATE.
════════════════════════════════════════════════════════════════════════════
`DEF-892`: a migration number is ALLOCATED TO A LANE, never taken from the
watermark. `customers 0032` is this lane's reservation and is recorded in
`12-governance/14-id-reservations.md`.

`0029` is unclaimed and this migration does NOT take it, for the reason `0030`'s
own header states and `0031` repeats: `0030` already depends on `0028`, so a
second child of `0028` would make two leaves and Django would demand a merge.
This depends on `0031`, the real leaf, and the graph stays linear.

════════════════════════════════════════════════════════════════════════════
NO NEW RLS POLICY, AND THE REASON IS STATED RATHER THAN ASSUMED
════════════════════════════════════════════════════════════════════════════
RLS in this product is a TABLE policy, not a column one, and
`0022_cr030_w7_disconnect_ladder` already puts `FORCE` row-level security on
`disconnect_cases` against `app.tenant_id`. Three new columns on that table
inherit it with nothing to add. Adding a policy here would create a SECOND
policy on one table, which is how a permissive OR-ed policy silently widens
access.

════════════════════════════════════════════════════════════════════════════
THE TWO CONSTRAINT CHANGES ARE THE HALF THAT IS EASY TO MISS
════════════════════════════════════════════════════════════════════════════
`closed_out` is an eighth `disconnect_cases.state`, so BOTH of these move:

  1. `ck_disconnect_case_state` — the CHECK that keeps the vocabulary closed.
     Without this the close-out raises `IntegrityError` on its first write.
  2. `uq_one_open_disconnect_case_per_account` — the PARTIAL unique index whose
     predicate is *"the case is not finished"*. `closed_out` IS finished, and if
     the predicate does not say so then `disconnects.restart_after_closure`
     cannot open the `BR-CUS-082` TIER-1 collections case beside a closed-out
     service case: the insert collides on the index instead. That is a
     customer-facing failure — a surviving debt that stops being chased — and it
     is invisible until an account is closed out owing money.

Reversible: dropping the three columns and restoring the two prior constraint
definitions. ⚠ **A REVERSE IS NOT SAFE ONCE A CASE IS IN `closed_out`** — the
restored CHECK would refuse the row. That is stated rather than guarded, because
a migration that silently rewrote a regulator-facing state to something else is
worse than one that refuses to run.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0031_br_cus_092_ssn"),
    ]

    operations = [
        migrations.AddField(
            model_name="disconnectcase",
            name="closed_out_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="closed_out_by",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="close_out_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="disconnectcase",
            name="ck_disconnect_case_state",
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=Q(
                    state__in=(
                        "notice_sent",
                        "scheduled",
                        "on_hold",
                        "cut",
                        "reconnecting",
                        "stopped",
                        "restored",
                        "closed_out",
                    )
                ),
                name="ck_disconnect_case_state",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="disconnectcase",
            name="uq_one_open_disconnect_case_per_account",
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.UniqueConstraint(
                condition=~Q(state__in=("stopped", "restored", "closed_out")),
                fields=("tenant", "account"),
                name="uq_one_open_disconnect_case_per_account",
            ),
        ),
    ]
