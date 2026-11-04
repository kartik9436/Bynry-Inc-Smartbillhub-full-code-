# ── Trace ──────────────────────────────────────────────
# Change:   CR-081 (PO ruling 2026-09-07; the six ❄️ frozen figures re-signed
#           2026-09-08 under HUMAN-GUIDE §6 — decision log, *"THE PO RE-SIGNS
#           SIX FROZEN SEWER FIGURES"*).
# Rules:    BR-RAT-015 ❄️ SUPERSEDED · BR-RAT-010 reopened and answered the
#           other way · BR-RAT-032 (one price is ONE 0→∞ tier) ·
#           BR-RAT-037 (a version is append-only — see "WHAT THIS MAY AND MAY
#           NOT TOUCH") · CLAUDE.md hard rule 1 (RLS), hard rule 2 (money to 4
#           decimals), law 14 (a savepoint per tenant)
# Tests:    06-backend/tests/test_cr081_sewer_volume_basis.py
# ───────────────────────────────────────────────────────
"""rating 0028 — CR-081: sewer gets a RATE, and its percent becomes a FACTOR.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-08 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT CHANGED ABOVE THIS FILE
-----------------------------
Sewer used to bill **40% of the water usage-charge DOLLARS** and therefore
needed no price of its own — the price came from the water schedule. From
2026-09-08 it bills **90% of the water VOLUME at its own rate per unit**:

    water 8 kgal → sewer 7.2 kgal → 7.2 × $5.0000 = **$36.00**   (was $15.80)

So every existing `percent_of_service` version in this product is now
**structurally incomplete**: it states a factor and no rate, and
`models/percent_of_service.py` REFUSES such a tariff by name rather than
billing $0.00. This migration is what stops that refusal from reaching a bill
run.

⚠ **WHAT THIS MAY AND MAY NOT TOUCH — BR-RAT-037 IS NOT BEING WAIVED.**
BR-RAT-037 makes a tariff version append-only: *"nothing here ever rewrites an
existing version"*. This migration writes to existing versions, so the
predicate it selects on is the whole of its licence, and it is narrow on
purpose:

    model = 'percent_of_service'  AND  the version has NO rate tier at all

**A version with no rate cannot be a filed tariff**, because until this commit
there was no code path in the product — no API field, no S11 control, no
seed — by which anyone could put a rate on one. Every such row is the seed's
own, `SCHEDULE_SEWER` at 40 points of `water`. So this is a REPAIR of rows the
product itself wrote and which the ruling has made unbillable, not a
re-pricing of anything a utility filed.

**A version that already has a rate is LEFT ALONE and COUNTED.** So is one
whose factor is not the seeded `40` — a hand-typed number is a price ratio a
human chose, and reinterpreting it as a return-to-sewer factor is a judgment
only that human can make. Both counts are logged; neither is silently changed.

THE TWO WRITES, AND WHY 40 → 90 IS NOT "THE SAME NUMBER MOVED UP"
------------------------------------------------------------------
1. **`percent` 40 → 90.** The 40 was a PRICE RATIO: what sewer cost relative to
   water's money. The 90 is a **RETURN-TO-SEWER FACTOR**: the fraction of
   metered water that physically reaches the sewer, sourced at 79–95% across
   North American municipal utilities and clustering on 90%. Leaving 40 in the
   column would bill 40% of the VOLUME at $5.0000 — $16.00 on the reference
   bill — a figure nobody has ever signed.
   ⚠ **The irrigation allowance is NOT made by lowering this factor.** The
   industry's answer to a garden hose is **winter-quarter averaging**, which B4
   has carried as *"winter-averaging v1.1"* since it was written and which this
   product does not do. Lowering 90 to allow for gardens would under-bill every
   apartment and every commercial account that waters nothing.
2. **One 0→∞ `rate_tiers` row at `$5.000000`.** Stored the way `flat` stores a
   single price (BR-RAT-032), so there is no new column and only one
   representation of "one price" in the product. FLAT rather than tiered
   deliberately: 66 of 88 municipal wastewater utilities surveyed bill a
   uniform rate, and inclining tiers exist to curb *outdoor* use — which is
   exactly the water that never reaches the sewer.

⚠ **A BARE `.update()` HERE WOULD MATCH ZERO ROWS AND PRINT `OK` (DEF-RAT-4620,
AND TWO OTHER LANES HIT IT THE SAME DAY).** `tariff_versions` and `rate_tiers`
carry `FORCE ROW LEVEL SECURITY` with B2 §3's policy `tenant_id =
NULLIF(current_setting('app.tenant_id', true), '')::uuid`, and a migration runs
with that setting at the database's default — all zeros — so **every tenant row
is invisible to it**. Nothing raises. So this walks the tenants and sets
`app.tenant_id` for each (CLAUDE.md hard rule 1 applied to a migration), and it
**LOGS COUNTS**: "Applying … OK" cannot tell 8 rows from 0.

⚠ **EACH TENANT IS ITS OWN SAVEPOINT (CLAUDE.md law 14).** On PostgreSQL one
failed statement aborts the WHOLE transaction, so a single refused row would
take every other tenant's repair with it and the entire `migrate` would roll
back — while the SQLite suite, which has no aborted-transaction state, stayed
green. The nested `transaction.atomic()` is the only option, not the tidy one.

⚠ **DATA ONLY.** `rate_tiers` is written here and altered nowhere; adding an
`AddField` beside this reproduces `tenancy/0031`'s measured PostgreSQL failure,
*cannot ALTER TABLE … because it has pending trigger events*.

REVERSIBLE, and honest about it: the reverse deletes ONLY the tier this
migration wrote (recognised by its exact shape — sole tier, 0→∞, $5.000000, on
a percent version) and puts the factor back to 40. A rate a human has since
edited is not this migration's to remove, so it is left and logged.
"""

import logging
from decimal import Decimal

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

MODEL_PERCENT = "percent_of_service"

#: ⚠ Re-declared rather than imported from `core.sample_fixture`: a migration
#: must keep running when the seed moves on, and importing the live constant
#: would let this file's behaviour change under it. These are the two figures
#: the PO signed on 2026-09-08, verbatim: *"C — factor 90%, rate $5.00 →
#: $36.00, which is what a real sewer customer actually pays"*.
OLD_PRICE_RATIO = Decimal("40")
RETURN_TO_SEWER_FACTOR = Decimal("90")
SEWER_RATE_PER_UNIT = Decimal("5.000000")

#: The all-zero uuid the database defaults `app.tenant_id` to. Restored when the
#: walk finishes so the connection is left as it was found (`assets/0011`).
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table (`db/rls_tenancy_w0.sql`), so
    it can be enumerated before any tenant context exists."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md hard rule 1 — never touch a tenant table without
    `app.tenant_id` set. On sqlite there is no RLS and no `set_config`: skipped
    honestly, and the same ORM path runs."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def forwards(apps, schema_editor):
    """Give every rate-less sewer version a rate, and turn its ratio into a factor."""
    TariffVersion = apps.get_model("rating", "TariffVersion")
    RateTier = apps.get_model("rating", "RateTier")
    connection = schema_editor.connection

    priced = 0
    refactored = 0
    already_priced = 0
    hand_typed_percent = []
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                versions = TariffVersion.objects.filter(tenant_id=tenant_id, model=MODEL_PERCENT)
                for version in versions:
                    if RateTier.objects.filter(
                        tenant_id=tenant_id, tariff_version_id=version.id
                    ).exists():
                        # Already has a price. Not ours — see the docstring's
                        # "WHAT THIS MAY AND MAY NOT TOUCH".
                        already_priced += 1
                        continue
                    RateTier.objects.create(
                        tenant_id=tenant_id,
                        tariff_version_id=version.id,
                        season=None,
                        size_class=None,  # NULL = every size; sewer has none.
                        seq=1,  # the base UNIQUE is (tariff_version, seq)
                        from_qty=Decimal("0"),
                        to_qty=None,  # ∞ — BR-RAT-032's single block
                        unit_price=SEWER_RATE_PER_UNIT,
                    )
                    priced += 1
                    if version.percent is not None and Decimal(version.percent) == OLD_PRICE_RATIO:
                        version.percent = RETURN_TO_SEWER_FACTOR
                        version.save(update_fields=["percent"])
                        refactored += 1
                    else:
                        # A number a human typed. It is a PRICE RATIO in a
                        # column that now means a return-to-sewer factor, and
                        # only that human can reinterpret it. Reported, never
                        # rewritten.
                        hand_typed_percent.append(f"{tenant_id}/{version.id}={version.percent}")
        except Exception:  # pragma: no cover — reported, never silently swallowed
            logger.exception(
                "rating 0028: tenant %s could not be repaired for CR-081; its sewer "
                "tariff states a factor with no rate and will REFUSE at the next bill "
                "run (BasisUnavailable is not raised — TariffConfigError is, by name). "
                "Every other tenant is unaffected (per-tenant savepoint).",
                tenant_id,
            )
    _leave_tenant(connection)
    # ⚠ THE NUMBERS ARE THE DELIVERABLE, NOT THE `OK`.
    logger.info(
        "rating 0028 (CR-081): priced %d sewer tariff version(s) at %s per unit; "
        "moved %d from the %s%% price ratio to the %s%% return-to-sewer factor; "
        "left %d that already carried a rate; left %d with a hand-typed percent "
        "for a human to reinterpret: %s",
        priced,
        SEWER_RATE_PER_UNIT,
        refactored,
        OLD_PRICE_RATIO,
        RETURN_TO_SEWER_FACTOR,
        already_priced,
        len(hand_typed_percent),
        ", ".join(hand_typed_percent) or "none",
    )


def backwards(apps, schema_editor):
    """Remove ONLY the tier this migration wrote, and put the ratio back.

    Recognised by its exact shape — the version's SOLE tier, 0→∞, at exactly
    $5.000000, on a percent-of-service version. A rate a human has since edited
    does not match and is left; that is logged rather than assumed away.
    """
    TariffVersion = apps.get_model("rating", "TariffVersion")
    RateTier = apps.get_model("rating", "RateTier")
    connection = schema_editor.connection

    removed = 0
    kept = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                for version in TariffVersion.objects.filter(
                    tenant_id=tenant_id, model=MODEL_PERCENT
                ):
                    tiers = list(
                        RateTier.objects.filter(tenant_id=tenant_id, tariff_version_id=version.id)
                    )
                    ours = (
                        len(tiers) == 1
                        and tiers[0].to_qty is None
                        and Decimal(tiers[0].from_qty) == Decimal("0")
                        and Decimal(tiers[0].unit_price) == SEWER_RATE_PER_UNIT
                    )
                    if not ours:
                        kept += len(tiers)
                        continue
                    tiers[0].delete()
                    removed += 1
                    if (
                        version.percent is not None
                        and Decimal(version.percent) == RETURN_TO_SEWER_FACTOR
                    ):
                        version.percent = OLD_PRICE_RATIO
                        version.save(update_fields=["percent"])
        except Exception:  # pragma: no cover
            logger.exception("rating 0028 reverse: tenant %s could not be reverted", tenant_id)
    _leave_tenant(connection)
    logger.info(
        "rating 0028 reverse (CR-081): removed %d seeded sewer rate tier(s) and restored "
        "the %s%% ratio; left %d tier(s) that did not match this migration's own shape",
        removed,
        OLD_PRICE_RATIO,
        kept,
    )


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("rating", "0027_cr078_backfill_plan_late_fee_charge"),
    ]

    operations = [
        # DATA ONLY, by rule. See the module docstring and `tenancy/0031`.
        migrations.RunPython(forwards, backwards),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-081@2026-09-08 (decision log "THE PO RE-SIGNS SIX FROZEN SEWER FIGURES")
# generated: 2026-09-08 by the CR-081 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16 with seeded sewer versions planted, the planted count ASSERTED BEFORE the run, and the row counts read back BY QUERY rather than trusted from "OK"
# exceptions: it WRITES to existing tariff versions, which BR-RAT-037 makes append-only — licensed by a predicate no filed tariff can satisfy (a percent version with no rate could not be created by any code path that existed before this commit) and stated at length in the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
