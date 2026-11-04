# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-009 (S59 Account ledger report — the full BR-REP-008 source
#           vocabulary and the running balance, reached through the report
#           viewer) · US-LED-010 (S60 By-premises summary — which today
#           REFUSES, with the money it cannot attribute) ·
#           US-REP-019 (S7 Dashboard — `GET /dashboard/summary`, A11's own S7
#           row, added 2026-08-16 from DEF-129: the first screen after every
#           sign-in had no story, no screen and no endpoint)
#           Screens: S7 · S59 · S60
# Rules:    BR-LED-010 (account ledger: account + date range → dated
#           charges/payments + running balance) · BR-LED-011 (by-premises:
#           billed/collected/owed) · BR-REP-001 (every money number labels its
#           date basis) · BR-REP-002 (read-models over journal-line dimensions,
#           never a side-maintained number) · BR-REP-006 (filters enumerate
#           LIVE vocabularies, never a hardcoded list) · BR-REP-008 (Type = the
#           FULL source vocabulary, so the report foots to the AR tie-out) ·
#           BR-REP-018 (downloads per IS-11 — NOT served here, see below) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1
#           (cross-tenant reads as absent) · CLAUDE.md rule 1 · rule 2
# Tests:    06-backend/tests/test_us_led_ledger_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           apps/ledger/reporting.py + apps/ledger/wire.py (READ ONLY — this
#           file calls them and writes nothing anywhere) ·
#           06-backend/openapi/schema.json (BE-11 TC05)
# ───────────────────────────────────────────────────────
"""`GET /reports/{key}` — the report viewer, serving S59 and S60 today.

11b §1 line 32 puts both screens on this path: *"`GET /reports/{key}` (S44/46)
— OK. **Also serves S59/S60** (13a)."* 13a's own rows agree
(*"S59 Report — Account ledger … GET /reports/{key}"*, same for S60), and
04-docs/05-modules/12-reports/01-overview.md settles why the route lives in
THIS module while the numbers come from the ledger:

    "**ledger owns** the TB/account-ledger/by-premises/remittance STORIES
     (US-LED-007..010/014 — S44 routes to them); **reports owns** the report
     CENTER (S44 catalog · S46 viewer · IS-11 download pipeline …)"

So the viewer route is the report centre's and the read models are
`apps.ledger.reporting`'s, called through its published functions and its
shared serializer — never by reaching into ledger's models, which B1 forbids
and G6 greps for. This module owns no tables and writes nothing.

════════════════════════════════════════════════════════════════════════════
THE `{key}` VOCABULARY — THE ONE THING THIS LANE HAD TO NAME, AND WHERE FROM
════════════════════════════════════════════════════════════════════════════
**No signed document contracts the key strings.** A11 gives the path and
"params → rows + totals"; 11b says which screens it serves; 13a maps the
screens to the stories. None of the three names a key.

They were therefore taken from the only machine-readable slugs for these two
reports that appear in a ratified document — the EXPORT FILENAMES in the
stories' own §4 Test Data, which are fixtures, not prose:

    US-LED-009 §4   brazos-bend_account_ledger_ACC-1042_2026-07_posting_….csv
    US-LED-010 §4   brazos-bend_by_premises_2026-07_posting_20260805.csv
                              ^^^^^^^^^^^^^^     ^^^^^^^^^^^

giving `account_ledger` and `by_premises`. That is a derivation from signed
fixtures rather than an invention, and it is still **REPORTED**: if the report
centre lands a catalog (US-REP-001) with its own key grammar, these two rename
with it and this docstring is where the next agent finds out why they were ever
these strings.

An UNKNOWN key is refused with VAL-005 and the refusal **enumerates the keys
this deployment actually serves**, so the vocabulary is discoverable from the
API itself without minting an uncontracted `GET /reports` index (BR-REP-006's
posture: a vocabulary is read live, never hardcoded into a client).

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT SERVED — none of it stubbed, because a 501 is a promise
════════════════════════════════════════════════════════════════════════════
  · **every OTHER key of the S44 library** — AR aging summary, DSO, revenue by
    service & rate, payments by method, sales tax remittance, trial balance,
    the operations and compliance sets (A14 §Report library). They are the
    reports module's own stories (US-REP-002/003/005–009/011, EP-REP-01..05)
    and most are blocked on the same two things S36's aging panel is: a journal
    line carries no due date and `account_opening_buckets` is unbuilt. An
    unknown key naming them as "not served here" would be worse than a plain
    refusal — it would advertise a route.
  · `POST /reports/{key}/export` and the IS-11 PDF/CSV halves of US-LED-009 §1
    and US-LED-010 §1 (BR-REP-018) — the export lane is SEQUENCED behind the
    job runner (PO ruling 2026-08-09, decision log), and this deployment has no
    job runner (TD-17).
  · `GET /reports/schedules` · `/history` · `/datasets` · `/custom` (11b §2.11)
    — S45 and S47, the reports module's own tables, none of which exist.
"""

import uuid
from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from apps.identity.auth import IdentitySessionAuthentication
from apps.tenancy import exports as export_kernel
from apps.tenancy import selectors as tenancy_selectors
from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core.permissions import AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

from . import catalog as report_catalog  # noqa: F401 — superseded on the catalogue path by `catalogue_read` (P1.1); still the home of the report KEY constants
from . import catalogue_read
from . import datasets as reports_datasets
from . import definitions as reports_definitions
from . import dashboard as dashboard_read_model
from . import queries
from . import runner as reports_runner
from . import report_seams as seams
from . import role_gate as reports_role_gate  # `P5.9` — BR-REP-023, asked here and in `catalogue_read`
from . import run_history
from .dashboard_tab_api import DASHBOARD_TAB_URLS
from .schedules_api import SCHEDULE_URLS
from . import service_accounts as svc_accounts
from .service_account_auth import (
    ReportServiceAccountAuthentication,
    ServiceAccountPrincipal,
    ServiceAccountThrottle,
)


class ServiceAccountOrTenantRole(AnyTenantRole):
    """A staff member with a Reports role, OR a machine principal (`P2.20`).

    ⚠ **THE MACHINE IS LET PAST THE ROLE CHECK AND IS NOT GIVEN A ROLE**, which
    is the whole difference between this and *"a person's password in a BI
    config file"* (§7.8). A `ServiceAccountPrincipal` carries no `role`
    attribute at all, so it cannot accidentally satisfy a role test somewhere
    else in the product; what it carries instead is its named list of reports,
    checked per key inside the view.

    ⚠ **IT IS NARROWER THAN `AnyTenantRole`, NOT WIDER.** A person still needs
    their Reports permission. A machine reaches exactly one route, and only for
    the keys it was granted — a smaller surface than any human role in A4.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if isinstance(getattr(request, "user", None), ServiceAccountPrincipal):
            return True
        return super().has_permission(request, view)

#: S59. Params: `account` (required), `from`, `to`.
KEY_ACCOUNT_LEDGER = report_catalog.KEY_ACCOUNT_LEDGER
#: S60. Params: `from`, `to`.
KEY_BY_PREMISES = report_catalog.KEY_BY_PREMISES

#: The keys this deployment serves, in the order a caller meets them. Named
#: once so the router, the dispatcher and the refusal cannot drift apart.
#:
#: ⚠ AMENDED 2026-08-16 (reports lane) and again 2026-09-26 (lane DS-LEDGER).
#: The two ledger-owned keys are joined by the EIGHT the reports module answers
#: itself — AR ageing, the billing register, revenue by service & rate and
#: payments by method, plus the `journal_lines` dataset's trial balance,
#: journal export, tax remittance and close pack. The tuple is
#: BUILT from `_VIEWERS` below rather than typed a second time, because the
#: whole reason the dispatcher is a dict is that an advertised key and a served
#: key must not be able to diverge.


def _tenant_currency() -> str | None:
    """The tenant's declared CHAR(3), through tenancy's own published read —
    see `apps/ledger/api._tenant_currency` for why the label is the tenant's
    and not a Σ-derived one."""
    return tenancy_selectors.regional_settings().get("currency")


def _date_param(params: Any, name: str, *, required: bool) -> date | None:
    """One ISO calendar date, or a refusal naming the parameter."""
    raw = params.get(name)
    if raw is None or str(raw).strip() == "":
        if required:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="reports.viewer.param_required",
                field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
            )
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="reports.viewer.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


def _required_window(params: Any) -> tuple[date, date]:
    """`from` + `to`, both required, and never inverted.

    US-LED-009 TC-6, verbatim: *"Param validation rejects the range … never an
    empty-but-plausible report."* Both bounds are required because a
    PARAMETERIZED REPORT is defined by its parameters — A14's viewer opens with
    a date-range bar, and a ledger run with no window would print a customer's
    entire history under whatever heading the screen happened to render.
    """
    start = _date_param(params, "from", required=True)
    end = _date_param(params, "to", required=True)
    assert start is not None and end is not None  # noqa: S101 — required=True guarantees both
    if start > end:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="reports.viewer.range_inverted",
            params={"from": start.isoformat(), "to": end.isoformat()},
            field_errors=[
                {"field": "from", "code": errors.VAL_RANGE},
                {"field": "to", "code": errors.VAL_RANGE},
            ],
        )
    return start, end


#: `CR-142-BRC07` `P0.14` — a ledger read this deployment does not publish,
#: stated as a refusal a screen can render rather than as an ImportError.
#:
#: ⚠ **THE IMPORT USED TO BE AT THIS MODULE'S TOP LEVEL** —
#: `from apps.ledger import reporting, wire` — so a deployment without
#: `apps.ledger.reporting` lost `GET /reports/{key}` ENTIRELY, the four reports
#: this module owns included, and lost `GET /dashboard/summary` with them. The
#: module's two most important reports bypassed its own refusal machinery: every
#: other read in this file goes through `report_seams.resolve`, whose whole
#: purpose is to turn a missing owner into a named gap (BR-REP-024).
#:
#: SYS-INTERNAL rather than a 4xx, deliberately: the caller did nothing wrong
#: and the report is real — what is missing is a module on the server.
#: ⚠ ONE KEY FOR ALL FOUR READS, NOT FOUR. `params.detail` never reaches a
#: screen (PO 2026-08-19), so a per-read key would buy the CLERK nothing and
#: cost eleven catalogues four sentences apiece. `wanted_read` is what the next
#: AGENT needs and it goes where an agent looks: the exception's own args.
def _ledger_gap(key: str, wanted_read: str) -> Any:
    return errors.SysError(
        errors.SYS_INTERNAL,
        message_key="reports.ledger_read_model_is_not_published",
        br_ref="BR-REP-024",
        params={"report": key, "wanted_read": wanted_read},
    )


def _account_ledger(request: Any) -> dict[str, Any]:
    """S59 (US-LED-009) — one account's receivable, dated, with a footer.

    `account` is REQUIRED. There is no "all accounts" account ledger: the
    report IS an account's ledger, its opening row is that account's position
    at `from`, and BR-REP-008's tie-out check (*"Σ closing balances of all
    account ledgers = the AR tie-out"*, LE-1's 135.90 + 16.42 = 152.32) is
    performed over runs, not inside one.

    **THE `premises` PARAMETER OF A14 IS NOT ACCEPTED**, and that is deliberate
    rather than missing. US-LED-009 §8 (amended 2026-08-11) records the reason:
    `journal_lines.premises_id` is NULL on every row in the product because
    US-LED-002 is unbuilt, so a premises parameter would be accepted, change
    nothing, and make the report LOOK filtered — which is worse than not
    offering it. It returns the day the dimension is stamped.

    An account id belonging to another tenant yields an EMPTY ledger rather
    than an error, and that is the isolation posture working: the read model's
    queryset is tenant-scoped (RLS FORCE plus an explicit filter), so a foreign
    id simply matches nothing. `test_us_led_009_tc6b__a_foreign_account_id_yields_nothing`
    already holds it at the read-model level.
    """
    account_id = request.query_params.get("account")
    if not account_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="reports.account_ledger.account_required",
            field_errors=[{"field": "account", "code": errors.VAL_REQUIRED}],
        )
    start, end = _required_window(request.query_params)
    result = seams.account_ledger(account_id, start=start, end=end)
    if result is None:
        raise _ledger_gap("account_ledger", "apps.ledger.reporting.account_ledger")
    shaped = seams.account_ledger_dict(result, currency=_tenant_currency())
    if shaped is None:
        raise _ledger_gap("account_ledger", "apps.ledger.wire.account_ledger_dict")
    return shaped


def _by_premises(request: Any) -> dict[str, Any]:
    """S60 (US-LED-010) — the report that reports its own blocker, in money.

    ⚠ **THIS DOCSTRING DESCRIBED A REFUSAL THAT ENDED ON 2026-08-16, AND WAS
    CORRECTED ON 2026-09-02 (`DEF-3382`).** It read: *"`premises_id` and
    `unit_id` are NULL on every journal line in this product (nothing stamps
    either; US-LED-002 is unbuilt), so there is no per-premises figure to sum."*
    **US-LED-002 landed that day** — `apps/ledger/posting.py` resolves account →
    unit → premises at posting time — and `reporting.by_premises_summary`'s own
    docstring was corrected with it while this caller was not. Hard-won law 1:
    the module that computes the figure and the route that serves it disagreed
    in writing for six weeks, and this route is the one a reader reaches first.
    **S60 renders LE-6's three rows today** — 500 Main St 247.87 · Oak Grove
    16.42 · Marina Bay 289.40, footing to the same 553.69 that used to be the
    refusal's measurement.

    **THE `available: false` SHAPE IS KEPT AND IS STILL REACHABLE**, which is
    why it is described rather than deleted: a tenant that has designated no AR
    account still gets it, and the read model publishes the money it could not
    attribute (`unattributed_billed` / `unattributed_collected`) beside the
    table rather than dropping it from the footer. It answers **200**, not 404
    and not 422, and the choice is the story's. The three possible answers, two
    of which are defects, are set out in `reporting.by_premises_summary`: an
    empty table reads as *no activity this period* to the one person who most
    needs to know otherwise; a single *Unassigned* row sorts, exports and reads
    like a premises; and the third — this one — says so.

    A 404 would say the report does not exist; a 422 would say the CALLER did
    something wrong. Neither is ever true here: the request is valid and the
    report is real.
    """
    start, end = _required_window(request.query_params)
    result = seams.by_premises_summary(start=start, end=end)
    if result is None:
        raise _ledger_gap("by_premises", "apps.ledger.reporting.by_premises_summary")
    shaped = seams.by_premises_dict(result, currency=_tenant_currency())
    if shaped is None:
        raise _ledger_gap("by_premises", "apps.ledger.wire.by_premises_dict")
    return shaped


#: key → the function that answers it. A dict rather than a chain of `if`s so
#: the refusal below can enumerate the vocabulary from the same object that
#: dispatches it — a served key and an advertised key cannot diverge.
_VIEWERS = {
    KEY_ACCOUNT_LEDGER: _account_ledger,
    KEY_BY_PREMISES: _by_premises,
    # The reports module's own four (US-REP-005/006/007). Each takes the
    # request's query params and answers a basis-labeled report — see
    # `apps/reports/queries.py`, which owns every one of these shapes.
    # ⚠ THROUGH `apps/reports/runner.run()` SINCE 2026-09-26 (`P0.5`), and so
    # is `apps/reports/exports.py`. These four used to call
    # `queries.VIEWERS[key]` here while the export called it there, with its
    # own defaults — two routes to the same numbers kept in agreement by
    # somebody remembering. The runner resolves the definition from
    # `report_definitions` and binds the request's parameters against the
    # dataset's own declaration.
    **{
        key: (lambda request, _key=key: reports_runner.run(
            _key,
            request.query_params,
            # `BR-REP-019` / `DEF-REP-6864` — a colleague's PRIVATE report is
            # absent at its address too, not merely absent from the list.
            as_user=getattr(getattr(request, "user", None), "id", None),
        ).payload)
        for key in queries.VIEWERS
    },
}

SERVED_KEYS: tuple[str, ...] = tuple(_VIEWERS)


# ── `DEF-REP-6898` (2026-09-27) · A REPORT THAT CANNOT BE PRODUCED ─────────
# ⚠ **THIS WAS A 500 FOR EVERY ONE OF TWENTY-SEVEN REPORTS, AND THE SENTENCE
# THE CLERK NEEDED ALREADY EXISTED TWO CLICKS EARLIER.** `DatasetCannotServe`
# and `DatasetNotExecutable` are siblings — both `NotImplementedError`, neither
# a subclass of the other — and the `except` below named the second by name and
# not the first. So the refusal the dataset queries actually raise fell straight
# through DRF's catch-all and drew *"The finance figures could not be loaded /
# Something went wrong on our side. Nothing was saved."* over a meter-reads
# report, while the catalogue card for the same key said, calmly and correctly,
# *"This report cannot be produced yet."* Hard-won law 2, one layer out: the
# engine refused by name and the WIRE threw the name away.
#
# **THE STATUS IS 422 AND IT IS NOT 500, 404 OR 409.** Not 500 — nothing broke
# and nothing was lost, and a fault report sends a clerk to support for an
# answer the product already holds. Not 404 — the report is real, it is listed
# in the catalogue, and an absent address would make it indistinguishable from
# a typo (the one thing `HR-1` reserves 404 for). Not 409 — there is no
# conflicting state to resolve and no retry that would help. It is a SEMANTIC
# refusal of a well-formed request, which is the B12 §3 row `BIZ-COMPLETENESS`
# occupies, and the completeness that is missing is real: this definition's
# grain is not the grain the dataset behind it states.
#
# ⚠ **IT CARRIES NO NEW CLERK-FACING STRING, DELIBERATELY.**
# `reports.library.unavailableGeneric` is the card's own key, authored in all
# eleven catalogues. Minting a second sentence for the viewer would let the two
# surfaces drift apart again — which is the defect — and would risk a twelfth
# instance of `DEF-REP-6900` (a key used on screen and never added).
#
# ⚠ **`params.detail` IS THE QUERY'S OWN PROSE AND NEVER REACHES A SCREEN.**
# The PO's ruling of 2026-08-19 drops it client-side; B14 rule 33 puts
# RATIONALE at zero words on screen. It travels for the log and for the next
# agent, which is where a paragraph explaining grain belongs.
def _cannot_be_produced(key: str, refusal: queries.DatasetCannotServe) -> Any:
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-REP-024",  # a stated absence, never a silent one
        message_key="reports.library.unavailableGeneric",
        params={
            "key": key,
            # The same machine code the CARD carries, from the same module, so
            # a screen resolving a more specific sentence resolves the same one
            # in both places.
            "reason_code": catalogue_read.REASON_GRAIN_NOT_SERVED,
            "detail": refusal.reason,
        },
    )



def _with_export_flag(payload: Any, key: str) -> Any:
    """Say whether THIS report can be downloaded, by asking the registry that
    `POST /exports` itself consults (`DEF-REP-6899`).

    ⚠ **THE VIEWER DREW `Download CSV` ON EVERY REPORT THAT SERVED A PAYLOAD
    AND FOUR WERE REGISTERED.** Clicked on Account Census at 1440 on
    2026-09-27: `POST /api/exports` answered **404 errors.not-found** and the
    screen did not change in any way — no toast, no panel, nothing a clerk
    could see. That is hard-won law 2's mirror, a live screen behind a control
    that does nothing, and it got wider every time a report started serving
    rows, because the control was drawn by the presence of a payload and the
    registry was never asked.

    ⚠ **IT ASKS `export_resource()` AND NOT A LIST OF KEYS.** The answer has to
    be the one the POST will give, or the screen and the endpoint disagree
    again the first time a resource is registered or removed —
    `DEF-REP-6866`'s lesson one module over: *the catalogue and the viewer must
    agree about whether a control opens onto anything, and the only way to
    guarantee that is to ask the code that runs it.* A hand-kept list here
    would be a second derivation of one fact.

    ⚠ **IT NEVER RAISES.** A payload that is not a dict — no report serves one
    today — is returned untouched rather than made an error on the read path.
    """
    if not isinstance(payload, dict):
        return payload
    payload = dict(payload)
    payload["exportable"] = export_kernel.export_resource(key) is not None
    return payload


@api_view(["GET"])
# ⚠ **TWO AUTHENTICATIONS, AND THE ORDER IS THE POINT** (`P2.20`). The service
# account is tried FIRST and returns `None` for any request that is not carrying
# one of our bearer tokens, so a browser falls straight through to the session
# class and is byte-for-byte unaffected. `AnyTenantRole` is listed second in the
# permission list for the same reason it always was — a PERSON still needs their
# role — and `ServiceAccountPermission` is what lets a machine past it, because
# a machine has no role to check and must never be given one.
@authentication_classes(
    [ReportServiceAccountAuthentication, IdentitySessionAuthentication]
)
@permission_classes([ServiceAccountOrTenantRole])  # A4 Reports + P2.20 tier 1
@throttle_classes([ServiceAccountThrottle])  # P2.20: counts credentials, not people
def report(request: Any, key: str) -> Response:
    """`GET /reports/{key}` (11b §1 · 13a) — S59 and S60 today.

    ⚠ **`P5.9` — A KEY THIS ROLE MAY NOT RUN IS `403 AUTH-002`, NOT 404 AND NOT
    AN EMPTY RESULT.** `BR-REP-023` restricts `access_review` to System Admin
    and Executive; the floor lives on the DEFINITION (`min_role`) and is read
    by `apps/reports/role_gate.py`, the same function the catalogue asks — so a
    card that is absent for this role and an address that serves it cannot
    disagree. A 404 would make a restricted report indistinguishable from a
    typo, and `HR-1` reserves 404 for another tenant's resource.

    An unknown key is **VAL-005 BIZ-free 422**, carrying the served vocabulary
    in `params.keys`. Two alternatives were rejected: a 404 (which would make
    an unbuilt report indistinguishable from a typo, and from another tenant's
    resource — the one thing HR-1 reserves 404 for) and a silent empty result
    (a report viewer that renders nothing for `?key=revenue_by_srevice` is the
    hardest bug in this product to see).
    """
    require_tenant(request)
    # `DEF-REP-10146` — a saved report's stored key (`overdue-60`) from the
    # spelling the viewer sends (`overdue_60`), BEFORE the role gate and the
    # privacy check look it up. See `runner.canonical_key`.
    key = reports_runner.canonical_key(key)
    # ⚠ **`P2.20` — A MACHINE PRINCIPAL READS A NAMED LIST AND NOTHING ELSE.**
    # Brief §7.8, p88: *"a connection granted Revenue Analysis and Trial Balance
    # can read those two and nothing else; AR Ageing later means somebody grants
    # it."* The check is HERE, on the one route a BI tool calls, rather than in
    # a permission class — a permission class answers *may this principal use
    # the reports module*, and this is a different question asked per key.
    #
    # ⚠ **IT IS ASKED BEFORE THE KEY IS RESOLVED, SO A GRANT CANNOT BE LEARNED
    # FROM A TYPO.** Resolving first would answer an ungranted-but-real key and
    # an unknown key with two different refusals, and the pair of them is a
    # membership oracle over the whole catalogue.
    principal = getattr(request, "user", None)
    if isinstance(principal, ServiceAccountPrincipal):
        account = principal.account
        if not svc_accounts.may_read(account, key):
            raise svc_accounts.refuse_report(key, getattr(account, "report_keys", None))
    else:
        # ── `P5.9` · `BR-REP-023` · THE ROLE FLOOR ON THE VIEWER ───────────
        # ⚠ **THE SAME FUNCTION THE CATALOGUE ASKS**, so a card that is absent
        # for this role and an address that serves it cannot disagree. Asked
        # only of a PERSON: a machine principal carries no `role` at all and is
        # already held to the narrower question above — the named list of keys
        # it was granted. See `role_gate.py`'s docstring.
        #
        # ⚠ **ASKED BEFORE THE VIEWER AND BEFORE THE RUNNER**, for the reason
        # the service-account check states one branch up: a refusal that
        # arrives only after the key resolves tells a caller which keys are
        # real, and the pair of answers is a membership oracle.
        gate = reports_role_gate.for_key(key)
        if gate is not None and not reports_role_gate.may_run(
            gate, getattr(request, "tenant_role", None)
        ):
            raise reports_role_gate.refusal(key)
    viewer = _VIEWERS.get(key)
    if viewer is not None:
        try:
            return Response(_with_export_flag(viewer(request), key))
        except queries.DatasetCannotServe as refusal:
            # A shipped key reaches the runner through `_VIEWERS` too, so the
            # refusal has to be caught on BOTH paths or twenty-eight reports
            # split between a sentence and a 500 depending on which branch
            # served them. Only this one exception is caught here: a
            # `DatasetNotExecutable` from a SHIPPED key is not an unknown key
            # and must not be dressed up as one.
            raise _cannot_be_produced(key, refusal) from refusal

    # ── `DEF-REP-6867` (2026-09-27) · A REPORT A UTILITY WROTE ─────────────
    # ⚠ **`_VIEWERS` IS FROZEN AT IMPORT AND A TENANT-AUTHORED KEY CAN NEVER BE
    # IN IT.** Until this branch existed, every custom report answered *"There
    # is no report called overdue-60"* at its own address — while `runner.run`
    # served it perfectly when called directly, because the runner resolves
    # from `report_definitions` and falls back to the DATASET's query. The
    # catalogue listed it, the row existed, the engine worked, and the door was
    # shut. Found by saving one and clicking it (law 6).
    #
    # ⚠ **THE REFUSAL STAYS FOR A KEY NOTHING CAN SERVE**, and the `keys` it
    # enumerates are still the shipped ones: a typo should still be told what
    # exists, and listing a colleague's private report names would be the leak
    # `resolve_for` closes. The two cases are now told apart by asking the
    # RUNNER rather than by asking a frozen dict.
    try:
        return Response(
            _with_export_flag(
                reports_runner.run(
                    key,
                    request.query_params,
                    as_user=getattr(getattr(request, "user", None), "id", None),
                ).payload,
                key,
            )
        )
    except queries.DatasetCannotServe as refusal:
        # ⚠ **FIRST, AND THE ORDER IS LOAD-BEARING TO A READER RATHER THAN TO
        # PYTHON.** The three are siblings today (`test_rep_ds_invoices`
        # asserts `DatasetCannotServe` is not a `DatasetNotExecutable`), so
        # either order works — and the day one of them gains a base class, a
        # report that names its own reason must not be reported as a report
        # that does not exist.
        raise _cannot_be_produced(key, refusal) from refusal
    except (reports_runner.DefinitionNotFound, reports_runner.DatasetNotExecutable) as exc:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="reports.viewer.unknown_key",
            params={"key": key, "keys": list(SERVED_KEYS)},
            field_errors=[{"field": "key", "code": errors.VAL_UNKNOWN_LOOKUP}],
        ) from exc


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def report_library(request: Any) -> Response:
    """`GET /reports` — the S44 library (US-REP-001).

    **This route is contracted by no signed document and is minted here.**
    REPORTED: A11 gives `GET /reports/{key}`; 11b §2.11 gives `/reports/schedules`,
    `/history`, `/datasets` and `/custom`; none of the five is an index.

    It is served rather than compiled into the client for the one reason a
    client cannot cover: **which reports THIS deployment can actually produce,
    and why not.** Thirteen of the twenty-three cards ship `available: false` today,
    each naming the read that would close it — and a card grid drawn from a
    hardcoded client list has no way to say so. It would show twenty-three confident
    tiles and discover on click that most answer nothing, which is the
    "confident empty report" posture S60 was built to avoid.

    The vocabularies the S46 parameter bar needs ride along on the same answer
    (BR-REP-006 — services are the tenant's ENABLED set, never the prototype's
    hardcoded trio), so opening the library costs one request and the parameter
    bar cannot render a service the tenant does not have.
    """
    require_tenant(request)
    # ⚠ **P1.1 (2026-09-26): THE CATALOGUE COMES OUT OF `report_definitions`.**
    # `apps/reports/catalog.py`'s frozen tuple of 23 is no longer read on this
    # path. The vocabularies are computed FIRST because the catalogue's service
    # filter reads the tenant's enabled set out of them — `P1.8`, and the whole
    # of it: the answer already carried that list for the S46 parameter bar, so
    # opening a report from the catalogue costs no extra request.
    vocabularies = queries.parameter_vocabularies()
    payload = catalogue_read.catalogue_payload(
        request.query_params,
        vocabularies=vocabularies,
        user_id=getattr(getattr(request, "user", None), "id", None),
        # `P5.9` — the catalogue is filtered by the caller's role, on the
        # server. The screen never sees a card it may not open.
        role=getattr(request, "tenant_role", None),
    )
    payload["vocabularies"] = vocabularies
    return Response(payload)


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: S7 is "All staff" (A1 row S7)
def dashboard_summary(request: Any) -> Response:
    """`GET /dashboard/summary` (A11 S7 row · 11b §1) — US-REP-019.

    **This route existed in the contract and nowhere else until 2026-08-16**,
    which is one half of DEF-129: the first screen after every sign-in had no
    story, no screen and no endpoint, and `/{tenant}/dashboard` fell through the
    router's catch-all to render the literal string "SMARTBillHub — W0 scaffold".

    ⚠ **CR-015 (2026-08-19) ADDS `f.period`.** The PO: *"we will ahve to allow
    period filter on dashbaord - so user can select the filter."* It is spelled
    `f.period` because BR-SHL-011's URL grammar spells a filter `f.<name>`, and
    the point of putting it in the URL rather than in component state is that a
    period a person is looking at is then SHAREABLE: they can paste the link and
    the other person sees the same window. An unknown, misspelled or
    no-longer-available value FALLS BACK to the ruled default rather than
    refusing — a landing page that 500s on a stale bookmark is a locked front
    door, and `f.period=last_cycle` on a tenant that has since retired its only
    cycle is exactly that bookmark.

    ⚠ **CR-012 (2026-08-18) ADDED `asOf` AND DELIBERATELY DID NOT RENAME THIS
    ROUTE.** The PO's build spec names `GET /api/dashboard?tenantId&asOf`. Two
    halves of that, and they are answered differently:

      `asOf`      ADDED. It picks WHICH accounting period, and it is an argument
                  rather than a clock (BR-TEN-043) for the same reason
                  `payments.summary` takes one: a dashboard that cannot be asked
                  for last month cannot be reconciled against last month's
                  day-end. Absent ⇒ the tenant's own today.
      `tenantId`  **REFUSED, and it is not a preference.** The tenant comes from
                  the request context (hard rule 1, RLS FORCE). A tenant id in a
                  query string is a tenant id a caller can edit.
      the path    UNCHANGED. `GET /dashboard/summary` is A11's own S7 row and a
                  SIGNED interface; renaming it is a contract decision, so it is
                  REPORTED rather than silently taken.

    The window is otherwise the tenant's own computed period (BR-TEN-022) — the
    same one S36, S59 and S60 head their pages with, so four screens cannot
    disagree about which month a figure belongs to. Everything else the answer
    contains is described in `apps/reports/dashboard.py`, whose one law is
    BR-REP-024: a tile renders the OWNER's figure or reports that it cannot
    answer, never a zero.

    Always 200. There is no 404 and no 422: a malformed `asOf` FALLS BACK to the
    tenant's today (BR-SHL-011 — an undeclared or impossible parameter falls
    back rather than refusing), because a landing page that 500s on a
    hand-edited URL is a locked front door. An absent figure is a `null` with a
    reason beside it, which is a state of this deployment rather than an error
    the caller caused.
    """
    require_tenant(request)
    return Response(
        dashboard_read_model.dashboard_summary(
            as_of=_as_of(request.query_params.get("asOf")),
            # BR-REP-035 / BR-SHL-011. Passed through RAW and validated by the
            # read model against the vocabulary it built for THIS tenant —
            # never against a list spelled here, which would be a second
            # vocabulary drifting from the first (BR-REP-006's own lesson).
            period=request.query_params.get("f.period") or None,
            # BR-REP-033: which page actions this role may run is the SERVER's
            # answer. A control hidden only by the client is a suggestion.
            role=getattr(request, "tenant_role", None),
        )
    )


def _as_of(raw: Any) -> date | None:
    """One ISO day from the query string, or None. Never raises (BR-SHL-011)."""
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def report_datasets(request: Any) -> Response:
    """`GET /reports/datasets` (11b §2.11) — `P0.4`'s metadata endpoint.

    Serves the DECLARATION in `apps/reports/datasets.py`: nine datasets, each
    with its grain, its columns with a type — and, where a column is a
    quantity, its unit (CLAUDE.md hard rule 3) — its measures with an
    aggregation AND an additivity (`P0.16`), its dimensions with attributes and
    hierarchies, and the filters it accepts.

    It is served rather than compiled into the client for BR-REP-006's reason,
    the same one `report_library` gives: a vocabulary is read LIVE, never
    hardcoded into a screen. The edit panel says *"13 available"* and *"4 of 7
    shown"* by counting what is here, so a screen and the engine cannot be
    counting different things — which is exactly what the six hand-typed maps
    `P0.7` deletes were doing.

    ⚠ **IT IS NOT IN `06-backend/openapi/schema.json` AND THAT IS DELIBERATE
    (`DEF-GOV-6800`).** That file is a generated artifact nothing regenerates
    or diffs in `run_gates` — hard-won law 1 records that three files describe
    an OpenAPI CI-diff no workflow runs, and that is still true. Measured on
    2026-09-26 it is **six routes behind the code before this one**, all six
    other lanes'. Regenerating is a 316 KB whole-file rewrite that would
    publish those six under this lane's commit with a correct file count (law
    11, mechanism five), so it was not done.

    ⚠ Three of the nine carry `paginates: false`. That is not a defect in this
    payload: `invoices`, `payments` and `journal_lines` do not accept
    `limit`/`offset`/`sort` in their owning modules today (`DEF-PAY-4221`), and
    those three feed 32 of the 46 definitions. Serving `true` would be a check
    that cannot fail.
    """
    require_tenant(request)
    return Response(reports_datasets.registry_payload())


def _envelope(request: Any, result: dict[str, Any]) -> dict[str, Any]:
    """A selector's page dict → **the four keys this product puts on the wire**.

    In goes `{rows, page, per, total}`; out goes `{count, next, previous,
    results}` and nothing else. `07-frontend/src/api/paginated.ts` is the ONE
    description of those four names on the client and `G114` fails a second one.

    ⚠ **THE NAMES CHANGE HERE, AND THAT IS WHY THREE SHIPPED SCREENS DREW EMPTY
    TABLES** (`DEF-WRK-4119`, `DEF-AST-4120`, 2026-09-05). `rows` → `results`,
    `total` → `count`. A client that says `rows` is reading the SELECTOR, not
    the API — the right file for the row shape and the wrong one for the reply.

    ⚠ **AND EVERY OTHER KEY IS DISCARDED.** This returns a fresh dict; it does
    not update `result`. A view with an extra figure must spread —
    `{**_envelope(request, result), "reports": …}` — which `report_runs` does.

    It is a copy of `apps/work/api.py`'s and `apps/runbooks/api.py`'s because
    each module keeps its own; the thing that must not be copied is the CLIENT's
    description, and there is exactly one of those.
    """
    per, page, total = result["per"], result["page"], result["total"]
    last = max(1, -(-total // per))
    url = request.build_absolute_uri()
    return {
        "count": total,
        "next": replace_query_param(url, "page", page + 1) if page < last else None,
        "previous": replace_query_param(url, "page", page - 1) if page > 1 else None,
        "results": result["rows"],
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def report_runs(request: Any) -> Response:
    """`GET /reports/history` — screen `5·1`'s rows (`CR-142-BRC07` `P3.1`).

    ⚠ **PAGED, ALWAYS, AND THE PAGE IS CUT IN SQL** (`NFR-3`). `DEF-PAY-4221`
    is the register row for the four reads in this product that are not, and
    the reason this one never joins them is that a run history only grows: a
    utility at the top of the ICP running four reports a day on a schedule
    writes ~1,460 rows a year and nothing ever deletes one.

    ⚠ **THE PARAMS ARE THE KIT'S OWN NAMES** — `q`, `page`, `per`, plus
    `f.report` and `f.status` — so `DataTable` drives this endpoint with the
    request state it already builds for every other list. A filter naming a
    report this module does not own is IGNORED rather than refused: the value
    comes from a select whose options this same endpoint publishes, so a bad
    one is a stale tab rather than a caller error, and an empty page is the
    honest answer to it.
    """
    require_tenant(request)
    params = request.query_params
    page = run_history.runs(
        q=str(params.get("q") or ""),
        resource=params.get("f.report") or None,
        status=params.get("f.status") or None,
        page=_positive_int(params.get("page"), 1),
        per=_positive_int(params.get("per"), 50),
    )
    return Response(
        {
            # ⚠ **THE PRODUCT'S ONE LIST ENVELOPE, NOT THIS VIEW'S OWN.** The
            # first draft returned the selector's dict — `{rows, total, page,
            # per, pages}` — straight onto the wire, and `G114` refused it. It
            # was right: that is a TWELFTH description of a paged reply, and
            # three shipped Work screens drew empty tables over rows the API
            # had returned because a lane typed a client from the layer below
            # the boundary (`DEF-WRK-4119`, `DEF-AST-4120`).
            **_envelope(request, page),
            # ⚠ **SPREAD, BECAUSE `_envelope` DISCARDS EVERY OTHER KEY.**
            # `asset_work_orders` did not, and `maintenance_index` never left
            # the server. These two are the *All reports* and *Any status*
            # selects' options, served WITH the page so the screen needs one
            # call — and from the same registry the rows are filtered by, which
            # is what stops a filter offering a report no row can have.
            "reports": list(run_history.report_resources()),
            "statuses": list(run_history.RUN_STATUSES),
            # `P5.12` — the number the retention line states. Served with the
            # page for the same reason the two selects are: the sentence is a
            # fact about THIS utility, and a screen that typed `3` into its own
            # catalogue was telling a tenant who had set seven that it was
            # three. Named here because `_envelope` keeps nothing it is not
            # given.
            "retention_days": page["retention_days"],
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def report_run(request: Any, job_id: uuid.UUID) -> Response:
    """`GET /reports/history/{job_id}` — screen `5·2`, one run opened.

    Absent, malformed, another tenant's, or a job that is not a REPORT run →
    the same plain 404 (HR-1 / 11b G4: existence must not leak, and a
    distinguishable message would confirm the id).
    """
    require_tenant(request)
    row = run_history.run(job_id)
    if row is None:
        raise errors.NotFoundError()
    return Response(row)


def _refused(exc: Any) -> Any:
    """One `DefinitionRefused` as the envelope G1 wants.

    ⚠ **VAL-005 AND NOT A 403, EVEN FOR A RESERVED NAME.** A clerk who types
    *History* has made a naming mistake, not an access attempt: the refusal
    belongs in the NAME field beside the box they typed it in, and a 403 would
    render as a page-level "you may not do that" over a form they can fix in
    one keystroke.
    """
    return errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key=exc.message_key,
        params=dict(exc.params),
        field_errors=[{"field": "name", "code": errors.VAL_UNKNOWN_LOOKUP}],
    )


def _body(request: Any) -> dict[str, Any]:
    data = getattr(request, "data", None)
    return dict(data) if isinstance(data, dict) else {}


def _actor(request: Any) -> Any:
    return getattr(getattr(request, "user", None), "id", None)


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def report_definitions(request: Any) -> Response:
    """`POST /reports/definitions` — screen 2·4's **Save as** (`P5.1`).

    ⚠ **THE REPLY IS 201 AND IT CARRIES THE KEY, BECAUSE THE SCREEN NAVIGATES.**
    p23's DOORS row: *"the confirmation after Save as: saving a report drops you
    here with it in view, because a save that gives no sign of where the thing
    went is how a clerk saves the same report three times."* A body without the
    key would make the screen guess the address from the name, and the slug is
    this server's to compute — `Overdue 60+` twice gives `overdue-60` and
    `overdue-60-2`, and only the server knows which one it just wrote.

    ⚠ **`tenant_id` IS NOT ACCEPTED AND NEVER WILL BE.** Hard rule 1: the tenant
    comes from the request context. A tenant id in a body is a tenant id a
    caller can edit.
    """
    require_tenant(request)
    body = _body(request)
    try:
        saved = reports_definitions.save(
            name=body.get("name", ""),
            dataset=body.get("dataset", ""),
            group_code=body.get("group", "") or body.get("group_code", ""),
            sub_group_code=body.get("sub_group") or body.get("sub_group_code") or None,
            columns=body.get("columns") or (),
            filters=body.get("filters") or {},
            group_by=body.get("group_by") or (),
            sort=body.get("sort") or (),
            service_codes=body.get("service_codes") or (),
            # ⚠ `BR-REP-019` — absent means PRIVATE, never "whatever the column
            # defaults to". The default is the ruling (`P5.7`).
            visibility=body.get("visibility") or reports_definitions.DEFAULT_TENANT_VISIBILITY,
            owner_user_id=_actor(request),
            based_on=body.get("based_on") or None,
        )
    except reports_definitions.DefinitionRefused as exc:
        raise _refused(exc) from exc
    return Response(saved.as_dict(), status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def report_definition(request: Any, definition_id: uuid.UUID) -> Response:
    """`PATCH`/`DELETE /reports/definitions/{id}` — 2·2's save, and 1·2's delete.

    ⚠ **A PLATFORM ROW REACHED HERE IS REFUSED, NOT COPIED.** Copy-on-write
    lives on the POST: a screen editing a built-in has never owned a row to
    PATCH, so it calls Save as. If an id for one of the forty-six arrives here
    it is a client bug, and answering it by quietly creating a different row
    would hide that bug behind a success.
    """
    require_tenant(request)
    if request.method == "DELETE":
        try:
            key = reports_definitions.delete(definition_id, actor_user_id=_actor(request))
        except reports_definitions.DefinitionRefused as exc:
            raise _refused(exc) from exc
        return Response({"key": key, "deleted": True})
    body = _body(request)
    changes = {
        field: body[wire]
        for wire, field in (
            ("name", "name"),
            ("dataset", "dataset"),
            ("group", "group_code"),
            ("group_code", "group_code"),
            ("sub_group", "sub_group_code"),
            ("sub_group_code", "sub_group_code"),
            ("columns", "columns"),
            ("filters", "filters"),
            ("group_by", "group_by"),
            ("sort", "sort"),
            ("service_codes", "service_codes"),
            ("visibility", "visibility"),
        )
        if wire in body
    }
    try:
        saved = reports_definitions.update(
            definition_id, actor_user_id=_actor(request), **changes
        )
    except reports_definitions.DefinitionRefused as exc:
        raise _refused(exc) from exc
    return Response(saved.as_dict())


def _positive_int(raw: Any, fallback: int) -> int:
    """A counting number from the query string, or the fallback. Never raises.

    BR-SHL-011's posture: a malformed `page=` is a stale bookmark, not a caller
    to refuse. The SELECTOR clamps the ceiling; this only refuses nonsense.
    """
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


# ═══════════════════════════════════════════════════════════════════════════
# `P2.20` — BI TIER 1: ISSUE AND REVOKE A SERVICE ACCOUNT
#
# ⚠ **`SystemAdminOnly`, AND IT IS THE NARROWER OF TWO READINGS.** The PO wrote
# *"a · Administrators only … M. Okonkwo creates it and hands Dana the token +
# clerk"*, and Dana is a billing clerk. The brief reads that as an administrator
# ISSUES one and any staff member HOLDS and uses it (§7.8, p89) — and says in as
# many words that if a clerk may also CREATE one, *"it is one line"*. It is not
# assumed, because this is a credential.
#
# ⚠ **THESE TWO ROUTES ARE SESSION-AUTHENTICATED ONLY.** A service account may
# not mint or revoke a service account. Nothing here adds
# `ReportServiceAccountAuthentication`, so a bearer token reaching them is an
# ordinary unauthenticated request — which is the difference between a
# credential that can read two reports and one that can make more of itself.
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@permission_classes([SystemAdminOnly])
def report_service_accounts(request: Any) -> Response:
    """`GET` the tenant's service accounts · `POST` issues one.

    ⚠ **THE TOKEN IS IN THE `POST` ANSWER AND IN NO OTHER ANSWER, EVER.** There
    is no read that can return it, by construction: only the hash is stored.
    The `GET` carries `token_prefix` so an administrator can tell two apart.
    """
    tenant_id = require_tenant(request)
    from apps.reports.models import ReportServiceAccount

    if request.method == "GET":
        rows = ReportServiceAccount.objects.order_by("-created_at")
        return Response({"results": [svc_accounts.wire(row) for row in rows]})

    payload = request.data if isinstance(request.data, dict) else {}
    name = str(payload.get("name") or "").strip()
    keys = payload.get("report_keys")
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="reports.service_account.name_required",
            field_errors=[{"field": "name", "code": errors.VAL_REQUIRED}],
        )
    if not isinstance(keys, list) or not keys:
        # ⚠ **A CREDENTIAL GRANTED NOTHING IS REFUSED AT THE DOOR, NOT STORED.**
        # `may_read` already denies an empty list, so an empty grant would be
        # harmless — and it would also be a live token that answers 422 to every
        # call, which an administrator would read as a broken product rather
        # than as a half-finished form. §7.8: *"a named list of reports"*.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="reports.service_account.keys_required",
            field_errors=[{"field": "report_keys", "code": errors.VAL_REQUIRED}],
        )
    unknown = [key for key in keys if str(key) not in SERVED_KEYS]
    if unknown:
        # A grant for a report this deployment cannot produce is a grant that
        # will look revoked the first time it is used.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="reports.service_account.unknown_key",
            params={"keys": sorted(str(k) for k in unknown), "served": list(SERVED_KEYS)},
            field_errors=[{"field": "report_keys", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )

    token, token_hash, prefix = svc_accounts.mint_token()
    account = ReportServiceAccount.objects.create(
        tenant_id=tenant_id,
        name=name,
        token_hash=token_hash,
        token_prefix=prefix,
        report_keys=[str(key) for key in keys],
        created_by_user_id=getattr(getattr(request, "user", None), "id", None),
    )
    # CLAUDE.md hard rule 7's shape for a credential: the act is recorded and
    # the credential is not.
    svc_accounts.audit_issued(account, actor_user_id=getattr(request.user, "id", None))
    return Response(svc_accounts.wire(account, token=token), status=201)


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def report_service_account_revoke(request: Any, account_id: Any) -> Response:
    """`POST /reports/service-accounts/{id}/revoke` — stop it, keep its history.

    ⚠ **A TIMESTAMP AND NOT A DELETE.** §7.8: *"a revoked account silently
    breaks a board pack"* is a thing somebody has to be able to look up
    afterwards, and a deleted row takes its own trail with it. Revoking twice is
    idempotent and keeps the FIRST timestamp — the second call is somebody
    making sure, not a new fact.
    """
    require_tenant(request)
    from apps.reports.models import ReportServiceAccount

    account = ReportServiceAccount.objects.filter(id=account_id).first()
    if account is None:
        # The tenant scoping is RLS's, not a filter's: this queryset is already
        # inside the tenant context, so another tenant's id is simply not here.
        raise errors.NotFoundError()
    if account.revoked_at is None:
        account.revoked_at = svc_accounts.now()
        account.revoked_by_user_id = getattr(getattr(request, "user", None), "id", None)
        account.save(update_fields=["revoked_at", "revoked_by_user_id", "updated_at"])
        svc_accounts.audit_revoked(account, actor_user_id=getattr(request.user, "id", None))
    return Response(svc_accounts.wire(account))


urlpatterns = [
    # S44 — the report LIBRARY. Declared BEFORE `reports/<key>` and it cannot
    # shadow it: `reports` is an exact, segment-complete match and
    # `reports/<key>` needs a second segment. US-REP-001; see `report_library`
    # for why an index that no document contracts is served at all.
    path("reports", report_library),
    # 11b §1 line 32 + 13a rows S59/S60, verbatim. `<str:key>` and not a
    # regex over SERVED_KEYS on purpose: an unknown key must reach the VIEW so
    # it can be refused with the vocabulary attached, rather than falling
    # through the router into a bare 404 that says nothing.
    # ⚠ **ABOVE `reports/<key>`, AND THAT ORDERING IS LOAD-BEARING.** `datasets`
    # sits in the same URL position as a report key, so a catch-all declared
    # first would swallow it and a client asking for the registry would get a
    # 422 about a report named "datasets". It is the same fault `P0.11` ranks
    # `custom`, `dashboard`, `scheduled` and `history` above `{key}` for, one
    # segment along, and `P5.2` is what refuses the name at save.
    path("reports/datasets", report_datasets),
    # ── `P2.20` · BI tier 1 ───────────────────────────────────────────────
    # ⚠ ABOVE `reports/<key>` for the reason `datasets` is: `service-accounts`
    # sits in the same URL position as a report key, and a tenant may name a
    # report anything.
    path("reports/service-accounts", report_service_accounts),
    path("reports/service-accounts/<uuid:account_id>/revoke", report_service_account_revoke),
    # ── `CR-142-BRC07` `P3.1` · the run history ───────────────────────────
    # ⚠ **ABOVE `reports/<key>` FOR THE REASON `datasets` IS, AND THE FRONT END
    # ALREADY RESERVED THE WORD.** `history` is one of the four segments
    # `P0.8`/`P0.11` claimed in the router precisely because a tenant may name a
    # report *History*; this is the server half of the same claim.
    path("reports/history", report_runs),
    path("reports/history/<uuid:job_id>", report_run),
    # ── `CR-142-BRC07` `P5.1` · the definition CRUD ───────────────────────
    # ⚠ **ABOVE `reports/<key>`, FOR THE FOURTH TIME ON THIS LIST AND THE SAME
    # REASON.** `definitions` sits in the URL position a tenant-authored report
    # key occupies, so a catch-all declared first would swallow a POST to it.
    # The word is NOT one of `P5.2`'s four reserved names, and it does not need
    # to be: the four exist because a utility might plausibly call a report
    # *History*, and a report called *Definitions* is refused by the ordinary
    # key-collision path rather than by a reserved-word list that grows every
    # time a route is added.
    path("reports/definitions", report_definitions),
    path("reports/definitions/<uuid:definition_id>", report_definition),
    path("reports/<str:key>", report),
    # A11's own S7 row, verbatim: `GET /dashboard/summary`. Declared BEFORE
    # nothing and AFTER nothing that could swallow it — it is all-static and
    # shares no prefix with `reports/<key>`.
    path("dashboard/summary", dashboard_summary),
]

# ── `CR-142-BRC07` `P4.4` / `P4.5` · the schedules ──────────────────────────
# ⚠ **INSERTED ABOVE `reports/<key>` AND NOT APPENDED.** `schedules` sits in
# the same URL position as a report key, so a catch-all ahead of it would
# swallow the list and a client asking for it would get a 422 about a report
# named *schedules* — the same fault `datasets` and `history` are ranked above
# `{key}` for, and the same one `P0.11` claims four router segments against.
#
# ⚠ **AND THE ROUTES LIVE IN `schedules_api.py` RATHER THAN IN THIS FILE, FOR
# HARD-WON LAW 11'S REASON.** This module is 35 KB and several lanes edit it;
# a pathspec commit takes the WHOLE file, so the second lane to commit
# silently reverts the first (`DEF-165`). Phase 4 touches it in ONE place —
# this splice — instead of adding three hundred lines to the contested file.
#
# ⚠ **THE POSITION IS FOUND BY PATTERN STRING, NOT BY `list.index`.** The first
# draft of this splice read `urlpatterns.index(path("reports/<str:key>",
# report))`, which BUILDS A SECOND `URLPattern` and looks for it — and
# `URLPattern` defines no `__eq__`, so the comparison is by identity, never
# matches, and `.index` raises `ValueError` at import time. It would have taken
# the whole reports module down on the first request.
_CATCH_ALL = next(
    index
    for index, route in enumerate(urlpatterns)
    if str(getattr(route, "pattern", "")) == "reports/<str:key>"
)
urlpatterns[_CATCH_ALL:_CATCH_ALL] = SCHEDULE_URLS

# ── `CR-142-BRC07` `P4.11` · the Reports Dashboard tab ──────────────────────
# ⚠ **SPLICED ABOVE `reports/<key>` FOR THE REASON EVERY ROUTE ON THIS LIST IS,
# AND HERE IT IS NOT HYPOTHETICAL.** `dashboard` is one of `P0.8`/`P5.2`'s FOUR
# RESERVED SEGMENTS precisely because a utility might name a report *Dashboard*;
# a catch-all ahead of it would answer the tab with a 422 about a report of that
# name. The routes live in `dashboard_tab_api.py` for hard-won law 11's reason —
# this module is edited by several lanes a week, so Phase 4's dashboard touches
# it in these two lines and nowhere else.
#
# ⚠ **`_CATCH_ALL` IS RE-COMPUTED AND NOT REUSED.** The splice above INSERTED
# routes, so the index found before it is now several short of the catch-all and
# reusing it would put the dashboard among the schedules — which happens to work
# and would be wrong for the next reader, and stops working the moment the order
# of the two splices changes.
_DASHBOARD_AT = next(
    index
    for index, route in enumerate(urlpatterns)
    if str(getattr(route, "pattern", "")) == "reports/<str:key>"
)
urlpatterns[_DASHBOARD_AT:_DASHBOARD_AT] = DASHBOARD_TAB_URLS

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-009@33253a0 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md — US-LED-009 + US-LED-010 — · 04-docs/05-modules/12-reports/01-overview.md, which settles the ledger/reports ownership split this route straddles · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 line 32 + §2.10b · 04-docs/02-decisions/13a-screen-component-map.md rows S59/S60; co-packet US-LED-010, same five sources)
# generated: 2026-08-11 by story-coder (W5 ledger read-API lane — the viewer route S59 and S60 had no way to reach their read models through) · AMENDED 2026-08-16 by story-coder (DEF-129 lane — `GET /dashboard/summary` added for US-REP-019, A11's own S7 row, which was contracted and served by nothing)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)  [E was `deferred(no-frontend-half — 07-frontend/src/features/reports is a README; S59/S60 have no screen yet)` and that sentence stopped being true when AccountLedgerReportPage and ByPremisesReportPage landed on 2026-08-11; US-REP-019's DashboardPage.tsx lands in this commit. Hard-won law 1 — a stale trailer is a comment claiming a guarantee.]
# gates: [DEF-129 lane 2026-08-16] RED PROVED FIRST — `GET /api/brazosbend/dashboard/summary` answered `django.urls.exceptions.Resolver404` before this route existed; quoted verbatim in the lane report. ruff✔ black✔ pytest tests/test_us_rep_019_dashboard.py✔ run_gates✔ · [W5 lane] see the lane report — ruff✔ black✔ · pytest tests/test_us_led_ledger_api.py (RED-PROVED FIRST: django.urls.exceptions.Resolver404 on /api/brazosbend/reports/account_ledger — verbatim in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it)
# exceptions: (1) **THE `{key}` STRINGS ARE NOT CONTRACTED ANYWHERE** — A11 gives the path, 11b says which screens it serves, 13a maps screens to stories, and none names a key. `account_ledger` / `by_premises` are taken from the EXPORT FILENAME fixtures in US-LED-009 §4 and US-LED-010 §4, the only machine-readable slugs for these reports in a ratified document. REPORTED for ratification with the S44 catalog (US-REP-001) · (2) an unknown key is 422 VAL-005 enumerating the served keys, not a 404 — a 404 would make an unbuilt report indistinguishable from a typo and from another tenant's resource, which is the one thing HR-1 reserves 404 for · (3) S60 answers **200 with `available:false`** and the unattributed money on it (553.69 billed / 446.37 collected), because the request is valid and the report is real — only the premises dimension has never been written (US-LED-002 unbuilt) · (4) the A14 `premises` parameter is NOT accepted on S59: every journal line carries premises_id = NULL, so the param would filter nothing while making the report look filtered (US-LED-009 §8) · (5) no `POST /reports/{key}/export` and no IS-11 download — BR-REP-018's pipeline is sequenced behind the job runner (PO 2026-08-09) and there is no job runner on this deployment (TD-17) · (6) no other S44 library key is served and none is stubbed: they are the reports module's own stories, and a route answering 501 advertises a report that does not exist · (7) this module owns no tables and this file writes nothing — every figure is `apps.ledger.reporting`'s, reached through its published functions (B1 cross-module READ), never through ledger's models
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
