"""customers 0035 — the cut records what it settled and what to restore.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, and one of the two columns holds MONEY. The marker is here
because the PATH is the category, not because the body is large (DEF-808). A row
in `12-governance/09-human-review-ledger.md` states in plain English what these
columns are for, with the figures.

WHAT THIS SERVES
================
**PO ruling 2026-08-30 — THE DISCONNECT IS THE WHOLE EVENT**, verbatim: *"when
we disconnect - we generate final bill at that time itself - so later bill is not
required ... entire workflow including all settlement and status update is taken
care at time of disconnect or move out - so account status changes and
outstanding is pending on account if any"*. It closes `OQ-1170` and grows CR-052
task 1 from *write a status column* to *bill, settle, write the status, leave the
remainder outstanding*.

Two nullable columns on `disconnect_cases`, and each one exists because a fact
that is not written down at the cut cannot be recovered afterwards:

  `status_before_cut`   TEXT     — the account status CODE held on the day of
      the cut. `OQ-1170`'s second half rules that a RESTORED account returns to
      **the billable status it held before the cut**. `restore_service` cannot
      derive that: by the time it runs the account reads `disconnected`, and
      defaulting to `active` would invent a status for a customer who was on
      `vacation_hold`. A CODE and not a foreign key, because account statuses
      are per-tenant rows a tenant may delete and re-create, and a code survives
      that where an id does not — the restore resolves it by `(tenant, code)`
      and reports by name when it cannot.

  `outstanding_at_cut`  NUMERIC(18,4) — what the account owed once the whole
      event had happened. CLAUDE.md rule 2 as re-signed 2026-08-22: money is
      STORED to 4 decimals and DISPLAYED at 2. On the PO's own worked case
      `A-11488` was cut owing **$612.75**, the final metered bill for the days
      before the cut carried **$23.23** of a $40.00 monthly base (18 days of 31)
      plus its consumption, and the reconnection fee added **$75.00** — and all
      of that stays OUTSTANDING on an account that is still open. The currency
      is `disconnect_cases.currency`, already on the row (rule 2 — a figure
      never travels without it).

NO BACKFILL, AND THAT IS THE HONEST DEFAULT
===========================================
Every existing row keeps NULL on both columns. A case cut before this ruling was
cut under the old rule — no bill was raised, no status was written — so there is
no pre-cut status to restore and no settled position to record. Inventing one
would put a figure a nobody computed onto a regulator-facing record.
`restore_service` reads a NULL as *nothing was recorded* and leaves the account
status alone, which is exactly what those cases need.

⚠ THIS IS `0035` AND IT WAS `0034` FOR AN HOUR — DEF-892'S OWN FAILURE MODE,
CAUGHT AT PUSH TIME AND NOT BY A GATE.
====================================================================
`DEF-892`: a migration number is ALLOCATED TO A LANE, never taken from the
watermark, **and it must be RE-DERIVED FROM THE BRANCH TIP AT PUSH TIME**
(CLAUDE.md law 11's `DEF-1787` clause — an allocated id is a blob too). This lane
took `0034` against a tip on which `0033` was the leaf; while it worked, the
CR-052 W3/W4 lane pushed **`0034_cr052_delivery_election_and_template_override`**
from its own worktree, where this lane could not see it. Two children of `0033`
is exactly the two-leaf merge every header in this directory warns about, and
**nothing would have caught it until `makemigrations` refused on a fresh
database.** Renumbered to `0035` on the rebase, depending on `0034`, the real
leaf; the reservation row is corrected in `12-governance/14-id-reservations.md`.

`0029` remains unclaimed and this migration does NOT take it, for the reason
`0030`, `0031`, `0032`, `0033` and `0034` each state in turn: `0030` already
depends on `0028`, so a second child of `0028` would make two leaves. The graph
stays linear.

NO NEW RLS POLICY, AND THE REASON IS STATED RATHER THAN ASSUMED
==============================================================
RLS in this product is a TABLE policy, not a column one, and
`0022_cr030_w7_disconnect_ladder` already puts `FORCE` row-level security on
`disconnect_cases` against `app.tenant_id`. Two new columns on that table inherit
it with nothing to add. Adding a policy here would create a SECOND policy on one
table, which is how a permissive OR-ed policy silently widens access — the same
sentence `0032` wrote for the same table and the same reason.

REVERSIBLE, CLEANLY. Dropping two nullable columns nothing else references. No
constraint moves: neither column joins a CHECK, a unique index or a foreign key,
and `disconnect_cases.state` keeps exactly the eight values `0032` left it with —
the ruling adds no ninth case state, because the cut is still a cut.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0034_cr052_delivery_election_and_template_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="disconnectcase",
            name="status_before_cut",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="outstanding_at_cut",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
    ]
