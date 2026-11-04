# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-650 (critical) · DEF-1088 (high)
# Rule:    BR-MET-400 — the premises owner IS the master account
# Ruling:  PO 2026-08-27, verbatim: *"so premises owner is master accountin
#          system. you ahve to showall details form account - Bascially
#          Premises -> owner = Master account - it can be existing master
#          account also so at the time of premises creation we should check -
#          how you will handle this"*
# ───────────────────────────────────────────────────────
"""`premises_owners.master_account_id` — the ONE missing link.

**WHAT THIS MIGRATION DELIBERATELY DOES NOT DO, and it is the important half.**

It writes **no data**. Some premises on a live tenant already carry a free-text
owner name in `premises.owner_manager`, and there are exactly two wrong things to
do with them:

* **drop the text** — that loses a utility's own record of who owns an address,
  and the string is often the only evidence anybody has;
* **invent parties from the strings** — that manufactures customers. *Whitfield
  Rentals LLC* and *Whitfield Rentals, L.L.C.* are one party or two and no
  algorithm knows which, and BR-MET-151 clause 3 already forbids exactly this:
  *"A flagged migration that offers each name for matching is the shape; silently
  guessing which string is which party is not."*

**So the free text is KEPT and the link is required GOING FORWARD** — the third
option, and the one the repo already chose once for the same data on 2026-08-27
(`metering 0040` backfills nothing for the same stated reason). An existing
premises stays exactly as it is, is listed by `unmatched_premises_qs()`, and a
person turns its string into a party on the PRM-04 matching surface. A premises
created from today needs an owner (BR-MET-401); one created before today does
not retroactively become invalid, because a rule that invalidates rows already on
disk is a rule that stops a utility saving an address it has had for ten years.

**THE COLUMN IS NULLABLE AND STAYS NULLABLE.** Beyond the pre-existing rows, the
second reason is live: WHEN an owner's account comes into existence and whether
it is `master` or `regular` is **`OQ-790`** and is not decided. The ruling makes
master-ness DERIVED from whether anyone else occupies the premises (`OCC-O`
against `OCC-T`), and at premises creation no unit is occupied yet.

⚠ **NUMBER ALLOCATED, NOT TAKEN FROM THE WATERMARK (`DEF-892`)** — recorded in
`12-governance/14-id-reservations.md` before this file was written. `0040` is the
real leaf: `0038` is unclaimed and `0040` already depends on `0039`, so a second
child of `0039` would make two leaf nodes and Django would demand a merge node.

⚠ **THE `customers` DEPENDENCY IS NOT DECORATION.** The FK's target table must
exist before this runs on a fresh database, and naming it here is the only thing
that orders the two apps. `customers 0031` is that app's leaf.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this file
declares schema that money is priced, posted or scoped against.

HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human."*). The standing record of that deferred
review is 12-governance/09-human-review-ledger.md; no 🔒 file reaches lifecycle
RATIFIED without a human sign-off recorded there.

⚠ **BOTH MARKERS WERE MISSING UNTIL 2026-09-02 AND G7 HAD BEEN RED ON THIS FILE
EVER SINCE IT LANDED (DEF-3229).** 198 of this repository's 218 migrations carry
them and 20 did not — so the gate that enforces the 🔒 protocol could not go green
for anybody, and every lane that ran it truthfully reported the failure as
"pre-existing, not mine". Nothing about the migration itself changed here.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0040_cr039_c12_premises_owner"),
        ("customers", "0031_br_cus_092_ssn"),
    ]

    operations = [
        migrations.AddField(
            model_name="premisesowner",
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
# packet: DEF-650 (critical) + DEF-1088 (high) + PO ruling 2026-08-27 ("Bascially Premises -> owner = Master account") + BR-MET-400
# generated: 2026-08-27 by the premises-owner lane
# checklist: A✔ B=deferred(DDL only — the behaviour TCs assert through the services) C✔ D=deferred(no-API-half in this file) E=deferred(no-frontend-half in this file) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 review ledger row APPENDED, and the row says out loud that this is NOT one of the seven named 🔒 paths and why it is filed anyway)
# gates: makemigrations --check clean ("No changes detected in app 'metering'") · the column is asserted present by tests/test_def650_owner_is_the_master_account.py, which was RED on it first
# exceptions: E3 NO RLS POLICY IS ADDED and none is needed — this adds a COLUMN to `premises_owners`, whose FORCE RLS policy metering 0040 already created; a second policy on the same table would be the drift DEF-639 warns about · E3 a NEW cross-module FK COLUMN metering -> customers.Account, B2 addendum r21, REVIEW OWED at the next B2 sitting (the DIRECTION is already in the reviewed set — this module FKs `customers.Account` twice) · E3 the column is NULLABLE and stays nullable: every owner row predates it, and OQ-790 (when the account exists and of which kind) is NOT decided · E3 LIVE POSTGRES PROOF NOT RUN IN THIS CONTAINER — the G5 isolation sweep is the gate and is REPORTED as owed for this column
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
