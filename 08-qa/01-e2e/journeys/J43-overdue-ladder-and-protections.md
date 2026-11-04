# J43 — Overdue: the ladder, its cost, and the three protections (`$412.60 + $95.00 + $150.00 = $657.60` beside a button that stops it; three lifetimes, three sentences; a rung the vocabulary cannot name rendered as an absence)

---
id: J43
tier: 2
rules: [BR-CWP-089, BR-CWP-090, BR-CWP-091, BR-CWP-092, BR-CWP-051, BR-CWP-066, BR-CWP-063, BR-CWP-010]
stories: [US-CWP-057, US-CWP-058, US-CWP-059]
# Wiring: every story above cites `J43` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J43.spec.ts`. Release 4.
# ⚠ `US-CWP-058` is BLOCKED on OQ-1391 for the PLAN card only (step 6); the
# certificate route and level pay are not blocked.
# ⚠ TWO THINGS THE PORTAL MUST NEVER DO, and this journey asserts both: grant a
# protection itself (every one needs a person and a document), and imply a hold
# is permanent when it has an expiry.
---

**Intent.** The most uncomfortable screen in the portal and the most useful. Everything on
the timeline is already decided by configured settings — reminder cadence, notice tier
days, the plan-notice window — and it is read from **this account's own disconnection case**,
not from the cadence. Showing **the total cost of letting it run, next to a button that stops
it**, is the whole argument for putting collections in front of the customer. Three
protections have **three different lifetimes and need three different sentences**: a
certificate that **ends on a date and says so in words**; a plan hold with **no date** that
lifts the day an instalment is missed; a moratorium that is a fixed window **nobody applies
for** and has **no button**. And **a hold stops a disconnection; it does not stop the debt.**

**Upstream leaves (handoff in).** Maria Alvarez's session (J37) switched to **`22 Palm
Ct`**: `$412.60` overdue by **19 days** — due **14 Aug 2026**; reminder sent 21 Aug by
email and post; late fee **`$8.25`** added 24 Aug; **first notice sent 1 Sep by post**;
final notice *around 15 Sep* by hand or tracked post; disconnection *no earlier than 25
Sep*; this account's `DisconnectCase` (28 fields) naming which services would be cut,
reconnection fee **`$95.00`**, new deposit **`$150.00`**. A **second account** at the
**five-day** notice whose tier the vocabulary cannot name — `TIER_UNMAPPED`. A write-off
`$84.20` on the account with reason `customer_bankruptcy`. Protections on `1408 Elm St ·
A`: a **medical certificate** holding since 14 Aug 2026, **ends 30 Nov 2026**; a **plan
hold** (J41/J42's plan, current); the regulator's **winter moratorium 1 Dec 2026 – 1 Mar
2027** as a record with a start **and** an end. A **lifted** protection from 2025. An
account with **no** protection. Clock **2 Sep 2026**.

**This journey leaves (handoff out).** Nothing money-bearing; ONE request (a certificate
route, channel `customer_portal`) **that created no protection row**; a plan **ask** (J41)
carrying `$412.60`. Reads only otherwise.

**Fixture.** Screens `CWP-057` (*What happens if this is not paid*) → `CWP-056` (*Help
paying*) → `CWP-064` (*What is protecting your supply*).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (case · arithmetic · absence · isolation) | Rule |
|---|---|---|---|---|
| 1 | `CWP-057` — kicker **OVERDUE**, title ***$412.60 is overdue by 19 days*** | **WHERE THINGS STAND** `ChecklistTimeline` × 6: *Due · 14 Aug · $412.60* done · *Reminder sent · 21 Aug · by email and post* done · *Late fee added · 24 Aug · $8.25* done · **First notice sent · 1 Sep · by post** current · *Final notice · around 15 Sep · delivered by hand or by tracked post* · *Supply disconnected · no earlier than 25 Sep · reconnection is charged*. Actions *Ask for a plan* · *Pay $412.60* (**held**) | **The timeline is built from this account's `DisconnectCase` and `NoticeHistory`, not from the tenant's cadence settings** — two accounts at different tiers show different dates. Which services would be cut are named **from the case**. `14 Aug → 2 Sep = 19 days` | `US-CWP-057` TC-1/4/5 |
| 2 | Rail **WHAT IT WOULD COST** | `KVList` *Owed now `$412.60`* / *Reconnection fee `$95.00`* / *New deposit `$150.00`* → `TotalRow` ***If it goes that far `$657.60`***. `Panel.Warning` *A plan stops this **today**, and it can be asked for on this screen.* | **`412.60 + 95.00 + 150.00 = 657.60`** — the only arithmetic on the screen, and it must equal the three displayed figures. All three read from the tenant's settings and the case; stored 4 dp, displayed 2 | `US-CWP-057` TC-2 · hard rule 2 |
| 3 | **negative · the absence** — the second account, at the **five-day** notice | The tier renders as an **absence** in the timeline — **not** the ten-day tier's chip and **not** its date. Assert the screen does **not** show the ten-day date | `TIER_UNMAPPED` is returned by the code and the caller renders the absence. Rounding to the nearest tier **moves the date the customer thinks they have** | BR-CWP-092 |
| 4 | **negative · what is held back** — the write-off | Shows *written off · 12 May · $84.20*. **The response body contains no reason code** — `customer_bankruptcy` never surfaces | The amount belongs to the customer; the reason does not | BR-CWP-051 |
| 5 | *Ask for a plan* | Reaches `CWP-042` **carrying `$412.60`** (J41's mechanics) | The ask lands for a person; self-activation raises `NotImplementedError("OQ-1391")` | BR-CWP-066 |
| 6 | `CWP-056` — *Help paying your bill. There are three things we can do. Ask before the final notice and all three stay open.* | `CardGrid3`: **Spread it out** — a plan over up to twelve months · *Ask for a plan* (**held**) · **Someone here is unwell** — a doctor's certificate, ***"it has an expiry date and it is not permanent"*** · `Button(outline)` *Send a certificate* · **Level out next year** — budget billing · *Look at budget billing* (**renamed 2026-09-08, `CR-085` task (c)**: the wireframe's own Words note is *"'Budget billing' — what North American utilities call it. 'Level pay' is the internal name and never appears"*; the English catalogue leaked it in eight messages and the other ten never did). `InfoBar`: *Between **1 December** and **1 March** nobody is disconnected in this state, whatever they owe. **You do not have to ask for that.*** — **with no button** | **Three doors, and one is not a door**: the moratorium is stated as a **fact** — assert **no control exists** for it. The dates are **read from the moratorium record**, not written in prose — changing the record changes the sentence. With `plans_enabled = false` the plan card is absent and its endpoint refuses; the other two remain. Past the final notice the screen says **which routes are still open** rather than offering all three as though nothing had changed | BR-CWP-089 · BR-CWP-090 · `US-CWP-058` TC-2/6/8 |
| 7 | **negative · the portal never grants a protection** — *Send a certificate* | It becomes **a request a person judges** (channel `customer_portal`). **Assert no `AccountProtection` row is created by the form.** Uploading the certificate is **not possible** — consumer upload is deferred — and the route ends with *bring it to the office* | Every one of the three needs a person and a document | BR-CWP-089 · `US-CWP-058` TC-4/5 |
| 8 | `CWP-064` (switcher → `1408 Elm St · A`) — *What is protecting your supply. Three different things, and they do not last the same way.* | `ProtectionCard` **A DOCTOR'S CERTIFICATE**: `HOLDING NOW` *Since 14 August 2026* · **Ends on 30 November 2026** · ***This is not permanent.** On 1 December the hold lifts and the account carries on where it left off. Send a new certificate before then if it is still needed.* · *Send a new certificate*. `ProtectionCard` **YOUR PAYMENT PLAN**: `HOLDING NOW` *While the plan is kept* · **Ends on: no date — see below** · *This one has no end date because it is not a period. It holds while the plan is **current**, and it lifts the day an instalment is missed.* · *See the plan*. Rail `ProtectionCard` **WINTER MORATORIUM**: `STARTS 1 DECEMBER` · *From 1 December 2026 · Until 1 March 2027* · *Nobody is disconnected in this state between those dates, whatever they owe. **You do not apply for this** — it is set by the regulator.* · **no button**. `Panel.Warning` ***A hold stops a disconnection. It does not stop the debt.** Interest and the balance carry on underneath.* | **Three lifetimes, three sentences.** The certificate's expiry is told **in words**. The plan hold carries **no date** — **assert no expiry date is invented for it**. A certificate with **no end date** in the data is refused **upstream** by the product's own rule (*a permanent exemption nobody signed*) and this screen must not render one. A **lifted** protection shows as lifted with its date, not silently removed. An account with **no** protection: the screen and its link are **absent** — not three empty cards | BR-CWP-090 · BR-CWP-091 · `US-CWP-059` TC-2/4/6/7 |
| 9 | **negative · the middle card is the one that saves money** | A customer who believes the plan hold is permanent stops paying and is cut the week it lapses — so the card says it lifts **the day an instalment is missed**, and `CWP-057` for a protected account shows the hold **and why it is paused** | The debt continues underneath and the screen says so — that sentence is the finance-relevant content | BR-CWP-091 · `US-CWP-057` TC-6 |
| 10 | **tenant isolation** | `CWP-057`, `CWP-056` and `CWP-064` with a Pine Hill session read Pine Hill's case, Pine Hill's moratorium dates and Pine Hill's settings only; Oak Ridge's moratorium record never renders | RLS `FORCE` on `DisconnectCase`, `NoticeHistory`, `AccountProtection`; both halves in the query | BR-CWP-010 · hard rule 1 |
| 11 | **INVARIANCE** | `657.60` equalled the three displayed figures on every render; the five-day account never borrowed the ten-day date; no protection was created by any form; the certificate always named 30 November in words; the plan hold never gained a date; the moratorium never gained a button; no reason code left the server; an account not overdue saw **neither `CWP-057` nor its link** | Every timeline was this account's own case, never the cadence | BR-CWP-092 · BR-CWP-089 · BR-CWP-090 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The plan card **activating** a plan | `OQ-1391` — the ask lands for a person |
| b | A certificate **uploaded** by the customer | A signed deferral — staff-mediated uploads only |
| c | *Pay $412.60* | Rails — release 5; the control is held in place |
