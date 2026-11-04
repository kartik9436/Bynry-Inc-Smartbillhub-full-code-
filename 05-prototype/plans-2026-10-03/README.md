# Plans — the 44 images the screens are built FROM (2026-10-03)

Source: the PO-approved mock-up, artifact `GYbqQEdpgxKZCm9Mp3MY3d` (Version 10, plus the PO's last two changes: *Try a bill* removed and *Move units to another plan* taken out). It is kept here as `plans-mockup.html`, which is built on the taxes & fees mock-up as its template.
Desktop only, 1440 wide, full page. The grey demo bar and the "What this design fixes" table are hidden because they are not part of the product.

**STATUS: GO — BUILDING (PO 2026-10-03, *"GO: build the plans redesign now."*), as `CR-167-BRC10`.** It read *"DRAWING APPROVED — NOT A GO TO BUILD"* until that ruling (decision log 2026-10-03, *"GO ON THE PLANS REDESIGN"*). Move units to another plan stays *not now*.

**How to use:**
- Build each screen from its IMAGES (B14 rule 42). PO: *"I want all screens to be created using Images in drawing and not text/content"*. The HTML and this index are an index, never the specification.
- The images decide WHAT is on the screen and HOW it is arranged. Our UI standard decides spacing, sizes, type scale, tokens and components every time (B14 rule 44). Every selection table is the kit `TableArray` (`07-frontend/src/components/TableArray.tsx`, reference `05-prototype/new-connect-redesign-2026-09-28/step4-charges.png`).
- Every figure in an image is an ILLUSTRATION (B14 rule 37). Real figures come from the data.
- An open native dropdown cannot be photographed. Its choices are the ones in the mock-up's data (`SVC`, `SCHED`, `CHPRICE`, `TAXES`, `DISCS`, `DEPS`, `CLASSES`).
- **Superseded inside the images, and the later ruling wins:** none. The two late removals were made before the images were taken.
- Before go-live, photograph the built screen in the same 44 states and compare them side by side (the walk below).

## Every PO ruling on this redesign (2026-10-03, verbatim)
| # | PO said | What the drawing does |
|---|---|---|
| 1 | *"dont start the work on plan … we have to reduce 3 of steps in plan create"* | 8 steps become 5 one-word steps: **Details · Services · Charges · Billing · Review**. Edit uses the same form, with three "What to change" cards: **Name and details** (same version), **Change from a date** (new version), **Fix a mistake** (same dates, with a reason). |
| 2 | *"i dont want to loose any details from Create, edit or list or view"* | Every input in today's 8 steps has a home: Details = basics + classes + intended-for + eligibility notes; Services = services + rate schedule per service + surcharge; Charges = charge codes + taxes; Billing = deposits + discounts + budget billing + minimum bill; Review = dates + publish. The details tabs are **Overview · Services · Charges · Billing · Units · Audit** — Units, not Accounts, because a plan attaches to units. |
| 3 | *"in create we use Table array for selections, at many palces we want to keep that behaviou"* | Services, charge codes, taxes, discounts, deposits and notes are each a table array. |
| 4 | *"Customer classes * - Drop down - all or multiple selections"* | One tick dropdown, with "Every customer class" first. |
| 5 | Intended for: *"B Keep both exactly as today (reminders only)"* | The three ticks AND the notes stay. They are reminders only and never enforced. |
| 6 | *"unable to add utility services … this table UI should imporve Drop down size add behaviour etc - it should be table array"* | Full-size controls in the row, a red × to remove, "+ Add …" under the table, disabled with "All added." when nothing is left. An empty row is refused by name. |
| 7 | *"Why dont we show base charges and code with rate schedule itself … base and minimum from rate schedule - update step 2"* | The step-2 service row shows the base ($ and base code) and the minimum from the picked schedule, with the monthly base total under the table. There is no base section on Charges. |
| 8 | *"on rate schedules, Base charges, charge codes, discounts, tax - on all show version and effective date"* | Every referenced item shows a version pill and "from MM/DD/YYYY" in the form rows, on Review and on the details tabs. |
| 9 | *"base code based on sizes, rate schedule based on sizes or tiered or charges based on customer class or sizes, we did not add dposites anywhere … table format … improve how it will be displayed at review"* | Review is tables: plan facts; per service, the base and minimum by size and the usage blocks or per-size rates; charge codes by class or size; taxes; **deposits** by class or size (a new table array on Billing); discounts; billing terms. |
| 10 | *"on last page of review youa re not giving publish plan option"* | Review ends with **Save as draft** and **Publish plan**. When editing, these are **Save new version** and **Publish new version**. |
| 11 | *"similar to review page of add plan - in details view this service field does not help - how you will align this"* | The details Services, Charges and Billing tabs render the SAME sections as Review. **Build note: one shared component for both.** |
| 12 | *"can we use base charges and usage charges vocabalary - to keep in line with rate schedule"* | "Base charges" and "Usage charges" everywhere, including "Monthly base charges". |
| 13 | *"update teh artifact - How I'd improve the plan details page"* | Every name is a link. Services fold to one line, with Expand all. A banner names an upcoming version. "Priced as of" a date. Tiles open their tab. A section's Edit opens that step. The header is sticky. The tab is kept in the address. Units has search, an occupancy filter and CSV. Audit has filters and rows that open to before → after. Arrow keys move between tabs. |
| 14 | *"remove Try a bill"* | Removed. |
| 15 | Move units to another plan: *"not now"* | Taken out: no selection column and no Move button on Units. It is a later item. |

## Checks to do before building (not ruled; ours to verify against the code)
- BASE-S and BASE-FIRE show both under base and in the charge-code list today. Check whether they are counted twice on a bill.
- A residential plan's water base shows "8.00 · 10.00 · 8.00 from BASE-W · BASE-W1 · BASE-W-COM · BASE-W-FIRE". Find out why four base codes resolve.
- The view lists LATE as a charge code, while edit step 4 lists BASE-FIRE and BASE-S.
- Defects already filed from today's screens: DEF-RAT-9285 (database id on eligibility), 9286 (review counts contradict), 9287 (minimum bill shown as 10.000000), 9288 (audit shows raw ids and JSON).

## Removed from the details page (text, not data — the PO asked to lose no DETAIL)
Revenue tile, Exceptions tile, the "Not recorded on a plan yet" list (7 items), *How a plan works*, *Sample bill*, "Splitting by city limits…", the draft-schedule note, the softer-state note, "Why units and not accounts".

## The work, once the PO says go (10 tasks; same pattern as `CR-165-BRC10` taxes and `CR-166-BRC10` discounts)
| # | Task |
|---|---|
| 1 | Drawing images — **done, this folder** |
| 2 | Contract and record: a CR with the field map (every today-input → its new home), the server's answers (plan versions, deposits on a plan, item version + from-date on every reference), and the checks above |
| 3 | Back end: deposits on a plan; version + from-date on each referenced item; "as of" pricing read; one plan version per date for billing |
| 4 | Shared plan-sections component (Review = details tabs) |
| 5 | New-plan form, 5 steps, table arrays |
| 6 | List |
| 7 | Details page, six tabs and the improvements in ruling 13 |
| 8 | Edit — three choices with their Review |
| 9 | Eleven languages |
| 10 | Full web walk (`web-walk.md`), photographs against these images, then close |

## The images
| # | File | State |
|---|---|---|
| 1 | [01-list-all.png](images/01-list-all.png) | List · all plans |
| 2 | [02-list-search.png](images/02-list-search.png) | List · searched “water” |
| 3 | [03-list-no-results.png](images/03-list-no-results.png) | List · search with no results |
| 4 | [04-new-1-details-empty.png](images/04-new-1-details-empty.png) | New · step 1 Details · empty |
| 5 | [05-new-1-details-errors.png](images/05-new-1-details-errors.png) | New · step 1 · Continue on empty: each missing box named |
| 6 | [06-new-1-classes-dropdown.png](images/06-new-1-classes-dropdown.png) | New · step 1 · Customer classes dropdown (Every customer class first) |
| 7 | [07-new-1-details-filled.png](images/07-new-1-details-filled.png) | New · step 1 Details · filled (classes, intended-for ticks, notes) |
| 8 | [08-new-2-services-filled.png](images/08-new-2-services-filled.png) | New · step 2 Services · table array with schedule, base, minimum per row |
| 9 | [09-new-2-services-row-added.png](images/09-new-2-services-row-added.png) | New · step 2 · empty row added |
| 10 | [10-new-2-services-row-error.png](images/10-new-2-services-row-error.png) | New · step 2 · empty row refused by name |
| 11 | [11-new-2-services-all-added.png](images/11-new-2-services-all-added.png) | New · step 2 · fire picked; + Add disabled, “All added.” |
| 12 | [12-new-2-surcharge-on.png](images/12-new-2-surcharge-on.png) | New · step 2 · outside-city surcharge on; Surcharge tick per row |
| 13 | [13-new-3-charges-filled.png](images/13-new-3-charges-filled.png) | New · step 3 Charges · charge codes and taxes, version and from-date |
| 14 | [14-new-3-tax-added.png](images/14-new-3-tax-added.png) | New · step 3 · tax row added |
| 15 | [15-new-3-charges-error.png](images/15-new-3-charges-error.png) | New · step 3 · empty charge-code row refused |
| 16 | [16-new-3-row-removed.png](images/16-new-3-row-removed.png) | New · step 3 · empty row removed with × |
| 17 | [17-new-4-billing-filled.png](images/17-new-4-billing-filled.png) | New · step 4 Billing · deposits, discounts, budget billing, minimum bill |
| 18 | [18-new-4-discount-added.png](images/18-new-4-discount-added.png) | New · step 4 · discount row added with offered from/until |
| 19 | [19-new-4-billing-error.png](images/19-new-4-billing-error.png) | New · step 4 · empty deposit row refused |
| 20 | [20-new-5-review-top.png](images/20-new-5-review-top.png) | New · step 5 Review · plan facts and price tables |
| 21 | [21-new-5-review.png](images/21-new-5-review.png) | New · step 5 Review · full page ending in Save as draft / Publish plan |
| 22 | [22-new-6-published.png](images/22-new-6-published.png) | New · published |
| 23 | [23-new-6-saved-draft.png](images/23-new-6-saved-draft.png) | New · saved as a draft (Save as draft) |
| 24 | [24-detail-overview.png](images/24-detail-overview.png) | Details · Overview (tiles open tabs, upcoming-change banner, intended-for) |
| 25 | [25-detail-more.png](images/25-detail-more.png) | Details · More ▾ (Duplicate, Retire) |
| 26 | [26-detail-services-folded.png](images/26-detail-services-folded.png) | Details · Services · each service folded to one line |
| 27 | [27-detail-services-open.png](images/27-detail-services-open.png) | Details · Services · Expand all (base and minimum by size, usage blocks) |
| 28 | [28-detail-services-asof-2027.png](images/28-detail-services-asof-2027.png) | Details · Services · Priced as of 01/15/2027 (water v5) |
| 29 | [29-detail-charges.png](images/29-detail-charges.png) | Details · Charges · charge codes by class/size, taxes |
| 30 | [30-detail-billing.png](images/30-detail-billing.png) | Details · Billing · deposits, discounts, billing terms |
| 31 | [31-detail-units.png](images/31-detail-units.png) | Details · Units · search, occupancy filter, CSV |
| 32 | [32-detail-units-search.png](images/32-detail-units-search.png) | Details · Units · searched |
| 33 | [33-detail-units-vacant.png](images/33-detail-units-vacant.png) | Details · Units · Vacant only |
| 34 | [34-detail-audit.png](images/34-detail-audit.png) | Details · Audit · all changes |
| 35 | [35-detail-audit-underneath.png](images/35-detail-audit-underneath.png) | Details · Audit · Changes underneath |
| 36 | [36-detail-audit-open.png](images/36-detail-audit-open.png) | Details · Audit · row opened to before → after |
| 37 | [37-detail-section-edit.png](images/37-detail-section-edit.png) | Details · section Edit opens that step of the form |
| 38 | [38-edit-info-1.png](images/38-edit-info-1.png) | Edit · Name and details · step Details |
| 39 | [39-edit-info-review.png](images/39-edit-info-review.png) | Edit · Name and details · Review (same version) |
| 40 | [40-edit-change-1.png](images/40-edit-change-1.png) | Edit · Change from a date · first step |
| 41 | [41-edit-change-review.png](images/41-edit-change-review.png) | Edit · Change from a date · Review (v1 ends, v2 new; units move) |
| 42 | [42-edit-change-published.png](images/42-edit-change-published.png) | Edit · Change from a date · new version published |
| 43 | [43-edit-correct-1.png](images/43-edit-correct-1.png) | Edit · Fix a mistake · first step |
| 44 | [44-edit-correct-review.png](images/44-edit-correct-review.png) | Edit · Fix a mistake · Review (same dates, reason) |
