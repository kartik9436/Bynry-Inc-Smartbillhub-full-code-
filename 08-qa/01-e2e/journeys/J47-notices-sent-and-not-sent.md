# J47 — A notice sent, a notice NOT sent, and post that came back (*Final notice · 15 Sep · post · not sent, no forwarding address* — the notice that never arrived is the one most visible)

---
id: J47
tier: 2
rules: [BR-CWP-083, BR-CWP-084, BR-CWP-085, BR-CWP-086, BR-CWP-088, BR-CWP-092, BR-CWP-093, BR-CWP-026, BR-CWP-010]
stories: [US-CWP-028, US-CWP-036, US-CWP-039, US-CWP-067]
# Wiring: every story above cites `J47` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J47.spec.ts`. Release 3.
# ⚠ BLOCKED ON OQ-1399 — IS THE PORTAL A CHANNEL A NOTICE CAN BE DELIVERED ON?
# The blueprint names it THE ONE TO ANSWER FIRST, before release 3 starts. A
# disconnection notice has legal delivery requirements; a portal message is
# not proof of delivery, and treating it as one "would be the most consequential
# mistake available here". It decides whether the portal is a convenience layer
# or a SYSTEM OF RECORD, which changes the audit, the retention and the legal
# review of nearly every paying and requesting screen. This journey builds the
# channel, the list and the read state; ANY PATH THAT TREATS A PORTAL ROW AS
# DELIVERY RAISES `NotImplementedError("OQ-1399")` (step 8).
---

**Intent.** *"I never got it"* is the second most common call, and the notice a customer
most needs to know about is the one that is **invisible today** — a **skipped** notice
produced **no document**, so the documents list cannot show it. Hence two screens: `CWP-031`
lists what was **sent** (a filtered read of a table that exists); `CWP-068` lists **every
notice sent and every notice deliberately not sent, with its reason**. Around them: the
other three channels **push**, **the portal waits** — it can never be the only channel for
anything with a deadline, and a portal row is **a record that a message exists, never proof
it arrived**; and **post that came back shows above the address field, and fixing the
address clears it.**

**Upstream leaves (handoff in).** J36's session for **Maria Alvarez**, `1408 Elm St · A`,
paperless (J45), **`bad_address = true`** with two `DeliveryReturnEvent` rows. `NoticeHistory`
for the account: *Reminder · 21 Aug · email and post · delivered* · *First notice · 1 Sep ·
post · **returned 8 Sep — not known at this address*** · *First notice · 1 Sep · SMS · **not
sent — you have text messages switched off*** · *Final notice · 15 Sep · post · **DUE TO GO**
on 2 Sep, then **not sent — no forwarding address** once the 15 Sep ladder step runs*.
`outbound_message` rows with the portal channel: *Your August bill is ready — $142.18*
(30 Aug, **unread**) · *We need two documents for your move-out* (`SR-26-0056`, 3 Sep,
**unread**) · *Your payment of $138.44 was received* (12 Aug, read) · *Water main work on Elm
St, 4–5 September* (28 Aug, read) · *Your June bill was corrected* (12 Jul, read) — 22 rows.
41 documents. A message the product **could not send** (`unavailable`, with reason). A
**paperless customer who has never signed in** since enrolment. A notice at an **unmapped
tier**. Tenant `oak-ridge`. Clock **2 Sep 2026**, then **16 Sep 2026**.

**This journey leaves (handoff out).** `outbound_message.portal_read_at` set on the rows
Maria opens (the bell's count); `bad_address = false` after the address fix with the
`DeliveryReturnEvent` rows **kept**; a `NoticeHistory` row for the 15 Sep final notice with
`outcome = skipped`, `skip_reason = no forwarding address`; the *Payment received* portal
switch off with **post still going**. **No notice was ever recorded as delivered by the
portal.**

**Fixture.** Screens `CWP-068` (*Everything we sent you, and what came back*) → `CWP-031`
(*Documents and letters*) → `CWP-024` (*Your details*) → `CWP-053` (*Messages*) → `CWP-025`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (history · document · flag · isolation) | Rule |
|---|---|---|---|---|
| 1 | Maria — `CWP-068`, 2 Sep. Subtitle *And the ones that did not arrive.* | `DataTable` What / Kind / Sent / How / What happened: *Your August bill · Bill · 30 Aug · Post · Email · **DELIVERED*** · *Payment received — $138.44 · Receipt · 12 Aug · Email · DELIVERED* · *Reminder — $412.60 overdue · Notice · 21 Aug · Post · Email · DELIVERED* · ***First notice** · Returned 8 Sep — not known at this address · Notice · 1 Sep · Post · **CAME BACK*** · ***First notice** · You have text messages switched off · Notice · 1 Sep · SMS · **NOT SENT*** · *Final notice · Notice · 15 Sep · Post · **DUE TO GO***. Filters *All · Bills · Receipts · Notices · Did not arrive*. Rail `Panel.Warning` ***Two letters came back from this address.** Check it is right — a notice that does not arrive still counts as sent.* · *Check my address*; **WHY SOMETHING WAS NOT SENT**: *A row saying **Not sent** is not a fault. It means you switched that channel off, or we do not hold an address for it. Bills, receipts, notices and plan letters are always posted whatever else you choose.* | Every row is a read of `NoticeHistory` (type, tier, channel, outcome, skip reason). **Post and email remain the delivery record**; this screen shows the record | BR-CWP-085 · BR-CWP-083 |
| 2 | **16 Sep** — the ladder's 15 Sep step ran with `bad_address = true` and no forwarding address | `CWP-068` now reads ***Final notice · 15 Sep · post · not sent, no forwarding address*** — **the most visible row on the screen**. A skipped notice produced **no document** | ⚠ `CWP-031` does **not** show it — it has no document. **The split between the two screens is the point.** Assert the row is on `CWP-068` and absent from `CWP-031` | BR-CWP-085 · `US-CWP-039` TC-1/2 |
| 3 | **negative · the message we could not send** | Shown with `unavailable` **and its reason** — never silently missing | A notice at an **unmapped tier** renders as an **absence**, never rounded to the nearest tier (`BR-CWP-092`, J43) | `US-CWP-039` TC-3 · BR-CWP-092 |
| 4 | `CWP-031` — *Documents and letters* | 41 rows, each *How* naming **every route it went by** — *Post · Email*, *Email*, *Post*. The August bill, the receipt, the July bill, *Your June bill was corrected*, the plan agreement. *Download a year* → the **issued** files | An internal letter is **absent**. A new account: an empty state naming what fills it. Documents are served, never re-rendered | BR-CWP-083 · BR-CWP-045 |
| 5 | `CWP-024` — the returned post | ***Two letters came back from this address*** sits **above the postal address field**. Maria corrects the postal address, *Save changes ✓* | **The flag clears** (`bad_address = false`) and paper **suppression lifts** (J17's shape); the two `DeliveryReturnEvent` rows are **kept** — flag history is append-only. ONE audit row naming Maria. Balances, due dates and late fees were **never** touched by the flag | BR-CWP-086 · BR-PAY-018 · hard rule 7 |
| 6 | `CWP-053` — *From Pine Hill*; the bell reads **`2`** | `DataTable` (unread rows **bold**) Message / About / When: *Your August bill is ready — $142.18 · BL-2608-0141 · 30 Aug* · *We need two documents for your move-out · SR-26-0056 · 3 Sep* · *Your payment of $138.44 was received · 12 Aug* · *Water main work on Elm St, 4–5 September · 28 Aug* · *Your June bill was corrected · 12 Jul*. Footer *Showing 1–5 of 22 · Page 1 of 5*. Opening the August bill message → `portal_read_at` set, the bell reads **`1`**. *Mark all read* → **`0`** and every row's timestamp set | **Every row corresponds to an event the product already declares** — around thirty in the catalogue. The planned-work row appears **only** for accounts in the affected area (`US-CWP-011`, J31). No messages → an empty state naming what fills it | BR-CWP-084 · `US-CWP-067` TC-1/8/9 |
| 7 | **negative · the portal waits** — `CWP-025`: turn *in the portal* **off** for *Payment received*; the never-signed-in paperless customer's twin fixture | The *Payment received* row **stops appearing** on `CWP-053` **and post still goes** — assert the outbound row still names post. For the customer who **never signs in**: post still went, and the notice's outcome **names post, not the portal** — **a customer who does not sign in was never told** by the portal, and the record must not say otherwise | The portal can **never be the only channel for anything with a deadline** | BR-CWP-084 · BR-CWP-083 · `US-CWP-067` TC-3/5 |
| 8 | **boundary · `OQ-1399`** | **Any code path that would record a portal row as *delivery* of a notice raises `NotImplementedError("OQ-1399")`** — the id in the code. `outbound_message.portal_delivered_at` means **queued and visible, never arrived** | The three options are the PO's — convenience copy only (what the blueprint draws) · counts as delivery for some named classes · counts as delivery (which makes portal retention a legal matter). **A lane may not choose**, and a lane that reaches release 3 without the ruling will guess — which is why the question is put **before** release 3 starts | BR-CWP-088 · `OQ-1399` |
| 9 | **negative · nothing empty** | An account with an **empty** notice history: `CWP-068` and its link are **absent**. `CWP-053` with nothing: an empty state | `CWP-031` and `CWP-068` are two different reads of two different tables and neither invents rows for the other | BR-CWP-093 · `US-CWP-039` TC-8 |
| 10 | **tenant isolation** | Notices, documents and messages with a Pine Hill session are Pine Hill's only; an Oak Ridge session cannot read `SR-26-0056`'s message or `BL-2608-0141`'s document | RLS `FORCE`; both halves in the query | BR-CWP-010 · hard rule 1 |
| 11 | **INVARIANCE** | Every notice sent **and** every notice deliberately not sent appeared with its route and outcome; the skipped notice was on `CWP-068` and never on `CWP-031`; the returned letters sat above the address and cleared on the fix without the return events being deleted; the bell counted only unread rows; post went on every print-floor class regardless of the portal switch; **no portal row was ever recorded as delivery** | The address fix wrote an audit row; the flag never touched money | BR-CWP-085 · BR-CWP-086 · BR-CWP-084 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Whether the portal **is** a delivery channel for any notice class | `OQ-1399` — **the one to answer first**. Until then every such path raises and the portal is a convenience copy |
| b | Planned-work messages from a **real** work record | `OQ-249` (J31 step 9) — seeded directly; the write path raises |
| c | The SMS notice actually sending | Twilio is `COMING_SOON · v1.1`; the *not sent — text messages switched off* row is a `NoticeHistory` outcome, asserted as such |
