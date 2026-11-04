NEW CONNECT — THE FIVE BUILT STEPS, PHOTOGRAPHED WITH REAL DATA
captured 2026-09-29T10:32:15.238Z by 10-scripts/nc5_five_step_photographs.mjs

⚠ THE IMAGES ARE THE THING (B14 rule 42). This file is an index to them.
⚠ Nothing was committed: the Create button was never pressed, and the walk ran
  against an ISOLATED CLONE of the demo database, not the demo database.

IMAGES — name · pixel dimensions · bytes · what state it shows
  step1-customer-1440.png   1440x2621   199671 bytes
      filled as a clerk would — Marisol Vandergriff, person, Residential/Permanent, SSN + driver's license, a co-applicant OPEN with its nine fields, mailing address ticked Same as service address, prefix NC, an external reference, mode Our crew did it
  step1-customer-1280.png   1280x2621   199696 bytes
      filled as a clerk would — Marisol Vandergriff, person, Residential/Permanent, SSN + driver's license, a co-applicant OPEN with its nine fields, mailing address ticked Same as service address, prefix NC, an external reference, mode Our crew did it
  step2-premise-1440.png   1440x1824   159197 bytes
      filled — Copperleaf Terrace Apartments, Bldg A, Austin TX 78704, parcel, read route RT-001, lat/lng typed, scope A new premise, BOTH services this utility sells chosen (electric, water), plan Industrial. The plan covers only electric, so the screen shows the real WON'T COVER refusal — which is the state step2-premise.png itself draws
  step2-premise-1280.png   1280x1824   157446 bytes
      filled — Copperleaf Terrace Apartments, Bldg A, Austin TX 78704, parcel, read route RT-001, lat/lng typed, scope A new premise, BOTH services this utility sells chosen (electric, water), plan Industrial. The plan covers only electric, so the screen shows the real WON'T COVER refusal — which is the state step2-premise.png itself draws
  step3-units-1440.png   1440x1664   137485 bytes
      REAL DATA — 6 units (NC 1..NC 6), 2 services each, tiles reading SERVICES HERE 2 of 2 · SERVICE POINTS 12 · METERS TO FIT 12 · WORK ORDERS 0 will be written. The first unit group is open, the other five folded
  step3-units-1280.png   1280x1690   136206 bytes
      REAL DATA — 6 units (NC 1..NC 6), 2 services each, tiles reading SERVICES HERE 2 of 2 · SERVICE POINTS 12 · METERS TO FIT 12 · WORK ORDERS 0 will be written. The first unit group is open, the other five folded
  step3a-add-row-1440.png   1440x1717   141047 bytes
      after one press of + Add row — the new row is added IN PLACE, no dialog
  step3b-add-work-order-1440.png   1440x1717   141042 bytes
      after + Add work order — the template search opens in place at the bottom of the table, no dialog
  step4-charges-1440.png   1440x1240   131053 bytes
      filled — owner's account, 30-day terms, posting date, Check 4471 for $250.00, and ONE real priced charge line: AFTER-HRS · After-hours service call, per unit, Qty 6, $75.00 each, $450.00
  step4-charges-1280.png   1280x1240   129877 bytes
      filled — owner's account, 30-day terms, posting date, Check 4471 for $250.00, and ONE real priced charge line: AFTER-HRS · After-hours service call, per unit, Qty 6, $75.00 each, $450.00
  step5-review-1440.png   1440x2833   256385 bytes
      the review of everything above, all four groups FOLDED as the wizard opens them
  step5-review-1280.png   1280x2867   256883 bytes
      the review of everything above, all four groups FOLDED as the wizard opens them
  step5-review-group-open-1440.png   1440x3104   270051 bytes
      the same screen with Charges and payment opened, which is the state step5-review.png draws

⚠ THE DIMENSIONS ARE PRINTED BECAUSE fullPage:true DOES NOT WORK ON THIS FRAME.
  `.app-shell` is height:100vh;overflow:hidden and `.view` is the scrolling pane
  inside it, so the document never grows and fullPage returns the fold. Each shot
  here grew the VIEWPORT to `.view`'s own scroll height. Two shots with the same
  height AND the same byte count would be the bug this note exists to expose.

CHECKED OBSERVATIONS — the deliverable as much as the images are
  PASS  step 1 · the drawn H1 — Who is asking, and what for?
  PASS  step 1 · the rail has FIVE cells — saw 5: Customer | Premise | Units | Charges | Review
  PASS  step 1 · the rail reads Customer · Premise · Units · Charges · Review, one word each — Customer | Premise | Units | Charges | Review
  PASS  step 1 · the sub-line reads "Step 1 of 5" — Step 1 of 5 · Customer
  PASS  step 1 · the sub-line names the step "Customer" — Step 1 of 5 · Customer
  PASS  step 1 · the last rail cell is inside the rail — 0px past the rail's right edge
  PASS  step 1 · the rail's right edge lines up with the panels — rail ends 0px short of the first panel
  PASS  step 1 · B14 rule 31 — no uuid is visible on the screen
  PASS  step 1 · no unresolved catalogue key on the screen
  PASS  step 1 · no sideways page scroll — 0px
  PASS  step 1 · B14 rule 31 — no uuid is visible on the screen
  PASS  step 1 · no unresolved catalogue key on the screen
  PASS  step 1 · no sideways page scroll — 0px
  PASS  step 2 · the drawn H1 — The premise
  PASS  step 2 · the rail has FIVE cells — saw 5: Customer | Premise | Units | Charges | Review
  PASS  step 2 · the rail reads Customer · Premise · Units · Charges · Review, one word each — Customer | Premise | Units | Charges | Review
  PASS  step 2 · the sub-line reads "Step 2 of 5" — Step 2 of 5 · Premise
  PASS  step 2 · the sub-line names the step "Premise" — Step 2 of 5 · Premise
  PASS  step 2 · the last rail cell is inside the rail — 0px past the rail's right edge
  PASS  step 2 · the rail's right edge lines up with the panels — rail ends 0px short of the first panel
  PASS  step 2 · the services control offered this utility's own services — 2: electric, water
  PASS  step 2 · a published plan could be chosen — 01a0e915-fbc7-79bd-a77d-2f336f392193
  PASS  step 2 · B14 rule 31 — no uuid is visible on the screen
  PASS  step 2 · no unresolved catalogue key on the screen
  PASS  step 2 · no sideways page scroll — 0px
  PASS  step 3 · the drawn H1 — The units
  PASS  step 3 · the rail has FIVE cells — saw 5: Customer | Premise | Units | Charges | Review
  PASS  step 3 · the rail reads Customer · Premise · Units · Charges · Review, one word each — Customer | Premise | Units | Charges | Review
  PASS  step 3 · the sub-line reads "Step 3 of 5" — Step 3 of 5 · Units
  PASS  step 3 · the sub-line names the step "Units" — Step 3 of 5 · Units
  PASS  step 3 · the last rail cell is inside the rail — 0px past the rail's right edge
  PASS  step 3 · the rail's right edge lines up with the panels — rail ends 0px short of the first panel
  PASS  step 3 · the eight ruled columns, in the drawn order — UNIT · KIND · SERVICE · ASSET · SIZE · WORK ORDER · COMPLETES · OCCUPANCY
  PASS  step 3 · UNIT · KIND · COMPLETES · OCCUPANCY are present (the absorbed fold, not drift) — UNIT · KIND · SERVICE · ASSET · SIZE · WORK ORDER · COMPLETES · OCCUPANCY
  PASS  step 3 · NO Qty column — OQ-CUS-12770 is OPEN and must not be built — UNIT · KIND · SERVICE · ASSET · SIZE · WORK ORDER · COMPLETES · OCCUPANCY
  PASS  step 3 · the table has real rows — 2 service rows
  NOTE  the four tiles read: SERVICES HERE = 2 of 2 · SERVICE POINTS = 12 · METERS TO FIT = 12 · WORK ORDERS = 0 will be written
  PASS  step 3 carries the unit range (old step 3 · Units)
  PASS  step 3 carries the per-unit service rows (old step 4 · Map services)
  PASS  step 3 carries the work orders (old step 5 · Plans & work orders)
  PASS  step 3 carries the work-order proposals
  PASS  step 3 · B14 rule 31 — no uuid is visible on the screen
  PASS  step 3 · no unresolved catalogue key on the screen
  PASS  step 3 · no sideways page scroll — 0px
  PASS  step 3 · + Add row adds a row IN PLACE — 2 → 3
  PASS  step 3 · + Add row opens NO dialog (the drawing says so in words)
  PASS  step 3 · + Add work order reaches a template search in place
  PASS  step 3 · + Add work order opens NO dialog
  PASS  step 4 · the drawn H1 — Charges
  PASS  step 4 · the rail has FIVE cells — saw 5: Customer | Premise | Units | Charges | Review
  PASS  step 4 · the rail reads Customer · Premise · Units · Charges · Review, one word each — Customer | Premise | Units | Charges | Review
  PASS  step 4 · the sub-line reads "Step 4 of 5" — Step 4 of 5 · Charges
  PASS  step 4 · the sub-line names the step "Charges" — Step 4 of 5 · Charges
  PASS  step 4 · the last rail cell is inside the rail — 0px past the rail's right edge
  PASS  step 4 · the rail's right edge lines up with the panels — rail ends 0px short of the first panel
  NOTE  step 4 · a charge row was added; 18 charge codes offered
  NOTE  step 4 · a Qty column IS on the screen (present) — reported to the PO, not treated as drift
  PASS  step 4 · Qty is NOT an editable box — OQ-CUS-12770 is OPEN and it multiplies a price — 0 editable Qty inputs
  PASS  step 4 · the What-is-charged table rendered its columns — CHARGE · BASIS · QTY · EACH · AMOUNT
  NOTE  step 4 · What is charged columns: CHARGE · BASIS · QTY · EACH · AMOUNT
  NOTE  step 4 money on screen: $75.00 | $450.00 | Total
$450.00PRICED, NOT POSTED
  PASS  step 4 · B14 rule 31 — no uuid is visible on the screen
  PASS  step 4 · no unresolved catalogue key on the screen
  PASS  step 4 · no sideways page scroll — 0px
  PASS  step 5 · the drawn H1 — What will be created
  PASS  step 5 · the rail has FIVE cells — saw 5: Customer | Premise | Units | Charges | Review
  PASS  step 5 · the rail reads Customer · Premise · Units · Charges · Review, one word each — Customer | Premise | Units | Charges | Review
  PASS  step 5 · the sub-line reads "Step 5 of 5" — Step 5 of 5 · Review
  PASS  step 5 · the sub-line names the step "Review" — Step 5 of 5 · Review
  PASS  step 5 · the last rail cell is inside the rail — 0px past the rail's right edge
  PASS  step 5 · the rail's right edge lines up with the panels — rail ends 0px short of the first panel
  PASS  step 5 carries the messages table (old step 7)
  PASS  step 5 carries the four-group review read-back — 4 groups: Customer · Marisol Vandergriff · A new premise | Premise · 103121 Copperleaf Terrace | Units and work · 6 · 12 | Charges and payment · $450.00PRICED, NOT POSTED · $250.00PRICED, NOT POSTED
  PASS  step 5 carries the At-a-glance tiles
  PASS  step 5 carries the What-Create-makes table
  FAIL  step 5 shows the Messages table ONCE — 2 copies of [data-telling]
  FAIL  step 5 shows the "Who we are telling" heading ONCE — 2 copies
  PASS  step 5 · B14 rule 31 — no uuid is visible on the screen
  PASS  step 5 · no unresolved catalogue key on the screen
  PASS  step 5 · no sideways page scroll — 0px
  PASS  step 5 · a review group opens in place to its own fields — 1 groups open
  FAIL  step 5 · the opened charges group shows EACH and AMOUNT, as drawn — CHARGE · BASIS · QTY
  FAIL  step 1 · "Account details" is not a heading over nothing — heading rendered with NO fields under it — text is "Account details"
  NOTE  the commit button was NOT pressed — this run photographs, it does not write

4 failed

THE FAILURES ARE FILED, NOT FIXED — this lane photographs and reports:
  DEF-CUS-7910  step 5 renders 'Who we are telling' and Messages TWICE
  DEF-CUS-7911  step 5's review charges table drops EACH and AMOUNT
  DEF-CUS-7912  step 1's 'Account details' heading renders over nothing
  DEF-CUS-7913  cr150's walkthrough §4 asks for three attributes that do not exist

The drawing-by-drawing comparison is DIVERGENCES-steps-4-5.md beside this file.
