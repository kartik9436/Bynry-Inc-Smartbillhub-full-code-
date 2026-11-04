# CR-174-BRC10 — US Payments (Prime): the three calls they make to us, built on the "USPayments" card, posting the moment they arrive

**Raised:** 2026-10-07 by the Product Owner, in chat (a specification titled *"US Payments (Prime) — What SmartBillHub Must Build"*, plus rulings D1–D4).
**Status:** **BUILT — 2.560.0, 2026-10-07 (lane US-PAY).** 🔒 human review pending (`09-human-review-ledger.md`, row of 2026-10-07).
**Branch:** `claude/charming-pascal-k7i2lr` (`BRC10`, this branch's suffix since `CR-171-BRC10`). `10-scripts/allocate.py cr` answered **174** against the remote and `--verify 174` reported it free on every branch at allocation.
**Classification (`13-change-process.md` §1):** a **CHANGE** — a utility cannot today take a payment from US Payments' kiosks, call centre, web or phone channels: the card is a coming-soon outward card processor and the kiosk door lands a payment without posting it. It **touches money** (a payment is recorded and a returned payment reversed inside the call), **idempotency** (two 🔒 duplicate keys), **a payments migration** (a new nullable column for the bank's return code and a fourth payment origin) and **the machine path to a reversal**. Every such file ships HUMAN-REVIEW-PENDING with a row in `12-governance/09-human-review-ledger.md`.

## 0 · What arrived, in the requester's words (verbatim)

The full rulings are the decision-log row of 2026-10-07 that starts *"PO RULINGS — US PAYMENTS (PRIME)"*. Only the PO's own words are repeated here.

| | The PO, verbatim |
|---|---|
| D1 — post on arrival | *"(a). A person standing at a machine needs the live balance. Runbooks still handle the exceptions in D2."* |
| D2 — an account we cannot find | *"this will nothappen; becuase they will ask for account and outstanding first before they display on screen - so they will be displaying what we send - user cannot type their account- user will search there account on kiosk, koisk will call our apis to find that account - at this stage if account is wrong we will return no such acount found and payment will not proceed; hence this situaiton will not come"* |
| D3 — not Ann Arbor's | *"no; thUS payment is generleal integration we are doing and nothing to do with Ann arbor"* |
| D4 — which card | *"US payment card - use it"* |

The specification's essentials, as supplied: they call us and we never call them; three operations — **Account Lookup** (`GET ?accountId=`, read only), **Payment Notification** (`POST`), **Return Notification** (`POST`); the credential is the `password` header (the key we issue), `username` optional, `enterpriseId` / `companyId` optional and, when sent, must match the credential's utility; **200 = accepted, 409 = duplicate, anything else = retry with the identical body**; duplicates keyed per utility on `us_payments` + `paymentId` and `us_payments_return` + `paymentId`, never expiring; `accountId` an exact string (letters, digits, hyphen, up to 50, leading zeros kept); `paymentId` a 64-bit integer; amounts USD to two decimals; times RFC 3339 UTC; an unknown method or channel becomes *Other* and is never refused; a return carries an optional Nacha `returnCode`.

## 1 · What is reversed, and what is NOT (step 2)

- **`BR-INT-058` / `OQ-INT-1729` (a) — *"the door stops after dedupe"*** — is SUPERSEDED **for US Payments only** by D1. The kiosk card (`payments_kiosk`) was not ruled and still applies nothing; its boundary test stays.
- **`BR-INT-054` — the lookup answers no balance** — is SUPERSEDED for US Payments only by D1 (*"A person standing at a machine needs the live balance"*).
- **`manifests/pay_uspayments.py`'s four outward coming-soon operations** (`deliver_charge`, `deliver_card_page`, `fetch_settlement`, `deliver_refund`) leave the card (D4; the reasoning is the coordinator's reading recorded in the D4 row).
- **NOT reversed:** the New World filter (`origin = webhook`) is unchanged (D3); `/partner/v1/receipts` and the New World file are byte-identical; `REVERSAL_REASONS` stays the closed four-word set; `reverse_payment`'s Admin-only gate for a PERSON is unchanged.

## 2 · What is built

**The three addresses a utility hands to US Payments** — the same three for every utility (`{host}` is our API host), since `DEF-INT-10020` (2.561.5, §5 below):

    GET  https://{host}/api/partner/v1/account-lookup?accountId=…
    POST https://{host}/api/partner/v1/add-payment
    POST https://{host}/api/partner/v1/add-return

with the key from *Generate a key* in the `password` header, exactly as issued (no `Bearer`); `username` is a label and is not checked. The key names the utility, so nothing in the address does.

⚠ **AS BUILT IN 2.560.0 THESE READ `https://{host}/api/{utility}/integrations/inbound/pay_uspayments/{account_lookup|payments|returns}`** — an address US Payments cannot call, because it sends no utility and no connector name in any URL. Superseded the same day by the PO's ruling (decision log 2026-10-07, *"go - for USPayments partner API URL Fix"*); that address now refuses these three operations.

| Surface | What changed |
|---|---|
| `manifests/pay_uspayments.py` | the card is LIVE; four outward coming-soon operations gone; three inbound operations, each declaring what it applies (`Operation.applies`), its HTTP verb and its partner's field names (`Operation.wire`); `password` header; `enterpriseId` / `companyId` checked against two optional fields (`Auth.identity_headers`); the `tender` vocabulary with `OTHER` as fallback and eight suggestions |
| `registry.py` | `applies`, `http_method`, `wire`, `identity_headers`, `Vocabulary.fallback` / `suggested`, each validated at load by name |
| `inbound.py` / `inbound_api.py` | the apply door: verb and identity checked after authentication; lookup answered from the one balance read; payment and return landed and posted in ONE transaction; 409 decided by the unique index (PostgreSQL 16 proof); run row per call with no account, amount or header on it; System Admin alert for D2's residue and for a third early return |
| `payments/agent_door.py` (new) | `account_position`, `post_payment` (record_payment, cleared, oldest-first, overpay as credit, key `agent\|pay_uspayments:<id>\|payment`), `post_return` (reverse_payment, key `…\|return`, bank code stored) |
| `payments/account_balance.py` (new) | the portal's balance read MOVED here (portal seam delegates); adds the signed `balance`, `credit_position`, `past_due` |
| `payments/0049` | `return_code`, `channel`, `terminal`; origin `agent` |
| `reversal.py` · `services.py` · `idempotency.py` | `return_code`; `channel` / `terminal`; `SOURCE_AGENT` |
| `services.py` / `mappings.py` (integrations) | switching on refused while `OTHER` is unmapped; suggestions applied on connect |
| Screens | *Map their words →* on the connector page and the set-up page; the payment page's Source line shows *Payment agent · Kiosk · 4471* and a reversing row *Bank code R01*; **Payment agent** in the Source filter; eleven catalogues |

**What a System Admin does to switch it on:** Settings → Connectors → USPayments → *Map their words →* → map **OTHER** to the utility's own catch-all method (create one on Reference data → Payment methods if it has none) → back → *Connect* → optionally type US Payments' source addresses, enterprise ID and company ID → *Save and test* → *Generate a key* and hand it to US Payments with the three addresses. Words left red record under OTHER until mapped.

**What DevOps must do (not in the product):** serve the API host over **TLS 1.2 or higher** with a **certificate chain from a public CA** (US Payments will not accept a private or self-signed chain); obtain **US Payments' source IP addresses** and either type them in the connection's *Allowed addresses* or enforce them at the edge (both is fine); make sure the reverse proxy forwards the real client address the way `TRUSTED_PROXY_COUNT` expects, or the allowlist reads the proxy's address; never log request headers at the edge (the credential is a header).

## 3 · What the build decided rather than asked (law 13)

Decision log 2026-10-07, *"CR-174-BRC10 (LANE JUDGMENTS)"*, J1–J8: a fourth origin `agent` (J1) · the Nacha code in its own column, R01/R09 → NSF, others → bank chargeback (J2) · channel and machine as columns (J3) · cleared on arrival (J4) · an early return answers 503 (J5) · the System Admin told on the third early return, and at once for D2's residue (J6) · the tender vocabulary reused, OTHER required before switching on (J7) · landing and money in one transaction (J8).

## 4 · Build record

| Step | Commit | Version |
|---|---|---|
| CR reserved | `85976295f` | — |
| backend + screens + tests | `9f75253bf` | — |
| connector page door, CHANGELOG, record | this commit | **2.560.0** |

Tests: `tests/test_cr174_us_payments.py` 26 on SQLite + the concurrent-duplicate case on PostgreSQL 16; with `test_us_int_044_inbound_door.py` and `test_cr060_c21_webhooks.py`, **65 passed on PostgreSQL 16**. Proved RED: without the one transaction, a failed post kept its landing row and the resend was answered `409` (`assert 409 == 503`). Browser walk at 1440/1280 and the curl transcript: `scratchpad/po-shots/uspayments/README.md`.

**Rollback:** redeploy 2.559.1 and reverse `payments/0049`; the reverse refuses while any payment carries origin `agent` — roll forward instead once US Payments money is posted.

**Left open / not this lane:** the returned-payment fee and customer notice (Runbook 26) — an R01 return does queue the existing *payment failed* letter where the utility has it switched on, because that is what the existing reversal does for NSF; the risk flag and refund flows; US Payments' real source addresses and enterprise / company IDs (theirs to give).

## 5 · `DEF-INT-10020` — the three addresses move to `/api/partner/v1/` (2.561.5, maintenance)

**The PO's report, 2026-10-07:** US Payments identifies the utility only by the key in its `password` header and sends no utility and no vendor name in any URL, so the per-utility address in §2 as first built could not be reached. **Ruling, verbatim:** *"go - for USPayments partner API URL Fix"* (decision log, the row starting *"PO RULING — US PAYMENTS MOVES TO THREE PARTNER ADDRESSES"*), under the 2026-09-16 rule — no utility and no vendor in any partner URL; the key names the utility.

**Was:** `https://{host}/api/{utility}/integrations/inbound/pay_uspayments/{account_lookup|payments|returns}`.
**Now:** `GET https://{host}/api/partner/v1/account-lookup?accountId=…` · `POST https://{host}/api/partner/v1/add-payment` · `POST https://{host}/api/partner/v1/add-return` (each also with a trailing `/`). The same three for every utility.

| Surface | What changed |
|---|---|
| `manifests/pay_uspayments.py` | each operation declares its address as `served_path`; docstring names the three addresses, the was/now and the key-directory repair |
| `partner_urls.py` | routes for every inbound operation that applies and declares a `/partner/v1/` address are BUILT from the manifest; the key reader is per route — these read the manifest's header (`password`), every other route still reads `Authorization: Bearer` |
| `inbound_api.py` | the door body is shared (`_serve`); `partner_door_for` is the view at the new addresses (one verb each); an operation with a `served_path` is refused at the old address and the refusal is logged with where it moved; `published_key_schemes` names the `password` header for the contract |
| `addressing.py` | a door we publish is shown with `/api` in front (`OUR_API_ROOT`) — on every partner card, since `/partner/v1/…` answers nothing |
| `management/commands/check_key_directory.py` (new) | lists live issued keys with no `integration_key_directory` row; read-only; `--fix` writes them through `key_directory.record` |
| `core/openapi.py` · `openapi/schema.json` | six addresses published with a `passwordHeader` scheme |
| `07-endpoints.md` | row 25a |

**Unchanged:** every check behind the door — live key, `enterpriseId` / `companyId` when sent, allowed addresses, rate limits, tender mapping, `409` on a repeated `paymentId`, `apps/payments/agent_door.py` saving the money; `GET /api/partner/v1/payments`; `make-payment`; the generic kiosk's address.

**Proof:** `tests/test_def_int_10020_uspayments_partner_addresses.py` — 18 cases through `django.test.Client` at the real addresses with no utility opened by the test (two utilities, same account number, each key reaches only its own; wrong / unknown / no key / right key as Bearer / revoked key → one refusal, byte-identical, each ≥ the 40 ms floor; a utility named in the query, body or a header is ignored; the old address refuses; `username` never checked; the card shows the three). Red first, on the tip before the change: 11 failed, 2 errors, 3 passed of the first 16 (`Resolver404` for every new address; no command); the 3 that passed were the two Bearer-unchanged cases and the issued-key directory row, which are meant to pass both before and after. `test_cr174_us_payments.py` now calls the new addresses. On PostgreSQL 16: **92 passed** across the new file, `test_cr174_us_payments.py` (including two identical payments at the same instant → one `200`, one `409`), `test_def_pay_10015_agent_payment_page.py`, `test_cr110_partner_tenant_from_key.py` and `test_us_int_044_inbound_door.py`, plus one red that was already red on the tip (below). Local curl walk and the card at 1440: `po-shots/uspayments-urls/`.

**Reds seen that this lane did not cause — each run on the untouched tip `b6741034f` and red there too:** `test_cr110_partner_tenant_from_key::test_partner_api_registers_none_of_the_five_itself` (asserts `PARTNER_ROUTES == 8`; it is 10 since `make-payment`, `dd7915c6d`, 2026-09-24) · `test_be_default_authentication` × 2 · `test_us_int_013_registry::…coming_soon_cards_carry_their_wave_label` · `test_cr110_connectors::…no_new_connector_declares_a_mapping` (`gis_esri`) · `test_be11_openapi::tc02` (the public list, at an assertion after this lane's new ones, which pass).

**What DevOps must do:** deploy 2.561.5 (no migration, no setting); run `python manage.py check_key_directory` once on the deployed database and, if it lists a US Payments key, either re-issue the key on the card or run it again with `--fix`; make sure the proxy passes the `password` and `username` headers through unchanged (a header named `password` is unusual and some proxies strip it); the TLS 1.2 floor, public certificate chain and US Payments' source addresses in §2 still stand.

**Rollback:** redeploy 2.561.4. No migration. US Payments would then be unreachable again; nothing it posted meanwhile is affected.
