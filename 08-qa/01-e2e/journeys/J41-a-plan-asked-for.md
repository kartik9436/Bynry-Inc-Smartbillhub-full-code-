# J41 — A plan the customer asks for, and keeps (`$172.20` less `$40.00` up front over six months = five of `$22.03` and a final `$22.05`, totalling `$132.20`, the remainder on the last one and shown)

---
id: J41
tier: 2
rules: [BR-CWP-062, BR-CWP-063, BR-CWP-064, BR-CWP-066, BR-CWP-010]
stories: [US-CWP-051, US-CWP-052]
# Wiring: every story above cites `J41` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J41.spec.ts`. Release 4.
# ⚠ BLOCKED ON OQ-1391 — can a customer GIVE THEMSELVES a plan, or must a
# person approve it? A CREDIT decision: the utility's appetite, not ours. The
# wording ships as "ask for this plan", the ask lands for a clerk, and the
# self-serve activation path raises `NotImplementedError("OQ-1391")` (step 5).
# ⚠ THE BLUEPRINT'S OWN CONSEQUENCE-BOX FIGURE WAS WRONG ("six payments of
# $22.03, then one of $22.05" — seven payments, $154.23 — beside its own table of
# six totalling $132.20). It is FIVE of $22.03 and one of $22.05. Use the
# corrected figures (US-CWP-051 §1).
# ⚠ FIXTURE NOTE: the flow document starts this journey on CWP-057, whose DRAWN
# figure ($412.60, 22 Palm Ct) is J43's. The plan arithmetic every story signs is
# on $172.20. This journey therefore runs on an account $172.20 in arrears, and
# names the difference rather than blending the two figures. Filed as
# DEF-CWP-3606; the flow document corrected 2026-09-03.
---

⚠ **AMENDED 2026-09-04 BY THE WAVE-M BUILD LANE — TWO OF THIS JOURNEY'S NOTES ARE STALE, AND
BOTH WENT STALE THE SAME DAY THEY WERE WRITTEN.**

**(1) `OQ-1391` IS CLOSED AND STEP 5 EXPECTS A STUB THAT MUST NOT EXIST.** The header says the
journey is BLOCKED on it and that *"the self-serve activation path raises
`NotImplementedError(\"OQ-1391\")`"*. The PO ruled on 2026-09-04 — *"Utility Clark will di it for
Consumer; COnsumer cannot do it by themself; these are special cases"* — closing it option (a),
and `BR-CWP-066` is CONFIRMED. **So there is no self-serve activation path to stub: there is no
such path at all.** `US-CWP-051` TC-10 asserts the REFUSAL instead, and a `NotImplementedError`
would be a door left in the wall. Steps 1–4 and 6–10 are unchanged and still exactly right.

**(2) STEPS 2 AND 7 PUT *"MISS TWO AND THE PLAN ENDS"* ON A CUSTOMER'S SCREEN, AND THIS PRODUCT
DOES NOT DO IT.** PO 2026-08-11: *"nodrop we chase for payments until write off"*, implemented as
an ABSENCE and tested. **Worked: two misses would end this plan and make `$66.11` fall due at once
under the blueprint; under this product the plan is still `active`, `$22.03` is still due on
14 February, and a notice goes out.** The collision is **`OQ-CWP-1720`**, OPEN and routed to the
Product Owner. Until it is answered no screen says a plan ends, and both screen tests assert the
absence. Step 10's INVARIANCE row is untouched — nothing the customer did activated a plan, no bill
was paused, and no payment or instalment row was edited.

**Intent.** A customer who cannot pay in one go spreads it, from the overdue screen, in a
preview that uses **the product's own instalment arithmetic** — which puts the remainder
**on the final instalment** rather than silently absorbing a cent, because a customer
comparing the plan against their bank statement will notice. The wording is **ask for**,
because whether a customer may self-serve a plan is the utility's credit appetite
(`OQ-1391`). Once granted, the customer sees **the whole plan**, not a monthly summary of
it — the down payment, the cadence read from the record, **which payment paid which
instalment**, and the sentence customers get wrong: **a plan holds the arrears; it does not
pause the current month's bill. New bills still arrive and still have to be paid.**

**Upstream leaves (handoff in).** Tenant `pine-hill` live with `plans_enabled = true`; plan
terms **two to twelve months**. A signed-in customer (Maria Alvarez's session) on an account
**`$172.20` in arrears** — the story's fixture — with the collections ladder running.
Tenant setting `suspend_late_fees` **left on** for the first plan; a second plan fixture
with `suspend_late_fees = false`. A **closed** plan from 2025. Exact-division fixture
`$120.00` over six. Clock **2 Sep 2026**; first payment **14 Sep 2026**. The existing
plan machinery: preview, instalment arithmetic, activation, missed-instalment events, plan
voiding, plan notices — all built.

**This journey leaves (handoff out).** ONE plan **request** for a clerk (channel
`customer_portal`) carrying the previewed schedule — **not an active plan**, until
`OQ-1391` rules otherwise. After a clerk grants it: ONE `payment_plan` (six instalments,
`down_payment = 40.0000`, cadence monthly, `suspend_late_fees = true`) whose instalments
J42 and J43 read; three paid instalments cleared by `PAY-26-09011`, `PAY-26-10004`,
`PAY-26-11077`. `CWP-064` (J43) shows the plan hold **with no end date**.

**Fixture.** Screens `CWP-057` (*Ask for a plan*) → `CWP-042` (preview, step 2 of 3) →
`CWP-043` (the whole plan). Instalments **14 Sep `$22.03` · 14 Oct `$22.03` · 14 Nov
`$22.03` · 14 Dec `$22.03` · 14 Jan 2027 `$22.03` · 14 Feb 2027 `$22.05` · Total `$132.20`**.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (arithmetic · request · record · isolation) | Rule |
|---|---|---|---|---|
| 1 | From `CWP-057` (the overdue screen for the `$172.20` account) — *Ask for a plan* | `CWP-042` opens **carrying the `$172.20`**. `Stepper` *✓ What you owe · **2** Choose the instalments · 3 Agree*. `Select` *Spread it over* **6 months** (helper *Between 2 and 12 months.*), `Date` *First payment on* 14 Sep 2026, money *Something up front?* **`$40.00`** (helper *Optional. It lowers each instalment.*) | The screen is unreachable **and the endpoint refuses** on a tenant with `plans_enabled = false`. The balance it starts from is `US-CWP-024`'s read, not typed | `US-CWP-051` TC-8 · BR-CWP-047 |
| 2 | The preview (`POST accounts/{id}/plans/preview`) | Rail **THE INSTALMENTS** `MiniTable` Due / Amount × 6 as the fixture, `TotalRow` **Total `$132.20`**, note *The last instalment carries the rounding.* `ConsequenceBox`: ***Five** payments of $22.03, then one of $22.05 · Late fees stop while you keep to it · Miss two and the plan ends.* | **The arithmetic, from the product's own instalment engine — previewed, never recomputed by the portal:** covered `172.20 − 40.00 = 132.20`; base `trunc(132.20 ÷ 6, 2) = 22.03`; `22.03 × 5 = 110.15`; final `132.20 − 110.15 = 22.05`; **Σ `= 132.20` exactly**. Stored to 4 dp, displayed 2. **The count in the copy matches the table — five, then one** | BR-CWP-062 · hard rule 2 |
| 3 | **negative · the edges** — thirteen months; up front `$172.20`; up front `$200.00`; `$120.00` over six | Thirteen → refused **naming the two-to-twelve range**. Up front equal to the balance → refused (*nothing left to spread*). Up front greater → refused. `$120.00 ÷ 6` → **six of `$20.00`, no odd final instalment invented** | The engine's remainder rule only fires when there is a remainder | `US-CWP-051` TC-4/5/6/7 |
| 4 | **negative · the per-plan election** — the second fixture with `suspend_late_fees = false` | The `ConsequenceBox` says **fees still apply** — it must **not** promise *late fees stop*. This is the case the blueprint singles out as *worse than a blank space* | Suspension of late fees and of disconnection is a **per-plan election**, not a global setting | BR-CWP-064 · `US-CWP-051` TC-11 |
| 5 | *Ask for this plan ✓* — then **boundary · `OQ-1391`** | ONE request lands **for a person** (channel `customer_portal`) carrying the previewed schedule. **The self-serve activation path raises `NotImplementedError("OQ-1391")`** — the id in the code. Nothing is active; the ladder keeps running until a clerk grants it | The three options are the PO's — ask only · self-serve inside limits the utility sets · self-serve outright. **A lane may not choose** | BR-CWP-066 · `OQ-1391` |
| 6 | A clerk grants it (payments, the existing activation); Maria opens `CWP-043` on 5 Dec | Title *Your plan is on track*, subtitle *Three of six paid. Next payment 14 December.* `MiniTable`: `1 of 6 · 14 Sep · $22.03 · PAID ON TIME` · `2 of 6 · 14 Oct · $22.03 · PAID ON TIME` · `3 of 6 · 14 Nov · $22.03 · PAID LATE` · `4 of 6 · 14 Dec · $22.03 · DUE IN 9 DAYS` · `5 of 6 · 14 Jan 2027 · $22.03 · TO COME` · `6 of 6 · 14 Feb 2027 · $22.05 · TO COME`. **`$40.00` paid up front** shown. Cadence *monthly* **read from the record, not assumed**. *↓ Agreement* is the existing document class | Instalment 2 **names the payment that cleared it** (`PAY-26-10004`) so the customer can match it to a statement — a field that reaches no screen today. **The whole plan**: `40.00 + 5 × 22.03 + 22.05 = 172.20`, **equal to the arrears it was raised against** — a plan silently covering the wrong figure is the defect this catches. `autopay_enabled` on the plan row is shown | `US-CWP-052` TC-1…4/10 · hard rule 2 |
| 7 | Rail **WHILE THE PLAN HOLDS** | *No late fees on the amount in the plan · No disconnection for that debt · **New bills still arrive and still have to be paid.*** `Panel.Warning`: *Missing **two** instalments ends the plan and the whole remaining balance falls due.* | On the `suspend_late_fees = false` plan the panel says **fees still apply**. **A plan holds the arrears; it does not pause the current month's bill** — the September bill still issued on 30 Aug and is still due 14 Sep on top of instalment 1 | BR-CWP-063 · BR-CWP-064 |
| 8 | **negative · two missed** — fixture: instalments 4 and 5 unpaid on 15 Jan 2027 | The plan **ends**, the whole remaining balance falls due, the ladder resumes — and the screen said so **before** it happened. The **closed** plan from 2025 is **still reachable**, marked closed with its close date — **not vanished** (a finished plan disappears from the portal today; it must not) | Existing missed-instalment events and plan voiding; the portal reads them | `US-CWP-052` TC-7/8 |
| 9 | **tenant isolation** | The preview and the plan with a Pine Hill session use **Pine Hill's** balance and settings only; a Pine Hill plan id with an Oak Ridge session → refused | RLS `FORCE`; both halves in the query | BR-CWP-010 · hard rule 1 |
| 10 | **INVARIANCE** | The instalments summed to the amount covered on every render; the remainder was on the **last** one and the screen said so; the count in the copy matched the table; nothing the customer did activated a plan by itself; no bill was paused; no payment or instalment row was edited | The portal **previewed** the engine's figures and recomputed nothing | BR-CWP-062 · BR-CWP-063 · hard rule 4 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | A customer **activating** a plan without a clerk | `OQ-1391` — a credit decision. The ask lands for a person; the path raises |
| b | *Pay the next one* | Rails — release 5; the control is held in place |
