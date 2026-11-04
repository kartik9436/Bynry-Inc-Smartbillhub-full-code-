# ── Trace ──────────────────────────────────────────────
# Change:  CR-138-BRC07 `P4.6` — **no new table.** Moving the Refunds tab is a
#          ROUTE change: model, service and API are already in `apps/payments`.
# Rules:   B2 §2 (a module owns its tables; cross-module writes are forbidden)
#          · B8 layering · CLAUDE.md hard-won law 1 (a comment claiming a
#          guarantee is not the guarantee — so this is a test, not a sentence
#          in the CR).
# ───────────────────────────────────────────────────────
"""**`P4.6` IS A PROOF, NOT A MIGRATION** — and this file is the proof.

`P4.6` says the Refunds tab moving to `/finance/refunds` needs no table,
because everything about a refund already lives in `apps/payments`. That is
the kind of claim hard-won law 1 is about: *a comment claiming a guarantee is
not the guarantee.* A CR row saying "no new table" is worth nothing; a check
that goes RED the day somebody adds one is worth something.

WHAT WAS ESTABLISHED, and each line below asserts one of them:

  **model**      `apps.payments.models.Refund`, `db_table = "refunds"` — the
                 ONLY model in the whole backend mapped to that table.
  **migration**  `payments/0006_w4_reversal_and_refunds.py` creates it, and no
                 other app's migrations create, alter or drop it.
  **service**    `apps/payments/refunds.py` — raise, approve, issue, clear,
                 void. Five verbs, one module.
  **API**        `apps/payments/refunds_api.py`, mounted once from
                 `config/urls.py`. Six routes, no other app declares one.
  **the tab**    `07-frontend/src/features/payments/paymentsShared.tsx` holds
                 `REFUNDS_ROUTE` as a single constant, so moving the tab is
                 changing one string.

⚠ **AND THE CREDIT HALF OF `P4.25` NEEDS NO TABLE EITHER**, which is the only
part of this that could have been a surprise: the one list that shows refunds
AND credits unions payments' `refunds` with **billing's existing
`credit_notes`** through `apps/payments/billing_seam.py`. Two modules, two
number series, two tables that both already exist.

⚠ **WHAT THIS DOES NOT PROVE, said because an undeclared blind spot is
indistinguishable from an empty one:** it does not prove the tab move is
SAFE or that the old address redirects — `P4.10` and `P4.21` own those and
both are HELD until phase 2's Counter screens land. It proves only that no
schema change is owed.

RED-PROVED FIRST (hard-won law 7): adding a second model with
`db_table = "refunds"` in another app makes `test_one_model_owns_the_table`
fail by naming it; declaring a refund route in `apps/ledger` makes
`test_one_module_serves_every_refund_route` fail.
"""

import pathlib

from django.apps import apps as django_apps

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def test_one_model_owns_the_table():
    """Exactly one model maps to `refunds`, and it is payments'."""
    owners = [
        f"{model._meta.app_label}.{model.__name__}"
        for model in django_apps.get_models()
        if model._meta.db_table == "refunds"
    ]
    assert owners == ["payments.Refund"], f"more than one model claims `refunds`: {owners}"


def test_no_other_app_migrates_the_table():
    """Only payments' migrations touch `refunds` as a TABLE.

    ⚠ The search is for the table name in an `operations` context, not for the
    word "refund" — several other apps' migrations mention refunds in a
    docstring or a lane report, and matching those would make this check
    permanently red for the wrong reason (hard-won law 7: what would make this
    FAIL wrongly is as important as what would make it pass wrongly).
    """
    offenders = []
    for path in sorted(BACKEND.glob("apps/*/migrations/*.py")):
        if path.parts[-3] == "payments":
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ('name="Refund"', "name='Refund'", 'db_table": "refunds"'):
            if marker in text:
                offenders.append(f"{path.relative_to(REPO)} ({marker})")
    assert offenders == [], f"another app migrates the refunds table: {offenders}"


def test_the_service_and_the_api_live_in_payments():
    assert (BACKEND / "apps/payments/refunds.py").is_file()
    assert (BACKEND / "apps/payments/refunds_api.py").is_file()
    for app in ("billing", "ledger", "customers", "tenancy"):
        assert not (BACKEND / f"apps/{app}/refunds.py").is_file()
        assert not (BACKEND / f"apps/{app}/refunds_api.py").is_file()


def test_one_module_serves_every_refund_route():
    """Six routes, one file, mounted once."""
    urls = (BACKEND / "config/urls.py").read_text(encoding="utf-8")
    assert 'include("apps.payments.refunds_api")' in urls

    declared = (BACKEND / "apps/payments/refunds_api.py").read_text(encoding="utf-8")
    assert 'path("refunds"' in declared

    offenders = []
    for path in sorted(BACKEND.glob("apps/*/*.py")):
        if path.parts[-2] == "payments":
            continue
        text = path.read_text(encoding="utf-8")
        if 'path("refunds' in text or "path('refunds" in text:
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"another module declares a refund route: {offenders}"


def test_the_tab_is_one_string_in_one_file():
    """`P4.10` is a ROUTE change, so the route must be a single constant.

    ⚠ It is NOT edited here. `P4.10` is HELD until phase 2's Counter screens
    land, precisely because phase 2 is editing this same file right now and two
    lanes writing one file is how law 11's revert-by-subtraction happens. This
    asserts the move is one string when it comes.
    """
    shared = (REPO / "07-frontend/src/features/payments/paymentsShared.tsx").read_text(
        encoding="utf-8"
    )
    assert shared.count('export const REFUNDS_ROUTE = "') == 1

    literals = []
    for path in sorted((REPO / "07-frontend/src").rglob("*.tsx")):
        if path.name == "paymentsShared.tsx" or ".test." in path.name:
            continue
        if '"/finance/refunds"' in path.read_text(encoding="utf-8"):
            literals.append(str(path.relative_to(REPO)))
    assert literals == [], f"the refunds address is written out again in: {literals}"


def test_the_credit_half_needs_no_table_either():
    """`P4.25`'s union is payments' `refunds` + billing's existing `CreditNote`."""
    owners = {
        model._meta.db_table: f"{model._meta.app_label}.{model.__name__}"
        for model in django_apps.get_models()
        if model._meta.db_table in ("refunds", "credit_notes")
    }
    assert owners == {"refunds": "payments.Refund", "credit_notes": "billing.CreditNote"}
