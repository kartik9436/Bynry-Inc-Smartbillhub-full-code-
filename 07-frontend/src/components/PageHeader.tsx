// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-020 (EP-SHL-01 — one page header for every screen)
//           Screens: S9 · S14 · S15 · S21 · S30 · S32 · S49 · S50
// Rules:    BR-SHL-044 (the skeleton, and its three properties)
// ───────────────────────────────────────────────────────
// The page header every screen uses, so a user learns the product once instead
// of once per screen.
//
// Built because eight screens had each solved this separately and each got it
// differently — which is why the PO's walk through the prototype found every
// one "misplaced" in a different way (DEF-021). A convention would not have
// fixed that; only a component makes a NEW screen conform by default rather
// than by diligence.
//
// The skeleton, in order:
//
//   ← back                                     (detail screens only)
//   KICKER
//   H1                              [secondary…] [ONE primary]
//   [status]
//   roll-up / subtitle line
//
//   ⚠ The status USED to sit at the head of the action row, and DEF-966 is
//   what that cost: state + an honest-absence note + four buttons is too wide
//   to share a line with a title, so the row wrapped and the actions drew on
//   the left. The right-hand side holds ACTIONS ONLY — which is also what r10
//   draws in every one of its seventeen page heads.
//   ─────────────────────────────────────────────────────
//   tab strip
//   per-tab explainer
//
// Three properties are easy to get wrong and were wrong everywhere (BR-SHL-044):
//   (a) the primary action is per-TAB, not per-page — the SAME slot renders
//       "+ New plan" then "+ New rate schedule" as the user moves across;
//   (b) the explainer changes with the tab, and sits BELOW the strip, because
//       the strip is what a returning user reaches for first;
//   (c) a tab may have NO header action at all (Meter → Audit) while another
//       carries one inside its body (Maintenance → "+ Log repair") — so the
//       slot must accept empty WITHOUT the layout shifting.
//
// Where the primary action comes from (addendum r2). Two screens answer this
// differently, and both are legitimate:
//
//   · Assets, Meter detail, Premises hold the action's state on the PAGE, so
//     the action is static config — `PageHeaderTab.primaryAction`.
//   · Plans & Rates holds it in the TAB BODY (`const [adding, setAdding] =
//     useState(false)` inside ChargeCodesTab), which no config value can
//     reach. Those tab bodies take a render prop and hand their button back
//     up; the frame passes it here as `primaryAction`.
//
// One slot, two sources, and tab config wins when a screen supplies both — so
// the "exactly one primary" law (TC-6) survives either route.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import "./PageHeader.css";
import { Kicker } from "@/components/TextBits";

export interface PageHeaderTab {
  id: string;
  label: string;
  /**
   * A COUNT beside the label — *Steps **6*** · *Guards **3*** · *Runs **34***.
   *
   * ⚠ **ADDED 2026-09-06 (`CR-075` wave C task C3) AND ADDED HERE RATHER THAN
   * IN THE SCREEN, WHICH IS B14 RULE 36'S OWN MECHANISM:** *"Where the kit
   * lacks a piece, ADD IT TO THE KIT — one component, one visual decision,
   * every screen — rather than hand-rolling it in the screen."* `RBS-004`'s
   * seven tabs each carry one and the build sheets size the two halves
   * differently — the label at 13.5px/600, the count at 11px/500 — which a
   * single `label` string cannot express. The alternative was a second tab
   * strip inside the runbooks feature, which is exactly what the Work module
   * did in `DEF-WRK-3955` and exactly what `to` above was added to stop.
   *
   * ⚠ **A NEW OPTIONAL FIELD, NOT A WIDENING OF `label`.** Making `label` a
   * `ReactNode` was tried first and it broke `features/work/OrderDetailPage.tsx`
   * at compile time: its own `DetailTab` declares `label: string`, so a
   * `PageHeaderTab` stopped being assignable to it. A kit change that makes a
   * sibling's file stop compiling is not additive whatever its docstring says —
   * `tsc` said so, which is the only opinion that counts. An extra optional
   * property changes no existing declaration and no existing pixel.
   *
   * Absent ⇒ nothing renders and no space is reserved, so every tab strip in
   * the product is byte-identical to what it drew before this field existed.
   */
  count?: ReactNode;
  /** Guidance for THIS tab. Omitted ⇒ no paragraph and no gap (TC-7). */
  explainer?: string;
  /** Rendered in the header's primary slot while this tab is active. */
  primaryAction?: ReactNode;
  /**
   * A ROUTED tab — this entry draws a real `<Link>` instead of a `<button>`.
   *
   * ⚠ **ADDED FOR THE WORK MODULE (2026-09-05, `DEF-WRK-3955`) AND ADDED HERE
   * RATHER THAN THERE, WHICH IS B14 RULE 36'S OWN MECHANISM:** *"Where the kit
   * lacks a piece, ADD IT TO THE KIT — one component, one visual decision,
   * every screen — rather than hand-rolling it in the screen."* Work drew its
   * own `<nav role="tablist">` of `<Link>`s precisely because this strip could
   * only make buttons, and the product then had two tab strips that did not
   * look alike — one boxed, eight underlined.
   *
   * A tab that navigates SHOULD be a link: ⌘-click opens it in a second tab,
   * right-click offers *Copy link address*, and the address bar tells a person
   * where they are. `onTabSelect` still fires when it is given, so a screen may
   * keep its own state in step.
   *
   * **It changes no existing call site and no pixel.** One CSS rule styles both
   * elements (`.page-header-tabs button, .page-header-tabs a`) so the two
   * shapes cannot drift apart — the same reasoning `buttonKit.ts` applies when
   * it fills every colour slot exactly once.
   */
  to?: string;
}

export interface PageHeaderProps {
  title: string;
  /**
   * The element the title is rendered as. `h1` (the default) is right for a
   * screen that owns its address; `h2` is for a header drawn INSIDE a page that
   * already has one.
   *
   * ⚠ **ADDED 2026-09-07 FOR SET-10, AND ADDED HERE RATHER THAN THERE, WHICH IS
   * B14 RULE 36'S OWN MECHANISM:** *"Where the kit lacks a piece, ADD IT TO THE
   * KIT — one component, one visual decision, every screen — rather than
   * hand-rolling it in the screen."* The template designer is a DETAIL drawn
   * inside the Settings page, which has already written *"Settings"* as its
   * `h1`, so a second `h1` put two page titles in one document outline. The
   * alternative — the screen drawing its own kicker, title and action row —
   * is the second tab strip `to` was added to stop.
   *
   * **It changes no existing call site and no pixel.** Every heading level takes
   * the ruled scale from `global.css` (OQ-275: h1 40 · h2 32), so a nested
   * header is smaller than the page title it sits under, which is what a
   * document outline is FOR.
   */
  titleAs?: "h1" | "h2";
  /**
   * A small control or marker drawn IMMEDIATELY AFTER the title, inside the
   * heading — the copy-this-number glyph the Billing blueprint puts beside a
   * bill number.
   *
   * ⚠ **ADDED 2026-09-14 (`CR-101-BRC03`) HERE RATHER THAN IN THE SCREEN,
   * WHICH IS B14 RULE 36'S OWN MECHANISM** — the same reason `kicker` was
   * widened to `ReactNode` the same day and `leadingAction` was added on
   * 09-07. `title` is a `string` and cannot hold a `<button>`; the alternative
   * was the bill detail drawing its own kicker, title and action row, which is
   * the second header this component exists to prevent.
   *
   * **It is INSIDE the heading on purpose.** A `<button>` is phrasing content,
   * so it is valid there, and it is the only placement that keeps the glyph on
   * the title's own baseline at every width without a wrapper that would move
   * the layout of all ~137 screens that mount this.
   *
   * **It changes no existing call site and no pixel** — absent, the heading
   * renders exactly the one child it always did.
   */
  titleAfter?: ReactNode;
  /**
   * ⚠ **WIDENED FROM `string` TO `ReactNode` ON 2026-09-14, AND ADDED HERE
   * RATHER THAN IN THE SCREEN — B14 RULE 36'S OWN MECHANISM:** *"Where the kit
   * lacks a piece, ADD IT TO THE KIT — one component, one visual decision,
   * every screen — rather than hand-rolling it in the screen."* The PO asked
   * for the meter number in the reading detail's kicker to link back to the
   * meter (*"please ensure you ahve link it back to account and mter to
   * imporve interaction design"*), and a `string` cannot hold an `<a>`. The
   * alternative was that screen drawing its own kicker, title and action row —
   * which is the second tab strip `to` above was added to stop.
   *
   * ⚠ **IT IS ADDITIVE AND IT BREAKS NO CALL SITE**, which is the test the
   * `PageHeaderTab.label` note beside it records failing: widening `label`
   * stopped `features/work/OrderDetailPage.tsx` compiling, because a sibling's
   * own `DetailTab` declares `label: string`. Nothing in the product reads
   * `PageHeaderProps` (grepped: two hits, both in this file), `Kicker` has
   * always taken `ReactNode` children, and every existing caller passes a
   * string, which a `ReactNode` accepts. `tsc` is the only opinion that counts
   * here and it is clean.
   *
   * **It changes no pixel.** The node lands inside the same `<Kicker>` element
   * with the same class, so a kicker that is one string renders byte for byte
   * as it did.
   */
  kicker?: ReactNode;
  /** The "6 plans · 4 rate schedules · …" line under the title. */
  rollup?: ReactNode;
  /**
   * Detail screens only; list screens pass nothing (TC-5).
   *
   * `to` is an address and draws a real `<Link>` — ⌘-click opens it in a second
   * tab and the address bar tells a person where they are, which is what a back
   * link should do wherever the destination has an address.
   *
   * ⚠ **`onClick` IS FOR THE CASE WHERE THE DESTINATION IS STATE, NOT AN
   * ADDRESS (added 2026-09-07, `DEF-NOT-4456`).** SET-10's back control closes
   * a detail drawn over a LIST at the same route, and closing it means
   * restoring the catalogue's own query string — its table state, its filters,
   * its page — which only `TemplateCatalog` holds. A `<Link>` built from here
   * would have to reconstruct all of it and would silently drop whatever it
   * forgot. So the screen was drawing its own back row above the header, which
   * cost 59 vertical pixels of every template on a screen whose whole subject
   * is the document underneath it.
   *
   * Exactly one of `to` and `onClick` is used; `to` wins if both are given, so
   * no existing call site changes and no pixel moves. One CSS rule
   * (`.page-header-back`) styles both elements, the same way the tab strip
   * styles its `<button>` and its `<Link>`, so the two shapes cannot drift.
   */
  backTo?: { to?: string; label: string; onClick?: () => void; testId?: string };
  /**
   * The record's state — a status pill, and any honest-absence note that sits
   * with it (BR-SHL-025).
   *
   * ⚠ **IT RENDERS WITH THE IDENTITY, NOT IN THE ACTION ROW (DEF-966).** This
   * doc used to read *"sits leftmost in the action row, ahead of the buttons"*
   * and that placement is the defect: state is not an action, it made the row
   * too wide to share a line with the title, and r10 puts state in the kicker
   * or the sub-line on every screen it draws. See the render below.
   */
  status?: ReactNode;
  /**
   * An action drawn BEFORE the secondaries — the leftmost control in the row.
   *
   * ⚠ **ADDED 2026-09-07 FOR `DEF-NOT-4460`, AND ADDED HERE RATHER THAN THERE,
   * WHICH IS B14 RULE 36'S OWN MECHANISM:** *"Where the kit lacks a piece, ADD
   * IT TO THE KIT — one component, one visual decision, every screen — rather
   * than hand-rolling it in the screen."*
   *
   * The row has drawn `secondaryActions` and then `primaryAction` since it was
   * written, so the ORDER was a property of this component and not of the
   * screen: a screen filling both slots exactly right still got the kit's
   * order. The design the Product Owner handed over for SET-10 puts *Edit
   * wording* — the loud one — FIRST, and the running screen drew it last. The
   * screen could not say otherwise, because there was no slot that meant
   * *first*.
   *
   * ⚠ **IT IS A PLACEMENT, NOT A SECOND PRIMARY.** The tier still comes from
   * the button's own `variant`, so nothing here decides what is loud; a screen
   * whose primary belongs on the left passes it as `leadingAction` and passes
   * no `primaryAction`, and TC-6's "exactly one primary" is untouched.
   *
   * **It changes no existing call site and no pixel** — the slot renders
   * nothing when it is not given.
   */
  leadingAction?: ReactNode;
  /** Secondaries, in prototype order, before the primary. */
  secondaryActions?: ReactNode;
  /**
   * The primary slot for screens whose action state lives in the ACTIVE TAB's
   * body rather than on the page (addendum r2). The tab hands its button up
   * through its render prop and the frame passes it here. Tab config wins if
   * a screen sets both, so exactly one primary renders either way (TC-6).
   */
  primaryAction?: ReactNode;
  tabs?: readonly PageHeaderTab[];
  activeTabId?: string;
  onTabSelect?: (tab: PageHeaderTab) => void;
  /** Accessible name for the tab strip — every screen's strip needs its own. */
  tabsLabel?: string;
  /**
   * What a drawing puts BETWEEN the title block and the tab strip — a band and
   * a row of tiles that describe the whole record rather than one tab
   * (`05-prototype/rate-schedules-2026-10-01/images/08`: banner, four tiles,
   * then Overview · Rates · Plans · Audit). Opt-in; absent, nothing moves.
   */
  aboveTabs?: ReactNode;
}

/** The count beside a tab's word — `PageHeaderTab.count`.
 *
 * ⚠ ONE HELPER FOR BOTH TAB SHAPES, AND THAT IS THE POINT. The strip draws a
 * `<button>` or a `<Link>` depending on `to`, and the `to` field's own note
 * records why one CSS rule styles both: *"so the two shapes cannot drift
 * apart"*. Two copies of this span would be that drift with extra steps.
 *
 * Tailwind utilities, not a stylesheet class (B14 rule 21) — and this file is
 * on `styles/route-b-migrated.txt`, which its `status` block records as the
 * reason it was added there, so the compiler is asked about it and the classes
 * are emitted (`DEF-974`). */
function TabCount(props: { count: ReactNode }) {
  return (
    <span className="ms-1.5 text-xs font-medium" data-tab-count="">
      {props.count}
    </span>
  );
}

export function PageHeader(props: PageHeaderProps) {
  const tabs = props.tabs ?? [];
  // No id given ⇒ the first tab, which is what a screen means when it has a
  // default. An id that MATCHES NOTHING means something different and must not
  // collapse into the same answer: the route is a sibling destination rather
  // than one of the tabs (Plans & Rates → History is one — the prototype gives
  // it a top-right button, not a fifth tab). The strip then renders with none
  // selected, and no tab's explainer or action leaks onto a screen that is not
  // that tab. Screens resolve unknown URL segments themselves before they get
  // here (`ratingTabFromParam` and friends), so an unmatched id is deliberate.
  const active =
    props.activeTabId === undefined ? tabs[0] : tabs.find((tab) => tab.id === props.activeTabId);

  return (
    <div className="page-header">
      {props.backTo !== undefined &&
        (props.backTo.to !== undefined ? (
          <Link className="page-header-back" to={props.backTo.to} data-testid={props.backTo.testId}>
            ← {props.backTo.label}
          </Link>
        ) : (
          <button
            type="button"
            className="page-header-back"
            onClick={props.backTo.onClick}
            data-testid={props.backTo.testId}
          >
            ← {props.backTo.label}
          </button>
        ))}

      <div className="page-header-top">
        <div className="page-header-id">
          {props.kicker !== undefined && <Kicker>{props.kicker}</Kicker>}
          {/* ⚠ **THE SIZE IS 32px AND IT IS SET HERE, NOT INHERITED FROM THE
              ELEMENT — B14 rule 40, PO ruling 2026-09-12: *"use 32 pixels — for
              every ordinary screen"*, then *"Please use 32 pixels"*.**

              `tokens.css` has said `--text-h2: 32px; page-head title — THE APP
              DEFAULT, every screen head` since the type scale was ruled, and
              `--text-h1: 40px` was reserved for a full-page wizard title. But
              `global.css` sizes a bare `h1` at `--text-h1`, and this component
              rendered a bare `h1`, so **136 of the 137 screens that mount
              `PageHeader` drew their title at the wizard size** (`DEF-SHL-4947`,
              measured 2026-09-12). The note beside the token was never a rule —
              hard-won law 1, *a comment claiming a guarantee is not the
              guarantee* — and the PO ratified it as one on being shown the two
              sizes side by side.

              ⚠ **THE SIZE IS NOW INDEPENDENT OF THE HEADING LEVEL, AND THAT IS
              THE POINT.** Before this, the only way to get 32px was `titleAs
              ="h2"`, which DEMOTES the heading — so a screen wanting the right
              size had to give up its `h1` and leave the document outline with
              no page title. That is why exactly ONE caller ever used it, and
              that caller (`TemplateDetail`) passes it for the correct reason:
              it is drawn inside Settings, which already owns the `h1`. Both
              branches now carry the size, so the level answers to the outline
              and nothing else.

              ⚠ **NO WIZARD EXCEPTION, DELIBERATELY.** B14 rule 2 is RATIFIED
              and reads *"One page header. EVERY screen, including task pages
              and workflows"* — and 15 wizards mount this very component. A
              second size for them would re-create the exact defect this closes,
              whose title is *two page-title sizes and nothing splits them by
              kind*. `--text-h1` stays a token; it is simply not a page head.

              Proved through the BUILT stylesheet, not by asserting a class
              name: `10-scripts/render-checks/cr093-page-title-size.mjs` reads
              `getComputedStyle` at 1280 and 1440. A `toContain("text-h2")`
              assertion would pass even if the utility were emitted for no file
              and the element rendered unstyled — the skill's §7.1 trap. */}
          {props.titleAs === "h2" ? (
            <h2 className="text-h2">
              {props.title}
              {props.titleAfter}
            </h2>
          ) : (
            <h1 className="text-h2">
              {props.title}
              {props.titleAfter}
            </h1>
          )}
          {/* ⚠ **THE STATUS PILL RENDERS HERE, WITH THE IDENTITY — NOT IN THE
              ACTION ROW (DEF-966's second half).** It was the first child of
              `.page-header-actions` for as long as this component has existed,
              and that is what made the action row too wide to share a line with
              the title: on BIL-02 the row held a status pill, an
              "Past-due unknown" honest-absence note and FOUR buttons, so it
              wrapped, and a wrapped action row is what the Product Owner
              photographed.

              **`margin-left: auto` fixed the wrong half.** It right-aligns the
              row whether or not it wraps, which closed the letter of B14 rule 2
              — and left the actions on a second line, which is what the PO was
              looking at when he said *"buttons are still at wrong places"*.
              Right-aligned-but-wrapped satisfies the rule and not the reason
              for it.

              **The rule underneath, and it is r10's own:** the action row holds
              ACTIONS — controls a person can press. A status pill is a FACT
              about the record, and r10 agrees without exception: in all
              seventeen `page-head` blocks in `SMARTBillHub.dc.html`,
              `.page-actions` contains buttons and nothing else, and every
              record's state lives in the kicker or the sub-line. B14 rule 2's
              own skeleton says the same by omission — *kicker, title, optional
              subtitle, right-aligned actions* names no status slot at all.

              So the pill joins the identity, and the row loses roughly a third
              of its width on every detail screen at once. This is the SHARED
              header: no call site changes, and ~20 screens that pass `status`
              are corrected by this one move. */}
          {props.status !== undefined && (
            // ⚠ **UTILITIES, AND THIS FILE IS ON `route-b-migrated.txt` BECAUSE
            //    OF THIS ONE LINE.** The first draft declared a
            //    `.page-header-state` class in `PageHeader.css` and G31 refused
            //    it, correctly and in its own words: *"the stylesheets declare
            //    504 class(es) and the ceiling is 503 — B14 rule 21: new UI is
            //    written in Tailwind utilities and adds NO class to a
            //    stylesheet."* Raising the ceiling is what that gate exists to
            //    prevent, and this is not an exception case — Tailwind
            //    expresses a wrapping flex row perfectly well.
            //
            //    A utility only renders if the compiler is asked about the file
            //    (DEF-974), so the file is handed to
            //    `src/styles/routeBUtilities.test.ts` — the same handover
            //    `DownloadButton`, `RowActions` and `DataTable` each made for
            //    the same reason, and for the same one-line cause.
            //
            //    A ROW and not an inline element: the state may be a pill AND an
            //    honest-absence note beside it (BR-SHL-025), and those two
            //    belong together on one line rather than stacked.
            <div className="mt-2 flex flex-wrap items-center gap-2">{props.status}</div>
          )}
          {props.rollup !== undefined && <div className="page-header-rollup">{props.rollup}</div>}
        </div>

        {/* Always rendered, even when empty: an action row that appears and
            disappears between tabs would shift the title on every click (TC-3). */}
        <div className="page-header-actions">
          {props.leadingAction}
          {props.secondaryActions}
          {active?.primaryAction ?? props.primaryAction}
        </div>
      </div>

      {props.aboveTabs}

      {tabs.length > 0 && (
        // ⚠ `data-page-header-tabs` AND `data-tab` ARE PART OF THE CONTRACT,
        // not debug attributes — the same reasoning `Button.tsx` records for
        // `data-variant`. A rendered-output check is the ONLY instrument that
        // can see a tab strip at all (hard-won law 6), and until this commit
        // every such check had to select the strip by a CSS class name that
        // Route B is in the business of deleting. Work's own three walkthrough
        // scripts each grew their own `[data-work-tab]` handle for exactly that
        // reason; there is one handle now, and every module's strip has it.
        <div
          className="page-header-tabs"
          data-page-header-tabs=""
          role="tablist"
          aria-label={props.tabsLabel}
        >
          {tabs.map((tab) =>
            // A ROUTED tab is a real link; everything else is the button this
            // strip has always drawn. One CSS rule styles both, so the choice
            // is about behaviour and never about how the tab looks.
            tab.to === undefined ? (
              <button
                key={tab.id}
                type="button"
                role="tab"
                data-tab={tab.id}
                aria-selected={tab.id === active?.id}
                className={tab.id === active?.id ? "active" : undefined}
                onClick={() => props.onTabSelect?.(tab)}
              >
                {tab.label}
                {tab.count !== undefined && <TabCount count={tab.count} />}
              </button>
            ) : (
              <Link
                key={tab.id}
                to={tab.to}
                role="tab"
                data-tab={tab.id}
                aria-selected={tab.id === active?.id}
                className={tab.id === active?.id ? "active" : undefined}
                onClick={() => props.onTabSelect?.(tab)}
              >
                {tab.label}
                {tab.count !== undefined && <TabCount count={tab.count} />}
              </Link>
            ),
          )}
        </div>
      )}

      {active?.explainer !== undefined && (
        <p className="page-header-explainer">{active.explainer}</p>
      )}
    </div>
  );
}

export default PageHeader;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-020@9941789 (EP-SHL-01 — authored 2026-08-10 from the PO's
//         prototype walk; this is the COMPONENT half. The four screen
//         conversions — Plans & Rates, Premises, Assets, Meter detail — are
//         the remainder and are NOT done here.)
// generated: 2026-08-10 by Eng-Lead (prevention session 1) · AMENDED 2026-08-10
//         (addendum r2 — the render-prop route into the primary slot, and the
//         sibling-destination tab state that Plans & Rates → History needs)
// checklist: A✔ B✔ C✔ D=deferred(no API call — layout component) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest PageHeader.test.tsx✔ · suite✔ · build✔ · run_gates 11-PASS/0-FAIL/2-SKIP✔
// exceptions: TC-9's visual-conformance gate lands with the screen conversions,
//         not here · TC-4 and TC-8 stay it.todo in this file because both are
//         assertions about a converted SCREEN, and they belong in that screen's
//         own test rather than restated against a config fixture
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
