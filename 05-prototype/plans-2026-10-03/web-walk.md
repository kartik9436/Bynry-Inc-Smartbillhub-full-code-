# Plans — the full web walk (task 10), as proposed to the PO 2026-10-03

Desktop only. Real app, real PostgreSQL 16, two utilities, clicking in a browser like a clerk. Every step gets a screenshot, opened and checked that it is not blank, and compared side by side with the matching image in `images/`. Every figure is the walk's own test data, not a signed rule. Every bug found is filed first, then fixed, then walked again. Anything touching ❄️ money math, a signed rule or RLS goes to the PO instead.

**Utility A** runs water, sewer, trash and fire, with 8 customer classes. Its rate schedules, charge codes, taxes, discounts and deposits come from the taxes and discounts walks. **Utility B** has no plans.

| Phase | What | Must be true |
|---|---|---|
| 1 | Create 4 plans: Residential (water, sewer, trash; surcharge on water and sewer), Commercial (water, sewer; class-priced late fee and deposit), Fire (6 sizes, counted), and a draft saved half way, then reopened and finished | Each list row shows version, from and to; **exactly one row in the database per plan**; only Utility A's services are offered |
| 2 | Each step left empty, then each table with an empty row | Each problem is named; nothing typed is lost; "All added." appears when nothing is left |
| 3 | Review for each plan | Base and minimum by size, usage blocks, charge codes and deposits by class or size, taxes, discounts — **every value entered in phase 1, exactly**, with each item's version and from-date |
| 4 | Open each plan's six tabs | Services, Charges and Billing match Review; links open the right pages; folding, Expand all, tiles, section Edit, the tab in the address and arrow keys all work |
| 5 | Give the water rate schedule a new version from 01/01/2027 | Banner on the plan; "Priced as of" 01/15/2027 shows the new rates; today still shows the old |
| 6 | Edit three ways: Name and details; Change from a date (01/01/2027); Fix a mistake (with a reason) | Same row and same version; v1 ends 12/31/2026 and v2 starts 01/01/2027, nothing deleted; corrected with the same dates and the old row kept. Audit shows each, before → after |
| 7 | Ask billing for the plan on 12/31/2026 and on 01/01/2027 | **One** plan version each, never both and never none |
| 8 | Bill run before and after 01/01/2027 | The December bill keeps the old figures and the January bill uses the new; deposit and base are not counted twice |
| 9 | Sign in to Utility B; switch through the other 10 languages | None of A's plans anywhere; no English left on these screens |
