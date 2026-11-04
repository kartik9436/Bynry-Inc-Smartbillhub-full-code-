# CR-094-BRC01 lane F — the service-request capture wizard and the request record

**Screens:** `S85` `/:tenant/requests/new` (six steps) · `S84` `/:tenant/requests/:requestId`
**Drawing:** `05-prototype/…/accounts-blueprint.pdf`, rendered as PAGE IMAGES at scale 2 —
**capture on p75–80, the record on p82–83.**
**Walked:** yes, in a browser, signed in as a billing clerk on `brazosbend`, at **1280 and 1440**.
**Date:** 2026-09-13.

---

## 0 · The drawing is on p82, not p141, and that is the first finding

The brief pointed at `blueprint/06-service-request-capture.md` and
`blueprint/17-service-request-detail.md`. **Neither contains a drawing.** Both are
redirects: 06 says its text is in `05-move-in-wizard-standalone.md`, and 17 says its
text is in `16-service-requests-list.md`. The extractor's own note explains why —
screens 16 and 17 print over one span and it could not separate them — and it adds
that *"some of these pages carry little extractable text (a drawing rather than
prose); read the PDF for those."*

**Reading the PDF as images settled it in one look:** the request record is drawn on
**page 82**, immediately under the requests list, and page 141 is a different screen
entirely. A lane working from the markdown alone would have found a pointer to a file
that does not contain the screen it names, and would have built from prose.

This is the PO's ruling of 2026-09-13 arriving as a measurement rather than as advice:

> *"When you use images to create screens your accuracy is higher; hence dont create
> screens using only Text"*

**What the text layer keeps:** the labels. **What it loses, and what the images gave
back here:** the two-column body on both screens; the drawing's right-hand ANNOTATION
column, which reads in text as if it were screen content; that the review's fact rows
are label-left / value-right rather than the label-above-value the product uses; that
the fees block is a bordered card with a rule above a bold outcome row; and which of
the drawing's blocks are dashed (a stated absence) rather than solid.

---

## 1 · The census — what was on screen before, measured not remembered

Both screens were driven in a real browser against the booted stack
(`127.0.0.1:8080` joined to Django on `8011`), signed in, at 1280 and 1440. Neither
scrolls sideways at either width; both page titles measure **32px** (B14 rule 40).

### The capture wizard, head

| | drawn (p75–80) | as built |
|---|---|---|
| kicker | `NEW REQUEST` | `NEW SERVICE REQUEST` |
| title | the step's own question, one per step | `Capture a service request.` on all six |
| sub-line | `Step 1 of 6 · Customer` … `Step 6 of 6 · Check` | none |
| step rail | six, in order | **matches** |
| right action | `Save & exit` | `Save as draft` |

### The capture wizard, step 6

Drawn order: **The applicant** ✎ Step 1 · **What they are asking for** ✎ Step 2 ·
**Addresses and property** ✎ Step 3.
As built: `Applicant` (1) · `Service address` (3) · `Connection` (2) — right content,
**wrong sequence**, and none of the three named as drawn. A clerk checking their work
jumped from the address back to a step they had answered earlier.

### The request record, head

| | drawn (p82) | as built |
|---|---|---|
| back crumb | `← The register` | `← Requests` |
| kicker | `REQUEST SR-26-0001 · NEW CONNECTION` | `REQUEST` |
| **title** | **the applicant — `Miller, Sarah`** | **the request number — `SR-26-0005`** |
| meta line | state · waiting-on · channel · `Received <date>` | state · number again · applicant again · address · a type chip |
| address | its own line, under the meta | inside the meta line |
| tabs | `Applicant · Documents · History` | six |
| actions | `Refuse · Ask for more · Approve` | `Save & exit · Park ▾ · Decide what this is →` |

---

## 2 · What was built

Both screens' heads now match the drawing **row for row**, verified in a browser at
both widths after the change:

```
← The register
REQUEST SR-26-0005 · NOT YET CLASSIFIED
Ridge Coffee Co.
Under review   Waiting on third party   Raised by our own staff   Received 09/09/2026
500 Main St
```

* the record's page title is the applicant; the number moved to the kicker beside the
  job type, so nothing a clerk quotes down the phone was lost;
* the meta line stopped repeating the number and the name that now stand above it, and
  gained the channel and the received date it was missing;
* **the waiting-on and channel words are the LIST's own catalogue keys**, with the raw
  value as the fallback, exactly as `ServiceRequestsListPage` renders them — so a
  status word cannot read one way on the list and another on the record;
* the Applicant tab's first block is headed `WHO IS ASKING`, not `Applicant`, which was
  the tab's own word repeated inside it;
* the wizard's kicker is `NEW REQUEST`; each step's question is its 32px page title and
  changes with the step; the head carries the drawn `Step N of 6 · <step>`;
* step 6's review reads 1 → 2 → 3 under the drawing's own three names.

**Two things came OFF the screen and into the code, both under B14 rule 33
(*rationale is zero words on screen*):** step 1's two-sentence hint about what the
category decides, and step 1's question as a body heading once it became the title.
Step 6 had the same duplication and it is gone too.

**One sentence lost a prefix rather than a meaning:** the draft footer read
`Step 1 of 6 · not saved yet — …`, which duplicated the drawn head line the moment it
landed. It keeps its `BR-CUS-093` draft statement and loses the four words that
repeated the head.

---

## 3 · What was NOT built, and why

| what | why not |
|---|---|
| The drawn **two-column body** on both screens (Documents · Fees · History beside the facts), and the record's **three** tabs against the product's six | Re-homing them moves every control on three live tabs, `Decide what this is →` among them, which is the approve path. The maintenance process returns a question to the PO when the answer changes what a user can DO. → **`OQ-CUS-12357`**, OPEN |
| The record's drawn action row `Refuse · Ask for more · Approve` | Same reason — those three live on the `Decision` tab today. → **`DEF-CUS-5194`**, waiting on the question above |
| Capture step 2's **eleven-service multiselect** and its per-service `REQUESTED START` table | The request carries ONE `connection_date` for the whole job. The drawing's own annotation says why it matters — *"a block that needs electric on the 12th and sewer a fortnight later is one request and not two"* — and it cannot be captured as drawn without a column per service. → **`DEF-CUS-5195`** |
| Capture step 4's **documents table** (`REQUIRED · FILE · UPLOADED BY · STATE`) and its four filter chips | There is no file store (`BR-CUS-095`, and the screen says so). But three of the drawn columns do not need one, and the product shows none of them: a partial absence was built as a total one. → **`DEF-CUS-5196`** |
| `Save & exit` on the wizard, which is what the drawing labels that button | The control saves a DRAFT and does not exit. Renaming it to match the picture would make the screen say something untrue about what pressing it does. Left, and stated here. |
| Step 3's drawn City / State / ZIP boxes and *"How many units are on this property?"* | **Not a divergence.** The drawing's own dashed blocks say the product keeps one address line and holds no unit count. The screen is honest and was left alone. |

---

## 4 · Proof

* **27 cases proved RED** against the starting tip's code in a `git worktree`, under the
  same `vitest` that runs them — the harness, not a hand-called module.
* **The two cases the tip could not falsify were proved red separately**, because a
  check that can only fail one way, described as if it guards both, is hard-won law 7:
  the step line said twice (prefix restored → *expected 2 to be 1*) and step 6's title
  said twice (the `h3` restored beside the new title → *expected 2 to be 1*).
* **93 tests green** across the three files; `tsc` clean — and proved live first by
  breaking it, because a `tsc` that reports nothing and a `tsc` that did not run look
  identical.
* **`G27` passes on the branch** (`every literal and config-carried translation key
  resolves`), verified in a clean worktree because the shared tree carries two other
  lanes' uncommitted wizards which fail it.
* 21 new catalogue keys plus 3 reworded, fanned into all eleven languages through
  `10-scripts/i18n_fanin.py` — parity or nothing, by that tool's own guarantee.

## 5 · The lesson worth keeping

**A blueprint entry that redirects is not a drawing, and neither is the text extracted
from one.** Both of this lane's screens pointed at files that did not contain them, and
the record's drawing was sixty pages from where the index said. Render the pages and
look at them; the index is a hint, the image is the specification.
