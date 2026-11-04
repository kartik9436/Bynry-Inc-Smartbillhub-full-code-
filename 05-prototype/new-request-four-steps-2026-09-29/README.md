# New Request, six steps into four — APPROVED by the PO, 2026-09-29

**These PNGs are the specification. Build from the IMAGES (B14 rule 42), not from this
text.** The text below is an index and a record of what was ruled; it is not the screen.
*"When you use images to create screens your accuracy is higher; hence dont create
screens using only Text"* (PO, 2026-09-13), restated on 2026-09-29: *"build all screens
using images and not text/content, use ui skills that we have in git repo"*.

⚠ **USE THE REPO'S UI SKILL.** `react-tailwind-css-ui-generator` is to be loaded before
the first line of TSX and again before calling a screen done. B14 rule 44: our UI
standard and the shared component kit win over the drawing on every screen, and rule 43:
a piece of UI is a COMPONENT, never code inlined in a page.

| File | What it is |
|---|---|
| `01-applicant-1440.png` | **Step 1.** The 11 applicant fields, category and sub-category, co-applicant, Documents. |
| `01b-applicant-coapplicant-open-1440.png` | Step 1 with **Add a co-applicant ticked** — the three fields expanded. |
| `02-property-1440.png` | **Step 2.** Address search in its *not found* state, read-only city/state/ZIP, Mailing address ticked. |
| `02b-property-mailing-expanded-1440.png` | Step 2 with **Same as the service address cleared** — the five fields expanded. |
| `03-service-1440.png` | **Step 3.** Services table array, Application fees table array, payment with the check fields. |
| `04-review-1440.png` | **Step 4.** Six panels, the new communication card, renumbered Edit links. |
| `…-1280.png`, `…-420.png` | The same four at 1280 and phone width. |

⚠ **THE TYPEFACE IN THESE IMAGES IS WRONG AND EVERYTHING ELSE IS RIGHT.** The renderer
cannot reach `fonts.googleapis.com` through this container's proxy, so the images show
the `system-ui` fallback rather than **Archivo**. Build with the product's own font
token; do not match the letterforms you see. Spacing, colour, control types, grouping and
order are drawn on `07-frontend/src/styles/tokens.css` and ARE the specification.

⚠ **THE DRAWINGS CARRY NO ANNOTATIONS, ON PURPOSE.** The working artifact had pink
explanatory boxes and green "changed" badges addressed to the PO. **None of it is product
copy and none of it may be built** — B14 rule 33 puts rationale at ZERO words on screen,
which is the same rule that removed 86 words from New Connect's Created screen on
2026-09-28 (`DEF-CUS-7692`). The captures were taken with every annotation hidden, and
the capture script **fails rather than shoots** if any is still drawn.
⚠ **AND THE FIRST ATTEMPT AT THAT CHECK FALSELY PASSED**, which is worth more than the
rule: it counted the `hidden` ATTRIBUTE and reported zero while the green badges were
still on screen — a local render has no `[hidden]{display:none!important}`, so `hidden`
loses to an explicit `display`. The check now measures **rendered geometry**
(`getClientRects().length`), which is the only form that can answer *is it drawn*. Law
7's *"ask what would make this check pass wrongly"*, caught in our own tooling.

---

## What the PO ruled

**Six steps → four, and nothing is lost.** All 42 inputs keep a place:
Applicant (13 + 5 documents) · Property (12) · Service (5 + 7) · Review (read-only).

| Ruling | Verbatim |
|---|---|
| `+ Premises` is removed from the Property step | *"if not found not add premise button should not show"*, then *"this si correct"* |
| One document button, not two | *"add another document button is not required attach document button"* |
| Category and sub-category move to the Applicant | *"move this to appliant sicne it is applicant - arrtributes"* |
| Services becomes one table array | *"can we merge this two and create table array for this"* |
| Application fees becomes a table array | *"application fees as table arrary"* |
| American English | *"use american english check = not cheque"* |
| Billing → **Mailing** address, and it shows the address when ticked | *"it should be mailing address - if ticked - then show the address here = service address so that user can understand"* |
| Co-applicant expands on tick | *"can you make this expand when tick"* |
| Review gains a communication card, in table form | *"on review you should display 1 card for communcaition to cusomer - in table format step 4"* |

## Three defects fixed by this build

1. **`+ Premises` showed in BOTH cases** — whether a premise matched or not — and pressing
   it navigated the clerk OUT of the wizard into the premises register. A request records
   what the applicant said; it never creates a property. The typed address is kept word
   for word (`BR-CUS-070`) and the register is matched separately.
2. **Two document buttons were one act with and without bytes.** The single `Attach a file`
   keeps BOTH routes: with a file it attaches; with none it records the document as
   expected, which is the only way to make the row that reads *Nothing attached*.
   **Removing that capability is not what was asked for — only the second button goes.**
3. **Review printed the connection date on every service row.** ⚠ Settled from the code,
   not from an opinion: `service_requests.requested_start` (commented *"Connection date"*)
   is ONE per request, and `ServiceRequestService.requested_start` is one per service.
   Two genuinely different facts, so repeating the request-level one down a column invited
   a clerk to believe they could differ. Review prints it once.

## The columns, and why

**Services** — `SERVICE · REQUESTED START · STATUS · ×`. The service is a dropdown IN the
row, so choosing one and dating it is one act; the chips and the separate *Add a service…*
box are gone, because adding a row IS adding a service. `STATUS` is *New* / *Already on
site* — the register knows it and a clerk should see it before promising a date.
**Connection date stays outside the table**, per the third defect above.

**Application fees** — `FEE · CHARGED PER · QTY · UNIT PRICE · AMOUNT · ×`. Only `FEE` and
`QTY` are typed. ⚠ **`AMOUNT` and the total are worked out by the SERVER and printed
here — never multiplied in the browser** (hard rule 2; `DEF-088` and `DEF-127` are what
that costs).

**What the customer is told** — `MESSAGE · CHANNEL · TO · WHEN`, read-only. ⚠ **A message
that will NOT be sent gets its own row saying so**, because an absent row and a withheld
one look identical. This is the only genuinely new capability in the redesign; everything
else rearranges what already works.
