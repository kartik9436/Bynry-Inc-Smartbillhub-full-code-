# B14 · UI & UX conventions — the binding rules for every screen

> **PO ruling 2026-08-16, verbatim:** *"Please ensure UI matches exactly, we are
> using icons instead of text for actions, colors, font, font sizes, description
> 80% space; as per guideline please; I want to see UI consistency every where -
> please make this part of repo"*

**THIS FILE IS THE RULES. `05-prototype/r10-2026-08-16/UI-RULES.md` IS ITS
SOURCE, NOT ITS AUTHORITY.**

The prototype folder is a design artefact stored verbatim — editing it would
destroy the record of what was handed over. So the rules were copied here, where
they can be amended, dated, cited and enforced. **Where this file and the
prototype's copy disagree, THIS FILE WINS**, and every divergence is stamped
below with the ruling that caused it.

**Why this file exists at all:** those twenty rules arrived on 2026-08-16 inside
the r10 bundle, opening with *"anything found violating them is a bug."* That
sentence makes them acceptance criteria over screens **already deployed** — and
for a full day **nothing in this repo enforced, cited or even referenced them.**
That is hard-won law 1 in its purest form: a document claiming a guarantee is
not the guarantee. The PO asked for them to become part of the repo. This is
that.

---

## Status of each rule

**RATIFIED** = repo law, cite it by number. **ENFORCED** = a gate or test fails
when it is broken. The two are different columns on purpose: a rule nothing
checks is a rule that will be broken silently, and saying so is the point.

| # | Rule | Status | Enforced by |
|---|---|---|---|
| 1 | **Exit vs step-back.** A page header's `←` names where it EXITS to ("← Payments"). Inside a stepper, the footer's `← Back` means only *previous step*. The two never share a label | RATIFIED | — |
| 2 | **One page header.** Every screen, including task pages and workflows, uses the shared page-head: kicker, title, optional subtitle, right-aligned actions. ⚠ **2026-10-02 (PO): a details view's or a list's PAGE actions sit here, top-right, on EVERY screen; an Add/Edit wizard keeps its bottom footer (rule 3)** — decision log 2026-10-02 page-actions ruling, carried to Work order details the same day (see rule 11) | RATIFIED | BR-SHL-044 · **kicker: CR-016 gate — ENFORCED, 0** |
| 3 | **Steppers.** Any flow with 2+ stages uses the numbered step rail (clickable when complete) + a wizard-actions footer. Single forms never fake a stepper | RATIFIED | — |
| 4 | **Button grammar.** `+ Noun` opens a creator · `Verb →` navigates/advances · `Verb ✓` commits/writes · `↑` import · `↓` download · `↗` send to an external system | RATIFIED | — |
| 5 | **Two button sizes only** — default and small (12px). No inline font sizes | RATIFIED | **CR-016 gate — ENFORCED**, register `["12px","14px"]` |
| 6 | **Danger tier.** Destructive commits (disconnect, retire, reverse, write-off) use the danger button — outlined accent, filled on hover — never the standard primary | RATIFIED | **ENFORCED on RENDERED OUTPUT for the wizard commit (2026-08-25, DEF-712) and for the CONFIRM DIALOG's commit (2026-08-26, DEF-718)** — `StateFrame` / `WizardFrame` / `DisconnectWizard` / `ConfirmDialog` / `ConfirmDialogTier.dom` / `AssetLifecycle` suites, each reading the button's own `class` attribute in BOTH directions, plus a census pinning all 30 confirm call sites. ⚠ Still unchecked: a commit button that composes NEITHER shared component — see the second amendment below |
| 7 | **Date fields** always use the date input (calendar affordance, keyed entry, Today shortcut). Never a bare text input ⚠ **HALF-ENFORCED SINCE 2026-09-12 (`DEF-MET-4974`).** The kit's `DatePickerField` gained `min`/`max` (`CR-092` wave A) and the four asset action screens now pass the bounds their own SERVER already refuses — log repair `max`=today, retire `min`=install date, reassign `min`=the assignment's start. **The TODAY SHORTCUT half is still unbuilt and is deliberately so:** it is a new control on every date field in the product plus a key in eleven catalogues, and no ruling authorises it. ⚠ **AND A BOUND WITHOUT ITS SENTENCE IS HALF A FIX** — a greyed-out calendar a person cannot account for is the same defect as a greyed-out button with no reason, so each bound ships with one short line saying what it is. | RATIFIED | PARTIAL — `AssetLifecycle.test.tsx` asserts the log-repair bound, including on a page mounted WITHOUT the `today` prop (the way `App.tsx` mounts it). No gate reads rendered output, so the other four inputs are person-checked. |
| 8 | **Dropdowns** share one chevron style; 5+ options are searchable (type-to-filter) | RATIFIED | **CR-016 gate — ENFORCED** for the chevron half, register `nativeSelects: 0`; the searchable half is unchecked |
| 9 | **Multi-select** renders as removable chips + an add control — never a wall of checkboxes | RATIFIED | — |
| 10 | **Required fields** carry the asterisk on the label | RATIFIED | — |
| 11 | **Consequence preview.** Any form writing money, service state or legal notices shows a "what this will do" box before its commit button. ⚠ **AMENDED 2026-10-02 (PO, decision log *"THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP"* (2): *"Move them to the top right like every other screen."*):** this rule places the BOX, never a details screen's ACTIONS. The Work order details screen (`Work-008`) had read it as licence to draw Mark complete · Reassign · Put on hold · Cancel order in a row at the bottom under its consequence box — the only details screen of 166 with page actions at the bottom. Those four now sit top-right in the shared page head like every other details view (rule 2; the 2026-10-02 page-actions ruling), Cancel last in the danger tier (rule 6), behind its confirm dialog as before; the one-sentence consequence box stays in the body where the drawing puts it. A FORM's commit (a wizard footer, rule 3; a dialog) still has the box before its button | RATIFIED | — (Work-008's placement: `OrderDetailPage.dom.test.tsx`) |
| 12 | **Table toolbar.** `[Search…] [All \| filter chips ×] [+ Filter ▾] … [▦ Columns]`. Filters are removable chips; All is the default | RATIFIED | — |
| 13 | **Sorting.** Headers show ⇅; click cycles asc → desc → clear | RATIFIED | — |
| 14 | **Column selector.** ▦ opens show/hide with reorder and Reset | RATIFIED | — |
| 15 | **Row actions are ICONS with tooltips, never text links.** Max 2 visible + `…` overflow. Vocabulary: 👁 view · ✎ edit/note · ⟲ roll back · 🔧 fix · 🖨 print · ✉ send · ⚡ raise work · ✓ assign · − remove | RATIFIED | **CONVERTED 2026-08-20 · G37 — ENFORCED**, plus a browser spec |
| 16 | **Pagination footer on every list table:** `Showing 1–50 of N · Rows per page 50/100/200/500/1000 · ⇤ ← Page x of y → ⇥`. Page size remembered per table. Wizard summary tables are exempt | RATIFIED | shared DataTable |
| 17 | **Empty state** on every list: what is missing, and the action that fills it | RATIFIED | — |
| 18 | ⚠ **Descriptions cap at 80% of the content width** — see the amendment below | RATIFIED (amended) | `--desc-measure` token · **CR-041 · G43 clause (b) — RATCHETED at 50** live `max-w-prose`, the WRONG cap (DEF-900/DEF-1006). May fall, never rise |
| 34 | ⚠ **ONE PAIR OF WORDS FOR *held here* AND *in the books* — **Recorded** and **In the books**, everywhere, in all eleven catalogues** | RATIFIED (`CR-060` C11, 2026-09-02) | UNENFORCED — nothing in this repo reads a sentence against the behaviour it describes. The sweep that minted it found the copy already FALSE on one screen (`DEF-2365`) |
| 35 | ⚠ **A CATALOGUE IS WRITTEN IN ITS OWN LANGUAGE, NOT TRANSLATED FROM ENGLISH.** PO, verbatim, 2026-09-03: ***"When you write multiple language - please ensure you write such a way that it sound like local person language and not mechanical translations of English"***. **The test is whether a clerk who speaks only that language would write the line that way.** Three things this rules out, each one found in the CR-069 grid copy the hour the rule was made: **(a)** an English sentence with the words swapped — *"Adding a provider adds a manifest entry and no React"* rendered word-for-word into Hindi, Japanese and Korean, which is also rule 32's ban on internal code in clerk-facing copy, one language further along; **(b)** English grammar carried across — Japanese and Korean UI labels are NOUNS (*未設定*, *테스트 전*), not translated verb phrases, and German drops the subject the English sentence needs (*"Verbinden Sie die Dienste, die Sie ohnehin schon nutzen"*, never *"die dieser Versorger nutzt"*); **(c)** a term nobody says at work — everyday office Hindi keeps the English loanword a clerk actually uses (*सेट अप नहीं है*), and inventing a pure-Sanskrit equivalent is not more correct, it is less readable. **AND THE HONEST PART: WHOEVER WRITES THE LINES IS USUALLY NOT A NATIVE SPEAKER OF TEN OF THE ELEVEN**, so a catalogue line is `NATIVE-REVIEW-OWED` until somebody who speaks it has read it — say so in the commit rather than implying eleven fluent authors. | RATIFIED (PO 2026-09-03) | UNENFORCED — no gate can read a sentence for register or naturalness, and this is one of the few rules where a gate is not even the right instrument. The cost lands on a person noticing, which is how it was found |
| 36 | ⚠ **THE CAPTURED PACKS GIVE LAYOUT AND DETAIL; `r10` GIVES THE VISUAL STYLE; THE SHARED COMPONENT KIT IS HOW YOU COMPLY.** PO, verbatim, 2026-09-04, on seeing three shipped screens: ***"you ahve to folow the stylegudie that we have approved from R10; style guide na dtailwind component remain same - thi sis not in line with style guide - also toolkit is not align"*** and, naming the split exactly: ***"UI screens layout and details you can folow from Screens that we capture from document, but style guide should be from r10 agreement"***. ⚠ **THIS AMENDS THE RULING OF 2026-09-03 THAT *the pack is the layout authority*** — that ruling stands **for layout and detail** and was never a licence to invent a visual language. `05-prototype/r10-2026-08-16/UI-RULES.md` governs button grammar and its two sizes, the danger tier, the toolbar and its filter chips, row-action icons, the pagination footer, empty states, description width and table type. **Four breaches were live when this was ruled, all of them in code that had passed every gate:** **(a)** the integrations connect modal drew PRODUCTION UI in a wireframe annotation style — `border-dashed border-info-700` with `font-mono uppercase tracking-wider` legends, at four places — so a customer-facing form looked like a sketch of itself; **(b)** *Sign in with Microsoft* was rendered in the **danger colour**, which `r10` rule 6 reserves for destructive commits (disconnect, retire, reverse, write-off) — the loudest colour in the product spent on a sign-in; **(c)** category chips and segmented controls were hand-rolled as raw `<button>` elements while `Button`, `buttonKit`, `FilterBar` and `SegmentedControl` all exist in the kit; **(d)** the portal's Overview drew on/off as bordered word-buttons rather than a control; **(e)** the portal's Branding screen drew *Services shown on the front page* as a **WALL OF CHECKBOXES**, which `r10` rule 9 forbids by name — a multiple-choice field is removable chips plus an add control — and put **Save** in the danger colour, rule 6 again; **(f)** and its preview panel wrapped **one word per line** for eleven lines, which is not a style question at all but a broken column that no test could see, because every suite asserts on text content and text content is identical however it wraps. **The rule in practice: compose the kit. Where the kit lacks a piece, ADD IT TO THE KIT** — one component, one visual decision, every screen — **rather than hand-rolling it in the screen**, which is how four screens acquire four different chips. And a wireframe or annotation style is for a wireframe: nothing dashed, monospaced or labelled like a diagram ships to a utility user. | RATIFIED (PO 2026-09-04) | UNENFORCED at ratification, and **two of the four breaches are mechanically catchable** — the annotation style in a screen under `features/`, and a raw `<button>` where the kit's `Button` would serve. The rest needs rendered output, which is law 6's standing gap |
| 37 | ⚠ **A FIGURE DRAWN IN A WIREFRAME IS AN ILLUSTRATION, NEVER A FACT TO BUILD TO.** PO, verbatim, 2026-09-10: ***"Treat every number drawn in a wireframe as an illustration, never a fact to build to."*** Every unit number, account number, address, date, price, page count and row total inked into a frame is an example of a SHAPE — it says *a unit number goes here and looks like this*, and it says nothing whatever about what any real row holds. **Three things this rules out:** a test that asserts a drawn figure; a fixture seeded from one; and a lane treating two frames that draw the same fact differently as a contradiction needing a ruling. ⚠ **THE THIRD IS WHY THE RULE EXISTS RATHER THAN BEING OBVIOUS.** The units blueprint draws one tenancy as one account and date on page 80 and a different account and year on page 84, and draws a four-day vacancy as a row on the Account frame while the Occupancy frame omits the row and counts it in its own footer. Read as facts those are irreconcilable and the PO ruling of 2026-09-10 (*the frame wins*) cannot settle them, because BOTH sides are frames. Read as illustrations they are not in conflict at all: **build the shape both frames agree on and ignore both sets of figures.** ⚠ **AND IT CUTS THE OTHER WAY TOO** — a lane that asserts `U-01145` because the drawing shows it has written a test about the illustrator's choice of example, which will go red the first time a real utility is seeded and will read as a product defect. | RATIFIED (PO 2026-09-10) | UNENFORCED, and this one is mechanically reachable in a way most of this table is not: a check could refuse a literal drawn from a conformance file's frame block appearing as an expected value in a test. Not built, and not to be built without agreement (PO 2026-09-10: a new gate is the last resort and needs their agreement) |
| 38 | ⚠ **WHERE A DRAWING AND OUR UI RULES DISAGREE ABOUT HOW A FORM IS BUILT, THE UI RULES WIN.** PO, verbatim, 2026-09-10, asked whether the shared dialog should change to match six things the units blueprint draws: ***"if youa re doing a form - go as per our UI rules"***. **This is rule 36's split carried one step further and stated as a general principle rather than a case.** Rule 36 says the captured packs give LAYOUT AND DETAIL while `r10` gives the VISUAL STYLE and the kit is how you comply; a drawing telling you that two fields sit side by side, that help text sits under its input, that the footer puts Cancel on the left, that the header carries a sub-line, what the kicker says, or that the close control is a labelled button rather than `✕` — **is not layout, it is FORM CONSTRUCTION, and B14 plus the component kit already settle it.** **So the drawing loses, the divergence is RECORDED in the conformance file, and nothing is built for it.** ⚠ **THE REASON IT IS A RULE AND NOT A JUDGEMENT CALL: the alternative is a kit change, and a kit change is never local.** Each of those six alters EVERY dialog in the product at once, on the authority of one screen's drawing, with no lane owning the blast radius — which is how a product acquires four different chips (rule 36's own finding). **If the kit genuinely lacks a piece the drawing needs, rule 36 already says what to do: ADD IT TO THE KIT as an opt-in, so nothing existing moves.** ⚠ **AND THE DRAWING IS STILL RIGHT ABOUT WHAT THE FORM CONTAINS.** This rule governs CONSTRUCTION only — which fields, in which order, under which headings, saying what, remains the drawing's to decide and the 2026-09-10 *the frame wins* ruling still governs there. | RATIFIED (PO 2026-09-10) | UNENFORCED — no gate in this repo reads rendered output, and the judgement *is this construction or content* is the part a person makes. What IS mechanical is the consequence: a screen that hand-rolls a control the kit already declares is rule 36's clause and reachable there |
| 39 | ⚠ **ONE SPACING SCALE, AND A FIELD IS LABEL → INPUT → HELPER.** PO, verbatim, 2026-09-11: ***"have a proper padding for each component on the screen. these padding should be universally fit for the product… the components are too much close as well as manage the margins also"***, and on the form half: ***"in the forms for the fields. It starts with the field name. then the input field, and then it should show the helper text below that input field."*** **THE SCALE, ratified as stated:** `--sp-1` 4px hairline inside a chip · `--sp-2` 8px inside a control, cell vertical padding · `--sp-3` 12px cell horizontal padding, step icon gap · `--sp-4` 16px between blocks ⚠ **(NOT between fields — see the 2026-09-12 amendment at the end of this rule)** · `--sp-5` 20px step side padding, KPI cell side padding · `--sp-6` 24px between sections, after a wizard rail · `--sp-7` 32px page bottom. **NO AD-HOC 3 / 7 / 9 / 14 ANYWHERE.** ⚠ **THE TOKEN NAMES ARE `--space-N`, NOT `--sp-N` — AMENDED 2026-09-11, THE DAY OF RATIFICATION.** The scale was never missing, it was MISNAMED: `07-frontend/src/styles/tailwind.css` AND `tokens.css` both already declare `--space-1: 4px · --space-2: 8 · --space-3: 12 · --space-4: 16 · --space-6: 24 · `--space-8: 32` — **six of these seven steps exist today.** The naming is px÷4, so the ONE missing step is **`--space-5: 20px`**. Put to the PO as a recommendation rather than a question; ruled, verbatim: ***"Okay"***. **So a lane ADDS `--space-5` to the scale that exists and creates NO `--sp-N` family.** The `--sp-N` spelling above is the PO's own wording for the SCALE and is kept so the ruling reads as it was given; it is not a token name to implement. ⚠ **THE REASON IS THE REPO'S MOST EXPENSIVE RECURRING FAULT:** two spacing scales in one product is a second copy free to drift, which is the same shape as two OpenAPI schemas (hard-won law 5), two base-charge columns (`DEF-154`) and two figures for one fact (`OQ-238`). **THE ANCHORS, all `getComputedStyle` on the running app:** page 24/16/32 · sidebar 240 · topbar 56 · title 40/800 · tabs margin 16 gap 16 · KPI 16/20 gap 6 · th/td 8×12 · rail margin-bottom 24 · step 16×20 gap 12 · `.input` 6×10 min-h 36. ⚠ **AMENDED 2026-09-11, HOURS AFTER RATIFICATION — THE KPI GAP IS 8, NOT 6.** The anchor as first ratified said `gap 6`, and 6 is not a step of the scale the same rule ratifies. Put to the PO as a contradiction inside one rule; ruled, verbatim: ***"(a). One off-scale value invites the next one. 8 is the nearest step and nobody will see 2px."*** So the KPI anchor reads **16/20 gap 8**. ⚠ **THIS RULING IS NOT GENERALISED TO THE OTHER OFF-SCALE FIGURES IN THIS RULE, DELIBERATELY.** `.input` 6×10 and the field anatomy's 5px and 6px are ALSO off-scale, and rounding them to scale steps would change the **1 : 1 : 4** ratio the PO specified on purpose — the ratio is the point of the field clause, not the individual numbers. They stand as ratified until the PO says otherwise. **FIELD ANATOMY:** label → input **5px** · input → helper **6px** · field → field **20px**, a ratio of ≈ 1 : 1 : 4. ⚠ **DOM ORDER ALONE IS NOT ENOUGH — the helper must READ as attached to the input above it, never to the label below it, and a 3/3/9 rhythm destroys that even with correct markup.** That is why the three gaps are ratified as FIGURES and not as an ordering. ⚠ **THE PO NUMBERED THE FIELD-ANATOMY HALF `R12`, AND THAT COLLIDES:** the customer-portal blueprint's own register already uses `R12` for *"a database id is never shown"* (itself B14 rule 31 inherited). The blueprint's `R` numbers are ITS numbering, not B14's; this is B14 **rule 39** and the `R12` label is recorded here only so a reader meeting it in chat can find it. ⚠ **AMENDED 2026-09-12 — THE RULE CONTRADICTED ITSELF ON THE ONE FIGURE A FORM USES MOST, AND THE ANATOMY WINS.** As ratified, THE SCALE said `--sp-4` **16px between fields** and FIELD ANATOMY said field → field **20px**. Both were in this rule from the day it was written, so every form in the product could cite it and be wrong either way — and none of them was right: `CR-092` step 1 measured **zero of eleven** adjacent field pairs at 20, finding 14px in dialogs and 16px on full-page forms. Put to the PO as a contradiction inside one rule; ruled, verbatim: ***"a) 20 everywhere — the anatomy wins"***. **So field → field is 20px (`--space-5`) EVERYWHERE, and the scale's 16px step governs blocks and sections, never two fields.** The reason the anatomy wins rather than the scale: the PO specified the field clause as a RATIO — 5 : 6 : 20, ≈ 1 : 1 : 4 — and 16 collapses it to 1 : 1 : 3.2, which is the thing the clause exists to prevent. ⚠ **AND THIS IS THE SECOND CONTRADICTION FOUND INSIDE RULE 39 IN TWO DAYS** — the KPI gap of 6 was the first. A rule that ratifies a SCALE and a set of ANCHORS in the same breath will keep producing them, because an anchor is a measurement and a scale is a policy, and nothing checks one against the other. Both were found by measuring the running app, not by reading this file. | **RATIFIED 2026-09-11** | **PARTLY BUILT, STILL UNENFORCED AT THE PIXEL — amended 2026-09-11 by `CR-085` step 2 lane 1 (`01cfb545a`).** This cell read *"entirely unbuilt at ratification"* and *"no `--sp-N` token exists in `tokens.css` today (94 custom properties)"*; both were true when written and neither is now, so they are corrected here rather than left for the next lane to rediscover. **BUILT:** `--space-5: 20px` is declared in `tailwind.css`'s `@theme` AND in `tokens.css` (95 properties), completing the seven steps under the `--space-N` family the same-day amendment ruled on; the customer portal's shared kit measures **label → input 5 · input → helper 6 · `.input` 6×10 min-height 36 · wizard rail 24 · step 16×20 gap 12** in Chromium at 390 and 1280, and `global.css`'s `p { margin-block: 1em }` — worth 13 of the 17px measured under a helper, and a different number at every font size — is scoped out of the portal by `:where([data-portal]) p`, the staff app untouched. **NOT BUILT (portal half):** field → field is 20 only where the kit's own container is used; five portal screens still stack their fields at 12 or 16 (`DEF-CWP-4856`, partially-fixed). ⚠ **THE STAFF FORM KIT'S ORDER AND ITS THREE FIGURES ARE BUILT AND MEASURED — amended 2026-09-12 by `CR-092-BRC01` step 2 wave A.** This cell read *"the STAFF form kit still renders the helper BETWEEN the label and the input in all five field variants across 28 files"*; that was true when written and is not now. `FormModal.tsx`'s five help-bearing variants (`TextField`, `PasswordField`, `SelectField`, `DatePickerField`, `SearchSelectField`) and `CustomFields.tsx`'s multi-select all render **label → input → helper**, and `.modal-body`'s `gap: 14px` — one of the four numbers this rule forbids by name — is `var(--space-5)`. **Measured in Chromium on the deployed join at 1280 AND 1440, 29 fields across five asset screens: label → input **5px** on 18 of 18 helper fields (was 28.59px one-line / 47.19px two-line), input → helper **6px** on 18 of 18 (the gap did not previously exist — the helper was above), field → field **20px** on 11 of 11 adjacent pairs (was 14px in the dialog and 16px on the four full-page forms, and ZERO pairs at 20). The instrument is `10-scripts/render-checks/cr092-lane3-field-anatomy.mjs`** and it was run before and after, so both numbers in this sentence are readings rather than intentions. ⚠ **THE 6px IS WRITTEN AS `mt-1.5`, NOT AS A TOKEN, AND `.field-help`'s OWN MARGIN DID NOT MOVE:** `.field-help` carries TWO roles — the kit's field helper (6 sites) and a standalone muted note (~38 sites in 21 feature files), and only the first has an input above it, so re-spacing the class would have moved a fifth of the product. `DEF-SHL-4921` is **fixed**. ⚠ **STILL UNENFORCED AT THE PIXEL, AND THE NEW CHECK SAYS SO ABOUT ITSELF:** `07-frontend/src/components/fieldAnatomyOrder.dom.test.tsx` asserts the ORDER only — DOM position of the helper against its control, in all six kit sites — because jsdom computes no layout; the 5/6/20 figures still have no gate and are readable only through the instrument above. It was proved red in a worktree pinned at the pre-fix tip `a0b28104a` (8 of its 9 cases failed there, one per variant) before it was trusted green. 32px is still unused anywhere in the portal (`DEF-CWP-4922`). **ENFORCEMENT:** still **NO GATE READS COMPUTED SPACING**, and nothing here changes that. What exists is source-level and says so about itself — `07-frontend/src/portal/components/spacingAnchors.test.ts` asserts the seven steps by name in both files, the ABSENCE of any `--sp-N` family, the portal reset **with its `:where()`**, and the staff rule still standing; each of its four cases was proved red before it was trusted green. The ten anchors themselves are NOT asserted, because measuring them needs a browser and the only instrument this repo has for that is a person with a walkthrough (hard-won law 6). |
| 40 | ⚠ **THE PAGE-HEAD TITLE IS 32px, ON EVERY SCREEN, AND THE SIZE IS SET ON THE ELEMENT RATHER THAN INHERITED FROM ITS TAG.** PO ruling 2026-09-12, verbatim: ***"use 32 pixels — for every ordinary screen"***, confirmed ***"Please use 32 pixels"***. `tokens.css` has carried `--text-h2: 32px; /* page-head title — THE APP DEFAULT, every screen head */` since the type scale was ruled (decision log 2026-08-19), with `--text-h1: 40px` reserved for a full-page wizard title — but **that note was never a rule, and the code never obeyed it.** `PageHeader` rendered a bare `<h1>` and `global.css` sizes a bare `h1` at `--text-h1`, so **136 of the 137 non-test files that mount `PageHeader` drew their title at the wizard size** (`DEF-SHL-4947`, measured 2026-09-12 at `404ae10c0`). ⚠ **THIS IS HARD-WON LAW 1 IN ITS PUREST FORM — *a comment claiming a guarantee is not the guarantee*.** The token sheet asserted an app default for three weeks and nothing made it true. ⚠ **AND THE SIZE IS NOW INDEPENDENT OF THE HEADING LEVEL, WHICH IS THE HALF THAT MATTERS FOR THE NEXT SCREEN.** Before this, the only way to get 32px was `titleAs="h2"`, which DEMOTES the heading — so a screen wanting the right size had to surrender its `<h1>` and leave the document outline with no page title. That is why **exactly one caller ever used it**, and that caller (`TemplateDetail`) passes it for the correct reason: it is drawn inside Settings, which already owns the document's `h1`. Both branches now carry the size; the level answers to the outline and nothing else. ⚠ **NO WIZARD EXCEPTION, DELIBERATELY — rule 2 already settles it.** Rule 2 is RATIFIED and reads *"One page header. EVERY screen, including task pages and workflows"*, and **15 wizards mount this very component**. A second size for them would re-create the defect this rule closes, whose title is *two page-title sizes and nothing splits them by kind*. `--text-h1` remains a token; it is simply not a page head. | **RATIFIED** | **ENFORCED, and by TWO checks that cover different things — neither is sufficient alone.** `components/PageHeader.test.tsx` asserts the component EMITS the size class; it cannot tell you the class renders, because a Tailwind utility written in a file absent from `styles/route-b-migrated.txt` is in the DOM and styles nothing. `10-scripts/render-checks/cr093-page-title-size.mjs` closes that gap by reading `getComputedStyle` against the **built** stylesheet at 1280 and 1440, and carries a `--before` mode that renders the pre-rule markup and MUST fail at 40px (law 7's red proof through the same entry point as the green run). |
| 41 | ⚠ **THE PRODUCT UI MATCHES THE BLUEPRINT EXACTLY. A SCREEN IS BUILT TO ITS DRAWN SPECIFICATION, AND THE ONLY THING THAT REACHES THE PO IS A DRAWING THAT CONTRADICTS A SIGNED RULE.** PO ruling 2026-09-13, verbatim: ***"it is expected that Product UI will match extactly the way it is given in Blueprint document. and most of the time screens are build with specifications. only exception to the rule can be in case any rule or BR is not matching or contrdicting - in such case you can ask us. otherwise Screens in Blue print should match with Product UI screens"***. **THIS IS A DEFAULT, NOT A NEGOTIATION.** A lane does not decide whether a drawing is "a redesign somebody should scope", does not ask whether the drawing is the target, and does not build the nearest thing the code already does. **The drawing IS the scope.** ⚠ **THE ONE LEGITIMATE QUESTION IS A CONTRADICTION, AND IT IS NARROW:** a drawn element that disagrees with a signed rule, a business rule or an earlier PO ruling. That goes to the PO with both sides quoted. A ❄️ FROZEN B4/B5 figure is still **STOP** and a re-sign (HUMAN-GUIDE §6), never a question. **Everything else — layout, grouping, order, labels, which facts appear — is the drawing's and is built.** ⚠ **WHY THIS RULE EXISTS, MEASURED:** the Accounts blueprint redesigned `ACC-02` on 2026-09-10 under four PO rulings, and **nothing was ever scoped to it.** The screen rendered **20 label/value rows** at the commit the blueprint audited (`2824c2e5`) and **the identical 20** three days later at `2.249.3` — so this was never drift or decay, it was a drawing nobody treated as work. The rulings themselves WERE captured (`DEF-GOV-5006`, filed 2026-09-12, severity high, **still open**) and captured is not built. Of the eleven served fields the blueprint counted as reaching no screen, **eight were still referenced nowhere** in the three account-detail files on 2026-09-13 — ageing among them, so a clerk drilling in from a list that shows an Ageing column lost the single fact saying how overdue the account is. ⚠ **AND THE FAILURE THAT PRECEDED IT IS THE REASON THE RULE IS WORDED AS A DEFAULT:** a lane read one frame of a 242-page blueprint, called it "the design", reported the product as having drifted from it, and proposed reversing a PO ruling of 2026-09-03 — three wrong answers in one hour, every one of them a fragment generalised. **A drawing is not evidence about the product and the product is not evidence about the drawing; the rule removes the judgment call between them.** | **RATIFIED 2026-09-13** | **UNENFORCED, AND HONESTLY SO — NOTHING IN THIS REPOSITORY READS A RENDERED SCREEN.** That is the whole hole this rule falls through, and it is named rather than papered over: `tsc`, eslint, every gate and 391 portal cases all passed over a front page with two working doors out of eight. **What is planned is a SCREEN CENSUS** — drive each route in Chromium (installed, with 58 walkthrough scripts already using it), dump every heading, group title, label/value pair and control label in order plus the measured gap between sibling blocks, commit it as text, and diff it against the drawing written as text. Then *how many gaps* is a subtraction with a command behind it rather than a reading. Until that exists, conformance to this rule is a person driving the product (hard-won law 6). |
| 42 | ⚠ **A SCREEN IS BUILT FROM THE DRAWING AS AN IMAGE. EXTRACTED TEXT IS AN INDEX, NEVER THE SPECIFICATION.** PO, verbatim, 2026-09-13: ***"When you use images to create screens your accuracy is higher; hence dont create screens using only Text"***. **This is rule 41's METHOD** — 41 says the product matches the blueprint, and 42 says how you are permitted to read the blueprint. Render the pages and LOOK at them; use the extracted markdown to find your page and to check a spelling, and for nothing else. ⚠ **THE REPO PROVED THIS BEFORE THE RULING EXISTED:** `CR-094`'s own step-1 record reads *"54 pages read as IMAGES at scale 2, never from the text layer"*, and a second says *"prose quoted from the text layer"* is the unreliable half. **The wireframes are VECTOR ART**, so an extractor returns the labels and silently drops everything DRAWN rather than written — which fields sit side by side versus stacked, what is a table and what is a list of facts, column widths, alignment, grouping, emphasis, which column a block is in, where a control sits inside its heading. ⚠ **AND IT LOSES SCREEN BOUNDARIES:** in the Accounts blueprint the extractor gives screens 09 and 10 the same starting page, and 16 and 17 the same — it could not tell where one screen ends and the next begins, which a lane looking at the page sees in a second and a lane reading text cannot know at all. **How, in this container:** `mkdir -p <out>` then `python3 10-scripts/pdf/pdf_render.py <file.pdf> <out> 2 60,61,62` — scale 2 is 2448x1584, scale 4 for a dense table — then open each PNG with the Read tool. `pdftoppm`, `PIL` and `pypdf` all fail here and `10-scripts/pdf/README.md` says why; do not reach for them. ⚠ **THE BLUEPRINT PDFs LIVE ON THE DEFAULT BRANCH, NOT ON A WORKING BRANCH** — six of them — so `git show "origin/<default>:05-prototype/<name>.pdf" > /tmp/x.pdf` first. A lane reporting *"the drawing is not in the repo"* has looked at one branch; that was said on 2026-09-13 and corrected by the PO. | RATIFIED (PO 2026-09-13) | UNENFORCED, and deliberately so: no check can tell whether a person looked at a picture. What IS mechanical is the consequence — rule 41's conformance census (`10-scripts/render-checks/acc02-tab-conformance.mjs`) fails a screen that diverges however the lane read the drawing. **The census covers 12 tabs of ONE screen today; no wizard has a drawn-as-data spec, which is the real gap this rule exposes.** |
| 43 | ⚠ **A PIECE OF UI IS BUILT AS A COMPONENT. STANDALONE CODE INSIDE A PAGE IS NOT REUSE AND IS NOT ENGINEERING.** PO, verbatim, 2026-09-20: ***"make them coponents - dont write stand alone code , engineer it"***. **It was ruled on a measured failure, not in the abstract.** On 2026-09-20 the PO said *"we have it - we have created it for service request move in - use it"* of the move-in applicant capture, and the lane told to reuse it found **120 lines written inline inside a 4,186-line page, importable by nothing** — so "use it" first required extracting a component that should have been one from the start. **The cost is not tidiness: a second host cannot reuse what is not addressable, so the second screen re-implements it, and the two then drift silently.** ⚠ **THE TEST IS ADDRESSABILITY, NOT LINE COUNT** — if a sibling screen needing the same block would have to copy it, it is standalone code however well written. ⚠ **AND THE OBLIGATION RUNS BOTH WAYS: BEFORE BUILDING, LOOK FOR THE COMPONENT**, and where one is found inline rather than extracted, extracting it is part of the job rather than a reason to copy. `apps/tenancy/document_store.py` is the shape to aim for — a named surface (`store`, `for_source`, `reference`, `fetch`, `download_url`) with callers in two modules. `applicantCapture.tsx` is the repair of the failure that produced this rule. **Where two hosts legitimately draw the same block differently, share the FIELD SET and let each host own its construction (rule 38), never fork the block.** | RATIFIED 2026-09-20 | — |
| 44 | ⚠ **THE DRAWING SAYS WHAT IS ON THE SCREEN AND HOW IT IS ARRANGED. OUR UI STANDARD SAYS HOW IT IS BUILT — SPACING, SIZES, THE TYPE SCALE, THE TOKENS AND THE COMPONENT KIT — AND IT WINS EVERY TIME, ON EVERY SCREEN, INCLUDING THE FRAME EVERY SCREEN SITS INSIDE.** PO ruling 2026-09-24, verbatim: ***"please use our ui, styleguide, spacing specifications. all the time , drawing is for how screen will look like you ahve to build it sing our ui standard"***. **THE TWO WORDS THAT DECIDE IT ARE *all the time*.** Rule 38 already gave the UI rules the win where a drawing and our rules disagree about **how a FORM is built**; this is that ruling with its scope removed — **it was never only forms**, and a rule scoped to one kind of screen is read as permission everywhere else (`DEF-1931`'s shape, where a rule naming one channel was read as permission for every other). **RULE 38 IS NOT SUPERSEDED — it is now rule 44's worked case for forms** (side-by-side fields, help under an input, a footer's button order) and its examples still decide those. **HOW IT SITS WITH RULE 41, WHICH IT DOES NOT CONTRADICT.** Rule 41 says the product matches the blueprint EXACTLY and that the only thing reaching the PO is a drawing contradicting a signed rule. *Exactly* is about the drawn **SHAPE** — what is present, in what order, in what grouping, under what heading. A pixel value a drawing happens to carry was never a claim about construction (**rule 37**: a drawn figure is an ILLUSTRATION, never a fact to build to), so a spacing disagreement is **not a contradiction to escalate** — there is nothing to escalate, because the drawing never spoke to it. Rule 41's escalation is still the path for a drawing that genuinely contradicts a signed rule about WHAT is on the screen. **WHAT THE STANDARD IS, IN ORDER:** `07-frontend/src/styles/tokens.css`'s scale · `05-prototype/r10-2026-08-16/UI-RULES.md` for visual style (rule 36) · the shared component kit, which is **how** you comply (rule 36 again) · Tailwind utilities and no new stylesheet class (rule 21). **WHAT SETTLED IT, AND THE FIGURE THE PO WAS SHOWN:** the Finance blueprint's `P2.17` counts **65 off-scale values in 11 files**, of which **25 are in `07-frontend/src/components/AppShell.css`** — the sidebar, top bar and page header every screen sits inside. That file's own header calls its layout *"ported from the signed reference `05-prototype/UtilityBilling.html`"*, and the blueprint warned that changing those is *"a rule change, not housekeeping"*. It was put to the PO as a product-wide change with a worked example — the sidebar at **236px** against a scale holding **224** and **240** — and they ruled the standard applies all the time. **SO THE FRAME IS IN SCOPE AND THERE ARE 65, NOT 40.** ⚠ **TWO THINGS A LANE MUST CHECK RATHER THAN ASSUME, BOTH FOUND WHILE PUTTING THIS TO THE PO.** (1) **`BR-SHL-001` SPECIFIES `240px` / `64px`, WHICH ARE ON THE SCALE** — so the sidebar's own signed widths were never the problem and moving them is NOT what this ruling licenses; the 25 are OTHER ported values in the same file, and **a signed figure is still signed**. (2) **THAT HEADER CITES A FILE THAT NO LONGER EXISTS** — r9 (`05-prototype/UtilityBilling.html`) was DELETED under `DEF-610`, so a comment claiming provenance outlived its source, which is hard-won law 1 and `DEF-524`'s shape exactly. **Neither of these is licence to change a signed number; both are reasons to read the rule rather than the comment.** | **RATIFIED** (PO 2026-09-24) | **UNENFORCED — no gate in this repo reads rendered output.** The nearest thing is `10-scripts/tokens_check.py`, which counts off-scale values in a file set and is an AUDIT, not a gate; Finance `P2.17` is the first work done under this rule and its triage is the baseline |
| 45 | ⚠ **THE NATIVE FIELD APP HAS ITS OWN TYPE RAMP AND ITS OWN TOUCH STANDARD — ONE UI STANDARD, TWO TYPE RAMPS, NEVER TWO DESIGN SYSTEMS.** Same colours, same spacing scale, same font (Archivo, `OQ-272` (a)), same rules; only the text sizes and the touch sizes differ, because the web anchors were measured in a browser at 1280 and 1440 and a 32px title on a 390pt phone wraps to three lines. **Native type ramp:** screen title **22** (web 32, rule 40) · section head **17** (web 20–25) · body **15** (unchanged) · label **13** (unchanged) · micro **12** (web 11, raised for daylight). **Touch standard (built for gloves):** primary action **56pt** · any interactive control **48pt** · icon-only button **48pt** · **8pt** clear between adjacent targets — reversing the 44pt desk minimum. **And a technician taps, never types:** choice chips over text fields, a stepper over a number field, dictation beside every note. Sources: the *SMART360 Next Field App* design, AD-08 (*"One standard, two type ramps"*) and AD-11 (*"Built for gloves, not for a desk"*); field-app rules R38 and R39, both **PO ruled** in the design conversation of 2026-10-20/21; written here as Phase 0 task T-04 at the PO's instruction of 2026-10-21 (*"As per Work to be done -page in artifacts complete phase 0"*). **Scope:** `field-app/` only. Nothing on the web changes, and rule 40's 32px page head still holds on every web screen. Where `shared/tokens.ts` lands, both ramps live in it side by side so a colour or a space changes in one place. | **RATIFIED** (PO 2026-10-20/21) | **ENFORCED in `field-app/` (2026-10-21)** — `field-app/tests/components/` asserts the 22/17/15/13/12 ramp and that every control is ≥ 48pt (56 primary); `tests/tokens/drift.test.ts` fails if `shared/tokens.ts` drifts from `tokens.css`; `tests/components/noLiterals.test.ts` fails on any literal colour or pixel in a component. Each proved red first |
| 32 | ⚠ **A screen has a DESCRIPTION BUDGET — one sentence per section; a stated absence is a `<details>` CLOSED by default; a row never repeats what its own control offers; no rule id or internal code in clerk-facing copy** | RATIFIED (PO 2026-08-31, four times: *"too much content - desctiption is too much for clark to read"*) | `RunGap` is structurally a `<details>` and holds by construction; clauses 1, 3 and 4 are UNENFORCED — no gate reads rendered output. Counted at ratification: step 5 of the bill run carried NINE paragraphs and TWO absence panels; one 24-word sentence printed 93 times |
| 19 | **Search placeholders** read "Search {entities}…" per module | RATIFIED | **CR-041 · G43 clause (a) — ENFORCED, baseline 0.** A list declaring `searchFields` and no `searchPlaceholder` FAILS. ⚠ Source-level only: no check can tell whether the sentence is TRUE (see the amendment below) |
| 20 | **Table type is one size (13.5px) everywhere**; no inline overrides | RATIFIED (⚠ header tier, below) | **CR-016 gate — ENFORCED**, body `["13.5px"]`, header `["12px"]` |

---

## Amendment 2026-08-25 — RULE 6 WAS NOT UNFOLLOWED, IT WAS UNFOLLOWABLE (DEF-712)

**The `danger` variant has existed in `buttonKit` since CR-018 Phase 3 with no
way to reach a commit button.** `WizardFrame` commits through
`StateFrame.WorkingButton`, which took `working` / `children` / `onClick` /
`type` and **no `variant`**, and hard-coded `primary`. So all **nineteen wizard commits in the product** (eighteen
files) — the disconnect wizard included — committed
through a button styled **exactly like Save**, and cutting off a household's
water looked like saving a form.

⚠ **AND THAT IS INDISTINGUISHABLE, IN THIS REPO, FROM A RULE NOBODY HAS GOT TO
YET.** The status table above says most rules are RATIFIED and UNENFORCED
because no gate reads rendered output; a rule that *cannot be obeyed* renders
into the same green. The distinction only became visible because a lane building
`DSC-02` hit the wall and **reported it rather than working around it** — it
refused to draw a second, danger-coloured commit button beside the frame's,
because that loses single-flight (BR-SHL-019), the A18 §3 working state and the
A18 §4 failure-with-entered-state-preserved. Three real guarantees for one
colour is the wrong trade, and the report is what produced the right fix.

**The fix, 2026-08-25:** one optional tier per shared component —
`WorkingButton`'s `variant?: CommitTier` (a narrowed `"primary" | "danger"`, so
a `ghost` commit does not compile) and `WizardFrame`'s `commitVariant?`. Absent
means `primary`, so every wizard that does not declare itself destructive renders
byte-for-byte what it rendered before. `DisconnectWizard` declares `danger`.

**What is CHECKED now, stated narrowly so nobody assumes more.** Three suites
read the RENDERED `class` attribute of the commit button against
`buttonClasses("danger")` — not the prop, because a prop assertion would have
been green on the broken day. They cover: the shared button, the shared frame
(both directions — a declared commit is danger, an undeclared one is primary),
and the disconnect screen itself.

✅ **THE LARGER HALF WAS SWEPT ON 2026-08-26 — see the amendment below.**
`components/ConfirmDialog.tsx` — whose own docstring calls it *"THE one
destructive-action confirm"* and whose example consequence is *"Write off 3
balances?"* — also committed through `WorkingButton` and **passed no tier**,
across **30 non-test call sites**. Filed as `DEF-718` on 2026-08-25 and closed
the next day on the PO's ruling.

---

## Amendment 2026-08-26 — THE CONFIRM DIALOG'S HALF, AND WHY IT IS A CLASSIFICATION AND NOT A SWEEP (DEF-718)

> **PO ruling 2026-08-26, verbatim:** *"A. B14 rule 6 is ratified; the tier
> exists; the only reason they're wrong is that nothing could reach it until
> tonight."*

DEF-712 gave `WorkingButton` an optional tier and reached the **wizard** commits.
`ConfirmDialog` composes that same button and passed **no tier**, so the rule's
largest surface — **30 non-test call sites** that delete, retire, archive,
deactivate and roll back — still committed through a button styled exactly like
Save. The fix is the same shape: one OPTIONAL `confirmVariant?: CommitTier`,
absent meaning `primary`, so a confirm that is not rule 6's subject renders
byte-for-byte what it rendered before.

⚠ **THE OPTIONALITY IS THE RULE, NOT A CONVENIENCE.** Rule 6's subject is the
**destructive** commit. A confirm in front of a **creation, a publish or a send**
is not, and reddening it spends the tier's meaning everywhere the tier is true.
So all thirty sites were classified by hand and the classification is written
down:

| | Count | Sites |
|---|---|---|
| **Destructive — `danger` pinned** | 21 | delete an asset (×2) · roll back an import (×3) · deactivate/delete a premise · deactivate/delete a unit · deactivate a template variant · delete a charge code · **retire** a plan · **retire** a rate schedule · archive a plan · archive a rate schedule · delete a cycle (×2) · deactivate-or-delete a route (×2) · delete a reference entry · remove a holiday |
| **Polymorphic — computed from the action** | 3 | Users & roles (deactivate/remove → danger; reactivate/temp-password → primary) · Plans (archive/delete → danger; **publish** → primary) · Services (disable → danger; **enable** → primary) |
| **Not rule 6's subject — LEFT PRIMARY on purpose** | 6 | bill-run bulk apply · close-export **send** · apply previewed rate changes · run the rate-change preview · forward-only numbering reset · tenant currency change |

The same ruling was taken to cover **`AssetRetireWizard`** — *"Retire {asset} ✓"*
— as the smaller included case: **retire is rule 6's own second named example**,
and that file's own `E4` exception had already reported the commit as primary and
pointed at this sweep. It now declares `commitVariant="danger"`.

**What is CHECKED, stated narrowly.** Every assertion reads the confirm button's
**rendered `class` attribute** against `buttonClasses(...)`, compared **whole**
(`toBe(...)` / `class="…"` with both quotes) rather than by substring — a
substring match cannot see what follows it, which is DEF-182's shape, and an
appended-class mutation was proved RED against the whole-value form. The
polymorphic screens are **clicked open in jsdom**, because a confirm dialog is
state and first paint never renders one. A **census** case pins all thirty sites
so the thirty-first fails until somebody classifies it.

⚠ **AND ONE HOLE STAYS OPEN, NAMED.** These two shared components are now
checked; a commit button that composes **neither** — hand-rolled in a screen — is
still invisible to every gate in this repo, because nothing here reads rendered
output on its own initiative. The status table above says RATIFIED · ENFORCED for
rule 6 on *these paths*, and nothing wider.

---

## Amendment 2026-08-27 — RULES 18 AND 19 GAIN A CHECK, AND IT IS THE FIRST THING IN THIS FILE THAT SWEEPS (CR-041)

> **PO ruling 2026-08-27, verbatim, asked twice in escalating terms:** *"tool bar
> - descrption, search, filter, column seelctor, pagination, export - - we need
> to ensure it behavios in a simialr way everywhere - currently it is lot
> differnt that many places - you ahve to do - where else is this class used the
> same way. and create a task list and fix all those not just report it"*

The status table above has said, since this file was written, that most rules are
RATIFIED and UNENFORCED *"because a rule nothing checks is a rule that will be
broken silently, and saying so is the point."* Two of them stop being that today.

**What the sweep actually found, because the numbers are the argument.**

| | Before | After |
|---|---|---|
| Searchable lists declaring their own prompt (rule 19) | **7 of 23** | **23 of 23** |
| Live `max-w-prose` — the WRONG description cap (rule 18) | **65**, in twelve files | **50**, in five |
| Customer-flow tabs whose filter sits OFF the toolbar row (rule 12) | 4 | **0** |
| List tables that cannot export, saying so | 2 of 8 | **8 of 8** |

**`10-scripts/gates/g43_list_toolbar_contract.py` is the check**, and its two
clauses are deliberately different shapes:

* **(a) rule 19 is an INVARIANT, baseline 0.** Every searchable list carries a
  prompt, so there is no legacy set to grandfather and the twenty-fourth must
  bring its own sentence.
* **(b) rule 18 is a RATCHET at 50.** Fifty `max-w-prose` remain — 41 in the
  service-request family, 7 in a file another lane held — and failing on all of
  them would make the gate red from birth, *"which is how a check earns a
  `# noqa` instead of a fix"* (G31's own words). It may fall and may never rise,
  and **a fall that is not banked in the baseline is also a failure.**

⚠ **WHAT IT CANNOT CHECK, SAID PLAINLY: WHETHER A PROMPT IS TRUE.** r10 draws
`Meter #, address…` on the reads list over a query that filters the meter number
and nothing else (DEF-950). No source-reading check can compare an English
sentence to a `Q()` expression, and one that pretended to would be worse than
none. So CR-041 wrote every prompt from the endpoint's own predicate, read first,
and **filed the three gaps rather than papering over them with copy** —
**DEF-1001** (bills: r10 promises a cycle search nothing serves), **DEF-1002**
(rate changes: two of three declared search fields were never matched),
**DEF-1003** (premises: the server searches a fourth field no story declares).

⚠ **AND ONE PLACE THIS FILE NOW OUTRANKS r10 EXPLICITLY.** r10 line 7193 draws
the reference-data toolbar's placeholder as *"Search this list"* — the generic
sentence rule 19 exists to remove — while the same prototype gives eleven other
lists a sentence naming their fields. **Rule 19 wins and the divergence is
stamped**, in `SettingsReferenceData.tsx` and `SettingsCustomFields.tsx`, on the
precedent rule 20's own amendment set: *"where an r10 rule and a ratified B14
rule disagree, B14 wins and the divergence is stamped."* DEF-510's register row
recorded those two screens as staying on the default *deliberately*; that
sentence is corrected in place rather than deleted.

**⛔ RULE 19'S GRAMMAR IS NOT SETTLED — `OQ-600`, OPEN.** Eighteen prompts read
*"Search …"* as rule 19's text requires; five read a bare field list
(*"Customer, account #, address, or meter #…"*) because those five sentences are
**B18's own**, served verbatim by the server as `search.hint` — rewriting them by
lane fiat would put the drawn prompt and the served hint into disagreement about
one box, which is the drift CR-041 exists to remove. Put to the PO as a copy
call. Nothing is blocked either way.

---

## Rule 21 — NEW UI IS TAILWIND (PO ruling 2026-08-20)

> *"Can you set the rule any new UI/screen we will use Tailwind only going
> forward"*

| # | Rule | Lifecycle | Enforced by |
|---|---|---|---|
| 21 | **A new screen, component or piece of UI is written in Tailwind utilities and adds NO class to a stylesheet.** Existing CSS is untouched by this and shrinks only as a migration phase takes it | RATIFIED | **G31 — the declared-class count is a CEILING (904 at ruling), may fall, never rise** |
| 31 | **NOTHING INTERNAL IS EVER VISIBLE TO A UTILITY USER — not an id, not a rule number, not a path.** That covers a primary or foreign key, a database column name, a **rule, story, defect or question number** (`BR-…`, `US-…`, `DEF-…`, `OQ-…`), a module path, a file name, a function name, an HTTP route and a gate id. Where the reference is genuinely what a user needs — a batch number, a premise number — it has a HUMAN-FACING number and that is what is shown; where neither exists, the field says so in words and the internal value may ride on `title` as evidence. **The provenance is not deleted, it MOVES to the code comment beside the string.** | **RATIFIED 2026-08-30** — PO: *"no Databse ID on screen - that is a rule"*, and, re-affirming their own ruling of 2026-08-19, *"no BR numbers or internal repo references"*. ⚠ **The 2026-08-19 wording is the fuller one and governs**: *"Youa re also adding internal content and BR codes on screen, that is not required; it is application also available to Utility suer why they ned all these details - those are for internal use"* | **ENFORCED — `G28`, in three parts.** Part 1 scans the eleven catalogues (**0 violations, baseline 0 — the surface a user actually reads is CLEAN**). Part 2b sweeps backend strings served verbatim (**20, baseline 24 — below it**). Part 3 counts `raise` sites whose prose carries a reference (**542, baseline 478 — RED, and rising**; `DEF-322`, left red deliberately). ⚠ **A uuid-shaped VALUE in a field is the one thing G28 cannot see**, because it inspects strings and not rendered output. **THAT HALF IS NO LONGER WHOLLY UNENFORCED — `DEF-2716`, 2026-08-31, built it where it was breached.** `10-scripts/render-checks/cr053-bill-surface.mjs` now reads every cell of the bill's lines table and every visible line of its Document tab as RENDERED TEXT and refuses a uuid in either: **7 leaked cells and 1 leaked line before, 0 and 0 after**, each assertion shown RED on the defect first. It covers `S30` alone; every other screen's uuid-shaped value is still unenforced, and the shape to copy is in that file. ⚠ **Read the value as `innerText`, never as markup** — this rule's own sentence puts the internal value on `title`, so a check over the DOM string goes RED on a correct fix and green on the breach. ⚠ **`S15` JOINED `S30` ON 2026-09-01 (`DEF-2412`), AND IT ADDS A CASE NEITHER OF THEM COVERED: THE FRAME BEFORE THE DATA ARRIVES.** The unit screen fetches its plan's NAME and had only the plan's uuid until the response landed, so it printed the uuid — for a moment while loading, and permanently for a plan that could not be read at all. **No test in this repo could see it and none was written badly:** every suite that renders that screen waits for the data and then asserts, and a transient is gone by then. `07-frontend/src/features/metering/UnitPlanIdNeverShows.dom.test.tsx` holds the query OPEN and asserts on the first paint (`neverAnswers()`), then lets it settle, then refuses it — three frames, the uuid absent from `textContent` in all three and present on `title` in two. **So the shape to copy for a FETCHED label is that file, not the S30 script**, and the question to ask of any screen showing a served name is *what does it render in the frame before it has one* |
| 33 | **ON-SCREEN TEXT IS CAPPED BY WHAT IT IS FOR, AND RATIONALE IS NOT ON SCREEN AT ALL.** Five kinds, five caps: a **LABEL or heading** (a name) ≤ **3 words**, no sentence · a **FACT** (a status, an age, a count qualifier, an audit line) ≤ **6 words** · an **INSTRUCTION** (what to type, what to do next, an empty state's next step) ≤ **6 words per sentence** — and **two sentences of six beat one sentence of twelve**, because the second sentence is where *what to do next* lives and cutting it to reach one short line is the failure this cap exists to prevent · a **CONSEQUENCE stated before an irreversible act** ≤ **6 words per sentence, at most two**, and **never cut below clarity** · **RATIONALE** (why the product works this way, why a control is absent, what a rule exists for) = **ZERO words on screen** — it belongs in the code and the register ⚠ **TWO PO RULINGS OF 2026-09-24 SIT ON THIS RULE AND THEY POINT IN OPPOSITE DIRECTIONS. BOTH ARE RECORDED HERE BECAUSE A COPY AUDIT READING ONLY THE CAP WILL "FIX" THE FIRST SET.** **(1) THE MOVE-OUT'S FOUR SHORTFALL PATH NAMES STAY AS DRAWN AND ARE NOT TO BE SHORTENED** — *Pursue it · Put it on a payment plan · Write it off · Tie it back to the master account*. Three break the 3-word heading cap; the PO was shown them and answered *"b) Leave as drawn"*. **(2) THE TRANSFER WIZARD'S FIVE PAGE-HEAD TITLES WERE SHORTENED TO THE CAP** — PO, verbatim: *"Shorten all five to the cap"* — so *Find the account, and who is selling* became **Account & seller**, and *Review — one account, one new owner* became **Review & confirm**. ⚠ **NEITHER IS A GENERAL PRECEDENT AND NEITHER OVERRIDES THE OTHER**: each was ruled on the strings in front of the PO, which is what *a signature covers only what was shown* means for copy. **So an over-cap string is not automatically wrong and not automatically lawful — check whether it has been ruled before touching it.** ⚠ **THE READING OF WHY THEY DIFFER IS OURS, NOT THE PO'S, and is recorded as ours so it can be reopened:** the move-out's four name four *choices* with different money consequences and are the only place each is named; the transfer's five name *the screen you are standing on*, which the step line, the rail and the section heading all say again. **If that reading does not hold for some third case, it goes back to the PO rather than being extended by analogy.** ⚠ **AND ONE MORE THING THE TRANSFER CASE PROVED ABOUT THIS RULE'S OWN ENFORCEMENT: A CAP ALONE IS NOT THE RULE.** *"Sold. Now who?"* is three words and two sentences — within the cap and still a breach of the no-sentence half. A check that counts words and does not also refuse a sentence is this repository's *check that does not check*. Test both halves. ⚠ **(3) ONE MESSAGE IS A PO-RULED EXCEPTION TO THE SIX-WORD CAP — 2026-10-06, `DEF-IDN-9777`.** When a Field Technician signs in to the STAFF web app, the sign-in page's error box and the staff shell's 403 page say, in two sentences of ten words each: **"Field Technicians do not have access to the staff portal."** and **"Please sign in on the Field Technician mobile app instead."**, with one button, **Open the field app**. The PO asked for *"a clear message Field Technicans are suppose to login into Field Technican Mobile app; They dont have access to Staff portal"*, rejected the six-word version with *"We need longner sentence 8 to 10 owords"*, and approved the two sentences verbatim: *"this si correct - please update"*. **SCOPE: THIS ONE MESSAGE ON THOSE TWO SCREENS ONLY. Rule 33 is unchanged everywhere else** — the scope is the coordinator's reading of the PO's choice, recorded in the decision log as ours, and like (1) and (2) above it is **not a precedent**: a third over-cap string goes back to the PO. | **RATIFIED 2026-08-30** — PO: *"it too much content we are publishing … 5 to 6 words - you can define what is reason we are showing this text based on reason you can vary the lenght … one it break the screen 2 for human it is too much to read and understand, high cognative laod"* | **NOT ENFORCED for these five kinds.** `G33` enforces the REFUSAL half — **TIGHTENED FROM 12 WORDS TO SIX PER SENTENCE, PO 2026-08-30** (*"this shuld be 6 words only - not too long"*). Measured that day over all 858 refusals: at twelve, **96%** passed; at six, **29%** do. So the cap binds every NEW or CHANGED string from today, and the **606** that already exceed it go into a baseline FILE that may only shrink — the instrument Parts 1/2/2b of `G28` already use and the one the permanently-red part lacks. A gate for the rest is buildable the same way — count words per key, bucket by key suffix — and the baselines below are measured, not guessed · **EXCEPTION 2026-10-06 (PO-ruled, `DEF-IDN-9777`):** the field technician's wrong-door message — two ten-word sentences on the sign-in error box and the shell's 403 page — and nothing else; see (3) in the rule |

It is the twenty-first rule and the first added since the original twenty. It
exists because a partial Tailwind migration otherwise leaves the product with
two styling systems and no rule about which to use — the one cost of stopping
that does not heal by itself. With rule 21, the CSS surface only ever shrinks.

⚠ **Exceptions are NAMED, in `g31_declared_classes.py`'s `NEW_CLASS_EXCEPTIONS`,
with a reason** — `@keyframes`, `@font-face`, a `:has()` chain Tailwind cannot
express. Raising the baseline instead is how a rule quietly stops being one.

---

## Amendments to the prototype's text

**Rule 18 — 66% → 80%.** PO ruling 2026-08-16: *"make it 80%"*, *"across the
app"*. The prototype's copy still reads 66% and is deliberately left alone.
Shipped as the `--desc-measure` token, which is the single source — before it,
the app capped descriptions **eight different ways** (56ch, 60ch ×3, 68ch, 70ch,
72ch, 78ch), so "the description width" was not one thing anybody could change.
A `ch` cap also drifts against a percentage rule as the viewport grows.

**Deliberately NOT at 80%:** centred empty-state cards, an export tooltip, an
audit callout, and a KPI absent-value. A percentage measure on centred or narrow
text reads worse, not better.

---

## What is actually enforced today — and what is not

**This section is the honest half, and it is why the table above has two
columns.**

**Enforced:** rule 16's pagination and page sizes ride the shared `DataTable`, so
a list built on it inherits them. Rule 18 is one CSS token with seventeen
declarations pointing at it. Rule 2's one-page-header is BR-SHL-044.

**NOT enforced — no gate reads rendered output at all.** Rules 1, 3–15, 17,
19 and 20 are RATIFIED and unchecked. ⚠ **AMENDED 2026-08-27 (CR-041): rule 19
is no longer in that list** — `G43` clause (a) fails a list that declares
`searchFields` and no `searchPlaceholder`, at a baseline of 0. It reads SOURCE,
not rendered output, so the sentence stays true of everything else.
A screen can break any of them and every
gate in the repo stays green. **That is not a theoretical risk:** on 2026-08-16
five reference-data screens returned HTTP 500 with the entire test suite green,
and they were found by clicking. Hard-won law 6 says diffing the running app
against the prototype is done by a human and by nothing else — this table is the
list of things that diff has to cover.

**Rule 15 is "partial" for a specific reason.** Row actions were converted from
text to icons on Services & UoM and on the reference-data lists (CR-003, CR-004),
and the tests assert the **accessible name** survives — which is the right
assertion, because an icon with no name passes a text-absence check and is
unusable without a mouse. **Every other list table in the product is unaudited.**

⚠ **AMENDED 2026-08-20 — THE AUDIT WAS DONE AND THE PO RULED ON WHAT IT FOUND.**
"Every other list table is unaudited" was true when written; it is not any more.
The sweep, by row-action container rather than by button prop:

| | files | tables | buttons |
|---|---|---|---|
| **Icons already** | 4 | 7 | 14 — `SettingsReferenceData`, `SettingsRoutesCyclesTab`, `TemplateCatalog`, `TemplateDetail` |
| **Text still** | 10 | 16 | ~40 — Assets, Premises, Units, Users & roles, Chart of accounts, Charge codes, Plans, Taxes & fees, Accounting, Allocation order, Custom fields, Services |

**PO ruling 2026-08-20:** *"Icons everywhere, per r10 and rule 15… Ends the split —
one product, one convention."* The ten convert. Recorded in the decision log with
the figures shown; **DEF-337** is the defect it closes and **DEF-342** closes with
it, because `row` (0 8px, a word in a table row) and `settings-row` (2px 6px, a
14px square) are one tier once the content is the same — **four button sizes
become three**, which is the first movement rule 5 has ever had.

⚠ **AND ONE PLACE r10 IS DELIBERATELY NOT FOLLOWED.** r10 puts the action's
meaning in `title` alone (`<button class="btn btn-icon-sm" title="Retire">`), which
is mouse-only. Every converted button here carries `aria-label` **and** `title`,
both through `t()`, for the reason the paragraph above already gives. Where r10 and
accessibility disagree, this file rules for the accessible name.

⚠ **AND THE RULE HAS A CHECK NOW — `10-scripts/gates/g37_row_actions.py`.**
It reads three things: a row-actions cell contains only row actions; every
element in `components/RowActions.tsx` writes `aria-label={props.label}`; and no
file outside `components/icons.tsx` declares an `<svg>`. The middle one is the
one that matters, and **its first draft PASSED on the exact defect it was
written for** — it searched the file for the string, and `RowActionLink`'s two
branches carry it too, so deleting the attribute from the component that draws
every row action left the string present twice. It reads each rendered element
now. There is a browser half as well, `07-frontend/e2e/CR-018-rule15-row-actions.spec.ts`,
because a source gate cannot see whether the attribute reaches the DOM.

⚠ **AND THE VOCABULARY IS FOR TABLE ACTIONS ONLY — PO ruling 2026-08-20:**
*"this only for table actions ; not for buttons"*. A row action is a glyph; an
ordinary button says a word, whatever the verb. So the retire ✕ and the delete 🗑
are distinct **in a row**, and a "Retire" button elsewhere on the screen stays
the word. G37 refuses a rule-15 glyph inside a plain `<button>`/`<Button>`.

⚠ **THE VOCABULARY NOW HAS ONE IMPLEMENTATION, AND UNTIL 2026-08-20 IT HAD THREE.**
Rule 15 lists its glyphs in prose and nothing turned that prose into code, so each
converting screen drew its own: the "edit" pencil existed **three times, byte for
byte**, under two names (DEF-348). PO ruling the same day — *"Tailwind, CSS,
STylesheet, UI COmponents - we should ahve only one reference point not two"* —
makes `07-frontend/src/components/icons.tsx` the single source for this row, and a
raw `<svg>` anywhere in `src/features` is now refused by G37. **The shell is the
one named exception** — 7 glyphs at 24×24 stroke 2, a genuinely different family,
filed as **DEF-349** and allowlisted by name rather than by pattern.

---

## The audit this file obliges

The PO asked for consistency **everywhere**, not on the screens that happened to
be touched. So this file is the checklist for a sweep of every screen in the
product, and the sweep's findings become defect rows — not silent fixes.

Priority, highest yield first: **15** (icon row actions) · **16** (pagination) ·
**20** (one table type) · **5** (two button sizes, no inline font size) ·
**6** (danger tier on destructive commits) · **11** (consequence preview before a
money write) · **18** (already tokenised — verify no stragglers).

⚠ **AMENDED 2026-08-19 — THE GATE THAT READS RENDERED OUTPUT NOW EXISTS, AND
THE FIRST THING IT DID WAS PROVE THIS SECTION RIGHT.** The sentence that stood
here said such a gate "does not exist" and that a browser walkthrough was the
only mechanism. `07-frontend/e2e/CR-016-ui-conformance.spec.ts` is that gate
(CR-016, from the PO's *"How many styling, CSS issues are there, can you compare
it with r10"*). It signs in, walks all 21 sidebar destinations plus two settings
sub-tabs, and reads **computed style** — never source.

**What it found on its first run, and these are counts, not impressions:**

| Rule | What it measures | Conforming | **Measured** |
|---|---|---|---|
| 8 | selects whose computed `appearance` is `none` | 0 native | **26 native**, on 10 screens (DEF-309) |
| 20 | distinct computed table font sizes | 1 (13.5px) | **6** — 10px, 11px, 12px, 13px, 13.5px, 14px (DEF-310) |
| 5 | distinct computed button font sizes | 2 (14 + 12px) | **5** — one of them 13.3333px, the browser's own default on a button no rule reaches (DEF-311) |
| 2 | `.kicker` at r10's 11px/uppercase/800 | 0 wrong | **10 wrong**, on 6 screens — and **no stylesheet in the app declares `.kicker` at all**, though 26 files ask for it (DEF-308) |
| — | controls matching a live `.input` | 1 height | **4 heights** — 27, 33, 36, 38px (DEF-313) |

**Why it compares against a live `.input` rather than a hex.** The gate injects
an actual `.input` element into each page and measures it, so retuning a token
moves both sides together and the check keeps asking the only question that
matters: *does every control on this screen look like the design system's
control?* The values that cannot be derived that way — `.kicker`'s 11px, rule
20's 13.5px, rule 5's two tiers — are quoted from r10 with their source line.

**It is a RATCHET, not a pass/fail**, and that is the only honest way to land a
check the product fails today. The counts live in
`07-frontend/e2e/ui-conformance-baseline.json` as EXACT numbers, the discipline
`10-scripts/gates/surface_debt.txt` already uses: a count going **up** is a new
violation, and a count going **down** is *also* red, because a register that
keeps claiming debt it has paid off is how a gate stops being a gate (DEF-077).

**Proved RED before trusted green, twice** (hard-won law 7): first against a
register asserting full conformance, where it printed the whole table above;
then by deleting `appearance: none` from `select.input` — DEF-302's own fix —
rebuilding, and watching it go red naming the exact regression,
`nativeSelects: 26 → 28`. The file was restored and checksum-verified.

**WHAT IT STILL DOES NOT SEE, said plainly.** It walks screens a person reaches
by navigation. It does **not** open modals, wizards or panels, so
`inlineWrappingLabels: 0` is a FLOOR and not a clean bill — the label the PO
photographed lives in a create panel this walk never opens. It reads no pixels
and no colours beyond borders and backgrounds. **Rules 1, 3, 4, 6, 7, 9–17 and
19 remain RATIFIED and UNENFORCED**, so the browser walkthrough is still the
mechanism for those, and this table is still the list that walk has to cover.

---

## How to cite this

`B14 rule N`. Amendments are dated and quoted here, never applied by editing the
prototype's copy. A rule the product cannot yet honour gets a defect row naming
the rule number — not a quiet exception.

---

⚠ **AMENDED AGAIN 2026-08-19 — THE FOUR MEASURED RULES ARE NOW TRUE IN THE PAINT, AND
RULE 20 GAINS A HEADER TIER IT ALWAYS HAD AND NEVER NAMED.**

The section above records what the gate FOUND on its first run. This records what the
remediation slice DID, because a table of findings with no outcome column is how a
finding becomes folklore.

| Rule | First run (2026-08-19) | After the design-system slice |
|---|---|---|
| 8 | 26 native selects on 10 screens | **0** |
| 20 | 6 table font sizes; 10 screens with more than one | body **1** (`13.5px`), header **1** (`12px`), **0** screens mixed |
| 5 | 5 button font sizes | **2** — `12px` + `14px` |
| 2 | 10 non-conforming `.kicker`s, and **no stylesheet declared the class** | **0** — declared once, `07-frontend/src/styles/global.css` |
| — | 4 control heights (27/33/36/38) · 3 foreign controls | **1** (36) · **0** |

### RULE 20 HAS TWO TIERS, AND SAYING ONLY ONE OF THEM WAS THE BUG IN THE RULE

Rule 20's text names one figure, 13.5px. r10's design system names two in the same block:

```
.table    { width:100%; border-collapse:collapse; font-size:13.5px; }
.table th { text-align:left; font-size:11px; letter-spacing:0.08em;
            text-transform:uppercase; ... border-bottom:2px solid var(--color-divider); }
            — 05-prototype/r10-2026-08-16/styles.css
```

So **rule 20's 13.5px is the BODY tier**, and a header tier has always existed and was
never written down. Every table in this product invented its own header size in its
absence — 10px, 11px, 12px and `var(--text-h6)`, with 0.04em, 0.06em and even
`--letter-spacing-heading`'s *negative* tracking. Rule 20 now reads, in full:

> **Table type is one size everywhere: body `--table-font-size` (13.5px), column headers
> `--table-header-font-size` (12px), uppercase at 0.08em tracking over a 2px rule. No
> inline overrides. A `<th>` in a body row or a `<tfoot>` is a CELL, not a header — it
> takes the body tier.**

⚠ **THE HEADER TIER IS 12px AND r10 DRAWS IT AT 11px.** That divergence is deliberate and
rule 5 is the reason: our `DataTable` puts a real `<button class="table-sort">` inside
every sortable header (r10 makes the whole `<th>` the click target and has no button), and
that button inherits the header's size. Measured across 24 screens: **11px header ⇒ 3
button sizes; 12px header ⇒ 2.** 12px is rule 5's own small tier, so the sort control and
its label are one size and neither rule is broken. Full reasoning and the worked figure:
`12-governance/02-decision-log.md`, 2026-08-19. **Put to the PO as OQ-267** — make the
`<th>` itself the sort target and take r10's 11px back, or keep the 1px.

**Two more r10 values were overridden by rule 5, for the same reason and recorded the same
way:** r10's `.settings-tabs button` (13px → **14px**; fourteen real buttons on every
Settings screen) and r10's `.seg-opt` (13px → **12px**; every segment is a `<button>` here,
where r10 uses a label wrapping a hidden input and has no button to count). **Where an r10
rule and a ratified B14 rule disagree, B14 wins and the divergence is stamped** — the same
precedent rule 18's 66%→80% set.

### THE r10 CLASS AUDIT, SO IT IS NOT RE-DERIVED

36 of r10's 51 component classes are declared by no app stylesheet. **Two were defects and
are now declared** (`.kicker`, 63 uses across 26 files; `.table`, 8 uses). **19 are
superseded** by an app class doing the same job under another name. **15 are unreferenced
by this product.** A class nothing references is not a defect — the full three-way mapping
is in the decision log entry above, and re-opening all 36 without reading it is wasted work.

### STILL UNENFORCED, AND THAT IS THE HONEST HALF

Rules **1, 3, 4, 6, 7, 9–17 and 19** remain RATIFIED and UNCHECKED. ⚠ **AMENDED
2026-08-27 (CR-041): strike 19 from that list** — `G43` clause (a) checks it, at
source level, baseline 0; and rule 6 gained its rendered-output checks on
2026-08-25/26 (DEF-712 / DEF-718), so strike that too. The rest stand.
`inlineWrappingLabels: 0`
is a **floor**: the gate walks screens reachable by navigation and opens no modal, wizard or
panel, so the label in the PO's second screenshot is outside what that number can see.

---

## Amendment 2026-08-30 — RULE 33, AND THE NUMBERS COME FROM THE CATALOGUE RATHER THAN FROM AN OPINION

**PO ruling, verbatim:**

> *"Also I want desctption used on screens, in tables, in details view, in audits, it too much content we are
> publishing, I want you to write rules or if there is already a rule reduce the lenght of these messages on
> screen - 5 to 6 words you can define what is reason we are showing this text based on reason you can vary
> the lenght - but too much content on screen - one it break the screen 2 for human it is too much to read and
> understand, high cognative laod"*

**Two harms are named and they are different.** One is LAYOUT — a long string breaks the screen. The other is
the reader — high cognitive load. A cap fixes the first; **deciding what does not belong on screen at all
fixes the second**, and that is why this rule has a zero in it.

### THERE WAS ALREADY HALF A RULE, AND THIS DOES NOT DISTURB IT

`G33` enforces **refusal** copy at **SIX words per sentence**, 2 sentences. ⚠ **THIS PARAGRAPH READ *twelve*
UNTIL 2026-08-31 AND WAS ALREADY STALE WHEN IT WAS WRITTEN.** Twelve came from the PO's ruling of 2026-08-19
(*"these kind of messagesa re okay; you need shorter sentences not long ones"*); the PO **tightened it to six
on 2026-08-30** — *"Refusal copy is short your 12-word ruling - this shuld be 6 words only - not too long"* —
in the same breath as rule 33 above, and rule 33's own status column recorded the new number while this
sentence kept the old one. **A document that states a cap twice and disagrees with itself is worse than one
that states it once**, because a lane reading the prose meets the wrong figure and the gate then refuses work
that looked compliant. Measured over all 850 refusals the day it moved: at twelve, **96%** passed; at six,
**30%** do, so **598** are baselined in `g33_refusal_copy_baseline.txt` — a file that may only shrink — and
the cap binds every NEW or CHANGED string from that day.

Rule 33 covers everything G33 does not, and carries G33's hardest-won clause forward unchanged: **shorten by
deleting RATIONALE, never INSTRUCTION.** Cutting the sentence that says what to do next passes any word count
and makes the message worse — **and six makes that clause matter more than twelve ever did**, which is why
rule 33 says two sentences of six beat one sentence of twelve.

### WHAT THE CATALOGUE ACTUALLY LOOKS LIKE — measured 2026-08-30 over `en.json`

| Kind | Keys | Median | 90th percentile | Longest |
|---|---|---|---|---|
| Help or hint under a field | 464 | 15 | 29 | **45** |
| Description or blurb | 48 | 12 | 26 | 35 |
| Note beside a control | 64 | 6 | 24 | **54** |
| Column heading | 761 | 1 | 2 | 5 |
| Empty state | 146 | 8 | 21 | 41 |
| Audit or history line | 93 | 5 | 19 | 36 |

**The medians are already close to the PO's five or six words. The tails are the defect** — a 54-word note
beside a control, a 45-word hint under a field. So the caps codify what the good strings already do, exactly
as G33's cap did — twelve when this table was measured, six from 2026-08-30 — rather than
imposing a target nobody meets.

### WHY THE VARIATION, SINCE THE PO INVITED IT

The PO said *"based on reason you can vary the lenght"*, so the reason is the axis:

* **A label names a thing.** Three words. It is not a sentence and never was.
* **A fact is read at a glance** — a status, an age, an audit line. Six words, the PO's own number, and the
  measured medians (5 and 6) say the product already agrees.
* **An instruction must survive being shortened.** **SIX PER SENTENCE**, and *two sentences of six beat one
  sentence of twelve* — because *"Choose the day to report on"* needs its verb and its object, and the way to
  keep both is a second short sentence rather than one long one. Cutting to a single *"Choose the day"* and
  stopping is the failure this cap exists to prevent, not the cap being obeyed.
* **A consequence before an irreversible act is the one place brevity loses.** **SIX PER SENTENCE, AT MOST
  TWO**, and never cut below clarity: *"A reading already on file is CORRECTED; the old one is kept"* is what
  stops a clerk overwriting a month of readings. Rule 11 already requires the preview; this stops a word count
  from eroding it.

⚠ **THESE TWO BULLETS READ *"Twelve"* UNTIL 2026-09-19 (`DEF-GOV-5792`) WHILE RULE 33'S OWN STATUS TABLE —
THE AUTHORITY — SAID SIX PER SENTENCE.** The PO tightened the cap on 2026-08-30 in the same breath as rule 33
itself (*"this shuld be 6 words only - not too long"*); the status row was written with the new number and
this prose kept the old one, which is precisely the fault the paragraph above this table names — *"a document
that states a cap twice and disagrees with itself is worse than one that states it once"*. It was found by a
lane sweeping the discount wizard, which read this section, measured against twelve, and would have reported
a clean sweep over strings G33 refuses. **Count the status table; never this prose.**
* **Rationale is zero.** This is the clause that does the work.

### THE ZERO IS THE RULE'S POINT, AND IT IS MEASURED

The two longest strings in the reads upload were **41 words explaining why a checkbox is absent** and **36
words explaining why a field is absent**. Neither told a clerk anything they could act on; both were written
honestly, for a reviewer, and left where a clerk reads them. **Deleting that class took the five upload stages
from 931 words to 425** without losing one thing a clerk uses — measured, in `CR-054`.

**So the test is: can the reader ACT on this sentence?** If not, it belongs in the docstring and the register,
which is what they are for. A screen is not where we explain ourselves.

### WHAT THIS COSTS

Every over-long string is now a defect rather than a preference, and the tails above are real: on the measured
counts roughly **10% of help text, notes and empty states** exceed their cap. **The eleven catalogues move
together** — a shortened English string with ten unshortened translations is the parity failure `G32` already
watches for. And **a gate is buildable**: count words per key, bucket by key suffix, baseline at today's count
and ratchet down, which is precisely how `G33` was built.

## Amendment 2026-09-02 — RULE 34, AND THE SWEEP THAT MINTED IT FOUND A FALSE SENTENCE

**`CR-060` C11, verbatim:**

> *"The product has SIX different phrasings for 'held here but not in the books' — posts nowhere ·
> moves no books · register-derived · kept apart from the totals · nothing reached the books. **Pick
> one pair and use it everywhere.**"*

C11 names `B14` as the home for it in the same breath — *"B14 is the right home; it already governs
clerk-facing copy"* — so the rule is minted here rather than in a module's business rules.

**THE PAIR IS THE CHANGE REQUEST'S OWN, AND IT IS NOT INVENTED HERE.** `CR-060` §8b's R8 spells both
states out for the Costs screen: **"Recorded — held here, not in the books"** and **"In the books —
posted when you enter *paid on*"**. Every other phrasing in the product is now one of those two.

### THE RULE

> **A thing this product is holding but has not posted is RECORDED. A thing that has posted is IN THE
> BOOKS.** Those two words, in that sense, everywhere a clerk can read them — screen copy, empty
> states, toasts, status pills and refusal sentences, in all **eleven** catalogues. No screen says
> *posts nowhere*, *moves no books*, *register-derived*, *kept apart from the totals* or *nothing
> reached the books*.

**WHY IT IS ONE PAIR AND NOT A GLOSSARY.** The six phrasings were each correct where they stood and
each true, and that is exactly the problem: a clerk reading *"moves no books"* on one screen and
*"nothing reached the books"* on another has no way to know they mean the same thing, and every
guess costs a support call. One pair is learnable in a sentence.

### WHAT THE SWEEP CHANGED, MEASURED

**Ten keys × eleven catalogues = 110 values**, on five screens: the Costs register, the close/export
cost line, the asset maintenance cost field, the write-off queue (three states) and its payments-side
twin, the service-request fee quote, the deposit-explanation form and the refund clear note.

### ⚠ AND IT FOUND A SENTENCE THAT HAD BECOME FALSE — `DEF-2365`

The Costs screen printed *"Capturing a supplier invoice records it and moves no books … and in no
trial balance"*, quoting the PO's `OQ-200` ruling that capture posts nothing in R2. **That ruling was
superseded by `CR-060` T6 earlier the same day** — a supplier cost now posts `DR cost / CR cash` on
the day a clerk records it was settled — and the paragraph stayed. **No check in this repo could see
it:** `G18` and `G27` confirm the key exists, resolves and is rendered, and `G15` confirms all eleven
catalogues agree with each other. All three PASS on a sentence that is not true.

**That is the honest status of this rule.** It is RATIFIED and it is UNENFORCED, like most of this
file, and the reason is the same one the status table already gives: **no gate in this repo reads
rendered output**, and none reads a sentence against the behaviour it describes. What the sweep buys
is one vocabulary today; what it cannot buy is a guarantee about tomorrow's copy.

## PROPOSED, AWAITING A PO RULING — NOT RULES YET (2026-08-27)

⚠ **THE COUNT OF BINDING RULES IS THIRTY-ONE SINCE 2026-08-30** — rules 31 and 33 were both ratified that day. — rule 31 was ratified and has moved into the status
table above. Nothing still in this section is
citable as law, nothing here has a Status column entry, and a screen that ignores
it is not in breach. It exists because two defects the PO reported on 2026-08-27
were each fixed by a judgement no rule in this file names, and hard-won law 10
says the judgement goes in the repo before the reply that explains it — otherwise
the next screen makes the same choice with nothing to check it against.

**Both are routed to the PO as open questions.** B14's rules come from PO rulings
(rule 21's own row records the one that made it), and the closing section of this
file forbids the alternative: *"A rule the product cannot yet honour gets a defect
row naming the rule number — not a quiet exception."* Minting rule 30 by lane fiat
would be that exception with better manners.

| Proposed | Rule as put to the PO | Raised by | Question |
|---|---|---|---|
| ~~**30**~~ | ~~A form that does not leave the user's current context opens in a DIALOG.~~ **DECLINED 2026-08-30 — AND THE DECLINE IS THE RECORD.** Asked alongside rule 31, the PO answered the INSTANCE and not the rule: *"for estimate reads - keep it modal"*. In the same sentence they said of rule 31 *"that is a rule"*, so the contrast is deliberate. **The number 30 is deliberately left unused** rather than reassigned, so every existing citation of "rule 31" in `OQ-541` and `DEF-899` still resolves. The next screen facing this choice follows the estimate precedent — three fields, one outcome, returns to the list it was launched from — and there is nothing for a gate to check. **A lane may not mint it on the strength of the instance ruling.** | **DEF-897** | **OQ-540 CLOSED** |
| ~~**31**~~ | **RATIFIED 2026-08-30 — moved into the status table above, per this section's own rule.** | **DEF-899** | **OQ-541 CLOSED** |
| **32** | **A row of controls holds only things a person can PRESS. A status, the reason a control is disabled, an age — any FACT — gets a declared line of its own. A toolbar's first row is rule 12's set plus the IS-9 export and nothing else; a screen's dimension controls go on a declared second row.** | **DEF-1085 · DEF-966 · DEF-1083**: three PO reports on one day, one defect in three frames — a row over capacity with every individual control correct. *"tool bar also not correct on this screen"* · *"buttons are still at wring places - do you ahve rules for button"* · *"UI is broken at Park"*. **Measured:** the reads toolbar is ~1,360px of controls in the ~1,150px a 1,440px laptop leaves; it wrapped, which pushed the ▦ to the left margin, where its 336px panel opened off the screen — the PO's screenshot reads *"OW / HIDE"*. **No rule was broken.** Rule 2 names four things in a page head and rule 12 names five in a toolbar, and neither says a word about how much either may hold — so three lanes touched the reads toolbar without anyone owning its width, and `PageHeader` put a status pill in the ACTION row from its first commit. ⚠ **It would be RATIFIED-AND-UNENFORCEABLE for width:** no gate here reads rendered output (law 6). G43 clause (c) holds the load-bearing half — which SLOT a control is declared in — at baseline zero. | **OQ-631** |

**If either is ruled in, it moves into the status table above with its ruling
quoted and its date — and this row is deleted, not left behind.** A proposal that
outlives its answer is the second copy B14 exists to prevent.
