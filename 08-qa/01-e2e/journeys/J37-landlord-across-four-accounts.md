# J37 — A landlord across four accounts, master over common areas (`$142.18 + $0.00 + $318.04 + $412.60 = $872.82`, never merged, and the tenants' own accounts nowhere in the set)

---
id: J37
tier: 2
rules: [BR-CWP-008, BR-CWP-009, BR-CWP-010, BR-CWP-013, BR-CWP-014, BR-CWP-015, BR-CWP-016, BR-CWP-033, BR-CWP-039, BR-CWP-047]
stories: [US-CWP-021, US-CWP-023, US-CWP-024, US-CWP-026, US-CWP-027]
# Wiring: every story above cites `J37` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J37.spec.ts`. Release 2.
# ⚠ `US-CWP-026` is BLOCKED on OQ-1397 (does a landlord see a tenant's bill?).
# FLAT is the only safe model until it is ruled — adding access later is a
# change, taking it away after a landlord has had it is a complaint. Step 7
# asserts the boundary; nothing here widens the set.
---

**Intent.** A landlord is a first-class case, not an edge case: the data model already
joins one customer to many accounts and already understands a **master account over a
building's shared supply**, billed to the landlord. The portal renders what the model
permits and adds **no second code path**. Two things carry the journey: the session holds a
**set, not an identity**, and **the set is flat** — the master is one more entry, not a
parent, and confers nothing over anybody else's account. Balances are shown **separately
and totalled for information**; they are **never merged into one invoice**.

**Upstream leaves (handoff in).** Tenant `pine-hill` live. One customer **Maria Alvarez** /
*Alvarez Properties*, four accounts through the existing many-to-many
`customer_account_link`: `1408 Elm St · A` `$142.18` DUE 14 Sep, *tenant billed* · `1408
Elm St · B` `$0.00` CLEAR, *tenant billed* · `1408 Elm St · Common areas` `$318.04` DUE 14
Sep, **master, `is_master_common_area`, billed to you as owner** · `22 Palm Ct` `$412.60`
OVERDUE 19 DAYS (due 14 Aug), *tenant billed*. **Two tenant accounts** at `1408 Elm St · A`
and `· B` (`ACC-10432-B-TENANT` among them) held by the tenants themselves. A fifth account
`ACC-10519-C` at `1408 Elm St · C`, postcode `78702`, contact `(512) 555-9037`, not yet in
Maria's set. No-contact account `ACC-10777-A`. Out-of-set account `ACC-99999-Z`. Tenant
`oak-ridge` with an account numbered identically to one of Maria's. Two unread messages.
Clock **2 Sep 2026**.

**This journey leaves (handoff out).** Maria's `portal_session.account_set` with **five**
flat entries after step 8 (a new `customer_account_link` for `ACC-10519-C`), ONE outbound
row to `(512) 555-9037`, audit rows for the add. **No merged invoice, no change to any
balance, no entry for any tenant's account.** J44 (delegates) starts from this session.

**Fixture.** Screens `CWP-020` (add another account), `CWP-023` (all my accounts),
`CWP-022` (home, re-scoped by the switcher). Filter chips *All · Owing · On a plan*.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (set · query · read · isolation) | Rule |
|---|---|---|---|---|
| 1 | Maria signs in; read the session | Tenant, person, and **four flat entries** — one of them the common-areas master — **not a parent**, and **the tenants' own accounts are not in the set**. Built from exactly two sources: her customer-to-account links and delegate grants; nothing else may add an entry | The URL strip reads *Alvarez Properties · 4 accounts*. The switcher is a real `<select>` of four addresses | BR-CWP-008 · BR-CWP-009 · BR-CWP-013 |
| 2 | `CWP-023` — *Four accounts on this login* | `DataTable`: Service address (bold + grey *Tenant billed* / **Billed to you as owner**) / Services / Next due / **Balance** / Status: `1408 Elm St · A` 14 Sep `$142.18` DUE · `· B` — `$0.00` CLEAR · `· Common areas` 14 Sep `$318.04` DUE · `22 Palm Ct` 14 Aug `$412.60` OVERDUE 19 DAYS. Toolbar right: **Total owing `$872.82`**. Row actions icons 👁 💳. Footer *Showing 1–4 of 4 · Rows per page 50* | **`142.18 + 0.00 + 318.04 + 412.60 = 872.82`** — Σ of four per-account reads, **information only**. Assert the response body names **four** account ids **and no fifth**. Each read is `US-CWP-024`'s: issued non-void invoices less allocations less unspent credits, the replacement of a corrected pair counted once, stored to 4 dp, displayed 2, **never cached** | BR-CWP-015 · BR-CWP-047 · hard rule 2 |
| 3 | **negative · never merged** | There is **no invoice** whose total is `$872.82` and no route that would create one. Filter *Owing* → **three** rows; `· B` at `$0.00` drops out. A single-account householder sees **one row and no total line** — a total of one number is noise | The master row's difference is **a billing fact, not a permission**: it is billed to the landlord and its usage is a building's shared supply | BR-CWP-015 · BR-CWP-014 |
| 4 | Switcher → `22 Palm Ct` | **Every** tab reloads against `22 Palm Ct` — Bills, Usage, Payments, Requests — not just the one in view. Home's lead tile now reads `$412.60` OVERDUE 19 DAYS and the attention panel offers *Ask for a plan* (J43) | The scope is applied **in the query**, never by the screen — the switcher is a convenience; the guard is the query | BR-CWP-010 · `US-CWP-023` TC-2 |
| 5 | **negative · the master confers nothing** — with the landlord's session, request a **tenant's** account (`ACC-10432-B-TENANT`) by id, directly; then force the switcher to `ACC-99999-Z` | Both **refused server-side**, and the refusal **does not reveal whether the account exists**. A crafted session naming the tenant's account is refused because the set is **re-derived from the two sources on read**, not trusted from the token | The tenants' accounts appear in **no** table, **no** total and **no** switcher | BR-CWP-013 · BR-CWP-009 · `US-CWP-026` TC-3/4 |
| 6 | `CWP-020` — *Add another account*: `ACC-10519-C` + `78702` | `ConsequenceBox`: *Adds 1408 Elm St · C to your list · Sends a code to that account's contact · **Nothing is combined — bills stay separate***. Rail **ALREADY ON THIS LOGIN** with a brand count **4** and four address/money rows | **The code goes to the account being added, not to the person adding it** — assert the outbound row's destination is `(512) 555-9037`, **not** Maria's `4218`. Otherwise anyone with one account and a stolen bill number collects a second | BR-CWP-033 · BR-CWP-039 |
| 7 | **negative** — right number, wrong postcode; an account already in the set; `ACC-10777-A` (no contact) | Wrong postcode → refused **identically** to an unknown number. Already held → refused as already held. No contact → **dead-ends into "ring the office"**, no code generated | The lockout and throttle of the public forms do not apply here — this is a signed-in write, audited under Maria's name | `US-CWP-027` TC-2/4/5 |
| 8 | Code verified → the account joins the set | The switcher lists **five**. A new `customer_account_link`; the set is **re-derived** and now has five flat entries | **Bills, balances and payments stay separate** — assert no merged invoice exists and `CWP-023` shows five rows with *Total owing* = Σ five reads | BR-CWP-009 · BR-CWP-015 |
| 9 | **boundary · `OQ-1397`** — the common-area reconciliation read (`CP-54`) | `NotImplementedError("OQ-1397")` — the id in the code. Whether a landlord may see a **tenant's bill** has a legal answer that **varies by state**; the screen is drawn as though the answer were **no** | The master-meter-against-sub-meters figure (`PremisesSubmeterReconciliation`) is **PROPOSED, not signed**, and stubbed. Until ruled, the flat set is the only safe model | BR-CWP-016 · `OQ-1397` |
| 10 | **tenant isolation** | The totalled read sums **Pine Hill** accounts only — proved with the identically numbered Oak Ridge account in the fixture. Oak Ridge's account number on `CWP-020` → refused. Oak Ridge's branding never renders inside a Pine Hill session | Every query filtered on **both halves**; RLS `FORCE`; `app.tenant_id` from the path | BR-CWP-010 · hard rule 1 |
| 11 | **INVARIANCE** | The set was **flat** in every step; the master was one more entry and conferred nothing; no invoice was ever merged; no tenant's account was ever in the set, the table, the total or the switcher. The bell reads `2` for two unread messages and `1` after one is opened (J47) | Every add wrote an audit row naming Maria; no balance changed | BR-CWP-013 · BR-CWP-015 · hard rule 7 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The master's reconciliation against the sub-meters, and any widening of the set to a tenant's bill | `OQ-1397` — a privacy question with a legal answer that varies by state. The flat set ships; the question blocks only widening it |
| b | *Pay several →* | Rails — release 5. The control is held in its normal place |
