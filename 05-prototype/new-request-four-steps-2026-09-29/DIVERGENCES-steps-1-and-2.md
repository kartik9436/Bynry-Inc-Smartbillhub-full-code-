# Where the build differs from the drawing — steps 1 and 2

Lane SCREEN-A, 2026-09-29, version `2.399.0`. Every row here is a place where
`01-applicant-*.png` / `01b-*.png` / `02-property-*.png` / `02b-*.png` and the
product do not match, **with the reason**. B14 rule 41 puts the product at the
drawing's shape and carves out exactly one exception — a drawing that
contradicts a signed rule — so each row below names the rule.

**Stamped here rather than left to be noticed** (hard-won law 6: no gate in
this repo reads rendered output, and a silent difference is indistinguishable
from a mistake).

| # | The drawing | The build | Why |
|---|---|---|---|
| 1 | The typeface is `system-ui` | **Archivo**, the product's font token | The renderer could not reach `fonts.googleapis.com` through the container's proxy. The README says so; this is the drawing being wrong, not the build. |
| 2 | *Nothing matched yet. The address above is kept as the applicant gave it.* | **Nothing matched yet. Your typed address is kept.** | B14 rule 33 caps a FACT at six words. Thirteen words in one sentence becomes two sentences of three and five, which is the rule's own *"two sentences of six beat one sentence of twelve"*. The meaning is unchanged. |
| 3 | *Sets which plans they are eligible for.* | *Sets which plans this customer is eligible for.* | The existing catalogue string, in all eleven languages. A one-word improvement is not worth moving eleven files while lane COPY owns them; the drawn wording is recorded here so it is not lost. |
| 4 | `File` is a bare `Choose File / No file chosen` | **`FileDropField`** — drag a file in, or browse | B14 rule 44: our UI standard and the shared component kit win over the drawing on every screen. The drop control is what the PO asked for on 2026-09-22 (*"a proper drop-file control"*) and is the kit's. |
| 5 | The city / state / ZIP boxes show `Ottumwa`, `Iowa`, `12365` while the panel says **No premises match** | Empty when nothing matched | B14 rule 37: a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build to. What the drawing SETTLES is the shape — three read-only boxes with *From the matched premise.* beneath — and that is built. |
| 6 | The co-applicant fields are drawn three across at 1440 | Three across, collapsing to one column below 1024px | `FieldGrid`'s own behaviour, not this screen's. Rule 44. |
| 7 | *Applying as* is drawn with no `Applying as` control on the older blueprint | Drawn, first on the step | Already-standing divergence: `BR-CUS-1022` requires the kind to be stated where identity is presented. Carried forward unchanged. |
| 8 | **`Driver's licence`** | **`Driver's license`** | The PO ruled American English on 2026-09-29 (*"use american english check = not cheque"*) and the catalogue already said `license`. **The drawing is the outlier**, so it is recorded here rather than built. |
| 9 | *Search premises. Pick the address.* | *Search Premises. Pick the address.* | The existing catalogue string in eleven languages, and `Premises` is capitalised because it names the REGISTER a clerk clicks in the sidebar. Not worth moving eleven files while lane COPY owns them. |
| 10 | No heading over the attach form | **No heading** | Was `Attaching one`. Found by looking at the running app, not by a test: the section already has `Documents` and a sub-line above the table, so a second heading is B14 rule 32's *"too much content"*. `DocumentCaptureForm` takes `formHeading={false}`; `TransferWizard` keeps it, because that step has no heading of its own and was not in front of the PO. |
| 11 | The mailing `Street address` and `Apt, suite or unit` sit side by side on one row | Stacked, full width, with `City · State · ZIP` in a row beneath | `components/UsAddressFields` is the kit's one US address block, shared with the move-in and the New account mailing panel. B14 rule 44: how a form is BUILT is the UI standard's. Changing it here would change three screens on one screen's authority. |

## What the running app showed that no test did

Three of the rows above — 8, 9 and 10 — and one missing sentence were found by
**putting the built screen beside the drawing at 1440**, with every suite green
and `tsc` clean. Hard-won law 6 is the only check in this repository that reads
rendered output, and it is a person.

The missing sentence: the search line printed **"No premises match."** and
stopped. The drawing prints **"No premises match. The address you typed is
kept."** — and the second half is the one a clerk taking a new connection at a
greenfield site actually needs, because it is what `BR-CUS-070` promises. It is
built now.

## What the drawing settled, against something already signed

**`Tax ID` is on screen for a person, and disabled.** `BR-CUS-1022` says a
person is never ASKED for a Tax ID. The drawing puts all eleven fields on at
once. Both hold, because a **disabled** box is not asking — it cannot be
filled, and `clearOtherKind` still blanks the other kind's values. It carries
the drawn placeholder *Companies only* as the reason `BR-SHL-025` requires, and
the three personal identifiers carry *People only* the other way round.

**City, State and ZIP are read-only, which reverses a PO ruling of 2026-09-22.**
That ruling made them typeable while no premises was picked. The drawing of
2026-09-29 draws them greyed in exactly that state. **A clerk can no longer
type a town for an address the register does not hold.** The columns are
untouched — a caller that knows them can still send them — and this is the one
thing on these two screens most likely to need the PO again. It is in the
decision log of 2026-09-29 with the same words.

## The 420px frame — reported, not built (`OQ-CUS-7853`)

The drawings carry a 420px frame for every step, with no sidebar. **The built
screens stack correctly at 420; the app SHELL does not collapse**, so its 240px
sidebar leaves about 180px of page and the fields render about 105px wide.

That is not a fault in these two screens and it is not fixed here. The PO ruled
on 2026-09-10 that the staff app is *"laptop, and desktop application - not
mobile"*, which is why 1440 and 1280 are the widths this build is verified at.
Whether the 420 drawings change that ruling is `OQ-CUS-7853`, and the three
options are written out there with the measured figures.

## The shots, and how to re-take them

    node 10-scripts/req03_four_step_screen_a_shots.mjs

It photographs both steps at **1440, 1280 and 420** and prints PASS/FAIL for
**eighteen claims** beside the shots, because three of the four things this
redesign changed are things that are no longer on the screen — and a photograph
of a correct screen and a photograph of a wrong one look identical to a reader
who does not know what to miss.

⚠ **ONE STATE COULD NOT BE PHOTOGRAPHED AND THE SCRIPT SAYS SO RATHER THAN
SKIPPING IT.** The *premises FOUND* half of `DEF-CUS-7850` needs a matching row
in the demo register and nothing matched; it is proved instead by
`ServiceRequestCaptureFourStep.dom.test.tsx`, which fakes one. An absence with
no reason beside it is indistinguishable from a pass.
