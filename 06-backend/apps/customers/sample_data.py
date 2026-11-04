# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S17, S18,
#           S20, S21 (the accounts and customers this writes) · S8 (Sample
#           data panel, BR-TEN-069)
# Rules:    BR-TEN-056 (the sample set) · BR-TEN-057 (`is_sample` on the owning
#           row) · BR-TEN-061 (removal order) · BR-TEN-063 (idempotent,
#           audited) · BR-TEN-065 as AMENDED 2026-08-16 (sample accounts are
#           ACTIVE, because the fixture must be billable) · BR-CUS-017 (one
#           occupying account per unit) · BR-CUS-018 (a new account is a draft
#           until something activates it) · BR-CUS-054 (the customer entity and
#           its N:M link) · BR-CUS-055 (status behaviour classes) ·
#           BR-CUS-048 (buckets age FORWARD from the cutover as-of date) ·
#           BR-CUS-049 (opening JEs dated at cutover, immutable) ·
#           BR-TEN-043 (event-time; see `demo_cutover_on`'s own block) ·
#           BR-TEN-081 (the tenant's own day)
#           ⚠ CR-030 W5 T5.11 adds: BR-SHL-046 (move-out is SIX steps — PO
#           2026-08-24, closing DEF-648, superseding §5.6.2's `of 4`) ·
#           BR-CUS-081 (settle and refund the difference) · BR-CUS-082 (a debt
#           surviving closure is still chased, ladder restarts at TIER 1) ·
#           BR-CUS-096 (an open dispute HOLDS the excess) · BR-CUS-097 (a
#           sub-account's residue goes to its master) · BR-MET-107 (an unbanked
#           export credit is applied to the FINAL BILL) · BR-CUS-057 (deposit
#           interest — NOT BUILT, which is why every drawn settlement gaps)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py ·
#           06-backend/tests/test_cr030_w1_import_seed.py (CR-030 W1 T1.23) ·
#           06-backend/tests/test_def629_seed_cutover.py (DEF-629) ·
#           06-backend/tests/test_w5_move_in_out_cases.py (CR-030 W5 T5.11/5.12)
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves the seam) ·
#           apps/billing (bills these accounts) · apps/payments (pays them)
# ───────────────────────────────────────────────────────
"""customers' half of the sample set: one account per seeded unit (DEF-153).

⚠ **THIS LINE SAID "the 48 accounts" UNTIL 2026-09-02 AND THE ESTATE NOW HOLDS
50** (`CR-062` addendum J3/J4 appended a municipal building and an industrial
plant). The count lives in `core/sample_fixture.UNIT_COUNT` and is written
nowhere else; a literal here is a sentence that outlives the thing it counts.

BR-TEN-065 IS AMENDED, AND THE AMENDMENT IS THE WHOLE REASON THIS LANE EXISTS
------------------------------------------------------------------------------
BR-TEN-065 (PO ruling 2026-08-10, OQ-080) seeded every sample account
NON-BILLABLE — `Pending activation` — and said so with its consequence stated
rather than buried: *"the sample set therefore cannot demonstrate a bill run."*

That consequence is exactly what the Product Owner asked to be removed on
2026-08-16, verbatim: *"if we are able to seed the data refernece as well as
transaction data, then we can test the application end to end and see what are
the issues; thiswill be human checking"* — and the fixture spec ruled the same
day states it as a table: **June and July BILLED and mostly PAID.** An account
in `Pending activation` cannot be billed, so the later ruling supersedes the
earlier one and these accounts are seeded **Active**.

The amendment is written into
`04-docs/05-modules/01-tenancy/02-business-rules.md`, dated, with both quotes,
BEFORE this file was built on it — not afterwards (process addendum r11, step W).

WHAT AN ACTIVE SAMPLE ACCOUNT COSTS, STATED RATHER THAN DISCOVERED
-------------------------------------------------------------------
BR-TEN-065's reasoning was sound: a non-billable account can never become an
append-only invoice by accident, so removal stays total. Active accounts CAN be
billed, and an issued invoice can never be deleted (hard rule 4). So removal is
partial from now on: everything that is free goes, the bills and payments stay
and are REPORTED BY NAME. That is BR-TEN-066's own shape — *"remove what is
free, report the rest BY NAME"* — applied to the one case its author did not
have to consider. It is named on the Sample data panel, so nobody discovers it.

THE AWKWARD CASES THIS MODULE OWNS (spec §4)
---------------------------------------------
* **case 9** — one account MOVED OUT mid-July, so proration and a closing
  balance have a subject;
* **case 10** — one MOVED IN the next day, so proration works the other way;
* **case 13** — a landlord: ONE `customers` row holding TWO accounts, which is
  the only thing that makes the customer screen more than a synonym for the
  account screen.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.customers import models, sample_account_flags, services
from core import audit as core_audit
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.customers")

# ══════════════════════════════════════════════════════════════════════════
# WHY EVERY `except … continue` IN THIS FILE OPENS A SAVEPOINT (DEF-2722)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **DO NOT "SIMPLIFY" THE `with transaction.atomic():` LINES AWAY. THEY ARE
# NOT TIDINESS — THEY ARE THE ONLY THING THAT MAKES THESE `except` CLAUSES
# WORK AT ALL**, and CLAUDE.md hard-won law 14 exists because two other lanes
# reached the same conclusion independently on 2026-08-29.
#
# The whole of this block runs inside ONE transaction: `apps.tenancy
# .sample_data.seed_sample_data` opens `with transaction.atomic()` per module
# (BR-TEN-063) and calls this. **On PostgreSQL, the FIRST statement that errors
# aborts that transaction.** Every later query then raises
# `InFailedSqlTransaction` no matter what it asks, and the rollback discards
# everything the block had already written. A bare
#
#     try: …one row… except Exception: logger.info(…); continue
#
# therefore does NOT skip one row and carry on. It converts one row's refusal
# into the loss of the whole block, and reports it with a sentence that names
# nothing: *"InternalError: current transaction is aborted, commands ignored
# until end of transaction block"*.
#
# **MEASURED, 2026-08-31, on real PostgreSQL 16 under a role subject to RLS.**
# A tenant provisioned through `tenancy.services.provision_tenant` on a database
# one migration behind (`customers.0035` unapplied, so `disconnect_cases
# .status_before_cut` did not exist) came up with **70 premises, 118 units, 69
# meters and ZERO accounts and ZERO customers**. The 48 accounts HAD been
# created; `_seed_w7_disconnects` — which runs later in the same block and is
# nothing to do with accounts — then hit the missing column, caught it, logged
# `ProgrammingError: column disconnect_cases.status_before_cut does not exist`
# at INFO and continued into a dead transaction. Eight of the fourteen sample
# blocks failed, seven of them only as a cascade off this one.
#
# **AND THE DEFAULT TEST SUITE CANNOT SHOW YOU ANY OF THIS.**
# `config/settings/test.py` hardcodes in-memory SQLite and ignores
# `DATABASE_URL` (law 14 names this file by name), and SQLite has NO aborted-
# transaction state — so the version without these savepoints passes the whole
# suite, green, on every machine. `tests/test_def2722_sample_plant_survives.py`
# is the guard, and it is `@requires_postgres` for exactly that reason.
#
# A nested `transaction.atomic()` is a SAVEPOINT. On the exception it rolls back
# to the savepoint and the OUTER transaction is still usable, which is what
# "one refusal must not stop 47 others" was always claiming.
# ══════════════════════════════════════════════════════════════════════════

#: BR-TEN-065 as AMENDED 2026-08-16 — see the module docstring. `active` is
#: BR-CUS-055's `billable` behaviour class, which is what makes the bill run
#: the Product Owner is going to press actually have accounts to bill.
SAMPLE_ACCOUNT_STATUS = "active"

# ── DEF-257 · the sub-type tree the demo has to actually demonstrate ────────
#
# THE DEFECT, from the live database: `accounts.account_subtype_id` was NULL on
# **49 of 49** sample accounts, on a tenant carrying all twelve seeded
# sub-types. The two-level tree the Product Owner asked for in CR-010 ("we have
# Residential, Commercial, Industrial, Municipal/Goventment - then sub
# categories in each one") existed as data, rendered on its Settings card, and
# the seeded product never showed it working. Nothing broke — which is exactly
# why nothing caught it.
#
# THE MAPPING, and why it is these three of the twelve. A sample account's
# sub-type is not a free choice: it has to be the truth about the unit the
# account occupies, or the demo teaches the wrong thing.
#   · the apartment block's six sub-metered units are **multi-family**;
#   · the two commercial suites (a laundromat and a diner) are **small
#     commercial** — not `large_commercial`, which on a 48-account utility
#     would be a fiction;
#   · every other unit is a house, so **single-family**.
# The remaining nine seeded sub-types stay unused ON PURPOSE. Spreading
# accounts across `heavy_industrial` or `schools` to make the card look busy
# would invent a customer base this fixture does not have, and the fixture's
# own rule is that the interesting cases must stand out from ordinary ones.
#
# ⚠ EVERY CODE HERE IS BR-CUS-067's, NOT NEW VOCABULARY: they are
# `SEED_ACCOUNT_SUBTYPES` rows, and each sits under the account_type the
# account is created with, which `create_account` is free to check and this
# file's test asserts row by row.
SUBTYPE_COMMERCIAL = "small_commercial"
SUBTYPE_MULTI_FAMILY = "multi_family"
SUBTYPE_SINGLE_FAMILY = "single_family"
# ── CR-062 ADDENDUM J3 / J4 · TWO OF THE NINE UNUSED SUB-TYPES ARE NOW USED ──
# ⚠ **AND THIS IS NOT THE "SPREAD ACCOUNTS TO MAKE THE CARD LOOK BUSY" THE NOTE
# ABOVE FORBIDS.** `BR-CUS-067`'s tree hangs each sub-type under a PARENT
# `account_type`, so an account created as `government` cannot carry
# `single_family` — that would be a sub-type from another branch, and the demo
# would teach a contradiction. These two rows are what the parent types the
# addendum seeds actually require, not decoration.
SUBTYPE_INDUSTRIAL = "light_industrial"
#: ⚠ **THE MUNICIPAL SEAT TAKES NO SUB-TYPE, AND THE ABSENCE IS THE HONEST
#: ANSWER RATHER THAN A GAP (`DEF-3284`).** `BR-CUS-067`'s twelve-row tree hangs
#: `municipal_buildings`, `schools` and `parks_facilities` under the parent
#: `government` — the code `BR-CUS-094` retired to LEGACY on 2026-08-24 — and it
#: has no branch under `municipal` at all. `_resolve_account_subtype` does not
#: check the parent, so writing `municipal_buildings` onto a `municipal` account
#: would succeed and would teach a contradiction: a sub-type from a branch the
#: account is not on. A sub-type is optional (`accounts.account_subtype_id` is
#: NULL by r5 #19), so the seat is created without one and the tree's own
#: staleness is filed rather than papered over.
SUBTYPE_NONE: str | None = None


def _subtype_code_for(entry: dict[str, Any]) -> str | None:
    """This account's sub-type code — see the mapping note above."""
    if entry["account_type"] == "municipal":
        return SUBTYPE_NONE
    if entry["account_type"] == "industrial":
        return SUBTYPE_INDUSTRIAL
    if entry["account_type"] == "commercial":
        return SUBTYPE_COMMERCIAL
    if entry["unit_index"] in fixture.apartment_unit_indexes():
        return SUBTYPE_MULTI_FAMILY
    return SUBTYPE_SINGLE_FAMILY


def _available_subtypes() -> set[str]:
    """The sub-type codes this tenant actually holds, lower-cased.

    A tenant provisioned with the S111 standard-data toggle OFF has none, and a
    tenant may have deactivated any of them. `_resolve_account_subtype` refuses
    an unknown code by name and the refusal would take the whole account with
    it, so the plant asks first and omits the field rather than failing 48
    accounts over a vocabulary row.
    """
    return {
        str(code).lower()
        for code in models.AccountSubtype.objects.filter(
            tenant_id=_tenant_id(), active=True
        ).values_list("code", flat=True)
    }


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _tag(queryset: Any) -> int:
    """BR-TEN-057 — this module's own write of its own tag."""
    return int(queryset.update(is_sample=True))


def _unit_no_to_id() -> dict[str, str]:
    """The units these accounts occupy, through metering's published selector —
    customers never reads metering's tables (B1)."""
    from apps.customers import seams

    resolver = seams.resolve("metering", "units_list", kind="selectors")
    if resolver is None:
        return {}
    return {row.unit_no: str(row.id) for row in resolver() if row.unit_no}


def _customer_block(entry: dict[str, Any]) -> dict[str, Any]:
    """Who this seeded account belongs to — `BR-CUS-1024`, and **nothing here is
    invented.**

    ⚠ **THIS IS THE SAME ANSWER `_link_customer` HAS BEEN GIVING SINCE
    `BR-CUS-1023` LANDED, MOVED TO WHERE THE DOOR CAN READ IT.** The identity
    lane already ruled what a seeded party presents (decision log 2026-09-01,
    *THE DEMO FIXTURE'S PEOPLE KEEP THEIR CUSTOMER NUMBERS, AND NOTHING WAS
    INVENTED TO DO IT*): a person is identified by **`entry["phone"]` — the
    value the fixture ALREADY holds and already writes onto that account's
    contact row**, a `555-` number in the reserved-for-fiction range; a business
    by `SAMPLE_COMPANY_TAX_ID`, `99-0001234`, in the IRS's own reserved range.
    **One rule applied twice, not two lanes each deciding for themselves.**

    ⚠ **AND AN ENTRY WITH NO PHONE PRESENTS NO IDENTITY, DELIBERATELY.** The
    ruling forbids inventing a digit to keep the fixture tidy by name. Today all
    48 entries carry one, so this branch plants nothing — it is here because the
    day a fixture entry loses its phone, the honest outcome is that the seed
    says so rather than that somebody mints a number for a fictional person.

    `external_ref` is what makes spec §4 case 13 work: units 45 and 46 share
    `landlord-45`, so `link_customer` matches on the reference and the two
    accounts land under ONE customer row without this file choosing which row to
    reuse. The product's own matching rule does it, which is the only way the
    case proves anything.
    """
    # ⚠ **`!= "residential"` SINCE `CR-062` ADDENDUM J3/J4, AND IT MOVES NO
    # EXISTING ROW.** Until today the seeded types were `residential` and
    # `commercial` alone, so the two readings were the same answer. They stop
    # being the same the moment a township and a mill are seeded: a `government`
    # or `industrial` account is an ORGANISATION, and calling it a `person`
    # would ask `BR-CUS-089`'s identity rule for a date of birth and a
    # government ID from a public works department.
    is_company = entry["account_type"] != "residential"
    block: dict[str, Any] = {
        "external_ref": entry["customer_key"],
        "display_name": (
            "Silver Creek Duplex Holdings"
            if entry["unit_index"] in fixture.CASE_LANDLORD
            else entry["display_name"]
        ),
        "kind": "company" if is_company else "person",
    }
    identity = (
        {"tax_id": SAMPLE_COMPANY_TAX_ID}
        if is_company
        else ({"phone": entry["phone"]} if entry.get("phone") else None)
    )
    if identity is not None:
        block["identity"] = identity
    return block


def _account_payload(entry: dict[str, Any], subtypes: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_type": entry["account_type"],
        # BR-CUS-018's draft is deliberately NOT taken: see the module
        # docstring for the ruling that changed it.
        "status": SAMPLE_ACCOUNT_STATUS,
        "opened_at": fixture.PERIODS[0]["start"].isoformat(),
        "contact": {
            "full_name": entry["display_name"],
            "email": entry["email"],
            "phone": entry["phone"],
            "is_primary": True,
        },
        "addresses": [
            {
                "kind": "mailing",
                "line1": entry["bill_to"],
                "city": fixture.CITY,
                # DEF-2848 — the third part BR-NOT-029 clause (b) requires.
                # Without it every seeded bill is held out of the print set.
                "state": fixture.STATE,
                "postal_code": fixture.POSTAL,
            }
        ],
        # ── `BR-CUS-1024` — THE SEED GOES THROUGH THE RULE, NOT AROUND IT ────
        # This block used to be written by a SEPARATE `link_customer` call after
        # the account existed, and the account itself was opened with
        # `require_identity=False`. Two things were wrong with that, and neither
        # is about this fixture:
        #
        #   * **the path most exercised in this repo was the one path the rule
        #     never ran on.** 48 accounts a plant, and the account-level refusal
        #     had no end-to-end proof it survives contact with any of them;
        #   * **a demo where every account has a customer is the demo the PO
        #     looks at.** They rebuild the database at will and judge the
        #     product from what comes out of it.
        #
        # Nothing is invented to get here — see `_customer_block`.
        "customer": _customer_block(entry),
    }
    # DEF-257. Sent only when the tenant HOLDS the sub-type: an unknown code is
    # refused by name and would take the whole account with it.
    subtype = _subtype_code_for(entry)
    if subtype in subtypes:
        payload["account_subtype"] = subtype
    return payload


#: DEF-2722 — how many refusals the shortfall sentence names before it stops.
#: Five, because a person needs to see whether the refusals are ONE cause or
#: several and the sixth line does not change that answer; the full set is in
#: the INFO trace, one line per unit, which is what a log is for.
SHORTFALL_REASONS_SHOWN = 5


def _report_short_accounts(actor: Any, *, seats: int, refusals: list[str]) -> None:
    """DEF-2722 — the block's own promise, CHECKED, and where a shortfall goes.

    ⚠ **WHY THE ANSWER IS SPLIT IN TWO, BECAUSE THE OBVIOUS ONE IS WRONG.**
    The tempting fix is *"if it is short, raise"*. It is wrong: `apps.tenancy
    .sample_data.seed_sample_data` runs this block inside ONE
    `transaction.atomic()` per module (BR-TEN-063), so a raise ROLLS BACK every
    account that DID land. A fix that turns 47 good accounts into 0 in order to
    report that the 48th refused has made the product worse and the report
    louder, which is the wrong trade in both directions.

    So the two cases are genuinely different and are answered differently:

    * **NOT ONE seat was taken** — raise `fixture.BlockCannotRun`. Nothing
      landed, so the rollback costs nothing, and this is precisely the state
      that type exists for: *"COULD NOT RUN — naming the reason … Never a 0."*
      The orchestrator then records the block FAILED with THIS sentence in
      `sample_data_runs.blocks[].detail`, which S62 renders and `run_summary()`
      reads, so `succeeded` goes False and C-15's `sample.seed_incomplete` row
      and ERROR log fire. **That is the whole difference DEF-2722 is about:
      before this, the same state was recorded as `InternalError: current
      transaction is aborted, commands ignored until end of transaction
      block` — a sentence that names nothing and blames the wrong statement.**

    * **SOME landed and some refused** — the rows STAY and the shortfall is a
      recorded warning: an ERROR log naming both numbers and the real reasons,
      plus an `audit_log` row (CLAUDE.md rule 7 — this is the plant a human
      asked for, and its outcome is a fact about the tenant). It is deliberately
      NOT raised: 47 accounts is a demonstrable product and 0 is not.

    **WHY THE AUDIT ROW AND NOT A `sample_data_runs` ROW**, since that is the
    S62 surface: `sample_data_runs` is `apps.tenancy`'s table and a cross-module
    write is forbidden (B1, BR-TEN-013). `audit_log` is the platform kernel
    (`core.audit`), which every module writes to by design. The action name is
    C-15's own `sample.seed_incomplete`, deliberately, so the shortfall counts
    and queries alongside every other incomplete plant instead of inventing a
    second vocabulary for the same fact.

    ⚠ `seats` counts only the fixture seats THIS TENANT HOLDS. A tenant with a
    smaller estate is not short — it was never asked for 48 (CR-039 wave A: the
    estate is a shape, the service is a parameter).
    """
    refused = len(refusals)
    if not refused:
        return
    seated = seats - refused
    reasons = " · ".join(refusals[:SHORTFALL_REASONS_SHOWN])
    if refused > SHORTFALL_REASONS_SHOWN:
        reasons += f" · …and {refused - SHORTFALL_REASONS_SHOWN} more, one INFO line each"
    if seated <= 0:
        raise fixture.BlockCannotRun(
            f"no sample account was created: every one of the {seats} seats this tenant "
            f"holds refused. Nothing downstream of accounts can be seeded — bills, "
            f"payments, the payment plan and the refund all read an account. The "
            f"refusals were — {reasons}",
            code=_shortfall_code(refusals),
        )
    logger.error(
        "sample data: the Accounts block came up SHORT — %s of %s seats took an account, "
        "%s refused. The %s that landed are KEPT (they are a usable demo); re-run the "
        "plant from Settings > Company profile once the named cause is fixed, and it will "
        "seat the rest (BR-TEN-063, this block is idempotent). Refusals — %s",
        seated,
        seats,
        refused,
        seated,
        reasons,
    )
    core_audit.write_row(
        action="sample.seed_incomplete",
        entity_type="tenant",
        entity_id=core_tenancy.current_tenant_id(),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "block": "customers:seed_sample_records",
            "promised": seats,
            "delivered": seated,
            "refused": refused,
            # BR-AUD-006 — PII enters MASKED only, and `audit_log` is
            # append-only (BR-AUD-002), so a row cannot be edited afterwards to
            # take something back. The driver's MESSAGE is free text this module
            # does not control: an `IntegrityError` quotes the key that
            # collided, and a `ValidationError` can quote the field value it
            # rejected — and the payload being written here carries a name, an
            # email and a phone. So the row carries the unit and the exception
            # TYPE, which is what a later query needs ("how often, and where"),
            # and the MESSAGE stays in the ERROR log above, which is where a
            # person reads a cause. Same posture as C-15's own row in
            # `apps/tenancy/sample_data.completeness_check`, which stores reason
            # CODES and not prose.
            "detail": [_masked(one) for one in refusals[:SHORTFALL_REASONS_SHOWN]],
        },
    )


def _masked(refusal: str) -> str:
    """`unit_no: ExceptionType` — a refusal with its free-text message removed.

    See the BR-AUD-006 note at the call site for why the message is dropped
    rather than truncated: a truncated driver message is still free text.
    """
    parts = refusal.split(":", 2)
    return ": ".join(part.strip() for part in parts[:2]) if len(parts) > 1 else refusal.strip()


def _shortfall_code(refusals: list[str]) -> str | None:
    """The stable code for a TOTAL refusal, so it can be counted across tenants.

    `core.sample_fixture.BlockCannotRun` sanctions declaring a code at the raise
    site: *"A seeder that knows exactly WHICH precondition it lacked may declare
    a code from `apps.tenancy.sample_errors.CATALOGUE` here"*. Without one the
    orchestrator would derive `SD-PRECONDITION` from the exception TYPE, which
    is honest but says the wrong thing when the real cause was the database —
    and DEF-2722's own cause was `SD-DB-ERROR`. Imported lazily and used for its
    constants only; nothing here writes a tenancy table.
    """
    if not refusals:
        return None
    from apps.tenancy import sample_errors

    head = refusals[0].split(":", 2)[1].strip() if ":" in refusals[0] else ""
    if head in {"IntegrityError", "UniqueViolation"}:
        return sample_errors.CODE_DB_INTEGRITY
    if head.endswith("Error") and head in {
        "ProgrammingError",
        "OperationalError",
        "DataError",
        "InternalError",
        "DatabaseError",
        "InterfaceError",
    }:
        return sample_errors.CODE_DB_ERROR
    return None


def seed_sample_records(actor: Any) -> int:
    """THE SEAM `apps/tenancy/seams.py` has documented since 2026-08-15.

    One ACTIVE account per seeded unit — 48, which is spec acceptance item 2's
    own number (*"Open Accounts and see 48"*) — each with its contact, its
    billing address and the service agreements the unit's service points imply.

    Every one goes through `create_account`, the S18 wizard's own call, so
    BR-CUS-017 (one occupying account per unit) is enforced by the product
    rather than assumed by the fixture.

    Idempotent (BR-TEN-063): a unit that already has an occupying account is
    skipped, so a replay writes nothing.

    ⚠ **THE 48 IS NOW COMPARED, AND THAT IS DEF-2722 (2026-08-31).**
    This docstring has promised 48 since it was written and NOTHING HAS EVER
    READ THE NUMBER IT RETURNS. A count returned and never compared is hard-won
    law 2 in its purest form — the same failure as a component nothing renders:
    the code runs, nothing errors, and the feature does not exist. Measured on a
    freshly provisioned tenant that day: **70 premises, 118 units, 69 meters and
    ZERO accounts and ZERO customers**, and the plant's own job record read
    `succeeded`.

    So the seats are counted three ways — ALREADY SEATED (a replay), CREATED
    HERE, REFUSED — and every planned seat is exactly one of them, which makes
    `seated = seats - refused` exact and free. `_report_short_accounts` below is
    what the number is compared against, and why the answer goes where it does.
    """
    units = _unit_no_to_id()
    if not units:
        # DEF-2722. NOT a 0. `fixture.BlockCannotRun`'s own rule: a seeder block
        # that cannot do its job SAYS SO and never answers 0, because a 0 with a
        # reason nobody reads is indistinguishable from "the fixture asked for
        # none". The assets block already raises exactly this sentence one step
        # downstream; this is the same fact one step earlier.
        raise fixture.BlockCannotRun(
            "no sample account was created: this tenant holds no units at all, so there "
            "is no seat for an account to occupy. The UPSTREAM block is metering's "
            "'Premises, units & service points' — fix that and load again."
        )
    written = 0
    created_ids: list[str] = []
    # DEF-2722 — what the fixture ASKED for on this tenant, and what refused.
    # A unit_no the fixture names but this tenant does not hold is not a
    # refusal: the estate is a shape and the tenant may hold a smaller one.
    seats = 0
    refusals: list[str] = []
    # DEF-257 — resolved once for the whole plant, not once per account.
    subtypes = _available_subtypes()
    for entry in fixture.account_plan():
        unit_id = units.get(entry["unit_no"])
        if unit_id is None:
            continue
        seats += 1
        if services.active_account_for_unit(unit_id) is not None:
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                # ⛔ **NO `require_identity=False` HERE ANY MORE — THE SEED
                # GOES THROUGH `BR-CUS-1024` LIKE EVERY OTHER DOOR.** It was
                # exempted when the rule landed, because these entries stated no
                # customer KIND and the rule would have refused all 48, leaving
                # the demo with no accounts and therefore no bills, no payments,
                # no payment plan and no refund.
                #
                # **The exemption was unnecessary and the answer was already in
                # the repo:** the identity lane had ruled hours earlier what a
                # seeded party presents — a person by the `555-` phone the
                # fixture already holds, a business by the reserved `99-0001234`
                # Tax ID — so `_customer_block` states the kind from data that
                # was there all along. **Nothing was invented then and nothing
                # is invented here** (decision log 2026-09-01, and again for
                # this change).
                #
                # ⚠ **AND THE CUSTOMER IS NOW RESOLVED INSIDE THE ACCOUNT'S OWN
                # TRANSACTION, WHICH IS THE POINT.** It used to be a second
                # `link_customer` call after the account existed, in its own
                # savepoint, swallowing its own failures — so a seeded account
                # could exist with no customer and nothing said so. Under this
                # ruling that state is exactly what may not exist: an account
                # whose customer cannot be resolved does not open.
                account = services.create_account(
                    actor,
                    {**_account_payload(entry, subtypes), "unit_id": unit_id},
                )
        except Exception as exc:  # noqa: BLE001 — one refusal must not stop 47 others
            # DEF-2722: the MESSAGE, not only the type. This line recorded
            # `type(exc).__name__` alone until 2026-08-31, so the one trace that
            # could have named the cause said `ProgrammingError` and stopped.
            refusals.append(f"{entry['unit_no']}: {type(exc).__name__}: {exc}")
            logger.info(
                "sample data: unit %s took no account (%s: %s)",
                entry["unit_no"],
                type(exc).__name__,
                exc,
            )
            continue
        created_ids.append(account["id"])
        written += 1

    # DEF-2722 — BEFORE the tagging and before every sub-fixture below, because
    # a total refusal here makes all of them meaningless and the operator should
    # read the cause and not its ninth consequence.
    _report_short_accounts(actor, seats=seats, refusals=refusals)

    tenant_id = _tenant_id()
    accounts_qs = models.Account.objects.filter(tenant_id=tenant_id, pk__in=created_ids)
    _tag(accounts_qs.filter(is_sample=False))
    _tag(
        models.Contact.objects.filter(tenant_id=tenant_id, account__in=accounts_qs, is_sample=False)
    )
    _tag(
        models.Address.objects.filter(tenant_id=tenant_id, account__in=accounts_qs, is_sample=False)
    )
    _tag(
        models.ServiceAgreement.objects.filter(
            tenant_id=tenant_id, account__in=accounts_qs, is_sample=False
        )
    )
    _tag(
        models.CustomerAccount.objects.filter(
            tenant_id=tenant_id, account__in=accounts_qs, is_sample=False
        )
    )
    _tag(
        models.Customer.objects.filter(
            tenant_id=tenant_id,
            pk__in=models.CustomerAccount.objects.filter(
                tenant_id=tenant_id, account__in=accounts_qs
            ).values("customer_id"),
            is_sample=False,
        )
    )
    # CR-030 W1 T1.23 — ❄️ GT-16's migrated account. LAST, and on a seat of its
    # own: the accounts above take every fixture unit (BR-CUS-017 allows one live
    # account per unit, ever), so this one occupies the cutover seat metering
    # seeded for it.
    written += _seed_gt16_cutover_account(actor)
    # CR-030 W2 T2.10 / W3 T3.12 / W4 T4.14 — the demo estate (PO 2026-08-24,
    # "so add them"). AFTER the per-unit accounts and after ❄️ GT-16, on seats
    # metering seeded
    # for them; nothing above is renumbered, re-addressed or re-priced.
    written += _seed_cr030_account_shapes(actor)
    written += _seed_cr030_demo_notes(actor)
    written += _seed_cr030_service_requests(actor)
    # CR-030 W5 T5.11 — B18 §5.5.7's five move-ins and §5.6.7's six move-outs.
    # LAST, and after the requests, because two of the five move-ins ARE service
    # requests (the drafts) and four of the eleven annotate accounts the W2
    # block above plants. It creates no account and no unit: see its own header
    # for the four measured facts that decide what it can plant.
    written += _seed_w5_move_fixtures(actor)
    # CR-030 W7 T7.12 — B18 §5.7.6's five transfers and §5.8.6's nine
    # disconnects. LAST, because three of the five transfers COMMIT (which
    # closes their outgoing account) and every ladder row reads what its account
    # owes from the LEDGER, so both need the accounts above and their opening
    # entries already on file.
    written += _seed_w7_fixtures(actor)
    # CR-039 wave D task 19 — *"seed one or two of each"*. AFTER W5, which is
    # what decides which drawn rows are plantable at all. It creates no account,
    # no unit and no note: it records the JOB that produced accounts already on
    # file.
    #
    # ⚠ **THIS COMMENT READ "AND AFTER W7 (three of its five transfers CLOSE
    # their outgoing account, and a closed account is a move-out that
    # happened)" UNTIL 2026-09-07, AND IT HAD BEEN FALSE FOR SIX DAYS**
    # (`DEF-CUS-4628`). The PO ruled on 2026-09-01 *"dont create new account -
    # we reassing that account"*; `commit_transfer` became
    # `transfers.reassign_account`, which closes NOTHING and says so on its own
    # audit row (`"account_closed": False`). So the branch below that needs
    # `account.closed_at` for a move-OUT record has never once found one, and
    # the demo's `MVO-` series has never issued a number. The block that now
    # produces a real closure is `seed_sample_move_out`, and it runs LATER than
    # this one for the reason given in its own header — so a move-out RECORD is
    # written by `services.move_out` itself rather than reconstructed here.
    written += _seed_cr039_move_records(actor)
    # DEF-709 — the developer's MASTER account (BR-CUS-083 / BR-CUS-068). LAST,
    # deliberately: it takes the next number from the tenant's account series
    # (BR-TEN-035), so putting it here leaves every number above it exactly
    # where it was.
    written += _seed_developer_master_account(actor)
    # CR-089 wave I task I6 / DEF-CUS-4692 — the nine account columns that were
    # populated on ZERO rows across BOTH demo utilities. LAST, after every
    # account this fixture creates exists, because the seats are chosen from the
    # accounts on file rather than named by number.
    written += sample_account_flags.seed_account_flags(actor)
    return written


# ══════════════════════════════════════════════════════════════════════════
# CR-039 WAVE D TASK 19 — ONE MOVE-IN AND ONE MOVE-OUT THAT LEFT A RECORD
# ══════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-08-27, verbatim and in full: *"you cna keep them as records for
# audit perpuses"*. Task 19 is *"seed one or two of each"*, and the point of
# seeding them is that **a record nobody can see is indistinguishable from a
# record that does not exist** — the same argument CR-039 finding 7 makes about
# sub-areas being *"fully built, ruled and never demonstrated"*.
#
# ⚠ **WHAT THIS BLOCK REFUSES TO DO, AND IT IS THE INTERESTING HALF.**
# The obvious way to seed a move record is to CALL `services.move_out` on a
# seeded account. That is refused: it would CLOSE a live account of the demo
# estate, free its unit, end its service agreements and change what the billing
# month bills — a fixture that reshapes the demo in order to demonstrate a
# record. The estate's shape is CR-039 wave A's and `core.sample_fixture
# .estate_plan` is not this lane's to move.
#
# So this records the jobs that ALREADY HAPPENED to accounts already on file,
# through `moves.record_move` — the module's own service function, which
# allocates the number inside this transaction exactly as the wizards do. It is
# NOT a seeder reaching past a validated write path with `.update()`, which the
# wave C lane established as the line (*"a 🔒 sensitive path may not be written
# by a seeder's `.update()`"*).
#
# ⚠ **`reads_committed` IS SEEDED AS `0`, AND THAT IS THE TRUE ANSWER RATHER
# THAN A GAP.** The column counts readings THIS JOB committed through the
# BR-CUS-021 event door. These jobs committed none — the fixture states reads as
# PROSE on the drawn row (*"Reads taken"*, *"final read taken"*) and prose is not
# a reading. Seeding a count to make the cell look populated would state that
# meter readings exist which nobody can find, which is `sample_fixture`'s spec
# rule 7 applied to a figure instead of a field.
#
# ⚠ **`from_account` IS LEFT NULL ON THE SEEDED MOVE-IN.** A chained move-in
# names the outgoing account it followed; the W5 fixture rows draw no such chain
# — each is one arrival at one address — so there is nothing to name and naming
# one would invent a tenancy that did not end.


#: How many of each kind to plant. Task 19's own words are *"one or two of
#: each"*, and TWO is chosen so the Reference column is visibly a SERIES rather
#: than a single value: a reader sees `MVO-26-0001` and `MVO-26-0002` and can
#: tell the counter moves. Beyond two adds nothing a third row would show.
CR039_MOVE_RECORDS_PER_KIND = 2


def _seed_cr039_move_records(actor: Any) -> int:
    """Task 19 — up to two move-in and two move-out records, on accounts the
    W5 fixture has already planted.

    Idempotent (BR-TEN-063 · CLAUDE.md rule 6): an account that already carries
    a record of that kind is skipped, so a replay writes nothing and returns 0.
    ⚠ That predicate is `(account, kind)` rather than a number, because the
    number is NULL on a tenant with no series row and a NULL cannot be a key.

    A row whose W5 entry is NOT planted is LOGGED with the blocker W5 already
    measured, never worked around — the posture `_seed_w5_move_fixtures` takes
    one function up.
    """
    from apps.customers import moves

    tenant_id = _tenant_id()
    written = 0
    planted_by_kind: dict[str, int] = {moves.KIND_MOVE_IN: 0, moves.KIND_MOVE_OUT: 0}
    for entry in w5_move_fixture_report():
        kind = moves.KIND_MOVE_IN if entry["kind"] == "Move-in" else moves.KIND_MOVE_OUT
        if planted_by_kind[kind] >= CR039_MOVE_RECORDS_PER_KIND:
            continue
        if not entry["planted"]:
            logger.info(
                "sample data (CR-039 wave D task 19): %s %s (%s) leaves no record — %s",
                entry["kind"],
                entry["drawn_no"] or "draft",
                entry["customer"],
                entry["blocker_detail"] or "no reason recorded, which is itself a defect",
            )
            continue
        account = models.Account.objects.filter(
            tenant_id=tenant_id, pk=entry["account_id"]
        ).first()
        if account is None:  # pragma: no cover - `planted` already proved it exists
            continue
        # The EFFECTIVE date is the account's OWN, never the drawn one and never
        # a clock (BR-TEN-043). A move-out's is `closed_at`; a move-in's is
        # `opened_at`. An account missing the one its kind needs is skipped
        # rather than dated with the other, which would state a tenancy boundary
        # nobody recorded.
        effective_on = account.closed_at if kind == moves.KIND_MOVE_OUT else account.opened_at
        if effective_on is None:
            logger.info(
                "sample data (CR-039 wave D task 19): %s has no %s date, so its %s leaves "
                "no record — a date is not invented for it",
                account.account_no,
                "closed_at" if kind == moves.KIND_MOVE_OUT else "opened_at",
                entry["kind"].lower(),
            )
            continue
        if moves.MoveRecord.objects.filter(
            tenant_id=tenant_id, account_id=account.id, kind=kind
        ).exists():
            planted_by_kind[kind] += 1
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                moves.record_move(
                    kind=kind,
                    account_id=account.id,
                    effective_on=effective_on,
                    actor=actor,
                    reads_committed=0,  # see the block header — the true answer
                    is_sample=True,
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-039 wave D task 19): %s kept no move record — %s: %s",
                account.account_no,
                type(exc).__name__,
                exc,
            )
            continue
        planted_by_kind[kind] += 1
        written += 1
    return written

# ══════════════════════════════════════════════════════════════════════════
# DEF-709 — THE DEVELOPER'S MASTER ACCOUNT (BR-CUS-083 · BR-CUS-068)
# ══════════════════════════════════════════════════════════════════════════
#
# THE DEFECT, and it is a DATA defect: the master-account feature is built and
# wired end to end — `accounts.kind` (BR-CUS-068), `create_master_account` as
# its only door, `kind` on every account row the selector serves, the `Master`
# pill on the Accounts list and on Account detail, the `kind` filter — and
# **no seeder anywhere had ever created one**, so all of it rendered against
# nothing on every tenant the product has ever planted. Every existing test
# builds its own master account inline and passes, which is exactly how this
# hid: the estate was never asked.
#
# WHICH WORKED CASE IS SEEDED, AND WHY IT IS THIS ONE
# -----------------------------------------------------
# Two rules work a master account with figures:
#
#   · **BR-CUS-068 / BR-MET-101** — *1408 Elm, 3 units + 2 common areas,
#     $41.20 + $28.40 = $69.60 on one owner bill.* NOT seeded. The estate's
#     `1408 Elm Street` is a **single-family house with one unit**
#     (`SCW-U-201`) and that unit is `A-10432`'s — the account every B18
#     `[shot]` draws. Seeding this case means re-shaping the demo's
#     most-photographed premises into a three-flat block and inventing two
#     more occupants, and it proves nothing new: the $69.60 already comes out
#     of the product end to end in `tests/test_br_cus_068_master_bill.py`.
#
#   · **BR-CUS-083** (PO 2026-08-24, closing OQ-349) — *"a) the developer, via
#     a master account"*, worked at `SR-26-0043` → `CON-26-0117`, `500 Main
#     Street`, 25 units, **$14,390.00**. **Seeded**, because the estate
#     already holds every part of it except the account: the premises, its
#     `owner_manager` **`Ridge Property LLC`** (who IS the payer this path
#     picks up on its own — PO 2026-08-22: *"payer = the premises'
#     owner/manager"*), the service request, the connection and its 25 units.
#     `BR-MET-116` (PO 2026-08-25) then supplies the one missing row and says
#     so as a manifest: ***`Units 26` = 25 apartments + 1 common area***.
#     `apps/metering/sample_data._seed_w6_common_area` plants that 26th unit;
#     this block opens the account that anchors on it. **No figure is
#     invented and no scenario is designed — every fact is already signed.**
#
# ⚠ **AND IT DELIBERATELY AVOIDS `OQ-366`.** BR-CUS-097 transfers a
# sub-account's unpayable residue to its master, and **nobody has ruled whether
# the dunning ladder then chases the departed tenant or the master**. A seeded
# master carrying a sub-account's debt would be a fixture that answers an open
# question by existing. This one carries **no residue and no sub-account**: it
# is a build's owner account over an empty building, which is the shape
# BR-MET-116 ruled *"unit will be all vacant right now"*.
#
# ⚠ **WHAT THIS BLOCK DOES NOT DO.** It does not stamp
# `connections.owner_account_id` on `CON-26-0117`. That column has exactly one
# lawful writer — `apps.metering.connections.create_owner_account`, BR-MET-116's
# own door — and it is METERING's, while this seeder runs in the customers
# block. Calling it from here would need a new declared seam contract, and
# calling it from metering's block would put an extra account AHEAD of the 48 in
# the tenant's number series (BR-TEN-035) and renumber all of them. So the
# account exists and the connection's payer link does not. **REPORTED, not
# silently skipped** — see the report accompanying DEF-709.


def _seed_developer_master_account(actor: Any) -> int:
    """ONE `kind='master'` account, through `create_master_account` — the only
    door there is (BR-CUS-068: *"`kind` is a REFUSED input on every other
    account path"*), never a model write.

    Idempotent (BR-TEN-063): the anchor unit is asked whether it already has an
    account, which is the same guard the 48 above use, so a replay writes
    nothing.
    """
    from apps.customers import seams

    resolver = seams.resolve("metering", "units_list", kind="selectors")
    if resolver is None:  # pragma: no cover - metering ships in the same packet
        return 0
    anchor = next(
        (row for row in resolver() if row.unit_no == fixture.CR030_COMMON_AREA_UNIT_NO),
        None,
    )
    if anchor is None:
        # BR-TEN-060's posture — an unloaded thing is a NAMED line. Metering's
        # block plants this unit; without it there is no common area on the
        # tenant and BR-CUS-068's path has nothing to anchor on.
        logger.info(
            "sample data (DEF-709): common-area unit %s is not on file, so the demo has no "
            "master account and the `Master` pill has nothing to render",
            fixture.CR030_COMMON_AREA_UNIT_NO,
        )
        return 0
    if not anchor.is_common_area:
        logger.info(
            "sample data (DEF-709): unit %s is on file but is not flagged as a common area "
            "(BR-MET-101), so BR-CUS-068's master path would refuse it by name",
            fixture.CR030_COMMON_AREA_UNIT_NO,
        )
        return 0
    if services.active_account_for_unit(anchor.id) is not None:
        return 0

    payload: dict[str, Any] = {
        "premises_id": str(anchor.premises_id),
        # Named explicitly rather than defaulted to "every common area of the
        # premises": a second common area added here later would silently join
        # this account's coverage, and BR-CUS-068 leaves two covered areas
        # taking the SAME service unruled (OQ-334).
        "unit_ids": [str(anchor.id)],
        # `500 Main St` is a `commercial_building` and its four suites are
        # commercial accounts; BR-MET-116's own door defaults a build account to
        # the same. A master account still HAS a consumer category (BR-CUS-068).
        "account_type": "commercial",
        # BR-MET-116 / BR-TEN-043: the build account opens on the TENANT'S
        # today, decided when the seed runs. DEF-629/DEF-704 — no literal date
        # anywhere in this fixture; a typed date is a clock waiting to expire.
        "opened_at": seams.tenant_today(),
        # ⛔ **THE OWNER IS IDENTIFIED — `BR-CUS-1024`, PO 2026-09-01: *"Without
        # identifier we cannot create Customer ID or master account ot regular
        # account"*.** The `owner_manager` fallback below supplies a NAME, and a
        # name alone now refuses this door outright — so the seed would plant an
        # estate with no master account, the `Master` pill would vanish from
        # every demo tenant's Accounts list, and the `except` below would log it
        # once and return 0. **The Tax ID is the fixture's own reserved value**
        # (`CR030_COMMON_AREA_OWNER_TAX_ID`), never a real business's number, and
        # a company is identified by its Tax ID and by nothing else
        # (`BR-CUS-1022`).
        # **NO `display_name` HERE, DELIBERATELY** — the premises already holds
        # the owner's name and the resolver fills it in, exactly as it fills the
        # contact below. Typing it again would be the second, drifting copy this
        # payload's next comment already refuses to make.
        "customer": {
            "kind": "company",
            "identity": {"tax_id": fixture.CR030_COMMON_AREA_OWNER_TAX_ID},
        },
        # `contact` is OMITTED on purpose. With no contact the path takes the
        # premises' `owner_manager` — `Ridge Property LLC` — which is the payer
        # BR-CUS-083 names ("the developer") and BR-CUS-068 defines ("payer =
        # the premises' owner/manager"). Typing the name here would be a second,
        # drifting copy of a fact the estate already holds.
        "addresses": [
            {
                "kind": "mailing",
                "line1": fixture.CR030_COMMON_AREA_ADDRESS,
                "city": fixture.CITY,
                # DEF-2848 — the third part BR-NOT-029 clause (b) requires.
                # Without it every seeded bill is held out of the print set.
                "state": fixture.STATE,
                "postal_code": fixture.POSTAL,
            }
        ],
    }
    # DEF-257 — sent only when the tenant HOLDS the sub-type, exactly as the 48
    # above do: an unknown code is refused by name and would take the whole
    # account with it.
    if SUBTYPE_COMMERCIAL in _available_subtypes():
        payload["account_subtype"] = SUBTYPE_COMMERCIAL

    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            account = services.create_master_account(actor, payload)
    except Exception as exc:  # noqa: BLE001 — one refusal must not fail the plant
        # NAMED, never swallowed — the same posture ❄️ GT-16's block takes one
        # screen down. The likeliest cause is BR-MET-040: the common area
        # reached this point without a rate plan, which is exactly the ordering
        # constraint BR-MET-116 closes with, and it is one edit to fix.
        logger.info(
            "sample data (DEF-709): the master account was refused (%s: %s) — the estate "
            "keeps no `kind='master'` row and the Accounts `Master` pill stays unrendered",
            type(exc).__name__,
            exc,
        )
        return 0

    tenant_id = _tenant_id()
    accounts_qs = models.Account.objects.filter(tenant_id=tenant_id, pk=account["id"])
    _tag(accounts_qs.filter(is_sample=False))
    _tag(
        models.Contact.objects.filter(tenant_id=tenant_id, account__in=accounts_qs, is_sample=False)
    )
    _tag(
        models.Address.objects.filter(tenant_id=tenant_id, account__in=accounts_qs, is_sample=False)
    )
    _tag(
        models.ServiceAgreement.objects.filter(
            tenant_id=tenant_id, account__in=accounts_qs, is_sample=False
        )
    )
    return 1


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W1 · TASK 1.23 — ❄️ GT-16's MIGRATED ACCOUNT, ITS FOUR AGED BUCKETS
# AND THE BALANCED OPENING ENTRY
# ══════════════════════════════════════════════════════════════════════════
#
# B5 GT-16, ❄️ FROZEN, finance-signed 2026-08-08, lines 55–56 verbatim:
#
#   *"Input: cutover 2026-08-31; imported account A-12103 opening buckets
#   Current 84.20 / 31–60 62.10 / 61–90 0.00 / 90+ 121.00 (USD)."*
#
#   *"Expected: `accounts.balance` = **267.30** (Σ buckets, exact — no
#   recompute); … one opening JE dated **2026-08-31**, source_type
#   `opening_balance`: **DR AR 267.30 / CR opening-balance clearing 267.30** —
#   balanced pair written ONLY by the ledger posting service … re-posting the
#   same batch is idempotent (no second JE set)."*
#
# ⚠ **NOT ONE FIGURE HERE IS THIS FILE'S TO CHOOSE.** They are copied from B5
# and nothing recomputes, rounds or "corrects" them. If the code ever produces
# a different total the CODE is wrong: a frozen figure moves only by a finance
# re-sign through HUMAN-GUIDE §6, never by an edit here (CLAUDE.md).
#
# WHY IT GOES THROUGH `services.create_from_import` AND NOT THROUGH
# `create_account`. This account is the demo's MIGRATED one: B18 §5.9.3a is
# explicit that the opening position arrives as four aged buckets and posts
# through the ledger, and `create_from_import` is the single path that writes
# the buckets, caches `accounts.balance` from the SAME position object and
# hands the batch on. Calling `create_account` and then writing buckets beside
# it would be a second derivation of one number, which is how two numbers come
# to disagree. It is also the fixture spec's own rule 4 — *"seed through the
# services a clerk's click uses"* — applied to a clerk who ran an import.
#
# ⚠ **CUSTOMERS WRITES NO JOURNAL LINES** (CLAUDE.md hard rule 5, B1). It calls
# `import_writer.post_opening_batch_from_import`, which composes the contract
# and hands it to `apps.ledger.opening_balances`; the POSTING SERVICE writes
# the balanced pair. Nothing in this module goes near `journal_lines`.

#: ❄️ B5 GT-16 line 55 — the account the frozen worked case names.
GT16_ACCOUNT_NO = "A-12103"

#: ❄️ B5 GT-16 line 55 — the four aged bands, in the order they age
#: (BR-CUS-048: `Current / 31–60 / 61–90 / 90+`; lump-sum and invoice-level
#: were EXPLICITLY REJECTED by the PO, AC-3 option B). Written as strings so
#: the value in this file is byte-for-byte the value in B5 and no float can
#: exist on the path (hard rule 2).
GT16_BUCKETS: dict[str, str] = {
    "ob_current": "84.20",
    "ob_31_60": "62.10",
    "ob_61_90": "0.00",
    "ob_90_plus": "121.00",
}

#: ❄️ B5 GT-16 line 56 — *"`accounts.balance` = 267.30 (Σ buckets, exact — no
#: recompute)"*. Carried as an ASSERTION, not as an input: the sum is computed
#: by `import_writer.opening_position` from the four bands above, and this
#: constant is what the seed refuses to disagree with.
GT16_BALANCE = Decimal("267.30")

#: ❄️ B5 GT-16's day-one overdue base: 62.10 + 0.00 + 121.00 = 183.10 (B18
#: §5.9.3a). Stated so the demo's collections surface has a known figure and so
#: a drift in `AccountOpeningBucket.OVERDUE_BUCKETS` goes RED in the test.
GT16_OVERDUE = Decimal("183.10")

#: The customer behind it — B18 §5.9.3a's own narrative row, and BR-CUS-054's
#: legacy key so the migrated account carries the number its old system used.
GT16_CUSTOMER_NAME = "Harmon, Luis"
GT16_CUSTOMER_REF = "CUST-118"

#: CR-056 W2b — the seeded COMPANY's Tax ID (`BR-CUS-1022`).
#:
#: ⚠ **OBVIOUSLY FICTIONAL AND DELIBERATELY SO.** `99-` is the IRS's own
#: reserved prefix for examples; this number belongs to nobody and cannot
#: collide with a real employer identification number. It exists so the company
#: half of the customers list is REACHABLE on the demo utility — before it, the
#: identity column read *"Nothing on file"* for every business in the fixture,
#: which is a built feature nobody can see (hard-won law 2). It is written
#: through `services.link_customer`, the same door a clerk uses, so it is
#: encrypted and blind-indexed exactly as a real one would be and only its last
#: four (`1234`) ever reach a screen.
SAMPLE_COMPANY_TAX_ID = "99-0001234"

#: The account is RESIDENTIAL and carries a sub-type under its own type
#: (DEF-257: a sample account with a NULL sub-type is the two-level tree the PO
#: ratified, invisible on the demo that never uses it).
GT16_ACCOUNT_TYPE = "residential"

#: ❄️ B5 GT-16 line 55 — *"cutover 2026-08-31"*. Customers' OWN copy of the
#: frozen date, carried for the same reason `GT16_BALANCE` is: as an ASSERTION,
#: never as an input. The date this account is actually migrated at comes from
#: metering's published seat; this constant is what that seat is refused for
#: disagreeing with. `apps/metering/sample_data.GT16_CUTOVER_ON` is the value,
#: this is the check on it, and a frozen figure moves only by a finance re-sign
#: through HUMAN-GUIDE §6 (CLAUDE.md).
GT16_CUTOVER_ON = date(2026, 8, 31)


# ══════════════════════════════════════════════════════════════════════════
# DEF-629 · THE DEMO'S CUTOVER DATE IS DECIDED WHEN THE SEED RUNS
# ══════════════════════════════════════════════════════════════════════════
#
# THE DEFECT. Opening buckets age FORWARD from the batch cutover date
# (BR-CUS-048, verbatim: *"Buckets age forward by CALENDAR DAYS from the cutover
# as-of date (an amount imported 45 days past due is 75 days past due 30 days
# later)"*), and BR-CUS-049 pins that date to the batch's ONE cutover
# (*"balanced opening journal entries … dated at cutover, immutable"*). So a
# demo ageing shape planted at a HARDCODED cutover does not stay the shape it
# was planted as: a row seeded `Current` at 2026-08-31 reads `31–60` on
# 2026-10-01 and `90+` by December, and the demo then draws a different AGEING
# column from the screenshot it was built to match. Two correct rules meeting a
# fixture that has to stay true for months.
#
# THE RULING, PO 2026-08-24, verbatim:
#
#   *"whenever you do the migration cant you devcide the date at that time"*
#
# So the demo seed CHOOSES its cutover when it runs. `demo_cutover_on()` below
# is that choice, and it is the ONLY place a demo shape may take a cutover from.
#
# ⚠ ❄️ **GT-16 IS EXCLUDED AND THAT IS PART OF THE RULING** (decision log
# 2026-08-24, item 5): *"GT-16's fixture is EXCLUDED: it is finance-signed at
# cutover 2026-08-31 and that date is part of the frozen case. The seed-time
# date applies to the DEMO SHAPES only."* `A-12103` keeps 2026-08-31, and
# `_seed_gt16_cutover_account` REFUSES a seat offering any other date rather
# than letting a seed-time date reach a finance-signed row.
#
# WHY BR-TEN-043 DOES NOT BITE, IN ONE SENTENCE. BR-TEN-043 is the config-
# forward law — *"every tenant-config change is EVENT-TIME evaluated; the value
# in force when an event occurs governs it"* — and its money-path reading (the
# one G6 greps for, and the one `selectors._bucket_days_past_due` states as
# *"`as_of` is an ARGUMENT and never a clock"*) is that a date governing money
# must be the EVENT's date rather than whatever a clock says when a reader
# happens to look: **this reads the clock exactly once, at the moment the
# migration it is dating actually happens, and STAMPS the answer into
# `account_opening_buckets.as_of`, so every later read still ages from a stored
# event date and no reader ever re-reads a clock.** It is `seams.tenant_today()`
# and not `timezone.now()`, so the day boundary is the utility's own
# (BR-TEN-081), and this module is not one of G6's money paths
# (rating/billing/ledger/payments) — but the reason it is lawful is the sentence
# above, not the directory it sits in.
#
# AND THE REPRODUCIBILITY ARGUMENT THAT FORBIDS A CLOCK IN A WORKFLOW SCRIPT IS
# ANSWERED BY THE SECOND RUN, NOT WAIVED. A seeder whose output moved every time
# it ran would be exactly the drift this fixes, one layer down. So the date is
# decided ONCE per tenant and then PERSISTED: a replay reads back the `as_of`
# already on the tenant's demo buckets and returns THAT. It has to — BR-CUS-049
# makes the opening entries immutable, so re-dating the buckets on a second run
# would leave the journal at the old cutover and the ageing at the new one, and
# the books and the screen would disagree. BR-TEN-063's *"a replay writes
# nothing"* and hard rule 4 point the same way.
#
# ⚠ **NO DEMO AGEING SHAPE IS SEEDED YET, AND THAT IS MEASURED, NOT ASSUMED.**
# On a fully-planted demo tenant `account_opening_buckets` holds four rows on
# ONE account — ❄️ GT-16's `A-12103` — and nothing else; the three shapes
# DEF-629 names (`Active/Current`, `Active/30d past`, `Active/60+ past`) are
# three of B18 §5.1.5's eight `[shot]` rows, which W2 task 2.10 is BLOCKED on
# fixture estate for (decision log 2026-08-24: seven of the eight need a UNIT
# and the fixture has no free one; units are metering's table, B1). This
# function lands AHEAD of them on purpose, so the lane that finally seats those
# rows has a dated policy to call instead of a literal to copy — that is the
# whole content of the PO's ruling, and it is the copy of a hardcoded date that
# this defect is about.


def demo_cutover_on() -> date:
    """The cutover date a DEMO ageing shape is migrated at — chosen AT SEED TIME.

    DEF-629 · PO 2026-08-24: *"whenever you do the migration cant you devcide
    the date at that time"*. See the block above for why this is lawful under
    BR-TEN-043 and why the second run must not move it.

    * **First run** — the tenant's own today (`seams.tenant_today()`, the
      utility's zone per BR-TEN-081), so a shape seeded `Current` derives
      `Current` whether the seed runs this month or in six months.
    * **Every run after** — the `as_of` already stored on this tenant's demo
      buckets, so a replay re-dates nothing (BR-TEN-063) and the immutable
      opening entries behind them stay in step (BR-CUS-049, hard rule 4).

    ❄️ **NOT FOR GT-16.** `A-12103` is finance-signed at `GT16_CUTOVER_ON` and
    is excluded from this decision by the same ruling; it is excluded from the
    lookback below too, or the frozen date would become every later shape's.
    """
    from apps.customers import seams

    stored = (
        models.AccountOpeningBucket.objects.filter(tenant_id=_tenant_id(), is_sample=True)
        .exclude(account__account_no=GT16_ACCOUNT_NO)
        .order_by("as_of")
        .values_list("as_of", flat=True)
        .first()
    )
    if stored is not None:
        return stored
    return seams.tenant_today()


def _cutover_seat() -> dict[str, Any] | None:
    """Metering's published read: the migration run, the seat and the cutover
    date, resolved through the seam — customers never reads `import_runs`
    (metering's table, B1) and never imports metering's sample module."""
    from apps.customers import seams

    resolver = seams.resolve("metering", "sample_account_cutover_seat", kind="sample_data")
    return None if resolver is None else resolver()


def _seed_gt16_cutover_account(actor: Any) -> int:
    """❄️ GT-16 as ROWS: one migrated account, four bucket rows, one balanced
    opening journal entry dated at cutover.

    Idempotent (BR-TEN-063 · CLAUDE.md rule 6, twice over): the account is
    skipped when its number is already on file, and the ledger's own key
    (`opening_balance|<account>|cutover:<batch>`) makes a re-post a no-op that
    returns the first entry — so a replay writes nothing and cannot double a
    utility's opening receivables.

    Returns 0 and says why, rather than raising: a demo tenant whose metering
    block has not run has no seat, and an honest zero with a named reason is
    what BR-TEN-066 asks for. **The one thing it does NOT swallow is a frozen
    figure coming out wrong** — that is a defect in the product, and a seeder
    that logged it would ship a demo whose books do not tie. ❄️ **The frozen
    CUTOVER DATE is now one of those figures** (DEF-629): the seat is refused if
    it offers anything but `GT16_CUTOVER_ON`, because the PO's seed-time cutover
    is for the demo shapes and this account's date is finance-signed.
    """
    seat = _cutover_seat()
    if seat is None:
        logger.info(
            "sample data (CR-030 W1): metering publishes no cutover seat, so ❄️ GT-16's "
            "%s is not planted — the premises/units block has to load first",
            GT16_ACCOUNT_NO,
        )
        return 0
    # ❄️ DEF-629's EXCLUSION, ENFORCED RATHER THAN ASSUMED. The PO's seed-time
    # cutover (`demo_cutover_on`) applies to the DEMO SHAPES only; this account
    # is finance-signed at 2026-08-31 and the date is part of the frozen case.
    # The seat is metering's to publish, so the only way customers can hold that
    # line is to refuse a seat that offers a different one — the same posture
    # this function already takes on the frozen SUM (see `produced != GT16_BALANCE`).
    if seat["cutover_on"] != GT16_CUTOVER_ON:
        raise fixture.BlockCannotRun(
            f"❄️ GT-16 is finance-signed at cutover {GT16_CUTOVER_ON.isoformat()} (B5 line 55) "
            f"and the seat offers {seat['cutover_on']}. DEF-629's seed-time cutover is for the "
            "DEMO SHAPES only (PO 2026-08-24) — this account's date is part of the frozen case "
            "and moves only by a finance re-sign through HUMAN-GUIDE §6, never by a seeder "
            "picking a date. The sample plant refuses rather than re-dating a signed row."
        )
    tenant_id = _tenant_id()
    if models.Account.objects.filter(tenant_id=tenant_id, account_no=GT16_ACCOUNT_NO).exists():
        return 0  # BR-TEN-063: a replay changes no count
    unit_id = _unit_no_to_id().get(seat["unit_no"])
    if unit_id is None:
        logger.info(
            "sample data (CR-030 W1): the cutover seat %s is not seeded, so ❄️ GT-16's "
            "%s has no unit to occupy (BR-CUS-047 — an account import never creates one)",
            seat["unit_no"],
            GT16_ACCOUNT_NO,
        )
        return 0

    try:
        # ONE transaction, so a demo tenant can never be left holding a migrated
        # account whose opening receivables are in `account_opening_buckets`
        # with nothing in the books behind them. Either all of it lands or none
        # of it does (the LOAD stage's own atomicity, TC-IMP-13).
        with transaction.atomic():
            return _plant_gt16_cutover_account(actor, tenant_id, unit_id, seat)
    except fixture.BlockCannotRun:
        # A frozen figure disagreed, or the tie-out failed. LOUD — see below.
        raise
    except Exception as exc:  # noqa: BLE001 — an environment gap, named, never swallowed
        # The commonest cause by far: this tenant has designated no `chart.AR`
        # or `chart.OPENING_CLEARING` account, so `opening_balances` refuses to
        # pick one for a utility's receivables (US-LED-005, OQ-106). That is one
        # edit on the GL mapping page and it must not take the other 48 sample
        # accounts down with it.
        logger.info(
            "sample data (CR-030 W1): ❄️ GT-16's %s was not planted — the books "
            "would not take its opening entry (%s: %s)",
            GT16_ACCOUNT_NO,
            type(exc).__name__,
            exc,
        )
        return 0


def _plant_gt16_cutover_account(
    actor: Any, tenant_id: Any, unit_id: str, seat: dict[str, Any]
) -> int:
    """The write half of `_seed_gt16_cutover_account`, inside its transaction."""
    from apps.customers import import_writer

    mapped = {
        "customer_name": GT16_CUSTOMER_NAME,
        "customer_ref": GT16_CUSTOMER_REF,
        **GT16_BUCKETS,
    }
    account_payload: dict[str, Any] = {
        "account_type": GT16_ACCOUNT_TYPE,
        "status": SAMPLE_ACCOUNT_STATUS,
        "opened_at": fixture.PERIODS[0]["start"].isoformat(),
        "contact": {"full_name": GT16_CUSTOMER_NAME, "is_primary": True},
    }
    # DEF-257 — as every other sample account: a sub-type under its own type,
    # sent only when the tenant HOLDS it (an unknown code is refused by name
    # and would take the whole account with it).
    if SUBTYPE_SINGLE_FAMILY in _available_subtypes():
        account_payload["account_subtype"] = SUBTYPE_SINGLE_FAMILY

    result = services.create_from_import(
        actor=actor,
        payload={
            "mapped": mapped,
            "unit_id": unit_id,
            "account_no": GT16_ACCOUNT_NO,  # BR-CUS-046 — the number they already quote
            "currency": None,  # the TENANT's currency; never a figure typed here
            "cutover_on": seat["cutover_on"],
            "import_run_id": seat["run_id"],
            "account": account_payload,
        },
    )

    # ❄️ The frozen sum, asserted rather than assumed. `create_from_import`
    # derives it from the four bands through `import_writer.opening_position`;
    # if the two ever disagree the CODE is wrong and the seed must stop rather
    # than plant a demo whose books do not tie (the DEF-075 posture).
    produced = Decimal(result["opening_total"])
    if produced != GT16_BALANCE:
        raise fixture.BlockCannotRun(
            f"❄️ GT-16 is finance-signed at {GT16_BALANCE} and the product produced "
            f"{produced} from the same four buckets ({', '.join(GT16_BUCKETS.values())}). "
            "The FIGURE is frozen (B5, 2026-08-08) and may only move by a finance "
            "re-sign through HUMAN-GUIDE §6 — so this is a defect in the code that "
            "summed them, and the sample plant refuses rather than seeding a demo "
            "whose opening books do not tie out."
        )

    # US-CUS-022 — the ONE handoff, exactly as `_load_accounts_rows` makes it
    # at the end of a real run: customers asks, the LEDGER writes the lines.
    posting = import_writer.post_opening_batch_from_import(
        actor=actor,
        batch_id=seat["run_id"],
        cutover_on=seat["cutover_on"],
        imported_at=datetime.combine(seat["cutover_on"], time(0, 0), tzinfo=dt_timezone.utc),
        currency=models.Account.objects.filter(pk=result["id"])
        .values_list("currency", flat=True)
        .first(),
        accounts=[
            {
                "account_id": result["id"],
                "account_ref": result["account_no"],
                "balance": produced,
            }
        ],
    )
    if posting is None:
        # The ledger could not answer and money was supposed to move. Refuse,
        # rather than report a migration whose books do not exist (DEF-075).
        raise fixture.BlockCannotRun(
            "❄️ GT-16's opening entry was not posted: the ledger publishes no "
            "`post_opening_batch` on this deployment, so the demo's migrated "
            f"{GT16_BALANCE} of receivables would sit in `account_opening_buckets` "
            "with nothing in the books behind it (BR-CUS-049)."
        )
    if Decimal(posting["ar_debits"]) != Decimal(posting["clearing_credits"]):
        # `post_opening_batch` refuses first; this is the caller's own check, so
        # the fixture cannot plant an untied batch even if that refusal moved.
        raise fixture.BlockCannotRun(
            f"❄️ GT-16's batch does not tie out: AR debits {posting['ar_debits']} against "
            f"opening-clearing credits {posting['clearing_credits']}. GT-16 requires "
            "Σ opening JEs = Σ imported buckets, and nothing here plugs a delta."
        )

    _tag(models.Account.objects.filter(tenant_id=tenant_id, pk=result["id"], is_sample=False))
    _tag(
        models.Contact.objects.filter(tenant_id=tenant_id, account_id=result["id"], is_sample=False)
    )
    _tag(
        models.AccountOpeningBucket.objects.filter(
            tenant_id=tenant_id, account_id=result["id"], is_sample=False
        )
    )
    _tag(
        models.CustomerAccount.objects.filter(
            tenant_id=tenant_id, account_id=result["id"], is_sample=False
        )
    )
    _tag(
        models.Customer.objects.filter(
            tenant_id=tenant_id, external_ref=GT16_CUSTOMER_REF, is_sample=False
        )
    )
    # 1 account + 4 bucket rows — the rows a reader can go and count.
    return 5


#: ⚠ **`_link_customer` WAS HERE AND IS RETIRED (`BR-CUS-1024`, 2026-09-01).**
#: It ran AFTER the account existed, in its own savepoint, and swallowed its own
#: failures — so a seeded account could end up with no customer and nothing said
#: so. Its whole answer, including the ruling it implements and the reason
#: nothing in it is invented, moves into `_customer_block` above, and the ACCOUNT
#: DOOR now resolves the customer inside the account's own transaction. It is
#: deleted rather than left beside the door: a helper that still works is a
#: helper the next lane will call instead of the rule.

def sample_account_ids() -> dict[int, str]:
    """`{unit_index: account_id}` for the modules that bill and pay these
    accounts, so billing and payments never have to guess which account is
    which awkward case. A published READ — neither module reads this one's
    tables."""
    units = {unit["unit_no"]: unit["unit_index"] for unit in fixture.units_flat()}
    out: dict[int, str] = {}
    for row in models.Account.objects.filter(tenant_id=_tenant_id(), is_sample=True).select_related(
        "unit"
    ):
        index = units.get(getattr(row.unit, "unit_no", None))
        if index is not None:
            out[index] = str(row.id)
    return out


# ══════════════════════════════════════════════════════════════════════════
# THE MOVE-OUT THAT ACTUALLY FINISHES — the demo's ONE closed account
# ══════════════════════════════════════════════════════════════════════════
#
# **THE DEFECT THIS BLOCK EXISTS FOR, MEASURED ON A SEEDED TENANT ON
# 2026-09-07 (`DEF-CUS-4628`).** On `brazosbend`, freshly planted:
#
#     69 Active · 1 Marked disconnect · 1 Pending activation ·
#     1 Vacation hold · 0 Closed · 0 Disconnected
#     select count(*) from accounts where closed_at is not null  →  0
#     select count(*) from move_records where kind = 'move_out'  →  0
#
# `Closed` is the TERMINAL state — the one the whole move-out flow exists to
# ARRIVE at — and **no seeded tenant this product has ever planted has
# contained a single account in it.** The `Move-out` button on `S21` is live,
# the `S20` wizard is built, `BR-CUS-030` is implemented, and the one question
# nobody asked was *does anything ever get there*.
#
# ⚠ **NOTHING WAS BROKEN IN THE PRODUCT, AND THAT IS THE PART WORTH READING.**
# `services.move_out` writes `closed_at`, the terminal status, every open
# `service_agreements.ended_on`, the `account.closed` audit row, the `MVO-`
# move record and the `email_move_out_final` letter, exactly as the rule says.
# What was missing is that **nothing ever called it on the demo estate.**
# `core/sample_fixture.account_plan()` has carried a `moved_out_on` key on
# `CASE_MOVED_OUT` since the fixture was written and a grep for that key over
# the whole of `06-backend/apps` and `06-backend/core` returned **the
# definition and no reader** — a fixture field with no consumer, which is
# hard-won law 2 ("built is not wired") wearing a data costume.
#
# ⚠ **AND THE SECOND CONSUMER OF `closed_at` WAS SILENTLY DOING NOTHING TOO.**
# `_seed_cr039_move_records` above skips any account whose `closed_at` is NULL,
# and the comment in `seed_sample_records` that justified its position says
# *"three of its five transfers COMMIT (which closes their outgoing
# account)"*. **That stopped being true on 2026-09-01**, when the PO ruled
# *"dont create new account - we reassing that account"* and `commit_transfer`
# became `transfers.reassign_account`, which asserts `"account_closed": False`
# on its own audit row. So the demo has ONE move record, it is a move-IN, and
# the `MVO-` series has never issued a number. This block is what makes it.
#
# ⛔ **WHAT THIS BLOCK REFUSES TO DO.** It does not `UPDATE` an account row to
# `closed`. A seeder that writes the status and the date directly would prove
# nothing at all — it would put the demo in a state the product's own door had
# never been asked to produce, which is precisely the gap being closed here.
# It calls `services.move_out`, the same function `POST /accounts/{id}/
# move-out` calls, and takes whatever that function does to the estate.
#
# ⚠ **ONE ACCOUNT, NOT FIFTY.** The Product Owner's standing principle for
# this fixture is that *a demo where everything is finished leaves nothing to
# evaluate* — it is why the third billing cycle is deliberately left unrun.
# So exactly one tenancy ends: the one the fixture already declared.
#
# ⚠ **THE ACCOUNT KEEPS ITS UNPAID JULY BILL, AND THAT IS `BR-CUS-082`, NOT AN
# OVERSIGHT.** `_july_share_for` leaves unit 41 unpaid (41 % 4 == 1), so the
# closed account carries **$139.72** outstanding. `BR-CUS-082` (CONFIRMED, PO
# 2026-08-24, *"(b) continue, ladder restarts"*) is explicit that a debt
# surviving closure is still chased, and until today that ruling had no worked
# case anywhere a person could open. Paying it off here to make the demo tidy
# would delete the only example of the rule.
#
# ⚠ **`final_read_state` LANDS ON `due`, WHICH IS THE TRUE ANSWER.** The seat
# is an apartment and its sub-meter `SM-7041` holds no reading at all, so
# `_final_read_state` answers `due` for the unit. That is the first non-NULL
# `final_read_state` any seeded tenant has ever held, and inventing a reading
# to make it say `taken` would state that a meter was read when none was
# (fixture spec rule 7).


def seed_sample_move_out(actor: Any) -> int:
    """ONE seeded tenancy ends, through `services.move_out` and nothing else.

    The seat and the date are BOTH the fixture's: `fixture.CASE_MOVED_OUT`
    names the unit and `fixture.move_out_on()` names the day, derived from the
    last period this fixture BILLED so the `BR-BIL-004` guard is satisfied by
    construction rather than by a literal somebody has to remember to move.

    Idempotent (BR-TEN-063 · CLAUDE.md rule 6): a replay finds the account
    already terminal and writes nothing, because the account row IS the state.

    ⚠ **IT RUNS AFTER THE MONEY, AND THE POSITION IS THE FEATURE** — the same
    argument `payments:seed_sample_refund` and `billing:seed_sample_correction`
    make one block up. Run it BEFORE the two billing blocks and this account
    leaves `accounts_in_cycle` (`OCCUPYING_BEHAVIOR_CLASSES`), so it is billed
    NEITHER month and the estate loses two bills and its August reading story.
    Run it after the collections block, as it does, and the tenancy is billed
    twice, part-collected exactly as the fixture intends, and then ends.
    """
    entry = next(
        (row for row in fixture.account_plan() if row["unit_index"] == fixture.CASE_MOVED_OUT),
        None,
    )
    if entry is None or entry.get("moved_out_on") is None:
        raise fixture.BlockCannotRun(
            "no account moved out: core/sample_fixture.account_plan() no longer carries a "
            "`moved_out_on` date for CASE_MOVED_OUT, so this block has no day to close on "
            "and does not invent one."
        )
    account_id = sample_account_ids().get(fixture.CASE_MOVED_OUT)
    if account_id is None:
        raise fixture.BlockCannotRun(
            f"no account moved out: the fixture's move-out seat ({entry['unit_no']}) holds no "
            "sample account. The UPSTREAM block is 'Accounts, customers & service agreements' "
            "— fix that block and load again. This is a failure, not an empty result."
        )
    account = (
        models.Account.objects.select_related("status")
        .filter(tenant_id=_tenant_id(), pk=account_id)
        .first()
    )
    if account is None:  # pragma: no cover - `sample_account_ids` just read it
        raise fixture.BlockCannotRun(
            f"no account moved out: {entry['unit_no']}'s account disappeared between being "
            "listed and being read."
        )
    if account.status.behavior_class == services.CLASS_TERMINAL:
        # A REPLAY, not a refusal. Stated rather than silent so an operator
        # reading the trace can tell "already done" from "did nothing".
        logger.info(
            "sample data (the move-out that finishes): %s is already %s since %s — nothing "
            "to do",
            account.account_no,
            account.status.code,
            account.closed_at,
        )
        return 0
    moved_out_on = entry["moved_out_on"]
    # NOT wrapped in a `try`. A refusal here is a real fact about the estate —
    # the wrong date, a bill issued past it, an account that is not an occupant
    # — and the orchestrator renders the BizError's own sentence on the Sample
    # data panel (BR-TEN-060). Swallowing it would put this block back where it
    # started: green, and closing nothing.
    services.move_out(actor, account.id, {"moved_out_on": moved_out_on.isoformat()})
    account.refresh_from_db()
    logger.info(
        "sample data (the move-out that finishes): %s closed on %s, final read %s",
        account.account_no,
        account.closed_at,
        account.final_read_state or "not derived",
    )
    return 1


def seed_sample_payment_plans(actor: Any) -> int:
    """THE COLLECTIONS SEAM — CR-010 Part-10.4 amendment 3 (PO 2026-08-17).

    PO verbatim: *"you did not cover outstanding repcrds, payment plans"* —
    CASE_PAYMENT_PLAN stops being a case NARRATIVE in core/sample_fixture.py
    and becomes the actual rows a trial user can open on S21/S24: one LIVE
    `payment_plans` row with its `payment_plan_installments`, mid-schedule.

    THE ROUTE IS THE S24 WIZARD'S OWN, STEP BY STEP — spec rule 4 (*"seed
    through the services a clerk's click uses"*) applied to the one money case
    the 2026-08-16 lane deferred:

      `preview` (BR-CUS-043's arithmetic via `build_schedule`, GT-47 ❄️ —
      NEVER duplicated in a seeder) → `send_agreement` (rows handed to
      payments through the wizard's own seam; customers writes no financial
      table, BR-CUS-037) → `activate` (the customer's e-signature alone,
      BR-CUS-044).

    THE BALANCE IT SPREADS IS THE LEDGER'S FIGURE, not an amount typed here:
    the account's June bill is deliberately left unpaid by payments'
    `_share_for`, and `seams.ar_positions` answers what the books say is owed
    (DEF-127's read — the cache is never trusted). The plan's MONEY — the down
    payment and the two paid instalments — is payments' own block,
    `seed_sample_plan_payments`, which runs after this one.

    Runs AFTER billing and payments in SAMPLE_MODULES, because a plan spreads
    a debt that exists (US-CUS-018 TC-6). Idempotent (BR-TEN-063): an account
    already holding a live plan is a replay, and nothing is written.
    """
    from apps.customers import payment_plan_service, seams
    from core import sample_fixture

    plan_spec = sample_fixture.PAYMENT_PLAN
    account_id = sample_account_ids().get(plan_spec["unit_index"])
    if account_id is None:
        raise fixture.BlockCannotRun(
            "no payment plan was created: the sample accounts are not seeded, so "
            f"unit {plan_spec['unit_index']}'s account does not exist. The Accounts "
            "block above has to load first."
        )
    existing = seams.payment_plans_for(account_id, as_of=None)
    if existing is None:
        raise fixture.BlockCannotRun(
            "no payment plan can be created: payments publishes no payment-plan "
            "read on this deployment (apps.payments.services.payment_plans_for_"
            "account), so this block cannot even tell whether one already exists."
        )
    if any(row["live"] for row in existing):
        return 0  # BR-TEN-063: a replay changes no count

    positions = seams.ar_positions([account_id])
    balance = positions.amount_for(account_id)
    if balance is None:
        reasons = "; ".join(
            str(row.get("detail") or row.get("code")) for row in positions.unavailable
        )
        raise fixture.BlockCannotRun(
            "no payment plan was created: the ledger could not be asked what this "
            "account owes, and a plan spreads a debt that EXISTS (US-CUS-018 TC-6) "
            f"— never a figure a fixture invents. {reasons or 'no reason reported'}"
        )
    balance = Decimal(str(balance))
    if balance <= 0:
        raise fixture.BlockCannotRun(
            f"no payment plan was created: the books say this account owes {balance}, "
            "and the fixture's plan spreads its UNPAID June bill. Payments' block above "
            "is supposed to leave CASE_PAYMENT_PLAN's June bill wholly unpaid "
            "(_share_for returns None for it) — if that changed, this broke with it."
        )
    currency = positions.currency or seams.tenant_currency()
    if not currency:
        raise fixture.BlockCannotRun(
            "no payment plan was created: neither the ledger nor tenancy reports a "
            "currency, and an instalment without its CHAR(3) is not money "
            "(CLAUDE.md rule 2)."
        )
    down = (balance * plan_spec["down_payment_share"]).quantize(Decimal("0.01"))
    preview = payment_plan_service.preview(
        balance_to_spread=balance,
        account_balance=balance,
        installments=plan_spec["installments"],
        cadence=plan_spec["cadence"],
        first_due_date=plan_spec["first_due"],
        as_of=plan_spec["proposed_on"],
        currency=currency,
        live_plan_exists=False,
        down_payment=down,
    )
    sent = payment_plan_service.send_agreement(
        actor=actor,
        account_id=account_id,
        plan=preview,
        channels=("email",),
        on_date=plan_spec["proposed_on"],
    )
    payment_plan_service.activate(
        actor=actor,
        plan_id=sent["id"],
        current_status=sent["status"],
        signed_on=plan_spec["signed_on"],
    )
    # The plan row and its instalment rows, counted as what landed.
    return 1 + plan_spec["installments"]


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-061/066 — hard delete of this module's `is_sample = true` rows in
    reverse dependency order, reporting what it RETAINED and why.

    An account that has been BILLED is retained BY NAME. Hard rule 4 makes its
    invoices, invoice lines and payments append-only, and `invoices.account_id`
    is `ON DELETE NO ACTION`, so the delete could not succeed and must not be
    attempted quietly. BR-TEN-066 is the rule and this is its literal case:
    *"remove what is free, report the rest BY NAME"*.
    """
    tenant_id = _tenant_id()
    removed = 0
    retained: list[dict[str, Any]] = []

    # ── DEF-MET-6302 — RELEASE THE OWNER-ACCOUNT LINKS BEFORE ANYTHING ELSE ──
    #
    # ⛔ **BR-TEN-061 REMOVES CUSTOMERS BEFORE METERING AND
    # `premises.master_account` IS `PROTECT`.** `_distinct_modules()` keeps each
    # module's FIRST block and `remove_sample_data` walks that list backwards, so
    # metering (its first block is the estate, near the top of `SAMPLE_MODULES`)
    # is removed AFTER this module — it can never clear these links in time.
    #
    # Without this line the four seeded owner accounts raise `ProtectedError` in
    # the per-account `except` below and are RETAINED under its sentence, *"it
    # has bills or payments against it"* — which is FALSE for every one of them
    # (they cover nothing and have never been billed). Hard-won law 1: a message
    # claiming a reason is not the reason, and this panel is where a utility
    # decides whether its demo data is gone.
    #
    # It releases ONLY a SAMPLE address naming a SAMPLE account, so a real
    # premises a utility has pointed at one of these is left exactly as it is.
    from apps.customers import sample_owner_accounts

    retained.extend(sample_owner_accounts.release_sample_owner_accounts())

    # CR-035 — the parked draft goes FIRST among the DELETES, and it is the only
    # free removal in this function: `wizard_parks` has no FK to anything
    # (BR-SHL-048 (a)), so nothing can hold it open and nothing it holds open
    # can be retained.
    parks = remove_sample_wizard_parks()
    removed += int(parks["removed"])
    retained.extend(parks["retained"])

    # CR-030 W7 T7.12 — the transfers, the disconnect cases, their notices and
    # the protections come out FIRST, because every one of them holds an
    # `accounts` row open through a `PROTECT` FK. An account carrying a case
    # would otherwise be RETAINED by name (BR-TEN-066) — correct, and wrong: the
    # case is sample data too.
    #
    # ⚠ **`disconnect_cases`, `disconnect_notices` AND `account_protections`
    # CARRY NO `is_sample` COLUMN** (measured 2026-08-25: task 7.5's migration
    # gives them none), so BR-TEN-057's predicate does not exist for them and
    # the sweep is keyed on the SAMPLE ACCOUNT instead. That is a narrower key,
    # not a wider one — nothing outside `is_sample` accounts is touched — but it
    # is a divergence from the tag rule and **the column is OWED**. Reported
    # here rather than papered over; `transfers` DOES carry the tag and is
    # swept on it.
    from apps.customers import disconnects, transfers

    sample_account_pks = models.Account.objects.filter(tenant_id=tenant_id, is_sample=True).values(
        "pk"
    )
    for label, queryset in (
        (
            "transfer",
            transfers.Transfer.objects.filter(tenant_id=tenant_id, is_sample=True),
        ),
        (
            "disconnect notice",
            disconnects.DisconnectNotice.objects.filter(
                tenant_id=tenant_id, case__account__in=sample_account_pks
            ),
        ),
        (
            "disconnect case",
            disconnects.DisconnectCase.objects.filter(
                tenant_id=tenant_id, account__in=sample_account_pks
            ),
        ),
        (
            "account protection",
            disconnects.AccountProtection.objects.filter(
                tenant_id=tenant_id, account__in=sample_account_pks
            ),
        ),
    ):
        for row in list(queryset):
            try:
                with transaction.atomic():
                    row.delete()
                removed += 1
            except Exception as exc:  # noqa: BLE001 — BR-TEN-066: name it, keep going
                retained.append(
                    {
                        "label": f"{label} {row.pk}",
                        "reason": (
                            "something you kept still references it — " f"{type(exc).__name__}"
                        ),
                    }
                )

    accounts = list(models.Account.objects.filter(tenant_id=tenant_id, is_sample=True))
    for account in accounts:
        try:
            with transaction.atomic():
                models.ServiceAgreement.objects.filter(
                    tenant_id=tenant_id, account=account, is_sample=True
                ).delete()
                models.Address.objects.filter(
                    tenant_id=tenant_id, account=account, is_sample=True
                ).delete()
                models.Contact.objects.filter(
                    tenant_id=tenant_id, account=account, is_sample=True
                ).delete()
                models.AccountNote.objects.filter(tenant_id=tenant_id, account=account).delete()
                # CR-030 W1 T1.23 — the migrated account's four aged buckets.
                # ⚠ The opening JOURNAL ENTRY behind them is NOT removed and
                # cannot be: a posted entry is append-only (hard rule 4) and
                # only the ledger may touch journal lines (rule 5). Removing
                # the buckets while the entry stands is the same partial
                # removal BR-TEN-066 already rules for a billed account, and
                # `apps/ledger` owns the correction path (J6).
                models.AccountOpeningBucket.objects.filter(
                    tenant_id=tenant_id, account=account, is_sample=True
                ).delete()
                models.CustomerAccount.objects.filter(
                    tenant_id=tenant_id, account=account, is_sample=True
                ).delete()
                account.delete()
            removed += 1
        except Exception as exc:  # noqa: BLE001 — BR-TEN-066: name it, keep going
            retained.append(
                {
                    "label": f"account {account.account_no}",
                    "reason": (
                        "it has bills or payments against it. An issued invoice, its "
                        "lines and its payments can never be changed or deleted "
                        "(CLAUDE.md hard rule 4), so the account they belong to stays "
                        f"— {type(exc).__name__}"
                    ),
                }
            )

    orphans = models.Customer.objects.filter(tenant_id=tenant_id, is_sample=True).exclude(
        pk__in=models.CustomerAccount.objects.filter(tenant_id=tenant_id).values("customer_id")
    )
    removed += orphans.delete()[0]
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    return int(models.Account.objects.filter(tenant_id=_tenant_id(), is_sample=True).count())


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W2 · TASK 2.10 — THE EIGHT `[shot]` ACCOUNT SHAPES (B18 §5.1.5)
# ══════════════════════════════════════════════════════════════════════════
#
# PO AUTHORISATION, 2026-08-24: ***"so add them"*** — the estate this needs
# (`core/sample_fixture.CR030_PREMISES`) is seeded by metering, which owns
# `premises` and `units`, and this block takes the seats it leaves.
#
# ⚠ **EVERY SHAPE GOES THROUGH `create_from_import`, INCLUDING THE ONES WITH NO
# OPENING BALANCE, and the reason is the same one `_seed_gt16_cutover_account`
# gives one screen up.** The AGEING column is DERIVED from the account's own
# opening position (BR-CUS-016 → BR-CUS-048), so a shape is made by giving the
# account a BUCKET and never by typing a segment; and `create_from_import` is
# the single path that writes the buckets, caches `accounts.balance` from the
# SAME position object and hands the batch to the ledger. Using it for the
# balance-less shapes too keeps ONE creation path for the estate, and it is the
# only door that accepts a MIGRATED deposit with its original receipt date
# (`IMPORT_ACCOUNT_FIELDS`, US-CUS-023) — which `A-12048 · Kwan, Michael` has
# and a hand-typed account may not.
#
# ⚠ **THE CUTOVER DATE IS `demo_cutover_on()`, NEVER A LITERAL** — DEF-629, PO
# 2026-08-24: *"whenever you do the migration cant you devcide the date at that
# time"*. Decided at seed time, persisted, so `Active/Current` still reads
# Current in six months. ❄️ GT-16 is EXCLUDED from that decision and keeps its
# finance-signed 2026-08-31; nothing here touches it.


def _cr030_account_payload(shape: dict[str, Any], subtypes: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_type": shape["account_type"],
        "status": shape["status"],
        "opened_at": shape["opened_at"].isoformat(),
        "autopay": bool(shape.get("autopay")),
        "contact": {
            "full_name": shape["customer_name"],
            "email": shape.get("email"),
            "phone": shape.get("phone"),
            "is_primary": True,
        },
    }
    if shape.get("deposit_on_file"):
        # US-CUS-023 / BR-CUS-050: a migrated deposit arrives WITH its original
        # receipt date, or interest starts at cutover and the longest-standing
        # customers are quietly under-paid.
        payload["deposit_on_file"] = shape["deposit_on_file"]
        payload["deposit_received_on"] = shape["deposit_received_on"].isoformat()
    subtype = SUBTYPE_COMMERCIAL if shape["account_type"] == "commercial" else SUBTYPE_SINGLE_FAMILY
    if subtype in subtypes:
        payload["account_subtype"] = subtype
    return payload


def _seed_cr030_account_shapes(actor: Any) -> int:
    """B18 §5.1.5's eight shapes, as rows a reader can go and count.

    Idempotent (BR-TEN-063): a shape whose account number is already on file is
    skipped, so a replay writes nothing and changes no count.
    """
    units = _unit_no_to_id()
    if not units:
        return 0
    seat = _cutover_seat()
    tenant_id = _tenant_id()
    subtypes = _available_subtypes()
    cutover = demo_cutover_on()
    written = 0
    posted: list[dict[str, Any]] = []
    #: DEF-1713 — the migrated deposits this block plants, so they reach the
    #: 2300 deposit-liability account as well as `accounts.deposit_on_file`.
    held: list[dict[str, Any]] = []
    for shape in fixture.CR030_ACCOUNT_SHAPES:
        account_no = shape["account_no"]
        if models.Account.objects.filter(tenant_id=tenant_id, account_no=account_no).exists():
            continue
        unit_id = units.get(shape["unit_no"])
        if unit_id is None:
            logger.info(
                "sample data (CR-030 W2): %s has no seat — unit %s is not seeded, so the "
                "%r shape is missing from the Accounts register",
                account_no,
                shape["unit_no"],
                shape["shape"],
            )
            continue
        if services.active_account_for_unit(unit_id) is not None:
            continue
        mapped: dict[str, Any] = {
            "customer_name": shape["customer_name"],
            "customer_ref": shape["customer_ref"],
            **(shape.get("buckets") or {}),
        }
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                result = services.create_from_import(
                    actor=actor,
                    payload={
                        "mapped": mapped,
                        "unit_id": unit_id,
                        "account_no": account_no,
                        "currency": None,  # the TENANT's, never a figure typed here
                        "cutover_on": cutover,
                        # The migration these rows came across on — B18 §5.9.6's
                        # RUN-2814, the run that "loads 1,247". None when metering
                        # has not seeded the history, which the buckets tolerate.
                        "import_run_id": (seat or {}).get("run_id"),
                        "account": _cr030_account_payload(shape, subtypes),
                    },
                )
        except Exception as exc:  # noqa: BLE001 — one refusal must not stop the rest
            logger.info(
                "sample data (CR-030 W2): %s (%s) was refused — %s: %s",
                account_no,
                shape["shape"],
                type(exc).__name__,
                exc,
            )
            continue
        written += 1
        _tag(models.Account.objects.filter(tenant_id=tenant_id, pk=result["id"], is_sample=False))
        _tag(
            models.Contact.objects.filter(
                tenant_id=tenant_id, account_id=result["id"], is_sample=False
            )
        )
        _tag(
            models.AccountOpeningBucket.objects.filter(
                tenant_id=tenant_id, account_id=result["id"], is_sample=False
            )
        )
        _tag(
            models.CustomerAccount.objects.filter(
                tenant_id=tenant_id, account_id=result["id"], is_sample=False
            )
        )
        _tag(
            models.Customer.objects.filter(
                tenant_id=tenant_id, external_ref=shape["customer_ref"], is_sample=False
            )
        )
        if not result["opening_empty"]:
            posted.append(
                {
                    "account_id": result["id"],
                    "account_ref": result["account_no"],
                    "balance": Decimal(result["opening_total"]),
                }
            )
        # DEF-1713 — the second money column on the same row. A shape may hold a
        # deposit and owe nothing (`A-12048 · Kwan, Michael` does), so this is
        # NOT nested under `opening_empty`: that nesting is the mistake that
        # would leave the liability unposted on exactly the accounts that have
        # one and no arrears.
        if Decimal(result.get("deposit_on_file") or 0):
            held.append(
                {
                    "account_id": result["id"],
                    "account_ref": result["account_no"],
                    "held": Decimal(result["deposit_on_file"]),
                    "received_on": result.get("deposit_received_on"),
                }
            )
    written += _post_cr030_opening_batch(actor, cutover, seat, posted, held)
    return written


def _post_cr030_opening_batch(
    actor: Any,
    cutover: date,
    seat: dict[str, Any] | None,
    accounts: list[dict[str, Any]],
    deposits: list[dict[str, Any]] | None = None,
) -> int:
    """The estate's opening receivables, posted BY THE LEDGER — never here.

    ⚠ **CUSTOMERS WRITES NO JOURNAL LINES** (CLAUDE.md hard rule 5, B1). This
    composes the contract and hands it to `import_writer.post_opening_batch_from
    _import`, which hands it to `apps.ledger.opening_balances`; the POSTING
    SERVICE writes the balanced pair, keyed (`opening_balance|<account>|cutover:
    <batch>`) so a replay is a no-op.

    **Why it must happen at all:** the S17 `BALANCE` cell is the LEDGER's AR
    position and NOT `accounts.balance` (DEF-127 — the number the product could
    not tell a customer). Buckets alone would age the row correctly and leave
    every balance reading *unavailable*, so `Park, Jenna`'s `$542.10` — one
    figure on two tabs, B18 §6.6(c) — would not render.

    Returns 0 and SAYS WHY rather than raising: a tenant that has designated no
    `chart.AR` account cannot post, and that must not take the eight accounts
    down with it (`_seed_gt16_cutover_account`'s own posture). ❄️ Unlike GT-16
    there is no frozen figure here, so nothing refuses.
    """
    deposits = deposits or []
    if (not accounts and not deposits) or seat is None:
        return 0
    from apps.customers import import_writer

    currency = (
        models.Account.objects.filter(pk=(accounts or deposits)[0]["account_id"])
        .values_list("currency", flat=True)
        .first()
    )
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            posting = import_writer.post_opening_batch_from_import(
                actor=actor,
                # ⚠ NOT `seat["run_id"]` — see `CR030_OPENING_BATCH_KEY`. ❄️ GT-16's
                # batch keeps one set of opening entries; the estate keys its own.
                batch_id=fixture.CR030_OPENING_BATCH_KEY,
                cutover_on=cutover,
                imported_at=datetime.combine(cutover, time(0, 0), tzinfo=dt_timezone.utc),
                currency=currency,
                accounts=accounts,
                # DEF-1713 — the deposits ride the SAME batch id and the SAME
                # cutover date as the receivables. One migration, one handoff.
                deposits=deposits,
            )
    except Exception as exc:  # noqa: BLE001 — an environment gap, named
        logger.info(
            "sample data (CR-030 W2): the estate's opening entries were not posted (%s: %s), "
            "so the AGEING column renders and the BALANCE column reads unavailable. Map "
            "the AR and opening-clearing accounts on Settings > Chart of accounts",
            type(exc).__name__,
            exc,
        )
        return 0
    if posting is None:
        logger.info(
            "sample data (CR-030 W2): the ledger publishes no `post_opening_batch` on this "
            "deployment, so the estate's opening receivables have no entry behind them "
            "(BR-CUS-049) and the BALANCE column reads unavailable"
        )
        return 0
    return len(accounts)


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W4 · TASK 4.14 — THE EIGHT `[shot]` REQUESTS (B18 §5.3.10 · B19 §12.1)
# ══════════════════════════════════════════════════════════════════════════
#
# ✅ **UNBLOCKED BY BR-CUS-095 (PO 2026-08-24, closing OQ-351).** The rule's own
# closing line is this task: *"THIS UNBLOCKS THE SEED, which was the only thing
# OQ-351 was actually blocking: the demo fixture can now show a request sitting
# in `More info needed` and say what it is waiting for."*
#
# ⚠ **THE SHIPPED DEFAULT IS NOT TOUCHED, AND THAT IS THE RULING'S SHARPEST
# CLAUSE:** *"nothing is ticked, so a utility that never opens the screen never
# has a request blocked. No helpful pre-tick of proof of identity, however
# reasonable it looks."* `_seed_cr030_document_requirements` below is the DEMO
# TENANT ticking its own two boxes through `set_document_requirement` — the same
# call the Settings screen makes, on that tenant's rows only. A tenant that
# never loads sample data still ticks nothing, and no migration, platform row or
# code default was changed to make this work.
#
# EVERY REQUEST IS BUILT THROUGH THE SERVICE PATH A CLERK DRIVES — `create_
# request` (which numbers it at creation, BR-CUS-093), `resolve_address`,
# `attach_document`, `verify_document`, `add_fee_line`, `collect_fee`, `submit`,
# `transition`, `decide_outcome`, `approve`, `park`, `link_child`. Nothing here
# writes a state, an outcome or a number behind the state machine's back.
#
# ⚠ **ONE COLUMN IS WRITTEN DIRECTLY AND IT IS `received_at`.** `create_request`
# stamps `timezone.now()`, and the list's whole point is *"Sorted by age, oldest
# first — the oldest thing waiting is the thing to look at"* with `15d` and `11d`
# in the accent. Eight requests all created this second would render eight `0d`
# rows and the column would teach nothing. So the seeder back-dates to
# *today − age_days*, on its OWN module's table, in the `_tag` disposition — and
# it is RELATIVE for DEF-629's reason: a hardcoded `Aug 08` is 15 days old today
# and a year old next August.


def _seed_cr030_document_requirements(actor: Any) -> int:
    """BR-CUS-095's worked example, as this tenant's own two ticks."""
    from apps.customers import service_request_service as sr

    written = 0
    for entry in fixture.CR030_DOCUMENT_REQUIREMENTS:
        # BR-TEN-063 is *"a replay writes nothing AND CHANGES NO COUNT"*, and
        # the second half is the one a tick can fail: `set_document_requirement`
        # is an upsert, so calling it twice writes one row and would report two.
        # The count is what the Sample data panel shows an operator.
        if models.ServiceRequestDocumentRequirement.objects.filter(
            tenant_id=_tenant_id(),
            request_type=entry["request_type"],
            doc_type=entry["doc_type"],
            required=bool(entry["required"]),
        ).exists():
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.set_document_requirement(
                    actor,
                    request_type=entry["request_type"],
                    doc_type=entry["doc_type"],
                    required=bool(entry["required"]),
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-030 W4): the %s/%s checklist tick was refused — %s: %s",
                entry["request_type"],
                entry["doc_type"],
                type(exc).__name__,
                exc,
            )
            continue
        written += 1
    return written


#: The lifecycle each drawn STATE is reached by — actions only, in order, and
#: every one of them a control the REQ-02 screen draws. `approve` and
#: `decide_outcome` have their own doors (the state machine refuses them through
#: `transition`), so they are named rather than listed here.
#:
#: ⚠⚠ **REWRITTEN 2026-09-19 — `pick_up` AND `route` NO LONGER EXIST.** The PO
#: left the request five states and took nine moves out of `TRANSITIONS`. Every
#: path here used to start with `pick_up`; the decisions work straight from
#: `submitted` now, so the paths are empty or one move long.
#:
#: ⚠ **`under_review` IS NOT REACHED HERE AT ALL — IT IS REACHED BY PARKING**,
#: further down this same function, because park is the one control that still
#: moves `submitted` → `under_review`. A fixture declaring `under_review` with
#: **no** `waiting_on` therefore cannot be planted any more: there is no way to
#: park without saying what is awaited, and that is the rule working rather
#: than a gap. See `_CR030_UNREACHABLE_SINCE_RULING`.
_CR030_STATE_PATH: dict[str, tuple[str, ...]] = {
    "submitted": (),
    "under_review": (),  # parked below — park moves submitted → under_review
    "more_info": ("request_info",),
    "approved": (),  # + decide_outcome + approve, both lawful from `submitted`
}

#: ⚠ **THE DRAWN STATES THE 2026-09-19 RULING PUT OUT OF REACH, AND WHERE EACH
#: ROW LANDS INSTEAD.** Named here rather than discovered: a fixture that
#: quietly lands somewhere other than its drawn state is a demo tenant nobody
#: can trust, and `CR030_SERVICE_REQUESTS` deliberately keeps its DRAWN
#: declarations as the record of the blueprint.
#:
#:   * `in_fulfilment` — `route` is retired; the row stops at `approved`, which
#:     is where the PO put the boundary (*"once requets is approved then in
#:     move in or new connect we take all those decision to in fulfill etc"*).
#:   * `under_review` **with no `waiting_on`** — park is the only way in and it
#:     requires a reason; the row stays `submitted`.
#:
#: And one that moves the other way, which is the same ruling seen from the
#: other side: a fixture drawn `submitted` **with** a `waiting_on` is parked,
#: and parking now picks it up — so it lands in `under_review`. The blueprint's
#: own register draws that combination (`SR-26-0001`, *Submitted · waiting on
#: documents*) and it is no longer reachable. Reported, not papered over.
_CR030_UNREACHABLE_SINCE_RULING: dict[str, str] = {
    "in_fulfilment": "approved",
}


def _cr030_capture_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "channel": entry["channel"],
        "applicant_kind": entry["applicant_kind"],
        "applicant_name": entry["applicant_name"],
        "address_as_given": entry["address_as_given"],
        "billing_address_same": True,
    }
    for key in (
        "applicant_email",
        "applicant_phone",
        "address_unit_as_given",
        "plot_or_parcel",
        "what_is_being_built",
        "property_type",
        "what_they_said",
        "requested_start",
    ):
        if entry.get(key):
            payload[key] = entry[key]
    return payload


def _seed_cr030_service_requests(actor: Any) -> int:
    """The eight `[shot]` requests — all five types, six states, cross-wired.

    Idempotent (BR-TEN-063): a request whose `address_as_given` + applicant is
    already on file as a SAMPLE row is skipped. The request NUMBER cannot be the
    idempotency key here — the series allocates it and a replay would allocate a
    different one, which is exactly the double-seed this guard has to catch.
    """
    from apps.customers import service_request_service as sr

    from apps.customers import seams

    tenant_id = _tenant_id()
    written = _seed_cr030_document_requirements(actor)
    today = seams.tenant_today()
    for entry in fixture.CR030_SERVICE_REQUESTS:
        already = models.ServiceRequest.objects.filter(
            tenant_id=tenant_id,
            is_sample=True,
            address_as_given=entry["address_as_given"],
            applicant_name=entry["applicant_name"],
        ).first()
        if already is not None:
            # ── DEF-CUS-5423 · A REPLAY REACHES A REQUEST THAT PREDATES THE
            # SERVICES STEP ────────────────────────────────────────────────
            # This block was idempotent PER REQUEST, so a request seeded before
            # 2026-09-16 could never gain the services step no matter how often
            # somebody pressed *Load sample data* — which would have left the
            # demo tenant the PO reviews screens on with the empty panel this
            # defect is about, for ever. That is `DEF-1250`'s shape exactly
            # (a plan idempotent per PLAN could never gain a service switched on
            # afterwards) and it is repaired the same way.
            #
            # ⚠ **ADDITIVE ONLY, AND ONLY WHEN THERE ARE NONE.** `set_services`
            # REPLACES the set, so running it over a request that already has
            # services would overwrite whatever is there — including a date a
            # person typed while demonstrating the screen. The guard is *no
            # rows at all*, which is `apply_default_gl_accounts`' rule one
            # module over: fill an absence, never replace an answer.
            written += _reconcile_cr030_services(actor, sr, already, entry)
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                request = sr.create_request(actor, _cr030_capture_payload(entry))
        except Exception as exc:  # noqa: BLE001 — one refusal must not stop the rest
            logger.info(
                "sample data (CR-030 W4): %s (%s) was refused at creation — %s: %s",
                entry["drawn_no"],
                entry["applicant_name"],
                type(exc).__name__,
                exc,
            )
            continue
        # ⚠ `received_at` — see the block header. The list's AGE column is the
        # whole reason this row exists, and it is relative so it stays true.
        received_at = datetime.combine(
            today - timedelta(days=int(entry["age_days"])), time(9, 30), tzinfo=dt_timezone.utc
        )
        models.ServiceRequest.objects.filter(pk=request.id).update(
            received_at=received_at, is_sample=True
        )
        models.ServiceRequestEvent.objects.filter(request_id=request.id).update(at=received_at)
        written += 1
        written += _drive_cr030_request(actor, sr, request.id, entry, received_at)
    return written


def _reconcile_cr030_services(
    actor: Any, sr: Any, request: Any, entry: dict[str, Any]
) -> int:
    """Give an ALREADY-SEEDED sample request its services, if it has none.

    The replay half of `DEF-CUS-5423`. Every tenant seeded before 2026-09-16
    holds eight sample requests with an empty services panel, and the block
    above is idempotent per REQUEST — so without this, pressing *Load sample
    data* again would walk straight past them and the demo the Product Owner
    reviews screens on would never show the thing they asked for.

    ⚠ **IT REFUSES TO REPLACE.** `set_services` replaces the whole set, so a
    request that already carries services is left exactly as it is — a date
    somebody typed while demonstrating the screen is an answer, and a seed that
    overwrote it would be a fixture undoing a person. The only state this acts
    on is *no rows at all*.

    ⚠ **THE DATES ARE ANCHORED TO THE ROW'S OWN `received_at`**, not to today,
    so a request seeded a fortnight ago keeps the offsets the fixture declares
    relative to the day it came in and the Requests tab's ages stay true.
    """
    declared = entry.get("services") or ()
    if not declared:
        return 0
    if models.ServiceRequestService.objects.filter(request_id=request.id).exists():
        return 0
    payload = _cr030_services_for(entry, request.received_at)
    if not payload:
        return 0
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            sr.set_services(actor, request.id, payload)
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "sample data (CR-030 W4): %s kept no requested services on replay — %s: %s",
            entry["drawn_no"],
            type(exc).__name__,
            exc,
        )
        return 0
    return 1


def _cr030_services_for(entry: dict[str, Any], received_at: datetime) -> list[dict[str, Any]]:
    """The fixture's `services` list, narrowed to what THIS utility sells.

    Answers the payload `set_services` takes — `[{"code", "requested_start"}]`,
    `requested_start` an ISO date or ABSENT.

    ⚠ **ABSENT AND NOT `None`, AND THAT IS `BR-CUS-1070` RATHER THAN A STYLE
    CHOICE.** An unset `requested_start` means *the clerk gave none*; it is not
    the job's `Connection date` under another name and it never falls back to
    it, in either direction. A fixture entry with no `start_days` therefore
    sends no key at all, which is what the endpoint's own bare-code form means.

    ⚠ **THE DATE IS RELATIVE, LIKE `age_days` AND `remind_on_days`.**
    `start_days` counts forward from the day the request came in, so a demo
    planted in March and a demo planted in November both show a connection date
    in the future. An absolute date would have rotted into the past and
    demonstrated the opposite of what these rows are here to show.

    ⚠ **A SERVICE THE TENANT HAS NOT SWITCHED ON IS DROPPED, NOT ENABLED.**
    `set_services` validates against the PLATFORM catalogue — all eleven — so
    nothing would have stopped this seeding sewer onto a utility that sells
    none. Brazos Bend runs electric and water; a sewer-and-trash utility
    loading the same fixture gets its own two and no request asks for something
    the utility cannot deliver. Reading the tenant's own rows rather than
    naming services here is `G47`'s rule (`BR-RAT-024` has moved twice).
    """
    from apps.customers import seams

    declared = entry.get("services") or ()
    if not declared:
        return []
    enabled = set(seams.enabled_service_codes())
    payload: list[dict[str, Any]] = []
    for row in declared:
        code = row["code"]
        if code not in enabled:
            continue
        item: dict[str, Any] = {"code": code}
        if row.get("start_days") is not None:
            item["requested_start"] = (
                received_at.date() + timedelta(days=int(row["start_days"]))
            ).isoformat()
        payload.append(item)
    return payload


def _drive_cr030_request(
    actor: Any,
    sr: Any,
    request_id: Any,
    entry: dict[str, Any],
    received_at: datetime,
) -> int:
    """One request, driven from `draft` to its drawn state through the product.

    Every failure is REPORTED BY NAME and the row is left where it stopped: a
    request stuck at `submitted` because a document could not be verified is a
    true statement about this deployment, and a seeder that swallowed it would
    make the Requests tab look right while the gate it demonstrates was broken.
    """
    written = 0
    if entry.get("account_type"):
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.set_customer_category(actor, request_id, account_type_code=entry["account_type"])
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s kept no customer category — %s: %s",
                entry["drawn_no"],
                type(exc).__name__,
                exc,
            )
    # ── CAPTURE STEP 2 · WHAT THEY WANT, AND WHEN THEY WANT EACH OF IT ──────
    # `BR-CUS-1070` (2026-09-15) · `DEF-CUS-5423`. This call did not exist
    # until 2026-09-16 and the join table therefore held **0 rows on every
    # tenant this product has ever seeded** — against 8 sample requests —
    # so capture step 2 and the request's own services panel had never had
    # anything to show, and nobody reviewing either could tell a working panel
    # from an empty one.
    #
    # ⚠ **HERE, AND NOT LATER: THIS IS STEP 2 AND IT RUNS BEFORE `submit`.**
    # A request whose services arrived after it was submitted would be a fact
    # no clerk could have entered, and the events on its History tab would say
    # so.
    #
    # ⚠ **A MISSING `services` KEY IS NOT A GAP.** `thompson-move-out` has none
    # on purpose — a request that never reached step 2 — so `count` is 0 on one
    # of the eight and the screens have that case in front of them too.
    services_payload = _cr030_services_for(entry, received_at)
    if services_payload:
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.set_services(actor, request_id, services_payload)
                written += 1
        except Exception as exc:  # noqa: BLE001
            # Reported BY NAME and the row left where it stopped, like every
            # other step here: a request with no services because the platform
            # refused one is a true statement about this deployment, and a
            # seeder that swallowed it would make step 2 look right while the
            # rule it demonstrates was broken.
            logger.info(
                "sample data (CR-030 W4): %s kept no requested services — %s: %s",
                entry["drawn_no"],
                type(exc).__name__,
                exc,
            )
    # The Decision tab's `Existing customer` search, and it is not optional: the
    # arrears condition asks *has anybody looked* (`match_confirmed_at` carries
    # it), so an unsearched request can never be approved. `customer_id=None`
    # records **searched, and there is no prior customer** — a real answer, and
    # the one a genuine first-time applicant gets.
    match = entry.get("match") or {}
    if match:
        customer = (
            models.Customer.objects.filter(
                tenant_id=_tenant_id(), external_ref=match["customer_ref"]
            ).first()
            if match.get("customer_ref")
            else None
        )
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.link_customer(
                    actor,
                    request_id,
                    customer_id=(customer.id if customer is not None else None),
                    # BR-CUS-089: only a `strong` match may move money, and the tier
                    # is the CLERK's — there is no automatic matcher in this product.
                    tier=(match.get("tier") if customer is not None else None),
                    basis=match.get("basis"),
                )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s recorded no customer search — %s: %s",
                entry["drawn_no"],
                type(exc).__name__,
                exc,
            )
    # The resolver runs on every request: `resolution_kind` + `lookup_found` are
    # the EVIDENCE the decision panel renders, and a request with none of it
    # draws an empty Location tab (B19 §12.3).
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            sr.resolve_address(actor, request_id)
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "sample data (CR-030 W4): %s could not resolve its address — %s: %s",
            entry["drawn_no"],
            type(exc).__name__,
            exc,
        )
    for document in entry.get("documents") or ():
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                row = sr.attach_document(
                    actor,
                    request_id,
                    doc_type=document["doc_type"],
                    name=document["name"],
                    what_it_proves=document["what_it_proves"],
                    # ⚠ **A REFERENCE TO NO STORED FILE, AND IT IS NAMED AS ONE.**
                    # This product has no document store: `storage_ref` is a string
                    # and nothing serves what it points at, so the detail's `View`
                    # will not open anything. It is written anyway because
                    # `verify_document` REFUSES a document with no file — *"that
                    # would be a clerk certifying nothing"* — and without it no
                    # required document can be verified, so BR-CUS-095's two gates
                    # (attach never blocks creation; verify unblocks approval) could
                    # not be demonstrated at all. The scheme says what it is.
                    storage_ref=f"sample-data://cr030/{entry['key']}/{document['name']}",
                )
                written += 1
                if document.get("verify"):
                    sr.verify_document(actor, row.id)
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s kept no %s document — %s: %s",
                entry["drawn_no"],
                document["doc_type"],
                type(exc).__name__,
                exc,
            )
    for line in entry.get("fees") or ():
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.add_fee_line(
                    actor,
                    request_id,
                    charge_code=line["charge_code"],
                    description=line["description"],
                    basis=line["basis"],
                    unit_amount=Decimal(line["unit_amount"]),
                    quantity=Decimal(line["quantity"]),
                )
                written += 1
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s kept no %s fee line — %s: %s",
                entry["drawn_no"],
                line["charge_code"],
                type(exc).__name__,
                exc,
            )
    collect = entry.get("collect")
    if collect:
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                # ⚠ BR-CUS-090 (2026-09-24, OQ-CUS-12624): the counter takes the
                # WHOLE fee still owing or refuses — a seeded `amount` short of the
                # quote is refused here and logged below, never recorded.
                sr.collect_fee(
                    actor,
                    request_id,
                    amount=Decimal(collect["amount"]),
                    method=collect["method"],
                    receipt_no=collect["receipt_no"],
                )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s recorded no counter collection — %s: %s",
                entry["drawn_no"],
                type(exc).__name__,
                exc,
            )
    state = entry["state"]
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            sr.submit(actor, request_id)
            for action in _CR030_STATE_PATH.get(state, ()):
                sr.transition(
                    actor,
                    request_id,
                    action,
                    reason=(
                        entry.get("park_note")
                        or "sample data — the demo fixture's own walkthrough (BR-TEN-056)"
                    ),
                )
    except Exception as exc:  # noqa: BLE001 — the row stays where it stopped
        logger.info(
            "sample data (CR-030 W4): %s did not reach %r — %s: %s. The row is left in the "
            "state the product allowed it to reach",
            entry["drawn_no"],
            state,
            type(exc).__name__,
            exc,
        )
    # ── THE DECISION AND THE APPROVAL · EACH ITS OWN SAVEPOINT (2026-09-23) ──
    # ⚠ **THEY SAT INSIDE THE BLOCK ABOVE, AND A REFUSED APPROVAL THEN ROLLED
    # THE WHOLE ROW BACK TO `draft`** — `DEF-CUS-5426`'s shape again, one step
    # later. It became reachable on 2026-09-23 (`DEF-CUS-6350`, `DEF-CUS-6420`):
    # Approve now checks the place (a move-in needs its unit in Premises and
    # free; a new connection needs an address NOT in Premises) and waits on an
    # unpaid fee. A drawn `approved` row the rules now refuse must stop where
    # the product stops it — submitted, with its outcome decided so the TYPE
    # column still shows what it is — and say so by name, which is this
    # function's own promise in its docstring.
    if state in ("approved", "in_fulfilment") and entry.get("outcome"):
        decided = False
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.decide_outcome(actor, request_id, outcome=entry["outcome"])
                decided = True
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s recorded no decision — %s: %s",
                entry["drawn_no"],
                type(exc).__name__,
                exc,
            )
        if decided:
            try:
                # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
                with transaction.atomic():
                    sr.approve(actor, request_id, note="sample data — conditions clear")
                # ⚠ **THE `route` CALL THAT STOOD HERE IS GONE (2026-09-19).**
                # `in_fulfilment` is not a state a request can reach any more,
                # so this row stops at `approved` — said out loud rather than
                # left as a silent difference between the fixture and the row.
                if state in _CR030_UNREACHABLE_SINCE_RULING:
                    logger.info(
                        "sample data (CR-030 W4): %s is drawn %r and stops at %r — that state "
                        "was retired by the PO ruling of 2026-09-19 and nothing can reach it",
                        entry["drawn_no"],
                        state,
                        _CR030_UNREACHABLE_SINCE_RULING[state],
                    )
            except Exception as exc:  # noqa: BLE001 — the row stays where it stopped
                logger.info(
                    "sample data (CR-030 W4): %s is drawn %r and Approve refused it — %s: %s. "
                    "The row stays submitted with its outcome decided",
                    entry["drawn_no"],
                    state,
                    type(exc).__name__,
                    exc,
                )
    # ── THE CROSS-WIRING · `DEF-CUS-5426`, ITS OWN STEP AND ITS OWN SAVEPOINT ──
    # ⚠ **IT USED TO SIT INSIDE THE BLOCK ABOVE AND THAT COST `SR-26-0043` ITS
    # WHOLE STATE.** Since `883206ca` (2026-09-15) approval RAISES the job and
    # `request_jobs.raise_job` calls `link_child` itself with the real child's
    # reference — so the fixture's drawn `CON-26-0117` is now a SECOND child,
    # `link_child` refuses it by name (`childAlreadyLinked`, correctly), and
    # because submit, every transition, `decide_outcome`, `approve`, `route` and
    # this call shared ONE transaction, that refusal rolled the whole chain
    # back. Measured on two freshly provisioned tenants on 2026-09-16: the
    # request landed at **`draft`** rather than `In fulfilment`, so the eight-
    # request fixture was one of its six states short on every tenant seeded
    # since. `brazosbend` was planted before that commit and still reads
    # `In fulfilment`, which is why weeks of screen review never saw it.
    #
    # ⚠ **A CHILD THE PRODUCT ALREADY NAMED IS LEFT ALONE, NOT OVERWRITTEN.**
    # The real reference beats the drawing's (B14 rule 37 — a figure drawn in a
    # wireframe is an illustration), and `link_child` owns the uniqueness
    # refusal anyway. The divergence is REPORTED rather than hidden, because
    # the fixture's cross-wiring note asks every lane to preserve it and this
    # is the product superseding it.
    if entry.get("outcome_ref"):
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                already = (
                    models.ServiceRequest.objects.filter(pk=request_id)
                    .values_list("outcome_ref", flat=True)
                    .first()
                )
                if already:
                    logger.info(
                        "sample data (CR-030 W4): %s already names %s — the product raised it "
                        "at approval, so the fixture's %s is NOT linked over it",
                        entry["drawn_no"],
                        already,
                        entry["outcome_ref"],
                    )
                else:
                    sr.link_child(
                        actor,
                        request_id,
                        child_ref=entry["outcome_ref"],
                        child_kind=entry.get("outcome_kind"),
                    )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s was not cross-wired to %s — %s: %s",
                entry["drawn_no"],
                entry["outcome_ref"],
                type(exc).__name__,
                exc,
            )
    # ⚠ **PARK NOW MOVES `submitted` → `under_review` (PO ruling 2026-09-19)**,
    # which is how the two `under_review` fixtures are planted at all — and it
    # is also why a fixture drawn `submitted` WITH a `waiting_on` comes out
    # `under_review`. Both are the ruling, not a seeding bug; the log says so
    # for the second, because a state that moved under a fixture is exactly the
    # kind of difference nobody notices until a demo.
    if entry.get("waiting_on"):
        if state == "submitted":
            logger.info(
                "sample data (CR-030 W4): %s is drawn %r waiting on %r, and parking it now "
                "picks it up — it lands in 'under_review'. The PO ruling of 2026-09-19 leaves "
                "no way to be submitted AND waiting on something",
                entry["drawn_no"],
                state,
                entry["waiting_on"],
            )
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                sr.park(
                    actor,
                    request_id,
                    waiting_on=entry["waiting_on"],
                    note=entry.get("park_note"),
                    remind_on=(
                        (received_at.date() + timedelta(days=int(entry["remind_on_days"])))
                        if entry.get("remind_on_days")
                        else None
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-030 W4): %s was not parked on %r — %s: %s",
                entry["drawn_no"],
                entry["waiting_on"],
                type(exc).__name__,
                exc,
            )
    # ⚠ **THE REQUEST ROW CARRIES `is_sample` AND ITS CHILDREN DO NOT.**
    # `service_requests.is_sample` is tagged by the caller; `service_request_
    # documents`, `_fees` and `_events` have no such column, so BR-TEN-057's
    # *"the tag is a column on the owning row"* cannot be honoured for them.
    # Stated rather than worked around: `--remove` will not sweep a demo
    # request's documents or fee lines, and adding those columns is a migration
    # on the CR-031 tables that belongs to the lane that owns them.
    return written


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W3 · TASK 3.12 — `A-10432`'s NOTES (B18 §5.2.2 · §5.2.4)
# ══════════════════════════════════════════════════════════════════════════
#
# THREE notes, through `add_note` — the S21 tab's own call. §5.2.2 records that
# the tab is *"built as a table; the screenshot draws cards"*, which is a
# CONFORMANCE drift (task 3.10) and not a data one: the rows below are what
# either rendering reads.
#
# ⚠ **THE OTHER EIGHT TABS' DATA IS NOT ALL SEEDABLE TODAY, and each absence is
# named rather than left to be found:**
#   · **Bills / Payments** — the demo's bills are issued by the REAL engine over
#     the sample billing cycle, and this estate deliberately joins no route (see
#     `apps/metering/sample_data._seed_cr030_estate`), so `A-10432` has none.
#     Writing six `invoices` rows from a fixture would be append-only rows
#     (hard rule 4) that no bill run produced.
#   · **Documents** — there is NO account-document table in this product
#     (`service_request_documents` is the request's). B18 §5.2.2 marks the whole
#     tab ❌ and task 3.7 owns it.
#   · **Adjustments** — `adjustments` is BILLING's table (B2), so customers may
#     not write it (B1). `core/sample_fixture.CR030_A10432_ADJUSTMENTS` declares
#     the three the design draws, for billing's own seeder to plant.
#   · **Usage / Meters** — assets seeds the two meters and metering seeds their
#     reads and the BR-MET-106 monthly usage those reads imply.
#   · **Audit** — fills from THIS seeding: every service call above writes its
#     own `audit_log` row (rule 7). The `portal actor` row §5.2.2 draws is not
#     seeded, because the identity model has no portal actor and inventing one
#     would be a fabricated actor on an audit trail.


def _seed_cr030_demo_notes(actor: Any) -> int:
    """`A-10432`'s three notes (§5.2.4). Idempotent on the subject."""
    tenant_id = _tenant_id()
    account = models.Account.objects.filter(
        tenant_id=tenant_id, account_no=fixture.CR030_DEMO_ACCOUNT_NO
    ).first()
    if account is None:
        return 0
    written = 0
    for note in fixture.CR030_A10432_NOTES:
        if models.AccountNote.objects.filter(
            tenant_id=tenant_id, account=account, title=note["title"]
        ).exists():
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                services.create_account_note(
                    actor, str(account.id), {"title": note["title"], "body": note["body"]}
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-030 W3): %s kept no note %r — %s: %s",
                fixture.CR030_DEMO_ACCOUNT_NO,
                note["title"],
                type(exc).__name__,
                exc,
            )
            continue
        written += 1
    # ⚠ **`account_notes` CARRIES NO `is_sample` COLUMN, so these three rows are
    # NOT TAGGED** — and that is BR-TEN-057 working rather than a gap papered
    # over: *"the tag is a column on the owning row"*, and this owning row has
    # none. The consequence is stated rather than hidden: `--remove` cannot
    # sweep the demo's notes, because nothing marks them as the demo's. Adding
    # the column is a migration on customers' own table and belongs to the lane
    # that owns the Notes tab (task 3.10), not to a seeder.
    return written


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W5 · TASK 5.11 — THE FIVE MOVE-INS AND THE SIX MOVE-OUTS
# ══════════════════════════════════════════════════════════════════════════
#
# B18 §5.5.7 (*"Seed data — the five `[shot]` rows"*) and §5.6.7 (*"Seed data —
# the six `[shot]` rows"*), declared here as rows a reader can go and count.
#
# ⚠ **FOUR MEASURED FACTS DECIDE WHAT THIS BLOCK CAN AND CANNOT PLANT, AND ALL
# FOUR ARE STATED BEFORE THE DATA RATHER THAN DISCOVERED AFTER IT.** Each was
# measured on this tree on 2026-08-25; each is a REPORT for the lane that owns
# the missing half, never a thing this seeder works around.
#
#   1. **THERE IS NO `move_ins` TABLE AND NO `move_outs` TABLE.** `apps/
#      customers/models.py` carries `accounts` · `contacts` · `addresses` ·
#      `customers` · `customer_accounts` · `account_opening_buckets` ·
#      `account_import_batches`/`_rows` · `service_agreements` ·
#      `account_notes` · the eight `service_request*` tables — and nothing
#      else; no migration under `apps/customers/migrations/` names either. A
#      move-in or move-out IN PROGRESS is therefore not a row anywhere: it is a
#      wizard the clerk has open. **So `STEP · 3 of 6` cannot be seeded**, and
#      neither can `WAITING ON`, which task 5.1 built on `service_requests`
#      alone (`MoveInWizard.tsx`'s own exception E4 says the same in the other
#      territory: *"`waiting_on`/`park_note`/`parked_at` are columns on
#      `service_requests` alone and a move-in in progress is not a row"*).
#   2. **EVERY SEAT IN THIS FIXTURE IS TAKEN.** `core.sample_fixture` seeds 48
#      base units (`SCW-U-001..048`), one ❄️ GT-16 cutover seat (`SCW-U-101`)
#      and thirteen estate units (`SCW-U-201..213`) — 62 in all. `account_plan()`
#      returns exactly 48 rows and `CR030_ACCOUNT_SHAPES` takes twelve of the
#      thirteen estate seats; the thirteenth (`SCW-U-207 · 3450 Oak Ridge Dr`)
#      carries `leave_vacant: True` and **must stay vacant** — it is what makes
#      `SR-26-0039` resolve `served_vacant`. So **there is no unit for a new
#      move-in or move-out account to occupy**, and premises and units are
#      metering's tables (B1): customers may not create one.
#   3. **`deposit_on_file` IS A REFUSED FIELD ON BOTH DOORS THAT EDIT AN
#      ACCOUNT.** `services.REFUSED_FIELDS` types it *"a LOOKUP from the plan
#      deposit schedule (US-CUS-007)"*, so neither `create_account` nor
#      `update_account` will take it; only `create_from_import` accepts it
#      (`IMPORT_ACCOUNT_FIELDS`), and creating is what needs the seat fact 2
#      says does not exist. **An already-seeded account cannot be given a
#      deposit by any service in this product.** Every drawn settlement below
#      applies ❄️ WE-7's `$150.00 + $3.50 = $153.50`, so this is the fact that
#      keeps the six settlements off the screen.
#   4. **AN ACCOUNT HOLDING A DEPOSIT CANNOT BE SETTLED TODAY ANYWAY.**
#      BR-CUS-057's accrual is unbuilt — `apps.customers.selectors.
#      deposit_interest_accrued` is published by nothing — so
#      `move_out_settlement.settlement_for` states **no landing** and serves
#      `deposit_interest_not_accrued`. That is the honest outcome and it is
#      recorded per row below as `lands_on: GAP`, not tuned away.
#
# ⚠ **TWO ACCOUNT NUMBERS DISAGREE BETWEEN B18 §5.6.7 AND THE ESTATE ALREADY
# SEEDED, AND NEITHER IS THIS LANE'S TO RENUMBER.** §5.6.7 draws `A-11603 ·
# Thompson, R. · 88 Pine Vista` and `A-11024 · Ridge Coffee Co. · 500 Main ·
# 200`; `CR030_ACCOUNT_SHAPES` planted the same customer at the same unit as
# `A-11996` and `A-11801`. `A-11996` is additionally B18 §5.7.6's *own* number
# for `Haddad, Nour`'s new transfer account, so one string names two accounts
# across two sections. The rows below carry BOTH numbers — `drawn_no` and
# `seeded_no` — and resolve on the seeded one, because renumbering a planted
# account would move `Thompson, R.` out from under `SR-26-0046` and
# `Ridge Coffee Co.` out from under `SR-26-0048` and `§5.1.2`'s `4 accounts`
# sub-link. **REPORTED for the fixture owner (`core/sample_fixture.py`), which
# this lane does not own.**
#
# ⚠ **THE STEP DENOMINATOR IS SIX, NOT FOUR (BR-SHL-046, PO 2026-08-24, closing
# DEF-648).** §5.6.2's column header reads `STEP (of 4)` and §5.6.7's cells read
# `4 of 4`, `3 of 4`, `2 of 4`, `1 of 4`; that count is SUPERSEDED. The rows
# below carry `step_of: 6` and keep the drawn numerator, exactly as
# `MoveOutWizard.tsx` does (*"a skipped step keeps its number"*). Seeding `of 4`
# here would put a superseded count into the demo three days after it was ruled.
#
# WHAT THIS BLOCK THEREFORE PLANTS, AND WHY IT IS A NOTE
# ------------------------------------------------------
# For every row that RESOLVES to an account already on file, one `account_notes`
# row through `services.create_account_note` — the S21 Notes tab's own call,
# customers' own table, the same door `_seed_cr030_demo_notes` uses one screen
# down. The note states the drawn move date, the drawn step, the drawn
# settlement sentence and the rule that governs it.
#
# ⚠ **A NOTE IS NOT A MOVE-OUT ROW AND THIS BLOCK DOES NOT PRETEND IT IS.** It
# is the honest shape of a scheduled move-out in a product whose move-out has no
# store: what a clerk would write down. It makes the fixture VISIBLE in the
# running product (hard-won law 2 — a fixture nobody can reach is not a fixture)
# without inventing a state the schema cannot hold, and it never sets
# `closed_at`: closing `A-11340 · Northwind Mfg.` would take it off the Accounts
# tab as `Marked disconnect` and off the Disconnects tab at `TIER 3`, and B18
# §5.6.7's own closing line is that a lane which breaks that three-tab
# consistency has broken the fixture.
#
# For every row that does NOT resolve, nothing is written and the reason is
# logged BY NAME — BR-TEN-066's *"remove what is free, report the rest BY NAME"*,
# applied to seeding. `w5_move_fixture_report()` returns the same dispositions
# as data so a test can read them instead of a log line.
#
# ⚠ **THE HEADLINE FIXTURE IS ONE OF THE UNRESOLVABLE ONES.** Task 5.11's own
# parenthesis is *"the two OQ fixtures"*: `A-11208 · Nakamura, Yuki` (OQ-347 →
# BR-CUS-081, refund $11.20) and `A-11024 · Ridge Coffee Co.` (OQ-346 →
# BR-CUS-082, SHORT $175.20). `A-11024` resolves onto `A-11801`; **`A-11208` has
# no seat at all** — `44 Larkspur Way` is not a seeded premises (`61 Larkspur
# Way` is, and `A-11512 · Hollis, Marcus` holds it). So BR-CUS-081's worked case
# is provable in the test file and **is not plantable in the demo**, and that is
# named here rather than left for somebody to find on the screen.
#
# WHICH LANDINGS THE SIX SPAN — three of five, and the other two are not drawn
# ---------------------------------------------------------------------------
# `move_out_settlement.MONEY_LANDINGS` is a CLOSED set of five. B18 §5.6.7's six
# rows span `refund_due` (two), `settled` (one) and `short` (one); the remaining
# two rows have no final read and so have no landing at all. **`refused_excess`
# and `refused_other_debt` are drawn by NEITHER row**, which is not an omission
# in this seed: J08 step 1a puts `refused_excess` on `F=ACC-1059` and B19
# §15.9.5 puts `refused_other_debt` on a sibling-debt case, and both live in
# the test file where their figures are. ⚠ **`refused_excess` could not be
# seeded even if a row drew it** — J08 step 7b(i), measured 2026-08-24: nothing
# in this repository stores a disputed AMOUNT, and `metering`'s `disputed_at` on
# a METER READ is a quantity in dispute and is deliberately not wired.

#: B18 §5.5.7's five rows, verbatim. `drawn_no` is the number the design prints;
#: `seeded_no` is the account this tree actually holds, or None when the row has
#: no account at all (the two drafts) or no seat (see the block header).
W5_MOVE_INS: tuple[dict[str, Any], ...] = (
    {
        "key": "mvi-baptiste",
        "drawn_no": "A-12039",
        "seeded_no": None,
        "customer": "Baptiste, Marie",
        "address": "2201 Cedar Ln",
        "moves_on": date(2026, 8, 18),
        "step": 5,
        "step_of": 5,
        "reads": "taken",
        "deposit": "waived",
        "state": "Done",
        "request_ref": None,
        # `2201 Cedar Ln` is not a seeded premises. B19 §12.1 draws `2201 Cedar
        # Ave` inside SR-26-0047's *address as given* string and that is a
        # TRANSFER's free text, not a premises row.
        "blocker": "no_seat",
    },
    {
        "key": "mvi-reyes",
        "drawn_no": "A-12041",
        "seeded_no": None,
        "customer": "Reyes, Antonio",
        "address": "12 Harbour View",
        "moves_on": date(2026, 8, 20),
        "step": 5,
        "step_of": 5,
        "reads": "taken",
        "deposit": "on first bill",
        "state": "Done",
        "request_ref": None,
        "blocker": "no_seat",
    },
    {
        # DRAFT 1 of 2 — the park-and-resume proof (B18 §5.5.7's own closing
        # paragraph). A draft has no account number BY CONSTRUCTION, and this
        # product has no wizard store, so `SR-26-0044` IS the draft.
        "key": "mvi-alvarez",
        "drawn_no": None,
        "seeded_no": None,
        "customer": "Alvarez, Rosa",
        "address": "3450 Oak Ridge Dr",
        "moves_on": date(2026, 8, 26),
        "step": 2,
        "step_of": 5,
        "reads": None,
        "deposit": "carried $153.50",
        "state": "In progress",
        "request_ref": "SR-26-0044",
        "blocker": "draft_has_no_account",
    },
    {
        "key": "mvi-kwan",
        "drawn_no": "A-12048",
        "seeded_no": "A-12048",
        "customer": "Kwan, Michael",
        "address": "88 Pine Vista",
        "moves_on": date(2026, 9, 1),
        "step": 3,
        "step_of": 5,
        "reads": "due",
        "deposit": "collected $150.00",
        "state": "Scheduled",
        "request_ref": "SR-26-0045",
        "blocker": None,
    },
    {
        # DRAFT 2 of 2. §5.5.7: *"`Osei, Grace` [links] to `SR-26-0039` (`More
        # info needed`, waiting on documents — which is exactly why her move-in
        # is `Waiting` at step 1)."*
        "key": "mvi-osei",
        "drawn_no": None,
        "seeded_no": None,
        "customer": "Osei, Grace",
        "address": "500 Main · 210",
        "moves_on": date(2026, 9, 8),
        "step": 1,
        "step_of": 5,
        "reads": None,
        "deposit": None,
        "state": "Waiting",
        "request_ref": "SR-26-0039",
        "blocker": "draft_has_no_account",
    },
)

#: B18 §5.6.7's six rows. `step_of` is **6** and not the drawn 4 — BR-SHL-046,
#: see the block header. `landing` is `move_out_settlement`'s own vocabulary so
#: the fixture and the engine cannot drift into two spellings of one settlement;
#: `outstanding`/`applied` are the figures the drawn sentence is made of, as
#: STRINGS (money is never a float — CLAUDE.md rule 2).
W5_MOVE_OUTS: tuple[dict[str, Any], ...] = (
    {
        "key": "mvo-fitzgerald",
        "drawn_no": "A-10992",
        "seeded_no": None,
        "customer": "Fitzgerald, Sean",
        "address": "17 Brambling Ct",
        "moves_on": date(2026, 8, 20),
        "step": 4,
        "step_of": 6,
        "final_read": "taken",
        "settlement": "refunded $88.40",
        "landing": "refund_due",
        "outstanding": "65.10",
        "applied": "153.50",
        "refund": "88.40",
        "shortfall": None,
        "state": "Done",
        "br_ref": "BR-CUS-081",
        "request_ref": None,
        "blocker": "no_seat",
    },
    {
        # ⚠ OQ FIXTURE 1 of 2 — OQ-347 CLOSED → BR-CUS-081 (PO 2026-08-24,
        # verbatim *"a) settle and refund the $11.20"*). `153.50 − 142.30 =
        # 11.20`; the account closes at zero and the bill does NOT stand.
        "key": "mvo-nakamura",
        "drawn_no": "A-11208",
        "seeded_no": None,
        "customer": "Nakamura, Yuki",
        "address": "44 Larkspur Way",
        "moves_on": date(2026, 8, 24),
        "step": 3,
        "step_of": 6,
        "final_read": "taken",
        "settlement": "refund $11.20",
        "landing": "refund_due",
        "outstanding": "142.30",
        "applied": "153.50",
        "refund": "11.20",
        "shortfall": None,
        "state": "Waiting",
        "br_ref": "BR-CUS-081",
        "request_ref": None,
        "blocker": "no_seat",
    },
    {
        "key": "mvo-thompson",
        "drawn_no": "A-11603",
        "seeded_no": "A-11996",  # see the block header's renumbering note
        "customer": "Thompson, R.",
        "address": "88 Pine Vista",
        "moves_on": date(2026, 8, 31),
        "step": 2,
        "step_of": 6,
        "final_read": "due",
        "settlement": "settles exactly",
        "landing": "settled",
        "outstanding": "153.50",
        "applied": "153.50",
        "refund": None,
        "shortfall": None,
        "state": "Scheduled",
        "br_ref": "BR-CUS-025",
        "request_ref": "SR-26-0046",
        "blocker": None,
    },
    {
        # ⚠ OQ FIXTURE 2 of 2 — OQ-346 CLOSED → BR-CUS-082 (PO 2026-08-24,
        # verbatim *"(b) continue, ladder restarts"*). `328.70 − 153.50 =
        # 175.20`, still chased after the close, ladder restarts at TIER 1, and
        # a closed account is never escalated to disconnection.
        "key": "mvo-ridge-coffee",
        "drawn_no": "A-11024",
        "seeded_no": "A-11801",  # see the block header's renumbering note
        "customer": "Ridge Coffee Co.",
        "address": "500 Main · 200",
        "moves_on": date(2026, 9, 5),
        "step": 3,
        "step_of": 6,
        "final_read": "taken",
        "settlement": "SHORT $175.20",
        "landing": "short",
        "outstanding": "328.70",
        "applied": "153.50",
        "refund": None,
        "shortfall": "175.20",
        "state": "In progress",
        "br_ref": "BR-CUS-082",
        "request_ref": "SR-26-0048",
        "blocker": None,
    },
    {
        "key": "mvo-delgado",
        "drawn_no": "A-11780",
        "seeded_no": "A-11780",
        "customer": "Delgado, Pilar",
        "address": "220 Sable Court",
        "moves_on": date(2026, 9, 9),
        "step": 2,
        "step_of": 6,
        # ⚠ `estimated` HAS NO HOME ON A SETTLEMENT. `move_out_settlement`
        # takes the final bill as a STATED figure and carries no flag for how
        # its reads were obtained, so §5.6.2's amber `estimated` and its
        # *"the settlement is provisional"* consequence cannot be seeded or
        # served. TC-MVO-7 asserts the absence.
        "final_read": "estimated",
        "settlement": None,
        "landing": None,
        "outstanding": None,
        "applied": None,
        "refund": None,
        "shortfall": None,
        "state": "In progress",
        "br_ref": "BR-MET-044",
        "request_ref": None,
        "blocker": None,
    },
    {
        "key": "mvo-northwind",
        "drawn_no": "A-11340",
        "seeded_no": "A-11340",
        "customer": "Northwind Mfg.",
        "address": "77 Industrial Way",
        "moves_on": date(2026, 9, 12),
        "step": 1,
        "step_of": 6,
        "final_read": None,
        "settlement": None,
        "landing": None,
        "outstanding": None,
        "applied": None,
        "refund": None,
        "shortfall": None,
        "state": "Scheduled",
        # §5.6.7's own closing line: this row is `Marked disconnect` on the
        # Accounts tab and `TIER 3` owing $8,240.00 on the Disconnects tab.
        # ONE account, THREE tabs — so this seeder must not close it.
        "br_ref": "BR-CUS-030",
        "request_ref": None,
        "blocker": None,
    },
)

#: Why a drawn row is not on the screen. One string per cause, so the report and
#: the log line cannot drift apart and a test can assert the cause rather than
#: grep a sentence.
W5_BLOCKERS: dict[str, str] = {
    "no_seat": "the drawn address is not a seeded premises, so there is no unit for the "
    "account to occupy (BR-CUS-047 — an account never creates one). `premises` and `units` "
    "are metering's tables (B1) and `core.sample_fixture.CR030_PREMISES` is where the seat "
    "would be declared; neither is this module's to write.",
    "draft_has_no_account": "a parked move-in draft has no account number by construction "
    "(BR-SHL-048 (a): a draft carries no foreign key to the record it names), so there is no "
    "account row for this block to annotate. \u26a0 AMENDED 2026-08-26 (CR-035): this string "
    "used to end \u2018and this product has no wizard store \u2014 `waiting_on`/`park_note`/"
    "`parked_at` are columns on `service_requests` alone\u2019. **THAT IS NO LONGER TRUE** \u2014 "
    "`wizard_parks` shipped in 2.51.0 and `seed_sample_wizard_parks` below plants exactly this "
    "drawn draft into it. What is still true is the half this key is FOR: a draft is not an "
    "account, so the note this block writes has nowhere to go. The linked request remains the "
    "row a clerk can open today.",
    "no_account_row": "the seat exists but no account was found under either the drawn or "
    "the seeded number, so there is nothing to annotate.",
}

#: What a settlement fixture cannot produce today, per row that wants one.
W5_SETTLEMENT_GAP = (
    "BR-CUS-057's deposit-interest accrual is NOT BUILT (`apps.customers.selectors."
    "deposit_interest_accrued` is published by nothing), so an account holding a deposit "
    "states NO LANDING and serves `deposit_interest_not_accrued`. ❄️ WE-7's $150.00 + $3.50 "
    "= $153.50 is the figure every drawn settlement applies, so every one of them GAPS. "
    "And `deposit_on_file` is a REFUSED field on `create_account` and `update_account` "
    "(services.REFUSED_FIELDS, BR-CUS-023), so a seeded account cannot be given one at all."
)


def _w5_note(row: dict[str, Any], kind: str) -> dict[str, str]:
    """One drawn row as the note a clerk would leave — never as a state."""
    title = f"W5 fixture · {kind} {row['moves_on'].isoformat()} · step {row['step']} of {row['step_of']}"
    lines = [
        f"{kind} drawn by B18 §{'5.5.7' if kind == 'Move-in' else '5.6.7'}: "
        f"{row['customer']} · {row['address']} · {row['state']}.",
        f"Drawn as {row['drawn_no'] or 'a draft with no account number'}"
        + (
            f"; seeded on this tree as {row['seeded_no']}."
            if row.get("seeded_no") and row["seeded_no"] != row["drawn_no"]
            else "."
        ),
    ]
    if kind == "Move-out":
        lines.append(
            f"Step count is {row['step_of']}, not the 4 §5.6.2 prints — BR-SHL-046 "
            "(PO 2026-08-24, closing DEF-648). A skipped step keeps its number."
        )
        if row.get("settlement"):
            lines.append(
                f"Drawn settlement: {row['settlement']} — landing `{row['landing']}` "
                f"({row['br_ref']}), everything outstanding {row['outstanding']} against "
                f"{row['applied']} applied."
            )
            lines.append(f"NOT COMPUTED HERE, and it cannot be: {W5_SETTLEMENT_GAP}")
        else:
            lines.append(
                f"No settlement is drawn: the final read is "
                f"{row['final_read'] or 'not taken'} and nothing settles without one."
            )
    else:
        lines.append(f"Reads {row['reads'] or '—'} · deposit {row['deposit'] or '—'}.")
    if row.get("request_ref"):
        lines.append(f"Linked service request: {row['request_ref']}.")
    lines.append(
        "This is a NOTE, not a move-out row: this product has no case row for a move in "
        "flight, so the wizard's step and state have nowhere else to live."
    )
    return {"title": title, "body": " ".join(lines)}


def w5_move_fixture_report() -> list[dict[str, Any]]:
    """Every drawn row and its disposition on THIS tree — data, not a log line.

    Returned rather than printed so `tests/test_w5_move_in_out_cases.py` can
    assert the dispositions. A blocker here is a REPORT for the lane that owns
    the missing half; nothing in this module works around one.
    """
    tenant_id = _tenant_id()
    out: list[dict[str, Any]] = []
    for kind, rows in (("Move-in", W5_MOVE_INS), ("Move-out", W5_MOVE_OUTS)):
        for row in rows:
            account_no = row.get("seeded_no")
            found = (
                models.Account.objects.filter(tenant_id=tenant_id, account_no=account_no).first()
                if account_no
                else None
            )
            blocker = row.get("blocker")
            if account_no and found is None and blocker is None:
                blocker = "no_account_row"
            out.append(
                {
                    "kind": kind,
                    "key": row["key"],
                    "drawn_no": row["drawn_no"],
                    "seeded_no": account_no,
                    "customer": row["customer"],
                    "address": row["address"],
                    "planted": found is not None,
                    "account_id": str(found.id) if found is not None else None,
                    "blocker": blocker,
                    "blocker_detail": W5_BLOCKERS.get(blocker) if blocker else None,
                    "landing": row.get("landing"),
                    "lands_on": ("GAP" if row.get("landing") else None),
                    "lands_on_detail": W5_SETTLEMENT_GAP if row.get("landing") else None,
                    "request_ref": row.get("request_ref"),
                    "step": row["step"],
                    "step_of": row["step_of"],
                }
            )
    return out


def _seed_w5_move_fixtures(actor: Any) -> int:
    """Task 5.11 — the five move-ins and six move-outs, as far as this tree goes.

    Idempotent (BR-TEN-063 · CLAUDE.md rule 6): the note is skipped when its
    title is already on the account, so a replay writes nothing and returns 0.
    """
    written = 0
    tenant_id = _tenant_id()
    for entry in w5_move_fixture_report():
        if not entry["planted"]:
            logger.info(
                "sample data (CR-030 W5 task 5.11): %s %s (%s · %s) is NOT on the screen — %s",
                entry["kind"],
                entry["drawn_no"] or "draft",
                entry["customer"],
                entry["address"],
                entry["blocker_detail"] or "no reason recorded, which is itself a defect",
            )
            continue
        rows = W5_MOVE_INS if entry["kind"] == "Move-in" else W5_MOVE_OUTS
        row = next(candidate for candidate in rows if candidate["key"] == entry["key"])
        note = _w5_note(row, entry["kind"])
        if models.AccountNote.objects.filter(
            tenant_id=tenant_id, account_id=entry["account_id"], title=note["title"]
        ).exists():
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                services.create_account_note(actor, entry["account_id"], note)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-030 W5 task 5.11): %s kept no fixture note — %s: %s",
                entry["seeded_no"],
                type(exc).__name__,
                exc,
            )
            continue
        written += 1
        if entry["lands_on"] == "GAP":
            logger.info(
                "sample data (CR-030 W5 task 5.11): %s's drawn settlement lands on a GAP, "
                "not a number — %s",
                entry["seeded_no"],
                entry["lands_on_detail"],
            )
    # ⚠ `account_notes` CARRIES NO `is_sample` COLUMN — the same statement
    # `_seed_cr030_demo_notes` makes one screen down, and for the same reason
    # (BR-TEN-057: the tag is a column on the OWNING row, and this row has
    # none). So `--remove` cannot sweep the notes this plants — FIVE of the
    # eleven declared rows, one per row that resolves. Adding the column is
    # a migration on customers' own table and belongs to the Notes-tab lane.
    return written


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W7 · TASK 7.12 — B18 §5.7.6's FIVE TRANSFERS AND §5.8.6's NINE
# DISCONNECTS (all tiers, all three built protections)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE SEATS ARE METERING'S AND ARE DECLARED THERE.** `premises` and `units`
# are metering's tables (B2 r4) and customers may not create one — the same
# fact that blocked W2 task 2.10 for a day. `apps/metering/sample_data.W7_SEATS`
# plants the eleven this block stands on, each with a rate plan and its service
# points, because every one of them takes an ACCOUNT (BR-CUS-014 / BR-MET-040:
# an active account on a planless unit is refused, correctly).
#
# ⚠ **THE DATES ARE OFFSETS FROM THE TENANT'S OWN TODAY**, decided at seed time
# and then persisted — `metering.sample_data.w6_anchor_on()`, DEF-629's ruling
# applied to this fixture. B18's drawn dates ride beside them as `drawn_*`. The
# reason is the same one that block gives: three of the five KPI tiles here are
# time-windowed (`MOVING THIS WEEK`, `DUE TO CUT THIS WEEK`, `COMPLETED THIS
# MONTH`), so a literal `2026-08-26` would make the drawn figures true for one
# day and wrong afterwards.
#
# ════════════════════════════════════════════════════════════════════════════
# WHAT THE ROWS HAVE TO REPRODUCE — the acceptance test, stated before the data
# ════════════════════════════════════════════════════════════════════════════
# `transfer_reads.kpi_strip` and `disconnect_reads.kpi_strip` already compute
# B18 §5.7.1's and §5.8.1's tiles, and each module's docstring pins its figures
# to these very rows. What this seed can and cannot make foot:
#
#   TRANSFERS  OPEN 2 ✔ · MOVING THIS WEEK 1 ✔ · DEPOSITS CARRYING 1 ✖ (see
#              `W7_ABSENCES["park_holds_no_deposit"]`) · ARREARS FOLLOWING 1 ✔ ·
#              COMPLETED THIS MONTH 3 ✔
#   DISCONNECTS AT NOTICE 4 ✔ · DUE TO CUT THIS WEEK 2 ✔ · ON HOLD 3 ✔ ·
#              CUT, AWAITING PAYMENT 1 ✖ · RECONNECTIONS DUE 1 ✖ (see
#              `W7_ABSENCES["no_writer_for_cut_or_reconnecting"]` — the two
#              states have NO writer anywhere in this product)
#
# Every ✖ is a stated absence with the measurement behind it, never a figure
# tuned to make a tile look right.
#
# ════════════════════════════════════════════════════════════════════════════
# TWO DRAWN NUMBERS ARE ALREADY TAKEN, AND NEITHER IS RENUMBERED HERE
# ════════════════════════════════════════════════════════════════════════════
# B18 §13 observation 4 records one of these itself — *"`A-11780` is
# `Delgado, Pilar` on Move-outs and `Whitfield, Dana` on Disconnects — the same
# account number, two customers. A fixture slip; **the seed must pick one**"* —
# and this block picks the one already on file. The second is worse and B18
# does not record it:
#
#   · **`A-11780`** — seeded as `Delgado, Pilar` with **$318.60**, which is
#     §5.8.6's own TIER 1 figure. Same account, same money, different name.
#     The ladder is put on the SEEDED row and the drawn name rides as
#     `drawn_customer`.
#   · **`A-11720`** — §5.8.6 draws `Calloway, Brett · $1,204.50 · TIER 3`, and
#     the estate holds that number as `Ridge Property LLC`, the `+3` chip
#     overflow account, **whose EMPTY balance is load-bearing**: its own fixture
#     comment says an opening balance there would block `SR-26-0043`'s approval
#     and *"the Requests tab would draw a state the estate contradicts"*. So
#     Calloway CANNOT go on `A-11720` and cannot be dropped either — without the
#     row, `AT NOTICE` reads 3 and `DUE TO CUT THIS WEEK` reads 1. The fixture
#     therefore NAMES a number for it, `A-11721`, exactly as
#     `core.sample_fixture.CR030_PREMISES` names `61 Larkspur Way` (*"THE ONE
#     ROW B18 DRAWS AS A SHAPE AND NEVER NAMES … The fixture names it — and says
#     so here"*). Both numbers ride the row. **REPORTED for the fixture owner.**
#   · **`A-11655 · Sandoval, Rita · HELD · PAYMENT PLAN`** is NOT given a new
#     account at all, and that is the most important resolution in this block. A
#     `payment_plan` protection has **no expiry of its own**: BR-CUS-043 holds
#     it *while the plan is active AND current*, and `disconnects.
#     _plan_protection_is_live` asks payments every time. On an account with no
#     plan the protection is stored and **is not in force**, so the row would
#     appear on the tab with no chip and `ON HOLD — PROTECTED` would read 2. The
#     fixture already seeds exactly ONE live, mid-schedule payment plan
#     (`seed_sample_payment_plans`, CR-010 Part-10.4 amendment 3), so the
#     protection goes THERE — on the account that really is protected, for the
#     reason the product really computes.

#: The four `[shot]` accounts this block creates, and the seat each stands on.
#: `bucket` ages the opening balance so `seams.ar_positions` — which is what
#: `disconnects._balance_for` reads, never `accounts.balance` — answers the
#: drawn figure. Money is a STRING, never a float (CLAUDE.md rule 2).
W7_ACCOUNTS: tuple[dict[str, Any], ...] = (
    # ── B18 §5.7.6's three completed transfers: the accounts they move FROM ──
    {
        "key": "trf-iversen",
        "account_no": "A-10650",
        "unit_no": "SCW-U-350",
        "customer_name": "Iversen, Britt",
        "customer_ref": "CUS-10650",
        "account_type": "residential",
        "status": "active",
        "buckets": None,
        "deposit_on_file": "150.00",
        "deposit_offset": -400,
    },
    {
        "key": "trf-haddad",
        "account_no": "A-10714",
        "unit_no": "SCW-U-352",
        "customer_name": "Haddad, Nour",
        "customer_ref": "CUS-10714",
        "account_type": "residential",
        "status": "active",
        "buckets": None,
        "deposit_on_file": "150.00",
        "deposit_offset": -300,
    },
    {
        "key": "trf-bianchi",
        "account_no": "A-10877",
        "unit_no": "SCW-U-354",
        "customer_name": "Bianchi, Marco",
        "customer_ref": "CUS-10877",
        "account_type": "residential",
        "status": "active",
        "buckets": None,
        "deposit_on_file": "150.00",
        "deposit_offset": -250,
    },
    {
        # §5.7.6 row 5 — the SCHEDULED transfer, still at step 1. Its seat is
        # `12 Harbour View · Unit 2`; unit 1 is `CON-26-0124`'s build, which
        # ends vacant with no account (see `W6_SEATS`' own note).
        "key": "trf-osei",
        "account_no": "A-11109",
        "unit_no": "SCW-U-306",
        "customer_name": "Osei, Grace",
        "customer_ref": "CUS-11109",
        "account_type": "residential",
        "status": "active",
        "buckets": None,
    },
    # ── B18 §5.8.6's four plantable ladder rows ─────────────────────────────
    {
        "key": "dsc-calloway",
        "drawn_no": "A-11720",
        "account_no": "A-11721",  # FIXTURE-NAMED — see the block header
        "unit_no": "SCW-U-357",
        "customer_name": "Calloway, Brett",
        "customer_ref": "CUS-11721",
        "account_type": "residential",
        "status": "active",
        "buckets": {fixture.CR030_90_PLUS: "1204.50"},
    },
    {
        "key": "dsc-bramble",
        "account_no": "A-11812",
        "unit_no": "SCW-U-358",
        "customer_name": "Bramble Bakery",
        "customer_ref": "CUS-11812",
        "customer_kind": "company",
        "account_type": "commercial",
        "status": "active",
        "buckets": {fixture.CR030_61_90: "2410.00"},
    },
    {
        "key": "dsc-okafor",
        "account_no": "A-11902",
        "unit_no": "SCW-U-359",
        "customer_name": "Okafor, Emmanuel",
        "customer_ref": "CUS-11902",
        "account_type": "residential",
        "status": "active",
        "buckets": {fixture.CR030_31_60: "948.20"},
    },
    {
        "key": "dsc-iqbal",
        "account_no": "A-11933",
        "unit_no": "SCW-U-361",
        "customer_name": "Iqbal, Nadia",
        "customer_ref": "CUS-11933",
        "account_type": "residential",
        "status": "active",
        "buckets": {fixture.CR030_31_60: "402.15"},
    },
)

#: The ledger batch these opening receivables are keyed to. ⚠ **NOT the estate's
#: `CR030_OPENING_BATCH_KEY` and emphatically not ❄️ GT-16's `RUN-2814`** — one
#: batch, one set of opening entries, so a replay or a repair of the W7 rows can
#: never reach either of those.
W7_OPENING_BATCH_KEY = "cr030-w7-disconnects"

#: B18 §5.7.6's five rows. `out_offset`/`in_offset` are days from the anchor;
#: `drawn_out`/`drawn_in` are the dates the design prints.
#: `to_unit_no` is the seat the new account opens at, `None` when the job has
#: not reached step 2.
W7_TRANSFERS: tuple[dict[str, Any], ...] = (
    {
        "key": "trf-iversen",
        "from_no": "A-10650",
        "drawn_to_no": "A-11940",
        "customer": "Iversen, Britt",
        "addresses": "18 Marten Row → 204 Quarry Lane",
        "to_unit_no": "SCW-U-351",
        "drawn_out": date(2026, 8, 2),
        "drawn_in": date(2026, 8, 2),
        "out_offset": -22,
        "in_offset": -22,
        "drawn_step": 5,
        "drawn_money": "deposit carried $153.50",
        "drawn_state": "Done",
        "commit": True,
    },
    {
        "key": "trf-haddad",
        "from_no": "A-10714",
        # ⚠ §5.7.6 gives Haddad's NEW account the number `A-11996`, which the
        # estate already holds for `Thompson, R.` (W5 reported the same clash
        # from the other side). It makes no difference here: a transfer's new
        # account number is ALLOCATED by `create_account` at commit and is not a
        # value any caller may pin, so the drawn number rides as a note.
        "drawn_to_no": "A-11996",
        "customer": "Haddad, Nour",
        "addresses": "3 Kestrel Close → 71 Alder Street",
        "to_unit_no": "SCW-U-353",
        "drawn_out": date(2026, 8, 5),
        "drawn_in": date(2026, 8, 6),
        "out_offset": -19,
        "in_offset": -18,
        "drawn_step": 5,
        "drawn_money": "deposit carried $150.00",
        "drawn_state": "Done",
        "commit": True,
    },
    {
        "key": "trf-bianchi",
        "from_no": "A-10877",
        "drawn_to_no": "A-12031",
        "customer": "Bianchi, Marco",
        "addresses": "44 Larkspur Way → 88 Foundry Row",
        "to_unit_no": "SCW-U-355",
        "drawn_out": date(2026, 8, 9),
        "drawn_in": date(2026, 8, 12),
        "out_offset": -15,
        "in_offset": -12,
        "drawn_step": 5,
        "drawn_money": "deposit carried $150.00",
        "drawn_state": "Done",
        "commit": True,
    },
    {
        # THE HEADLINE ROW. §5.7.6: *"`Park, Jenna` links to `SR-26-0047` and is
        # the same $542.10 balance the Accounts tab shows at `60+ past` — one
        # customer, two tabs, one figure."* So this transfer starts from the
        # ESTATE's own `A-11455`, never from an account of this block's making.
        "key": "trf-park",
        "from_no": "A-11455",
        "drawn_to_no": None,
        "customer": "Park, Jenna",
        "addresses": "901 Hillside Ave → 26 Meadowbank Rise",
        "to_unit_no": "SCW-U-356",
        "drawn_out": date(2026, 8, 28),
        "drawn_in": date(2026, 9, 3),
        "out_offset": 4,
        "in_offset": 10,
        # ⚠ **DRAWN `3 of 5`, SEEDED `4 of 5`, AND THE TWO CANNOT BOTH BE TRUE.**
        # §5.7.1's `DEPOSITS CARRYING` and `ARREARS FOLLOWING` tiles count the
        # clerk's ELECTION (`deposit_carry_elected` / `arrears_follow_elected`)
        # and `transfer_reads`' own docstring pins both of them to THIS row —
        # *"Park = 1 ✔"*. The election is made at **step 4** and
        # `transfers.elect_money` writes `step = max(step, 4)`, so a row
        # standing at step 3 has made no election and both tiles read 0.
        # There is no third option: the STEP cell and the two tiles disagree in
        # the drawing. The election wins, because two KPI tiles depend on it and
        # the step number depends on nothing. **REPORTED.**
        "drawn_step": 3,
        "seeded_step": 4,
        "drawn_money": "deposit carried $154.20 · arrear follows $542.10",
        "drawn_state": "In progress",
        "commit": False,
    },
    {
        "key": "trf-osei",
        "from_no": "A-11109",
        "drawn_to_no": None,
        "customer": "Osei, Grace",
        "addresses": "12 Harbour View → 500 Main · 210",
        # ⚠ **NO TARGET UNIT, AND THAT IS THE DRAWN STEP.** §5.7.6 puts this job
        # at `1 of 5` — *"Find the account and confirm the customer"* — and the
        # target is chosen at step 2. It also prints `Sep 14` in BOTH date
        # cells, and dates are stored at step 3. A step-1 job in this product
        # holds neither, so neither is seeded: `transfers.set_dates` would move
        # the row to step 3 and contradict the drawn cell. **REPORTED.**
        # (The drawn target `500 Main · 210` is `SCW-U-211`, which
        # `Ridge Coffee Co.` occupies — `set_target_unit` would refuse it by
        # name under BR-CUS-017, which is the product working.)
        "to_unit_no": None,
        "drawn_out": date(2026, 9, 14),
        "drawn_in": date(2026, 9, 14),
        "out_offset": 21,
        "in_offset": 21,
        "drawn_step": 1,
        "drawn_money": None,
        "drawn_state": "Scheduled",
        "commit": False,
    },
)

#: B18 §5.8.6's nine rows. `tier` is how far up the ladder the case is walked
#: (`None` = no case, a protection only); `cut_offset` schedules the cut.
W7_DISCONNECTS: tuple[dict[str, Any], ...] = (
    {
        "key": "dsc-greaves",
        "drawn_no": "A-11507",
        "account_no": None,
        "customer": "Greaves, Tom",
        "drawn_owed": "0.00",
        "drawn_tier": None,
        "drawn_cut": date(2026, 8, 12),
        "drawn_state": "Reconnecting",
        "blocker": "no_writer_for_cut_or_reconnecting",
    },
    {
        "key": "dsc-doyle",
        "drawn_no": "A-11488",
        "account_no": None,
        "customer": "Doyle, Patrick",
        "drawn_owed": "612.75",
        "drawn_tier": None,
        "drawn_cut": date(2026, 8, 18),
        "drawn_state": "Cut",
        "blocker": "no_writer_for_cut_or_reconnecting",
    },
    {
        "key": "dsc-northwind",
        "drawn_no": "A-11340",
        "account_no": "A-11340",  # the estate's own row, $8,240.00, 90+
        "customer": "Northwind Mfg.",
        "drawn_owed": "8240.00",
        "drawn_tier": "tier_3",
        "drawn_cut": date(2026, 8, 24),
        "cut_offset": 0,
        "drawn_state": "Scheduled",
        "proof_reference": "7020 3160 0001 4488 2059",
        "served_offset": -2,
        "signed_offset": -1,
    },
    {
        "key": "dsc-calloway",
        "drawn_no": "A-11720",
        "account_no": "A-11721",  # FIXTURE-NAMED — see the block header
        "customer": "Calloway, Brett",
        "drawn_owed": "1204.50",
        "drawn_tier": "tier_3",
        "drawn_cut": date(2026, 8, 26),
        "cut_offset": 2,
        "drawn_state": "Scheduled",
        # §5.8.6 draws this row `certified sent` and the one above `certified
        # signed`, so this proof carries NO signature date. `assert_service_
        # proved` deliberately does not read `signed_for_on` — whether an
        # unclaimed letter stops a cut is unruled and is not decided here.
        "proof_reference": "7020 3160 0001 4488 3107",
        "served_offset": -1,
        "signed_offset": None,
    },
    {
        "key": "dsc-bramble",
        "drawn_no": "A-11812",
        "account_no": "A-11812",
        "customer": "Bramble Bakery",
        "drawn_owed": "2410.00",
        "drawn_tier": "tier_2",
        "drawn_cut": None,
        "drawn_state": "Notice sent",
    },
    {
        "key": "dsc-whitfield",
        "drawn_no": "A-11780",
        "account_no": "A-11780",  # the estate's `Delgado, Pilar`, $318.60
        "drawn_customer": "Whitfield, Dana",
        "customer": "Delgado, Pilar",
        "drawn_owed": "318.60",
        "drawn_tier": "tier_1",
        "drawn_cut": None,
        "drawn_state": "Notice sent",
        "slip": "b18_13_observation_4",
    },
    {
        "key": "dsc-okafor",
        "drawn_no": "A-11902",
        "account_no": "A-11902",
        "customer": "Okafor, Emmanuel",
        "drawn_owed": "948.20",
        "drawn_tier": None,
        "drawn_cut": None,
        "drawn_state": "On hold",
        "protection": "medical_certificate",
        "protection_from_offset": -30,
        "protection_expires_offset": 60,
    },
    {
        "key": "dsc-sandoval",
        "drawn_no": "A-11655",
        # RESOLVED at seed time onto the account that holds the fixture's one
        # LIVE payment plan — see the block header. `None` here means "look it
        # up", not "not plantable".
        "account_no": None,
        "resolve": "live_payment_plan_account",
        "customer": "Sandoval, Rita",
        "drawn_owed": "205.40",
        "drawn_tier": None,
        "drawn_cut": None,
        "drawn_state": "On hold",
        "protection": "payment_plan",
        "protection_from_offset": -20,
        "protection_expires_offset": None,
        # ⚠ Stored, and NOT in force today — see the absence it names.
        "note": "the_live_payment_plan_is_no_longer_current",
    },
    {
        "key": "dsc-iqbal",
        "drawn_no": "A-11933",
        "account_no": "A-11933",
        "customer": "Iqbal, Nadia",
        "drawn_owed": "402.15",
        "drawn_tier": None,
        "drawn_cut": None,
        "drawn_state": "On hold",
        "protection": "weather_moratorium",
        "protection_from_offset": -10,
        "protection_expires_offset": 45,
    },
)

#: What this block could NOT plant, and the measurement behind each. A blocker
#: is a REPORT for the lane that owns the missing half; nothing here is worked
#: around (BR-TEN-066's *"remove what is free, report the rest BY NAME"*,
#: applied to seeding — the `W5_BLOCKERS` posture).
#: `DEF-CUS-9072` — why none of `W7_TRANSFERS` is planted.
W7_TRANSFER_BLOCKER = "transfer_rows_are_moves"

W7_ABSENCES: dict[str, str] = {
    W7_TRANSFER_BLOCKER: (
        "B18 §5.7.6's five transfers each draw a customer MOVING to a new address, closing "
        "one account and opening another. `BR-CUS-1030` (PO 2026-09-01: *\"dont create new "
        "account - we reassing that account - bascailly I have sold my property\"*) made a "
        "transfer a SALE of the same account to a new customer, and `BR-CUS-1031` made a move "
        "a new service request. The rows describe a job the product no longer has, so none "
        "is planted (`DEF-CUS-9072`)."
    ),
    "no_writer_for_cut_or_reconnecting": (
        "B18 §5.8.6 draws `A-11488` as **Cut** and `A-11507` as **Reconnecting**, and "
        "**NOTHING IN THIS PRODUCT WRITES EITHER STATE.** Measured 2026-08-25: "
        "`disconnects.STATE_CUT` and `STATE_RECONNECTING` appear in `CASE_STATES`, in the "
        "migration's check constraint and in `disconnect_reads`' two tiles — and in NO "
        "assignment anywhere. `schedule_cut` sets `STATE_SCHEDULED` and says so in its own "
        "docstring (*'The cut itself — the danger-tier commit, the audit_log row and the base "
        "charges keep accruing statement — is task 7.8 and is NOT in this lane'*); the reconnect "
        "flow is task 7.9 and is unbuilt. So the two rows are NOT planted and "
        "`CUT, AWAITING PAYMENT` and `RECONNECTIONS DUE` seed as **0**, not 1. Writing "
        "`case.state = 'cut'` here would manufacture a state the product cannot produce and "
        "teach the demo a lie; tasks 7.8 and 7.9 own it."
    ),
    "park_holds_no_deposit": (
        "§5.7.6 draws `deposit carried $154.20` on `Park, Jenna`, and `A-11455` HOLDS NO "
        "DEPOSIT. `deposit_on_file` is a REFUSED field on `create_account` and `update_account` "
        "(services.REFUSED_FIELDS, BR-CUS-023) — only `create_from_import` writes one, and "
        "`A-11455` was created through it by `_seed_cr030_account_shapes` from "
        "`core.sample_fixture.CR030_ACCOUNT_SHAPES`, **a file this lane does not own**, whose "
        "row carries no deposit. So `transfers._statement_for` reports no deposit, "
        "`elect_money` defaults `deposit_carry` to False, and §5.7.1's `DEPOSITS CARRYING` "
        "tile reads **0** rather than 1. The election is NOT forced True here: a clerk "
        "recorded as carrying a deposit the account does not hold is a worse fixture than a "
        "tile that is honestly short. **The one-line fix belongs to the fixture owner:** add "
        '`"deposit_on_file": "150.00"` and a receipt date to `CR030_ACCOUNT_SHAPES`\' '
        "`A-11455`."
    ),
    "carried_figure_is_unreadable": (
        "Every drawn `deposit carried` figure needs BR-CUS-057's interest accrual, which is "
        "NOT BUILT (`apps.customers.selectors.deposit_interest_accrued` is published by "
        "nothing). ❄️ WE-7/GT-23 is the frozen worked pair — $150.00 held earns $3.50, so "
        "$153.50 is carried — and the seeded accounts hold the $150.00 PRINCIPAL, which is "
        "the half that is representable. The MONEY cell therefore renders a "
        "`deposit_carried` line with no figure and the absence attached, never `$150.00` and "
        "never `$0.00`: the writer lane measured that the tempting zero *'serves the principal "
        "AS the carried amount and keeps $3.50 of the customer's money'*."
    ),
    "osei_step_1_holds_no_dates": (
        "§5.7.6 puts `Osei, Grace` at `1 of 5` and prints `Sep 14` in both date cells. A "
        "transfer stores its dates at STEP 3 (`transfers.set_dates`, which writes "
        "`step = max(step, 3)`), so a step-1 job in this product holds no dates at all. The "
        "row is seeded at the drawn STEP and the drawn dates ride the report as `drawn_out` / "
        "`drawn_in`. The drawn target — `500 Main · 210`, i.e. `SCW-U-211` — is occupied by "
        "`Ridge Coffee Co.` and `set_target_unit` would refuse it by name (BR-CUS-017), which "
        "is the product working rather than a fixture problem."
    ),
    "last_notice_column": (
        "§5.8.6's `LAST NOTICE` column prints `certified signed` · `certified sent` · `posted` "
        "· `emailed`. Task 7.10 and `disconnects.DELIVERY_UNAVAILABLE`: there is no email, SMS "
        "or print adapter in this release, so `delivery_state` is written NULL on every notice "
        "with its reason beside it. What IS recorded, on the two tier-3 rows, is BR-CUS-100's "
        "PROOF OF SERVICE — a person's attestation with a real certified-mail article number — "
        "because that is a record of something that happened outside this product, not a "
        "delivery claim this product makes."
    ),
    "no_row_names_a_chased_party": (
        "OQ-366 is OPEN — when a sub-account's debt moves to its master, nobody has ruled "
        "whether the ladder chases the departed tenant or the master. No row here is a "
        "post-closure collections sequence and none names a chased party; every case seeded is "
        "an ordinary SERVICE sequence against the account that owes the money."
    ),
    "the_live_payment_plan_is_no_longer_current": (
        "§5.8.6's `HELD · PAYMENT PLAN` row needs a protection that is IN FORCE, and a "
        "`payment_plan` protection has no date of its own: BR-CUS-043 holds it *while the plan "
        "is active AND current* and `disconnects._plan_protection_is_live` asks payments every "
        "time. The fixture's ONE live plan (`core.sample_fixture.PAYMENT_PLAN`) is dated with "
        "LITERAL instalment dues — `Jul 20 · Aug 3 · Aug 17 · Aug 31`, of which two are seeded "
        "PAID — so from **2026-08-18** onwards the Aug 17 instalment is missed, "
        "`collections_pause_for` returns `plan_behind`, and the protection is stored and NOT in "
        "force. **`ON HOLD — PROTECTED` therefore reads 2 where B18 draws 3.** The protection "
        "is still recorded, on the only account in the fixture that has a plan at all, so it "
        "comes into force the moment the plan is current again. ⚠ **THIS IS A FINDING ABOUT "
        "THE EXISTING FIXTURE, NOT ABOUT THIS SEED:** the demo's payment-plan case (S24, spec "
        "§4 case 6) is drifting into arrears as the calendar moves past it — DEF-629's own "
        "failure mode, one fixture over — and the fix is seed-time-relative instalment dates in "
        "`core/sample_fixture.PAYMENT_PLAN` and payments' plan-money seeder, **neither of which "
        "this lane owns.** REPORTED."
    ),
    "a_transfer_does_not_carry_the_sub_type": (
        "⚠ **FOUND BY THIS SEED, AND IT IS A PRODUCT GAP RATHER THAN A FIXTURE ONE.** "
        "`transfers.commit_transfer` opens the incoming account with `account_type`, `status`, "
        "`opened_at` and `preferred_language` — and **not** `account_subtype`. So a "
        "`residential / single_family` customer who transfers across town arrives with NO "
        "sub-type, which is the exact state DEF-257 was raised about; that defect's own guard "
        "(`test_def257_every_sample_account_carries_a_sub_type`) went RED on the three accounts "
        "the committed transfers create, which is how this was noticed. The seeded rows are "
        "repaired here through `update_account` (`account_subtype` is a PATCH field — the S21 "
        "edit a clerk would make), and **the fix belongs in `commit_transfer`'s `opening` "
        "payload**, in a file this lane does not own. A transfer is *the same customer, a new "
        "address*; their classification is part of who they are. REPORTED."
    ),
    "addresses_are_fixture_named": (
        "§5.8.6 draws an `ADDRESS` column and prints no address in any of its nine rows, so "
        "the four seats this block's new accounts stand on are named by the fixture "
        "(`metering.sample_data.W7_SEATS`) and say so. The seven transfer addresses ARE "
        "§5.7.6's own."
    ),
}


def _w7_anchor() -> date:
    """The W6/W7 fixture's anchor — metering's, never a second copy.

    A second `tenant_today()` here would be a second answer to *"what day is
    this fixture dated"*, and the two would disagree the first time a seed was
    replayed (hard-won law 5's shape, applied to a date).
    """
    from apps.metering import sample_data as metering_sample

    return metering_sample.w6_anchor_on()


def _live_payment_plan_account_id() -> str | None:
    """The account holding the fixture's one LIVE, mid-schedule payment plan.

    `seed_sample_payment_plans` puts it on `sample_fixture.PAYMENT_PLAN`'s unit,
    and BR-CUS-043 is what makes it the right home for §5.8.6's
    `HELD · PAYMENT PLAN` row — the protection has no date of its own and is
    READ from payments every time it is asked.
    """
    return sample_account_ids().get(fixture.PAYMENT_PLAN["unit_index"])


def _w7_account_payload(spec: dict[str, Any], subtypes: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_type": spec["account_type"],
        "status": spec["status"],
        "opened_at": (_w7_anchor() - timedelta(days=730)).isoformat(),
        "autopay": False,
        "contact": {"full_name": spec["customer_name"], "is_primary": True},
    }
    if spec.get("deposit_on_file"):
        # US-CUS-023 / BR-CUS-050: a migrated deposit arrives WITH its original
        # receipt date, or interest starts at cutover and the longest-standing
        # customers are quietly under-paid.
        payload["deposit_on_file"] = spec["deposit_on_file"]
        payload["deposit_received_on"] = (
            _w7_anchor() + timedelta(days=spec["deposit_offset"])
        ).isoformat()
    subtype = SUBTYPE_COMMERCIAL if spec["account_type"] == "commercial" else SUBTYPE_SINGLE_FAMILY
    if subtype in subtypes:
        payload["account_subtype"] = subtype
    return payload


def _seed_w7_accounts(actor: Any) -> int:
    """The eight accounts §5.7.6 and §5.8.6 need and this tree does not have.

    Through `create_from_import` for the reason `_seed_cr030_account_shapes`
    gives one screen up: the AGEING column is DERIVED from the account's own
    opening position (BR-CUS-016 → BR-CUS-048), so a shape is made by giving the
    account a BUCKET and never by typing a segment — and it is the only door
    that accepts a migrated deposit with its original receipt date.

    ⚠ **THE BALANCE HAS TO REACH THE LEDGER, NOT JUST THE CACHE.**
    `disconnects._balance_for` reads `seams.ar_positions` — *"from the ledger,
    through the published seam"* — and `halt_reason` stops the ladder on an
    unreadable balance (hard-won law 3: the unsafe option here is chasing). So
    the opening batch below is not decoration: without it every seeded case
    would refuse to open with `balance_not_readable`.

    Idempotent (BR-TEN-063): an account already on file under its number is
    skipped and a replay writes nothing.
    """
    units = _unit_no_to_id()
    if not units:
        return 0
    tenant_id = _tenant_id()
    subtypes = _available_subtypes()
    cutover = demo_cutover_on()
    seat = _cutover_seat()
    written = 0
    posted: list[dict[str, Any]] = []
    #: DEF-1713 — the three carried deposits §5.7.6 draws (3 × $150.00), so the
    #: 2300 liability knows about the money the register says is held.
    held: list[dict[str, Any]] = []
    for spec in W7_ACCOUNTS:
        account_no = spec["account_no"]
        if models.Account.objects.filter(tenant_id=tenant_id, account_no=account_no).exists():
            continue
        unit_id = units.get(spec["unit_no"])
        if unit_id is None:
            logger.info(
                "sample data (CR-030 W7 task 7.12): %s has no seat — unit %s is not seeded by "
                "`metering.sample_data.W7_SEATS`, so the %s row is missing from the tab",
                account_no,
                spec["unit_no"],
                spec["key"],
            )
            continue
        if services.active_account_for_unit(unit_id) is not None:
            continue
        mapped: dict[str, Any] = {
            "customer_name": spec["customer_name"],
            "customer_ref": spec["customer_ref"],
            **(spec.get("buckets") or {}),
        }
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                result = services.create_from_import(
                    actor=actor,
                    payload={
                        "mapped": mapped,
                        "unit_id": unit_id,
                        "account_no": account_no,
                        "currency": None,  # the TENANT's, never a figure typed here
                        "cutover_on": cutover,
                        "import_run_id": (seat or {}).get("run_id"),
                        "account": _w7_account_payload(spec, subtypes),
                    },
                )
        except Exception as exc:  # noqa: BLE001 — one refusal must not stop the rest
            logger.info(
                "sample data (CR-030 W7 task 7.12): %s (%s) was refused — %s: %s",
                account_no,
                spec["key"],
                type(exc).__name__,
                exc,
            )
            continue
        written += 1
        _tag(models.Account.objects.filter(tenant_id=tenant_id, pk=result["id"], is_sample=False))
        _tag(
            models.Contact.objects.filter(
                tenant_id=tenant_id, account_id=result["id"], is_sample=False
            )
        )
        _tag(
            models.AccountOpeningBucket.objects.filter(
                tenant_id=tenant_id, account_id=result["id"], is_sample=False
            )
        )
        _tag(
            models.CustomerAccount.objects.filter(
                tenant_id=tenant_id, account_id=result["id"], is_sample=False
            )
        )
        _tag(
            models.Customer.objects.filter(
                tenant_id=tenant_id, external_ref=spec["customer_ref"], is_sample=False
            )
        )
        if not result["opening_empty"]:
            posted.append(
                {
                    "account_id": result["id"],
                    "account_ref": result["account_no"],
                    "balance": Decimal(result["opening_total"]),
                }
            )
        # DEF-1713 — NOT nested under `opening_empty`: all three deposit-holding
        # W7 accounts carry `"buckets": None`, so nesting it there would post
        # exactly none of them, which is how the drift got to $750.00.
        if Decimal(result.get("deposit_on_file") or 0):
            held.append(
                {
                    "account_id": result["id"],
                    "account_ref": result["account_no"],
                    "held": Decimal(result["deposit_on_file"]),
                    "received_on": result.get("deposit_received_on"),
                }
            )
    written += _post_w7_opening_batch(actor, cutover, posted, held)
    return written


def _post_w7_opening_batch(
    actor: Any,
    cutover: date,
    accounts: list[dict[str, Any]],
    deposits: list[dict[str, Any]] | None = None,
) -> int:
    """The four ladder accounts' opening receivables, posted BY THE LEDGER.

    ⚠ **CUSTOMERS WRITES NO JOURNAL LINES** (CLAUDE.md hard rule 5, B1). This
    composes the contract and hands it to `import_writer.post_opening_batch_
    from_import`, which hands it to `apps.ledger.opening_balances`; the POSTING
    SERVICE writes the balanced pair, keyed so a replay is a no-op.

    Returns 0 and SAYS WHY rather than raising — a tenant that has designated no
    `chart.AR` account cannot post, and that must not take the accounts down
    with it. ⚠ **But it DOES take the ladder down with it**, and the log line
    says so: a case cannot open on a balance nobody can read.
    """
    deposits = deposits or []
    if not accounts and not deposits:
        return 0
    from apps.customers import import_writer

    currency = (
        models.Account.objects.filter(pk=(accounts or deposits)[0]["account_id"])
        .values_list("currency", flat=True)
        .first()
    )
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            posting = import_writer.post_opening_batch_from_import(
                actor=actor,
                batch_id=W7_OPENING_BATCH_KEY,
                cutover_on=cutover,
                imported_at=datetime.combine(cutover, time(0, 0), tzinfo=dt_timezone.utc),
                currency=currency,
                accounts=accounts,
                # DEF-1713 — same batch, same cutover date, one handoff.
                deposits=deposits,
            )
    except Exception as exc:  # noqa: BLE001 — an environment gap, named
        logger.info(
            "sample data (CR-030 W7 task 7.12): the ladder accounts' opening entries were NOT "
            "posted (%s: %s), so `seams.ar_positions` cannot answer what they owe and every "
            "disconnect case below will refuse to open with `balance_not_readable` — which is "
            "the ladder failing safe (hard-won law 3), not a bug. Map the AR and "
            "opening-clearing accounts on Settings > Chart of accounts",
            type(exc).__name__,
            exc,
        )
        return 0
    if posting is None:
        logger.info(
            "sample data (CR-030 W7 task 7.12): the ledger publishes no `post_opening_batch` on "
            "this deployment, so the ladder accounts have no entry behind them (BR-CUS-049) and "
            "no case can open"
        )
        return 0
    return len(accounts)


def _seed_w7_transfers(actor: Any) -> int:
    """B18 §5.7.6's five rows — **NONE IS PLANTED, AND EACH SAYS WHY**
    (`DEF-CUS-9072`, `W7_ABSENCES["transfer_rows_are_moves"]`).

    Every one of the five draws a customer MOVING HOUSE — two addresses, a new
    account at the second. `BR-CUS-1030` (PO, 2026-09-01) made a transfer a
    SALE: the same account passes to a new customer, and nothing opens or
    closes. `BR-CUS-1031` made a move a new service request. So the drawn rows
    describe a job this product no longer has, and the steps they were walked
    through (`set_target_unit`, `set_dates`, `elect_money`, `commit_transfer`)
    were removed by `CR-058` on the same day.

    ⚠ **THIS USED TO PLANT THEM AND HAS FAILED QUIETLY SINCE 2026-09-01.** Each
    row raised `AttributeError` inside a savepoint, the row rolled back, and one
    INFO line was the only trace — so the tenant held one half-started transfer
    and nothing said four were missing. A demo SALE to show on the Transfers
    tab is a new fixture (buyers nobody has drawn), not a repair of these rows.

    Returns 0, and logs each row by name.
    """
    for row in W7_TRANSFERS:
        logger.info(
            "sample data (CR-030 W7 task 7.12): transfer %s (%s) is not seeded — %s",
            row["key"],
            row["customer"],
            W7_ABSENCES[W7_TRANSFER_BLOCKER],
        )
    return 0


def _seed_w7_disconnects(actor: Any) -> int:
    """B18 §5.8.6's nine rows — every tier and all three BUILT protections.

    ⚠ **THREE PROTECTIONS, NOT TEN (BR-CUS-101, PO: *"3 is okay to start
    with"*).** Medical certificate, payment plan and weather moratorium are what
    exist; the other seven do not exist to seed.

    The ladder is walked through `disconnects.advance()` — the ONE gate — and
    never by an UPDATE: a tier set with an UPDATE would prove only that a column
    can hold a string. A tier-3 cut then goes through `record_proof_of_service`
    (BR-CUS-100 — a PERSON attests how the notice was served, with a real
    certified-mail article number) and `schedule_cut`, in that order, because
    *"a tier-3 cut must not be schedulable on an unrecorded service"*.

    ⚠ **TWO OF THE NINE ARE NOT PLANTED** — see
    `W7_ABSENCES["no_writer_for_cut_or_reconnecting"]`.
    """
    from apps.customers import disconnects

    tenant_id = _tenant_id()
    anchor = _w7_anchor()
    written = 0
    for row in W7_DISCONNECTS:
        if row.get("blocker"):
            logger.info(
                "sample data (CR-030 W7 task 7.12): %s (%s · %s) is NOT on the screen — %s",
                row["drawn_no"],
                row["customer"],
                row["drawn_state"],
                W7_ABSENCES[row["blocker"]],
            )
            continue
        account_id = None
        if row.get("resolve") == "live_payment_plan_account":
            account_id = _live_payment_plan_account_id()
        elif row.get("account_no"):
            account_id = (
                models.Account.objects.filter(tenant_id=tenant_id, account_no=row["account_no"])
                .values_list("id", flat=True)
                .first()
            )
        if account_id is None:
            logger.info(
                "sample data (CR-030 W7 task 7.12): %s (%s) has no account on this tree and is "
                "not seeded",
                row["drawn_no"],
                row["customer"],
            )
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                if row.get("protection"):
                    if disconnects.AccountProtection.objects.filter(
                        tenant_id=tenant_id, account_id=account_id, kind=row["protection"]
                    ).exists():
                        continue
                    expires = row["protection_expires_offset"]
                    disconnects.record_protection(
                        actor,
                        account_id,
                        kind=row["protection"],
                        effective_from=anchor + timedelta(days=row["protection_from_offset"]),
                        expires_on=(None if expires is None else anchor + timedelta(days=expires)),
                        note=f"CR-030 W7 task 7.12 · B18 §5.8.6 · {row['customer']}",
                    )
                    written += 1
                    continue
                if disconnects.open_case_for(account_id) is not None:
                    continue
                tier = {"tier_1": 1, "tier_2": 2, "tier_3": 3}[row["drawn_tier"]]
                for _step in range(tier):
                    disconnects.advance(actor, account_id, as_of=anchor)
                written += 1
                if row.get("cut_offset") is None:
                    continue
                case = disconnects.open_case_for(account_id)
                notice = disconnects.latest_notice_at_tier(case, disconnects.TIER_3)
                disconnects.record_proof_of_service(
                    actor,
                    notice.pk,
                    channel=disconnects.SERVE_CERTIFIED_MAIL,
                    reference=row["proof_reference"],
                    served_on=anchor + timedelta(days=row["served_offset"]),
                    signed_for_on=(
                        None
                        if row["signed_offset"] is None
                        else anchor + timedelta(days=row["signed_offset"])
                    ),
                )
                disconnects.schedule_cut(
                    actor,
                    account_id,
                    cut_on=anchor + timedelta(days=row["cut_offset"]),
                    as_of=anchor,
                )
        except Exception as exc:  # noqa: BLE001 — one refusal must not stop the rest
            logger.info(
                "sample data (CR-030 W7 task 7.12): %s (%s) stopped early — %s: %s",
                row["drawn_no"],
                row["customer"],
                type(exc).__name__,
                exc,
            )
    return written


def w7_fixture_report() -> list[dict[str, Any]]:
    """Every drawn W7 row and its disposition on THIS tree — data, not a log
    line, so `tests/test_w6_w7_seed.py` asserts the dispositions instead of
    re-deriving them (`w5_move_fixture_report`'s posture)."""
    from apps.customers import disconnects, transfers

    tenant_id = _tenant_id()
    out: list[dict[str, Any]] = []
    for row in W7_TRANSFERS:
        account = models.Account.objects.filter(
            tenant_id=tenant_id, account_no=row["from_no"]
        ).first()
        job = (
            None
            if account is None
            else transfers.Transfer.objects.filter(
                tenant_id=tenant_id, from_account_id=account.id
            ).first()
        )
        out.append(
            {
                "kind": "transfer",
                "key": row["key"],
                "from_no": row["from_no"],
                "drawn_to_no": row["drawn_to_no"],
                "customer": row["customer"],
                "addresses": row["addresses"],
                "drawn_step": row["drawn_step"],
                "seeded_step": None if job is None else job.step,
                "drawn_state": row["drawn_state"],
                "seeded_state": None if job is None else job.state,
                "drawn_money": row["drawn_money"],
                "planted": job is not None,
                "seeded_to_no": (
                    None if job is None or job.to_account is None else job.to_account.account_no
                ),
                # `DEF-CUS-9072` — the row is a MOVE, which `BR-CUS-1030` retired.
                "blocker": W7_TRANSFER_BLOCKER,
                "blocker_detail": W7_ABSENCES[W7_TRANSFER_BLOCKER],
            }
        )
    for row in W7_DISCONNECTS:
        account_id = None
        if row.get("resolve") == "live_payment_plan_account":
            account_id = _live_payment_plan_account_id()
        elif row.get("account_no"):
            account_id = (
                models.Account.objects.filter(tenant_id=tenant_id, account_no=row["account_no"])
                .values_list("id", flat=True)
                .first()
            )
        case = None if account_id is None else disconnects.open_case_for(account_id)
        protections = (
            ()
            if account_id is None
            else disconnects.protections_for(account_id, as_of=_w7_anchor())
        )
        # PLANTED means the row EXISTS, never that a tile counts it: a stored
        # protection that is not in force is planted and is honestly short, and
        # collapsing the two would hide exactly the case `note` explains.
        seeded_no = None
        if account_id is not None:
            seeded_no = (
                models.Account.objects.filter(tenant_id=tenant_id, pk=account_id)
                .values_list("account_no", flat=True)
                .first()
            )
        out.append(
            {
                "kind": "disconnect",
                "key": row["key"],
                "drawn_no": row["drawn_no"],
                "seeded_no": seeded_no,
                "customer": row["customer"],
                "drawn_customer": row.get("drawn_customer"),
                "drawn_owed": row["drawn_owed"],
                "drawn_tier": row["drawn_tier"],
                "drawn_state": row["drawn_state"],
                "planted": case is not None or bool(protections),
                "seeded_tier": None if case is None else disconnects.ladder_tier_of(case),
                "seeded_state": None if case is None else case.state,
                "cut_scheduled_for": (
                    None
                    if case is None or case.cut_scheduled_for is None
                    else case.cut_scheduled_for.isoformat()
                ),
                "protections_in_force": [p["kind"] for p in protections if p["in_force"]],
                "blocker": row.get("blocker"),
                "blocker_detail": W7_ABSENCES.get(row.get("blocker") or ""),
                "note": row.get("note"),
                "note_detail": W7_ABSENCES.get(row.get("note") or ""),
            }
        )
    return out


def _seed_w7_fixtures(actor: Any) -> int:
    """Task 7.12, in the one order that works: accounts and their ledger
    positions FIRST, then the transfers, then the ladder.

    The order is not a preference. A disconnect case reads what an account owes
    from the LEDGER (`disconnects._balance_for` → `seams.ar_positions`), so a
    case opened before the opening batch is posted refuses with
    `balance_not_readable`; and a transfer commits by CLOSING its outgoing
    account, so a ladder walked first would be walking one that is about to
    close.
    """
    written = _seed_w7_accounts(actor)
    written += _seed_w7_transfers(actor)
    written += _seed_w7_disconnects(actor)
    for name, reason in W7_ABSENCES.items():
        logger.info("sample data (CR-030 W7 task 7.12): %s — %s", name, reason)
    return written


# ══════════════════════════════════════════════════════════════════════════
# CR-035 · STEP 6 ROW 6 — THE SEEDED PARKED DRAFT (S17.2, "Waiting on")
# ══════════════════════════════════════════════════════════════════════════
#
# CR-035's own scope table, verbatim: **"a seeded parked example, so the screen
# is not empty on a demo."** One row. It exists so a clerk opening
# `/{tenant}/accounts?tab=waiting-on` on a fresh tenant sees the feature instead
# of an empty state.
#
# ⚠ **EVERY VALUE BELOW IS QUOTED FROM A FIXTURE ROW THAT ALREADY EXISTS, WITH
# ONE EXCEPTION THAT IS LABELLED.** That is `seed_demo.py`'s `[F]`/`[W]`
# provenance discipline applied to a non-money fixture: a demo figure nobody can
# trace is a figure the next lane will "correct" in the wrong direction.
#
#   flow          `move_in`                       B18 §5.5.7 draws the row as a
#                                                 move-in DRAFT
#   subject       `3450 Oak Ridge Dr · Unit 1`    CR030_SERVICE_REQUESTS
#                 = `SCW-U-207`                   ['osei-move-in']
#                                                 .address_unit_as_given
#   step          1 of 5                          W5_MOVE_INS['mvi-osei'].step —
#                                                 *"her move-in is Waiting at
#                                                 step 1"*
#   waiting_on    `documents`                     the same SR row, verbatim, and
#                                                 one of B18 §4.2's nine
#   park_note     "Photo ID and the signed        the same SR row, verbatim
#                  agreement still to come —
#                  chased 21 Aug."
#   remind_on     tenant today + 2 days           the same SR row's
#                                                 `remind_on_days: 2`, verbatim
#   age           5 days                          ⚠ **DERIVED, not drawn** — see
#                                                 CR035_PARK_AGE_DAYS below
#
# ⚠ **THE SUBJECT IS THE ONE SEEDED UNIT THAT IS VACANT, AND THAT IS THE POINT,
# NOT A COINCIDENCE.** `SCW-U-207` carries `leave_vacant: True` in
# `core.sample_fixture.CR030_PREMISES` and **must stay vacant** — it is what
# makes `SR-26-0039` resolve `served_vacant`. So BR-SHL-048's worked example
# ("a clerk parks a move-in for a unit; the unit still reads Vacant") is planted
# on the one seat where getting it wrong is loudest.
#
# **That is deliberate, and it is the lesson of the premises-services defect.**
# A seeder that writes BOTH sides of what it is demonstrating always agrees with
# itself: green in the demo, wrong in production. Here the seeder writes ONE row
# and the check reads the other side through the PRODUCT'S OWN selector
# (`services.active_account_for_unit`) — never through a value this file wrote.
#
# ⚠ **AND NOTHING ELSE IN THIS REPOSITORY CHECKS THAT SEAT — measured
# 2026-08-26.** `tests/test_cr031_service_request.py::test_a_served_vacant_unit_
# fits_a_move_in` builds its own premises and unit and never touches the sample
# estate, and `tests/test_w5_move_in_out_cases.py::test_task_5_11…` reads
# `W5_BLOCKERS` rather than the database. `SCW-U-207`'s vacancy is asserted only
# by `tests/test_cr035_fixture.py::test_cr035_fixture__the_unit_it_names_is_
# still_vacant`. **REPORTED** — the estate's own load-bearing vacancy deserves a
# case that does not depend on this fixture existing.
#
# ⛔ **WHAT IS NOT SEEDED, AND WHY.** B18 §5.5.7 draws a SECOND draft —
# `Alvarez, Rosa`, `2 of 5`, deposit *carried $153.50*, §5.5.1's `OLDEST · 6
# days`. It is not planted: the drawing gives it **no park reason**, its linked
# `SR-26-0044` carries `waiting_on: None`, and `wizard_parks` has a CHECK
# constraint refusing an empty `waiting_on` — *"a row with no reason is a park
# that forgot the only thing it is for."* Seeding it would mean **inventing the
# one thing a park exists to record**. Recorded rather than tuned away.
#
# ⛔ **AND THE REMINDER GOES NOWHERE.** `remind_on` is stored and nothing sends
# it (**DEF-758**). This fixture makes that gap MORE visible, not less: a demo
# tenant now carries a reminder date that no adapter will ever act on. Reported;
# building a notification path is not this block's job and not this CR's scope.

#: ⚠ **THE ONE DERIVED VALUE, AND THE DERIVATION IS STATED SO IT CAN BE
#: ARGUED WITH.** B18 draws no age for `Osei, Grace`'s draft. What it DOES draw
#: is §5.5.1's KPI `OLDEST · 6 days · Alvarez, Rosa · started Aug 17`, which
#: caps every other in-flight move-in at **≤ 6 days**. So 5 is the oldest a
#: second draft can be while that drawn figure stays true — chosen at the bound
#: rather than plucked, because the AGE column is the whole feature
#: (BR-SHL-048 (c)) and a fixture with age zero demonstrates nothing.
CR035_PARK_AGE_DAYS = 5

#: The SR fixture row this draft is the other half of. Named once so the seeder
#: and its test cannot drift into two spellings of one row.
CR035_PARK_SOURCE_SR = "osei-move-in"

#: The W5 row that draws the move-in itself (its STEP).
CR035_PARK_SOURCE_MOVE_IN = "mvi-osei"

#: ⚠ **THE TWO AUTHORITIES DISAGREE ABOUT THE ADDRESS, AND THE SEEDED ONE WINS
#: — REPORTED, NOT RESOLVED.** B18 §5.5.7's move-in table draws `Osei, Grace` at
#: `500 Main · 210` (= `SCW-U-211`, which is OCCUPIED), while B19 §12.2 and
#: `CR030_SERVICE_REQUESTS['osei-move-in']` put her at `3450 Oak Ridge Dr` (=
#: `SCW-U-207`, vacant) — and `SR-26-0044`/`SR-26-0039`'s addresses cross the
#: same way in the other direction. This block resolves on the LINKED REQUEST,
#: because that is the row that actually exists in a seeded tenant and the row
#: §5.5.7's own closing paragraph says the draft links to. Neither document is
#: edited here; the divergence belongs to the fixture owner
#: (`core/sample_fixture.py`) and to B18.
CR035_PARK_UNIT_NO = "SCW-U-207"


def _cr035_park_payload(today: date) -> dict[str, Any]:
    """The park payload, assembled from the fixture rows rather than typed."""
    source = next(
        row for row in fixture.CR030_SERVICE_REQUESTS if row["key"] == CR035_PARK_SOURCE_SR
    )
    move_in = next(row for row in W5_MOVE_INS if row["key"] == CR035_PARK_SOURCE_MOVE_IN)
    units = _unit_no_to_id()
    unit_id = units.get(CR035_PARK_UNIT_NO)
    return {
        "flow": "move_in",
        "step": int(move_in["step"]),
        # BR-SHL-048 (a) — a COPIED id, never a foreign key. Absent when the
        # estate has not been seeded, which is lawful: a draft parked on step 1
        # before the clerk chose anything has no subject at all.
        "subject_ref": {"unit_id": unit_id} if unit_id else {},
        "subject_label": str(source["address_unit_as_given"]),
        "waiting_on": str(source["waiting_on"]),
        "park_note": str(source["park_note"]),
        "remind_on": (today + timedelta(days=int(source["remind_on_days"]))).isoformat(),
        # What the clerk had typed when they stopped. Step 1 of the move-in is
        # `Unit`, so the applicant's own details are what step 2 is FOR and are
        # not in the draft yet — putting them here would draw a further-along
        # wizard than the STEP column claims.
        "values": {"unit_no": CR035_PARK_UNIT_NO},
    }


def _cr035_park_exists(label: str) -> bool:
    """Idempotency key (BR-TEN-063): flow + subject label, read through the
    OWNING module's list. Not the id — the store mints a fresh uuid7 on every
    call, so a replay keyed on it would plant a second draft every time."""
    from apps.customers import seams

    return any(
        row.flow == "move_in" and row.subject_label == label
        for row in seams.wizard_park_rows(flow="move_in")
    )


def seed_sample_wizard_parks(actor: Any) -> int:
    """CR-035 step 6 row 6 — ONE parked move-in, so `Waiting on` is not empty.

    ⚠ **IT WRITES ONE ROW OF `wizard_parks` AND NOTHING ELSE, WHICH IS THE
    FIXTURE'S ENTIRE POINT.** BR-SHL-048: *"Option A - Unitl move in executed,
    no records updates."* A seeded draft has to obey that exactly like a real
    one — no account, no occupancy, no service agreement, no bill, and no change
    to the unit it names. A seeder that wrote a draft AND its unit's state would
    teach every reader of this demo the wrong model of the feature.

    Everything goes through `apps.tenancy.wizard_parks.park` — the same function
    the wizards' `POST /wizard-parks` calls — via `seams`, so BR-SHL-048's own
    one-row guarantee is the product's rather than this file's, and the audit row
    (hard rule 7) is written by the service exactly as it is for a clerk.

    Idempotent (BR-TEN-063): a replay finds the draft already parked and writes
    nothing.
    """
    from apps.customers import seams

    today = seams.tenant_today()
    payload = _cr035_park_payload(today)
    if _cr035_park_exists(payload["subject_label"]):
        return 0
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            row = seams.park_wizard_draft(actor, payload)
    except Exception as exc:  # noqa: BLE001 — one refusal must not fail the run
        logger.info(
            "sample data (CR-035): the parked move-in was refused — %s: %s",
            type(exc).__name__,
            exc,
        )
        return 0
    # The AGE. `parked_at` is `auto_now_add`, so a freshly seeded draft is zero
    # days old and demonstrates nothing (see CR035_PARK_AGE_DAYS). Relative to
    # the TENANT's today, so the fixture stays true next month.
    seams.backdate_wizard_park(
        row.id,
        datetime.combine(
            today - timedelta(days=CR035_PARK_AGE_DAYS), time(9, 30), tzinfo=dt_timezone.utc
        ),
    )
    return 1


def remove_sample_wizard_parks() -> dict[str, Any]:
    """BR-TEN-061/066 for this block — and the KEY is narrower than the tag rule.

    ⚠ **`wizard_parks` CARRIES NO `is_sample` COLUMN**, so BR-TEN-057's
    predicate does not exist for it and the sweep is keyed on the draft this
    block plants: flow `move_in` at the seeded subject label. That is a NARROWER
    key, not a wider one — a draft a real clerk parked is never touched — but it
    IS a divergence from the tag rule and **the column is OWED**. Reported here
    rather than papered over, exactly as `remove_sample_records` reports the same
    divergence for `disconnect_cases`, `disconnect_notices` and
    `account_protections`.
    """
    from apps.customers import seams

    today = seams.tenant_today()
    label = _cr035_park_payload(today)["subject_label"]
    removed = 0
    retained: list[dict[str, Any]] = []
    for row in seams.wizard_park_rows(flow="move_in"):
        if row.subject_label != label:
            continue
        try:
            # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
            with transaction.atomic():
                seams.discard_wizard_park_for_sample(row.id)
                removed += 1
        except Exception as exc:  # noqa: BLE001 — BR-TEN-066: name it, keep going
            retained.append(
                {
                    "label": f"parked move-in {row.id}",
                    "reason": f"the draft store refused the delete — {type(exc).__name__}",
                }
            )
    return {"removed": removed, "retained": retained}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-257: every sample account carries a sub-type under its own type — `accounts.account_subtype_id` was NULL on 49 of 49 live rows) · AMENDED 2026-08-24 by story-coder (CR-030 W1 T1.23 demo-seed lane — ❄️ GT-16's migrated account A-12103: four aged buckets 84.20 / 62.10 / 0.00 / 121.00 = 267.30 at cutover 2026-08-31, cached balance from the same position object, and ONE balanced opening JE posted BY THE LEDGER) · AMENDED 2026-08-24 by story-coder (DEF-629 seed-cutover lane — PO ruling *"whenever you do the migration cant you devcide the date at that time"*: `demo_cutover_on()` decides a DEMO ageing shape's cutover when the seed runs (`seams.tenant_today()` on the first run, the `as_of` already stored on the tenant's demo buckets on every run after, so a replay re-dates nothing), and ❄️ GT-16 is EXCLUDED — `A-12103` keeps the finance-signed 2026-08-31 and the plant now REFUSES a seat offering any other date)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel serves this through tenancy's endpoints) E=deferred(same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: [DEF-629] `demo_cutover_on()` has NO in-seed caller yet and that is stated rather than hidden (hard-won law 1/2): the three demo ageing shapes it exists for (`Active/Current`, `Active/30d past`, `Active/60+ past`) are three of B18 §5.1.5's eight `[shot]` rows and W2 task 2.10 is BLOCKED on fixture estate — seven of the eight need a UNIT, the fixture has no free one, and units are metering's table (B1). MEASURED, not assumed: a fully-planted demo tenant holds opening buckets on exactly ONE account, ❄️ GT-16's A-12103. The policy lands ahead of the shapes on purpose, because the thing the PO ruled against is a literal date being copied into the seeder that finally seats them; `tests/test_def629_seed_cutover.py` proves it on real rows through `selectors.ageing_segments_for` and goes RED if a demo shape is ever seeded at a date this function did not decide · [CR-030 W1 T1.23] ❄️ GT-16's batch tie-out (1,213 accounts → $184,320.55) is RECORDED on RUN-2814's counts and is NOT posted as 1,213 journal entries — PO ruling 2026-08-11: *"The opening-balance import verifies a single account only; the 1,213-account batch total stays illustrative"*, and 10-scripts/03-golden-verify.py reports the same line NOT-CHECKABLE. Composing 1,212 per-account figures to make the total come out would be a fixture proving the fixture, and posting them against ids no `accounts` row carries would put phantom AR into ledger.reporting.ar_positions (hard-won law 1). What IS proved from real rows is the property the total rests on: Σ AR debits = Σ clearing credits · [CR-030 W1 T1.23] the seed REFUSES (BlockCannotRun) if the product's Σ of the four buckets is not the frozen 267.30 — a frozen figure moves only by a finance re-sign (HUMAN-GUIDE §6), so a disagreement is a defect in the code and never an edit here; a ledger that cannot take the entry (no chart.AR / chart.OPENING_CLEARING designation) is an ENVIRONMENT gap, logged by name, and the account is not planted at all rather than half-planted · BR-TEN-065 is AMENDED (PO 2026-08-16 supersedes PO 2026-08-10) — sample accounts are ACTIVE, because a Pending-activation account cannot be billed and the fixture spec requires June and July BILLED; the rule doc carries the amendment, dated, with both quotes · the price of that amendment is stated rather than discovered: removal becomes PARTIAL, and a billed account is retained BY NAME under BR-TEN-066 because hard rule 4 forbids deleting its invoices
# AMENDED 2026-08-25 by the CR-030 W5 lane (task 5.11) — B18 §5.5.7's five move-ins and §5.6.7's six move-outs are DECLARED as `W5_MOVE_INS` / `W5_MOVE_OUTS` and resolved against this tree by `w5_move_fixture_report()`; `_seed_w5_move_fixtures` writes ONE `account_notes` row per resolvable row and reports every unresolvable one BY NAME.
# exceptions [CR-030 W5 T5.11]: (1) THE FIXTURE ROWS ARE DECLARED IN THIS FILE AND NOT IN `core/sample_fixture.py`, where its eight sibling fixture sets live. That module is not this lane's file; the rows are marked for the fixture owner to move.
#   (2) FOUR OF THE ELEVEN ROWS ARE NOT PLANTABLE AND ONE OF THEM IS THE HEADLINE. `A-12039 · 2201 Cedar Ln`, `A-12041 · 12 Harbour View`, `A-10992 · 17 Brambling Ct` and `A-11208 · 44 Larkspur Way` have NO SEEDED PREMISES, and every one of the 62 seeded units already holds an account except `SCW-U-207`, which must stay vacant. `A-11208` is task 5.11's own *"two OQ fixtures"* half — BR-CUS-081's `refund $11.20`. Seats are metering's (`core.sample_fixture.CR030_PREMISES` + `apps/metering/sample_data.py`); REPORTED, never worked around.
#   (3) NO SETTLEMENT FIGURE IS SEEDED, AND NONE CAN BE. `deposit_on_file` is a REFUSED field on `create_account`/`update_account` (BR-CUS-023), so only `create_from_import` writes one — which needs the seat (2) says does not exist; and BR-CUS-057's accrual is unbuilt, so every account holding a deposit states NO LANDING. Every drawn settlement lands on a GAP and each row says so (`lands_on: GAP`).
#   (4) `STEP · 3 of 6` HAS NO STORE. There is no `move_ins`/`move_outs` table and no wizard store; `waiting_on`/`park_note`/`parked_at` are columns on `service_requests` alone. The two DRAFT move-ins are therefore the two service requests (`SR-26-0044`, `SR-26-0039`), which is what §5.5.7 itself says they link to.
#   (5) TWO ACCOUNT NUMBERS DISAGREE WITH B18 §5.6.7 AND ARE NOT RENUMBERED HERE: `A-11603 · Thompson, R.` was planted as `A-11996` and `A-11024 · Ridge Coffee Co.` as `A-11801` (W2 task 2.10), and `A-11996` is also §5.7.6's number for `Haddad, Nour`'s transfer account. Both numbers ride each row (`drawn_no` + `seeded_no`). REPORTED for the fixture owner.
#   (6) THE STEP DENOMINATOR IS SIX. §5.6.2/§5.6.7 print `of 4`; BR-SHL-046 (PO 2026-08-24, closing DEF-648) ruled SIX and the rows carry 6, so the demo cannot teach a count superseded three days earlier.
#   (7) `account_notes` CARRIES NO `is_sample` COLUMN, so `--remove` cannot sweep these notes — BR-TEN-057's own shape, the same statement `_seed_cr030_demo_notes` makes.
#   (8) BLACK WAS ALREADY FAILING ON THIS FILE AT HEAD (three pre-existing spots in `seed_sample_records`). This lane's `black` run fixed them; they are the only lines outside the W5 block that moved.
# AMENDED 2026-08-25 by the SEED lane (CR-030 W7 task 7.12) — B18 §5.7.6's five transfers and §5.8.6's nine disconnects, declared as `W7_TRANSFERS` / `W7_DISCONNECTS` / `W7_ACCOUNTS` and resolved against this tree by `w7_fixture_report()`. Proved through the two selectors the screens call: `transfer_reads.list_transfers` serves `OPEN 2 · MOVING THIS WEEK 1 · ARREARS FOLLOWING 1 · COMPLETED THIS MONTH 3` and `disconnect_reads.list_disconnects` serves `AT NOTICE 4 · DUE TO CUT THIS WEEK 2`.
# exceptions [CR-030 W7 T7.12] — every one is a MEASUREMENT carried as data in `W7_ABSENCES`, never a figure tuned to make a tile read right:
#   (1) ⛔ **`CUT, AWAITING PAYMENT 1` AND `RECONNECTIONS DUE 1` SEED AS 0, BECAUSE NOTHING IN THIS PRODUCT WRITES `cut` OR `reconnecting`.** Measured 2026-08-25: both tokens appear in `CASE_STATES`, in migration 0022's check constraint and in two KPI tiles — and in no assignment anywhere. `schedule_cut` writes `STATE_SCHEDULED` and says so itself (*"The cut itself … is task 7.8 and is NOT in this lane"*); the reconnect flow is task 7.9, unbuilt. `A-11488 · Doyle` and `A-11507 · Greaves` are therefore NOT planted. Writing the column from a seeder would manufacture a state the product cannot produce.
#   (2) ⛔ **`ON HOLD — PROTECTED` READS 2 WHERE B18 DRAWS 3 — AND THE CAUSE IS AN EXISTING FIXTURE, NOT THIS SEED.** A `payment_plan` protection has no date of its own (BR-CUS-043 holds it *while the plan is active AND current*), and the fixture's ONE live plan (`core.sample_fixture.PAYMENT_PLAN`) has LITERAL instalment dues — Jul 20 · Aug 3 · Aug 17 · Aug 31, two seeded paid — so **from 2026-08-18 it is behind** and `collections_pause_for` returns `plan_behind`. The protection is recorded on that account anyway, so it comes into force the moment the plan is current. **The demo's payment-plan case is drifting into arrears as the calendar moves past it — DEF-629's failure mode one fixture over — and the fix (seed-time-relative dues) belongs to `core/sample_fixture.py` and payments' plan-money seeder, neither of which this lane owns.** REPORTED.
#   (3) ⛔ **`DEPOSITS CARRYING` READS 0 WHERE B18 DRAWS 1.** `A-11455 · Park, Jenna` holds no deposit; `deposit_on_file` is a REFUSED field on `create_account`/`update_account` (BR-CUS-023) and the account is planted from `CR030_ACCOUNT_SHAPES`, a constant in a file this lane does not own, which carries none. The election is NOT forced True — a clerk recorded as carrying money the account does not hold is a worse fixture than a tile that is honestly short. **One-line fix for the fixture owner:** add `deposit_on_file` + a receipt date to that row.
#   (4) **PARK'S DRAWN `3 of 5` AND §5.7.1's TWO ELECTION TILES CANNOT BOTH BE TRUE.** The tiles count `deposit_carry_elected`/`arrears_follow_elected`, which are written at STEP 4 (`elect_money` sets `step = max(step, 4)`). The seed takes the ELECTION and carries both numbers (`drawn_step` 3 / `seeded_step` 4), because two tiles depend on the election and the step number depends on nothing. REPORTED.
#   (5) **TWO DRAWN ACCOUNT NUMBERS ARE ALREADY TAKEN AND NEITHER IS RENUMBERED.** `A-11780` keeps the estate's `Delgado, Pilar` (B18 §13 obs. 4: *"a fixture slip; the seed must pick one"*) and the drawn `Whitfield, Dana` rides the row. `A-11720` is the estate's `+3` overflow account, **whose EMPTY balance is load-bearing for `SR-26-0043`'s approval**, so `Calloway, Brett` is planted under a FIXTURE-NAMED `A-11721` with both numbers on the row — the `61 Larkspur Way` precedent. REPORTED for the fixture owner.
#   (6) **`A-11655 · Sandoval` IS RESOLVED, NOT CREATED** — onto the one account in the fixture that holds a live payment plan, because a `payment_plan` protection on an account with no plan is stored and never in force. The right home for the drawn row is the account the product really protects.
#   (7) **OSEI'S ROW HOLDS NO DATES AND NO TARGET.** §5.7.6 puts it at `1 of 5` and prints `Sep 14` in both date cells; a transfer stores dates at STEP 3. The drawn target (`500 Main · 210` = `SCW-U-211`) is occupied by `Ridge Coffee Co.` and `set_target_unit` would refuse it by name (BR-CUS-017) — the product working, not a fixture problem.
#   (8) **NO `deposit carried` FIGURE IS SEEDED AND NONE CAN BE.** BR-CUS-057's accrual is unbuilt, so the MONEY cell renders a line with no figure and the absence attached — never `$150.00` and never `$0.00`. The $150.00 PRINCIPAL is seeded, which is the representable half (❄️ WE-7/GT-23's frozen pair is $150.00 + $3.50 = $153.50).
#   (9) **`disconnect_cases`, `disconnect_notices` AND `account_protections` CARRY NO `is_sample` COLUMN** (measured on task 7.5's migration), so BR-TEN-057's predicate does not exist for them and `remove_sample_records` sweeps them on the SAMPLE ACCOUNT instead — a narrower key, not a wider one. **The column is OWED.** `transfers` does carry the tag and is swept on it.
#   (10) **THE SEATS ARE METERING'S** — `apps/metering/sample_data.W7_SEATS` — because `premises`/`units` are metering's tables (B2 r4), and the five disconnect addresses are FIXTURE-NAMED: §5.8.6 draws an ADDRESS column and prints no address in any of its nine rows.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
