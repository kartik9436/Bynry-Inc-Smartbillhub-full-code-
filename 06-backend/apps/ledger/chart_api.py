# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (chart of accounts: seeded, tenant-customizable,
#           audit-locked in use — TC-2 a hand-added account, TC-3 the rename,
#           TC-4 deactivate-first, TC-5 the referenced row that never deletes) ·
#           US-LED-006 (export codes on the GL mapping page — qbo_ref /
#           xero_ref, TC-1 gaps render as visible empty states) ·
#           US-LED-017 (the cost-of-service chart section — TC-5: no surface
#           presents an unsigned code as finance-signed)
#           Screens: S56 · S73
# Rules:    BR-LED-014 (the GL mapping page, under Settings → Configure per the
#           PO ruling of 2026-08-12) · BR-LED-015 (every chart change audits) ·
#           BR-LED-037 (the cost section is PROPOSED and unsigned until a
#           finance re-sign via HUMAN-GUIDE §6) · BR-LED-038 (a tenant's own
#           pointer survives a re-seed) · BR-BIL-010 (service → revenue GL with
#           an optional usage/base split; the AR / deposit / clearing /
#           write-off designations) · BR-BIL-069 (one 2200-series account per
#           tax authority, minted because a human asked) · BR-REP-006 (filters
#           and pickers enumerate the LIVE vocabulary) · BR-SHL-011 (list
#           grammar q / f.<name>) · BR-TEN-013 (a module never touches another
#           module's ORM — the service pointer is read through the seam and
#           WRITTEN by tenancy's own endpoint) · BR-TEN-043 (event time is an
#           input; there is no clock in this file) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 4 (financial records never delete) · rule 7 (every
#           money action audits)
# Tests:    06-backend/tests/test_us_led_005_chart_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           apps/ledger/services.py (the write half this surface calls) ·
#           07-frontend/src/features/ledger/ChartOfAccountsPage.tsx (S56's
#           chart + mapping tab — the first and only caller) ·
#           06-backend/openapi/schema.json (BE-11 TC05 diffs the snapshot)
# ───────────────────────────────────────────────────────
"""The chart of accounts, and the GL map, as HTTP.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — every route below decides which GL account
a money line will land in, which is the 🔒 sensitive path CLAUDE.md names.
AI-authored 2026-08-16 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS
════════════════════════════════════════════════════════════════════════════
`apps/ledger/chart.py` holds twenty-four finance-signed accounts and twelve GL
designations. `apps/ledger/services.py` seeds them at provisioning and its own
docstring said, from the day it was written until 2026-08-16: *"WHAT IS NOT:
the S56 chart CRUD (US-LED-005's write half), and the GL mapping SCREEN."*
`apps/ledger/api.py` lists `GET /ledger/accounts`, `GET /ledger/gl-mappings`
and `PUT /ledger/gl-mappings` under **NOT SERVED**.

So the chart was **tenant-customizable by design and by nobody in practice**: a
utility that numbers receivables 1150 had a seeded 1200 and no way to change
it, and the eleven-then-twelve designations — the pointers the posting service
resolves every entry through — could be read by code and by no human at all.

════════════════════════════════════════════════════════════════════════════
WHAT IS SERVED, AND THE ONE WRITE THAT IS DELIBERATELY SOMEWHERE ELSE
════════════════════════════════════════════════════════════════════════════
    GET    /ledger/accounts                       the S56 chart panel
    POST   /ledger/accounts                       US-LED-005 TC-2, a typed row
    POST   /ledger/accounts/import                CR-008 Tab 1, a mapped file
    PATCH  /ledger/accounts/{id}                  code (System Admin) · name · designation · refs
    DELETE /ledger/accounts/{id}                  ONLY when unreferenced (IS-1)
    POST   /ledger/accounts/{id}/deactivate       IS-1 deactivate-first
    POST   /ledger/accounts/{id}/reactivate
    GET    /ledger/gl-mappings                    the whole map, in one read

**THE SERVICE → REVENUE POINTER IS NOT WRITTEN HERE, AND THAT IS B1.**
`tenant_services.revenue_account` is TENANCY's column (S8 Services card) and a
cross-module write is forbidden — `apps/ledger/tenancy_seam.py` says so in its
own exceptions block. `GET /ledger/gl-mappings` therefore READS it through the
seam and publishes, on the response, the endpoint that writes it
(`PATCH /settings/services/{code}`, `apps.tenancy.services.update_tenant_service`,
which has accepted `revenue_account` since the PO's OQ-115 ruling). The screen
calls that route for that one field. A `PUT /ledger/gl-mappings` that wrote both
sides would have been the shorter contract and an outright boundary violation.

**`PUT /ledger/gl-mappings` IS THEREFORE NOT SERVED AT ALL** (11b §2.10 names
it). Half of what it would write belongs to tenancy and the other half is a
designation on one chart row, which `PATCH /ledger/accounts/{id}` already
writes with an audit row naming the account that moved. A route that wrote one
half and delegated the other would leave a partial save with no transaction
around it. REPORTED rather than stubbed — a 501 is a promise.

════════════════════════════════════════════════════════════════════════════
THIS FILE COMPUTES NOTHING AND HOLDS NO ACCOUNT CODE
════════════════════════════════════════════════════════════════════════════
There is no arithmetic here, no ORM (G6 greps every `*_api.py` for a model
manager) and — the one that matters for this module — **no account NUMBER
anywhere in the file**. `chart.py`'s whole subject is that code reads the
DESIGNATION and never the number; an endpoint that special-cased `"1200"` would
be the exact latent misposting OQ-106 was raised to prevent. The only codes
that appear are ones a request carried in.

════════════════════════════════════════════════════════════════════════════
AN UNSIGNED ROW IS SERVED MARKED, NEVER HIDDEN (US-LED-017 TC-5)
════════════════════════════════════════════════════════════════════════════
⚠ **AMENDED 2026-08-18 — THE EIGHT ARE SIGNED NOW.** This section read *"THE
UNSIGNED EIGHT … `5100 Purchased power` … `5300 Infrastructure` are BR-LED-037's
PROPOSAL and carry no finance signature at all"*. The Product Owner — the
sign-off authority per their own ruling of 2026-08-11 — finance re-signed all
eight codes and names on 2026-08-18, together with 4180 Budget billing variance,
shown them in plain English with **no dollar figure attached to any of the
nine** and with B4/B5 ❄️ FROZEN and un-edited. So this endpoint serves them
`finance_signed: true`, and `pending_finance_re_sign_cost` comes back empty.

**The posture is unchanged for the next row.** Every account travels with
`finance_signed`, and an unsigned one also brings
`chart.COST_SECTION_RE_SIGN_SOURCE` — the named route the signature has to come
from. Filtering an unsigned row out of this list would hide an account that
exists; serving it unmarked would present a lane's proposal as law; and marking
a RATIFIED row is the same failure in the third direction, which is what
happened between the re-sign and the fix to `services._chart_row`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from typing import Any

from django.db import transaction
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ledger import chart, models, selectors, services, tenancy_seam
from apps.tenancy import selectors as tenancy_selectors
from apps.ledger import gl_mapping_save
from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole, SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant

#: The one route that writes a service's revenue pointer, published on the
#: mapping read so the screen does not have to know tenancy's URL grammar —
#: and so a reader of THIS file can see where the other half of the map lives.
SERVICE_MAPPING_WRITE_ROUTE = "PATCH /settings/services/{service_code}"

#: ⚠ **RETIRED 2026-09-02 — `PUT /ledger/gl-mappings` IS SERVED (CR-060 C10 /
#: T11).** This constant published the route as a named gap while it was
#: declined, and its reasoning — *"half of what it would write is tenancy's
#: `tenant_services.revenue_account` (a cross-module write, forbidden by B1)"* —
#: was right about the constraint and wrong about the conclusion: each half is
#: written by the module that owns it, so nothing crosses. It is kept, unused,
#: with this stamp rather than deleted, because a reader who finds the old
#: sentence quoted in `CR-060` or in a screen comment needs to be able to see
#: that it was answered and how (hard-won law 1's other direction — a file that
#: quietly stops describing its own former hole).
#:
#: **NOTHING READS IT.** `gl_mappings` no longer publishes it on the response;
#: a gate that finds it unreferenced is finding the truth.
UNSERVED_MAPPING_WRITE_RETIRED = {
    "code": "gl_mapping_bulk_write_is_not_served",
    "br_ref": "BR-LED-014",
    "wanted_read": (
        "11b §2.10 names PUT /ledger/gl-mappings. Half of what it would write is "
        "tenancy's tenant_services.revenue_account (a cross-module write, forbidden by B1) "
        "and half is ledger_accounts.designation, which PATCH /ledger/accounts/{id} already "
        "writes under its own audit row. The two halves are written by their owners."
    ),
}


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="ledger.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """WHO changed the chart, from the SESSION — never from the body.

    `audit_log.actor_user_id` is hard rule 7's evidence half (BR-LED-015 makes
    every chart change audited), so the one thing it must not be is client
    input.
    """
    return getattr(request, "user", None)


def _moment(payload: dict[str, Any], name: str = "at") -> datetime:
    """The instant a chart row was retired — an INPUT (BR-TEN-043, gate G6).

    There is no clock in this file. A double-submitted Deactivate must stamp ONE
    moment, and a server reading its own clock would stamp two and record two
    different histories of one act. Bare `YYYY-MM-DD` is anchored at UTC, which
    is the shape a date field collects; WHICH instant a typed calendar date
    should become in a tenant's own zone is **OQ-153** and is not answered here.
    """
    raw = payload.get(name)
    if raw is None or str(raw).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.chart.moment_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    text = str(raw).strip()
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.combine(date.fromisoformat(text), datetime.min.time())
        except (TypeError, ValueError) as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="ledger.report.date_invalid",
                field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
            ) from problem
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_timezone.utc)
    return moment


def _account_dict(row: dict[str, Any]) -> dict[str, Any]:
    """One chart row on the wire. `created_at` is the only value to convert."""
    created = row.get("created_at")
    return {
        **row,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
    }


# ═══════════════════════════════════════════════════════════════════════════
# GET / POST /ledger/accounts — the S56 chart panel and its Add
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # the WRITE re-gates below; A4 gives every role R
def accounts(request: Any) -> Response:
    """EP-LED-02's capability row, served — and US-LED-005 TC-2's Add.

    **NOT PAGINATED.** The row count is the tenant's CHART — the twenty-four
    seeded rows plus its own additions plus one per tax authority — and it does
    not grow with transaction volume. The Type filter and the designation
    picker on the screen are both derived from the whole list, so a page would
    make each of them a claim about a page.

    `with_references=1` adds the per-kind reference counts every row's Delete
    control needs. It is OPT-IN because it is N queries over the journal, and a
    screen that only draws the table does not pay for them.
    """
    require_tenant(request)
    if request.method == "POST":
        # A4 gives Executive full on Finance, but a chart edit is a System
        # Admin / Billing Clerk act by BR-LED-015's own audit posture and by the
        # service-layer gate, which refuses whatever this class allows.
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-LED-015")
        body = _payload(request)
        created = services.create_account(
            _actor(request),
            code=body.get("code"),
            name=body.get("name"),
            type=body.get("type"),
            designation=body.get("designation"),
            # CR-061 statement (1) — OPTIONAL. A body that names no heading
            # creates an uncategorised account, which is lawful and is what a
            # tenant's own hand-added row carries until somebody files it.
            category=body.get("category"),
        )
        return Response(_account_dict(created), status=201)

    params = request.query_params
    result = services.chart_of_accounts(
        search=params.get("q") or None,
        account_type=params.get("f.type") or None,
        # BR-SHL-011's `f.<name>` grammar. `f.category=none` is the
        # UNCATEGORISED group and is a real value: on any database provisioned
        # before 2026-09-02 it is the ONLY group, because nothing backfills.
        category=params.get("f.category") or None,
        status=params.get("f.status") or None,
        # DEF-LED-6715 / blueprint p025 note 3 — the ROLE filter, drawn on p024
        # and marked NOT SERVED on p025 ("the gap"). `f.designation=none` is
        # the rows carrying no role; `needs-account` is a question about ROLES
        # and is answered by `roles_needing_account` below, not by rows.
        designation=params.get("f.designation") or None,
        with_references=str(params.get("with_references") or "").strip() in {"1", "true", "yes"},
    )
    return Response(
        {
            "rows": [_account_dict(row) for row in result["rows"]],
            "types": list(result["types"]),
            # CR-061 statement (1) — the eighteen headings, published rather
            # than hardcoded on the screen (BR-REP-006), for the same reason the
            # pending registers below are: a screen carrying its own copy would
            # disagree with `chart.py` the first time one is added.
            "categories": list(result["categories"]),
            "designations": list(result["designations"]),
            # DEF-LED-6715 — the GL roles with NO live account. Published
            # rather than derived on the screen, for the reason every register
            # beside it is: a screen that worked this out from its own rows
            # could not, because an unfilled role HAS no row. See
            # `services.chart_of_accounts` for why it is a warning and not a
            # vocabulary.
            "roles_needing_account": list(result["roles_needing_account"]),
            # US-LED-017 TC-5 — which codes await a finance signature, and the
            # named route it has to come through. Published rather than left to
            # the screen: a screen that hardcoded the list would disagree with
            # chart.py the first time finance re-signs one (hard-won law 1).
            "pending_finance_re_sign": list(result["pending_finance_re_sign"]),
            "pending_finance_re_sign_cost": list(result["pending_finance_re_sign_cost"]),
            # US-LED-017 TC-5 again, for CR-061's 67 utility-books accounts: a
            # third register, published beside the other two so no surface can
            # present one of them as finance-signed.
            "pending_finance_re_sign_books": list(result["pending_finance_re_sign_books"]),
            "cost_section_source": result["cost_section_source"],
            "utility_books_source": result["utility_books_source"],
            "currency": tenancy_selectors.regional_settings().get("currency"),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# PATCH / DELETE /ledger/accounts/{id}
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def account_item(request: Any, account_id: str) -> Response:
    """One chart row: read it, edit it, or remove it if nothing points at it.

    ⚠ **PATCH ACCEPTS FIVE FIELDS SINCE 2026-10-29 — `code` JOINED THE FOUR
    (`CR-196-BRC10`).** It read *"PATCH accepts FOUR fields and refuses every
    other, including `code` and `type`"*. The PO ruled, verbatim: *"in many
    cases utilities are giving there own GL codes; which means we have to
    ability to change existing GL code as per the given utility for that
    specific tenant; even if they are used"*. So `code` is accepted — for a
    **System Admin only** (Q4 A; a clerk is refused BY NAME by
    `services.change_account_code`, and nothing else in the same request lands)
    — and applies everywhere at once because everything holds the account's id.
    **`type` is still refused** with `field_not_editable` (Q3 A).

    ⚠ **ONE TRANSACTION FOR THE WHOLE PATCH.** A code change and a rename in one
    request either both land or neither does: a refusal raised inside the block
    rolls it back and is NOT caught, so hard-won law 14's aborted-transaction
    trap cannot arise here.

    **GET carries `usage`** — `services.account_code_usage`, the counts and the
    closed/exported month the code-change confirmation shows (PO (2) and Q2).

    **DELETE is IS-1's hard delete and refuses unless the row is unreferenced
    AND every reference kind was readable.** Two of the four kinds are other
    modules' reads that publish no reverse lookup, so the answer is *"I cannot
    tell"* rather than zero, and this route refuses on that alone. Deactivate is
    always available and loses nothing.
    """
    require_tenant(request)
    if request.method == "GET":
        references = services.account_references(account_id)
        rows = services.chart_of_accounts()["rows"]
        row = next((item for item in rows if item["account_id"] == str(account_id)), None)
        if row is None:
            raise errors.NotFoundError()
        return Response(
            {
                **_account_dict(row),
                "references": references,
                # CR-196-BRC10 — what a code change would touch.
                "usage": services.account_code_usage(account_id),
            }
        )

    if not AdminOrClerk().has_permission(request, None):
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-LED-015")

    if request.method == "DELETE":
        return Response(services.delete_account(_actor(request), account_id=account_id))

    body = _payload(request)
    unknown = set(body) - {"code", "name", "designation", "qbo_ref", "xero_ref"}
    if unknown:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.chart.field_not_editable",
            params={"fields": ", ".join(sorted(unknown))},
            field_errors=[{"field": field, "code": errors.VAL_FORMAT} for field in sorted(unknown)],
        )

    row: dict[str, Any] | None = None
    with transaction.atomic():
        if "code" in body:
            # CR-196-BRC10 — FIRST, so a clerk's request is refused before
            # anything else in it is written (and the block rolls back anyway).
            services.change_account_code(_actor(request), account_id=account_id, code=body["code"])
        if "name" in body or "designation" in body:
            row = services.update_account(
                _actor(request),
                account_id=account_id,
                **({"name": body["name"]} if "name" in body else {}),
                **({"designation": body["designation"]} if "designation" in body else {}),
            )
        if "qbo_ref" in body or "xero_ref" in body:
            # US-LED-006's write. Deliberately the SAME request as the rename:
            # the mapping page edits a row, and two round trips for one row
            # would leave a half-saved line if the second failed.
            services.set_export_codes(
                _actor(request),
                account_id=account_id,
                **({"qbo_ref": body["qbo_ref"]} if "qbo_ref" in body else {}),
                **({"xero_ref": body["xero_ref"]} if "xero_ref" in body else {}),
            )
    rows = services.chart_of_accounts()["rows"]
    row = next((item for item in rows if item["account_id"] == str(account_id)), None)
    if row is None:
        raise errors.NotFoundError()
    return Response(_account_dict(row))


# ═══════════════════════════════════════════════════════════════════════════
# POST /ledger/accounts/import — CR-008 Tab 1's "↑ Import CSV"
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def accounts_import(request: Any) -> Response:
    """Validate a mapped chart file, and load it only when asked to.

        {"rows": [{"code": "1150", "name": "Trade debtors", "type": "asset"}],
         "commit": false}

    **The CSV never reaches this endpoint as a file, and that is deliberate.**
    r10's flow is *upload → map columns → validate → load*: the mapping step is
    the screen's — a person looking at their own spreadsheet's headers and
    saying which column is the code — so the server takes ROWS that have
    already been mapped. Parsing a file here would mean this endpoint guessing
    which column was which, which is the step the CR gives to a human.

    `commit: false` (the default) writes NOTHING and returns the full per-row
    report the preview table draws. `commit: true` refuses outright if any row
    is invalid or duplicated in the file — see `services.import_accounts` for
    why an all-or-nothing load is the usable one.

    **System Admin, per CR-008 #4** — the PO's ruling for the whole Accounting
    screen. `SettingsReadAnyWriteSystemAdmin` allows any tenant role to READ
    and only a System Admin to write, and this route is a write.
    """
    require_tenant(request)
    body = _payload(request)
    return Response(
        services.import_accounts(
            _actor(request),
            rows=body.get("rows") or [],
            commit=bool(body.get("commit")),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_deactivate(request: Any, account_id: str) -> Response:
    """IS-1 deactivate-first. `at` is REQUIRED (BR-TEN-043 — see `_moment`)."""
    require_tenant(request)
    body = _payload(request)
    return Response(
        _account_dict(
            services.set_account_active(
                _actor(request), account_id=account_id, active=False, at=_moment(body)
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def account_reactivate(request: Any, account_id: str) -> Response:
    """The other direction. `at` is read and ignored for the value — the row is
    cleared, not stamped — but is still REQUIRED, so both controls send the same
    body and neither is the one that "does not need a date"."""
    require_tenant(request)
    body = _payload(request)
    _moment(body)
    return Response(
        _account_dict(
            services.set_account_active(
                _actor(request), account_id=account_id, active=True, at=None
            )
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# GET /ledger/gl-mappings — the whole map, in one read
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def gl_mappings(request: Any) -> Response:
    """BR-LED-014's page — and, since **CR-060 C10 / T11**, the ONE SAVE behind it.

    ⚠ **`PUT` IS SERVED HERE, ON THE PATH 11b §2.10 NAMES, AND IT USED TO BE
    DECLINED.** The reason published on this read said so in terms: *"Half of
    what it would write is tenancy's `tenant_services.revenue_account` (a
    cross-module write, forbidden by B1)."* **That was right about the
    constraint and wrong about the conclusion.** The write goes through the
    module that OWNS each column — the ledger writes `ledger_accounts.
    designation`, tenancy writes its own row through a published callable — so
    there is no cross-module write anywhere on the path. `UNSERVED_MAPPING_WRITE`
    is RETIRED with this change rather than reworded, because it describes a
    limit that no longer holds (hard-won law 1).

    ⚠ **ONE VIEW AND NOT TWO, because Django dispatches on the PATH.** A second
    `path("ledger/gl-mappings", …)` entry would never be reached: the first
    match wins and the read view would answer the PUT with a 405, which is a
    route that looks served and is not.

    **THE PERMISSION IS PER METHOD AND THE CLASS IS THE ONE THAT DOES THAT.**
    `SettingsReadAnyWriteSystemAdmin` — any tenant role may READ this map, only
    a System Admin may change it, which is the posture the whole Accounting tab
    already has. It was `AnyTenantRole` while this was read-only; widening the
    method without narrowing the write is DEF-196's shape in reverse.

    ── THE READ ────────────────────────────────────────────────────────────

    Four sections, and every one of them is the LIVE pointer rather than the
    seed's default (BR-LED-038 / PO 2026-08-11: *"you create an account, but
    allow tenant user to override it"*):

      * **designations** — the twelve of `chart.GL_DESIGNATIONS`, each resolved
        through `apps.ledger.selectors.designation_map()`. A `null` account is a
        REAL and reportable state: `budget_variance` has no seeded home at all
        (its account is an addition to ❄️ frozen B5 line 74 awaiting a finance
        re-sign), and a designation whose account was deactivated resolves to
        nothing until another row claims it.
      * **services** — the tenant's enabled services with their revenue and base
        pointers, read through the seam. When the seam is unwired the section is
        served ABSENT WITH ITS REASON, never as an empty list: "this tenant sells
        nothing" and "the ledger cannot see tenancy" have the same shape, and an
        empty list would render a mapping page that looks complete.
      * **tax_authorities** — every live 2200-series account. B5 line 74 seeds
        none of them (*"tenant authorities mint their own"*), so an empty
        section here means this tenant has entered no authority, which is a
        different fact from a gap and is labelled as one.
      * **export_codes** — US-LED-006's QBO/Xero refs with their gaps, straight
        from `services.export_code_map()`.
    """
    require_tenant(request)
    if request.method == "PUT":
        # ALL OF IT OR NONE OF IT — `save_gl_mappings` opens the one transaction
        # over both halves, and C10's proof ("a partial failure writes NOTHING")
        # is asserted on a real PostgreSQL because SQLite has no
        # aborted-transaction state and would pass a broken version green
        # (hard-won law 14).
        return Response(gl_mapping_save.save_gl_mappings(_actor(request), _payload(request)))
    designation_map = selectors.designation_map()
    live_rows = {
        row["account_id"]: row for row in services.chart_of_accounts(status="active")["rows"]
    }

    designations = []
    for name in chart.GL_DESIGNATIONS:
        account_id = designation_map.get(name)
        account = live_rows.get(str(account_id)) if account_id else None
        designations.append(
            {
                "designation": name,
                "account_id": str(account_id) if account_id else None,
                "code": account["code"] if account else None,
                "name": account["name"] if account else None,
                "type": account["type"] if account else None,
                # Two pending states share one honest flag (amended 2026-08-18,
                # CR-010 B-8): `chart.PENDING_FINANCE_RESIGN` names a designation
                # with NO seeded account at all (empty since 4180 landed), and
                # `chart.PENDING_FINANCE_RE_SIGN` names a seeded CODE finance has
                # not re-signed yet. Served so the page can say WHY a row is
                # empty or provisionally coded, instead of drawing a gap that
                # looks like a configuration mistake somebody should fix.
                #
                # ⚠ **BOTH ARE EMPTY SINCE LATER THE SAME DAY.** This comment
                # said the second holds "today exactly 4180 Budget billing
                # variance … awaiting HUMAN-GUIDE §6"; the PO finance re-signed
                # 4180 on 2026-08-18 (its code and name, with the eight cost
                # accounts, no figure attached), so every designation now comes
                # back `awaiting_finance_re_sign: false`. The union stays,
                # because the two states are different questions and the next
                # row to need one of them must still be reported.
                "awaiting_finance_re_sign": (
                    name in chart.PENDING_FINANCE_RESIGN
                    or (account is not None and account["code"] in chart.PENDING_FINANCE_RE_SIGN)
                ),
            }
        )

    services_section: dict[str, Any]
    try:
        codes = tenancy_seam.enabled_service_codes()
        rows = []
        for code in codes:
            attributes = tenancy_seam.service_gl_attributes(code) or {}
            revenue_id = attributes.get("revenue_account_id")
            base_id = attributes.get("base_revenue_account_id")
            revenue = live_rows.get(str(revenue_id)) if revenue_id else None
            base = live_rows.get(str(base_id)) if base_id else None
            rows.append(
                {
                    "service_code": code,
                    "revenue_account_id": str(revenue_id) if revenue_id else None,
                    "revenue_code": revenue["code"] if revenue else None,
                    "revenue_name": revenue["name"] if revenue else None,
                    "base_revenue_account_id": str(base_id) if base_id else None,
                    "base_revenue_code": base["code"] if base else None,
                    "base_revenue_name": base["name"] if base else None,
                    # BR-BIL-010: a bill whose line cannot resolve a GL fails
                    # ATOMICALLY at issue. A service with no revenue account is
                    # therefore not a cosmetic gap and the page says so.
                    "blocks_issue": revenue is None,
                }
            )
        services_section = {
            "available": True,
            "rows": rows,
            "write_route": SERVICE_MAPPING_WRITE_ROUTE,
        }
    except tenancy_seam.LedgerSeamNotWired as unwired:
        services_section = {
            "available": False,
            "rows": [],
            "write_route": SERVICE_MAPPING_WRITE_ROUTE,
            "reason": {
                "code": "service_gl_attributes_seam_is_not_wired",
                "br_ref": "BR-TEN-013",
                "wanted_read": str(unwired),
            },
        }

    # CR-196-BRC10 5b — by id, from the code OR the minted slot, so a renamed
    # authority stays in the tax section; the slot itself never leaves the server.
    tax_ids = services.tax_payable_account_ids()
    tax_authorities = [row for row in live_rows.values() if row["account_id"] in tax_ids]
    export_codes = services.export_code_map()

    return Response(
        {
            "designations": designations,
            "services": services_section,
            "tax_authorities": {
                "series": chart.TAX_PAYABLE_SERIES,
                "rows": [_account_dict(row) for row in tax_authorities],
            },
            "export_codes": {
                "rows": [dict(row, gaps=list(row["gaps"])) for row in export_codes["rows"]],
                "missing": {key: list(value) for key, value in export_codes["missing"].items()},
            },
            "unavailable": [],
        }
    )


urlpatterns = [
    # None of these collides with a path `apps/ledger/api.py` or
    # `apps/ledger/finance_api.py` already registers, which matters more here
    # than it reads: Django resolves by URL and NOT by method, so registering
    # `ledger/journal-entries` twice would shadow a GET with a POST-only view.
    path("ledger/accounts", accounts),
    # BEFORE the <uuid:...> item route is not required (Django matches by
    # converter, and "import" is not a uuid) but it reads as the collection
    # act it is: an import is about the CHART, not about one account.
    path("ledger/accounts/import", accounts_import),
    path("ledger/accounts/<uuid:account_id>", account_item),
    path("ledger/accounts/<uuid:account_id>/deactivate", account_deactivate),
    path("ledger/accounts/<uuid:account_id>/reactivate", account_reactivate),
    path("ledger/gl-mappings", gl_mappings),
]

# `models` is imported for the module's own type vocabulary through
# `services.chart_account_types()`; the reference keeps the dependency visible
# to a reader even though no manager is touched here (G6 forbids the manager,
# not the import).
_TYPE_VOCABULARY = models.LEDGER_ACCOUNT_TYPES

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@e85081b (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md — US-LED-005 + US-LED-006 — · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.10 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md — US-LED-017 TC-5; co-packets US-LED-006/US-LED-017, same four sources)
# generated: 2026-08-16 by story-coder (the ledger surface lane — the chart of accounts and its GL map were tenant-customizable by design and reachable by nobody)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, row in 12-governance/09-human-review-ledger.md)
# gates: RED PROVED FIRST — every path below answered `django.urls.exceptions.Resolver404` before this file was included; verbatim in the lane report. pytest tests/test_us_led_005_chart_api.py · ruff · black · run_gates
# exceptions: (1) **`PUT /ledger/gl-mappings` IS NAMED BY 11b §2.10 AND IS NOT SERVED** — half of what it would write is tenancy's `tenant_services.revenue_account` (a cross-module write, forbidden by B1/BR-TEN-013) and half is `ledger_accounts.designation`, which `PATCH /ledger/accounts/{id}` writes under its own audit row. Not stubbed (a 501 is a promise); the read publishes the gap by name and names the route that writes the other half · (2) PATCH does NOT accept `type`: US-LED-005 freezes it once the row is posted against. ⚠ AMENDED 2026-10-29 (`CR-196-BRC10`, PO: *"we have to ability to change existing GL code … even if they are used"*): `code` IS accepted, for a System Admin only, even on a used account — it read "PATCH does NOT accept `code` or `type` … A renumber is a new account plus a designation re-point — two acts, two audit rows" · (3) DELETE refuses when ANY reference kind is unreadable, not only when a reference exists: `charges.gl_account` (BR-BIL-010) and the tax-authority pointer (BR-BIL-069) publish no reverse lookup, so the honest answer is "I cannot tell" and deleting on it would be DEF-127's shape · (4) the chart list is NOT paginated — it is bounded by the tenant's chart, not by transaction volume, and the Type filter and designation picker are derived from the whole of it · (5) `with_references` is OPT-IN: it is N queries over `journal_lines` and a screen that only draws the table does not pay for them · (6) an unsigned account is served MARKED `finance_signed: false` with `COST_SECTION_RE_SIGN_SOURCE`, never filtered out — hiding a real account and presenting a proposal as law are both failures, in opposite directions (US-LED-017 TC-5). ⚠ AMENDED 2026-08-18: this clause named "the eight 5xxx cost accounts" as the marked set; the PO finance re-signed all eight (and 4180) that day, so the set is EMPTY and every seeded row is served `finance_signed: true`. Serving a ratified row as unsigned is the third direction of the same failure and it happened — `services._chart_row` was reading cost-section membership instead of the signature; fixed the same day, held by `test_us_led_017_tc5__the_cost_accounts_are_served_SIGNED_and_the_flag_still_discriminates`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
