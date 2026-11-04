# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S49, S51
#           (the meter register and the add-asset form this drives) · S8
#           (Sample data panel, BR-TEN-069)
# Rules:    BR-TEN-056 (the sample set) · BR-TEN-057 (`is_sample` on the owning
#           row) · BR-TEN-061 (removal order — sub-meters before their parents)
#           · BR-TEN-063 (idempotent, audited) · BR-AST-009 (a measuring asset
#           declares its service AND an explicit UoM) · BR-AST-011
#           (assign-on-create) · BR-AST-043/044 (read method · meter type) ·
#           BR-RAT-090 (unmetered quantity = OBSERVED asset count — the carts) ·
#           BR-AST-003 (sub-meter parent) · BR-AST-010 (net metering) ·
#           BR-AST-042 (container_cart vocabulary) · BR-AST-047 (valuation on
#           the device record — CR-028) · CLAUDE.md rule 2 (money) · rule 3
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves the seam) ·
#           apps/metering (reads land on these meters)
# ───────────────────────────────────────────────────────
"""assets' half of the sample set: the meters and their assignments (DEF-153).

ONE METER PER UNIT, IN THE TENANT'S OWN SERVICE — AND WHY NOT TWO
------------------------------------------------------------------
⚠ **THIS HEADING SAID "ONE WATER METER PER UNIT" UNTIL CR-039 (2026-08-26) AND
THE CODE MATCHED IT — that agreement IS DEF-795.** The whole estate was water in
literals, so an electric or gas utility signed up and received nothing: the
seeder correctly refused to plant a service the utility does not sell, and the
refusal was invisible. The estate's SHAPE below is unchanged; WHICH service it
speaks is now resolved from the tenant (`_estate()` → `core.sample_fixture.
estate_plan`), and a service the tenant declares no UoM for is REPORTED rather
than given a guessed unit.

The rest of this section is about the COUNT and is unchanged by that.
The fixture spec asks for 96 meters, *"water + sewer per unit"*. It was written
when sewer was going to be billed FLAT and therefore metered. Sewer is now
billed as **40% of the water usage charge** (BR-RAT-015, the engine landed
2026-08-16 and the PO ratified $15.80 on $39.50), and a percentage of another
service's money reads no register at all.

Seeding 48 sewer meters nobody ever reads would put 48 phantom missing-reads
into every bill run and bury the THREE deliberately unreadable meters the spec
asks for — which is acceptance item 8, *"find the disputed read, the estimated
reads, the account in collections"*. So: **48 water meters, plus the one
replacement** spec §4 case 3 needs, and the spec sentence is amended in the same
commit rather than quietly disobeyed.

THE REPLACED METER IS THE POINT OF CASE 3
-------------------------------------------
One unit's meter comes off after the June read and a new serial goes on. The
retirement and the new install both go through `retire_asset` and
`create_asset` — the same two calls a clerk makes on S51 — so the assignment
rows tell the true story: one meter assigned from January to June, another from
July. A read chain that crosses two serials is a thing every utility has and
almost no fixture contains.

SUB-METERS AND BEHIND-THE-METER DEVICES — CR-010 Part-10.4, PO 2026-08-17
---------------------------------------------------------------------------
PO verbatim: *"please add sub meter and few bhend the meter devices"*. Until
that ruling this block seeded meters ONLY (measured — a grep for
sub_meter/BTM here returned nothing), so the S49 register's `Sub-meters` and
`Behind the meter` tabs were empty on every seeded tenant. Now:

* **six SUB-METERS**, one per apartment unit, each parented on that unit's own
  water meter (BR-AST-003: a sub-meter requires a meter/net-meter parent) and
  declaring service + explicit UoM because a sub-meter is a MEASURING type
  (BR-AST-009). They are deliberately never read — they land on the unit's
  EXISTING water service point (get-or-create), so the parent's committed read
  keeps satisfying the bill run and the READY-TO-RUN July gains no phantom
  missing-reads; the fixture declaration argues this in full.
* **three BTM devices** — a backflow preventer on the laundromat's connection,
  a solar inverter and an EV charger on two houses — using the SEEDED
  `asset_types` vocabulary (backflow · pv · ev_charger; the tenancy
  `device_types` lookup names the same devices). Non-measuring, so no service
  and no UoM: a water-only tenant can hold a customer's inverter without
  selling solar. The backflow row picks up its seeded 12-month test interval
  (BR-AST-027), so the compliance surface has a due date to show.

THE r10 SHAPE — CR-028 AST-W0-T1, PO 2026-08-22 (B16 §9)
----------------------------------------------------------
Additive on top of everything above (nothing existing renumbered or changed):

* **TRASH CARTS — DEF-496 closed.** Four `container_cart` assets, each with
  `service: trash`, because BR-RAT-090's count runs asset → service point →
  service: a cart without a trash service point is invisible to billing, which
  is DEF-496 with extra rows. Three on the CR-019 walkthrough unit and one
  next door, so the ruled *"3 × $15.00 = $45.00"* is finally producible from
  the shipped tenant — and a third unit deliberately keeps NONE, proving 0 is
  a real answer beside real 3s. The block SKIPS BY NAME on a tenant that has
  not enabled trash (the metering seeder's own posture, never a silent gap).
* **A MASTER + ITS SUBS.** `M-MASTER-01` (meter_type `master`) on the
  apartment block, three new sub-meters parented ON IT (BR-AST-003) — r10's
  `Master · N units` / `Sub → M-MASTER-01` role tags drawn from real rows.
  All land on EXISTING water service points, so like the six subs above they
  are never read and add no phantom missing-read to the July run.
* **A NET METER, IN INVENTORY.** `M-NET-01` (type `net_meter`, flag locked ON
  per BR-AST-010) so the detail's net line renders. Deliberately UNASSIGNED:
  assigning it would mint an electric service point with no read behind it,
  and a phantom missing-read in the ready-to-run July batch deletes the PO's
  acceptance test. Its export READS are metering's W2 half — the lane that
  seeds them assigns this meter beside the PV inverter.
* **THE TWO MISSING BTM KINDS** — `COM-0001` (comms) and `BAT-0001`
  (battery), completing r10's five device kinds on the BTM tab.
* **INVENTORY STOCK** — four more unassigned assets (no unit ⇒ BR-AST-011's
  leave-in-inventory path), one aged past 12 months, for the Inventory tab's
  counts-and-costs launch scope (§10-D5).
* **VALUATION ON EVERY NEW SEED** (BR-AST-047): purchase cost stored 4dp
  (rule 2), purchase date, supplier, expected life, warranty where stated.
  ⚠ Written by `_apply_valuation` DIRECTLY on this module's own rows —
  `services._validate_asset` does not accept the CR-028 valuation fields yet
  (that acceptance is AST-W2/W4's half); this is the `_tag` disposition — the
  module's own write of its own columns on the sample path — each backfill
  audited, and the seeder should route through the service the day it takes
  these fields.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.assets import models, selectors, services
from core import audit as core_audit
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.assets")

#: One install date for the whole set: assign-on-create needs one, and a
#: fixture whose meters all arrived on the same day is honest about being a
#: fixture. The date precedes the first read period, which is what matters.
INSTALL_DATE = "2026-01-05"
#: The replacement goes on the day after the June read (spec §4 case 3).
REPLACEMENT_INSTALL_DATE = "2026-07-01"
RETIREMENT_DATE = "2026-06-30"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _tag(queryset: Any) -> int:
    """BR-TEN-057 — this module's own write of its own tag."""
    return int(queryset.update(is_sample=True))


def _estate() -> fixture.EstatePlan:
    """WHICH service this tenant's meters are in — CR-039 wave A, DEF-795.

    ⚠ **RESOLVED INDEPENDENTLY OF METERING AND GUARANTEED TO AGREE.**
    `apps/metering/sample_data.estate()` asks the same pure function
    (`core.sample_fixture.estate_plan`) the same two questions through the same
    two seams, so both modules reach the same backbone without either reading
    the other's tables (B1). That matters more here than anywhere: the meter
    serial this block creates is the serial metering's read batch names, and a
    disagreement would surface as `unknown_meter` on 49 rows.

    ── BR-MET-143 (PO 2026-08-27, closing OQ-391) ─────────────────────────────
    PO verbatim: *"we have to match utility service unit and meter reading unit
    - if it does not match then we have intriduce multiplier factor on meter.
    **you will ahve to seed that data.**"* So this call now also hands the plan
    the unit each service is BILLED in and metering's classifier, and the plan
    answers with `multiplier` — the factor every meter below is created with.
    It is `"1"` for every tenant that has configured no `billed_uom` (which is
    every tenant today: r6.4 made it an option and nothing seeds it), so no
    existing estate moves; a tenant that HAS configured one gets its own
    `conversion_factor` on the meter, and a pair that no factor can reconcile
    is REFUSED by name rather than planted at ×1.
    """
    from apps.assets import seams

    return fixture.estate_plan(
        seams.enabled_service_codes(),
        seams.service_default_uoms(),
        seams.service_billed_uoms(),
        seams.unit_reconciliation,
    )


def _unit_index_to_id() -> dict[int, str]:
    """The unit each meter sits on, resolved through metering's published read.

    assets never queries metering's tables (B1); `apps/assets/seams.py` is the
    documented edge and `units_for_sample` below goes through it.
    """
    from apps.assets import seams

    resolver = seams.resolve("metering", "units_list", kind="selectors")
    if resolver is None:
        return {}
    by_no = {row.unit_no: str(row.id) for row in resolver() if row.unit_no}
    return {
        unit["unit_index"]: by_no[unit["unit_no"]]
        for unit in fixture.units_flat()
        if unit["unit_no"] in by_no
    }


def seed_sample_records(actor: Any) -> int:
    """THE SEAM `apps/tenancy/seams.py` has documented since 2026-08-15.

    One meter per seeded unit **PER METERED SERVICE THE TENANT SELLS**, each
    declaring that service AND its explicit UoM (BR-AST-009 / CLAUDE.md rule 3 —
    `kgal` on a water utility, `kWh` on an electric one, `ccf` on a gas one,
    and never a bare number), created with a `unit_id` so the service point is
    minted through metering's seam and the first assignment opens in the same
    call (BR-AST-011).

    ⚠ **IT SAID "IN THE TENANT'S OWN BACKBONE SERVICE" — SINGULAR — UNTIL
    `CR-062` C4 (PO statement (8), 2026-09-02), AND THE CODE AGREED WITH IT.**
    `core/sample_fixture.estate_plan` took the first enabled metered service as
    the estate's one backbone and refused every later one by name, so a utility
    selling Electric + Water + Sewer received water and sewer and **no electric
    line on any of its 95 bills** — not the usage, not even the signed `$12.00`
    monthly base, which is `$576.00` a month across 48 homes. The PO ruled it
    not acceptable: *"this is not correct - you cannot drop electricty or gas"*.
    The estate's SHAPE is unchanged (one connection per service, the case-3 swap
    on the first service only) and its SIZE now follows what the utility sells:
    one meter per unit per metered service.

    ⚠ **THE FIGURES IN THIS PARAGRAPH WERE MEASURED AT 48 UNITS AND THE ESTATE
    IS 50 SINCE 2026-09-02** (`CR-062` addendum J3/J4 appended a municipal
    building and an industrial plant). The `$576.00` and the 48/96/144 above are
    kept as the record of what `DEF-3224` measured; the live count is
    `core/sample_fixture.UNIT_COUNT` and is written nowhere else.

    ⚠ **THIS SENTENCE SAID "One WATER meter per seeded unit" UNTIL CR-039, AND
    THE CODE AGREED WITH IT** — `fixture.meter_plan()` hardcoded `"service":
    "water"` on every row and nothing here branched on the tenant's enabled set.
    That is DEF-795 stated in English in the one place a reader would have
    checked, which is why it survived: the docstring and the code were
    consistent, and both were wrong about what a utility needs. The estate's
    SHAPE is unchanged (one meter per unit + the case-3 replacement); only which
    register it is expressed in is now the tenant's.

    Idempotent (BR-TEN-063): an asset already carrying the fixture's number is
    skipped, so a replay writes nothing.
    """
    units = _unit_index_to_id()
    plan = _estate()
    if not units:
        # ⛔ **THIS `return 0` WAS THE THIRD INVISIBLE ZERO OF DEF-795, AND IT IS
        # ALSO DEF-809's FIRST HALF** (filed independently while this lane was in
        # flight — same line, same reading). No unit exists because metering's
        # premises block did not seed one, and this block answered `seeded · 0
        # rows` over it — so a tenant whose estate was refused upstream showed a
        # GREEN meters line. `BlockCannotRun`'s own contract says to raise and
        # NAME THE UPSTREAM BLOCK RESPONSIBLE, which is exactly this case
        # (DEF-166/167's rule, applied where it was missed).
        raise fixture.BlockCannotRun(
            # ⚠ THE COUNT IS READ, NEVER TYPED. This is the sentence a person
            # reads on the Sample data panel, and a refusal that describes the
            # fixture wrongly sends them looking for a limit that does not exist
            # (hard-won law 1; the estate went 48 -> 50 on 2026-09-02).
            f"no meters were seeded: not one of the fixture's {fixture.UNIT_COUNT} "
            "units exists on this "
            "tenant, so there is nothing for a meter to stand on. The UPSTREAM block is "
            "metering's 'Premises, units & service points' — fix that and load again. "
            + (
                plan.refusal_sentence
                if plan.primary is None
                else f"(this tenant CAN hold a {plan.primary.code} estate, so the cause is "
                "the premises block itself, not the services it sells)"
            )
        )
    if not plan.metered:
        # ── DEF-BIL-8725 · A CAPACITY-ONLY UTILITY STILL GETS ITS EQUIPMENT ──
        # This branch used to raise straight away, which was harmless while a
        # capacity service billed with nothing installed. The PO's ruling of
        # 2026-09-30 — *no asset = not in service* — made the equipment the
        # thing that puts a service on a bill, and the carts, fire lines,
        # panels, batteries and broadband lines are all planted BELOW this
        # line, after the meters. So a utility that signed up for trash alone
        # (or fire, solar, broadband, battery) had no asset on any unit and
        # its sample product issued 0 bills. There is still no meter to make;
        # the equipment that is not a meter is planted here instead.
        existing = {asset.asset_no for asset in selectors.asset_list(filters={"status": "all"})}
        written = _seed_cr028_r10_shape(actor, units, existing, entries=fixture.trash_cart_plan())
        written += _seed_cr062_capacity_equipment(actor, units, existing)
        if written:
            numbers = [entry["asset_no"] for entry in fixture.trash_cart_plan()]
            numbers += list(fixture.capacity_equipment_numbers())
            assets_qs = models.Asset.objects.filter(tenant_id=_tenant_id(), asset_no__in=numbers)
            _tag(assets_qs.filter(is_sample=False))
            _tag(
                models.AssetAssignment.objects.filter(
                    tenant_id=_tenant_id(), asset__in=assets_qs, is_sample=False
                )
            )
            return written
        # CR-039 / DEF-795. No enabled service can hold a register, so there is
        # no meter to create — and a `0` here would read exactly like "the
        # fixture asked for none". `BlockCannotRun` is the third state: could
        # not run, with the reason. Metering's premises block refuses first for
        # the same cause, so the panel names it twice and both sentences are true.
        # (Reached now only by a tenant whose services carry no equipment at
        # all — storm water and thermal/heat, whose capacity is on the unit.)
        raise fixture.BlockCannotRun(
            "no meters were seeded: this tenant sells no service the sample estate can "
            "put a register on. "
            + plan.no_register_reason  # DEF-2396 — a capacity-only estate is not "nothing enabled"
        )
    # CR-062 C8 — the DEMONSTRATION seeders below (sub-meters, the BTM
    # devices, the CR-028 registry shapes) stay on the FIRST metered
    # service. They are exhibits rather than coverage: a yard full of
    # spares and a master/sub tree repeated per service would triple the
    # thing a person is meant to read once.
    service, uom = plan.primary.code, plan.primary.uom
    # BR-AST-500 (DEF-514) — the demo estate's connection size.
    #
    # ⚠ **SEEDED BECAUSE DEF-515 IS THE ALTERNATIVE.** That defect is a column
    # that landed with its migration, its read path and its engine arithmetic
    # and NOTHING able to set it, so a real utility could compute the surcharge
    # and never ask for it — and it stayed invisible because *"a factor that is
    # NULL everywhere prices identically to no factor at all"*. A size column
    # NULL on every seeded meter is that shape exactly: the R1–R7 shadow would
    # still report `blocked {connection_size_unresolved}` on the demo tenant and
    # a reader would conclude the fix had not landed.
    #
    # ⚠ **THE CODE COMES FROM TENANCY'S RATIFIED LIST, NEVER FROM A STRING
    # TYPED HERE** (BR-TEN-171 — `W-58`, `E-1P-100`, …). A demo tenant carrying
    # an invented code would teach every reader the wrong vocabulary, and the
    # value ends up on a rate schedule.
    #
    # **The SMALLEST band is chosen** — first in the ratified order, and the
    # residential one for every service that has bands (water `W-58` is 5/8",
    # electric `E-1P-100` is single-phase 100A). It moves no money: no rate
    # schedule in the seed carries a per-size override, so `pricing_inputs`
    # returns the NULL "every size" group either way and every seeded bill is
    # byte-identical to yesterday's.
    #
    # Empty for a service the vocabulary does not answer for (sewer by ruling;
    # steam and battery by OQ-560/OQ-561) — then the meters keep NULL, which is
    # the honest answer and not a fallback.
    from apps.assets import seams  # local, as everywhere else in this module

    existing = {asset.asset_no for asset in selectors.asset_list(filters={"status": "all"})}
    written = 0
    # ⛔ **DEF-809's SECOND HALF.** `if unit_id is None: continue` dropped a
    # PLANNED meter without a word — the fixture asked for 49 and the block
    # could report `seeded · 12` with nothing anywhere saying which 37 never
    # arrived or why. The skip itself is right (a meter cannot stand on a unit
    # that does not exist), so what was missing is the SENTENCE, exactly as in
    # DEF-166/167. The numbers are collected and named once per block rather
    # than logged 37 times — and since CR-062 they are collected PER SERVICE,
    # because "37 meters found no unit" says nothing about which register.
    seatless: list[str] = []
    for metered in plan.metered:
        # ── CR-062 C4 · A METER PER UNIT PER METERED SERVICE ────────────────
        # This loop did not exist: the block read `plan.backbone` and planted
        # ONE service. A tenant selling electric + water received 49 water
        # meters and no electric meter, no electric reading and no electric
        # line on any of its 95 bills — 48 × $12.00 of monthly base absent from
        # the documents (`DEF-3224`, PO statement (8)).
        #
        # The SERIALS do not collide and nothing renumbers: `meter_no` is
        # `<prefix>-<5000 + unit index>` and the prefix is the service's
        # (`SERVICE_METER_PREFIX`), so water keeps `W-5000 … W-5047` byte for
        # byte and electric arrives beside it as `E-5000 …`.
        #
        # ⚠ **THE SWAP IS THE FIRST SERVICE'S ONLY** — CR-062 judgment 4. The
        # case-3 replacement is a demonstration (a read chain crossing two
        # serials), and three copies of it makes the demo harder to read rather
        # than richer, so every later service plants its 48 and no `W-9011`.
        is_primary = metered is plan.metered[0]
        # BR-AST-500 (DEF-514) — resolved PER SERVICE, because a connection
        # size is a fact about a connection: `W-58` is a 5/8" water tap and
        # `E-1P-100` is a single-phase 100A electric service, and the ratified
        # ladder is per service (BR-TEN-171). Empty for a service the
        # vocabulary does not answer for — then the meters keep NULL, which is
        # the honest answer and not a fallback.
        # ⚠ **THIS READ `sizes[0]` — THE SMALLEST BAND, FOR EVERY METER OF
        # EVERY SERVICE — UNTIL 2026-09-07 (`DEF-MET-4496`).** It is correct
        # code for ONE meter and wrong for an estate: 50 electric meters all
        # `E-1P-100` against a six-size ladder and 51 water meters all `W-58`
        # against a nine-size one, so a per-size base curve would be exercised
        # at exactly one point and five of six electric prices could be wrong
        # with every test green. The band is now a fact about the CONNECTION,
        # resolved per unit by customer class — see
        # `core.sample_fixture.meter_size_class_for`, which also explains why
        # the residential awkward units keep the band they already carry and
        # therefore why no ❄️ frozen figure can move.
        sizes = seams.service_size_class_codes(metered.code)
        rows = fixture.meter_plan(
            metered.code, metered.uom, metered.multiplier or "1", replacement=is_primary
        )
        for entry in rows:
            if entry["asset_no"] in existing:
                continue
            unit_id = units.get(entry["unit_index"])
            if unit_id is None:
                seatless.append(entry["asset_no"])
                continue
            # `DEF-MET-4496` — the band this CONNECTION is, checked against the
            # tenant's own ratified ladder inside the fixture so a utility that
            # has renamed or removed a band never receives a code it does not
            # hold. `None` for a service the vocabulary does not answer for,
            # which keeps the column NULL exactly as it did before.
            seed_size_class = fixture.meter_size_class_for(
                metered.code, entry["unit_index"], sizes
            )
            payload: dict[str, Any] = {
                "asset_no": entry["asset_no"],
                "type": "meter",
                "service": entry["service"],
                # BR-AST-009 / rule 3: the asset's OWN explicit UoM column.
                "unit": entry["uom"],
                "meter_type": entry["meter_type"],
                "read_method": entry["read_method"],
                "multiplier": entry["multiplier"],
                "unit_id": unit_id,
                "install_date": (
                    REPLACEMENT_INSTALL_DATE if entry.get("replaces") else INSTALL_DATE
                ),
                # BR-AST-500 — omitted entirely when the service has no ratified
                # bands, so the payload is unchanged rather than gaining a null.
                **({"size_class": seed_size_class} if seed_size_class else {}),
                # ── PO 2026-09-07 · THE TWO SOLAR HOUSEHOLDS' METERS ARE NET
                # METERS, AND WITHOUT THIS FLAG THEIR EXPORT READING IS REFUSED.
                # `BR-AST-029` puts an export record on a net-metering asset and
                # on no other, and `validation.export_not_net` is a hard ERROR —
                # so the reading model's *"solar on site → plus an export
                # register"* is unbuildable until the meter says it can push
                # back. `EXPORT_UNITS` is derived from the panel plan, so the
                # roof with panels and the meter that can export cannot get out
                # of step. `BR-AST-010` makes the flag optional on a `meter` and
                # unavailable on anything else, so nothing is invented here.
                **(
                    {"net_metering": True}
                    if entry["service"] == "electric"
                    and entry["unit_index"] in fixture.EXPORT_UNITS
                    else {}
                ),
                # DEF-CWP-3995 — WHERE the thing physically is. The column,
                # the service, the selector (`equipment_reads` serves it as
                # `where`) and two tests all existed; no sample plant ever
                # SET it, so every equipment row of every demo tenant read a
                # dash and a working screen was indistinguishable from a
                # broken one. A fixture is a claim about what a screen looks
                # like, and an empty optional column is a claim nobody meant
                # to make. BR-AST-014 caps it at 280.
                "location_note": "Front boundary box",
            }
            services.create_asset(actor, payload)
            written += 1

    if seatless:
        # DEF-809 — named, never a silent drop (BR-TEN-060).
        planned = sum(
            len(
                fixture.meter_plan(
                    row.code,
                    row.uom,
                    row.multiplier or "1",
                    replacement=row is plan.metered[0],
                )
            )
            for row in plan.metered
        )
        logger.info(
            "sample data: %d of %d meter(s) across %s were NOT created because their unit "
            "is not on this tenant — %s%s. The unit is metering's row; if the premises "
            "block reported anything but `seeded`, that is the cause",
            len(seatless),
            planned,
            ", ".join(plan.metered_codes),
            ", ".join(seatless[:8]),
            "…" if len(seatless) > 8 else "",
        )

    # ⛔ **THE RETIREMENT IS NOT DONE HERE ANY MORE — DEF-660, 2026-08-24.**
    # It used to run right here, and this block runs BEFORE metering's reads
    # block (`SAMPLE_MODULES` order: … assets · customers · metering reads …).
    # `validation.retired_meter` errors on ANY read for a retired meter, so the
    # opening batch's W-5011 row blocked, `commit_read_batch` refused the whole
    # batch, metering's block rolled back, and **0 reads landed on a fresh
    # tenant** — taking billing, payments, the payment plan and all plan money
    # with it in a chain of five failures that read like five separate bugs.
    # Measured from empty, 2026-08-24: `meter_reads: 0` · `invoices: 0` ·
    # `read batches: []` · `W-5011 retire_date 2026-06-30, status terminal`.
    #
    # Spec §4 case 3 says *"the old serial comes off AFTER the June read"*, and
    # that sentence is now the code: `retire_sample_replaced_meter` is published
    # on this module's services and metering's reads block calls it through its
    # own seam once its batches have posted. Assets still performs the write —
    # B1 is unmoved, nothing reaches across a module boundary to touch `assets`.
    written += _seed_sub_meters(actor, units, existing, service, uom)
    written += _seed_btm_devices(actor, units, existing)
    written += _seed_cr028_r10_shape(actor, units, existing, service, uom)
    # CR-062 D3-D7 — solar panels, batteries and broadband lines, so a
    # seeded capacity price has something installed to multiply.
    written += _seed_cr062_capacity_equipment(actor, units, existing)
    written += _seed_cr030_demo_meters(actor, existing)

    # CR-062 C4 — every metered service's serials, not just the first's.
    # This list is what `_tag` marks `is_sample`, so a serial missing from
    # it is a seeded row the removal path would leave behind (BR-TEN-057).
    numbers = [
        entry["asset_no"]
        for row in plan.metered
        for entry in fixture.meter_plan(
            row.code, row.uom, row.multiplier or "1", replacement=row is plan.metered[0]
        )
    ]
    numbers += [entry["asset_no"] for entry in fixture.sub_meter_plan(service, uom)]
    numbers += [entry["asset_no"] for entry in fixture.BTM_DEVICE_PLAN]
    numbers += list(fixture.cr028_asset_numbers(service, uom))  # CR-028 AST-W0-T1
    numbers += list(fixture.capacity_equipment_numbers())  # CR-062 D3-D7
    numbers += [entry["asset_no"] for entry in fixture.CR030_A10432_METERS]  # W3 T3.12
    assets_qs = models.Asset.objects.filter(tenant_id=_tenant_id(), asset_no__in=numbers)
    _tag(assets_qs.filter(is_sample=False))
    _tag(
        models.AssetAssignment.objects.filter(
            tenant_id=_tenant_id(), asset__in=assets_qs, is_sample=False
        )
    )
    return written


def _seed_sub_meters(
    actor: Any,
    units: dict[int, str],
    existing: set[str],
    service: str = "water",
    uom: str = fixture.WATER_UOM,
) -> int:
    """CR-010 Part-10.4: the apartment block's six sub-meters (S49 tab 2).

    Through `create_asset`, exactly as the meters above: BR-AST-003's parent
    requirement, BR-AST-009's service + explicit UoM, and BR-AST-011's
    assign-on-create are all the SERVICE's refusals, not this fixture's
    assumptions. Idempotent on the asset number, like everything here.
    """
    from apps.assets import seams  # local, as everywhere else in this module

    # `DEF-AST-4494` — a SUB-METER IS A CONNECTION AND HAS A SIZE. Ten of them
    # were seeded with a NULL `size_class`, which `connection_size_for` reports
    # as "nobody recorded one" and `gather` then refuses by name the moment the
    # schedule in force carries per-size overrides. A sub-metered building was
    # therefore the FIRST case that would break under a per-size base curve.
    sizes = seams.service_size_class_codes(service)
    written = 0
    for entry in fixture.sub_meter_plan(service, uom):
        if entry["asset_no"] in existing:
            continue
        unit_id = units.get(entry["unit_index"])
        if unit_id is None:
            continue
        size_class = fixture.meter_size_class_for(service, entry["unit_index"], sizes)
        services.create_asset(
            actor,
            {
                "asset_no": entry["asset_no"],
                "type": "sub_meter",
                "service": entry["service"],
                "unit": entry["uom"],  # BR-AST-009 / rule 3 — explicit, never inferred
                "meter_type": entry["meter_type"],
                "read_method": entry["read_method"],
                "multiplier": "1",
                "parent_asset_no": entry["parent_asset_no"],  # BR-AST-003
                "unit_id": unit_id,
                "install_date": INSTALL_DATE,
                # BR-AST-500 — omitted entirely when the service has no ratified
                # bands, so the payload gains no null.
                **({"size_class": size_class} if size_class else {}),
                # DEF-CWP-3995 — WHERE the thing physically is. The column,
                # the service, the selector (`equipment_reads` serves it as
                # `where`) and two tests all existed; no sample plant ever
                # SET it, so every equipment row of every demo tenant read a
                # dash and a working screen was indistinguishable from a
                # broken one. A fixture is a claim about what a screen looks
                # like, and an empty optional column is a claim nobody meant
                # to make. BR-AST-014 caps it at 280.
                "location_note": "Rear alley",
            },
        )
        written += 1
    return written


def _seed_btm_devices(actor: Any, units: dict[int, str], existing: set[str]) -> int:
    """CR-010 Part-10.4: a few behind-the-meter devices (S49 tab 3).

    Non-measuring types, so NO service and NO UoM (BR-AST-009 allows "—" for
    exactly these) — which is also what lets a water-only tenant carry a
    customer's solar inverter. `create_asset` assigns on create and gives the
    backflow preventer its seeded 12-month test interval (BR-AST-027).
    """
    written = 0
    for entry in fixture.BTM_DEVICE_PLAN:
        if entry["asset_no"] in existing:
            continue
        unit_id = units.get(entry["unit_index"])
        if unit_id is None:
            continue
        services.create_asset(
            actor,
            {
                "asset_no": entry["asset_no"],
                "type": entry["type"],
                "unit_id": unit_id,
                "install_date": INSTALL_DATE,
                # `DEF-AST-4495` — the statutory test date, where the device
                # has one. `next_test_date` prefers this explicit column over
                # the `last_test_date + interval` derivation, and no seeded
                # asset has ever carried EITHER — so the registry's Next-test
                # column was a dash on every row of every demo tenant, over an
                # interval the seed had been setting all along. Omitted
                # entirely for a device with no test, so the payload gains no
                # null. See `core.sample_fixture.BTM_DEVICE_PLAN`.
                **(
                    {"certification_due": entry["certification_due"]}
                    if entry.get("certification_due")
                    else {}
                ),
                # DEF-CWP-3995 — WHERE the thing physically is. The column,
                # the service, the selector (`equipment_reads` serves it as
                # `where`) and two tests all existed; no sample plant ever
                # SET it, so every equipment row of every demo tenant read a
                # dash and a working screen was indistinguishable from a
                # broken one. A fixture is a claim about what a screen looks
                # like, and an empty optional column is a claim nobody meant
                # to make. BR-AST-014 caps it at 280.
                "location_note": "Side of the house",
            },
        )
        written += 1
    return written


def _seed_cr028_r10_shape(
    actor: Any,
    units: dict[int, str],
    existing: set[str],
    service: str = "water",
    uom: str = fixture.WATER_UOM,
    entries: Any = None,
) -> int:
    """CR-028 AST-W0-T1 (B16 §9): carts · master+subs · net meter · the two
    missing BTM kinds · aged inventory — the module docstring's own section.

    `entries` narrows the pass to a subset of that plan — the trash carts alone
    for a utility with no metered service (`DEF-BIL-8725`); `None` is the whole
    plan, as every metered tenant has always had it.

    ⚠ **CR-039 A3 — THE MASTER AND ITS SUBS ARE SERVICE-SHAPED NOW.** The skip
    below ("an entry naming a service the tenant has not enabled is SKIPPED BY
    NAME") is correct and unchanged; what was wrong is that `MASTER_METER` and
    `master_sub_meter_plan` said `water` in a literal, so **a submetering
    utility that sells electricity got no master and not one sub-meter** — the
    S49 register's whole submetering story, missing, on the one kind of tenant
    this product is built for. The hierarchy is identical in any service.

    The NET METER keeps its own `electric` and is still skipped on a tenant that
    does not sell electricity: a net meter is an electricity arrangement
    (BR-AST-010), not a shape to be re-expressed.

    One generic pass over `fixture.cr028_asset_plan()`, through `create_asset`
    like every block above, idempotent on the asset number (BR-TEN-063). Order
    inside the plan matters once: the master precedes the subs parented on it.
    An entry naming a service the tenant has not enabled is SKIPPED BY NAME —
    a water-only tenant gets no trash cart and is told so in the log, never
    handed a service point for a service it does not sell (BR-MET-003).
    """
    from apps.assets import seams

    enabled = seams.enabled_service_codes()
    written = 0
    for entry in entries if entries is not None else fixture.cr028_asset_plan(service, uom):
        if entry["asset_no"] in existing:
            continue
        service = entry.get("service")
        if service and service not in enabled:
            logger.info(
                "sample data (CR-028): %s not seeded — service %r is not enabled",
                entry["asset_no"],
                service,
            )
            continue
        payload: dict[str, Any] = {"asset_no": entry["asset_no"], "type": entry["type"]}
        for key in ("service", "meter_type", "read_method", "parent_asset_no", "allocation_rule"):
            if entry.get(key):
                payload[key] = entry[key]
        # ── BR-AST-500 · THE CONTAINER'S OWN CONNECTION SIZE (`DEF-2414`) ────
        # PO ruling 2026-09-01, verbatim: *"we will ahve to set in seeder as
        # well as in setting the sizes also on Units - so it works properly"*.
        # The carts landed 2026-08-22 with `size_class` NULL on every one, which
        # is the DEF-515 shape the meters block above warns about in full: a
        # column that has a migration, a read path and a screen, and no seeded
        # row carrying a value, reads to the next person as a fix that never
        # landed. Trash carries SEVEN ratified bands (`BR-TEN-171`), so a NULL
        # here is *"nobody recorded one"* and not *"this service has no size"*.
        #
        # ⚠ **THE CODE COMES FROM THE RATIFIED LIST, NEVER FROM A STRING TYPED
        # HERE** — the same discipline, and the same seam, the meters block uses
        # thirty lines up. A demo tenant carrying an invented code teaches every
        # reader a vocabulary the product does not have, and the value ends up
        # on a rate schedule.
        #
        # ⚠ **MEASURING ASSETS ARE DELIBERATELY LEFT ALONE HERE, AND THE REASON
        # IS ARITHMETIC RATHER THAN TASTE.** `connection_size_for` answers
        # `None` when two assets on ONE service point record DIFFERENT sizes
        # (decision log 2026-08-27 — one connection has one size). The CR-028
        # master and its sub-meters land on units that ALREADY hold a seeded
        # water meter sized from the same list, and absence is not a competing
        # claim — so leaving them NULL keeps those units resolving their meter's
        # own size, while giving them one would be a second claim that could
        # only ever agree by luck. The containers have no such neighbour: a
        # trash service point holds carts and nothing else.
        #
        # ⚠ **AND EVERY CART ON ONE UNIT TAKES THE SAME BAND FOR THAT REASON** —
        # the walkthrough unit's three carts are three assets on ONE point, so a
        # per-cart size would make that very unit unresolvable. One code for the
        # whole block, which is also what a real street looks like.
        if entry["type"] == fixture.TRASH_CART_TYPE and entry.get("service"):
            band = _container_size_class(entry["service"])
            if band:
                payload["size_class"] = band
        # ── CR-089 G1 · A SPARE ON THE SHELF SAYS WHAT IT IS (`DEF-AST-4735`) ─
        #
        # ⚠ **THE PARAGRAPH ABOVE EXEMPTS MEASURING ASSETS FOR AN ARITHMETIC
        # REASON THAT CANNOT REACH A SPARE.** `connection_size_for` answers
        # `None` when two assets on ONE service point record different sizes —
        # and an INVENTORY row has no service point, no unit and no neighbour,
        # so there is nothing for its size to disagree with. That exemption was
        # right for the master and its sub-meters and was never about the yard.
        #
        # ⚠ **AND THE COST OF LEAVING IT NULL IS NOW A SCREEN.** `G1` lets a
        # clerk search the depot in the words they are holding — *5/8 water
        # meter inventory* — and every one of this tenant's spares answered
        # nothing to *5/8*, because no seeded spare has ever said what size it
        # is. A demo that cannot demonstrate the feature it ships with reads as
        # a feature that does not work.
        #
        # The band is the SMALLEST in the tenant's ratified ladder, exactly as
        # the meters block chooses, and it moves no money: a spare bills
        # nothing, and once assigned it agrees with the meter it replaces
        # because both took the same first code.
        elif entry.get("unit_index") is None and entry.get("service"):
            spare_bands = seams.service_size_class_codes(entry["service"])
            if spare_bands:
                payload["size_class"] = spare_bands[0]
        if entry.get("uom"):
            payload["unit"] = entry["uom"]  # BR-AST-009 / rule 3 — explicit UoM
        valuation = entry.get("valuation") or {}
        if valuation.get("warranty_end"):
            # warranty_end is already a service-accepted field — it rides create.
            payload["warranty_end"] = valuation["warranty_end"]
        unit_index = entry.get("unit_index")
        if unit_index is not None:
            unit_id = units.get(unit_index)
            if unit_id is None:
                continue
            payload["unit_id"] = unit_id
            payload["install_date"] = INSTALL_DATE
        # No unit_index ⇒ no unit_id ⇒ BR-AST-011's leave-in-inventory path.
        services.create_asset(actor, payload)
        _apply_valuation(actor, entry)
        written += 1
    return written



def _seed_cr062_capacity_equipment(
    actor: Any, units: dict[int, str], existing: set[str]
) -> int:
    """**CR-062 D3–D7 — the equipment that turns a seeded capacity price into a
    seeded capacity BILL.** Solar panels, batteries and broadband lines.

    Three lanes each did a third of this on 2026-09-02 and none of them alone
    produced a dollar. `E3` seeded the Product Owner's `$14.0000` per kW; `D1`
    made the quantity the SUM of installed capacity rather than a COUNT of
    panels; **and a seeded solar line was still `$0.00`, because the estate had
    no panels on it.** Both of those lanes wrote that boundary down rather than
    leaving it to be discovered, and this is the block that closes it: with the
    Product Owner's own array planted, unit 4 bills **14 kW × $14.0000 =
    `$196.00`** with no further code anywhere.

    ⚠ **A SIZE CODE IS CHECKED AGAINST THE TENANT'S OWN RATIFIED LADDER AND THE
    ROW IS SKIPPED WHEN IT IS NOT THERE — IT IS NEVER WRITTEN BLIND AND NEVER
    DOWNGRADED TO NULL.** The two failures are not symmetrical and that is the
    whole reason this branch exists:

      * **a panel that is not planted** leaves the unit at `0 kW`, which is
        `BR-MET-108`'s ruled zero: `$0.00` on the document, honest, and visible
        to anybody comparing the estate against the bills;
      * **a panel planted with NO size class** makes `installed_capacity`
        unstateable, and `_stamp_installed_capacity` then refuses **the whole
        account's bill** by name (`installed_capacity_undetermined`) rather than
        totalling the panels it does recognise. On a demo tenant that is not a
        smaller number, it is a run that will not produce a document.

    So the safe direction is to plant nothing, say so in the log, and let the
    ruled zero stand. It is the same discipline `_container_size_class` applies
    one block up — the code comes from the ratified list or it does not come at
    all — with the consequence spelled out because here it is a bill and not a
    display value.

    An entry naming a service the tenant has not enabled is SKIPPED BY NAME, as
    everywhere else in this module: a water-only utility gets no solar panel and
    is told so, never a service point for a service it does not sell
    (`BR-MET-003`). Idempotent on the asset number (`BR-TEN-063`).
    """
    from apps.assets import seams

    enabled = seams.enabled_service_codes()
    ladders: dict[str, set[str]] = {}
    written = 0
    for entry in fixture.capacity_equipment_plan():
        asset_no = entry["asset_no"]
        if asset_no in existing:
            continue
        service = entry["service"]
        if service not in enabled:
            logger.info(
                "sample data (CR-062 D3-D7): %s not seeded — service %r is not enabled",
                asset_no,
                service,
            )
            continue
        if service not in ladders:
            ladders[service] = set(seams.service_size_class_codes(service))
        size_class = entry["size_class"]
        if size_class not in ladders[service]:
            logger.warning(
                "sample data (CR-062 D3-D7): %s not seeded — %r is not in this "
                "tenant's ratified %s size classes (BR-TEN-171). The unit keeps "
                "0 installed capacity and bills BR-MET-108's ruled $0.00, which "
                "is the safe direction: planting it with no size class would "
                "make the total unstateable and refuse the whole account's bill",
                asset_no,
                size_class,
                service,
            )
            continue
        unit_id = units.get(entry["unit_index"])
        if unit_id is None:
            logger.info(
                "sample data (CR-062 D3-D7): %s not seeded — unit index %s is "
                "not on this tenant",
                asset_no,
                entry["unit_index"],
            )
            continue
        services.create_asset(
            actor,
            {
                "asset_no": asset_no,
                "type": entry["type"],
                "service": service,
                "unit_id": unit_id,
                "install_date": INSTALL_DATE,
                # BR-AST-500 — the capacity this thing IS. For a SUMMING service
                # this is arithmetic and not a label: `SOL-P2` + `SOL-P4` +
                # `SOL-P8` is 14 kW (BR-TEN-171 / `total_capacity`).
                "size_class": size_class,
            },
        )
        written += 1
    return written


def _container_size_class(service: str) -> str | None:
    """The ratified band a seeded CONTAINER is (`BR-AST-500`, `DEF-2414`).

    Returns the code the fixture says these devices are — `TRASH_CART_SIZE`,
    matched against `BR-TEN-171`'s ratified list for the service and never
    trusted on its own — or the SMALLEST band when the fixture's stated one is
    not in this tenant's list, or `None` when the vocabulary does not answer
    for the service at all.

    ⚠ **THE FIXTURE'S STATED BAND IS PREFERRED OVER THE SMALLEST, AND THAT IS
    THE ONE PLACE THIS DIFFERS FROM THE METERS BLOCK.** Those meters have no
    declared physical size, so first-in-ratified-order is as good an answer as
    any. These carts DO: `trash_cart_plan`'s valuation has read *"r10 ballpark
    floor; a 96-gal cart"* since the day they were seeded, and seeding a
    35-gallon band onto a row whose own comment calls it a 96-gallon cart would
    put a contradiction into the demo tenant.

    **It moves no money on any seeded tenant** — no rate schedule in the seed
    carries a per-size override and `BASE-T` is flat (`BR-RAT-1010` case 1), so
    `pricing_inputs` returns the same NULL every-size group whichever band this
    picks, and every seeded bill is byte-identical either way. The band is
    DATA a utility records, not a price.

    ⚠ **AND ON THIS FIXTURE IT IS NOT WHAT MAKES TRASH BILLABLE** — the
    metered/unmetered declaration is (`BR-RAT-081`,
    `fixture.UNMETERED_ESTATE_SERVICES`), and a declared-unmetered service is
    never asked its size at all. This exists because the column is real, the
    screens read it, and `BR-RAT-1010` lets a charge code price per band the
    day a utility wants to.
    """
    from apps.assets import seams

    codes = seams.service_size_class_codes(service)
    if not codes:
        return None
    return fixture.TRASH_CART_SIZE if fixture.TRASH_CART_SIZE in codes else codes[0]


def _apply_valuation(actor: Any, entry: dict[str, Any]) -> None:
    """BR-AST-047 valuation onto ONE new seed — purchase cost (4dp, rule 2),
    purchase date, supplier, expected life.

    ⚠ A DIRECT write on this module's own rows, the `_tag` disposition, because
    `services._validate_asset` does not accept these fields yet — that
    acceptance is AST-W2/W4's half, and this function should collapse into the
    create payload the day it lands. Guarded on `purchase_cost__isnull` so a
    replay (or an operator's later edit) is never overwritten, and audited when
    it writes (CLAUDE.md rule 7: it is a stored money figure, even one that
    posts nothing — BR-AST-047).
    """
    valuation = entry.get("valuation")
    if not valuation:
        return
    row = models.Asset.objects.filter(
        tenant_id=_tenant_id(), asset_no=entry["asset_no"], purchase_cost__isnull=True
    ).first()
    if row is None:
        return
    row.purchase_cost = Decimal(valuation["purchase_cost"])
    row.purchase_date = date.fromisoformat(valuation["purchase_date"])
    row.supplier = valuation["supplier"]
    row.expected_life_years = int(valuation["expected_life_years"])
    row.save(
        update_fields=[
            "purchase_cost",
            "purchase_date",
            "supplier",
            "expected_life_years",
            "updated_at",
        ]
    )
    core_audit.write_row(
        action="asset.sample_valuation_set",
        entity_type="asset",
        entity_id=row.id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "asset_no": row.asset_no,
            "purchase_cost": str(row.purchase_cost),
            "purchase_date": row.purchase_date.isoformat(),
            "supplier": row.supplier,
            "expected_life_years": row.expected_life_years,
        },
    )


def retire_the_replaced_meter(actor: Any) -> bool:
    """Spec §4 case 3: the old serial comes off AFTER the June read.

    ⚠ **CALLED AFTER THE READS BLOCK, NOT INSIDE THE METERS BLOCK (DEF-660).**
    Returns True when it retired the meter and False when there was nothing to
    do (already terminal, or the meter is not seeded on this tenant) — the
    caller reports which, because "nothing to do" and "done" are different
    facts and a seeder that conflated them is how DEF-166 read.

    Through `retire_asset`, the same call S51's Retire control makes — so the
    assignment closes with a real `to_date` and the read chain genuinely crosses
    two registers rather than merely appearing to.

    DEF-597 (CR-028 debt sweep, 2026-08-22): this function used to pass a
    narrative string as the `reason` — not in BR-AST-021's ratified set — AND
    the wrong date key (`retired_on`; the contract reads `retire_date`), so
    `retire_asset` refused, the broad except logged one line, and every seeded
    tenant shipped with TWO active meters on the case-3 unit. Now: the ratified
    reason `replaced`, verbatim; the case-3 narrative lives in the lawful
    `replaced_by` link naming the new serial (retire_asset's contract carries
    no free-text note field — checked, not assumed); and a refusal RAISES so
    the seeder asserts its own outcome. There is no genuinely-can't case here:
    retire touches no reads, the meter carries no valuation (so no book-value
    treatment is demanded), and the replacement is created earlier in the same
    pass — any failure is a seeder bug, never an acceptable skip.
    """
    plan = _estate()
    if plan.primary is None:
        # No estate was seeded, so there is no case-3 meter to retire. This is
        # the "nothing to do" state, not a failure — the caller's own docstring
        # distinguishes the two and the reads block that calls this has already
        # refused with the reason.
        return False
    # CR-062 C8 — the swap is the FIRST metered service's demonstration, so
    # this retires that service's `W-5011` and nothing else. No later
    # metered service plants a replacement to retire.
    old_no = fixture.meter_no(plan.primary.code, fixture.CASE_METER_REPLACED)
    asset = (
        models.Asset.objects.filter(tenant_id=_tenant_id(), asset_no=old_no)
        # `status` is a FK — `.values("status")` yields the stage row's uuid,
        # so the old `== "retired"` replay guard could never be true (part of
        # DEF-597: the retire always re-ran and the refusal was swallowed).
        .values("id", "status__behavior_class").first()
    )
    if asset is None or asset["status__behavior_class"] == services.STAGE_TERMINAL:
        return False
    services.retire_asset(
        actor,
        str(asset["id"]),
        {
            "retire_date": RETIREMENT_DATE,
            "reason": "replaced",  # BR-AST-021's ratified set, verbatim
            "replaced_by": fixture.replacement_meter_no(plan.primary.code),
        },
    )
    return True


def seed_sample_aged_meters(actor: Any) -> int:
    """**The three meters wave M's nightly rule fires on** — `CR-070` `M5`.

    `M5`'s fixture line, verbatim: *"Fixture: `AST-04412` and two more meters
    past certification life; the drawing's seven rules, six On"*. The RULES are
    `apps/work/sample_data.py`'s; these are the SUBJECTS, and they are an
    assets block rather than a work one for a reason that is not a preference:
    **Work may not write `assets`** (`BR-WRK-002`, and `G78` fails the merge on
    a foreign write from Work's first commit). `apps/work/seams/assets_seam.py`
    READS them — `assets_past_certification` — and that is the whole contract.

    ⚠ **ITS OWN BLOCK, NOT THREE MORE ROWS IN THE METERS BLOCK ABOVE.** Both
    would seed the same three assets; only one of them reports on `S62` as a
    line an operator can read — *"Meters past their certification life"* — and
    only one of them can be seen to have failed. The Meters block writes ~130
    rows for a demo estate and three more inside it are invisible whether they
    land or not, which is exactly the shape `BR-TEN-060` exists to refuse. It
    also leaves that block's counts and its tests untouched.

    ⚠ **IN INVENTORY, WITH NO UNIT** — the fixture constant carries the full
    reasoning. In one line: assigning them would put a second live meter on a
    service point that already has one, and a work-order fixture must not move
    this tenant's billing.

    ⚠ **IDEMPOTENT ON THE ASSET NUMBER** (`BR-TEN-063`), like every block in
    this file, and the numbers are the fixture's so the check and the tag
    cannot drift apart.

    ⚠ **A SAVEPOINT PER ROW** (CLAUDE.md hard-won law 14). This runs inside
    tenancy's per-module `atomic`, and on PostgreSQL one refused INSERT aborts
    the WHOLE transaction — so a bare `except: continue` would discard every
    row already written at COMMIT while passing the entire SQLite suite. NOT
    tidiness; do not remove.
    """
    plan = _estate()
    if plan.primary is None:
        # A NAMED no-op rather than a silent one (BR-TEN-060). No enabled
        # service can hold a register, so a measuring asset cannot be created
        # at all — the rules still list on Work > Rules and the asset-age rule
        # simply has nothing to fire on. Reported rather than raised, because
        # the Meters block above has already said the same thing louder.
        logger.info(
            "sample data (CR-070 wave M): no meters past certification life were seeded — %s",
            plan.refusal_sentence,
        )
        return 0
    service, uom = plan.primary.code, plan.primary.uom

    existing = {
        asset.asset_no
        for asset in selectors.asset_list(filters={"status": "all"})
    }
    written = 0
    for entry in fixture.aged_meter_plan(service, uom):
        if entry["asset_no"] in existing:
            continue
        payload: dict[str, Any] = {
            "asset_no": entry["asset_no"],
            "type": entry["type"],
            "service": entry["service"],
            "unit": entry["uom"],  # BR-AST-009 / rule 3 — explicit, never inferred
            "meter_type": entry["meter_type"],
            "read_method": entry["read_method"],
        }
        try:
            with transaction.atomic():
                services.create_asset(actor, payload)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 wave M): %s was not created — %s: %s. The asset-age "
                "rule will raise one order fewer than the demo script expects",
                entry["asset_no"],
                type(exc).__name__,
                exc,
            )
            continue
        # BR-AST-047 — and it is what makes the meter OVERDUE: there is no
        # explicit certification_due on any seeded asset, so the seam derives
        # it as purchase_date + expected_life_years. Without this call the row
        # is a perfectly ordinary new meter and the sweep finds nothing.
        _apply_valuation(actor, entry)
        written += 1

    # BR-TEN-057 — this module's own write of its own tag, on the rows this
    # plan names and no others.
    _tag(
        models.Asset.objects.filter(
            tenant_id=_tenant_id(),
            asset_no__in=list(fixture.aged_meter_numbers()),
            is_sample=False,
        )
    )
    return written


def tag_sample_assets(asset_nos: Iterable[str]) -> int:
    """`BR-TEN-057` — THIS module's own write of its own tag, for rows another
    module's fixture created through `create_asset` (CR-068 wave H).

    ⚠ **IT EXISTS BECAUSE `create_asset` DOES NOT TAKE `is_sample` AND SHOULD
    NOT.** The flag is not a property of an asset a clerk is adding; it is a
    statement by a SEEDER about rows it planted, and `BR-TEN-057` puts that
    statement in the owning module — *"the tag is written by THIS module's own
    service on the sample path and by nobody else"*. Without this door a fixture
    in another app could only choose between a raw cross-module write (refused
    by `G84`) and leaving its rows untagged, which is `DEF-WRK-4117`: sample
    rows `BR-TEN-061` can never remove.

    Idempotent, and it only ever tags — it never clears a tag, so a real asset
    that happens to share a number is not reclassified by a fixture replay.
    """
    numbers = [str(number) for number in asset_nos if number]
    if not numbers:
        return 0
    return _tag(
        models.Asset.objects.filter(
            tenant_id=_tenant_id(), asset_no__in=numbers, is_sample=False
        )
    )


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — hard delete of this module's `is_sample = true` rows,
    sub-meters before their parents (the self-FK), reporting what it retained.

    A meter that has REadS against it is retained by name rather than deleted:
    `meter_reads.asset_id` is `ON DELETE NO ACTION`, so the delete would fail
    anyway, and a partial-and-named answer (BR-TEN-066) is what the rule asks
    for. Metering removes its own reads first — that is why BR-TEN-061 puts
    `meter_reads` at the head of the order.
    """
    tenant_id = _tenant_id()
    removed = 0
    retained: list[dict[str, Any]] = []

    assets_qs = models.Asset.objects.filter(tenant_id=tenant_id, is_sample=True)
    removed += models.AssetAssignment.objects.filter(tenant_id=tenant_id, is_sample=True).delete()[
        0
    ]
    # Sub-meters first (self-FK), then their parents — BR-TEN-061's own order.
    # Sub-meters before their parents (BR-TEN-061's self-FK clause). The
    # parent column is optional on this model, so it is read defensively rather
    # than assumed — a missing attribute must not turn a removal into a crash.
    ordered = sorted(assets_qs, key=lambda row: (getattr(row, "parent_asset_id", None) is None,))

    for asset in ordered:
        try:
            with transaction.atomic():
                asset.delete()
            removed += 1
        except Exception as exc:  # noqa: BLE001 — BR-TEN-066: name it, keep going
            retained.append(
                {
                    "label": f"meter {asset.asset_no}",
                    "reason": ("something you kept still references it — " f"{type(exc).__name__}"),
                }
            )
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    tenant_id = _tenant_id()
    return int(models.Asset.objects.filter(tenant_id=tenant_id, is_sample=True).count())


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W3 · TASK 3.12 — `A-10432`'s TWO METERS (B18 §5.2.1 · §5.2.4)
# ══════════════════════════════════════════════════════════════════════════
#
# The account detail's header draws exactly two service chips and each one
# CARRIES ITS METER NUMBER: `▪ ELECTRIC · M-4021` `▪ WATER · M-4022`, and the
# Meters tab draws the same two with `TYPE (AMI · Itron OpenWay CENTRON)`,
# install date, multiplier and last read. §5.2.4 asks for both, with four reads
# each — the reads are metering's half and land with `seed_sample_reads`.
#
# ⚠ **THEY RESOLVE BY UNIT NUMBER, NOT BY THE FIXTURE'S `unit_index`.** The
# CR-030 estate is a second plan (`core/sample_fixture.cr030_units_flat`) with
# no unit_index of its own, deliberately: indexing it into the 0..47 space would
# make every awkward-case constant in that file ambiguous.
#
# ⚠ **A METER ON A UNIT MINTS ITS SERVICE POINT** (BR-AST-011's assign-on-
# create, through metering's seam). `M-4021` is ELECTRIC, so on a tenant that
# does not sell electricity the create is refused BY THE SERVICE — reported by
# name here rather than swallowed, because a silently missing meter is a Meters
# tab that reads empty for no stated reason.


def _cr030_unit_no_to_id() -> dict[str, str]:
    """The estate's units, by unit number, through metering's published read."""
    from apps.assets import seams

    resolver = seams.resolve("metering", "units_list", kind="selectors")
    if resolver is None:
        return {}
    wanted = {unit["unit_no"] for unit in fixture.cr030_units_flat()}
    return {row.unit_no: str(row.id) for row in resolver() if row.unit_no in wanted}


def _seed_cr030_demo_meters(actor: Any, existing: set[str]) -> int:
    """`M-4021` (AMI electric) and `M-4022` (AMR water) on `1408 Elm Street ·
    Unit A`. Idempotent on the asset number, like every block here."""
    units = _cr030_unit_no_to_id()
    if not units:
        return 0
    written = 0
    for entry in fixture.CR030_A10432_METERS:
        if entry["asset_no"] in existing:
            continue
        unit_id = units.get(entry["unit_no"])
        if unit_id is None:
            continue
        payload: dict[str, Any] = {
            "asset_no": entry["asset_no"],
            "type": "meter",
            "service": entry["service"],
            "unit": entry["uom"],  # BR-AST-009 / rule 3 — explicit, never inferred
            "meter_type": entry["meter_type"],
            "read_method": entry["read_method"],
            "multiplier": entry["multiplier"],
            "unit_id": unit_id,
            "install_date": entry["valuation"]["purchase_date"],
        }
        try:
            # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
            # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
            # (this block runs inside tenancy's per-module `atomic`), so without it the
            # work already done is lost at COMMIT. NOT tidiness — do not remove.
            with transaction.atomic():
                services.create_asset(actor, payload)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-030 W3): %s (%s) was not created — %s: %s. The account "
                "detail's Meters tab will be short one row and the header one chip",
                entry["asset_no"],
                entry["service"],
                type(exc).__name__,
                exc,
            )
            continue
        _apply_valuation(actor, entry)  # BR-AST-047
        written += 1
    return written


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16) · CR-028/B16 §9 AST-W0-T1 (PO 2026-08-22)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane) · AMENDED 2026-08-22 by story-coder (CR-028 AST-W0 lane — the r10 shape: trash carts closing DEF-496, master+subs, net meter in inventory, the two missing BTM kinds, aged inventory stock, BR-AST-047 valuation) · AMENDED 2026-08-26 by the CR-039 wave A lane (DEF-795 — meters, sub-meters, the master and its subs and the inventory spares are built in the tenant's own backbone service; the net meter keeps its electric; `if not units: return 0` becomes a BlockCannotRun naming metering's premises block upstream)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel serves this through tenancy's endpoints) E=deferred(same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: 48 water meters and not the spec's 96 — a sewer line priced as 40% of the water usage charge reads no register, and 48 unread sewer meters would bury the three deliberately unreadable ones (argued in full in the module docstring; the spec sentence is amended in the same commit) · a meter carrying reads is RETAINED by name on removal rather than deleted, because meter_reads.asset_id is ON DELETE NO ACTION and BR-TEN-066 rules removal partial-and-named · [CR-028 AST-W0] _apply_valuation writes the BR-AST-047 fields DIRECTLY on this module's own rows (the _tag disposition, audited, isnull-guarded): services._validate_asset does not accept them yet — that acceptance is AST-W2/W4's half and this backfill collapses into the create payload the day it lands · the net meter is seeded IN INVENTORY, not assigned: assigning it would mint an electric service point with no read behind it and a phantom missing-read in the ready-to-run July batch deletes the PO's acceptance test; its export reads are metering's W2 half
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
