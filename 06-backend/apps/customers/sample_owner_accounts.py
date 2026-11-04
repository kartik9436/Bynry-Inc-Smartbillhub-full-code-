# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S14 (the
#           Premises list and its Owner column — the screen the PO was looking
#           at) · S17 / S21 (the Accounts list, its `Master` pill, and the
#           Accounts tab on a master account, BR-CUS-1048)
# Change:   DEF-MET-6302 — PO 2026-09-23, verbatim: *"attach master accounts to
#           the sample data"*. Measured on a seeded `brazosbend` clone the same
#           day: 79 premises, **0** of them naming a master account.
# Rules:    BR-CUS-1010 (a master account is the owner's account AT AN ADDRESS;
#           it names a premises and need name no unit) · BR-CUS-068 as amended
#           (an ordinary `accounts` row, `kind='master'`, no new table; the
#           common-area clause is REVERSED) · BR-MET-400 (*"Premises -> owner =
#           Master account"*) · BR-MET-1181 (the address DECLARES its account)
#           · BR-MET-1030 (`ensure_master_account_for_premises` is the one
#           entry) · BR-CUS-1011 (one owner account per address) · BR-CUS-1022
#           / BR-CUS-1024 (a company is identified by its Tax ID; no identifier,
#           no account) · BR-MET-151 clause 3 (never read a party's category off
#           a name) · BR-TEN-057 (`is_sample` on the OWNING row) · BR-TEN-060
#           (an unloaded block is a NAMED line) · BR-TEN-063 (idempotent) ·
#           BR-TEN-061 (removal order) · BR-TEN-043 (no literal dates)
# Change:   BR-CUS-1094 (PO 2026-09-23, CLOSING OQ-CUS-12609) landed the same
#           day: a VACANT unit is billed to its premises' master account and an
#           occupied one to its tenant. Billing cannot do that yet, so nothing
#           here flows — and this fixture is the shape that ruling will be built
#           against. See the closing section of the docstring.
# Tests:    06-backend/tests/test_def_met_6302_seeded_owner_accounts.py
# Impacts:  apps/tenancy/sample_data.py (the orchestrator's block row) ·
#           apps/customers/sample_data.py (the removal release) ·
#           apps/customers/seams.py (three metering contracts) ·
#           core/sample_fixture.py (the reserved tax ids and the rule's figures)
# ───────────────────────────────────────────────────────
"""**The estate's OWNER ACCOUNTS — one per address whose owner is not its
occupier, and none anywhere else.**

WHAT WAS WRONG, IN THE ONE SENTENCE A CLERK WOULD USE
------------------------------------------------------
Open the Premises list on a freshly seeded utility and the **Owner** column is
empty on every row. It was empty honestly: `premises.master_account_id` is the
column that fills it (`BR-MET-1181`, PO 2026-09-22) and **no seeder in this
product had ever written one**. `DEF-709` seeds a single master account for the
developer at `500 Main St` — through customers' own door, which does not touch
`premises` — so even that one address did not name it.

Measured on a seeded `brazosbend` clone, 2026-09-23:

    premises (not deleted)                        79
    premises naming a master account               0
    accounts with kind='master'                    1   (DEF-709's, at 500 Main St)
    premises_owners rows                           5
    premises_owners naming a master account        0

WHY NOT SIMPLY FILL THE COLUMN ON EVERY ROW
--------------------------------------------
PO, in the same instruction: *"a demo where all 80 properties have an identical
master account teaches a clerk nothing and hides the cases that matter"*. An
owner-occupier does not need a separate account naming themselves, and a demo
that pretends otherwise teaches the wrong habit to the person who will set a
real utility up.

**THE RULE, AND EVERY CLAUSE OF IT IS A DECLARED FACT RATHER THAN A GUESS.**
A seeded address receives its owner's account when all three hold:

  1. **the fixture NAMES an owner for it** (`premises.owner_manager`) — nothing
     is invented for an address nobody has said the owner of;
  2. **it holds at least `OWNER_ACCOUNT_MIN_UNITS` (2) active units**, which is
     the arithmetic that says the owner cannot be its only occupier; and
  3. **the fixture does not state that owner an OWNER-OCCUPIER**
     (`OWNER_CATEGORY_BY_NAME`).

⛔ **CLAUSE 2 IS NOT A HEURISTIC ABOUT A NAME, AND THE DISTINCTION IS
`BR-MET-151` CLAUSE 3.** That rule forbids reading a party's category off a
string — *Whitfield Rentals LLC* is not evidence of a landlord — and
`test_cr039_c14__no_seeded_owner_has_an_INVENTED_category` has already failed one
seeder for trying. A unit COUNT is a fact about the building.

⚠ **AND IT IS DERIVED, NEVER AN ALLOW-LIST OF ADDRESSES — `DEF-MET-4288`'s
LESSON, IN THE MODULE THAT LEARNED IT.** The premises geo fill used a literal
address list, so every estate added after it was excluded *by construction and
in silence*, and 17 of 17 work orders fell off the map with nothing reading as
broken. This block walks the tenant's own sample premises, and
`owner_account_report()` NAMES every address it passed over with the clause that
excluded it — a blind spot with a number beside it is not a blind spot.

WHAT THE ESTATE LOOKS LIKE AFTERWARDS (measured, 2026-09-23)
-------------------------------------------------------------
Five addresses of the 73 sample premises name an owner's account:

    500 Main St            31 units   AC-2026-00051   Ridge Property LLC
    Kestrel Park ph. 2     12 units   AC-2026-00052   Kestrel Park Developments
    301 Mill Pond Ln        6 units   AC-2026-00053   Mill Pond Apartments LP
    181 Willow Bend Dr      2 units   AC-2026-00054   Silver Creek Duplex Holdings
    183 Cedar Ridge Way     2 units   AC-2026-00054   Silver Creek Duplex Holdings

Sixty-eight do not, and each falls into one of two stated cases: **65** have no
owner party named at all (62 single-family houses, 2 commercial units and the
municipal depot), and **3** are single-suite commercial premises whose
`owner_manager` IS their occupying customer — `Northwind Mfg.`, `Quarry Hill
Diner`, `Creekside Laundromat`.

**THREE ACCOUNTS ARE OPENED AND FIVE DECLARATIONS ARE WRITTEN**, which is the
whole of the block's reported count (5). Two of those five are not new accounts:
`500 Main St` already held `DEF-709`'s and was missing only the declaration.

⛔ **AND THE TWO DUPLEXES SHARE ONE ACCOUNT — `AC-2026-00054` — WHICH IS THE
PRODUCT'S OWN MODEL AND NOT A COLLISION.** They have one typed owner record
between them, so the door takes its typed-owner branch and `ensure_owner_master_
account` is *ensure* **for the OWNER**: the landlord's existing account comes
back and the second address declares that. `BR-CUS-1011` reads *at most one
owner account per address*, never *exactly one per address*, and
`premises.master_account`'s own `PROTECT` comment states the intended shape in
as many words — *"an account twelve addresses are billed through"*. It is the
case a clerk meets first (one landlord, several buildings) and the estate now
demonstrates it rather than only describing it.

TWO THINGS THIS BLOCK DELIBERATELY DOES NOT DO
-----------------------------------------------
1. **It moves no money.** None of these five addresses has a common-area unit
   except `500 Main St`, whose one common area is already covered by `DEF-709`'s
   account — so every account this block opens covers nothing, bills nothing and
   produces no document (*no lines, no document*, the 2026-08-31 ruling).

   ⛔ **AND THAT SENTENCE NOW HAS A CLOCK IN IT — `BR-CUS-1094`, RULED THE SAME
   DAY (`OQ-CUS-12609`, CLOSED 2026-09-23).** *"5 teannt bill will go to them to
   their regualr account, but for 5 vacant units - bill will be generated
   against master account"*. **Billing has no concept of a master account
   today** — every `master` in `apps/billing/` is `master_data_ref`, unrelated —
   so nothing flows now and this block decides nothing about a bill. But the
   moment that ruling is built, `Kestrel Park ph. 2` — **12 units, all vacant,
   with an owner account** — is precisely the case it describes, and the
   single-family street is its one deliberately-unruled clause: *a vacant unit
   whose premises has NO master account*, where the charge has no payer and the
   run must say so rather than skip the unit silently.

   ⚠ **SO THIS IS THE FIXTURE THAT RULING WILL BE BUILT AGAINST, AND IT IS SAID
   OUT LOUD HERE RATHER THAN DISCOVERED.** A lane building `BR-CUS-1094` needs a
   seeded vacant block with a master and a seeded vacant unit without one; the
   estate now has both, for reasons that had nothing to do with billing. It is
   also a thing to re-read before changing the rule above: widening which
   addresses get an account would silently move which units acquire a payer.
2. **It invents no owner RECORD.** `Kestrel Park Developments` is a name with no
   category in `OWNER_CATEGORY_BY_NAME`, so it has no `premises_owners` row, and
   minting one would need a category read off its name. That address therefore
   takes `ensure_master_account_for_premises`' SECOND branch — the account is
   opened for the ADDRESS and the party stays on `PRM-04`'s matching worklist —
   which is exactly the shape `BR-MET-1181` was ruled for, demonstrated on the
   estate instead of only in a test.

WHY THIS FILE LIVES IN `customers` AND NOT IN `metering`
---------------------------------------------------------
The rows that have to carry `is_sample` are `accounts`, `contacts`, `addresses`
and `service_agreements` — all customers' — and **BR-TEN-057 puts the tag on the
OWNING row, which only the owning module may write**. Metering could not tag
what it caused to be created. The premises DECLARATION is metering's and stays
metering's: it is written by metering's own door, reached through
`apps/customers/seams.py`, exactly as the reverse call already works.

⚠ **AND REMOVAL IS WHY IT HAD TO BE THIS WAY ROUND.** `premises.master_account`
is `PROTECT` and BR-TEN-061 removes **customers before metering**, so a
declaration written anywhere else would make customers' remover hit
`ProtectedError` and RETAIN four accounts under the sentence *"it has bills or
payments against it"* — which would be false. `release_sample_owner_accounts()`
below is called first thing in `remove_sample_records`, so the link is gone
before the account is.

⚠ **IT IS ITS OWN BLOCK RATHER THAN MORE OF `customers:seed_sample_records`** —
`BR-TEN-060`, the same reasoning `assets:seed_sample_aged_meters` gives one
screen up: four accounts inside a block that writes fifty are invisible whether
they land or not, and a named line on the Sample data panel can be SEEN to have
failed. It also places the block after the fifty, so not one of the estate's
pinned account numbers moves.

WHAT HAS TO HAVE RUN FIRST, AND IT IS TWO DIFFERENT KINDS OF FIRST
--------------------------------------------------------------------
**metering's estate block**, because there is no seeded address to own until
metering's estate block has planted the premises and the units this rule counts
— a data dependency, and the block reports a bare zero without it.

**customers' own accounts block**, for a reason that is not a row at all: the
account NUMBER SERIES. Four accounts opened ahead of the estate's fifty would
renumber all fifty (`BR-TEN-035`), and the estate's numbers are pinned in tests,
worked examples and screenshots.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.customers import models, seams, selectors
from core import sample_fixture as fixture
from core.permissions import SYSTEM_ADMIN
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.customers")

#: Why an address was passed over, in the words the report prints. One code per
#: clause of the rule, so a reader can tell WHICH test excluded an address
#: rather than only that something did.
SKIP_NO_OWNER_NAMED = "no_owner_named"
SKIP_SINGLE_UNIT = "single_unit"
SKIP_OWNER_OCCUPIER = "owner_occupier"
SKIP_NO_TAX_ID = "no_tax_id_declared"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _tag(queryset: Any) -> int:
    """BR-TEN-057 — the tag goes on the OWNING row, and this module owns these.

    `update()` rather than a save loop: `is_sample` is not a money column, the
    rows were created moments ago inside this block, and there is nothing to
    audit about a fixture label (the account's own creation already wrote its
    `account.master_created` row).
    """
    return int(queryset.update(is_sample=True))


class _Candidate:
    """One address, its owner, and what the rule decided about it."""

    def __init__(
        self,
        *,
        premises_id: str,
        address_line: str,
        owner_manager: str | None,
        units: int,
        declared_account_id: Any,
        declared_source: str | None,
        owner_id: Any = None,
        owner_account_id: Any = None,
    ) -> None:
        self.premises_id = premises_id
        self.address_line = address_line
        self.owner_manager = (owner_manager or "").strip()
        self.units = units
        self.declared_account_id = declared_account_id
        self.declared_source = declared_source
        #: The TYPED party record, where the fixture states a category for this
        #: owner — and its own `master_account_id`, which is a second `PROTECT`
        #: and therefore a second thing removal has to release.
        self.owner_id = owner_id
        self.owner_account_id = owner_account_id

    @property
    def tax_id(self) -> str | None:
        """The owner's declared identifier, or `None` — *the fixture states
        none*, which `BR-CUS-1024` makes a refusal rather than a gap.

        ⚠ **`500 Main St` IS KEYED ON ITS ADDRESS CONSTANT AND NOT ON ITS
        OWNER'S NAME**, so this file spells no owner's name at all. That address
        already carries `CR030_COMMON_AREA_OWNER_TAX_ID` on the customer
        `DEF-709` created for it, and writing *"Ridge Property LLC"* here to look
        it up would be the drifting second copy the fixture keeps refusing to
        make — one that a rename of the party would silently break.
        """
        if self.address_line == fixture.CR030_COMMON_AREA_ADDRESS:
            return fixture.CR030_COMMON_AREA_OWNER_TAX_ID
        return fixture.OWNER_ACCOUNT_TAX_IDS.get(self.owner_manager)

    def skip_reason(self) -> str | None:
        """`None` where this address should hold an owner's account.

        The clauses are tested in the order the docstring states them, and the
        FIRST failure is what the report names — so *"no owner named"* is never
        reported as *"single unit"* for an address that is both.
        """
        if not self.owner_manager:
            return SKIP_NO_OWNER_NAMED
        if self.units < fixture.OWNER_ACCOUNT_MIN_UNITS:
            return SKIP_SINGLE_UNIT
        if fixture.owner_category_for(self.owner_manager) == fixture.OWNER_CATEGORY_OWNER_OCCUPIER:
            return SKIP_OWNER_OCCUPIER
        if not self.tax_id:
            # BR-CUS-1024, PO 2026-09-01: *"Without identifier we cannot create
            # Customer ID or master account ot regular account"*. A NAME is not
            # an identity, so an owner the fixture has not identified is
            # REPORTED rather than given an account the product would refuse.
            return SKIP_NO_TAX_ID
        return None


def _sample_premises() -> list[_Candidate]:
    """Every SAMPLE premises on this tenant, with its unit count and whatever it
    already declares — read through metering's own selectors.

    ⚠ **`is_sample` IS THE WHOLE PREDICATE, AND IT HAS TO BE.** A tenant that
    has started entering its own addresses has real premises in this list, and a
    seeder that opened an account against one of those would be inventing an
    owner for a building a utility actually operates.

    Two selector calls and one link read per candidate, rather than a join:
    `premises` and `units` are metering's tables and customers may not query
    them (B1/B8). The cost is a seeding-time cost on ~80 rows, paid once.
    """
    premises_rows = seams.resolve("metering", "premises_list", kind="selectors")
    units_rows = seams.resolve("metering", "units_list", kind="selectors")
    if premises_rows is None or units_rows is None:
        return []

    units_by_premises: dict[str, int] = {}
    for unit in units_rows():
        key = str(getattr(unit, "premises_id", "") or "")
        if key:
            units_by_premises[key] = units_by_premises.get(key, 0) + 1

    out: list[_Candidate] = []
    for row in premises_rows():
        if not getattr(row, "is_sample", False):
            continue
        premises_id = str(row.id)
        account_id, source = seams.premises_master_account_link(premises_id)
        out.append(
            _Candidate(
                premises_id=premises_id,
                address_line=row.address_line,
                owner_manager=row.owner_manager,
                units=units_by_premises.get(premises_id, 0),
                declared_account_id=account_id,
                declared_source=source,
                owner_id=getattr(row, "owner_id", None),
                owner_account_id=(
                    getattr(row.owner, "master_account_id", None)
                    if getattr(row, "owner_id", None)
                    else None
                ),
            )
        )
    out.sort(key=lambda c: (-c.units, c.address_line))
    return out


def _plan() -> tuple[list[_Candidate], list[_Candidate], list[dict[str, Any]]]:
    """`(every sample premises, the ones selected, the ones skipped with why)`.

    One pass, so the report a human reads and the list the seeder writes from can
    never be two different answers to one question.
    """
    candidates = _sample_premises()
    selected: list[_Candidate] = []
    skipped: list[dict[str, Any]] = []
    for candidate in candidates:
        reason = candidate.skip_reason()
        if reason is None:
            selected.append(candidate)
        else:
            skipped.append({**_row(candidate), "reason": reason})
    return candidates, selected, skipped


def _row(candidate: _Candidate) -> dict[str, Any]:
    return {
        "premises_id": candidate.premises_id,
        "address_line": candidate.address_line,
        "owner_manager": candidate.owner_manager or None,
        "units": candidate.units,
    }


def owner_account_report() -> dict[str, Any]:
    """BR-TEN-060's named lines — *what this block did, and what it passed over
    and why*, without writing anything.

    ⛔ **THE SKIPPED LIST IS THE POINT, NOT A COURTESY.** `DEF-MET-4288` and
    `G32` are the same shape one layer apart: a fill pass that quietly excluded
    every estate added after it, and a check that truthfully reported `0
    unresolved` over 21 refusals it could not see. **A declared blind spot with
    no NUMBER beside it is indistinguishable from an empty one**, so this prints
    what it skipped beside what it selected, every time.
    """
    candidates, selected, skipped = _plan()
    return {
        "sample_premises": len(candidates),
        "selected": [
            {
                **_row(candidate),
                "account_id": (
                    str(candidate.declared_account_id) if candidate.declared_account_id else None
                ),
                "declared": bool(candidate.declared_account_id),
                "source": candidate.declared_source,
            }
            for candidate in selected
        ],
        "skipped": skipped,
    }


#: What a clerk reads for each skip reason. Plain words, no rule ids and no
#: internal codes — B14 rule 31/32, and `sample_notes.for_screen` strips a
#: reference rather than letting one through, which is a repair and not a
#: licence to write one.
#: ⚠ **`single_unit` READS *"hold one unit"* AND NOT *"are owner-occupied"*,
#: WHICH THE FIRST DRAFT SAID.** On today's estate the two are the same three
#: addresses — `Northwind Mfg.`, `Quarry Hill Diner`, `Creekside Laundromat`,
#: each occupied by the firm that owns it — but the CLAUSE that excluded them is
#: the unit count, and an estate that later adds a landlord's single house would
#: have been described on screen as owner-occupied when nobody had said so.
#: Hard-won law 1: a message naming a cause that is not the cause.
_SKIP_WORDS: dict[str, str] = {
    SKIP_NO_OWNER_NAMED: "name no owner",
    SKIP_SINGLE_UNIT: "hold one unit",
    SKIP_OWNER_OCCUPIER: "are owner-occupied",
    SKIP_NO_TAX_ID: "have no owner tax id",
}


def owner_account_note() -> str | None:
    """`DEF-3224`'s contract, applied to this block: the sentence that was going
    only to a log file goes to the Sample data panel too.

    ⛔ **B14 RULE 33 — EACH SENTENCE IS A FACT AND CAPS AT SIX WORDS**, so the
    count is stated three short ways rather than one long one, and the WHY is
    absent: rationale is ZERO WORDS ON SCREEN and the reasoning lives in this
    file and in the decision log, where a reader can find all of it.

    ⚠ **THE SKIPPED NUMBERS ARE IN IT DELIBERATELY.** *"Five addresses have an
    owner account"* on its own reads like a partial failure; with the other
    sixty-eight named and reasoned it reads as the estate it was designed to be.
    """
    _, selected, skipped = _plan()
    if not selected and not skipped:
        return None
    sentences = [f"{len(selected)} addresses show an owner account."]
    counts: dict[str, int] = {}
    for row in skipped:
        words = _SKIP_WORDS.get(row["reason"])
        if words:
            counts[words] = counts.get(words, 0) + 1
    sentences.extend(f"{n} {words}." for words, n in sorted(counts.items()))
    return " ".join(sentences)


def seed_sample_owner_accounts(actor: Any) -> int:
    """`DEF-MET-6302` — open each selected address's owner account and let the
    address DECLARE it. Returns the number of rows written.

    **IT WRITES THROUGH THE PRODUCT'S OWN DOOR AND NOWHERE ELSE.**
    `metering.premises_owners.ensure_master_account_for_premises` is
    `BR-MET-1030`'s single entry: it reaches `customers.create_master_account`
    through the seam — so `BR-CUS-017`'s family, `BR-CUS-1011`'s
    one-owner-account-per-address and `BR-CUS-1024`'s identity guard all apply —
    and it writes `premises.master_account_id` inside the same transaction, plus
    `premises_owners.master_account_id` wherever a typed owner exists.

    **IT IS IDEMPOTENT (BR-TEN-063).** An address that already DECLARES an
    account is skipped before the door is called, so a replay writes nothing,
    audits nothing and returns 0. `BR-CUS-1011` would refuse a second account
    anyway; this asks first so that a replay is silent rather than merely safe.

    ⚠ **AN ADDRESS THAT ALREADY HAS AN ACCOUNT IS DECLARED AND NOT RE-OPENED,
    AND THAT BRANCH IS `DEF-MET-6303` (measured, not guessed).** `500 Main St`
    holds `DEF-709`'s account, opened through customers' own door before
    `BR-MET-1181` existed, and declares nothing. Calling the `ensure` door for it
    was tried on a live PostgreSQL clone and **refused with `BR-CUS-068
    unit_already_occupied`** — the door defaults its coverage to every common
    area of the premises, that building has one, and `DEF-709`'s account already
    covers it. So the door never reaches its own `BR-CUS-1011` branch, that
    branch would not have declared the link either, and the address stayed empty.
    Here the account is found through `selectors.master_account_at_premises` —
    the same one query `BR-CUS-1011`'s guard asks — and the declaration is
    written through `declare_premises_master_account`, which is the door the
    Premises edit form uses when a clerk names an account that already exists.

    ⚠ **LAW 14 — EACH ADDRESS GETS ITS OWN SAVEPOINT.** One refused owner must
    not take the other four with it, and on PostgreSQL a failed statement aborts
    the whole transaction: without the nested `atomic()` the `except` below would
    be a handler that cannot handle anything, and the suite would never say so
    because `config/settings/test.py` runs on sqlite, which has no aborted-
    transaction state.
    """
    candidates, selected, skipped = _plan()
    if not selected:
        # BR-TEN-060 — a block that wrote nothing says why, by name.
        logger.info(
            "sample data (DEF-MET-6302): no seeded address qualifies for an owner's "
            "account (%s sample premises examined, %s); the Premises list's Owner "
            "column stays empty and S14 has nothing to demonstrate",
            len(candidates),
            _skip_summary(skipped),
        )
        return 0

    written = 0
    for candidate in selected:
        if candidate.declared_account_id:
            continue  # BR-TEN-063 — a replay writes nothing.
        existing = selectors.master_account_at_premises(candidate.premises_id)
        if existing is not None:
            # `DEF-MET-6303` — the address HAS its account and only the
            # declaration is missing. Opening a second one is what `BR-CUS-1011`
            # exists to refuse, so nothing is opened.
            _tag_account(existing.id)
            written += int(
                seams.declare_premises_master_account(
                    actor, candidate.premises_id, str(existing.id)
                )
            )
            continue
        written += _open_and_declare(actor, candidate)
    logger.info(
        "sample data (DEF-MET-6302): %s owner account(s)/declaration(s) written over "
        "%s selected address(es); %s sample premises deliberately have none (%s)",
        written,
        len(selected),
        len(skipped),
        _skip_summary(skipped),
    )
    return written


def _skip_summary(skipped: list[dict[str, Any]]) -> str:
    """`no_owner_named 65 · single_unit 3` — the count beside each reason.

    Counted rather than listed: 68 addresses in a log line is a line nobody
    reads, and the addresses themselves are in `owner_account_report()`.
    """
    counts: dict[str, int] = {}
    for row in skipped:
        counts[row["reason"]] = counts.get(row["reason"], 0) + 1
    return " · ".join(f"{reason} {n}" for reason, n in sorted(counts.items())) or "none"


def _open_and_declare(actor: Any, candidate: _Candidate) -> int:
    """One address: the account, its tag, and the declaration. 0 on a refusal."""
    payload = {
        # No default is invented for either of these — the same posture
        # `ensure_owner_master_account` takes. The consumer category is
        # `OWNER_ACCOUNT_TYPE` and the fixture states why; the account opens on
        # the TENANT'S today, decided when the seed runs (BR-TEN-043, DEF-629:
        # a typed date is a clock waiting to expire).
        "account_type": fixture.OWNER_ACCOUNT_TYPE,
        "opened_at": str(seams.tenant_today()),
        # `contact` is OMITTED on purpose: with none, the door takes the
        # premises' own `owner_manager` as the payer, which is what BR-CUS-068
        # defines and what the estate already holds. Typing it here would be a
        # second, drifting copy of a fact the premises states.
        "customer": {
            "kind": "company",
            "identity": {"tax_id": candidate.tax_id},
        },
    }
    try:
        # DEF-2722 · law 14 — a SAVEPOINT, so this `except` really can continue.
        with transaction.atomic():
            answer = seams.ensure_master_account_for_premises(actor, candidate.premises_id, payload)
    except Exception as exc:  # noqa: BLE001 — one refusal must not fail the plant
        logger.info(
            "sample data (DEF-MET-6302): the owner's account at %s was refused (%s: %s) "
            "— that address keeps an empty Owner column and every other address is "
            "unaffected",
            candidate.address_line,
            type(exc).__name__,
            exc,
        )
        return 0
    if answer is None:
        logger.info(
            "sample data (DEF-MET-6302): metering publishes no "
            "premises_owners.ensure_master_account_for_premises, so no owner account "
            "could be opened for %s",
            candidate.address_line,
        )
        return 0

    account_id = answer.get("account_id")
    if answer.get("created"):
        _tag_account(account_id)
        return 1
    if account_id:
        # The door found an account it did not open — its `BR-CUS-1011` branch,
        # which returns the id and declares nothing (`DEF-MET-6303`). The loop
        # above normally reaches that case first and never gets here; this is the
        # race where an account arrived between the two reads, and it takes the
        # same repair rather than leaving the Owner column empty.
        _tag_account(account_id)
        return int(seams.declare_premises_master_account(actor, candidate.premises_id, account_id))
    return 0


def _tag_account(account_id: Any) -> None:
    """BR-TEN-057 on all four owning rows, the same set
    `_seed_developer_master_account` tags.

    ⚠ **`is_sample=False` IS IN EVERY FILTER, DELIBERATELY.** Tagging is
    idempotent that way, and it means this can never re-tag a row another block
    already counted — the same discipline DEF-709's block takes one file over.

    ⚠ **IT TAGS TWO ROW KINDS `DEF-709`'s BLOCK DOES NOT, AND THAT IS STATED
    RATHER THAN LEFT TO LOOK ACCIDENTAL.** That block tags the account, its
    contact, its address and its service agreements; it does not tag the
    `customers` row its own path created, nor the `customer_accounts` link. Both
    ARE sample rows — the sample seeder made them — and `remove_sample_records`
    selects on the tag, so an untagged one survives a removal the operator was
    told had finished. **Measured on a live clone: after this block runs,
    `Ridge Property LLC`'s customer carries the tag where it did not before**,
    and a full removal then leaves zero master accounts and zero links. It
    cannot over-reach: the remover only deletes a sample customer that no
    account still references, so a party a real account also uses is never
    touched.
    """
    tenant_id = _tenant_id()
    accounts_qs = models.Account.objects.filter(tenant_id=tenant_id, pk=account_id)
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


class _RemovalActor:
    """The acting user, as metering's role-gated door has to see one.

    ⛔ **THE SEAM GIVES REMOVAL NO ACTOR, AND THAT IS THE WHOLE REASON THIS
    CLASS EXISTS.** `remove_sample_data` resolves each module's
    `remove_sample_records` and calls it with NO arguments — every remover in the
    product deletes its rows straight through the ORM, unguarded, because the
    authorisation was already made at the entry: the S8 panel is role-gated at
    the API and the management command builds the same `SYSTEM_ADMIN` shim
    (`load_sample_data._SampleDataActor`). This carries that decision inward to
    the one door on this path that asks — `declare_premises_master_account`,
    `BR-SHL-025` — rather than reaching past its guard through `__wrapped__`.

    ⚠ **IT NAMES NO USER, DELIBERATELY.** `id` is `None`, so the release's audit
    row records *no named user*, which is the truth: the seam did not say who.
    The person who pressed the button IS named, once, on the run-level
    `sample.removed` row the orchestrator writes. Inventing a user id here would
    be a worse answer than an honest absence (hard-won law 1).
    """

    id = None
    pk = None
    role = SYSTEM_ADMIN
    roles = (SYSTEM_ADMIN,)
    is_authenticated = True


def release_sample_owner_accounts(actor: Any = None) -> list[dict[str, Any]]:
    """Stop every SAMPLE address naming a SAMPLE account, before the accounts go.

    ⛔ **BR-TEN-061 REMOVES CUSTOMERS BEFORE METERING, AND
    `premises.master_account` IS `PROTECT`.** Without this, the four accounts
    this block opened would raise `ProtectedError` inside
    `remove_sample_records`' per-account `except`, and every one of them would be
    RETAINED under the sentence *"it has bills or payments against it"* — a
    sentence that would be false, on a panel a utility reads to decide whether
    its demo data is gone. Hard-won law 1: a message claiming a reason is not the
    reason.

    ⚠ **IT RELEASES ONLY WHERE BOTH SIDES ARE SAMPLE ROWS.** A real address that
    a utility has pointed at a sample account, or a sample address pointed at a
    real account, is left exactly as it is and is NOT reported as removed —
    removal is partial and named (BR-TEN-066), never quietly wider than asked.

    Returns the rows it could not release, in `remove_sample_records`' `retained`
    shape, so an unwired door is reported rather than silently skipped.
    """
    sample_account_ids = {
        str(pk)
        for pk in models.Account.objects.filter(tenant_id=_tenant_id(), is_sample=True).values_list(
            "pk", flat=True
        )
    }
    acting = actor if getattr(actor, "role", None) else _RemovalActor()
    retained: list[dict[str, Any]] = []
    released_owners: set[str] = set()
    for candidate in _sample_premises():
        # ── the ADDRESS's declaration ────────────────────────────────────
        account_id = candidate.declared_account_id
        if account_id and str(account_id) in sample_account_ids:
            if not seams.declare_premises_master_account(acting, candidate.premises_id, None):
                retained.append(
                    {
                        "label": f"owner account link at {candidate.address_line}",
                        "reason": (
                            "metering publishes no declare_premises_master_account, so "
                            "the address still names this account and the account "
                            "cannot be deleted while it does"
                        ),
                    }
                )
        # ── the OWNER RECORD's declaration ───────────────────────────────
        # ⚠ **A SECOND `PROTECT`, AND FORGETTING IT LEFT TWO ACCOUNTS RETAINED
        # UNDER A REASON THAT WAS NOT THEIRS** (measured 2026-09-23:
        # `AC-2026-00053` and `AC-2026-00054`, both with zero invoices, both
        # reported as *"it has bills or payments against it"*). Where a typed
        # owner exists, metering writes BOTH columns in one transaction, so
        # both have to be released or the release is only half of one.
        owner_account_id = candidate.owner_account_id
        if (
            candidate.owner_id
            and owner_account_id
            and str(owner_account_id) in sample_account_ids
            and str(candidate.owner_id) not in released_owners
        ):
            released_owners.add(str(candidate.owner_id))
            if not seams.link_owner_master_account(acting, candidate.owner_id, None):
                retained.append(
                    {
                        "label": f"owner record link for {candidate.owner_manager}",
                        "reason": (
                            "metering publishes no link_owner_master_account, so the "
                            "owner record still names this account and the account "
                            "cannot be deleted while it does"
                        ),
                    }
                )
    return retained
