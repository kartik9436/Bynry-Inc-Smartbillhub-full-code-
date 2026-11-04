# features/tenancy — tenant provisioning, subscription, tenant settings

Docs: `04-docs/05-modules/01-tenancy/`.

Shipped here: the S1/S110–S114 signup wizard, the S62 onboarding checklist, and
**S8 Settings** — the tab frame (`SettingsPage.tsx`) plus the tab bodies that
belong to tenancy (Company, Regional, Services & UoM, Configure's four
children, and **Accounting**). Users & roles and Security live in
`features/identity/` and are mounted by the same frame.

---

## S8 → Accounting — the GL code mapping (added 2026-08-11)

**Why it exists.** The Product Owner made two rulings on 2026-08-11 and both
were built into the API with no screen behind them:

| Ruling | Verbatim | Rule |
|---|---|---|
| OQ-115 | *"A, you create an account, but allow tenant user to override it - also note every Utility may not have all the services."* | **BR-BIL-067** |
| OQ-116 | *"For each atheority have separate account and tagging; but also ensure you allow Use to manage it since every utility may not have every account"* | **BR-BIL-069** |

`PUT /api/settings/services/<service>` has accepted `revenue_account` and
`base_revenue_account` since the OQ-115 backend lane landed, and
`07-frontend/src/api/endpoints.ts` declared neither — so a tenant could not
exercise a ruling the PO made and the server honours. That is the DEF-007..010
"built is not wired" class, and G13 exists because of it.

**Where it lives.** `/{tenant}/settings/accounting`, a top-level Settings tab.
The PO closed OQ-106 with *"it will be done during GL cod emapping in
settings"*; the prototype names the destination twice in its own words —
`05-prototype/UtilityBilling.html` lines 3714 and 3930 both send the reader
from the read-only Finance panel to **"Settings → Accounting"**. That two-
segment path is why this is a tab and not a fifth child of Configure.
⚠ **Nine tabs, where CR-001 measured that eight fit on one line.** OQ-151 puts
the placement to the PO; moving it is one `SETTINGS_TABS` line, one
`CONFIGURE_SUB_TABS` entry and one `LEGACY_SETTINGS_TAB_PATHS` redirect.

⚠ **No A1 screen id owns this surface.** A1 gives S8 to Settings and S56 to the
Finance → General ledger tab; `US-BIL-009` declares `screens: [S56, S66]` and
S66 is *Billing defaults*, a different screen. Rendered under S8 and reported —
never renumbered (hard-won law 8). OQ-151 carries this half too.

### The API this screen uses, and the one it is waiting for

| Route | Served? | What it carries |
|---|---|---|
| `GET /settings/services` | **yes** | each service + `revenue_account` / `base_revenue_account` as `{id, code, name}` or `null` |
| `PUT /settings/services/<code>` | **yes** | the BR-BIL-067 override. `null` CLEARS; an omitted field leaves the pointer alone |
| `GET /taxes` | **yes** | `jurisdiction.authority` + `liability_gl_account_id` |
| `PATCH /taxes/{id}` | **yes** | the BR-BIL-069 write (`liability_gl_account_id`) |
| `GET /ledger/accounts` | **NO** | the chart of accounts. Contracted at 11b §S56, owned by US-LED-005; `apps/ledger/api.py` has no `urlpatterns` and `config/urls.py` no ledger include |

**The chart's absence is DERIVED from its 404** (`chartRouteAbsent`), never
from a build flag, so the pickers fill by themselves the day the ledger lane
mounts the route — same idiom as `listRouteAbsent` on `GET /invoices`.

### The two halves behave differently on purpose

**Service revenue — a working fallback.** Without the chart, the picker offers
the DISTINCT accounts the served service rows already point at. Those are not
guesses: they come from `tenancy.selectors._account_ref` and are live accounts
of this tenant's chart. For BR-BIL-067's own worked tenant — Silver Creek
Water, seeded `4110 · 4115 · 4120` and nothing else — that IS their revenue
chart. The panel labels the list *"only the accounts your services already post
to, not your whole chart of accounts"*, so it is never read as complete.

**Tax liability — deliberately NOT that fallback.** A liability account is
2200-series; the fallback is 41xx revenue. The server validates ownership and
liveness and **not** the account's `type` (a stated non-decision, decision log
2026-08-11), so offering the revenue list there would let a tenant remit sales
tax into water revenue and the product would accept it. The control is drawn,
**disabled, carrying that reason**, and is fully wired to `PATCH /taxes/{id}` —
its test asserts the request path and body, so it works the day the chart lands.

### What US-BIL-009 asks for and this screen does NOT draw

Charge-code GLs (a read-only echo, edited on S12) and the AR /
deposit-liability / opening-clearing / write-off **designations**. No endpoint
serves either, and an empty section implies a mapping exists where none is
readable. Named here rather than left as silence.

### Open questions this screen does not answer

`OQ-145` (does adding an authority auto-mint its 2200-nn account?) ·
`OQ-146` (a tax whose authority has no account: refuse at issue or at setup?) ·
~~`OQ-147`~~ (CLOSED 2026-08-12 — the product generates the 2200-nn suffix; nobody types one) · `OQ-151` (tab placement + the
missing A1 row).

---

## The two settings of 2026-08-12, given screens on 2026-08-15

Both are S8 → **Configure** → Reference data → a rule-page card, drawn by the
one `RulePageView` shell (BR-SHL-035). Click by click:

| Setting | Path | Control |
|---|---|---|
| `allocation_class_order` (S66) | Settings → **Configure** → *Billing defaults* card | `SettingsAllocationOrder.tsx` — an ordered list with Move up / Move down on every row, plus a worked example that recomputes live |
| `tax_remitting_basis_by_authority` (S71) | Settings → **Configure** → *Finance controls* card | `SettingsRemittingBasis.tsx` — one row per tax authority, each choosing *what you billed* or *what you collected*, or nothing |

**Why they needed screens at all.** The storage, the validation and the callers
all landed on 2026-08-15 (`apps/payments/services.tenant_class_order` and
`apps/ledger/reporting._remitting_basis_by_authority` both read them) and the
client mirror `settingsRulePages.ts` named neither, so no user could reach
either. That is the DEF-007..010 *built is not wired* class — hard-won law 2 —
in its fourth week.

### Three decisions inside those two controls

1. **No "restore the shipped order" button.** The default order lives once, on
   the server; a copy here would be free to drift from the one the engine walks.
   A move is its own inverse and Discard restores the saved order.
2. **No default basis, anywhere.** The server seeds the map EMPTY because LE-3
   has State on *collected* and County on *billed* in the same month, so any
   default is wrong for one authority in month one. An unset authority renders
   as **Not set**, clearing a choice DELETES the key, and the panel says what
   unset costs. A single `?? "billed"` would undo all three — which is exactly
   what `SettingsRemittingBasis.test.tsx` was proved RED on.
3. **The worked example is an illustration, not a money path.** Five fixed
   figures from the PO's own ruling, walked in exact `bigint` integer
   arithmetic, rendered through `MoneyCell`. No tenant bill, payment or balance
   is read. Measured: the same walk in IEEE-754 doubles pays **11.120000000000001**
   where the ruling says 11.12.

### OQ-194 — where the per-authority control lives

**OPEN. This lane built option (b)** — its own control on Finance controls,
beside the storage — for one reason it did not decide and one it found:

* the PO ruled on 2026-08-12 that GL configuration lives *"under Configure"*
  (OQ-151), and Finance controls is under Configure while **Accounting is still
  a top-level tab** (that move is OQ-151's other half and is not this lane's);
* **option (a) is not implementable today.** The setting is keyed by the
  authority's **2200-nn GL account CODE** (BR-BIL-069). The Accounting tab's tax
  table carries `liability_gl_account_id`, a **uuid**, and `GET /ledger/accounts`
  is still unserved — which is why that table renders "mapped, unresolved"
  rather than a code. It cannot produce the key.

The authority list therefore comes from **`GET /finance/taxes`** (S41's own
read, served): one row per tax-payable account with `code`, `name` and the
stored `remitting_basis`. It is the report that CONSUMES the setting, so the
rows a utility chooses on are the rows they read the choice back on. It requires
a period; the screen passes the tenant's own `current_period` (BR-TEN-022) and
says so when no fiscal calendar is set. The row SET does not vary with the
window — only the money columns do, and this screen draws none.

### What this lane found and did NOT fix

* **`back_bill_segment_estimate_source` (S71) is still unwired** — a third
  parameter, in the backend registry since 2026-08-12 (OQ-191) and in no
  `RulePage` here, so a tenant cannot choose between `day_weighted` and
  `metering`. Left to the back-bill lane, whose `apps/billing/backbill.py` reads
  it; two lanes adding the same mirror row is how one gets dropped.
* **DEF-095** — `reportQuery` sends every finance report's period as
  `f.from`/`f.to` and the server reads `from`/`to`, so S36/S59/S60 ask for a
  window nothing reads. This module's own `getRemittanceByAuthority` sends them
  plain.

---

## Prototype conformance (hard-won law 6)

| Where | Prototype | Shipped | Verdict |
|---|---|---|---|
| Settings strip | ten tabs, no "Accounting" | nine tabs, including Accounting | **deviation, deliberate** — the prototype's own copy names "Settings → Accounting" and never draws the tab. Also carries CR-001's earlier divergence (eleven → eight, "Configure") |
| Finance → General ledger | read-only `Account mapping` panel, Source / Posts to | not built here — S56 is the Finance lane's | **behind** — the read-only twin still owes its screen |
| The mapping's own shape | Source / Posts to, five rows incl. charge codes, tax and write-offs | Service / Usage account / Base account, plus Authority / Tax / Liability account | **deviation** — the prototype's five rows collapse services, fees, tax and write-offs into one list; BR-BIL-067 and BR-BIL-069 make services and authorities separately editable, and the fee/write-off rows have no served read |
| "Edit in Settings → Accounting" | a hint on the Finance panel | that destination now exists | **prototype was right, and we were behind** |

G14 does not guard Settings top-level tab labels (`TAB_LABEL_KEYS` covers Plans
& Rates, Assets and Company's two sub-tabs only), so **nothing catches these
divergences automatically** — the same hole CR-001 recorded from the other
side. Reported, not silenced.
