# J39 — A self-read: submitted, validated, reviewed, billed, superseded (`158940` on a meter last read `153040` — about nineteen times usual, not eight — sent anyway, on no bill until a clerk clears it)

---
id: J39
tier: 2
rules: [BR-CWP-067, BR-CWP-068, BR-CWP-069, BR-CWP-070, BR-CWP-071, BR-CWP-072, BR-CWP-074, BR-CWP-010]
stories: [US-CWP-041, US-CWP-042]
# Wiring: every story above cites `J39` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J39.spec.ts`. Release 3 (the read),
# release 2 (the readings list).
# ⚠ BLOCKED ON OQ-1393 — does a customer-submitted reading go straight onto a
# bill, or wait for review? The blueprint assumes REVIEW and so does this journey;
# the straight-through path raises `NotImplementedError("OQ-1393")` (step 9). A
# lane may not choose. ⚠ Self-read is the ONE of the five portal switches that is
# OFF for a new tenant (CR-068 R8).
# ⚠ THE BLUEPRINT'S OWN FIGURE WAS WRONG AND IT CORRECTED ITSELF: 5,900 gallons
# in two days against 155 gal/day is about NINETEEN times usual, not eight (its
# §26 lists the repair). Use nineteen.
---

**Intent.** For a utility with one or two staff, a self-read that arrives on time is a walk
somebody did not have to make — and it is the portal's most valuable write. It must go
through **exactly the same validation** a staff read runs through — high, low, rollover,
window — because a customer read that skipped the thresholds would be a route into billing
that nobody checked. A failing reading is **not refused**: the customer is shown what the
figure implies against **their own history** and may send it anyway. It lands
**`awaiting_review`** and appears on **no bill** until a clerk clears it; a later real read
**supersedes** it and **the customer is not charged twice for the same water**.

**Upstream leaves (handoff in).** J36's session for **Maria Alvarez**, `1408 Elm St · A`.
Tenant `pine-hill` with `self_read_enabled = true` (switched **on** by Sarah Miller on
`CWP-069` — off by default). Meter *Water · front · serial `88-40219`*. Readings: 31 Aug
`153,040` (reader, `BL-2608-0141`) · 31 Jul `148,220` (reader, `BL-2607-0139`) · 30 Jun
`144,130` (**estimated `144,600`, corrected to `144,130` when read on 3 Jul**,
`BL-2606-0147`) · 31 May `140,370` (*you sent it in*, `BL-2605-0131`) — 26 rows. Daily
average **`155 gal`**. Read window for the route **open until 6 September**. Expected now
*about `153,300`*. The metering validation service with its high and low thresholds, rollover
handling (`999,900 → 000,400`) and window. Tenant `oak-ridge` with a meter on its own
premises. Clock **2 Sep 2026**.

**This journey leaves (handoff out).** ONE `meter_read` row (metering): `value = 158940`,
`source = portal`, `review_state = awaiting_review`, `submitted_by_credential_id` →
Maria's `portal_credential` (**never** `identity.user`), `evidence_document_id` → a photo in
the existing store, flagged **high** by the same validator a staff read uses. Then, after
the real read of **`153,190`**: the submitted row `review_state = superseded`, the real row
on the next bill, and **no bill charging both**. The September bill run (J24's shape)
**excludes** the awaiting-review row.

**Fixture.** Screens `CWP-035` (send your own reading) → `CWP-034` (every reading) → the
next bill run. Submitted figures: `153300` (plausible), `158940` (high — `5,900 gal` in two
days), `152900` (lower than last), `000400` after `999900` (rollover). Superseding real read
`153,190`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (validation · review state · bill run · isolation) | Rule |
|---|---|---|---|---|
| 1 | `CWP-034` — *Readings on your water meter* | Columns Taken ⇅ / Reading / Used since (**with unit**) / How it was taken / On which bill: `31 Aug 153,040 · 4,820 gal · Read by a meter reader · BL-2608-0141` · `31 Jul 148,220 · 4,090 gal · reader · BL-2607-0139` · **`30 Jun 144,130 · 3,760 gal · ESTIMATED then corrected · BL-2606-0147`** · `31 May 140,370 · 3,410 gal · You sent it in · BL-2605-0131`. `InfoBar`: *an estimated reading is our best guess… the next real reading corrects it, and you are never charged twice for the same water* | Opening the estimated row: *"estimated 144,600, corrected to 144,130 when the meter was read on 3 July — you were not charged twice"* — the reason **and its size**. **How a reading was taken is as prominent as the number** — plain words, never a code. A rollover (`999,900 → 000,400`) computes used-since **through** the rollover, never negative. Every used-since cell carries its unit | BR-CWP-071 · BR-CWP-072 · hard rule 3 |
| 2 | `CWP-035` — *Send us your reading. The window for your route is open until 6 September.* `Select` *Water · front · serial 88-40219*; `Date` 2 Sep 2026; `DialInput` **`153300`** | Rail **LAST READING** *Taken 31 Aug `153,040` · Expected now about `153,300`*; **WHAT HAPPENS TO IT** `ChecklistTimeline` × 3: *You send it · held, not billed yet* · *We check it · same rules as our own readers* · *It goes on your next bill · or we ring you if it looks odd*. *Send it ✓* → ONE `meter_read`, `source = portal`, **`review_state = awaiting_review`** | The meter is shown by **serial**, never by id (rule 31). The row appears on `CWP-034` as *You sent it in · awaiting review* with the *on which bill* column **empty — not a guess** | BR-CWP-068 · BR-CWP-071 · B14 rule 31 |
| 3 | **the flagged read** — `DialInput` **`158940`** | The field takes the **flagged** state — brand border and the brand helper: *That is 5,900 gallons in two days — about **nineteen** times your usual. Check the dials and try again, or send it anyway and we will look.* **It can still be sent** | The sentence comes from **the same validation service** a staff read calls — high threshold against **this account's own** `155 gal/day` — not a second, weaker check in the portal. `(158940 − 153040) = 5,900 gal`; `5,900 ÷ 2 ÷ 155 ≈ 19`. A **lower** reading (`152900`) fires the **low** threshold with a plain sentence and is **not** silently accepted as a rollover; a genuine rollover is handled by the **existing** rollover logic, not a new branch | BR-CWP-067 · BR-CWP-070 |
| 4 | *Send it ✓* on `158940`, with a photo | Accepted; `review_state = awaiting_review`; the photo goes through the **existing** document store — allow-list and size cap, no malware scan (SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload)) — and `evidence_document_id` is set. *A read with a picture is one a clerk can settle in seconds instead of scheduling a visit* | ⚠ **The finance-relevant assertion:** the September bill run's stage 2 **excludes** this row — it appears on **no bill** until a clerk clears it. Assert the draft set for `ACC-10432-A` prices on the last cleared read | BR-CWP-068 · `US-CWP-042` TC-3/11 |
| 5 | A clerk reviews (`Reads`, the existing review queue) | The read is listed **with the customer's photo** and the validator's flag. The clerk **does not clear it** — the figure is implausible — and the account is read on 4 Sep | Cross-module: the portal wrote through metering's service; the clerk works in metering. The portal never wrote a second set of rules | BR-CWP-067 · BR-CWP-012 |
| 6 | A later real read of **`153,190`** on the same period | The submitted `158940` is **superseded** — `review_state = superseded`, shown so on `CWP-034` — and the real read is the one the bill uses. **No bill charges both.** Assert exactly one consumption line for the period, from `153,040 → 153,190 = 150 gal` | The existing true-up is what stops double-charging; this journey makes it visible. The superseded row **stays** on `CWP-034` — nothing is deleted | BR-CWP-069 · hard rule 4 |
| 7 | **negative · the window and the switch** — submit on 7 Sep; then Sarah turns self-read **off** | 7 Sep: refused, **naming the window** (*until 6 September*). Switch off: `CWP-035` is **unreachable and its endpoint refuses** — a greyed button with a live route behind it is *built is not wired* inverted. Every other tab is unchanged; `CWP-069`'s readings count reads *"Readings are off, so nothing is counted"* — **not zero** | Self-read is **off for a new tenant** (`CR-068` `R8`) — the one switch of five that is | `US-CWP-042` TC-6/7 · `US-CWP-069` TC-4/7 |
| 8 | **negative · the actor** — the row's `submitted_by_credential_id` | Points at Maria's `portal_credential` — **never at `identity.user`**. An invited helper with *See* only cannot submit a reading | The named actor is the reason the column exists; a submission by a delegate (J44) is recorded under **their** name | BR-CWP-004 · hard rule 7 |
| 9 | **boundary · `OQ-1393`** | The straight-to-bill path raises **`NotImplementedError("OQ-1393")`** — the id in the code. Under review (the blueprint's assumption, and this journey's), `158940` reached no bill; straight through it would have billed `5,900 gal` | The three options are the PO's: always review · straight through when it passes validation · a per-tenant switch. **A lane may not choose** | BR-CWP-074 · `OQ-1393` |
| 10 | **tenant isolation** | A submission against a meter on **Oak Ridge's** premises with Maria's session → refused. Oak Ridge's readings never appear on `CWP-034` | Filtered on tenant and account set in the query; RLS `FORCE` on `meter_read` | BR-CWP-010 · hard rule 1 |
| 11 | **INVARIANCE** | One validation, two sources — the sentence on `CWP-035` was the validator's own. Nothing the portal wrote reached a bill without a clerk. The superseded read stayed visible and charged nothing. Every consumption figure on every screen carried its unit | The portal added a way **in**, not a second set of rules | BR-CWP-067 · BR-CWP-069 · hard rule 3 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | A submitted read reaching a bill **without** a clerk | `OQ-1393`. The path raises; the review path is the one built |
| b | The high-usage **alert** (`US-CWP-044`, `CWP-036`) firing from this read | No trigger exists in the product (wave 0, deliberately unscheduled). The read-validation threshold flags a reading for a clerk — a **different question** from *"this household's use has changed"* — and conflating them is the defect |
