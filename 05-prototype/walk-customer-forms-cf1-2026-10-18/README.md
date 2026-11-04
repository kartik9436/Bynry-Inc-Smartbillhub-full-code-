# Walk — one customer form on Move-in, the service request and New connect (lane CF-1, 2026-10-18)

Built from the drawing set `04-docs/05-modules/03-customers/wireframes/customer-forms-2026-10-18/` (images 01, 02, 03, 06, 10, 11). Walked in Chromium at 1440 px wide on a private copy of the database (`smartbillhub_cf1`, dropped afterwards), backend on 8032, the built app on 8112. Script: `10-scripts/walk_customer_forms_cf1_2026_10_18.mjs` (`STEP=request | requestBusiness | movein | moveinComplete | newconnect | newconnectCreate | search`).

**Data set up on the copy first:** three customers named Maria Lopez (C-90412 with SSN 123-45-4471, DOB 04/12/1988, an account owing $247.30; C-90978 same DOB, other phone; C-91203 no DOB, same phone). Requests SR-26-0026 (approved, move-in) and SR-26-0009 (approved, new connection) given every CF-1 field: Contact by *text*, government ID 9001, co-applicant card Daniel Lopez (spouse, responsible for bills, SSN 987-65-2208), mailing PO Box 2210, Ypsilanti MI 48197, paperless and text reminders on. SR-26-0026 also given a phone, an SSN 555-11-2233 and a licence.

## What was checked, and what the database held afterwards

| # | Screen | Drawing | Result |
|---|---|---|---|
| A | Service request, step 1 — every field filled, Continue | 03 | Saved as SR-26-0062 and read back: name, email, phone, DOB 1988-04-12, Contact by *text*, government ID 9001, SSN ••4471, licence ••8903, the co-applicant card whole (relationship, bills, phone, email, DOB, SSN ••2208), mailing PO Box 2210 / Ypsilanti / MI / 48197, paperless and text on. `request-step1-filled.png` |
| A2 | Service request — a business | 03 | Tax ID 47-1234567 saved; the read shows ••4567 (`DEF-CUS-10223`). `request-business-step1.png` |
| B | Move-in from SR-26-0026 | 01 | Opened with Contact by, government ID 9001, the co-owner card, the mailing address and both preferences filled. Completed as MVI-26-0020; account AC-2026-00057 holds: customer C-00055 with SSN ••2233 and licence (carried by the server), contact *text* / 9001, mailing PO Box 2210 Ypsilanti MI 48197, co-owner Daniel Lopez (spouse, bills, DOB 1986-09-30, SSN ••2208), paperless and text on. `movein-from-request-customer-step.png`, `movein-review-step.png`, `movein-completed.png` |
| C | New connect from SR-26-0009 (CON-26-0002) | 06, 02 | Owner step opened with every request answer filled. Created with the mailing address unticked, the co-owner card kept, tax exempt EX-55-90211 to 01/04/2029, preferences set. Account AC-2026-00058: mailing PO Box 2210 Ypsilanti MI 48197 (`DEF-CUS-10222`), contact *text* / 9001, co-owner Daniel Lopez with SSN ••2208 (carried by name), tax exempt EX-55-90211 expiring 2029-01-04, paperless and text on. `newconnect-owner-step.png`, `newconnect-charges-step.png`, `newconnect-review-step.png`, `newconnect-done.png` |
| D | Search customer ID (New connect owner step) | 10, 11 | **Two** rows, not three: C-90412 *Existing customer* (owes $247.30, 1 of 1 open) and C-90978 *Possible match*. C-91203 (name + phone only) was not offered — the server's candidate search did not pick it up from a phone set directly on the copy; the rule itself is unchanged by this lane. Accounts row opens; Link collapses to the one-line *Linked* state. `search-three-matches.png`, `search-accounts-open.png`, `search-linked.png` |

## Second walk — Move-in's full Tax and Discounts panels on New connect (same day)

Fresh copy of the database; data set up first: an exemption type *Religious organisation* on each of the tenant's two taxes, and request SR-26-0014 given a co-applicant card (Daniel Walker, SSN 987-65-2208), Contact by and government ID.

| # | Screen | Drawing | Result |
|---|---|---|---|
| E | New connect owner step from SR-26-0008 | 06 | The co-owner card's summary reads `Spouse · (281) 555-0144 · Responsible for bills · •••-••-2208`: the ID the server carries, not *No ID* (`DEF-CUS-10232`). `newconnect-owner-step-coowner-mask.png` |
| F | New connect from SR-26-0014 (CON-26-0003), plan *Sample — Residential*, owner-occupier | 02 | Charges step: Claim discounts → *Paperless billing* ($1.00); Tax exempt → *Religious organisation*, certificate EX-55-90211, issued 01/05/2026, expires 01/04/2029, file exempt-cert.pdf. Created. Account AC-2026-00058: rating's certificate row (Religious organisation, EX-55-90211, 2026-01-05 → 2029-01-04), the file filed in KYC (`AC-2026-00058-exempt-cert.pdf`), a PAPERLESS enrolment and paperless switched on, the blanket exemption columns unset, co-owner Daniel Walker with SSN ••2208 (`DEF-CUS-10233`). Repeated on CON-26-0002 after the dates became the utility's date picker: AC-2026-00059, the same rows. `newconnect-charges-tax-discount.png`, `newconnect-done-tax-discount.png` |

What it showed on the way: a build whose owner is a builder or landlord opens a billing-only account with no home, which carries no plan, so a discount claim on it is refused (*discount not offered*) — Move-in's own rule. The discount list offers every discount on the chosen plan (Autopay, Municipal account, Paperless billing); one no person may add (Municipal account) is refused at Create, not hidden. Claiming *Paperless billing* switches paperless on at the server; the Preferences panel on the screen does not tick itself the way Move-in's does (the plan read serves no `pairs_with`).

## Built vs drawing — differences left on purpose

- **Service request:** the *Channel* select stays under the Who panel (BR-CUS-091 makes *staff collections* the thing that lets a request carry no name). The co-applicant card shows *Contact by* where the drawing shows *Photo ID* (a request has nowhere to file a photo). *More about the customer* is drawn only when the utility placed a field on that screen; the walk tenant has none there.
- **New connect:** *Owner type* stays under the Who panel (it decides whether the owner holds a single-family home); the *Becomes a customer* badge stays; the licence keeps Show/Hide (PO ruling Q4). Reference and Work panels stay below the drawn ones. The Tax and Discounts panels are Move-in's own (second walk). Move-in's Fees table is not on the charges step — the existing charges table, payer and payment panels stay.
- **Every screen:** the mailing address uses the product's US address block (street on its own row, then apt, then city / state / ZIP) where the drawing puts three across.
- **The wizard's own steps, titles and footers** are unchanged (request: Applicant · Property · Service · Review).
