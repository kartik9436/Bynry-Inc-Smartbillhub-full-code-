# J42 — A plan the utility offered, accepted on the customer's signature (`agreement_sent` → `active` with `customer_signed_on`, instalment 1 of 6 reading *To come*, and an offer that expires 16 September)

---
id: J42
tier: 2
rules: [BR-CWP-065, BR-CWP-063, BR-CWP-062, BR-CWP-084, BR-CWP-010]
stories: [US-CWP-053]
# Wiring: `US-CWP-053` cites `J42` in its `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J42.spec.ts`. Release 4.
# ⚠ THE JOURNEY THE BLUEPRINT'S §17 AUDIT WAS WRITTEN FOR. A plan record moves
# proposed → agreement_sent → active → closed, and the product is explicit that
# a plan ACTIVATES ON THE CUSTOMER'S SIGNATURE ALONE, not the clerk's. So
# `agreement_sent` means one thing — offered, waiting on the customer — and it
# is the only state where the customer has something to do. Three of the four
# states are drawn and this one was not: until this screen exists the utility
# raises a plan the customer cannot see, cannot accept, and hears about only if
# somebody rings them.
# `OQ-1391` does NOT block this journey: a plan the UTILITY offered needs no
# ruling on customer self-service.
---

**Intent.** A clerk builds a plan in the back office and the record sits at
`agreement_sent`. Nothing happens until the customer accepts — **the clerk's action alone
never activates it**. This journey gives the customer the screen: the plan, the
instalments, what accepting does, and three controls **in this order** — *Accept this plan ✓
· Ask for different terms · Decline* — because accepting is one press and *ask for different
terms* is a **route rather than a dead end**. The figures on the offer are **byte-identical
to the plan that activates**; a customer who accepts one schedule and receives another is
the worst outcome on this screen.

**Upstream leaves (handoff in).** Tenant `pine-hill`. **Sarah Miller** (a clerk) built a
plan on **2 Sep 2026** for Maria Alvarez's account **`$172.20` overdue**: `$40.00` **paid up
front, already received**, six monthly instalments from 14 Sep — five at `$22.03`, final
`$22.05`, total `$132.20` — `suspend_late_fees = true`, `suspend_disconnect = true`.
`payment_plan.status = agreement_sent`, **`offer_expires_on = 2026-09-16`**,
`customer_signed_on` **NULL**. The agreement document rendered in the existing document
class. The collections ladder still running on the `$172.20`. A delegate **J. Alvarez**
with *See · Pay* and **Kestrel Bookkeeping** with *See · Download* on the account (J44).
Notifications' fourth channel (portal) declared. Clock **3 Sep 2026**.

**This journey leaves (handoff out).** `payment_plan.status = active`,
**`customer_signed_on` = the moment Maria pressed Accept**, the same six instalments
untouched, instalment 1 of 6 *To come*; ONE `audit_log` row naming **Maria Alvarez** as the
signer; the ladder **paused for that debt** (J43 reads the hold with **no end date**). On the
decline branch: the plan **closed**, the arrears untouched, the ladder resumed. On the
*different terms* branch: ONE request for a clerk.

**Fixture.** Screen `CWP-063` (*Pine Hill has offered you a plan*) → `CWP-043` → `CWP-053`
(the message row *Pine Hill has offered you a plan*, about the plan, 2 Sep).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (state · signature · figures · isolation) | Rule |
|---|---|---|---|---|
| 1 | Maria signs in; `CWP-022`'s attention panel and `CWP-053` carry *Pine Hill has offered you a plan* (2 Sep) | The message row exists **because the event was already declared**; the bell's unread count includes it. **The portal WAITS** — the same offer went by post and email, the delivery record; a portal row is a record that a message exists, never proof it arrived | A customer who never signs in was still told by post. Any path treating this row as **delivery** of a notice raises `NotImplementedError("OQ-1399")` (J47) | BR-CWP-084 · BR-CWP-083 |
| 2 | `CWP-063` — *Pine Hill has offered you a plan. Sarah at the office set this up on 2 September. It starts when you accept it.* | **THE PLAN** `KVList`: *What it covers `$172.20` overdue* / *Paid up front `$40.00` — already received* / *Spread over 6 monthly instalments* / *First payment 14 September 2026*, footer *The last instalment carries the rounding.* Rail **THE INSTALMENTS** × 6 + `TotalRow` `$132.20`; ⓘ ***Nothing happens until you accept.** The offer stands until 16 September; after that the office has to set it up again.* *↓ Agreement* is the existing agreement document | *Sarah at the office* — **a person's name, never a user id** (rule 31). The figures are the **same instalment arithmetic as `US-CWP-051`**: `40.00 + 5 × 22.03 + 22.05 = 172.20` | BR-CWP-062 · BR-CWP-065 · B14 rule 31 |
| 3 | `ConsequenceBox` **WHAT ACCEPTING THIS DOES** | *Late fees stop on the $172.20 while you keep to it · No disconnection for that debt · **New bills still arrive and still have to be paid** · Miss two and the plan ends, and the whole balance falls due.* Then **three buttons, in this order**: *Accept this plan ✓* · `Button(outline)` *Ask for different terms* · *Decline* | The two suspensions are read from **this plan's** elections; a plan with `suspend_late_fees = false` would say fees still apply (J41 step 4) | BR-CWP-063 · BR-CWP-064 |
| 4 | **negative · doing nothing** — a week passes; a clerk edits nothing | The plan **stays `agreement_sent`**. **Nothing activates on the clerk's action alone.** The ladder keeps running on the `$172.20` | Assert `status` and `customer_signed_on` unchanged across the week | BR-CWP-065 · `US-CWP-053` TC-3 |
| 5 | *Accept this plan ✓* (`POST plans/{id}/accept`) on 5 Sep | `agreement_sent → active` **with `customer_signed_on = 2026-09-05T…`**. `CWP-043` opens: *1 of 6 · 14 Sep 2026 · $22.03 · TO COME*, the `$40.00` up front shown, cadence *monthly* from the record. ONE audit row naming **Maria Alvarez** | **The figures on the offer are byte-identical to the plan that activated** — assert the six instalment rows unchanged by the accept. The hold now shows on `CWP-064` with **no end date** — it lifts the day an instalment is missed (J43) | BR-CWP-065 · hard rule 7 |
| 6 | **negative · a signature is the holder's** — Kestrel Bookkeeping (See · Download) and J. Alvarez (See · Pay) each try *Accept* | Both **refused**. A delegate may see and pay; **the signature is the account holder's** | The refusal is five or six words and does not move the plan's state | `US-CWP-053` TC-7 · BR-CWP-017 |
| 7 | **negative · the expiry** — on a twin fixture nobody accepts by **16 Sep**; on 17 Sep Maria presses Accept | Refused with *"the office has to set it up again"*. The plan does not activate; `offer_expires_on` is the boundary | The screen said so on day one (ⓘ). An expired offer is not silently extended | `US-CWP-053` TC-4 |
| 8 | *Decline* (a third twin) | The plan **closes**; the arrears are **untouched**; the ladder **resumes** from where it stood. The closed plan stays visible on `CWP-043` marked closed (J41 step 8) | No money moved; no instalment row edited or deleted | `US-CWP-053` TC-5 · hard rule 4 |
| 9 | *Ask for different terms* (a fourth twin) | Raises a **request that reaches a clerk** (channel `customer_portal`) — **not a dead end and not a silent no-op**. The plan stays `agreement_sent` while the office considers it | Trackable on `CWP-051`; a clerk's revised offer arrives as a **new** `agreement_sent` row | `US-CWP-053` TC-6 · BR-CWP-076 |
| 10 | **tenant isolation** | The offer with an Oak Ridge session → refused; `POST plans/{id}/accept` with a Pine Hill plan id from Oak Ridge → refused, revealing nothing | RLS `FORCE` on `payment_plan`; both halves in the query | BR-CWP-010 · hard rule 1 |
| 11 | **INVARIANCE** | `agreement_sent` meant exactly one thing throughout — offered, waiting on the customer — and only the customer's press moved it. The instalment schedule never changed between offer and activation. New bills kept arriving and kept being due. The clerk's name appeared as a name and nothing on the screen was a database id | The `$172.20`, the `$40.00`, the `$22.03 × 5`, the `$22.05` and the `$132.20` agree with J41 to the cent | BR-CWP-065 · BR-CWP-062 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The offer **arriving** on the portal channel as delivery | `OQ-1399` — the portal waits; post and email remain the delivery record. The row's existence is asserted, its arrival is not |
| b | Paying instalment 1 from the plan screen | Rails — release 5 |
