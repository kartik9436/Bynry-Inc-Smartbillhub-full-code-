#!/usr/bin/env python3
"""G31 — every class a component asks for must be declared by a stylesheet.

WHY THIS GATE EXISTS
--------------------
A React component says `className="bil-layout-card"`. If no stylesheet declares
`.bil-layout-card`, the browser applies nothing and the screen renders as
flowing unstyled text. Now count what can see that:

    tsc        — a string is a string.               Clean.
    eslint     — a string is a string.               Clean.
    vitest     — `toHaveClass("bil-layout-card")`    PASSES. The class is on
                 the element. Nobody asked whether it MEANS anything.

So the product ships a screen that looks broken to a customer and healthy to
every automated check the repo owns. This is not hypothetical and it is not
rare: DEF-244, DEF-305, DEF-308, DEF-314 and DEF-315 are all this one shape,
recurring across five months, each found by a human looking at a screenshot.
DEF-308 alone was 26 files asking for `.kicker` — including the shared
PageHeader, so it was on nearly every screen in the product.

The lane that filed DEF-314 and DEF-315 on 2026-08-19 said this in its handover:
*"The one check I'd add next, needing no browser: every className in *.tsx vs
every class declared in *.css, fail on the difference."* This is that check.

WHAT IT MEASURES
----------------
DECLARED: every `.name` appearing in any `.css` under 07-frontend/src, comments
stripped. Deliberately generous — it does not care whether the selector is
reachable, only whether the name is claimed somewhere.

REFERENCED: class name literals in `className=`. Two forms:
  * `className="a b"`     — every token.
  * `className={expr}`    — every string literal inside, EXCEPT those that are
    operands of a comparison. `className={row.state === "auto" ? … : "pay-row-
    attention"}` asks for `pay-row-attention`; `"auto"` is a state value that
    happens to sit in the same braces. Not excluding those produced the first
    draft's only false positive, and a gate with a false positive is worse than
    no gate because it gets switched off (DEF-323's lesson, one register over).

⚠ AND THE STATIC CHUNKS OF AN INTERPOLATED TEMPLATE, WHICH THE FIRST DRAFT
DROPPED — the blind spot that would have let DEF-327 survive its own fix.
The literal reader only accepted a backtick string with no `${` in it, so

    className={`rd-source-card${sel ? " is-selected" : ""}`}

reported `is-selected` and `is-blocked` and NOT `rd-source-card` — the class
that actually draws the card. The upload-reads wizard is one of the eight
screens DEF-327 names, and a lane fixing it from this gate's output would have
declared the three classes AROUND the card, left the card undeclared, and
shipped the screen still broken with the gate green. Found by re-reading the
regex while fixing DEF-327, not by the gate.

A token ending in `-` is DROPPED: `svc-`, `met-tag-`, `skeleton-` and three
others are prefixes completed at runtime (`svc-${service}`), not class names,
and counting them would be six false positives — the thing this gate must not
have. Measured: the widening finds exactly one real name and those six
prefixes, and the trailing-dash rule separates them cleanly.

⚠⚠ AND THE FIRST ATTEMPT AT THAT WIDENING TRADED ONE BLIND SPOT FOR ANOTHER —
which is the more useful of the two lessons, because the gate stayed GREEN
through it. Reading templates with a single alternation
(`"…" | '…' | `…``) makes the backtick branch consume the template WHOLE, so
the quoted strings inside its `${…}` are swallowed with it. On this exact call
site:

    className={`chooser-option${sel ? " is-selected" : ""}${
      blocked ? " is-blocked" : ""
    }`}

the first widening gained `chooser-option` and SILENTLY LOST `is-selected` and
`is-blocked`, which the narrower original had been finding — by accident,
because its backtick branch failed to match and it fell through to the quoted
branch. Referenced-class count went 871 → 870 while looking like an
improvement. It was caught by tallying how each of DEF-327's 125 names was
resolved and finding `is-blocked` in the "renamed away" column when nothing
had renamed it.

So the expression is read by TWO separate passes, and it has to be two:
  (a) `_QUOTED` over the whole expression — finds a state class wherever it
      lives, including inside an interpolation;
  (b) `_TEMPLATE` + `_INTERPOLATION` split — finds the static base class at
      the front of a template.
Both are proved RED on a planted `` `def327-base-class${s ? " def327-state-class" : ""}` ``:
the gate must report BOTH names, not one. If a future edit makes it report
one, that edit is this bug again.

THE RATCHET
-----------
125 classes were undeclared when this gate was written. Failing on all of them
would have made it red from birth, which is how a check earns a `# noqa`
instead of a fix. So the count is BASELINED: the gate fails when it RISES.
`--list` prints the current set grouped by file so a lane knows what it buys.

⚠ THE BASELINE IS NOW **ZERO** (DEF-327 fixed, 2026-08-19), AND THAT CHANGES
WHAT THIS FILE IS. At 125 it was a debt register. At 0 it is an INVARIANT: the
next component that asks for a class no stylesheet declares turns this red on
the commit that adds it, which is the first time in this repo's history that
has been true. Six recurrences (DEF-244, DEF-305, DEF-308, DEF-314, DEF-315,
DEF-327) were each found by a human looking at a screenshot; none of them can
reach a screenshot again.

So DO NOT RAISE IT. A class that genuinely cannot be declared does not exist —
if a component asks for a name, either a stylesheet owes it a rule or the
component should not be asking. Raising this number to land a story is
re-opening a defect that took five months and eight screens to close.

⚠ AMENDED 2026-08-19 BY CR-018 PHASE 1 — THE ONE CASE WHERE A CLASS GENUINELY
CANNOT BE DECLARED BY A STYLESHEET
--------------------------------------------------------------------------
The paragraph above says such a class "does not exist". Under Route B (PO
ruling 2026-08-19) it does: a Tailwind utility is declared by the COMPILER, and
no `.css` under src/ will ever name `flex` or `items-end`. The first migrated
component took this gate from 0 to 25 while being entirely correct.

The ratchet is NOT lowered — lowering it would blind the gate to the other 126
components and re-open DEF-327 for a seventh time. Instead the migrated files
are named in `07-frontend/src/styles/route-b-migrated.txt` and handed to
`src/styles/routeBUtilities.test.ts`, which asks the STRICTER question because
it can reach the compiler: declared by a stylesheet OR generates a real rule.
This gate keeps its exact rule, its ratchet of 0, and its jurisdiction over
every component that has not been migrated. See `route_b_migrated()`.

**So the CR's plan for this gate was inverted, and that is worth knowing before
Phase 2 is sized.** CR-018 §4.3 and the Route B ruling both say G31 "becomes
meaningless" and is retired at the END of Phase 3. It is the START that breaks
it, on component 1 of 127.

⚠ AMENDED 2026-08-20 — THE GRAMMAR IS NO LONGER WRITTEN IN THIS FILE (OQ-277)
-----------------------------------------------------------------------------
The handover above created a SECOND reader of the same grammar, in a second
language, in a workflow that shares no runtime with this one. Neither can be
deleted (they ask different questions) and neither can call the other
(`gates.yml` installs Python and nothing else; `ci-frontend.yml` runs node and
nothing else). The cost was measured, not feared: **three corrections to this
grammar have each landed in ONE language** — the comparison operand (130 vs the
true 125), the interpolated template (871 -> 870, which LOST two real classes
while looking like an improvement), and G34's newline anchor.

So the five shared regexes now come from `07-frontend/classname-grammar/
patterns.json`, and BOTH readers assert the same golden corpus — this one in
`grammar_corpus_selftest()` below, called first thing in `run()`; the other in
vitest. Sharing the sources catches TEXTUAL drift; the corpus catches SEMANTIC
drift, which is what all three of those bugs actually were — not one of them was
a wrong character of regex.

`_TOKEN` is deliberately NOT shared, and the reason is a ruling rather than an
oversight: this gate must reject `sm:foo` and `text-[13px]` forever, the vitest
reader must accept them, and merging the two breaks one. Corpus case C10 gives
that divergence an exact size of one token so it cannot silently grow.

Nothing about what this gate MEASURES changed. Before and after: 908 declared,
863 referenced, **0 undeclared**.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "07-frontend" / "src"

# 0 since DEF-327 (2026-08-19): all 125 declared or renamed onto an existing
# class. MUST NEVER RISE — see THE RATCHET above.
UNDECLARED_BASELINE = 0

# ── B14 RULE 21 · NEW UI IS TAILWIND (PO ruling 2026-08-20) ────────────────
#
#   "Can you set the rule any new UI/screen we will use Tailwind only going
#    forward"
#
# ⚠ THIS CEILING IS THE RULE ITSELF, NOT A PROXY FOR IT. A new screen written in
# CSS adds class declarations; a new screen written in Tailwind adds none. So the
# number of classes the stylesheets declare MAY FALL AND MAY NEVER RISE — a
# migration that removes three and adds one still falls and is still allowed.
#
# It exists because a partial Tailwind migration otherwise leaves the product
# with two styling systems and no rule about which to use. That was the one cost
# of stopping mid-migration that does not heal by itself, and the PO closed it by
# making the CSS surface one that only ever shrinks.
#
# ⚠ LOWER THIS NUMBER WHEN IT FALLS. Leaving it high turns a ratchet back into a
# baseline, and the next lane gets room to add three classes without noticing.
# 2026-08-21 · 897 -> 892 (DEF-442). `components/FilterBar.css` is DELETED: r10
# draws filters as one `+ Filter` panel with removable chips, so the five rules
# that styled the three dropdowns and the old chips (`.filter-bar`,
# `.filter-select`, `.filter-chips`, `.filter-chip`, `.filter-chip-remove`) have
# nothing left to style. The gate asked for this in its own note — "5 below it —
# LOWER THE CEILING".
# 2026-08-21 · 892 -> 891 (DEF-332). `.settings-refusal-ref` and `.cus-rule`
# both styled an INTERNAL ID printed beside a sentence — ` (BR-IDN-013)` after
# every Settings refusal, and the server's own rule id beside a not-recorded
# value on three customer screens. The PO's standing ruling of 2026-08-19 is
# that those ids do not belong on a user's screen, so the spans went and the
# ids moved to `data-br-ref` / `data-rule-ref`, which need no declaration. Two
# rules deleted, one net class removed (`.cus-rule` had three call sites,
# `.settings-refusal-ref` one). ⚠ The ceiling is lowered in the SAME commit
# that removed them, because a ceiling nobody tightens is a number nobody reads
# — this gate says so itself when the count falls beneath it.
# 2026-08-21 · 891 -> 885 (CR-018 Route B, PO ask: "We need this as part of
#   Tailwind - can we do it?"). `components/WizardFrame.css` is DELETED and its
#   six classes with it: .wizard-frame, .br-steps, .br-step, .wizard-step-content,
#   .wizard-actions, .wizard-blocked. The frame 15 wizards mount is now utilities,
#   and its semantic names became `data-` attributes because Route B's own rule
#   refuses a class token that renders nothing.
# 2026-08-21 · 885 -> 875 (CR-023 P1). The service cell on the premises and
# units tables draws r10's coloured letter squares now, from ONE badge
# component (`features/rating/ratingShared`), so the ten
# `.met-tag-<service>` colour rules in `features/metering/metering.css`
# had no caller left and are deleted. The gate asked for this in its own
# output — `10 below it — LOWER THE CEILING` — and DEF-490's lesson is that
# a ratchet only ratchets when somebody turns it.
# 2026-08-22 · 875 -> 872 (CR-018 long tail, W14). `features/rating/
#   PlansRatesPage.css` is DELETED as a DEAD FILE: nothing imports it — the
#   page it is named after imports `PlansRates.css` — so none of its three
#   rules has ever reached a browser from this bundle. `.rating-head-id` and
#   `.rating-head-actions` have ZERO callers; `.rating-head` (one caller, the
#   rate-schedule wizard) keeps its declaration via `PlansRates.css`'s
#   `.rating-head h1`, which is the only rule that actually styles it. The
#   gate's own note had read `1 below it — LOWER THE CEILING` since CR-023 P1;
#   this lowers past it to the new count. Zero pixels move — an unimported
#   stylesheet styles nothing.
# 2026-08-22 · 872 -> 871 (CR-018 long tail, W14). `components/DateCell.css`
#   is DELETED — its one class `.cell-date` (tabular numerals + nowrap) is now
#   two utilities on the `<time>` element, ported value for value. The file
#   joins route-b-migrated.txt.
# 2026-08-22 · 871 -> 868 (CR-018 long tail, W14). `components/UnitCell.css`
#   is DELETED — `.cell-unit`, `.cell-unit-qty` (DEF-327's tnum) and
#   `.cell-unit-label` are utilities now, ported value for value; the one test
#   that grepped for the class name reads `data-cell="unit"` instead.
# 2026-08-22 · 868 -> 867 (CR-018 long tail, W14). `components/
#   ConfirmDialog.css` is DELETED — `.confirm-consequence` becomes
#   `m-0 text-md leading-body` (1.55 IS `--leading-body`, token for token).
#   The FormModal shell classes it composed are untouched.
# 2026-08-22 · 867 -> 864 (CR-018 long tail, W14). `components/Toast.css` is
#   DELETED — `.toast-region`, `.toast` and `.toast-dot` are utilities now,
#   ported value for value (r10's ink chip: bg-text/text-bg/shadow-lg; the
#   region's handle became `data-toast="region"`).
# 2026-08-22 · 864 -> 860 (CR-018 long tail, W14). `features/exports/
#   ListExportButton.css` is DELETED — `.list-export`, `-note`, `-refusal`,
#   `-download` are utilities now, ported value for value; the roles and
#   `data-resource` were already the handles the tests read.
# 2026-08-22 · 860 -> 857 (CR-018 long tail, W14). `components/StatusPill.css`
#   is DELETED — `.pill.ok`, `.pill.warn`, `.pill.draft` become their exact
#   token pairs as utilities on the one component; `.pill` and `.pill.past`
#   stay StateFrame.css's. The raw `pill ok` / `pill warn` spans on S103's
#   checklist and the report viewer now render StatusPill itself — the
#   DashboardPage comment block already named them DEF-244's shape.
# 2026-08-22 · 857 -> 847 (CR-018 long tail, W14). `features/identity/
#   SignInPage.css` is DELETED — S3's ten `.signin-*` rules become utilities
#   on the page, ported value for value (the two color-mix inks written
#   long-hand in srgb); the `.signin-actions .btn` parent rule travels down as
#   `[&_.btn]:` variants, and the page's handle is `data-page="signin"`.
# 2026-08-22 · 847 -> 840 (CR-018 long tail, W14). `components/
#   CustomFields.css` is DELETED — the tenant-fields section's seven classes
#   become utilities (descendant dt/dd/legend rules travel onto the elements;
#   the two INERT mode-gap declarations are dropped, which renders
#   identically). 0.04em joins the theme as `--tracking-label`.
# 2026-08-22 · 840 -> 828 (CR-018 long tail, W14). `features/tenancy/
#   ChecklistPage.css` is DELETED — S62's twelve `.checklist-*` classes AND
#   the bare `.done` state name (13 in all — no other stylesheet declared
#   `.done`) become utilities; the `.done` parent state is two full utility
#   strings and the test handles are data attributes now.
# 2026-08-22 · 827 -> 815 (CR-018 long tail, W14). `features/reports/
#   reports.css` is DELETED — S44's card grid and S46's viewer scaffolding
#   (twelve `.rep*` classes, `.rep-desc` among them already caller-less)
#   become utilities; a.rep's hover/focus rule is hover:/focus-visible:
#   variants on the Link, and the badge's 0.08em reuses
#   `--tracking-table-header` instead of minting a duplicate.
# 2026-08-22 · 815 -> 812 (CR-018 long tail, W14). `components/
#   DownloadButton.css` is DELETED — `.download-menu`, `.download-menu-list`
#   and `.download-button` become utilities (the component was already a
#   Route B file; only its stylesheet remained). The 17 test greps for the
#   two class names read `data-download="button|menu"` now.
# 2026-08-22 · 812 -> 811 (CR-018 long tail, W14). `components/
#   ScreenIdTag.css` is DELETED — the diagnostic pill is utilities (its 0.07em
#   and 1.4 named in the theme as `--tracking-screen-id` /
#   `--leading-screen-id`; its @media print rule is `print:hidden`), and every
#   reader uses the `data-testid` the element already carried.
# 2026-08-22 · 811 -> 794 (CR-018 long tail round 2, W14). `features/assets/
#   assets.css` is DELETED — 222 lines, 20 declared names, across S49–S55. The
#   panels, fact lists, embedded tables, bulk bar, import counts and the retire
#   notice are utilities on the four files now named in route-b-migrated.txt.
#   `.ast-filters` and `.ast-filters .field` were DEAD (declared, zero callers)
#   and are simply gone. Net 18 names removed, and ONE ADDED BACK ON PURPOSE:
#   `.page-header` — the shared component's own root class, which assets.css was
#   the only file declaring (via `.ast-page .page-header`). It moves to
#   `components/PageHeader.css` where the component lives, so this is one
#   declaration site replacing another, not a new class.
# 2026-08-22 · 794 -> 768 (CR-018 long tail round 2, W14). `features/reports/
#   dashboard.css` is DELETED — 298 lines, 26 declared names across S7's mix
#   bars, AR-ageing table, activity rows, to-do list and CR-015 period
#   statement. Its `@media (max-width: 1024px)` is `max-lg:`, the ratified
#   desktop-first spelling (G36/OQ-274). Nine class names that were Playwright
#   handles are one `data-dash` attribute with distinct values.
# 2026-08-22 · 768 -> 725 (CR-018 long tail round 2, W14). `features/billing/
#   billRun.css` is DELETED — 342 lines, 43 declared names across S31's six
#   wizard steps. Its two media queries are `max-sm:` / `max-md:`;
#   `.brun-table` was redundant with `PlainTable`'s own base and is dropped
#   rather than ported; `.brun-gap-rule` was DEAD (zero callers). Nine class
#   names that four Playwright specs selected on are one `data-brun`
#   attribute.
# 2026-08-22 · 725 -> 706 (CR-018 long tail round 3, W14). `features/public/
#   PricingPage.css` is DELETED — 170 lines, 19 declared names covering the WHOLE
#   public surface: S1 Pricing and the tenant-less `/signin-help`, which imported
#   another feature's stylesheet for its nav and content column. Unblocked by
#   OQ-279 (PO 2026-08-22, option A): `.pricing-lede` was one of G34's exact six
#   font-size literals and is `text-lead` now. `.public-nav a` was a DESCENDANT
#   rule that out-specified every button utility, so it is reproduced as a
#   `[&_a:not([data-public-brand])]:` variant at the same values — reproduced,
#   not corrected (CR-018 §6; filed as DEF-573). Handles are `data-public-page`,
#   `data-public-brand` and `data-pricing`.
# 2026-08-22 · 706 -> 673 (CR-018 long tail round 3, W14). `features/tenancy/
#   SignupWizard.css` is DELETED — 324 lines, 30 declared names across S110–S114
#   and CR-017's provisioning screen. The `@keyframes` round 2 named as its
#   blocker is `--animate-provisioning-pulse` in `tailwind.css`, copied byte for
#   byte (a transcription, the shape `--leading-btn` already has), with
#   `motion-reduce:animate-none` for the reduced-motion half. THREE classes were
#   DEAD and are deleted rather than ported: `.signup-success`,
#   `.signup-success-go`, `.signup-success-note` — zero callers anywhere. The
#   `is-${state}` interpolation is two `Record<StepState, string>` tables of
#   whole strings; handles are `data-signup` = page | services | provisioning.
# 2026-08-22 · 673 -> 647 (CR-018 long tail round 4, W14). `features/audit/
#   AuditLogPage.css` is DELETED — 218 lines, 26 declared names across S61's
#   viewer + drawer and the US-MET-020/US-AUD-007 retention page. Unblocked by
#   OQ-337 (PO 2026-08-22, "A please do it"): its three unreachable
#   line-heights are `leading-prose` (1.6, x2) and `leading-note` (1.7), at the
#   same numbers. One rule was INERT and is deleted rather than ported —
#   `.audit-filters .field { margin: 0 }`, where `.field` is a `<div>` and no
#   stylesheet declares a bare `.field`. `.audit-retention-link`'s
#   `padding-left: 0` has been LOSING to the ghost Button's own `px-1` since
#   Phase 4a (the utilities sheet is emitted last), so it is not ported either
#   and the 4px it should have removed is filed as DEF-581, never fixed here
#   (CR-018 §6). No handles were added: nothing ever selected an `audit-*`
#   class.
# 2026-08-22 · 647 -> 599 (CR-018 long tail round 4, W14). `features/tenancy/
#   RoutesCyclesWizards.css` is DELETED — 421 lines across both SET-06/07
#   wizards. OQ-337 unblocked it twice: `.rcw-preview`'s 1.9 is `leading-sample`,
#   and with the leading answered the 24px `.rcw-title` could take `--text-panel`
#   (G34 5 -> 4). `.rcw-table .cell-num` was REDUNDANT with the shared
#   `.cell-num` and is dropped, not ported. `.rcw-exit` is DEF-581 again: two of
#   its three declarations have been losing to the button kit's own utilities
#   since Phase 4a, so only `align-self` crosses. `--tracking-tag: 0.06em` joins
#   the theme as a transcription. Handles are `data-rcw`; 21 Playwright locators
#   rewritten.
# 2026-08-22 · 599 -> 546 (CR-018 long tail round 4, W14). `features/billing/
#   billing.css` is DELETED — 583 lines, 52 declared names across TEN components
#   (All bills, bill detail, Fix a bill, One-time bill, Budget bills, the bill
#   document, the pending queue, the layout tab and the two shared helpers). It
#   held EIGHT of the sixteen 1.6 line-heights OQ-337 named, more than any other
#   file; all eight are `leading-prose`. `.bil-linegroup th`'s `padding-top` is
#   DEAD — `PlainTable`'s own `[&_th]:p-2` is the same (0,1,1) rank and sits later
#   in the bundle — so it is not ported (DEF-585). `.bil-level` needs
#   `text-h5 leading-body tracking-normal` where `.bil-doc-band h3` needs
#   `text-h5` alone; the element decides. Handles are `data-bil`.
# 2026-08-26 · 546 -> 509 (CR-038 W5). The S29 read-detail DRAWER is retired —
#   the PO ruled the detail a PAGE ("i want page to be open for consitency - we
#   dont open side panel") and then reinforced rule 21 mid-build ("no custom
#   CSS in new UI") — so THIRTY-SEVEN classes go in one commit: the six shell
#   classes that framed the drawer (`.rd-scrim`, `.rd-drawer`,
#   `.rd-drawer-head`, `.rd-drawer-body`, `.rd-drawer-foot`, `.rd-close`), the
#   29 S29-only content rules (figures, math, outcome cards, compliance list,
#   chain, dispute banner) which ReadDetailPage (route-b-migrated) now carries
#   as utilities ported value for value, and `.met-tags`/`.met-tag`, whose last
#   renderer that page was. `.rd-block` survives — NetMeterPair, unmigrated,
#   still asks for it. Ceiling lowered in the SAME commit, per this gate's own
#   rule.
# 2026-08-27 · 509 → 505 (DEF-897). The estimate screen became a DIALOG, so
# `.rd-est-lede` / `.rd-est-form` / `.rd-est-actions` had nothing left to
# style — `FormModal` owns the frame, the field stack and the footer — and
# `.rd-archive` became utilities beside the reads filter bar (DEF-896).
# 2026-08-27 · 505 → 503 (DEF-1150). `.table-search` and `.table-search-clear`
#   were ORPHANED by the CR-018 Route B migration — the classes left the shared
#   list toolbar's markup and the rules stayed in the stylesheet. Nothing could
#   see it: THIS GATE ASKS ONLY WHETHER EVERY CLASS A COMPONENT NAMES IS
#   DECLARED, and never the mirror — whether every class a stylesheet DECLARES
#   is named. So a rule carrying `min-width: 220px` AND the whole field kit went
#   dead, the search box on all 27 lists rendered with no styling at all, and
#   the ceiling kept reporting healthy at 505 for as long as the corpse was in
#   the file. The mirror check is raised as OQ-630. Ceiling lowered in the SAME
#   commit, per this gate's own rule.
# 2026-08-30 · 503 → 486 (CR-048 wave C1). The five notification and template
#   ↑ CR-048.
# 2026-08-30 · 486 → 475 (CR-054 W0 T3). `EstimateReadModal.tsx` joins
#   `route-b-migrated.txt` and its ELEVEN `rd-est-*` declarations leave
#   `reads.css` in the same commit — it was the last Reads file off the list,
#   and therefore the one place in the module where a Tailwind utility
#   compiled to nothing. THE GUARD WAS SHOWN RED FIRST: with the file migrated
#   and not yet listed, this gate failed naming all eleven utilities as
#   undeclared, which is precisely the failure the migration clause exists to
#   prevent and is why the two halves must land together.
#   files are on the Route B ledger, so seventeen `.settings-*` names they were
#   the only caller of are retired from `features/tenancy/SettingsPage.css`:
#   `settings-helper`, `settings-chips`, `settings-badge`,
#   `settings-badge-muted`, `settings-actions`, `settings-inline-form`,
#   `settings-preview-strip`, `settings-subhead`, `settings-offer-body`,
#   `settings-tokens`, `settings-muted`, `settings-field` and the five
#   `settings-clause-*`. Their transcription lives in
#   `07-frontend/src/features/notifications/notificationsKit.ts`, declaration by
#   declaration. Eight class names the same files write are DELIBERATELY kept
#   and are not in this drop — `data-table`, `input`, `pill`, `settings-table`,
#   `settings-frame-toolbar`, `settings-icon-btn`, `settings-search` and
#   `panel-hint` — because screens that are NOT migrated still render them.
#   Ceiling lowered in the SAME commit, per this gate's own rule; the mirror
#   this retirement was done by hand for is still OQ-630.
# 2026-08-30 · 475 → 470 (CR-054 task 18). The S28 upload wizard adopts the
#   shared workflow kit, so `features/metering/reads.css` loses the five class
#   names that styled its hand-rolled tables — `.rd-manual`, `.rd-mapping`,
#   `.rd-rules`, `.rd-review`, `.rd-composition`. `MappingTable`,
#   `RuleResultsTable`, `ReconcileStrip` and the shared `PlainTable` draw all
#   five surfaces now, in Tailwind, on a file that IS on the Route B ledger.
#   THE GUARD WAS SHOWN RED FIRST, both ways: with the ceiling left at 475 the
#   gate printed "5 below it — LOWER THE CEILING", and with the classes deleted
#   while the wizard still named them it failed with five undeclared classes.
#   Ceiling lowered in the SAME commit, per this gate's own rule.
# 2026-10-11 · 470 → 466 (PO ruling "DEBTORS DETAIL … SHOWS THE PAYMENT
#   PLAN'S INSTALMENTS"). `.cus-plan-schedule` leaves `customers.css`: the
#   instalment table is `features/customers/PaymentPlanSchedule.tsx`, in
#   utilities on the Route B ledger, and the e2e journey locates it by
#   `[data-plan-schedule]`. The gate read "3 below it" before this commit and
#   "4 below it" after; the ceiling goes to the count, in the same commit.
DECLARED_CEILING = 466

# Things Tailwind genuinely cannot express. Each entry is a decision somebody
# wrote down — the same shape as G36's ALLOWED_ORPHANS and G37's SVG_OWNERS.
# ⚠ ADD A NAME HERE; DO NOT RAISE THE CEILING. Raising it is how a rule quietly
# stops being one.
NEW_CLASS_EXCEPTIONS: dict[str, str] = {
    "svc-fire": (
        "CR-063, 2026-09-02 — the ELEVENTH utility service's dot. THE CLASS IS "
        "BUILT AT RUNTIME as `svc-${service.code}` (ratingShared.tsx, "
        "RateSchedulesTab.tsx), so no Tailwind utility can name it and no "
        "compiler check can see it; the ten siblings `svc-electric` … "
        "`svc-battery` are already declared in PlansRates.css for that reason "
        "and this is the eleventh member of that ratified family, not new UI. "
        "⚠ THE ALTERNATIVE IS NOT 'write a utility instead' — it is a fire dot "
        "that silently falls through to `--color-neutral-500` and renders the "
        "same grey as any other unknown code, which is precisely the defect "
        "OQ-273 was ruled to close for four services on 2026-08-20. Named here "
        "rather than raising the ceiling, exactly as this gate asks."
    ),
}

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_SELECTOR = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

# ── THE GRAMMAR IS NOT WRITTEN HERE ANY MORE (OQ-277, 2026-08-20) ────────────
#
# It lives in `07-frontend/classname-grammar/patterns.json`, because it is read
# by TWO checks in two languages that cannot call each other: this gate (Python,
# `gates.yml`, which installs Python and nothing else) and
# `07-frontend/src/styles/routeBUtilities.test.ts` (JS, `ci-frontend.yml`, which
# runs node and nothing else). Deleting either is not available — one asks "is
# this class declared by a stylesheet?", the other asks "does the Tailwind
# compiler accept this utility?", and both are load-bearing.
#
# The cost of the duplication was measured, not feared: THREE corrections to
# this grammar have each landed in ONE language. The comparison-operand fix
# (130 vs 125), the interpolated-template fix (871 -> 870, which LOST two real
# classes while looking like an improvement), and G34's newline anchor. Nothing
# made the other reader follow.
#
# Sharing the sources stops the two SPELLING the grammar differently. It does
# not stop them USING it differently — none of those three bugs was a wrong
# character of regex — so both readers also assert the same golden corpus in
# their own workflow. See `grammar_corpus_selftest()` at the bottom of this
# file, which runs inside `run()`.
# ────────────────────────────────────────────────────────────────────────────
GRAMMAR = SRC.parent / "classname-grammar"
_PATTERNS = json.loads((GRAMMAR / "patterns.json").read_text("utf-8"))


def _bare_and_escapes(src: str) -> tuple[str, set[str]]:
    """Split a regex source into its bare metacharacters and its escape pairs.

    ⚠ THE NAIVE VERSION OF THIS IS WRONG AND FAILS LOUDLY ON ITS FIRST RUN — a
    substring search for `^` fires on `[^"]*`, which every pattern here uses, and
    a substring search for `$` fires on the escaped `\$\{` of `interpolation`.
    So character-class BODIES and ESCAPE PAIRS are skipped: `^`/`$` are refused
    only as bare anchors, `\A`/`\Z` only as escapes. Written identically in
    `routeBUtilities.test.ts` — it is the one piece of shared logic that cannot
    be expressed as data in `patterns.json`.
    """
    bare: list[str] = []
    escapes: set[str] = set()
    i, in_class = 0, False
    while i < len(src):
        ch = src[i]
        if ch == "\\" and i + 1 < len(src):
            escapes.add(src[i : i + 2])
            i += 2
            continue
        if in_class:
            in_class = ch != "]"
            i += 1
            continue
        if ch == "[":
            in_class = True
            i += 1
            continue
        bare.append(ch)
        i += 1
    return "".join(bare), escapes


def _shared(name: str) -> re.Pattern[str]:
    """Compile one shared pattern, refusing anything JS cannot read the same way.

    The blacklist is not decoration. `^\\s*` matching across a newline is the
    G34 bug verbatim, and Python's `$` matches before a trailing newline where
    JS's does not — so an anchor is the single likeliest way for these two
    readers to drift while both look correct. The one pattern that genuinely
    needs anchors is `_TOKEN`, and that is exactly the one `patterns.json`
    refuses to share (see `not_shared` there, and its `_why_not_shared`).
    """
    src = _PATTERNS["patterns"][name]["source"]
    bare, escapes = _bare_and_escapes(src)
    for banned in _PATTERNS["forbidden_constructs"]:
        hit = banned["literal"] in escapes if banned["kind"] == "escape" else banned["literal"] in bare
        if hit:
            raise SystemExit(
                f"G31: shared pattern {name!r} contains {banned['literal']!r}, which "
                f"patterns.json forbids — {banned['why']}"
            )
    return re.compile(src)


_CLASSNAME = _shared("classname")
_COMPARISON = _shared("comparison")
# Two readers, deliberately SEPARATE and both run over the whole expression.
# One regex cannot do this: a single alternation consumes a template literal
# whole, which hides the quoted strings inside its `${…}`, and that is exactly
# how the first widening of this gate LOST `is-blocked` while gaining
# `rd-source-card` — see the docstring.
_QUOTED = _shared("quoted")
_TEMPLATE = _shared("template")
# `${…}` splits a template into the STATIC chunks around it. Those chunks hold
# whole class names; the interpolations are read by `_QUOTED` above.
_INTERPOLATION = _shared("interpolation")

# ⚠ NOT SHARED, AND THAT IS A RULING RATHER THAN AN OVERSIGHT. This is the only
# place the two readers are ALLOWED to disagree: this gate asks "could a
# stylesheet declare this name?", so `sm:foo` and `text-[13px]` must be rejected
# here forever — accepting them would report every Tailwind utility as an
# undeclared class and make the gate cry wolf, which is the one failure this
# family of gates does not survive (DEF-323). The vitest reader asks "could
# Tailwind compile this candidate?" and must accept exactly those. Merging the
# two breaks one of them.
# Unshared is not unwatched: corpus case C10 gives the divergence an exact size
# of one token, asserted on both sides.
_TOKEN = re.compile(_PATTERNS["not_shared"]["token"]["python"]["source"])
_KIT_CONSTANT = _shared("kit_constant")
_UTILITY_SHAPED = re.compile(r"[a-z0-9][^\s]*\Z")
_KEY_POSITION = re.compile(r"\s*:")
_KEY_PRECEDED = re.compile(r"[{,]\s*\Z")


MIGRATED_LEDGER = SRC / "styles" / "route-b-migrated.txt"


def route_b_migrated() -> set[str]:
    """Files whose class names Route B moved out of the stylesheets.

    ⚠ THIS GATE'S RULE IS FALSE FOR THESE FILES, AND THAT IS NOT A WEAKENING.
    G31 asks "does a `.css` under src/ declare this name?". After CR-018 Phase 1
    a migrated component writes `flex items-end gap-3` and those are declared by
    the TAILWIND COMPILER — no stylesheet will ever name them. Measured on the
    first migrated component, 2026-08-19: this gate went `0 → 25` on a migration
    that was entirely correct.

    Leaving it red is not an option (a red gate nobody can make green is turned
    off), and lowering the ratchet would blind it to the other 126 components,
    which is the DEF-327 defect this gate exists to stop recurring a seventh
    time. So the migrated files are handed to a check that CAN ask the compiler:
    `07-frontend/src/styles/routeBUtilities.test.ts`, which runs in `npm test`
    and asks the STRICTER question — declared by a stylesheet OR generated by
    Tailwind. `itmes-end` fails there and would pass this gate's rule.

    ⚠ THE HANDOVER IS ONLY HONEST IF THE OTHER CHECK ACTUALLY RUNS, AND FOR
    THREE WEEKS IT DID NOT. `gates.yml` installs Python and nothing else;
    `.github/workflows/ci-frontend.yml` was what ran `npm test`, and every
    workflow was disabled on 2026-09-04 (PO: Actions minutes exhausted; see
    .github/workflows/README.md). This docstring then said *"Run it by hand"*,
    which is hard-won law 1 exactly — a comment claiming a guarantee is not the
    guarantee. `moveOutTables.tsx` asked for `border-danger` and `bg-danger-50`
    from 2026-09-24 and drew with no border and no background, with tsc, eslint,
    `toHaveClass()` and every gate green over it.

    ⚠ **`G134` IS THE ANSWER, AND IT IS A GATE ROW RATHER THAN A SENTENCE**
    (2026-09-25): `g134_route_b_utilities_compile.py` shells that vitest file
    from `run_gates` and reports its orphan list, and SKIPs with the NUMBER of
    unchecked files when vitest is not installed. This function still verifies
    what it can — that the file exists and that every ledger entry names a real
    file — and fails closed if the ledger points at a check that has been
    deleted. The count of files skipped now also goes in this gate's own
    RETURNED detail, so the runner's row cannot read as a clean sheet over
    files nobody looked at.
    """
    if not MIGRATED_LEDGER.exists():
        return set()
    owner = SRC / "styles" / "routeBUtilities.test.ts"
    if not owner.exists():
        raise SystemExit(
            "G31: route-b-migrated.txt exists but src/styles/routeBUtilities.test.ts "
            "does not. The ledger hands those files to that check; with the check "
            "gone they are guarded by NOBODY. Restore it or empty the ledger."
        )
    out: set[str] = set()
    for line in MIGRATED_LEDGER.read_text("utf-8").splitlines():
        entry = line.strip()
        if entry == "" or entry.startswith("#"):
            continue
        if not (SRC / entry).exists():
            raise SystemExit(f"G31: route-b-migrated.txt names a file that does not exist: {entry}")
        if entry.endswith("/"):
            # CR-068 wave A (2026-09-03): a DIRECTORY entry — every source file
            # beneath it, so a file born in a Tailwind-only application root is
            # handed to the compiler check on the day it is born rather than
            # when somebody remembers the ledger (DEF-974's trap, structurally
            # closed for src/portal/). routeBUtilities.test.ts expands the same
            # way; hard-won law 5 — one list, two readers, one rule.
            folder = SRC / entry
            if not folder.is_dir():
                raise SystemExit(f"G31: route-b-migrated.txt names a directory that does not exist: {entry}")
            for path in sorted(folder.rglob("*.ts*")):
                if path.suffix in {".ts", ".tsx"} and ".test." not in path.name:
                    out.add(str(path.relative_to(SRC)))
            continue
        out.add(entry)
    return out


def declared_classes() -> set[str]:
    names: set[str] = set()
    for path in SRC.rglob("*.css"):
        names |= set(_SELECTOR.findall(_COMMENT.sub(" ", path.read_text("utf-8", errors="replace"))))
    return names


def class_tokens(text: str) -> list[str]:
    """Every class name the source `text` asks for, in order, duplicates kept.

    THE READER ITSELF, lifted out of `referenced_classes()` so the golden corpus
    can be run through the SAME code the gate runs on the product (OQ-277). Its
    TypeScript twin is `classTokens()` in
    `07-frontend/src/styles/routeBUtilities.test.ts`; the two share their
    regexes through `classname-grammar/patterns.json` and are held to the same
    expected output by `classname-grammar/corpus.expected.json`. Keep the two
    bodies in the same shape — a reader comparing them line by line is how the
    871 -> 870 bug was found.
    """
    found: list[str] = []
    for quoted, braced in _CLASSNAME.findall(text):
        if quoted:
            blobs = [quoted]
        else:
            # A comparison operand is a VALUE, not a class — see the module
            # docstring. Strip the whole comparison before reading anything.
            expr = _COMPARISON.sub(" ", braced)
            # (a) every quoted string ANYWHERE in the expression, including
            #     inside a template's `${…}` — that is where a state class
            #     like `" is-selected"` lives.
            blobs = [g for lit in _QUOTED.findall(expr) for g in lit if g]
            # (b) plus the STATIC chunks of every template literal — that is
            #     where the base class like `rd-source-card` lives.
            for template in _TEMPLATE.findall(expr):
                blobs.extend(_INTERPOLATION.split(template))
        for blob in blobs:
            for token in blob.split():
                # A token ending in `-` is a PREFIX an interpolation
                # completes (`svc-${service}`), never a class name.
                if token.endswith("-"):
                    continue
                if _TOKEN.fullmatch(token):
                    found.append(token)
    return found


def kit_tokens(text: str) -> list[str]:
    """Every UTILITY a component kit names in a module-level constant (OQ-280).

    `class_tokens()` above reads `className=`. A component kit does not use it —
    it holds its utilities in constants and hands them to an element it renders:

        const STRUCTURE = "inline-flex items-center " + "border rounded-md";
        const FONT_SIZE = { default: "text-btn", sm: "text-btn-sm" } as const;

    So the strings leave `class_tokens()`'s field of view the moment a shared
    class becomes a component — and CR-018 Phase 3 established that shared
    classes MUST become components, because repeating utilities at 250 sites
    produced 540 differing properties. Phase 3 proved the blindness by planting
    `itmes-center` in `buttonKit.ts`: this gate said PASS / 0 undeclared and
    `routeBUtilities.test.ts` said 5 passed.

    ⚠ THE RETURN VALUE IS NOT ADDED TO `referenced_classes()`, DELIBERATELY.
    These are UTILITIES, not stylesheet classes. Counting them as referenced
    would report every one as undeclared — no stylesheet declares
    `items-center` — and the ratchet would explode on a correct product. This
    gate's job here is to EXTRACT them correctly and prove that against the
    corpus; whether Tailwind will actually emit each one is a question only the
    compiler can answer, and `routeBUtilities.test.ts` asks it.

    All-or-nothing per string (`shared_rules.kit_string_is_all_or_nothing`): a
    constant holding prose contributes nothing rather than contributing its
    lowercase words.
    """
    found: list[str] = []
    for raw_body in _KIT_CONSTANT.findall(text):
        # ⚠ THE SAME COMPARISON STRIP `class_tokens` DOES, and leaving it out
        # was historical bug 1 coming back in a new reader: `variant === "link"`
        # inside a kit constant contributed `link` and `ghost` as utilities,
        # and the compiler check named them. The two bodies are meant to be
        # comparable line by line — that is how the 871 -> 870 bug was found —
        # and this is what that discipline is FOR.
        body = _COMPARISON.sub(" ", raw_body)
        for match in _QUOTED.finditer(body):
            # ⚠ A QUOTED OBJECT KEY IS NOT A UTILITY. `{ "settings-row":
            # "px-[6px]" }` holds a key that is perfectly utility-SHAPED —
            # lowercase, hyphenated, no scheme — so the all-or-nothing rule
            # cannot tell it from a class. Position can: a literal followed by
            # `:` is a key. Found by this very check on the real buttonKit.ts,
            # which named `settings-row`, `link` and `ghost` as utilities
            # Tailwind would not emit.
            # A key is `{ "k": v }` or `, "k": v` — PRECEDED by a brace or a
            # comma AND followed by a colon. Both halves are needed: a ternary
            # `? "a" : "b"` is also followed by a colon, and testing only the
            # colon threw away the true branch. Caught by corpus case C16.
            if _KEY_POSITION.match(body, match.end()) and _KEY_PRECEDED.search(body[: match.start()]):
                continue
            for blob in (g for g in match.groups() if g):
                tokens = blob.split()
                if not tokens:
                    continue
                # The WHOLE string is rejected if any token is not utility-shaped
                # — `"Save changes"` must not contribute `changes`.
                if not all(_UTILITY_SHAPED.match(t) and "://" not in t for t in tokens):
                    continue
                found.extend(tokens)
    return found


def referenced_classes() -> dict[str, set[str]]:
    """class name -> the files that ask for it.

    Files on the Route B ledger are NOT read here — see `route_b_migrated()`.
    """
    migrated = route_b_migrated()
    used: dict[str, set[str]] = collections.defaultdict(set)
    for path in list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts")):
        if ".test." in path.name or ".stories." in path.name:
            continue
        if str(path.relative_to(SRC)) in migrated:
            continue
        text = path.read_text("utf-8", errors="replace")
        for token in class_tokens(text):
            used[token].add(str(path.relative_to(SRC)))
    return used


# ── The cleared-namespace orphan check (DEF-CWP-3774, DEF-974) ────────────
#: Tailwind's `text-` prefix carries FOUR different things and `@theme`'s
#: `--text-*: initial` clears exactly ONE of them — the SIZE scale. Alignment,
#: wrapping and the two colour keywords come from namespaces no `@theme` block
#: empties, so Tailwind emits them whatever the token files say. A gate that
#: did not know that would report `text-left` as dead and be switched off in a
#: week, which is the one failure this family does not survive (DEF-323).
TEXT_ALWAYS_EMITTED = frozenset(
    {
        "left", "center", "right", "justify", "start", "end",
        "inherit", "current", "transparent",
        "wrap", "nowrap", "balance", "pretty", "ellipsis", "clip",
    }
)

#: Where a `--text-*` or `--color-*` token is allowed to be declared. Both, not
#: one: `tailwind.css` holds the `@theme` block Tailwind compiles against and
#: `tokens.css` holds the same names for the plain-CSS side.
TOKEN_FILES = ("tailwind.css", "tokens.css")

_TEXT_TOKEN = re.compile(r"--text-([a-z0-9-]+?)\s*:")
_COLOUR_TOKEN = re.compile(r"--color-([a-z0-9-]+?)\s*:")
#: A bare `text-<name>` utility. Deliberately excludes `[`, so an arbitrary
#: value (`text-[13px]`, `text-[color-mix(...)]`) never reaches this check —
#: that is G34's question and it answers it differently.
_TEXT_UTILITY = re.compile(r"text-([a-z0-9][a-z0-9-]*)")


def declared_text_suffixes() -> tuple[set[str], set[str]]:
    """The `<name>`s that `text-<name>` may legally carry: sizes, then colours.

    Read from the token files rather than guessed, so the answer moves when the
    scale does. `--text-h1--line-height` declares the modifier of `h1`, not a
    step called `h1--line-height`, hence the split.
    """
    sizes: set[str] = set()
    colours: set[str] = set()
    for name in TOKEN_FILES:
        path = SRC / "styles" / name
        if not path.exists():
            continue
        css = _COMMENT.sub(" ", path.read_text("utf-8", errors="replace"))
        for match in _TEXT_TOKEN.finditer(css):
            sizes.add(match.group(1).split("--")[0])
        for match in _COLOUR_TOKEN.finditer(css):
            colours.add(match.group(1).split("--")[0])
    return {s for s in sizes if s}, {c for c in colours if c}


def type_scale_orphans() -> dict[str, set[str]]:
    """`text-<name>` where NOTHING declares `<name>` — a class that renders nothing.

    ⚠ **THIS IS THE HALF OF THE ROUTE-B QUESTION PYTHON CAN ACTUALLY ANSWER,
    AND `DEF-CWP-3774` IS WHY IT IS HERE.** `referenced_classes()` skips every
    file on the Route B ledger, because for those the answer is "did Tailwind
    compile it", which needs the compiler. `routeBUtilities.test.ts` asks the
    compiler and catches this exactly — but it runs in `npm test`, and every
    workflow in `.github/workflows/` is `.disabled`, so on a merge it never
    runs at all. `text-xl` therefore shipped on the portal's front door
    (CWP-015) rendering the utility's name at body size, with `tsc`, eslint and
    every `toContain` assertion green because the class IS in the DOM.

    **A cleared namespace does not need the compiler.** `--text-*: initial`
    deletes Tailwind's own scale outright, so the only sizes that survive are
    the ones the token files re-declare — a set this gate can read. So this
    check reads EVERY file, Route B included, and asks the one question that
    is decidable from the stylesheets alone.
    """
    sizes, colours = declared_text_suffixes()
    legal = sizes | colours | TEXT_ALWAYS_EMITTED
    orphans: dict[str, set[str]] = collections.defaultdict(set)
    for path in list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts")):
        if ".test." in path.name or ".stories." in path.name:
            continue
        text = path.read_text("utf-8", errors="replace")
        for token in class_tokens(text) + kit_tokens(text):
            # Strip any variant prefix (`md:`, `hover:`) — the utility is the
            # last segment, and a bracketed arbitrary value cannot match below.
            bare = token.rsplit(":", 1)[-1].lstrip("!")
            match = _TEXT_UTILITY.fullmatch(bare)
            if match is not None and match.group(1) not in legal:
                orphans[bare].add(str(path.relative_to(SRC)))
    return orphans


def grammar_probe_selftest() -> list[str]:
    """Prove each SHARED pattern still means in Python what it means in JS.

    The probes' expected matches were produced by Python `re` and asserted
    unchanged in JS before `patterns.json` was committed. Both halves re-run
    them, so "these are the same regex in both engines" is a check that runs
    rather than a comment claiming a guarantee (hard-won law 1). If a construct
    ever DOES diverge, one of these rows is what says so, by name.
    """
    problems: list[str] = []
    for name, spec in _PATTERNS["patterns"].items():
        rx = re.compile(spec["source"])
        ngroups = spec["group_count"]
        for probe in spec["probes"]:
            got = [
                [m.group(0)] + [m.group(i) for i in range(1, ngroups + 1)]
                for m in rx.finditer(probe["input"])
            ]
            if got != [[None if g is None else g for g in row] for row in probe["matches"]]:
                problems.append(
                    f"pattern {name!r} on probe {probe['input']!r}: expected "
                    f"{probe['matches']!r}, Python re produced {got!r}"
                )
    return problems


def grammar_corpus_selftest() -> list[str]:
    """Run the golden corpus through THIS reader and demand the ruled answer.

    WHY THIS IS INSIDE THE GATE AND NOT IN A TEST FILE
    --------------------------------------------------
    `gates.yml` installs Python and nothing else, so this is the only place the
    Python reader can be measured on every push. Its twin runs in vitest, which
    is the only place the TypeScript reader can be measured. Neither needs the
    other's runtime; each goes red in its OWN workflow if it drifts. That is the
    whole of OQ-277 — sharing `patterns.json` catches TEXTUAL drift, and only
    this catches SEMANTIC drift, which is the kind all three historical bugs
    actually were.

    SET EQUALITY, NOT `issubset`. The 871 -> 870 bug GAINED a name while losing
    two; every assertion that only looks for the names it expects passes it.
    """
    problems: list[str] = []
    expected = json.loads((GRAMMAR / "corpus.expected.json").read_text("utf-8"))
    got = set(class_tokens((GRAMMAR / "corpus.tsx").read_text("utf-8")))
    corpus_text = (GRAMMAR / "corpus.tsx").read_text("utf-8")

    # ── OQ-280 · the KIT reader, held to the same corpus ────────────────────
    # `class_tokens` reads `className=`; a component kit holds its utilities in
    # constants, so a whole family of strings is invisible to it. Phase 3 proved
    # that by planting `itmes-center` in buttonKit.ts and getting PASS here and
    # 5 passed in vitest. Set equality again, for the 871 -> 870 reason.
    kit_got = set(kit_tokens(corpus_text))
    kit_want = set(expected["kit_constant_expected"])
    if kit_got != kit_want:
        for name in sorted(kit_want - kit_got):
            problems.append(f"kit_constant corpus: did NOT find {name!r}")
        for name in sorted(kit_got - kit_want):
            problems.append(
                f"kit_constant corpus: wrongly found {name!r} — a kit constant "
                f"holding prose must contribute NOTHING, not its lowercase words"
            )
    want = set(expected["shared_expected"]) | set(expected["stylesheet_reader_only"])

    # Named first and separately, because a set diff does not tell a reader
    # WHICH of the ten old bugs just came back.
    for case in expected["cases"]:
        missed = [n for n in case["finds"] if n not in got]
        crept = [n for n in case["rejects"] if n in got]
        if missed or crept:
            problems.append(
                f"corpus case {case['id']}: "
                + (f"did NOT find {missed} " if missed else "")
                + (f"wrongly found {crept} " if crept else "")
                + f"— {case['guards']}"
            )
    for name in expected["must_not_find"]:
        if name in got:
            problems.append(f"corpus: {name!r} is on must_not_find and was reported as a class")
    if got != want:
        problems.append(
            f"corpus extraction is not the ruled set: unexpected {sorted(got - want)}, "
            f"missing {sorted(want - got)}"
        )
    return problems


def run() -> tuple[str, str]:
    # THE READER IS CHECKED BEFORE THE PRODUCT IS (OQ-277). If the grammar has
    # drifted, every number below is measured with the wrong ruler and a green
    # "0 undeclared" means nothing — which is precisely how the 871 -> 870
    # regression read as an improvement. So this fails FIRST and says which of
    # the ten corpus cases moved.
    grammar = grammar_probe_selftest() + grammar_corpus_selftest()
    if grammar:
        return "FAIL", (
            "the shared className grammar has drifted — "
            "07-frontend/classname-grammar/ (OQ-277). "
            + " | ".join(grammar[:3])
            + (f" (+{len(grammar) - 3} more)" if len(grammar) > 3 else "")
        )

    declared = declared_classes()
    countable = {c for c in declared if c not in NEW_CLASS_EXCEPTIONS}
    used = referenced_classes()
    missing = {name: files for name, files in used.items() if name not in declared}

    if "--list" in sys.argv:
        by_file: dict[str, list[str]] = collections.defaultdict(list)
        for name, files in missing.items():
            for f in files:
                by_file[f].append(name)
        for f in sorted(by_file, key=lambda k: -len(by_file[k])):
            print(f"{len(by_file[f]):3d}  {f}")
            print(f"     {', '.join(sorted(by_file[f]))}")

    migrated = route_b_migrated()
    note = (
        f"note: {len(declared)} class(es) declared across the stylesheets "
        f"(rule 21 ceiling {DECLARED_CEILING}"
        + (f", {DECLARED_CEILING - len(countable)} below it — LOWER THE CEILING"
           if len(countable) < DECLARED_CEILING else ", at it")
        + f"); "
        f"{len(used)} referenced by components"
    )
    if migrated:
        note += (
            f"; {len(migrated)} Route B file(s) handed to "
            f"src/styles/routeBUtilities.test.ts (CR-018)"
        )
    # ── B14 rule 21 — the CSS surface only ever shrinks ──────────────────
    if len(countable) > DECLARED_CEILING:
        return "FAIL", (
            f"the stylesheets declare {len(countable)} class(es) and the ceiling is "
            f"{DECLARED_CEILING} — B14 rule 21 (PO 2026-08-20): new UI is written in "
            f"Tailwind utilities and adds NO class to a stylesheet. If Tailwind genuinely "
            f"cannot express it (@keyframes, @font-face, a :has() chain), name it in "
            f"NEW_CLASS_EXCEPTIONS with a reason — do NOT raise the ceiling."
        )

    if len(missing) > UNDECLARED_BASELINE:
        worst = sorted(missing.items(), key=lambda kv: sorted(kv[1]))[:5]
        detail = "; ".join(f"{n} (asked for by {sorted(f)[0]})" for n, f in worst)
        return "FAIL", (
            f"undeclared classes ROSE: {len(missing)} now, {UNDECLARED_BASELINE} baselined. "
            f"A class no stylesheet declares renders as nothing — tsc, eslint and "
            f"toHaveClass() all pass on it. First few: {detail}"
        )
    # ── The cleared type scale has no orphans (DEF-CWP-3774) ────────────
    # Deliberately a HARD ZERO and not a ratchet. There was exactly one on the
    # day this landed and it is fixed in the same commit, so a baseline would
    # only be somewhere for the next one to hide.
    orphans = type_scale_orphans()
    if orphans:
        worst = sorted(orphans.items())[:5]
        detail = "; ".join(f"{name} (asked for by {sorted(files)[0]})" for name, files in worst)
        return "FAIL", (
            f"{len(orphans)} type-scale orphan(s): a `text-<name>` no token file declares. "
            f"`--text-*: initial` deleted Tailwind's own scale, so this compiles to NO RULE "
            f"and renders as nothing — tsc, eslint and every toContain() assertion pass on it "
            f"because the class IS in the DOM (DEF-CWP-3774, DEF-974). "
            f"Use a declared step, or a `--color-*` name if you meant the colour. {detail}"
        )
    print(note)
    # ── THE SKIP IS PART OF THE ANSWER, AND IT CARRIES ITS NUMBER ─────────
    #
    # ⚠ THIS GATE SKIPS ROUTE B FILES BY DESIGN AND SAID SO NOWHERE A READER
    # OF THE RESULTS TABLE COULD SEE IT (2026-09-25). `note` above is PRINTED,
    # not RETURNED: the runner's row read `0 undeclared class(es), at the
    # baseline of 0` over 559 files this gate had not looked at, and the one
    # check that does look — `src/styles/routeBUtilities.test.ts` — is not in
    # `run_gates` at all (it is vitest; `ci-frontend.yml` has been `.disabled`
    # since 2026-09-04). `moveOutTables.tsx` drew with no border and no
    # background for a day behind exactly that silence.
    #
    # Hard-won law 7, fifth shape: **a declared blind spot with no NUMBER
    # attached is indistinguishable from an empty one.** So the count of files
    # NOT checked here goes in the detail the runner prints, beside the count
    # of files that were, and it names who was handed them. `G134` is the gate
    # that actually runs that check; this sentence is what a reader sees when
    # `G134` skipped or is absent.
    skipped = (
        f" — and {len(migrated)} Route B file(s) were NOT checked by this gate "
        f"(a utility is declared by the compiler, not by a stylesheet); they are "
        f"handed to src/styles/routeBUtilities.test.ts, which G134 runs"
        if migrated
        else ""
    )
    if len(missing) < UNDECLARED_BASELINE:
        return "PASS", (
            f"{len(missing)} undeclared class(es), DOWN from the {UNDECLARED_BASELINE} "
            f"baseline — lower UNDECLARED_BASELINE to {len(missing)} to hold the gain"
            f"{skipped}"
        )
    return "PASS", (
        f"{len(missing)} undeclared class(es), at the baseline of "
        f"{UNDECLARED_BASELINE}{skipped}"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
