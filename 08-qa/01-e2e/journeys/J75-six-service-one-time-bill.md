# J75 — Every one-time bill kind for a utility with six services: water, sewer, trash, fire, battery, solar

---
id: J75
tier: 2
rules: [BR-BIL-1067, BR-BIL-1066, BR-BIL-010, BR-BIL-011, BR-BIL-012, BR-BIL-013, BR-BIL-014, BR-BIL-018, BR-RAT-090, BR-RAT-1046]
stories: [US-BIL-010, US-BIL-011, US-BIL-012, US-BIL-013, US-BIL-014, US-BIL-032, US-BIL-033]
depends_on_journeys: [J74]
# WALKED 2026-10-01 at 1440 on PostgreSQL 16, build 2.428.1 — spec
# `07-frontend/e2e/J75-six-service-one-time-bill.spec.ts`, database check
# `10-scripts/verify_j74_one_time_bill.py --world j75`, bill-detail check
# `10-scripts/j75_bill_breakdowns.mjs`, seed `10-scripts/seed_six_service_one_time.py`.
---

**The request, verbatim (PO 2026-10-01):** *"when you complete this please run end to end run for all one
tim ebill scenarios with utility ahving 6 utility services - Water, Sewer, trash, Fire, Battery and Solar -
and see we are able to create one time bill for this utility if you face bugs fix them - we already done end
to end run before you can use that"*.

**Intent.** J74 proved the one-time bill end to end on Brazos Bend, which runs electric, gas and broadband
and prices trash with a flat base. J75 runs the SAME harness (J74's spec copied, its verifier with a second
world) on a utility that has exactly the six services the PO named, after the capacity-base build
(BR-BIL-1067, 2.427.0): trash, battery and solar bases priced BY SIZE, one size of each left unpriced, and
fire's $84.00 property.

## The world — `10-scripts/seed_six_service_one_time.py`

**A new utility, signed up through the real signup service** (`provision_tenant`, as S114 does): *Six Rivers
Utility*, subdomain `sixrivers`, Texas, owner **Priya Shah** (`priya@sixriversutility.com`), services
**water, sewer, trash, fire, battery, solar** and nothing else. Its sample set, taxes, charge codes and
tax-liability accounts are the signup's own. The seed then adds, on 1200 Confluence Ave:

* **Plan `SRU-RES` "Six Rivers Residential"**, every schedule from 2026-01-01: water tiered **0–5 kgal
  $4.00, 5–15 $6.50, 15+ $8.00**, base `BASE-W` W-58 **$8.00** · sewer **90% of water × $5.00**, base
  `BASE-S` **$9.00** · trash **per container by size** CART-35 $10, CART-64 $12, CART-96 $15, DUMP-4 $85 ·
  fire **per line by size** FL-2 $12, FL-4 $30, FL-6 $60, base `BASE-FIRE` **$0.00** · battery **$3.00/kW**
  summed · solar **$14.00/kW** summed.
* **Bases BY SIZE (BR-BIL-1067):** `BASE-T` CART-64 $2.00, CART-96 $3.00, DUMP-4 $10.00 — **CART-35 not
  priced**; `BASE-BAT` BAT-5 $2.00, BAT-10 $4.00 — **BAT-15 not priced**; `BASE-SOL` SOL-P2 $1.00, SOL-P4
  $2.00, SOL-P8 $3.00 — **SOL-P6 not priced**.
* Tax: **Local · Bexar County 2.00%** on every usage and base line (TX State 6.25% names commercial and
  industrial only). CONN $45.00, the deposit, RECON $75.00 and TAMPER $250.00 are not taxed (the signup's
  own codes). Cycle `SRU-MONTHLY` (monthly from Jan 1, 21 days to pay). Deposit rule $150.00.
* Eight residential accounts, each carrying several services at once:

| Unit | Customer | Equipment | Used for |
|---|---|---|---|
| 1 | Ana Ruiz | W-2001 · 2 × CART-96 + 1 × CART-35 · FL-6 + 2 × FL-2 · BAT-10 · SOL-P2 + SOL-P4 + SOL-P8 | interim, all six services |
| 2 | Ben Okoro | W-2002 (read to Aug 31 only) · DUMP-4 · BAT-15 | interim, estimated |
| 3 | Carla Mendes | W-2003 (move-in read 100.0 on 09/12) · CART-64 · FL-4 · BAT-5 · SOL-P6 | first bill |
| 4 | Dev Patel ($50.00 deposit) | W-2004 · CART-96 · FL-2 · BAT-10 · SOL-P4 | final, deposit less |
| 5 | Elena Brooks ($200.00 deposit) | as Unit 4 | final, deposit more |
| 6 | Femi Adeyemi | W-2006 read monthly May–Aug · CART-96 · FL-2 · BAT-5 · SOL-P2 | catch-up Jul–Sep |
| 7 | Gita Rao | W-2007 read monthly May–Sep · CART-64 · FL-4 · BAT-10 · SOL-P2 + SOL-P4 | penalty Jul–Sep |
| 8 | Hugo Lind | W-2008 · CART-96 | fee |

## Stack (re-runnable)

1. `createdb` → `manage.py migrate` (template `sbh_six_mig`) → `seed_six_service_one_time.py` (template
   `sbh_six_seeded`); each walk starts from a fresh copy, **`sbh_six`** (kept, holds the walked bills).
2. `runserver 127.0.0.1:8696` and the built SPA (`npx vite build --mode compose`) behind `server.mjs` on 8796.
3. `E2E_TENANT=sixrivers E2E_EMAIL=priya@sixriversutility.com E2E_BASE_URL=http://127.0.0.1:8796
   E2E_VIEWPORT=1440 npx playwright test e2e/J75-six-service-one-time-bill.spec.ts --workers=1`.
4. `DATABASE_URL=…/sbh_six python 10-scripts/verify_j74_one_time_bill.py --world j75` — J74's checks
   (a)–(j) plus **(k)**: every capacity line stores its size trace (`invoice_lines.pricing_trace`) with the
   sizes and counts stated and `base_priced: false` exactly on the size left unpriced.
5. `BASE=http://127.0.0.1:8796 BILLS=<the eight ids> node 10-scripts/j75_bill_breakdowns.mjs` — the sent
   bill's own Charges tab shows the breakdown under every capacity line.

## The eight cases, priced by hand BEFORE the run

On a part month the bases, the tier bounds, the trash/fire per-container charges (B4.3, `DEF-BIL-8566`) **and
the battery and solar kW charge** (B4.3; B5 WE-16/GT-31; GT-15 amended 2026-08-11, *"BOTH lines prorate"*)
are × days/30. ⚠ **The first statement of cases 3–5 priced the kW charge WHOLE ($425.11, $159.63) because
that is what the code did** — the trap J74 named: a figure taken from the code agrees with the bill and
proves nothing. Re-read against WE-16 after the first pass, it is `DEF-BIL-8743`, fixed below; the figures
in this table are the signed rule's.

| # | Kind | Account | Working | Expected |
|---|---|---|---|---|
| 1 | Interim Sep 1–30 | Unit 1 | W-2001 500.0 → 512.0 = 12 kgal: 5 × 4.00 + 7 × 6.50 = 65.50 + 8.00 · sewer 10.8 × 5 = 54.00 + 9.00 · trash 2 × (15 + 3) + 1 × (10 + **0.00**) = 46.00 · fire 60 + 2 × 12 = **84.00** · battery 10 kW × 3 = 30 + 4 · solar 14 kW × 14 = 196 + 1 + 2 + 3 → 502.50 + 2% 10.05 | **$512.55** |
| 2 | Interim, estimated | Unit 2 | estimate 6.0 kgal (0.2 a day): 20.00 + 6.50 + 8.00 = 34.50 · sewer 5.4 × 5 = 27.00 + 9.00 · DUMP-4 85 + 10 · BAT-15 15 kW × 3 = 45 + **0.00** → 210.50 + 4.21 | **$214.71** |
| 3 | First bill Sep 12–30 (19/30) | Unit 3 | 8.6 kgal, bound 3.1667: 12.67 + 35.32 + base 5.07 = 53.06 · sewer 7.74 × 5 = 38.70 + 5.70 · CART-64 (12 + 2) × 19/30 = 8.87 · FL-4 30 × 19/30 = 19.00 · BAT-5 5 kW × 3 × 19/30 = 9.50 + 1.27 · SOL-P6 6 kW × 14 × 19/30 = 53.20 + **0.00** → 189.30 + 3.79 + deposit 150.00 + CONN 45.00 | **$388.09** |
| 4 | Final Sep 1–18 (18/30), $50 deposit | Unit 4 | 4.2 kgal, bound 3: 12.00 + 7.80 + 4.80 · sewer 18.90 + 5.40 · CART-96 10.80 · FL-2 7.20 · BAT-10 30.00 × 0.6 = 18.00 + 2.40 · SOL-P4 56.00 × 0.6 = 33.60 + 1.20 → 122.10 + 2.44; left to pay 124.54 − 50.00 = **$74.54** | **$124.54** |
| 5 | Final, $200 deposit | Unit 5 | as case 4; refund 200.00 − 124.54 = **$75.46** to customer credit | **$124.54** |
| 6 | Catch-up Jul–Sep, MISSED | Unit 6 | Jul 7.0 kgal 41.00 + sewer 40.50 · Aug 8.0 47.50 + 45.00 · Sep 7.5 (typed 228.5) 44.25 + 42.75 · each month trash 18 + fire 12 + battery 17 + solar 29 = 76 × 3 → 489.00 + 9.78 | **$498.78** |
| 7 | Penalty Jul–Sep, TAMPER, Approved by Priya Shah | Unit 7 | Jul 60.50 + 54.00 · Aug 67.00 + 58.50 · Sep 54.00 + 49.50 · each month trash 14 + fire 30 + battery 34 + solar 87 = 165 × 3 → 838.50 + 16.77 + TAMPER 250.00 | **$1,105.27** |
| 8 | Fee, RECON (untaxed here) | Unit 8 | 75.00, no tax | **$75.00** |

## RESULTS — walked 2026-10-01, build 2.428.1, 1440, PostgreSQL 16: 8 OF 8 PASS

(The screenshots' footer reads **v2.427.1**: the walk ran before the tip's 2.428.0 landed and the fixes
were renumbered above it as 2.428.1 at push. These fixes did not change after the walk; 2.428.0 — the bulk
run's Sign off speed-up, `DEF-BIL-8696`/`8697`/`8694`/`8720` — was merged in after it.)

| # | Kind | Expected | Bill | Issued | (a)–(k) | Size breakdown on Review and on the sent bill | Result |
|---|---|---|---|---|---|---|---|
| 1 | Interim, six services | $512.55 | BL-2609-000001 | $512.55 | all PASS | trash *96-gallon cart × 2 · base $3.00 · $15.00 each* + *35-gallon cart × 1 · no base price · $10.00 each*; fire *6" × 1 … $60.00 each* + *2" × 2 … $12.00 each* (one $84.00 line); battery *10 kW × 1 · base $4.00*; solar 2/4/8 kW; warning *"BASE-T has no price for CART-35. Billed $0.00."* | **PASS** |
| 2 | Interim, estimated | $214.71 | BL-2609-000002 | $214.71 | all PASS | DUMP-4 *base $10.00 · $85.00 each*; *Battery 15 kW × 1 · no base price*; warnings: BASE-BAT/BAT-15 and *1 reading estimated*; W-2002 6.0 kgal saved as an estimated read | **PASS** |
| 3 | First bill (19/30) | $388.09 | BL-2609-000003 | $388.09 | all PASS | CART-64, FL-4, BAT-5, *Solar panel 6 kW × 1 · no base price*; solar 6 kW $53.20, battery 5 kW $9.50 (after `DEF-BIL-8743`); footer $189.30 + $3.79 + one-time $195.00 | **PASS** |
| 4 | Final, deposit less | $124.54 | BL-2609-000004 | $124.54 | all PASS | screen *Left to pay $74.54*; $50.00 deposit released | **PASS** |
| 5 | Final, deposit more | $124.54 | BL-2609-000005 | $124.54 | all PASS | screen *Refund due $75.46*; $75.46 to customer credit | **PASS** |
| 6 | Catch-up Jul–Sep | $498.78 | BL-2609-000006 | $498.78 | all PASS | 3 month groups; **one** trash and **one** fire line a month (after `DEF-BIL-8733`) | **PASS** |
| 7 | Penalty Jul–Sep | $1,105.27 | BL-2609-000007 | $1,105.27 | all PASS | 3 months + Other charges; approver on the bill; one trash/fire line a month | **PASS** |
| 8 | Fee, RECON | $75.00 | BL-2610-000008 | $75.00 | all PASS | footer Subtotal **$75.00** (after `DEF-BIL-8734`) | **PASS** |

Every case: issued and numbered, Review lines = stored lines to the cent, a balanced journal, five
confirmations with the clerk and the time, one audit row, a complete snapshot, paper queued, typed readings
saved, and a second Send or a second draft never made a second bill. Screenshots:
`08-qa/screens/six-service-onetime-2026-10-01/` (step 2, Review, Sent and the bill's Charges tab per case).

### Bugs found on the first pass, filed, fixed (2.428.1) and re-walked

* **`DEF-BIL-8733` — a catch-up or penalty printed and stored trash and fire as TWO lines a month**
  (*Per cart $15.00* and *Base · per cart $3.00*) where every other kind prints one line per service (PO
  2026-09-30, *"per service"*). Amounts were right. The back-bill pass prices through `price_bill` and never
  reached `DEF-BIL-8151`'s join; it now joins per month (`counted_service_line.
  one_line_per_counted_service_per_window`). **Unit 6's catch-up: 12 trash and fire lines became 6** (3 trash
  at $18.00 = $54.00, 3 fire at $12.00 = $36.00 — the same $90.00), and the penalty the same; $498.78 and
  $1,105.27 did not move.
* **`DEF-BIL-8743` — a solar or battery kW charge was charged WHOLE on a part period** (first and final
  bills): 6 kW × $14.00 = $84.00 for 19 of 30 days, while its base and trash/fire's per-container charge
  prorated. Signed law (B4.3, WE-16/GT-31, GT-15 *"BOTH lines prorate"*) prorates it; only the `capacity`
  pricing model did, and a schedule quoted *flat per kW* — the shape the signup's own sample schedules carry
  — did not. Now flagged where billing sums the installed kW (`installed_sum_line`) and prorated in the
  engine's usage stage exactly as the cart is. Case 3 **$425.11 → $388.09**, cases 4 and 5 **$159.63 →
  $124.54**; whole months (cases 1, 2, 6, 7) unchanged. The kW quantity is never scaled.
* **`DEF-BIL-8734` — a fee bill whose code is not taxed printed Subtotal $0.00 over Total $75.00.** J74's
  RECON is taxable by its seed, so nothing had raised an untaxed fee; a freshly signed-up utility's RECON is
  untaxed. The Review footer now counts the fee as the subtotal. (The STORED `invoices.subtotal` of a fee
  bill is still the taxable subtotal — `DEF-BIL-6124` / `DEF-BIL-7966`, open, not touched here.)

### Open — reported, not ruled or not ours

* ~~**The prorated kW line prints its rate unscaled**~~ — **FIXED, `DEF-BIL-8744` (2.430.1)**: the line
  now reads *6 kW · $14.00 · 19/30 days · $53.20* on Review, on the sent bill's Charges tab and the
  portal, and *solar usage · 18/31 days* on a document printed after the fix; no amount moved. Walked at
  1440 on copies of `sbh_six` (`10-scripts/def_bil_8744_day_share_walk.mjs`): cases 3–5's Charges tabs
  and Unit 7's final bill (1–18 Oct, $156.49, Review → Send → Charges → document), before and after —
  `1440-def-bil-8744-{before,after}-*.png`. Cases 3–5's printed documents were kept at issue and stay
  as printed.
* ~~**A utility that signs up on the 1st–4th of a month gets a short sample set**~~ — **FIXED,
  `DEF-MET-8693` with `DEF-BIL-8755`, `DEF-PAY-8756`, `DEF-RAT-8757` (2.432.2)**; decision log 2026-10-01.
* On bill detail, a summing service (battery, solar) prints its size breakdown under both its kW line and
  its base line — the stored trace is on both. Cosmetic; not filed.

**This journey leaves (for downstream):** eight issued one-time bills at Six Rivers on `sbh_six`.
