# ── Trace ──────────────────────────────────────────────
# Change:   CR-010 item 1 — the FULL lists. PO verbatim: *"also for each
#           configure table - you need to see all possible items thata re
#           reuqired; currently youa re only looking at sample; we have to
#           provide a full possible list"*   Screens: S8 (Settings → Configure
#           → Reference data)
# Rules:    BR-TEN-012/013 (what seeds, and what may legitimately skip) ·
#           BR-TEN-067 (structural vs discretionary) · BR-TEN-077 (a content
#           change needs a fixture VERSION bump) · BR-MET-034 · BR-MET-084 ·
#           BR-CUS-055 · BR-CUS-067 (the module-owned ratified constants)
# Tests:    this file
# Impacts:  apps/tenancy/fixtures/lookup_defaults.json · apps/metering/
#           services.py (SEED_PREMISES_TYPES · SEED_UNIT_TYPES) ·
#           apps/customers/services.py (SEED_ACCOUNT_STATUSES ·
#           SEED_ACCOUNT_SUBTYPES)
# ───────────────────────────────────────────────────────
"""THE MEASUREMENT CR-010 item 1 asked for, made permanent instead of reported once.

The Product Owner's instruction is that every reference list must be *"the full
possible list"* a small utility actually operates on, not the starter rows a lane
happened to need. Answering that needs a number per list, and the number the
repository kept giving was **stale within a day** — the seed-map's own predecessor
was reviewed on 2026-08-17 and by the next morning charge codes had gone 6 → 25,
units of measure 6 → 26 and the chart of accounts partial → 33.

So this file pins what a **freshly provisioned tenant** actually receives, list by
list, measured out of the product rather than out of a document. Two things it is
for, and the second is the one that matters:

  1. anybody re-running CR-010's measurement reads the table below instead of
     re-deriving it, and the table cannot be wrong because the test asserts it;
  2. **vocabulary cannot change without the record changing with it.** Adding a
     row to a seeded list is a change to what every customer's product says, and
     the sign-off rule of 2026-08-11 makes it the PO's to approve. The fixture
     already has a digest+version guard (BR-TEN-077); the four lists seeded from
     module CONSTANTS have none, and this is theirs.

⚠ WHAT THIS FILE DELIBERATELY DOES NOT DO. It does not assert a list is *right*.
Nine of these twenty are shorter than a real water/electric/gas utility needs and
the drafted additions are with the PO — a test cannot ratify vocabulary, and one
that pinned a guess would make the guess look signed.
"""

import pytest

from apps.tenancy import services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import brazos  # noqa: F401 — a fixture

pytestmark = pytest.mark.django_db

#: list code → (rows a fresh tenant receives, the r10 prototype card's own
#: badge, source of truth for the content).
#:
#: The r10 column is `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`'s card
#: registry (around line 10156), which carries a row-count badge per card. It is
#: the closest thing to a design-side answer to *"how many should there be"* and
#: is recorded here so the two can be compared without opening the prototype.
#: `None` means the prototype has no card for that list at all.
#:
#: WHERE THE TWO DISAGREE, NEITHER IS AUTOMATICALLY RIGHT: r10 is a drawing and
#: its badges are illustrative counts, not a ratified set. The disagreements are
#: the AGENDA for the PO, listed in the CR-010 write-back — they are not defects
#: and this test does not treat them as any.
INVENTORY: dict[str, tuple[int, int | None, str]] = {
    # ── platform fixture (lookup_defaults.json, V2.18.0.0 · digest-pinned) ──
    # ── 26 → 27 on 2026-09-02 · `CR-063` task A3 ─────────────────────────
    # `connection` / "Connection", SCOPED TO FIRE — the eleventh utility
    # service, added because a real utility is being onboarded and it sells
    # fire protection. The unit is `connection` and NOT `line` — originally
    # because a private hydrant is not a line and both were billed off the one
    # tick. **The PO removed the hydrant on 2026-09-03 and the unit still does
    # not move**: a fire line IS a service connection, and BR-TEN-072 forbids
    # renaming a seeded code in any case. Fixture V2.48.0.6, digest re-pinned.
    #
    # ⚠ **THIS FIGURE STAYS A LITERAL WHILE FOUR COPIES OF IT IN
    # `test_us_ten_009_011_lookups.py` WERE DERIVED THE SAME DAY, AND THE
    # DIFFERENCE IS THIS FILE'S WHOLE POINT.** There the number is
    # scaffolding for a case about something else; HERE the number IS the
    # assertion — *"vocabulary cannot change without the record changing with
    # it"* — so typing it is what makes a seeded-list change a visible diff
    # somebody approves. Deriving it here would delete the check.
    "uoms": (27, 6, "fixture"),
    "charge_codes": (23, 13, "fixture"),  # 25 in the fixture; 2 deposit codes
    #                                       are deliberately omitted and named
    "reason_codes": (5, 5, "fixture"),
    "payment_methods": (7, 7, "fixture"),
    "meter_types": (5, 5, "fixture"),
    # ── 5 → 8 on 2026-08-27 · BR-MET-142 (PO ruling closing OQ-392) ────────
    # `drive_by` "Drive-by", `self_read` "Self-read", `field_visit` "Field
    # visit" join AMI · AMR · walk-by · Manual · Mobile. Fixture V2.48.0.2,
    # digest re-pinned; mirrored in `apps.assets.services.SEED_READ_METHODS`.
    #
    # ⚠ **THE PO DELEGATED THIS ONE EXPLICITLY, WHICH IS RARE ENOUGH TO WRITE
    # DOWN, AND IT IS WHY THIS EDIT IS LAWFUL.** This assertion refuses to be
    # quieted by anyone but the PO — *"a seeded list changed size … it needs the
    # PO's word (sign-off rule 2026-08-11) and this table updated in the same
    # commit — not a green suite."* The PO's word is the delegation itself:
    # *"(a) Rule each onto one of the five or you can add new categories"*,
    # which authorises the list GROWING and hands the choice to the build. So
    # unlike the `areas` row below, the FIGURE is not left on the agenda — the
    # permission covered adding categories and three is what adding these three
    # costs. **What was shown, in plain English with the number:** *"a brand-new
    # utility's Read methods list goes from 5 rows to 8 — AMI, AMR, walk-by,
    # Manual, Mobile, plus Drive-by, Self-read and Field visit. Readings your
    # old system recorded as drive-by, self-read or a field visit stop saying
    # 'method not stated' and start saying what they were."*
    #
    # The r10 column stays at FIVE and is NOT "corrected": it is a fact about a
    # drawing made on 2026-08-16, and a disagreement here is the agenda, never a
    # defect (see the note above).
    "read_methods": (8, 5, "fixture"),
    "asset_types": (12, 12, "fixture"),
    #: ⚠ STILL FIVE ON 2026-09-07 AND TWO OF THE NAMES CHANGED, WHICH IS THE
    #: ONE KIND OF VOCABULARY CHANGE THIS TABLE CANNOT SEE. PO: *"use only
    #: Inventory and Installed"* — `Inventory/Spare` → Inventory,
    #: `Installed/Active` → Installed. A count is blind to a rename, so the
    #: NAMES are asserted in `tests/test_po_20260907_stage_names.py` instead,
    #: beside the migration that carries them to tenants that already exist.
    "asset_statuses": (5, 5, "fixture"),
    # 4 → 8 on 2026-08-26. BR-CUS-094 (PO 2026-08-24) expanded the signed
    # consumer-category vocabulary from four to SEVEN — Residential ·
    # Commercial · Industrial · Agricultural · Institutional · Municipal ·
    # Builder or developer — and made `government` LEGACY: unselectable on a
    # NEW record, lawful and filterable everywhere else. Seven selectable plus
    # the legacy row is eight, and migration 0019 adds the four that were
    # missing.
    # ⚠ **THE PO CONFIRMED THE FIGURE ITSELF, WHICH IS WHY THIS EDIT IS
    # LAWFUL.** This assertion refuses to be quieted by anyone but them — *"a
    # seeded list changed size … it needs the PO's word (sign-off rule
    # 2026-08-11) and this table updated in the same commit — not a green
    # suite."* Put to them in plain English with the number: *"a brand-new
    # utility's customer-category list goes from 4 rows to 8 — your seven
    # selectable categories, plus `government` kept as a legacy row so existing
    # accounts stay valid and findable."* PO, 2026-08-26: **"this si correct"**.
    # ⚠ **IT WAS RED FOR TWO DAYS AND NOBODY READ IT (DEF-748).** The guard
    # fired the moment BR-CUS-094 landed and did its job perfectly; the finding
    # died in a scrollback, because this suite runs for tens of minutes, already
    # carries unrelated failures, and `-q` prints a failure as an `F` in a
    # progress bar nobody maps back to a name. The lesson is NOT that another
    # gate was needed — it is that a ruling which changes a signed vocabulary
    # must sweep the guards that MEASURE it, not only the code that READS it.
    # The r10 column stays at FOUR and is NOT "corrected": it is a fact about a
    # drawing made before the ruling, and a disagreement here is the agenda,
    # never a defect (see the note above).
    # ⚠ **THE FIXTURE COLUMN GOES 4 → 8 ON 2026-09-17 AND THE SOURCE NOTE
    # CHANGES WITH IT.** PO ruling *"utility can get their own account types"*
    # (`BR-CUS-1079`): the rows are the TENANT's, seeded per tenant from the
    # fixture at `V2.48.0.12`. The four missing codes had been missing since
    # `BR-CUS-094` and were harmless only while the table was global.
    "account_types": (8, 8, "fixture · TENANT rows, seeded per tenant"),
    # ── 4 → 7 on 2026-08-27 · CR-039 wave E task 22 (BR-MET-066c) ──────────
    # The three SUB-AREAS BR-MET-066b permitted on 2026-08-16 and that nothing
    # had ever created: `NORTH-NE` "NE" and `NORTH-NW` "NW" under NORTH,
    # `EAST-SE` "SE" under EAST. Fixture V2.48.0.1, digest re-pinned.
    #
    # ⚠ **THE PO AUTHORISED SUB-AREAS EXISTING. THE PO WAS NOT SHOWN THE
    # FIGURE 7 OR THE THREE NAMES, AND THIS COMMENT IS WHERE THAT IS RECORDED
    # RATHER THAN GLOSSED.** The sign-off rule of 2026-08-11 is explicit that
    # *"a signature covers only what was shown"*, and what was shown is one
    # question — *"Why you dont have sub areas below - Areas metering 4 North
    # district · Downtown · East district · Industrial corridor"* — plus
    # CR-039's own wave list, which carries "seed sub-areas" as task 22. That
    # authorises the LIST GROWING; it does not ratify how far.
    #
    # So this row is updated in the SAME COMMIT as the code, which is what this
    # file exists to force, and the figure goes ON THE AGENDA rather than being
    # treated as signed. **What to put to the PO, in plain English with the
    # number:** *"a brand-new utility's Areas list goes from 4 rows to 7 — your
    # four districts, plus NE and NW under North district and SE under East
    # district. Downtown and Industrial corridor get none, so the demo can show
    # a district that has sub-areas and one that has not."*
    #
    # The r10 column stays at **8** and is NOT "corrected": r10's SET-04 card
    # declares 3 · 2 · 2 · 1 sub-areas and NAMES six of those eight nowhere, so
    # matching it would mean inventing six names. A disagreement here is the
    # agenda, never a defect — the note above says so, and this is the second
    # row on this table to be in exactly that position.
    "areas": (7, 8, "fixture"),
    # ── 9 → 40 on 2026-08-27 · CR-039 wave E task 20 (BR-TEN-171), AND THE
    # KEY ITSELF MOVED (BR-TEN-170) ───────────────────────────────────────
    # PO verbatim: *"Water (has 4) Pipe diameter keep the four; add 1½" · 3" ·
    # 4" · 6" - you need 1 inch 2 inch also 5 inch also; rest all are correct
    # in this … it is utility service size class"*. Water 9, electric 6, gas 4,
    # trash 7, storm water 4, solar 4, broadband 3, thermal chilled water 3.
    # Fixture V2.48.0.3, digest re-pinned.
    #
    # ⚠ **THE FIGURE 40 *WAS* SHOWN, WHICH MAKES THIS ROW DIFFERENT FROM THE
    # `areas` ROW ABOVE IT.** That one records a list the PO authorised GROWING
    # without being shown how far. Here the PO was shown the table service by
    # service and answered on it — *"rest all are correct in this"* — and
    # CORRECTED one row of it, which is what a reader of a real table does. So
    # 40 is ratified arithmetic, not a lane's extrapolation.
    #
    # ⚠ **BUT THE SAME SENTENCE DOES NOT RATIFY EVERYTHING IN THE LIST'S REACH.**
    # Two of the ten services on that table carried a UNIT and no boundary —
    # thermal STEAM (*"by thousand pounds per hour"*) and BATTERY (*"by kW and
    # kWh together … the pair is the class"*) — so those two seed NOTHING and
    # are OQ-560 / OQ-561. A signature covers only what was shown (PO
    # 2026-08-11). **Sewer's zero is a different fact**: it is RULED to have
    # none, because sewer is priced as a share of the water usage charge
    # (BR-RAT-015) and reads no register. `service_size_classes.
    # UNBANDED_SERVICE_DIMENSIONS` is the register that keeps the two zeros
    # apart, and this comment is why it exists.
    #
    # **THE r10 COLUMN STAYS AT NINE AND IS NOT "CORRECTED".** r10's card
    # registry (line 10167) reads `['sizes','Meter size classes','5/8"–4" water ·
    # 1φ/3φ electric · gas classes · carts','9']` — a badge of **9**. That is a
    # fact about a drawing made on 2026-08-16, eleven days before the PO ruled
    # forty, and this column records the design side exactly as it is. The
    # 40-vs-9 gap is the AGENDA, never a defect — the note at the top of this
    # table says so, and this is the third row to sit in that position after
    # `areas` and `account_types`. **It is also the largest such gap in the
    # file**, and honestly so: the ruling did not adjust r10's list, it
    # replaced the premise, because r10's card could only ever have described
    # metered services.
    # ── 53 → 60 on 2026-09-02 · `CR-063` tasks A4/A5 ─────────────────────
    # FIRE arrived with seven: six line diameters `FL-2` … `FL-12` and `HYD`, a
    # private hydrant. They are BANDS — the size PICKS the price and the COUNT
    # multiplies it, which is trash's arithmetic and not solar's, and is the
    # whole of the PO's *"this will behave exactly like trash"*.
    #
    # ── 60 → 59 on 2026-09-03 · PO ruling ────────────────────────────────
    # ⚠ **THE FIRST TIME A PRODUCT OWNER HAS TAKEN A ROW OFF THIS TABLE.** PO
    # verbatim: *"remove private hydrants from list"*, after *"hydrants are
    # assets not utility service as of now"*. `HYD` at `$25.0000` is withdrawn,
    # fire goes 7 → 6, and the warehouse that billed `$110.00` now bills
    # `$60.00` — `−$50.00` a month on a real customer. `BR-TEN-071` deletes
    # nothing, so a tenant that already holds `HYD` keeps it; the withdrawal
    # means no NEW tenant receives it, and this count measures what a NEW
    # tenant receives.
    #
    # ⚠ **AND THESE SIX ARE STILL THE ONLY ROWS ON THIS WHOLE TABLE THE PRODUCT
    # OWNER HAS NEVER RATIFIED AS A PRICE LIST.** Every other figure here traces
    # to a ruling; fire's were authored by the `CR-063` lane as a seeded default
    # a tenant edits on Settings, because the product needed a list before the
    # going-live customer could give us theirs. **Removing one row is not
    # ratifying the rest** — `OQ-1360` is that question and it stays OPEN — so
    # this row's 59 is a measurement of what ships, and emphatically not a claim
    # that six is the right number.
    "service_size_classes": (59, 9, "fixture · mirrors service_size_classes.py"),
    "occupancy_statuses": (5, 5, "fixture"),
    "device_types": (6, 6, "fixture"),
    "certification_types": (6, 6, "fixture"),
    # ── seeded from the OWNING MODULE's ratified constant, by design: one copy
    # of the law, nothing to drift (the DEF-026 premises_types posture). These
    # four have NO digest guard, which is why this test exists for them.
    "premises_types": (6, 7, "apps.metering.services.SEED_PREMISES_TYPES"),
    "unit_types": (5, 7, "apps.metering.services.SEED_UNIT_TYPES"),
    # 5 → 6 on 2026-08-25: BR-CUS-107 (PO ruling closing DEF-701) adds
    # `disconnected` / "Disconnected" / `non_billable`, the state a CUT account
    # is in. The fixture carries the same six at V2.48.0.0. The r10 badge stays
    # at FIVE and is not "corrected": it is a fact about a drawing made on
    # 2026-08-16, nine days before the ruling, and this column records the
    # design side exactly as it is — a disagreement here is the agenda, never a
    # defect (see the note above).
    "account_statuses": (6, 5, "apps.customers.services.SEED_ACCOUNT_STATUSES"),
    #: ⚠ 12 → 13 ON 2026-09-07 (PO: *"please add Governtment in it"*) — the
    #: general Government subtype beside Municipal buildings, Schools and Parks
    #: & facilities. Not a duplicate of the platform account TYPE of the same
    #: name: this is the tenant-editable level beneath it (BR-CUS-067).
    "account_subtypes": (13, 4, "apps.customers.services.SEED_ACCOUNT_SUBTYPES"),
    # ── the two that are legitimately not a flat count ─────────────────────
    #: State-dependent: FIVE Texas authorities for a Texas signup plus the
    #: County/City/Special-district scaffold every state gets — and the Texas
    #: `City` row shares its NAME with the scaffold's, so a Texas tenant lands
    #: on SEVEN and not eight.
    #:
    #: ⚠ 5 → 7 ON 2026-08-18, AND THE RATES ARE NO LONGER BLANK FOR TEXAS
    #: (DEF-254 → DEF-273). The comment here used to read *"NO RATES — a wrong
    #: tax rate charges real customers real money"*, which was correct while
    #: nobody had ruled the figures. The PO then ruled them twice — *"Tax
    #: jurisdiction rates (5 TX rows) - already answered"*, *"I ahve already
    #: answered it; close it"* — and the answer is r10's own tax table, so a
    #: Texas tenant now seeds five priced `taxes` rows WITH their conditions
    #: (residential exemption, inside-city scope, electric-only). The ALL
    #: scaffold every other state gets is STILL rate-less: that is the
    #: 2026-08-17 ruling and it is not reversed.
    "tax_jurisdictions": (7, 5, "fixture · state-dependent"),
    #: THREE, by ruling (BR-AST-048, PO 2026-08-22 — CR-028): one GENERATED
    #: system default per assets import target (Meters · Sub-meters · Devices
    #: default), derived from the runner's own target contract so the CR-025
    #: sample round-trips with zero mapping work. TENANT maps are still never
    #: seeded — the 2026-08-16 reasoning stands for those (a fixture cannot
    #: describe a tenant's own file layout); only the generated defaults ship.
    #: ⚠ **3 → 4 ON 2026-08-27, AND IT IS A CORRECTION, NOT A CHANGE — DEF-881.**
    #: `import_runs.DEFAULT_MAPPING_TEMPLATES` gained `accounts_default`
    #: ("Accounts default") when CR-030 W1 made `accounts` the sixth import
    #: target (BR-CUS-075), and `default_import_mapping_entries`' own docstring
    #: has said *"the four defaults"* ever since. This row was never told, so
    #: this whole test has been RED since that landing — pinning a count by hand
    #: in a file whose entire purpose is to pin counts by hand, and the second
    #: row on this table to go stale that way. Nothing in the PRODUCT is wrong:
    #: a fresh tenant genuinely receives four generated defaults and always did.
    #: ⚠ **4 → 6 ON 2026-09-07, AND THIS TIME THE ROW WAS TOLD.** PO ruling,
    #: verbatim: *"it is required for - Premises, Units, Meters, Sub meter,s
    #: Assets, Parts, Accounts, Reading - including all readings - Flat, Demand
    #: based, Seasonal, Peak , off peak, etc"*. `premises` and `units` are the
    #: two a utility loads FIRST — the README's build order is Premises → Units
    #: → Assets → Accounts — and they were the two targets with no starter while
    #: all four that come after them had one. `Parts` (no import target exists)
    #: and the reads (a separate importer with its own `template_csv`) are the
    #: same ruling and are NOT counted here: neither is built yet and both are
    #: named in the decision log of 2026-09-07 rather than quietly dropped.
    "import_mappings": (6, 6, "generated from the runner's target contract (BR-AST-048)"),
    # ── EIGHT LISTS THAT JOINED `SEED_LIST_OWNERS` AND NEVER JOINED THIS TABLE
    # ⚠ **THIS FILE HAD BEEN RED SINCE 2026-09-04 AND NOTHING SAID SO
    # (`DEF-TEN-4486`).** `work_order_types`, `work_skills`, `work_priorities`,
    # `work_safety_kits` and `work_parts_categories` arrived with CR-070 wave C
    # on 2026-09-04; `owner_categories`, `bank_accounts` and
    # `bank_rec_difference_reasons` the same way. Every one of them was
    # registered in the PRODUCT correctly — the drift is entirely in this
    # record, which is the third time a row here has gone stale by omission
    # (read methods, then the accounts default, now eight at once).
    #
    # **THE COUNTS ARE MEASURED, NOT RATIFIED, AND THE DIFFERENCE MATTERS.**
    # This table's job is *"vocabulary cannot change without the record changing
    # with it"*, and a list that is in neither state is guarded by nothing at
    # all. Registering them starts the guard; it does not endorse the values,
    # exactly as the file's own header says it cannot. Each figure below is what
    # `reference_data_report()` reports on a freshly provisioned tenant today.
    #
    # The r10 column is `None` for all eight: the 2026-08-16 prototype has no
    # card for a work-management or bank-reconciliation list, which is a fact
    # about a drawing and not a gap (see the note at the top of this table).
    "work_order_types": (8, None, "apps.work.services — CR-070"),
    "work_skills": (8, None, "apps.work.services — CR-070"),
    "work_priorities": (4, None, "apps.work.services — CR-070"),
    "work_safety_kits": (4, None, "apps.work.services — CR-070"),
    "work_parts_categories": (4, None, "apps.work.services — CR-070"),
    # `CR-168-BRC10` P0.4 (2026-10-04, lane SRV-1) — five hold reasons.
    "work_hold_reasons": (5, None, "apps.work.services — CR-168"),
    "owner_categories": (5, None, "fixture"),
    "bank_rec_difference_reasons": (9, None, "fixture"),
}

#: ⚠ **A LIST CAN BE DECLARED IN `LOOKUP_LISTS` AND NOT IN `SEED_LIST_OWNERS`,
#: AND UNTIL 2026-09-07 NOTHING IN THIS FILE COULD EXPRESS THAT.** The two
#: assertions below read two different registries — the first walks
#: `SEED_LIST_OWNERS` (what SEEDS), the second walks `reference_data_report()`,
#: which walks `LOOKUP_LISTS` (what has a CARD). They agreed when this file was
#: written, so one table served both; `bank_accounts` is the first list to be
#: one and not the other, and with a single table the two assertions became
#: mutually unsatisfiable — put it in and the first fails, leave it out and the
#: second does.
#:
#: So it is named HERE instead, with its own count, and both guards keep working
#: at full strength: a new SEEDED list still fails the first assertion by name,
#: and a new CARDED list still fails the second. What is no longer possible is
#: for the difference between the two registries to be indistinguishable from
#: a mistake.
#:
#: `bank_accounts` is ZERO ON PURPOSE and must stay legible as such: a tenant's
#: bank accounts are its own and no fixture can know them. The list is
#: registered so the S8 card exists and says so, which is DEF-016's own rule —
#: a list may have no rows; it may never be empty with nobody having written
#: down why.
CARDED_BUT_NOT_SEEDED: dict[str, tuple[int, int | None, str]] = {
    "bank_accounts": (0, None, "tenant-entered — no fixture rows by design"),
}


def test_the_twenty_seeded_lists_are_exactly_the_twenty_this_file_measures():
    """The inventory cannot silently miss a list somebody added.

    RED-PROOF, and it is the reason this assertion is first: adding a
    twenty-first list to `SEED_LIST_OWNERS` without a row here fails with that
    list's name — which is the DEF-017 failure shape (a list in neither
    registry, seeded by a side effect, reported by nothing).
    """
    declared = {code for code, _owner in tenancy_services.SEED_LIST_OWNERS}
    assert declared == set(INVENTORY), (
        "SEED_LIST_OWNERS and this inventory have drifted: "
        f"only in the product {sorted(declared - set(INVENTORY))}, "
        f"only here {sorted(set(INVENTORY) - declared)}"
    )


def test_a_fresh_tenant_receives_the_measured_number_of_rows_in_every_list(brazos):
    """THE MEASUREMENT ITSELF, off a provisioned tenant.

    `reference_data_report()` is the product's own per-list count — the same
    read the S8 cards and `seed_demo`'s report use — so this measures what an
    operator sees, not what a fixture file contains.

    A list reported `uncounted` has no registered lookup handler and therefore
    no live count; its seed-ledger figure is used instead, which is what that
    state exists to carry.
    """
    with tenant_ctx(brazos):
        report = tenancy_services.reference_data_report()

    measured = {}
    for row in report["lists"]:
        measured[row["list"]] = row["count"] if row["count"] is not None else row["seed_run_count"]

    expected = {
        code: rows
        for code, (rows, _r10, _src) in (*INVENTORY.items(), *CARDED_BUT_NOT_SEEDED.items())
    }
    assert measured == expected, (
        "a seeded list changed size. That is a change to the vocabulary every "
        "customer's product speaks, so it needs the PO's word (sign-off rule "
        "2026-08-11) and this table updated in the same commit — not a green "
        "suite. Differences: "
        + str(
            {
                code: (expected.get(code), measured.get(code))
                for code in set(expected) | set(measured)
                if expected.get(code) != measured.get(code)
            }
        )
    )


def test_no_seeded_list_is_quietly_empty(brazos):
    """DEF-016's rule, re-asserted from the item-1 angle.

    A list may legitimately have no rows — `import_mappings` does, and says why
    on screen. What it may never be is empty with nobody having written down a
    reason. This is the assertion that turns "the full list is short" into a
    question somebody is asked, rather than a blank card.
    """
    with tenant_ctx(brazos):
        report = tenancy_services.reference_data_report()
    assert (
        report["unexplained"] == []
    ), f"UNEXPLAINED empty reference list(s): {report['unexplained']}"


@pytest.mark.parametrize(
    ("constant_path", "expected_rows"),
    [
        ("apps.metering.services.SEED_PREMISES_TYPES", 6),
        ("apps.metering.services.SEED_UNIT_TYPES", 5),
        # BR-CUS-107 (2026-08-25) — six, not five.
        ("apps.customers.services.SEED_ACCOUNT_STATUSES", 6),
        ("apps.customers.services.SEED_ACCOUNT_SUBTYPES", 13),
    ],
)
def test_the_module_owned_constants_carry_the_measured_number_of_rows(constant_path, expected_rows):
    """The four lists the fixture's digest guard cannot see.

    `lookup_defaults.json` is content-hashed and refuses a change without a
    version bump (BR-TEN-077). These four live in Python, deliberately — one
    ratified source per list, so the fixture and the module cannot disagree —
    and that same choice puts them outside the digest. Editing one is exactly as
    much of a vocabulary change as editing the fixture, and until this test
    existed nothing said so.
    """
    from importlib import import_module

    module_path, _, attribute = constant_path.rpartition(".")
    constant = getattr(import_module(module_path), attribute)
    assert len(constant) == expected_rows, (
        f"{constant_path} now has {len(constant)} rows, not {expected_rows}. "
        "Seeded vocabulary is the PO's to approve (sign-off rule 2026-08-11): "
        "put the rows to them in plain English, then update this figure and "
        "tests/test_cr010_reference_list_inventory.py's INVENTORY together."
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 item 1 (12-governance/11-change-requests.md, PO 2026-08-17)
#         + item 0's count, reconciled against the r10 card registry
#         (05-prototype/r10-2026-08-16/SMARTBillHub.dc.html, ~line 10156)
# generated: 2026-08-18 by the CR-010 silent-seed-gaps lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — this measures existing seeded
#            data through the existing report) E=deferred(no-frontend-half —
#            the S8 cards already render every list with its live count)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check✔ · black --target-version py311✔ · pytest this file: 7
#        passed · RED-PROVED: changing one expected figure (uoms 26 → 27) fails
#        with `Differences: {'uoms': (27, 26)}`, which is the drift this file
#        exists to catch
# exceptions: this file measures and pins; it does NOT ratify. Nine of the
#             twenty lists are shorter than a real water/electric/gas utility
#             needs and the drafted additions are with the PO (sign-off rule
#             2026-08-11) — a test that pinned a guess would make the guess
#             look signed. Two lists are excluded from any proposal because
#             their rows carry money: charge_codes and tax_jurisdictions.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
