# One-time bill redesign — API contract (2026-09-30)

Status: **CONTRACT FOR THE BUILD — API HALF BUILT 2026-09-30** (plan A1–A8, DB2, DB3;
`apps/billing/one_time_answer.py`, `one_time_send.py`, `api.py`; tests
`tests/test_otb_a_one_time_api_contract.py`). The backend (plan groups B, A, DB) and
the frontend (group F) both build to this file, so they can proceed in parallel.
**Where the build differs from or adds to the text below, it says so in a
*Built* note under the section** — read those before assuming a field.
Design: `11-one-time-bill-redesign.md` · plan: `12-one-time-bill-build-plan.md` ·
images: `05-prototype/one-time-bill-2026-09-30/`. Money travels as strings with 4
decimals and a `currency`; quantities always carry their unit (CLAUDE.md rules 2, 3).
Every clerk-facing sentence is a catalogue key plus params, never server prose.

## 1 · Account search (A1)

`GET /accounts?q=<text>&per=20` — the existing list. The dropdown uses `id`,
`account_no`, `name`, `premise`, `unit_label`, `status_name`,
`status_behavior_class`, `balance`, `balance_currency`. **No change** to the list;
the plan name and the cycle's days to pay come from §2's `account` block, which is
read once the clerk has picked.

**Built (2026-09-30, `DEF-BIL-8281`):** `GET /billing/one-time/accounts/{id}` answers
§2's `account` block from the ACCOUNT alone — plan (the unit's), `cycle_due_days`,
`last_bill_on`, `moved_in_on`, balance — the moment it is chosen, never waiting on
a preview (which refuses while a step-1 field is empty). It answers with
`moved_in_on: null` when none is recorded; everything else still fills.

## 2 · Preview (A2–A4) — `POST /billing/one-time/preview` (writes nothing)

### Request

```json
{
  "account_id": "uuid",
  "kind": "interim | first | final | backbill | penalty | fee",
  "period_start": "YYYY-MM-DD",            // interim, first, final
  "period_end": "YYYY-MM-DD",              // interim, first, final (final: move-out)
  "sub_periods": [{"period_start": "...", "period_end": "..."}],  // backbill, penalty
  "reason_code": "MISSED",                 // backbill, penalty — must be an ACTIVE row of reason_codes
  "charge_code": "RECON",                  // fee (required), penalty (optional)
  "bill_date": "YYYY-MM-DD",               // REQUIRED, every kind
  "due_days": 21,                          // REQUIRED, every kind; 0 is lawful
  "readings": [                            // optional: values typed but not yet saved, priced as provisional
    {"asset_id": "uuid", "read_at": "YYYY-MM-DD", "value": "488.4", "role": "current | move_in | last_period"}
  ]
}
```

### Refusal — ALL problems at once (A3)

`422`, code `VAL-FORMAT` or `BIZ-COMPLETENESS`, body `field_errors` lists **every**
problem found in one pass, each with the field it belongs to and its own key:

```json
{"field_errors": [
  {"field": "sub_periods[1].period_end", "code": "VAL-003", "message_key": "billing.oneTime.err.periodEndsBeforeStart"},
  {"field": "reason_code", "code": "VAL-001", "message_key": "billing.oneTime.err.reasonRequired"},
  {"field": "due_days", "code": "VAL-001", "message_key": "billing.oneTime.err.dueDaysRequired"}
]}
```
Keys (≤ 6 words each, B14 rule 33): `periodEndsBeforeStart` "Ends before it starts." ·
`periodRequired` "Enter the period." · `reasonRequired` "Choose a reason." ·
`reasonUnknown` "Choose a reason from the list." · `chargeRequired` "Choose a charge code." ·
`billDateRequired` "Enter the bill date." · `dueDaysRequired` "Enter days to pay." ·
`dueDaysInvalid` "Enter whole days, zero or more." · `accountRequired` "Choose an account." ·
`notFirstBill` "Move-in is outside this period." · `moveInReadingRequired` "Enter the move-in reading."
A refusal from pricing (a real setup error: two base codes, no price for a size, no rate
version) keeps a named key and names the service: `billing.oneTime.err.<reason>`
with `{service}`. The generic `billing.run.refused` is never used on this route.

### Answer

```json
{
  "kind": "interim",
  "account": {"id": "...", "account_no": "AC-2026-00042", "name": "Maria Alvarez",
              "address": "1408 Elm St · Unit A", "plan": "Residential Standard",
              "status_name": "Active", "balance": "142.1800", "currency": "USD",
              "cycle_due_days": 21, "last_bill_on": "2026-08-31", "moved_in_on": "2026-09-12"},
  "defaults": {"bill_date": "2026-09-30", "due_days": 21},
  "due_date": "2026-10-21",
  "services": [
    {"service": "water", "assets": [{"asset_id": "...", "label": "W-10442"}, {"asset_id": "...", "label": "W-10443"}],
     "status": "billed | follows_basis | not_in_service | not_taken | billed_base_zero",
     "basis_service": null, "count": 2, "on_bill": "per_meter_lines"}
  ],
  "rates": [
    {"service": "water", "asset_id": "...", "asset_label": "W-10442",
     "rate_type": "tiered | flat | per_asset | percent_of_service | time_of_use | demand | capacity",
     "usage_rate": {"tiers": [{"up_to": "5.000000", "unit": "kgal", "price": "3.2500"}, {"up_to": null, "unit": "kgal", "price": "4.5000"}]},
     "base_charge": {"amount": "8.0000", "code": "BASE-W", "set": true, "per_asset": false, "prorated": null},
     "minimum": null, "versions": [{"label": "Water v4", "from": "2026-08-15"}],
     "amount": "29.2000"}
  ],
  "readings": {
    "needed": "every_meter | move_in_and_new | final | last_period | none",
    "rows": [{"asset_id": "...", "label": "W-10442", "unit": "kgal",
              "previous": {"value": "482.3", "read_at": "2026-08-31", "on_file": true},
              "current": {"value": null, "read_at": "2026-09-30", "fixed_date": false},
              "usage": null, "status": "waiting | accepted | refused | estimated | assessed | actual",
              "refusal_key": null, "period_index": null}]
  },
  "periods": [{"period_start": "...", "period_end": "...", "days": 30,
               "versions": ["Water v3", "Electric v7"], "reading": "actual | estimated | assessed",
               "split_on": "2026-08-15"}],
  "move_in_charges": {"moved_in_on": "2026-09-12", "deposit_asked": "150.0000", "deposit_paid": "0.0000",
                      "lines": [{"kind": "deposit", "label": "Security deposit", "amount": "150.0000"},
                                {"kind": "fee", "code": "CONN", "label": "Connection charge", "amount": "45.0000"}]},
  "settlement": {"this_bill": "...", "prior_balance": "...", "deposit": "...", "interest": "...",
                 "remainder": "...", "automatic": "write_off | refund | null",
                 "paths": ["collect", "payment_plan", "transfer"]},
  "charge": {"code": "RECON", "label": "Reconnection fee", "amount": "75.0000", "taxable": true},
  "bill": {
    "groups": [{"label": "Sep 1 – Sep 30", "period_start": "...", "period_end": "...", "subtotal": "...",
                "lines": [{"service": "water", "asset_label": "W-10442", "charge": "usage | base | per_asset | percent | deposit | fee | minimum | discount",
                           "quantity": "6.1", "unit": "kgal", "rate": "tiered | 3.2500", "amount": "21.2000",
                           "flags": ["estimated", "base_not_set"]}]}],
    "subtotal": "...", "tax": [{"label": "Utility tax", "rate": "2.000000", "amount": "..."}],
    "total": "...", "currency": "USD"
  },
  "warnings": [{"key": "billing.oneTime.warn.baseNotSet", "params": {"service": "Electric"}},
               {"key": "billing.oneTime.warn.noAgreements", "params": {}}],
  "duplicate": null
}
```
**Built (2026-09-30):**
- **`bill.lines` for a counted service and a minimum** (2.411.3). A counted service
  (trash, fire) is ONE line, `charge: "per_asset"`, its quantity the count and its
  unit the service's (2 carts at $18.00 = one `36.0000` line) — PO *"per service"*,
  `DEF-BIL-8151`. A per-service minimum is its own `charge: "minimum"` line carrying
  the `asset_label` of the meter it tops up (meter B `$6.00` + `$4.00` minimum) —
  PO *"consider them 2 lines anc charge"*, `DEF-BIL-8150`.
- **The one tolerated problem.** When the ONLY problem is an empty `due_days`, the
  preview still answers `200` — with `account`, `defaults.due_days` (the cycle's) and
  `due_date: null` — and carries that one problem as `field_errors` in the body, because
  the screen prefills Days to pay from `defaults`. The DRAFT refuses it (`422`).
- **A first bill's `period_start` IS its move-in date, as the clerk left it** (PO
  change 2026-09-30, *"Move -date should have date picker cleark will overwrite
  it"*): the screen pre-fills it from `accounts.opened_at`, the preview and the
  draft price from the request's date (deposit and connection charge still
  apply), the account's recorded date is never written, and `notFirstBill` is no
  longer raised. An empty one on a first bill is `billing.oneTime.err.moveInRequired`.
- **Two catch-up / penalty periods that share a day** are `billing.oneTime.err.
  periodOverlaps` on the later row's `period_start` (`DEF-BIL-8322`); periods are
  taken in date order whatever order they were typed in.
- **The request also takes** `settlement_path` (final: `collect | payment_plan |
  transfer`), `evidence` (penalty, text) and `note` (fee). Only the draft uses them
  (§6); the preview prices nothing from them.
- **A pricing refusal** is `422 BIZ-COMPLETENESS` with rating's own clerk key where the
  refusal carries one, else `billing.oneTime.err.notPriced` `{service, service_code,
  reason}` ("{service} can't be priced. Check its rates."), else — when no service can
  be named — `billing.oneTime.refused`. Never `billing.run.refused`.
- **`bill.groups[].label`** is a DATE group (`period_start`/`period_end` set) or a
  stable code — `charges` (fee), `move_in_charges` (first bill's deposit and
  connection charge), `other_charges` (any other fee line) — translated by the screen
  from `billing.oneTimeBill.bill.group.<code>`.
- **`services[].on_bill`** is `usage_and_base | per_asset_lines | percent_line |
  no_line` (the screen reads the status, not this).
- **`rates`** carries a `rate_type: null`, `amount: "0.0000"` row for every service
  `not_in_service` (design §4 *No rate used*). `versions[].from` is `null`: the label
  (`rating.tariff_version_labels`) already names the date it took effect.
- **`readings.rows[].previous`** falls back to the current read's own `prior_value`
  (with its `days_since_prior` date) when the meter's earlier read was never loaded as
  a row of its own. A typed-not-saved value in `readings` is ECHOED on its row and
  **priced as PROVISIONAL by the preview** (`DEF-BIL-8300`, 2026-09-30 — this note
  read *"not priced"* until then, and step 1 could not reach step 2 for any meter
  with no reading in the period). Meter Reads' own overlay does the arithmetic and
  writes nothing; a typed `move_in` value on the same meter is its start reading;
  a committed read in the period wins. The row reads `accepted`, or `refused` with
  `refusal_key: billing.oneTimeBill.readings.status.belowLast` for a value below the
  last one. **The draft prices only saved readings** (§3).
- **A meter still waiting for its reading is answered, not refused** (`DEF-BIL-8300`).
  The preview answers `200` with the services, rates and reading rows, a `bill` with
  no groups and **`subtotal`/`total` `null`** (never `0.00`), and `waiting_for:
  {reason, service_code}`. Every other pricing refusal is still `422`. The draft
  still refuses.
- **A catch-up or penalty prints ONE date group over the whole window**, not one per
  period: the periods are priced together and no line records its period. `periods`
  lists each with its days and price versions. Said on `unavailable`.
- **`unavailable`** (every answer) lists these limits as `{code, br_ref, detail}`.

Sections absent for a kind are `null` (e.g. `move_in_charges` except `first`,
`settlement` except `final`, `periods` except `backbill`/`penalty`, `charge` except
`fee`/`penalty`; for `fee`, `services`, `rates` and `readings` are `null`).

Warnings (≤ 6 words): `baseNotSet` "No base charge for {service}. Billed $0.00." ·
`noAgreements` "No services on file. Billed all connected." · `estimated` "{count} reading estimated."

## 3 · Readings (A5)

No billing route. The screen saves each typed reading through Meter Reads:
`POST /read-batches` (one row per meter) → `POST /read-batches/{id}/validate` →
`POST /read-batches/{id}/post`, then re-runs the preview. A refused reading is shown
on its row from the validate response.

## 4 · Draft — `POST /billing/one-time` (A2, A8)

Same request as §2. `201` with `{run_id, invoice_id, invoice_no, total, currency, due_date}`
plus the §2 `bill` and `warnings`. Duplicate: `409 BIZ-IDEMPOTENT`, params
`{invoice_no, run_id, ran_by_name, ran_at}` → "Already billed for this period." with a
link to that bill.

**Built (2026-09-30):** the `409` params also carry `invoice_id` (the link) and
`ran_by` (a user id, never shown); the preview answers the same object as `duplicate`.
The `201` also carries `kind`, `status`, `bill_type`, `unavailable` and, for a final
bill, `settlement_detail`. `due_date` is issue's own derivation (`bill_date +
due_days`), the date the bill will be stamped with. A `settlement_path` the rule does
not allow for this remainder is refused by `final_bill.settle` in its own words; one
outside the three words is `billing.oneTime.err.settlementPathUnknown`.

## 5 · Send (A6, A7) — `POST /billing/one-time/{run_id}/send`

```json
{"confirmations": {"compliance": true, "email_mandate": true, "sms_mandate": true,
                   "autopay_mandate": true, "final": true},
 "delivery": "email | paper | email_and_paper", "sent_at": "ISO-8601 with offset"}
```
One call: authorise and issue this run's single draft. ⚠ **AMENDED 2026-09-30 (PO
ruling, option B: *"B · Show all five ticks on the one-time Send card."*)** — refused
unless all FIVE release confirmations arrive as literal `true`, each untaken one named
on `confirmations.<name>` (`billing.oneTime.err.confirmRequired` "Tick this to send.").
The single `acknowledged` tick (`ackRequired`) is retired from the wire and the catalogues.
NOT refused for a penalty bill without an approval (PO 2026-09-30): the body carries optional `approved_by` ({user_id} or {name}), stored in `bill_payload.penalty.approved_by` (no `approvalRequired` key).
**Idempotent:** a second call returns `200` with the
same bill. `201` answer: `{invoice_no, total, currency, due_date, delivery: "queued", reads: "locked"}`.

**Built (2026-09-30), `apps/billing/one_time_send.py`:** the answer also carries
`run_id`, `invoice_id`, `status`, `delivery_choice`, `created` (`false` on a replay) and
`unavailable`. The five confirmations are recorded exactly as given (BR-BIL-058),
`confirmed_by` = the clerk, `confirmed_at` = `sent_at` (2.412.2; until then one
acknowledgement was recorded as all five).
Authorise and issue run in ONE transaction: if the one bill cannot issue, nothing is
written and the call is refused. **Paper is the floor** (BR-BIL-036): `email` queues
email AND paper, as `email_and_paper` does; `paper` queues paper only. A cycle run's
id answers `404` here. An unknown `delivery` is `billing.oneTime.err.deliveryUnknown`;
an `approved_by` that is neither `{user_id}` nor `{name}` is
`billing.oneTime.err.approverInvalid`.

## 6 · Database (DB1–DB3)

- `invoice_lines.asset_id` — new, nullable; the meter or asset a line was priced for.
- Penalty evidence text → `bill_payload.penalty.evidence`. **Photos: NOT stored
  (decision DB2, 2026-09-30)** — the platform store's `stored_documents.kind` is a closed
  product vocabulary owned by tenancy, so a penalty-evidence kind is a tenancy
  migration and not a clean fit; text only until that is taken on.
- Fee note → `bill_payload.note`.
- Final bill's chosen settlement path → `bill_payload.settlement.path` (+
  `chosen_by_clerk`), checked against `final_bill.settle_final_bill(…, chosen=…)`.
- Penalty approver (§5) → `bill_payload.penalty.approved_by`, plus an `audit_log` row.
