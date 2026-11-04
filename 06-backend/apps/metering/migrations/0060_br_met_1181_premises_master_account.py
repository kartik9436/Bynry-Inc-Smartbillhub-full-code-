"""metering 0060 — a premises NAMES its master account (2026-09-22, `BR-MET-1181`).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE NULLABLE COLUMN. NOTHING IS BACKFILLED AND NOTHING IS DROPPED.

──────────────────────────────────────────────────────────────────────────────
WHAT THE PO RULED
──────────────────────────────────────────────────────────────────────────────
**Verbatim, 2026-09-22:** *"why you are point is at owner id - why not directly
at master accoutn Id - it will solev the problem … master Account do not have
any Owner ID - please confirm ; we are not using it - owner IDs are not required
hence no screens or fucntionality for it"*, and on the three consequences put
back to them: *"yes - im okay with this"*.

⚠ **IT IS `OQ-790`'s OWN MECHANISM, NAMED BY THE SAME PERSON ON 2026-08-27 AND
NOT BUILT FOR TWENTY-SIX DAYS:** *"you ahev to call master account creation
logic by passing the details and generate account number using Setting ->
numbering and use this number to write premsies"*. **This column is the "use
this number to write premsies" half.** What stopped it was not a missing
ruling — it was `_ensure_owner_master_account` reading `row.owner_id` first and
returning `no_typed_owner` before it ever looked at the identity payload
(`DEF-MET-6139`).

──────────────────────────────────────────────────────────────────────────────
WHY A COLUMN AND NOT A READ OF THE TWO THAT EXIST
──────────────────────────────────────────────────────────────────────────────
Three columns can answer *who is the master account for this address*, and
three answers that disagree is who gets billed wrongly:

  1. **`premises.master_account_id`** — this one. The declaration. Wins
     whenever set.
  2. `premises_owners.master_account_id` — the PRE-RULING declaration, read for
     rows written before today.
  3. `accounts.premises_id` — *which premises this account covers*, **never**
     *who owns this premises*. Both master AND regular accounts carry it, so
     promoting it would make every tenant at an address a candidate owner of
     it. It is never promoted and nothing writes it into this column.

`BR-MET-400`'s *declared, never inferred* survives: this is a SHORTER CHAIN
between the same two ends, still a read of a declared column, never a guess.
That rule retired the hallway derivation *"because a fallback that disagrees
with the declared owner would silently bill a different party"*, and the same
sentence is why the precedence is RULED in the decision log rather than left to
the reading order of a function.

──────────────────────────────────────────────────────────────────────────────
NULLABLE, AND NOTHING IS BACKFILLED
──────────────────────────────────────────────────────────────────────────────
Measured on a clone of the `brazosbend` beta, 2026-09-22, real PostgreSQL 16:
**79 premises, 5 owner records, and 0 premises whose owner record names a
master account.** So a backfill would move nothing on that database anyway —
and on one where it would, it would be this migration asserting a declaration
nobody made. A row written before today declares nothing here and is answered
by precedence 2, which is that column doing its job.

⚠ **`premises_owners` IS NOT DROPPED AND NEITHER IS ITS LINK.** 19 backend
files read it; `BR-MET-151`'s free-text import matching and the move-out
shortfall stand on it. It stops being what a SCREEN reaches for. Retiring it is
separate work and is not this change.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0059_def_cus_6109_draft_build_before_its_address"),
        ("customers", "0062_br_cus_1083_disconnect_visits"),
    ]

    operations = [
        migrations.AddField(
            model_name="premises",
            name="master_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column="master_account_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="customers.account",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-6139 (high) + PO ruling 2026-09-22 ("why not directly at master accoutn Id") + OQ-790 (CLOSED 2026-08-27, option (c)) + BR-MET-1181 + BR-MET-400 (narrowed, not weakened)
# generated: 2026-09-22 by lane C1 of CR-130-BRC07 part three
# checklist: A✔ B=deferred(DDL only — the behaviour TCs assert through the services) C✔ D=deferred(no-API-half in this file) E=deferred(no-frontend-half in this file) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 review ledger row APPENDED)
# gates: makemigrations --check clean ("No changes detected in app 'metering'") · the column is asserted present by tests/test_br_met_1181_premises_master_account.py, which was RED on it first
# exceptions: E3 NO RLS POLICY IS ADDED and none is needed — this adds a COLUMN to `premises`, whose FORCE RLS policy already exists; a second policy on the same table would be the drift DEF-639 warns about · E3 a cross-module FK metering -> customers.Account, the SAME direction and the SAME target `premises_owners.master_account` already takes (B2 §2 reviewed set; metering FKs customers.Account three times now), REVIEW OWED at the next B2 sitting · E3 the column is NULLABLE and stays nullable: every premises row predates it and NOTHING is backfilled, which is the ruling's own posture · E3 LIVE POSTGRES PROOF IS RUN — 10-scripts/br_met_1181_premises_master_account_readback.py applies this migration to a clone of the beta and reads the column back
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
