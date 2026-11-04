# J36 — The eleven-month cold return (`$142.18 · Due 14 Sep · in 12 days`, a corrected bill that stays in the list, owing as its own column, and the PDF that was issued)

---
id: J36
tier: 2
rules: [BR-CWP-041, BR-CWP-042, BR-CWP-043, BR-CWP-044, BR-CWP-045, BR-CWP-047, BR-CWP-049, BR-CWP-050, BR-CWP-051, BR-CWP-052, BR-CWP-053, BR-CWP-061, BR-CWP-071, BR-CWP-073, BR-CWP-083, BR-CWP-093, BR-CWP-095, BR-CWP-008, BR-CWP-010, BR-CWP-013]
stories: [US-CWP-016, US-CWP-021, US-CWP-023, US-CWP-024, US-CWP-025, US-CWP-031, US-CWP-032, US-CWP-033, US-CWP-034, US-CWP-036, US-CWP-038, US-CWP-040, US-CWP-043, US-CWP-048]
# Wiring: every story above cites `J36` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J36.spec.ts`. Release 2 — "see
# everything, pay nothing": every Pay control on these screens is HELD (CR-068 R3).
# ⚠ `US-CWP-038` (a statement) is BLOCKED on OQ-1395 and step 11 asserts the
# boundary. ⚠ `US-CWP-024`'s balance read is NEW arithmetic on a money path and
# carries NO golden test yet — it must not be described as golden-tested until a
# test in 06-backend/tests/golden/ runs it (14 of 61 GTs are engine-verified).
---

**Intent.** Somebody who pays four to twelve times a year and has forgotten everything
signs in after eleven months and needs the answer to *do I owe anything and by when* above
everything else. Every figure they see is a **read of what the staff app wrote** — the
portal has no bills of its own and **sees nothing above the issued bill**. A corrected bill
and its replacement **both stay in the list forever**; **owing is a separate column from
amount**; the PDF served is **the file that was issued**, never a re-render; a bounced
cheque is **two rows**; a write-off shows its amount and **never its reason**; and the
balance is **re-read on every load, never cached** — a credit real on Tuesday can be spent
by Thursday.

**Upstream leaves (handoff in).** J35's credential and one-entry set for **Maria Alvarez**,
`ACC-10432-A` at `1408 Elm St · A`; her *keep me signed in* session from **1 Oct 2025**.
Bills: `BL-2608-0141` 1–31 Aug, issued 30 Aug, due **14 Sep 2026**, `4,820 gal`, `$142.18`,
owing `$142.18`, DUE · `BL-2607-0139` 1–31 Jul, `4,090 gal`, `$138.44`, owing `$0.00`,
PAID · `BL-2606-0147` 1–30 Jun, issued 12 Jul, `3,760 gal`, `$129.02`, PAID ·
`BL-2606-0137` 1–30 Jun, issued 30 Jun, `$154.90`, **CORRECTED → replaced by
`BL-2606-0147`** · `BL-2605-0131` May, `3,410 gal`, `$121.55`, PAID. A **draft** bill of
`$99.99` inside a live bill run. Payments: 12 Aug bank transfer `Chase ••••4021` →
`BL-2607-0139` `$138.44` CLEARED · 14 Jul cheque `#10188` → `BL-2606-0147` `$129.02`
CLEARED · **2 Jul cheque `#10174` → `BL-2606-0147` `$129.02` REVERSED and the reversal
`−$129.02` BOUNCED *returned by the bank*** · 13 Jun card `Visa ••••8812` → `BL-2605-0131`
`$121.55` CLEARED — 31 rows. Adjustment `−$25.88` goodwill (reading dispute) 12 Jul.
Write-off `$84.20` on 12 May, reason `customer_bankruptcy`. Two credits of `$25.88` used on
`BL-2607-0139`. Deposit `$150.00` taken 4 Mar 2021, interest to date `$3.20`. Tax exempt
until 31 Mar 2027. Internal `credit_tier = B2`. 41 documents. Readings: 31 Aug `153,040`
(reader) · 31 Jul `148,220` (reader) · 30 Jun `144,130` (**estimated `144,600`, corrected 3
Jul**) · 31 May `140,370` (*you sent it in*). Equipment: water meter `88-40219`, refuse cart
`C-11840`, backflow device `BF-2210` (TEST DUE NOV); a sub-meter on unit B. Templates
`bill-v3` pinned at issue; `bill-v4` published 1 Sep 2026. Tenant `oak-ridge` with a bill
**also numbered `BL-2608-0141`**. Clock **2 Sep 2026**.

**This journey leaves (handoff out).** Nothing written except session rows, read
timestamps and audit rows for sign-in. Every figure asserted here is the baseline J38, J39,
J40 and J47 read from.

**Fixture.** Screens `CWP-015` → `CWP-022` → `CWP-027` → `CWP-028` → `CWP-029` and then
`CWP-033`, `CWP-037`, `CWP-041`, `CWP-065`, `CWP-031`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (read · cache · DOM · isolation) | Rule |
|---|---|---|---|---|
| 1 | Maria returns after eleven months; `CWP-015` | The October session has **expired**; the screen is fully usable cold — no stale state, no half-rendered shell. `m.alvarez@example.com` + password → `CWP-022`, avatar `MA`. Header *Pine Hill Water & Power* in `#EC3013`; the switcher renders as a **label, not a control** — one account, so an empty dropdown would be worse than none | Six tabs *Home · Bills · Usage · Payments · Requests · My details*. `07-frontend/src/portal/` is on `route-b-migrated.txt` — prove `g31` goes RED on a file that is not (rule 21) | BR-CWP-008 · `US-CWP-023` TC-4/7 |
| 2 | `CWP-022` — the four tiles | **`KpiTile.lead` BALANCE `$142.18` · *Due 14 Sep · in 12 days*** · LAST BILL `$142.18` *Issued 30 Aug · Aug cycle* · LAST PAYMENT `$138.44` *12 Aug · Bank transfer* · WATER THIS MONTH **`4,820 gal`** *18% above last August*. **NEEDS YOUR ATTENTION**: `DUE SOON` *Bill BL-2608-0141 is due on 14 September.* · *Pay $142.18* (**held**) · `READING` *Your water reading is due between 2 and 6 September.* · *Send a reading* — offered **only while the window is open** | The balance is `US-CWP-024`'s read: Σ issued non-void invoice totals − Σ allocations − Σ unspent credits, taking the **replacement** of a corrected pair once, **never a draft**. `142.1800` → `$142.18`, rounded at display only. **Never cached** — two loads with a credit spent between them show two figures. The `$99.99` draft is **invisible**. The usage tile carries its unit — `4,820 gal`, never `4,820` | BR-CWP-047 · BR-CWP-041 · hard rules 2 · 3 |
| 3 | **negative · nothing empty** — the same screen for an account owing nothing with no window open | The attention panel is **absent**, not an empty box saying *no items*. The tip slot is **absent from the DOM** — the only home-page tip is OFF and Dec–Feb (J46). A trash-only account shows **no usage tile and no empty chart**; the screen says the service is not measured | Assert on the DOM: no panel element, no `TipBar` element | BR-CWP-093 · BR-CWP-095 · BR-CWP-073 |
| 4 | `CWP-027` — *Your bills* | Columns Bill ⇅ / Period ⇅ / Issued / Due / Usage / **Amount** / **Owing** / Status. Five rows. `BL-2608-0141` … `$142.18` `$142.18` **DUE IN 12 DAYS**. `BL-2606-0137` **greyed**, `$154.90`, owing `$0.00`, **CORRECTED**, caption *Replaced by BL-2606-0147* — and `BL-2606-0147` is **its own row**. Usage `4,820 gal` with its unit | **Owing is a separate column from amount**: a part-paid case — `$142.18` with `$40.00` against it — reads amount `$142.18`, owing **`$102.18`** and a status that is **neither PAID nor DUE**. Filter *Unpaid* keeps rows with owing > 0 — the part-paid row **is** included. The `$99.99` draft is **absent from the table entirely**. A voided bill reads *cancelled*, owing `$0.00`, still downloadable | BR-CWP-043 · BR-CWP-042 · BR-CWP-041 |
| 5 | `CWP-028` — `BL-2608-0141`, line by line | **WHAT YOU WERE CHARGED**, grouped **WATER · SEWER · TRASH · TAXES AND FEES**: *Monthly service charge* — — `$18.50` · *Usage · first 2,000 gal* `2,000 gal` `$8.90 / 1,000 gal` `$17.80` · *Usage · 2,001–5,000 gal* `2,820 gal` `$12.10 / 1,000 gal` `$34.12` · *Sewer · share of water used* `4,820 gal` `$7.40 / 1,000 gal` `$35.67` · *Cart collection · 96 gal cart* `1 cart` `$22.00 / cart` `$22.00` · *State utility tax* — `4.25%` `$5.42` · *Regulatory fee* — — `$8.67` · *Charges before tax* **`$128.09`** · *Tax* **`$14.09`** · `TotalRow` *Total for August* **`$142.18`**. Rail **YOUR ACCOUNT** Brought forward `$0.00` / This bill `$142.18` / Paid since `$0.00` / **Owing `$142.18`**; **READINGS THIS BILL** *Water · front 31 Jul 148,220 · 31 Aug 153,040 — Both taken by a reader. Neither was estimated.* | **The additive check is the point**: `18.50 + 17.80 + 34.12 + 35.67 + 22.00 = 128.09`; `128.09 + 5.42 + 8.67 = 142.18` — **exactly, from the displayed figures**; a penny of disagreement is a support call. **Every quantity cell carries its unit** — assert on every row. Rates display per their unit from `NUMERIC(18,6)`; amounts from `NUMERIC(18,4)`, both shown at 2. A bill with eleven services groups all eleven — fire **counts**: one 6" line and two 2" lines read `$60.00 + 2 × $12.00` on two lines | BR-CWP-044 · hard rules 2 · 3 · B4 |
| 6 | `CWP-029` — *The bill we sent you*; *↓ Download* | The file is **byte-identical** to the one the bill run produced, rendered from **`bill-v3`, pinned at issue**. `bill-v4` (published 1 Sep) and a **changed tenant logo** leave it **unchanged**. A bill issued in Spanish serves its pinned `bill-v3-es` variant | **The portal never re-renders.** A bill whose file is missing from storage gives a plain sentence and a route to ask — **not a re-render and not a 500**. A delegate with *Download* may; one with *See* only may not (J44) | BR-CWP-045 |
| 7 | `CWP-033` — *What you have used*; `CWP-037` — *Meters and equipment* | Tiles WATER · THIS PERIOD `4,820 gal` *18% above last August* · DAILY AVERAGE `155 gal` · NEXT READING DUE *2–6 Sep*. `ChartPanel` **WATER · GALLONS PER MONTH**, twelve bars, **the axis in gallons**, lowest `3,050 gal`, highest `4,820 gal`, note *Sewer is billed on this figure*. Panels: SEWER *Billed on: Water used · Not separately metered —* · TRASH *Billed on: Your 96 gal cart · Not measured —*. `TipBar` *Watering before 10am…* (Jun–Sep, J46). Equipment: `88-40219` front boundary box, fitted Mar 2021, last read 31 Aug, IN SERVICE · `C-11840` rear alley, **no last read (empty, not zero)**, IN SERVICE · `BF-2210` **TEST DUE NOV** | **No chart and no zero series for an unmeasured service.** One month of history → no year-on-year comparison offered. CSV carries the unit **as a column on every row**. The sub-meter on unit B is **absent**. Every identifier is a **serial**, never a row id | BR-CWP-073 · hard rule 3 · B14 rule 31 |
| 8 | `CWP-041` — *What you have paid* | Newest first. **The bounce is two rows**: `2 Jul · Cheque #10174 · Returned by the bank · −$129.02 · BOUNCED` (danger row, every cell brand red, 🖨 absent) sitting **directly above** `2 Jul · Cheque #10174 · BL-2606-0147 · $129.02 · REVERSED`. The goodwill adjustment `−$25.88` with its date and a plain reason. The write-off `$84.20` *written off · 12 May* | **No portal route updates or deletes a payment — assert the endpoint set.** The write-off's response body contains **no reason code** — `customer_bankruptcy` never surfaces. A write-off reversal is its own row, not a deletion. A cheque's reference is its **cheque number**, never a row id. A payment whose confirmation was corrected (`POST /payments/{id}/correct-reference`) shows the corrected value, and the old value lives **only in `audit_log`, which is pruned** — this screen is **not** a permanent record of it (`OQ-1340` OPEN). Net of the pair `$0.00`; `BL-2606-0147` re-opened at **its own** due date with the late-fee clock unreset — existing behaviour this screen must not contradict | BR-CWP-061 · BR-CWP-050 · BR-CWP-051 · hard rule 4 |
| 9 | `CWP-065` — *Your account* | **THE DEPOSIT WE HOLD** *Held `$150.00` · Taken 4 March 2021 · Interest so far `$3.20`* and that it returns at closing **with** interest — and that it is **not money off a bill in the meantime**. **YOUR SERVICES** Water 4 Mar 2021 (meter) · Sewer 4 Mar 2021 (share of water) · Trash 1 Jun 2024 (`96 gal` cart). **HOW YOU ARE BILLED** *Residential Standard since 1 Jan 2026 · before that Residential Basic*. **TAX** EXEMPT *from state utility tax · runs out 31 March 2027* and a reminder a month before | The response body contains **no `credit_tier`, no `match_tier`, no `match_basis`** — held back on purpose, asserted on the body. `$150.00 + $3.20 = $153.20` is exactly what J40's final bill settles. An account with **no** deposit: the panel is **absent**, not `$0.00`. Thirty days before 31 Mar 2027 a **message**, not a bigger bill | BR-CWP-049 · BR-CWP-053 · BR-CWP-052 |
| 10 | `CWP-031` — *Documents and letters* | 41 rows, page 1 of 9, newest first: *Bill for August · Bill · 30 Aug · Post · Email* · *Receipt for $138.44 · Receipt · 12 Aug · Email* · *Bill for July · 30 Jul · Post · Email* · *Your June bill was corrected · Letter · 12 Jul · Post* · *Payment plan agreement · 3 Mar · Post · Email*. Every row's *How* names **every route it went by** | A **skipped** notice (J47) is **not here** — it produced no document; that split is deliberate. An internal letter is absent. *Download a year* → one archive, each file the **issued** one. A new account: an empty state naming what fills it | BR-CWP-083 · BR-CWP-045 |
| 11 | **boundary · `OQ-1395`** — the statement (`US-CWP-038`) | Picking 1 Jan – 30 Jun 2026 returns every bill, payment, credit and adjustment in date order — the corrected pair as **two rows**, the bounced `#10174` pair as two rows, the two `$25.88` credits. **Requesting the document raises `NotImplementedError("OQ-1395")`** — the id in the code | Once ruled, the carried-forward on 30 Jun must **equal the balance read on that date** — the tie-out is the reason to answer rather than build twice. A window with no activity → an honest empty result | BR-CWP-047 · `OQ-1395` |
| 12 | **tenant isolation** | The balance read sums Pine Hill accounts only; Oak Ridge's identically numbered `BL-2608-0141` never appears in the list, the detail or the PDF route (`GET bills/BL-2608-0141/document` with an Oak Ridge session → refused). Every query is filtered on **tenant and account set, in the query** | An account outside the set requested by id → refused without revealing existence. `app.tenant_id` from the path | BR-CWP-010 · hard rule 1 |
| 13 | **INVARIANCE** | Every Pay control on every screen rendered **in place, disabled, carrying its reason** — never hidden, never live-but-inert; forcing one wrote nothing. The corrected original was never deleted; the issued bill and every payment row are immutable; no figure on any screen disagreed with any other (balance tile = bills owing = account panel; deposit here = final bill there) | The portal added **no second copy** of a bill, a payment or a balance — every screen is a view through the owning module's seam | BR-CWP-056 · BR-CWP-012 · hard rule 4 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The statement **document** | `OQ-1395` — whether the transaction list **is** the statement or one is built |
| b | The balance read as **golden-tested** arithmetic | No GT exists for it; B4/B5 are frozen. The worked figures (`$142.18`, `$102.18`, `$872.82`) go to finance through HUMAN-GUIDE §6 before any of them is called signed |
| c | Whether an audit row holding a corrected payment reference survives retention pruning | `OQ-1340` OPEN — so no screen or docstring may call `CWP-041` a permanent record of the old value |
