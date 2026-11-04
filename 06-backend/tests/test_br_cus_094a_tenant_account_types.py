# ── Trace ──────────────────────────────────────────────
# Rules:   BR-CUS-094a (PO 2026-09-17, "utility can get their own account
#          types" + "we have to ensure it is not hard coded") — supersedes
#          BR-CUS-094's PLATFORM SEVEN, which becomes the SEED · BR-TEN-034 (a
#          deactivated lookup row stops being pickable and a fallback must not
#          resurrect it) · BR-MET-084 (the three-outcome resolver shape this
#          copies) · BR-RAT-108 / DEF-273 (the INCLUSION-list direction) ·
#          CLAUDE.md hard rule 1 (tenant scoping)
# Golden:  NONE MOVES. This widens the set of class codes a restriction MAY
#          NAME and changes no rate, no base, no rounding and no stored row.
# Files:   apps/rating/seams.py :: selectable_account_type_codes ·
#          apps/rating/services.py :: the three validators ·
#          apps/billing/template_models.py :: categories ·
#          apps/portal/seams/customers_seam.py :: home_account_type_id
# ───────────────────────────────────────────────────────
"""BR-CUS-094a — the four consumers that read a hardcoded account-type list.

**The ruling, in one sentence a person would say:** a utility may now invent its
own kinds of customer, so anywhere the product wrote the list of customer kinds
into its own source code is a place that utility's new kind does not exist.

**WHY EACH CASE HERE IS A MONEY OR A TRUST SURFACE, not a tidiness one.**
A tax or a connection charge is RESTRICTED to a list of class codes; a code the
validator refuses cannot be stored, so the utility writes a rule it believes is
configured and the customer it was written for is charged nothing by it. That
is DEF-738 exactly, one ruling later. The portal case is the mirror: a figure
quoted to a member of the public for a class they may not belong to.

**THE RED PROOF IS IN EACH TEST'S OWN DOCSTRING**, quoted from the run against
the unpatched tree at 2b1619b0f. Run through pytest, never `python3 <file>` —
`DEF-GOV-3733` is what happens when a guard is proved through an entry point
nothing uses.

⚠ **EVERY HELPER HERE WORKS WHETHER OR NOT `account_types` HAS A `tenant_id`.**
A sibling lane is making the table tenant-owned under the same ruling. Reading
ROWS instead of a constant is correct either way, and a test that assumed either
shape would go red on the merge rather than on a real fault.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.customers import models as customers_models
from core import errors
from apps.rating import seams as rating_seams
from apps.rating import services as rating_services
from tests.test_us_rat_helpers import env, growth_plan, job_store, other_env, tenant_ctx  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# helpers — tenant-shape-agnostic, deliberately
# ══════════════════════════════════════════════════════════════════════════
def _account_types_are_tenant_scoped() -> bool:
    """Does `account_types` carry a tenant column YET? Asked of the MODEL.

    The sibling lane adding it and this lane reading rows are independent; this
    keeps every case below true on both sides of that migration.
    """
    return any(f.attname == "tenant_id" for f in customers_models.AccountType._meta.concrete_fields)


def _add_account_type(tenant, code: str, name: str, *, active: bool = True):
    """Give this tenant a customer kind of its own — the thing the PO ruled for."""
    fields = {"code": code, "name": name, "is_system": False, "active": active, "legacy": False}
    if _account_types_are_tenant_scoped():
        fields["tenant_id"] = tenant.id
    return customers_models.AccountType.objects.create(**fields)


def _seeded_codes() -> set[str]:
    model = customers_models.AccountType
    return {code for code, _name in model.SEVEN_CATEGORIES} | set(model.LEGACY_CODES)


# ══════════════════════════════════════════════════════════════════════════
# 1 · RATING — the money path: a tenant's own class may be priced
# ══════════════════════════════════════════════════════════════════════════
def test_a_tenants_own_class_may_restrict_a_tax(env):  # noqa: F811
    """A utility invents "Marina" and writes a 6.25% tax for it.

    ⚠ **RED ON THE UNPATCHED TREE, and the failure is the money one:**

        core.errors.ValidationError: VAL_UNKNOWN_LOOKUP
        field_errors: [{'field': 'applies_to_customer_classes[0]',
                        'code': 'VAL_UNKNOWN_LOOKUP',
                        'message_key': 'rating.taxes.unknown_customer_class'}]

    The tax cannot be STORED, so the marina is charged $0.00 by a rate the
    utility believes it configured — DEF-738's shape, one ruling later.
    """
    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina")

    tax = env.tax(
        "Harbour District",
        kind="percent",
        rate="0.0625",
        applies_to_customer_classes=["marina"],
    )
    assert tax["applies_to_customer_classes"] == ["marina"]


def test_the_selectable_codes_come_from_the_rows_not_the_constants(env):  # noqa: F811
    """`selectable_account_type_codes()` IS the tenant's own vocabulary.

    ⚠ **RED ON THE UNPATCHED TREE:** the function did not exist —
    `AttributeError: module 'apps.rating.seams' has no attribute
    'selectable_account_type_codes'`.
    """
    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina")
        codes = rating_seams.selectable_account_type_codes()

    assert "marina" in codes
    # The ruled seven are still there — a tenant ADDS, it does not replace.
    assert {"residential", "commercial", "agricultural", "municipal"} <= set(codes)


def test_a_deactivated_class_is_not_resurrected_by_the_fallback(env):  # noqa: F811
    """BR-TEN-034, the clause `_resolve_unit_type` is careful about.

    A tenant that retires its "Marina" class must not find the fallback handing
    it back. The seeded rows are NOT touched here — deactivating a platform seed
    is the sibling lane's territory; this asserts the rule on a row we own.
    """
    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina", active=False)
        codes = rating_seams.selectable_account_type_codes()

    assert "marina" not in codes


def test_the_legacy_code_stays_selectable_for_a_restriction(env):  # noqa: F811
    """⚠ `government` IS in the list and that is deliberate, BR-CUS-094.

    *"A tax restriction is a filter over accounts, and accounts still carry the
    code"* — dropping it would invalidate every restriction already stored.
    """
    with tenant_ctx(env.tenant):
        assert "government" in rating_seams.selectable_account_type_codes()


def test_a_tenant_with_no_rows_at_all_falls_back_to_the_ruled_vocabulary():
    """The third outcome of the three — a deployment whose rows have not been

    seeded yet keeps working on the ruled vocabulary rather than refusing every
    class. `_resolve_unit_type`'s middle branch, verbatim in shape.
    """
    customers_models.AccountType.objects.all().delete()
    codes = set(rating_seams.selectable_account_type_codes())
    assert codes == _seeded_codes()


def test_a_size_rows_customer_class_is_checked_against_the_table(env):  # noqa: F811
    """⚠ **THE SECOND MONEY COLUMN, AND IT WAS CHECKED AGAINST NOTHING.**

    `charges.size_amounts[].customer_class` is `CR-087 A1`'s narrowing
    dimension — the column that makes one code price a `$45.00` residential
    connection and an `$85.00` commercial one. Until 2026-09-17 it accepted ANY
    string up to 60 characters, while `size_class` beside it was refused unless
    served and `applies_to_customer_classes` on the same object refused an
    unknown code by name.

    **The cost of the gap is silent and it is money.** A typo'd `residental`
    row is stored, matches no account that ever existed, and the customer it was
    written for is billed the every-class amount instead — `$45.00` where the
    utility typed `$85.00`, with no error anywhere. `DEF-273`'s ruled direction
    (refuse, never drop) applies here for exactly the reason it applies there.

    ⚠ **THE STORAGE IS UNCHANGED** — still TEXT, still `None` meaning every
    class, and every row already stored keeps its value. Only what may be
    WRITTEN moved, and it moved onto the tenant's own table.
    """
    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina")

    def class_errors(value):
        """The field errors this class value produces on a size row.

        Asserted on the FIELD ERRORS rather than on whether the charge was
        created, so the case does not depend on which meter sizes this fixture
        happens to serve — `size_class` has its own refusal and it is not the
        subject here.
        """
        try:
            env.charge(
                code=f"CONN-{value[:4].upper()}",
                name="Connection",
                charge_type="one_time",
                size_amounts=[
                    {"size_class": "W-58", "amount": "85.00", "customer_class": value}
                ],
            )
        except errors.ValidationError as caught:
            return {e["field"] for e in caught.field_errors}
        return set()

    # A typo is REFUSED rather than stored and silently never matched.
    assert "size_amounts[0].customer_class" in class_errors("residental")
    # The utility's OWN class raises no complaint about the class.
    assert "size_amounts[0].customer_class" not in class_errors("marina")
    # And so does a ruled one, which is the case that must not have regressed.
    assert "size_amounts[0].customer_class" not in class_errors("commercial")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE GUARD STAYS CAPABLE OF FAILING — the half that is easy to destroy
# ══════════════════════════════════════════════════════════════════════════
def test_the_ruled_vocabulary_is_still_read_from_the_constants():
    """⚠ **THIS IS WHAT STOPS THE DEF-273 GUARD BECOMING A TAUTOLOGY.**

    `account_type_codes()` must go on reading the model's DECLARED CONSTANTS. If
    it ever derives from rows, then `test_def273_the_class_vocabulary_mirrors_
    the_platform_account_types` compares the rows with themselves and can never
    go red — a check that cannot fail is worse than none (DEF-182).

    So the split is the deliverable, not an implementation detail:
      · `account_type_codes()`            — the vocabulary AS RULED  (constants)
      · `selectable_account_type_codes()` — the vocabulary AS HELD   (rows)
    """
    customers_models.AccountType.objects.all().delete()
    # No rows at all, and it STILL answers — proving it read no table.
    assert set(rating_seams.account_type_codes()) == _seeded_codes()
    assert set(rating_services.TAX_CUSTOMER_CLASSES) == _seeded_codes()


def test_the_seeded_rows_still_match_the_ruling(env):  # noqa: F811
    """The real question the DEF-273 guard exists to ask, narrowed so a

    tenant-added row cannot make it red: **do the rows the PLATFORM SEEDS still
    match the vocabulary the PO ruled?** It goes red the day a migration seeds a
    code the ruling does not name, or names one it does not seed.
    """
    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina")
        seeded = {row.code for row in customers_models.AccountType.objects.filter(is_system=True)}
    assert seeded == _seeded_codes(), (
        f"the platform seeds {sorted(seeded)} and BR-CUS-094 rules {sorted(_seeded_codes())}"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · BILLING TEMPLATES — four constants, one of them a code that never was
# ══════════════════════════════════════════════════════════════════════════
def test_billing_categories_are_read_from_the_table(env):  # noqa: F811
    """⚠ **RED ON THE UNPATCHED TREE, and it is a three-way disagreement:**

        AssertionError: assert 'agricultural' in ('residential', 'commercial',
                                                  'industrial', 'govt')

    `billing` spelt the fourth category `govt`, `notifications` spells the same
    idea `government`, and the ratified code is `municipal` with `government`
    LEGACY. Three spellings of one thing in three modules, which only a table
    read settles.
    """
    from apps.billing import template_models

    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina")
        categories = template_models.categories()

    assert "marina" in categories
    assert {"agricultural", "municipal", "institutional", "builder_developer"} <= set(categories)


def test_govt_is_not_a_code_this_product_has_ever_had():
    """⚠ **`govt` IS NOT A REAL CODE** — it appears in no `account_types` row,

    no migration and no ratified list. It was a fourth constant invented beside
    three real ones.

    MEASURED rather than asserted, before it was removed: `bill_templates` held
    **ZERO rows in every database on this machine** (`sbh`, `sbh_capis` and both
    test databases), no migration seeds a category, the only production writer
    (`ensure_seed_template`) writes `category=None`, and `create_template` — the
    one path that could store a category — **is not served by any route**
    (`templates_service.py`'s own refusal register: *"STILL NOT SERVED:
    create_template"*). So no row anywhere carries it and this needed a constant
    change, NOT a data migration.
    """
    from apps.billing import template_models

    source = Path(template_models.__file__).read_text(encoding="utf-8")
    # Comment lines are stripped: the module now EXPLAINS `govt` at length, and
    # prose naming a mistake is how the next reader learns not to repeat it.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert '"govt"' not in code and "'govt'" not in code, (
        "`govt` is back in billing's template vocabulary"
    )


def test_a_tenants_own_class_may_have_its_own_bill_layout(env):  # noqa: F811
    """BR-BIL-025 end to end: the utility's new class gets a template default.

    ⚠ **RED ON THE UNPATCHED TREE:**

        ValueError: 'marina' is not a consumer category; BR-BIL-025 names
        residential, commercial, industrial, govt.
    """
    from apps.billing import template_models, templates_service

    with tenant_ctx(env.tenant):
        _add_account_type(env.tenant, "marina", "Marina")
        template = templates_service.create_template(
            name="Bill · Marina",
            template_type=template_models.TYPE_BILL,
            category="marina",
            actor=env.admin,
        )
    assert template.category == "marina"


# ══════════════════════════════════════════════════════════════════════════
# 4 · PORTAL — one literal, and the honest fallback is NOT a different class
# ══════════════════════════════════════════════════════════════════════════
def test_the_portal_reads_the_home_class_from_the_table(env):  # noqa: F811
    """`CWP-008` quotes a deposit to a visitor who has not said what kind of

    customer they are, so it asks for the HOME class.

    ⚠ **THE HONEST FALLBACK IS `None`, AND IT IS NOT A JUDGMENT CALL.**
    `rating_seam.deposit` already returns None for a missing class, and the
    screen then says *"deposit on your first bill"* with no figure. The
    alternative — picking the tenant's first active row — would quote a
    COMMERCIAL deposit to somebody moving into a house, which is a money figure
    shown to a member of the public for a class they do not belong to. There is
    no safe substitute for the class somebody actually belongs to, so the figure
    is WITHHELD rather than guessed.
    """
    from apps.portal.seams import customers_seam

    with tenant_ctx(env.tenant):
        row = customers_models.AccountType.objects.filter(code="residential").first()
        assert customers_seam.home_account_type_id() == row.id


def test_the_portal_quotes_no_deposit_when_there_is_no_home_class(env):  # noqa: F811
    """A utility whose vocabulary has no home class gets `None`, not somebody

    else's deposit. ⚠ **RED ON THE UNPATCHED TREE** — the function did not
    exist under this name, and the literal it replaced could not have been asked
    this question.

    ⚠ **THE CLASS IS RETIRED, NOT DELETED, AND THAT IS THE REAL CASE.** A seeded
    row is `is_system` — deactivatable, never deletable (`BR-TEN-036`) — and
    `AccountSubtype.account_type` is `on_delete=PROTECT`, so a delete is refused
    by the database itself. Deactivating is the only thing a utility can actually
    do to a class it does not use, and `BR-TEN-034` says the fallback must not
    resurrect it.
    """
    from apps.portal.seams import customers_seam

    home_code = customers_models.AccountType.SEVEN_CATEGORIES[0][0]
    with tenant_ctx(env.tenant):
        customers_models.AccountType.objects.filter(code=home_code).update(active=False)
        assert customers_seam.home_account_type_id() is None


def test_the_portal_does_not_name_the_home_class_as_a_literal():
    """⚠ **AND THE CODE IS STILL NOT TYPED OUT** — it is read from the model

    that owns it, so the day the PO renames the home class this follows.
    """
    from apps.portal.seams import customers_seam

    source = Path(customers_seam.__file__).read_text(encoding="utf-8")
    body = source[source.index("def home_account_type_id") :]
    body = body[: body.index("\ndef ")]
    # ⚠ Strip the DOCSTRING as well as the `#` comments. The function explains
    # at length that it used to read `code__iexact="residential"`, and prose
    # naming the bug is how the next reader learns not to reintroduce it — the
    # same distinction `_enumerations_in` makes below. Only EXECUTABLE lines
    # are the subject here.
    head, _marker, rest = body.partition('"""')
    docstring, _marker, tail = rest.partition('"""')
    code = "\n".join(
        line
        for line in (head + tail).splitlines()
        if not line.strip().startswith("#")
    )
    assert not re.search(r'["\']residential["\']', code), (
        "the portal seam names the home class as a literal again"
    )


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE GUARD — one check worth more than the four fixes above
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **WHY A GUARD AT ALL.** The four fixes are correct today. `BR-CUS-094a` will
# not be the last ruling to move this list, and the failure mode is silent every
# time: a hand-typed vocabulary does not raise, it just quietly omits a utility's
# own customers from a tax, a bill layout or a deposit quote. `DEF-738` was
# exactly this, one ruling earlier, and it survived two days with a check
# pointed straight at it.
#
# ⚠ **AND WHAT IT CANNOT SEE IS DECLARED WITH A NUMBER.** Hard-won law 7: *"a
# declared blind spot with no NUMBER attached is indistinguishable from an empty
# one"*. Every file this guard skips is named below with the reason, and
# `test_the_guard_states_its_blind_spot_with_a_number` asserts the size of each
# category — so a file quietly joining a skip list goes RED.

#: ── THE VOCABULARIES THIS GUARD KNOWS, AND WHY THERE ARE TWO ──────────────
#:
#: ⚠ **THE SAME DISEASE WAS FOUND THREE TIMES ON 2026-09-17, IN THREE
#: VOCABULARIES, BY THREE DIFFERENT PEOPLE.** The PO found it in account types;
#: this lane found it in bill-template categories; and a sibling found the
#: Add-units form reading a hardcoded five-string array while the backend read
#: the tenant's `unit_types` table (`DEF-MET-5656`). A guard written for ONE
#: table would have missed two of the three, so it is written for the SHAPE —
#: *a seeded, tenant-extensible lookup vocabulary written into our own source* —
#: and `unit_types` is here as the second case that proves it.
_VOCABULARY = frozenset(
    {
        # `account_types` — BR-CUS-094's seven, its legacy code, and the two
        # spellings that are NOT codes and exist only as mistakes: `govt`
        # (billing's, removed by this lane) and `government` used as if current.
        "residential",
        "commercial",
        "industrial",
        "agricultural",
        "institutional",
        "municipal",
        "builder_developer",
        "government",
        "govt",
        # `unit_types` — BR-MET-084's seeded five. It OVERLAPS the list above on
        # `residential` and `commercial`, which is a coincidence of English and
        # not a relationship; `metering/services.UNIT_TYPES` is the owner and is
        # forgiven by name below so nobody "fixes" it into the wrong table.
        "residential_submetered",
        "commercial_master",
        "common_area",
    }
)

#: TWO distinct codes inside one three-line window is an enumeration.
#:
#: ⚠ **TWO AND NOT THREE, AND THE DIFFERENCE IS A REAL DEFECT.** The nearest
#: existing check — `test_def_738_tax_customer_classes.py::test_def738_rating_
#: holds_no_hand_typed_copy_of_the_vocabulary` — uses THREE, and at three
#: `apps/notifications/rule_catalog.py`'s `PLAN_CLASSES = ("all", "residential",
#: "commercial")` is INVISIBLE: it offers TWO of the seven classes and the guard
#: written to catch exactly that shape cannot see it. A threshold is a blind
#: spot wearing a number.
_WINDOW = 2
_THRESHOLD = 2

#: ── WHAT THIS GUARD DELIBERATELY DOES NOT FLAG, EACH WITH ITS REASON ───────
#: A bare word in prose is not an enumeration, so comment lines are stripped
#: before scanning. These are the remaining files, and every one is named. The
#: key is `<tree>:<path>`, so a file cannot be forgiven in the wrong tree.
_ALLOWED: dict[str, str] = {
    # ══ BACKEND ══════════════════════════════════════════════════════════
    # ── the OWNERS. A vocabulary has to be written down exactly once. ────
    "backend:customers/models.py": (
        "`AccountType.SEVEN_CATEGORIES` / `LEGACY_CODES` — this IS the "
        "declaration every other module now reads. Flagging it would be asking "
        "the list to have no home."
    ),
    "backend:metering/services.py": (
        "`UNIT_TYPES` is the UNIT-type vocabulary's OWNER (`BR-MET-084`) and "
        "collides with the account-type list on two English words by "
        "coincidence. `_resolve_unit_type` beside it is the pattern every fix "
        "in this lane copied. ⚠ Named so the next reader does not 'fix' it into "
        "the wrong table."
    ),
    # ── SAMPLE DATA. A demo utility is entitled to pick concrete classes. ─
    "backend:customers/sample_data.py": (
        "the seeded demo utility's own accounts. Sample data names concrete "
        "codes the way a real utility's data does; it offers nothing to a clerk."
    ),
    "backend:rating/sample_data.py": (
        "the seeded demo plans. Same reason — `plan_class == 'commercial'` is a "
        "fact about the demo fixture, not a vocabulary offered on a screen."
    ),
    # ── REAL BUGS, DEFERRED BY SCOPE, EACH WITH ITS FILED ROW. ───────────
    "backend:customers/services.py": (
        "`DEF-CUS-5664` — `SEED_ACCOUNT_TYPES` is a STALE FOUR — it seeds "
        "residential, commercial, industrial, government and is missing all "
        "four codes BR-CUS-094 added in 2026-08. A REAL defect, not an "
        "exemption; the table is being made tenant-owned by a sibling lane and "
        "this list is theirs to move. Filed rather than fixed here."
    ),
    "backend:notifications/template_models.py": (
        "`DEF-NOT-5663` — spells the fourth category `government` where billing "
        "spelt it `govt` and the ratified code is `municipal`. A REAL defect; "
        "`notifications/` is held by another lane. Filed rather than fixed here."
    ),
    "backend:notifications/rule_catalog.py": (
        "`DEF-NOT-5662` — `PLAN_CLASSES` offers TWO of the seven classes to a "
        "notification rule, so a rule can never be written for an industrial or "
        "agricultural customer. A REAL defect; `notifications/` is held by "
        "another lane. Filed rather than fixed here."
    ),
    # ══ FRONTEND ═════════════════════════════════════════════════════════
    # ⚠ **THE FRONT END IS SCANNED FROM 2026-09-17 AND IT IS WHERE THIS BITES
    # HARDEST** — a hardcoded array there is what a clerk SEES, so a class the
    # utility added is simply not in the dropdown, with a green backend behind
    # it. Every entry below is BASELINED, never excused: the list may shrink and
    # a NEW offender goes red.
    "frontend:api/endpoints.ts": (
        "`TAX_CUSTOMER_CLASSES` is a DELIBERATE mirror and the reason is a money "
        "one: `[]` means EVERY class, so a wizard that fetched the catalogue and "
        "failed would save a tax applying to everybody. A static list cannot do "
        "that. It is held equal to the backend by `test_def738_the_frontend_"
        "mirror_is_the_same_list_in_the_same_order`, which is the check that "
        "makes the mirror safe. NOT a defect."
    ),
    "frontend:api/notificationRuleEndpoints.ts": (
        "`DEF-NOT-5662`'s front-end half — the same two-of-seven list the "
        "notification rule catalogue offers. Held by another lane."
    ),
    "frontend:features/metering/AddPremisesWizard.tsx": (
        "⚠ `DEF-MET-5656` — the Add-units form's unit-type dropdown reads a "
        "hardcoded five-string array while the backend reads the tenant's "
        "`unit_types` table, so a type the utility added is not offered. **This "
        "is the THIRD independent sighting of this lane's disease and it was "
        "found by a sibling, not by this guard — which is exactly why the "
        "front end is scanned from today.** Held by that lane."
    ),
    "frontend:features/metering/UnitsListPage.tsx": (
        "`DEF-MET-5656`'s second site — the same unit-type list again, on the "
        "list screen's filter. Held by the metering lane."
    ),
    "frontend:features/notifications/TemplateCatalog.tsx": (
        "`DEF-NOT-5663`'s front-end half — the four template categories typed "
        "out. Held by the notifications lane."
    ),
    "frontend:features/notifications/TemplateDetail.tsx": (
        "`DEF-NOT-5663`'s second front-end site. ⚠ ALREADY RED INDEPENDENTLY — "
        "`test_def_684_category_vocabulary.py::test_def_684__the_legacy_code_is_"
        "written_down_by_no_screen` fails on this exact file and was failing "
        "before this lane started (verified against the tip). Held by that lane."
    ),
}

#: The blind spot, counted. Each number is asserted, so a file joining one of
#: these categories cannot do it quietly.
_BLIND_SPOT_CENSUS = {
    "owner_declaration": 2,
    "sample_data": 2,
    "deliberate_frontend_mirror": 1,
    "real_defects_deferred": 8,
}

#: Whole TREES this guard does not walk, with the reason each is legitimate.
#: Counted in the same census so "we do not look there" is a number too.
_UNSCANNED_TREES = {
    "06-backend/apps/*/migrations/": (
        "a migration is a historical record of what the schema WAS. Its "
        "literals are frozen on purpose and rewriting one rewrites history."
    ),
    "06-backend/tests/ and *.test.ts(x)": (
        "a test names concrete codes to assert on them — that is what a test IS."
    ),
    "04-docs/ and 12-governance/": (
        "prose and registers quote codes by name, which is how a person reads "
        "them."
    ),
}


def _enumerations_in(text: str) -> list[tuple[int, list[str]]]:
    """Every window of `_WINDOW`+1 lines holding `_THRESHOLD`+ distinct codes.

    Comment lines are stripped first — Python `#`, and JS/TS `//` and `*` — for
    the reason the docstrings in this lane make necessary: they quote `govt` and
    `government` by name to explain why they are wrong, and prose naming a
    mistake is how the next reader learns not to repeat it. Quoted string
    literals only: a bare word in a sentence is not an enumeration.
    """
    seen: list[tuple[int, set[str]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(("#", "//", "*")):
            continue
        codes = {m for m in re.findall(r'["\']([a-z_]+)["\']', line) if m in _VOCABULARY}
        if codes:
            seen.append((number, codes))
    out = []
    for index, (start, _codes) in enumerate(seen):
        window: set[str] = set()
        for number, codes in seen[index:]:
            if number - start > _WINDOW:
                break
            window |= codes
        if len(window) >= _THRESHOLD:
            out.append((start, sorted(window)))
    return out


#: The two trees walked, and what counts as a production file in each.
_TREES = {
    "backend": ("06-backend/apps", ("*.py",)),
    "frontend": ("07-frontend/src", ("*.ts", "*.tsx")),
}


def _is_production(path: Path, tree: str) -> bool:
    text = path.as_posix()
    if "/migrations/" in text or "/node_modules/" in text:
        return False
    # A test names concrete codes in order to assert on them — that is what a
    # test IS, and flagging one would make the guard argue with its own suite.
    return not re.search(r"\.(test|spec)\.[tj]sx?$", text) and not path.name.startswith("test_")


def _scan() -> tuple[dict[str, tuple[int, list[str]]], dict[str, int]]:
    """Every offending file across both trees, keyed `<tree>:<path>`."""
    offenders: dict[str, tuple[int, list[str]]] = {}
    scanned: dict[str, int] = {}
    for tree, (rel, globs) in _TREES.items():
        root = REPO_ROOT / rel
        count = 0
        for pattern in globs:
            for path in sorted(root.rglob(pattern)):
                if not _is_production(path, tree):
                    continue
                count += 1
                found = _enumerations_in(path.read_text(encoding="utf-8", errors="ignore"))
                if found:
                    offenders[f"{tree}:{path.relative_to(root).as_posix()}"] = found[0]
        scanned[tree] = count
    return offenders, scanned


def test_no_module_names_an_account_type_code_as_a_literal():
    """⚠ **THE ONE CHECK THAT OUTLIVES THIS LANE.**

    A utility may define its own account types, so any module that writes the
    list of account types into its own source is a module that utility's own
    customers do not exist in. This walks every production module and refuses a
    new one.
    """
    offenders, scanned = _scan()
    unexpected = {path: hit for path, hit in offenders.items() if path not in _ALLOWED}
    assert unexpected == {}, (
        f"{len(unexpected)} file(s) write a tenant-extensible lookup vocabulary down. "
        f"`account_types` is owned by `customers.AccountType` and read through "
        f"`rating.seams.selectable_account_type_codes()`, "
        f"`billing.template_models.categories()` or "
        f"`portal…customers_seam.home_account_type_id()`; `unit_types` is owned by "
        f"`metering.services` and read through `_resolve_unit_type`. A typed copy cannot "
        f"notice a ruling, which is BR-CUS-094a exactly — and on a SCREEN it is worse, "
        f"because the class the utility added is simply missing from the dropdown with a "
        f"green backend behind it (DEF-MET-5656). Scanned "
        f"{scanned['backend']} backend + {scanned['frontend']} frontend files. "
        f"Found: {unexpected}"
    )


def test_the_guard_states_its_blind_spot_with_a_number():
    """⚠ **HARD-WON LAW 7 — a declared blind spot with no NUMBER attached is

    indistinguishable from an empty one.** This asserts the SIZE of what the
    guard above forgives, so a file cannot quietly join the allow list, and it
    prints the census beside the scan so a reader can tell pass from fail
    without reading an exit code.
    """
    offenders, scanned = _scan()
    still_allowed = sorted(path for path in _ALLOWED if path in offenders)
    print(
        f"\nlookup-vocabulary literal guard — CHECKED {scanned['backend']} backend "
        f"modules under 06-backend/apps and {scanned['frontend']} front-end sources "
        f"under 07-frontend/src (migrations, node_modules and tests excluded).\n"
        f"  flagged and forgiven : {len(still_allowed)} -> {still_allowed}\n"
        f"  allow entries now stale (no longer flagged): "
        f"{sorted(set(_ALLOWED) - set(offenders))}\n"
        f"  trees NOT walked at all: {len(_UNSCANNED_TREES)} -> {sorted(_UNSCANNED_TREES)}\n"
        f"  of the forgiven, REAL DEFECTS deferred to other lanes: "
        f"{_BLIND_SPOT_CENSUS['real_defects_deferred']}"
    )
    assert sum(_BLIND_SPOT_CENSUS.values()) == len(_ALLOWED), (
        "the census and the allow list disagree — one was edited without the other"
    )
    # ⚠ An allow entry that is no longer flagged is DEAD and must be deleted:
    # a forgiveness nobody needs is how the next real offender gets forgiven.
    assert set(_ALLOWED) <= set(offenders), (
        "these allow entries no longer match anything and must be removed: "
        f"{sorted(set(_ALLOWED) - set(offenders))}"
    )


def test_the_literal_guard_goes_red_on_the_code_it_was_written_for():
    """⚠ **THE GUARD RE-PROVES ITSELF RED ON EVERY RUN, not once at birth.**

    Hard-won law 7 says prove a guard red before trusting it green — and its own
    2026-09-05 addendum says *"a red proof at birth says nothing about whether
    anyone ever reads it again"*. So the pre-fix text is kept here verbatim and
    the scanner is run over it every time. If someone weakens the scanner, this
    goes red immediately rather than the guard silently forgiving everything.

    This is `apps/billing/template_models.py` as it stood at `2b1619b0f` — the
    four constants this lane removed, `govt` among them.
    """
    pre_fix = (
        'CATEGORY_RESIDENTIAL = "residential"\n'
        'CATEGORY_COMMERCIAL = "commercial"\n'
        'CATEGORY_INDUSTRIAL = "industrial"\n'
        'CATEGORY_GOVT = "govt"\n'
    )
    assert _enumerations_in(pre_fix), "the guard cannot see the code it was written for"

    # And the shape the THREE-code threshold misses — notifications' two-of-seven.
    two_of_seven = 'PLAN_CLASSES = (PLAN_CLASS_ALL, "residential", "commercial")\n'
    assert _enumerations_in(two_of_seven), "the guard cannot see a two-code enumeration"

    # ⚠ AND THE SECOND VOCABULARY, WHICH IS THE CASE THIS GUARD DID NOT FIND.
    # `DEF-MET-5656` — the Add-units form's unit-type dropdown, found by a
    # sibling lane on the same day and in TypeScript, not Python. It is here
    # verbatim because a guard proved only against the bug its author already
    # knew about is a guard proved against nothing.
    add_units_form = (
        'const UNIT_TYPES = ["residential", "residential_submetered",\n'
        '  "commercial", "commercial_master", "common_area"];\n'
    )
    assert _enumerations_in(add_units_form), (
        "the guard cannot see a hardcoded unit-type array — DEF-MET-5656"
    )

    # ⚠ AND A `//` COMMENT IS PROSE TOO, or scanning TypeScript turns every
    # explanatory line into a failure and the next lane disables the guard.
    js_prose = '// residential and commercial are the two the old list offered\n'
    assert not _enumerations_in(js_prose), "the guard fires on a JS comment"

    # ⚠ AND IT MUST NOT FIRE ON PROSE — the false pass this check exists to
    # deny is a scanner so eager that every lane disables it.
    prose = '# `govt` is not a real code; the ratified ones are residential and municipal\n'
    assert not _enumerations_in(prose), "the guard fires on a comment, which makes it noise"
