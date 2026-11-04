# One-time bill — after the fix (2026-10-12)

Re-walk of `DEF-BIL-10067`, `-10068` and `-10069` on **brazosbend**, at branch tip `c6372b70b` (fix commits `cf522835d`, `2bfd5b3c4`, `c6372b70b`), against the same data as `../otb-before-2026-10-12/README.md`. Every shot is 1440 wide, taken from the running product. No product code was changed.

⚠ **The footer still reads `v2.569.0`, the same version the BEFORE walk was taken on.** None of the three fix commits moved `07-frontend/package.json`, so a reader cannot tell the two builds apart from the screen.

## Before → after

| Issue | Before (what the screen showed) | After (what the screen shows) | Result | Shot |
|---|---|---|---|---|
| OTB-10/17 duplicate warned late, and called "Already billed" | Step 1 silent; step 3: "Already billed for this period. BL-2609-000101" | Step 1, AC-2026-00012, 1–30 Sep: **"Draft already exists for this period. BL-2609-000101 · 10/12/2026 · by Dana Whitfield"** with **Open draft** and **Discard draft**. No "Already billed" anywhere | PASS | `otb-10-17a-step1-draft-banner-and-closed-month.png` |
| Closed-month note on step 1 (scenario 1) | Nothing | **"September is closed. Posts to October."** (the period is September only, so August is not named) | PASS | same |
| Open draft | — | Opens the draft, after a "Leave without saving?" prompt (Stay / Leave without saving) | PASS (see notes) | `otb-10-17d-open-draft-leave-prompt.png` |
| OTB-8 label | **BILL · CYCLE BILL** | **BILL · ONE-TIME BILL** | PASS | `otb-08-one-time-bill-label.png` |
| OTB-9 Total due | **—** | **$175.44** (Current charges $175.44) | PASS | `otb-09-total-due.png` |
| OTB-6 Approve / Cancel on a draft | No Approve; Cancel disabled | **Approve** and **Cancel draft** buttons, both enabled. Cancel draft → "Cancel this draft? The draft is deleted. Its number is not reused." (Keep draft / Cancel draft) → back to Billing, BL-2609-000101 gone | PASS | `otb-06-draft-approve-and-cancel.png`, `otb-06b-cancel-draft-dialog.png`, `otb-06c-draft-canceled.png` |
| Discard draft from step 1 | — | Discards the draft; banner goes; the step-1 note stays | PASS | `otb-10-17c-step1-after-discard.png` |
| OTB-1 usage follows the typed reading | Typed 4.6, Usage stayed **5.1 kgal** | Typed 4.6, Usage shows **1.7 kgal** at once | PASS | `otb-01-usage-recalculated.png` |
| OTB-3 Rates follow the typed reading | Water $44.40, Before tax $172.00, unchanged | Water **$28.65**, Before tax **$139.75**, **unchanged after typing 4.6** (at 1.7 kgal water would be $8.00 + 1.7 × $4.00 = **$14.80**). The preview request does carry `value: 4.6`; the answer still bills 5.1 kgal | **FAIL** | `otb-02-03-rates-after-typing-4.6.png`, `otb-01-04-step2-full-after-typing-4.6.png` |
| OTB-4/13a Rates show each electric part | One line, "from 09/20/2026" only | Electric **$111.10** with three part rows: **09/01–09/14 · 373.33 kWh · $0.11/$0.135/$0.16 · $44.57**; **09/15–09/19 · 133.33 kWh · $0.115/$0.14/$0.165 · $16.58**; **09/20–09/30 · 293.33 kWh · $0.12/$0.145/$0.17 · $37.95** | PASS | `otb-04-13a-rates-one-line-per-part.png` |
| Water not cut at electric's dates | Water cut 3 ways | Water **one row**, "Water · from 08/01/2026", $28.65 | PASS | same |
| OTB-11/12 one base row per service (step 3) | Electric base ×3, water base ×3 | **Electric Base 1 × $12.00**, **Water Base 1 × $8.00** — one each | PASS | `otb-11-12-one-base-per-service.png`, `otb-11-12-step3-full.png` |
| OTB-13b step 3 electric usage split into parts | One line, 800 kWh, $91.60 | **Still one line: Electric Usage 800 kWh, Tiered, $99.10.** The amount is now the three parts added ($44.57 + $16.58 + $37.95), but the parts are not printed | **FAIL** (if per-part lines are expected on the bill) | `otb-04-13b-step3-usage-one-line.png` |
| No 799.999999 | Draft Usage panel: **799.999999 kWh** | Step 3: **800 kWh**; new draft BL-2609-000107 Usage panel: **800 kWh** | PASS | `otb-x1-new-draft-detail-usage.png` |
| Water billed on 1.7 kgal (step 3) | 5.1 kgal, $20.40 | **5.1 kgal, $20.65** — not 1.7 | **FAIL** | `otb-11-12-step3-full.png` |
| Step-3 figures | Subtotal $172.00, tax $3.44, total $175.44 | **Subtotal $139.75, tax $2.80 (2.00%), total $142.55** | — | same |
| OTB-18 closed month, step 1 | Nothing | AC-2026-00054, 16–31 Aug: **"August is closed. Posts to October."** (also "Draft already exists for this period. BL-2608-000104", which was discarded) | PASS | `otb-18a-step1-closed-month-note.png` |
| OTB-18 closed month, Send | "Failed. The bill was not sent … CLOSED fiscal period 2026-08-01 … 2026-08-31" | **"Bill BL-2608-000108 sent"**, $146.88, due 11/01/2026, Email · queued, Meter reads Locked. Journal entry **JE-100126-0205 dated 2026-10-01**, memo "Bill BL-2608-000108 issued", $146.88 both sides; the bill keeps service period 08/16–08/31 | PASS | `otb-18b-step4-ready-to-send.png`, `otb-18-closed-month-posts-forward.png`, `otb-18c-sent-bill-detail.png`, `otb-18e-journal-entry-oct-01.png` |

## Why the typed reading still does not reach the money

Asked directly, `POST /billing/one-time/preview` returns the same bill with and without `readings: [{W-9011, 2026-09-29, 4.6, current}]` in the body — water 5.100000 kgal, $20.65, total $142.55 both times, and its own `readings.rows` still report current 8.0 on 09/29. W-9011 already has a reading on file inside the window (8.0 on 29 Sep), and the typed value does not override it. The fix's own note says the reading now reaches the **split** parts; water is not split any more, so it goes through the whole-period path, where the on-file read wins. On Continue the typed 4.6 is now posted to Meter Reads (a read batch is staged, validated and posted — the BEFORE walk saw no batch), yet the preview after that still reads 8.0 for 29 Sep.

## Also seen

* **Rates table parts do not foot on screen:** 373.33 + 133.33 + 293.33 = **799.99 kWh** against an 800 kWh read (each part is rounded to 2 places for display; step 3 and the saved bill do show 800).
* The Rates row's tag reads **"Split 09/15/2026"** only, though electric is cut twice (15 and 20 Sep).
* On the draft detail the ⋯ menu still holds a disabled **"Cancel this bill"** with the tooltip *"A draft is not canceled — it is simply not issued."*, beside the new enabled **Cancel draft** button.
* AC-2026-00054's step 3 still prints **Base $0.00** for electric and water (noted in the BEFORE walk too); the journal entry posts $0.00 to 4105 and 4115.
* The sent bill's Audit tab shows raw timestamps (`2026-10-12T16:17:23.449000+00:00`) and the stored bill type **`cycle`** on "Bill drafted", though the head reads One-time bill.
* The journal entry shows its date as **2026-10-01** (ISO), where the rest of the product shows 10/01/2026.
* The step-1 "Open draft" link asks "Leave without saving?" even though only the account and dates have been entered.
* **Console:** the only error on every page was the browser's *"The Content Security Policy directive 'frame-ancestors' is ignored when delivered via a <meta> element."* No page errors and no failed API calls beyond the one refused read batch below.
* **Database ids on screen:** none. Every page walked was scanned for a uuid in its visible text; zero found (B14 rule 31 holds).

## Data this walk changed

| What | Detail |
|---|---|
| Canceled / discarded drafts | **BL-2609-000101** (Cancel draft on its page), **BL-2609-000105** and one more AC-2026-00012 September draft (made by this walk's earlier passes, discarded from step 1; the second's number was not captured), **BL-2608-000104** (discarded from step 1) |
| New draft left in place | **BL-2609-000107**, AC-2026-00012, 1–30 Sep, **$142.55** (water on 5.1 kgal) |
| Sent | **BL-2608-000108**, AC-2026-00054, 16–31 Aug, **$146.88**, booked **2026-10-01** (JE-100126-0205) |
| Reads | W-9011 **4.6 on 2026-09-29** posted by the step-2 Continue (RB-2610-0057). A second identical post was refused as a duplicate (RB-2610-0058, left validated, not posted) |
