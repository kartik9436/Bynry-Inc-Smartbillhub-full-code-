# EP-LED-06 — Cost-of-service capture: the payable side as system of record (S73 · S74 · S42)

**Module:** ledger · **Wave:** W5 · **Screens:** S73, S74, S42, S43, S56 · **Status:** BUILT AND REACHABLE 2026-08-16 (S73 register + Capture/Correct/Void, S74 reconciliation, the S42 drift warning; BR-LED-028..039 minted 2026-08-15). **OQ-200, OQ-202 and OQ-203 were CLOSED by the Product Owner on 2026-08-16 and are implemented, not stubbed:** a capture posts NOTHING to the books in R2 *("(b) for R2, (a) once supplier payments exist")*; the billed denominator is the SERVICE period *("You're measuring physical water loss, so match the physical period")*; and a captured invoice MAY be corrected after its period closes *("Yes it can be corrected")* — with a reason, an audit row, and a named warning on the export screen saying which batch no longer matches, which is the condition the PO attached. **STILL OPEN and stubbed by name:** OQ-201 (the purchase-unit vocabulary — the gas row is ABSENT and the capture form offers no unit picker) and OQ-204 (where S74 lives — its download raises and the control renders disabled with the reason). **OQ-227 was minted:** re-dating a purchase inside a closed period is a MOVE, not a correction, and is refused. Schema = a B2 addendum still owed on the schema route

> **Why this lives in the ledger and not in a fifteenth module.** Eng-Lead disposition, `12-governance/02-decision-log.md` 2026-08-15 ("THE AP CAPTURE LIVES IN THE LEDGER MODULE"): the chart of accounts, the posting service, month close, remittance and the accounting export are all ledger-owned, and a supplier invoice is captured, closed and exported through them. A separate module would cross a boundary on every one of its own operations and would need a hole in hard rule 5 the day it was minted. IDs are minted in the ledger vocabulary — BR-LED-###, US-LED-###, EP-LED-##.
>
> **The prototype contains nothing for this capability.** `05-prototype/UtilityBilling.html` has zero occurrences of *supplier*, *vendor* or *purchased power* — it predates the OQ-188 ruling. So no row in this epic is prototype-extracted, and none may be presented as such (hard-won law 1).
>
> ⚠ **Why the open questions start at OQ-200.** **OQ-195, OQ-196 and OQ-197 are already cited in shipped code** — `apps/payments/credit.py` (the multi-payment refund schema question, inside a `raise NotImplementedError`) and `apps/notifications/catalogs.py` (the email/SMS token catalogs, the payment-plan notice class) — **and none of the three has a row in `12-governance/01-open-questions.md`**. Taking them would have been DEF-053 over again, so this lane took the block above every number in use and left 198/199 free rather than splitting it. The three unregistered numbers are REPORTED to the PO batch, not fixed here.

## Scope

**In:** the **capture** of a supplier invoice (BR-LED-029: invoice date · service or cost category · supplier name as FREE TEXT · amount `NUMERIC(18,6)` + `CHAR(3)` · **optional** volume + unit · GL account · accounting period) on **S73 Finance → Cost of service**; the **register** over captured invoices (list · search · filter · edit while the period is open · **void with reason, never delete**); the **reconciliation** on **S74** — bought vs billed per service per period with the **unaccounted-for percentage** and its **ABSENT-with-reason** case (BR-LED-031); the **cost-of-service section of the existing accounting export** (S42/S43, BR-LED-039 riding BR-LED-004's idempotent batch); and the **cost-of-service section of the chart** proposed for finance signature (BR-LED-037, seeded marked-unsigned per BR-LED-038).

**Out — and these are OUT AS RULES (BR-LED-028), not as v1 deferrals, so a later lane cannot drift into them:** approval workflows · payment runs · a **vendor master** · ageing chase / dunning of suppliers · cheque printing or remittance advice · paying anything at all. Option (c) *full accounts payable* was put to the Product Owner and **declined** (OQ-188). Also out: the **schema migration** for the payable table (a B2 addendum on the schema route — that lane owns it, r13 #8 pattern: exact DDL = Eng-Lead 🔒); **B5 line 74 itself**, which is ❄️ FROZEN and finance-signed and gets an ADDENDUM through HUMAN-GUIDE §6, never an inline edit; the receivable side, which already exists (EP-LED-01..05).

**Tables:** **GAP — a new payable table is owed on the schema route.** This epic names it `supplier_invoices` as a PROPOSED name so its rows can be written about; the schema lane owns the name, the DDL, the RLS policy and the immutability shape. Reads: `ledger_accounts` (the GL account picker), `invoice_lines.quantity/.unit` through a published billing selector seam (billed volume — the ledger read model never imports billing, see §8 of US-LED-020), fiscal period state (BR-LED-006).

**Customer types this is for, named by the PO and not all utilities:** *Utility · submetering company · HOA*. For an HOA reconciling one bulk supplier invoice against many member bills, this is close to the point of the product rather than a bookkeeping extra.

## Screen IDs — assigned from the reserved block, and stated explicitly

CLAUDE.md forbids renumbering; A1's canonical range is S1–S114 with **S61–S90 reserved for design** and S61–S71 already assigned by A1 addenda. **S72 is deliberately skipped**: EP-IDN-01 line 234 carries it as a *proposal* riding OQ-078 ("S72 is a *proposal*, not an assignment"), and taking it would create exactly the collision G17 exists to stop.

| ID | Screen | Home | Status |
|---|---|---|---|
| **S73** | Finance (tab: **Cost of service**) — captured supplier-invoice register + capture/edit/void modals | Sidebar → Finance | **PROVISIONAL** — assigned here from the reserved block, ratification into A1 = OQ-204 (the route OQ-034/S62 and OQ-063/S68 took) |
| **S74** | Finance (tab: Cost of service → **Reconciliation**) — bought vs billed per service per period | S73 | **PROVISIONAL** — ID assigned; its HOME (a Finance sub-view or a reports-viewer report beside S59/S60) is **OQ-204 OPEN** |

*A-docs are design-session-owned (HUMAN-GUIDE §6: "don't hand-edit content — corrections land as dated addenda"), so A1 is NOT edited by this lane. These two rows are the addendum text OQ-204 asks the PO to ratify.*

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S73 · Captured cost register | supplier name, invoice reference, memo | period, service/cost category, status (captured/voided), volume captured (yes/no), GL account | invoice date desc | date, supplier, service, amount, volume | Date · Supplier · Service/category · Amount · Volume · Unit · GL account · Period · Status / +Reference, Captured by, Captured at, Void reason (IS-5) | View · Edit (period OPEN only, BR-LED-034) · Void with reason (BR-LED-035) | — *(none: a bulk action here would be a payment run or an approval queue, both forbidden by BR-LED-028)* | CSV (IS-9) |
| S74 · Cost-of-service reconciliation | — *(aggregate table; nothing free-text to search)* | period, service | service asc | service, bought volume, bought cost, billed volume | Service · Bought volume · Unit · Bought cost · Billed volume · Unaccounted for % · Reason (when ABSENT) · Basis / +Purchase count, Purchases missing volume (IS-5) | Drill to the purchases behind the row (S73) · Drill to the billed volume behind it | — | CSV + PDF per IS-11 (basis labeled, filters echoed) |

## Stories

---
id: US-LED-017
epic: EP-LED-06
module: ledger
screens: [S56, S73]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-005]
journeys: [J25]
rules: [BR-LED-037, BR-LED-038, BR-LED-015]
golden_tests: []
finance_calc: none
---
### US-LED-017 — Cost-of-service chart section: proposed for finance signature, seeded only for the services a tenant sells

**1 · Details** — As a System Admin or Billing Clerk, I want the tenant chart of accounts to carry a **cost-of-service section** so a captured supplier invoice has somewhere to point (BR-LED-029's GL-account field), **without anybody inventing a signed account inline**. The books hold exactly **two expense accounts today — 6800 bank fees and 6900 bad debt** — both arising from meter-to-cash itself; purchased power, water and gas, O&M and infrastructure have **no accounts at all** (`12-governance/02-decision-log.md`, 2026-08-12 and 2026-08-15). This story ships the **mechanism** exactly as US-LED-005 ships the chart mechanism and never the numbers: the proposed section mirrors the finance-signed **41xx revenue ladder digit for digit** so a reviewer checks it in one pass (5100 ↔ 4100 electric, 5110 ↔ 4110 water, 5120 ↔ 4120 sewer, 5130 ↔ 4130 trash, 5140 ↔ 4140 gas, 5145 ↔ 4145 broadband) plus **5200 Operations & maintenance** and **5300 Infrastructure**, the two non-commodity categories the PO named in OQ-188's own words (*"O&M cost, infra cost"*). **It is an addition to B5 line 74, which is ❄️ FROZEN and finance-signed 2026-08-08, so it needs a finance RE-SIGN via HUMAN-GUIDE §6 — the route the 4160/4170 revenue codes and the concession account took, and never an inline edit** (BR-LED-037). Until that signature exists the codes seed **marked-unsigned** and no surface may present them as signed. Seeding follows **BR-BIL-067's ruled shape** extended to the cost ladder (BR-LED-038): a tenant is seeded only the cost accounts for the services it **sells**, and a tenant's own pointer is never overwritten by a re-seed. Entry: S56 chart panel (the accounts) / S73 GL-account picker (their use). Exit: a GL account exists for every captured purchase, or the tenant's own account does.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-037 | The cost-of-service chart section is an addition to B5 line 74 ❄️ and needs a finance re-sign via HUMAN-GUIDE §6; until signed, codes seed marked-unsigned. Proposed: 5100 · 5110 · 5120 · 5130 · 5140 · 5145 · 5200 · 5300. | **PROPOSED — pending finance re-sign.** Derivation: B5 line 74 is ❄️ frozen (finance-signed 2026-08-08); CLAUDE.md "changing a signed rule or figure needs a finance re-sign via HUMAN-GUIDE §6, never an inline edit"; the 4160/4170 precedent (BR-BIL-067) and the concession-account precedent (BR-LED-022) |
| BR-LED-038 | A tenant is seeded only the cost accounts for the services it sells; a tenant's own pointer is never overwritten by a re-seed. | **PROPOSED** — derivation: BR-BIL-067 verbatim, *"you create an account, but allow tenant user to override it - also note every Utility may not have all the services"* (PO 2026-08-11, OQ-115), extended from the revenue ladder to its mirror |
| BR-LED-028 *(consumed)* | No vendor master, no approvals, no payment runs — so the chart is the ONLY place a captured cost is classified. | CONFIRMED — PO 2026-08-12 (OQ-188) |
| BR-LED-005 / US-LED-005 *(consumed)* | Chart accounts are tenant-customizable and audit-locked while in use (IS-1 deactivate-first; code/type frozen once posted against — ⚠ AMENDED 2026-10-29 for the CODE only, `CR-196-BRC10`: a System Admin may change it even when used; TYPE stays frozen). | CONFIRMED — PO LB-1/LF-5, 2026-08-08 |
| BR-LED-015 | Every chart change writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Brazos Bend (Electric · Water · Sewer · Trash · Gas) is provisioned | Cost section seeded **5100 · 5110 · 5120 · 5130 · 5140 · 5200 · 5300**; **5145 Broadband transport is NOT seeded** (Brazos Bend sells no broadband); each row renders the `unsigned` marker until the B5 addendum is signed |
| TC-2 | Silver Creek Water (sells Water + Sewer only) is provisioned | **5110 and 5120 only** — four fewer commodity lines on every trial balance than a force-seeded chart would give (BR-LED-038, the BR-BIL-067 worked shape) |
| TC-3 | Silver Creek enables **Gas** on 2026-09-01 | **5140 is minted at that moment**, not before; audit `ledger_account.created`; nothing else changes |
| TC-4 | A tenant points purchased water at its own existing `5115 · Raw water purchases` and a re-seed runs | The tenant's pointer **survives the re-seed** — the seed never overwrites a claimed designation (BR-LED-038, the BR-BIL-067 protection) |
| TC-5 *(negative)* | Any surface (capture form, export, report) presents a 51xx/52xx/53xx code as finance-signed while the B5 addendum is unsigned | **Refused / flagged** — the account carries `unsigned` and the surface must say so; presenting an unsigned account as signed is the hard-won-law-1 failure this rule exists to stop |
| TC-6 *(negative)* | Delete attempted on 5110 after a supplier invoice references it; code/type edit attempted on the same | Delete blocked with the reference count (IS-1 audit-lock); TYPE frozen once referenced; ⚠ the CODE changes for a System Admin since 2026-10-29 (`CR-196-BRC10`), a clerk is refused (US-LED-005 TC-4 pattern, amended) |
| TC-7 *(isolation)* | Lone Star Ridge chart | Its own cost rows only; Brazos Bend's 5110 is invisible there and the codes may repeat per tenant (per-tenant UNIQUE, RLS FORCE) |

**4 · Test Data** — Brazos Bend (Electric · Water · Sewer · Trash · Gas): seeded 5100 Purchased power · 5110 Purchased water · 5120 Sewer treatment & disposal · 5130 Trash hauling & disposal · 5140 Purchased gas · 5200 Operations & maintenance · 5300 Infrastructure — all marked `unsigned (B5 addendum pending)`. Existing expense rows unchanged: **6800 Bank fees · 6900 Bad debt · 6950 Deposit interest expense**. Silver Creek Water: 5110 + 5120 only; Gas enabled 2026-09-01 → 5140 minted that day by Norma Reyes (Billing Clerk). Tenant-own-pointer fixture: `5115 · Raw water purchases`. Isolation: Lone Star Ridge (J. Okafor).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Cost account code / name / type | S56 chart | BR-LED-037 (proposed section) | `ledger_accounts.code`, `.name`, `.type = expense` | text/enum | reference-data (seeded) | UNIQUE per tenant; frozen once referenced (US-LED-005) |
| `unsigned` marker on a proposed code | S56 chart · S73 picker | BR-LED-037 | **GAP — no column carries "seeded pending a finance signature"; the 4160/4170 rows have the same gap today (BR-BIL-067)** | flag | system-derived | must render wherever the account is offered; see §8 |
| Service → cost-account default | S56 mapping (Settings → Configure, BR-LED-014) | BR-LED-038 | service attribute on `ledger_accounts` (the BR-BIL-067 shape, ledger-owned per OQ-106) | uuid/enum | reference-data + user override | tenant override never overwritten by re-seed |
| Seeded set per tenant | — | BR-LED-038 | `ledger_accounts` seed at provisioning / at service enablement | rows | reference-data | only services the tenant sells |
| Audit | — | CLAUDE.md #7 · BR-LED-015 | `audit_log` `ledger_account.created` / `.updated` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a tenant selling five services, Then exactly the five commodity cost accounts plus O&M and Infrastructure exist, each marked unsigned, and the sixth (broadband) does not.
- Given a tenant enabling a service later, Then its cost account is minted at that moment with an audit row; given a tenant's own pointer, Then a re-seed leaves it alone.
- Given the unsigned state, Then no surface presents these codes as finance-signed; given references, Then delete is impossible and code/type are frozen; given two tenants, Then charts never cross.

**7 · Finance Calculation** — **N/A** (chart mechanism; no arithmetic). The account CONTENT is finance-owned and pending a re-sign of B5 line 74 ❄️ per BR-LED-037 — this story ships the mechanism, exactly as US-LED-005 §7 does.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| — | **Not an OQ — a SIGNATURE ROUTE.** The cost section is an addition to B5 line 74 ❄️ (finance-signed 2026-08-08) and needs a finance re-sign via HUMAN-GUIDE §6. It is recorded here so nobody mistakes an unsigned proposal for law, and so the addendum has one place to be checked against. The proposal itself is in `08-worked-examples.md` §"PROPOSED chart addendum". | The codes' SIGNED status only — the mechanism, the seeding and the capture are all buildable against unsigned-marked rows | Finance / Product Owner via HUMAN-GUIDE §6 | **PENDING RE-SIGN** |
| OQ-200 | Whether capture POSTS a journal entry decides whether this section needs a **liability** account beside the expense ones (a `2500 Accounts payable`). The expense ladder is unaffected either way, which is why this story is not blocked on it. | The liability half of the proposed section only | Product Owner (chat session) | **OPEN** |

**REPORTED, not resolved — the `unsigned` marker has no home.** BR-BIL-067 already seeds **4160 Storm water** and **4170 Thermal/Heat** *"marked-unsigned pending a re-sign"*, and no column on `ledger_accounts` carries that state; the marking lives in prose. This story adds eight more rows in the same condition, so the gap goes from two rows to ten. It is named here rather than solved because inventing a column is the schema lane's call and because a comment claiming a guarantee is not the guarantee (hard-won law 1).

---
id: US-LED-018
epic: EP-LED-06
module: ledger
screens: [S73]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-017, US-LED-015]
journeys: [J25]
rules: [BR-LED-028, BR-LED-029, BR-LED-030, BR-LED-033, BR-LED-034, BR-LED-036]
golden_tests: []
finance_calc: none
---
### US-LED-018 — Capture a supplier invoice (S73): date · service · supplier free text · amount · OPTIONAL volume · GL account · period

**1 · Details** — As a System Admin or Billing Clerk, I want to **capture** what the utility was invoiced — purchased power, purchased water, purchased gas, O&M, infrastructure — so the product is the **system of record for both sides** and **processes neither** (BR-LED-028; PO verbatim 2026-08-12: *"we can make this system of record and capture Ap, AR both ; we dont have to process anything just capture and help Utility, Sub metering copany or HOA reconcile both sides as system of record"*). The capture form (IS-6 modal → explicit confirm → toast → `audit_log`) takes: **invoice date · service or cost category · supplier name (FREE TEXT — there is no vendor master and BR-LED-028 forbids one) · amount `NUMERIC(18,6)` with a `CHAR(3)` currency, never float and never cents (CLAUDE.md rule 2 / DB-3) · an OPTIONAL volume with its explicit unit (BR-LED-030; PO verbatim: _"I dont know but we can make a provision and make it optional"_) · a GL account from US-LED-017's section or the tenant's own · the accounting period · an invoice reference and memo**. Nothing about paying it exists: no approval step, no payment date, no due date chase, no vendor record (BR-LED-028). A capture **dated into a CLOSED period auto-posts forward to the earliest open period with an audit note** and never lands in the closed month (BR-LED-034 riding BR-TEN-038 / BR-LED-006, LE-9's ruled behaviour). The **cost-category vocabulary is the tenant's live service list plus O&M and Infrastructure** — the PO's own five categories in OQ-188 (*"electric purchases   Water purchase   O&M cost, infra cost"*) — and O&M/Infrastructure carry no volume denominator (BR-LED-031). Entry: Finance → Cost of service → Capture. Exit: J25 step 2's handoff — a captured row the reconciliation (US-LED-020) and the export (US-LED-021) read.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-028 | Capture, hold, reconcile, export — and process NOTHING: no approvals, no payment runs, no vendor master, no ageing chase, no cheque printing. Option (c) full AP declined. | CONFIRMED — PO 2026-08-12 (OQ-188), verbatim |
| BR-LED-029 | What a captured invoice holds: date · service/category · supplier FREE TEXT · amount NUMERIC(18,6) + CHAR(3) · optional volume + unit · GL account · period. Money never float, never cents. | CONFIRMED for the field set named in OQ-188's own option text (date, service, volume, amount, account) and for the money typing (CLAUDE.md rule 2 / DB-3); **PROPOSED** for supplier-as-free-text (derivation: BR-LED-028 forbids a vendor master, and a payable naming no supplier cannot be reconciled to a statement) and for the period field (derivation: BR-LED-006 close + OQ-190's per-period figure both require one) |
| BR-LED-030 | Volume is OPTIONAL; nothing refuses a cost-only invoice. | CONFIRMED — PO 2026-08-12 (OQ-190), verbatim |
| BR-LED-033 | A captured volume carries an EXPLICIT unit; it is never assumed. | CONFIRMED for the explicit-unit requirement (CLAUDE.md rule 3); the per-service purchase-unit VOCABULARY is **OQ-201 OPEN** |
| BR-LED-034 | Dated into a closed period → auto-forward to the earliest open period + audit note; never a write into a closed month. | CONFIRMED (consumed) — BR-TEN-038 (PO Q&A R6, OQ-033) · BR-LED-006 |
| BR-LED-036 | Every capture writes `audit_log` (`supplier_invoice.captured`). | CONFIRMED — CLAUDE.md #7 · BR-LED-015 |
| IS-6 *(consumed)* | Money action = modal → explicit confirm → toast → audit_log. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Capture **RS-2607-0141** — City of Rosenberg — Bulk Water Supply, 2026-07-06, service Water, **400,000 gal**, **$1,240.00 USD**, GL 5110, period 2026-07 | Row stored; amount held as `NUMERIC(18,6)` with currency `USD`; volume 400000 with unit `gal`; audit `supplier_invoice.captured` naming actor Norma Reyes; IS-6 confirm + toast |
| TC-2 *(the ruled case)* | Capture **HPV-4471** — Hillcrest Pipe & Valve, 2026-07-15, category **O&M**, **no volume**, $1,845.50, GL 5200 | **Accepted** — nothing refuses a cost-only invoice (BR-LED-030). The row carries `volume = null` and the reconciliation treats it per BR-LED-031, never as a validation error |
| TC-3 | Capture **BVPC-070026** — Brazos Valley Power Cooperative, 2026-07-31, Electric, **412,000 kWh**, **$28,222.00** | Stored with unit `kWh`; the unit travels with the number and is never inferred from the service (CLAUDE.md rule 3) |
| TC-4 | Supplier name typed twice with different spellings ("City of Rosenberg" / "City of Rosenberg - Water Dept") | **Both accepted as typed.** No vendor record is created, no dedupe prompt, no master list — BR-LED-028. The register searches the free text (S73 capability row) |
| TC-5 | Capture dated **2026-07-30**, keyed **2026-08-07**, with July already CLOSED | **Auto-posts forward to August** with the audit note "period closed; auto-forwarded"; July is untouched and its export batch is unaffected (BR-LED-034 · LE-9) |
| TC-6 *(negative)* | Capture with amount `1240` and no currency; amount `1,240.005` (three decimals); amount as a float in an API payload | Refused — currency `CHAR(3)` is required, and the money contract is `NUMERIC(18,6)` + `CHAR(3)`, never float and never cents (CLAUDE.md rule 2). A posting carrying more than two decimals is separately refused by BR-LED-025 at the ledger boundary |
| TC-7 *(negative)* | Capture with a volume of `400000` and **no unit**; capture with a unit and no volume | Both refused — a volume without an explicit unit is exactly what CLAUDE.md rule 3 forbids, and a unit with no quantity is a half-filled field. Omitting BOTH is legal (TC-2) |
| TC-8 *(negative)* | Any request to approve, schedule, pay, or attach a vendor record to a captured invoice | **Refused and named** — there is no such path, by rule (BR-LED-028). The refusal cites the rule so a later lane reads it as law, not as an unbuilt feature |
| TC-9 *(negative)* | Capture attempted by an **Executive** role | Refused server-side — an executive reads the books, a clerk records them (BR-LED-003 as amended 2026-08-12; ⚠ carried as the READING for capture, see §8) |
| TC-10 *(isolation)* | Lone Star Ridge captures its own bulk-water invoice while Brazos Bend's July is open | Each tenant sees only its own rows; no cross-tenant read or write is possible (RLS FORCE, `app.tenant_id` required — CLAUDE.md rule 1). J. Okafor cannot see RS-2607-0141 by id, by search or by export |

**4 · Test Data** — Brazos Bend, July 2026 (fixture CI-1..CI-9, `08-worked-examples.md` §LE-11): **Water** — City of Rosenberg — Bulk Water Supply: RS-2607-0141 Jul 6, 400,000 gal, $1,240.00 · RS-2607-0158 Jul 13, 250,000 gal, $775.00 · RS-2607-0175 Jul 20, 100,000 gal, $310.00 · RS-2607-0192 Jul 27, 50,000 gal, $155.00 · RS-2607-0208 Jul 31, 200,000 gal, $620.00 (all at $3.10/kgal; total 1,000,000 gal / $3,100.00). **Electric** — Brazos Valley Power Cooperative BVPC-070026, Jul 31, 412,000 kWh, $28,222.00 ($0.0685/kWh). **Gas** — Gulf Coast Gas Transmission GCGT-2607-88, Jul 31, 1,450 MMBtu, $6,235.00 ($4.30/MMBtu). **O&M** — Hillcrest Pipe & Valve HPV-4471, Jul 15, no volume, $1,845.50. **Infrastructure** — Katy Meter Works KMW-2026-118, Jul 22, no volume, $12,500.00 (40 replacement meters). Currency USD throughout. Actors: Norma Reyes (Billing Clerk, captures), Alex Reed (Executive, read-only), Dana Fox (System Admin). Isolation: Lone Star Ridge (J. Okafor).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Invoice date | S73 capture | OQ-188 option (b) text, as ruled | **GAP — `supplier_invoices.invoice_date` (PROPOSED table; B2 addendum owed, schema route)** | date | user-input | required; a typed date = midnight in the utility's OWN timezone (BR-TEN-081) |
| Service / cost category | S73 capture | OQ-188 verbatim (*"electric purchases   Water purchase   O&M cost, infra cost"*) | **GAP — `supplier_invoices.service`** | enum (tenant live services + O&M + Infrastructure) | user-input | required; LIVE vocabulary, never hardcoded (BR-REP-006) |
| Supplier name | S73 capture | BR-LED-029 (PROPOSED — derivation BR-LED-028) | **GAP — `supplier_invoices.supplier_name`** | text | user-input | required; **FREE TEXT — no FK, no vendor table, no dedupe** (BR-LED-028) |
| Amount + currency | S73 capture | OQ-188 option (b) + CLAUDE.md rule 2 / DB-3 | **GAP — `supplier_invoices.amount` `NUMERIC(18,6)` + `.currency` `CHAR(3)`** | numeric(18,6) + CHAR(3) | user-input | > 0; never float, never cents; rounding only at display (B4 ❄️); tenant currency lock applies (BR-TEN-042) |
| Volume | S73 capture | **PO 2026-08-12 (OQ-190) — CONFIRMED OPTIONAL** | **GAP — `supplier_invoices.volume` `NUMERIC(18,6)` NULLABLE** | numeric(18,6) | user-input | **nullable by rule**; if present, the unit is required |
| Volume unit | S73 capture | BR-LED-033 · CLAUDE.md rule 3 | **GAP — `supplier_invoices.volume_unit`** | text/enum | user-input | required whenever volume is present; **the per-service vocabulary is OQ-201 OPEN** |
| GL account | S73 capture | BR-LED-037 / US-LED-017 | `ledger_accounts.id` (cost section or the tenant's own) | uuid | user-input (defaulted from the service mapping) | must be an expense account; unsigned-marked accounts render their marker |
| Accounting period | S73 capture | BR-LED-029 (PROPOSED — derivation BR-LED-006 + OQ-190) | **GAP — `supplier_invoices.period`** | period key | user-input (defaulted from the invoice date) | closed period → auto-forward + audit note (BR-LED-034) |
| Invoice reference · memo | S73 capture | BR-LED-029 | **GAP — `supplier_invoices.reference`, `.memo`** | text | user-input | reference optional but searchable (S73 matrix) |
| Status | S73 register | BR-LED-035 | **GAP — `supplier_invoices.status` captured\|voided** | enum | system-derived | void is a state, never a delete |
| Journal entry for the capture | S56 | **UNDERIVABLE — OQ-200** | — | — | — | **not built; `raise NotImplementedError("OQ-200")` at the posting boundary** (prime directive) |
| Audit | — | CLAUDE.md #7 · BR-LED-036 | `audit_log` `supplier_invoice.captured` | jsonb | system-derived | append-only; actor + before/after |

**6 · Acceptance**
- Given a supplier's bulk-water invoice, Then a clerk captures it in one modal with its optional volume, and the row is stored with money as `NUMERIC(18,6)` + `USD` and the volume with an explicit unit.
- Given a cost-only invoice, Then it is accepted without complaint; given a volume without a unit, Then it is refused.
- Given a date inside a closed period, Then the capture auto-forwards with an audit note and the closed month is untouched.
- Given any attempt to approve, pay or vendor-master a captured invoice, Then the product refuses and names BR-LED-028; given another tenant, Then nothing crosses.

**7 · Finance Calculation** — **N/A at capture** (a record, not a computation — nothing is derived, netted or rounded here). The one arithmetic fact worth stating is the one this story does NOT do: the amount is stored exactly as keyed at six decimals and is **never rounded by the ledger**, because rounding is the caller's job and happens once at finalization (BR-LED-025, B4 ❄️ / BR-RAT-003 — two rounding sites is how two figures start disagreeing). The computation built on these rows is US-LED-020 §7.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-200 | **Does a captured supplier invoice POST a balanced journal entry, and if so what is the credit side?** | Nothing — closed and implemented | Product Owner (chat session) | **CLOSED 2026-08-16 — IT POSTS NOTHING IN R2. PO verbatim: _"(b) for R2, (a) once supplier payments exist"_.** The reason is the rule: option (a) credits an accounts payable BR-LED-028 forbids this product from ever draining, so twelve months at $3,100.00 of purchased water would leave **$37,200.00** standing for invoices the utility settled by cheque — *a growing false number is worse than an absent true one*. July's trial balance stays **598.69 = 598.69** and the export's cost section is register-derived and labelled. ⚠ **THE CLOSURE CARRIES A TRIGGER:** the day a supplier-payment path ships, option (a) becomes the ruling and the posting half must be built. It is not a new question, must not be re-asked, and must not be forgotten — `cost_capture.POSTING_RULING_EXPIRES_WHEN` carries it in the code and a test asserts it. |
| OQ-201 | **The purchase-side unit vocabulary per service, and whether a signed conversion factor may be applied.** | The unit field's ENUM and any cross-unit comparison. A free-text unit that must match the billed unit exactly is buildable meanwhile | Product Owner (chat session) | **OPEN** |

**WHY OQ-200 IS A FINANCE QUESTION AND NOT AN IMPLEMENTATION DETAIL, with the figure.** A double-entry book needs both sides. If capture posts, July's cost-of-service debits total **$51,902.50** (LE-14) and the credit side has to be something — an `Accounts payable` liability nothing in this product ever drains, because BR-LED-028 forbids payment runs. **Worked:** at $3,100.00 of water a month, twelve months of captured-and-paid-elsewhere purchases leave **$37,200.00** of payable standing in the books that the utility settled long ago. **And it moves a FROZEN figure:** LE-1's July trial balance is **598.69 = 598.69** and is golden test **GT-51** (B5's mechanical allocation, LE-n → GT-(50+n)); posting July's costs makes it **52,501.19 = 52,501.19**, which is a change to a finance-signed example and needs the re-sign route, not a lane's decision. The three readings are (a) DR cost-of-service / CR accounts payable, drained by a manual journal entry when the utility wants it out — which is exactly the posture BR-LED-024 already ruled for un-reconciling (*"Utility will balance the books by manual journal entry - if required ; we dont have to do anything just show correct calculations"*); (b) capture holds the row and posts NOTHING — the books stay as LE-1 signed them, the reconciliation and the export still work, and the trial balance simply never shows cost; (c) DR cost / CR cash at capture, which asserts the invoice was paid and is wrong for anything unpaid. **Nothing is chosen here.** The capture stores its GL account either way, so closing this question later is a posting call, not a re-capture.

**THE ROLE GATE IS CARRIED AS A READING AND FLAGGED, NOT ASSUMED.** BR-LED-003 was amended 2026-08-12 (PO, OQ-175, verbatim *"System Admin, Billing Clerk"*) and its own text says the same substitution *"is owed anywhere 'Finance/Owner' gates a ledger action in this module's epics … flagged, not assumed"*. **What was put to the PO was the REVERSAL.** Capture was not separately raised, so TC-9's Executive refusal is this lane's reading of a ratified pattern and is **not treated as separately ratified** — the same posture US-LED-014 §8 takes for the remittance record and the month close.

---
id: US-LED-019
epic: EP-LED-06
module: ledger
screens: [S73]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-018]
journeys: [J25]
rules: [BR-LED-028, BR-LED-034, BR-LED-035, BR-LED-036]
golden_tests: []
finance_calc: none
---
### US-LED-019 — The captured-cost register (S73): list, search, edit while the period is open, void with reason — never delete

**1 · Details** — As a System Admin or Billing Clerk, I want the **register** of everything captured: the full IS-2/3/4/5 list (capability row above) over `supplier_invoices`, searchable by **supplier free text**, invoice reference and memo, filterable by period, service/category, status and **whether a volume was captured** — that last filter exists because it is precisely the set that decides whether the unaccounted-for figure can be produced at all (BR-LED-031), so a clerk can find and fix the gap in one click instead of reading a suppressed percentage and wondering. **Editing is allowed while the invoice's period is OPEN** and every edit audits with before/after (BR-LED-034, BR-LED-036). **Correcting a captured invoice after the fact is a VOID with a reason plus a fresh capture, never a delete** (BR-LED-035, deriving from hard rule 4 and IS-1: financial records never delete). A voided row stays visible in the register with its reason, because a register that hides its corrections cannot be reconciled against a supplier statement. **What is deliberately absent, by rule:** no approve action, no "mark paid", no payment scheduling, no supplier page, no ageing bucket, no bulk action bar (BR-LED-028) — S73's bulk-actions cell is empty on purpose and the capability matrix says so. Entry: Finance → Cost of service. Exit: J25 step 6's handoff — a register whose rows the reconciliation and the export read, with the voided ones excluded from both.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-035 | Void, never delete: a captured invoice is voided with a reason and stays visible; corrections are new rows. | **PROPOSED** — derivation: CLAUDE.md hard rule 4 (*"corrections are new rows"*) + IS-1 (*"Financial records never delete"*, B9) + BR-LED-003's reverse-and-repost shape for the books |
| BR-LED-034 | Editable while the period is OPEN; a closed-period date auto-forwards (BR-TEN-038). **Whether an invoice may be edited or voided after its own period CLOSES is OQ-203.** | CONFIRMED for the dating (BR-TEN-038 · BR-LED-006); the after-close half **OPEN (OQ-203)** |
| BR-LED-028 | No approvals, no payment runs, no vendor master, no ageing — so the register has no such actions and no bulk bar. | CONFIRMED — PO 2026-08-12 (OQ-188) |
| BR-LED-036 | Every edit and void writes `audit_log` (`supplier_invoice.updated` / `.voided`). | CONFIRMED — CLAUDE.md #7 · BR-LED-015 |
| IS-1 / IS-2 / IS-3 / IS-4 / IS-5 / IS-9 *(consumed)* | Deactivate-first, server-side tables, debounced search, URL-persisted filters, dynamic columns, filtered CSV. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Register renders Brazos Bend July | 9 rows (CI-1..CI-9) — 5 water, 1 electric, 1 gas, 1 O&M, 1 infrastructure; default sort invoice date desc; totals footer **$51,902.50 USD**; every money cell 2dp (OQ-186: API serves 4, screen shows 2) |
| TC-2 | Search `Rosenberg`; filter period = 2026-07 + service = Water | 5 rows, $3,100.00; debounced ≥2 chars, server-side, filters in the URL (IS-3/IS-4) |
| TC-3 *(the useful filter)* | Filter **volume captured = no** for period 2026-07 | Returns **HPV-4471** and **KMW-2026-118** (O&M and Infrastructure — legitimately volume-free) and, in the degraded fixture, **RS-2607-0208**; the clerk sees exactly why a service's percentage is suppressed |
| TC-4 | Edit RS-2607-0175's amount $310.00 → $312.40 while July is OPEN | Saved; audit `supplier_invoice.updated` with before/after; the reconciliation's cost column moves by $2.40 and its volume figure does not |
| TC-5 | Void RS-2607-0192 with reason "duplicate of RS-2607-0175" | Status → `voided`, reason stored, actor + timestamp audited; the row **stays visible** in the register; it leaves the reconciliation's denominator and the export's section |
| TC-6 *(negative)* | Hard delete attempted on any captured row (UI, API or bulk) | **Refused** — void is the only disposition (BR-LED-035, hard rule 4). No path exists at any layer |
| TC-7 *(negative)* | The register is asked for an "approve", "mark paid", "schedule payment", "supplier statement" or "ageing" action | **Refused and named** as out of scope BY RULE (BR-LED-028) — not as a missing feature. The bulk-action bar does not render at all |
| TC-8 *(negative)* | Edit attempted on RS-2607-0141 after July CLOSES | **BLOCKED pending OQ-203** — the boundary is stubbed `NotImplementedError("OQ-203")` and nothing guesses. The two readings differ on whether a reconciliation that has already been exported can change afterwards |
| TC-9 *(isolation)* | J. Okafor opens Lone Star Ridge's register and exports its CSV | Only Lone Star Ridge rows, in the list, in the search, in the totals footer and in the CSV; Brazos Bend's CI-1..CI-9 are unreachable by id (RLS FORCE) |

**4 · Test Data** — the LE-11 fixture (US-LED-018 §4), 9 rows, $51,902.50 USD total. Edit fixture: RS-2607-0175 $310.00 → $312.40 on 2026-08-02 by Norma Reyes (footer → $51,904.90). Void fixture: RS-2607-0192 voided 2026-08-03 by Norma Reyes, reason "duplicate of RS-2607-0175" (footer → $51,747.50). Closed-period fixture: July closed 2026-08-05 (LE-9). Isolation: Lone Star Ridge, invoice `LSR-BW-0091`, City of Bandera, $842.00 (J. Okafor).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Register row (all capture fields) | S73 list | US-LED-018 §5 | **GAP — `supplier_invoices` (PROPOSED table; B2 addendum owed)** | mixed | system-derived | tenant-scoped; voided rows visible, excluded from aggregates |
| Search (supplier, reference, memo) | S73 list | IS-3 + capability matrix | `supplier_invoices.supplier_name`, `.reference`, `.memo` | text | user-input | server-side, debounced 300 ms, min 2 chars |
| Filter: volume captured yes/no | S73 list | BR-LED-031 (it names the suppression set) | computed over `supplier_invoices.volume IS NULL` | boolean | user-input | URL-persisted (IS-4) |
| Edit | S73 modal | BR-LED-034 | `supplier_invoices` UPDATE **while the period is open** | — | user-input | period-open guard; **after close = OQ-203** |
| Void + reason | S73 row action | BR-LED-035 | `supplier_invoices.status`, `.void_reason`, `.voided_by`, `.voided_at` | enum/text/uuid/timestamp | user-input | reason REQUIRED; IS-6 confirm; row never removed |
| Totals footer | S73 list | IS-2 + BR-REP-001 | Σ `amount` over the filtered, non-voided set | numeric(18,6) | computed-display | basis labeled; excludes voided rows |
| Audit | — | CLAUDE.md #7 · BR-LED-036 | `audit_log` `supplier_invoice.updated` / `.voided` | jsonb | system-derived | append-only, before/after |

**6 · Acceptance**
- Given nine captured July invoices, Then the register lists them with a $51,902.50 footer, searches the supplier free text and filters to the volume-less set in one click.
- Given an open period, Then an edit saves with before/after audit; given a mistake, Then a void with a reason keeps the row visible and drops it from every aggregate.
- Given a delete attempt, an approval attempt or a closed period, Then the product refuses — the first two by rule, the third by open question, and none by guess.
- Given another tenant, Then no row, total or CSV crosses.

**7 · Finance Calculation** — **N/A** (list mechanics; the only arithmetic is the footer Σ of the filtered non-voided rows: 1,240.00 + 775.00 + 310.00 + 155.00 + 620.00 + 28,222.00 + 6,235.00 + 1,845.50 + 12,500.00 = **51,902.50**, with the voided row excluded — after the TC-5 void the footer reads **51,747.50**). Worked in LE-11/LE-13.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-203 | **May a captured supplier invoice be edited or voided after its period has CLOSED?** | Nothing — closed and implemented | Product Owner (chat session) | **CLOSED 2026-08-16 — YES, WITH A REASON. PO verbatim: _"Yes it can be corrected"_** (option b: editable with a reason and an audit row, never frozen). **The consequence the PO accepted, and the condition attached to accepting it:** the export is idempotent and a re-run is blocked (BR-LED-004), so a correction after a handover changes a reconciliation the ERP already holds — therefore the export screen NAMES the batch that no longer matches and quotes both figures with their currency (*EXP-2607-QBO carried 51,902.50 USD; the register now totals 51,747.50 USD*). Building the edit without that warning would have been worse than freezing it. Safe to permit **because** capture posts nothing (OQ-200), so no signed total moves — and that reasoning expires the day capture starts posting cost. ⚠ **OQ-227 was minted from this closure:** an after-close correction does NOT re-home the purchase, and RE-DATING one is refused by name. |

**WHY OQ-203 IS NOT ANSWERABLE FROM THE EXISTING RULES, stated so nobody closes it by analogy.** Three signed rules point three ways. **(1)** Hard rule 4 makes issued invoices, payments and journal entries immutable — but a captured supplier invoice is on none of those lists, and it is not a document anybody was sent. **(2)** BR-LED-006 locks a closed period and BR-TEN-038 auto-forwards late EVENTS into the next open one — which answers where a NEW capture goes (BR-LED-034) and says nothing about editing one already sitting in the closed month. **(3)** BR-LED-003 gives the books their one lawful edit, reverse + repost — which is available only if the capture posts at all, and that is OQ-200. **The consequence that makes it a real decision:** July's export batch **EXP-2607-QBO** is idempotent and re-running it is blocked (BR-LED-004), so an edit permitted after close changes a reconciliation the ERP has already been handed, with no second handover possible. Readings on the table: (a) frozen at close, corrections go to the open period as a new capture with a memo pointing back; (b) editable with reason + audit, and the export batch's drift becomes a named problem on S42; (c) voidable but not editable. Nothing chosen.

---
id: US-LED-020
epic: EP-LED-06
module: ledger
screens: [S74, S73]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-018, US-LED-019, US-LED-002]
journeys: [J25]
rules: [BR-LED-030, BR-LED-031, BR-LED-032, BR-LED-033]
golden_tests: []
finance_calc: confirmed
---
### US-LED-020 — Bought vs billed (S74): the unaccounted-for percentage, and the ABSENT-with-reason case that protects it

**1 · Details** — As a System Admin, Billing Clerk or Executive, I want the **reconciliation the accounting package cannot produce**: per **service** and per **period**, the volume BOUGHT (captured, US-LED-018) beside the volume BILLED (the utility's own invoice lines), and the **unaccounted-for percentage** between them — leak, meter under-registration or theft, in one number, computable **only here because only this product holds the billed volumes** (OQ-188/OQ-190 rationale, PO 2026-08-12). **Worked, in the PO's own figures:** bought **1,000,000 gallons**, billed **910,000** → **9.00% unaccounted for**. **The percentage is ALL-OR-NOTHING per service per period** (BR-LED-031): it is produced only when **every** captured purchase of that service in that period carries a volume, and otherwise the cell reads **ABSENT with its reason, naming the count** — *"no volume captured for 1 of 5 water purchases this period"* — because against a partial denominator the same month reads **−13.75%**, i.e. the utility appears to have delivered more than it bought, which is nonsense a reader would try to explain rather than distrust. **Optional at capture, all-or-nothing at report** — the same posture the finance screens already take for collection % and DSO, and the same posture BR-REP-008 requires of a report that cannot attribute something. **O&M and Infrastructure carry no volume and never enter any service's denominator** (they are cost rows on the same table with no percentage), which is why one pipe invoice does not suppress the water figure. **A unit mismatch suppresses the same way** (BR-LED-033): gas bought in **MMBtu** against gas billed in **ccf** produces no number, by name, rather than a ratio of two different quantities. **The report never recomputes money** (BR-REP-002 and the ledger read model's own law, `01-overview.md` v5.1): the billed volume arrives through a published billing selector seam, not by importing billing into the ledger read model — a test asserts that import does not exist today and it must keep passing. Entry: Finance → Cost of service → Reconciliation. Exit: J25 steps 4–5's handoff — the figure, or its stated absence, on the period the export then carries out.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-031 | The unaccounted-for percentage is ALL-OR-NOTHING per service per period; a service with any volume-less purchase reports ABSENT with its reason and the count, never a percentage from a partial denominator. | CONFIRMED — PO 2026-08-12 (OQ-190) + the consequence row recorded the same day in `12-governance/02-decision-log.md` |
| BR-LED-032 | Formula: `(bought_volume − billed_volume) ÷ bought_volume`, per service, per period, both sides in the SAME unit; displayed 2dp with its basis labeled and both volumes shown beside it. It is a VOLUME ratio, never a money ratio. | **PROPOSED** — derivation: OQ-190's ruled worked figure is volumes (1,000,000 → 910,000 → 9%); BR-REP-001 (every report labels its basis); BR-REP-009's shape (an explicit numerator, denominator and basis) |
| BR-LED-033 | Bought and billed volumes must carry the SAME explicit unit or the figure is ABSENT with reason `purchase_unit_does_not_match_billed_unit`. | **PROPOSED** — derivation: CLAUDE.md rule 3 (*always with an explicit unit; never assume*) + OQ-004's ruled shape (*unit must match or conversion factor defined; mismatch → user message + block*). The vocabulary and any conversion factor = **OQ-201 OPEN** |
| BR-LED-030 *(consumed)* | Volume is optional at capture — which is exactly why BR-LED-031 exists. | CONFIRMED — PO 2026-08-12 (OQ-190) |
| BR-REP-001 / BR-REP-002 / BR-REP-008 *(consumed)* | Every report labels its date basis; reports are read-models, never side-maintained numbers; a report states what it could not attribute. | CONFIRMED — PO 2026-08-08 · reports audit |
| BR-REP-006 *(consumed)* | The service filter enumerates the tenant's LIVE service list, never a hardcoded one. | CONFIRMED — reports audit F-17..21 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(the ruled figure)* | Brazos Bend, July 2026, Water: all five purchases carry volume — 400,000 + 250,000 + 100,000 + 50,000 + 200,000 = **1,000,000 gal**; billed **910,000 gal** | **9.00% unaccounted for**; both volumes shown beside the percentage; bought cost **$3,100.00** in its own column; basis labeled |
| TC-2 | Same period, Electric: bought **412,000 kWh** / billed **389,340 kWh** | **5.50%**; the row is independent of Water's — the figure is per service, never a blended one |
| TC-3 *(the ABSENT case — the whole point of BR-LED-031)* | RS-2607-0208 is captured **cost-only** ($620.00, no volume); the other four water purchases total **800,000 gal**; billed is still 910,000 | Water reads **ABSENT — "no volume captured for 1 of 5 water purchases this period"**. The percentage is NOT shown. The partial denominator would have read **−13.75%** and that number never reaches a screen, a CSV, a PDF or an API payload |
| TC-4 *(the case that must NOT suppress)* | The same period contains HPV-4471 (O&M, $1,845.50, no volume) and KMW-2026-118 (Infrastructure, $12,500.00, no volume) | Water still reads **9.00%** and Electric **5.50%** — O&M and Infrastructure carry no volume denominator and enter no service's ratio. They appear as cost-only rows with "—" in the percentage column and the reason "no volume denominator for this category" |
| TC-5 *(unit mismatch)* | Gas bought **1,450 MMBtu**; gas billed **18,900 ccf** | **ABSENT — `purchase_unit_does_not_match_billed_unit` (MMBtu vs ccf)**, naming both units and citing OQ-201. No conversion is applied and no number is produced |
| TC-6 | Drill-back both ways | The Water row opens to its five S73 rows (the bought side) and to the billed volume's own invoice lines (the billed side) — every figure explains itself, the BR-LED-004 drill-back discipline applied to volumes |
| TC-7 *(negative)* | A voided purchase (RS-2607-0192, TC-5 of US-LED-019) is in the period | Excluded from both the bought volume and the bought cost; the "1 of 5" style count reports the LIVE purchases, not the voided one |
| TC-8 *(negative)* | The reconciliation is asked for a MONEY percentage ("what margin did we make on water?") | Not served — BR-LED-032 makes this a volume ratio. A margin figure needs revenue beside cost and the revenue basis question (BR-REP-001) has not been asked for this surface; nothing is invented |
| TC-9 *(negative)* | The period's billed volume cannot be read (the billing seam is unavailable) | The row reports **ABSENT with the reason**, exactly as it does for a missing volume — it never falls back to zero, and a zero billed volume would read as **100.00% unaccounted for** on a healthy month |
| TC-10 *(isolation)* | Lone Star Ridge opens its own July reconciliation | Its own purchases against its own billed volumes; Brazos Bend's 1,000,000 gal is not in the denominator, the drill-back or the CSV (RLS FORCE) |

**4 · Test Data** — Brazos Bend, July 2026 (LE-12 / LE-13):

| Service | Bought volume | Bought cost | Billed volume | Unaccounted for |
|---|---|---|---|---|
| Water | 1,000,000 gal (5 purchases) | $3,100.00 | 910,000 gal | **9.00%** |
| Electric | 412,000 kWh (1 purchase) | $28,222.00 | 389,340 kWh | **5.50%** |
| Gas | 1,450 MMBtu (1 purchase) | $6,235.00 | 18,900 ccf | **ABSENT — unit mismatch (OQ-201)** |
| O&M | — | $1,845.50 | — | — (no volume denominator) |
| Infrastructure | — | $12,500.00 | — | — (no volume denominator) |
| **Total cost** | | **$51,902.50** | | |

Degraded fixture (TC-3): RS-2607-0208 captured cost-only → Water volume 800,000 gal over 4 of 5 purchases → **ABSENT**, "no volume captured for 1 of 5 water purchases this period"; suppressed figure would have been −13.75%. Actors: Norma Reyes (Billing Clerk), Alex Reed (Executive, read-only). Isolation: Lone Star Ridge (J. Okafor), 220,000 gal bought / 214,500 billed = 2.50%.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Bought volume (per service, period) | S74 | BR-LED-031 | Σ `supplier_invoices.volume` where status = captured **(GAP — PROPOSED table)** | numeric(18,6) + unit | computed-display | excludes voided; unit must be single-valued across the set |
| Bought cost (per service, period) | S74 | BR-LED-029 | Σ `supplier_invoices.amount` | numeric(18,6) + CHAR(3) | computed-display | excludes voided; 2dp at display (OQ-186) |
| Billed volume (per service, period) | S74 | BR-LED-032 | `invoice_lines.quantity` + `.unit` for that service, **read through a published billing selector seam — never by importing billing into the ledger read model** | numeric(18,6) + unit | computed-display (cross-module READ, B1 boundary rule) | the PERIOD BASIS of this figure is **OQ-202 OPEN** |
| Unaccounted-for % | S74 | **PO 2026-08-12 (OQ-190)** | computed — `(bought − billed) ÷ bought` | percent, 2dp | computed-display | produced ONLY when every live purchase of that service in the period carries a volume AND the units match |
| Absence reason | S74 | BR-LED-031 (PO consequence row) | computed problem code + count | text | computed-display | must NAME the count (`no volume captured for N of M …`) or the mismatch (`MMBtu vs ccf`); never a blank cell |
| Purchases / purchases-missing-volume counts | S74 (IS-5 optional columns) | BR-LED-031 | computed over `supplier_invoices` | integer | computed-display | the numbers behind the reason string |
| Basis label | S74 | BR-REP-001 | — | text | computed-display | mandatory — no unlabeled figure anywhere |
| Drill-back (bought / billed) | S74 → S73 / bills | BR-LED-004 discipline | rows behind each figure | rows | computed-display | both directions, always |
| Download | S74 | IS-11 | streamed CSV + PDF | file | computed-display | filters echoed, basis labeled, money-export audited |

**6 · Acceptance**
- Given July's five water purchases and 910,000 gallons billed, Then the screen reads **9.00%** with both volumes and the $3,100.00 cost beside it, basis labeled.
- Given one cost-only water purchase, Then the cell reads ABSENT with "no volume captured for 1 of 5 water purchases this period" and **−13.75% never appears anywhere**.
- Given a volume-free O&M or infrastructure purchase, Then no service's percentage is suppressed by it.
- Given gas bought in MMBtu and billed in ccf, Then the figure is absent by name and no conversion is invented.
- Given a voided purchase, an unavailable billing read, or another tenant, Then the row excludes it, states it, or shows nothing of it respectively.

**7 · Finance Calculation** — **CONFIRMED** (the PO's own worked figures, OQ-190 / decision log 2026-08-12).

**Formula (BR-LED-032):** `unaccounted_for_pct = (bought_volume − billed_volume) ÷ bought_volume`, per service, per period, both volumes in the same unit, displayed to 2dp, produced only when `count(purchases with volume) = count(live purchases)` for that service and period.

**Worked — the ruled case (Water, July 2026):** bought `400,000 + 250,000 + 100,000 + 50,000 + 200,000 = 1,000,000 gal`; billed `910,000 gal`; `(1,000,000 − 910,000) ÷ 1,000,000 = 90,000 ÷ 1,000,000 = 0.0900` → **9.00% unaccounted for**. Cost beside it: `400 + 250 + 100 + 50 + 200 = 1,000 kgal × $3.10 = $3,100.00` ✔ (1,240.00 + 775.00 + 310.00 + 155.00 + 620.00 = 3,100.00).

**Worked — Electric:** `(412,000 − 389,340) ÷ 412,000 = 22,660 ÷ 412,000 = 0.0550` → **5.50%**; cost `412,000 kWh × $0.0685 = $28,222.00` ✔.

**Worked — the suppressed case, which is the rule's whole reason:** with RS-2607-0208 captured cost-only, the volumes present total `800,000 gal` against `910,000` billed: `(800,000 − 910,000) ÷ 800,000 = −110,000 ÷ 800,000 = −0.1375` → **−13.75%**, a utility that delivered more than it bought. **The product prints the reason instead of the number.**

**GT ref:** none of GT-1..61 covers a volume ratio — this is the first non-money computation in the finance workbook, so it is carried as **LE-12/LE-13** in `08-worked-examples.md` and a golden test is owed at the next finance freeze (the mechanical allocation LE-n → GT-(50+n) would place LE-12 at GT-62, which is beyond the frozen GT-1..61 range and therefore a finance decision, not this lane's).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-201 | **The purchase-side unit vocabulary per service, and whether a signed conversion factor may be applied.** | The GAS row only, and any service whose purchase unit differs from its billed unit. Water (gal/gal) and Electric (kWh/kWh) compute today | Product Owner (chat session) | **OPEN** |
| OQ-202 | **Which bills form the BILLED denominator — those ISSUED in the period, or those whose SERVICE PERIOD lies in it?** | Nothing — closed and implemented | Product Owner (chat session) | **CLOSED 2026-08-16 — THE SERVICE PERIOD. PO verbatim: _"(b). You're measuring physical water loss, so match the physical period."_** The reasoning is the rule and generalises: a metric about PHYSICAL water is bounded by the period the water physically moved, never by the month an invoice happened to be printed. The issued basis reads **11.55%** where this reads **9.00%** for July — a 2.55-point swing. The ruled basis now carries **no problem code at all** (a report still apologising for a settled question reads as a number about to change), and the issued basis is still served and NAMES itself as not the ruled one. |
| OQ-204 | **Is S74 a Finance sub-view or a reports-viewer report — and are S73/S74 ratified into A1?** | Navigation and the download contract only; the computation is unaffected | Product Owner (chat session) | **OPEN** |

**WHY OQ-202 CHANGES THE ANSWER, with the figure.** Bills issue in arrears: Brazos Bend issues July's bills on **Aug 3** for the July service period. Count the bills **ISSUED IN JULY** and the denominator is **June's** deliveries — **884,500 gal** — so the July purchase of 1,000,000 gallons is compared against a different month's water and the figure reads `(1,000,000 − 884,500) ÷ 1,000,000 = 11.55%` instead of **9.00%**. A 2.55-point swing on the headline loss number of the product, purely from a basis nobody labelled. **BR-REP-001 already forbids an unlabeled money figure**; this is the same requirement one level out, and the basis is not derivable from any signed rule — the posting basis serves the books and the service period serves the physics, and both are defensible. Nothing is chosen: the report carries the problem code `billed_volume_period_basis_is_not_ruled` until it is.

**REPORTED, not resolved — the ledger read model may not import billing.** `01-overview.md` v5.1 records that *"a report never recomputes money: no import of billing, payments or customers exists in either file, and a test asserts that on the source"*. The billed VOLUME is not money, but the assertion is on the import, not on the value — so this read needs a published billing selector seam (the `apps/billing/selectors` shape G20 already harvests) rather than a new import. Which file it lands in is the eng lane's call and is named here so it is not discovered at build time.

---
id: US-LED-021
epic: EP-LED-06
module: ledger
screens: [S42, S43]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-018, US-LED-019, US-LED-016, US-LED-015]
journeys: [J25]
rules: [BR-LED-039, BR-LED-004, BR-LED-017, BR-LED-015]
golden_tests: []
finance_calc: proposed
---
### US-LED-021 — The cost-of-service section of the accounting export (S42/S43): both sides leave in one idempotent batch

**1 · Details** — As a System Admin or Billing Clerk, I want the period's handover to accounting to carry **both sides** — the receivable side it already carries (US-LED-016) **and** the captured payable side — because "capture, hold, reconcile, **export**" is the whole of what the PO ruled the product does with AP (OQ-188), and because the real payables live in the tenant's QuickBooks or Xero where they always did. The **S42 GL summary gains a cost-of-service section** (BR-LED-039): one summary row per period per cost GL account, addressed by the same mapping-page export codes (BR-LED-014), inside **the same recorded, idempotent `export_batches` row** keyed on (period, target) — **not a second batch**, because two handovers for one month is exactly the double-handover BR-LED-004 exists to prevent, and a utility reconciling its ERP would find the same July twice. The **S43 send modal's balanced preview** shows the cost rows in the totals it already balances, and **export still requires the period CLOSED** (BR-LED-017, the L-3b gate: the ERP never receives numbers that can still move). Drill-back applies unchanged — "what is the $28,222.00?" opens the Brazos Valley Power Cooperative invoice behind it. **The SHAPE of these rows depends on OQ-200**: if capture posts, they are ordinary GL summary rows read out of the books like every other row on the page; if it does not, the section is register-derived and must be labelled as such so a reader never adds it to a trial-balance total that does not contain it. Entry: S42, after US-LED-015's close. Exit: J25 steps 10–11's handoff — one batch, both sides, re-run blocked.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-039 | The accounting export carries the payable side out beside the receivable side: one summary row per period per cost GL account, in the SAME idempotent (period, target) batch. | CONFIRMED that the export carries it (PO 2026-08-12, OQ-188 — *"capture, hold, reconcile, export"*); the row SHAPE (journal-derived vs register-derived) **blocked on OQ-200** |
| BR-LED-004 *(consumed)* | One summary JE per period per GL account; batches recorded + IDEMPOTENT; every figure drills back; dimension CSVs. | CONFIRMED — PO LF-4, 2026-08-08 (LE-5) |
| BR-LED-017 *(consumed)* | Export requires the covered period CLOSED; granularity flexible per export. | CONFIRMED — PO L-1 + L-3b, 2026-08-08 |
| BR-LED-020 *(consumed)* | File/batch export v1; direct connect (QBO/Xero OAuth) v2 — so the payable side leaves as a file, not as a live sync. | CONFIRMED — PO L-5 + L-2, 2026-08-08 |
| BR-LED-015 | The export (a money handover) writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | Export July to QuickBooks after close | The batch carries LE-5's existing 8 receivable rows **plus 5 cost rows** — 5100 **$28,222.00** · 5110 **$3,100.00** · 5140 **$6,235.00** · 5200 **$1,845.50** · 5300 **$12,500.00**, Σ **$51,902.50** — each with its `qbo_ref`; ONE batch `EXP-2607-QBO`, one hash, one audit row |
| TC-2 *(negative — idempotency)* | Re-run July to QBO after the cost section exists | **Blocked with a link to the existing batch** (BR-LED-004). Adding the payable side does NOT create a second July batch — a utility must never receive one month twice |
| TC-3 *(negative)* | Export attempted for a period that is still OPEN | Refused — BR-LED-017's L-3b gate is unchanged by this section; the refusal writes a security-event attempt row (BR-AUD-018) |
| TC-4 | Drill-back on a cost row | "What is the $28,222.00?" opens **BVPC-070026, Brazos Valley Power Cooperative, 412,000 kWh, 2026-07-31** — the same discipline BR-LED-004 requires of every exported figure |
| TC-5 *(negative)* | A cost account has no `qbo_ref` | Export to QBO blocked **naming the account** (the US-LED-006 TC-5 atomic-fail pattern); code-addressed CSV and IIF remain available |
| TC-6 *(negative)* | A voided purchase (RS-2607-0192) sits in the period | Excluded from the exported section; the batch hash reflects the live set only |
| TC-7 *(negative — the honesty guard)* | Under OQ-200 reading (b) the cost section is register-derived while the receivable rows are journal-derived | The section is **labelled as register-derived** and its total is **not** added to the trial-balance footer; an unlabelled mixed total is a figure no reader can reconcile, and it is the failure this TC exists to catch |
| TC-8 *(isolation)* | Lone Star Ridge exports its own July | Its own cost rows, its own refs, its own batch series; no Brazos Bend purchase appears in its payload or its hash (RLS FORCE) |

**4 · Test Data** — LE-14: July 2026 → QuickBooks Online, batch `EXP-2607-QBO`, sent 2026-08-08 by Norma Reyes. Receivable rows = LE-5's 8 GL rows (Σ DR 598.69 = Σ CR 598.69). Cost rows: 5100 $28,222.00 · 5110 $3,100.00 · 5140 $6,235.00 · 5200 $1,845.50 · 5300 $12,500.00 = **$51,902.50**. QBO refs for the cost section are unset in the fixture → TC-5's atomic block fires until Norma sets them (5100→`412`, 5110→`413`, 5140→`414`, 5200→`420`, 5300→`430`). Extract filename per IS-11: `brazos-bend_cost_of_service_2026-07_posting_20260808.csv`. Isolation: Lone Star Ridge (J. Okafor).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Cost-of-service summary rows | S42 | BR-LED-039 | Σ per cost GL account per period — **from `journal_lines` (OQ-200 reading a) or from `supplier_invoices` (reading b)** | numeric(18,6) | computed-display | source labeled; voided rows excluded |
| Export codes on cost accounts | S56 mapping | BR-LED-014 · US-LED-006 | `ledger_accounts.qbo_ref` / `.xero_ref` | text | user-input | required per target; missing → atomic block naming the account |
| Batch | S42 history | BR-LED-004 / r13 #4 | `export_batches` (period, target, who/when, content hash) | row | system-derived | UNIQUE (period, target) — the cost section rides the SAME row |
| Balanced preview | S43 | US-LED-016 §5 | computed (entries, Σ DR, Σ CR) | numeric(18,6) | computed-display | must balance before send; mixed-source totals labeled (TC-7) |
| Drill-back on a cost figure | S42 | BR-LED-004 | figure → its `supplier_invoices` row(s) | rows | computed-display | every figure, always |
| Cost dimension CSV | S42 | BR-LED-004 + IS-11 | streamed CSV by service/supplier/account | file | computed-display | sums tie to the exported section; money-export audited |
| Audit | — | CLAUDE.md #7 · BR-LED-015 | `audit_log` `export.batch_created` (target, hash) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a closed July and nine captured purchases, Then one batch carries both sides — the 598.69 receivable summary and the $51,902.50 cost section — with export codes and a single content hash.
- Given a re-run, an open period, or a missing export code, Then the export refuses exactly as it does today; adding the payable side loosens no existing gate.
- Given a register-derived section, Then it is labelled and never silently summed into a journal-derived total.
- Given a voided purchase or another tenant, Then it is out of the payload and out of the hash.

**7 · Finance Calculation** — **PROPOSED** (the arithmetic is settled; the row SHAPE is OQ-200's). Cost section Σ = `28,222.00 + 3,100.00 + 6,235.00 + 1,845.50 + 12,500.00 = **51,902.50**`. Under OQ-200 reading (a) these are debits and the July trial balance moves from LE-1's **598.69 = 598.69** to **52,501.19 = 52,501.19** — which is a change to a finance-signed example (**GT-51** by B5's LE-n → GT-(50+n) allocation) and needs the HUMAN-GUIDE §6 re-sign route, not a lane's decision. Under reading (b) LE-1 is **unmoved** and the section is a labelled register extract. **Both are worked so the PO is choosing between two stated consequences, not between two words.**

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-200 | **Does capture post a journal entry, and what is the credit side?** — decides whether this section is journal-derived or register-derived, and whether LE-1/GT-51 moves. | Nothing — closed and implemented | Product Owner (chat session) | **CLOSED 2026-08-16 — reading (b) for R2.** The section is REGISTER-DERIVED, labelled as such in three places, kept OUT of the trial-balance footer, and its problem code changed from `posting_shape_is_not_ruled` to `cost_section_is_register_derived` — because a payload still calling a ruled question open reads to a finance officer as a number about to change. **LE-1 is unmoved at 598.69 = 598.69 and GT-51 does not need a re-sign.** |
| OQ-203 | An edit permitted after close (US-LED-019) changes a section already handed over, and BR-LED-004 blocks a second batch for the same (period, target). | Nothing — closed, and this epic carries the answer | Product Owner (chat session) | **CLOSED 2026-08-16 — the edit is permitted AND the already-exported month is named.** `exports.stale_batches` recomputes each recorded batch's cost section over the window it covered and compares it against what the batch CARRIED, so no writer has to remember to flag anything. The warning renders at the top of S42 with both figures and their currency, and the same fact is returned at the moment of correction on S73. |
