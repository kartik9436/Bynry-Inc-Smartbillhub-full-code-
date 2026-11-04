# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-088 (PO ruling 2026-08-20 — THE CHARGE CODE OWNS THE BASE
#           AMOUNT; supersedes BR-RAT-012 and BR-RAT-027, retires
#           `tariff_versions.base_charge`) · BR-RAT-103 (PO ruling 2026-08-21 —
#           a charge code prices ONE customer class; the base narrows by
#           SERVICE → ACCOUNT TYPE → METER SIZE) · BR-RAT-092 (the decimal rule
#           for money columns) · BR-RAT-080 (a base is charged because a
#           connection EXISTS, so it is a THING, so it is a charge code) ·
#           BR-RAT-035 (amounts are seeds, never constants) ·
#           CLAUDE.md hard rules 1 (tenant scoping), 2 (money), 7 (audit)
# Defects:  DEF-455 (the seeder writes no base charge codes) · DEF-452 (every
#           seeded plan has NO customer class — the blocker this command hits
#           on the shipped fixture) · DEF-438 (the R1–R7 chain has no
#           production caller) · DEF-468 (two surviving base codes REFUSE) ·
#           DEF-477 (the cleared column is REFILLED with 0 by the next ordinary
#           plan save — the precondition this report prints) ·
#           DEF-467/DEF-469 (the class column this migration needs) ·
#           DEF-154 / DEF-277 (why `gather._base_charge_for` reads two columns)
# Tests:    06-backend/tests/test_br_rat_088_base_migration.py
# Impacts:  `plan_services.base_charge` (cleared) · `charges` (minted) ·
#           `apps/billing/gather._base_charge_for` (the live read this command
#           does NOT own and cannot flip — see THE LIVE PATH below)
# ───────────────────────────────────────────────────────
"""`manage.py migrate_base_to_charge_codes` — move the base amount off the plan
and onto class-scoped `is_base` charge codes, per BR-RAT-088.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING
-------------------------------------
This file moves money between the two objects that decide what a customer's base
charge is. It is a 🔒 sensitive path twice over (CLAUDE.md: *rating math* and
*migration ordering*), authored by AI under the PO ruling of 2026-08-09 (*"AI
will do it; we will review it later as human"*), and it carries a row in
`12-governance/09-human-review-ledger.md`. **Nothing here invents a rule.**
BR-RAT-088 and BR-RAT-103 are the signed law; this executes them and REFUSES
wherever executing them would require a judgement they do not make.

⚠ WHAT IT DOES — AMENDED 2026-10-02 (`DEF-RAT-9139`, `DEF-RAT-9140`)
---------------------------------------------------------------------
**IT CREATES NO CHARGE CODE ANY MORE, AND THAT IS THE RULING, NOT A GAP.** PO,
2026-09-28 (decision log *"A STALE PLAN FIGURE MAY NOT STOP A BILL"*), verbatim:
*"we will never take default value from plan $8.0 - that is retired"*. Billing
reads the base ONLY from the charge code bound to the plan (`DEF-BIL-7170`), and
where none is defined and bound it bills `$0.00` with a warning (PO 2026-09-30).
So the two halves of the old migration now have opposite effects on a bill:

  * **clearing `plan_services.base_charge` moves NO bill** — nothing reads it;
  * **minting a code FROM that column would move bills** — a water bill that
    charges `$0.00` today (*base not set*) would charge the retired `$8.00`
    from the next run. That is the retired figure being read again, one
    indirection out, by a tool rather than by billing.

So, per row (decision log 2026-10-02 *"THE BASE MIGRATION CREATES NO CHARGE
CODE FROM A RETIRED PLAN FIGURE"*): billing's own functions are asked what the
bill charges for that plan's class TODAY. **Where the plan figure equals it, the
column is cleared** (an audit row keeps the old figure). **Where it differs, the
row is HELD — listed for a human, the column left as it is, and no code
created**: whether that utility should start charging `$8.00` is a pricing
decision a person makes on the charge code, never one a migration infers from a
column the PO retired. The codes such a person would need are still computed
and printed (the grouping and the four refusals below are unchanged), as
information — `action` reads `new` for a code that does not exist, `reuse` for
one that already charges exactly that figure.

⚠ **RE-READ 2026-10-06 (`DEF-RAT-9841`) AGAINST PO RULING 2026-10-06 — THE
PURPOSE SURVIVES AND THE MEASUREMENT WAS ALREADY THE RULED ONE.** The ruling
(*"if it is not provided then you will take it zeo ; but you cannot take W-COM
because it is availabel in charge coede"*) removed the class-narrowed pool, so
"what the bill charges today" is now plan → rate schedule → the code it NAMES,
else `$0.00`. `_bill_base_today` already asks billing exactly that (it passes the
schedule's named code), so the command needed no new arithmetic: a residential
plan stating `$8.00` whose schedule names nothing is now, truthfully, a bill at
`$0.00` and a HELD row. What changed is the ADVICE: where an existing code
already charges the held figure for that class, the report says the cure is to
NAME that code on the rate schedule (*"if BASE-W were named on its rate
schedule"*), not to create one. **It still writes no schedule and names no code
for anyone** — which code a utility's schedule names is a person's choice
(*Rate schedules › Choose a base code*), never a migration's.

The ORIGINAL design, kept for the history: for every `(plan, service)` row
carrying a base charge, it minted or reused ONE `is_base` charge code for
`(service, customer class)` carrying that amount, and then cleared
`plan_services.base_charge`. The plan's class is
`RatePlan.account_type_id`; BR-RAT-103 gave `charges` the matching
`applies_to_customer_classes` column on 2026-08-21, and **before that column
existed this migration was not expressible at all** (DEF-467): Silver Creek's
water base is `$8.00` residential and `$15.00` commercial — one service, two
amounts — where the plan column is per PLAN and a charge code is per TENANT.

TWO PLANS STATING THE SAME AMOUNT ARE ONE CODE, NOT TWO
--------------------------------------------------------
Silver Creek's trash base is `$18.00` on BOTH plans. Minting two codes for it
would put two `is_base` codes on one service whose class scopes are disjoint —
legal, but it would also mean the utility maintains one figure in two rows,
which is the shape BR-RAT-088 exists to end. So codes are grouped by AMOUNT and
the class list is the union of the classes that stated it.

⚠ **THE CLASS LIST IS ENUMERATED, NEVER LEFT NULL.** BR-RAT-103 rules that NULL
or `[]` means EVERY class. A trash base stated by a residential plan and a
commercial plan is a statement about those two classes and about nothing else —
writing NULL would silently extend it to `industrial` and `government` accounts
that no plan priced. DEF-273's inclusion-list reasoning, applied to the base:
a class nobody listed is simply not in it.

WHERE IT REFUSES RATHER THAN GUESSING
-------------------------------------
Three refusals, and each one is a case where a single answer does not exist:

  1. **Two plans, same class, same service, DIFFERENT amounts.** There is no one
     code that can hold both, and picking either changes what somebody is
     billed.
  2. **A plan with no `account_type_id`.** An unscoped code means EVERY class,
     so it silently overrides a scoped one for accounts of other classes — the
     exact widening BR-RAT-103's inclusion list was chosen to prevent. On the
     fixture the product ships today this is EVERY plan (DEF-452, OPEN).
  3. **Two `is_base` codes surviving the narrowing for one account.**
     `resolution.resolve_base_charge` REFUSES on that and names them (DEF-468,
     2026-08-21), so a migration producing that state does not produce wrong
     bills — it produces REFUSED ones, for every account of the overlapping
     class.

A refusal stops the tenant, not the run: other tenants still report and still
apply. **This command never resolves a refusal by choosing.** Each one is
printed with its plan and service named, for the Product Owner.

THE LIVE PATH — WHAT THE REPORT SAYS A BILL DOES, AND HOW IT KNOWS
------------------------------------------------------------------
⚠ **THIS SECTION READ, UNTIL 2026-10-02, THAT `_base_charge_for` "STILL
IMPLEMENTS THE SUPERSEDED LAW" AND THAT CLEARING THE PLAN COLUMN "STOPS" A BILL
(`DEF-RAT-9141`).** Both were true when written (DEF-438) and both stopped being
true on 2026-09-28, when `DEF-BIL-7170` took the plan figure out of billing
altogether. The report went on asserting the old world for four days: it called
`_base_charge_for` with the retired `(service, plan_base, schedule_base)`
arguments, the call raised `TypeError`, an `except Exception` swallowed it, and
**every row was reported as a bill that would REFUSE** — false, and printed in
red (`DEF-RAT-9139`).

**Now, per row, the report ASKS BILLING, by name, what the bill charges today**
for that plan's customer class: `gather._base_charge_code_for` (rating's own
narrowing through billing's seam, honouring the code the schedule names) and
then `gather._base_charge_for(service, code_base=...)`. A conflict rating
refuses is printed with rating's own sentence. **Nothing is caught broadly any
more:** a billing signature that changes again raises here, loudly, rather than
turning into a report.

**And the outcome column is `UNCHANGED` for every row**, because the probe
below establishes that billing takes no plan figure at all, so clearing one
cannot move a bill. That is a measurement, not a constant: should anybody ever
wire a plan figure back into billing, the probe answers `True`, every row reads
`UNKNOWN`, and `--apply` refuses.

The probe is `live_path_still_reads_the_plan_column`. It reads BEHAVIOUR, so it
lifted itself on 2026-09-28 with no follow-up commit. `--allow-refused-bills`
still overrides it, spelled out on purpose (hard-won law 3).

⚠ **THE DEF-477 PRECONDITION IS GONE FROM THE REPORT (`DEF-RAT-9141`).** It
warned that the next plan save wrote `0` back into a cleared column and that the
bill would then print `$0.00`. `DEF-477` was fixed on 2026-08-21 (`242e873`),
and since 2026-09-28 no bill reads the column in any case, so the report printed
a stale instruction — *"Fix DEF-477 before running --apply"* — on every run.

REVERSIBILITY
-------------
**There is no reverse command.** `plan_services.base_charge` is not versioned:
once cleared, the only surviving record of the figure is the `audit_log` row
this command writes, whose `before` payload carries the exact prior value per
plan-service — and `audit_log` is pruned on its retention schedule (`OQ-1340`,
PO 2026-09-23), so that is not a permanent record either. Only rows whose figure
EQUALS what the bill already charges are cleared, so nothing a bill depends on
is lost; a HELD row keeps its figure on the plan. Restoring a cleared figure
means typing it back on S9, or restoring the database from a backup taken
beforehand.

WHAT IT DOES NOT TOUCH
----------------------
`tariff_versions.base_charge` is left EXACTLY as it is. BR-RAT-088 retires it and
its own words are *"a schedule version that still carries a base is a migration
artefact and must be refused once the charge code owns it"* — REFUSED, by a
gate, not silently nulled by this command. Two further reasons: BR-RAT-017 keeps
tariff versions reproducible for SEVEN YEARS, and blanking the column on an
in-force version destroys the only record of what a past bill was priced from.
(Since 2026-09-28 billing reads it no more than it reads the plan column.) Every
non-NULL schedule base is REPORTED, so the gate that must eventually refuse it
has a count.

**Nothing here writes `charges` or `charge_code_amounts` (2026-10-02).** A code
a held row would need is printed with a suggested code string, a FLAT amount and
its class list — a plan base has no size dimension, so inventing per-size rows
from a scalar would be inventing prices — and a person creates it, or decides
not to, on the charge code.

THE SUGGESTED CODE STRING IS NOT LOAD-BEARING
---------------------------------------------
`BASE-WATER`, `BASE-WATER-RES` and so on are generated for readability and
uniqueness only. The engine matches on `is_base`, `service_id` and
`applies_to_customer_classes` — never on the string — because BR-RAT-088's own
docstring warns that name-matching `BASE-<service>` is a hard-coded vocabulary
that fails SILENTLY for a tenant who names theirs anything else. So a `reuse`
is found by those attributes and the figure, whatever the tenant named it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.rating import charge_prices, models, services
from apps.tenancy import models as tenancy_models
from core import audit as core_audit
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

#: `charges.code` is capped at 20 by `services._validate_charge`, the writer a
#: person uses to create a suggested code. Derived here rather than re-typed as
#: a literal would be better still; the validator does not export it, so the
#: cap is asserted equal by the test file instead of guessed at.
CODE_MAX_LENGTH = 20

#: Audit action code (BR-AUD-003 dotted `entity.action` shape). Clearing the
#: plan's base is this command's own money action and needs its own code.
ACTION_BASE_CLEARED = "plan_service.base_charge_migrated"


# ── the plan ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlanBase:
    """ONE `(plan, service)` row carrying a base charge — the migration's input."""

    plan_service_id: Any
    plan_id: Any
    plan_code: str
    plan_name: str
    plan_status: str
    service_id: Any
    service_code: str
    #: `account_types.code` for the ONE class this plan names, or None.
    #:
    #: ⚠ **`None` NOW MEANS TWO THINGS AND BOTH ARE REFUSAL 2 — `DEF-RAT-5768`
    #: (PO ruling 2026-09-19).** `rate_plans.account_type_id` became
    #: `account_type_ids`, a LIST, where `[]` means EVERY class. So this is
    #: None when the plan names NO class (as before) **and** when it names
    #: MORE THAN ONE — because this command writes ONE scoped charge code per
    #: plan-service and `charge_code_amounts` is unique on
    #: `(tenant, charge, size_class)`, so a base that reaches two classes
    #: cannot be expressed here without deciding something nobody ruled.
    #: **Refusing is the safe direction on a money path**: an operator reads
    #: the refusal and asks, where a guess would quietly scope a residential
    #: base to a commercial account. None is never a default.
    customer_class: str | None
    #: How many classes the plan names — carried so the refusal can say WHICH
    #: of the two cases it is rather than printing one sentence for both.
    customer_class_count: int
    amount: Decimal
    currency: str
    #: `tariff_versions.base_charge` in force for this plan's schedule for this
    #: service, or None. NOT migrated and NOT cleared — see the module docstring.
    schedule_base: Decimal | None
    schedule_wired: bool


@dataclass(frozen=True)
class CodePlan:
    """ONE `is_base` charge code the plan figures call for — reused if it exists,
    printed for a person if it does not. Never created here (2026-10-02)."""

    code: str
    name: str
    service_code: str
    service_id: Any
    customer_classes: tuple[str, ...]
    amount: Decimal
    action: str  # ACTION_NEW | ACTION_REUSE
    existing_id: Any | None
    sources: tuple[PlanBase, ...]


@dataclass(frozen=True)
class Refusal:
    """A case where executing BR-RAT-088 would need a judgement it does not make.

    `kind` is a stable token so a test can assert WHICH refusal fired; `detail`
    is the sentence a human reads, and it names the plan and the service every
    time — a refusal that says "two plans disagree" without saying which two is
    a refusal nobody can act on.
    """

    kind: str
    service_code: str
    detail: str


REFUSAL_CONFLICTING_AMOUNTS = "conflicting_amounts"
REFUSAL_NO_CUSTOMER_CLASS = "no_customer_class"
REFUSAL_UNKNOWN_CUSTOMER_CLASS = "unknown_customer_class"
REFUSAL_OVERLAPPING_BASE_CODES = "overlapping_base_codes"
REFUSAL_MIXED_CURRENCY = "mixed_currency"


#: What the LIVE bill run does to this plan-service's base when the plan column
#: is cleared.
#:
#: ⚠ **TWO OUTCOMES, NOT FOUR, FROM 2026-10-02 (`DEF-RAT-9139`).** `moves` and
#: `refuses` described a billing that read the plan column. It does not
#: (`DEF-BIL-7170`, PO 2026-09-28), so clearing the column cannot move or stop a
#: bill, and keeping two outcomes nothing can produce would be a report column
#: incapable of saying anything but zero (hard-won law 7). `unknown` is what
#: every row reads if the probe ever finds billing reading a plan figure again.
LIVE_UNCHANGED = "unchanged"
LIVE_UNKNOWN = "unknown"

#: `CodePlan.action` — `reuse`: a base code already charges exactly this figure
#: for exactly these classes. `new`: no such code exists, and THIS COMMAND DOES
#: NOT CREATE IT (decision log 2026-10-02) — it is printed for a person.
ACTION_REUSE = "reuse"
ACTION_NEW = "new"


@dataclass(frozen=True)
class LiveEffect:
    """ONE plan-service row, and what its bill's base is today, asked of billing.

    `bill_base` is the figure billing charges for this plan's class today —
    `$0.00` where no code is defined and bound (PO 2026-09-30) — or None where
    rating refuses the base outright, in which case `bill_refusal` carries
    rating's own sentence. `bill_code` names the code that prices it, if any.
    """

    base: PlanBase
    outcome: str
    bill_base: Decimal | None
    bill_code: str | None
    bill_refusal: str | None

    @property
    def refusal_free(self) -> bool:
        return self.bill_refusal is None

    @property
    def class_resolved(self) -> bool:
        """The plan names exactly ONE known customer class, so "what does the
        bill charge" has one answer. A plan for none, several, or an unknown
        class prices accounts the report cannot enumerate — refusal 2 — and its
        figure is compared with nothing, so it is always held."""
        return (
            self.base.customer_class is not None
            and self.base.customer_class in services.TAX_CUSTOMER_CLASSES
        )

    @property
    def held(self) -> bool:
        """The plan states a figure the bill does NOT charge today (or one the
        report cannot compare). Clearing it moves no bill, but it is the only
        place that figure is written, and the question it raises — should this
        utility start charging it? — is a person's. So it is listed and left,
        never cleared and never coded."""
        return (
            not self.class_resolved or self.bill_base is None or self.bill_base != self.base.amount
        )


@dataclass
class TenantPlan:
    """Everything the dry run prints for one tenant, computed and written down
    before a single row is touched."""

    tenant_id: Any
    subdomain: str
    bases: list[PlanBase] = field(default_factory=list)
    codes: list[CodePlan] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    live_effects: list[LiveEffect] = field(default_factory=list)
    accounts_affected: int | None = None
    units_affected: int = 0
    schedule_bases_remaining: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """A refusal stands. ⚠ **FROM 2026-10-02 IT NO LONGER STOPS `--apply`.**
        Every refusal is about a code a PERSON would have to create, and only a
        HELD row ever calls for one; a held row is never cleared. So a refusal
        stops nothing the command does — it is printed for that person — and
        the rows whose figure the bill already charges are still cleared."""
        return bool(self.refusals)

    @property
    def new_codes(self) -> list[CodePlan]:
        """Codes that do not exist. Printed for a person; never created here."""
        return [code for code in self.codes if code.action == ACTION_NEW]

    @property
    def reuses(self) -> list[CodePlan]:
        return [code for code in self.codes if code.action == ACTION_REUSE]

    @property
    def bills_that_change(self) -> int:
        """Bills whose base clearing the plan column would change. Zero by
        measurement while billing reads no plan figure; an `unknown` row counts
        here, because a question about money nobody could answer is not a no."""
        return sum(1 for effect in self.live_effects if effect.outcome != LIVE_UNCHANGED)

    @property
    def held(self) -> list[LiveEffect]:
        """Rows left on the plan for a person — the plan figure is not what the
        bill charges, and creating a code from it would RAISE that bill."""
        return [effect for effect in self.live_effects if effect.held]

    @property
    def to_clear(self) -> list[LiveEffect]:
        """Rows whose plan figure IS what the bill charges, where clearing it is
        measured to move nothing. An `unknown` row is never cleared."""
        return [
            effect
            for effect in self.live_effects
            if not effect.held and effect.outcome == LIVE_UNCHANGED
        ]

    @property
    def bases_newly_charged(self) -> list[LiveEffect]:
        """The held rows whose figure would be CHARGED where the bill charges
        less today — the `$0.00 → $8.00` case. The subset a person must see."""
        return [
            effect
            for effect in self.held
            if effect.bill_base is not None and effect.base.amount > effect.bill_base
        ]


# ── reads that cross a module boundary (each one asks by name) ──────────────


def _account_type_codes() -> dict[str, str]:
    """`account_types.id → code`, the PLATFORM table's own vocabulary.

    B2 §2: rating does not read another module's STORAGE, and this is the one
    place that rule needs a word. `account_types` is a PLATFORM table — no
    `tenant_id`, RLS-exempt, seeded identically for every tenant (r5 #12 [D5])
    — and `rate_plans.account_type_id` is a DEFERRED FK into it that rating's
    own validator already accepts and serves. Resolving that id to its code is
    reading the meaning of rating's own column, not reading customers' data, and
    it is done through `apps.customers.models` by name so a rename fails loudly
    here rather than producing an unscoped base charge.

    Returns `{}` when the model cannot be resolved at all, which every caller
    treats as "the class could not be determined" — refusal 2 — never as "no
    class needed".
    """
    try:
        customers_models = import_module("apps.customers.models")
    except ImportError:  # pragma: no cover - the app package always imports
        return {}
    account_type = getattr(customers_models, "AccountType", None)
    if account_type is None:  # pragma: no cover - renamed model
        return {}
    return {str(row.id): row.code for row in account_type.objects.all()}


def _accounts_on_units(unit_ids: list[str]) -> int | None:
    """How many ACCOUNTS ride these units, through customers' own read surface.

    `accounts_for_bill_run` is the selector the bill run itself uses, so this
    counts what would actually be billed rather than what a join guessed. None
    means customers could not answer — reported as unknown, never as zero,
    because "no accounts" and "the read does not exist" are different facts and
    only one of them makes a migration safe.
    """
    if not unit_ids:
        return 0
    try:
        customers_selectors = import_module("apps.customers.selectors")
    except ImportError:  # pragma: no cover
        return None
    fn = getattr(customers_selectors, "accounts_for_bill_run", None)
    if not callable(fn):  # pragma: no cover
        return None
    try:
        return int(fn(unit_ids).count())
    except Exception:  # pragma: no cover - a selector that cannot answer
        return None


def live_base_charge_reader() -> Any | None:
    """`apps.billing.gather._base_charge_for`, or None when it is gone.

    Asked for BY NAME rather than reimplemented. Billing owns the rule that
    decides which stored column a bill's base comes from (DEF-154, DEF-277), and
    a second copy of it in rating would be two rules that agree until the day
    one of them is fixed. When it cannot be reached, every live-path answer is
    reported as `unknown` and `--apply` refuses — an unanswerable question about
    money is not a yes.
    """
    try:
        gather = import_module("apps.billing.gather")
    except ImportError:  # pragma: no cover
        return None
    return getattr(gather, "_base_charge_for", None)


def live_path_still_reads_the_plan_column() -> bool | None:
    """Does the live bill run still take its base from `plan_services`?

    ⚠ **BEHAVIOUR, NOT A COMMENT.** It hands billing's own function a plan
    figure and no schedule figure and looks at what comes back: `Decimal("1")`
    means the plan column is still the source of every base on every invoice, so
    clearing it stops bills. Anything else — a refusal, a different figure, or
    the function having been removed — means the read has moved on, and the gate
    below lifts itself with no commit required.

    None = could not be determined (billing unreachable). Treated as True by the
    gate, because CLAUDE.md hard-won law 3 puts the unsafe option behind a
    typed flag, not behind an import error.
    """
    reader = live_base_charge_reader()
    if reader is None:
        return None
    try:
        answer = reader("water", Decimal("1"), None)
    except Exception:
        # ⚠ **THIS IS THE ARM THAT ANSWERS FROM 2026-09-28, AND IT ANSWERS
        # CORRECTLY (`DEF-BIL-7170`).** The PO retired the plan's base — *"we
        # will never take default value from plan $8.0 - that is retired"* —
        # so `_base_charge_for` no longer HAS the parameter this probe passes
        # and the call raises `TypeError`. That is precisely the case the
        # docstring above names: *the function having been removed — means the
        # read has moved on, and the gate below lifts itself*.
        #
        # ⚠ **IT IS LEFT AS A BEHAVIOUR PROBE RATHER THAN REWRITTEN TO RETURN
        # A CONSTANT.** The question this function asks is *does the live bill
        # run still take its base from `plan_services`* — and the honest way to
        # answer it will still be to ASK BILLING on the day somebody wires a
        # plan figure back in. A hard-coded `False` here would be a comment
        # claiming a guarantee (hard-won law 1) and would go on claiming it.
        return False
    return answer == Decimal("1")


# ── planning (pure: reads, computes, writes nothing) ────────────────────────


def _class_set(classes: Any) -> frozenset[str] | None:
    """BR-RAT-103: NULL or `[]` means EVERY CLASS. None here IS "every class",
    and it is deliberately not the empty set — an empty set intersects nothing,
    which would make the widest possible scope look like the narrowest."""
    if not classes:
        return None
    return frozenset(str(code).strip().lower() for code in classes)


def _overlaps(left: frozenset[str] | None, right: frozenset[str] | None) -> bool:
    """Two codes can both reach one account when either is unscoped, or when
    their class lists share a member. This is the predicate DEF-468 refuses on."""
    if left is None or right is None:
        return True
    return bool(left & right)


def _shorten(stem: str, suffix: str) -> str:
    """A code that fits `charges.code`'s 20-character validator, trimming the
    SERVICE segment rather than the class one — losing the class from the string
    would make two class-scoped codes look identical to a human reading a list.
    The string is cosmetic (see the module docstring), the collision is not."""
    room = CODE_MAX_LENGTH - len(suffix)
    return f"{stem[:room]}{suffix}"


def _unique_code(stem: str, suffix: str, taken: set[str]) -> str:
    candidate = _shorten(stem, suffix)
    if candidate not in taken:
        taken.add(candidate)
        return candidate
    ordinal = 2
    while True:
        tail = f"{suffix}-{ordinal}"
        candidate = _shorten(stem, tail)
        if candidate not in taken:
            taken.add(candidate)
            return candidate
        ordinal += 1


def _service_in_force_base(plan_id: Any, service_id: Any) -> tuple[Decimal | None, bool]:
    """The schedule base the live path would fall back to for this plan-service.

    Returns `(amount, wired)`. `wired` False means this plan attaches no schedule
    for the service at all, so there is nothing to fall back TO — reported, and
    it is the case where clearing the plan column refuses a bill outright.
    """
    link = (
        models.PlanRateSchedule.objects.filter(rate_plan_id=plan_id, service_id=service_id)
        .select_related("tariff")
        .first()
    )
    if link is None:
        return None, False
    version = (
        models.TariffVersion.objects.filter(tariff_id=link.tariff_id)
        .exclude(effective_from=None)
        .order_by("-effective_from")
        .first()
    )
    if version is None:
        return None, False
    return version.base_charge, True


def collect_bases(plan_statuses: tuple[str, ...] | None = None) -> list[PlanBase]:
    """Every `(plan, service)` row that states a base, inside the caller's
    tenant context. Ordered so the report and the apply agree on sequence."""
    type_codes = _account_type_codes()
    rows = (
        models.PlanService.objects.exclude(base_charge=None)
        .select_related("rate_plan", "service")
        .order_by("service__code", "rate_plan__code")
    )
    if plan_statuses:
        rows = rows.filter(rate_plan__status__in=plan_statuses)
    bases: list[PlanBase] = []
    for row in rows:
        plan = row.rate_plan
        # DEF-RAT-5768 — the plan names a LIST now. Exactly one class scopes a
        # code; none and many are both refusal 2 (see `customer_class` above).
        class_ids = list(getattr(plan, "account_type_ids", None) or [])
        customer_class = type_codes.get(str(class_ids[0])) if len(class_ids) == 1 else None
        schedule_base, wired = _service_in_force_base(plan.id, row.service_id)
        bases.append(
            PlanBase(
                plan_service_id=row.id,
                plan_id=plan.id,
                plan_code=plan.code,
                plan_name=plan.name,
                plan_status=plan.status,
                service_id=row.service_id,
                service_code=row.service.code,
                customer_class=customer_class,
                customer_class_count=len(class_ids),
                # Decimal straight off the column. NOT quantized: B4 is ❄️ FROZEN
                # and rounding a stored figure on the way past would be an
                # unsigned rounding rule standing in front of a signed one.
                amount=row.base_charge,
                currency=row.currency,
                schedule_base=schedule_base,
                schedule_wired=wired,
            )
        )
    return bases


def _existing_base_codes() -> list[models.Charge]:
    return list(
        models.Charge.objects.filter(is_base=True, deleted_at__isnull=True).select_related(
            "service"
        )
    )


def _named_base_code(plan_id: Any, service_id: Any) -> str | None:
    """The code the plan's in-force schedule NAMES as its base (`BR-RAT-1025`),
    or None where it names nothing — which is what billing passes too."""
    link = models.PlanRateSchedule.objects.filter(
        rate_plan_id=plan_id, service_id=service_id
    ).first()
    if link is None:
        return None
    version = (
        models.TariffVersion.objects.filter(tariff_id=link.tariff_id)
        .exclude(effective_from=None)
        .select_related("base_charge_code")
        .order_by("-effective_from")
        .first()
    )
    if version is None or version.base_charge_code_id is None:
        return None
    return version.base_charge_code.code


def _bill_base_today(base: PlanBase) -> tuple[Decimal | None, str | None, str | None]:
    """`(figure, code, refusal)` — what the bill charges for this plan-service's
    base TODAY, asked of billing's own two functions by name.

    `gather._base_charge_code_for` is the narrowing billing runs (rating's seam,
    the schedule's named code, the class); `gather._base_charge_for` turns its
    answer into the figure — `$0.00` where nothing is defined and bound (PO
    2026-09-30). A conflict rating refuses comes back as billing's
    `GatherProblem` and is reported with its own sentence.

    ⚠ **ONLY `GatherProblem` IS CAUGHT (`DEF-RAT-9139`).** The previous version
    caught `Exception`, so a changed billing signature became a `TypeError`
    which became *"every bill REFUSES"*. A billing that cannot be asked this
    question must fail this command, not populate its report. The connection
    size is not known per plan (a plan prices many), so a per-size code reads
    as rating's *"size is not recorded"* refusal — stated, never guessed.
    """
    gather = import_module("apps.billing.gather")
    try:
        amount, code = gather._base_charge_code_for(
            base.service_code,
            customer_class=base.customer_class,
            size_class=None,
            named_code=_named_base_code(base.plan_id, base.service_id),
        )
    except gather.GatherProblem as problem:
        return None, None, str(problem)
    return gather._base_charge_for(base.service_code, code_base=amount), code, None


def _live_effect(base: PlanBase, plan_column_read: bool | None) -> LiveEffect:
    """What clearing this row's plan column does to its bill.

    `plan_column_read` is the probe's answer, asked once per tenant. False —
    billing takes no plan figure — means UNCHANGED, as a measurement. Anything
    else is UNKNOWN, never a guess in either direction."""
    figure, code, refusal = _bill_base_today(base)
    outcome = LIVE_UNCHANGED if plan_column_read is False else LIVE_UNKNOWN
    return LiveEffect(base, outcome, figure, code, refusal)


def plan_tenant(tenant: Any, *, plan_statuses: tuple[str, ...] | None = None) -> TenantPlan:
    """THE WHOLE MIGRATION, COMPUTED AND NOT PERFORMED.

    Called by the dry run and by `--apply` alike, so the thing an operator reads
    and the thing that executes are the same computation and cannot disagree.
    """
    result = TenantPlan(tenant_id=tenant.id, subdomain=tenant.subdomain)
    result.bases = collect_bases(plan_statuses)
    reader = live_base_charge_reader()
    if reader is None:
        result.notes.append(
            "apps.billing.gather._base_charge_for could not be imported — the live-path "
            "column of this report is UNKNOWN rather than empty, and --apply refuses."
        )
    plan_column_read = live_path_still_reads_the_plan_column()

    # ── the live-path effect and the schedule bases left behind ────────────
    for base in result.bases:
        if reader is None:
            result.live_effects.append(LiveEffect(base, LIVE_UNKNOWN, None, None, None))
            continue
        result.live_effects.append(_live_effect(base, plan_column_read))
    result.schedule_bases_remaining = sum(
        1 for base in result.bases if base.schedule_base is not None
    )

    # ── how many customers this reaches ────────────────────────────────────
    plan_ids = {base.plan_id for base in result.bases}
    unit_ids = list(
        models.UnitPlanAssignment.objects.filter(
            rate_plan_id__in=plan_ids, assigned_to__isnull=True
        ).values_list("unit_id", flat=True)
    )
    result.units_affected = len(unit_ids)
    result.accounts_affected = _accounts_on_units([str(uid) for uid in unit_ids])

    # ── REFUSAL 2 · a plan with no class has nothing to scope a code to ────
    held_by_row = {effect.base.plan_service_id: effect.held for effect in result.live_effects}
    classed: list[PlanBase] = []
    for base in result.bases:
        if base.customer_class is None:
            result.refusals.append(
                Refusal(
                    REFUSAL_NO_CUSTOMER_CLASS,
                    base.service_code,
                    f"plan {base.plan_code!r} ({base.plan_name}) states a "
                    f"{base.service_code} base of {base.amount} and "
                    + (
                        "NO customer class (`rate_plans.account_type_ids` is empty, "
                        "which means EVERY class), so there is nothing to scope the "
                        "charge code to. An unscoped code means EVERY class "
                        "(BR-RAT-103), which would silently override a scoped code for "
                        "accounts of other classes. Name the plan's customer class "
                        "first — DEF-452 is open on exactly this, for exactly these "
                        "plans."
                        if base.customer_class_count == 0
                        else f"{base.customer_class_count} customer classes "
                        "(`rate_plans.account_type_ids`, DEF-RAT-5768). This command "
                        "writes ONE scoped charge code per plan-service and "
                        "`charge_code_amounts` is unique on (tenant, charge, "
                        "size_class), so a base reaching several classes cannot be "
                        "written here without choosing one — which nobody has ruled. "
                        "Split the plan, or price the base on the charge code directly."
                    ),
                )
            )
            continue
        if base.customer_class not in services.TAX_CUSTOMER_CLASSES:
            result.refusals.append(
                Refusal(
                    REFUSAL_UNKNOWN_CUSTOMER_CLASS,
                    base.service_code,
                    f"plan {base.plan_code!r} names customer class "
                    f"{base.customer_class!r}, which is not one of the platform "
                    f"account types {services.TAX_CUSTOMER_CLASSES}. BR-RAT-103: an "
                    "unknown class is REFUSED, never dropped — a silently-vanished "
                    "restriction leaves a base the utility believes is restricted "
                    "applying to everybody, on every bill.",
                )
            )
            continue
        # 2026-10-02 — a row the bill ALREADY charges needs no code: it is
        # cleared, and it takes no part in the codes or refusals 1 and 3, which
        # are about codes a person would create for the HELD rows.
        if not held_by_row[base.plan_service_id]:
            continue
        classed.append(base)

    # ── REFUSAL 1 · same class, same service, two different amounts ────────
    by_class: dict[tuple[str, str], list[PlanBase]] = {}
    for base in classed:
        by_class.setdefault((base.service_code, base.customer_class or ""), []).append(base)
    conflicted: set[tuple[str, str]] = set()
    for (service_code, customer_class), group in sorted(by_class.items()):
        amounts = {base.amount for base in group}
        if len(amounts) > 1:
            conflicted.add((service_code, customer_class))
            named = ", ".join(f"{base.plan_code}={base.amount}" for base in group)
            result.refusals.append(
                Refusal(
                    REFUSAL_CONFLICTING_AMOUNTS,
                    service_code,
                    f"{service_code} · {customer_class}: {len(amounts)} different base "
                    f"amounts are stated by plans of the SAME class — {named}. "
                    "BR-RAT-088 puts ONE amount on the charge code for a "
                    "(service, class) pair and no code can hold both, so this is a "
                    "question about what the utility charges, not a migration step. "
                    "Nothing is chosen here.",
                )
            )

    # ── group into codes: one per (service, amount), classes unioned ───────
    groups: dict[tuple[str, Decimal], list[PlanBase]] = {}
    for base in classed:
        if (base.service_code, base.customer_class or "") in conflicted:
            continue
        groups.setdefault((base.service_code, base.amount), []).append(base)

    existing = _existing_base_codes()
    # CR-156-BRC10 — a code's flat amount is its *All sizes* row now, read
    # through the one lookup (today's), never `charges.amount`.
    existing_flat = charge_prices.flat_amounts(existing)
    taken_codes = set(models.Charge.objects.values_list("code", flat=True))
    consumed: set[Any] = set()
    desired: list[CodePlan] = []
    for (service_code, amount), members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        classes = tuple(sorted({base.customer_class for base in members if base.customer_class}))
        currencies = {base.currency for base in members}
        if len(currencies) > 1:
            result.refusals.append(
                Refusal(
                    REFUSAL_MIXED_CURRENCY,
                    service_code,
                    f"{service_code} · {amount}: the plans folding into one charge code "
                    f"state {len(currencies)} different currencies ({sorted(currencies)}). "
                    "`charges` carries NO currency column, so the move would drop the "
                    "distinction silently and CLAUDE.md hard rule 2 requires money to "
                    "carry its currency. Refused rather than picking one.",
                )
            )
            continue
        service_id = members[0].service_id
        wanted = _class_set(classes)

        match = next(
            (
                charge
                for charge in existing
                if charge.id not in consumed
                and charge.service_id == service_id
                and _class_set(charge.applies_to_customer_classes) == wanted
                and existing_flat.get(charge.id) is not None
                and existing_flat.get(charge.id) == amount
            ),
            None,
        )
        if match is not None:
            consumed.add(match.id)
            desired.append(
                CodePlan(
                    code=match.code,
                    name=match.name,
                    service_code=service_code,
                    service_id=service_id,
                    customer_classes=classes,
                    amount=amount,
                    action=ACTION_REUSE,
                    existing_id=match.id,
                    sources=tuple(members),
                )
            )
            continue

        stem = "BASE-" + service_code.upper().replace("_", "-")
        # A suffix only where the service needs more than one code. One code for
        # a service reads as `BASE-WATER`, which is what a utility would type.
        needs_suffix = len([g for g in groups if g[0] == service_code]) > 1
        suffix = "-" + classes[0][:3].upper() if (needs_suffix and classes) else ""
        code = _unique_code(stem, suffix, taken_codes)
        label = ", ".join(classes) if classes else "every class"
        desired.append(
            CodePlan(
                code=code,
                name=f"{service_code.replace('_', ' ').title()} base service ({label})",
                service_code=service_code,
                service_id=service_id,
                customer_classes=classes,
                amount=amount,
                action=ACTION_NEW,
                existing_id=None,
                sources=tuple(members),
            )
        )

    # ── REFUSAL 3 · two is_base codes surviving the narrowing (DEF-468) ────
    for charge in existing:
        if charge.id in consumed:
            continue
        left = _class_set(charge.applies_to_customer_classes)
        clashes = [
            code
            for code in desired
            if code.service_id == charge.service_id
            and code.action == ACTION_NEW
            and _overlaps(left, _class_set(code.customer_classes))
        ]
        if clashes:
            names = ", ".join(sorted(code.code for code in clashes))
            scope = ", ".join(sorted(left)) if left else "EVERY class"
            result.refusals.append(
                Refusal(
                    REFUSAL_OVERLAPPING_BASE_CODES,
                    charge.service.code if charge.service_id else "",
                    f"charge code {charge.code!r} is already declared the base for "
                    f"{charge.service.code if charge.service_id else 'no service'} and "
                    f"applies to {scope}; the plan figures call for {names} over the same "
                    "accounts. `resolution.resolve_base_charge` REFUSES when two base "
                    "codes survive the narrowing (DEF-468, 2026-08-21) and names them "
                    "both, so creating them would refuse bills — not price them — for "
                    "every account of the overlapping class. A person decides which "
                    "figure that class pays; nothing is chosen here.",
                )
            )

    result.codes = desired
    # DEF-RAT-9141 — the DEF-477 "PRECONDITION" note that stood here is removed,
    # not reworded: DEF-477 was fixed in 242e873, and no bill reads the column.
    if any(code.action == ACTION_NEW for code in desired):
        result.notes.append(
            "`charges` has no currency column, so a code a person creates from a held "
            "figure carries none. Every source row here reads "
            f"{sorted({base.currency for base in result.bases})}."
        )
    if result.schedule_bases_remaining:
        result.notes.append(
            f"{result.schedule_bases_remaining} of these plan-services also have a "
            "`tariff_versions.base_charge`. It is NOT cleared: BR-RAT-088 says such a "
            "version is a migration artefact that must be REFUSED by a gate, and "
            "BR-RAT-017 keeps tariff versions reproducible for seven years."
        )
    return result


# ── applying ────────────────────────────────────────────────────────────────


@require_role(SYSTEM_ADMIN)
def apply_plan(actor: Any, plan: TenantPlan) -> dict[str, int]:
    """Perform the plan, in ONE transaction, inside the caller's tenant context.

    ⚠ **IT CLEARS AND IT CREATES NOTHING (2026-10-02, `DEF-RAT-9139`).** Only the
    rows whose plan figure equals what the bill charges today are cleared, each
    with its audit row. Held rows are left exactly as they are and NO charge
    code is written — see the module docstring. Returns `cleared` and `held`.

    ⚠ **`@require_role(SYSTEM_ADMIN)` IS HERE BECAUSE THE CHECK USED TO LIVE
    ONE CALL DOWN.** `services.create_charge` carried it, and this function
    reached it on every run that minted. With the mint gone, a run would have
    cleared money columns with no role check at all — so the guard moves up to
    the function that now does the writing, never weaker than before.

    Idempotent by CONSTRUCTION rather than by a flag: the second run finds only
    held rows (or none), so it clears nothing. There is no "already migrated"
    marker to keep in step with reality.
    """
    # A refusal no longer stops the run (see `TenantPlan.blocked`): every row a
    # refusal names is HELD, and only `to_clear` rows are written. TC-6 and
    # TC-10b are the cases that prove a refused row is left as it was.
    cleared = 0
    with transaction.atomic():
        for effect in plan.to_clear:
            base = effect.base
            row = models.PlanService.objects.get(pk=base.plan_service_id)
            before = str(row.base_charge)
            row.base_charge = None
            row.save(update_fields=["base_charge", "updated_at"])
            # CLAUDE.md hard rule 7 — every money action writes `audit_log`, and
            # this row's `before` is the ONLY surviving record of the figure once
            # the column is cleared. It is the reversal story (module docstring).
            core_audit.money_action(
                actor,
                ACTION_BASE_CLEARED,
                "plan_service",
                row.id,
                before={
                    "base_charge": before,
                    "currency": base.currency,
                    "rate_plan_code": base.plan_code,
                    "service": base.service_code,
                },
                after={
                    "base_charge": None,
                    # The code that charges this figure today, or None where the
                    # bill charges `$0.00` because none is defined and bound.
                    "charged_by_charge_code": effect.bill_code,
                    "bill_base": str(effect.bill_base),
                    # `br_ref` and not `rule`: it is a MACHINE field, so the S61
                    # presenter drops it instead of showing a clerk a rule id
                    # (DEF-2377, the DEF-322 `data-br-ref` precedent).
                    "br_ref": "BR-RAT-088",
                },
            )
            cleared += 1
    return {"cleared": cleared, "held": len(plan.held)}


# ── the command ─────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = (
        "BR-RAT-088 — clear each plan's retired per-service base figure where it "
        "equals what the bill already charges, and LIST for a person every figure "
        "it does not. Creates NO charge code (PO 2026-09-28: the plan's figure is "
        "retired). DEFAULT IS A DRY-RUN REPORT THAT WRITES NOTHING. --apply clears "
        "in one transaction per tenant and is idempotent. It REFUSES rather than "
        "guessing wherever two plans disagree, a plan states no customer class, "
        "or two base codes would survive the narrowing (DEF-468)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="PERFORM the clearing. Without it this command is a report and "
            "writes nothing — no cleared column, no audit row. It never writes a "
            "charge code either way.",
        )
        parser.add_argument(
            "--tenant",
            metavar="SUBDOMAIN",
            action="append",
            default=None,
            help="Restrict to the named tenant (repeatable). Default: every tenant.",
        )
        parser.add_argument(
            "--actor-email",
            default=None,
            help="The System Admin this runs AS — an ACTIVE member of the tenant "
            "holding that role. Required with --apply: every base cleared is a money "
            "action and hard rule 7 wants a who, not a blank.",
        )
        parser.add_argument(
            "--allow-refused-bills",
            action="store_true",
            help="Apply even though the probe finds the LIVE bill run reading the "
            "plan column (it has not since 2026-09-28). Every row then reads UNKNOWN "
            "and none is cleared, so the run writes nothing a bill could depend on. "
            "Spelled out because the unsafe option must be the one you type.",
        )
        parser.add_argument(
            "--published-only",
            action="store_true",
            help="Consider only plans with status 'published'. ⚠ A plan excluded this "
            "way is INVISIBLE to the report, not listed as skipped — so it keeps its "
            "base on the plan while its siblings move, which is the two-claimants state "
            "BR-RAT-088 exists to end. Use it to shrink a first run's blast radius, "
            "never as the final pass. Default (omitted) considers every plan.",
        )

    # ── pre-flight ─────────────────────────────────────────────────────────
    def _refuse_up_front(self, options: dict[str, Any]) -> Any:
        if options["apply"]:
            if connection.vendor != "postgresql":
                raise CommandError(
                    f"database vendor is {connection.vendor!r} — tenant context is a "
                    "Postgres GUC (core/tenancy.py set_config) and RLS FORCE is what "
                    "keeps this write inside one tenant. Nothing was read or written."
                )
            if getattr(core_audit, "_sink", None) is None:
                raise CommandError(
                    "no BE-03 audit sink registered (core/audit.py) — moving a base "
                    "charge is a money action and CLAUDE.md hard rule 7 says it may not "
                    "happen without its audit row. Refused before any tenant was touched."
                )
            if not options["actor_email"]:
                raise CommandError(
                    "--apply needs --actor-email: every cleared column is "
                    "a money action, and an audit row with no actor cannot answer who "
                    "did it (BR-AUD-003)."
                )
            still_live = live_path_still_reads_the_plan_column()
            if still_live is not False and not options["allow_refused_bills"]:
                raise CommandError(
                    "REFUSED: the live bill run still takes its base from "
                    "`plan_services.base_charge` (`apps.billing.gather._base_charge_for`, "
                    "probed just now"
                    + (
                        " — and could not be probed at all, which is treated the same way"
                        if still_live is None
                        else ""
                    )
                    + "). The PO retired that figure on 2026-09-28 and billing stopped "
                    "reading it (DEF-BIL-7170), so a billing that reads it again is a "
                    "regression to find, not a state to migrate under. Type "
                    "--allow-refused-bills to run anyway: every row then reads UNKNOWN "
                    "and none is cleared."
                )
        return options

    def _targets(self, subdomains: list[str] | None) -> list[Any]:
        """`tenants` is the PLATFORM registry and RLS-exempt (B2 §3), so this is
        the one query here that is not inside a tenant context."""
        qs = tenancy_models.Tenant.objects.all().order_by("subdomain")
        if subdomains:
            wanted = [s.strip().lower() for s in subdomains]
            qs = qs.filter(subdomain__in=wanted)
            found = set(qs.values_list("subdomain", flat=True))
            missing = [s for s in wanted if s not in found]
            if missing:
                known = sorted(tenancy_models.Tenant.objects.values_list("subdomain", flat=True))
                raise CommandError(
                    f"unknown --tenant: {', '.join(missing)} (present: "
                    f"{', '.join(known) or 'none'}). Nothing was read."
                )
        return list(qs)

    def _actor(self, tenant: Any, email: str) -> Any:
        """The real `users` row, carrying its role in THIS tenant — the shape
        `identity.auth` hands every service after sign-in.

        ⚠ **IT RETURNED THE BARE ROW UNTIL 2026-10-02 (`DEF-RAT-9140`).** A
        `users` row has no `.role` — the role lives on `TenantMembership` — so
        `@require_role` refused EVERY real user with AUTH-002. Nobody saw it,
        because the DEF-438 gate refused every `--apply` before an actor was
        resolved, and every test passed a `SimpleNamespace(role=...)`.

        **The role is attached exactly as `identity/auth.py` attaches it**
        (`user.role = membership.role.code`), from the membership read for THIS
        tenant inside its context, and the permission check itself is not
        touched — `apply_plan` still refuses anyone who is not a System Admin.
        It is STRICTER than sign-in in one place: a membership that is not
        ACTIVE (invited, deactivated) is refused here, because an operator
        action with a blast radius is not run as somebody who cannot sign in.
        """
        identity_selectors = import_module("apps.identity.selectors")
        user = identity_selectors.user_by_email(tenant.id, email)
        if user is None:
            raise CommandError(
                f"{tenant.subdomain}: no user {email!r} — the actor must be a real user "
                "row, because `audit_log` and friends hold FKs into `users` and a "
                "synthetic id is a foreign-key violation, not an actor."
            )
        membership = identity_selectors.membership_for_user(tenant.id, user.id)
        if membership is None or membership.status != membership.STATUS_ACTIVE:
            raise CommandError(
                f"{tenant.subdomain}: {email!r} is not an active member of this tenant "
                f"(membership: {getattr(membership, 'status', 'none')}). Nothing was written."
            )
        user.role = membership.role.code
        return user

    # ── report ─────────────────────────────────────────────────────────────
    @staticmethod
    def _money(value: Decimal | None) -> str:
        return "—" if value is None else f"{value:.2f}"

    def _print_tenant(self, plan: TenantPlan, *, applied: dict[str, int] | None) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"── {plan.subdomain} ──"))
        if not plan.bases:
            self.stdout.write(
                "  no plan states a base charge — nothing to migrate "
                "(this is also what a second --apply run sees: idempotent by construction)"
            )
            return

        self.stdout.write("  bases found on plans")
        for base in plan.bases:
            self.stdout.write(
                f"    {base.plan_code:<10} {base.plan_name[:26]:<26} "
                f"{base.service_code:<12} {(base.customer_class or '(NO CLASS)'):<12} "
                f"{self._money(base.amount)} {base.currency}"
            )

        self.stdout.write("")
        self.stdout.write(
            "  what each bill's base is today, and what clearing the plan column does to it"
        )
        for effect in plan.live_effects:
            base = effect.base
            today = (
                f"bill charges {self._money(effect.bill_base)}"
                + (f" ({effect.bill_code})" if effect.bill_code else " (no base code)")
                if effect.refusal_free
                else f"bill base refused today: {effect.bill_refusal}"
            )
            fate = "HELD for a person" if effect.held else "cleared"
            style = self.style.ERROR if effect.outcome != LIVE_UNCHANGED else str
            self.stdout.write(
                "    "
                + style(
                    f"{base.plan_code:<10} {base.service_code:<12} "
                    f"{effect.outcome.upper():<10} plan {self._money(base.amount)} · "
                    f"{today} · {fate}"
                )
            )

        self.stdout.write("")
        self.stdout.write(
            "  HELD FOR A PERSON · the plan figure is not what the bill charges. "
            "No charge code is created from a retired plan figure (PO 2026-09-28)."
        )
        if not plan.held:
            self.stdout.write("    (none — every plan figure is what its bill already charges)")
        # DEF-RAT-9841 — a held row whose figure an EXISTING code already charges
        # is not a code to create: under PO ruling 2026-10-06 the bill reads only
        # the code its rate schedule NAMES, so the cure is naming that code there
        # (Rate schedules › Choose a base code), and that is a person's choice.
        reused_by_row = {
            source.plan_service_id: code.code
            for code in plan.reuses
            for source in code.sources
        }
        for effect in plan.held:
            base = effect.base
            reused = reused_by_row.get(base.plan_service_id)
            cure = (
                f"if {reused} were named on its rate schedule"
                if reused
                else "if a code were created"
            )
            raise_to = (
                f"would RAISE the bill from {self._money(effect.bill_base)} "
                f"to {self._money(base.amount)} {cure}"
                if effect in plan.bases_newly_charged
                else "differs from the bill"
            )
            self.stdout.write(
                self.style.WARNING(
                    f"    {base.plan_code:<10} {base.service_code:<12} "
                    f"{(base.customer_class or '(NO CLASS)'):<12} "
                    f"plan {self._money(base.amount)} · {raise_to}"
                )
            )

        self.stdout.write("")
        self.stdout.write("  base charge codes these figures call for (NOT created here)")
        if not plan.codes:
            self.stdout.write("    (none — every source row is blocked by a refusal below)")
        for code in plan.codes:
            scope = ", ".join(code.customer_classes) or "EVERY class"
            plans = ", ".join(sorted({base.plan_code for base in code.sources}))
            self.stdout.write(
                f"    {code.action.upper():<5} {code.code:<20} {code.service_code:<12} "
                f"{scope:<26} {self._money(code.amount)}   from {plans}"
            )

        if plan.refusals:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR("  ── REFUSALS · the rows they name are HELD, not cleared ──")
            )
            for refusal in plan.refusals:
                self.stdout.write(f"    [{refusal.kind}] {refusal.detail}")

        for note in plan.notes:
            self.stdout.write(f"    note: {note}")

        self.stdout.write("")
        accounts = (
            "could not be determined"
            if plan.accounts_affected is None
            else str(plan.accounts_affected)
        )
        self.stdout.write(
            f"  totals: {len(plan.bases)} plan-service base(s) · {plan.units_affected} unit(s) "
            f"· {accounts} account(s) · bills that change {plan.bills_that_change} "
            f"· to clear {len(plan.to_clear)} · held for a person {len(plan.held)} "
            f"(would newly charge {len(plan.bases_newly_charged)}) · charge codes created 0"
        )
        if applied is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  APPLIED: {applied['cleared']} plan base(s) cleared, "
                    f"{applied['held']} held for a person, 0 charge codes created"
                )
            )

    # ── handle ─────────────────────────────────────────────────────────────
    def handle(self, *args: Any, **options: Any) -> None:
        self._refuse_up_front(options)
        tenants = self._targets(options["tenant"])
        statuses = ("published",) if options["published_only"] else None

        mode = "APPLY — this WRITES" if options["apply"] else "DRY RUN — nothing is written"
        self.stdout.write(self.style.WARNING(f"BR-RAT-088 · base → charge code · {mode}"))
        self.stdout.write(f"tenants targeted ... {len(tenants)}")
        if not tenants:
            self.stdout.write("nothing to do — no tenant matched")
            return

        blocked = 0
        for tenant in tenants:
            with core_tenancy.tenant_context(tenant.id):
                plan = plan_tenant(tenant, plan_statuses=statuses)
                applied = None
                if options["apply"] and plan.bases:
                    actor = self._actor(tenant, options["actor_email"])
                    applied = apply_plan(actor, plan)
                if plan.blocked:
                    blocked += 1
            self._print_tenant(plan, applied=applied)

        self.stdout.write("")
        if blocked:
            self.stdout.write(
                self.style.ERROR(
                    f"{blocked} tenant(s) carry refusals; the rows they name were HELD, not cleared. Every refusal names "
                    "its plan and its service; none of them is resolved here."
                )
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 §A3 + BR-RAT-088 (PO 2026-08-20) + BR-RAT-103 (PO 2026-08-21),
#         both verbatim in 04-docs/05-modules/06-rating/02-business-rules.md.
#         ⚠ NOT a `US-XXX-###@<hex>` packet, so THIS FILE FAILS G1 — deliberately
#         and visibly, in the same way its sibling `apps/rating/resolution.py`
#         does and 90 other files do: the ruling of 2026-08-20 moved the base and
#         named no migration, so no story owns this. Hard-won law 8's remedy is
#         to AUTHOR the story; that is a product decision and is reported to the
#         PO rather than taken here, and inventing a US-ID to satisfy the regex
#         would be the gate lying about traceability instead of reporting it.
# generated: 2026-08-21 by the BR-RAT-088 migration lane (claude)
# checklist: A✔ B✔ C✔ D=deferred(no-endpoint-half — a management command by design: an operator action with a blast radius, not a screen) E=deferred(no-frontend-half — same reason) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row added)
# gates: golden-verify 33 PASS / 0 FAIL✔ · pytest -m golden 23 passed / 1 xfailed, unchanged✔ · G5 isolation 44 passed✔ · G7 no longer names this file (the 10 it does name are other lanes' migrations, RED before this lane)✔ · G30 defect register sound✔ · makemigrations --check --dry-run clean (no migration, no model field)✔ · pytest tests/test_br_rat_088_base_migration.py 21 passed✔ (RED proved first, four ways — see the ledger row) · G1 FAILS by design, see packet: above
# amended: 2026-10-02 (DEF-RAT-9139/9140/9141, build 2.453.1) — creates NO charge code; clears only a plan figure the bill already charges and HOLDS the rest for a person; apply_plan carries @require_role(SYSTEM_ADMIN); _actor attaches the membership role · pytest tests/test_br_rat_088_base_migration.py 21 passed / 1 failed (tc10 = DEF-RAT-7141, pre-existing) on SQLite and PostgreSQL 16 · golden-verify 33 PASS / 0 FAIL and tests/golden 25 passed / 1 xfailed, unchanged · 🔒 HUMAN-REVIEW-PENDING, ledger row 2026-10-02
# exceptions: `_account_type_codes` reads the PLATFORM `account_types` table
#         through `apps.customers.models` by name — it is RLS-exempt, carries no
#         tenant_id, and the id being resolved is rating's OWN column
#         (`rate_plans.account_type_id`), so this resolves the meaning of a
#         rating column rather than reading customers' tenant data · the live
#         path is read through `apps.billing.gather._base_charge_for` by name
#         rather than mirrored, because a second copy of billing's
#         which-column-wins rule is two rules that agree until one is fixed ·
#         `plan_services.base_charge` is cleared by a DIRECT model write: no
#         service function clears one column without a whole plan payload, and
#         rating owns this table (the BR-TEN-057 precedent for an owning-module
#         direct update) — the audit row is written explicitly beside it ·
#         `tariff_versions.base_charge` is REPORTED and NOT cleared, per
#         BR-RAT-088's own "must be refused" wording and BR-RAT-017's seven-year
#         reproducibility · NO OQ is minted: the one question this surfaced —
#         that no seeded plan carries a customer class — is already filed as
#         DEF-452 (OPEN) and is cited rather than re-raised
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
