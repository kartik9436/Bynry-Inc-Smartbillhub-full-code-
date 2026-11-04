# Taxes & fees — the 33 images the screens are built FROM (2026-10-03)

Source: the PO-reviewed mock-up, artifact `Gv7YJoQbydd1aj42te9cRk` Version 8, kept here as `taxes-fees-mockup.html`.
Desktop only, 1440 wide, full page. **No phone layout is drawn or required (PO 2026-10-03: *"phone edit will not required; this si desktop version"*).** The mock-up's grey demo bar and its "What this design fixes" table are hidden; they are not part of the product.

**How to use (PO ruling 2026-10-03, decision log *"GO ON THE TAXES & FEES REDESIGN"*):** *"I want all screens to be created using Images in drawing and not text/content"*.
- Build each screen from its IMAGES (B14 rule 42). The HTML and this index are an index, never the specification.
- The images decide WHAT is on the screen and HOW it is arranged; our UI standard decides spacing, sizes, type scale, tokens and components, every time (B14 rule 44).
- Every figure in an image is an ILLUSTRATION (B14 rule 37). Real figures come from the data.
- **Superseded inside the images, and the later ruling wins:**
  - Images 01–03 (list): the All / Active / Draft / Ended **buttons** are superseded. PO 2026-10-03, verbatim: *"on list view of Tax - ensure you ahve filter and not button for filters- follow our toolkkit standard"*. The list uses the shared kit's table toolbar (B14 rule 12: Search · filter chips · + Filter ▾ · Columns), with Status as one of the filters.
  - Images 04 and 07: the boundary choices **"Outside city limits" and "A named place" are superseded**, and the Place name box is not built. PO 2026-10-03: *"Only what works today. An outside-city charge stays on the plan. - this is correct"*. The form offers only the boundaries billing applies today. If a later PO ruling moves something drawn here, stamp it in this list, never by editing an image.
- Before go-live, photograph the built screen in the same 33 states and compare side by side (task 9).

| # | File | State |
|---|---|---|
| 1 | `images/01-list-all.png` | List · All |
| 2 | `images/02-list-active.png` | List · filter Active |
| 3 | `images/03-list-no-results.png` | List · search with no results |
| 4 | `images/04-new-1-what-filled.png` | New · step 1 What it is · filled in |
| 5 | `images/05-new-1-services-open.png` | New · step 1 · Services dropdown open (only active services, All first) |
| 6 | `images/06-new-1-classes-open.png` | New · step 1 · Customer classes dropdown open |
| 7 | `images/07-new-1-named-place.png` | New · step 1 · Boundary = a named place (Place name appears) |
| 8 | `images/08-new-1-errors.png` | New · step 1 · empty, Continue pressed (errors on each box) |
| 9 | `images/09-new-2-how-filled.png` | New · step 2 How much · filled in |
| 10 | `images/10-new-2-rate-warning.png` | New · step 2 · rate 62.5% (over-20% warning) |
| 11 | `images/11-new-2-errors.png` | New · step 2 · rate empty, Continue pressed |
| 12 | `images/12-new-2-fixed-amount.png` | New · step 2 · charged as a fixed amount per bill |
| 13 | `images/13-new-3-filing-filled.png` | New · step 3 Filing · filled in |
| 14 | `images/14-new-3-filing-errors.png` | New · step 3 Filing · liability account missing, bad email |
| 15 | `images/15-new-4-review.png` | New · step 4 Review & save |
| 16 | `images/16-new-4-review-rate-warning.png` | New · step 4 Review · rate typed as 62.5 (warning) |
| 17 | `images/17-new-5-saved.png` | New · saved |
| 18 | `images/18-detail-overview-over20.png` | Details · ann arbor City · Overview (Over 20%, Fix the rate) |
| 19 | `images/19-detail-plans.png` | Details · Plans tab |
| 20 | `images/20-detail-audit.png` | Details · Audit tab |
| 21 | `images/21-detail-more-menu.png` | Details · More ▾ open (Duplicate, Retire) |
| 22 | `images/22-detail-overview-scheduled.png` | Details · TX State Utility Tax · Overview (next rate scheduled) |
| 23 | `images/23-detail-overview-versions.png` | Details · Bexar County · Overview (three versions) |
| 24 | `images/24-edit-info-1-name.png` | Edit · Name and filing · step Name (rate and reach locked) |
| 25 | `images/25-edit-info-2-filing.png` | Edit · Name and filing · step Filing |
| 26 | `images/26-edit-info-3-review.png` | Edit · Name and filing · Review (before → after, same version) |
| 27 | `images/27-edit-saved.png` | Edit · saved |
| 28 | `images/28-edit-change-1-rate.png` | Edit · New rate from a date · step New rate |
| 29 | `images/29-edit-change-1-error.png` | Edit · New rate · start not after today's start |
| 30 | `images/30-edit-change-2-review.png` | Edit · New rate · Review (old ends day before, new version) |
| 31 | `images/31-edit-correct-1-fix.png` | Edit · Fix a mistake · step Fix the rate (dates locked, reason) |
| 32 | `images/32-edit-correct-1-error.png` | Edit · Fix a mistake · reason missing |
| 33 | `images/33-edit-correct-2-review.png` | Edit · Fix a mistake · Review (superseded, issued bills keep old rate) |

## What the PO ruled into this drawing (rounds 1–7, all 2026-10-02/03)
1. Services: only the services this utility has switched on, in one dropdown with "All services" first. Customer classes: one dropdown, "Every customer class" first.
2. Rate is typed and shown as a percent (6.25, not 0.0625); over 20% warns before saving and on Review.
3. Filing is taken during creation (step 3, *Filing*) and shown read-only on details. *Due* and *Account with the authority* are dropdowns; the accounts come from Settings › Accounting.
4. List: Version, From, To (separate), GL code in bold with its name under it, premises reached, an "over 20%" banner and pill.
5. Details: one Edit button top right plus More ▾ (Duplicate, Retire). No side panel anywhere.
6. Edit opens the SAME full-page form as New, with "What to change" first: *Name and filing* (same version, rate and reach locked) · *New rate from a date* (old version ends the day before) · *Fix a mistake* (same dates, reason required, old row superseded and kept). Review shows before → after, a $60.00 bill before → after, and the versions saved.
7. Rate history tab removed: Overview carries a small versions table, Audit carries every change with its reason. Tabs: Overview · Plans · Audit.
8. Header adds: version, code, Over 20%, *Filing due*, and the next scheduled rate change (only when one exists).
