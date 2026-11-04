# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-5000 — S21's Account panel printed the raw database word
#          `small_commercial` at a clerk, because `selectors.account_row`
#          served only the CODE and the screen had nothing else to render.
#          Found by `CR-094-BRC01` step 1 lane 2 on the running product;
#          measured on `A-11812` (Bramble Bakery) and `AC-2026-00043`.
# Rules:   B14 rule 31 (PO 2026-08-30, verbatim: *"no Databse ID on screen -
#          that is a rule"*) · B14 rule 32 (no internal code in clerk-facing
#          copy) · BR-CUS-067 (the twelve-row account_type → account_subtype
#          tree, PO 2026-08-17 *"add them"*, seeded PER TENANT) ·
#          BR-CUS-094 / DEF-684 (a label is never invented for a code the
#          catalogue does not hold)
# ───────────────────────────────────────────────────────
"""The sub-type reaches a screen as the TENANT'S LABEL, with the code beside it.

WHY THE FIX IS ON THE WIRE AND NOT IN A FRONT-END CATALOGUE
───────────────────────────────────────────────────────────
`account_subtypes` is **tenant-defined**: BR-CUS-067's twelve rows are SEEDED
per tenant and a tenant may add its own, so the label belongs to the tenant and
cannot live in `src/i18n/locales/**`. That is exactly the mistake `DEF-684`
made one field over — the Category cell resolved
`customers.accounts.category.<code>`, the catalogue only ever held BR-CUS-094's
superseded four, and the three codes the ruling added printed their raw slug on
S21. A second catalogue of tenant data would have re-created that defect with a
different key prefix.

So this mirrors the pair `account_row` already serves for status — `status`
and `status_name` — and the screen falls back to the CODE when no label
arrives. Falling back to the code is deliberate: `accountCategoryName`'s own
docstring records why, and it is BR-CUS-094's named prohibition — invent a
label and `government` quietly starts reading as *"Municipal"*. A code on
screen is a fact about the DATA; a wrong word is a lie about it.

RED BEFORE THIS LANE
────────────────────
`account_row` had no `account_subtype_name` key at all, so §1 fails with a
`KeyError` and §2's label assertion fails on the raw code.
"""
import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.metering import models as metering_models

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

#: The code the PO's own screenshot carried, and its seeded label. Both from
#: `SEED_ACCOUNT_SUBTYPES` (BR-CUS-067) rather than typed as a preference.
MEASURED_CODE = "small_commercial"
MEASURED_LABEL = "Small commercial"


def _account_with_subtype(tenant, *, subtype_code=MEASURED_CODE):
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line="142 Bakers Row", city="Silver Creek", state="TX"
    )
    unit = metering_models.Unit.objects.create(tenant=tenant, premises=premises, label="Suite 1")
    status = customers_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account_type = customers_models.AccountType.objects.get(code="commercial")
    subtype = (
        None
        if subtype_code is None
        else customers_models.AccountSubtype.objects.get(tenant=tenant, code=subtype_code)
    )
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        account_no="A-11812",
        status=status,
        account_type=account_type,
        account_subtype=subtype,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE LABEL IS SERVED, AND THE CODE IS STILL SERVED BESIDE IT
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_5000__the_row_serves_the_label_and_keeps_the_code(growth_plan, identity_seam):
    """Both keys, because they answer different questions.

    The label is what a clerk reads; the code is what a caller filters and
    branches on. Dropping the code to "fix" the screen would break every
    consumer that keys off it, and B14 rule 31 does not ask for that — it asks
    that the code is not the VISIBLE VALUE OF A FIELD.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account_with_subtype(tenant)
        row = customers_selectors.account_row(
            customers_selectors.account_queryset().get(pk=account.pk)
        )
    assert row["account_subtype"] == MEASURED_CODE
    assert row["account_subtype_name"] == MEASURED_LABEL
    # The pair this mirrors, asserted in the same breath so the two shapes
    # cannot drift apart.
    assert row["status"] == "active"
    assert row["status_name"] == "Active"


def test_def_cus_5000__no_subtype_serves_null_for_both(growth_plan, identity_seam):
    """An account with no sub-type says so twice, and never as an empty string.

    `null` is what the screen's `Dash` branches on. An empty string would
    render a blank cell, which reads as a value that happens to be nothing
    rather than as a fact that was never recorded.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account_with_subtype(tenant, subtype_code=None)
        row = customers_selectors.account_row(
            customers_selectors.account_queryset().get(pk=account.pk)
        )
    assert row["account_subtype"] is None
    assert row["account_subtype_name"] is None


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE LABEL IS THE TENANT'S, WHICH IS WHY IT CANNOT BE A CATALOGUE STRING
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_5000__a_tenant_renaming_its_subtype_changes_what_the_screen_reads(
    growth_plan, identity_seam
):
    """The whole reason the label travels on the wire (BR-CUS-067 · DEF-684).

    A tenant edits its own sub-type vocabulary on Settings. A front-end
    catalogue keyed on the CODE would keep printing our seeded English over the
    utility's own word — and for a code the tenant ADDED it would print the raw
    slug, which is `DEF-684` verbatim, one field over.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account_with_subtype(tenant)
        row = customers_models.AccountSubtype.objects.get(tenant=tenant, code=MEASURED_CODE)
        row.name = "Main Street business"
        row.save(update_fields=["name"])
        served = customers_selectors.account_row(
            customers_selectors.account_queryset().get(pk=account.pk)
        )
    assert served["account_subtype_name"] == "Main Street business"
    assert served["account_subtype"] == MEASURED_CODE


# ══════════════════════════════════════════════════════════════════════════
# 3 · IT COSTS NO QUERY, WHICH IS WHY THIS IS THE CHEAP FIX
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_5000__the_label_is_already_joined_and_adds_no_statement(
    growth_plan, identity_seam, django_assert_num_queries
):
    """`account_queryset` already `select_related`s `account_subtype`.

    Asserted rather than asserted-in-a-comment: `DEF-2723` measured six extra
    statements per row on this very serialiser, so a new key that reads through
    an unjoined FK would be an N+1 on the account LIST as well as the detail.
    The count is taken from the queryset evaluation itself, so reading
    `.name` afterwards must add nothing.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        account = _account_with_subtype(tenant)
        loaded = customers_selectors.account_queryset().get(pk=account.pk)
        # Zero further statements: the join has already brought the row back.
        with django_assert_num_queries(0):
            assert loaded.account_subtype.name == MEASURED_LABEL


@pytest.mark.parametrize("code", ["single_family", "large_commercial", "parks_facilities"])
def test_def_cus_5000__every_seeded_subtype_has_a_label_to_serve(code, growth_plan, identity_seam):
    """No seeded row is left with the code as its own label.

    A row whose `name` equals its `code` would pass every assertion above and
    still print `parks_facilities` at a clerk — the defect surviving the fix,
    which is the false-pass this parametrisation exists to rule out.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customers_models.AccountSubtype.objects.get(tenant=tenant, code=code)
    assert row.name
    assert row.name != row.code
    assert "_" not in row.name


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-5000 (CR-094-BRC01 step 2 wave B)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
