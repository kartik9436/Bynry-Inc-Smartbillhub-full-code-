# Walk — customer forms, lane CF-2 (2026-10-18)

What was walked: a customer applies on the portal with every field filled. Staff open the request, set the category, approve it, and finish the move-in it opens. Then staff check the new account, open the edit dialogs, and sell a different account to a buyer with a tax exemption and a discount.

**Where:** a private copy of the database (`smartbillhub_cf2`), API on port 8033, screens on port 8113, built from this branch (version shown on screen: 2.586.0). Tenant *Brazos Bend Utilities*, signed in as Dana Whitfield. The scripts that drove the browser are in the lane's scratchpad (`cf2_walk_*.mjs`); the text each one read off the screen is beside the pictures (`*.txt`).

**The drawings these are compared with** are in `04-docs/05-modules/03-customers/wireframes/customer-forms-2026-10-18/`. The side panel and the left-hand frame in the drawings are notes, not screens.

## 1 · Portal apply — drawing `04-portal.png`

| Picture | What it shows |
|---|---|
| `p1-address-*` | Address check: 2200 Riverbend Ct, Apt 101, Katy 77494 is served (Electric, Water). |
| `p2-when-*` | Start date in the product's date picker (MM/DD/YYYY); the utility's own question *Roof Material* must be answered before Continue. |
| `p3-about-empty-*` | About you, empty, in the drawing's order: Person/Business · names · cell phone · email (*Optional*) · contact by · date of birth · last 4 of SSN · co-applicant · mailing · preferences · documents. No category. |
| `p3-about-filled-*` | Every box filled: Maria Lopez, (734) 555-0182, text message, 04/12/1988, SSN 4471; co-applicant Daniel Lopez, Spouse (chosen from Move-in's list), (734) 555-0144, 09/30/1986; preferences paperless on, text reminders on, Español. |
| `p3-about-mailing-doc-*` | Mailing unticked → PO Box 2210, Ypsilanti, Michigan 48197; photo ID attached. |
| `p4-check-*` / `p5-sent-*` | Check and send restates every value; sent as SR-26-0065 (390 wide) and SR-26-0064 (1440 wide). |

Taken at 1440 and 390 wide. At 390 everything is one column and nothing scrolls sideways. Every box has a label a screen reader reads; the ticks and the folding card are keyboard controls with a 44px target. A wrong email or phone is named under its own box and never saved.

## 2 · Approve — drawing `05-approve.png`

| Picture | What it shows |
|---|---|
| `s1-request-1440` | The request as staff see it. |
| `s0-link-property-1440` | The existing step that links a portal request to its property (the portal finds the address; staff confirm the unit). |
| `s2-approve-blocked-1440` | **Category to be set.** This request came from the portal. Category and sub-category to pick; *From the customer*: name, phone, SSN last 4 4471, co-applicant Daniel Lopez (Spouse), the photo ID. **Approve is off: "Set the category first."** |
| `s3-approve-category-set-1440` | Residential chosen; the block is gone; the arrears search answered *No match*; Approve on. |
| `s4-move-in-opened-1440` | Approve opens Move-in carrying the request. |

## 3 · Move-in from the request, and the account it opens

| Picture | What it shows |
|---|---|
| `m2-move-in-customer-1440` | Customer step filled from the request: name, email, phone, date of birth, **contact by: Text**, co-owner card Daniel Lopez, the photo ID in the documents table, mailing PO Box 2210. Category Residential · Multi-family. |
| `m3-move-in-billing-1440` | Preferences filled: paperless **On**, text reminders **On**, language **Español**. |
| `m4-move-in-review-1440` / `m5-move-in-done-1440` | Review and the completed move-in: customer C-00057, account AC-2026-00058. |
| `a1-account-1440` | An account opened this way (AC-2026-00057): customer, date of birth, co-applicant, mailing address, paperless and text reminders all shown. |

Read back from the database for AC-2026-00057: paperless yes, SMS reminders yes, language `es`; contact Maria Lopez, maria.lopez@example.com, (734) 555-0182, contact by text, born 1988-04-12; co-owner Daniel Lopez, spouse, (734) 555-0144, dan.lopez@example.com, born 1986-09-30; mailing PO Box 2210, Ypsilanti MI 48197; 1 document. **Nothing the applicant typed was lost**, except the SSN's last four, which stays on the request by design (decision log, CF-2 item 3).

## 4 · Edit dialogs — drawing `08-edit.png`

| Picture | What it shows |
|---|---|
| `e0-edit-customer-record-1440` | Customers list → Edit customer: Person/Company (a change of kind is refused), name and phone required, email, contact by, date of birth in the date picker, SSN, driver's license. |
| `e1-edit-customer-1440` | Account page → Customer: name and phone required, email, contact by, date of birth. |
| `e2-edit-co-applicant-1440` | Account page → Co-applicant, with a date of birth (empty here: this account's second person is a co-owner, not a contact). |
| `e3-edit-mailing-1440` | Account page → Mailing address: street, **Apt / Unit**, city, **state from the list**, ZIP, the four marked required; a malformed ZIP is refused. |

## 5 · Transfer — drawing `07-transfer.png`

| Picture | What it shows |
|---|---|
| `t1-account-1440` | Account A-10650 chosen (an earlier run sold A-10432). |
| `t2-buyer-empty-1440` | The buyer step in the drawing's order: seller (account and category), Who is buying (no category), Identity with *Search customer ID*, co-buyers, documents, mailing, Tax, Discounts, Preferences. |
| `t2-buyer-ticked-1440` | Jordan Reyes, SSN given; co-buyer Ana Reyes, spouse; both required documents; tax exempt *Nonprofit organisation*, certificate TX-EX-20417, 01/05/2026–01/05/2028, certificate file; discount *Paperless billing*; paperless and text reminders on. |
| `t3-date-of-sale-1440` | Date of sale in the product's date picker. |
| `t5-review-1440` | Review restates co-buyer, 2 documents, Tax *Exempt · TX-EX-20417*, Discounts *1 claimed*, Preferences *Paperless · Text reminders*. |
| `t6-done-1440` | The sale is recorded. |

Read back from the database for A-10432 after its sale: paperless yes, SMS yes, autopay no; co-owner Ana Reyes, spouse, (281) 555-0142, born 1987-07-09; 3 documents (two staged plus the certificate); exemption certificate TX-EX-20417, 2026-01-05 → 2028-01-05, Nonprofit organisation; discount Paperless billing enrolled. The seller's own exemption and discounts were not copied.

Set-up note: Brazos Bend had no tax-exemption categories, so one (*Nonprofit organisation*) was added to each of its two taxes through the product's own endpoint, as Dana, before the transfer.

## Bugs the walk found, all filed

| Defect | What | State |
|---|---|---|
| DEF-CUS-10257 | Portal co-applicant relationship reached Move-in as free text, so the card printed a raw key. | **Fixed** (portal uses Move-in's list) |
| DEF-CUS-10258 | Move-in from a request showed no sub-category and printed its database id on Review. | **Fixed** |
| DEF-CUS-10261 | The account page's co-applicant pencil had no words (a screen reader read the raw key). | **Fixed** |
| DEF-CUS-10264 | Transfer Review said *Co-applicant: None* and *Documents: None* and showed no Tax, Discounts or Preferences. | **Fixed** |
| DEF-CUS-10265 | Transfer date of sale was a native browser date box. | **Fixed** |
| DEF-CUS-10259 | Move-in Review prints a co-owner's relationship as its code (*spouse*). | Open — Move-in's (CF-1) |
| DEF-CUS-10260 | Move-in Review says *Documents: None* when the documents came from the request. | Open — Move-in's (CF-1) |
| DEF-CUS-10262 | Account page shows the language as its code (*es*). | Open |
| DEF-CUS-10263 | Move-in's tax certificate dates (shared with Transfer and New connect) are native browser date boxes. | Open — Move-in's (CF-1) |

## Differences from the drawings that were left, and why

1. **Portal steps:** four (address · when · about you · check) against the drawing's *Address · About you · Documents · Review*. The PO signed the four. Documents sit at the foot of About you.
2. **Portal label:** *Cell phone* (the portal's word on every screen) for the drawing's *Mobile phone*.
3. **Approve:** the marker and the category pick are inside the Approve window rather than on a separate *Review* step — that window is where the product's approve checks already live.
4. **Transfer step bar:** five steps against the drawing's four (the signed transfer flow).
5. **Transfer co-buyer card:** no Photo ID upload; the documents table carries it.
6. **Transfer:** *More about the customer* (the utility's own fields) is not on the buyer step — there is no place configured for those fields on a transfer.
7. **Transfer:** Person/Company is not pre-chosen; the step asks for it (its existing rule).
8. **Account page *Customer* dialog:** no SSN / licence / Person-Company — those are the customer record's and are edited from the Customers list (`e0`).
9. Some drawn labels run past rule 33's three-word label cap (*Someone else on the account*, *How should we contact you?*); kept as drawn.

The app scrolls inside its own frame, so some staff pictures show the part of the page the step is about rather than the whole page.
