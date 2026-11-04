// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C3.
// Screens: RBS-004 (`S150`) — RBS-004.1 … RBS-004.7, seven tabs, region by
//          region against the sheets AND their frames.
// Rules:   B14 rule 2 (one page header) · rule 5 (two button sizes) ·
//          rule 6 (danger tier on a destructive commit) · rule 16 (pagination
//          footer) · rule 20 (one table type) · rule 21 (Tailwind utilities,
//          no stylesheet class) · rule 31 (no database id on screen) ·
//          rule 32 (description budget) · rule 33 (a refusal is five or six
//          words) · rule 36 (compose the shared kit) ·
//          `BR-RBS-002` · `BR-RBS-012` · `BR-RBS-042` · `NFR-3`.
// Defects: DEF-RBS-4285 (`why` and `summary` have no engine field) ·
//          DEF-CWP-3925 (mount under the real path pattern) ·
//          DEF-974 (a utility in an unlisted file renders as nothing).
// ───────────────────────────────────────────────────────
// THE SETUP RENDERER. One screen, twenty-six runbooks, no runbook named.
//
// ══════════════════════════════════════════════════════════════════════════
// B14 RULE 21 — WHY UTILITIES ARE SAFE IN THIS FILE, CHECKED NOT ASSUMED
// ══════════════════════════════════════════════════════════════════════════
// `07-frontend/src/styles/route-b-migrated.txt` line 3267 lists `features/
// runbooks/`, and the entry's own note says a file BORN under that folder is
// owned by it. So Tailwind is asked about this file and every utility below is
// emitted. `DEF-974` is what the other answer costs: a utility in an unlisted
// file renders as NOTHING while `tsc`, eslint and every `toContain("flex")`
// pass, because the class IS in the DOM. Grepped before the first utility was
// written, not after.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE SHEETS SAY AND WHERE THE RULE WINS — THREE DIVERGENCES, STAMPED
// ══════════════════════════════════════════════════════════════════════════
// `10-execution-plan.md`: *"Where a sheet and a B14 rule disagree, the RULE
// wins and the divergence is stamped in `08-screen-layouts.md`."* All three are
// stamped there; each is repeated at its own call site below so a lane reading
// the code never has to take the stamp on trust.
//
//   1. **ALL SEVEN TABS, ON EVERY TAB.** `RBS-004.3` draws five tabs, `.5` and
//      `.6` draw four, `.7` draws THREE, and the counts drop off after `.2`.
//      That is the drawing fitting its frame, and `08-screen-layouts.md` says
//      so in terms: *"A lane building `RBS-004.7` literally ships a three-tab
//      screen, and no check in this repository would see it."*
//   2. **THE STEPS NOTE IS SIX WORDS, NOT EIGHT.** The frame writes *"Tier days
//      and amounts are not edited here."* B14 rule 33 caps a refusal at five or
//      six.
//   3. **THE GUARDS TAB DRAWS A DISABLED CONTROL.** `08-screen-layouts.md`
//      says *"and no control"*; the FRAME (`RBS-004.4.png`) draws a greyed
//      **Edit** beside the reason, and B14 agrees with the frame — *a control a
//      user may not use is drawn disabled with its reason, never hidden*. Two
//      sources against one prose line, and the two that agree are the rule and
//      the picture.
//
// ⚠ **AND THAT DISABLED BUTTON IS NOT A HOLD.** Hard-won law 2's mirror is
// about a control refusing over a screen that has since shipped, and the cure
// is a test that fires when the hold expires. This one **never expires**:
// `BR-RBS-012` says guards are absolute and cannot be switched off, so the
// button is disabled BY RULE and for ever. A later lane that "releases" it has
// broken the rule, not fixed the screen — which is why it says so here and in
// the test rather than only in a business-rules file.
//
// ══════════════════════════════════════════════════════════════════════════
// EVERY HANDLER IS REQUIRED, AND THAT IS THE ANSWER TO LAW 2 / G13
// ══════════════════════════════════════════════════════════════════════════
// `onRun`, `onPauseToggle`, `onChangeScope`, `onChangeLimits` and the two run
// pagers are NOT optional. An optional prop nothing passes is the exact shape
// of the four defects in one day that law 2 was written from, and `G13`'s
// whole question is whether a guarded prop has a non-test caller. A required
// prop cannot have that shape: a caller that forgets one does not compile.
import { RunbookSettingsFields } from "./RunbookSettingsFields";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { Button, ButtonLink } from "@/components/Button";
import { Chip } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import type { PageHeaderTab } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { PageSize, TableConfig, TableRequestState } from "@/components/tableTypes";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import type {
  RunbookSetupView,
  SetupActivityEntry,
  SetupRow,
  SetupRun,
  SetupValue,
} from "./setupTypes";

/** The seven, in the order `RBS-004.1` draws them. Exported because the route
 *  resolves a URL hash against it and a test asserts the set — the same list in
 *  two places would be the drift this screen exists to avoid. */
export const RUNBOOK_SETUP_TABS = [
  "overview",
  "steps",
  "scope",
  "guards",
  "limits",
  "runs",
  "activity",
] as const;

export type RunbookSetupTab = (typeof RUNBOOK_SETUP_TABS)[number];

/** Which tab a URL hash names, or `overview`.
 *
 *  ⚠ **AN UNKNOWN HASH IS `overview`, NOT A BLANK SCREEN.** `BR-SHL-011`'s
 *  fallback law: an unreadable URL fragment reads as absent and the screen
 *  opens on its default. A pasted `#stpes` shows the runbook. */
export function runbookSetupTabFromHash(hash: string): RunbookSetupTab {
  const wanted = hash.replace(/^#/, "");
  return RUNBOOK_SETUP_TABS.find((tab) => tab === wanted) ?? "overview";
}

export interface RunbookSetupProps {
  view: RunbookSetupView;
  /** **Run ▶** — the header's one primary (B14 rule 4). */
  /** Where **Run ▶** goes — the Check wizard (`RBS-004.run`). A NAVIGATION, so
   *  a link: middle-click and *open in a new tab* keep working. It was an
   *  `onRun` that opened a pop-up until `OQ-WRK-12792` → A (PO 2026-10-13). */
  runTo: string;
  /** **Pause** / **Resume**. */
  onPauseToggle: () => void;
  /** `RBS-004.3` region 3. */
  onChangeScope: () => void;
  /** `RBS-004.5` region 3. */
  onChangeLimits: () => void;
  /** `CR-173-BRC10` — the schedule's own editor (PO 2026-10-07, Q6: *"User will
   *  configure this in runbook on thier own"*). Writes `trigger_kind`, `cron`
   *  and `timezone` through `PUT /runbooks/{key}`, which already accepted them. */
  onChangeSchedule: () => void;
  /** `RBS-004.6` — SERVER-side paging (`NFR-3`). The renderer holds no page of
   *  its own and slices nothing: it hands the request back and draws what it is
   *  given next. */
  onRunsPage: (page: number) => void;
  onRunsPer: (per: PageSize) => void;
}

export function RunbookSetup(props: RunbookSetupProps) {
  const { t } = useTranslation();
  const { view } = props;
  const active = runbookSetupTabFromHash(useLocation().hash);
  const tenant = useTenant();

  const tabs: PageHeaderTab[] = [
    tab(t("runbooks.setup.tab.overview"), "overview", null),
    tab(t("runbooks.setup.tab.steps"), "steps", view.steps.length),
    tab(t("runbooks.setup.tab.scope"), "scope", null),
    tab(t("runbooks.setup.tab.guards"), "guards", view.guards.length),
    tab(t("runbooks.setup.tab.limits"), "limits", null),
    tab(t("runbooks.setup.tab.runs"), "runs", view.runs.total),
    tab(t("runbooks.setup.tab.activity"), "activity", null),
  ];

  return (
    // `data-screen` is the convention every screen in this product follows and
    // the handle a hold-expiry test or a walkthrough holds on to. It is an
    // ATTRIBUTE, never visible copy, so B14 rule 32's ban on an internal code
    // in clerk-facing text is untouched.
    <main data-screen="RBS-004" data-runbook={view.key}>
      <PageHeader
        // ⚠ **`backTo` AND NOT `kicker`, THOUGH THE SHEET CALLS IT A KICKER.**
        // `RBS-004.1` writes *"kicker: ← My runbooks"* and rule 1 in the same
        // cell: *"a ← kicker names where the page EXITS to"*. A kicker is
        // TEXT — it draws the arrow and goes nowhere — so building it that way
        // ships an exit sign that is not a door. `PageHeader`'s `backTo` is the
        // kit's own answer: it renders `← label` as a real `<Link>` in the same
        // slot. Passing both would draw two lines where the frame draws one.
        //
        // ⚠ **THE ADDRESS IS BUILT FROM THE TENANT, NOT WRITTEN AS `".."`, AND
        // THE TEST IS WHAT FOUND THAT.** The first draft passed `to=".."`,
        // which reads as *"up one"* and is not: React Router resolves a
        // relative `to` against the ROUTE hierarchy, so `..` from the
        // `runbooks/:key` route removes that whole route — two URL segments —
        // and lands on `/{tenant}`, or on `/` when the route is mounted flat.
        // `RunbookSetup.dom.test.tsx` asserts the href by ADDRESS rather than
        // by "there is a link", which is `DEF-CWP-3925`'s lesson exactly: its
        // broken `//portal/…` addresses were perfectly good STRINGS, and only
        // an assertion on the resolved path could tell them from working ones.
        backTo={{ to: tenantPathFrom(tenant, "runbooks"), label: t("runbooks.setup.back") }}
        title={view.name}
        rollup={
          // ⚠ ONE SENTENCE AND A CHIP — B14 rule 32's description budget, and
          // the frame draws exactly this: the purpose, then the category as a
          // resting chip. The PO said *"too much content - desctiption is too
          // much for clark to read"* four times in twenty minutes; a second
          // sentence here is the thing they were looking at.
          // ⚠ **AN ABSENT PURPOSE DRAWS NOTHING — NO LINE, NO DASH, NO
          // PLACEHOLDER** (`DEF-RBS-4309`, and `SetupStep.why`'s rule one tab
          // over). Nothing on the wire carries the card sentence, so wave `E4`
          // made the field optional rather than have the mapper invent one; the
          // chip alone is honest and a dash would read like a lost sentence.
          <span className="flex flex-wrap items-center gap-2">
            {view.purpose !== undefined && <span data-purpose="">{view.purpose}</span>}
            <Chip>{view.category}</Chip>
          </span>
        }
        secondaryActions={
          <Button size="sm" onClick={props.onPauseToggle}>
            {view.paused ? t("runbooks.setup.action.resume") : t("runbooks.setup.action.pause")}
          </Button>
        }
        primaryAction={
          <ButtonLink variant="primary" to={props.runTo} data-run-open="">
            {t("runbooks.setup.action.run")}
          </ButtonLink>
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("runbooks.setup.tabsLabel")}
      />

      {active === "overview" && (
        <OverviewTab view={view} onChangeSchedule={props.onChangeSchedule} />
      )}
      {active === "steps" && <StepsTab view={view} />}
      {active === "scope" && <ScopeTab view={view} onChangeScope={props.onChangeScope} />}
      {active === "guards" && <GuardsTab view={view} />}
      {active === "limits" && <LimitsTab view={view} onChangeLimits={props.onChangeLimits} />}
      {active === "runs" && (
        <RunsTab view={view} onRunsPage={props.onRunsPage} onRunsPer={props.onRunsPer} />
      )}
      {active === "activity" && <ActivityTab view={view} />}
    </main>
  );
}

/**
 * One tab entry, as a ROUTED link with its count.
 *
 * ⚠ **A LINK, NOT A BUTTON, AND THE ADDRESS IS THE POINT.** `PageHeader`'s own
 * documentation says a tab that navigates should be a link: ⌘-click opens it in
 * a second tab, right-click offers *Copy link address*, and the address bar
 * tells a person where they are. Every `RBS-004` sheet writes its route with
 * the fragment — `…/collections-ladder#steps` — so the address IS part of what
 * the sheet specifies, and a `<button>` could not satisfy it.
 *
 * ⚠ **THE COUNT IS A `ReactNode`, WHICH IS A ONE-LINE WIDENING OF THE KIT AND
 * NOT A LOCAL WORKAROUND.** The sheets size a tab label at 13.5px/600 and its
 * count at 11px/500, which one string cannot express. B14 rule 36 names the
 * mechanism for exactly this: *"Where the kit lacks a piece, ADD IT TO THE KIT
 * — one component, one visual decision, every screen — rather than hand-rolling
 * it in the screen."* `PageHeaderTab.label` now takes a node; `string` is
 * assignable to `ReactNode`, so every existing call site is untouched and no
 * pixel moves anywhere else.
 */
function tab(label: string, id: RunbookSetupTab, count: number | null): PageHeaderTab {
  // `undefined`, never `null` and never `0`: an absent count draws nothing and
  // reserves no space, so a strip with no counts is byte-identical to what
  // `PageHeader` drew before the field existed. A tab whose count is genuinely
  // zero — a runbook with no runs — still shows `0`, because that IS the fact.
  return { id, to: `#${id}`, label, count: count === null ? undefined : count };
}

/** `RBS-004.1` regions 3–9 — three key–value blocks in one grid row.
 *
 *  The sheet: *"3 blocks in one grid row, wrapping below 228px each · grid,
 *  gap 13–14px"*. `minmax(228px, 1fr)` with `auto-fit` is that sentence
 *  exactly, and it wraps by itself rather than at a breakpoint someone picked
 *  (which is also `G36`'s one-responsive-direction rule). */
function OverviewTab(props: { view: RunbookSetupView; onChangeSchedule: () => void }) {
  const { t } = useTranslation();
  const { view } = props;
  return (
    <div
      className="mt-4 grid gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(228px,1fr))]"
      data-region="overview"
    >
      <Block heading={t("runbooks.setup.overview.schedule")} region="schedule">
        <KeyValues
          rows={[
            { id: "runs", label: t("runbooks.setup.schedule.runs"), value: view.schedule.runs },
            {
              id: "tz",
              label: t("runbooks.setup.schedule.timeZone"),
              value: view.schedule.timeZone,
            },
            { id: "next", label: t("runbooks.setup.schedule.next"), value: view.schedule.next },
          ]}
        />
        <div className="mt-2">
          <Button size="sm" onClick={props.onChangeSchedule} data-change-schedule="">
            {t("runbooks.setup.schedule.change")}
          </Button>
        </div>
      </Block>

      <Block heading={t("runbooks.setup.overview.lastRun")} region="last-run">
        {view.lastRun === null ? (
          // A runbook that has never run has no *When*, no *State* and no
          // *Planned* — and three empty rows would read as three unknowns
          // rather than as one fact. B14 rule 32: a stated absence, one
          // sentence, and nothing else.
          <p className="m-0 text-base text-neutral-600" data-absent="last-run">
            {t("runbooks.setup.lastRun.never")}
          </p>
        ) : (
          <KeyValues
            rows={[
              { id: "when", label: t("runbooks.setup.lastRun.when"), value: view.lastRun.when },
              { id: "state", label: t("runbooks.setup.lastRun.state"), value: view.lastRun.state },
              {
                id: "planned",
                label: t("runbooks.setup.lastRun.planned"),
                value: view.lastRun.planned,
              },
            ]}
          />
        )}
      </Block>

      <Block heading={t("runbooks.setup.overview.thisCan")} region="this-can">
        {view.capabilities.length === 0 ? (
          // ⚠ **A CHECK'S EMPTY LIST IS THE SAFETY PROMISE, NOT AN OMISSION.**
          // `BR-RBS-002`: a Check is CONSTRUCTED with no writer, so the
          // capability is absent rather than merely unused — that is the whole
          // reason a two-person utility can press Run on a thousand accounts.
          // Drawing nothing here would hide the best thing this screen has to
          // say.
          <p className="m-0 text-base text-neutral-700" data-absent="capabilities">
            {t("runbooks.setup.thisCan.none")}
          </p>
        ) : (
          <KeyValues
            rows={view.capabilities.map((capability) => ({
              id: capability.id,
              label: capability.label,
              value: {
                kind: "pill" as const,
                // *Yes* is DANGER and *No* is SUCCESS, which reads backwards
                // until you remember who is reading it: a clerk is asking
                // "what can this do to my customers", and the answer they need
                // to notice is the one that can send or charge. The frame
                // agrees, and so does B14 rule 6's reservation of the danger
                // tier for a state a person must act on rather than notice.
                label: capability.can
                  ? t("runbooks.setup.thisCan.yes")
                  : t("runbooks.setup.thisCan.no"),
                tone: capability.can ? ("danger" as const) : ("success" as const),
              },
            }))}
          />
        )}
      </Block>
    </div>
  );
}

/** `RBS-004.2` — the progress list, every step marked `read` or `writes`. */
function StepsTab(props: { view: RunbookSetupView }) {
  const { t } = useTranslation();
  const { view } = props;
  return (
    <div className="mt-4" data-region="steps">
      <ol className="m-0 list-none border border-divider bg-[white] p-0" data-step-list="">
        {view.steps.map((step, index) => (
          <li
            key={step.id}
            className="flex items-start gap-3 border-b border-b-divider px-4 py-3 last:border-b-0"
            data-step={step.id}
          >
            {/* The position marker. `RBS-004.2` draws every step `waiting` —
                correct, because this is the DEFINITION screen and nothing has
                run. The done/current/skipped/failed markers belong to the run
                wizard (`RBS-005`, task C4) and to the result renderer, which
                have a run to read them from; drawing a state here would be a
                screen inventing one. */}
            <span
              className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-neutral-400 text-xs text-neutral-600"
              data-step-marker="waiting"
              aria-hidden="true"
            >
              {index + 1}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-table text-neutral-700">{step.label}</span>
              {/* ⚠ ABSENT DRAWS NOTHING — no line, no dash, no placeholder.
                  `contract.py`'s `Step` has no field for this and the frame
                  draws it on all six steps (`DEF-RBS-4285`). A placeholder
                  would be this screen inventing the rule that decided the
                  step, which is the one thing `BR-RBS-010` says must be real. */}
              {step.why !== undefined && (
                // ⚠ `text-sm` (12px), NOT the sheet's 12.5px — THE SCALE'S OWN
                // RULE, AND `G98` IS WHAT SAID SO. `styles/tokens.css` records
                // that 10px *"and the half-steps"* were deliberately deleted on
                // 2026-08-19 (OQ-275/276/278), and the eslint rule refuses an
                // arbitrary type value by name: *"the ruled scale names every
                // step … use the name"*. `text-[12.5px]` compiled and rendered
                // at 12.5px — the browser check measured it — so nothing but
                // the lint rule could see it. Same shape as the percentage
                // divergence C1c settled: the rule wins over the drawing, and
                // it is stamped in `08-screen-layouts.md`.
                <span className="block text-sm text-neutral-600" data-step-why="">
                  {step.why}
                </span>
              )}
            </span>
            <span
              // `text-xs` (11px) for the sheet's 11.5px — the same half-step
              // the scale deleted, and the same ruling. See the note above.
              className="shrink-0 font-mono text-xs text-neutral-600"
              data-step-writes={step.writes ? "writes" : "read"}
            >
              {step.writes ? t("runbooks.setup.step.writes") : t("runbooks.setup.step.read")}
            </span>
          </li>
        ))}
      </ol>

      {view.settingsOwned !== null && (
        // ⚠ **SIX WORDS, WHERE THE FRAME WRITES EIGHT.** B14 rule 33 caps a
        // refusal at five or six words and the rule wins over the drawing;
        // stamped in `08-screen-layouts.md`. The frame's second, muted sentence
        // ("They are your collections settings, shown read-only") is dropped
        // for rule 32's budget — the link beside it already says where the
        // value lives, so the sentence repeats the button.
        <div
          className="mt-3 flex flex-wrap items-center gap-3 border-l-4 border-l-danger-500 px-4 py-3"
          data-settings-owned-note=""
        >
          <p className="m-0 text-base font-bold text-neutral-900">
            {t("runbooks.setup.steps.settingsOwned")}
          </p>
          <ButtonLink size="sm" to={view.settingsOwned.to}>
            {t("runbooks.setup.steps.openSettings")}
          </ButtonLink>
        </div>
      )}
    </div>
  );
}

/** `RBS-004.3` — the runbook's own inputs, then **Change scope** and the FACT
 *  line beside it.
 *
 *  ⚠ **THE ROWS ARE WHAT THIS TENANT SET, NOT WHAT THE RUNBOOK SHIPPED WITH**
 *  (`BR-RBS-042`, `DEF-RBS-4338`). Until wave `T` there was nowhere to save an
 *  input value, so these rows drew each parameter's DECLARED DEFAULT and called
 *  it the scope — accidentally right, because no tenant had set anything.
 *
 *  ⚠ **AND *All* IS A WORD HERE BECAUSE IT IS A RULE IN THE DATA.** The row
 *  says *All* rather than listing the services, because the stored value IS the
 *  word and it is resolved when the run starts: a utility that adds Trash next
 *  month gets three without touching this screen. */
function ScopeTab(props: { view: RunbookSetupView; onChangeScope: () => void }) {
  const { t } = useTranslation();
  const { view } = props;
  return (
    <div className="mt-4" data-region="scope">
      <KeyValues rows={view.scope} />
      {/* `OQ-WRK-12793` → A (PO 2026-10-13): an input Settings owns is shown
          read-only with its link, and the value is Settings' — read by the
          page's `RunbookSettingsProvider`, never the runbook's default. */}
      {view.settingsFields.length > 0 && (
        <div className="mt-3">
          <RunbookSettingsFields fields={view.settingsFields} />
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button size="sm" onClick={props.onChangeScope}>
          {t("runbooks.setup.scope.change")}
        </Button>
        {/* The sheet: *"the note is a FACT line, not a control (rule 32)"*.
            `null` draws NO line — a fact line with no fact is worse than none,
            and *Matches — accounts today* is exactly the kind of half-sentence
            the description budget exists to stop. */}
        {view.scopeMatches !== null && (
          <span className="text-base text-neutral-600" data-scope-matches="">
            {t("runbooks.setup.scope.matches", { total: view.scopeMatches.toLocaleString() })}
          </span>
        )}
      </div>
    </div>
  );
}

/** `RBS-004.4` — three guards, each *Never touched*, and a control that is
 *  disabled for ever. */
function GuardsTab(props: { view: RunbookSetupView }) {
  const { t } = useTranslation();
  return (
    <div className="mt-4" data-region="guards">
      <KeyValues
        rows={props.view.guards.map((guard) => ({
          id: guard.id,
          label: guard.label,
          value: {
            kind: "pill" as const,
            label: t("runbooks.setup.guards.never"),
            tone: "success" as const,
          },
        }))}
      />
      {/* ⚠ **DISABLED FOR EVER, AND THAT IS WHY IT IS DRAWN.** `BR-RBS-012`:
          guards are absolute, evaluated before any step, and they cannot be
          switched off — `contract.py`'s own `Guard` docstring says `RBS-004.4`
          draws the control disabled with its reason *"because a guard a clerk
          cannot see is a guard they will assume is absent"*.

          **This is NOT hard-won law 2's rotting hold.** That mirror is about a
          control refusing over a screen that has since shipped, and its cure is
          a test that fires the day the screen lands. Nothing lands here: there
          is no screen behind this button and there never will be. A later lane
          that enables it has broken a business rule, not released a hold — so
          `RunbookSetup.test.tsx` asserts the button is disabled and says this,
          and the reason travels with the assertion. */}
      <div className="mt-3 flex flex-wrap items-center gap-3" data-guards-locked="">
        <p className="m-0 text-base text-neutral-600">{t("runbooks.setup.guards.locked")}</p>
        <Button size="sm" disabled title={t("runbooks.setup.guards.locked")}>
          {t("runbooks.setup.guards.edit")}
        </Button>
      </div>
    </div>
  );
}

/** `RBS-004.5` — four fixed rows, then **Change limits**. */
function LimitsTab(props: { view: RunbookSetupView; onChangeLimits: () => void }) {
  const { t } = useTranslation();
  const { limits } = props.view;
  return (
    <div className="mt-4" data-region="limits">
      <KeyValues
        rows={[
          {
            id: "most",
            label: t("runbooks.setup.limits.mostPerRun"),
            value: limits.mostPerRun,
          },
          { id: "approval", label: t("runbooks.setup.limits.approval"), value: limits.approval },
          { id: "fees", label: t("runbooks.setup.limits.fees"), value: limits.fees },
          {
            id: "who",
            label: t("runbooks.setup.limits.whoCanApprove"),
            value: limits.whoCanApprove,
          },
        ]}
      />
      <div className="mt-3">
        <Button size="sm" onClick={props.onChangeLimits}>
          {t("runbooks.setup.limits.change")}
        </Button>
      </div>
    </div>
  );
}

/**
 * `RBS-004.6` — the run history, three columns, and the pagination footer.
 *
 * ⚠ **THE PAGE COMES FROM THE SERVER AND THIS COMPONENT SLICES NOTHING.**
 * `NFR-3` is universal server pagination, and CLAUDE.md's opening paragraph
 * makes it the deliverable rather than the background: four endpoints already
 * breach it by paging in Python at a ceiling that was correct at 3,000 accounts
 * and is 13× short of 40,000 (`DEF-PAY-4221`). A renderer that took the whole
 * history and sliced it locally would be the fifth.
 *
 * ⚠ **NO ROW ACTION, AND THE ABSENCE IS DELIBERATE.** A run row's natural
 * destination is its report — `RBS-006`, task `C2`, landing in this same wave —
 * and that address is not mine to invent. Hard-won law 2's mirror is a live
 * control onto a screen that is not there; the honest form is to draw the three
 * columns the sheet lists and let the lane that owns the address add the door.
 * `RunbookSetup.test.tsx` asserts the column set, so adding one is a deliberate
 * act with a test in front of it.
 */
function RunsTab(props: {
  view: RunbookSetupView;
  onRunsPage: (page: number) => void;
  onRunsPer: (per: PageSize) => void;
}) {
  const { t } = useTranslation();
  const { runs } = props.view;

  const config: TableConfig<SetupRun> = {
    screenId: "RBS-004.6",
    getRowId: (row) => row.id,
    defaultSort: { sort: "when", dir: "desc" },
    columns: [
      { key: "when", label: t("runbooks.setup.runs.when"), identity: true },
      {
        key: "outcome",
        label: t("runbooks.setup.runs.outcome"),
        cell: (row) => <StatusPill tone={row.outcome.tone}>{row.outcome.label}</StatusPill>,
      },
      {
        key: "acted",
        label: t("runbooks.setup.runs.acted"),
        numeric: true,
        // `—`, never `0`. A run that is still waiting has not acted on nobody;
        // it has not acted YET, and a zero would say the first thing.
        cell: (row) => (row.acted === null ? "—" : row.acted.toLocaleString()),
      },
    ],
  };

  const state: TableRequestState = {
    q: "",
    sort: "when",
    dir: "desc",
    page: runs.page,
    per: runs.per,
    filters: {},
  };

  return (
    <div className="mt-4" data-region="runs">
      <DataTable
        config={config}
        state={state}
        rows={runs.rows}
        totalRows={runs.total}
        loading={runs.loading}
        onStateChange={(next) => {
          // The only two dimensions this table has. Sort, search and filters are
          // not declared on the config, so the shared table draws no control for
          // them and nothing can arrive here (B14 rule 12's bounded toolbar).
          if (next.per !== state.per) props.onRunsPer(next.per);
          else if (next.page !== state.page) props.onRunsPage(next.page);
        }}
        empty={{
          title: t("runbooks.setup.runs.empty.title"),
          helper: t("runbooks.setup.runs.empty.helper"),
          ctaLabel: t("runbooks.setup.action.run"),
          // B14 rule 4 — the page header already carries **Run ▶**, so the
          // empty state's copy of it is the secondary tier and the screen keeps
          // exactly one primary.
          ctaVariant: "secondary",
          onCta: () => undefined,
        }}
      />
    </div>
  );
}

/** `RBS-004.7` — the change log, newest first, with the version each made. */
function ActivityTab(props: { view: RunbookSetupView }) {
  const { t } = useTranslation();
  const { activity } = props.view;
  if (activity.length === 0) {
    return (
      <p className="mt-4 text-base text-neutral-600" data-absent="activity">
        {t("runbooks.setup.activity.empty")}
      </p>
    );
  }
  return (
    <div className="mt-4" data-region="activity">
      <PlainTable>
        <tbody>
          {activity.map((entry) => (
            <ActivityRow key={entry.id} entry={entry} />
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

function ActivityRow(props: { entry: SetupActivityEntry }) {
  const { entry } = props;
  return (
    <tr data-activity={entry.id}>
      <th scope="row" className="font-heading">
        {/* ⚠ **`v4` IS A HUMAN-FACING NUMBER, NOT A DATABASE ID.**
            `08-screen-layouts.md` rules it in those words: *"A runbook version
            (`v4`) is a human-facing number under B14 rule 31's own escape
            clause, not an internal id."* It is what a clerk and an auditor say
            out loud — *"it was v3 when that went out"* — and what a run pins
            (`BR-RBS-038`). The row's real id is `entry.id` and it is drawn
            nowhere. */}
        <span className="me-2 text-neutral-600" data-activity-version="">
          v{entry.version}
        </span>
        {entry.summary}
      </th>
      <td className="text-right text-neutral-700">
        {entry.actor}
        <span className="ms-3 text-neutral-600">{entry.when}</span>
      </td>
    </tr>
  );
}

/** An `h5` section heading over its block. `RBS-004.1` regions 4, 6 and 8. */
function Block(props: { heading: string; region: string; children: React.ReactNode }) {
  return (
    <section data-region={props.region}>
      <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
        {props.heading}
      </h5>
      {props.children}
    </section>
  );
}

/**
 * The key–value table every one of these tabs draws — *"PlainTable (Surfaces)
 * · label left, value right-aligned · no header, no toolbar, no pager"*.
 *
 * ONE component for all six regions that use it, because six copies of a
 * two-column table is how a product ends up with six spacings. B14 rule 20 says
 * one table type; this is the small-table half of it and `PlainTable` is the
 * shared kit's own.
 */
function KeyValues(props: { rows: readonly SetupRow[] }) {
  return (
    <PlainTable>
      <tbody>
        {props.rows.map((row) => (
          <tr key={row.id} data-kv={row.id}>
            <th scope="row" className="font-heading">
              {row.label}
            </th>
            <td>
              {/* ⚠ **A FLEX ROW JUSTIFIED RIGHT, NOT `text-right` — AND THE
                  BROWSER CHECK IS WHAT FOUND THAT.** Every one of these six
                  regions says *"label left, value right-aligned"*, and the
                  obvious `className="text-right"` on this `<td>` DOES NOTHING:
                  `PlainTable` sets `[&_td]:text-left` on the table, which
                  compiles to `.plain td` at specificity (0,1,1) and outranks a
                  plain `.text-right` at (0,1,0). The class is in the DOM, so
                  `tsc`, eslint and `toContain("text-right")` all pass over a
                  value column drawn on the LEFT — `DEF-974`'s shape with the
                  cascade instead of the compiler. `rbs-c-setup-renderer.mjs`
                  read the computed alignment in a real engine and said
                  `label left · value left`, which is the only instrument that
                  could (hard-won law 6).

                  Justification is not text alignment, so nothing on the table
                  competes with it: the `<td>` stays a real table cell — making
                  IT the flex container would drop `display: table-cell` and
                  break the column widths — and this span fills it. */}
              <span className="flex justify-end">
                <Value value={row.value} />
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

function Value(props: { value: SetupValue }) {
  const { t } = useTranslation();
  if (props.value.kind === "pill") {
    return <StatusPill tone={props.value.tone}>{props.value.label}</StatusPill>;
  }
  if (props.value.kind === "absent") {
    // Not an empty cell. An empty cell and a zero look identical, and only one
    // of them is a fact — the same reasoning `MoneyCell` records for an absent
    // amount.
    return (
      <span className="text-neutral-600" data-absent="value">
        {t("runbooks.setup.absent")}
      </span>
    );
  }
  return <>{props.value.text}</>;
}

export default RunbookSetup;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · US-RBS-001 · CR-075 wave C task C3 ·
//         wireframes/RBS-004.1–.7 (sheets AND frames, read region by region)
// generated: 2026-09-06 by the CR-075 wave C · C3 build lane
// checklist: A✔ B✔ C✔ D=deferred(`GET /runbooks/{key}` is task D1, in flight in
//         a sibling lane — this renderer is pure over its view model and the
//         page that feeds it names the endpoint) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc (local install, never `npx tsc` — law 7's *incapable of failing*) ·
//         vitest RunbookSetup.test.tsx · render-check rbs-c-setup-renderer.mjs
// exceptions: three sheet/rule divergences, every one stamped in
//         `08-screen-layouts.md` and repeated at its call site above ·
//         `SetupStep.why` and `SetupActivityEntry.summary` have no engine field
//         (`DEF-RBS-4285`, filed before this file was written)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
