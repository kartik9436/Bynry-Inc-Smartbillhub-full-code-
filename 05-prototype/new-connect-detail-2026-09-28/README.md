# New Connect: the build detail page and the list — drawings of record (2026-09-28)

**These eleven PNGs ARE the specification.** PO instruction, verbatim: *"ensure
you use images to build screens and not text/content"*, and earlier the same
day *"please ensure you usgae drawing images anot not text/content to create
screensin b[product and use Ui skills, spcaing, font setc - this is improtnt"*.
That is B14 rule 42 and rule 44. **Open the PNG with an image reader and look at
it before writing TSX.** Reading `00-all-screens.html` as text instead is the
failure this file exists to prevent.

| File | Screen |
|---|---|
| `00-list.png` | Accounts › New connects, the list |
| `01-overview.png` | The build page, Overview tab, with the More menu open |
| `02-units.png` | Units tab |
| `03-work.png` | Work tab — crew and technician are separate columns |
| `04-charges.png` | Charges tab |
| `05-documents.png` | Documents tab |
| `06-messages.png` | Messages tab |
| `07-audit.png` | Audit tab (named Audit, as on the account and template pages) |
| `08-resend.png` | Pressing Resend |
| `09-take-payment.png` | Pressing Take payment |
| `10-draft.png` | A parked draft |

⚠ **THIS PAGE REVERSES A RULING.** On 2026-09-04, `CR-070` wave O deleted
`features/customers/ConnectionDetailPage.tsx` (1,464 lines), kept the route as a
redirect, moved the panels into `features/work/buildViews.tsx`, and added
`G93` so the destination *"cannot come back"*. **PO ruling 2026-09-28
supersedes it**: a full detail page per build. The supersession is written down,
`G93` is amended deliberately citing the new ruling, and the two rules that
killed the old page still hold: **money facts link to the account rather than
being re-implemented**, and **no panel is copied — this page composes the shared
ones.**

⚠ **FIGURES ARE ILLUSTRATIONS** (rule 37). Jonas Janssen, `$1,035.00`,
`B-2026-00042`, the Ottumwa addresses and every count are examples from the PO's
own screenshots of `v2.385.1`. Build the SHAPE; hard-code no figure.

⚠ **WHERE THE DRAWING AND OUR UI STANDARD DISAGREE, THE STANDARD WINS** (rule
44). Spacing, sizes, the type scale and the components come from
`04-docs/02-decisions/14-ui-conventions.md` and the shared kit; the LAYOUT, the
fields and their order come from the image. Staff screens are built at 1440 and
must work at 1280.

**Every action label is one or two words** — PO, 2026-09-28: *"you need to use 1
or 2 action words - dont use 3 words"*. Raise order · Hold · Release · Waiting
on · Add service · Mark outstanding · Close outstanding · Cancel build · Take
payment · Resend · Add document · Carry on · Re-park.

**No saved-view chips on the list** — PO: *"all these option will anyway will be
in filter - so we dont need them outside"*. State is a filter. The tiles SET
that filter rather than filtering around it, or the two controls disagree.
