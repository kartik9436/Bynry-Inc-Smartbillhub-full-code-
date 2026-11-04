# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (chart of accounts — the reads that make a seeded,
#           tenant-customizable chart usable by a posting entry) ·
#           US-LED-017 (the cost-of-service GL picker — TC-5: no surface
#           presents an UNSIGNED 51xx/52xx/53xx code as finance-signed)
#           Screens: S56 · S73
# Rules:    BR-BIL-010 (every invoice line carries a GL account resolved from
#           the mapping — service→revenue with an OPTIONAL usage/base split;
#           AR / deposit-liability / clearing / write-off designations) ·
#           BR-LED-001 (a journal line carries its dimension set) ·
#           BR-LED-037 (the cost section is PROPOSED and unsigned until a
#           finance re-sign via HUMAN-GUIDE §6) · BR-LED-038 (seeded per service
#           sold; a tenant's own pointer survives a re-seed) ·
#           CLAUDE.md rule 1 (tenant scoping — RLS on Postgres, explicit
#           tenant filters here so the same law holds on the sqlite test DB)
# Tests:    06-backend/tests/test_us_led_005_gl_designations.py ·
#           06-backend/tests/test_us_led_017_cost_chart.py
# Impacts:  apps/billing (BR-BIL-010's stamp at issue reaches these by name) ·
#           apps/payments (per-service cash collections, PO 2026-08-11) ·
#           apps/ledger/posting.py (BUILT 2026-08-11 — its callers resolve "the
#           AR account" and "the opening clearing account" through these reads
#           instead of hardcoding 1200 and 3000; the trace line used to say
#           "stage 7, not built")
# ───────────────────────────────────────────────────────
"""ledger read path — **the account a journal entry is looking for**.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides which GL account a
money line lands in. AI-authored 2026-08-11 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md.

────────────────────────────────────────────────────────────────────────────
THE WHOLE POINT: RESOLVE BY DESIGNATION, NEVER BY NUMBER
────────────────────────────────────────────────────────────────────────────
OQ-106 existed because the posting service could not find "the AR account"
without writing `1200` into Python, and US-LED-005 makes the chart
tenant-customizable — a utility may renumber AR to 1150 or rename it entirely.
The PO's closure (2026-08-11) made a designation an ATTRIBUTE on a ledger
account; this module is the read that turns the attribute back into an account.

**No function here takes an account CODE, and no caller should ever hold one.**
`apps/ledger/services.ensure_service_revenue_accounts` touches a code exactly
once, at the instant a service is switched on, and says why in its own
docstring. Everything after that moment resolves a name.

────────────────────────────────────────────────────────────────────────────
WHAT `None` MEANS, AND WHAT A CALLER MUST DO WITH IT
────────────────────────────────────────────────────────────────────────────
Every read here answers `None` for "this tenant has no live account for that",
and that is a REFUSAL the caller must honour, never a value to substitute for.
The reason is specific rather than stylistic: `invoice_lines.gl_account_id` is
frozen by a database trigger the moment its bill leaves draft, so a line issued
with the wrong account — or with none — can never be repaired, only credited
and re-billed. BR-BIL-010's own test case says it: *"issue fails atomically if
any line cannot resolve a GL; nothing partial issues."*

`None` is returned rather than raised because the natural caller resolves MANY
accounts for one document and wants to report every gap at once, not the first.

────────────────────────────────────────────────────────────────────────────
TWO ATTRIBUTE HOMES, ONE DERIVATION
────────────────────────────────────────────────────────────────────────────
PO, closing OQ-106: *"using attributes on accounts and Utility services - we
can derive how it sum up at Ledger."*

  * **`ledger_accounts.designation`** — this module's own table. Eleven values
    (`apps/ledger/chart.GL_DESIGNATIONS`), at most one live account each.
  * **`tenant_services.revenue_account` / `.base_revenue_account`** — tenancy's
    table, reached through `apps/ledger/tenancy_seam.py`, never through
    tenancy's ORM (B1 / BR-TEN-013). **The tenant may re-point it** (PO
    2026-08-11, OQ-115: *"allow tenant user to override it"*), so what the seed
    put there is where the answer STARTED, never where it must still be. That
    is why every read below resolves the stored pointer and none of them
    consults `chart.SERVICE_REVENUE_ACCOUNTS`.

The derivation the ledger performs over the two is the usage/base fallback and
the liveness check, and both live below rather than in any caller — there is
exactly one implementation of "which account does this service's base charge
land in", which is what stops billing and payments drifting apart on it.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY NOT ANSWERED HERE
────────────────────────────────────────────────────────────────────────────
Named because a caller must not read silence as "not applicable" (hard-won
law 1 — this docstring claims an ABSENCE, and the absence is real):

  * **A FEE line's account.** BR-BIL-010: *"charge codes carry their own GL"* —
    and they carry it on `rating.charges.gl_account_id`, which is rating's
    column on rating's table. The ledger neither owns it nor mirrors it; a
    caller holding a `charge_id` asks rating.
  * **A TAX line's liability account** — still not answered here, but for a
    DIFFERENT reason since 2026-08-11, and the change is worth reading. This
    paragraph used to say the read was unbuildable: `tax_authority_gl_map`
    (r10 #2) keyed on the AUTHORITY, `invoice_lines` carried no authority
    column, so no read could place 2200-01 against 2200-03 and every taxed bill
    refused at issue. **That was OQ-116 and the PO closed it** (BR-BIL-069),
    verbatim: *"For each atheority have separate account and tagging; but also
    ensure you allow Use to manage it since every utility may not have every
    account."* `invoice_lines.tax_id` now exists and the mapping is reachable —
    and it is reachable in RATING, not here. The PO's declined option B was a
    ledger-side table keyed on the authority, precisely because
    `rating.taxes.liability_gl_account_id` already holds that fact and two homes
    for one mapping drift within a release. So a caller holding a `tax_id` asks
    rating (`liability_gl_account_id_for_tax`), exactly as a caller holding a
    `charge_id` does — and then asks `account_is_live` below, because whether an
    account is live is a question about THIS module's table.

    The 2200-series accounts themselves are minted here, on request:
    `apps.ledger.services.create_tax_authority_account`. They are seeded to
    nobody — B5 line 74 (❄️) says *"tenant authorities mint their own"*.
  * **A composite "one call per invoice line" adapter.** `apps/billing/issue.py`
    proposes `gl_account_ids_for_lines(rows)` keyed on billing's own line
    KINDS. Its own docstring calls that signature *"PROPOSED, not settled"*, and
    a line kind is billing's vocabulary, not the ledger's — the ledger would
    have to import billing's `usage`/`base`/`fee`/`tax`/`minimum_adjustment`
    taxonomy to honour it, and answer `None` for two of the five for reasons
    that belong to other modules. What this module publishes is what it can
    honestly answer; the per-kind mapping is a thin adapter over these reads
    and belongs on the side that owns the kinds. See the lane report.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import TruncMonth

from apps.ledger import chart, models, tenancy_seam
from core import errors
from core import tenancy as core_tenancy


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is read without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _live_accounts() -> Any:
    """Live chart rows for the current tenant.

    `deleted_at__isnull=True` is not a nicety: IS-1 deactivates rather than
    deletes, and an account a tenant has deactivated is one they have said
    stop using. Posting to it would be posting to a row the trial balance
    already treats as retired.
    """
    return models.LedgerAccount.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)


# ── designation → account (the thirteen; PO 2026-08-11 · 08-15 · 08-28) ─────
def tax_payable_q(prefix: str = "") -> Q:
    """The query form of `chart.is_tax_payable_account` — `CR-196-BRC10` 5b.

    A tax liability is an account whose CODE is in the 2200 series (as it has
    always been) OR whose minted slot `seed_key` is, so a System Admin who
    renames `2200-01` to the utility's own number does not take it off the tax
    report or out of the month-end remittance check. `prefix` lets a query
    over journal lines say `ledger_account__`.
    """
    series = chart.TAX_PAYABLE_SERIES
    return Q(**{f"{prefix}code__startswith": series}) | Q(
        **{f"{prefix}seed_key__startswith": series}
    )


def gl_account_for_designation(designation: str) -> models.LedgerAccount | None:
    """The tenant's live account carrying `designation`, or None.

    `designation` is one of `apps/ledger/chart.GL_DESIGNATIONS`. An unknown
    string is refused rather than answered `None`: "no account is designated
    accounts receivable" and "you asked for `accounts_recievable`" are
    different problems, and returning None for the typo would hide it behind
    the caller's own not-configured branch — the caller would report a mapping
    gap to a clerk who has nothing to fix.

    At most one row can come back: `uq_ledger_accounts_designation` is a
    partial unique index over live rows, which is the database half of the PO's
    reason for choosing a field over a table (*"unambiguous at posting time"*).
    """
    if designation not in chart.GL_DESIGNATIONS:
        raise ValueError(
            f"{designation!r} is not one of the GL designations the Product Owner has ruled — "
            f"{', '.join(chart.GL_DESIGNATIONS)}. A posting with no home is an OQ row and "
            "never a new designation invented here; the route in is a PO ruling, a constant "
            "in apps/ledger/chart.py and a migration that moves the CHECK."
        )
    return _live_accounts().filter(designation=designation).first()


def gl_account_id_for_designation(designation: str) -> str | None:
    """`gl_account_for_designation` as the uuid string other modules store.

    The cross-module shape: `invoice_lines.gl_account_id` and
    `journal_lines.ledger_account_id` want an id, and handing a neighbour an
    ORM instance would hand them this module's internals.
    """
    account = gl_account_for_designation(designation)
    return str(account.id) if account is not None else None


# ── CR-066: where a charge code, a reason and a discount START ─────────────
#
# ⚠ **THESE ARE THE ONLY READS IN THIS MODULE BESIDES
# `ensure_service_revenue_accounts` THAT RESOLVE AN ACCOUNT BY CODE, AND THE
# CONFINEMENT IS THE SAME.** The module's own law is *code reads the
# DESIGNATION, never the NUMBER*, because a tenant may renumber 1200 to 1150.
# These three run at ONE instant — the moment a seeded row is given the account
# it STARTS at — and never again: after that the live answer is the tenant's own
# column, and `default_gl_account_id_for_charge_code` is not consulted for that
# tenant a second time. That is exactly the licence `SERVICE_REVENUE_ACCOUNTS`
# operates under one file over, stated in its own words: *"the seed says where a
# service starts; a tenant may re-point it"*.
def gl_account_id_for_code(code: str) -> str | None:
    """The tenant's live account with this CHART CODE, as an id string, or None.

    `None` when the tenant has no such row, which is a real and lawful state:
    the nine accounts CR-066 adds reach a tenant on the day it is PROVISIONED
    and, until the sweep runs, never afterwards (hard-won law 4), so a tenant
    created before 2026-09-02 holds none of them until its chart is topped up.
    ⚠ **THAT TOP-UP EXISTS AND THIS LINE USED TO IMPLY IT DID NOT**
    (`DEF-LED-6223`): `tenancy.services.seed_reference_data_for_tenant` calls
    `ledger.services.seed_chart_of_accounts` unconditionally, and
    `tenancy.reference_sweep.sweep()` runs that over `Tenant.objects.all()`
    from `06-backend/docker-entrypoint.sh` after every `migrate` (OQ-087).
    Until that runs, the caller leaves the mapping NULL and the Accounting
    screen reports the gap, which is what it already does today.
    """
    cleaned = str(code or "").strip()
    if not cleaned:
        return None
    account = _live_accounts().filter(code=cleaned).first()
    return str(account.id) if account is not None else None


def default_gl_account_id_for_charge_code(
    code: str, *, service: str | None = None, is_base: bool = False
) -> str | None:
    """Where this charge code's fee line STARTS posting — CR-066 table 1.

    ⚠ **A BASE CODE IS A RULE AND NOT A LIST, AND THAT IS THE WHOLE POINT OF
    THE TASK.** *A base charge code posts to its own service's revenue
    account.* The tenant in the screenshot that raised `DEF-2386` sells water,
    sewer, trash and fire and therefore holds five base codes; a tenant selling
    electric, gas or thermal receives `BASE-E`, `BASE-G`, `BASE-TH`, and a
    capacity tenant `BASE-SOL`, `BASE-BAT`, `BASE-BB`, `BASE-SW`. Hard-listing
    the five would leave every one of the others unmapped and hand the next
    utility the identical wall — a bill that refuses at issue because a base fee
    line has nowhere to post.

    It resolves through `revenue_account_id_for_service`, which is the single
    implementation of BR-BIL-010's optional-split fallback (a sewer base lands
    in sewer revenue because sewer has no separate base account) and which reads
    the TENANT's pointer rather than the chart's default — so a utility that has
    re-pointed water revenue gets its base code pointed there too.

    Everything else comes from `chart.CHARGE_CODE_ACCOUNTS`, the PO's approved
    table. A code that is in neither answers `None`: a tenant's OWN charge code
    is theirs to map, and guessing an account for it would post their money
    somewhere nobody chose.
    """
    if is_base and service:
        return revenue_account_id_for_service(str(service), base=True)
    account_code = chart.CHARGE_CODE_ACCOUNTS.get(str(code or "").strip().upper())
    if account_code is None:
        return None
    return gl_account_id_for_code(account_code)


def default_gl_account_id_for_reason_code(code: str) -> str | None:
    """Where this adjustment reason STARTS pointing — CR-066 table 2.

    ⚠ **NOTHING POSTS THROUGH THIS COLUMN TODAY** and the PO was told so in the
    message that carried the table. A credit reverses whatever account the
    original bill credited; `reason_codes.default_gl_account_id` has no reader
    in the backend. The mapping is correct to have and it is NOT what unblocks a
    bill — no caller of this function may claim otherwise.
    """
    account_code = chart.REASON_CODE_ACCOUNTS.get(str(code or "").strip().upper())
    if account_code is None:
        return None
    return gl_account_id_for_code(account_code)


def default_gl_account_id_for_discount() -> str | None:
    """Where a discount STARTS posting — CR-066 table 3, `4760`.

    The account CR-061 already ruled into existence, typed `contra_revenue`
    because of that ruling's own words: *"no, you cannot file discount under
    revenue"*. Discount LINES already resolve here by DESIGNATION at issue, so
    this changes no posting; it gives the tenant a column to override and a row
    on the Accounting screen to override it on.
    """
    return gl_account_id_for_code(chart.DISCOUNT_DEFAULT_ACCOUNT)


def account_labels(account_ids: Any) -> dict[str, dict[str, str]]:
    """`{id: {"code": "4110", "name": "Water usage revenue"}}` for a set of ids.

    ⚠ **PUBLISHED FOR DEF-937 (CR-043 finding 3, PO 2026-08-27).** The bill's
    Charges tab printed `01a01d99-d995-7127-aad8-faace1cba6e2` in a column
    headed ACCOUNTING CODE, under a footnote promising a clerk *"the accounting
    code … recorded when the bill was issued"*. A uuid makes that promise
    uncheckable against any chart of accounts, and DEF-206 is the standing rule:
    never print the raw key at a person. `apps/billing/selectors.invoice_line_row`
    served `gl_account_code: None` with the comment *"`ledger_accounts` is W5"* —
    true when written, false since W5 landed (hard-won law 1).

    **RESOLVED LIVE, AND THAT IS THE POINT.** `invoice_lines.gl_account_id` is
    the STAMP (BR-BIL-010) and stays the authority — this reads the chart TODAY
    to find out what that stamped account is CALLED. A renamed or renumbered
    account therefore shows its new label beside a bill issued under the old
    one, which is correct: the clerk is looking the account up in the chart in
    front of them. Nothing here re-resolves which account the line posted to.

    **DEACTIVATED ROWS ARE INCLUDED, unlike `_live_accounts`.** An account a
    tenant retired last month still has bills posted to it, and dropping the
    label would put the uuid back on exactly the bills that most need reading.
    Liveness gates POSTING (see `_live_accounts`); it does not gate reading a
    name.

    An id this tenant does not own is simply absent from the result — never an
    exception, and never another tenant's label (hard rule 1: the queryset is
    tenant-scoped, so RLS and this filter agree).
    """
    wanted = {str(one) for one in (account_ids or ()) if one}
    if not wanted:
        return {}
    rows = models.LedgerAccount.objects.filter(tenant_id=_tenant_id(), id__in=wanted).values_list(
        "id", "code", "name"
    )
    return {str(pk): {"code": code, "name": name} for pk, code, name in rows}


def account_is_live(account_id: Any) -> bool:
    """Is `account_id` one of THIS tenant's live accounts?

    The ownership-and-liveness probe behind a tenant's GL override. Re-exported
    by `apps/ledger/services.py` because a neighbouring module reaches this
    module through its service layer (B1), and implemented once, here, so the
    override path and the roll-up reads agree on what "usable account" means.

    False — never an exception — for an id that belongs to another tenant, for
    a deactivated account and for anything that is not an id at all. A caller
    turns that into a field error naming the account; distinguishing "not
    yours" from "not real" would answer a question the asker has no right to.
    """
    if account_id in (None, ""):
        return False
    try:
        return _live_accounts().filter(pk=account_id).exists()
    except (ValidationError, ValueError, TypeError):
        # A malformed uuid is a caller mistake, not a chart fact.
        return False


def account_display(account_id: Any) -> dict[str, str] | None:
    """This tenant's CODE and NAME for a live account — `{"code", "name"}`.

    The DISPLAY half of `account_is_live`, published because B14 rule 31 forbids
    a database id on screen and `charges.gl_account_id` is a uuid: a screen that
    wants to print `4010 · Water revenue` has no other lawful way to get it.
    PO ruling 2026-09-17, verbatim: *"dont show uuiD- shoe actual 3 of gL code
    4000 , 4010 something liek this and its name - you might have to pull it
    from GL code mapping we have it - if GL code is not map then dont show it"*.

    ⚠ **`None` FOR EVERY WAY OF NOT KNOWING, AND THAT IS THE RULING.** A null
    id, an id belonging to another tenant, a deactivated account and a malformed
    uuid all answer `None`, and the screen then renders NOTHING — no dash, no
    placeholder, no id. Distinguishing "not yours" from "not real" would answer
    a question the asker has no right to, which is `account_is_live`'s own
    reasoning one function up.

    It reads `_live_accounts`, so the two cannot disagree about what a usable
    account is: an account this says nothing about is one the other refuses.
    """
    if account_id in (None, ""):
        return None
    try:
        row = _live_accounts().filter(pk=account_id).values("code", "name").first()
    except (ValidationError, ValueError, TypeError):
        # A malformed uuid is a caller mistake, not a chart fact.
        return None
    return None if row is None else {"code": row["code"], "name": row["name"]}


def designation_map() -> dict[str, str | None]:
    """EVERY designation, resolved in one query — `{designation: account_id | None}`.

    For the GL-mapping settings surface (which renders every designation,
    including the unmapped ones, so a gap is visible rather than absent) and
    for a posting service resolving several designations for one entry without
    N round trips. The keys are `chart.GL_DESIGNATIONS` entire, in the PO's own
    order; a value of None is a real, reportable gap.

    ⚠ **THIS SAID "ALL ELEVEN" TWICE UNTIL 2026-09-23 AND THE TUPLE HELD
    SEVENTEEN** (`DEF-LED-6222`). It was never a behaviour bug — the function
    has always walked the tuple — which is exactly why nothing caught it for
    six weeks: no gate reads a count written in prose, and the DATA is asserted
    by `tests/test_us_led_005_gl_designations.py` while the SENTENCE is not.
    Count the tuple; do not read a number out of a docstring.
    """
    by_designation = {
        row.designation: str(row.id)
        for row in _live_accounts().filter(designation__isnull=False).only("id", "designation")
    }
    return {name: by_designation.get(name) for name in chart.GL_DESIGNATIONS}


# ── service → revenue account, usage or base (BR-BIL-010) ───────────────────
def class_revenue_account_id(
    service_code: str, *, base: bool = False, customer_class: str | None = None
) -> str | None:
    """The CLASS override for one service and part, or None (BR-LED-801).

    `CR-197-BRC10`. Live accounts only: an override pointing at a deactivated
    account is no answer, and the every-class account then applies — the same
    liveness rule the every-class read below has always had.
    """
    code = str(customer_class or "").strip()
    if not code or not service_code:
        return None
    account_id = (
        models.ServiceClassRevenueAccount.objects.filter(
            tenant_id=_tenant_id(),
            service_code=service_code,
            part="base" if base else "usage",
            customer_class=code,
        )
        .values_list("ledger_account_id", flat=True)
        .first()
    )
    if account_id is None:
        return None
    return str(account_id) if _live_accounts().filter(pk=account_id).exists() else None


def revenue_account_id_for_service(
    service_code: str, *, base: bool = False, customer_class: str | None = None
) -> str | None:
    """The revenue account a service's line lands in — `base=True` for a base
    charge, the default for usage.

    **THE FALLBACK IS THE RULE** (BR-BIL-010, CONFIRMED). `base_revenue_account`
    is OPTIONAL: the finance-signed chart splits Electric into 4100/4105 and
    Water into 4110/4115, while Sewer, Trash, Gas and Broadband carry ONE
    account each. So `base=True` on a service with no split resolves to the
    service's `revenue_account` — a Trash base charge lands in Trash revenue,
    which is the whole reason the split was made optional instead of a second
    required field. This is the single implementation of that fallback;
    a caller that re-implements it will one day disagree with this one.

    **IT READS THE TENANT'S POINTER, NOT THE CHART'S DEFAULT.** The seed says
    where a service starts; a tenant may re-point it (PO 2026-08-11, OQ-115),
    and this read answers wherever it points TODAY.

    `None` when the tenant has no row for the service — including a service the
    tenant does not sell, which since OQ-115 has no seeded revenue account at
    all — when the service has a row with nothing mapped, or when the configured
    account has since been deactivated. All three are gaps a human fixes on the
    GL mapping page; none of them is a reason to guess.
    """
    # ⚠ **CR-197-BRC10 (BR-LED-801): THE CLASS ROW IS ASKED FIRST.** PO
    # 2026-10-29: *"some time utility wants track the seperate as per cutomer
    # class also"*. A bill of a commercial account with a Solar · Usage ·
    # Commercial row lands on that row's account; every other bill falls
    # through to the lines below, which are unchanged. A base part with no
    # class row of its own does NOT borrow the usage class row: the class row is
    # per part, and the part's own fallback is the every-class split below.
    override = class_revenue_account_id(service_code, base=base, customer_class=customer_class)
    if override is not None:
        return override
    attributes = tenancy_seam.service_gl_attributes(service_code)
    if attributes is None:
        return None
    account_id = attributes.get("base_revenue_account_id") if base else None
    if account_id is None:
        account_id = attributes.get("revenue_account_id")
    if account_id is None:
        return None
    # Liveness is the LEDGER's to check even though the pointer is tenancy's:
    # the FK guarantees the row exists, not that the tenant still uses it.
    exists = _live_accounts().filter(pk=account_id).exists()
    return str(account_id) if exists else None


def revenue_account_for_service(service_code: str, *, base: bool = False) -> Any:
    """`revenue_account_id_for_service` as the ORM row, for in-module callers
    that need the code/name (the S56 mapping panel, an export). Other modules
    take the id form."""
    account_id = revenue_account_id_for_service(service_code, base=base)
    if account_id is None:
        return None
    return _live_accounts().filter(pk=account_id).first()


# ── the COST section (US-LED-017 · BR-LED-037/038) ──────────────────────────
# ⚠ EVERY READ BELOW CARRIES THE `unsigned` MARKER WITH THE ACCOUNT, AND THAT
# IS THE POINT OF THEM.
#
# ⚠ **NOTHING IS MARKED TODAY (amended 2026-08-18).** The Product Owner finance
# re-signed all eight cost codes and names on 2026-08-18, so
# `chart.PENDING_FINANCE_RE_SIGN_COST` is `()` and every read below answers
# `unsigned: False`. The mechanism is untouched and is kept under test on a
# SYNTHETIC unsigned code (`test_us_led_017_cost_chart.py` TC-5), because a
# marker with no subject left would rot into a constant unnoticed.
# US-LED-017 TC-5: *"Any surface (capture form, export,
# report) presents a 51xx/52xx/53xx code as finance-signed while the B5 addendum
# is unsigned → Refused / flagged."* A picker that returned a bare account would
# make the marker somebody else's job to remember, which is hard-won law 1 in
# its usual disguise. So the marker travels IN the answer.
#
# ⚠ **THE MARKER HAS NO COLUMN, AND THAT IS A REPORTED GAP (field map D-10).**
# `ledger_accounts` carries nothing that says *"seeded pending a finance
# signature"*. So these reads derive it from `chart.PENDING_FINANCE_RE_SIGN_COST`
# — the code's own list — which is honest for the SEEDED codes and answers
# nothing about a tenant's own `5115 Raw water purchases` (correctly: nobody
# proposed that one on finance's behalf, so it is not marked). A column is the
# schema lane's call and is NAMED here rather than invented, exactly as D-10
# says. BR-BIL-067's 4160/4170 rows had the same gap before finance re-signed
# them on 2026-08-11; these eight had it from 2026-08-15 until their own
# re-sign on 2026-08-18. **The column is still missing**, and it is still the
# schema lane's call — a re-sign does not close a reported gap, it only empties
# the list the gap was noticed on.
def cost_account_row(account: Any) -> dict[str, Any]:
    """One GL-picker row: the account, plus whether finance has signed it.

    `unsigned=True` means *"this code was proposed and B5 line 74 has not been
    re-signed for it"*. Any surface offering the row must render it.

    ⚠ AMENDED 2026-08-18: it is False for every seeded code now — the PO
    finance re-signed the eight BR-LED-037 rows that day (codes and names, no
    figure attached), so the marker is dormant rather than gone. Leaving a
    ratified account marked would tell a finance reviewer that signed rows still
    need their attention, which is US-LED-017 TC-5's failure in reverse.
    """
    return {
        "account_id": str(account.pk),
        "code": account.code,
        "name": account.name,
        "type": account.type,
        "unsigned": account.code in chart.PENDING_FINANCE_RE_SIGN_COST,
        "unsigned_reason": (
            chart.COST_SECTION_RE_SIGN_SOURCE
            if account.code in chart.PENDING_FINANCE_RE_SIGN_COST
            else None
        ),
    }


def cost_accounts() -> tuple[dict[str, Any], ...]:
    """S73's GL picker — every LIVE expense account of this tenant, marked.

    **Every expense account, not only the eight proposed ones.** BR-LED-038
    makes the seeded pointer a default a tenant may override (BR-BIL-067
    verbatim: *"you create an account, but allow tenant user to override it"*),
    so a tenant that runs `5115 Raw water purchases` must be able to pick it.
    It comes back with `unsigned=False`, because it is theirs.

    6800 Bank fees and 6900 Bad debt are in the list too. They are expense
    accounts and nothing rules them out of a capture; that is the tenant's call,
    not this selector's.
    """
    rows = _live_accounts().filter(type="expense").order_by("code")
    return tuple(cost_account_row(row) for row in rows)


def cost_account_for_service(service_code: str) -> Any:
    """The tenant's live account for this service's purchases — or None.

    Resolves by CODE against `chart.SERVICE_COST_ACCOUNTS`, which is the seeded
    DEFAULT and nothing more. **None has three legitimate meanings and the
    caller must not collapse them:** the proposal names no cost mirror for this
    service (solar, battery, storm_water, thermal_heat — see
    `chart.SERVICE_COST_ACCOUNTS`); the tenant never sold the service so it was
    never seeded; or the tenant DEACTIVATED the account (IS-1, and rule 1 of the
    seed says the code stays theirs, so nothing resurrects it). In all three the
    capture asks the clerk for an account instead of choosing one.

    ⚠ **THIS IS THE ONE READ IN THIS FILE THAT RESOLVES BY CODE, AND IT IS THE
    EXCEPTION THE MODULE DOCSTRING WARNS ABOUT** — *"code reads the DESIGNATION,
    never the NUMBER"*. It is lawful here only because a cost account carries no
    designation and there is nothing else to resolve by: the eight codes are
    unsigned, so minting a designation for them would claim a place in a signed
    enumeration for an account finance has not approved. **When the B5 addendum
    is signed, a service→cost-account attribute (the BR-BIL-067 shape the field
    map names) is what should replace this lookup**, and then a tenant
    renumbering 5110 to 5115 keeps working. Today, a tenant who renumbers loses
    the default and picks the account by hand — REPORTED, not hidden.
    """
    code = chart.cost_account_code_for_service(service_code)
    if code is None:
        return None
    return _live_accounts().filter(code=code, type="expense").first()


def cost_account_for_category(category: str) -> Any:
    """The tenant's live 5200 / 5300 account, or None.

    The twin of `cost_account_for_service` for the two categories that belong to
    no service — `chart.COST_CATEGORY_OM` and
    `chart.COST_CATEGORY_INFRASTRUCTURE`, the PO's own *"O&M cost, infra cost"*
    from OQ-188. Same code-resolution caveat, same reason.
    """
    code = chart.COST_CATEGORY_ACCOUNTS.get(category)
    if code is None:
        return None
    return _live_accounts().filter(code=code, type="expense").first()


# ── what a set of entries DEBITED (CR-008 B-10, PO 2026-08-17 "10 - A") ─────
def entry_debit_totals(entry_ids: Any) -> dict[str, Any]:
    """Σ of POSTED debit lines per account, for THIS tenant's given entries.

    `{ledger_account_id: total}` — PUBLISHED FOR PAYMENTS' bank-rec lane, which
    must credit at reconciliation EXACTLY what each member payment's receipt
    entry debited (the tender's clearing account since CR-008 B-10, or 1010
    Undeposited funds). Reading the ENTRIES rather than today's tender mapping
    is the load-bearing choice: a tender re-pointed between receipt and
    reconciliation must still credit the account the money actually sits in,
    or the trial balance goes out by that payment forever.

    Tenant-scoped like every read in this module (CLAUDE.md rule 1): another
    tenant's entry ids contribute NOTHING, and an id that is no entry of this
    tenant is simply absent from the answer — the caller treats absence as the
    pre-seam legacy residual, which is a real state and not an error.

    Keys are STRING uuids (the cross-module shape, as
    `gl_account_id_for_designation` answers) and values are `Decimal`
    (CLAUDE.md rule 2 — this function computes no money, it sums what the
    posting service already wrote).
    """
    from decimal import Decimal

    from django.db.models import Sum

    wanted = [str(entry_id) for entry_id in entry_ids if entry_id]
    if not wanted:
        return {}
    rows = (
        models.JournalLine.objects.filter(
            tenant_id=_tenant_id(),
            journal_entry_id__in=wanted,
            journal_entry__status=models.JE_POSTED,
            side="debit",
        )
        .values("ledger_account_id")
        .annotate(total=Sum("amount"))
    )
    return {str(row["ledger_account_id"]): row["total"] or Decimal("0") for row in rows}


# ── one POSTED entry by its replay key (LBX-05, 2026-10-30) ─────────────────
def posted_entry_for_key(posting_key: str) -> dict[str, Any] | None:
    """`{"entry_id", "debits"}` for THIS tenant's posted entry under `posting_key`, or None.

    PUBLISHED FOR PAYMENTS' bank-rec lane (`DEF-PAY-10694`): a bank fee typed on
    a Reverse is posted under `payment|<id>|bank_fee`, and when the statement's
    own fee line arrives the clerk links the line to THAT entry rather than
    posting the same fee a second time. Reading the entry by its key is the
    only way payments can find it without reading ledger tables itself (B1).
    Tenant-scoped like every read here (CLAUDE.md rule 1).
    """
    from decimal import Decimal

    from django.db.models import Sum

    entry = (
        models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), posting_key=posting_key, status=models.JE_POSTED
        )
        .only("id")
        .first()
    )
    if entry is None:
        return None
    debits = models.JournalLine.objects.filter(
        tenant_id=_tenant_id(), journal_entry_id=entry.pk, side="debit"
    ).aggregate(total=Sum("amount"))["total"]
    return {"entry_id": str(entry.pk), "debits": debits or Decimal("0")}


# ── the accounting months a tenant has actually posted into ─────────────────
def posted_months() -> tuple[tuple[date, date], ...]:
    """Every calendar month this tenant has a POSTED journal entry in, oldest first.

    **Why this exists and why it lives here.** `BR-RBS-042` clause 2 makes every
    runbook input's domain tenant-resolved and never hardcoded — *"a two-service
    utility sees two"* — and the month-end journal export's one input is a
    PERIOD. A domain of *the last twelve months* would offer eleven empty files
    to a utility that went live in August, and a hardcoded list would offer none
    at all to one that has been live for three years. So the domain is the
    months the books themselves hold.

    ⚠ **POSTED ONLY, WHICH IS THE SAME LINE `trial_balance` DRAWS.** A draft
    entry is not in the books, so a month whose only entries are drafts is not
    an accounting month yet and is not offered as one. Offering it would produce
    a file of zeroes that reads as *"nothing happened in July"* — the shape
    `result_files.py` calls the most dangerous this product has.

    Returned as `(first_day, last_day)` pairs rather than as labels, because the
    caller needs the window to read a trial balance with and a label is a
    display decision it can make for itself.
    """
    rows = (
        models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), status=models.JE_POSTED
        )
        .annotate(month=TruncMonth("entry_date"))
        .values_list("month", flat=True)
        .distinct()
        .order_by("month")
    )
    months: list[tuple[date, date]] = []
    for first in rows:
        if first is None:  # pragma: no cover — entry_date is NOT NULL
            continue
        first = first.date() if hasattr(first, "date") else first
        last = date(
            first.year + (1 if first.month == 12 else 0),
            1 if first.month == 12 else first.month + 1,
            1,
        ) - timedelta(days=1)
        months.append((first, last))
    return tuple(months)


def accounts_without_a_code() -> tuple[dict[str, str], ...]:
    """Live accounts a bookkeeper's chart cannot be mapped to — a blank `code`.

    An accounting import addresses an account by its CODE (`A14 §Accounting
    exports` — CSV and IIF address accounts by code and name, which is why
    neither needs a target ref). An account whose code is blank therefore has
    nothing to put in the *account code* column, and a file that carried it
    would either drop the row silently or invent a code. **Inventing one is the
    single worst thing an export can do**: it imports cleanly and puts the money
    somewhere nobody chose, and nothing surfaces until a reconciliation.

    `code` is `NOT NULL`, so this is the empty string and never a NULL — which
    is exactly why a column constraint cannot catch it and a read has to.
    """
    rows = (
        _live_accounts()
        .filter(code__in=("", " "))
        .values("id", "name")
        .order_by("name")
    )
    return tuple({"id": str(row["id"]), "name": row["name"] or ""} for row in rows)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (sources: 12-governance/02-decision-log.md 2026-08-11 "OQ-106 IS CLOSED" + "OQ-110 CLOSED" + "STORM WATER AND THERMAL HEAT GET REVENUE ACCOUNTS" · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ seed chart · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-010 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane: account_is_live published so tenancy can validate a tenant's own GL override — ownership and liveness, which an FK does not give) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: docstring corrected — the tax read is RATING's by the same ruling, not an unbuildable gap) · AMENDED 2026-08-15 by the AP-capture lane (US-LED-017: cost_accounts / cost_account_row / cost_account_for_service / cost_account_for_category — every row carries its `unsigned` marker because the marker has no column, field map D-10) · AMENDED 2026-08-18 by the CR-008 ledger lane (B-10 / OQ-264 CLOSED: `entry_debit_totals` published for payments' bank-rec lane — reconciliation credits what the member receipts DEBITED, read from the entries, never from today's tender mapping; tenant-scoped, POSTED debit lines only)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S56 mapping endpoints are another story) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see 06-backend/tests/test_us_led_005_gl_designations.py
# exceptions: a FEE line's account (rating.charges.gl_account_id) and a TAX
#         line's liability account (rating.taxes.liability_gl_account_id) are
#         NOT answerable here and are named in the docstring rather than
#         returned as a silent None. CORRECTED 2026-08-11: this line said the
#         tax half was unanswerable because `invoice_lines` had no authority
#         column and cited OQ-116 as the open gap. OQ-116 is CLOSED (PO ruling,
#         BR-BIL-069), the column exists, and the read is rating's by the same
#         ruling — the ABSENCE here is now a boundary, not a gap · no composite
#         per-invoice-line
#         adapter is published: `apps/billing/issue.py` proposes
#         `gl_account_ids_for_lines(rows)` keyed on BILLING's line kinds, its
#         own docstring calls that signature "PROPOSED, not settled", and the
#         kinds are billing's vocabulary — REPORTED to the lane rather than
#         guessed here · `gl_account_for_designation` RAISES on an unknown
#         designation while every other read returns None; the asymmetry is
#         deliberate and argued in its docstring ·
#         `cost_account_for_service` / `cost_account_for_category` RESOLVE BY
#         CODE, which is the exception this module's own docstring warns
#         against. Lawful only because a cost account carries no designation
#         and minting one would claim a slot in a signed enumeration for an
#         account finance has not approved. **A tenant who renumbers 5110 loses
#         the DEFAULT and picks the account by hand** — the read never lands on
#         the wrong account, it lands on none. The fix is a service→cost-account
#         attribute (the BR-BIL-067 shape) once the B5 addendum is signed.
#         REPORTED · the `unsigned` marker is DERIVED from chart.py because no
#         column carries it (field map D-10): honest for the eight seeded codes,
#         silent about a tenant's own 5115, and a column is the schema lane's
#         call
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
