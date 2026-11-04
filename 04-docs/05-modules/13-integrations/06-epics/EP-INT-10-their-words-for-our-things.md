# EP-INT-10 — Their words for our things: mappings, unknown values, and format as a parameter

**Module:** integrations · **Wave:** phase 1 (the table and the codec registry) · phase 4–5 (the rows real partners need) · **Screens:** S143 value mapping · S141 (format picker) · **Status:** draft (`CR-069`, 2026-09-03)

## Scope

**In:** *"the most reusable decision in this document"* — `integration_target_reference`, the row that replaces every column named after a vendor (`BR-INT-032`); the rule that an unknown value **degrades** on the way in and is **refused by name** on the way out (`BR-INT-031`); the codec registry — projection × codec × packaging — lifted out of billing so one projection emits JSON to one partner and XML to another (`BR-INT-033`); and the two nearly-free standards, Nacha return codes as mapping rows and camt.053 as a codec (`C36`).

**Out:** the ledger's own decision about `qbo_ref` / `xero_ref` and fund/department segments — that is `OQ-INT-1480`, the PO's, and the table ships **beside** the two columns until it is ruled. What Nacha `R02` maps to — `OQ-INT-1487`, the PO's, because the four reversal reasons are signed.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S143 · *Their words* tab | their word · our value | connection · type (account · tender · return code · route · meter type) · **unmapped only** | unmapped first, then their word | their word · our value · type | their word · means (our value) · type · state (**red** when unmapped) / + connection · last seen | edit (icon, rule 15) | — | — |

S143's second tab, *Waiting for a decision* (the GIS difference queue), is `US-INT-043`'s and is declared there.

## Stories

---
id: US-INT-037
epic: EP-INT-10
module: integrations
screens: [S143]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-014, US-INT-019]
journeys: [J54, J59]
rules: [BR-INT-032, BR-INT-031]
golden_tests: []
finance_calc: none
---
### US-INT-037 — Their words for our things: a foreign name is a row, never a column (S143)

**1 · Details** — As **a billing clerk**, I want **to say which of our payment methods each of their fourteen means** — so that **money does not land under *Other* on a report, and so that adding a partner never needs a database change**.

The chart of accounts carries `qbo_ref` and `xero_ref` — two columns, two vendors; the third partner needs a third, *"and the third one is what makes the shape visible: the first two looked like fields, and they were always rows."* `integration_target_reference (target_key, entity_type, entity_id | local_value, external_value)`: a ledger account as their account string (`001.100.51200`), a payment method as one of their fourteen (`ACHCHECK`), a bank return code as one of our four reasons (`R01`), a route as their composite code. **UNIQUE on the EXTERNAL side** — one of their words means exactly one of ours; two of theirs may share one of ours (`ACHCHECK` and `ACHSAVINGS` both mean *bank transfer*); never the other way round, because a mapping that multiplies rows is a report nobody can reconcile. A fourth partner costs rows; so does the tenth. **S143 — *Their words*:** one row per foreign word, its meaning chosen from our own lookup (`tenancy.PaymentMethod` is tenant-extensible, so the choices are the utility's own words), **red when unmapped**, unmapped first. `GET` / `PUT /integrations/{key}/mappings`. ⚠ The ledger's two columns are **read, never widened**; the table is added beside them until `OQ-INT-1480` rules whether it replaces them.

Entry: a partner's vocabulary arriving (a manifest ships the known list; an inbound value adds an unmapped row). Exit: rows the runners read through `selectors.py`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-032` | A foreign name is a row keyed by target; UNIQUE external side; a fourth partner costs rows | PROPOSED — design §2.13.3; ledger half OPEN → `OQ-INT-1480` |
| `BR-INT-031` | An unmapped inbound value records as `other` and shows red | PROPOSED |
| B14 rule 31 | The visible value is their word and our word — never a database id | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Kiosk manifest ships fourteen tender words; Priya opens S143 for it | Fourteen rows, all **red** *unmapped*, sorted first; she maps `ACHCHECK` and `ACHSAVINGS` both to *Bank transfer*; both rows go green |
| TC-2 · **PG · negative** | A second row `ACHCHECK → Cash` for the same target | Refused by the UNIQUE — one of their words means exactly one of ours |
| TC-3 | A fourth accounting partner needs our accounts in its words | Rows added under `target_key = aclarian`, `entity_type = ledger_account` — **no migration** (doc TC-INT-30 **PG**); `ledger_accounts` unchanged |
| TC-4 · **negative** | `PUT …/mappings` with `local_value = "Bitcoin"` (not one of our payment methods) | Refused *not one of our values* |
| TC-5 | The kiosk sends `CASHAPP`, unmapped | The payment is recorded as **Other**; a red row `CASHAPP` appears on S143 with *last seen 06:15 today* |
| TC-6 · **tenant isolation** | Lone Star Ridge opens S143 for the same provider key | Its own rows only; Brazos Bend's fourteen mappings are absent |

**4 · Test Data** — Kiosk tender vocabulary (fourteen): `CASH · CHECK · CREDIT · DEBIT · ACHCHECK · ACHSAVINGS · MONEYORDER · CASHIERCHECK · PAYPAL · VENMO · ZELLE · GIFTCARD · CRYPTO · OTHER`; Brazos Bend payment methods: *Cash · Cheque · Card · Bank transfer · Money order*. Aclarian account rows: `1200 → 001.100.11200`, `4100 → 001.100.44100`. Nacha `R01 → not enough money` (`nsf`); `R02` **unmapped, red, `OQ-INT-1487`**.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| their word (`external_value`) | S143 | `BR-INT-032` | `integration_target_reference.external_value` | text | integration / user-input | UNIQUE `(tenant, target, type, external)` |
| means (`entity_id` or `local_value`) | S143 | — | `.entity_id` (a lookup row) or `.local_value` (an enum value) | uuid/text | user-input | must be one of ours |
| `entity_type` | S143 filter | — | `.entity_type` | enum | reference-data | `ledger_account · tender · reversal_reason · route · meter_type · service` |
| state | S143 | `BR-INT-031` | computed: mapped / unmapped | enum | computed-display | red when unmapped |
| last seen | S143 | — | `config`-side counter per row (non-secret) | ts | system-derived | from the last inbound value |

**6 · Acceptance**
- Given a partner's fourteen words, then a clerk maps them to the utility's own words on one screen, two of theirs may share one of ours, and no migration ran.
- Given a word we have never seen, then money lands under *Other* and the row is red.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1480` | Per-target row instead of `qbo_ref` / `xero_ref`; fund/department/object segments? | Retiring the two columns only | PO (finance) | OPEN |

---
id: US-INT-038
epic: EP-INT-10
module: integrations
screens: [S143, S142]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-037, US-INT-039, US-INT-033]
journeys: [J51, J59]
rules: [BR-INT-031, BR-INT-033, BR-INT-053]
golden_tests: []
finance_calc: none
---
### US-INT-038 — Unknown values degrade inbound and refuse outbound — and the two nearly-free standards: Nacha codes as rows, camt.053 as a codec (C4, C36; C32 open)

**1 · Details** — As **a billing clerk**, I want **a payment that arrives naming a method nobody has mapped to be accepted and recorded as *Other* — and an outbound file naming a format nobody registered to be refused by name, with the list of what exists** — so that **a real payment is never refused over a vocabulary, and a file never leaves in a shape nobody agreed to**.

Same rule, opposite directions (`BR-INT-031`): **inbound degrades** — *"refusing a real payment over a vocabulary is worse than misfiling it"* — and the row goes red on S143; **outbound refuses by name** with the registered list. The two standards that are nearly free once `BR-INT-032` and `BR-INT-033` exist: **Nacha return codes** (`R01` *not enough money* … dozens of them) are mapping rows onto our four signed reversal reasons — `R01 → nsf` maps cleanly, **`R02` *account closed* maps to none of ours, which was `OQ-INT-1487` and was RULED on 2026-09-04 to option (b)**: it records as `other`, keeps the raw code on the payload, and **the four signed reasons are not widened to hold a third party's vocabulary**. ⚠ The word *until ruled* stood here until 2026-09-06 and is gone: it IS ruled, the refusal to map `R02` is now a RULED refusal, and nothing about this story waits on anybody; **camt.053** (the newer ISO bank statement) imports through the **same** bank connection as BAI2 with the codec named, not coded. **MultiSpeak and Green Button are not claimed** — a claim needs a test programme behind it (`BR-INT-053`, `OQ-INT-1483`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-031` | Inbound unknown → `other`, red; outbound unregistered → refused by name with the list | PROPOSED — `C4`. ⚠ **The `R02` half is no longer open:** `OQ-INT-1487` **CLOSED 2026-09-04 to (b)** — `other`, raw code kept, the four signed reasons not widened |
| `BR-INT-033` | camt.053 is a registered codec with a recorded fixture, or it is not supported | PROPOSED — `C36` |
| `BR-INT-053` | MultiSpeak and Green Button not claimed | PROPOSED — `C7`, `C36` |
| `BR-PAY-*` (four reversal reasons) | Signed and constrained; not widened here | CONFIRMED — relied on |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Kiosk payment naming `CASHAPP` | Accepted, recorded with method **Other**; S143 shows `CASHAPP` red (doc TC-INT-29, inbound half) |
| TC-2 · **negative** | Export requested as `codec = "xlsx"` (unregistered) | Refused **by name**: *xlsx is not a registered format — QuickBooks, Xero, CSV, IIF* (doc TC-INT-29, outbound half) |
| TC-3 | A camt.053 statement uploaded to the bank connection | Imports through the same connection as BAI2; the run names `codec = camt.053`; the recorded fixture from a real bank is in the repo |
| TC-4 | A returned payment `R01` | Reversal reason *not enough money* (`nsf`), raw `R01` kept on the payload |
| TC-5 · **boundary** | A returned payment `R02` | Recorded as `other`; raw `R02` on the payload; S143 row red; the reversal-reason lookup still has **four** values — and the code path that would choose one still REFUSES — ⚠ **as a RULED refusal since 2026-09-04, naming `OQ-INT-1487`'s closure to (b), not as a `NotImplementedError` awaiting an answer** |
| TC-6 · **negative** | A codec registered with no fixture file | The conformance kit fails it as *not a supported format* |
| TC-7 · **tenant isolation** | Two tenants map `R01` differently (one utility uses a custom reason name) | Each sees its own mapping; the raw code is the same |

**4 · Test Data** — Kiosk payload `CASHAPP $42.10 ACC-1048`; export request `xlsx`; a real-bank camt.053 fixture (redacted); Nacha returns `R01`, `R02`, `R03`; Brazos Bend reversal reasons (four, signed): ~~`nsf · bank_chargeback · duplicate · error`~~ ⚠ **AMENDED 2026-09-03 (wave D):** the four signed reasons in the code are `nsf · bank_chargeback · data_entry_error · customer_dispute` (`payments/models.py` `REVERSAL_REASONS`); the two names written here did not match the code, and the code wins. `mappings.our_choices()` serves exactly those four.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `unknown_value_policy` | — | `C4` | manifest per operation | enum | reference-data | inbound `degrade`; outbound `refuse` |
| raw code on payload | payment detail | `C32` | payments' webhook/import payload (raw persisted) | text | integration | kept verbatim |
| codec name on the run | S142 | `C36` | `integration_run.summary` / artifact | text | system-derived | registered name |

**6 · Acceptance**
- Given an unfamiliar tender word, then the payment lands and the word is red for a clerk to map.
- Given an unregistered format, then the file does not leave and the refusal lists what exists.
- Given `R02`, then nothing chooses a reason for it until the PO does.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1487` | What does Nacha `R02` (*account closed*) map to, given the four signed reversal reasons? | Only the `R02` mapping; everything else records | PO | ⚠ **CLOSED 2026-09-04 — option (b).** PO: *"(b) — widening a signed list for one code needs a re-sign; the raw code is kept"*. `R02` records as **`other`**, shows red, and the raw code is kept on the payload. The four signed reasons are **not widened to five**. ⚠ NOT (c), so the writer still refuses to map `R02` — but the refusal names this CLOSURE, not a `NotImplementedError` awaiting an answer. **Nothing here is blocked.** |
| `OQ-INT-1483` | Which words may we use about a standard — *supports*, *compatible with*, *certified*? | Badge copy on S141 | PO + legal | ⚠ **CLOSED 2026-09-04 — option (a), self-declared only.** PO: *"⚑ (a) — a claim we can't defend is worse than a modest one"*. Never *certified* (we hold no certificate), never *compatible with* — even where a recorded fixture from the real provider exists. No certification is pursued. |

---
id: US-INT-039
epic: EP-INT-10
module: integrations
screens: [S141, S142]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-013, US-INT-015]
journeys: [J54]
rules: [BR-INT-033, BR-INT-038]
golden_tests: []
finance_calc: none
---
### US-INT-039 — Format is a parameter: projection × codec × packaging, and one projection proved through two codecs (C8)

**1 · Details** — As **an engineer**, I want **to hand the same information to one partner as JSON and another as XML without writing it out twice** — so that **every standard — and every standard in the design's reading is XML — is a codec and not a connector**.

Three declared values on an operation: **projection** (a named resource view — which fields, under which external names: `gl_payment_v1`, `bill_message_v1`) · **codec** (how they become bytes: `json · xml · csv · iif · bai2 · camt.053 · mime`) · **packaging** (`none · zip · pgp`). The codec registry is **lifted out of billing** (`T63` — the named-format registry that shipped 1 September for the print vendor refuses an unregistered name; it becomes the module's) into `apps/integrations/codecs.py`. **The same payment is emitted as JSON to one partner and as XML to another from one projection, proved in a test.** An unregistered codec name is refused **at load**; a format picker appears on S141 **only where more than one codec is registered** for the operation; **a codec with no recorded fixture from the real provider is not a supported format.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-033` | Codec separate from projection; unregistered refused by name; picker only where > 1; no fixture = not supported | PROPOSED — design §2.17.3, §2.19, `C8` |
| `BR-INT-038` | P2 — their rename touches the projection, not a model | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Projection `gl_payment_v1`; codecs `json` and `xml` registered | The same payment row emits as JSON and as XML; both parse back to identical field sets (doc TC-INT-33) |
| TC-2 · **negative** | A manifest names `codec = "yaml"` | Refused at load with the registered list |
| TC-3 | `accounting_file` has four codecs; `email_smtp` has one (`mime`) | S141 shows a format picker on the accounting target and **no picker** on the mailbox |
| TC-4 · **negative** | `codecs/camt053.py` registered, `fixtures/camt053/*.xml` absent | Conformance kit: *not a supported format* |
| TC-5 | The partner renames `paymentDate` → `postedDate` | One edit in the projection; no model, no migration, no other codec changes |
| TC-6 · **gate** | `grep -rn "registry.register_format\|NAMED_FORMATS" 06-backend/apps/billing` | The print-vendor format registry reads from `apps.integrations.codecs` — one registry, not two |

**4 · Test Data** — Payment `PAY-2609-0311 · $142.18 · 2026-09-01 · Bank transfer · account 4100`; projections `gl_payment_v1` (JSON + XML fixtures); `bill_message_v1` (mime); accounting codecs `qbo · xero · csv · iif`; bank codecs `bai2 · csv · ofx · qbo · qfx · camt053`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `projection` | — | `C8` | manifest per operation → `codecs.py` view registry | name | reference-data | fields exist on the domain object |
| `codec` · `packaging` | S141 picker (when > 1) · S142 run | `C8` | manifest; the chosen codec in `config` | enum | reference-data / user-input | registered; fixture present |
| format picker | S141 | `BR-INT-033` | — | select | user-input | rendered only when > 1 codec |

**6 · Acceptance**
- Given one projection and two codecs, then two partners receive two shapes of the same fact from one definition.
- Given an unregistered format, then it is refused at load, by name.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
