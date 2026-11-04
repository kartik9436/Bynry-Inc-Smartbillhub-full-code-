# Discounts — the full web walk (task 9), as agreed with the PO 2026-10-03

Desktop only. Real app, real PostgreSQL 16, two utilities (A runs water, sewer, trash, storm water; B has no discounts), clicking like a clerk. Every step gets a screenshot, opened and checked not blank. Example bill: **$60.00 before taxes**. Every figure is the walk's own test data, not a signed rule; where a figure depends on the engine's signed stacking/rounding rules, the engine's answer is checked against B4, never invented here. Every bug found is filed first, fixed and walked again; ❄️ money math, signed rules and RLS go to the PO.

## Step 1 — create one discount of every kind
| # | Discount | Type | Who qualifies | Enrollment | Limits | On the $60.00 bill |
|---|---|---|---|---|---|---|
| 1 | Senior discount | 15% off | Age 65 or over | Apply and approve, with proof | — | −$9.00 |
| 2 | CAP credit | $25.00 off | In a state assistance program | Apply and approve | Cap $300.00 a year · bill floor $50.00 | −$10.00 (the floor stops it at $50.00) |
| 3 | Autopay discount | 0.5% off | Autopay is on | Automatic | — | −$0.30 |
| 4 | Municipal account | 20% off | Government or municipal account | Automatic | Cap $5.00 per bill | −$5.00 (capped) |
| 5 | Lifeline water | $10.00 off, water only | Household income under a limit | Apply and approve | Same exclusivity group as CAP | −$10.00, never on the same bill as CAP |
| 6 | Lead line waiver | Charge waiver on named codes | Medical equipment at home | Apply and approve | — | the named charge removed |
| 7 | ~~Garden allowance~~ — **withdrawn 2026-10-03** (see the note below) | ~~Usage allowance, 2 kgal free~~ | — | — | — | not created: the New form no longer offers the type |
| 8 | A draft | — | — | — | — | Save draft & exit half way, reopen, finish |
Each: exactly one row in the database, in the list, saved as a draft.

⚠ **Dated note 2026-10-03 — Garden is withdrawn from the walk.** PO ruling (decision log 2026-10-03, option b, *"recommend (b) - this is correct"*): *Usage allowance* is not offered on the New discount form until free units come off the reading before pricing (`BR-RAT-962` unchanged). Built in **2.488.0**: the type is not in the form's list and the server refuses a new one. So row 7 is not created, step 5 puts no Garden on a plan, and step 9's check *"Garden suspends when the budget runs out"* is removed. A re-walk of step 1 checks instead that the *Type* list offers no *Usage allowance*.

## Steps 2–10
| Step | What I do | Must be true |
|---|---|---|
| 2 · Form checks | Continue empty; percent over 100; no who-qualifies; end before start | Each mistake named on its box; nothing typed lost; currency is the utility's and cannot be changed |
| 3 · View | Open each discount | All 31 values exactly as entered; buttons match the status |
| 4 · Going live | Submit → Approve (including self-approval); a budget above the threshold needing a second approver | Approved → live by itself on its start date (ruling 1); Audit shows who did each step |
| 5 · Plans and enrollment | Put Senior on a plan; enroll an account on it and one that is not; take it off the plan; Autopay/Municipal on their plans | The off-plan account is refused; after removal, no discount from the next bill (ruling 2); automatic discounts enroll every qualifying account on their plans (ruling 3) |
| 6 · Accounts tab | Enroll with proof pending, verify, end one enrollment | Tab, Overview "Receiving it" and "Granted", and the bill all agree |
| 7 · Edit, three ways | Name and details · Senior 15% → 12% from 01/01/2027 · fix a value typed 1.5 instead of 15, with a reason | Same row; v1 ends 12/31/2026 and v2 starts 01/01/2027, nothing deleted; the old row kept and marked replaced |
| 8 · Billing gets exactly one version | Ask billing for Senior on 12/31/2026 and 01/01/2027; run December and January bills | One version every time; December −$9.00, January −$7.20; the December bill keeps −$9.00 |
| 9 · Limits on real bills | Senior with Autopay; CAP with Lifeline; CAP over 13 months | Stacking order applied; CAP and Lifeline never both; CAP stops after $300.00 in the year (the Garden check was removed 2026-10-03 — note under step 1) |
| 10 · Retire | Retire Senior on a date | After that date nobody gets it, enrolled accounts included (ruling 4) |
| 11 · Isolation and languages | Utility B; the other 10 languages | B sees none of A's discounts on screen or from the server; no English left |

Evidence: screenshots `discwalk_<step>_<n>.png`, a pass/fail table in `08-qa/`, and every bug with where found, what the user saw, and which build fixed it.
