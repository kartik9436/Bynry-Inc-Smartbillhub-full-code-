# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 — two defects the PO reported from the live
#           deployment at v2.291.0, fixed together because they are the same
#           screen and the same file.
# Defects:  DEF-INT-5622 (the one-account-at-a-time API is built, tested and
#           INVISIBLE — no `served_path`, so no row, so the connector screen
#           shows four APIs where five exist) ·
#           DEF-INT-5623 (the partner surface calls an account a customer in
#           three places while every VALUE is the account's) ·
#           DEF-INT-5642 (found while fixing 5623: `shapes.BY_CONNECTOR` named
#           no connector a partner can hold a key for, so the InvoiceCloud
#           dialect was dead on every real call)
# Rules:    PO 2026-09-16 *"Customers = accounts"* · PO 2026-09-17 *"it should
#           be account and not customer"* and *"this apis is not visiable in
#           invoice cloud"* · BR-INT-037 (a dialect is DATA, never a branch;
#           `G77`) · BR-INT-044 (one refusal, in words AND in timing) ·
#           CLAUDE.md hard-won law 2 and its mirror (a live capability with no
#           door) · law 7 (proved RED first, in the harness that runs it)
# Tests:    this file
# Impacts:  apps/integrations/manifests/pay_invoicecloud_partner.py ·
#           manifests/erp_aclarian.py · partner_api.py · partner_urls.py ·
#           shapes.py · 07-frontend/src/i18n/locales/*.json (eleven)
# ───────────────────────────────────────────────────────
"""The two defects, asserted where they were actually wrong.

**WHY A FILE OF ITS OWN RATHER THAN CASES IN `test_cr111_invoice_cloud.py`.**
The sibling file proves what the Invoice Cloud WAVE built. These cases prove
what the PO SAW and could not do: count five APIs on a screen, and read the
word *account* on a partner payload. They are about the join between a
manifest, a route, a catalogue and a dialect — four files that were each
internally right — so they belong where a reader looking for *why does the
screen say four* will find them.

**WHAT WOULD MAKE EVERY CASE HERE PASS WRONGLY**, written down because law 7
says a check you cannot describe a false pass for is one you do not
understand:

* `test_the_connector_screen_draws_a_row_for_every_address` would pass on a
  manifest that declared a fifth operation with no route behind it — a row for
  a door that opens on nothing. So it walks the OTHER way too: every partner
  address that serves a payload must be named by an operation.
* `test_the_partner_reads_account_not_customer` would pass on a shape nobody
  resolves, which is exactly the state `DEF-INT-5642` was. So it asks
  `shapes.resolve` for the connector key a REAL call carries rather than
  reaching for `INVOICE_CLOUD` by name.
* the catalogue case would pass if the manifest alone moved, because a
  manifest label is only the English fallback. So it reads the catalogues.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from apps.integrations import partner_api, partner_urls, shapes
from apps.integrations.manifests import MANIFESTS
from apps.integrations.registry import REGISTRY

INVOICE_CLOUD_PARTNER = "pay_invoicecloud_partner"
ACLARIAN = "erp_aclarian"

_LOCALES = (
    pathlib.Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "i18n"
    / "locales"
)
#: The eleven the product ships (`10-scripts/i18n_fanin.py` owns this list).
LANGS = ("en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR")


# ══════════════════════════════════════════════════════════════════════════
# DEF-INT-5622 — a built capability with no door out of the screen
# ══════════════════════════════════════════════════════════════════════════


def test_consumer_info_declares_its_own_address_so_it_draws_a_row() -> None:
    """PO 2026-09-17: *"this apis is not visiable in invoice cloud"*.

    The connector screen renders one row per operation and puts
    `Operation.served_path` under its name. `consumer-info` was built, routed
    and covered by tests, and declared by no manifest — so it was ABSENT
    rather than refused, and an absence is invisible to every check this repo
    has.
    """
    manifest = REGISTRY.require(INVOICE_CLOUD_PARTNER)
    by_path = {one.served_path: one.name for one in manifest.operations}
    assert "/partner/v1/consumer-info" in by_path, (
        "the one-account-at-a-time address names no path, so it draws no row "
        "and a clerk counting APIs sees four of five (DEF-INT-5622)"
    )
    # ⚠ **SIX SINCE 2026-09-24, AND THE SIXTH IS NOT A READ.** This read `== 5`
    # and went RED naming this manifest when `record_payment` was declared —
    # which is the assertion doing its job: an exact count is what makes a new
    # row on a clerk's connector screen a thing somebody has to write down.
    # **It is moved deliberately and never widened into `>= 5`**, for the same
    # reason `test_be_default_authentication.py` gives about its own exact
    # list: a count that cannot go red is a count nobody reads.
    #
    # `POST /partner/v1/make-payment/` lets Invoice Cloud post us a payment a
    # customer made on their portal (PO 2026-09-18, *"they post to us daily"*;
    # the design confirmed 2026-09-24). It draws a SIXTH row, labelled *Take a
    # payment* beside five that say *Read* — which is the whole point of it
    # being its own operation: the tick that grants it is the tick that lets a
    # key create money, and a clerk can see which one it is.
    assert len(manifest.operations) == 6
    assert by_path["/partner/v1/make-payment/"] == "record_payment", (
        "the write must draw a row of its own; folded onto a read's tick, a clerk "
        "granting *read accounts* would silently be granting *take a payment*"
    )


def test_the_connector_screen_draws_a_row_for_every_address_that_serves() -> None:
    """⚠ **BOTH DIRECTIONS, BECAUSE ONE OF THEM IS THE DEFECT AND THE OTHER IS
    THE OBVIOUS WRONG FIX.**

    Forwards: every operation that names a path has a route behind it, or the
    screen offers a door that opens on nothing. Backwards: every address that
    SERVES a payload is named by some operation, or it is invisible — which is
    what `consumer-info` was and what `DEF-INT-5586` was for `bill-download`
    one week earlier. The same shape twice is what makes it worth a standing
    check rather than a fix.
    """
    declared = {
        one.served_path
        for manifest in MANIFESTS
        for one in manifest.operations
        if one.served_path
    }
    routed = {f"/{partner_api.PARTNER_PREFIX}/{name}" for name in partner_urls.PARTNER_ROUTES}
    # A declared path may carry a trailing slash (Invoice Cloud's document
    # writes `bill-download/` that way) and the route table holds the bare
    # segment, so compare on the stripped form.
    assert {one.rstrip("/") for one in declared} <= {one.rstrip("/") for one in routed}, (
        "a manifest offers an address with no route behind it"
    )

    retired = {f"/{partner_api.PARTNER_PREFIX}/{one}" for one in partner_api.RETIRED_FOR}
    serving = {
        f"/{partner_api.PARTNER_PREFIX}/{name}"
        for name in partner_api.SERVED_ROUTES
    }
    unnamed = sorted(
        one for one in serving
        if one.rstrip("/") not in {two.rstrip("/") for two in declared}
        and one not in retired
    )
    assert unnamed == [], (
        f"{unnamed} serves a payload and no manifest names it, so it draws no "
        "row on any connector screen and nobody can discover it (DEF-INT-5622)"
    )


def test_the_two_account_addresses_are_two_operations_and_not_one() -> None:
    """⚠ **THIS IS THE REVERSAL, AND WHY IT IS SAFER RATHER THAN LOOSER.**

    `CR-111-BRC04` hung `consumer-info` on `serve_customer` so that a clerk who
    switched the account list off switched this off too. That property was
    real. Its price was that the address could not be SEEN. Two operations give
    the clerk the property back in a stronger form — two rows, two ticks — and
    the detail payload carries `remote_plan_id` and `opening_balance`, which
    the list deliberately does not, so they are genuinely different
    permissions.
    """
    assert partner_api.SERVED_ROUTES["accounts"][0] == "serve_customer"
    assert partner_api.SERVED_ROUTES["consumer-info"][0] == "serve_consumer_info"
    assert (
        partner_api.SERVED_ROUTES["accounts"][0]
        != partner_api.SERVED_ROUTES["consumer-info"][0]
    ), "one tick silently governing two addresses is what DEF-INT-5622 cost"

    from apps.integrations import machine_auth

    offered = machine_auth.callable_operations(REGISTRY.require(INVOICE_CLOUD_PARTNER))
    assert "serve_consumer_info" in offered, (
        "a clerk cannot grant a key the permission, so the row would be a "
        "control that does nothing (hard-won law 2)"
    )
    # ⚠ **AND NO OTHER PARTNER DECLARES IT**, which is the consequence recorded
    # rather than discovered later: an ERP key cannot reach `consumer-info`.
    # That is correct — the address is out of Invoice Cloud's document and
    # appears in no ERP's — and it is stated here so a lane meeting a refused
    # Aclarian key finds the reason instead of filing it as a bug.
    declaring = sorted(
        manifest.key
        for manifest in MANIFESTS
        for one in manifest.operations
        if one.name == "serve_consumer_info"
    )
    assert declaring == [INVOICE_CLOUD_PARTNER], declaring


# ══════════════════════════════════════════════════════════════════════════
# DEF-INT-5623 — the word on the screen, in the address and on the wire
# ══════════════════════════════════════════════════════════════════════════


def test_the_address_says_accounts() -> None:
    """PO 2026-09-17: *"it should be account and not customer - theya re
    lookung for details for accounts not customer id"*.

    ⚠ **ONE ROUTE TABLE, SO EVERY PARTNER'S PATH MOVED TOGETHER.**
    `partner_urls.PARTNER_ROUTES` is shared, so `/partner/v1/accounts` could
    not be renamed for InvoiceCloud and left as `/partner/v1/customers` for
    Aclarian without giving one thing two names.
    """
    assert "accounts" in partner_urls.PARTNER_ROUTES
    for key in (INVOICE_CLOUD_PARTNER, ACLARIAN):
        paths = {one.name: one.served_path for one in REGISTRY.require(key).operations}
        assert paths["serve_customer"] == "/partner/v1/accounts", key


def test_the_old_address_is_retired_and_names_its_replacement() -> None:
    """⚠ **A `404` HERE IS THIS SURFACE'S REFUSAL — THE SAME FIVE WORDS A
    STOLEN KEY GETS.** So deleting the old address outright would have told a
    partner holding yesterday's document that their KEY was bad and sent their
    engineer to look at their credentials. `410` names the replacement.

    Five `live` ERP manifests share this route table and the connector the PO
    looked at is only one of them, which is why the mechanism was used rather
    than the address simply dropped.
    """
    assert partner_api.RETIRED_FOR["customers"] == "/partner/v1/accounts"
    assert partner_urls.PARTNER_ROUTES["customers"] is partner_api.partner_customers_retired
    # It is registered in the LOOP, so it gets `_with_utility_from_key` and can
    # authenticate at all — a retirement notice still has to.
    spellings = {str(one.pattern) for one in partner_urls.urlpatterns}
    assert "partner/v1/customers" in spellings
    assert "partner/v1/customers/" in spellings


def test_the_partner_reads_account_not_customer() -> None:
    """The KEYS on the wire, asked for the way a real call asks.

    ⚠ **IT RESOLVES THE SHAPE FROM THE CONNECTOR KEY RATHER THAN NAMING
    `INVOICE_CLOUD`, AND THAT IS THE POINT.** Reaching for the shape by name
    passes even when nothing resolves to it, which is exactly the state
    `DEF-INT-5642` found: `BY_CONNECTOR` held `erp_invoicecloud` (a manifest
    that does not exist) and `pay_invoicecloud` (the card half, which is never
    a partner caller), so every real InvoiceCloud call got `NATIVE`.
    """
    assert INVOICE_CLOUD_PARTNER in partner_api.partner_provider_keys()
    shape = shapes.resolve(INVOICE_CLOUD_PARTNER)
    assert shape is shapes.INVOICE_CLOUD, (
        "the connector whose key InvoiceCloud presents resolves to our own "
        "dialect, so every rename in shapes.INVOICE_CLOUD is dead (DEF-INT-5642)"
    )

    record = {
        "id": "A-10432",
        "consumer_no": "A-10432",
        "customer_name": "Marisol Ruiz",
        "phone": "512-555-0134",
    }
    out = shapes.apply_record(record, shape, resource="customers")
    assert out["account_no"] == "A-10432"
    assert out["account_name"] == "Marisol Ruiz"
    assert "consumer_no" not in out and "customer_name" not in out, (
        "a partner reading `consumer_no` maps it to THEIR customer record, and "
        "this product has a separate customers table where a landlord is one "
        "row and fourteen accounts (DEF-INT-5623)"
    )


def test_the_seam_keeps_our_own_words_and_no_other_partner_moved() -> None:
    """⚠ **THE HALF THAT WAS DELIBERATELY NOT DONE, ASSERTED SO IT STAYS
    DELIBERATE.** A `Shape` is one partner's dialect (`BR-INT-037`), so this
    fix touched no route and no other connector. The seam goes on serving
    `consumer_no` to the five ERPs — **which means the seam itself still holds
    a partner's word where our own column is `account_no`.** That is filed, not
    fixed here: moving it changes what five `live` connectors receive.
    """
    assert shapes.resolve(ACLARIAN) is shapes.NATIVE
    native = shapes.apply_record(
        {"consumer_no": "A-10432"}, shapes.NATIVE, resource="customers"
    )
    assert native == {"consumer_no": "A-10432"}


@pytest.mark.parametrize("lang", LANGS)
def test_the_catalogue_says_accounts_in_every_language(lang: str) -> None:
    """⚠ **THE CATALOGUE WINS OVER THE MANIFEST ON SCREEN**, so a lane that
    changed only the manifest changed nothing a clerk sees. B14 rule 35: each
    catalogue is written in its own idiom, never translated word for word from
    English — and rule 33 caps a LABEL at three words.
    """
    catalogue = json.loads((_LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
    stem = f"integrations.provider.{INVOICE_CLOUD_PARTNER}.operation"
    listed = catalogue[f"{stem}.serve_customer"]
    one = catalogue[f"{stem}.serve_consumer_info"]
    assert listed.strip() and one.strip()
    assert listed != one, "two rows on one screen reading the same words"
    if lang == "en":
        assert listed == "Read accounts"
        assert one == "Read one account"
    else:
        for word in ("customer", "Customer", "client", "Client"):
            assert word not in listed, (lang, listed)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 — DEF-INT-5622 + DEF-INT-5623 (PO, live deployment)
# generated: 2026-09-17 by the DEF-INT-5622/5623 lane
# checklist: A✔ B=n/a(no screen code — the row is drawn from the manifest) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_def_int_5622_5623_account_vocabulary.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
