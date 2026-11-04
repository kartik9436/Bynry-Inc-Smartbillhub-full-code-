# Discounts — the 36 images the screens are built FROM (2026-10-03)

Source: the PO-approved mock-up, artifact `JmwhY7nnzCWXjSkyGwHiLY` Version 6, kept here as `discounts-mockup.html`. Built on the taxes & fees mock-up as its template (PO: *"when you create HTML artifact use this as sample"*).
Desktop only, 1440 wide, full page. The grey demo bar and the "What this design fixes" table are hidden; they are not part of the product.

**How to use (PO ruling 2026-10-03, decision log *"GO ON THE DISCOUNTS REDESIGN"*):** *"i want images to be used to create prodict screens ; dont use text to create product screens"*.
- Build each screen from its IMAGES (B14 rule 42). The HTML and this index are an index, never the specification.
- The images decide WHAT is on the screen and HOW it is arranged; our UI standard decides spacing, sizes, type scale, tokens and components, every time (B14 rule 44).
- Every figure in an image is an ILLUSTRATION (B14 rule 37). Real figures come from the data.
- An open native dropdown cannot be photographed; its CHOICES are listed below and are part of the drawing.
- **Superseded inside the images, and the later ruling wins:** none yet.
- Before go-live, photograph the built screen in the same 36 states and compare side by side (task 9).

| # | File | State |
|---|---|---|
| 1 | `images/01-list-all.png` | List · All |
| 2 | `images/02-list-filter-menu.png` | List · + Filter ▾ open |
| 3 | `images/03-list-filter-chip.png` | List · Status: Active chip applied |
| 4 | `images/04-list-no-results.png` | List · search with no results |
| 5 | `images/05-new-1-details-pct.png` | New · step 1 Details · percentage, Limits closed |
| 6 | `images/06-new-1-limits-open.png` | New · step 1 · Limits open |
| 7 | `images/07-new-1-details-fixed.png` | New · step 1 · fixed amount, limits set (2 set) |
| 8 | `images/08-new-1-type-rate-override.png` | New · step 1 · type rate override |
| 9 | `images/09-new-1-type-charge-waiver.png` | New · step 1 · type charge waiver |
| 10 | `images/10-new-1-type-usage-allowance.png` | New · step 1 · type usage allowance |
| 11 | `images/11-new-1-applies-service.png` | New · step 1 · Applies to one service |
| 12 | `images/12-new-1-applies-codes.png` | New · step 1 · Applies to named charge codes |
| 13 | `images/13-new-1-errors.png` | New · step 1 · empty, Continue pressed |
| 14 | `images/14-new-1-value-over-100.png` | New · step 1 · percent over 100 refused |
| 15 | `images/15-new-2-eligibility.png` | New · step 2 Eligibility · filled in |
| 16 | `images/16-new-2-errors.png` | New · step 2 · who missing, end before start |
| 17 | `images/17-new-3-review.png` | New · step 3 Review |
| 18 | `images/18-new-4-saved.png` | New · saved as a draft |
| 19 | `images/19-detail-active-overview.png` | Details · Senior (Active, next value scheduled) · Overview |
| 20 | `images/20-detail-accounts.png` | Details · Accounts tab (12 receiving) |
| 21 | `images/21-detail-plans.png` | Details · Plans tab |
| 22 | `images/22-detail-audit.png` | Details · Audit tab |
| 23 | `images/23-detail-active-more.png` | Details · Active · More ▾ (Duplicate, Retire) |
| 24 | `images/24-detail-draft.png` | Details · Veteran (Draft) · Edit, Submit for approval |
| 25 | `images/25-detail-accounts-empty.png` | Details · Accounts tab · nobody receives it yet |
| 26 | `images/26-detail-waiting-approval.png` | Details · Lifeline (Waiting approval) · Send back, Approve |
| 27 | `images/27-edit-info-1-details.png` | Edit · Name and details · step Details (value and limits locked) |
| 28 | `images/28-edit-info-2-eligibility.png` | Edit · Name and details · step Eligibility (start locked) |
| 29 | `images/29-edit-info-3-review.png` | Edit · Name and details · Review (before → after, same version) |
| 30 | `images/30-edit-saved.png` | Edit · saved |
| 31 | `images/31-edit-change-1-value.png` | Edit · New value from a date · step New value |
| 32 | `images/32-edit-change-1-error.png` | Edit · New value · start not after today's start |
| 33 | `images/33-edit-change-2-review.png` | Edit · New value · Review (v1 ends the day before, v2 new) |
| 34 | `images/34-edit-correct-1-fix.png` | Edit · Fix a mistake · step Fix the value (dates locked, reason) |
| 35 | `images/35-edit-correct-1-error.png` | Edit · Fix a mistake · reason missing |
| 36 | `images/36-edit-correct-2-review.png` | Edit · Fix a mistake · Review (superseded and kept) |

## What the PO ruled into this drawing (2026-10-03)
1. Form: five steps become three, one word each — **Details · Eligibility · Review**; all 31 of today's boxes kept (map in the decision log). Limits is one section, closed by default, reading "No limits".
2. Currency is always the utility's own; shown, never changeable.
3. Dropdowns (values are the coordinator's, editable per utility in Settings): **Program owner** — Billing · Customer service · Finance · Conservation · Community programs · City or county agency · State agency · Nonprofit partner. **Exclusivity group** — None · Low-income programs · Age-based · Payment method (autopay, paperless) · Government and municipal · Military and veterans. **Who qualifies**, in two groups — *The system checks*: Everyone on the plan · Autopay is on · Paperless billing is on · Government or municipal account; *The customer shows proof*: Age 65 or over · Household income under a limit · In a state assistance program · Veteran or active military · Person with a disability · Medical equipment at home · Nonprofit or place of worship.
4. Enrollment has two choices only: Automatic · Apply and approve.
5. List: no paragraph; $ on fixed values; From and To; open instead of a pencil; the standard toolbar.
6. Details: header buttons follow the status (Draft: Edit · Submit for approval; Waiting approval: Send back · Approve; Active: Edit; More ▾ holds Duplicate, Delete draft, Retire); tabs **Overview · Accounts · Plans · Audit**; every entered value shown; Accounts lists who receives it.
7. Edit is the same full-page form: Name and details (same version; value, limits and start locked) · New value from a date (old version ends the day before) · Fix a mistake (same dates, reason required, old row kept).
8. Lifecycle (ruled as recommended): approved → live by itself on its start date; only accounts whose plan carries it can get it, and removal from a plan stops it from the next bill; Automatic enrolls every account on its plans meeting a *system checks* condition; Retire takes an end date after which nobody gets it.
