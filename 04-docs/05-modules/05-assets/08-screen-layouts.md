# A5 · Assets — screen layouts, and where the drawing is

**Created 2026-09-12, `CR-092-BRC01`, between step 1 and step 2 — because the module had
none.** Assets held business rules, a field map, flows, stories and epics and **no drawn
specification at all**: no wireframes, no screen-layouts file, no component inventory.
The portal has all five; this module had zero.

## Why this file exists, and it is a rule rather than a preference

The repository's build skill, `react-tailwind-css-ui-generator`, opens with it:

> *"A URL is not a drawing. 'The design doc' is not a drawing.
> **A drawing a lane cannot open is a drawing that will not be built.**"*

The 56 Assets wireframes existed only inside a published artifact. **A lane could not open
them**, so five lanes would have built from a prose summary of a picture — which is exactly
how the property Overview shipped with three rows missing and four labels different, the
incident the skill cites as its own reason for existing.

## Where the drawing is

**[`wireframes/CR-092-assets-screens.html`](wireframes/CR-092-assets-screens.html)** —
open it in a browser.

⚠ **AND THE DURABLE SOURCE IS A PDF ON THE DEFAULT BRANCH, NOT THE ARTIFACT THIS WAS
EXTRACTED FROM.** The artifact lives in a session scratchpad and dies with the session;
the PDF is in version control. **`05-prototype/01 Assets Menu Blueprint.pdf`** on
`claude/confirm-understanding-3ktufc` — **219 pages, 9.9 MB**, and **proved to be the
same document**: same version `2.234.17`, same commit `79c659d7`, same 35 screens / 56
wireframes / 137 fields / 24 specifications / 49 absences.

**It is not copied onto this branch on purpose** — a 9.9 MB binary duplicated across
branches is a second copy free to drift, which is hard-won law 5. Fetch it when you
need it:

```
git fetch origin claude/confirm-understanding-3ktufc
git show "origin/claude/confirm-understanding-3ktufc:05-prototype/01 Assets Menu Blueprint.pdf" > /tmp/assets.pdf
python3 10-scripts/pdf/pdf_text.py   /tmp/assets.pdf            # 377 KB of searchable text
python3 10-scripts/pdf/pdf_render.py /tmp/assets.pdf /tmp/pages 2 "34,35,36"   # pages to PNG
```

⚠ **Nothing in this container reads a PDF without those two scripts** — poppler will
not install, PIL times out, and `pypdf` crashes on a broken `cryptography` build. That
is why they exist, and their README says so. Self-contained: it re-pins the product's own literals, so a picture
of a light product does not restyle itself in a dark viewer.

**Proved to render rather than assumed** (Chromium, 1440×1000, 2026-09-12):
**56 of 56 wireframes draw with real height**, 48 product rails, 35 screen blocks,
**zero page errors, no horizontal scroll.**

⚠ **AS-BUILT, NOT AS-SHOULD-BE.** Screens 01–33 draw the product *as it is*, broken
controls included. A tidied drawing would delete every finding from the picture. **Section
10's six drawings are REMEDY** — drawn answers, not current state.

⚠ **THE DRAWINGS HOLD; THE FIGURES IN THEM DO NOT.** Every as-built statement was true at
`2.234.17` / `79c659d7d`, and all seven cited asset files are byte-identical to this branch.
**But the walk ran against a tenant holding 126 assets and no tenant holds 126 today** —
14 / 74 / 135. Every row count, every pager figure and every KPI number drawn here needs
re-measuring before it is trusted. `CR-092-BRC01` §3a carries the trap in full.

⚠ **B14 rule 37: a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build
to.** That rule and the paragraph above say the same thing from two directions.

## The 35 screens

| # | Screen | Route | Drawings | Specifications | State |
|---|---|---|---|---|---|
| **01** | [Meters](wireframes/CR-092-assets-screens.html#screen-01) | `/:tenant/assets?tab=meters &nbsp;·&nbsp; also /:tenant/ass` | 1 | AST-B-01, AST-B-15, AST-B-20 | Exists behind, New read |
| **02** | [Sub-meters](wireframes/CR-092-assets-screens.html#screen-02) | `/:tenant/assets?tab=sub_meters` | 1 | AST-B-01, AST-B-15, AST-B-20 | Exists behind |
| **03** | [Behind the meter](wireframes/CR-092-assets-screens.html#screen-03) | `/:tenant/assets?tab=behind_the_meter` | 1 | AST-B-01, AST-B-15, AST-B-20 | Exists behind, New read |
| **04** | [Inventory](wireframes/CR-092-assets-screens.html#screen-04) | `/:tenant/assets?tab=inventory` | 1 | AST-B-01, AST-B-15, AST-B-20 | Exists behind |
| **05a** | [Lifecycle · Certifications & tests due](wireframes/CR-092-assets-screens.html#screen-05a) | `/:tenant/assets?tab=lifecycle&amp;section=certifications` | 1 | AST-B-11, AST-B-15 | **BUILT `2.237.5`** |
| **05b** | [Lifecycle · Warranty & supplier](wireframes/CR-092-assets-screens.html#screen-05b) | `/:tenant/assets?tab=lifecycle&amp;section=warranty` | 1 | AST-B-11, AST-B-15 | **BUILT `2.237.5`** |
| **05c** | [Lifecycle · Age & replacement forecast](wireframes/CR-092-assets-screens.html#screen-05c) | `/:tenant/assets?tab=lifecycle&amp;section=forecast` | 1 | AST-B-11, AST-B-15 | **BUILT `2.237.5`** — the Asset value panel REMOVED per the PO's quoted instruction; the Programme total and the Turn-into-work panel KEPT (the carry-over left both undecided) |
| **06** | [Map](wireframes/CR-092-assets-screens.html#screen-06) | `/:tenant/assets?tab=map` | 1 | AST-B-06, AST-B-15 | Exists behind |
| **07** | [Assign 3 assets to a unit](wireframes/CR-092-assets-screens.html#screen-07) | `no address of its own — a dialog on /:tenant/assets` | 1 | — | Exists behind |
| **08** | [Overview](wireframes/CR-092-assets-screens.html#screen-08) | `/:tenant/assets/{id}` | 3 | AST-B-12, AST-B-16, AST-B-22 | Exists behind, New build |
| **09** | [Reads](wireframes/CR-092-assets-screens.html#screen-09) | `/:tenant/assets/{assetId}?tab=reads` | 3 | AST-B-16, AST-B-19, AST-B-20, AST-B-23, AST-B-24 | Exists behind |
| **10** | [Export](wireframes/CR-092-assets-screens.html#screen-10) | `/:tenant/assets/{assetId}?tab=export &nbsp;— an inverter w` | 1 | — | Exists behind |
| **11** | [Assignment history](wireframes/CR-092-assets-screens.html#screen-11) | `/:tenant/assets/{assetId}?tab=assignments` | 1 | AST-B-19, AST-B-23 | Exists behind |
| **12** | [Work & maintenance](wireframes/CR-092-assets-screens.html#screen-12) | `/:tenant/assets/{id}?tab=work` | 2 | AST-B-02, AST-B-18, AST-B-19, AST-B-21, AST-B-23 | Exists behind, New build |
| **13** | [Audit](wireframes/CR-092-assets-screens.html#screen-13) | `/:tenant/assets/{assetId}?tab=audit` | 1 | AST-B-02, AST-B-18 | Exists behind |
| **14** | [Edit one asset](wireframes/CR-092-assets-screens.html#screen-14) | `/:tenant/assets/{assetId}/edit &nbsp;— a full page, replac` | 1 | AST-B-12, AST-B-13, AST-B-26 | **BUILT `2.239.9`** — ⚠ **ITS FIELD TABLE NAMES ONE FIELD THE FORM DOES NOT HAVE (`DEF-AST-5107`): read `manufacturer_model` where the drawing writes `location_note`.** The drawing says its field set was read from `AssetFormModal`; it was read wrongly, and the reconciliation arithmetic beside it cannot see a SWAP because a swap leaves the count right. `location_note` IS editable — on the Lifecycle panel dialog (`AST-B-25`), which is why it was not added here as a second way to write one field |
| **15** | [Delete this asset?](wireframes/CR-092-assets-screens.html#screen-15) | `no address of its own — a confirm on /:tenant/assets and /` | 1 | — | Exists behind |
| **16** | [Edit · What's due](wireframes/CR-092-assets-screens.html#screen-16) | `Modal over /:tenant/assets/{id} · PATCH /assets/{id}` | 1 | AST-B-13, AST-B-25, AST-B-26 | New build |
| **17** | [Edit · Measurement](wireframes/CR-092-assets-screens.html#screen-17) | `Modal over /:tenant/assets/{id} · PATCH /assets/{id}` | 1 | AST-B-13, AST-B-25, AST-B-26 | New build |
| **18** | [Edit · Measurement · confirm](wireframes/CR-092-assets-screens.html#screen-18) | `The second step of the same modal — no second address` | 1 | AST-B-13, AST-B-25, AST-B-26 | New build |
| **19** | [Edit · Device](wireframes/CR-092-assets-screens.html#screen-19) | `Modal over /:tenant/assets/{id} · PATCH /assets/{id}` | 1 | AST-B-13, AST-B-25, AST-B-26 | New build |
| **20** | [Edit · Cost & value](wireframes/CR-092-assets-screens.html#screen-20) | `Modal over /:tenant/assets/{id} · PATCH /assets/{id}` | 1 | AST-B-13, AST-B-25, AST-B-26 | New build |
| **21** | [Edit · Lifecycle](wireframes/CR-092-assets-screens.html#screen-21) | `Modal over /:tenant/assets/{id} · PATCH /assets/{id}` | 2 | AST-B-13, AST-B-25, AST-B-26 | New build |
| **22** | [Reassign](wireframes/CR-092-assets-screens.html#screen-22) | `/:tenant/assets/{assetId}/reassign &nbsp;·&nbsp; ?unit={id` | 3 | AST-B-26 | Exists behind |
| **23** | [Log repair / maintenance](wireframes/CR-092-assets-screens.html#screen-23) | `/:tenant/assets/{assetId}/maintenance/new &nbsp;— titled L` | 2 | AST-B-04, AST-B-13, AST-B-26 | Exists behind, New build |
| **24** | [Retire · 1 Reason & final read](wireframes/CR-092-assets-screens.html#screen-24) | `/:tenant/assets/{assetId}/retire — step 1` | 2 | AST-B-26, AST-B-28 | Exists behind |
| **25** | [Retire · 2 Replacement](wireframes/CR-092-assets-screens.html#screen-25) | `/:tenant/assets/{assetId}/retire — step 2` | 2 | AST-B-26, AST-B-28 | Exists behind |
| **26** | [Retire · 3 Book value](wireframes/CR-092-assets-screens.html#screen-26) | `/:tenant/assets/{assetId}/retire — step 3` | 2 | AST-B-26, AST-B-28 | Exists behind |
| **27** | [Raise work order](wireframes/CR-092-assets-screens.html#screen-27) | `/:tenant/assets/{assetId}/work-orders/new` | 2 | AST-B-02, AST-B-05, AST-B-10, AST-B-14, AST-B-26, AST-B-27 | Exists behind, New build |
| **28** | [Add an asset · 1 Identity](wireframes/CR-092-assets-screens.html#screen-28) | `/:tenant/assets/new?class=meters` | 2 | AST-B-03, AST-B-26, AST-B-27, AST-B-28 | Exists behind, New build |
| **29** | [Add an asset · 2 Specification](wireframes/CR-092-assets-screens.html#screen-29) | `/:tenant/assets/new?class=meters` | 2 | AST-B-14, AST-B-26, AST-B-27, AST-B-28 | Exists behind, New build |
| **30** | [Add an asset · 3 Assignment](wireframes/CR-092-assets-screens.html#screen-30) | `/:tenant/assets/new?class=meters` | 1 | AST-B-26, AST-B-27, AST-B-28 | Exists behind, New build |
| **31** | [Add an asset · 4 Lifecycle](wireframes/CR-092-assets-screens.html#screen-31) | `/:tenant/assets/new?class=meters` | 1 | AST-B-26, AST-B-27, AST-B-28 | Exists behind, New build |
| **32** | [Add an asset · 5 Review & add](wireframes/CR-092-assets-screens.html#screen-32) | `/:tenant/assets/new?class=meters · POST /assets` | 1 | AST-B-26, AST-B-27, AST-B-28 | New build |
| **33** | [Drafts](wireframes/CR-092-assets-screens.html#screen-33) | `/:tenant/assets?drafts=1 &nbsp;— proposed &nbsp;·&nbsp; GE` | 7 | AST-B-01, AST-B-02, AST-B-03, AST-B-13, AST-B-14, AST-B-15, AST-B-28 | New build, AST-B-02, AST-B-01, AST-B-03, AST-B-13, AST-B-14, AST-B-15 |

⚠ **THREE OF THESE SCREENS NOW EXIST — 05a, 05b and 05c LANDED IN `2.237.5`**
(`CR-092` step 2 wave B lane 1, `DEF-MET-4955`). Their drawings above are still
the REMEDY drawings and are still what the built screens were built to, so they
stay as they are; what has changed is that the code beside them is no longer the
three stacked hand-built tables. Two things in those drawings were deliberately
NOT built and each is recorded on the row it belongs to: the pager's first/last
page control (a shared-table row, OUT OF SCOPE by PO ruling 2026-09-12, its own
CR) and server-side paging of `GET /assets/lifecycle` (`DEF-MET-4962`, still
open — the three tables search, sort, filter and page in the browser over the
whole payload, which the remedy drawing itself says in its own words).

## What a lane does with this

1. **Open the HTML and find your screen** by its number. The anchor is in the table.
2. **Read the drawing beside the code**, not instead of it — the drawing is as-built at a
   commit, the code is now.
3. **Quote the labels into your working notes.** The skill is explicit: *a link gets
   skimmed, a quote gets built.* Half the "screen doesn't match" defects in this repository
   are a correct row reworded by somebody who never saw it.
4. **Where the drawing and B14 disagree, B14 wins** — and you file the difference rather
   than silently following either.

⚠ **FOUR SPECIFICATION NUMBERS ARE WITHDRAWN AND APPEAR IN NO ROW ABOVE:** `AST-B-07`,
`-08`, `-09` (the import runner, out of scope) and `-17` (a registry-wide Work orders tab,
withdrawn the day it was drawn by PO instruction). **The Imports tab is out of scope
entirely** — the registry draws seven tabs and this work covers six.

## What is still NOT drawn, and needs the PO before it is built

**Ten new capabilities were added to scope on 2026-09-12** and several have **no screen
today at all** — an edit address for an asset, the attention strip on the Overview header,
the six per-panel edit dialogs. The skill's rule for that case is the PO's own ruling of
2026-09-10: **draw it, show it, then build — and the middle step is not optional.** Those
drawings are made and put up before any lane builds them; the other twenty-five items build
against the as-built screens above.
