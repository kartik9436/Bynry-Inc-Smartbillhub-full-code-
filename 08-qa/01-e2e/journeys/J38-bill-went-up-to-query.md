# J38 — The bill that went up → comparison → a query that holds the account (`+$8.83 · $0.00 · +$4.29 · −$9.38 = +$3.74`, exactly, and a bill that does not change)

---
id: J38
tier: 2
rules: [BR-CWP-044, BR-CWP-046, BR-CWP-042, BR-CWP-071, BR-CWP-010]
stories: [US-CWP-033, US-CWP-035, US-CWP-065]
# Wiring: every story above cites `J38` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J38.spec.ts`. Release 4 (the explainer);
# release 3 (the dispute).
# ⚠ THE DECOMPOSITION RULE IS PROPOSED, NOT SIGNED. `US-CWP-035` §7 is new
# arithmetic on a money path and B4/B5 are ❄ FROZEN: which components exist and
# how they are attributed when two move at once is a FINANCE judgment that goes
# through HUMAN-GUIDE §6 with the figure below. A lane must not ratify its own
# formula. This journey asserts the ADDITIVE property (the lines sum to the
# difference, with no tolerance) — that holds under any signed decomposition.
---

**Intent.** The single biggest deflector of phone calls in the blueprint, and it exists in
no form today: *"Why August cost `$3.74` more."* Every ingredient is already stored — the
prior period's usage, the days in each period, the rate version that applied, the discount
that ended — and the explainer is **arithmetic over stored data that must never disagree
with the bill it explains**: the component lines **sum exactly** to the stated difference.
When the customer still disagrees, the dispute is **a marker with a reason that never edits
the number it questions**: collection is held on the disputed amount, no late fee accrues on
it, **the bill itself does not change**, anything not disputed is still due on time — and if
the utility agrees the outcome is **a corrected bill, a new document**, with the original
still in the list.

⊕ **AS BUILT 2026-09-05 (`2.163.0`) — AND THREE OF THIS JOURNEY'S ASSERTIONS
CANNOT PASS YET. THEY ARE STAMPED RATHER THAN REWRITTEN, because the design is
right and the product is behind it.**

`CWP-055` ships: the two-step form, the check page, the query on a clerk's
worklist naming the bill, the period, the total, what is questioned, the reason
and the customer's own reading — and `BL-2608-0141` **byte-identical
afterwards**, asserted field by field (step 6's immutability half, `US-CWP-065`
TC-2, hard rule 4). Step 7's corrected-bill pair, step 9's tenant isolation and
step 10's invariance are unaffected.

**What is NOT built, with the question that decides each:**

| This journey says | What ships | Open |
|---|---|---|
| *Collection is held on `$142.18`; no late fee accrues on it* (steps 5, 6) | **Nothing is held.** `BR-MET-133` clause 4 is built and needs the DISPUTED AMOUNT; **no model, column or service in this product records one** — `late_fee.ageable_portion` raises rather than choosing between two fallbacks **`$137.20` apart** on the rule's own bill. The consequence box says what the code does instead, and a test asserts **no catalogue in any of the eleven languages** promises a hold | **`OQ-420`** (OPEN since 2026-08-26) · **`OQ-CWP-1682`** |
| *`CWP-034`: the 31 Aug reading carries a dispute marker* (step 6) | **No marker.** `metering.services.dispute_read` is `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` under `BR-MET-035`, **holds the account out of the next bill run** (`BR-MET-024`) and is cleared only by a System Admin. A customer reaching it would be a customer suspending their own billing. **A clerk raises it after reading the request** — the shape `BR-CWP-066` already gives a payment plan | **`OQ-CWP-1681`** |
| *`CWP-027`: `BL-2608-0141` gains* ***held while we look*** (step 6) | **No such state.** It is the first row's consequence: with nothing held there is nothing for the list to show | `OQ-CWP-1682` |

⚠ **STEP 1's RAIL SENTENCE IS ALSO NOT WHAT SHIPPED.** This journey has it read
*"Tell us before the due date and we will hold the account while we look."*
`CWP-028`'s new rail panel says *"Tell us and somebody will look at this bill"*
and offers two doors — *Query this bill →* and *Ask us about it →* — because a
promise to hold is the one thing on that panel the product cannot keep.

⚠ **AND ONE STEP THIS JOURNEY DOES NOT HAVE IS NOW REACHABLE:** the reference a
query returns opens `CWP-051`, *track your request* (`US-CWP-063`), where the
customer sees the six progress steps, whatever the office wrote **for them**, and
can add a note or withdraw. A future revision of this journey should walk it.

**Upstream leaves (handoff in).** J36's session for **Maria Alvarez**, `1408 Elm St · A`.
July `BL-2607-0139` `$138.44`, `4,090 gal`. August `BL-2608-0141` `$142.18`, `4,820 gal`,
lines as J36 step 5 (`18.50 · 17.80 · 34.12 · 35.67 · 22.00 · 5.42 · 8.67`). Last August
(2025) `4,090 gal`, rate unchanged. Readings 31 Jul `148,220`, 31 Aug `153,040`, both by a
reader. A summer discount that ended with July. A **second, undisputed** bill on the same
account. A **first-bill** account for the no-comparison case. Tenant `oak-ridge`. Clock **2
Sep 2026**.

**This journey leaves (handoff out).** ONE dispute (a **marker** on the 31 Aug reading, with
reason, with the customer's own reading `153,190` recorded **as evidence, not as a meter
read**), a collection hold on **`$142.18` only**, the late-fee clock held on that amount,
`BL-2608-0141` byte-identical, and — after the utility agrees — a **credit note plus a
rebill** (a new invoice, EP-BIL-04) with the original staying in `CWP-027` greyed and
naming its replacement. `CWP-034` shows the dispute marker; `CWP-027` shows *held while we
look*.

**Fixture.** Components: *You used more water* **`+$8.83`** · *Trash cart charge unchanged*
**`$0.00`** · *A summer discount ended* **`+$4.29`** · *Lower tax on a smaller sewer share*
**`−$9.38`** · `TotalRow` *Difference **`+$3.74`***. Dispute: bill `BL-2608-0141 · $142.18`,
questioning *the meter reading on 31 August*, reason *the house was empty for two weeks*,
own reading today `153,190`. Screens `CWP-028` → `CWP-030` → `CWP-055` → `CWP-034`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (arithmetic · hold · immutability · isolation) | Rule |
|---|---|---|---|---|
| 1 | Maria opens `BL-2608-0141` (`CWP-028`) | Lines grouped by service, every quantity with its unit, the additive check `128.09 + 14.09 = 142.18` from the displayed figures (J36 step 5). Rail **SOMETHING WRONG?** *Tell us before the due date and we will hold the account while we look.* · *Query this bill* | The readings panel names **how** each was taken — *Both taken by a reader. Neither was estimated.* | BR-CWP-044 · BR-CWP-071 |
| 2 | `CWP-030` — *Why August cost `$3.74` more* | **AGAINST LAST MONTH** `KVList` with **signed money** (positives brand red, zero and negatives ink): `+$8.83` · `$0.00` · `+$4.29` · `−$9.38` → `TotalRow` **Difference `+$3.74`**. **AGAINST LAST AUGUST**: two-bar chart with mono labels *Aug 2025 · Aug 2026*, *Water used `4,090 → 4,820 gal`*, *Rate per gallon unchanged*, a plain sentence (*a jump like this is usually a leak, a hosepipe or a visitor…*), buttons *Send a reading* · *Query this bill* | **The arithmetic check, and it is the point:** `8.83 + 0.00 + 4.29 − 9.38 = 3.74` **exactly**, and `142.18 − 138.44 = 3.74` **exactly**. Each component is computed against the **rate version effective in its own period**, never today's tariff. Stored to 4 dp, rounded **at display only** (B4) — and the displayed lines must still sum | BR-CWP-046 · hard rule 2 |
| 3 | **negative · no tolerance** — perturb any component by one cent in the fixture | The sum no longer matches the difference and **the test fails**. A tolerance here would defeat the whole story | The explainer is a **view, not a source**: it reads the two bills and their periods; it writes nothing and caches nothing | BR-CWP-046 · `US-CWP-035` TC-3 |
| 4 | **negative · the cases with no comparison** — the **first** bill on an account; a bill that went **down**; a period of a different length; a month a rate version changed | First bill: **no comparison offered at all** — not one against zero. Down: *"cost less"* with the signs reversed, still summing. Different length: the days-in-period component appears as **its own line**, not absorbed. Rate change: the rate component is its own line **from the version that applied** | Assert each shape sums exactly | `US-CWP-035` TC-4/5/6/9 |
| 5 | *Query this bill* → `CWP-055`, step 2 of 2 | `KVList` Bill `BL-2608-0141 · $142.18` / What you are questioning *The meter reading on 31 August* / Your reason *The house was empty for two weeks* / Your own reading today `153,190`. `ConsequenceBox`: *We hold collection on $142.18 · No late fee while we look · We answer within five working days.* Rail **WHILE A BILL IS QUERIED**: *The bill itself does not change. If we agree, we issue a corrected one. Anything you do not dispute is still due on time.* | The own reading is recorded **on the dispute as evidence — not as a `meter_read` row**. A dispute with no reason is refused. Disputing an already-disputed bill is refused **as already open, with its reference** | `US-CWP-065` TC-8/9 |
| 6 | *Send the query ✓* | ONE dispute marker with its reason. `CWP-027`: `BL-2608-0141` gains *held while we look*. `CWP-034`: the 31 Aug reading carries a **dispute marker**. Collection is **held on `$142.18`**; **no late fee accrues on it** — assert the fee clock is held on that amount | **The bill itself is unchanged**: `invoice.total` still `142.1800`; **no row of `invoices` or `invoice_lines` was updated**. The **second, undisputed** bill on the account is **still due on time and still accruing** — the hold is **per amount, not per account**. Only a **System Admin** clears a dispute; a portal attempt is refused. The existing dispute ageing applies | BR-CWP-042 · hard rule 4 · `US-CWP-065` TC-2/3/4/6 |
| 7 | The utility agrees (a clerk, EP-BIL-04) | A **corrected bill** is issued — **a new document**: a credit note and a rebill. `CWP-027` shows the original **greyed, CORRECTED, *Replaced by BL-26nn-nnnn*** and the replacement as its own row; the correction letter appears on `CWP-031` | Nothing on the original was edited or deleted. The balance read (J36) counts the **replacement** once. A run summary holding a corrected bill follows BR-BIL-064 (J24 step 9) | BR-CWP-042 · hard rule 4 |
| 8 | **negative · a customer-safe view of the reading** — `CWP-034` after the marker | The row reads its method in words, the marker, and *awaiting our answer*; the internal dispute ageing bucket and any clerk comment not flagged customer-visible are **absent** | Consumption cells carry their unit (`4,820 gal`) | BR-CWP-071 · BR-CWP-078 |
| 9 | **tenant isolation** | The explainer and the dispute for `BL-2608-0141` with an Oak Ridge session → **refused**. The hold is scoped to Pine Hill's account | Every query on both halves, in the query; RLS `FORCE` | BR-CWP-010 · hard rule 1 |
| 10 | **INVARIANCE** | `142.18 − 138.44 = 3.74` and the lines summed to it on every render; the bill never moved; the dispute never edited a number; the hold touched **one amount** and nothing else; the corrected outcome was a **pair** in the list, never a silently changed figure | The explainer never disagreed with the bill it explains — a penny of disagreement is the defect | BR-CWP-046 · BR-CWP-042 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The **decomposition rule** — which four components, and the attribution order when two move at once | A finance judgment under ❄ B4/B5: HUMAN-GUIDE §6 re-sign with the figure `+$8.83 · $0.00 · +$4.29 · −$9.38 = +$3.74`. Until then the formula is PROPOSED and only the additive property is asserted |
| b | The rebill's `corrects_invoice_id` chain | `OQ-120` (billing) — the chain has no column; J24 step 9 records the consequence for run summaries |
