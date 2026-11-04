# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (S17 rows need the premise/unit address and the meter #
#           the BR-CUS-053 search covers) · US-CUS-002 (search by service
#           address / meter #) · US-CUS-003 (S18 step 2 — the unit picker, its
#           service points, and the unit's default plan BR-MET-040 requires at
#           activation)   Screens: S17 · S18 · S21
#           AMENDED 2026-08-15 (tenant custom-fields lane): US-SHL-015 (EP-SHL-07 — `validate_custom_data`, a HARD import of tenancy's
#           published validator: a soft fallback would accept anything into a jsonb column, which is DEF-075's shape at its worst)
# Rules:    BR-CUS-020 (unit pickers offer vacant/reserved units only) ·
#           BR-CUS-017 (at most ONE active account per unit) · BR-MET-036
#           (occupancy is DERIVED from the active account — customers is the
#           module that answers it) · BR-MET-040 (plan REQUIRED at activation) ·
#           BR-CUS-053 (search covers service address + meter #) · BR-TEN-035
#           (account numbers come from the tenant series) · BR-TEN-043 (the
#           event date is named explicitly, never a wall clock)
# Tests:    06-backend/tests/test_us_cus_003_account_write.py
# Impacts:  apps/customers/services.py + selectors.py (every cross-module read
#           goes through here) · apps/metering/seams.py (which resolves the
#           customers half of BR-MET-036/037/047 by NAME — defining
#           `active_account_for_unit` here is what wires unit occupancy on)
# ───────────────────────────────────────────────────────
"""customers → other-module SEAMS: every cross-module call this module makes.

B1/B8: customers NEVER touches another module's ORM. Everything it needs from a
neighbour is one of the documented callables below, resolved AT CALL TIME from
`apps.<module>.selectors` (pure reads) or `.services` (writes). Same shape as
apps/metering/seams.py, deliberately — one pattern for cross-module access, not
two.

While a neighbour's function is not authored yet the seam reports "not wired"
and the caller takes the DOCUMENTED fallback; nothing here guesses a business
answer, and nothing here writes another module's tables.

Contracts consumed (owning lane → what customers asks it for):

  apps.metering.selectors.unit_row(unit_id) -> Unit
  apps.metering.selectors.unit_detail_dict(unit) -> dict
    BR-CUS-020 unit eligibility + the S17 "Premise" cell. `unit_row` raises the
    404-never-403 refusal for a cross-tenant id (HR-1) — customers reuses that
    rather than re-implementing the boundary.

  apps.metering.selectors.service_points_for(unit_id) -> list[dict]
    US-CUS-003 §5 "one service_agreement row per active service": the service
    points at the unit ARE the services the account takes.

  apps.metering.selectors.premises_services_for(premises_ids) -> dict
    BR-CUS-1093 (PO 2026-09-23): a MASTER account names no unit, so the line
    above reaches nothing for it and its services are the BUILDING's — read,
    never copied (BR-CUS-672). Unwired ⇒ {} ⇒ the account draws the service
    agreements it already holds, and no emptiness is invented for it.

  apps.metering.selectors.reads_for_unit(unit_id, on=…) -> dict
    CR-038 W9 task 2 — the unit's committed read heads per meter/register, for
    the move worklists' READS / FINAL READ cells and the FINAL READS DUE tile.
    Unwired ⇒ None ⇒ the cells state the absence (DEF-127; B2 §2 row OWED —
    see the function's own docstring).

  apps.metering.services.commit_event_reads(actor, payload) -> dict
    CR-038 W9 task 1 — THE event-reads write door (BR-MET-128 · BR-CUS-021 ·
    BR-MET-129): the wizards' initial/final reads commit through metering's
    own append-only pipeline, stamped with the EVENT and the ACTING USER.
    Unwired ⇒ None ⇒ a caller holding a reads payload REFUSES it stating
    `event_read_door_unwired` — keyed readings are never silently dropped
    (B2 §2 row OWED — see the function's own docstring).

  apps.metering.premises_owners.ensure_master_account_for_premises(
      actor, premises_id, payload) -> dict
  apps.metering.premises_owners.declare_premises_master_account(
      actor, premises_id, account_id | None) -> None
  apps.metering.premises_owners.link_owner_master_account(
      actor, owner_id, account_id | None) -> dict
  apps.metering.premises_owners.premises_master_account_link(
      premises_id) -> (account_id | None, source | None)
    `DEF-MET-6302` — the sample estate's OWNER ACCOUNTS. `premises` is
    metering's table (B2 r4), so metering opens the account through its own
    door and writes its own declaration; customers supplies the payload, tags
    the `accounts` row `is_sample` (BR-TEN-057 — only the owning module may)
    and RELEASES the declaration before removal, because
    `premises.master_account` is `PROTECT` and BR-TEN-061 removes customers
    first. Unwired ⇒ the block reports the absence BY NAME (BR-TEN-060) and
    seeds nothing (B2 §2 row OWED — see each function's own docstring).

  apps.metering.selectors.unit_ids_matching(term) -> list[str]
  apps.assets.selectors.unit_ids_for_asset_search(term) -> list[str]
  apps.assets.selectors.assets_on_unit(unit_id) -> list[dict]
    BR-CUS-053: the S17 search covers service address and meter #, neither of
    which is a customers column. Unwired ⇒ that search LEG returns nothing;
    the account-number and customer-name legs still work, so the search
    narrows rather than lying.

  apps.metering.selectors.premises_list(q=…) -> QuerySet[Premises]
    `CR-089` `PUJ-51` — an ADDRESS finds the accounts at it, the owner's
    account included. `unit_ids_matching` above walks the UNIT, so an account
    that names no unit (`BR-CUS-1010` — the owner's account is at an ADDRESS)
    could not be found by the building it stands on. Consumed lazily by
    `selectors.account_ids_at_matching_address`, which is also what payments
    and billing resolve for their own address leg. Unwired ⇒ that leg returns
    nothing, exactly as the unit leg above does.

  apps.tenancy.selectors.tenant_today() -> date
  apps.tenancy.selectors.tenant_timezone() -> ZoneInfo
  apps.tenancy.selectors.regional_settings() -> dict   (the tenant currency,
                                                        and its language)
    BR-TEN-043 event-time law + the CHAR(3) money partner (CLAUDE.md rule 2).
    ⊕ 2026-09-24 — `tenant_timezone` (`DEF-CUS-6433`): `tenant_today()` is one
    end of a date subtraction and a stored `datetime` is the other, so the AGE
    on `REQ-01` needs the ZONE as well as the day, from the same derivation.
    An account's currency is the TENANT's currency, never client input.
    ⊕ 2026-09-23 — `language` too: since 2026-10-29 (PO option B) the
    FALLBACK language of a message to a customer, whose own preferred language
    is asked first (`BR-NOT-006` amended). See `tenant_default_language` below.

  apps.rating.selectors.plan_ref(plan_id) -> {id, code, name, version} | None
    ⚠ **THIS ENTRY READ "NOT CONSUMED HERE, deliberately" UNTIL 2026-09-01, AND
    IT WAS THE REASONING THAT WAS WRONG RATHER THAN THE SENTENCE (DEF-2419).**
    It is kept and corrected rather than deleted, because the distinction it
    got wrong is the one every later reader needs.

    What it said: the account-side plan snapshot is `account_plan_assignments`
    (BR-CUS-029), it has no DDL in any signed document, therefore this module
    reads the unit's plan only to answer BR-MET-040 ("is there a plan at all?")
    and stores nothing about it.

    **The first half is still true and nothing here changes it.** No account
    plan snapshot is written, `record_plan_snapshot` still raises BR-CUS-029,
    and `account_detail_dict` still serves `plan: None` beside that rule id.

    **The second half conflated STORING with SHOWING.** Storing a snapshot on
    the account needs a table this repo does not have. Showing which plan the
    account is billed on needs no table at all — it is a read along keys the
    schema already carries: `accounts.unit_id` (the reviewed cross-module FK,
    B2 §2) → `units.rate_plan_id` → this function. The stated ground for
    withholding it was that an account's plan and its unit's "match only until
    the first override", and **there is no override and there cannot be one**:
    no column anywhere can record a plan for one account differing from its
    unit, so the divergence being guarded against has nowhere to be stored.

    Two PO rulings say so, three weeks apart. 2026-08-11: *"from unit you will
    derive the plan"* — which `services._account_and_unit_plan` and the whole
    change-plan wizard have followed ever since, leaving the account header as
    the one surface that had not. 2026-09-01, on DEF-2419: *"It should be
    foreign key - it should take it from Unit and display it there - that is
    important"*.

    So `plan_ref` IS consumed here, at two call sites and now a third:
    `services._account_and_unit_plan` (S23 change-plan), `services.
    plan_change_preview`, and `unit_plan_in_force` below, which is the read the
    account detail serves. See services.record_plan_snapshot() for the half
    that is still refused.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any


class SeamUnavailable(RuntimeError):
    """A seam this module must WRITE through is not published.

    Distinct from the ordinary degradation in this file. Every READ seam here
    answers None when its lane has not landed, because an absent figure renders
    an absent cell. A WRITE seam cannot do that: silently not-writing looks
    exactly like writing, and the caller records an act it never performed
    (DEF-708's shape).
    """


def resolve(module: str, attribute: str, kind: str = "services") -> Callable[..., Any] | None:
    """The owning module's callable, or None while its lane has not landed."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


# ── tenancy (event date + the tenant's one currency) ────────────────────────
def tenant_today() -> Any:
    """Today in the tenant's timezone (BR-TEN-020/043). The numbering kernel
    demands the event date explicitly — this module never reads a wall clock."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.tenant_today()


def tenant_timezone() -> Any:
    """The clock this utility is on — `tenant_today()`'s other half.

    ⚠ **ADDED FOR `DEF-CUS-6433`, AND THE REASON IS THE DEFECT ITSELF.** An AGE
    is a subtraction of two DAYS, and `tenant_today()` alone gives you only the
    left one: the right one is a stored `datetime`, and turning that into a day
    needs the same zone or the two halves of one sum are read on two clocks.
    That is exactly `DEF-094`'s shape one module over — a read and a write each
    correct on its own terms, disagreeing by a day — so this seam names
    tenancy's ONE derivation (`BR-TEN-081`) rather than letting a caller reach
    for `ZoneInfo` itself. B1 / `BR-TEN-013`: by name, through the seam, never
    by importing tenancy.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.tenant_timezone()


def tenant_holidays() -> frozenset[Any]:
    """The CURRENT tenant's public holidays, as real `date` objects.

    ⚠ **`BR-BIL-002`'s SEAM, NOT A NEW ONE.** Billing has counted business days
    against `holiday_calendars` since 2026-08-11 through
    `apps/billing/tenancy_seam.holiday_dates()`, and this is the same read from
    the other side of the boundary. Two reasons it is copied rather than
    imported: `apps.billing` is a neighbour and customers may not reach into it
    (B1 / `BR-TEN-013`), and that module's refusal raises `BillingConfigError`,
    which is billing's exception and has no business in a disconnection.

    ⚠ **THE CONVERSION IS THE POINT.** Tenancy publishes the `S63` card's
    payload, shaped for a screen, and its `date` is an ISO **string**:

        date(2026, 5, 25) in {"2026-05-25"}   ->   False

    So a caller handing tenancy's payload straight to a day-counter would skip
    **no holiday whatsoever**, silently, with every test still green. That is
    the exact mistake `apps/billing/tenancy_seam.py` was written to prevent, and
    the consequence here is worse than a late fee: an earliest-lawful-cut date
    computed one day early on a household's service.

    ⚠ **IT REFUSES RATHER THAN ANSWERING AN EMPTY SET** when tenancy publishes
    no read at all, because *unreachable* and *keeps no calendar* are different
    facts and only one of them is safe to compute a cut date on (hard-won law 3:
    the unsafe option must be the one you type). A tenant that genuinely keeps
    no holidays answers an empty frozenset from a WIRED seam and means it.
    """
    from apps.tenancy import selectors as tenancy_selectors

    read = getattr(tenancy_selectors, "holidays", None)
    if not callable(read):
        raise RuntimeError(
            "apps.tenancy.selectors.holidays is not published, so the tenant's "
            "public holidays cannot be read. This does NOT fall back to an empty "
            "calendar: a business-day count that skips no holiday puts the "
            "earliest lawful cut date EARLIER than the law allows, on the screen "
            "that authorises cutting somebody's service (PO ruling 2026-09-12, "
            "OQ-CUS-1810; the same posture BR-BIL-002 takes for the late-fee "
            "grace clock)."
        )
    out: list[Any] = []
    for row in read():
        value = row["date"] if isinstance(row, dict) else row
        if isinstance(value, date):
            out.append(value)
            continue
        if isinstance(value, str):
            try:
                out.append(date.fromisoformat(value))
                continue
            except ValueError as exc:
                raise ValueError(
                    f"the tenant holiday calendar carries {value!r}, which is not "
                    "an ISO date. Nothing is guessed: a day this seam cannot read "
                    "must not silently become a working day."
                ) from exc
        raise ValueError(
            f"the tenant holiday calendar carries a {type(value).__name__} where a "
            "date was expected. See apps/customers/seams.py::tenant_holidays."
        )
    return frozenset(out)


def tenant_collections_settings() -> dict[str, Any]:
    """The tenant's own `collections` rule page — `S70`, family `collections`.

    ⚠ **THE NOTICE PERIODS THE PO RULED ON 2026-09-12 ALREADY LIVED HERE, AND
    THAT IS WHY NOTHING NEW WAS BUILT FOR THEM.** Answer 6 was *"(b) A
    per-tenant setting, seeded with our three, that each utility sets to its own
    regulator's number"* — and `settings_families.COLLECTIONS` has carried
    `notice_tier_days = [10, 5]` and `final_notice_hours = 48` under
    `BR-PAY-017`, per tenant, on a screen, since the collections lane. Our
    three, seeded, editable per utility. Building a second home for them would
    have given one product two places a regulator's number lives, which is the
    duplication `BR-CUS-1020` refuses for identity and the PO's standing
    instruction of 2026-09-12 refuses generally (*build from the actual code,
    and do not create duplicate code*).
    """
    from apps.tenancy import selectors as tenancy_selectors

    # `settings_family` returns the MERGED flat document — the tenant's stored
    # values with each family's ratified seeded default filled in behind them
    # (`settings_families.merge`), so a parameter a tenant has never saved still
    # answers its seeded number rather than absent.
    return dict(tenancy_selectors.settings_family("collections"))


def service_request_default_target_days() -> int | None:
    """How many days after the request date an acknowledgement aims at.

    `DEF-CUS-10445` (PO 2026-10-22, *"Default 15 days"* and *"don't do any
    hardcoding"*). Tenancy's `service-requests` rule page, seeded 15 and edited
    on Settings → Reference data → Accounts → Service requests. Read through
    tenancy's published selector, never a constant here; `None` only if the
    stored value is not a whole number, which the family's validator refuses
    on save — the caller then leaves the date absent rather than guessing.
    """
    from apps.tenancy import selectors as tenancy_selectors

    value = tenancy_selectors.settings_family("service-requests").get(
        "service_request_default_target_days"
    )
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def tenant_currency() -> str | None:
    """The tenant's currency (CHAR(3)). One tenant = one currency (BR-TEN-021
    forward-only + the T4-22 currency-lock journey), so `accounts.currency` is
    DERIVED from it and is not an input field anywhere in this module."""
    from apps.tenancy import selectors as tenancy_selectors

    code = tenancy_selectors.regional_settings().get("currency")
    return str(code).upper() if code else None


def tenant_default_language() -> str | None:
    """The utility's default language — the FALLBACK language of every message
    to a customer.

    ⛔ **SUPERSEDED FOR MESSAGES 2026-10-29 (PO option B, decision log *"A
    message goes in the customer's preferred language"*).** PO, verbatim:
    *"Question: which language should messages be sent in? - B"*. A message
    (email, text, letter, in-app) now asks first for the ACCOUNT's
    `preferred_language` — read by `notifications.queue_document` from the
    account it names, or passed as `preferred_language=` for an applicant with
    no account yet — and falls back to THIS code only where the utility has not
    published that class in the customer's language
    (`notifications.message_language.language_for`). So writers still pass
    this as `language=`, and it now means *the fallback*. Worked: Rosa,
    Español, at an English-default utility → Springfield published a Spanish
    *Bill ready*, so her bill email is Spanish; no Spanish past-due reminder,
    so that one is English.

    (History, 2026-09-23 to 2026-10-29: `OQ-CUS-12619` (a), *"(a) Portal only;
    emails in English."* — every message went in this language and the
    account's drove the portal alone.)

    ⚠ **THE VARIANT MODEL IS UNTOUCHED — THIS ONLY CHANGES WHAT IS ASKED FOR.**
    The code is passed to `template_service.resolve` as the requested language,
    so a Spanish-default utility that published a Spanish variant still sends
    it, and one that did not falls back to its `default` variant — which is, by
    that model's own definition, *"the tenant's own default-language variant"*.
    A reprint still renders the language pinned on the row it reprints.

    **`None` when the utility has never set a language.** Passed as `None`, the
    resolver takes the `default` variant — the same answer, arrived at without
    a guess. `""` is not a language and travels as `None`.

    Read through tenancy's own published selector — the one `tenant_currency`
    above uses — so there is ONE place a utility's language is read from, the
    Settings → Regional row, and no second copy to drift from it.
    """
    from apps.tenancy import selectors as tenancy_selectors

    code = tenancy_selectors.regional_settings().get("language")
    return str(code) if code else None


# ── tenancy (the parked-wizard draft store — CR-035 / BR-SHL-048) ───────────
#
# ⚠ **`wizard_parks` IS TENANCY-HOSTED AND CUSTOMERS MAY NOT TOUCH IT.** The
# five parkable flows span TWO modules (customers and metering), so the table
# sits on the shell's scratch pad rather than in either one — `models.WizardPark`
# calls it the `user_preferences` posture, *"hosting ≠ owning"*. (It named
# `bell_events` alongside it until 2026-09-03; that table is gone — DEF-3422.)
# B1 / BR-TEN-013 therefore route every write through the OWNING module's own
# service function, and these three forwarders are that route. Nothing in
# `apps/customers/` imports `apps.tenancy.models` (G6 rule 4 forbids it) and
# nothing here re-implements a single line of `wizard_parks.py`.
#
# The ONE caller today is `sample_data.seed_sample_wizard_parks` — CR-035 step 6
# row 6, *"a seeded parked example, so the screen is not empty on a demo"*. The
# product's own park comes from the wizards' frontend through
# `POST /wizard-parks`, which never passes through this module.


def park_wizard_draft(actor: Any, payload: dict) -> Any:
    """Write one parked draft. BR-SHL-048: **one row, and nothing else moves.**"""
    from apps.tenancy import wizard_parks

    return wizard_parks.park(actor, payload)


def wizard_park_rows(*, flow: str | None = None) -> list:
    """Every parked draft in this tenant, newest first (tenant-scoped, RLS)."""
    from apps.tenancy import wizard_parks

    return wizard_parks.list_parks(flow=flow)


def wizard_park_queryset(*, flow: str | None = None):
    """The same drafts as a **LAZY QUERYSET** — for a list that pages in SQL.

    ⚠ **IT EXISTS BECAUSE `wizard_park_rows` MATERIALISES AND `NFR-3` FORBIDS
    THAT ON A LIST** (PO ruling 2026-09-19 — the Move-outs list shows the
    move-outs that have not finished yet, which are exactly these rows). The
    Move-outs tab pages a UNION of closed accounts and parked move-outs, and a
    `UNION` arm has to be a queryset: handed a list, the page would be sliced in
    Python after every parked draft in the tenant had been built. `wizard_parks
    .parks_queryset`'s own docstring carries that lesson under `DEF-SHL-5748`,
    which is the same defect one layer down.

    ⚠ **THE LIST FORWARDER IS KEPT AND IS NOT A DUPLICATE OF THIS.** Its caller
    deletes rows while iterating what it is handed (`sample_data
    ._remove_cr035_park`), which is safe over a list and safe over a queryset
    only by accident of the result cache. Two callers with opposite needs, two
    doors, one owning module — and neither re-implements a line of
    `wizard_parks.py` (B1 / BR-TEN-013; G6 rule 4 forbids the import).
    """
    from apps.tenancy import wizard_parks

    return wizard_parks.parks_queryset(flow=flow)


def backdate_wizard_park(park_id: Any, parked_at: Any) -> None:
    """FIXTURE ONLY — give a seeded draft a visible AGE. See the tenancy door's
    own docstring for why `auto_now_add` makes this necessary and why it is
    reachable from no route."""
    from apps.tenancy import wizard_parks

    wizard_parks.backdate_for_sample(park_id, parked_at)


def discard_wizard_park_for_sample(park_id: Any) -> None:
    """FIXTURE ONLY — the removal half of the sample block. The sample-removal
    contract takes no actor, so this reaches tenancy's unattributed door rather
    than `discard(actor, id)`, whose `@require_role` nothing here can satisfy
    honestly. See that door's own docstring."""
    from apps.tenancy import wizard_parks

    wizard_parks.discard_for_sample(park_id)


#: BR-PAY-013's threshold, and where it lives — B2 r14 #5 puts `nsf_privilege_n`
#: on the S70 collections rule page. Named as constants so the contract is
#: greppable from BOTH sides of the boundary: a string typed twice is a setting
#: that silently stops being read (the precedent `apps/payments/services.py`
#: sets for `allocation_class_order`).
NSF_PRIVILEGE_FAMILY = "collections"
NSF_PRIVILEGE_KEY = "nsf_privilege_n"


def nsf_privilege_threshold() -> int | None:
    """How many bounces trip the cash-only / no-autopay flag, for THIS tenant.

    BR-PAY-013: *"N NSFs (default 2, config)"*, and *config* is the whole point
    — US-PAY-009 TC-3 changes the tenant's N to 3 and requires a third NSF
    before the flag trips, *"config, not constant"*.

    **None means the setting could not be read, and it is never read as 2.**
    The ratified default lives once, in `apps.tenancy.settings_families`, and is
    merged in by tenancy's own read; a `2` substituted here would be a second
    copy of that default, free to drift from the number on the tenant's own
    screen. The caller reports the absence and flags nothing (`record_nsf`).
    """
    from apps.tenancy import selectors as tenancy_selectors

    values = tenancy_selectors.settings_family(NSF_PRIVILEGE_FAMILY)
    raw = values.get(NSF_PRIVILEGE_KEY)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):  # pragma: no cover - the family types it INTEGER
        return None


def validate_custom_data(
    entity: str,
    submitted: Any,
    *,
    screen: str | None,
    existing: Any = None,
    require_input: bool = True,
) -> dict:
    """The tenant's OWN field definitions, applied to a value blob (US-SHL-015).

    `apps.tenancy.services.validate_custom_data_for(entity, submitted)` is the
    contract: unknown keys are rejected, options are enforced, types are checked
    and a required field blocks save on an INPUT placement. It is a HARD import
    rather than a late-bound lookup on purpose — tenancy owns the registry, this
    module already imports tenancy selectors two functions up, and a soft
    fallback here would be the DEF-075 shape in its worst form: an unresolved
    seam would silently accept whatever the client sent into a jsonb column.

    A refusal is the caller's refusal — the catalog exception travels straight
    out, keyed `custom_data.<key>` (BR-SHL-037), so FormModal highlights the
    control through the path it already has.

    ⚠ **`screen` HAS NO DEFAULT, ON PURPOSE (`DEF-TEN-9157`).** A required
    field binds only on the screen it is typed in on, so every door says which
    screen its form is — `"S18"` for New account, `"S21"` for Account detail,
    `None` for a door that is not a screen. A default would let a new door
    forget, which is how New Account came to be refused over a field it never
    drew. `existing` makes the call an EDIT and returns the merged blob.
    """
    from apps.tenancy import services as tenancy_services

    return tenancy_services.validate_custom_data_for(
        entity,
        submitted,
        require_input=require_input,
        screen=screen,
        existing=existing,
    )


def custom_field_definitions(entity: str) -> list[dict[str, Any]]:
    """`CR-161-BRC10` W6 — the ACTIVE definitions for one record type (key,
    label, data type), for the approval review of a service request. A read of
    tenancy's cached, tenant-keyed registry; a deactivated field is absent
    (BR-TEN-050), which is how its answer stays on the request uncopied."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.custom_field_registry(entity)


def premises_custom_answers(premises_id: Any) -> dict[str, Any] | None:
    """`CR-161-BRC10` W6 — one premises' stored custom answers and its number,
    for the approval review's *Existing* column. Metering's own tenant-scoped
    row read (404-never-403 for another utility's id, HR-1). `None` when the
    door is unwired, which reads as *no target* — never as an empty premises."""
    fn = resolve("metering", "premises_row", kind="selectors")
    if fn is None:
        return None
    row = fn(premises_id)
    return {"premise_no": row.premise_no, "custom_data": dict(row.custom_data or {})}


def copy_premises_custom_answers(actor: Any, premises_id: Any, answers: dict[str, Any]) -> None:
    """`CR-161-BRC10` W6 — an approved service request's answers onto the
    premises, through METERING'S OWN EDIT DOOR (`update_premises`): metering
    validates them against the premises registry, MERGES them into what is
    stored, and writes its own `premises.updated` audit row. `custom_fields_
    screen=None` — an approval is not a screen the premises fields are typed
    on, so nothing is *required* of it; only the keys named move.

    Refuses loudly when the door is unwired: an approval that silently copied
    nothing would read as done (hard-won law 2)."""
    fn = resolve("metering", "update_premises")
    if fn is None:
        raise SeamUnavailable("metering.services.update_premises")
    fn(actor, premises_id, {"custom_data": answers}, custom_fields_screen=None)


def service_catalog_order() -> tuple[str, ...]:
    """The platform service catalog in CATALOG SORT ORDER (BR-TEN-025 closed
    set) — the order the S17 "Services" chips render in (prototype: E · W · S).

    Read-only probe on the RLS-exempt platform table: tenancy's own
    `services_overview()` is the ordered selector, but it calls back into this
    module for BR-TEN-026 counts, so using it to order a list row would make
    every row re-count every service. Same Eng disposition metering records for
    `service_row_id` — a read, never a write, on a table with no tenant column.
    """
    from django.apps import apps as django_apps

    model = django_apps.get_model("tenancy", "Service")
    return tuple(
        model.objects.filter(active=True).order_by("sort", "code").values_list("code", flat=True)
    )


def enabled_service_codes() -> tuple[str, ...]:
    """What THIS TENANT actually sells, in the catalogue's own order.

    `service_catalog_order` above answers a different question — the whole
    PLATFORM catalogue, eleven codes, whatever a utility switched on — and the
    two are easy to confuse. This one is `tenancy.selectors.
    enabled_service_codes`, the read tenancy already publishes to the ledger and
    to metering, and it filters on `tenant_services.enabled` AND on the
    catalogue row being active, so it and `services_overview()` cannot disagree
    (`DEF-324`).

    ⚠ **NEVER DERIVED FROM A LITERAL LIST OF THE ELEVEN.** `BR-RAT-024` has
    moved from six services to ten to eleven, and the lists that named them
    individually are still being found — which is the whole of `G47`. The only
    caller today is the sample seeder (`sample_data._cr030_services_for`), which
    asks it so that a seeded service request asks for what its utility runs
    rather than for whatever the demo fixture happens to name.

    Unwired ⇒ empty tuple, and the caller then seeds no service rather than
    guessing one.
    """
    try:
        from apps.tenancy import selectors as tenancy_selectors
    except ImportError:  # pragma: no cover - the app package always imports
        return ()
    read = getattr(tenancy_selectors, "enabled_service_codes", None)
    if not callable(read):  # pragma: no cover - defensive
        return ()
    return tuple(str(code) for code in read())


def tenant_languages() -> tuple[str, ...]:
    """BR-TEN-042's seeded language set, for validating BR-CUS-064's
    `preferred_language`. Unwired ⇒ empty tuple, and the caller accepts the
    value as free text rather than inventing a vocabulary of its own."""
    try:
        from apps.tenancy import services as tenancy_services
    except ImportError:  # pragma: no cover - defensive
        return ()
    return tuple(getattr(tenancy_services, "SEED_LANGUAGES", ()) or ())


# ── metering (units, their service points, their address) ───────────────────
def unit_row(unit_id: Any) -> Any:
    """The metering `units` row, through its owning module's selector.

    Raises the same 404-never-403 refusal metering raises for an id belonging
    to another tenant (HR-1 / 11b G4) — the boundary is not re-implemented."""
    from apps.metering import selectors as metering_selectors

    return metering_selectors.unit_row(unit_id)


def unit_dict(unit: Any) -> dict[str, Any]:
    from apps.metering import selectors as metering_selectors

    return metering_selectors.unit_detail_dict(unit)


def service_points_for(unit_id: Any) -> list[dict[str, Any]]:
    """The active service points at a unit — the services an account there
    takes (US-CUS-003 §5: "one SA row per active service")."""
    from apps.metering import selectors as metering_selectors

    return list(metering_selectors.service_points_for(unit_id))


def service_points_for_units(unit_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """The plural of `service_points_for` — one call for a whole page (DEF-2723).

    `{}` while metering is absent, which is the same answer the singular's `[]`
    gave: no points are known, and none is invented."""
    fn = resolve("metering", "service_points_for_units", kind="selectors")
    return dict(fn(unit_ids)) if fn is not None else {}


def unit_refs(unit_ids: Any) -> dict[str, dict[str, Any]]:
    """The plural of `unit_row` + `unit_dict`, reduced to the four fields a LIST
    row draws (DEF-2723).

    ⚠ **ABSENCE REPLACES THE REFUSAL, AND THAT IS DELIBERATE.** `unit_row`
    raises metering's 404-never-403 for an id belonging to another tenant; a
    batch read has no single subject to refuse about, so a unit this tenant
    cannot see is simply not in the map — which the caller already handles,
    because that is what `_premise_cell` did with the `NotFoundError` it caught.
    """
    fn = resolve("metering", "unit_refs", kind="selectors")
    return dict(fn(unit_ids)) if fn is not None else {}


def premises_refs(premises_ids: Any) -> dict[str, dict[str, Any]]:
    """The plural of `premises_ref` (DEF-2723) — same fields, same absence rule."""
    fn = resolve("metering", "premises_refs", kind="selectors")
    return dict(fn(premises_ids)) if fn is not None else {}


def premises_services_for(premises_ids: Any) -> dict[str, list[str] | None]:
    """`BR-CUS-1093` — the services each of these buildings offers.

    THE CONTRACT (metering's own docstring is the authority):

        apps.metering.selectors.premises_services_for(premises_ids)
            -> {premises_id: ["water", …] | None}

    A MASTER account's service list is a READ of this (`BR-CUS-1093`, PO ruling
    2026-09-23) because the account hangs off the ADDRESS and names no unit
    (`BR-CUS-1010`), so `service_points_for(account.unit_id)` reaches nothing
    for it. **Nothing is stored and nothing is backfilled** — `BR-CUS-672`'s
    *"every inherited fact is held by reference, never copied"*.

    ⚠ **`None` AND `[]` ARE DIFFERENT ANSWERS AND BOTH SURVIVE THE SEAM**
    (`DEF-762`): nobody was ever asked, versus a clerk answering *this address
    offers nothing*. The chips render the same for both — a chip row has no way
    to say *unasked* — but the distinction is what a later screen would need,
    and collapsing it in a seam is where it would be lost.

    ⚠ **UNWIRED ⇒ `{}`**, which reads as *no premises is known* and is the same
    answer `premises_refs` above gives. A master account then draws the
    agreement services it already had and nothing is invented in metering's
    absence — never an empty list presented as *this building offers nothing*.
    """
    fn = resolve("metering", "premises_services_for", kind="selectors")
    return dict(fn(premises_ids)) if fn is not None else {}


def reads_for_unit(unit_id: Any, *, on: Any = None, since: Any = None) -> dict[str, Any] | None:
    """The unit's committed read heads, per meter and register — THE seam
    `move_reads.py` §4 named as missing (CR-038 W9 task 2).

    THE CONTRACT (metering's own docstring is the authority):

        apps.metering.selectors.reads_for_unit(unit_id, on=date|None,
                                               since=date|None)
            -> {"unit_id", "as_of",
                "meters": [{"asset_id", "asset_no", "type", "qualifier",
                            "latest_read_at": "YYYY-MM-DD" | None,
                            "registers": [{"read_id", "channel",
                                           "current_value",         # THE READING
                                           "consumption", "unit",   # rule 3
                                           "read_at", "source", "lifecycle",
                                           "estimated", "estimation_method"}]}]}

    ⚠ **`current_value` IS THE READING AND `consumption` IS THE USAGE, AND THEY
    ARE INDEPENDENTLY NULL** (`DEF-CUS-5910`, `DEF-MET-5862`). An OPENING read
    has a reading and no usage — nothing before it to subtract from; an ESTIMATE
    has a usage and no reading — nobody read the dial (`BR-MET-028`). A consumer
    drawing a column headed READING must take `current_value`; taking
    `consumption` makes a register a clerk really read look unread.

    Committed lineage HEADS only (BR-MET-016/053 — superseded rows are
    invisible), tenant-scoped on the owning side, quantities WITH their unit
    (hard rule 3), `on` as-of capping (BR-TEN-043). Until this existed the
    move worklists' READS / FINAL READ cells and the `FINAL READS DUE` tile
    could only state an absence; `move_reads.unit_reads_cell` is the consumer.

    **The KIND is named explicitly** — `selectors`, metering's read side — the
    DEF-035/DEF-127 lesson: two words wrong there and a guard "passes" without
    ever having run.

    **`None` means the read is UNWIRED — never "no reads."** A deployment where
    metering publishes no such selector cannot answer, and the caller states
    that (`move_reads.READS_NOT_READABLE`) rather than scoring `due`, `taken`
    or a fabricated 0 (DEF-075 / DEF-127). A unit with no meters or no reads
    is a RESOLVED answer inside the returned mapping, not a None.

    ⚠ **B2 §2 INTERFACE ROW OWED.** Cross-module reads are the reviewed
    interface set and this seam's row is not yet in the register — this lane
    works in an isolated worktree and may not edit `04-docs/`; the row is
    FLAGGED in the lane report for the merging session's central write-back.
    """
    fn = resolve("metering", "reads_for_unit", kind="selectors")
    if fn is None:
        return None
    # `since` (DEF-CUS-9726) is passed only when asked, so a deployment whose
    # selector predates it answers every other caller unchanged.
    return fn(unit_id, on=on, since=since) if since is not None else fn(unit_id, on=on)


def latest_read_dates_for_units(unit_ids: Any) -> dict[str, dict[str, Any]] | None:
    """`reads_for_unit`'s `latest_read_at` per meter, for MANY units at once —
    `CR-171-BRC10` P1.04 (the Move-ins list's *Waiting on a read* filter and
    tile, which must judge every live move-in and not one page of them).

        apps.metering.selectors.latest_read_dates_for_units(unit_ids)
            -> {unit_id: {"unit_id", "as_of": None,
                          "meters": [{"asset_id", "asset_no", "type",
                                      "qualifier", "registers": [],
                                      "latest_read_at"}]}}

    A subset of `reads_for_unit`'s shape, so `move_reads.unit_reads_cell` reads
    it unchanged. **`None` means UNWIRED, never "no reads"** — the same
    contract as `reads_for_unit` above, and the caller states it.
    """
    fn = resolve("metering", "latest_read_dates_for_units", kind="selectors")
    return fn(list(unit_ids)) if fn is not None else None


def commit_event_reads(actor: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    """The metering EVENT-READS write door — CR-038 W9 task 1 (BR-MET-128 ·
    BR-CUS-021 · BR-MET-129).

    THE CONTRACT (metering's own docstring is the authority):

        apps.metering.services.commit_event_reads(actor, {
            "event":  "move_in" | "move_out" | "transfer" | "disconnect"
                      | "new_connect",                  # BR-MET-128's five
            "reads":  [{"meter_no", "read_at",
                        "value" | "estimate": true, "channel"?}, ...],
            "context"?: {...}})                          # audit context only
            -> {"event", "batch_id", "posted": [read dicts], "posted_reads",
                "estimates": [...], "warnings": [{row_no, meter_no, rules}]}

    BR-CUS-021, verbatim: initial/final reads are *"committed via the metering
    service (append-only BR-MET-017)"* — customers NEVER writes `meter_reads`
    (B1/B8); the wizard payloads travel through this one door and the SAME
    stage→validate→commit pipeline every S28 row takes. BR-MET-129 semantics
    live on the metering side: WARNED rows post with their flags; ERRORS raise
    with named rows and nothing persists. The committed read carries the EVENT
    and the ACTING USER (BR-MET-128), both stamped at insert.

    **The KIND is named explicitly** — `services`, metering's write side — the
    DEF-035/DEF-127 lesson, same as `reads_for_unit` above names `selectors`.

    **`None` means the door is UNWIRED — never "committed."** A deployment
    where metering publishes no such service cannot commit event reads, and a
    caller holding a reads payload must REFUSE it stating that absence
    (`event_read_door_unwired`) rather than silently dropping readings a clerk
    keyed (DEF-075/DEF-127: a dropped write is worse than a refused one).

    ⚠ **B2 §2 INTERFACE ROW OWED** — same as `reads_for_unit`'s: cross-module
    calls are the reviewed interface set, this lane may not edit `04-docs/`,
    and the row is FLAGGED in the W9 lane report for central write-back.
    """
    fn = resolve("metering", "commit_event_reads", kind="services")
    return fn(actor, payload) if fn is not None else None


def ensure_master_account_for_premises(
    actor: Any, premises_id: Any, payload: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """`BR-MET-1030` / `BR-MET-1181` — the owner's account AT AN ADDRESS, opened
    if it is not there already, with `premises.master_account_id` declared in the
    same transaction.

    THE CONTRACT (`apps/metering/premises_owners.py`'s own docstring is the
    authority):

        apps.metering.premises_owners.ensure_master_account_for_premises(
            actor, premises_id, {"account_type", "opened_at"?, "contact"?,
                                 "customer"?})
            -> {"created": bool, "account_id": str, "owner_id": str | None,
                "owner_linked": bool, "reason": str}

    ⛔ **THIS IS NOT CUSTOMERS WRITING METERING'S TABLE, AND THE DIRECTION IS THE
    WHOLE POINT.** `premises` is metering's (B2 r4), so metering writes it —
    through its own role-gated door, under its own audit row. What comes BACK
    across the boundary is an account id. The door then reaches
    `customers.import_writer.create_master_account_from_import` for the account
    itself, so the round trip ends at customers' own `create_master_account` with
    `BR-CUS-017`'s family, `BR-CUS-1011`'s one-owner-account-per-address and
    `BR-CUS-1024`'s identity guard all intact. **There is no second creation path
    and this seam does not become one.**

    **The KIND is named explicitly** — `premises_owners`, the module that owns
    this door — the DEF-035/DEF-127 lesson, exactly as `commit_event_reads`
    above names `services`.

    **`None` means the door is UNWIRED — never "opened".** A caller must then
    report the absence by name (BR-TEN-060) rather than reporting a seeded
    estate it did not seed.

    ⚠ **B2 §2 INTERFACE ROW OWED**, the same standing note `commit_event_reads`
    and `reads_for_unit` carry: a cross-module call is the reviewed interface
    set and this lane may not edit `04-docs/`.
    """
    fn = resolve("metering", "ensure_master_account_for_premises", kind="premises_owners")
    return fn(actor, premises_id, payload or {}) if fn is not None else None


def declare_premises_master_account(actor: Any, premises_id: Any, account_id: Any) -> bool:
    """`BR-MET-1181` — this ADDRESS names that account as its owner's, or, with
    `account_id=None`, stops naming one.

    THE CONTRACT:

        apps.metering.premises_owners.declare_premises_master_account(
            actor, premises_id, account_id | None) -> None

    **TWO CALLERS, AND THEY ARE OPPOSITE ENDS OF THE SAME LIFECYCLE.**
    `sample_owner_accounts.seed_sample_owner_accounts` declares the link for an
    address whose account already existed before `BR-MET-1181` was ruled — the
    `ensure` door above returns that account and does NOT declare it
    (`DEF-MET-6303`) — and `sample_data.remove_sample_records` RELEASES every
    sample declaration before deleting the accounts, because
    `premises.master_account` is `PROTECT` and BR-TEN-061 removes customers
    BEFORE metering. Without the release those accounts would be retained under
    customers' generic *"it has bills or payments against it"* sentence, which
    would be false.

    Returns True when the door was reached, False when it is unwired — a caller
    that could not release a link must say so rather than delete blindly.
    """
    fn = resolve("metering", "declare_premises_master_account", kind="premises_owners")
    if fn is None:
        return False
    fn(actor, premises_id, account_id)
    return True


def link_owner_master_account(actor: Any, owner_id: Any, account_id: Any) -> bool:
    """`BR-MET-400` — the OWNER RECORD's own declaration of the account it is
    billed through, or, with `account_id=None`, its release.

    THE CONTRACT:

        apps.metering.premises_owners.link_owner_master_account(
            actor, owner_id, account_id | None) -> dict

    ⚠ **IT IS A SECOND COLUMN AND NOT A SECOND COPY.** `premises.master_account_
    id` says *this ADDRESS's owner holds that account*; this one says *this
    PARTY is billed through it*, and metering writes both, in one transaction,
    naming one account (`_link_created_master_account`). Both are `PROTECT`, so
    **removal has to release both** — releasing only the address left two seeded
    accounts held by their owner records and RETAINED under a reason that was not
    theirs (measured on a live clone, 2026-09-23: `AC-2026-00053` and
    `AC-2026-00054`).

    Its own docstring already rules the `None` case a first-class act — *"Passing
    `None` CLEARS the link, which is a real act a clerk may need (an account
    closed, the wrong one picked) and is audited like any other"* — so this asks
    for nothing the door does not already offer.

    Returns True when the door was reached, False when it is unwired.
    """
    fn = resolve("metering", "link_owner_master_account", kind="premises_owners")
    if fn is None:
        return False
    fn(actor, owner_id, account_id)
    return True


def premises_master_account_link(premises_id: Any) -> tuple[Any, str | None]:
    """`BR-MET-1181` — *does this address already name an owner's account, and
    which declaration said so?*

    `(None, None)` where neither declaration names one, and the same `(None,
    None)` while the door is unwired: both mean *nothing here says who owns this
    address*, which is the honest answer in both worlds. It is a READ of
    metering's own ruled precedence and never a second copy of it — a copy here
    would eventually disagree about who gets billed.
    """
    fn = resolve("metering", "premises_master_account_link", kind="premises_owners")
    return fn(premises_id) if fn is not None else (None, None)


def premises_ref(premises_id: Any) -> dict[str, Any]:
    """One premises resolved for the BR-CUS-068 master-account path: id,
    address, and the OWNER/MANAGER who becomes the payer (PO 2026-08-22:
    "payer = the premises' owner/manager").

    Raises metering's own 404-never-403 for a cross-tenant or unknown id
    (HR-1) — the boundary is not re-implemented."""
    from apps.metering import selectors as metering_selectors

    row = metering_selectors.premises_row(premises_id)
    return {
        "id": str(row.id),
        "premise_no": row.premise_no,
        "address_line": row.address_line,
        "owner_manager": row.owner_manager,
    }


def premises_locality(premises_id: Any) -> dict[str, Any] | None:
    """`BR-MET-1161` — town, state and postcode, read from the one home.

    The account's service locality is the PREMISES' locality; it is not stored
    on the account and never was worth storing. `None` while metering cannot
    answer, which reads as *nobody recorded it* — the same thing the screen
    already draws for a premises whose city is blank.
    """
    fn = resolve("metering", "premises_locality", kind="selectors")
    return fn(premises_id) if fn is not None else None


def envelope_addresses(*, unit_ids: Any = (), premises_ids: Any = ()) -> dict[str, dict] | None:
    """`BR-MET-1161` — the SERVICE ADDRESS as envelope lines (`DEF-PAY-6342`).

    Metering's `envelope_addresses`: four discrete columns of the premises plus
    the unit's LABEL, for many units and premises in two statements at most.
    It is what lets `selectors.delivery_recipients_for_account` do what B2 §2
    has always said an absent mailing row means — *same as service* — instead of
    queueing the letter unaddressed.

    ⚠ **`None` MEANS METERING CANNOT ANSWER, AND IT IS NOT AN EMPTY MAP.** The
    caller turns `None` into `recipient_not_resolvable` (a fact about the
    PLATFORM) and an answered-but-blank street into `no_postal_address` (a fact
    about the PROPERTY). Merging the two is the error `BR-BIL-036` exists to
    prevent, so they are kept apart here as well.
    """
    fn = resolve("metering", "envelope_addresses", kind="selectors")
    if fn is None:
        return None
    return fn(unit_ids=list(unit_ids or ()), premises_ids=list(premises_ids or ()))


def owner_master_account_for_premises(premises_id: Any) -> Any:
    """DEF-650 / BR-MET-400 — *Premises → owner → master account*, DECLARED.

    **PO 2026-08-27:** *"Bascially Premises -> owner = Master account"*. This is
    the read that replaced `master_account_for`'s walk over the premises' common
    areas; the account id comes back, and nothing about the master is inferred
    from the shape of the building any more (decision 4, retired not fallback).

    `None` while metering cannot answer, which reads exactly like *no owner is
    declared* — and the two want the same behaviour: no master is named, and no
    party is guessed at in its place.
    """
    fn = resolve("metering", "owner_master_account_for_premises", kind="premises_owners")
    return fn(premises_id) if fn is not None else None


def premises_ids_owned_by_account(account_id: Any) -> list[str]:
    """The inverse of the read above: every premises whose DECLARED owner is
    billed through this account.

    `sub_accounts_for_master` needs it because a master's children are the
    occupants of the premises it OWNS, and under the ruling that is a declared
    fact rather than a property of the unit the account happens to anchor on.
    """
    fn = resolve("metering", "premises_ids_owned_by_account", kind="premises_owners")
    return list(fn(account_id)) if fn is not None else []


def common_area_units_for_premises(premises_id: Any) -> list[dict[str, Any]]:
    """The premises' ACTIVE common-area units (BR-MET-101's flag), through the
    owning module's selectors — the attachment set BR-CUS-068's master account
    covers. Soft-deleted units are excluded: a deactivated unit is not
    attachable (BR-CUS-020's posture, applied to the master path).

    Ordered by (label, id) so the ANCHOR choice — the master row's `unit_id`
    points at the FIRST — is deterministic (decision log 2026-08-22)."""
    from apps.metering import selectors as metering_selectors

    rows = metering_selectors.units_list(filters={"premises_id": premises_id})
    kept = [row for row in rows if row.is_common_area and row.deleted_at is None]
    kept.sort(key=lambda row: ((row.label or ""), str(row.id)))
    return [metering_selectors.unit_detail_dict(row) for row in kept]


def service_point_ref(service_point_id: Any) -> dict[str, Any] | None:
    """One service point resolved to `{id, unit_id, service}` — the service
    code behind a `service_agreements` row (BR-TEN-026's live count)."""
    fn = resolve("metering", "service_point_ref", kind="selectors")
    return fn(service_point_id) if fn is not None else None


def service_points_queryset() -> Any:
    """Metering's service points as a LAZY queryset, or None while metering
    publishes none — correlated as a subquery by `active_account_counts`
    (`DEF-TEN-8731`), so no point id is read into Python."""
    fn = resolve("metering", "service_points_queryset", kind="selectors")
    return fn() if fn is not None else None


def service_codes_by_ids(service_ids: Any) -> dict[str, str]:
    """`{service id: code}` — metering's catalog lookup, `{}` while unwired."""
    fn = resolve("metering", "service_codes_by_ids", kind="selectors")
    return dict(fn(service_ids)) if fn is not None else {}


def service_codes_for_points(service_point_ids: Any) -> dict[str, str | None]:
    """MANY service points resolved to their service codes in one pass — the
    plural of `service_point_ref` above, published by metering for DEF-1549.

    `{}` while metering is absent, which is the same answer the singular's
    `None` gave the one caller (`active_account_count` then counts nobody for
    that service, rather than guessing)."""
    fn = resolve("metering", "service_codes_for_points", kind="selectors")
    return dict(fn(service_point_ids)) if fn is not None else {}


def unit_ids_matching(term: str) -> list[str]:
    """BR-CUS-053 search leg: service address / premise / unit label."""
    fn = resolve("metering", "unit_ids_matching", kind="selectors")
    return list(fn(term)) if fn is not None else []


def move_in_unit_queryset(term: str, *, also_unit_ids: Any = None) -> Any:
    """`DEF-CUS-10190` — every live unit the move-in search may list, LAZY
    (metering matches its own columns; `None` while metering is unwired, so
    the caller can say *nobody could be asked* rather than *no unit*)."""
    fn = resolve("metering", "move_in_unit_queryset", kind="selectors")
    return None if fn is None else fn(term, also_unit_ids=also_unit_ids)


def assets_on_units(unit_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """The assets standing on each of MANY units, three queries (assets owns
    it). `{}` while assets is unwired: no meter is named, none invented."""
    fn = resolve("assets", "assets_on_units", kind="selectors")
    return dict(fn(list(unit_ids))) if fn is not None else {}


def premises_ids_matching(term: str) -> Any:
    """`CR-089` `PUJ-51` search leg: the PROPERTIES whose text matches.

    ⚠ **THIS RETURNS A LAZY QUERYSET OF IDS, NOT A LIST, AND THAT IS THE WHOLE
    POINT.** `unit_ids_matching` above materialises every matching unit id into
    Python so its caller can OR them into a `Q`; at the top of the customer band
    an address like *Main* matches thousands of units and that list is built,
    shipped and re-parsed on every keystroke. Handed to `Q(premises_id__in=…)`
    unevaluated, this renders instead as a nested SQL subquery inside the list's
    own `WHERE`, so the address leg costs the request **no extra round trip at
    all** — the same discipline `selectors._account_ids_by_customer_no` records
    for the customer-number leg, and `NFR-3`'s reason for existing.

    **The MATCH is metering's own and is deliberately not re-stated here.**
    `premises_list(q=…)` is what the Properties screen searches with — address
    line, town, property number and owner — so *does this property match what I
    typed* has ONE answer in the product rather than one per screen (hard-won
    law 1). A second predicate written here would be free to disagree with the
    Properties list about the same building.

    `None` — never an empty queryset — while metering publishes no list: the
    caller can then tell *no property matches* from *nobody could be asked*, and
    an unreachable seam reports rather than answering zero.
    """
    fn = resolve("metering", "premises_list", kind="selectors")
    if fn is None:
        return None
    # `.order_by()` clears the screen sort `premises_list` applies for S14: an
    # ORDER BY inside an `IN (…)` subquery buys nothing and costs a sort.
    return fn(q=term).order_by().values_list("id", flat=True)


def unit_id_for_reference(ref: str) -> str | None:
    """BR-CUS-047: resolve the import template's `unit_ref` column against
    EXISTING units only — "1408 Elm Street · Unit A", a unit_no or a uuid.

    An unmatched reference is a ROW ERROR for the caller, never an auto-created
    premises or unit: the migration order is Premises → Units+Plans → Assets →
    Accounts, and a unit conjured out of a spreadsheet cell would carry no
    plan, no service points and no meter — an account on it could never be
    billed, and nobody would find out until the first run.

    This is the SAME metering selector the S52 asset import resolves
    (`apps/assets/services._resolve_unit_ref`). One reference grammar for the
    product, not one per importer."""
    fn = resolve("metering", "unit_id_for_reference", kind="selectors")
    return fn(ref) if fn is not None else None


# ── DEF-CUS-6350 · is this address already in Premises? (metering answers) ──
#
# ⚠ **THE APPROVE WINDOW ASKS; METERING DECIDES.** A new connection creates a
# premises at the New connect wizard's last button, which is metering's write
# (`BR-MET-112`), so *"is this address already on file?"* is metering's
# question and `apps/metering/address_match.py` holds the ONE answer. These are
# the doors to it; nothing here compares two addresses itself.
#
# ⚠ **`None` MEANS NOBODY COULD BE ASKED, NEVER "NOT FOUND".** The caller turns
# an unreachable matcher into a condition that says so — refusing to certify an
# address it could not check — rather than reading silence as *not in Premises*
# (the read-seam posture this file already takes, pointed the safe way).
def premises_matching_address(
    address_line: Any, *, city: Any = None, postal_code: Any = None
) -> dict[str, Any] | None:
    fn = resolve("metering", "premises_matching_address", kind="address_match")
    if fn is None:
        return None
    return dict(fn(address_line, city=city, postal_code=postal_code))


def premises_label(premises_id: Any) -> dict[str, Any] | None:
    fn = resolve("metering", "premises_label", kind="address_match")
    return fn(premises_id) if fn is not None else None


def same_place(line_a: Any, line_b: Any, **parts: Any) -> str | None:
    """`exact` · `near` · `none` for two addresses — metering's comparison."""
    fn = resolve("metering", "same_place", kind="address_match")
    return fn(line_a, line_b, **parts) if fn is not None else None


def open_builds_for_requests(request_ids: Any) -> dict[str, dict[str, Any]] | None:
    fn = resolve("metering", "open_builds_for_requests", kind="address_match")
    return dict(fn(request_ids)) if fn is not None else None


def builds_for_requests(request_ids: Any) -> dict[str, dict[str, Any]]:
    """`{request_id: {id, connection_no, state}}` — the build each application
    raised, in any state. `{}` while metering is absent: no build is named, and
    none is invented."""
    fn = resolve("metering", "builds_for_requests", kind="address_match")
    return dict(fn(request_ids)) if fn is not None else {}


def units_at_premises_count(premises_id: Any) -> int | None:
    fn = resolve("metering", "units_at_premises_count", kind="address_match")
    return int(fn(premises_id)) if fn is not None else None


def premises_account_kind(premises_id: Any) -> str | None:
    """`CR-162-BRC10` (Q1) — the account type this property's TYPE takes:
    `master`, `regular`, or `None` (a type nobody has answered yet, or none);
    the caller falls back to counting homes. Metering owns the setting."""
    fn = resolve("metering", "premises_account_kind", kind="premises_capacity")
    return fn(premises_id) if fn is not None else None


def unit_build_services(unit_id: Any) -> list[dict[str, Any]]:
    """`CR-162-BRC10` — the services a live New Connection provides at this
    unit, each with its activation moment or `None` while it waits. `[]` when
    no build touched the unit, or when metering is unwired (then no window is
    subtracted — the pre-CR-162 behaviour, stated rather than silent)."""
    fn = resolve("metering", "unit_build_services", kind="premises_capacity")
    return list(fn(unit_id)) if fn is not None else []


def units_build_services(unit_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """`unit_build_services` for a whole bulk-Check batch, in one query."""
    fn = resolve("metering", "units_build_services", kind="premises_capacity")
    return dict(fn(unit_ids)) if fn is not None else {}


def unit_not_yet_active(unit_id: Any) -> dict[str, Any] | None:
    """`CR-162-BRC10` — `None` when the unit may be moved into; otherwise
    `{connection_id, connection_no}` of the New Connection still waiting on
    approval for it (metering owns the answer)."""
    fn = resolve("metering", "unit_not_yet_active", kind="premises_capacity")
    return fn(unit_id) if fn is not None else None


def premises_status(premises_id: Any) -> str | None:
    """`CR-162-BRC10` — the premises' stored status (`pending` while the New
    Connection that created it has not been approved)."""
    fn = resolve("metering", "premises_status", kind="premises_capacity")
    return fn(premises_id) if fn is not None else None


# ── assets (the meter # the S17 search covers, and the S21 meters cell) ─────
def unit_ids_for_asset_search(term: str) -> list[str]:
    """BR-CUS-053 search leg: meter #."""
    fn = resolve("assets", "unit_ids_for_asset_search", kind="selectors")
    return list(fn(term)) if fn is not None else []


def assets_on_unit(unit_id: Any) -> list[dict[str, Any]]:
    fn = resolve("assets", "assets_on_unit", kind="selectors")
    return list(fn(unit_id)) if fn is not None else []


# ── ledger (WHAT THE CUSTOMER OWES — DEF-127) ───────────────────────────────
#: The ledger's published per-account AR derivation, named as constants so the
#: contract is greppable from BOTH sides of the boundary. `apps/reports/api.py`
#: already reads this module by name, which is why `reporting` is the kind
#: rather than `selectors` — it is where the ledger derives money and the one
#: place `ar_control`, `accounts_owing` and this read all come from.
AR_POSITIONS_MODULE = "ledger"
AR_POSITIONS_READ = "ar_positions"
AR_POSITIONS_KIND = "reporting"


class ArPositions:
    """What the LEDGER says these accounts owe — or the fact that it cannot say.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-127 — AN UNWIRED SEAM REPORTS. IT NEVER ANSWERS 0.              ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `accounts.balance` is a CACHE (BR-CUS-015, and B2's own column comment says
    the ledger is the source of truth) and **nothing in this product has ever
    written it**. Customers served it anyway, so on 2026-08-15 a browser found
    account `E2E-10001` holding an ISSUED, UNPAID **108.88** — the books said
    `1200 AR` debit 108.880000 and the finance KPI said `still_owed
    108.880000` — while S17 rendered the row as **$0.00** and the header as
    **Outstanding $0.00**. A customer who owed money was told they owed nothing,
    on the one screen a clerk opens to find out.

    The lesson this class encodes is not "read the ledger". It is that **the
    absence of an answer must not be spelled the same way as zero**. A cache
    nobody fills reads 0.00; an unresolved seam that returned 0.00 would read
    0.00; and money owed reads 0.00 only when it is actually nil. So
    `amount_for` returns `None` — not `Decimal("0")` — whenever the books could
    not be asked, and every surface built on it renders an absence with a
    reason instead of a figure a customer would act on.

    `positions is None` means one of two things and `unavailable` says which:
    the ledger module published no `ar_positions` (a partial deployment), or it
    published one that refused (no AR designation, or DEF-081's mixed book).
    """

    __slots__ = ("positions", "currency", "basis", "unavailable")

    def __init__(
        self,
        *,
        positions: dict[str, Any] | None,
        currency: str | None = None,
        basis: str | None = None,
        unavailable: tuple[dict[str, Any], ...] = (),
    ) -> None:
        self.positions = positions
        #: DEF-099 / CLAUDE.md rule 2 — the CHAR(3) the figures ARE, derived by
        #: the ledger from the entries it summed. Never a label applied here.
        self.currency = currency
        self.basis = basis
        self.unavailable = unavailable

    @property
    def available(self) -> bool:
        return self.positions is not None

    def amount_for(self, account_id: Any) -> Any:
        """This account's position, or **None when the books cannot be asked**.

        A present `positions` map with no row for this account IS zero: once the
        tenant has an AR account, "nothing was ever posted for this customer" is
        a derived answer and not a gap. The whole distinction DEF-127 turns on
        lives in the line above it.
        """
        if self.positions is None:
            return None
        return self.positions.get(str(account_id), Decimal("0"))


#: The refusal, built once, so every caller reports the same sentence.
AR_POSITIONS_UNWIRED: tuple[dict[str, Any], ...] = (
    {
        "code": "ledger_publishes_no_per_account_ar_position",
        "br_ref": "BR-CUS-015 · BR-REP-002 · DEF-127",
        "detail": "the ledger module publishes no "
        f"`apps.{AR_POSITIONS_MODULE}.{AR_POSITIONS_KIND}.{AR_POSITIONS_READ}`, so what this "
        "customer owes cannot be read from the books. Reported rather than answered 0.00: "
        "`accounts.balance` is a cache nothing writes and serving it told a customer owing "
        "108.88 that their balance was zero (DEF-127). The screen shows an absence with this "
        "reason; it never shows a figure nobody derived.",
        "wanted_reads": (
            f"apps.{AR_POSITIONS_MODULE}.{AR_POSITIONS_KIND}.{AR_POSITIONS_READ}"
            "(account_ids=..., as_of=...) -> "
            "{basis, currency, positions: {account_id: Decimal}, available: bool, unavailable}",
        ),
    },
)


def ar_positions(
    account_ids: Any = None, *, as_of: Any = None, with_held_credit: bool = False
) -> ArPositions:
    """WHAT THESE ACCOUNTS OWE, from the ledger — one call for a whole page.

    Resolved BY NAME at call time (B1/B8: customers never touches another
    module's ORM) and asked ONCE for every account a list is about to render,
    because a per-row seam call is a query per row on the product's busiest
    screen.

    **The ledger's own refusals travel through rather than being swallowed.**
    `MixedCurrencyBook` (DEF-081) is a catalog `BizError` that the error handler
    already turns into a 409 naming the currencies, and a screen darkened by a
    tenant holding USD and CAD entries side by side is the correct outcome — the
    alternative is a sum with no unit rendered beside a currency symbol. What is
    caught here is the seam being ABSENT, which is a deployment fact and not a
    money fact.
    """
    fn = resolve(AR_POSITIONS_MODULE, AR_POSITIONS_READ, kind=AR_POSITIONS_KIND)
    if fn is None:
        return ArPositions(positions=None, unavailable=AR_POSITIONS_UNWIRED)
    # `DEF-PAY-10707` — the account's NET position (1200 + 2400), asked only by
    # the balance cells; passed only when asked so every other caller's call is
    # byte-for-byte what it was.
    if with_held_credit:
        answer = fn(account_ids=account_ids, as_of=as_of, with_held_credit=True)
    else:
        answer = fn(account_ids=account_ids, as_of=as_of)
    if not answer.get("available"):
        return ArPositions(
            positions=None,
            currency=answer.get("currency"),
            basis=answer.get("basis"),
            unavailable=tuple(answer.get("unavailable") or ()),
        )
    return ArPositions(
        positions=dict(answer.get("positions") or {}),
        currency=answer.get("currency"),
        basis=answer.get("basis"),
        unavailable=tuple(answer.get("unavailable") or ()),
    )


# ── ledger (THE BALANCE TO OWNER POSTS — CR-185-BRC10 D5) ────────────────────
#: `OQ-1250` CLOSED 2026-10-14 → (a): the residue a clerk ties back moves as ONE
#: entry, DR AR (owner account) / CR AR (tenant account). Customers writes no
#: journal line (hard rule 5); the ledger composes the pair and its posting
#: service writes it. Named as constants so the contract is greppable from both
#: sides of the boundary.
BALANCE_TRANSFER_MODULE = "ledger"
BALANCE_TRANSFER_CALL = "post_balance_to_owner"
BALANCE_TRANSFER_KIND = "balance_transfer"


class BalanceTransferRefused(Exception):
    """The ledger refused the tie-back, in customers' vocabulary.

    The ledger's `PostingError` is translated HERE so the settlement module
    imports nothing from `apps.ledger` (B1: a module reaches a neighbour
    through its seam file). The ledger's sentence travels as the message.
    """


def post_balance_to_owner(**kwargs: Any) -> Any:
    """Hand the tie-back to the ledger, or None where the ledger publishes none.

    None is a DEPLOYMENT fact, and the caller refuses on it rather than
    recording a transfer as posted — a decision that claimed the books moved
    when they had not is the exact sentence `OQ-1250` existed to keep off a
    screen. A ledger refusal is raised as `BalanceTransferRefused`.
    """
    fn = resolve(BALANCE_TRANSFER_MODULE, BALANCE_TRANSFER_CALL, kind=BALANCE_TRANSFER_KIND)
    if fn is None:
        return None
    refused = getattr(import_module("apps.ledger.posting"), "PostingError", Exception)
    try:
        return fn(**kwargs)
    except refused as refusal:
        raise BalanceTransferRefused(str(refusal)) from refusal


def unissued_final_bill_for_account(account_id: Any) -> dict[str, Any] | None:
    """`CR-185-BRC10` — billing's answer to *is a final bill still waiting to be sent?*

    The tie-back to the owner moves only money that is IN THE BOOKS
    (coordinator ruling 2026-10-14), so while a drafted final bill waits the
    tie-back waits with it. ⚠ **AN UNPUBLISHED READ ANSWERS "WAITING"** — the
    caller records the tie-back as pending rather than posting money that may
    still be missing a bill; a wrongly pending tie-back is visible on the
    record and harmless, a wrongly posted one is an entry nobody can take back.
    """
    fn = resolve("billing", "unissued_final_bill_for_account", kind="selectors")
    if fn is None:  # pragma: no cover - billing publishes it
        return {"invoice_id": None, "invoice_no": None, "total": None, "currency": None}
    return fn(account_id)


# ── billing (the S17 "Last bill" cell + the BR-CUS-016 aging derivation) ────
def last_issued_invoice_date(account_id: Any) -> Any:
    """US-CUS-001 §5 "Last bill" — the date the account's latest bill ISSUED.

    ⚠ **WIRED 2026-08-15 (DEF-127), AND IT HAD NEVER RUN.** This docstring used
    to read *"Billing owns `invoices` (W3) and the table does not exist, so this
    returns None and the cell renders '—'"*. `invoices` has existed since W3
    landed; the cell went on rendering **"Awaits billing"** beside an account
    holding an ISSUED bill, because this seam resolved `apps.billing.SERVICES`
    (the resolver's default kind) and billing publishes its reads in
    `selectors`. **Two words wrong, and nothing else** — the identical mistake
    DEF-035 found one function below this one, which is why the KIND is now
    named explicitly here.

    Unwired ⇒ None ⇒ the cell renders its absence. It never renders a date
    nobody read.
    """
    fn = resolve("billing", "last_issued_invoice_date", kind="selectors")
    return fn(account_id) if fn is not None else None


def billing_can_answer() -> bool:
    """Is billing REACHABLE at all — as distinct from having nothing to say?

    ⚠ **THIS EXISTS BECAUSE `None` IS AMBIGUOUS, AND DEF-075 IS WHAT THAT COSTS.**
    `last_issued_invoice_date` above returns None both when an account has no
    issued bill and when billing cannot be resolved. For the S17 *"Last bill"*
    cell the two collapse harmlessly — either way it renders an absence. For
    CR-030 W1's rollback they are opposites: *"no bill"* means the account may
    be reversed, *"cannot answer"* means we do not know, and reversing an
    account that carries an issued invoice corrupts books hard rule 4 forbids
    correcting by edit.

    DEF-075's own sentence: *"`None` was read as 'this module has nothing' when
    it meant 'this module cannot answer'"* — a tenant's currency was changed
    under an issued bill because of exactly that. So the question is asked
    separately rather than inferred from a null.
    """
    return resolve("billing", "last_issued_invoice_date", kind="selectors") is not None


def last_issued_invoice_dates(account_ids: Any) -> dict[str, Any]:
    """The same read for a WHOLE PAGE — `{account_id: date}`, ONE call.

    `apps/customers/api.accounts` builds every row before the paginator slices,
    so a per-row seam call is a query per account on the product's busiest
    screen. Same shape and same reason as `ar_positions` above.

    Unwired ⇒ an EMPTY mapping, which reads as "no account has a date" and is
    the same absence the per-row read returns. That direction is safe here and
    would not be for a money figure: a missing date renders an awaiting cell,
    while a missing balance rendered as 0.00 is DEF-127. The distinction is
    stated rather than assumed, because the two seams sit next to each other.
    """
    fn = resolve("billing", "last_issued_invoice_dates", kind="selectors")
    return dict(fn(account_ids)) if fn is not None else {}


def debtor_positions_queryset() -> Any:
    """**Who owes you's own debtor statement, LAZY** — `DEF-CUS-10181`.

        apps.payments.billing_seam.debtor_positions_queryset() -> QuerySet
            values: account_id · oldest_due_on · net (> 0) · …

    The Accounts list's Aging column composes it as a correlated subquery, so
    the band a clerk reads on the list and the days late they read on Who owes
    you are ONE computation (PO 2026-10-17: *"the same figure Who owes you
    uses"*). B1: by name, never by importing payments. None while unwired —
    the caller then says the bill half is unavailable rather than inventing it.
    """
    fn = resolve("payments", "debtor_positions_queryset", kind="billing_seam")
    return fn() if fn is not None else None


def live_bills_queryset() -> Any:
    """Every live bill, LAZY (`id · account_id · due_date · amount_due`), through
    payments' seam — which bill was an account's FIRST is what tells the Aging
    column whether the migrated opening balance is still unpaid (OQ-530 carries
    it on that bill). None while unwired."""
    fn = resolve("payments", "live_bills_queryset", kind="billing_seam")
    return fn() if fn is not None else None


def raise_and_issue_charge_fee(
    actor: Any,
    *,
    account_id: Any,
    charge_code: str,
    on_date: Any,
    due_days: int,
    description: str | None = None,
    issued_at: Any = None,
) -> Any:
    """**DEF-708 — make a tenant charge code a REAL RECEIVABLE.**

    `apps.billing.services.raise_and_issue_charge_fee` — drafts a `fee` bill
    carrying one charge-code line and ISSUES it, so the amount reaches AR and
    the reconnection gate has something to check. PO ruling 2026-08-27:
    *"Make the fee a real charge — It becomes a line that can be billed and
    paid, so the gate has something to check."*

    ⚠ **THIS IS THE ONLY LAWFUL WAY THIS MODULE CAN CHARGE ANYTHING.**
    BR-CUS-037: *"S22 money modals are ENTRY POINTS: validate → confirm →
    owning-module service"*, and CLAUDE.md rule 5 leaves journal lines to the
    ledger posting service alone. Customers writes no financial table; it asks
    billing, which issues, which posts.

    ⚠ **AND AN UNPUBLISHED SEAM RAISES RATHER THAN RETURNING None.** Every
    other billing seam in this file degrades to an absence, because every other
    one is a READ and a missing read renders an empty cell. This one is a
    WRITE, and a caller that took None for "no fee then" would record a cut,
    tell the customer they owe $75.00 and never charge it — which is DEF-708
    itself, restored by a defensive default. The caller catches this and
    refuses the cut.
    """
    fn = resolve("billing", "raise_and_issue_charge_fee")
    if fn is None:
        raise SeamUnavailable(
            "apps.billing.services.raise_and_issue_charge_fee is not published, so the "
            "reconnection fee cannot be charged (DEF-708 / BR-CUS-104). This module may "
            "not write a financial table (BR-CUS-037) and will not record a cut whose fee "
            "it cannot collect — the customer would be told they owe it and never billed."
        )
    return fn(
        actor,
        account_id=account_id,
        charge_code=charge_code,
        on_date=on_date,
        due_days=due_days,
        description=description,
        issued_at=issued_at,
    )


def raise_and_issue_cut_bill(
    actor: Any,
    *,
    account_id: Any,
    cut_on: Any,
    due_days: int,
    cycle_days: int | None = None,
    issued_at: Any = None,
) -> Any:
    """**CR-052 W0 task 1 — THE FINAL METERED BILL, RAISED AT THE CUT.**

    `apps.billing.services.raise_and_issue_cut_bill` — drafts and ISSUES one
    ordinary metered bill covering the account's first unbilled day through the
    cut day inclusive, priced by the same engine as every other bill, and
    returns a `CutBill` result object saying which of four things happened.

    **PO ruling 2026-08-30, verbatim:** *"when we disconnect - we generate final
    bill at that time itself - so later bill is not required ... entire workflow
    including all settlement and status update is taken care at time of
    disconnect or move out - so account status changes and outstanding is
    pending on account if any"*. It closes `OQ-1170`, and the reason it had to
    be ruled is money: writing BR-CUS-107's `Disconnected` status drops the
    account out of `selectors.accounts_for_bill_run`, so the days it used
    BEFORE the cut would have been billed by nobody — **$23.23** of a **$40.00**
    monthly base on `A-11488` (18 days of 31), plus every gallon and every kWh.
    The ruling removes the lateness rather than choosing a casualty.

    ⚠ **THIS IS THE ONLY LAWFUL WAY THIS MODULE CAN RAISE THAT BILL**, and it is
    `raise_and_issue_charge_fee`'s reason one rule along: BR-CUS-037 keeps money
    modals to *"validate → confirm → owning-module service"*, CLAUDE.md rule 5
    leaves journal lines to the ledger posting service, and B1 forbids the
    cross-module write outright. Customers writes no financial table; it asks
    billing, which prices, issues and posts.

    ⚠ **AN UNPUBLISHED SEAM RAISES RATHER THAN RETURNING None**, for the same
    reason the fee door does and with more money behind it. This is a WRITE, and
    a caller that read None as *"no bill then"* would record a cut, write the
    status, drop the account out of every future run and bill those days to
    nobody — which is `OQ-1170`'s defect, restored by a defensive default. The
    caller catches this and refuses to write the status.

    `cycle_days` is B4.3's DENOMINATOR and is the caller's: billing chooses
    nothing (`due_days` travels the same way, CR-029 D8③). `None` means the
    customer's cycle length could not be read, and billing states the
    consequence on the result instead of inventing one.
    """
    fn = resolve("billing", "raise_and_issue_cut_bill")
    if fn is None:
        raise SeamUnavailable(
            "apps.billing.services.raise_and_issue_cut_bill is not published, so the "
            "final bill a disconnection raises AT the cut cannot be produced (CR-052 W0 "
            "task 1, PO ruling 2026-08-30). This module may not write a financial table "
            "(BR-CUS-037) and will not record a cut it cannot bill for: the account "
            "would be marked Disconnected, leave every bill run, and the days it used "
            "before the cut would be billed to nobody — $23.23 of a $40.00 base on the "
            "PO's own worked case, plus the consumption."
        )
    return fn(
        actor,
        account_id=account_id,
        cut_on=cut_on,
        due_days=due_days,
        cycle_days=cycle_days,
        issued_at=issued_at,
    )


def estimate_closing_usage(*, account_id: Any, meter_no: str, moved_out_on: Any) -> dict[str, Any] | None:
    """`DEF-BIL-10052` — billing's estimate for one meter's closing period, or
    None while billing publishes none. READS ONLY."""
    fn = resolve("billing", "estimate_closing_usage")
    if fn is None:
        return None
    return fn(account_id=account_id, meter_no=meter_no, moved_out_on=moved_out_on)


def preview_final_bill(
    *,
    account_id: Any,
    moved_out_on: Any,
    period_start: Any = None,
    cycle_days: int | None = None,
    keyed_reads: Any = None,
) -> dict[str, Any] | None:
    """**S20 step 3 — what the final bill WILL contain, priced and unissued.**

    `apps.billing.services.preview_final_bill` — prices the closing period with
    the run's own stages 1–5 and returns the LINES and the net. **It writes
    nothing**: no invoice, no invoice line, no journal line, no payment, no
    ledger entry and no bill number.

    **PO ruling 2026-09-19, verbatim** on step 3 of the move-out wizard: *"we
    need to do it"*, and the Billing blueprint p112 says what "it" is, in a
    dashed panel: *"NO BILL IS ISSUED BY THIS SCREEN. Billing raises the final
    bill; this wizard prices what it will contain and posts nothing. The
    figures above are a settlement position, not an invoice, and the account
    closes owing what the invoice will say."*

    ⚠ **IT RETURNS None WHEN THE SEAM IS UNPUBLISHED, AND THAT IS THE OPPOSITE
    POSTURE TO `raise_and_issue_cut_bill` DIRECTLY ABOVE — DELIBERATELY.** That
    one RAISES, because it is a WRITE and a caller that read None as *"no bill
    then"* would close an account whose last days were billed to nobody. This
    one is a READ on a screen that already knows how to say *"this could not be
    worked out"*: step 3 renders the gap, the clerk is told, and nothing is
    recorded either way. Refusing the whole wizard because a preview could not
    be produced would block a move-out the product can otherwise complete.

    ⚠ **IT PRICES THE READS THE CLERK KEYED ON STEP 2, WHICH NOBODY HAS
    COMMITTED** — PO ruling 2026-09-20, verbatim *"option b is correct"*
    (`DEF-CUS-5931`). `keyed_reads` is the step-2 capture in the shape the
    wizard already posts to `commit_event_reads` at step 6
    (`{"meter_no": …, "value": …}`). It is READ and stored by nobody: the reads
    still commit with the close, inside the one transaction, exactly as
    blueprint p111 requires. Absent, this prices from committed reads alone,
    which is what it did before the ruling.

    ⚠ **THE NET IT RETURNS IS THE CHARGES, AND `close-impact` IS WHAT APPLIES
    THE REST.** BR-MET-107's unbanked export credit and BR-BIL-013's deposit
    are both applied by `move_out_settlement`, which serves `export_credit`,
    `final_bill_net` and the five landings. Passing `total` to
    `GET /accounts/{id}/close-impact?final_bill=` is what this figure is FOR;
    subtracting either of them here first would double-count them.
    """
    fn = resolve("billing", "preview_final_bill")
    if fn is None:
        return None
    return fn(
        account_id=account_id,
        moved_out_on=moved_out_on,
        period_start=period_start,
        cycle_days=cycle_days,
        keyed_reads=keyed_reads,
    )


def draft_move_out_final_bill(actor: Any, *, account_id: Any, moved_out_on: Any) -> dict[str, Any]:
    """`DEF-CUS-10093` — the move-out's Complete drafts the final bill, BEFORE the close.

    `apps.billing.services.draft_move_out_final_bill`. PO ruling 2026-10-13,
    option B, verbatim: *"Go with this - I recommend B: nothing can be
    forgotten, readings are typed once, and the clerk still reviews the bill
    before it goes out."* Customers may not write an invoice (BR-CUS-037 / B1),
    so it asks billing by name, exactly as the disconnection's cut bill does.

    ⚠ **AN UNPUBLISHED SEAM RAISES**, `raise_and_issue_cut_bill`'s posture: this
    is a WRITE, and a caller reading None as *"no bill then"* would close an
    account whose last days are billed by nobody — the defect this ruling fixes.
    """
    fn = resolve("billing", "draft_move_out_final_bill")
    if fn is None:
        raise SeamUnavailable(
            "apps.billing.services.draft_move_out_final_bill is not published, so the "
            "move-out cannot draft its final bill before the close (DEF-CUS-10093). The "
            "account is not closed: closing it would leave its last days billed by nobody."
        )
    return fn(actor, account_id=account_id, moved_out_on=moved_out_on)


def final_bill_email_document(invoice_id: Any) -> dict[str, Any] | None:
    """`DEF-NOT-10536` — the drafted final bill's PDF, due date and total.

    `apps.billing.services.final_bill_email_document`: the page issue would
    keep, rendered and rolled back so the draft is unchanged (PO 2026-10-22:
    *"send at move-out completion with the draft figures"*). `None` when billing
    publishes no such read; the move-out email then states its absence.
    """
    fn = resolve("billing", "final_bill_email_document")
    return fn(invoice_id) if fn is not None else None


def last_issued_invoice_period_end(account_id: Any) -> Any:
    """US-CUS-005 TC-6: a move-out may not be dated BEHIND the last issued
    bill's period end — "issued bills are untouched (BR-BIL-004); corrections
    route via J6, not move-out backdating".

    WIRED 2026-08-11 (DEF-035), and it had never run before that. This resolved
    `apps.billing.SERVICES` — the resolver's default kind — and billing's
    services module publishes only `assess_late_fee`, so the lookup returned
    None on every call and the caller dutifully recorded
    `move_out_date_not_checked_against_issued_bills`. The guard was correct,
    its tests passed (they monkeypatch this seam), and it had never once been
    asked about a real bill. Two words were wrong: the KIND, and nothing else.

    The caller still records the not-checked outcome when this returns None,
    because a seam that goes missing again must fail visibly rather than
    silently permitting what it was written to refuse."""
    fn = resolve("billing", "last_issued_invoice_period_end", kind="selectors")
    return fn(account_id) if fn is not None else None


def unbilled_service_window(account_id: Any, *, through: Any) -> dict[str, Any] | None:
    """The days this account has NOT been billed for, up to `through` inclusive.

    **PO ruling 2026-09-21 — a cut is completed WITHOUT a bill**, and the days
    that were never billed must stay visible to somebody rather than becoming
    invisible the moment BR-CUS-107's status is written. Billing owns the
    answer; `apps/billing/selectors.unbilled_service_window` is the read and
    its docstring carries the reasoning.

    ⚠ **THE ABSENCE IS NOT THE SAME AS "NOTHING IS UNBILLED", AND A CALLER MUST
    NOT COLLAPSE THE TWO.** `None` here means either *billing says there is
    nothing unbilled* or *billing did not answer at all* — DEF-035's shape,
    where a seam resolving to nothing let a guard silently permit what it was
    written to refuse. `disconnects.unbilled_days_at_cut` therefore reports the
    unanswered case as a stated absence rather than as a clean bill of health.
    """
    fn = resolve("billing", "unbilled_service_window", kind="selectors")
    return fn(account_id, through=through) if fn is not None else None


def billing_selectors_answer() -> bool:
    """Is billing's SELECTOR surface reachable at all from this process?

    `billing_can_answer` above asks the same question of the `services` kind.
    This is its twin for `selectors`, and it exists so a caller can tell *there
    are no unbilled days* from *nobody answered* — see `unbilled_service_window`
    directly above, and DEF-035 for what it costs to conflate them.
    """
    return resolve("billing", "unbilled_service_window", kind="selectors") is not None


def assess_late_fee(**terms: Any) -> Any:
    """BR-BIL-001 as amended 2026-08-11 — billing's fee, never a second copy.

    US-CUS-018's plan carries a `suspend_late_fees` election over the ARREARS it
    spreads (BR-CUS-043), and the CURRENT month's bill is unaffected by the plan
    entirely (PO 2026-08-11, *"there is monthly charges that thye have to pay nad
    it is due every month"*). So the current bill's fee is billing's own
    calculation with billing's own $25.00 balance floor — reached BY NAME rather
    than restated here, because the ruled figure lives in
    `apps/billing/late_fee.py` and a second copy is how two figures start
    disagreeing.

    Unwired ⇒ None, and the caller must treat that as *"the fee could not be
    assessed"*, never as *"no fee applies"*. `apps.billing.services` publishes
    it today, so this resolves.
    """
    fn = resolve("billing", "assess_late_fee")
    return fn(**terms) if fn is not None else None


def propose_payment_plan(**plan: Any) -> dict[str, Any] | None:
    """US-CUS-018's handoff: the wizard's result → payments' own service.

    THE CONTRACT, and the ask for the lane that publishes it:

        apps.payments.services.propose_payment_plan(
            actor, account_id, total_amount, down_payment, installments,
            cadence, autopay_enabled, suspend_late_fees, suspend_disconnect,
            schedule=((seq, due_date, amount), ...),
        ) -> Mapping  with keys {id, status}

    `payment_plans` and `payment_plan_installments` are PAYMENTS-owned (B2 §2,
    EP-PAY-05) and BR-CUS-037 is explicit that customers writes no financial
    table: *"S22 money modals are ENTRY POINTS: validate → confirm → owning-module
    service"*. The wizard therefore computes and validates the schedule — that
    part is live, tested and frozen as GT-47 — and hands it over.

    Unwired ⇒ None, and `apps/customers/services.propose_payment_plan` REFUSES
    rather than reporting a plan it did not create. A wizard that answered "sent
    ✓" over a table that does not exist would be the exact defect hard-won law 2
    describes: built, green, and not there.
    """
    fn = resolve("payments", "propose_payment_plan")
    return dict(fn(**plan)) if fn is not None else None


def payment_plans_for(account_id: Any, *, as_of: Any = None) -> list[dict[str, Any]] | None:
    """Every plan this account has, from the module that owns the rows.

        apps.payments.services.payment_plans_for_account(account_id, as_of=date)
            -> list[Mapping]  each with {id, status, currency, total_amount,
               down_payment, installments:[{seq, due_date, amount, currency}], …}

    **`None` means the read is UNWIRED, and it is NOT an empty list.** An
    account with no plan and an account whose plans this deployment cannot read
    are different facts, and DEF-127 is what happens when a product spells them
    the same way: a screen that renders "no payment plan" over a plan it simply
    could not fetch tells a clerk the customer never agreed one. The caller
    renders the absence with its reason (`ArPositions` sets the same posture for
    the balance right above).

    A pure READ: it writes nothing, transitions nothing, and never creates the
    rows it fails to find (BR-CUS-037 — customers writes no financial table).
    """
    fn = resolve("payments", "payment_plans_for_account")
    if fn is None:
        return None
    return [dict(row) for row in fn(account_id, as_of=as_of)]


def activate_payment_plan(**activation: Any) -> dict[str, Any] | None:
    """BR-CUS-044: the plan activates on the CUSTOMER's signature alone.

        apps.payments.services.activate_payment_plan(actor, plan_id, signed_on)
            -> Mapping  with keys {id, status}

    Same posture as `propose_payment_plan`: unwired ⇒ None ⇒ the caller refuses.
    Pausing dunning on a plan nobody recorded would stop chasing a real debt.
    """
    fn = resolve("payments", "activate_payment_plan")
    return dict(fn(**activation)) if fn is not None else None


# ── CR-089 wave I · the two account states the unit's Account tab states ────
#
# `PUJ-39` / `DEF-CUS-4691`: *"an absent row reads as 'not looked up'; a stated
# 'none' is the answer"*. Both rows below therefore have to tell three states
# apart — enrolled, not enrolled, and **could not be read** — and the third is
# why they answer `None` rather than a falsy dict. `payment_plans_for` above
# carries the same posture and `DEF-127` is what collapsing them costs.
def budget_enrolment_for(account_id: Any) -> dict[str, Any] | None:
    """Is this account on budget billing, and at what level?

        apps.billing.budget_service.status_for(account_id)
            -> AccountBudgetStatus | None
        apps.billing.budget_service.effective_level(status) -> Decimal

    `account_budget_status` is BILLING's table (B2 §2). The two callables are
    resolved by name and the ROW IS FLATTENED HERE, inside the seam, so nothing
    in `customers` holds a billing model — `apps/portal/seams/billing_seam.py`
    reads the same pair the same way and is the precedent.

    **`None` means billing could not be reached; `{"enrolled": False}` means the
    account is not on the programme.** They are different sentences on screen.

    The level is a DECIMAL STRING at the stored scale (hard rule 2) — the
    override where there is one, which is what `effective_level` settles.
    """
    status_for = resolve("billing", "status_for", kind="budget_service")
    effective_level = resolve("billing", "effective_level", kind="budget_service")
    if status_for is None or effective_level is None:
        return None
    row = status_for(account_id)
    if row is None:
        return {"enrolled": False}
    return {
        "enrolled": True,
        "status": row.status,
        "level": str(effective_level(row)),
        "currency": row.currency,
        "enrolled_on": row.enrolled_on,
    }


def collection_state_for(account_id: Any, *, as_of: Any) -> dict[str, Any] | None:
    """Where this account stands on the dunning ladder, if anywhere.

        apps.payments.collections_read.account_position(account_id=…, as_of=…)
            -> Mapping  with keys {state:{tier,tier_sent_on,next_step_due,…},
               pause:{…}, disconnect_blocked: bool, …}

    `account_collection_state` is PAYMENTS' table, ONE row per account, and an
    account nobody has chased simply has no row — so **a row with no tier is the
    real answer *not in collections***, and `None` from this seam is *payments
    could not be read*. Same three-state posture as `budget_enrolment_for`.

    ⚠ **THE WHOLE POSITION IS ASKED FOR AND FOUR FIELDS ARE KEPT, DELIBERATELY.**
    `account_position` is the read payments PUBLISHES; a narrower one would have
    to be authored in `apps/payments`, which is another lane's file, and a second
    implementation of *where is this account on the ladder* is `DEF-154`'s shape.
    It costs a handful of queries on ONE account and it cannot drift from S34.

    `as_of` is REQUIRED (BR-TEN-043, gate G6): whether a tier is due today is a
    question about the tenant's business date, never this process's clock.
    """
    fn = resolve("payments", "account_position", kind="collections_read")
    if fn is None:
        return None
    position = fn(account_id=account_id, as_of=as_of)
    state = dict(position.get("state") or {})
    pause = dict(position.get("pause") or {})
    return {
        "on_the_ladder": state.get("tier") is not None,
        "tier": state.get("tier"),
        "tier_sent_on": state.get("tier_sent_on"),
        "next_step_due": state.get("next_step_due"),
        # WHY the ladder is not running, in payments' own word. `US-PAY-019`.
        "paused_reason": pause.get("reason"),
        # ⚠ **`position["disconnect_blocked"]` IS DELIBERATELY NOT RETURNED, AND
        # THE NAME IS WHY.** It reads as *may this account be cut today* and
        # answers only the PAYMENT-PLAN half: `dunning.disconnect_blocked` calls
        # `collections_pause_for` and then asks the plan's own
        # `suspend_disconnect` election, and it never looks at
        # `account_protections` at all. Measured on `brazosbend` 2026-09-08:
        # account `A-11902` carries a medical certificate in force to 5 Nov 2026
        # and that function answers **False**. Carrying it here as a cross-check
        # on the protection banner would have shipped exactly the misreading the
        # banner exists to prevent. `DEF-PAY-4703`.
    }


# ── rating (the plan catalog + THE proration seam) ──────────────────────────
#
# AMENDED 2026-08-11 (W8 change-plan lane). The header above still says "no
# rating seam is consumed", and that was true while the account-side plan
# snapshot was the only thing customers wanted from rating. The PO's ruling of
# 2026-08-11 — *"from unit you will derive the plan"* — deleted that snapshot
# and left S23 needing three genuinely different things from rating: which plans
# may be offered, what each one's base charges are, and the ONE piece of money
# arithmetic in the whole wizard. All three are reads or pure functions; none of
# them writes a rating table.
def assignable_plans() -> list[dict[str, Any]]:
    """Every PUBLISHED plan this tenant may put a unit on (BR-RAT-030).

    Rating's own `plan_list` does the filtering, through its own declared
    `status` filter — customers passes the value and never writes the predicate,
    so BR-RAT-030 stays in one file. The page size is deliberately large: this
    is a wizard PICKER over a tenant's own plan catalog (a handful of rows for a
    utility of this size), not a paged list screen, and a silently truncated
    picker would hide a plan a clerk was told to choose.
    """
    from core.pagination import ListParams

    fn = resolve("rating", "plan_list", kind="selectors")
    if fn is None:
        return []
    return list(fn(ListParams(filters={"status": "published"}, per=1000)))


def plan_ref(plan_id: Any) -> dict[str, Any] | None:
    """`{id, code, name, version}` for a PUBLISHED plan, or None.

    None covers both "no such plan" and "not published" deliberately — that is
    rating's own posture in `plan_ref`, and separating the two would leak which
    ids exist to a caller who may not see them (HR-1)."""
    fn = resolve("rating", "plan_ref", kind="selectors")
    return fn(plan_id) if fn is not None else None


def account_tax_exemptions(account_id: Any) -> list[dict[str, Any]]:
    """The account's per-tax exemption CERTIFICATES — rating's rows
    (BR-RAT-105), each naming the tax it removes. `DEF-CUS-9774` / `9775`.

    Unwired ⇒ `[]`, which reads as *no certificate*: rating owns the row and
    customers never reads its table (B1)."""
    fn = resolve("rating", "exemption_certificates_for_account", kind="selectors")
    return list(fn(account_id)) if fn is not None else []


def unit_plan_in_force(unit_id: Any) -> dict[str, Any] | None:
    """The plan the account's UNIT is on, and since when — `DEF-2419`.

    Returns `{"id", "name", "code", "version", "since"}` or None. `since` is
    `units.plan_effective_from` as an ISO date, which is the same date the unit
    screen prints as *"ON PLAN SINCE"*; `version` is BR-CUS-013's SNAPSHOT
    integer that travels with `plan_ref`.

    ⚠ **THIS SHOWS, IT DOES NOT STORE, AND THE DIFFERENCE IS THE WHOLE POINT.**
    The account-side snapshot (`account_plan_assignments`, BR-CUS-029) still has
    no DDL and is still not written — `account_detail_dict` keeps serving
    `plan: None` beside that rule id, and this answer is served under a
    different key so nothing can read one as the other. What is read here is a
    chain of keys the schema already has: `accounts.unit_id` (the reviewed
    cross-module FK, B2 §2) → `units.rate_plan_id` → `rating.plan_ref`.
    PO ruling 2026-09-01: *"It should be foreign key - it should take it from
    Unit and display it there - that is important"*, confirming their ruling of
    2026-08-11, *"from unit you will derive the plan"*.

    **THREE ABSENCES, ALL REAL, ALL THE SAME None** — and the caller states an
    absence rather than inventing a plan for any of them:

      · the account names no unit (a master covering premises, BR-CUS-1010);
      · the unit stands on no plan — `rate_plan_id` is nullable and a unit
        with no plan is an ordinary state, not a gap in our data;
      · the plan is no longer PUBLISHED — `plan_ref` filters to published
        (BR-RAT-030) and answers None, which is rating's posture, not ours.

    ⚠ **`unit_row` RAISES 404-never-403 FOR A UNIT THIS TENANT CANNOT SEE (HR-1)
    AND THAT REFUSAL IS CAUGHT HERE.** It is the right answer when the unit IS
    the subject of the request; on an account detail the subject is the account,
    and letting metering's refusal escape would blow up a whole screen over one
    cell. Same posture `unit_refs` documents for the batch read and `_premise_
    cell` has always taken. The tenant boundary itself is NOT re-implemented:
    `unit_row` and `plan_ref` each scope on their owning side.

    Unwired ⇒ None, per this file's rule for every READ seam.
    """
    if unit_id is None:
        return None
    from core import errors

    unit_fn = resolve("metering", "unit_row", kind="selectors")
    if unit_fn is None:
        return None
    try:
        unit = unit_fn(unit_id)
    except errors.NotFoundError:
        return None
    ref = plan_ref(getattr(unit, "rate_plan_id", None))
    if ref is None:
        return None
    since = getattr(unit, "plan_effective_from", None)
    return {
        # Record links (PO 2026-10-19): the plan's id, so the plan name on the
        # Account page opens the plan. It is the unit's own `rate_plan_id` —
        # the key `plan_ref` was just asked about, so nothing new is read — and
        # it builds an address only, never a visible value (B14 rule 31).
        "id": str(unit.rate_plan_id),
        "name": ref.get("name"),
        "code": ref.get("code"),
        # BR-CUS-013's snapshot integer, forwarded verbatim — never recomputed.
        "version": ref.get("version"),
        "since": since.isoformat() if since is not None else None,
    }


def plan_detail(plan_id: Any) -> dict[str, Any] | None:
    """The plan bundle S23 compares: `services[]` with each `base_charge`.

    The base charges are the ONLY money the preview states without asking the
    engine, and they are not computed — they are the tenant's own configured
    figures, read verbatim and compared. `12.00 − 30.50` is a subtraction of two
    stored amounts, not a proration.
    """
    fn = resolve("rating", "plan_detail", kind="selectors")
    return fn(plan_id) if fn is not None else None


def prorate_base_charge(*, base_charge: Any, period: Any) -> Any:
    """B4.3 CALENDAR-DAY PRORATION — the rating ENGINE's, never a second copy.

    🔒 THIS SEAM IS THE POINT OF THE WHOLE PREVIEW. B4.3 is finance-signed and
    frozen, GT-3 pins its one figure (15/30 × 30.50 = 15.25), and the rule lives
    in exactly one file: `apps.rating.engine.prorate_base_charge`, which
    finalizes half-up to 2dp exactly once (BR-RAT-003). A wizard that multiplied
    a base charge by a day ratio would be a second implementation of signed
    money law, in a module that does not own it, on a screen a customer is read
    from — which is the defect class CLAUDE.md's sensitive-paths section exists
    to prevent.

    `period` is any object exposing `.service_days` and `.cycle_days`; the
    engine reads nothing else off it.

    Unwired ⇒ None, and the caller must state that no prorated figure could be
    produced. It must NEVER fall back to arithmetic of its own.
    """
    fn = resolve("rating", "prorate_base_charge", kind="engine")
    return fn(base_charge=base_charge, period=period) if fn is not None else None


# ── metering (the plan WRITE path, and the billing period S23 cannot see) ───
def assign_unit_plan(actor: Any, unit_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Move a unit onto a plan, effective-dated (BR-CUS-014 sc.3).

    THE REVIEWED CROSS-MODULE WRITE, and the only one this module makes. B2 §2's
    interface register carries it, EP-CUS-05 US-CUS-017 §5 names it in so many
    words (*"⚠ cross-module WRITE via the plan-assignment service owned with
    metering; the reviewed interface is the write path BR-CUS-010 established at
    move-in"*), and metering's own service is what runs: it holds the BR-MET-007
    plan lock, moves `units.rate_plan_id`, and calls rating to append the
    `unit_plan_assignments` row inside one transaction. Customers writes neither
    table and re-implements neither guard.

    Unwired ⇒ None ⇒ the wizard REFUSES. A "Plan changed ✓" toast over a unit
    whose plan never moved is the exact shape of hard-won law 2.
    """
    fn = resolve("metering", "assign_unit_plan")
    return dict(fn(actor, unit_id, payload)) if fn is not None else None


def raise_connection_build(
    actor: Any,
    *,
    premises_id: Any,
    service_request_id: Any,
    target_activation: Any = None,
) -> dict[str, Any] | None:
    """Raise a `Draft` build on the New connects tab, naming the request.

    **THE SECOND REVIEWED CROSS-MODULE WRITE THIS MODULE MAKES**, the first being
    `assign_unit_plan` above, and it is the same shape for the same reason: the
    row is metering's (`connections`, B2 §2), so metering's own door writes it.
    `metering.connections.create_connection` allocates the `CON-` number,
    resolves the premises with the 404-never-403 refusal, writes the
    `connection.created` audit row and reports its own `numbering_series_missing`
    warnings. Customers re-implements none of that.

    ⚠ **THE DOOR HAS TAKEN `service_request_id` SINCE `CR-070` WAVE B AND
    NOTHING HAS EVER PASSED ONE** (`DEF-MET-5397`). Its docstring says *"Prefilled
    from an approved request where there is one"* — it was built for this call
    and the call did not exist until `CR-094-BRC01`. `connections.request_id` has
    been NULL on every row of every tenant.

    ⚠ **A REQUEST WHOSE ADDRESS HAS NOT RESOLVED STILL RAISES A BUILD, SINCE
    `DEF-CUS-6109` (2026-09-21) — `premises_id=None` SENDS `premises_at_commit`.**
    PO ruling of that day: approving an application *"may create a new conenct
    request - as draft request"*, and the wizard then asks for the owner, the
    units and the services and **creates the address at commit** (`BR-MET-112`).

    ⚠ **THIS PARAGRAPH SAID THE OPPOSITE UNTIL THEN AND WHAT IT SAID WAS FALSE
    — `DEF-MET-6117`.** It read: *"`premises_id` ONLY — NEVER the `premises`
    BLOCK. That door will create the address it builds on (`BR-MET-1024`), and
    creating one requires a MANDATORY OWNER (`BR-MET-1010`) which a service
    request does not carry."* **Measured against the schema:**
    `premises.owner_id` is NULLABLE, the owner refusal on a premises create was
    itself reversed on 2026-08-27 (`DEF-650`), and `create_premises` opens the
    owner's master account LAST in its own savepoint — *"a refused account
    leaves the address standing"*. Nothing was missing; the refusal was a
    choice. **This seam still sends no `premises` block**, and the reason is now
    the real one: `BR-MET-112` says the address is written at the last button,
    not at approval.

    Unwired ⇒ None ⇒ the caller reports `job_door_unpublished` and the approval
    stands (`BR-WRK-055`). A "build raised ✓" over a build that does not exist is
    hard-won law 2 on data, and `SeamUnavailable`'s own note above says a write
    seam may not degrade silently.
    """
    fn = resolve("metering", "create_connection", kind="connections")
    if fn is None:
        return None
    return dict(
        fn(
            actor,
            {
                "premises_id": premises_id,
                # `DEF-CUS-6109` — *no address yet, and one is not created
                # here*. An EXPLICIT key rather than the absence of the other
                # two, so a caller that simply forgot its `premises_id` is
                # still refused by name (`create_connection`).
                "premises_at_commit": premises_id is None,
                "service_request_id": service_request_id,
                "target_activation": target_activation,
            },
        )
    )


def billing_period_for_unit(unit_id: Any, *, as_of: Any = None) -> dict[str, Any] | None:
    """The unit's billing period — `{start, end}`, ISO dates. B4.3's denominator.

    ✅ **WIRED 2026-08-31 (`DEF-2708`), AFTER TWENTY DAYS UNANSWERED.** The
    contract below was written here on 2026-08-11 and nobody published it, so
    both callers fell back and one of them was a customer's final bill:
    `apps/customers/disconnects._cycle_days_for` divided by the BILLED WINDOW's
    own length, the B4.3 factor became 1, and the bill raised at a
    disconnection charged a FULL month's standing charge for a PART month —
    **$40.00 where 18 days of 31 is $23.23, $16.77 too much**, on the PO's own
    account `A-11488`.

        apps.metering.selectors.billing_period_for_unit(unit_id, as_of=date|None)
            -> {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} | None

    ⛔ **THE JOIN THIS PARAGRAPH USED TO DESCRIBE NO LONGER EXISTS, AND THAT IS
    WHY THE ASK SAT UNANSWERED.** It said the period was
    `cycles.window_start`/`.window_end` reached through `service_points
    .cycle_id`. **Both columns are dropped** (metering `0021`, and `0023` took
    `bill_date`), and the stamp is a projection CR-029 D4 re-derives. A period
    is now DERIVED from the cycle's ruled schedule — the anchor is the first
    run's day (`OQ-340`), the step is B17 §2's frequency table, a month with no
    such day clamps (`OQ-339`) — which is metering's own arithmetic and is the
    reason customers still may not make this read itself (B1).

    ⚠ **PASS `as_of` ON A MONEY PATH** (BR-TEN-043 / G6 — the event date is an
    argument, never a clock). A cut on 18 February committed by a clerk in March
    must divide by February's 28 days, not March's 31. It defaults to the
    tenant's today, which is what a screen asking *"what period are we in"*
    wants and what the plan-change preview asks.

    STILL None WHEN IT CANNOT BE ANSWERED, and every caller must still STATE
    that: a unit on no cycle, a pre-CR-029 cycle with no frequency or no first
    run, a date before the cycle's first run, or a unit on TWO cycles. Assuming
    a 30-day month would be money invented from a calendar nobody configured, on
    a figure a customer is quoted — so the preview names its prorated lines
    unavailable and produces no figure at all, and the cut bill states
    `cut_bill.CUT_BILL_DENOMINATOR_ABSENT` on its result.
    """
    fn = resolve("metering", "billing_period_for_unit", kind="selectors")
    if fn is None:
        return None
    # ⚠ POSITIONAL, AND `as_of` ONLY WHEN THERE IS ONE. The published contract
    # is one argument; a caller with no event date must not force a keyword a
    # stub or an older implementer may not accept (DEF-047's shape — a seam
    # that adapted the owner's result but not its signature).
    return fn(unit_id) if as_of is None else fn(unit_id, as_of=as_of)


def billing_cycle_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """The unit's cycle, its current period and the cycle's next bill date.

    THE CONTRACT (`DEF-CUS-5182`):

        apps.metering.selectors.billing_cycle_for_unit(unit_id)
            -> {"code", "name", "bill_day", "period_start", "period_end",
                "next_bill_on"} | None

    Metering DERIVES all of it (CR-029 D4 · `OQ-339` · `OQ-340` · `OQ-344`), so
    customers asks rather than walking `service_points` itself (B1). `None` —
    no unit, no cycle, two cycles, or the door unwired — is an honest answer the
    caller STATES; it is never a guessed 30-day month.
    """
    if unit_id is None:
        return None
    fn = resolve("metering", "billing_cycle_for_unit", kind="selectors")
    return fn(unit_id) if fn is not None else None


def transfer_premises_owner(
    actor: Any, premises_id: Any, account_id: Any, owner: dict[str, Any]
) -> dict[str, Any] | None:
    """`BR-CUS-1081` (T2, PO 2026-09-23) — the buyer of a MASTER account becomes
    the property's owner, through METERING's own door.

    PO, verbatim: *"in case of master account - not in case of regualr account -
    (a) The sale makes the buyer the property's owner."*

    THE CONTRACT:

        apps.metering.premises_owners.transfer_premises_owner(
            actor, premises_id, account_id, {"name", "email"?, "phone"?})
            -> {"moved": bool, "owner_id": str | None, "reason": str | None}

    ⛔ **CUSTOMERS WRITES NO METERING TABLE** (B1 / B2 §2). `premises.owner_id`
    and the owner record are metering's, so metering writes them under its own
    role gate and audit row; what crosses back is whether it moved. `None` means
    the door is unwired, and the caller states that rather than claiming a move.
    """
    fn = resolve("metering", "transfer_premises_owner", kind="premises_owners")
    return fn(actor, premises_id, account_id, owner) if fn is not None else None


# ── notifications (the ONE writer of the outbound queue) ────────────────────
def queue_document(**message: Any) -> Any:
    """Write a message to `outbound_messages` (BR-NOT-005) — never send it.

        apps.notifications.services.queue_document(
            source_type=..., source_id=..., channels=(...), account_id=...,
            template=TemplatePin(...), actor=..., ...
        ) -> QueueWrite

    `outbound_messages` is the one table B1 opens to cross-module writes (B2 r16
    #7) and `queue_document` is what that exception means: it adds BR-BIL-036's
    print floor, resolves the recipient, honours rule 6 and audits — all of
    which a caller reaching for the ORM would skip.

    Unwired ⇒ None ⇒ the caller reports that nothing was queued. It never
    reports a notification it did not queue (US-CUS-017 TC-4's toast is only
    allowed to say "customer notified" when a row exists).
    """
    fn = resolve("notifications", "queue_document")
    return fn(**message) if fn is not None else None


def queue_template_pin(**pin: Any) -> Any:
    """`notifications.TemplatePin` — the contract TYPE `queue_document` takes.

    Resolved by name for the same reason the callable is: half a published
    interface is not an interface (`apps/billing/delivery_seam.py` says exactly
    that and builds its pin the same way). A queue row must say what will render
    it — `queue_document` REFUSES a row carrying neither a code nor a pin — and
    customers holds the code for the A19 plan-change email.
    """
    factory = resolve("notifications", "TemplatePin")
    return factory(**pin) if factory is not None else None


def queue_refusal_type() -> Any:
    """`notifications.QueueWriteRefused`, so a caller can catch the queue's own
    refusal and report it rather than let a notification failure take down a
    plan change that already committed."""
    return resolve("notifications", "QueueWriteRefused") or ()


# ── work (CR-070 wave P · the five flows raise their jobs) ──────────────────
#
# ⚠ **THIS MODULE WRITES NOTHING TO `work_orders`, AND THESE TWO FUNCTIONS ARE
# THE WHOLE REASON IT DOES NOT HAVE TO.** `BR-WRK-055`: *"the move-out,
# disconnect and reconnect wizards call Work from the SCREEN to raise the visit;
# Customers writes nothing to `work_orders`"*. `A7`'s boundary gate and `G102`
# both read `apps/customers/**` for a write to that table and fail the merge on
# one. What customers does instead is ASK Work, by name, exactly as it asks
# billing to issue a fee (`raise_and_issue_charge_fee` above) — one pattern for
# cross-module access, not two.
#
# ⚠ **AND THE FAILURE POSTURE IS THE OPPOSITE OF BILLING'S, DELIBERATELY.** An
# unpublished billing write RAISES, because a cut recorded with an uncharged fee
# tells a customer they owe money nobody ever billed (`DEF-708`). An unraisable
# WORK ORDER is not that: `BR-WRK-055` and judgment 7 both say the flow completes
# either way, and a field module able to block a customer's move-out is the
# failure this design exists to prevent. So the raise raises, the CALLER catches,
# and the flow finishes carrying `work_orders_not_raised`.


def propose_flow_work_orders(flow_kind: str, flow_id: Any) -> dict[str, Any] | None:
    """What field work this flow could raise. READ — writes nothing.

    Answers None while `apps.work.from_flows` is not published, and a caller
    that gets None offers no panel. That is the ordinary read degradation of
    every other read in this file: an absent offer renders an absent control,
    which is honest, where a silently-not-written row would not be.
    """
    fn = resolve("work", "propose", kind="from_flows")
    return None if fn is None else fn(flow_kind, flow_id)


def raise_flow_work_orders(
    actor: Any, *, flow_kind: str, flow_id: Any, template_ids: Any
) -> dict[str, Any]:
    """Raise the field jobs a clerk ticked, through Work's own service.

    ⚠ **THE CALLER MUST CATCH THIS.** It raises when the seam is unpublished,
    when the template is not published, when the flow has no anchor and when the
    database refuses the row — and `BR-WRK-055` says the flow completes anyway.
    Every one of the five doors wraps it and reports `flow_work_not_raised()`.
    """
    fn = resolve("work", "raise_for", kind="from_flows")
    if fn is None:
        raise SeamUnavailable(
            "apps.work.from_flows.raise_for is not published, so the field job cannot be "
            "created (BR-WRK-055). This module may not write `work_orders` itself "
            "(BR-WRK-002 / A7) — the flow completes and reports that no job was raised."
        )
    return fn(flow_kind, flow_id, template_ids, actor)


def clean_flow_order_rows(rows: Any) -> list[dict[str, Any]]:
    """Work's own validation of a flow's work-order rows, BEFORE any transaction
    (`DEF-CUS-6363`). Refuses a row with no job type by name. With Work
    unpublished the rows pass through untouched and the raise itself reports
    that nothing was raised — never a flow refused over a job."""
    fn = resolve("work", "clean_order_rows", kind="from_flows")
    return list(rows or []) if fn is None else fn(rows)


def check_flow_order_rows_on_unit(rows: Any, unit_id: Any) -> None:
    """Work's check of a flow's rows against the UNIT, BEFORE the flow commits
    (`DEF-WRK-9784`): each *For* meter is on the unit and a named template is
    of that meter's service. Refuses by name. With Work unpublished nothing is
    checked here and the raise itself reports what it could not do."""
    fn = resolve("work", "check_order_rows_on_unit", kind="from_flows")
    if fn is not None:
        fn(rows, unit_id)


def raise_flow_order_rows(
    actor: Any, *, flow_kind: str, flow_id: Any, rows: Any
) -> dict[str, Any]:
    """Raise the work-order ROWS a clerk added on a flow (`DEF-CUS-6363`),
    through Work's own service. The same contract as `raise_flow_work_orders`
    above: it raises, and the caller catches (`BR-WRK-055`)."""
    fn = resolve("work", "raise_orders_for", kind="from_flows")
    if fn is None:
        raise SeamUnavailable(
            "apps.work.from_flows.raise_orders_for is not published, so the field job cannot "
            "be created (BR-WRK-055). The flow completes and reports that no job was raised."
        )
    return fn(flow_kind, flow_id, rows, actor)


def raise_cut_visits(actor: Any, *, account_id: Any, visits: Any) -> dict[str, Any]:
    """The disconnect wizard's work-order rows, raised by Work (`DEF-CUS-9631`).

    The same contract as `raise_flow_work_orders` above: it RAISES, and the
    caller catches and reports `flow_work_not_raised()` (`BR-WRK-055`).
    """
    fn = resolve("work", "raise_cut_visits", kind="from_flows")
    if fn is None:
        raise SeamUnavailable(
            "apps.work.from_flows.raise_cut_visits is not published, so the cut visit cannot "
            "be created (BR-WRK-055). The disconnection is scheduled and reports that no job "
            "was raised."
        )
    return fn(account_id, visits, actor)


def raise_temporary_stop_visits(actor: Any, *, account_id: Any, visits: Any) -> dict[str, Any]:
    """`CR-183-BRC10` B2 — a temporary stop's shut-off and turn-on jobs, raised
    by Work. The same contract as `raise_cut_visits` above: it RAISES, and the
    caller catches and reports `flow_work_not_raised()` (`BR-WRK-055`)."""
    fn = resolve("work", "raise_temporary_stop_visits", kind="from_flows")
    if fn is None:
        raise SeamUnavailable(
            "apps.work.from_flows.raise_temporary_stop_visits is not published, so the field "
            "visit cannot be created (BR-WRK-055). The temporary stop stands and reports that "
            "no job was raised."
        )
    return fn(account_id, visits, actor)


def cancel_flow_order(actor: Any, *, order_no: Any) -> bool:
    """`DEF-CUS-10190` — call off ONE open job this module raised (by its
    number), through Work's own dispatch door: nothing is deleted. `False` when
    Work cannot be asked, the job is not found, or it already left the run —
    the caller reports it and carries on (`BR-WRK-055`)."""
    fn = resolve("work", "cancel_flow_order", kind="from_flows")
    if fn is None or not order_no:
        return False
    try:
        from django.db import transaction

        with transaction.atomic():
            return bool(fn(order_no, actor))
    except Exception:  # noqa: BLE001 - a job that cannot be called off never refuses the flow
        return False


def flow_work_acceptance(*, flow_kind: str, source_ref: Any) -> dict[str, int] | None:
    """How many of the jobs a flow record raised have been accepted, or None.

    B19 §12.3's promise is a COUNT and not a flag — see
    `service_request_service.close_if_field_work_done`. None means Work cannot
    answer, and a caller that gets None concludes nothing: closing a request on
    an unreadable tally is the same error as closing it on the first acceptance,
    reached from the other direction.
    """
    fn = resolve("work", "acceptance", kind="from_flows")
    return None if fn is None else fn(flow_kind, source_ref)


def flow_work_visits(*, flow_kind: str, source_ref: Any) -> dict[str, Any] | None:
    """The jobs a flow record raised — counts AND the numbers — or None when
    Work publishes no read (`CR-168-BRC10` §F, `DEF-CUS-9628`/`9629`/`9630`).

    `source_ref` is the flow's NUMBER (`MVO-`, `MVI-`, `TRF-`, `DSC-`), because
    that is what `from_flows` stamps on the order; a database id finds nothing.
    """
    fn = resolve("work", "visits", kind="from_flows")
    return None if fn is None else fn(flow_kind, source_ref)


def flow_work_not_raised(detail: str | None = None) -> dict[str, Any]:
    """The platform's own sentence for a job that could not be created, in the
    shape every flow already puts its unavailabilities in (`MOVE_OUT_UNAVAILABLE`).

    ⚠ **THE FALLBACK IS NOT A SECOND SENTENCE — IT IS THE SAME CODE AND THE SAME
    CATALOGUE KEY.** Work owns the words; this answers them even when Work is
    the thing that is unreachable, which is precisely the case a caller most
    needs a sentence for. A different string here would put two spellings of one
    fact in front of a clerk depending on which failure they hit.
    """
    fn = resolve("work", "not_raised_warning", kind="from_flows")
    if fn is not None:
        return fn(detail)
    return {
        "code": "work_orders_not_raised",
        "message_key": "work.fromFlows.notRaised",
        "br_ref": "BR-WRK-055",
        "detail": detail
        or "the field job could not be created. The flow completed; nothing is waiting on it.",
    }


# ── the ONE deposit capability's two seams (CR-094-BRC01 wave H) ───────────
#
# PO ruling 2026-09-12: *"(a) It is one concept — money held against an account
# — and building it four times would give four behaviours."* `apps/customers/
# deposit.py` is the customers half of that one concept; these are the only two
# places it crosses a module boundary.


def deposit_rule_for_account(
    *, unit_id: Any, account_type_id: Any, size_class: str | None = None
) -> dict[str, Any] | None:
    """The STANDARD deposit for this account's plan × category, or None.

        apps.metering.selectors.unit_row(unit_id)            -> .rate_plan_id
        apps.rating.selectors.deposit_rule_for(plan, type)   -> {amount, currency}

    **`BR-RAT-020/023` put the figure on `plan_deposit_rules`** (rate_plan ×
    account_type, r5 #8), and it is a TENANT SETTING — editable on Plans &
    Rates — not a constant. The chain is `accounts.unit_id` (the reviewed
    cross-module FK, B2 §2) → `units.rate_plan_id` → rating's own read, which
    is exactly the chain `unit_plan_in_force` above already walks for the plan
    NAME; this one needs the id rather than the ref, which is why it walks it
    again instead of parsing a display payload.

    ⚠ **THIS IS THE READ `apps/payments/purposes.py` HAS BEEN NAMING AND NOT
    FINDING.** `DEPOSIT_REQUIREMENT_READ = "deposit_requirement_for_account"`
    is its contract for the same fact, published from RATING and keyed by
    ACCOUNT. It still does not exist, so every deposit-purpose payment still
    carries `deposit_requirement_not_checked` — this seam does not close that,
    because a customers-side read is not what payments resolves. Filed, not
    quietly half-served.

    **FOUR WAYS TO `None`, all ordinary, none of them an error:**

      · the account names no unit — a master account is at an ADDRESS
        (`BR-CUS-1010`);
      · the account carries no type (nullable before 2026-08-18, migration
        0011);
      · the unit stands on no plan — `rate_plan_id` is nullable;
      · this plan asks no deposit of this category, which rating states as
        `None` *on purpose* and warns must not be read as zero.

    ⚠ **`unit_row` RAISES 404-never-403 FOR ANOTHER TENANT'S UNIT (HR-1) AND
    THAT IS CAUGHT HERE**, the posture `unit_plan_in_force` documents: on a
    deposit the subject is the account, and letting metering's refusal escape
    would fail a whole move-in over one reference figure.
    """
    if unit_id is None or account_type_id is None:
        return None
    from core import errors as core_errors

    unit_fn = resolve("metering", "unit_row", kind="selectors")
    rule_fn = resolve("rating", "deposit_rule_for", kind="selectors")
    if unit_fn is None or rule_fn is None:
        return None
    try:
        unit = unit_fn(unit_id)
    except core_errors.NotFoundError:
        return None
    plan_id = getattr(unit, "rate_plan_id", None)
    if plan_id is None:
        return None
    # `OQ-RAT-12786` (CLOSED 2026-10-03) — the unit travels so a deposit code
    # priced by meter size is asked at THIS connection's size; `DEF-CUS-9521`
    # (PO 2026-10-04, *"(c) Let the clerk pick the size on the Deposit step."*)
    # — where no meter is fitted, the size the clerk picked travels too.
    row = rule_fn(plan_id, account_type_id, unit_id=unit_id, size_class=size_class)
    return dict(row) if row is not None else None


def deposit_awaiting_clearance(account_id: Any) -> Any:
    """Deposit-purpose money recorded and not yet cleared, or None if unasked.

    `apps.payments.credit.deposit_awaiting_clearance(account_id) -> Decimal`
    (`DEF-CUS-9755`). None is *payments could not be asked*, never a zero.
    """
    fn = resolve("payments", "deposit_awaiting_clearance", kind="credit")
    return fn(account_id) if fn is not None else None


def record_deposit_payment(**payment: Any) -> dict[str, Any] | None:
    """A deposit taken at the counter → payments' own service.

        apps.payments.services.record_payment(
            actor, account_id=…, amount=…, posted_at=…,
            method_code=…, confirmation=…, purpose="deposit",
            idempotency_reference=…,
        ) -> RecordedPayment

    **`BR-CUS-037`: customers writes no financial table.** The wizard validates
    and confirms; `payments` records the row, allocates nothing (a deposit
    meets no bill and becomes no credit — `BR-PAY-012`), and its `ledger_seam`
    posts `DR undeposited funds / CR deposit liability 2300` through the ledger
    posting service, which hard rule 5 keeps as the sole writer of journal
    lines. Nothing about that is re-implemented here.

    ⚠ **`purpose` IS SET HERE AND IS NOT THE CALLER'S TO CHOOSE.** This seam
    exists to take a DEPOSIT; a caller that could pass `purpose="bill"` through
    it would be allocating a customer's held money against their invoices,
    which is the one thing `BR-CUS-025` forbids. Any `purpose` in `payment` is
    overwritten.

    Unwired ⇒ None, and `deposit.take` then REPORTS that it could not record
    the money rather than answering "recorded" — the G20 rule, and the posture
    `propose_payment_plan` above takes for the same boundary.
    """
    fn = resolve("payments", "record_payment")
    if fn is None:
        return None
    actor = payment.pop("actor", None)
    payment["purpose"] = "deposit"
    recorded = fn(actor, **payment)
    if recorded is None:
        return None
    # ⚠ **`deposit_held_after` IS READ BACK, NEVER RE-DERIVED.** `BR-CUS-670`'s
    # register writer (`services.record_deposit_movement`) is what moves
    # `accounts.deposit_on_file`, and `record_payment` calls it inside its own
    # transaction when the deposit is POSTED. A second writer on this side would be
    # two paths to one column, which is the shape `DEF-154` and `OQ-238` both
    # are — so the figure is forwarded and nothing here writes it.
    return {
        "payment_id": getattr(recorded, "payment_id", None),
        "payment_no": getattr(recorded, "payment_no", None),
        "status": getattr(recorded, "status", None),
        "created": bool(getattr(recorded, "created", True)),
        "held_after": getattr(recorded, "deposit_held_after", None),
        "posted_to_ledger": bool(getattr(recorded, "posted_to_ledger", False)),
        "problems": tuple(getattr(recorded, "problems", ()) or ()),
    }


def aging_state(account_id: Any) -> str | None:
    """BR-CUS-016: Current / 30d past / 60+ past is DERIVED from open-invoice
    due-date math and is NEVER stored. Billing owns the invoices, so until W3
    this is None — the S17 pill renders the STORED status only, and no aging
    claim is made. A fabricated "Current" would be a claim about money."""
    fn = resolve("billing", "account_aging_state")
    return fn(account_id) if fn is not None else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@bbed56d (slice 3 — the billing seam US-CUS-005 TC-6 needs; co-packets US-CUS-004@bbed56d · US-CUS-003@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-11 by story-coder (W2 customers slice 2 = the account write path + its API · slice 3 = `last_issued_invoice_period_end`) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane) · AMENDED 2026-08-26 by the CR-038 W9-seam lane (task 2: `reads_for_unit` — the metering read seam `move_reads.py` §4 named as missing; resolves `apps.metering.selectors.reads_for_unit` by NAME with the kind explicit (DEF-035), None-when-unwired so consumers STATE the absence (DEF-075/DEF-127); ⚠ B2 §2 interface-register row OWED — flagged for central write-back, 04-docs is not this lane's to edit)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — seam module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: all three billing seams (`last_issued_invoice_date`, `aging_state`, `last_issued_invoice_period_end`) are DOCUMENTED and unwired — W3 owns `invoices` and billing has no tables; the first two return None so the S17 cells render absent rather than a fabricated value (metering's `collected_read_count` precedent), and the third makes every move-out REPORT that US-CUS-005 TC-6's issued-bill check could not run rather than letting silence read as "it passed" · no metering WRITE seam is consumed: BR-CUS-021's reads commit through metering's own S28 batch path, and a single-meter batch minted from here could collide with the month's real import on the BR-MET-018 fingerprint (REPORTED; `final_reads`/`initial_reads` are refused inputs) · no rating seam is consumed: the account-side plan snapshot is BR-CUS-029 `account_plan_assignments`, which has no DDL in any signed document, so this lane reads the unit's plan through metering ONLY to answer BR-MET-040 and stores nothing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
