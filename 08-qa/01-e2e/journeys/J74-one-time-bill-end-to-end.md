# J74 — The one-time bill, end to end for a clerk: eight cases billed, sent and checked in the database

---
id: J74
tier: 2
rules: [BR-BIL-010, BR-BIL-011, BR-BIL-012, BR-BIL-013, BR-BIL-014, BR-BIL-015, BR-BIL-016, BR-BIL-018, BR-BIL-020, BR-BIL-030, BR-BIL-036, BR-BIL-058, BR-BIL-1047, BR-RAT-1015]
stories: [US-BIL-010, US-BIL-011, US-BIL-012, US-BIL-013, US-BIL-014, US-BIL-032, US-BIL-033]
depends_on_journeys: [J70]
# WALKED 2026-09-30 at 1440 on PostgreSQL 16, build 2.413.0 — spec
# `07-frontend/e2e/J74-one-time-bill-end-to-end.spec.ts`, database check
# `10-scripts/verify_j74_one_time_bill.py`, seed `10-scripts/seed_j70_one_time_bill.py`
# (Units I and J added for this journey). Results in § RESULTS below.
---

**The request, verbatim (PO 2026-09-30):** *"for every one time bill interim, first bill, final bill -
all 6 or 7 cases, generate end to end bill and send it - it should work for clerk end to end - take 7
or 8 cases and run it end to end - bill should be generated check in database"*.

**Intent.** J70 proved the one-time page's screens. J74 proves what a clerk's Send LEAVES BEHIND.
Each case is billed in a real browser the way a clerk does it — step 1 Account → step 2 Services
(readings typed there) → Review → Send with all five confirmations ticked — and then the database
is read: the invoice, its lines to the cent, its tax, its journal, the release row, the audit row,
the frozen snapshot, the delivery queue, the saved readings, and a second Send and a second draft
that must not make a second bill. **Every expected total below was priced by hand from the seed's
rates and readings BEFORE the run** — never read off the screen — so a bill that agrees with itself
and is still wrong shows up.

## Stack (re-runnable)

1. A PostgreSQL 16 database of its own (`sbh_j74` on `127.0.0.1:55433`):
   `manage.py migrate` → `manage.py seed_demo` → `python 10-scripts/seed_j70_one_time_bill.py`
   (`DJANGO_SETTINGS_MODULE=config.settings.local`). The seeded state is kept as a template
   (`sbh_j74_seeded`) and the run starts from a fresh copy of it — the bills are real, and a second
   pass over the same database meets its own bills as *Already billed*.
2. Django `runserver` on 8474 and the built SPA (`npx vite build --mode compose`) behind
   `07-frontend/server.mjs` on 8574, as `08-qa/01-e2e/stack/boot_stack.sh` runs them.
3. `E2E_BASE_URL=http://127.0.0.1:8574 E2E_VIEWPORT=1440 npx playwright test e2e/J74-one-time-bill-end-to-end.spec.ts --workers=1`
   (Chromium `/opt/pw-browsers/chromium-1194`), under `nice -n 10`.
4. `DATABASE_URL=postgres://…/sbh_j74 python 10-scripts/verify_j74_one_time_bill.py` — exits 1 on
   any failed check and prints every failure. It reads the spec's
   `08-qa/screens/one-time-bill-e2e-j74/j74-results.json` (what Review showed, the Send answer and
   both replays).

Tenant Brazos Bend (`brazosbend`), clerk **Dana Whitfield**, 1408 Elm St, clock Wed 30 Sep 2026.
Every Elm St account is `institutional` and on a cycle (`J70-MONTHLY`, 21 days to pay), so only the
**Local 2.00%** tax applies, to usage and base lines (B4.2); deposits, CONN and TAMPER are not taxed,
RECON is. Rates: water tiered $3.00/$4.25 to Jul 15 and **$3.25 to 5 kgal, $4.50 above** from Jul 16,
base $8.00 per meter; electric $0.1245/kWh, no base; trash $15.00 per cart + $3.00 base; sewer 40% of
water × $5.00/kgal + $6.00 base.

## The eight cases, with the total stated before the run

| # | Case | Account | What the clerk does | Expected total (hand-priced) |
|---|---|---|---|---|
| 1 | Interim — two water meters, electric, sewer 40% of water, one cart | Unit A, Maria Alvarez | Sep 1–30; types W-10442 488.4, W-10443 136.7, E-55120 19,020 on step 2 | water 2 × (5 × 3.25 + 1.1 × 4.50 + 8.00) = 58.40 · electric 600 kWh = 74.70 · trash 18.00 · sewer 4.88 kgal = 24.40 + 6.00 → 181.50 + 2% 3.63 = **$185.13** |
| 2 | Interim — one service, no reading in the period, estimated on step 2 | Unit I, Hannah Ortiz (water only, W-10460, 6.2 kgal a month to Aug 31) | Sep 1–30; types nothing; presses **Estimate** | water 6.0 kgal → 16.25 + 4.50 + 8.00 = 28.75 · sewer follows water on this plan (the %-of-service exception) 2.4 kgal → 12.00 + 6.00 → 46.75 + 2% 0.94 = **$47.69** *(stated $29.33 before the first run, which left sewer out — corrected 2026-09-30)* |
| 3 | First bill — move-in date from the account, move-in reading typed, deposit + connection charge | Unit C, Maria Alvarez (moved in 09/12/2026; move-in reads on file for W-10442C and E-55120C, none for W-10443C) | From left at the pre-filled 09/12; types W-10443C move-in 128.9, then 488.4 / 136.7 / 19,020 | **Sep 12–30 = 19 of the cycle's 30 days, f = 19/30** (DEF-BIL-8331, 2.416.3; the cycle's first run date, DEF-BIL-8333): tier bound 5 × 19/30 = 3.1667 kgal → W-10442C 10.29 + 5.4333 × 4.50 = 24.45 → 34.74 · W-10443C 10.29 + 4.6333 × 4.50 = 20.85 → 31.14 · water bases 2 × (8.00 × 19/30 = 5.07) = 10.14 · electric 520 kWh 64.74 · trash 15.00 per cart + 3.00 × 19/30 = 1.90 · sewer 6.56 kgal 32.80 + 6.00 × 19/30 = 3.80 → 194.26 + 2% 3.89 = 198.15 + deposit 150.00 + CONN 45.00 = **$393.15** *(was $397.82 with the bases whole)* |
| 4 | Final — deposit LESS than owed | Unit J, Samuel Okafor ($50.00 deposit) | Sep 1–18; final reads 485.0 / 133.0 / 18,700 | **Sep 1–18 = 18 of 30 days, f = 0.6** (DEF-BIL-8333): water 8.78 + 7.80 (both under the 3-kgal scaled bound) + bases 2 × 4.80 · electric 280 kWh 34.86 · trash 15.00 + 3.00 × 0.6 = 1.80 · sewer 2.04 kgal 10.20 + 6.00 × 0.6 = 3.60 → 91.64 + 2% 1.83 = **$93.47**; deposit $50.00 applied → **Left to pay $43.47** *(was $103.67 / $53.67 with the bases whole)* |
| 5 | Final — deposit MORE than owed | Unit D, Maria Alvarez ($150.00 deposit) | the same readings on its own meters | the same 18/30 arithmetic → **$93.47**; deposit 150.00 → **Refund due $56.53**, to customer credit *(was $103.67 / $46.33)* |
| 6 | Catch-up Jul–Sep, split at the Jul 16 price change, one stretch never read | Unit E | periods Jul, Aug, Sep; reason MISSED; last-period reads 482.3 / 130.6 / 18,420 | month by month (July 15/31 + 16/31 across the two prices; W-10443E's unread stretch shared by days from the typed Sep 30 reading, decision log 2026-09-30) = 636.75 + 2% 12.74 = **$649.49** — re-priced independently line by line (`10-scripts/j74_reprice_case6.py`: nothing imported from the application) and it agrees to the cent |
| 7 | Penalty / theft — assessed usage, tamper charge, *Approved by* | Unit F | periods Jul, Aug, Sep; reason TAMPER; charge TAMPER $250.00; evidence typed; Approved by Dana Whitfield | month by month from F's reads (Aug 16.3 + 9.6 kgal, 1,020 kWh; Sep 14.2 + 9.3 kgal, 890 kWh; July split) = 899.85 taxable + TAMPER 250.00 + 2% 18.00 = **$1,167.85** |
| 8 | Fee — taxable reconnection fee | Unit H, John Robert | charge RECON, note typed | 75.00 + 2% 1.50 = **$76.50** |

**3b** (retired 2026-09-30): case 3's first bill from **09/13**, J70 E2's route round DEF-BIL-8563.
With 8563 fixed on the tip, case 3 bills from the account's own date and 3b has no purpose.

## RESULTS — walked 2026-09-30, build 2.413.0, 1440, PostgreSQL 16

Checks: **(a)** invoice issued, numbered, right account, kind and period · **(b)** lines match Review
line by line to the cent (Review draws one *Tiered* line per meter, so the stored tier lines of one
meter are added together first — nothing else is merged), total = lines + tax, header subtotal =
lines, money ≤ 4 decimals, **and the issued total equals the hand-priced figure** · **(c)** tax lines
as Review, present where something is taxable · **(d)** every journal entry for the bill balances,
the receivable is debited by the total, the deposit legs are right, and the customer's receivable
moves by what is left to pay · **(e)** release row: four confirmation columns true, clerk and time,
and the audit row's five confirmations · **(f)** one `invoice.one_time_sent` audit row · **(g)** frozen
snapshot names the customer, service address, mailing address and utility address · **(h)** paper
(`pdf_print`) queued · **(i)** typed readings saved in Meter Reads; estimates saved as estimated
readings · **(j)** a second Send answers the same bill (`created: false`) and a second draft is
refused (`409 BIZ-IDEMPOTENT`), and the database holds one bill.

| Case | Expected total | Bill number | Issued total | Lines match | Ledger balanced | Confirmations | Audit | Snapshot | Delivery | Readings | Duplicate refused | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Interim, 4 services | $185.13 | BL-2609-000101 | $185.13 | yes (9 Review lines = 11 stored, tiers added) | yes; receivable +185.13 | 5 of 5, Dana, 22:28:07 | 1 row | all four | paper + email + portal queued | 3 typed reads saved, locked | yes | **PASS** |
| 2 Interim, estimated | $29.33 | — | — | — | — | — | — | — | — | — | — | **FAIL** — step 2 has no way to estimate; the bill cannot be made (`DEF-BIL-8562`) |
| 3 First bill, account's date | $397.82 | — | — | — | — | — | — | — | — | — | — | **FAIL** — from 09/12 the move-in reading of that day is not found; nothing prices, Move-in charges $0.00, no deposit, no CONN (`DEF-BIL-8563`) |
| *3b First bill from 09/13* | *$397.82* | *BL-2609-000102* | *$397.82* | *lines yes; stored subtotal 198.84 ≠ lines 393.84* | *yes; deposit 150.00 credited to 2300 liability; receivable +397.82* | *5 of 5* | *1 row* | *all four* | *queued* | *4 typed reads saved* | *yes* | *FAIL on (b) only — `DEF-BIL-8565`* |
| 4 Final, deposit < owed | $103.67 | BL-2609-000103 | $103.67 | yes (9 = 9) | yes; deposit 50.00 released from 2300 against receivable; receivable nets **53.67** | 5 of 5, Dana, 22:29:26 | 1 row | all four | queued | 3 final reads saved, locked | yes | **PASS** |
| 5 Final, deposit > owed | $103.67 | BL-2609-000104 | $103.67 | yes (9 = 9) | yes; deposit 150.00 released: 103.67 to receivable, **46.33 to 2400 Customer credit balances**; receivable nets **0.00** | 5 of 5, Dana, 22:29:49 | 1 row | all four | queued | 3 final reads saved, locked | yes | **PASS** |
| 6 Catch-up Jul–Sep | $649.49 | BL-2609-000105 | **$710.06** | **no** — Review 32 lines vs 48 stored, one group for the whole window | yes (in itself) | 5 of 5, Dana, 22:30:30 | 1 row | all four | queued | typed saved; **no estimated read saved for W-10443E** | yes | **FAIL** — sewer billed twice for Aug + Sep (`DEF-BIL-8560`, +$60.58); months lost (`DEF-BIL-8561`); estimate not in Meter Reads (`DEF-BIL-8564`) |
| 7 Penalty / theft | $1,167.85 | BL-2609-000106 | **$1,268.62** | **no** — Review 33 lines vs 49 stored; stored subtotal 998.65 leaves out TAMPER | yes (in itself); TAMPER to 4640 | 5 of 5, Dana, 22:31:00; *Approved by* on the bill | 1 row | all four + approver | queued | read-only, from Meter Reads | yes | **FAIL** — sewer billed twice for Aug + Sep (`DEF-BIL-8560`, +$100.77); months lost (`8561`); subtotal (`8565`) |
| 8 Fee, RECON | $76.50 | BL-2609-000107 | $76.50 | yes (1 = 1) | yes; RECON to 4610, tax 1.50 to 2200-01 | 5 of 5, Dana, 22:31:18 | 1 row | all four | queued | none needed | yes | **PASS** |

**Four of eight pass end to end** (1, 4, 5, 8). Every one of the six bills that was sent passed
(a), (c), (d), (e), (f), (g), (h) and (j): issued and numbered, balanced journal, five confirmations
recorded with the clerk and the time, one audit row, a complete snapshot, paper queued, and a second
Send or draft never made a second bill. What failed is the MONEY of the two multi-month kinds, the
two things a clerk cannot do (estimate an interim, bill a first bill from the account's own move-in
day), and a first bill's footer.

### What the database showed that the screen did not

* **Sewer on a multi-month catch-up or penalty is charged twice (`DEF-BIL-8560`, high).** On case 6,
  sewer for August and for September is each **$59.39 — the two months' water together** (Aug
  15.09 kgal → $30.18, Sep 14.60 kgal → $29.21, pair $59.39). On case 7 each is **$98.80** where Aug
  $51.80 + Sep $47.00 = $98.80. July, split at the price change, is right; so is every water,
  electric, trash and base line. Overcharge: **$60.58** on case 6 and **$100.77** on case 7, tax
  included. **J70 accepted $710.06 for the catch-up** because every check compared the bill with
  itself: lines add up, tax is 2%, the journal balances, Review equals the invoice.
* **A catch-up or penalty loses its months (`DEF-BIL-8561`).** Review draws one group
  *07/01/2026 – 09/30/2026*, merges usage across months on some rows (*Electric 1,720 kWh $214.14*)
  and lists four unlabelled base rows; every stored line is dated the whole window, and 12 of 16 water
  usage lines name no meter.
* **A first bill's Subtotal + Tax is not its Total (`DEF-BIL-8565`).** Case 3b prints Subtotal
  $198.84, Tax $3.98, Total due $397.82 and stores `subtotal` 198.84 — the deposit and CONN are in
  the total and in no footer line. The penalty stores the same shape (subtotal 998.65 without the
  $250.00 TAMPER). A fee bill counts its fee in the subtotal.
* **A catch-up's estimate is not saved in Meter Reads (`DEF-BIL-8564`).** Review says *12 readings
  estimated*; `meter_reads` holds no estimated row for W-10443E.
* Case 7's *assessed usage*: the seed gives Unit F ordinary monthly reads, so the penalty prices on
  those, shown read-only on step 2 as the design says; no tamper-assessed reads were seeded.
* Delivery: the clerk chose Email; paper (`pdf_print`), email and portal rows were all queued —
  paper is the floor (BR-BIL-036).

## RE-WALKED 2026-10-01 (fixes) — J74 fixes 2.416.4 on the tip, 1440, PostgreSQL 16: 8 OF 8 PASS

After the five fixes (`DEF-BIL-8560`, `8561`, `8562`, `8564`, `8565`, released as **2.416.4**, the
version above the tip's 2.416.3 so the build on screen says whether they are in it) merged with the tip
(`DEF-BIL-8330`/`8332`/`8563` 2.416.1, `DEF-BIL-8331` 2.416.3). A FRESH database: migrate, `seed_demo`,
the J70 seed. The walk ran on a build reading 2.416.3, before the version was moved to 2.416.4; no code
changed between the two.

⚠ **CASES 3, 4 AND 5 NEED THE SEED FIX `DEF-BIL-8333` (2.416.5), WHICH IS NOT ON THE TIP YET.** Their
figures ($393.15, $93.47, $93.47) prorate the base by the days billed, and that needs the cycle
`J70-MONTHLY` to have a first run date. The seed does not give it one yet, so for this walk it was set
in this database only and not committed: `UPDATE cycles SET first_run_date = '2026-01-01' WHERE code =
'J70-MONTHLY'`. **On a database seeded before 8333 lands, those three cases fail on their totals by
design** — they bill the bases whole ($397.82, $103.67, $103.67). The seed's first W-10460 read no
longer carries a consumption with no day count (it made Meter Reads' own estimate 8.90 kgal instead of
6.0).

The verifier also checks that the Review footer adds up (Subtotal + Tax + One-time charges = Total),
that a catch-up stores one window per month and names every water meter, and that no estimated
reading is saved over a stretch a real reading covers. `invoices.subtotal` is checked as what it
holds for every bill — the taxable subtotal (decision log 2026-09-30, judgment (d)).

| Case | Expected total | Bill number | Issued total | Lines match | Ledger balanced | Confirmations | Audit | Snapshot | Delivery | Readings | Duplicate refused | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Interim, 4 services | $185.13 | BL-2609-000101 | $185.13 | yes | yes; receivable +185.13 | 5 of 5, Dana | 1 row | all four | paper queued | 3 typed, saved | yes | **PASS** |
| 2 Interim, estimated | $47.69 | BL-2609-000102 | $47.69 | yes | yes | 5 of 5 | 1 row | all four | queued | W-10460 6.0 kgal saved as an estimated reading, locked to the bill | yes | **PASS** |
| 3 First bill, account's date (19/30) | $393.15 | BL-2609-000103 | $393.15 | yes; footer $194.26 + tax $3.89 + one-time $195.00 | yes; deposit $150.00 to 2300 | 5 of 5 | 1 row | all four | queued | move-in + 3 typed, saved | yes | **PASS** |
| 4 Final, deposit < owed (18/30) | $93.47 | BL-2609-000104 | $93.47 | yes | yes; deposit $50.00 released; receivable nets $43.47 | 5 of 5 | 1 row | all four | queued | 3 saved | yes | **PASS** |
| 5 Final, deposit > owed (18/30) | $93.47 | BL-2609-000105 | $93.47 | yes | yes; $56.53 to customer credit; receivable 0.00 | 5 of 5 | 1 row | all four | queued | 3 saved | yes | **PASS** |
| 6 Catch-up Jul–Sep | $649.49 | BL-2609-000106 | $649.49 | yes; 3 month groups; every water line names its meter | yes | 5 of 5 | 1 row | all four | queued | typed saved; no estimate saved (all shares of a real reading) | yes | **PASS** |
| 7 Penalty / theft | $1,167.85 | BL-2609-000107 | $1,167.85 | yes; 3 months + Other charges; footer $899.85 + $18.00 + $250.00 | yes; TAMPER to 4640 | 5 of 5; approver on the bill | 1 row | all four + approver | queued | read-only | yes | **PASS** |
| 8 Fee, RECON | $76.50 | BL-2609-000108 | $76.50 | yes | yes | 5 of 5 | 1 row | all four | queued | none needed | yes | **PASS** |

**Found by re-pricing case 6 independently, and filed rather than fixed (`DEF-BIL-8566`):** July,
cut at the Jul 16 price change, charges the $15.00 per-cart trash charge in EACH half while the
$3.00 base beside it is prorated ($1.45 + $1.55). With the cart charge prorated like the base the
catch-up would be $634.19. No rule says which is right; it needs a ruling. The same is true of the
final and first bills above: their trash charge is $15.00 whole while the base is a share. **Also
seen:** every usage line on the penalty's Review carries *Est.* — the flag is set per SERVICE, and
July's split shares make the whole service "estimated".

## RE-WALKED 2026-10-01 (PO ruling 5: the cart prorates) — build 2.422.0, 1440, PostgreSQL 16: 7 OF 8 PASS, the eighth on a clock date only

**Why the totals moved.** The PO ruled on 2026-10-01 (decision log *"SIX PO RULINGS IN ONE MESSAGE"*, (5)),
verbatim: *"A · Cart shrinks too: $9.00"* — the $15.00 trash cart on a part month prorates exactly like
the base (`DEF-BIL-8566`, BR-RAT-1046). The expected totals were re-priced BEFORE the run, in the spec and
the verifier, with the day arithmetic written out:

| Case | Days | Cart was | Cart now | Taxable | Tax 2% | Total was → now |
|---|---|---|---|---|---|---|
| 3 First bill | Sep 12–30 = 19/30 | $15.00 | 19/30 × $15.00 = **$9.50** | 194.26 − 15.00 + 9.50 = 188.76 | 3.78 | $393.15 → **$387.54** (+ deposit 150.00 + CONN 45.00) |
| 4 Final, deposit < owed | Sep 1–18 = 18/30 | $15.00 | 18/30 × $15.00 = **$9.00** | 91.64 − 6.00 = 85.64 | 1.71 | $93.47 → **$87.35**; left to pay $43.47 → **$37.35** |
| 5 Final, deposit > owed | 18/30 | $15.00 | **$9.00** | 85.64 | 1.71 | $93.47 → **$87.35**; refund $56.53 → **$62.65** |
| 6 Catch-up Jul–Sep | Jul 1–15 = 15/31, Jul 16–31 = 16/31 | $15.00 + $15.00 | **$7.26 + $7.74** | 636.75 − 15.00 = 621.75 | 12.44 | $649.49 → **$634.19** (`j74_reprice_case6.py`, independent) |
| 7 Penalty Jul–Sep | July split as case 6 | $15.00 + $15.00 | **$7.26 + $7.74** | 899.85 − 15.00 = 884.85 | 17.70 | $1,167.85 → **$1,152.55** (+ TAMPER 250.00) |
| 1, 2, 8 | whole month / no cart / fee | — | — | — | — | unchanged: $185.13, $47.69, $76.50 |

**Stack.** A FRESH database `sbh_six74`: `migrate` → `seed_demo` → `seed_j70_one_time_bill.py` (template
`sbh_six74_seeded`); `runserver` + the built SPA behind `server.mjs`; the spec at 1440 with Chromium
`/opt/pw-browsers/chromium-1194`; then `verify_j74_one_time_bill.py` against the database.

**Results — every priced bill equals its hand-priced figure to the cent.** Case 1 **$185.13** · case 2
**$47.69** · case 3 **$387.54** · case 4 **$87.35** · case 5 **$87.35** · case 6 **$634.19** · case 7
**$1,152.55** — each PASS on all ten checks (a)–(j): issued and numbered, lines = Review, tax, a balanced
journal (case 5: deposit 150.00 released, 87.35 to receivable, **62.65 to 2400 customer credit**), the five
confirmations, one audit row, the snapshot, delivery queued, readings saved, the duplicate refused. On the
paper case 4 reads *"trash - 1 × Trash 96-gallon cart = 10.80"* — the $9.00 cart and the $1.80 base on one
line (`DEF-BIL-8151`'s layout). **Case 8 ($76.50) passes on its money and fails (a)/(j) on its PERIOD**:
a fee bill's period is the day it is raised, and the walk ran on 1 October against a verifier that states
30 September. That is the walk's clock, not a product fault; the spec's two case-4/5 expected totals were
missed in the first edit and corrected after the run (the screen showed the ruled $87.35).

## RE-WALKED 2026-10-01 (PO ruling: an interim bill cuts the base down by days) — build 2.423.0, 1440, PostgreSQL 16: 8 OF 8 PASS

**The ruling.** PO verbatim: *"Should interim bills cut the base down like first and final bills? A · Cut
down (10/30)"* (decision log *"TWO PO RULINGS ON THE BASE CHARGE"*, `BR-BIL-1066`, `OQ-242` option (a)).
An interim bill's base is `base × service days / the account's own cycle length`; the cycle is read on
the window's last day. An interim bill for an account with no cycle is refused (*"No billing cycle.
Assign one on the account."*).

**Re-priced by hand BEFORE the run — the two interim cases do not move:**

| Case | Window | Cycle (J70-MONTHLY, monthly from 2026-01-01) | Factor | What it touches | Total |
|---|---|---|---|---|---|
| 1 Interim, 4 services | Sep 1–30 = 30 days | September = 30 days | 30/30 = **1** | water bases 2 × $8.00, cart $15.00, trash base $3.00, sewer base $6.00 all whole; tier bound stays 5 kgal | **$185.13** (unchanged) |
| 2 Interim, estimated | Sep 1–30 = 30 days | 30 days | 30/30 = **1** | water base $8.00, sewer base $6.00 whole | **$47.69** (unchanged) |

Before the ruling the same two cases also had a factor of 1, for a different reason: the window's own
length (30) stood in for the cycle's. They would move only on a window shorter than the cycle — e.g. Sep
21–30 on a $30.50 base is 10/30 × $30.50 = **$10.17**, and WE-6's 20/31 is 7.74 / 5.16 / 11.61 =
**$24.51**; both are asserted in `06-backend/tests/test_br_bil_1066_interim_bill_prorates_its_base.py`.

**Case 8's date.** A fee bill is dated the day it is raised, so its period is that one day. The verifier
stated `2026-09-30` and the last walk, on 1 October, failed (a)/(j) on the clock alone. It now checks the
period against the run's own bill date and the issue day (± one day for the zone) — never a fixed date.
This walk raised it on 1 October: **BL-2610-000008**, period 2026-10-01, PASS.

**Stack.** A fresh database `sbh_j74i`: `migrate` → `seed_demo` → `seed_j70_one_time_bill.py`;
`runserver` on 8494 and the built SPA (`--mode compose`) behind `server.mjs` on 8594; the spec at 1440
with Chromium `/opt/pw-browsers/chromium-1194`; then `verify_j74_one_time_bill.py`. Spec: **8 passed
(2.2 min)**. Verifier: exit 0, every case PASS on all ten checks (a)–(j).

| Case | Expected total | Bill number | Issued total | Lines match | Ledger balanced | Confirmations | Audit | Snapshot | Delivery | Readings | Duplicate refused | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Interim, 4 services (30/30) | $185.13 | BL-2609-000001 | $185.13 | yes | yes; receivable +185.13 | 5 of 5, Dana | 1 row | all four | paper + email + portal queued | 3 typed, saved | yes | **PASS** |
| 2 Interim, estimated (30/30) | $47.69 | BL-2609-000002 | $47.69 | yes | yes | 5 of 5 | 1 row | all four | queued | W-10460 estimate saved | yes | **PASS** |
| 3 First bill (19/30) | $387.54 | BL-2609-000003 | $387.54 | yes | yes; deposit $150.00 to 2300 | 5 of 5 | 1 row | all four | queued | move-in + 3 typed, saved | yes | **PASS** |
| 4 Final, deposit < owed (18/30) | $87.35 | BL-2609-000004 | $87.35 | yes | yes; deposit $50.00 released | 5 of 5 | 1 row | all four | queued | 3 saved | yes | **PASS** |
| 5 Final, deposit > owed (18/30) | $87.35 | BL-2609-000005 | $87.35 | yes | yes; refund to customer credit | 5 of 5 | 1 row | all four | queued | 3 saved | yes | **PASS** |
| 6 Catch-up Jul–Sep | $634.19 | BL-2609-000006 | $634.19 | yes; 3 month groups | yes | 5 of 5 | 1 row | all four | queued | typed saved; no estimate rows | yes | **PASS** |
| 7 Penalty / theft | $1,152.55 | BL-2609-000007 | $1,152.55 | yes | yes; TAMPER to 4640 | 5 of 5; approver on the bill | 1 row | all four + approver | queued | read-only | yes | **PASS** |
| 8 Fee, RECON (raised 1 Oct) | $76.50 | BL-2610-000008 | $76.50 | yes | yes; RECON to 4610 | 5 of 5 | 1 row | all four | queued | none needed | yes | **PASS** |

**Not changed, and reported rather than ruled:** a catch-up or penalty bill divides each stated
sub-period by its OWN length (`backbill`), so a sub-period shorter than a cycle (say Sep 1–10) charges
that sub-period's base whole; a fee bill has no base. The ruling is interim only.

## The SQL (run it in `psql` against the walked database)

Set the tenant first (hard rule 1), then set `inv` to a bill's id
(`SELECT id FROM invoices WHERE invoice_no = 'BL-2609-000105'`), `run` to its `bill_run_id` and
`acct` to its `account_id`. The same statements, with parameters, are the constants at the top of
`10-scripts/verify_j74_one_time_bill.py`.

```sql
SELECT set_config('app.tenant_id', (SELECT id::text FROM tenants WHERE subdomain = 'brazosbend'), false);
\set inv '''<invoice id>'''
\set run '''<bill_run id>'''
\set acct '''<account id>'''

-- (a) the invoice
SELECT invoice_no, status, bill_type, account_id, period_start, period_end,
       subtotal, tax_total, total, currency, issued_at, due_date
  FROM invoices WHERE id = :inv;

-- (b)(c) its lines, and money stored to at most 4 decimals
SELECT l.kind, s.code AS service, a.asset_no, l.description, l.quantity, l.unit, l.amount,
       l.taxable, l.period_start, l.period_end
  FROM invoice_lines l LEFT JOIN services s ON s.id = l.service_id LEFT JOIN assets a ON a.id = l.asset_id
 WHERE l.invoice_id = :inv ORDER BY l.created_at, l.id;
SELECT sum(amount) FILTER (WHERE kind <> 'tax') AS lines, sum(amount) FILTER (WHERE kind = 'tax') AS tax,
       count(*) FILTER (WHERE amount <> round(amount, 4)) AS over_4dp
  FROM invoice_lines WHERE invoice_id = :inv;

-- (d) every journal entry for the bill balances; its legs; the customer's receivable, net
SELECT je.id, je.status, sum(jl.amount) FILTER (WHERE jl.side = 'debit') AS debits,
       sum(jl.amount) FILTER (WHERE jl.side = 'credit') AS credits
  FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
 WHERE je.source_type = 'invoice' AND je.source_id = :inv GROUP BY je.id, je.status;
SELECT la.code, la.name, jl.side, jl.amount
  FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
  JOIN ledger_accounts la ON la.id = jl.ledger_account_id
 WHERE je.source_type = 'invoice' AND je.source_id = :inv ORDER BY je.created_at, jl.side DESC, la.code;
SELECT sum(CASE WHEN jl.side = 'debit' THEN jl.amount ELSE -jl.amount END) AS receivable_net
  FROM journal_lines jl JOIN ledger_accounts la ON la.id = jl.ledger_account_id
 WHERE jl.account_id = :acct AND la.code = '1200';

-- (e) the release row: the confirmations, the clerk, the time
SELECT r.compliance_confirmed, r.email_mandate_confirmed, r.sms_mandate_confirmed,
       r.autopay_mandate_confirmed, u.email AS confirmed_by, r.confirmed_at, r.released_at
  FROM bill_run_releases r LEFT JOIN users u ON u.id = r.confirmed_by WHERE r.bill_run_id = :run;

-- (f) the audit row for the send (its `after` carries all five confirmations)
SELECT action, actor_user_id, after -> 'confirmations', created_at
  FROM audit_log WHERE entity_type = 'invoice' AND entity_id = :inv AND action = 'invoice.one_time_sent';

-- (g) the frozen snapshot
SELECT bill_payload ->> 'customer_name', bill_payload ->> 'service_address',
       bill_payload ->> 'mailing_address', bill_payload ->> 'utility_address',
       bill_payload -> 'penalty' -> 'approved_by'
  FROM invoices WHERE id = :inv;

-- (h) delivery
SELECT channel, status FROM outbound_messages WHERE source_type = 'invoice' AND source_id = :inv;

-- (i) readings typed on step 2 (e.g. W-10442 488.4), and any estimated reading for a meter
SELECT a.asset_no, r.current_value, r.source, r.lifecycle, r.read_at::date, r.estimation_method
  FROM meter_reads r JOIN assets a ON a.id = r.asset_id
 WHERE a.asset_no = 'W-10442' AND r.channel = 'total' ORDER BY r.read_at;
SELECT a.asset_no, r.read_at::date, r.current_value, r.source, r.estimation_method
  FROM meter_reads r JOIN assets a ON a.id = r.asset_id
 WHERE a.asset_no = 'W-10443E'
   AND (r.source ILIKE '%estimat%' OR r.estimation_method IS NOT NULL OR r.status ILIKE '%estimat%');

-- (j) one bill for the run, and for the account, kind and period
SELECT count(*) FROM invoices WHERE bill_run_id = :run;
SELECT count(*) FROM invoices i, invoices me
 WHERE me.id = :inv AND i.account_id = me.account_id AND i.bill_type = me.bill_type
   AND i.period_start = me.period_start AND i.period_end = me.period_end AND i.status <> 'void';
```

**This journey leaves (for downstream):** seven issued one-time bills on Elm St (A interim, C first
from 09/13, D and J final, E catch-up, F penalty, H fee), each with one number, balanced entries, one
release, one audit row and queued delivery; J's receivable at $53.67 and D's $46.33 in customer credit.
