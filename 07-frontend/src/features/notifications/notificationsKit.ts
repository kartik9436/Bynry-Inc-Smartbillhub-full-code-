// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave C1 — "migrate all five files to Tailwind", the task every
//          screen task in that CR waits behind.
// Screens: SET-09 (Templates) · SET-12 / SET-12D (Notifications) · S8
// Rules:   B14 rule 21 (new UI is Tailwind utilities and adds NO class to a
//          stylesheet; the migration clause is PER FILE) · B14 rule 18
//          (descriptions at 80%) · B14 rule 20 (one table type) · OQ-274
//          (desktop-first, ruled breakpoints only) · G34 (no arbitrary type)
// ───────────────────────────────────────────────────────
// THE UTILITIES THE FIVE NOTIFICATION SCREENS WRITE, IN ONE PLACE.
//
// ── WHY A KIT AND NOT UTILITIES AT EVERY SITE ─────────────────────────────
// `route-b-migrated.txt`'s own header records Phase 3's measurement: repeating
// utilities at 250 sites produced 540 differing properties for shapes that were
// meant to be one. `settings-helper` alone is written 19 times across these
// files. So the shared shapes are named here, exactly as `workflowKit.ts` and
// `buttonKit.ts` name theirs — and `routeBUtilities.test.ts` walks every
// `*Kit.ts` in `src/`, pushing each constant through the REAL Tailwind compiler,
// so a typo here is a test failure rather than an element with no styling.
//
// ── WHAT THIS FILE IS A TRANSCRIPTION OF ──────────────────────────────────
// Every constant below is the CSS rule it replaces, declaration for
// declaration, from `features/tenancy/SettingsPage.css` and `styles/global.css`.
// This is a MIGRATION: the screens must render what they rendered. Three values
// could not cross exactly and each is named where it happens rather than left
// for someone to find in a screenshot:
//
//   1. `.settings-badge`'s `letter-spacing: 0.02em` → `tracking-wide` (0.025em).
//      No ruled `--tracking-*` key holds 0.02em and G34 forbids
//      `tracking-[0.02em]`. At the badge's 11px that is 0.055px per character.
//   2. `.kv-v`'s `font-feature-settings: "tnum" 1` → `tabular-nums`
//      (`font-variant-numeric`). Same rendering, and the arbitrary-property
//      spelling needs quote characters the className grammar cannot read, so a
//      typo in it would be invisible to both readers.
//   3. `.kv` / `.kv-list > li`'s `@media (max-width: 760px)` → `max-sm:`
//      (720px). 760 is G36's ONE allowlisted orphan and it is allowlisted BY
//      NAME for `global.css .chooser/.kv` — authoring a second unruled step in
//      markup is the thing OQ-274 closed. Between 720px and 760px the two
//      notification key/value cards now stay in rows instead of stacking.
//
// ── AND ONE THING THAT IS DELIBERATELY NOT TRANSCRIBED ────────────────────
// `.kv-v` carries `flex: none` AND `white-space: nowrap`, which is correct for
// a COUNT and is the whole of CR-048's most visible defect for a SENTENCE: the
// dispatch card's *"Always on — print is the floor and cannot be switched off"*
// could neither wrap nor shrink, so it left the card and ran across the card
// beside it in `.settings-grid`. The two cases are separated here —
// `KV_FIGURE` and `KV_SENTENCE` — rather than the sentence being shortened.
// `notificationsLayout.dom.test.tsx` resolves the rendered element's classes
// through the stylesheets AND the Tailwind compiler and fails if the value can
// be told not to wrap.

/* ── Prose ────────────────────────────────────────────────────────────────
 * `.settings-helper` and `.panel-hint` are the same ink and the same B14
 * rule 18 measure; only the helper sets a leading of its own. Both carry
 * `data-desc` at their call sites so the CR-007 e2e can still measure every
 * description on the screen without naming a class.
 */
export const DESC =
  "m-0 max-w-measure text-sm leading-normal " +
  "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
export const HINT =
  "m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** `.settings-muted` — the quiet tier: a reason, an "off", an empty list. */
export const MUTED = "italic text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]";

/** `.settings-subhead` — a heading INSIDE a panel, under the panel's own h3. */
export const SUBHEAD = "mx-0 mt-3 mb-1 text-base font-semibold text-text";

/* ── Badges (BR-NOT-001 / BR-NOT-015 a — who owns this wording) ──────────── */
const BADGE_BOX = "ml-2 inline-block border px-2 py-px text-xs leading-prose tracking-wide";
/** `.settings-badge` — the utility's own marking. */
export const BADGE =
  BADGE_BOX + " border-divider text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]";
/** `.settings-badge.settings-badge-muted` — a marking the PLATFORM supplied.
 *  Both are badges; only the ownership differs, so only the ink differs. */
export const BADGE_MUTED =
  BADGE_BOX +
  " border-[color-mix(in_srgb,var(--color-text)_20%,transparent)]" +
  " text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";

/* ── Layout shapes ───────────────────────────────────────────────────────── */
/** `.settings-actions` — the button row under a card's body. */
export const ACTIONS = "mt-2 flex flex-wrap items-center gap-2";
/** `.settings-chips` — the chip/tab strip. ⚠ Its `button.active` companion is a
 *  PARENT rule Route B cannot express; see `TemplateDetail.tsx`, where the
 *  selected tab now says so in the button kit's own variant vocabulary
 *  (DEF-343's fix, applied a second time). */
export const CHIPS = "flex flex-wrap items-center gap-2";
/** `.settings-field` — label FIRST, control second, stacked. */
export const FIELD = "mb-3 flex flex-col gap-1";
/** `.settings-inline-form` — the create form that unfolds under a toolbar. */
export const INLINE_FORM = "mt-3 flex w-full flex-col gap-2 border-t border-t-divider pt-3";
/** `.settings-preview-strip` — the facts above a rendered preview. */
export const PREVIEW_STRIP =
  "flex flex-wrap items-center gap-2 border-b border-b-divider pb-2 text-sm " +
  "text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]";
/** `.settings-tokens` — the merge-field shape list. */
export const TOKEN_LIST = "mx-0 mt-2 mb-0 flex list-none flex-wrap gap-2 p-0 text-sm";
/** `.settings-offer-body` — wording the PLATFORM offers, shown as written: a
 *  contract's own line breaks are part of the document, so it does not reflow. */
export const OFFER_BODY =
  "mx-0 mt-2 mb-0 max-w-measure overflow-x-auto border-l-2 border-l-divider " +
  "bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)] p-3 font-body text-sm leading-body " +
  "whitespace-pre-wrap";

/* ── The disconnect-rights clauses (BR-NOT-015) ──────────────────────────── */
export const CLAUSE_LIST = "mx-0 mt-3 mb-0 list-none p-0";
export const CLAUSE_ITEM = "border-b border-b-divider py-3 last:border-b-0";
export const CLAUSE_HEAD = "flex flex-wrap items-baseline gap-2";
/** ⚠ The `<label>` WRAPS its checkbox, and a wrapping label at `display:inline`
 *  drops its own text onto the control's last baseline — the shape
 *  `inlineWrappingLabels` counts in `e2e/ui-conformance-baseline.json`. */
export const CLAUSE_HEAD_LABEL = "inline-flex min-w-0 cursor-pointer items-baseline gap-2";
export const CLAUSE_TITLE = "font-heading font-semibold";
/** The text a customer receives: a readable measure (rule 18) and quoted. */
export const CLAUSE_TEXT =
  "mx-0 mt-2 mb-0 max-w-measure border-l-2 border-l-divider pl-3 text-base leading-prose text-pretty";
export const CLAUSE_EDITOR = "mt-2 flex flex-col gap-2";

/* ── The key/value card (`.kv-list`, `.kv-k`, `.kv-v`) ───────────────────── */
export const KV_LIST = "m-0 list-none p-0";
export const KV_ROW =
  "flex min-w-0 items-baseline justify-between gap-4 border-b border-b-divider py-2 " +
  "last:border-b-0 max-sm:flex-col max-sm:items-start max-sm:gap-0.5";
export const KV_KEY = "min-w-0 text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
/** A COUNT or a short fact. Tabular figures so a column of numbers lines up,
 *  and it holds its width because "93" beside "1,204" should share a column. */
export const KV_FIGURE =
  "flex-none whitespace-nowrap text-right font-heading font-extrabold tabular-nums max-sm:text-left";
/**
 * A value that is a SENTENCE — and the fix for CR-048's most visible defect.
 *
 * `.kv-v` refuses to wrap AND refuses to shrink (`flex: none`), so a sentence
 * in that slot overflowed its `<li>`, its `.panel`, and the `.settings-grid`
 * track the panel sits in, printing across the card beside it. It must be able
 * to do one of the two; it does both.
 */
export const KV_SENTENCE =
  "min-w-0 whitespace-normal text-right font-heading font-extrabold text-pretty max-sm:text-left";

/* ── The SET-12 matrix columns · CR-048's second visible defect ──────────── */
/**
 * A one-line row was four lines tall because no column on the matrix declared a
 * minimum width: `notifications.rules.timing.ladder` — *"On the escalation
 * ladder below"* — broke onto four lines and the matrix became long to scroll.
 * Table layout is `auto`, so a `min-width` on the `<th>` sizes the column.
 *
 * 13rem ≈ 208px, which holds that string on one line at `--table-font-size`
 * (13.5px); 11rem holds two channel pills side by side.
 */
export const COL_TIMING = "min-w-[13rem]";
export const COL_CHANNELS = "min-w-[11rem]";
/* ⚠ CR-048 wave H — AND THE EVENT COLUMN NEEDED ONE TOO, WHICH IS WHY THE
 * "nothing fires this yet" box read as a red blob rather than a sentence.
 * Measured at 1728×1080: the event column resolved to 131px, the twelve rows
 * carrying BR-NOT-018's 95-character reason were 158px tall each, and the
 * tallest row on the matrix was 222px. A sentence in a 131px column is not a
 * sentence, it is a stripe. 15rem holds the longest event name with that reason
 * on two lines; the neighbouring columns carry `min-width` floors of their own,
 * so the table absorbs the width instead of growing past its card. */
export const COL_EVENT = "min-w-[15rem]";
/** …and the pill itself does not break *"Text message"* across two lines. */
export const CHANNEL_PILL = "pill whitespace-nowrap";
export const CHANNEL_PILL_OFF = CHANNEL_PILL + " " + MUTED;

/* ── CR-048 wave E · the grouped catalog row and the designer ─────────────
 *
 * ⚠ **APPENDED, NEVER INTERLEAVED.** This file is shared with the lane working
 * in `NotificationRules.tsx` and `SettingsNotificationsTab.tsx`; every constant
 * above is untouched and in its original order, and the additions sit in one
 * block at the end so a diff of the two lanes' work does not overlap. The
 * `NOTIFICATIONS_KIT_TOKENS` list below grows by exactly these names.
 */

/** E8 — a panel heading with its PAGE ACTION on the same line.
 *
 *  *"the page action belongs in the title row, and '+ New variant' should not
 *  sit on its own row above the toolbar."* `justify-between` puts the heading
 *  left and the action right; `gap-3` keeps them apart when a long title wraps
 *  the row instead of colliding with the button. */
export const TITLE_ROW = "flex flex-wrap items-center justify-between gap-3";

/** E7 — the name cell of a grouped row: the event heading on its own line
 *  above the surface, rather than the two run together. `flex-col` and not two
 *  block elements, because the cell is a `<span>` inside a `<td>` and a block
 *  child of an inline parent is the shape that collapses under `min-width`. */
export const NAME_CELL = "flex flex-col items-start gap-0.5";

/** E7 — the event's own line: the heading, then its surface count. Baseline-
 *  aligned so the badge sits on the heading's own line rather than riding
 *  above it, which is what `items-center` would do at two different sizes. */
export const EVENT_HEAD = "flex flex-wrap items-baseline gap-2 font-heading font-semibold";

/** E7 — a surface under its event: indented, and quieter than the heading,
 *  so the column reads as a list of surfaces under one document and not as
 *  two documents of equal weight. */
export const SURFACE_LINE = "pl-3 text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]";

/** E1, AMENDED TWICE — the designer's two-column frame: **three fifths of the
 *  screen for the DOCUMENT, two fifths for the wording, and the document
 *  FIRST.**
 *
 *  ⚠ **THE 60 BELONGS TO THE DOCUMENT, AND THAT IS THE PRODUCT OWNER'S OWN
 *  SENTENCE (`DEF-NOT-4457`, 2026-09-07):** *"thi si very importna to achieve -
 *  Preview-first: a big paper showing the real document"*, and, naming the
 *  number this constant carries, *"here 60 is for A big paper showing real
 *  docume nt"*. Measured in Chromium at 1440 before the swap: wording 662px,
 *  document 442px.
 *
 *  ⚠ **THE PARAGRAPH THAT USED TO BE HERE ARGUED THE OPPOSITE, HONESTLY, AND
 *  THE CHAIN IS WRITTEN OUT RATHER THAN LEFT TO BE INFERRED.** E1 asked for a
 *  quarter/three-quarters in the document's favour; CR-076 item 2 read the
 *  PO's *"60"* as the WORDING panel's share on 2026-09-07 and reversed it; the
 *  PO settled it the same day against the running screen. The number 60 appears
 *  in all three readings and only the last one says which pane it is, which is
 *  exactly why the supersession is spelled out here.
 *
 *  ⚠ **AND THE RATIO WAS NEVER THE WHOLE ASSERTION.** `templateDesigner.dom.test`
 *  pinned `[3fr_2fr]` and the walkthrough measured "the rail is 55–65% of the
 *  frame": both were true of the screen with the WRONG pane enlarged, because
 *  neither said which side was which. A ratio check that does not name its
 *  panes passes on its own mirror image (hard-won law 7's second question).
 *  So the frame also fixes the ORDER — the document is the FIRST child now, so
 *  the paper does not jump across the screen when a person presses *Edit
 *  wording*, and both modes put it on the left.
 *
 *  ⚠ **`[3fr_2fr]` AND NOT `[minmax(0,3fr)_minmax(0,2fr)]`, WITH `min-w-0` ON
 *  THE COLUMNS INSTEAD — AND THAT IS THE READABILITY FIX `RULE_LAYOUT` ALREADY
 *  MADE.** They are the two standard cures for the same thing (a track refusing
 *  to shrink below its content and pushing its neighbour off the page) and only
 *  one of them is READABLE BY OUR OWN CHECKS: an arbitrary value containing a
 *  comma produces a class SELECTOR containing a comma, and every selector
 *  parser in this repo (`notificationsLayout.dom.test.tsx`,
 *  `routeBUtilities.test.ts`) splits a selector list on commas — so the old
 *  `lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]` was read as two selectors that
 *  match nothing. It compiled perfectly and no check could see it. Both columns
 *  already carry `min-w-0` (see the two constants below), which is the whole of
 *  what the `minmax(0,…)` was doing.
 *
 *  ⚠ **MAX-WIDTH, NOT MIN-WIDTH (`G107`).** `tailwind.css` says it in capitals:
 *  this theme is DESKTOP-FIRST and every responsive rule is `max-width`, so the
 *  two-column form is the BASE and `max-lg:grid-cols-1` is the override. It read
 *  `grid-cols-1 … lg:grid-cols-[…]` until 2026-09-07 — both forms compile and
 *  render identically at every width, which is exactly why the drift is silent
 *  and why a gate is the only thing that can see it.
 *
 *  ⚠ It stacks below `lg` (1024px) rather than at a step of its own: OQ-274
 *  allows only the ruled breakpoints, and a rail plus a rendered page needs the
 *  large one. Above it, the rail holds its own scroll so a long control list
 *  does not drag the document down with it. */
/*
 *  ⚠ **CR-199-BRC10 · 2026-10-29 — THE WORDING IS ON THE LEFT AND THE DOCUMENT
 *  STILL TAKES THREE FIFTHS.** The redesign's drawing (`02`) puts the Wording
 *  pane first and the Preview second, and that ARRANGEMENT is the drawing's to
 *  decide (B14 rule 44). The PROPORTION is not drawn as a ruling — rule 37
 *  makes a drawn width an illustration — while CR-076 item 2's *"60 is for a
 *  big paper showing real document"* IS a PO ruling, so the document keeps its
 *  60%: `2fr` wording, `3fr` preview. Decision log 2026-10-29 *"screens lane"*. */
export const DESIGNER_FRAME = "grid grid-cols-[2fr_3fr] items-start gap-4 max-lg:grid-cols-1";
/** E1 — the control rail, and the SECOND child since `DEF-NOT-4457`: two
 *  fifths, on the right, beside the document rather than in front of it.
 *  `min-w-0` so its own children may shrink. */
export const DESIGNER_RAIL = "flex min-w-0 flex-col";
/** E1 — the output half, where the rendered document lives. The FIRST child
 *  and the three-fifths one (`DEF-NOT-4457`). */
export const DESIGNER_OUTPUT = "flex min-w-0 flex-col";

/** E2 — the SMS composer's counter line, which sits BESIDE the words being
 *  typed rather than under the save button. */
export const SMS_METER = "mt-1 flex flex-wrap items-baseline gap-3 text-sm tabular-nums";
/** E2 — the counter's warning tier. ⚠ It is a WARNING and never a refusal:
 *  no signed rule says a 161-character SMS is invalid, so nothing truncates or
 *  blocks. What it says is what the extra segment COSTS.
 *
 *  ⚠ **`-700` AND NOT `-500` OR `-600`, AND THE COMPILER IS WHY.** `tokens.css`
 *  declares three steps of this ramp — `--color-warning-100/500/700` — and
 *  nothing else, so `text-warning` and `text-warning-600` are class names no
 *  rule exists for: they render as NOTHING while `tsc`, eslint and any
 *  `toContain("text-warning")` assertion pass over them, which is B14 rule 21's
 *  exact failure mode. This constant was first written `text-warning` and
 *  `routeBUtilities.test.ts` reported it as an orphan; -700 is also the step
 *  the file's own contrast note measures for ink (4.45:1). */
export const SMS_METER_WARN = "font-semibold text-warning-700";
/** E2 — the phone-sized bubble an SMS is previewed in. `max-w-[22rem]` is a
 *  phone's text column, so a body that will wrap on a handset wraps here. */
export const SMS_BUBBLE =
  "mx-0 my-2 max-w-[22rem] whitespace-pre-wrap border border-divider bg-surface p-3 " +
  "text-base leading-body";

/** E2 — the printable page, rendered AS a page: paper, a margin, and a measure
 *  a letter is actually set to. Not a `<pre>` on the page background. */
export const PAPER =
  "mx-0 my-2 max-w-measure whitespace-pre-wrap border border-divider bg-surface p-6 " +
  "font-body text-base leading-body";

/** E2 — the two lines an inbox shows before anything else. */
export const INBOX_LINES = "flex flex-col gap-0.5 border-b border-b-divider pb-2";

/** E4 — a LOCKED block: content the template may never be saved without, drawn
 *  where it will appear rather than enforced only at save time. The left rule
 *  and the tint mark it as not-yours-to-delete without a second control. */
export const LOCKED_BLOCK =
  "mx-0 my-2 max-w-measure border-l-2 border-l-accent " +
  "bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)] p-3 text-sm leading-body";
/** E4 — the padlock line above a locked block's text. */
export const LOCKED_HEAD = "flex flex-wrap items-baseline gap-2 font-heading text-sm font-semibold";
/* ── CR-048 WAVE F · THE TWO NOTIFICATION SCREENS ────────────────────────────
 * APPEND-ONLY. Nothing above this banner is edited or reordered — a sibling
 * lane owns `TemplateCatalog.tsx` and `TemplateDetail.tsx`, which render the
 * constants above, and a reorder here is a silent restyle over there.
 */

/* ── F6 · the template and language pickers were 60px ─────────────────────
 * A clerk saw `Bill re ⌄` and could not tell WHICH template, WHICH language or
 * WHICH version was selected. It is the SAME mechanism as wave C's four-line
 * cells and it needs the same two halves: table layout is `auto`, so a
 * `min-width` on the `<th>` sizes the column, and the control must be told to
 * fill the column its header sized or it shrinks back to its own content.
 *
 * 18rem ≈ 288px holds a catalogue name plus its *"— not published"* suffix on
 * one line at `--table-font-size`; 11rem holds *"English only"* plus the
 * select's chevron.
 */
export const COL_TEMPLATE = "min-w-[18rem]";
export const COL_LANGUAGE = "min-w-[11rem]";
/* ⚠ **AND THERE IS NO SECOND HALF, WHICH IS NOT WHAT THIS LANE FIRST WROTE.**
 * The obvious reading of *"the pickers are 60px"* is that the CONTROL is
 * narrow, so a `PICKER = "input w-full"` constant was written here and a test
 * asserted the select resolved to `width: 100%`. **The test could not fail:**
 * `FormModal.css`'s `.input` has declared `width: 100%` all along, so the
 * assertion was green against the DEFECT as well as against the fix — the
 * shape DEF-182 names, a check whose output cannot distinguish pass from fail
 * and is therefore worse than no check, because it is trusted.
 *
 * The RED run is what said so: every other F6/F7 case failed against this
 * lane's parent commit and that one passed. So the finding is recorded instead
 * of the constant: **the pickers were narrow ONLY because the columns were**,
 * a `<select>` at `width: 100%` of 60px is 60px, and the two `min-width`s above
 * are the whole of the fix. */

/* ── F1 · the flat matrix's own code column ───────────────────────────────
 * `NTF-01` is six characters and must never wrap onto a second line, because a
 * code that wraps stops being scannable, which is the whole reason for having
 * one — so the width and the no-wrap are ONE constant here rather than a
 * `COL_CODE` beside it. A pair of them is a pair a call site can write half of.
 */
export const CODE_CELL =
  "block min-w-[6rem] whitespace-nowrap font-heading font-semibold tabular-nums";

/* ── F7 · the unavailable-channel reason was five lines of red inside a row ──
 * The information is RIGHT — BR-SHL-025 requires a forbidden control to carry
 * its reason — and the place was wrong: `RefusalStrip` is the danger tier and
 * paints a paragraph, so three disabled channels made the channels card taller
 * than the rest of the page put together.
 *
 * One line, in the QUIET tier (`MUTED`'s own docstring names this exact case —
 * *"a reason, an 'off', an empty list"*), with the server's full sentence on
 * `title`. That is the same shape the matrix row already uses for the same
 * fact, and the same shape `RowActions` uses for every disabled row action in
 * the product, so the two halves of this screen stop disagreeing.
 */
export const UNAVAILABLE_REASON = MUTED + " block min-w-0 truncate";

/* ── F2 · channel status is a STRIP, not a card of switches ───────────────
 * The email and text switches are the GO-LIVE GATE. Sitting them in a card
 * beside a matrix of per-event channel toggles made them read as a second copy
 * of the same control, so *"why is nothing sending?"* was asked at the row and
 * answered nowhere. The strip puts the answer across the top of the list, where
 * the question is actually asked.
 *
 * `basis-[16rem]` with `flex-1`: three channels share a row on a wide screen
 * and fall to one column when the tab is narrow, with no breakpoint to rule —
 * OQ-274 only governs the ones that ARE authored.
 */
export const STRIP = "m-0 flex list-none flex-wrap gap-3 p-0";
export const STRIP_ITEM =
  "flex min-w-0 flex-1 basis-[16rem] flex-col gap-1 border border-divider p-3";
export const STRIP_HEAD = "flex flex-wrap items-baseline gap-2";
export const STRIP_CHANNEL = "min-w-0 font-heading font-semibold";
/** ⚠ A SENTENCE, exactly as `KV_SENTENCE` is — see its docstring. This is the
 *  slot *"Always on — print is the floor and cannot be switched off"* now
 *  lives in, so it must still be able to wrap AND to shrink. */
export const STRIP_STATE = "min-w-0 whitespace-normal text-pretty";
/** The waiting COUNT beside it: tabular, and it holds its own width. */
export const STRIP_FIGURE = "flex-none whitespace-nowrap tabular-nums";

/* ── F4 · the rule page gets a real RIGHT RAIL ────────────────────────────
 * The plain-English sentence, the delivery half and the audit note were three
 * cards inside `.settings-grid`'s `repeat(auto-fit, minmax(320px, 1fr))`, so
 * they took whichever track was free and the page had no rail at all. A rail is
 * a COLUMN: it stays beside the body and it does not reflow into it.
 *
 * ⚠ `max-lg:`, NEVER `lg:` — OQ-274 ratified desktop-first and the
 * `--breakpoint-*` namespace is cleared, so a min-width variant would compile
 * to nothing at all (the DEF-974 hazard in variant form).
 *
 * ⚠ **`1fr` AND NOT `minmax(0,1fr)`, WITH `min-w-0` ON THE COLUMN INSTEAD.**
 * They are the two standard cures for the same thing — a grid track refusing to
 * shrink below its content and pushing the rail off the page — and only one of
 * them is READABLE BY OUR OWN CHECKS: an arbitrary value containing a comma
 * produces a class SELECTOR containing a comma, and every selector parser in
 * this repo (`notificationsLayout.dom.test.tsx`, `routeBUtilities.test.ts`)
 * splits a selector list on commas, so `.grid-cols-[minmax(0,1fr)_20rem]` is
 * read as two selectors that match nothing. It compiles perfectly and no check
 * can see it — which is the one property a value in this file must not have.
 */
export const RULE_LAYOUT = "grid grid-cols-[1fr_20rem] items-start gap-4 max-lg:grid-cols-1";
/** Both columns. `min-w-0` is the other half of the `1fr` above: without it a
 *  long unbroken string in the body pushes the rail off the screen. */
export const RULE_COLUMN = "min-w-0";

/* ══ CR-048 wave H · THE PAGE ITSELF WAS THE DEFECT, ONE LEVEL ABOVE ══════
 *
 * ⚠ **THREE WEEKS OF FIXES DID NOT CONVERGE BECAUSE EVERY ONE OF THEM WAS
 * MADE INSIDE THE COMPONENT AND THE BREAKAGE WAS IN ITS PARENT.** Measured in
 * Chromium at 1728×1080 against the running app, not read off the source:
 *
 *   · the template designer's frame rendered **448px inside a 1424px page**.
 *     Its own `DESIGNER_FRAME` split of 1fr : 3fr — the ratio of the day; it
 *     is 3fr : 2fr since CR-076 — was applied CORRECTLY — to
 *     448px — which is how a control rail ends up **108px wide** with one word
 *     per line and "Save as new version" on four lines;
 *   · the notifications list was `330px 330px 330px 330px`, ten sections all
 *     330px, widest : narrowest **exactly 1.00 : 1** — the tell that a page
 *     drawn as "cards and a rail" has no rail at all;
 *   · five tables on that page were 14px, 76px, 200px, 323px and **692px
 *     wider than the section containing them**, which is what the PO
 *     photographed as a table running underneath the next card.
 *
 * The cause in every case is the same: these screens render their whole body
 * inside `settingsShared.PanelGrid` → `.settings-grid`, which is
 * `repeat(auto-fit, minmax(320px, 1fr))` — a legacy EQUAL-COLUMN card grid.
 * It is the right container for a tab that IS a handful of same-sized cards
 * (Company, Users & roles, Security, Regional still are, and are untouched
 * here). **It is the wrong container for a screen that has a layout of its
 * own**, because it hands that layout one 330–448px track and then the
 * screen's own correct proportions are applied inside a cell a third of the
 * page wide.
 *
 * ⚠ **`.settings-grid` ITSELF IS NOT CHANGED, DELIBERATELY.** It is shared by
 * every Settings tab; widening it to fix Notifications would restyle Company,
 * Users & roles, Services and Security in the same commit, which is a worse
 * day than the one being fixed. The three redesigned screens stop being its
 * CHILDREN instead — they compose their own stack out of the two constants
 * below — and the tabs that are genuinely a card grid keep it unchanged.
 * (Verified by measuring Company and Users & roles before and after: 3 × 448px
 * both times.)
 *
 * ⚠ **AND NOTHING IN THIS REPO COULD SEE ANY OF IT.** jsdom performs no
 * layout, so a column collapsed to 108px satisfies every `toContain("flex")`
 * assertion written about it, `tsc` is green and eslint is green. That is
 * hard-won law 6 with a number attached, and it is why the fix ships with
 * `10-scripts/render-checks/cr048-notifications-geometry.mjs` turned from a
 * printer into a set of assertions.
 */

/** The page's own vertical stack — what a screen with a layout uses INSTEAD of
 *  `PanelGrid`. `gap-6` is `.settings-grid`'s own `--space-6`, so the rhythm
 *  between cards is unchanged and only the WIDTHS move. */
export const PAGE_STACK = "flex flex-col gap-6";
/** One column of that page: cards stacked, each free to use the full width of
 *  its column. `min-w-0` because a column holding a wide table must be allowed
 *  to shrink below that table's content — without it the table sizes the
 *  track and pushes the rail off the page. */
export const CARD_COLUMN = "flex min-w-0 flex-col gap-6";
/** A wide table's own horizontal scroller. The page body must NEVER scroll
 *  sideways (nothing in the repo asserts this either), so a table that cannot
 *  fit scrolls inside its own box — the same move `.numbering-scroll` makes on
 *  the numbering screen, which is where this was borrowed from. */
export const TABLE_SCROLL = "max-w-full overflow-x-auto";
/** `DEF-NOT-9667` — a cell holding a value with no break opportunity (an email
 *  address, a provider's error code). `overflow-wrap: anywhere` lowers the
 *  cell's MIN-CONTENT width, which is what an auto-layout table sizes a column
 *  by; `break-word` does not. Measured at 1440 before: one 44-character email
 *  held *Messages needing attention*'s table at 838px in a 752px card, so the
 *  last two columns sat past its edge. */
export const BREAK_ANYWHERE_CELL = "[overflow-wrap:anywhere]";

/* ── H · A REFUSAL MAY NOT SET THE HEIGHT OF THE CARD IT SITS IN ──────────
 * Measured: the platform-wording notice on the notifications list was
 * 238 × 318px carrying 414 characters, and four notices on the template
 * designer were 137–217px tall carrying 266–499. All five computed
 * `max-height: none; overflow: visible`, so a card's height was decided by
 * the longest sentence the server happened to send.
 *
 * ⚠ **THE WORDS ARE NOT THE PROBLEM AND ARE NOT TOUCHED.** `BR-SHL-025`
 * requires a refusal to carry its reason, `DEF-445` is what happens when a
 * stated absence is quietly dropped, and a reason trimmed to "…" is a reason
 * nobody can act on. So nothing is truncated: the sentence is in the DOM in
 * full, selectable, reachable by a screen reader, and a person can read all of
 * it. What is capped is how much VERTICAL SPACE it may take from the card.
 *
 * ⚠ **`10rem` AND NOT `7.5rem`, AND THE DIFFERENCE WAS FOUND BY LOOKING.**
 * 7.5rem was the first draft and it measured fine — every over-tall box came
 * back under the cap. Then the screenshot: the rule page's delivery note is
 * 137px in a 230px rail, so a 120px cap clipped it **17px into its last line**
 * and left half a word showing above a scrollbar. Technically correct, and it
 * reads as a rendering bug. A clamp whose only visible effect is a severed
 * line is the "truncated into meaninglessness" this was written to avoid.
 *
 * `10rem` ≈ eight lines at the body measure — past a paragraph, short of a
 * card. It clears every note that is merely long (137px, 157px, 97px) and
 * still catches every one that was setting the height of its card (318px,
 * 217px, 197px). Below the cap it is invisible: no scrollbar is drawn and the
 * strip looks exactly as it did. It engages only in the case that caused the
 * defect, which is the property a clamp has to have. The house precedent is
 * `FilterBar`'s panel (`max-h-[70vh] … overflow-auto`), same shape, same
 * reason.
 *
 * ⚠ THE RENDER-CHECK'S THRESHOLD IS 170px AND IS DELIBERATELY LOOSER THAN THIS
 * CAP. A gate pinned to the exact value of the thing it checks passes because
 * the two numbers are the same number, not because the screen is right. */
export const REASON_CLAMP = "max-h-[10rem] overflow-y-auto";

/* ── CR-048 wave I · A FACT ON A ROW IS A MARKER, NEVER A PARAGRAPH ───────
 *
 * The PO read the deployed screens and named the same disease five times:
 * *"why so much text"*, *"all these long messages are breaking to UI ... just
 * use 3 or 4 wrods"*. A sentence inside a table cell sets the height of its
 * whole row and wraps at whatever width the column happens to be, so one
 * honest explanation on twelve rows turns a list into a wall.
 *
 * ⚠ **THE FACT IS NOT DROPPED WITH THE PARAGRAPH.** `BR-NOT-018` requires an
 * event nothing fires to be DRAWN AND REFUSED BY NAME, and `BR-SHL-025`
 * requires a dead control to carry its reason — deleting either would put back
 * the exact defect CR-048 was raised to fix. What changes is WHERE the words
 * live: three or four on the row, the whole sentence on `title` and on the
 * detail page the row opens.
 *
 * `whitespace-nowrap` is the load-bearing half and not a flourish: a marker
 * that can wrap is a paragraph again the first time a column narrows, and the
 * render-check asserts exactly one line box per marker. */
export const ROW_MARKER =
  "inline-block whitespace-nowrap text-xs leading-prose " +
  "text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";


/** CR-048 wave I · the KIND column, drawn as icons.
 *
 *  *"on this screen for KInd - can you use Icons - it will save real estate on
 *  screen"* — PO, 2026-08-30. A row of 16px glyphs on ONE line, each carrying
 *  the word it replaced as its accessible name. `whitespace-nowrap` again for
 *  the same reason as `ROW_MARKER`: "Certified print + email" was three lines
 *  in this column and the point of the change is the height it was taking. */
export const KIND_ICONS = "inline-flex flex-nowrap items-center gap-1 whitespace-nowrap";

/** CR-048 wave J · a sub-tab that is ONE card, held at the measure it already had.
 *
 *  The rights wording and the email sender each got a tab of their own (PO,
 *  2026-08-30). Neither has a rail, so `RULE_LAYOUT` would leave a 20rem empty
 *  column, and `PAGE_STACK` alone would stretch a five-field form across the
 *  whole 1392px page — the "one word per line" defect of wave H with the sign
 *  flipped.
 *
 *  **64rem is not a round number somebody liked.** Inside `RULE_LAYOUT` on the
 *  settings tab these two cards rendered in `notifications-main`, measured at
 *  **1056px**; 64rem is 1024px at the default root size, so the move changes
 *  WHICH TAB they are on and not how wide they read. It is a cap rather than a
 *  width, so a narrow window still gets the full column. */
export const SINGLE_CARD = "flex min-w-0 max-w-[64rem] flex-col gap-6";

/* ── CR-076 ADDENDUM · SET-10 IS A DOCUMENT WITH A RAIL, NOT AN EDITOR ──────
 * APPEND-ONLY, like every block above it: `TemplateDetail.tsx` and
 * `TemplateCatalog.tsx` render these constants and a reorder here is a silent
 * restyle over there.
 *
 * The Product Owner compared the running screen with the design and asked for
 * the DEFAULT view to be the rendered document and a narrow rail — the wording
 * form appears only when *Edit wording* is pressed. `DESIGNER_FRAME` above is
 * still the EDIT mode's 60/40 split (CR-076 item 2, unchanged and still ruled);
 * these are the reading mode it now opens into.
 */

/** The reading view: the document, and a narrow rail beside it.
 *
 *  ⚠ **`[1fr_20rem]` AND NOT `[minmax(0,1fr)_20rem]`, FOR `DESIGNER_FRAME`'s
 *  OWN REASON.** An arbitrary value containing a comma produces a class
 *  SELECTOR containing a comma, and every selector parser in this repo
 *  (`notificationsLayout.dom.test.tsx`, `routeBUtilities.test.ts`) splits a
 *  selector list on commas — so the guard reads it as two selectors that match
 *  nothing, and a broken layout passes every check. `min-w-0` on both columns
 *  is the whole of what `minmax(0,…)` was doing.
 *
 *  20rem is the rail: it holds `{{cycle.due_date}}` beside its sample value on
 *  one line, which is what the design's merge-field panel is for. It stacks
 *  below `lg` (1024px) — OQ-274 allows only the ruled breakpoints, and a page
 *  plus a rail needs the large one. */
export const READING_FRAME = "grid grid-cols-[1fr_20rem] items-start gap-6 max-lg:grid-cols-1";
/** The reading view's main column, which is the paper. */
export const READING_MAIN = "flex min-w-0 flex-col gap-3";
/**
 * The reading view's rail — the design's three stacked panels, plus the two
 * that used to stand above the document (`DEF-NOT-4456`).
 *
 * ⚠ **IT IS BOUNDED BY THE SAME `--doc-max-h` AS THE DOCUMENT, AND BOUNDING
 * ONLY THE DOCUMENT WOULD HAVE ACHIEVED NOTHING.** Measured across all 38 rows
 * this tenant's catalogue serves, the biggest element on the screen was
 * `reading-rail` on **33 of them** — the rail was larger than the letter, which
 * is the design's central claim exactly inverted. Giving the DOCUMENT its own
 * scroll box leaves the rail free to grow to its content, so the page goes on
 * scrolling and the rail goes on being the tallest thing on screen. The
 * Product Owner's ruling says the rail STAYS PUT, and a rail that stays put is
 * a rail with a height.
 *
 * `none` when the variable is unset, so a rail mid-mount or in a test renderer
 * is its natural height rather than one pixel tall.
 */
export const READING_RAIL =
  "flex min-h-0 min-w-0 flex-col gap-4 max-h-[var(--doc-max-h,none)] overflow-y-auto " +
  "overscroll-contain [scrollbar-gutter:stable]";

/** THE PAPER. A page, with a page's margins, standing on the surface.
 *
 *  ⚠ **IT IS NOT `PAPER` ABOVE AND BOTH ARE KEPT.** `PAPER` is a
 *  `whitespace-pre-wrap` block at `max-w-measure` — the right answer for the
 *  email body under an inbox's two lines, where the document is a fragment
 *  inside a mock-up of a mail client. This is the whole sheet: it fills its
 *  column, carries a real page margin and an elevation so it reads as something
 *  standing on the desk rather than a bordered div, and it does NOT declare
 *  `whitespace-pre-wrap` because its children are BLOCKS now (see
 *  `templateDocument.ts`) and each sets its own.
 *
 *  `shadow-md` and not `shadow-lg`: the system declares exactly three
 *  elevations and a preview is not a modal.
 *
 *  ⚠ **`bg-neutral-100` AND NOT `bg-surface`, AND THE BROWSER IS WHAT SAID
 *  SO.** `surface` is the CARD colour — `#eae9e9`, which is DARKER than the
 *  page it stands on (`--color-bg` is `#f3f2f2`), so the paper read as a hole
 *  in the page rather than as a sheet on it. Measured at 1440: paper
 *  `rgb(234,233,233)` against a page of `rgb(243,242,242)`. `--color-neutral-100`
 *  (`#f8f4f4`) is the lightest step the ruled palette declares and is the
 *  nearest thing to white it has; nothing here invents a colour, and a literal
 *  `#fff` would be the hex this file's own header forbids. **No DOM check could
 *  have found this** — every class was real and every assertion passed
 *  (hard-won law 6). */
export const DOC_CARD =
  "mx-0 my-2 w-full border border-divider bg-neutral-100 p-10 shadow-md " +
  "font-body text-base leading-body max-sm:p-6";
/** The document's own first line — a letterhead, set as one.
 *
 *  ⚠ **`text-lead` AND NOT `text-lg`, AND THE GUARD IS WHAT SAID SO.** This
 *  constant was first written with `text-lg` — Tailwind's OWN name, which
 *  `tailwind.css` clears with `--text-*: initial` precisely so the product's
 *  type scale is the only one anybody can reach. It compiles, `tsc` is happy,
 *  and a `toContain("text-lg")` assertion would pass over a letterhead rendered
 *  at body size: B14 rule 21's exact failure mode. `routeBUtilities.test.ts`
 *  reported it as an orphan, which is the second time that check has caught a
 *  Tailwind-default type name in this one file (`SMS_METER_WARN` was the
 *  first). `--text-lead` is 16px with the BODY weight, which is what a
 *  letterhead wants — the heading steps at that size carry extrabold. */
export const DOC_MASTHEAD = "m-0 font-heading text-lead font-bold text-text";
/** The accent rule under the letterhead. A `<div>`, not an `<hr>`: an `<hr>` is
 *  a thematic break in the DOCUMENT and this is the page's own furniture. */
export const DOC_RULE = "my-3 h-0.5 w-full bg-accent";
/** A line the author wrote in capitals — their emphasis, given typography. */
export const DOC_HEADING =
  "m-0 mt-4 font-heading text-sm font-semibold uppercase tracking-kicker text-text";
/** A label and the value a merge field put at the end of its line. */
export const DOC_PAIR = "flex min-w-0 items-baseline justify-between gap-6";
/** The value half: right, and tabular so a column of amounts lines up. */
export const DOC_PAIR_VALUE = "flex-none whitespace-nowrap text-right tabular-nums";
/** Everything else — prose, set as prose, keeping the author's own line. */
export const DOC_TEXT = "m-0 whitespace-pre-wrap";
/** The author's own blank line, kept as space rather than collapsed. */
export const DOC_GAP = "h-3";

/**
 * THE DOCUMENT'S OWN SCROLL BOX — the Product Owner's *"you give scroll option
 * in PDF view area"* (ruling 2026-09-07).
 *
 * The pane takes the height left on the screen and scrolls its own contents,
 * like a PDF viewer. The head, the variant tabs, the one caption line and the
 * right rail stay put and stay visible while a clerk reads to the end of a
 * three-page notice.
 *
 * ⚠ **IT DISSOLVED AN ARGUMENT RATHER THAN WINNING IT.** Three earlier answers
 * to *"the document starts too low"* were all about DELETING chrome — trim the
 * Settings heading, unwrap the tab rows, take a template out of the Settings
 * frame — and each cost another screen something. The top edge was only ever
 * load-bearing because everything above it pushed the READABLE AREA off the
 * bottom of the window. With the pane scrolling itself, the top edge stops
 * being a criterion at all and nothing is deleted from any screen.
 *
 * ⚠ **`--doc-max-h` IS MEASURED IN THE BROWSER, NOT WRITTEN HERE.** *"The
 * height left on the screen"* is not a number this file can know: the pane's
 * own top moves when the title wraps, when a refusal appears, when a meta line
 * grows — so a `vh` expression is right at exactly one viewport and wrong at
 * every other. `Reading`/`Designer` set the variable from a layout measurement
 * and re-measure on resize. Falling back to `28rem` if the variable is unset
 * keeps a server-rendered or mid-mount pane usable rather than one pixel tall.
 *
 * ⚠ **`min-h-0` IS LOAD-BEARING AND ITS ABSENCE LOOKS LIKE SUCCESS.** A flex
 * or grid child will not shrink below its content's height by default, so
 * `overflow-y: auto` on it never has anything to overflow: the box simply grows,
 * no scrollbar appears, and every DOM assertion about the scroll container
 * passes over a pane that does not scroll.
 *
 * ⚠ **`overscroll-contain` STOPS THE HAND-OFF.** Without it, reaching the end
 * of the pane silently continues into the PAGE's scroll — the classic broken
 * version of a nested scroller, and the thing that makes a reader lose their
 * place mid-letter.
 *
 * ⚠ **`scrollbar-gutter: stable` AND `overflow-y: auto`, TOGETHER.** The pane
 * has to LOOK scrollable: if the letter appears to end where the frame ends, a
 * clerk believes it does, which is worse than the scrolling this replaced. The
 * gutter reserves the track's width whether or not it is occupied, so the
 * document does not reflow the moment content grows past the box.
 *
 * `print:` resets are not needed — what travels to the print window is the node
 * INSIDE this box (`preview-printable`), which carries no height limit.
 */
export const DOC_SCROLL =
  "min-h-0 max-h-[var(--doc-max-h,28rem)] overflow-y-auto overscroll-contain " +
  "[scrollbar-gutter:stable] border border-divider bg-neutral-100";

/** The head's meta line — `Print + email · All bill runs · last edited …`. */
export const HEAD_META = "flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm";
/** One fact in that line, and the dot before it. */
export const HEAD_META_SEP =
  "text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]";
/** A fact the server does not hold, said in the meta line rather than left out
 *  — `BR-SHL-020`: an absent fact is NAMED, never faked and never blank. */
export const HEAD_META_ABSENT =
  "italic text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";

/** A merge field's TOKEN in the rail — able to wrap, because `{utility_website}`
 *  is seventeen characters of monospace in a 20rem column.
 *
 *  ⚠ **`break-all` IS THE LOAD-BEARING HALF AND THE BROWSER IS WHAT ASKED FOR
 *  IT.** `KV_KEY` already carries `min-w-0`, which lets the SLOT shrink — and a
 *  `<code>` with no break opportunity in it does not shrink with its slot, so
 *  the token simply overprinted the value beside it. Measured at 1440 in a
 *  320px rail: `{utility_website}` and *"Sample utility website"* overlapped by
 *  36px, on a row every DOM assertion passed over. */
export const MERGE_TOKEN = "min-w-0 break-words";
/** The merge rail's ROW — `KV_ROW` with ONE difference, and the difference is
 *  the whole of `DEF-NOT-4455`'s fix.
 *
 *  ⚠ **IT WRAPS.** `KV_ROW` is a non-wrapping flex line, so a 17-character
 *  monospace token and a 28-character sample value in a 320px rail had nowhere
 *  to go but on top of each other — measured at 1440, `{utility_website}` and
 *  its value overlapped by 36px on a row every DOM assertion passed over.
 *
 *  ⚠ **AND WRAPPING IS WHY THE TOKEN NO LONGER NEEDS `break-all`.** The first
 *  fix gave the token `break-all`, which removed the overlap and printed
 *  `{service_add` / `ress}` — a field name broken mid-word is a field name a
 *  person cannot search a template for. With the ROW able to wrap, the value
 *  drops to a line of its own and the token keeps the whole width, so it stays
 *  whole; `break-words` remains only as the last resort for a token longer than
 *  the rail, which no A19 token is. */
export const MERGE_ROW =
  "flex min-w-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 " +
  "border-b border-b-divider py-2 last:border-b-0";
/** …and its SAMPLE VALUE: right, tabular so a column of money lines up, and
 *  able to WRAP.
 *
 *  ⚠ **NEITHER `KV_FIGURE` NOR `KV_SENTENCE`, AND THE TWO ARE WHY.** A merge
 *  sample is a figure on one row (`$123.45`) and a sentence on the next
 *  (*"Sample utility website"*), and the kit's two slots each get exactly one
 *  of those right: `KV_FIGURE` refuses to wrap AND refuses to shrink, which is
 *  CR-048's most visible defect the moment the value is prose; `KV_SENTENCE`
 *  wraps but is `font-extrabold`, which is a heading weight on what is a
 *  sample. Choosing between them by looking at the CONTENT would be reading a
 *  drawing decision out of a served string, which this feature has a rule
 *  against. So one slot that is correct for both. */
export const MERGE_VALUE =
  "ml-auto min-w-0 whitespace-normal text-right tabular-nums text-pretty";

/** One dated entry in the rail's history summary. */
export const HISTORY_ITEM = "flex flex-col gap-0.5 border-b border-b-divider py-2 last:border-b-0";
/** Its date and version — the half this product actually holds. */
export const HISTORY_WHEN = "font-heading text-sm font-semibold";

/**
 * Every token this kit can write, flattened — the same publication
 * `workflowKit.ts` and `buttonKit.ts` make, for the same two-reader reason: a
 * token deleted from a component but left here still has to compile, and a
 * token added to a constant and forgotten here is still reached by
 * `routeBUtilities.test.ts` walking `*Kit.ts` by name.
 */
export const NOTIFICATIONS_KIT_TOKENS: readonly string[] = [
  DESC,
  HINT,
  MUTED,
  SUBHEAD,
  BADGE,
  BADGE_MUTED,
  ACTIONS,
  CHIPS,
  FIELD,
  INLINE_FORM,
  PREVIEW_STRIP,
  TOKEN_LIST,
  OFFER_BODY,
  CLAUSE_LIST,
  CLAUSE_ITEM,
  CLAUSE_HEAD,
  CLAUSE_HEAD_LABEL,
  CLAUSE_TITLE,
  CLAUSE_TEXT,
  CLAUSE_EDITOR,
  KV_LIST,
  KV_ROW,
  KV_KEY,
  KV_FIGURE,
  KV_SENTENCE,
  COL_TIMING,
  COL_CHANNELS,
  COL_EVENT,
  CHANNEL_PILL,
  CHANNEL_PILL_OFF,
  // ── CR-048 wave E, appended in the order they are declared above ────────
  TITLE_ROW,
  NAME_CELL,
  EVENT_HEAD,
  SURFACE_LINE,
  DESIGNER_FRAME,
  DESIGNER_RAIL,
  DESIGNER_OUTPUT,
  SMS_METER,
  SMS_METER_WARN,
  SMS_BUBBLE,
  PAPER,
  INBOX_LINES,
  LOCKED_BLOCK,
  LOCKED_HEAD,
  // ── CR-048 wave F, appended in the order the block above declares them ──
  COL_TEMPLATE,
  COL_LANGUAGE,
  CODE_CELL,
  UNAVAILABLE_REASON,
  STRIP,
  STRIP_ITEM,
  STRIP_HEAD,
  STRIP_CHANNEL,
  STRIP_STATE,
  STRIP_FIGURE,
  RULE_LAYOUT,
  RULE_COLUMN,
  // ── CR-048 wave H, appended in the order the block above declares them ──
  PAGE_STACK,
  CARD_COLUMN,
  TABLE_SCROLL,
  REASON_CLAMP,
  // ── CR-048 wave I, appended in the order the block above declares them ──
  ROW_MARKER,
  KIND_ICONS,
  // ── CR-048 wave J, appended in the order the block above declares them ──
  SINGLE_CARD,
  // ── CR-076 addendum, appended in the order the block above declares them ─
  READING_FRAME,
  READING_MAIN,
  READING_RAIL,
  DOC_CARD,
  DOC_MASTHEAD,
  DOC_RULE,
  DOC_HEADING,
  DOC_PAIR,
  DOC_PAIR_VALUE,
  DOC_TEXT,
  DOC_GAP,
  DOC_SCROLL,
  HEAD_META,
  HEAD_META_SEP,
  HEAD_META_ABSENT,
  MERGE_TOKEN,
  MERGE_ROW,
  MERGE_VALUE,
  HISTORY_ITEM,
  HISTORY_WHEN,
]
  .join(" ")
  .split(/\s+/)
  .filter((token) => token !== "");
