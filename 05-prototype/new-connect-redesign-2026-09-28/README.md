# New Connect redesign — the drawings of record (2026-09-28)

**These seven PNGs ARE the specification for the five-step New Connect.** PO
instruction, verbatim: *"please ensure you usgae drawing images anot not
text/content to create screensin b[product and use Ui skills, spcaing, font
setc - this is improtnt"* — which is B14 rule 42 (a screen is built from the
drawing AS AN IMAGE; extracted text is an index, never the specification) and
rule 44 (our UI standard decides how it is built: spacing, sizes, the type
scale, the tokens, the component kit — every time, on every screen, including
the frame).

**So: open the PNG with the Read tool and look at it before writing TSX.**
Reading `00-all-screens.html` as text instead is the failure this file exists
to prevent.

| File | Screen |
|---|---|
| `step1-customer.png` | Step 1 · Customer |
| `step2-premise.png` | Step 2 · Premise |
| `step3-units.png` | Step 3 · Units |
| `step3a-add-row.png` | Step 3 after **Add row** |
| `step3b-add-work-order.png` | Step 3 after **Add work order** |
| `step4-charges.png` | Step 4 · Charges |
| `step5-review.png` | Step 5 · Review |

`00-all-screens.html` is the source the images were rendered from. It also
carries, per screen, the list of sentences DELETED under rule 33 and the notes
on what each control does — read it for those, never for layout.

⚠ **THE DRAWINGS ARE ILLUSTRATIONS FOR EVERY FIGURE THEY CONTAIN** (rule 37).
Jonas Janssen, `$1,035.00`, `C-00010`, the Ottumwa address and every count come
from the PO's own screenshots of the deployed build `v2.385.1`. Build the SHAPE;
never hard-code a figure off the drawing.

⚠ **WHERE THE DRAWING AND OUR UI STANDARD DISAGREE, THE STANDARD WINS** (rule
44). The PNGs were drawn at 1560px in a stand-alone page, so their spacing and
type are an approximation of the product's: take spacing, sizes, the type scale
and the components from `04-docs/02-decisions/14-ui-conventions.md` and the
shared kit, and take the LAYOUT, the fields and their order from the image.
Staff screens are built at 1440 and must work at 1280.
