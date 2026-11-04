# Steps 1 and 2 as built, against the drawings — every divergence, named

`CR-150-BRC09` · `NCT-01` tasks 4, 5 and 6 · lane CUSTOMER-PREMISE · 2026-09-29

The drawings are `step1-customer.png` and `step2-premise.png`, and they are the
specification (B14 rule 42). **Where what shipped differs from what is drawn,
it is written here rather than left to be found** — the README's own
instruction, and hard-won law 1: a difference nobody wrote down is a difference
nobody can count.

Screenshots of the built screens at 1440, beside the drawings:
`10-scripts/nct01_steps12_walkthrough.mjs` writes them to
`05-prototype/new-connect-redesign-2026-09-28/as-built/`.

---

## A · Wording shortened, because B14 rule 33 caps it

Rule 44 gives the drawing what is on the screen and our standard how it is
built; rule 33 is our standard's cap on ON-SCREEN TEXT, and it is the rule that
bites here. **Rationale is removed rather than shortened; a fact is capped at
six words.** Four drawn sentences are over the cap.

| Where | Drawn | Built | Why |
|---|---|---|---|
| Gov-ID | *"A company is asked for Tax ID instead."* (8) | **"A company gives Tax ID instead."** (6) | a FACT, capped at six |
| Mailing address | *"The product's own US address block, the one move-in and new account already use. Nothing is required; the ZIP is checked for five digits or ZIP+4."* (28) | **deleted**, replaced by **"Taken from the service address."** when the tick is on | pure RATIONALE — *why the product works this way* — at rule 33's ZERO words. The replacement is a fact a clerk can act on |
| Unit, apt. or suite | *"Part of the postal address, optional. The units themselves are named on step 3."* (6 + 8) | **"Part of the postal address. Units are named on step 3."** (5 + 6) | two sentences of six beat one of twelve; *optional* is already said by the absent required marker (rule 32) |
| The record | *"The point is the building's. A unit may carry its own later; every screen says which one it shows."* (5 + 15) | **"The point is the building's."** (5) | the first sentence is `BR-MET-1162`'s required fact and is kept VERBATIM; the second is rationale about other screens |
| Priced-at table | *"Figures come from the plan as the server states them. No monthly total is multiplied up here."* (10 + 8) | **"Figures come from the plan."** (5) | the second sentence explains an ABSENCE, which is rationale. Hard rule 2 is what keeps the total off the screen, and it is enforced by the code and the test, not by a sentence |

**Two drawn HEADINGS are over rule 33's three-word label cap and are kept
verbatim anyway:** `Unit, apt. or suite` (4) and `What each service is priced
at` (6). A heading is the screen's own content, the drawing owns content, and
shortening either loses the distinction the PO asked for. Raised here rather
than decided silently.

---

## B · Drawn as one control, built as another, because the data is not there

| Where | Drawn | Built | Why, and what would close it |
|---|---|---|---|
| Step 1 · External system reference | a dropdown | a text box | **the drawing flags this itself** — its open question `A` reads *"External system reference drawn as a dropdown — what fills the list?"*. Nothing answers it, and a `<select>` with no list behind it is a control that cannot act |
| Step 2 · State | a dropdown | a text box | the state list is `apps/tenancy/selectors.US_STATES` and **no endpoint publishes it**. Typing fifty states into a screen is the third hand-typed list of a thing the server owns — the `fire` defect's shape. `AddPremisesWizard`, the other door that writes this column, draws a text box for the same reason, and the two must agree |
| Step 2 · `PRICED AS` column | two facts — *Metered · Water 1"* | one — the attached rate schedule's name | the pricing BASIS has no field on `PlanServiceLine` or anywhere else `GET /plans/{id}` serves. The cell shows what is served and an em dash where nothing is, rather than inventing a word |
| Step 2 · `ACCOUNT TYPE` | *Residential* | *Every class*, or *not named* | `PlanRow.account_type_ids` is a list of **ids** and `GET /lookups/account_types` 404s. B14 rule 31 forbids printing the uuid, and `rating/PlanDetail.tsx`'s own audience line already says *not named* for this reason. `null` or `[]` genuinely means every class, and that IS shown |

---

## C · Captured on screen, NOT yet carried by the commit — `DEF-CUS-6577`

**This is the one that matters and it is filed, not merely noted.**

`PREMISES_BLOCK_FIELDS` in `apps/metering/connections.py` refuses an unknown
key **by name**, and the block it accepts is
`address · premise_type · parcel_ref · read_route · services_available · name ·
city · state · postal_code`. So everything new on these two screens is held on
the draft and reaches no server:

* step 2 — `unit`, `lat`, `lng`, `locationVerified`
* step 1 — the customer `category`, `dateOfBirth`, the communication
  preferences, the co-applicant, the mailing address, the account custom data,
  and a document's `documentNumber`

**Adding them to the payload without the server's half would have broken the
commit outright**, which is why the wire was left alone. The gap is
`DEF-CUS-6577`, and it is the next thing to build on these two steps.

---

## C2 · One construction choice the drawing does not speak to

**The co-applicant panel takes the whole width once it is open.** The drawing
draws it half-width beside *Mailing address*, holding one button — which is
the closed state and fits. The nine fields that button opens do not: a
three-column form grid inside a 550px column is how a screen starts to look
like a mistake. Closed it is half-width as drawn; open it is full width and
*Mailing address* moves below it. That is CONSTRUCTION, which B14 rule 44
gives to our standard, and it is written here because it is visible.

⚠ **AND THE GOV-ID PANEL WAS BUILT WRONG FIRST AND WAS FOUND BY LOOKING.** The
first pass folded the three identity controls into the *Owner* panel with no
heading, so the drawn `Gov-ID` panel was simply absent and *Communication* sat
beside *Mailing address* instead. Every test passed — the controls were all
there and all wired. It was found by putting the screenshot beside the drawing
(hard-won law 6), which is the only check in this repository that reads
rendered output. `GovIdFields` is now one component mounted twice: the owner's
copy is the drawn panel, the co-applicant's is inline in theirs (rule 43).

## D · Tidy-ups recorded rather than done

* **The file is `NewConnectOwnerStep.tsx` and the step id is `customer`.**
  Renaming a file is a separate, noisy act and was kept out of this build.
* `customers.newConnect.step3.*` is step 2's key prefix, deliberately: renaming
  it moves every string in eleven catalogues for no user-visible change.
* `customers.newConnect.step1.how` and `customers.newConnect.step1.title` no
  longer have a call site on step 1. They are LEFT in the catalogues because
  the wizard frame may still read the title, and retiring a key that is still
  called prints the key rather than falling back.
