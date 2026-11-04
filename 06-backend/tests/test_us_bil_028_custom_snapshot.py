# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-028 (stamp the custom-field snapshot onto the invoice at
#           issue)   Screens: S30 · S31 (nothing displays it in R2)
# Rules:    BR-BIL-030 (the bill is LOCKED — the document instance is stamped
#           and a reprint renders it forever, joining nothing live) ·
#           BR-BIL-004 (an issued invoice is immutable) · BR-TEN-046 (custom
#           fields are tenant-defined data with RLS FORCE) · BR-TEN-048 (a
#           custom field can never influence money) · BR-TEN-050 (deactivate
#           excludes from new snapshots; values survive) · CLAUDE.md rule 1
# Note:     TC-10 and the immutability case carry @pytest.mark.isolation and
#           SKIP with a vendor reason off Postgres — sqlite has neither RLS nor
#           triggers, so a green run there would prove nothing. Both were proved
#           RED against the live cluster before being trusted (hard-won law 7);
#           transcripts in 12-governance/09-human-review-ledger.md.
# ───────────────────────────────────────────────────────
"""The R2 one-way door, asserted from both sides.

Most of this file is about a feature NOTHING READS YET. That is the point, and
it is B12 r7.2's point: *"You cannot retroactively reconstruct what an account
looked like six months ago… Stamp early, render later."* The tests that matter
most here are therefore the two that would go green by accident —

  * `tc12` proves the stamp is WIRED. A `custom_snapshot.py` that is perfect and
    that `assemble_document` never calls produces `{}` on every invoice, passes
    every other test in this file, and loses exactly as much data as having no
    column at all. Hard-won law 2, in the one place where the damage is
    permanent.
  * `tc2` proves the stamp does not MOVE. A snapshot that quietly re-reads live
    master data satisfies DB-4 to the letter — no UPDATE is ever issued — while
    rewriting last January's bill from this March's data.

The fail-closed case (`tc11`) is the OQ-076 ruling in test form: the PO said
*"Dont put SSN on invoices"* and confirmed the mechanism INVERTED, so a field
that nobody marked document-safe must never appear. The failure mode it guards
is a Social Security number frozen into an append-only table that BR-TEN-044's
day-91 deletion cannot reach.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.db import (
    DatabaseError,
    IntegrityError,
    InternalError,
    ProgrammingError,
    connection,
    transaction,
)

from apps.billing import custom_snapshot, documents, models
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from apps.billing.stages import assemble_document as stage6
from apps.tenancy import models as tenancy_models

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_bil_005_issue import (
    TEMPLATE_ID as DOC_TEMPLATE_ID,
    TEMPLATE_VERSION as DOC_TEMPLATE_VERSION,
    a_priced_draft,
)
from tests.test_us_bil_029_assemble import assemble, billing_data
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

ISSUED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=timezone.utc)


def a_definition(tenant, *, entity="accounts", key="service_class", data_type="text", **overrides):
    """One `custom_field` row.

    Written straight through the ORM and NOT through a service, because the
    definition-write service is US-TEN-015 in the tenancy lane and does not
    exist — the registry table lands ahead of its S8 UI precisely because the
    invoice stamp cannot read a table that is not there (B12 r7.2). Stated here
    so nobody reads this helper as evidence the write path is built.
    """
    values = dict(
        tenant=tenant,
        entity=entity,
        key=key,
        label=key.replace("_", " ").title(),
        data_type=data_type,
        is_active=True,
        # OQ-076, PO 2026-08-10, mechanism INVERTED: nothing is stamped unless
        # the tenant explicitly says so. The tests that want a stamp must ask
        # for it, exactly as a tenant would have to.
        is_document_safe=True,
    )
    values.update(overrides)
    return tenancy_models.CustomField.objects.create(**values)


def a_water_account(actor, tenant, *, account_no="LSR-ACC-0003"):
    """The isolation tenant's account. Water only — Lone Star Ridge has no
    Electric service enabled, so `an_account`'s electric premises is refused
    there (`metering.service_not_enabled`), which is the fixture family working
    as intended rather than an obstacle to route around."""
    from apps.customers import models as customer_models

    premises = make_premises(  # noqa: F405 — shared fixture helper
        actor, address_line="700 Ranch Rd", services_available=["water"]
    )
    unit = make_unit(  # noqa: F405 — shared fixture helper
        actor, premises["id"], label="Unit A", services=["water"]
    )
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def set_account_values(account, values):
    """Write `accounts.custom_data` directly — the capture UI is EP-SHL-07."""
    account.custom_data = values
    account.save(update_fields=["custom_data", "updated_at"])


def set_premises_values(account, values):
    from apps.metering import models as metering_models

    unit = metering_models.Unit.objects.get(pk=account.unit_id)
    premises = metering_models.Premises.objects.get(pk=unit.premises_id)
    premises.custom_data = values
    premises.save(update_fields=["custom_data", "updated_at"])


def draft_for(tenant, account, run):
    return assemble(tenant, account, run, billing_data(account))


# ── TC-1 · the stamp itself ─────────────────────────────────────────────────
def test_us_bil_028_tc1__the_bill_stamps_the_accounts_custom_field_value(brazos, dana):
    """US-BIL-028 TC-1 — `{"accounts.service_class": "Commercial"}`.

    The key grammar is `<entity>.<key>` (B2 r17.3) and the value is a STRING.
    Both are asserted rather than just the presence of the key: the grammar is
    the contract R3's template variables (`{{account.custom.<key>}}`) are
    written against, and "strings only" is the structural half of BR-TEN-048.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(account, {"service_class": "Commercial"})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {"accounts.service_class": "Commercial"}
        assert all(isinstance(v, str) for v in invoice.custom_snapshot.values())


def test_us_bil_028_tc1b__the_property_entities_stamp_under_their_own_keys(brazos, dana):
    """§4's other half — premises `easement_ref = "ESM-77"` on the same bill.

    `accounts` → `units` → `premises` is the invoice's own path and every hop is
    single-valued, which is what makes a FLAT key space well-defined for these
    three. The other five r17.2 entities are multi-row and are OQ-118.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        a_definition(brazos, entity="premises", key="easement_ref")
        set_account_values(account, {"service_class": "Commercial"})
        set_premises_values(account, {"easement_ref": "ESM-77"})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {
            "accounts.service_class": "Commercial",
            "premises.easement_ref": "ESM-77",
        }


def test_us_bil_028_tc1c__the_five_multi_row_entities_are_not_reached_oq_118(brazos, dana):
    """OQ-118 pinned as a test, so the gap cannot be quietly assumed handled.

    `contacts`, `addresses`, `service_agreements`, `service_points` and `assets`
    each have their r17.2 STORAGE built and are deliberately not read by the
    stamp: an account holds several of each and `<entity>.<key>` has room for
    one. If a later lane starts stamping them without a ruling, this goes RED
    and sends them to the open question instead of to a guess.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos, entity="assets", key="feeder_number")
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {}
        assert set(custom_snapshot.UNREACHED_ENTITIES) == {
            "contacts",
            "addresses",
            "service_agreements",
            "service_points",
            "assets",
        }


# ── TC-2 · the whole reason the column exists ───────────────────────────────
def test_us_bil_028_tc2__editing_master_data_after_issue_does_not_move_the_bill(brazos, dana):
    """US-BIL-028 TC-2 — the one-way door, from the inside.

    Change `service_class` to "Irrigation" AFTER the bill is issued and re-read
    it: the snapshot still says "Commercial". This is the failure a live join
    would produce and no immutability check would catch — no UPDATE is ever run
    on the invoice, and last January's bill silently renders from this March's
    data (B2 r17.3: satisfying the letter of DB-4 while breaking it in
    substance).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(account, {"service_class": "Commercial"})
        invoice = draft_for(brazos, account, a_run(brazos))
        models.Invoice.objects.filter(pk=invoice.pk).update(
            status=models.INVOICE_ISSUED, issued_at=ISSUED_AT
        )

        set_account_values(account, {"service_class": "Irrigation"})

        reread = models.Invoice.objects.get(pk=invoice.pk)
        assert reread.custom_snapshot == {"accounts.service_class": "Commercial"}
        assert account.custom_data == {"service_class": "Irrigation"}


# ── TC-3 / TC-4 · the four types the APPLICATION formats (OQ-125 CLOSED) ────
# PO 2026-08-12, verbatim: *"in remark or note section on bill - applicationd
# eicde the format for time being"*. These four used to raise
# `NotImplementedError("OQ-125")`; they now stamp, in a format this application
# chose under a TEMPORARY grant. Each case therefore asserts the EXACT string,
# because that string is frozen into an append-only row and because the day the
# grant is withdrawn, a tenant-controlled format has to be a visible diff here
# rather than a quiet change of what bills print.
def test_us_bil_028_tc3__a_number_field_stamps_ungrouped_under_the_po_grant(brazos, dana):
    """US-BIL-028 TC-3 — `1234` → `"1234"`, and `10432` is NOT `"10,432"`.

    OQ-125 named the tension the registry cannot resolve: *"a meter multiplier
    typed as `1.5` and a co-op member number typed as `10432` want opposite
    answers"*. The application's answer under the PO's grant is ONE rule that
    is right for both — print the figure the tenant typed, no thousands
    grouping, no forced decimals — because grouping an identifier is wrong and
    nothing in the definition says which kind of number this is.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos, key="co_op_member_no", data_type="number")
        a_definition(brazos, key="meter_multiplier", data_type="number")
        set_account_values(account, {"co_op_member_no": 10432, "meter_multiplier": 1.5})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {
            "accounts.co_op_member_no": "10432",
            "accounts.meter_multiplier": "1.5",
        }
        assert "," not in invoice.custom_snapshot["accounts.co_op_member_no"]
        assert all(isinstance(v, str) for v in invoice.custom_snapshot.values())


def test_us_bil_028_tc4__a_date_field_stamps_iso_8601_under_the_po_grant(brazos, dana):
    """US-BIL-028 TC-4 — `2026-03-04` stamps `"2026-03-04"`, not `"03/04/2026"`.

    `tenant_settings.date_format` is still a stored CHOICE with no renderer
    behind it (that half of OQ-125 did not become false), so the application
    picks — and it picks the one format that cannot be read as a different day:
    `03/04/2026` is 4 March in Madrid and 3 April in Houston, and the string is
    frozen into an append-only row where nobody can ever correct the reader's
    guess. ISO 8601 is the same day in all eleven r17.4 locales.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos, key="easement_signed", data_type="date")
        set_account_values(account, {"easement_signed": "2026-03-04"})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {"accounts.easement_signed": "2026-03-04"}


def test_us_bil_028_tc4e__a_boolean_field_stamps_yes_or_no_under_the_po_grant(brazos, dana):
    """`True` → `"Yes"`, `False` → `"No"` — and this one is ENGLISH.

    OQ-125 asked *"in which of the eleven r17.4 locales, given the bill may be
    Spanish?"* and the grant does not answer it — it lets the application ship
    something while nobody has. Asserted as the literal words so that the day a
    Spanish bill needs `Sí`/`No`, it is a failing test and a new question, not a
    silent divergence between two tenants' invoices.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos, key="autopay_enrolled", data_type="boolean")
        a_definition(brazos, key="paperless", data_type="boolean")
        set_account_values(account, {"autopay_enrolled": True, "paperless": False})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {
            "accounts.autopay_enrolled": "Yes",
            "accounts.paperless": "No",
        }


def test_us_bil_028_tc4f__a_multi_select_field_joins_the_tenants_own_options(brazos, dana):
    """`["Dog on site", "Locked gate"]` → `"Dog on site, Locked gate"`.

    The separator is the application's, the ORDER is the tenant's: the stored
    order is kept rather than sorted, because sorting would be a second choice
    nobody asked for and it would reorder a hazard note the clerk typed
    deliberately.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(
            brazos,
            key="site_hazards",
            data_type="multi_select",
            options=["Dog on site", "Locked gate", "Steep drive"],
        )
        set_account_values(account, {"site_hazards": ["Locked gate", "Dog on site"]})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {"accounts.site_hazards": "Locked gate, Dog on site"}


def test_us_bil_028_tc4b__all_six_data_types_stamp_and_the_grant_is_named(brazos, dana):
    """No data type raises any more. Asserted as a SET, and so is the grant.

    `STRING_DATA_TYPES` stamp the tenant's own string; `FORMATTED_DATA_TYPES`
    are the four the APPLICATION renders under the PO's 2026-08-12 grant. The
    two sets still have to cover all six r17.1 types — a seventh type added to
    the registry with no rendering behind it must land here as a failure rather
    than as a refused bill in production.
    """
    assert set(custom_snapshot.STRING_DATA_TYPES) == {"text", "select"}
    assert set(custom_snapshot.FORMATTED_DATA_TYPES) == {
        "number",
        "date",
        "boolean",
        "multi_select",
    }
    assert set(custom_snapshot.STRING_DATA_TYPES) | set(
        custom_snapshot.FORMATTED_DATA_TYPES
    ) == set(tenancy_models.CUSTOM_FIELD_DATA_TYPES)
    # The grant is TEMPORARY and the code has to say so where a reader looks
    # for the format, not only in a docstring paragraph.
    assert custom_snapshot.APPLICATION_FORMAT_GRANT_IS_TEMPORARY is True
    assert custom_snapshot.BOOLEAN_TEXT == {True: "Yes", False: "No"}
    assert custom_snapshot.MULTI_SELECT_SEPARATOR == ", "


def test_us_bil_028_tc4g__a_value_that_contradicts_its_declared_type_is_still_refused(brazos, dana):
    """The grant covers FORMATTING, not coercion — proved on each of the four.

    A `number` holding `"abc"`, a `date` holding `"the 4th"`, a `boolean`
    holding `"yes"` and a `multi_select` holding a bare string are each refused
    by name. The PO chose how a number PRINTS; nobody said a bill may invent
    one, and `str()` here would freeze a nonsense string onto a row that can
    never be corrected.
    """
    cases = {
        "co_op_member_no": ("number", "abc"),
        "easement_signed": ("date", "the 4th"),
        "autopay_enrolled": ("boolean", "yes"),
        "site_hazards": ("multi_select", "Locked gate"),
    }
    for index, (key, (data_type, bad)) in enumerate(cases.items()):
        with tenant_ctx(brazos):
            account = an_account(dana, brazos, account_no=f"A-{key[:6]}")
            a_definition(brazos, key=key, data_type=data_type)
            set_account_values(account, {key: bad})
            run = a_run(brazos, key=f"2026-06|bad-{index}")

            with pytest.raises(BillingRuleError) as raised:
                draft_for(brazos, account, run)
            assert key in str(raised.value)
            assert data_type in str(raised.value)


def test_us_bil_028_tc4c__a_select_field_stamps_the_tenants_own_option(brazos, dana):
    """`select` needs no formatter: the stored value IS one of the tenant's
    `options` strings, so nothing is rendered and nothing is decided."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(
            brazos,
            key="hazard_note",
            data_type="select",
            options=["None", "Dog on site", "Locked gate"],
        )
        set_account_values(account, {"hazard_note": "Dog on site"})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {"accounts.hazard_note": "Dog on site"}


def test_us_bil_028_tc4d__a_string_typed_field_holding_a_non_string_is_refused(brazos, dana):
    """Not coerced. `str({"a": 1})` on a bill is a customer-visible defect that
    can never be corrected once the bill is issued, and it would satisfy
    "strings only" while losing the reason for the rule."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(account, {"service_class": {"nested": "object"}})

        with pytest.raises(BillingRuleError) as raised:
            draft_for(brazos, account, a_run(brazos))
        assert "strings only" in str(raised.value)


# ── TC-5 · the empty case, which is most bills in R2 ────────────────────────
def test_us_bil_028_tc5__an_account_with_no_custom_fields_stamps_an_empty_map(brazos, dana):
    """US-BIL-028 TC-5 — `{}`, never null, and the bill run is unaffected.

    Also the R2 reality: no shipped screen can define a field or mark one
    document-safe yet, so this is what every real invoice carries today. The
    column is what matters, not its contents in week one.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {}
        assert invoice.custom_snapshot is not None
        assert invoice.total == Decimal("108.88")  # GT-1 — the money is untouched


def test_us_bil_028_tc5b__a_defined_field_with_no_stored_value_contributes_no_key(brazos, dana):
    """ "Never filled in" and "filled in as blank" are different facts about a
    document and nothing ruled that they collapse. The absent key keeps them
    apart for whatever R3 decides."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {}


# ── TC-6 · deactivation (BR-TEN-050) ────────────────────────────────────────
def test_us_bil_028_tc6__a_deactivated_field_is_excluded_from_new_snapshots(brazos, dana):
    """US-BIL-028 TC-6 / BR-TEN-050 — excluded from NEW snapshots; the stored
    value survives untouched, and an already-stamped bill keeps its own."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        definition = a_definition(brazos)
        set_account_values(account, {"service_class": "Commercial"})
        first = draft_for(brazos, account, a_run(brazos))
        assert first.custom_snapshot == {"accounts.service_class": "Commercial"}
        models.Invoice.objects.filter(pk=first.pk).update(status=models.INVOICE_ISSUED)

        definition.is_active = False
        definition.save(update_fields=["is_active", "updated_at"])

        second = draft_for(brazos, account, a_run(brazos, key="2026-07|cycle-1"))
        assert second.custom_snapshot == {}
        # BR-TEN-050: the VALUE is retained and reappears on reactivation.
        account.refresh_from_db()
        assert account.custom_data == {"service_class": "Commercial"}
        assert models.Invoice.objects.get(pk=first.pk).custom_snapshot == {
            "accounts.service_class": "Commercial"
        }


# ── TC-7 / TC-8 · the DB-17 gate rule ───────────────────────────────────────
def test_us_bil_028_tc7__db17_fails_tenant_data_in_the_rating_engine():
    """US-BIL-028 TC-7 — merge-blocking FAIL naming BR-TEN-048, no allowlist.

    Exercised through `g06_forbidden.db17_violation`, the same pure function
    the gate calls — there is no second copy of the rule to drift. The gate was
    ALSO proved RED against the real tree by adding the token to
    `apps/rating/engine.py` and running `run_gates.py`; that transcript is in
    the human-review ledger (hard-won law 7).
    """
    verdict = _db17("06-backend/apps/rating/engine.py", "    value = row.custom_data['x']")
    assert verdict is not None
    assert "BR-TEN-048" in verdict
    assert "RATING" in verdict


def test_us_bil_028_tc8__db17_allows_only_the_one_billing_module():
    """US-BIL-028 TC-8 — FAIL anywhere under billing/ledger/payments except the
    single allowlisted module, which passes.

    The allowlist is asserted to have exactly ONE entry. Adding a second is a
    change to signed schema law (B2 r17.3 names the path), not a convenience,
    and this is what makes that visible in a diff.
    """
    import sys

    sys.path.insert(0, str(_GATES_DIR))
    import g06_forbidden

    assert g06_forbidden.DB17_ALLOWLIST == ("06-backend/apps/billing/custom_snapshot.py",)
    line = "    values = account.custom_data"
    assert _db17("06-backend/apps/billing/issue.py", line) is not None
    assert _db17("06-backend/apps/ledger/posting.py", line) is not None
    assert _db17("06-backend/apps/payments/allocation.py", line) is not None
    assert _db17("06-backend/apps/billing/custom_snapshot.py", line) is None
    # Outside the money paths the token is ordinary code — the owning modules
    # store the values and must be able to say so.
    assert _db17("06-backend/apps/customers/selectors.py", line) is None


def test_us_bil_028_tc8b__the_real_gate_is_clean_over_the_real_tree():
    """The rule, run for real. TC-7/TC-8 prove it BITES; this proves it does not
    bite the code that shipped — a gate that fails on its own repo gets muted."""
    import sys

    sys.path.insert(0, str(_GATES_DIR))
    import common
    import g06_forbidden

    hits = [
        f"{common.rel(path)}:{lineno}"
        for path in common.backend_code_files()
        for lineno, line in enumerate(common.read_text(path).splitlines(), start=1)
        if not line.strip().startswith("#") and g06_forbidden.db17_violation(common.rel(path), line)
    ]
    assert hits == []


# ── TC-9 · a second bill is its own document ────────────────────────────────
def test_us_bil_028_tc9__a_later_bill_stamps_its_own_snapshot(brazos, dana):
    """US-BIL-028 TC-9 — DB-4: a correction is a NEW row with its OWN stamp at
    its own moment, and the original is untouched."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(account, {"service_class": "Commercial"})
        first = draft_for(brazos, account, a_run(brazos))
        models.Invoice.objects.filter(pk=first.pk).update(status=models.INVOICE_ISSUED)

        set_account_values(account, {"service_class": "Irrigation"})
        second = draft_for(brazos, account, a_run(brazos, key="2026-07|cycle-1"))

        assert first.custom_snapshot == {"accounts.service_class": "Commercial"}
        assert second.custom_snapshot == {"accounts.service_class": "Irrigation"}
        assert models.Invoice.objects.get(pk=first.pk).custom_snapshot == {
            "accounts.service_class": "Commercial"
        }


# ── TC-11 · OQ-076, fail-closed ─────────────────────────────────────────────
def test_us_bil_028_tc11__a_field_not_marked_document_safe_is_never_stamped(brazos, dana):
    """OQ-076, PO 2026-08-10: *"Dont put SSN on invoices"*, mechanism INVERTED.

    The tenant defines "SSN last 4", fills it in, and never touches the
    document-safe flag — the default path, and the one an unlucky tenant takes.
    Nothing reaches the invoice. If this ever inverts, a Social Security number
    lands in an append-only table that BR-TEN-044's day-91 deletion cannot
    reach, and no correction is possible: hard-won law 3, at its most expensive.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos, key="ssn_last4", is_document_safe=False)
        a_definition(brazos, key="service_class")
        set_account_values(account, {"ssn_last4": "6789", "service_class": "Commercial"})
        invoice = draft_for(brazos, account, a_run(brazos))

        assert invoice.custom_snapshot == {"accounts.service_class": "Commercial"}
        assert "accounts.ssn_last4" not in invoice.custom_snapshot
        assert "6789" not in str(invoice.custom_snapshot)
        # The value is still CAPTURED — the ruling excludes it from documents,
        # not from the product (r17.5 #2: "usable on screens, never stamped").
        account.refresh_from_db()
        assert account.custom_data["ssn_last4"] == "6789"


def test_us_bil_028_tc11b__the_default_for_a_new_definition_is_not_document_safe(brazos):
    """The fail-closed default, asserted on the MODEL rather than through a
    caller — a helper that passes `is_document_safe=True` everywhere would hide
    a default that had flipped."""
    with tenant_ctx(brazos):
        field = tenancy_models.CustomField.objects.create(
            tenant=brazos, entity="accounts", key="ssn_last4", label="SSN last 4", data_type="text"
        )
        assert field.is_document_safe is False


# ── TC-12 · built is not wired (hard-won law 2) ─────────────────────────────
def test_us_bil_028_tc12__assemble_document_actually_stamps_the_snapshot(brazos, dana):
    """The guard that makes every other test in this file worth anything.

    A perfect `custom_snapshot.py` that nothing calls yields `{}` on every
    invoice, passes TC-5, TC-6, TC-11 and the whole isolation suite, and loses
    precisely as much data as having no column at all — permanently, because
    the rows are append-only. Four defects in one day came from this shape
    (hard-won law 2).

    Asserted by SPYING on the module the stage imports, not by checking the
    result: a result-based check cannot tell a stamp that ran and found nothing
    from a stamp that never ran, which is exactly the confusion this test
    exists to remove.
    """
    calls = []
    real = custom_snapshot.stamp_for_account

    def spy(account_id):
        calls.append(str(account_id))
        return real(account_id)

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(account, {"service_class": "Commercial"})
        stage6.custom_snapshot_module.stamp_for_account = spy
        try:
            invoice = draft_for(brazos, account, a_run(brazos))
        finally:
            stage6.custom_snapshot_module.stamp_for_account = real

    assert calls == [str(account.id)], (
        "stages/assemble_document.py did not call the stamp. An unwired stamp is "
        "indistinguishable from a tenant with no custom fields, and the rows it "
        "should have written can never be repaired (B12 r7.2)."
    )
    assert invoice.custom_snapshot == {"accounts.service_class": "Commercial"}


def test_us_bil_028_tc12b__an_unresolvable_registry_refuses_rather_than_stamping_empty(
    brazos, dana, monkeypatch
):
    """Fail-closed at the seam. `{}` written because the registry could not be
    read is indistinguishable, forever, from `{}` meaning "nothing defined" —
    on a row that can never be updated. A run that stops is a morning's delay."""
    monkeypatch.setattr(custom_snapshot, "REGISTRY_READ", "no_such_selector_published")
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(BillingConfigError) as raised:
            draft_for(brazos, account, a_run(brazos))
        assert "no_such_selector_published" in str(raised.value)


# ── TC-13 · hard rule 4, on the live cluster ────────────────────────────────
@pytest.mark.isolation
@requires_postgres
def test_us_bil_028_tc13__the_snapshot_is_frozen_once_the_bill_is_issued(brazos, dana):
    """CLAUDE.md rule 4 — the DATABASE refuses it, not just the service layer.

    A new column is NOT covered by an existing trigger: PostgreSQL stores a
    function body as TEXT, so `billing_invoice_immutable()` had to be re-emitted
    naming `custom_snapshot` (migration 0009). Without that line the freeze
    fails OPEN over the one column this whole lane exists to protect, and every
    test in this file still passes. Proved RED exactly that way before the line
    was trusted.
    """
    with live_tenant_context(brazos.id):
        account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(account, {"service_class": "Commercial"})
        invoice = draft_for(brazos, account, a_run(brazos))
        models.Invoice.objects.filter(pk=invoice.pk).update(
            status=models.INVOICE_ISSUED, issued_at=ISSUED_AT
        )

        refusals = (IntegrityError, InternalError, ProgrammingError, DatabaseError)
        # `transaction.atomic()` is the SAVEPOINT that lets the aborted
        # statement be rolled back without poisoning the test's own transaction
        # — the same shape test_us_bil_005_issue.py uses for the money columns.
        with pytest.raises(refusals), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE invoices SET custom_snapshot = %s WHERE id = %s",
                ['{"accounts.service_class": "Irrigation"}', str(invoice.pk)],
            )

        # The narrow door still opens: settlement must remain possible.
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE invoices SET status = 'paid' WHERE id = %s", [str(invoice.pk)])
        assert models.Invoice.objects.get(pk=invoice.pk).custom_snapshot == {
            "accounts.service_class": "Commercial"
        }


# ── TC-10 · tenant isolation ────────────────────────────────────────────────
def test_us_bil_028_tc10__each_tenant_stamps_only_its_own_registry(brazos, dana, lonestar):
    """US-BIL-028 TC-10, app-layer half — runs on every vendor.

    Brazos Bend defines `service_class`; Lone Star Ridge defines nothing and
    bills the same period. No key from the other tenant's registry appears, and
    Lone Star Ridge's own bill is `{}` rather than an error.
    """
    erin = staff_actor(lonestar, "system_admin", "erin@lsrwater.test")
    with tenant_ctx(brazos):
        brazos_account = an_account(dana, brazos)
        a_definition(brazos)
        set_account_values(brazos_account, {"service_class": "Commercial"})
        brazos_invoice = draft_for(brazos, brazos_account, a_run(brazos))

    with tenant_ctx(lonestar):
        # Water only — Lone Star Ridge does not have Electric enabled, so its
        # account cannot be built by the electric helper the GT-1 chain uses.
        # The stamp is therefore called DIRECTLY here: this case is about the
        # registry the stamp reads, not about pricing a second bill.
        lsr_account = a_water_account(erin, lonestar)
        # The SAME key, filled in on the other tenant's own row — so a stamp
        # that read the registry unscoped would find a definition for it.
        set_account_values(lsr_account, {"service_class": "Irrigation"})
        lsr_snapshot = custom_snapshot.stamp_for_account(lsr_account.id)

    assert brazos_invoice.custom_snapshot == {"accounts.service_class": "Commercial"}
    assert lsr_snapshot == {}


@pytest.mark.isolation
@requires_postgres
def test_us_bil_028_tc10b__custom_field_is_rls_isolated(brazos, lonestar, rls):  # noqa: F811
    """US-BIL-028 TC-10 / BR-TEN-046, database half — through the NON-SUPERUSER
    probe role, so the policy is genuinely consulted rather than bypassed.

    A definition leak is both a disclosure (the label is the tenant's own prose)
    and a document defect (it decides what is stamped onto their invoices).
    """
    with live_tenant_context(brazos.id):
        owned = a_definition(brazos)
    with live_tenant_context(lonestar.id):
        a_definition(lonestar, key="feeder_zone")

    assert_rls_scoped(
        rls, "custom_field", owner=brazos, intruder=lonestar, owner_ids={str(owned.id)}
    )
    assert_denied_without_context(rls, "custom_field")


# ── plumbing ────────────────────────────────────────────────────────────────
def _gates_dir():
    from pathlib import Path

    return Path(__file__).resolve().parents[2] / "10-scripts" / "gates"


_GATES_DIR = _gates_dir()


def _db17(rel_path: str, line: str):
    import sys

    sys.path.insert(0, str(_GATES_DIR))
    import g06_forbidden

    return g06_forbidden.db17_violation(rel_path, line)


# ═══════════════════════════════════════════════════════════════════════════
# WHERE THE SNAPSHOT PRINTS — the PO's 2026-08-12 ruling, on the paper
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ THE EPIC NUMBERS TWO DIFFERENT CASES `TC-9` AND TWO `TC-10` (EP-BIL-02
# US-BIL-028 §3 — the older pair is the re-issue snapshot and the DB-17 gate,
# the 2026-08-12 pair is where custom fields PRINT and the four literals). The
# tests below are the 2026-08-12 pair and are suffixed `p` for *print* so both
# pairs keep a test and neither name is reused. The duplicate numbering is the
# epic's and is REPORTED here rather than renumbered — screen and case IDs are
# never renumbered (CLAUDE.md §Screen IDs).
#
# WHAT WAS ACTUALLY MISSING UNTIL 2026-08-16, and it is the whole reason these
# cases exist: every test above proves the snapshot is STAMPED correctly, and
# `10-scripts/gates/surface_debt.txt` said of this story *"read by nothing until
# US-NOT-016 in R3"* — a sentence that was true of the CODE and false of the
# PLAN, because the PO had already ruled on 2026-08-12 that the values print on
# the bill. A stamp nobody prints is a column, not a feature.
def a_bill_with_snapshot(tenant, account, run, snapshot, **overrides):
    """An issued-shaped draft carrying a stamped snapshot, ready to render.

    Built through `a_priced_draft` — the same fixture the document tests use —
    rather than through the real stage 6, because what these cases are about is
    the DOCUMENT: driving the whole pricing chain to reach the renderer would
    make a rendering failure look like a pricing failure.
    """
    return a_priced_draft(
        tenant,
        account,
        run,
        custom_snapshot=snapshot,
        template_id=DOC_TEMPLATE_ID,
        template_version=DOC_TEMPLATE_VERSION,
        **overrides,
    )


def test_us_bil_028_tc9p__every_custom_field_prints_in_ONE_remark_section(brazos, dana):
    """US-BIL-028 TC-9 (2026-08-12) — *"in remark or note section on bill"*.

    The PO's ruling has two halves and this asserts both. **ONE section** — the
    eight custom-field areas do not each get a designed place on the page — and
    **every** field in it, so a tenant cannot discover that the platform prints
    three of their five.

    Asserted on BOTH serialisations. The HTML is what the S30 viewer renders
    from and the PDF is what the customer holds; a value that reached one and
    not the other would be two different bills with one bill number.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = a_bill_with_snapshot(
            brazos,
            account,
            a_run(brazos),
            {
                "accounts.member_no": "10432",
                "accounts.multiplier": "1.5",
                "accounts.connected_on": "2026-03-04",
                "accounts.autopay": "Yes",
                "premises.access_notes": "Locked gate, Dog on site",
            },
        )
        rendered = documents.render_invoice(invoice)

    # ONE section, and it carries all five.
    assert len(rendered.remarks) == 5
    assert rendered.body.count('<section class="remarks">') == 1
    page = rendered.pdf.decode("latin-1")
    assert page.count("REMARKS & NOTES") == 1

    values = [field.value for field in rendered.remarks]
    for value in ("10432", "1.5", "2026-03-04", "Yes", "Locked gate, Dog on site"):
        assert value in values, f"{value!r} is stamped on the bill and printed nowhere"
        assert value in rendered.body
        assert value in page


def test_us_bil_028_tc10p__the_four_literals_reach_the_paper_unchanged(brazos, dana):
    """US-BIL-028 TC-10 (2026-08-12) — the grant's literals, on the DOCUMENT.

    `tc3`/`tc4`/`tc4e`/`tc4f` already pin these four strings where they are
    STAMPED. This pins them where they are READ, and the two are different
    guarantees: a renderer that grouped the identifier as `10,432` or localised
    the ISO date to `03/04/2026` would satisfy every stamping test in this file
    and still print the wrong thing on an append-only document.

    `10,432` and `03/04/2026` are asserted ABSENT by name rather than only
    asserting the right string present, because a document containing both
    would pass a presence-only check.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = a_bill_with_snapshot(
            brazos,
            account,
            a_run(brazos),
            {
                "accounts.member_no": "10432",
                "accounts.multiplier": "1.5",
                "accounts.connected_on": "2026-03-04",
                "premises.access_notes": "Locked gate, Dog on site",
            },
        )
        rendered = documents.render_invoice(invoice)

    page = rendered.pdf.decode("latin-1")
    for surface in (rendered.body, page):
        assert "10432" in surface
        assert "10,432" not in surface, "an identifier was grouped as a quantity"
        assert "2026-03-04" in surface
        assert "03/04/2026" not in surface, "an ISO date was localised on an immutable bill"
        assert "Locked gate, Dog on site" in surface


def test_us_bil_028_tc9p_b__a_tenant_with_no_custom_fields_gets_no_remark_section(
    brazos, dana
):
    """TC-5's other half: `{}` stamps, and NOTHING is drawn.

    An empty *Remarks & notes* heading on a bill invites the customer to ask
    what was supposed to be under it, and invites the clerk to think something
    failed to load. The section is omitted whole.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = a_bill_with_snapshot(brazos, account, a_run(brazos), {})
        rendered = documents.render_invoice(invoice)

    assert rendered.remarks == ()
    assert '<section class="remarks">' not in rendered.body
    assert "REMARKS & NOTES" not in rendered.pdf.decode("latin-1")


def test_us_bil_028_tc9p_c__the_printed_label_comes_from_the_frozen_key(brazos, dana):
    """BR-BIL-030 on the LABEL, not only on the value.

    `custom_field_definitions.label` is live master data. A renderer that read
    it would print THIS March's label above LAST January's stamped value — the
    live join BR-BIL-030 forbids, satisfying DB-4 to the letter while rewriting
    an issued document in substance. So the label is derived from the key that
    was stamped beside the value.

    Driven by RENAMING the definition after the bill exists: the document must
    not move.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        definition = a_definition(brazos, key="service_class")
        invoice = a_bill_with_snapshot(
            brazos, account, a_run(brazos), {"accounts.service_class": "Commercial"}
        )
        before = documents.render_invoice(invoice).remarks

        definition.label = "RENAMED AFTER THE BILL WAS ISSUED"
        definition.save(update_fields=["label", "updated_at"])
        after = documents.render_invoice(invoice).remarks

    assert before == after
    assert [f.label for f in after] == ["Account · Service class"]
    assert "RENAMED AFTER THE BILL WAS ISSUED" not in documents.render_invoice(invoice).body


def test_us_bil_028_tc9p_d__a_non_string_in_the_snapshot_refuses_the_document(brazos, dana):
    """The strings-only rule, enforced at READ as well as at stamp.

    `_display_string` refuses a non-string on the way IN. This is the same
    refusal on the way OUT, and it is not belt-and-braces theatre: the column is
    `jsonb` and nothing stops a migration, a fixture or a future writer putting
    a number in it. `str()` here would print `{'a': 1}` onto a bill that can
    never be corrected, so the document is refused instead and BR-BIL-033 turns
    that into one named break on one bill.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        invoice = a_bill_with_snapshot(
            brazos, account, a_run(brazos), {"accounts.multiplier": 1.5}
        )
        with pytest.raises(BillingRuleError) as refused:
            documents.render_invoice(invoice)

    assert "accounts.multiplier" in str(refused.value)
    assert "float" in str(refused.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-028@f61575a (sha256[:7], 2026-08-11, over B12 12-engineering-plan.md + B2
#         02-database-design-brief.md + EP-BIL-02 + EP-TEN-09 +
#         07-billing/02-business-rules.md + 01-tenancy/02-business-rules.md.
#         This file's own sources: B12 addendum r7 · B2 addendum r17 ·
#         EP-BIL-02-invoice-gl.md US-BIL-028 · EP-TEN-09-custom-fields.md ·
#         07-billing/02-business-rules.md BR-BIL-030)
# generated: 2026-08-11 by story-coder (tenant custom-fields lane) · AMENDED
#         2026-08-12 by story-coder (OQ-125 CLOSED — TC-3/TC-4 rewritten from
#         pinning the refusal to pinning the ruling, plus tc4e/tc4f/tc4g)
# checklist: A✔ B✔ C✔ D✔(the snapshot is read and served since 2026-08-16 — see apps/billing/custom_snapshot.py's trailer for the stale claim this row used to repeat) E✔(the Remarks & notes band, tc9p/tc10p) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · run on sqlite (the two isolation cases skip with a
#         vendor reason) and on a live Postgres cluster (all cases run)
# exceptions: (1) TC-3 AND TC-4 ASSERT THE EXACT PRINTED STRING. This item
#         previously read "TC-3 and TC-4 assert the STUB, not the behaviour
#         their story describes — OQ-125 is open" and was TRUE WHEN WRITTEN;
#         the PO closed OQ-125 on 2026-08-12 and granted the FORMAT to the
#         application *"for the time being"*. The cases were rewritten to pin
#         the ruling rather than deleted, and they assert literals ("10432",
#         "2026-03-04", "Yes", "Locked gate, Dog on site") because those strings
#         are frozen into append-only rows: when the temporary grant is
#         withdrawn, the change of format has to be a RED test rather than a
#         quiet change in what bills print · (2) definitions are written through the ORM, not a
#         service: US-TEN-015's write path does not exist and this file says so
#         rather than letting a helper imply it · (3) TC-12 spies on the module
#         attribute rather than asserting a result, because a result cannot
#         distinguish "stamped nothing" from "never stamped" — which is the
#         whole failure mode it guards
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
