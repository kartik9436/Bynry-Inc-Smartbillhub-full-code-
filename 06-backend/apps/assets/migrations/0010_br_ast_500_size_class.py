# ── Trace ──────────────────────────────────────────────
# Story:    Step 1 of 12-governance/19-execution-sequence.md — SOURCE THE
#           CONNECTION SIZE. The R1–R7 lane finished step 3 and stopped:
#           `accounts 1 · attempted 0 · disagreed 0 ·
#           blocked {connection_size_unresolved: 1}`.
#           Screens: AST-01/02 asset detail, SET-06 step 3 (the Size column),
#           S16 unit-wizard meter grid
# Defects:  DEF-514 (no row anywhere records a connection size — this column is
#           its named prevention, verbatim) · DEF-1811 (the shadow cannot run on
#           a single real account of any tenant) · DEF-484 (a per-size tier
#           override is stored and served and does not reach a bill) · DEF-255
#           (the reference list was seeded ahead of the column that points at it)
# Rules:    BR-AST-500 (new — the asset carries the connection's size class) ·
#           BR-TEN-170/171 (the list is `service_size_classes`; the hosted TABLE
#           still carries the old `meter_size_classes` name — DEF-970) ·
#           BR-RAT-108 (PO verbatim: "based on Asset and Account type you will
#           have select 1 base charge") · BR-TEN-078 (the list is NOT
#           service-scoped) · B2 §2 (a cross-module FK is a reviewed interface —
#           which is why this is TEXT)
# Tests:    06-backend/tests/test_def_1900_connection_size.py
# Impacts:  apps/assets/models.Asset · apps/assets/selectors (asset_dict ·
#           assets_on_unit) · apps/assets/services._validate_asset ·
#           apps/metering/selectors (connection_size_for — billing's seam) ·
#           apps/billing/gather._connection_size_for (already resolves that seam
#           BY NAME and is UNCHANGED by this migration)
# ───────────────────────────────────────────────────────
"""assets 0010 — `assets.size_class` (BR-AST-500, closing DEF-514).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-27 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in `12-governance/09-human-review-ledger.md`.

**WHY THE COLUMN EXISTS.** Rating can price per connection size — the per-size
base grid (BR-RAT-088/108) and DEF-433's per-size tier ladder both narrow on
it — and until this migration **the product recorded a connection size on no
table anywhere**. The consequence was not an error; it was silence. A utility
that typed a 2" water ladder of `3.45 / 5.10 / 7.70` got a bill priced off the
every-size ladder of `3.20 / 4.80 / 7.20`, because `pricing_inputs` with no size
correctly falls back to the NULL "every size" group. Correct fallback, wrong
money, and no test could go red on it.

**WHY IT IS ON THE ASSET AND NOT THE SERVICE POINT.** DEF-514's own prevention
says so, and BR-RAT-108 is why: the base charge is selected *"based on Asset and
Account type"*. The size is a property of the DEVICE — a 5/8" meter carried from
one premises to another is still a 5/8" meter — so it travels with the row that
travels.

**WHY TEXT AND NOT A FOREIGN KEY.** `rating.RateTier.size_class` and
`rating.ChargeCodeAmount.size_class` are both TEXT for a reason this column
inherits unchanged: *"a size Settings RETIRES must not vanish from a schedule
that already priced it"*. A retired `W-4` must likewise not vanish from the
meter that is bolted to a wall. A cross-module FK into a tenancy-framework
lookup is also a reviewed interface (B2 §2) that this row does not need.

**ONE NULLABLE TEXT COLUMN. NO BACKFILL, NO CONSTRAINT, NO INDEX, NO DEFAULT.**
Every existing row keeps NULL, and NULL is the state the whole product was in
five minutes ago — so this migration cannot move one figure on one bill of one
tenant. That is deliberate and it is the point: a DEFAULTED size would have
selected a tier ladder for every meter in every database on the strength of a
guess, which is the one thing a migration on a money path must never do.

**ROLLBACK** is a clean `RemoveField` (`migrate assets 0009`). Nothing reads the
column until a human records a size; `gather` refuses BY NAME when a schedule
carries per-size overrides and no size was resolved, which is the behaviour
before and after this migration for every row that stays NULL.

**FRESH DATABASE:** an `AddField` of a nullable TextField with no default, no
`RunSQL` and therefore no `%`/`%%` trap (DEF-622, DEF-064, DEF-072, DEF-103 were
all raw SQL). It depends on 0009, the current head of this app.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0009_br_ast_049_external_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="size_class",
            field=models.TextField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-004@1a7b52d (the extended asset-field story, at the branch-base
#   commit this lane assembled from — the one carrying DEF-514, DEF-1811 and
#   DEF-1812 in 12-governance/10-defect-log.csv and the step-1 hand-off in
#   19-execution-sequence.md. ⚠ THE CITATION IS A LOCATOR, NOT A CLAIM: no story
#   owns this column. It is a DEFECT FIX (DEF-514), and US-AST-004 is named
#   because the human-facing surface still owed for it — a size control on
#   AST-05 and AST-01/02, filed as DEF-1900 — is that story's screen. No
#   verifier tool recomputes this hash, so it is a checkable reference rather
#   than a snapshot digest.)
# generated: 2026-08-27 by the connection-size lane (step 1 of
#   12-governance/19-execution-sequence.md — BR-AST-500; the R1–R7 lane had
#   stopped at step 3 having proved the chain could not be run on a single real
#   account of any tenant for want of this column)
# checklist: A✔ (backend — the column, its two publications, the metering seam and the write path) B=deferred(DEF-1900 — no size control on AST-05 or AST-01/02 and no SIZE column on the meters import; both are other lanes' files and the frontend half is governed by B14 rule 21's PER-FILE migration clause, so a utility can be TOLD the gap exists but this lane may not close it) C✔ (11 cases in tests/test_def_1900_connection_size.py, plus the demo estate seeding a ratified band) D✔ (proved — see gates:; every case RED first at 1a7b52d) E=deferred(same as B — and note the ONE screen change this lane makes needed no frontend edit at all: SET-06 step 3 has read asset.get("size_class") since it was built, so its permanently empty Size column is repaired by the selector alone) F✔ (see gates:) G✔ (BR-AST-500/501 + BR-MET-500 written; DEF-514/1811/1812 closed with their worked figures; DEF-1900 and DEF-1901 MINTED rather than left; the decision log carries the before/after table and the four judgments; NO open question was minted because the size vocabulary was ALREADY RULED by BR-TEN-170/171 and law 13's grep found it) H=deferred(PO 2026-08-09 — AI authors, human reviews later; the row is in 12-governance/09-human-review-ledger.md and states in plain English with a figure the three things owed to the PO)
# gates: makemigrations --check --dry-run *No changes detected* · full
#   `manage.py migrate` on an EMPTY Postgres 16 applies clean, and DEF-255's own
#   probe (information_schema for %size_class%) now returns
#   `assets | size_class | text | YES` where it returned nothing ·
#   golden-verify 33 PASS / 0 FAIL BEFORE AND AFTER, so no ❄️ B4/B5 figure moves
#   · tests/test_def_1900_connection_size.py 11 passed, ALL PROVED RED FIRST at
#   1a7b52d (hard-won law 7) with `core.errors.ValidationError: VAL-002
#   (assets.unknown_field)` and `AttributeError: module 'apps.metering.selectors'
#   has no attribute 'connection_size_for'` · DEF-1812's own pin fired BY NAME
#   ("billing's read seam has GAINED a multiplier") and is now the parity
#   assertion it was blocking · run_gates 38 PASS / 13 FAIL, every one of the 13
#   pre-existing and none naming a file or an id of this lane (G26's
#   assets/sample_data.py finding was re-run at 1a7b52d and is byte-identical
#   there) · G23 PASS — this lane adds no unreachable story · G35 PASS at 2.79.5
# exceptions: (1) **NO BACKFILL, NO DEFAULT, NO CONSTRAINT, NO INDEX — and that
#   is the design, not an omission.** Every existing row keeps NULL, which is the
#   state the whole product was in before this migration, so it cannot move one
#   figure on one bill of one tenant. A DEFAULTED size would select a tier ladder
#   for every meter in every database on the strength of a guess, which is the
#   one thing a migration on a money path must never do. (2) The column is TEXT
#   and is NOT validated against `service_size_classes` — `RateTier.size_class`'s
#   own stated reason ("a size Settings RETIRES must not vanish from a schedule
#   that already priced it"), which holds identically for a meter bolted to a
#   wall. (3) DEF-1810 is NOT resolved by this lane and must not be: what
#   `served_sizes` MEANS is a design question with money behind it and is the
#   PO's (prime directive). apps/rating/resolution.py and
#   apps/billing/resolution_shadow.py are untouched.
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING 🔒 — migration ordering, a
#   CLAUDE.md sensitive path; row in 12-governance/09-human-review-ledger.md.
#   Not RATIFIED without a recorded human sign-off.
# ──────────────────────────────────────────────────────────
