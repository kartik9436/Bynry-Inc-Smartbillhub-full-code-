# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-684 — the New account, Move-in and Common-areas screens still
#          offered the SUPERSEDED four customer categories, `government`
#          included, after BR-CUS-094 expanded the signed vocabulary to seven
#          and made `government` legacy
# Rules:   BR-CUS-094 (PO 2026-08-24, "Expand the signed list to seven";
#          `government` LEGACY — unselectable on new records, lawful
#          everywhere else) · B2 r5 #12 [D5] (the SIGNED four this supersedes) ·
#          hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Files:   apps/customers/models.py :: AccountType.SEVEN_CATEGORIES /
#          LEGACY_CODES · 07-frontend/src/features/customers/customersShared.tsx
#          · NewAccountWizard.tsx · MoveInWizard.tsx · AccountsListPage.tsx ·
#          07-frontend/src/features/metering/CommonAreasTab.tsx
# ───────────────────────────────────────────────────────
"""DEF-684 — the check that did not exist: a frontend vocabulary, read against
the backend's.

**The defect.** `customersShared.ACCOUNT_CATEGORIES` was a four-code tuple —
`residential · commercial · industrial · government` — and it was RIGHT when it
was written: B2 r5 #12 [D5] signs exactly those four and calls `account_types` a
platform table, so typing them into the client was the platform catalogue rather
than a guess about tenant data. **BR-CUS-094 (PO 2026-08-24) then moved the fact
under it**: seven selectable codes, and `government` marked LEGACY — *"it stops
being selectable on any form"*. The tuple became one code short in one direction
and one refused code long in the other, and four screens read it.

**Why nothing caught it, in the words of the register:** *"No gate compares a
frontend constant against a backend vocabulary, so tsc, eslint and every screen
test pass on a list that is one code short of correct in one direction and one
refused code long in the other."* It was found because a lane was told to COPY
ACC-03's control — copying it as instructed would have put the superseded
vocabulary into a fifth screen.

**So this file is that comparison**, and it lives in the backend because this is
the only process that can open both trees at once.

⚠ **THE GATE FOR THIS ALREADY EXISTS AND HELD ONE ROW.**
`10-scripts/gates/g22_picker_vocabulary.py` is literally *"a picker offers the
vocabulary its endpoint accepts"*, written from DEF-114 for this exact failure
shape — and it says outright that it *"does NOT claim to discover pickers by
itself"*: its register (`picker_endpoint_pairs.json`) holds ONE pair, and the
account-category picker was never in it. Registering it is the right home for
this check and is **blocked on DEF-736** — G22's live probe asserts the ids the
picker serves are ids the writer ACCEPTS, and `POST /accounts` still accepts a
legacy code this picker no longer offers, so the pair would be registered around
a hole. File the register row with DEF-736's fix; until then, this file is the
comparison. Three things it pins:

  1 · **No production frontend file enumerates the vocabulary.** A picker reads
      `GET /service-requests/categories`; the platform table is the only place a
      category is written down. The scan is by CONTENT, not by symbol name, so
      renaming the tuple does not evade it.
  2 · **`government` is offered by nothing.** The legacy code may be filtered,
      stored and priced; it may not be an OPTION.
  3 · **The one literal category code left in the frontend — S18's default — is
      one of the seven**, checked against the model rather than trusted.

⚠ **AND FOUR SECOND SITES OF THE SAME SUPERSEDED FOUR WERE PINNED AS BROKEN**,
under `xfail(strict=True)`, because each belonged to a module this lane did not
own and each was a real gap rather than a tidy-up. A strict xfail is the honest
shape: it goes RED the day someone fixes one (delete the marker, keep the
assertion) and it goes RED the day the vocabulary moves again. Silence would
have been the same mistake DEF-684 is.

**THREE ARE STILL PINNED; ONE IS CLOSED.** The rating site — `DEF-738`, the tax
wizard's restrict-to control and the vocabulary rating validates it against —
was fixed on **2026-08-30**: its marker is deleted and its assertion kept, which
is the shape this paragraph promised. The other three stand.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.notifications import template_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "07-frontend" / "src"

#: BR-CUS-094's seven selectable codes plus the one it retires. Read from the
#: MODEL, never re-typed: a list typed here would be the defect wearing a lab
#: coat.
SELECTABLE = tuple(code for code, _name in customer_models.AccountType.SEVEN_CATEGORIES)
LEGACY = customer_models.AccountType.LEGACY_CODES
VOCABULARY = frozenset(SELECTABLE) | frozenset(LEGACY)

#: The superseded four (B2 r5 #12 [D5]). Named so the assertions below can say
#: *this exact list* rather than *three or more of them*.
SUPERSEDED_FOUR = ("residential", "commercial", "industrial", "government")

#: How close two code literals must be to count as ONE enumeration. A tuple, an
#: array and a `type X = "a" | "b"` union all fit inside ten lines; two
#: unrelated fixtures thirty lines apart do not.
WINDOW = 10

#: A file "enumerates the vocabulary" when three DISTINCT platform codes appear
#: within `WINDOW` lines of one another. Three, not four: the superseded tuple
#: minus one code is still a hardcoded vocabulary.
DISTINCT_CODES_THAT_MAKE_AN_ENUMERATION = 3

#: ⚠ **TEST FILES ARE EXEMPT AND PRODUCTION FILES ARE NOT.** A test fixture
#: naming three categories is a fixture; `ServiceRequestCapturePage.test.tsx`
#: deliberately invents codes precisely so a hardcoded list cannot satisfy it.
#: The catalogues are exempt because a locale file is where a NAME lives.
EXEMPT_SUFFIXES = (".test.tsx", ".test.ts", ".spec.tsx", ".spec.ts")
EXEMPT_DIRS = ("i18n/locales",)

#: ⛔ **THE SECOND SITES — REPORTED WITH DEF-684, NOT FIXED BY IT.** Each is the
#: superseded four in a module this lane does not own, each is pinned by an
#: `xfail(strict=True)` below, and each is listed here so the scan can be a
#: WHOLE-TREE scan instead of a customers-only one. **Deleting an entry is what
#: closing one of them looks like**; adding one requires a defect row first.
KNOWN_SECOND_SITES = {
    # `TAX_CUSTOMER_CLASSES` — **CLOSED 2026-08-30 (`DEF-738`), and the entry
    # STAYS, which is the one case where staying is not a deferral.** The list
    # is no longer the superseded four: it is all eight, in BR-CUS-094's ruling
    # order, and `apps/rating/services.TAX_CUSTOMER_CLASSES` is now DERIVED from
    # `customers.AccountType` rather than typed. It remains a written-down list
    # here because on THIS control an empty list means *every class*, so a
    # fetched catalogue that failed would silently widen a restricted tax to
    # everybody — the money reason is argued at the constant itself. A mirror
    # that nothing compares is what DEF-738 was, so it is compared, in order and
    # both directions, by `tests/test_def_738_tax_customer_classes.py`.
    "api/endpoints.ts",
    # `AUDIENCES` — BR-NOT-001's "four consumer categories" for a template
    # variant. A tenant with an agricultural account cannot write it a letter.
    "features/notifications/TemplateCatalog.tsx",
}


def _production_sources() -> list[Path]:
    out = []
    for path in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
        rel = path.relative_to(FRONTEND_SRC).as_posix()
        if any(rel.endswith(suffix) for suffix in EXEMPT_SUFFIXES):
            continue
        if any(part in rel for part in EXEMPT_DIRS):
            continue
        out.append(path)
    return out


def _enumerations(path: Path) -> list[tuple[int, list[str]]]:
    """Every window in `path` holding three or more distinct platform codes."""
    lines = path.read_text(encoding="utf-8").splitlines()
    hits: list[tuple[int, set[str]]] = []
    for number, line in enumerate(lines, start=1):
        found = {m for m in re.findall(r'"([a-z_]+)"', line) if m in VOCABULARY}
        if found:
            hits.append((number, found))
    found_windows = []
    for index, (start, _codes) in enumerate(hits):
        window: set[str] = set()
        for number, codes in hits[index:]:
            if number - start > WINDOW:
                break
            window |= codes
        if len(window) >= DISTINCT_CODES_THAT_MAKE_AN_ENUMERATION:
            found_windows.append((start, sorted(window)))
            break
    return found_windows


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE VOCABULARY IS THE MODEL'S, AND IT IS WHAT BR-CUS-094 RULED
# ══════════════════════════════════════════════════════════════════════════
def test_def_684__the_platform_vocabulary_is_seven_selectable_plus_one_legacy():
    """The fixed point everything below is measured against.

    If this row ever changes, every assertion in this file re-points itself —
    which is the difference between reading a vocabulary and re-typing one.
    """
    assert SELECTABLE == (
        "residential",
        "commercial",
        "industrial",
        "agricultural",
        "institutional",
        "municipal",
        "builder_developer",
    ), "BR-CUS-094's seven, in the ruling's own order — never alphabetical"
    assert LEGACY == ("government",)
    assert (
        "government" not in SELECTABLE
    ), "BR-CUS-094: `government` is not one of the seven and is never re-labelled"


# ══════════════════════════════════════════════════════════════════════════
# 2 · NO PRODUCTION FRONTEND FILE ENUMERATES IT — THE MISSING CHECK
# ══════════════════════════════════════════════════════════════════════════
def test_def_684__no_frontend_screen_hardcodes_the_category_vocabulary():
    """⚠ **THE CHECK DEF-684 WAS MISSING.**

    Scanned by CONTENT, so renaming `ACCOUNT_CATEGORIES` does not evade it, and
    a NEW hardcoded list in a fifth screen fails here on the day it is written
    rather than on the day a ruling makes it wrong.
    """
    offenders = {}
    for path in _production_sources():
        rel = path.relative_to(FRONTEND_SRC).as_posix()
        if rel in KNOWN_SECOND_SITES:
            continue
        found = _enumerations(path)
        if found:
            offenders[rel] = found
    assert offenders == {}, (
        "a frontend file enumerates the platform consumer categories. The "
        "catalogue is served by `GET /service-requests/categories` and read "
        "through `useAccountCategories` — a typed copy cannot notice a ruling, "
        f"which is DEF-684 exactly. Found: {offenders}"
    )


def test_def_684__the_deleted_tuple_has_not_come_back_by_name():
    """`ACCOUNT_CATEGORIES` is DELETED, not deprecated.

    The register's own prescription: *"delete `ACCOUNT_CATEGORIES` so a fourth
    screen cannot copy it"*. An exported constant left in place is an invitation
    with a comment on it.
    """
    for path in _production_sources():
        source = path.read_text(encoding="utf-8")
        assert (
            "export const ACCOUNT_CATEGORIES " not in source
        ), f"{path.relative_to(FRONTEND_SRC)} re-exports the tuple DEF-684 deleted"


def test_def_684__the_legacy_code_is_written_down_by_no_screen():
    """`government` may be stored, filtered and priced. It may not be TYPED.

    ⚠ **THE FIRST DRAFT OF THIS CHECK ASSERTED `value: "government"` AND WAS
    GREEN ON THE DEFECT.** The wizard never wrote that string: it mapped over a
    tuple, so the option was assembled at render and the literal the check
    looked for did not exist anywhere. A check whose output cannot tell pass
    from fail is worse than none, so it asks the answerable question instead —
    **does the code appear in production source at all** — which is red on the
    tuple, red on a `value:` literal, and red on the next spelling of either.

    A backticked `government` in prose is not a match, deliberately: DEF-684's
    own fix documents the retired code in half a dozen comments, and the
    `disconnects.CUT_WILL` posture says a retired spelling must stay quotable.
    """
    for path in _production_sources():
        rel = path.relative_to(FRONTEND_SRC).as_posix()
        if rel in KNOWN_SECOND_SITES:
            continue
        source = path.read_text(encoding="utf-8")
        for legacy in LEGACY:
            assert f'"{legacy}"' not in source, (
                f"{rel} writes the legacy category `{legacy}` down as a string. "
                "BR-CUS-094 retires it from every picker; the catalogue serves it "
                "on `legacy[]` for the surfaces that may still filter on it."
            )


def test_def_684__the_three_pickers_and_the_filter_read_the_served_catalogue():
    """Built is not wired (hard-won law 2), pointed at a data source.

    Deleting the tuple is only half the fix; each of the four surfaces has to
    read the endpoint. Named individually so a screen that quietly drops the
    control fails here rather than rendering nothing.
    """
    for rel in (
        "features/customers/NewAccountWizard.tsx",
        "features/customers/MoveInWizard.tsx",
        "features/customers/AccountsListPage.tsx",
        "features/metering/CommonAreasTab.tsx",
    ):
        source = (FRONTEND_SRC / rel).read_text(encoding="utf-8")
        assert "useAccountCategories" in source, f"{rel} does not read the served catalogue"


def test_def_684__s18s_default_category_is_one_of_the_seven():
    """The ONE category literal the frontend still holds, checked.

    `emptyCustomerForm()` needs a default and a default is not a vocabulary —
    but an unchecked default is how a retired code would ship as the value every
    new account starts on. This is the cross-stack pin its comment promises.
    """
    source = (FRONTEND_SRC / "features/customers/NewAccountWizard.tsx").read_text(encoding="utf-8")
    match = re.search(r'account_type: "([a-z_]+)"', source)
    assert match is not None, "S18's default category literal has moved or gone"
    default = match.group(1)
    assert default in SELECTABLE, (
        f"S18 starts every new account on `{default}`, which BR-CUS-094 does not "
        f"make selectable. The seven are {SELECTABLE}."
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE SECOND SITES — PINNED BROKEN, EACH IN ANOTHER LANE'S MODULE
# ══════════════════════════════════════════════════════════════════════════
# ✅ **CLOSED 2026-08-27 — DEF-736.** The pin below was `xfail(strict=True)` and
# is now a live assertion, which is the whole point of the strict form: the day
# the behaviour arrived it XPASSed and the suite went red until somebody closed
# the row. `services._resolve_account_type` now reads `legacy` and refuses by
# default, and the CUTOVER IMPORT is exempted EXPLICITLY — `_commit_import_row`
# passes `allow_legacy_type=True` and nothing else in the module does. Both
# halves are asserted, because closing only the first would have broken every
# utility's first upload, which is the failure BR-CUS-094 was written to avoid.
def test_def_684__post_accounts_refuses_a_legacy_category(brazos):
    """BR-CUS-094: *"unselectable on new records"* — on every door, not one."""
    with tenant_ctx(brazos):
        field_errors: list[dict] = []
        resolved = customer_services._resolve_account_type("government", field_errors)
        assert (
            resolved is None or field_errors
        ), "`POST /accounts` accepted the legacy category `government` for a NEW account"
        assert [e["message_key"] for e in field_errors] == [
            "customers.account.type_is_legacy"
        ], "the refusal must say the code is RETIRED, not that it is unknown"


def test_def_736__the_cutover_import_may_still_carry_a_legacy_category(brazos):
    """DEF-736's own capitalised warning, pinned so nobody closes the hole the
    wrong way: *"DO NOT close this by refusing every legacy code"*.

    BR-CUS-094 is explicit that every existing record keeps its code and keeps
    billing, and re-pointing is a human act per record (US-CUS-020's
    value-mapping step). A blanket refusal would fail the first bulk upload of
    every utility carrying `government` — the exact migration the rule was
    written to make painless.
    """
    with tenant_ctx(brazos):
        field_errors: list[dict] = []
        resolved = customer_services._resolve_account_type(
            "government", field_errors, allow_legacy=True
        )
        assert not field_errors, f"the cutover import was refused: {field_errors}"
        assert resolved is not None and resolved.code == "government"


def test_def_736__the_import_is_the_only_caller_that_asks_for_the_exemption():
    """A guard on the guard. `allow_legacy_type=True` appearing at a second call
    site is how this refusal quietly stops applying to a new door — so the
    number of places that ask for it is asserted, not trusted."""
    source = (
        Path(customer_services.__file__).read_text(encoding="utf-8")
    )
    asked = [
        line.strip()
        for line in source.splitlines()
        if "allow_legacy_type=True" in line
    ]
    assert len(asked) == 1, (
        "DEF-736's cutover exemption is passed from more than one place: "
        f"{asked}. It belongs to `_commit_import_row` alone."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-684 second site (customers backend, REPORTED not fixed): "
        "`services.SEED_ACCOUNT_TYPES` is still the superseded FOUR, so "
        "`ensure_account_types()` — the backfill that restores a deleted platform row — "
        "would (a) never restore Agricultural, Institutional, Municipal or "
        "Builder-developer, and (b) recreate `government` with `legacy` defaulted to False, "
        "silently un-retiring the code BR-CUS-094 retired. Migration 0019 got both halves "
        "right; this constant beside it did not move."
    ),
)
def test_def_684__the_platform_backfill_seeds_all_eight_with_government_legacy():
    seeded = {code for code, _name in customer_services.SEED_ACCOUNT_TYPES}
    assert seeded == set(SELECTABLE) | set(LEGACY)


# ✅ **CLOSED 2026-08-30 — `DEF-738`. THE MARKER IS DELETED AND THE ASSERTION
# KEPT**, which is what this file says closing a pinned second site looks like.
#
# **The rating site did not escape for want of a check; it escaped because a red
# check went unread.** `tests/test_def_273_tax_conditions.py::
# test_def273_the_class_vocabulary_mirrors_the_platform_account_types` compared
# `rating.TAX_CUSTOMER_CLASSES` against the LIVE `account_types` table and had
# been failing since BR-CUS-094's migration seeded the four new rows on
# 2026-08-24 — *"platform account_types are ['agricultural', 'builder_developer',
# … ] and rating mirrors ['commercial', 'government', 'industrial',
# 'residential']"*. Its own docstring predicted the failure and said what to do:
# *"a tax restricted to the old spelling now reaches NOBODY (fail-closed), which
# is safe and wrong. Update both, in the same commit."* Both halves were closed
# in one commit, as it asked. DEF-684 had no guard; DEF-738 had one and nobody
# looked — a distinction worth keeping, because the fixes are different.
#
# Nothing is duplicated here: this covers the FRONTEND mirror the tax wizard
# renders, and `tests/test_def_738_tax_customer_classes.py` pins it in ORDER and
# in both directions against the backend's derived vocabulary.
def test_def_684__the_tax_wizards_class_list_covers_all_seven():
    source = (FRONTEND_SRC / "api" / "endpoints.ts").read_text(encoding="utf-8")
    start = source.index("export const TAX_CUSTOMER_CLASSES")
    offered = set(re.findall(r'"([a-z_]+)"', source[start : start + 400]))
    assert offered >= set(SELECTABLE), (
        "the tax wizard's restrict-to control offers "
        f"{sorted(offered)} and BR-CUS-094 prices {sorted(SELECTABLE)}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-684 second site (notifications, REPORTED not fixed): "
        "`apps/notifications/template_models.CATEGORIES` is BR-NOT-001's 'four consumer "
        "categories', spelled as `account_types.code` — so a template variant cannot be "
        "written for an Agricultural, Institutional, Municipal or Builder-developer account, "
        "and every one of them falls to the `default` variant. BR-NOT-001 quotes the four "
        "verbatim, so widening it is a RULE change (HUMAN-GUIDE §6), not a lane's edit."
    ),
)
def test_def_684__a_template_variant_exists_for_each_of_the_seven():
    assert set(template_models.CATEGORIES) >= set(SELECTABLE)


# ── Trace footer ───────────────────────────────────────
# packet: DEF-684 · DEF-736 · DEF-737 · DEF-738 · DEF-739
#         (12-governance/10-defect-log.csv) · BR-CUS-094
#         (04-docs/05-modules/03-customers/02-business-rules.md) · B2 r5 #12 [D5]
# generated: 2026-08-26 by lane ACCTSTALE (the Accounts stale-copy sweep)
# gates: proved RED first (hard-won law 7) against the unpatched frontend —
#        `test_def_684__no_frontend_screen_hardcodes_the_category_vocabulary`
#        failed on `{'features/customers/customersShared.tsx': [(162, ['commercial',
#        'government', 'industrial', 'residential'])]}`, and the four
#        `xfail(strict=True)` pins all xfailed as written. ⚠ The legacy-code
#        check was GREEN on the defect in its first draft (it looked for a
#        `value: "government"` literal the mapped tuple never produced) and was
#        rewritten until it went red — hard-won law 7, and the reason DEF-182
#        is in CLAUDE.md.
# exceptions: THREE of the four second sites are still `xfail(strict=True)`
#        rather than fixed — `_resolve_account_type` and `SEED_ACCOUNT_TYPES` are
#        the customers write path with the cutover import behind them, and
#        `template_models.CATEGORIES` quotes BR-NOT-001 verbatim so widening it
#        needs a re-sign, not an edit. The fourth, `TAX_CUSTOMER_CLASSES`, was
#        CLOSED 2026-08-30 as `DEF-738`: rating's copy is derived from
#        `customers.AccountType` and the frontend mirror is pinned in order ·
#        the scan exempts `*.test.tsx` because a fixture naming three categories
#        is a fixture, and `ServiceRequestCapturePage.test.tsx` deliberately
#        invents codes so that no hardcoded list can satisfy it · `WINDOW = 10`
#        and three DISTINCT codes is the boundary that separates an enumeration
#        from two unrelated fixtures; it was measured against the whole tree
#        before it was written, and it found six sites, of which four are pinned
#        above and two were this lane's to fix
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
