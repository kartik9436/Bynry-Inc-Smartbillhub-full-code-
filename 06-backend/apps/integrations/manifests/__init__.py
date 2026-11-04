"""The THIRTY manifests: the blueprint's catalogue of 28, and two beside it.

⚠ **THE THIRTIETH IS `postmark`, ADDED 2026-09-17 (`CR-115-BRC05`), AND ROW 04
WAS RENAMED THE SAME DAY.** The blueprint draws one unnamed *Bulk email
service* at 04; the PO named two ESPs and both accounts exist, so 04 became
`sendgrid` (key and display name, from `email_bulk`) and `postmark` sits beside
it at 04b. **A rename is not an arrival** — only `postmark` moves
`CONNECTOR_COUNT`.

⚠ **THE TWENTY-NINTH IS `pay_invoicecloud_partner`, ADDED 2026-09-17, AND IT IS
THE FIRST ROW THE BLUEPRINT DOES NOT DRAW** (`CR-111-BRC04`, `DEF-INT-5574`).
The catalogue on p161–p162 numbers twenty-eight; this one is an addition the
drawing never made, so it carries `10b` rather than renumbering 11–28. It is
the READING half of InvoiceCloud — they hold a key we issued and collect
customers, bills, payments and bill documents — and it exists beside
`pay_invoicecloud` because a manifest declares ONE `auth.mode` and InvoiceCloud
runs in both directions. ⚠ **That pair is an accommodation of a product
limitation and not the target shape: `BR-INT-077` records what is owed.**

Adding a connector is adding ONE file here and ONE name to `MANIFESTS` below —
no screen, no endpoint, no migration. That is `BR-INT-037`, which the Product
Owner confirmed in their own words on 2026-09-16: *"So adding an API is data,
not code"*, in answer to *"are you creating 28 tables -in database?"*. **Five
tables serve all 28. A connector is a ROW, never a table**, and a twenty-ninth
next year adds no table, no column and no migration.

⚠ **EIGHTEEN BECAME TWENTY-EIGHT AND ONLY ONE OF THE TEN IS NEW FROM NOTHING**
(`CR-110-BRC04` wave C). The other thirteen additions came out of SPLITTING four
files we already had, which is the difference between *build fourteen
connectors* and *split four*:

| Was | Became |
|---|---|
| `payments_card` | `pay_invoicecloud` · `pay_paymentus` · `pay_uspayments` · `pay_worldpay` · `pay_globalpayments` |
| `gl_partner` | `erp_aclarian` · `erp_workday` · `erp_sap` · `erp_infor` · `erp_msgp` |
| `meters_mdm` | `meters_itron` · `meters_sensus` |
| `gis_city` | `gis_esri` — renamed only; fields, operations and adapter untouched |

and `meters_badger` (Badger BEACON) is the one built from nothing. Two display
names moved with the blueprint: *Text messages* → **Twilio**, *Water meter
cloud* → **Neptune 360**.

⚠ **THE ORDER IS THE GRID'S ORDER, AND IT IS NOW THE BLUEPRINT'S.** `US-INT-013`
§4's seed sequence ordered the first eighteen and the card grid draws
`REGISTRY.all()` as registered. The Integration Blueprint's catalogue (p161–p162)
numbers all twenty-eight, and under B14 rule 42 the drawing owns the layout, so
the sequence below is 01 to 28 as that catalogue draws it. **Moving a line here
moves a card on Settings for every tenant.**

⚠ **FOUR KEYS WERE RETIRED AND NOTHING WAS STRANDED — MEASURED, NOT ASSUMED.**
`payments_card`, `gl_partner`, `meters_mdm` and `gis_city` no longer exist. The
development database was read tenant by tenant under RLS on 2026-09-16: **12
connection rows across 4 tenants, none of them one of the four** (they are
`bank_lockbox_file`, `email_smtp` and `meters_neptune360`), and **0 rows in
`integration_credential`.** ⚠ An aggregate read WITHOUT `app.tenant_id` first
returned `(0 rows)` over those twelve — row-level security hides rows from a
`count(*)` exactly as it hides them from a `SELECT`, so a zero read that way
proves nothing.
"""

from apps.integrations import registry as _registry
from apps.integrations.manifests import (
    accounting_file,
    bank_lockbox_file,
    email_google,
    email_microsoft,
    email_smtp,
    erp_aclarian,
    erp_infor,
    erp_newworld,
    erp_msgp,
    erp_sap,
    erp_workday,
    geocoder_census,
    gis_esri,
    map_tiles_public,
    meters_badger,
    meters_itron,
    meters_neptune360,
    meters_sensus,
    pay_globalpayments,
    pay_invoicecloud,
    pay_invoicecloud_partner,
    pay_paymentus,
    pay_uspayments,
    pay_worldpay,
    payments_kiosk,
    payments_sandbox,
    postmark,
    print_vendor,
    sendgrid,
    sms_twilio,
    sso,
)

#: The blueprint's catalogue order, p161–p162, 01 to 28.
MANIFESTS: tuple[_registry.Manifest, ...] = (
    email_microsoft.MANIFEST,  # 01
    email_google.MANIFEST,  # 02
    email_smtp.MANIFEST,  # 03
    sendgrid.MANIFEST,  # 04 — was `email_bulk`; vendor named 2026-09-17
    # ── 04b · `CR-115-BRC05`, PO ruling 2026-09-17 ──────────────────────
    # ⚠ **THE THIRTIETH, AND IT IS NOT NUMBERED 29 OR 30.** The blueprint's
    # catalogue draws twenty-eight and numbers them 01 to 28; row 04 is
    # *"Bulk email service"*, ONE unnamed ESP. Two are now named and both
    # accounts exist, so which one a utility sends through is a choice per
    # utility — and a choice is two rows, not one row with a hidden setting.
    # It sits BESIDE its sibling for the same reason `pay_invoicecloud_partner`
    # does at 10b: this list is the order the grid draws, and two ESP cards a
    # page apart read as two unrelated connectors rather than as one decision.
    # Renumbering 05–28 would move every drawn number to record an addition the
    # drawing never made.
    #
    # ⚠ **UNLIKE 10b, THIS PAIR IS NOT A WORKAROUND.** `pay_invoicecloud_partner`
    # exists because `Manifest.auth` carries one mode and one partner needed two
    # (`BR-INT-077`, owed). These two are simply two vendors.
    postmark.MANIFEST,  # 04b — the second ESP, coming soon
    sms_twilio.MANIFEST,  # 05
    meters_neptune360.MANIFEST,  # 06
    meters_badger.MANIFEST,  # 07 — the one new from nothing
    meters_itron.MANIFEST,  # 08 — split from meters_mdm
    meters_sensus.MANIFEST,  # 09 — split from meters_mdm
    pay_invoicecloud.MANIFEST,  # 10 ── split from payments_card
    # ── 10b · `CR-111-BRC04` / `DEF-INT-5574`, PO ruling 2026-09-17 ──────
    # ⚠ **THE TWENTY-NINTH, AND IT IS NOT NUMBERED 29.** The blueprint's
    # catalogue draws twenty-eight and numbers them 01 to 28; this connector is
    # not in that drawing, so renumbering 11–28 to 12–29 would move every drawn
    # number to record an addition the drawing never made. It sits BESIDE its
    # sibling instead, because this list is the order the grid draws and the
    # PO's ruling is that *"Two rows in the list with the same company name -
    # this is correct"* — two rows a page apart would be two connectors a clerk
    # cannot see are one relationship.
    #
    # ⚠ **TWO ROWS IS A WORKAROUND, NOT THE DESIGN** (`BR-INT-077`). The PO
    # asked for ONE connector holding both credentials; `Manifest.auth` carries
    # one mode, so it cannot. See this file's own docstring and the decision log
    # of 2026-09-17 before reading the pair as an intention.
    pay_invoicecloud_partner.MANIFEST,  # 10b — the reading half, live
    pay_paymentus.MANIFEST,  # 11 ┐
    pay_uspayments.MANIFEST,  # 12 ├ split from payments_card
    pay_worldpay.MANIFEST,  # 13 │
    pay_globalpayments.MANIFEST,  # 14 ┘
    payments_kiosk.MANIFEST,  # 15
    payments_sandbox.MANIFEST,  # 16
    erp_aclarian.MANIFEST,  # 17 ┐ PO: "this is erp company aclarian"
    erp_workday.MANIFEST,  # 18 │
    erp_sap.MANIFEST,  # 19 ├ split from gl_partner
    erp_infor.MANIFEST,  # 20 │
    erp_msgp.MANIFEST,  # 21 ┘
    # ── `CR-132-BRC07` · A SIXTH ERP, AND A REAL CUSTOMER GOES LIVE ON IT ──
    # ⚠ **APPENDED AFTER THE FIVE `gl_partner` WAS SPLIT INTO, AND NOTHING IS
    # RENUMBERED.** It is not one of the blueprint's twenty-eight — the same
    # position `pay_invoicecloud_partner` and `postmark` are in — so the
    # catalogue's numbering stops being a sequence here and `CONNECTOR_COUNT`
    # below is what a reader should trust.
    erp_newworld.MANIFEST,  # 31 — Tyler New World / Logos
    accounting_file.MANIFEST,  # 22
    bank_lockbox_file.MANIFEST,  # 23
    print_vendor.MANIFEST,  # 24 — placeholder vendor, coming soon
    gis_esri.MANIFEST,  # 25 — renamed from gis_city
    geocoder_census.MANIFEST,  # 26
    map_tiles_public.MANIFEST,  # 27
    sso.MANIFEST,  # 28
)

#: What we ship, asserted where a reader will see it. A connector arriving or
#: leaving without this number moving is the thing
#: `tests/test_cr110_connectors.py` refuses.
#:
#: ⚠ **28 → 29 ON 2026-09-17, AND THE ONE CONNECTOR IS
#: `pay_invoicecloud_partner`** (`CR-111-BRC04`, `DEF-INT-5574`). It is the
#: first row that is NOT in the blueprint's catalogue of twenty-eight, so this
#: number has stopped being *what the blueprint draws* and is now *what we
#: ship*; the two were the same until today and the sentence above has been
#: changed rather than left to mislead.
#:
#: ⚠ **29 → 30 THE SAME DAY, AND THE ONE CONNECTOR IS `postmark`**
#: (`CR-115-BRC05`). The blueprint's row 04 is one unnamed ESP; two are named
#: now, so the catalogue of twenty-eight and what we ship have diverged by two
#: rather than by one. **`sendgrid` did NOT move this number** — it is row 04
#: renamed from `email_bulk`, not an arrival.
#: ⚠ **30 → 31 ON 2026-09-22, AND THE ONE CONNECTOR IS `erp_newworld`**
#: (`CR-132-BRC07`). A SIXTH named ERP, arriving the same way SAP did
#: mid-build: **one file, no migration, no screen code.** That is `BR-INT-037`
#: being true rather than claimed — the connection screen grows a card and two
#: API rows because a manifest is data.
CONNECTOR_COUNT = 31


def register_all(registry: _registry.Registry | None = None) -> _registry.Registry:
    """Register every manifest, in order, refusing the first bad one by name.

    Idempotent for the SAME declarations (the registry treats an identical
    re-registration as a no-op), so a test session and `ready()` can both call
    it. A different declaration under an existing key is refused.
    """
    target = registry if registry is not None else _registry.REGISTRY
    for manifest in MANIFESTS:
        target.register(manifest)
    return target
