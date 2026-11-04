# J33 — Guest reads an answer and ends at a person (eight written, six shown, a French reader gets English, and *No* is its own event)

---
id: J33
tier: 2
rules: [BR-CWP-093, BR-CWP-094, BR-CWP-022, BR-CWP-076, BR-CWP-007]
stories: [US-CWP-001, US-CWP-066, US-CWP-069, US-CWP-071, US-CWP-072]
# Wiring: every story above cites `J33` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J33.spec.ts`. Release 1.
# ⚠ `US-CWP-071` is BLOCKED on OQ-1398 (who keeps the answers current, in how
# many languages). That blocks MAINTENANCE, not the reads — this journey asserts
# the visible "needs translating" state and the English fallback, and does not
# promise a translation workflow.
# ⚠ The flow document (04-flows.md) says "a Spanish reader with no `fr` variant
# gets English"; the story (US-CWP-071 TC-6, US-CWP-072 TC-8) says a FRENCH
# reader with no `fr` variant. The `fr-FR` variant is the one that is
# `needs_translating` in the fixture, so the reader here is French. Filed as
# DEF-CWP-3605; the flow document corrected 2026-09-03.
---

**Intent.** The cheapest calls the portal deflects need no billing system at all: six
answers a utility has written, gated **in the query** to `status = published`, never a
count of what is hidden, and **every answer ending in a route to a person**. The one
localisation rule is *a missing translation is better than a missing answer* — a reader
whose language has no variant gets **English, not a blank**. And the smallest write in the
portal: a **read** and a **vote** counted **separately**, so the back office's read column
is not a column of zeroes (J46 continues that).

**Upstream leaves (handoff in).** Tenant `pine-hill` live. Eight `help_answer` rows in
`tenancy` in this **position** order: 1 *Why is my bill higher than last month?* BILLING
PUBLISHED 11 langs · 2 *What does "estimated" mean on my bill?* READINGS PUBLISHED 11 · 3
*How do I check for a leak?* WATER PUBLISHED 2 · 4 *When is my meter read?* READINGS
**DRAFT** English · 5 *Can I pay in instalments?* PAYING PUBLISHED 11 · 6 *What happens if I
pay late?* PAYING PUBLISHED 11 · 7 *How do I close my account?* MOVING PUBLISHED 2 · 8 *Who
is responsible for the pipe outside?* WATER **NOT SHOWN** English. Answer 1's
`help_answer_variant` rows: `en` PUBLISHED, `es-MX` PUBLISHED, `hi` PUBLISHED, eight more
PUBLISHED, **`fr-FR` NEEDS TRANSLATING**. Answer 1 has `also_show_on_screen = the bill
screen` and `1,204` reads this month. Customer Maria Alvarez enrolled (J35) with
`m.alvarez@example.com`, account `1408 Elm St · A`, bill `BL-2608-0141`. Tenant `oak-ridge`
with one published answer of its own.

**This journey leaves (handoff out).** `help_answer_feedback` rows: three `read` events and
one `not_helpful` event on answer 1 — **four rows, two kinds** — so `CWP-071` reads `1,207`
and the *No* count moves by one. ONE `service_request` (category `bill_question`, channel
`customer_portal`, naming `BL-2608-0141`) from the signed-in ask. **No change** to any
answer, any account or any money table.

**Fixture.** Public help `/pine-hill/help` (`CWP-011`), one answer `/pine-hill/help/bill-higher`
(`CWP-011/{slug}`, drawn as `CWP-060` for the signed-in reader), the ask `CWP-054`. Reader
locales: default `en`; a French reader `fr-FR`. Office `(512) 555-0148`, emergency `(512)
555-0100`. Main office shown to customers (so *Where you can walk in* is a live route — J34).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (query · feedback rows · worklist) | Rule |
|---|---|---|---|---|
| 1 | Guest opens `/pine-hill` → *Help & answers* (`CWP-011`) | **Six** rows, in **position** order: the six PUBLISHED answers, each with its TOPIC chip and `→`. Toolbar chips *All · Paying · Readings · Moving*. Rail **STILL STUCK?** with *Ask a question* and the office and emergency lines | **The gate is `status = published` in the query, not in the template** — assert the SQL, not the DOM. The response carries **no count of hidden answers** — no *"2 more"*, no `total: 8`. The `GuestFrame` header shows *Help* only because something is published | BR-CWP-094 · BR-CWP-093 |
| 2 | **negative · the two that never leave the back office** — request answers 4 (DRAFT) and 8 (NOT SHOWN) by slug | Both **not found**, identically. Draft and not-shown are **two different states** and neither leaves the back office | Assert the response bodies are byte-identical to an unknown slug | BR-CWP-094 |
| 3 | Opens *Why is my bill higher than last month?* **three times** | The answer page: kicker **BILLING**, the question as title, *Updated 2 September.*, the body, and **in-text actions** *See my bill* · *Compare in Usage* that go where the answer describes. Rail **STILL STUCK?** *Three ways, and all of them reach a person*: *Ask a question* · *Call (512) 555-0148* · *Where you can walk in*. Rail **ALSO WRITTEN IN** *Español (México) · हिंदी and eight more. Not yet in Français.* | **Three `help_answer_feedback` rows, `event = read`** → `CWP-071`'s read column moves **`1,204` → `1,207`** (J46 asserts the back office). *Where you can walk in* is present **only because** a centre is shown (`BR-CWP-093`; J34) | `US-CWP-072` TC-3/5/10 |
| 4 | Presses **No** on *Did this help?* | ONE `help_answer_feedback` row with `event = not_helpful` — **a distinct event from opening it**. Assert two event kinds, four rows total | Pressing *No* does **not** increment the read count a fourth time. Nothing else in the database changes | `US-CWP-072` TC-4 · `CP-34` |
| 5 | **negative · fallback** — a reader with locale `fr-FR` opens answer 1 | The **English** body renders, with a line saying so — **never a blank, never hidden**. The rail still reads *Not yet in Français.* | `help_answer_variant` for `fr-FR` is `needs_translating` and is **visible as a state** on `CWP-072`'s language table for the utility to see. **No translation workflow is promised** — `OQ-1398` | BR-CWP-094 · `OQ-1398` |
| 6 | Guest presses *Ask a question* from the rail | Routes to the **public** quick asks (`CWP-010`) — *A question about my bill* requires the bill number. A guest has no account to attach it to | The request lands with channel `customer_portal` and a reference; the guard applies — the 61st ask in a minute is refused | BR-CWP-028 · BR-CWP-022 |
| 7 | Maria **signs in** and opens the same answer (`CWP-059` → `CWP-060`), then *Ask a question* (`CWP-054`) | `CWP-059` adds only *"we already know which account you are asking about"* — nobody retypes an address. `CWP-054`: `Select` *What is it about?* → *a bill*; `Select` *Which bill* → `BL-2608-0141 · August · $142.18`; textarea *"My August water is nearly double July and nobody has been at the house…"*. Rail **MIGHT ANSWER IT NOW** lists three published answers; rail **OR RING** two lines, the emergency number distinct from the office number | *Send ✓* → ONE `service_request`, channel `customer_portal`, **already naming `BL-2608-0141`**, trackable by reference on `CWP-051`. A question with no bill selected is accepted as a general question and routed by category. The photo goes through the existing document store | BR-CWP-076 · `US-CWP-066` TC-1/2/5 |
| 8 | **negative · nothing empty ever appears** — unpublish all six on `oak-ridge`'s twin fixture | The help page, its **header link**, the *might answer it now* panel on `CWP-054` and the *Still stuck?* suggestions are **all absent** — no page, no *"no answers found"* | *Help* disappears from `GuestFrame` and *Help* from `PortalShell`'s header. The `AttachedAnswerCard` slot under a bill is absent too (J46 step 4) | BR-CWP-093 · `US-CWP-072` TC-7 |
| 9 | **tenant isolation** | `/oak-ridge/help` shows Oak Ridge's **one** answer only; `app.tenant_id` is set from the path **before** the content query. A Pine Hill slug under `/oak-ridge` → not found. Feedback rows are tenant-scoped; Pine Hill's `1,207` is unmoved by an Oak Ridge read | RLS `FORCE` on `help_answer`, `help_answer_variant`, `help_answer_feedback` | hard rule 1 · `US-CWP-001` TC-5 |
| 10 | **INVARIANCE** | No answer row changed; no account row changed; no money moved. Every rendered answer ended in a **route to a person** — a help page that dead-ends sends the reader to the phone anyway, only crosser. The customer was never told how many answers are hidden | The two hidden answers stayed hidden across every read and every locale | BR-CWP-094 · `US-CWP-072` |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Who translates the `fr-FR` variant, and when | `OQ-1398` — an ongoing job, not a build. The store, the statuses and the visible `needs_translating` state are asserted; a workflow is not promised |
| b | The answer's read count on the **back-office** screen | Asserted in **J46** (`CWP-071`), which this journey feeds |

## Walked, in a browser — added 2026-09-04 by the CR-068 wave D build lane

`10-scripts/render-checks/cr068-d-help-tips-centres.mjs`, steps 3 and 7. The
`fr-FR` reader is a real Playwright context with `locale: "fr-FR"`, so the
English fallback and the line that reports it are asserted on rendered output
and not on a mock. ⚠ The last screen (*Ask a question*, `CWP-054`) is wave I's
and this walk ends at the three routes to a person, exactly as this file says.
