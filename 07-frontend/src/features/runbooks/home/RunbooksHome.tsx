// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2. `RBS-001`, the
//          Runbooks home. Screens: RBS-001 (`S147`), drawn against
//          `wireframes/RBS-001.1.md`–`.3.md` and their three PNG frames.
// Rules:   B14 rule 2 (one page header: kicker · title · subtitle ·
//          right-aligned actions) · rule 4 (`Verb →` navigates; one primary) ·
//          rule 15 (row actions are ICONS with tooltips, max 2 + …) ·
//          rule 16 (a pagination footer on every list table) · rule 17 (an
//          empty state says what is missing and what fills it) · rule 20 (one
//          table type) · rule 21 (Tailwind; `features/runbooks/` is a
//          DIRECTORY entry on route-b-migrated.txt, so files born here are
//          covered) · rule 31 (no database id is ever the visible value) ·
//          rule 32 (one sentence per section; no rule id or internal code in
//          clerk copy) · rule 33 (a FACT ≤ 6 words; RATIONALE is ZERO words on
//          screen) · rule 36 (compose the kit) · BR-SHL-025 (a control that
//          cannot act is DISABLED WITH ITS REASON, never hidden)
// Defects: DEF-RBS-4304 (two of the four KPI tiles have no total anywhere) ·
//          DEF-RBS-4305 (the outcome filter takes one status) · DEF-RBS-4327
//          (the run list serves no verdict) · DEF-RBS-4289 (there is no Draft
//          run status and the frame draws one) · DEF-RBS-4286 (no per-step
//          progress is recorded, and the frame draws a progress bar) ·
//          DEF-CWP-3925 (a live screen behind a dead control, and its mirror)
// Tests:   src/features/runbooks/home/RunbooksHome.dom.test.tsx ·
//          src/features/runbooks/home/homeHoldExpiry.test.tsx
// Impacts: src/App.tsx (the `runbooks` index route) ·
//          src/components/NotBuiltYet.tsx (the `/runbooks` hold, deleted in
//          the same commit) · src/features/runbooks/navHoldExpiry.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **Is anything waiting on me · what is running now · what can I run.**
 *
 * `08-screen-layouts.md` names those three questions in that order and the
 * layout follows them: *Needs you* sits ABOVE *Finished recently* because a
 * clerk opening this screen has one real question.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT THIS SCREEN DRAWS THAT THE FRAMES DO NOT, AND WHAT IT DOES NOT DRAW
 * ══════════════════════════════════════════════════════════════════════════
 * Every one of these is stamped in `04-docs/05-modules/17-runbooks/`
 * `08-screen-layouts.md` under `RBS-001`, which is where the execution plan
 * says a sheet-vs-rule divergence belongs. They are repeated here in one place
 * so a reader holding the frame beside the screen is never left to re-derive
 * one:
 *
 *   * **Both tables carry a pagination footer.** `RBS-001.1` draws one under
 *     *Finished recently* only. B14 rule 16 puts one on every list table and
 *     `NFR-3` makes it the deliverable rather than the background, so the rule
 *     wins and the divergence is stamped.
 *   * **The page head carries all three actions in every state.** `.2` draws
 *     one and `.3` draws one; that is the drawing fitting its figure, exactly
 *     as `08-screen-layouts.md` already records for `RBS-004`'s seven tabs
 *     (*"a lane building `RBS-004.7` literally ships a three-tab screen"*).
 *   * **The Needs you table holds the runs waiting for a person, and the run
 *     in flight is the banner.** `.1` draws a *Running* row in the table and
 *     `.3` draws the same run as a banner whose own note says *"Stop is always
 *     reachable … the control sits on the banner rather than two screens
 *     away"*. One read per status is all `f.outcome` can express
 *     (`DEF-RBS-4305`), so the banner is where a running run lives.
 *   * **No Draft row.** `DEF-RBS-4289`: there is no `draft` in `RUN_STATUSES`,
 *     no draft in the status machine and no endpoint that saves a run without
 *     starting it. A row that cannot exist is not drawn empty.
 *   * **No progress bar and no time estimate.** `DEF-RBS-4286`: nothing
 *     records a per-step outcome — `RunResult.step_runs` is a count held in
 *     memory and never persisted — so *Step 3 of 5*, *1,842 of 3,010 accounts*
 *     and *About 40 seconds left* have no source. A bar drawn at an invented
 *     percentage is worse than no bar (hard-won law 1).
 *   * **No sortable header.** `GET /runbooks/runs` declares
 *     `allowed_sorts=()`; it orders on `(-started_at, -created_at, -id)` and a
 *     `sort` param is dropped. A ⇅ that changes nothing is dead UI.
 *   * **`👁` and not `→`.** B14 rule 15 fixes the row-action vocabulary and it
 *     has no arrow. The frame's `▶ run again` is wave L's write route and rule
 *     15 has no glyph for it either, so the row carries the one action that
 *     works today rather than a greyed one and an empty `…`.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * FOUR CONTROLS ARE HELD, AND THE CLOCK ON THEM HAS ALREADY GONE OFF ONCE
 * ══════════════════════════════════════════════════════════════════════════
 * **Held:** *History →* (`RBS-008`), *Work list →* (`RBS-007`),
 * *Run "Can we bill?" ▶* and *Stop* — the last two waiting on the acting half's
 * write routes, since every runbooks route in the product today is a `GET`.
 * ⚠ **UPDATED 2026-10-13 (`DEF-WRK-10120`):** *History →* and *Work list →*
 * opened long ago, and *Run "Can we bill?" ▶* opened today — onto the Check
 * wizard (`RBS-004.run`), because `POST /runbooks/{key}/runs` landed on
 * 2026-10-07 and the hold-expiry test was red for six days before anybody
 * read it. **Only *Stop* is still held**: no route stops a run.
 * **Open:** *Templates →* and *Browse templates →*, both onto `RBS-002`, and
 * `👁 View` onto `RBS-006`.
 *
 * ⚠ **THIS PARAGRAPH SAID *SIX CONTROLS ARE HELD* FOR ONE AFTERNOON.**
 * `RBS-002` landed in a sibling lane hours after this screen was written,
 * `homeHoldExpiry.test.tsx` went red on the merge and named the *Templates →*
 * button, and the two template doors were opened in the commit that first met
 * it. That is a hold-expiry test doing its whole job, and it is the opposite of
 * `DEF-CWP-3925`, where the customer portal's front page had **two working
 * doors out of eight** — five cards and the sign-in bar still refusing over
 * screens that had shipped days earlier, with `tsc`, 42 test files, 391 cases
 * and every gate green.
 *
 * ⚠ **AND HOLDING A DOOR IS NOT TIDINESS HERE, IT IS CORRECTNESS.** `App.tsx`
 * mounts `runbooks/:key`, and React Router v6 ranks a static segment above a
 * dynamic one — so `/{tenant}/runbooks/templates` opened the setup screen for
 * *the runbook whose key is templates* until `RBS-002` declared its own route.
 * That is `integrations/subprocessors` exactly: read as a provider key,
 * answered 405, under a comment asserting the collision away.
 */
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { Button, ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { EyeIcon } from "@/components/icons";
import { KPIStrip } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";

import type { RunRow } from "./homeEndpoints";
import {
  formatTook,
  HEAD_DESTINATIONS,
  isOpen,
  OPEN_DESTINATIONS,
  kindKey,
  kindTone,
  runResultPath,
  statusKey,
  statusTone,
} from "./runbooksHomeModel";
import type { HomeKpi } from "./runbooksHomeModel";

/** The id this screen stamps on its own root — the handle a hold-expiry test
 *  and a walkthrough hold on to. An ATTRIBUTE, never visible copy, so B14 rule
 *  32's ban on an internal code in clerk-facing text is untouched. */
export const RUNBOOKS_HOME_SCREEN = "RBS-001";

/** Tenant-relative, exactly as `SHELL_NAV` declares it. */
export const RUNBOOKS_HOME_ROUTE = "/runbooks";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** One list's worth of state, handed down whole so the screen owns no fetching. */
export interface HomeSection {
  rows: readonly RunRow[];
  /** The SERVER's total. `null` until the first response — never `rows.length`. */
  total: number | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  loading: boolean;
  /** A plain-language reason, already resolved. `null` = the read succeeded. */
  error: string | null;
  onRetry: () => void;
}

export interface RunbooksHomeProps {
  tenant: string;
  kpis: HomeKpi[];
  /** The newest run in flight, or `null`. Drives `RBS-001.3`'s banner. */
  inFlight: RunRow | null;
  needsYou: HomeSection;
  history: HomeSection;
  regional: { timeZone: string; dateFormat: RegionalDateFormat };
  /**
   * `true` while any figure the strip draws is still on its way.
   *
   * A tile whose value is not known yet draws the shared skeleton, never a
   * zero — see the note at the render below.
   */
  kpisLoading: boolean;
  /**
   * `true` when this tenant has never run anything — `RBS-001.2`.
   *
   * Computed by the page from the SERVER's totals rather than from row counts,
   * because a page-2 read with an empty page is not an empty product.
   */
  nothingHasRunYet: boolean;
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 1 — THE PAGE HEAD
// ══════════════════════════════════════════════════════════════════════════
/**
 * The three `Verb →` actions, in the frame's order — one live, two held.
 *
 * **Templates →** opens `RBS-002`, which landed the same day as this screen.
 * **History →** (`RBS-008`) and **Work list →** (`RBS-007`) are later waves and
 * draw as disabled buttons carrying their reason.
 *
 * ⚠ **A DISABLED BUTTON THAT SAYS WHY, NOT A HIDDEN ONE** (`BR-SHL-025`). The
 * reason is three words (B14 rule 33) and names no screen, wave or id (rule
 * 32) — the ids live in `runbooksHomeModel.ts` and in this file's header, which
 * is where an engineer looks.
 *
 * ⚠ **A RELEASED HOLD KEEPS ITS POSITION.** The button that starts working
 * changes tier, never place, so a clerk who learned where *History →* sits does
 * not have to learn again the week it starts working.
 */
function HeadActions(props: { t: Translate; tenant: string }) {
  return (
    <>
      {HEAD_DESTINATIONS.map((action) =>
        isOpen(action.id) ? (
          <ButtonLink
            key={action.id}
            size="sm"
            data-open={action.id}
            to={`/${props.tenant}${action.path}`}
          >
            {props.t(action.labelKey)}
          </ButtonLink>
        ) : (
          <Button
            key={action.id}
            size="sm"
            disabled
            title={props.t("runbooks.home.hold.screen")}
            data-held={action.id}
          >
            {props.t(action.labelKey)}
          </Button>
        ),
      )}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 2 — THE KPI STRIP
// ══════════════════════════════════════════════════════════════════════════
/**
 * Four tiles, two of them a dash.
 *
 * ⚠ **A DASH IS NOT A ZERO.** A confident `0` under *Block billing* reads as
 * *nothing is stopping the bill run*, which is the most dangerous sentence this
 * screen could print. The four-word line under it says the product does not
 * count this yet, so the absence is on the screen rather than in a comment
 * (`DEF-RBS-4304`, and `RulesPage`'s `DEF-WRK-4096` is the same decision).
 */
function kpiTiles(kpis: readonly HomeKpi[], t: Translate) {
  return kpis.map((kpi) => ({
    id: kpi.id,
    label: t(kpi.labelKey),
    value:
      kpi.value === null ? (
        <span data-kpi-absent={kpi.id}>
          <Dash />
        </span>
      ) : (
        kpi.value
      ),
    detail: kpi.value === null ? t("runbooks.home.kpi.notCounted") : undefined,
  }));
}

// ══════════════════════════════════════════════════════════════════════════
// `RBS-001.3` — THE RUN IN FLIGHT
// ══════════════════════════════════════════════════════════════════════════
/**
 * The banner, and only what the module can actually say about a running run.
 *
 * **Watch → is a real door**: `RBS-006` is routed at
 * `runbooks/{key}/runs/{id}` and this links to it by ADDRESS.
 * **Stop is held**: `POST /runbooks/runs/{id}/stop` is wave L, and every
 * runbooks route that exists today is a `GET`. It keeps the danger tier the
 * frame gives it (B14 rule 6) so the control a clerk needs to find is where
 * they will look for it the day it works.
 */
function InFlightBanner(props: { row: RunRow; tenant: string; t: Translate }) {
  const { row, t } = props;
  return (
    <section
      data-in-flight={row.runbook_key}
      className="mb-4 flex flex-wrap items-center gap-3 border-l-4 border-accent bg-accent-100 px-4 py-3"
    >
      <strong className="text-base">
        {t("runbooks.home.banner.running", { name: row.runbook_name })}
      </strong>
      <span className="grow" />
      <ButtonLink size="sm" to={runResultPath(props.tenant, row)}>
        {t("runbooks.home.banner.watch")}
      </ButtonLink>
      <Button size="sm" variant="danger" disabled title={t("runbooks.home.hold.stop")}>
        {t("runbooks.home.banner.stop")}
      </Button>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// `RBS-001.2` — NOTHING HAS RUN YET
// ══════════════════════════════════════════════════════════════════════════
/**
 * Where *Run "Can we bill?" ▶* goes: runbook 1's Check wizard
 * (`RBS-004.run`). `configuration_check` is the key `services.add_template`
 * gives runbook 1 (`definitions/configuration_check.py`). Exported so the
 * hold-expiry test asserts the address the button actually carries.
 */
export const FIRST_RUN_PATH = "/runbooks/configuration_check/run";

/**
 * The screen-level empty state, with the TWO buttons the frame draws.
 *
 * ⚠ **NOT `EmptyList`, AND THE REASON IS ITS SHAPE RATHER THAN ITS LOOKS.**
 * `EmptyList` takes ONE cta; `RBS-001.2` draws two, side by side. Widening a
 * component 27 screens compose is a deliberate act for the kit rather than a
 * side effect of one screen, so this composes the kit's OWN frame classes —
 * `state-frame state-empty` and `state-helper`, both declared in
 * `StateFrame.css` — with the kit's `Button`. That adds no class to any
 * stylesheet, which is what B14 rule 21 is actually asking for, and it invents
 * no visual language, which is rule 36's concern. **A two-CTA empty state is a
 * real kit gap** and it is written down here rather than left as a shape the
 * next screen copies by eye.
 */
function NothingHasRunYet(props: { t: Translate; tenant: string }) {
  const { t } = props;
  const templates = OPEN_DESTINATIONS.find((open) => open.id === "templates");
  return (
    <div className="state-frame state-empty" data-empty="runbooks-home">
      <h4>{t("runbooks.home.empty.title")}</h4>
      <p className="state-helper">{t("runbooks.home.empty.helper")}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {/* RELEASED 2026-10-13 (`DEF-WRK-10120`). This was a disabled button
            held on `POST /runbooks/{key}/runs`; that route landed on 2026-10-07
            (`54583c831`, CR-173-BRC10) and the hold-expiry test went red six
            days before anybody read it. It now opens the Check wizard for
            runbook 1 — the ONE way a run starts (`OQ-WRK-12792` → A). A
            NAVIGATION, so a link. */}
        <ButtonLink
          variant="primary"
          data-open="run-first"
          to={`/${props.tenant}${FIRST_RUN_PATH}`}
        >
          {t("runbooks.home.empty.run")}
        </ButtonLink>
        {/* OPEN — RBS-002 landed the same day. The second door out of an empty
            screen, so a first visit is never a dead end. */}
        {templates === undefined ? null : (
          <ButtonLink data-open="templates-empty" to={`/${props.tenant}${templates.path}`}>
            {t("runbooks.home.empty.browse")}
          </ButtonLink>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGIONS 4 AND 6 — THE TWO TABLES
// ══════════════════════════════════════════════════════════════════════════
/**
 * `RBS-001.1` region 4 — **Run · State · Detail · Started · (row actions)**.
 *
 * *Detail* is the run's own count of record rows, which is a fact this endpoint
 * serves (`records`, grouped in SQL over the page). The frame's *812 planned ·
 * cap is 400* is a plan figure that arrives with the acting half.
 */
function needsYouConfig(
  t: Translate,
  tenant: string,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
): TableConfig<RunRow> {
  return {
    screenId: `${RUNBOOKS_HOME_SCREEN}.needsYou`,
    getRowId: (row) => row.id,
    defaultSort: { sort: "started", dir: "desc" },
    columns: [
      { key: "run", label: t("runbooks.home.col.run"), identity: true, cell: (row) => row.runbook_name },
      {
        key: "state",
        label: t("runbooks.home.col.state"),
        cell: (row) => (
          <StatusPill tone={statusTone(row.status)}>
            {t(statusKey(row.status), { defaultValue: row.status })}
          </StatusPill>
        ),
      },
      {
        key: "detail",
        label: t("runbooks.home.col.detail"),
        // ⚠ **THE PARAM NAME IS `n` AND NOT `count`, AND GETTING IT WRONG
        // PRINTS THE BRACES** — `DEF-RBS-4334`, which shipped to a screenshot
        // and no further. i18next substitutes by NAME, so a mismatch renders
        // the placeholder verbatim: this cell read `Records {{n}}` in a real
        // browser while `tsc`, eslint and every case in the DOM suite were
        // green, because none of them asserted the cell's TEXT.
        // ⚠ And it is `n`, not `count`, on purpose: `count` is i18next's own
        // plural selector and would make it look for `…records_one` /
        // `…records_other`, which no catalogue has.
        cell: (row) => t("runbooks.home.detail.records", { n: row.records }),
      },
      {
        key: "started",
        label: t("runbooks.home.col.started"),
        cell: (row) =>
          row.started_at === null ? (
            <Dash />
          ) : (
            <DateCell
              value={row.started_at}
              timeZone={regional.timeZone}
              dateFormat={regional.dateFormat}
              withTime
            />
          ),
      },
      {
        key: "actions",
        label: t("runbooks.home.col.actions"),
        cell: (row) => <ViewRun row={row} tenant={tenant} t={t} />,
      },
    ],
  };
}

/**
 * `RBS-001.1` region 6 — **Run · Kind · Outcome · Took · Finished · (actions)**.
 *
 * ⚠ **OUTCOME IS WHAT THE RUN DID, NOT WHAT IT FOUND** (`DEF-RBS-4327`). The
 * frame draws *3 blockers* and *Priced*; those are the verdict block of the
 * frozen report and reaching them would be one extra fetch per row.
 */
function historyConfig(
  t: Translate,
  tenant: string,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
): TableConfig<RunRow> {
  return {
    screenId: `${RUNBOOKS_HOME_SCREEN}.finished`,
    getRowId: (row) => row.id,
    defaultSort: { sort: "finished", dir: "desc" },
    columns: [
      { key: "run", label: t("runbooks.home.col.run"), identity: true, cell: (row) => row.runbook_name },
      {
        key: "kind",
        label: t("runbooks.home.col.kind"),
        cell: (row) => (
          <StatusPill tone={kindTone(row.kind)}>
            {t(kindKey(row.kind), { defaultValue: row.kind })}
          </StatusPill>
        ),
      },
      {
        key: "outcome",
        label: t("runbooks.home.col.outcome"),
        cell: (row) => (
          <StatusPill tone={statusTone(row.status)}>
            {t(statusKey(row.status), { defaultValue: row.status })}
          </StatusPill>
        ),
      },
      {
        key: "took",
        label: t("runbooks.home.col.took"),
        numeric: true,
        cell: (row) => formatTook(row.took_seconds) ?? <Dash />,
      },
      {
        key: "finished",
        label: t("runbooks.home.col.finished"),
        cell: (row) =>
          row.finished_at === null ? (
            <Dash />
          ) : (
            <DateCell
              value={row.finished_at}
              timeZone={regional.timeZone}
              dateFormat={regional.dateFormat}
              withTime
            />
          ),
      },
      {
        key: "actions",
        label: t("runbooks.home.col.actions"),
        cell: (row) => <ViewRun row={row} tenant={tenant} t={t} />,
      },
    ],
  };
}

/** The one row action that works today: open the run's result (`RBS-006`).
 *
 *  A `RowAction` and not a `RowActionLink` because `RowActionLink` takes a
 *  string address and this screen already builds one — either shape is a link;
 *  this keeps the address in `runResultPath` where the DOM test asserts it by
 *  destination rather than by "there is a link". */
function ViewRun(props: { row: RunRow; tenant: string; t: Translate }) {
  const to = runResultPath(props.tenant, props.row);
  return (
    <RowActions>
      <ButtonLink
        variant="ghost"
        size="row"
        aria-label={props.t("runbooks.home.rowAction.view")}
        title={props.t("runbooks.home.rowAction.view")}
        to={to}
      >
        <EyeIcon />
      </ButtonLink>
    </RowActions>
  );
}

/** A section heading — `RBS-001.1` regions 3 and 5. 12px, uppercase, 800,
 *  tracked out, exactly as `BreakdownBlock` already draws one in this module. */
function SectionHeading(props: { children: string }) {
  return (
    <h5 className="m-0 mt-6 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
      {props.children}
    </h5>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SCREEN
// ══════════════════════════════════════════════════════════════════════════
export function RunbooksHome(props: RunbooksHomeProps) {
  const { t } = useTranslation();
  const translate = t as Translate;
  const navigate = useNavigate();

  return (
    <main data-screen={RUNBOOKS_HOME_SCREEN}>
      <PageHeader
        kicker={translate("runbooks.home.kicker")}
        title={translate("runbooks.home.title")}
        rollup={translate("runbooks.home.subtitle")}
        secondaryActions={<HeadActions t={translate} tenant={props.tenant} />}
      />

      {/* ⚠ **`loading` IS NOT DECORATION — WITHOUT IT THIS STRIP PRINTS A
          CONFIDENT ZERO IT DOES NOT HAVE.** The two servable tiles are the
          SERVER's counts, and before the first response there is no count; the
          page can only pass `0`. So for one paint *Waiting for you* read **0**
          over a tenant with a run waiting, which is the same shape as
          `DEF-2412` — the unit screen printing a plan's uuid for the moment
          before its name arrived, permanently for a plan that never loaded.
          **Found by looking at the screenshot**, because every locator in the
          walkthrough auto-waits and every DOM test seeds its data: no check in
          this repository looks at the FIRST PAINT except one written to
          (`UnitPlanIdNeverShows.dom.test.tsx`, which is the shape copied in
          `RunbooksHome.dom.test.tsx`). Hard-won law 6, exactly. */}
      <KPIStrip kpis={kpiTiles(props.kpis, translate)} loading={props.kpisLoading} />

      {props.inFlight !== null && (
        <InFlightBanner row={props.inFlight} tenant={props.tenant} t={translate} />
      )}

      {props.nothingHasRunYet ? (
        <NothingHasRunYet t={translate} tenant={props.tenant} />
      ) : (
        <>
          <SectionHeading>{translate("runbooks.home.section.needsYou")}</SectionHeading>
          <DataTable<RunRow>
            config={needsYouConfig(translate, props.tenant, props.regional)}
            state={props.needsYou.state}
            onStateChange={props.needsYou.onStateChange}
            rows={props.needsYou.rows}
            totalRows={props.needsYou.total}
            loading={props.needsYou.loading}
            error={
              props.needsYou.error === null
                ? null
                : { reason: props.needsYou.error, onRetry: props.needsYou.onRetry }
            }
            empty={{
              title: translate("runbooks.home.needsYou.empty.title"),
              helper: translate("runbooks.home.needsYou.empty.helper"),
              ctaLabel: translate("runbooks.home.empty.run"),
              // Released with the empty state's own button (`DEF-WRK-10120`):
              // it was `ctaReason` + a no-op `onCta` over a route that exists.
              ctaVariant: "secondary",
              onCta: () => navigate(`/${props.tenant}${FIRST_RUN_PATH}`),
            }}
          />

          <SectionHeading>{translate("runbooks.home.section.finished")}</SectionHeading>
          <DataTable<RunRow>
            config={historyConfig(translate, props.tenant, props.regional)}
            state={props.history.state}
            onStateChange={props.history.onStateChange}
            rows={props.history.rows}
            totalRows={props.history.total}
            loading={props.history.loading}
            error={
              props.history.error === null
                ? null
                : { reason: props.history.error, onRetry: props.history.onRetry }
            }
            empty={{
              title: translate("runbooks.home.empty.title"),
              helper: translate("runbooks.home.empty.helper"),
              ctaLabel: translate("runbooks.home.empty.run"),
              // Released with the empty state's own button (`DEF-WRK-10120`):
              // it was `ctaReason` + a no-op `onCta` over a route that exists.
              ctaVariant: "secondary",
              onCta: () => navigate(`/${props.tenant}${FIRST_RUN_PATH}`),
            }}
          />
        </>
      )}
    </main>
  );
}

export default RunbooksHome;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D2; wireframes/RBS-001.1–.3 read region by region, PNG frames included)
// generated: 2026-09-06 by the CR-075 wave D task D2 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc✔ (./node_modules/.bin/tsc, the LOCAL compiler — never npx) · vitest (RunbooksHome.dom.test.tsx, homeHoldExpiry.test.tsx) · G31 (rule 21 — features/runbooks/ is a directory entry on route-b-migrated.txt) · i18n ×11
// exceptions: the two-CTA empty state composes the kit's own frame classes rather than EmptyList, which takes one CTA — stated in NothingHasRunYet's docstring as the kit gap it is
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
