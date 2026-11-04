// ── Trace ──────────────────────────────────────────────
// Change:  **PO ruling 2026-09-28, verbatim: *"the report editor — panel or
//          its own page - own page"*** (12-governance/02-decision-log.md,
//          commit `d8c4bc1cb`). It SUPERSEDES the ruling of 2026-09-26 —
//          *"panel"* — which is stamped `RULED PANEL` on p031 of the Reports
//          Build Brief. The supersession is stated, not assumed (law 13), and
//          the PO was shown the cost before choosing: **a page cannot show the
//          rows changing as a column is ticked.**
// Defects: DEF-REP-7080 (the Filters section drew every declared filter —
//          fixed in `ReportEditPanel`, which this page mounts) ·
//          DEF-REP-7073 (any control closed the editor — designed out here,
//          see §3 below) · DEF-REP-7072 (`columnChoices`, carried unchanged)
// Screens: 2·2 (A1 S47) · `/{tenant}/reports/{key}/edit`
// Rules:   B14 rule 44 (the drawing says what is on screen and how arranged;
//          OUR standard says how it is built, and wins — including the frame) ·
//          rule 43 (a piece of UI is a COMPONENT: the sections are
//          `ReportEditPanel`, the preview is `ReportSamplePreview`, and this
//          page composes them) · rule 42 (p031–p033 read as IMAGES) · rule 40
//          (the page head is `PageHeader`'s) · rule 33 (a LABEL ≤ 3 words · a
//          FACT ≤ 6 · RATIONALE zero words on screen) · rule 32 (one sentence
//          per section) · rule 31 (no database id is ever a visible value) ·
//          rule 21 (Tailwind utilities; listed in route-b-migrated.txt) ·
//          BR-SHL-011 (the URL grammar) · BR-SHL-044 (one page header)
// Tests:   07-frontend/src/features/reports/reportEditorPage.dom.test.tsx
// Impacts: App.tsx (the route) · routing/screenIds.ts (its id) ·
//          ReportViewerPage.tsx (the `Edit` door now navigates here, and a
//          legacy `?edit=1` redirects here) · ReportEditPanel.tsx (`variant`)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  §1 · WHAT THE CLERK SEES WHILE THEY ARE CHOOSING — THE ONE DECISION     ║
// ║        THIS LANE WAS HANDED, AND THE ANSWER                              ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The 2026-09-28 entry hands exactly one thing to whoever builds this:
//
//     *"AND THE PREVIEW IS THE THING TO DESIGN FOR, NOT THE THING TO DROP.
//      The panel's whole argument was commit-at-the-end means you cannot see
//      your report until you have finished describing it. A page that simply
//      reproduces that failure is the wizard the PO already refused on
//      2026-09-26. Whoever builds it owes an answer to what does the clerk see
//      while they are choosing."*
//
// **THE ANSWER, AND IT IS A RULING THIS LANE MADE RATHER THAN INHERITED: the
// page shows the report's OWN FIRST FIVE ROWS, run with the draft's columns,
// re-running on every tick — and where those rows do not exist, the SHAPE.**
//
// ⚠ **THE PAGE GIVES UP THE FURNITURE, NOT THE ANSWER.** What the panel bought
// was a live table: toolbar, search, sort, pager, KPI band, export, fifty
// rows. Only ONE thing in that list is a decision a person is making on this
// screen — *which columns, in what order, reading which way, over rows that
// are really mine*. The rest belongs to the report a clerk is READING, which
// is 2·1 and is one click away. So the preview keeps the rows and drops
// everything around them, and the space that buys goes to the controls the
// Product Owner said they could not understand.
//
// ⚠ **AND IT IS STICKY, WHICH THE PANEL NEVER WAS.** On the panel, scrolling
// down to *Group & sort* scrolled the table away — the live rows were beside
// section ① and nowhere near section ⑤. Here the preview holds its position
// while the sections scroll under it, so the rows are in front of the clerk
// for every section rather than for the first one. That is the one respect in
// which the page is BETTER than what it replaces, and it is worth saying out
// loud because the rest of this trade is a cost.
//
// ⚠ **THE ROWS ARE REAL, AND WHERE THEY ARE NOT THERE ARE NO ROWS AT ALL.**
// `ReportSamplePreview` draws the server's own answer. `ReportShapePreview`
// draws column headings over grey bars and NOT ONE CHARACTER a clerk could
// read as a figure — that component's own docstring gives the reason, and it
// is this product's posture: *a confident wrong fact is worse than having
// none*. The page picks between them on `rows.length`, so there is always a
// shape on screen and never an invented number on a money screen.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  §2 · WHAT THE DRAWING STILL OWNS, AND THE ONE THING IT NO LONGER DOES   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// p031–p033 were rendered at scale 3 and read as IMAGES (B14 rule 42). The
// ruling reverses ONE sentence of that drawing — *"THE SAME TABLE, WITH A
// PANEL BESIDE IT"* — and nothing else on those three pages. So everything
// below is still the drawing's and is still built to it:
//
//   ① Report — dataset · one row per · calendar
//   ② Attributes — `4 OF 7`, tick to show, arrows to reorder, pencil to rename
//   ③ Measures — each carrying its own aggregation
//   ④ Filters — only the filters on the bar, then `+ Add filter`, then
//     `Show on the bar · 4 of 13`  ← `DEF-REP-7080`, and the drawing already
//     solved it; this build finally follows it
//   ⑤ Group & sort — three levels
//   ⑥ the unsaved marker, in the rollup where state belongs (B14 rule 2)
//   ⑦ Where it lives — group · sub-group · services · visible to
//   and the head: `←` back · kicker `EDITING` · the report's name ·
//   `Cancel` (ghost) and `Save as` (filled), in that order.
//
// ⚠ **`Save as`, NEVER `Save` — p032's PRIMARY ACTION row.** Editing a
// built-in never overwrites it: `tenant_id` is null on a platform row and
// copy-on-write is the rule (`P5.1`). *"That wording is the safety."*
//
// ⚠ **THE DEPARTURE IS RECORDED WHERE A NEXT LANE WILL LOOK**, not only here —
// `04-docs/05-modules/12-reports/07-builder-screen-2-2-drawn-spec.md` §9.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  §3 · WHY `DEF-REP-7073` CANNOT COME BACK AT THIS ADDRESS                ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The editor used to live at `?edit=1` on the viewer. `searchFrom` rebuilds
// the WHOLE query string from the report's own parameters, so a parameter it
// does not know about is DELETED by any update — and every control on the
// screen reaches `update()`. Typing one character into the account chooser
// took the URL from `/reports/statement?edit=1` to `/reports/statement` and
// the editor vanished mid-keystroke. The fix at the time was one line
// re-setting the flag, which is a thing every future caller has to remember.
//
// **The editor is now a PATH SEGMENT, and `searchFrom` cannot touch a path.**
// `update()` below rewrites the query string exactly as the viewer's does and
// the screen stays where it is by construction. That is the fault class
// removed rather than patched — and the journey test presses a control and
// then asks whether the screen is still the editor, which is the check that
// was missing when the defect shipped.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  §4 · IT ALSO OPENS ON NOTHING — `DEF-REP-7640`, 2026-09-28              ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The Product Owner pressed `+ Build your own` on Reports → Catalogue in
// deployed `v2.388.0` and nothing happened. The button navigated to
// `/reports/custom`, which since `P5.10` mounts the SAME catalogue on its
// Custom sub-tab — so from `/reports/custom` the press was a no-op and from
// `/reports` it switched sub-tab to an empty list.
//
// **PO ruling of the same day, verbatim: *"Opens the editor on a blank
// definition, then Save as"*.** This page was already the editor and already
// had `Save as` as its primary action; the one thing it could not do was
// START, because it resolves its report from `useParams().reportKey`.
//
// ⚠ **SO THE CHANGE IS A MODE, NOT A SECOND SCREEN.** `blank` seeds
// `draftFrom("")` at first render and four things follow from it: the kicker
// reads NEW rather than EDITING, the exit is the Custom sub-tab rather than a
// viewer that does not exist, the parameter bar is not drawn (nothing can be
// run, so nothing can be narrowed), and the preview column says *Nothing to
// show yet.* rather than rendering empty. A second page would have been a
// second place for `columnChoices` to be forgotten, which is exactly what
// `ReportEditPanel`'s `variant` prop already records about itself.
//
// ⚠ **AND THERE IS NO PREVIEW ON THIS PATH, WHICH IS A COST AND NOT AN
// OVERSIGHT.** §1 above answers *what does the clerk see while they are
// choosing* with the report's own first five rows — and those come from
// `GET /reports/{key}`, which resolves a SAVED definition. A report that has
// never been saved has no key and therefore no read path, so a blank builder
// can show the sections and the shape and nothing else until it is saved
// once. Inventing a run-this-draft endpoint is an interface decision beyond a
// maintenance fix, and the cost is STATED rather than hidden: the decision
// log of 2026-09-28 (`DEF-REP-7640`) carries it, and the clerk is told on
// screen in four words rather than left looking at an empty half-page.
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getReportDatasets,
  getReportLibrary,
  reportDatasetsQueryKey,
  runReport,
  saveReportDefinition,
} from "@/api/reportsEndpoints";
import type { ReportQuery, ReportResponse } from "@/api/reportsEndpoints";
import { Button } from "@/components/Button";
import { todayInZone } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { AbsentPanel, REPORTS_PERMISSION, gapSentence } from "@/features/ledger/financeShared";
import { isDenied, useAccessCell, useRegional } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ReportEditPanel, draftFrom, draftToWire } from "./ReportEditPanel";
import type { ReportDraftState } from "./ReportEditPanel";
import { ReportGrainLine } from "./ReportGrainLine";
import { ReportParameters, reportRunnable } from "./ReportParameters";
import { ReportRequiredInputs } from "./ReportRequiredInput";
import { ReportBlankPreview } from "./ReportBlankPreview";
import { ReportSamplePreview } from "./ReportSamplePreview";
import { ReportShapePreview } from "./ReportShapePreview";
import { ReportSubjectHead } from "./ReportSubjectHead";
import { SaveReportAsModal } from "./SaveReportAsModal";
import { paramsFrom, reportQueryKey, searchFrom } from "./ReportViewerPage";
import { reportLibraryQueryKey } from "./ReportLibraryPage";
import {
  REPORTS_ROUTE,
  ReportGapList,
  ReportParamBar,
  isNotProducible,
  keyForSegment,
  refusalReasonCode,
  reportWord,
  unavailableSentence,
  viewerRouteFor,
} from "./reportsShared";

import "@/features/ledger/finance.css";

export interface ReportEditorPageProps {
  /** ⚠ **A REPORT THAT DOES NOT EXIST YET** (`DEF-REP-7640`, PO ruling
   *  2026-09-28: *"Opens the editor on a blank definition, then Save as"*).
   *
   *  `App.tsx` passes this at `/reports/custom/new` and nowhere else. It is a
   *  PROP rather than a sniff at `useParams()` because a screen that infers
   *  its own mode from the address is a second routing table — the shape that
   *  put `/settings/audit-log` on a card and opened Settings → Company
   *  (`DEF-REP-6812`). The router says which screen this is; the screen does
   *  not guess.
   *
   *  Everything below then asks `blank` rather than asking whether `key` is
   *  empty: an empty key is also what a MALFORMED address produces, and those
   *  two must not render the same screen. */
  blank?: boolean;
  /** Test seam: the API client. Production takes the module default. */
  client?: ApiClient;
  /** Test seam: the report key, when no router segment carries one. */
  reportKey?: string;
  /** Test seam: the tenant's zone, when no shell has published one. */
  timeZone?: string;
  /** Test seam: today in the tenant's zone. */
  today?: string;
  locale?: string;
}

/**
 * Screen 2·2 — the report builder, at its own address.
 *
 * This page OWNS the draft and the two queries the builder needs, composes the
 * required-record chooser (only the page holds an API client — see
 * `ReportEditPanel`'s `requiredInputs` slot for why that seam exists), and
 * hands the sections to `ReportEditPanel` and the rows to
 * `ReportSamplePreview`. It renders no section and no table of its own, which
 * is B14 rule 43 read forwards rather than after the fact.
 */
export function ReportEditorPage(props: ReportEditorPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);
  const today = props.today ?? todayInZone(timeZone);

  const blank = props.blank === true;
  const key = props.reportKey ?? keyForSegment(routeParams.reportKey ?? "");
  const query = paramsFrom(searchParams);
  const cell = useAccessCell(REPORTS_PERMISSION, client);
  // ⚠ **A BLANK BUILDER EXITS TO THE CUSTOM SUB-TAB AND NOT TO A VIEWER.**
  // There is no report to go back to — `viewerRouteFor("")` would build
  // `/reports/`, which is the catalogue wearing a trailing slash. The Custom
  // tab is where the thing being built will land, so it is also the honest
  // place to abandon it from.
  const exitPath = blank
    ? tenantPath(`${REPORTS_ROUTE}/custom`)
    : `${tenantPath(viewerRouteFor(key))}${
        searchParams.toString() === "" ? "" : `?${searchParams.toString()}`
      }`;

  // ⚠ **A BLANK DRAFT EXISTS FROM THE FIRST RENDER, AND THAT IS THE WHOLE OF
  // THE FIX** (`DEF-REP-7640`). Everything below is gated on `draft !== null`
  // — the sections, `Save as`, the preview — and the draft is normally seeded
  // from the report's first answer. A report that has never been saved has no
  // answer coming, so on this address the seed is a real EMPTY definition:
  // subject unchosen, no columns, no filters. `draftFrom("")` is exactly that
  // and is the same constructor every other draft is built with, so `private`
  // stays the default (`BR-REP-019`) with no second rule.
  const [draft, setDraft] = useState<ReportDraftState | null>(() =>
    props.blank === true ? draftFrom("") : null,
  );
  const [savingAs, setSavingAs] = useState(false);
  // What `Save as` refused, if it did. Cleared by any change to the draft,
  // because a refusal that outlives the thing it refused is this repo's most
  // filed rot (hard-won law 2's mirror).
  const [refusal, setRefusal] = useState<string | null>(null);

  // ⚠ **NO `enabled` GUARD, AND THAT IS THE DIFFERENCE A PAGE MAKES.** On the
  // viewer the dataset registry was fetched only while `?edit=1` was set,
  // because a clerk merely READING a report should pay nothing for a registry
  // only the builder reads. At this address everybody is the builder.
  const datasetsQuery = useQuery({
    queryKey: reportDatasetsQueryKey,
    queryFn: () => getReportDatasets(client),
    retry: false,
  });
  // BR-REP-006 — the vocabularies and the catalogue groups are the TENANT's,
  // read live from the same call the library and the viewer use, never a list
  // compiled into this file.
  const libraryQuery = useQuery({
    queryKey: reportLibraryQueryKey,
    queryFn: () => getReportLibrary(client),
    retry: false,
  });

  // ⚠ **THE PREVIEW IS THE SAME REQUEST THE VIEWER MAKES, NOT A SECOND ONE**
  // (`P5.3`, and it survives the move to a page unchanged). The ticked columns
  // join the URL's parameters, so the query key changes on every tick and
  // TanStack re-runs the REPORT. A separate preview endpoint would be a second
  // renderer that could disagree with the one the clerk saves into.
  const previewColumns =
    draft !== null && draft.columns.length > 0 ? draft.columns.join(",") : undefined;
  const runQuery: ReportQuery =
    previewColumns === undefined ? query : { ...query, columns: previewColumns };
  const runnable = key !== "" && reportRunnable(key, runQuery);
  const reportRun = useQuery({
    queryKey: reportQueryKey(key, searchFrom(runQuery).toString()),
    queryFn: () => runReport(key, runQuery, client),
    retry: false,
    enabled: runnable,
    // ⚠ **THE PREVIEW STAYS ON SCREEN WHILE THE NEXT ANSWER IS FETCHED.**
    // Without this every tick blanks the rows to nothing and back, which is a
    // flicker on the one part of the screen this page exists to show.
    placeholderData: (previous: ReportResponse | undefined) => previous,
  });
  const report = reportRun.data;

  // ⚠ **THE DRAFT IS SEEDED FROM THE REPORT ON SCREEN, ONCE** — and the reason
  // is the same one `ReportViewerPage` recorded: re-seeding on every response
  // would undo the clerk's last tick the moment the preview came back, so the
  // column would appear and vanish. `held ?? …` is first-write-wins, so it
  // waits for BOTH the run and the catalogue (`DEF-REP-6863`, which came back
  // twice because a first fix did not wait).
  useEffect(() => {
    // ⚠ **NEVER ON A BLANK BUILDER.** `held ?? …` already protects the seed
    // and `runnable` is false with no key, so this is belt and braces — but a
    // reader arriving here needs to be told that the blank draft is authored
    // in `useState` above and is not waiting for a response that is not
    // coming. A silent second seeding path is how `DEF-REP-6863` came back
    // twice.
    if (blank) return;
    if (report === undefined) return;
    const card = libraryQuery.data?.cards.find((one) => one.key === key);
    setDraft((held) =>
      held ??
      draftFrom(report.dataset ?? "", {
        columns: [...report.columns],
        group: report.group ?? card?.group ?? "",
        sub_group: report.sub_group ?? card?.sub_group ?? null,
      }),
    );
  }, [blank, report, libraryQuery.data, key]);

  function update(next: Partial<ReportQuery>): void {
    // ⚠ **ANY CHANGE OF WHAT IS BEING ASKED RETURNS TO PAGE ONE** — the same
    // rule 2·1 keeps, for the same reason: narrowing while sitting on page 40
    // lands on a page that no longer exists and reads as *no matches*.
    const changesSelection = Object.keys(next).some((name) => name !== "page");
    const merged: ReportQuery = { ...query, ...next };
    if (changesSelection && next.page === undefined) {
      delete merged.page;
    }
    // ⚠ **NOTHING IS RE-SET HERE AND NOTHING NEEDS TO BE** (`DEF-REP-7073`).
    // The address that says *this is the builder* is the PATH, and `searchFrom`
    // rebuilds only the query string. See §3 in this file's head.
    setSearchParams(searchFrom(merged), { replace: true });
  }

  // ⚠ **ABOVE THE PERMISSION EXIT, AND IT HAS TO BE (DEF-GOV-8540, 2026-09-30).**
  // It sat below it, so a refused run arriving after the first render ran one
  // hook fewer and React threw on hook order instead of drawing the refusal.
  // ⚠ **THE SHAPE FALLS BACK TO THE DRAFT'S OWN TICKS.** Before an account is
  // chosen a statement cannot run at all, so there is no `report.columns` to
  // describe — and a clerk who has ticked four columns should still see four.
  const shapeColumns = useMemo(
    () =>
      (report?.columns ?? draft?.columns ?? []).map((column) => ({
        key: column,
        label: reportWord(column, translate),
      })),
    // `translate` is re-created per render and `t` is stable through i18next's
    // own instance; depending on it would rebuild this list on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [report?.columns, draft?.columns],
  );

  const runRefused = reportRun.isError && isPermissionDenied(reportRun.error);
  if (isDenied(cell) || runRefused) {
    // `DEF-REP-6907` — one report refused is not the module refused, and the
    // server already sends the six-word sentence for the per-report floor.
    return (
      <PermissionDenied
        helper={runRefused ? apiErrorText(reportRun.error, translate) : t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const failed = reportRun.isError && report === undefined;
  const notProducible = reportRun.isError && isNotProducible(reportRun.error);
  const vocab = libraryQuery.data?.vocabularies;
  const applied: ReportQuery = {
    ...query,
    columns: previewColumns ?? query.columns,
    from: query.from ?? report?.window.start ?? report?.window.as_of,
    to: query.to ?? report?.window.as_of ?? report?.window.end,
  };

  // ⚠ **THE ROW'S NAME, THEN THE CATALOGUE CARD, THEN THE CATALOGUE KEY** —
  // the same three sources and the same order 2·1 resolves, because a report a
  // utility wrote has its name only in its own row and a REFUSED report has no
  // payload at all. Without the third, thirty-odd screens drew a slug as their
  // title, which is B14 rule 31 reached through a fallback (`DEF-REP-6898`).
  //
  // ⚠ **AND A BLANK BUILDER HAS NO NAME TO RESOLVE, SO IT IS NAMED RATHER
  // THAN LEFT EMPTY** (`DEF-REP-7640`). All three sources are about a report
  // that exists; on `/reports/custom/new` the first two are absent and the
  // third resolves `reports.card..name` to the empty string, which draws a
  // page with no title at all.
  const title = blank
    ? t("reports.edit.newTitle")
    : (report?.name ??
      libraryQuery.data?.cards.find((one) => one.key === key)?.name ??
      t(`reports.card.${key}.name`, { defaultValue: key }));

  // ── `DEF-REP-7640` · WHAT `Save as` REFUSES, AND WHAT IT NAMES ───────────
  //
  // ⚠ **A DISABLED `Save as` WOULD HAVE BEEN THE WRONG FIX.** A blank draft
  // is not saveable, and the obvious way to say so is to grey the button —
  // which is B14 rule 33's *grey means you cannot* over a thing a clerk very
  // much can do, and hard-won law 2's mirror if the reason is never rendered.
  // So the control stays live and the PRESS is refused, naming the one thing
  // that is missing. The server refuses both of these too — an unknown
  // dataset by name — and this is the round trip a clerk is not charged for,
  // exactly as `SaveReportAsModal`'s own schema is.
  //
  // ⚠ **IT IS NOT SCOPED TO THE BLANK BUILDER, DELIBERATELY.** Every standard
  // report arrives with a dataset and columns, so this cannot fire there
  // today — except where a clerk has unticked every column, which is the same
  // empty definition arriving through the other door.
  const missing =
    draft === null
      ? null
      : draft.dataset === ""
        ? t("reports.edit.needDataset")
        : draft.columns.length === 0
          ? t("reports.edit.needColumns")
          : null;

  return (
    <div className="fin-page">
      <PageHeader
        // ⚠ **THE KICKER IS THE STATE AND IT IS ALWAYS ON HERE** — B14 rule 2
        // puts a record's state in the kicker, and p031 callout ⑥ puts the
        // unsaved marker there rather than on a button or in a banner. On the
        // viewer this was conditional because the viewer is two screens; this
        // address is only ever one of them.
        // ⚠ **AND ON A BLANK BUILDER THE STATE IS *NEW*, NOT *EDITING*.**
        // There is nothing to edit yet; a kicker reading EDITING over a report
        // that does not exist is the screen stating something false about
        // itself, which is what rule 2 puts a kicker there to prevent.
        kicker={blank ? t("reports.edit.newEyebrow") : t("reports.edit.eyebrow")}
        title={title}
        // ⚠ **THE BACK ARROW SAYS WHAT IT EXITS TO, AND ON A PAGE THAT IS THE
        // REPORT** — not *Reports*, which is what the drawing shows because on
        // the drawing the arrow belonged to 2·1 and the builder had no address
        // of its own to leave. A clerk who came here from a report and is sent
        // to the library has lost the report. On a blank builder there is no
        // report, so it says **Custom** — see `exitPath`.
        backTo={{
          to: exitPath,
          label: blank ? t("reports.library.tab.custom") : title,
        }}
        secondaryActions={
          <Button variant="ghost" onClick={() => navigate(exitPath)}>
            {t("reports.edit.cancel")}
          </Button>
        }
        primaryAction={
          <Button
            variant="primary"
            // ⚠ **A PRESS ON AN EMPTY DEFINITION IS REFUSED, NOT SWALLOWED**
            // (`DEF-REP-7640`). Opening the dialog over a draft the server
            // will refuse spends a clerk's four fields and a round trip to
            // tell them something this screen already knows.
            onClick={() => {
              if (missing !== null) {
                setRefusal(missing);
                return;
              }
              setRefusal(null);
              setSavingAs(true);
            }}
            // ⚠ **DISABLED UNTIL THERE IS SOMETHING TO SAVE**, which is until
            // the report has answered once and seeded the draft. A `Save as`
            // that opens a dialog over `null` is a control that cannot work.
            // On a blank builder the draft is seeded at first render, so this
            // is false there and the refusal above is what speaks instead.
            disabled={draft === null}
          >
            {t("reports.edit.saveAs")}
          </Button>
        }
        rollup={
          report === undefined ? undefined : (
            <span className="fin-rollup">
              {/* `DEF-REP-7052` — whose money this is, and it goes first. */}
              <ReportSubjectHead head={report.head} />
              <span className="fin-rollup-item">
                {report.window.as_of === undefined
                  ? t("reports.rollup", { from: report.window.start, to: report.window.end })
                  : t("reports.asOf", { date: report.window.as_of })}
              </span>
              {/* BR-REP-001 — the basis, on the page head, before any figure. */}
              <span className="fin-rollup-item">{t(`cells.basis.${report.basis}`)}</span>
              <ReportGrainLine grain={report.grain} t={translate} inline />
            </span>
          )
        }
      />

      {/* ⚠ **THE REFUSAL GOES WHERE THE PRESS WAS, AND IT IS ONE SENTENCE**
          (`DEF-REP-7640`). Rule 32 gives a section one sentence and rule 33
          puts RATIONALE at zero words, so this says what is missing and not
          why a definition needs it. `role="alert"` is how a screen reader
          hears a refusal it did not scroll to. */}
      {refusal === null ? null : (
        <Panel role="alert">
          <p data-report-save-refusal="" className="fin-absent-reason">
            {refusal}
          </p>
        </Panel>
      )}

      {/* The window, the class and the service — the same bar 2·1 carries, so
          a clerk narrows the rows they are previewing without leaving.

          ⚠ **NOT DRAWN ON A BLANK BUILDER** (`DEF-REP-7640`). Every slicer on
          this bar narrows a report that is being RUN, and a report with no key
          cannot be run at all — `REPORT_FILTERS[""]` is empty, so the bar would
          render as an empty grey strip above the sections. An empty frame is
          the shape hard-won law 2's mirror objects to: furniture that looks
          like a control. */}
      {blank ? null : (
        <ReportParamBar actions={null}>
          <ReportParameters
            reportKey={key}
            dataset={report?.dataset}
            query={applied}
            onChange={(next) => update({ ...applied, ...next })}
            vocab={vocab}
            dateFormat={dateFormat}
            timeZone={timeZone}
            today={today}
            t={translate}
            client={client}
          />
        </ReportParamBar>
      )}

      {/* ⚠ **THE SECTIONS LEAD AND THE PREVIEW FOLLOWS, WHICH REVERSES THE
          DRAWING'S COLUMNS ON PURPOSE.** On the panel the table led because the
          table was the screen and the panel was beside it. Here the choosing is
          the screen. DOM order is reading order, so a keyboard and a screen
          reader meet the controls first — and at narrow widths the stack puts
          them first too, rather than after a table. */}
      <div className="flex flex-col items-start gap-4 lg:flex-row">
        {/* ⚠ **384px, NOT 240px.** `lg:w-96` is the scale's step above the
            panel's `lg:w-60`, and the extra 144px is the whole physical answer
            to *"as a user I don't know what I'm doing and how fields are
            shown"*: a filter's name and its value stop competing for one line.
            It is a token on our scale rather than a measurement off the page —
            B14 rule 44, and rule 37 (a drawn figure is an illustration). */}
        <div className="w-full lg:w-96 lg:shrink-0">
          {draft === null ? (
            // ⚠ **A SKELETON WHILE IT IS COMING AND NOTHING WHEN IT IS NOT.**
            // The sections cannot be drawn until the report has answered once,
            // because the draft is seeded FROM that answer. On a refusal the
            // answer is never coming, and a skeleton that spins for ever is a
            // screen making a promise it will not keep — the reason is already
            // on the right, once, where rule 32's budget puts it.
            failed || notProducible ? null : <LoadingSkeleton variant="card" />
          ) : (
            <ReportEditPanel
              variant="page"
              // ⚠ **`DEF-REP-7070` — THE REPORT'S OWN DECLARATION, NOT THIS
              // FILE'S OPINION.** `controls.requires` is the server's; the page
              // composes the chooser because only the page holds the client,
              // and `subject_id` lives in the URL exactly as every other
              // parameter does (`BR-SHL-011`), so a chosen account is
              // bookmarkable and survives a refresh.
              requiredInputs={
                (report?.controls?.requires ?? []).length === 0 ? undefined : (
                  <ReportRequiredInputs
                    requires={report?.controls?.requires}
                    values={{ subject_id: query.subject_id ?? "" }}
                    onChange={(param, value) =>
                      update({ [param]: value === "" ? undefined : value })
                    }
                    client={client}
                    t={translate}
                  />
                )
              }
              dataset={(datasetsQuery.data?.datasets ?? []).find(
                (one) => one.code === draft.dataset,
              )}
              // ⚠⚠ **KEEP THIS OR THE STATEMENT COLLAPSES TO ONE COLUMN**
              // (`DEF-REP-7072`). A report served by a MODULE VIEWER declares
              // its own column vocabulary: the statement serves seven names and
              // the `journal_lines` dataset declares five, and the two lists
              // intersect in `reference` and nothing else. Offering the
              // dataset's instead sends a `columns` control the runner narrows
              // to ONE name — and `tsc`, every DOM case and every gate pass
              // over it. It is `undefined` on all forty-five dataset-backed
              // reports, which go on reading the dataset exactly as they did.
              columnChoices={report?.column_choices}
              datasets={datasetsQuery.data?.datasets ?? []}
              draft={draft}
              // A change to the draft is what clears the refusal: the sentence
              // named a thing that is missing, and the clerk is now supplying
              // things. A refusal that outlives what it refused is the rot
              // this whole defect is an instance of.
              onChange={(next) => {
                setRefusal(null);
                setDraft(next);
              }}
              groups={libraryQuery.data?.groups ?? []}
              onSaveAs={() => setSavingAs(true)}
              onCancel={() => navigate(exitPath)}
            />
          )}
        </div>

        {/* ⚠ **STICKY, SO THE ROWS ARE BESIDE EVERY SECTION AND NOT ONLY THE
            FIRST.** `lg:` only — at narrow widths a sticky block is a block
            covering the thing under it, and below 1280 is not a width this
            staff screen supports anyway (the skill's §6). */}
        <div className="w-full min-w-0 flex-1 lg:sticky lg:top-4">
          {notProducible ? (
            /* The SAME sentence the catalogue card renders, from the same
               function. Rule 33 puts the server's engineering prose — grain,
               datasets, which wave builds it — at zero words on screen. */
            <AbsentPanel
              title={t("reports.premises.unavailableTitle")}
              reason={unavailableSentence(refusalReasonCode(reportRun.error), translate)}
            />
          ) : failed ? (
            <Panel role="alert">
              <h3>{t("finance.error.title")}</h3>
              <p className="fin-absent-reason">{apiErrorText(reportRun.error, translate)}</p>
            </Panel>
          ) : report !== undefined && report.rows.length > 0 ? (
            <ReportSamplePreview
              report={report}
              reportKey={key}
              t={translate}
              locale={props.locale}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
          ) : (
            <>
              {/* ⚠ **THE REASON GOES ABOVE THE SHAPE** (`DEF-REP-7070`). A
                  statement with no account chosen answers nothing, and the
                  sentence that explains it — *A statement opens on one
                  account* — is the first thing a clerk needs, not the last. */}
              {report === undefined ? null : (
                <ReportGapList
                  gaps={report.unavailable}
                  title={t("finance.gap.title")}
                  render={(gap) => gapSentence(gap, translate)}
                />
              )}
              {/* ⚠ **A REPORT THAT HAS NEVER BEEN SAVED HAS NO SHAPE EITHER**
                  (`DEF-REP-7640`). `ReportShapePreview` returns `null` on zero
                  columns — deliberately, because an empty frame under a
                  heading is a promise with nothing behind it — so a blank
                  builder rendered NOTHING in this whole column, and half an
                  empty screen reads as broken. `ReportBlankPreview` says the
                  one true thing instead, and hands over the moment a column is
                  ticked.

                  ⚠ **`blank &&` IS LOAD-BEARING AND IT IS NOT DEFENSIVE.**
                  On a REAL report this branch is also reached while the first
                  answer is still in flight — `report` undefined, `draft` null,
                  `shapeColumns` empty — and *Nothing to show yet.* over a
                  screen that is loading is a false statement, which is the
                  fault this whole defect is an instance of. */}
              {blank && shapeColumns.length === 0 ? (
                <ReportBlankPreview t={translate} />
              ) : (
                <ReportShapePreview
                  columns={shapeColumns}
                  columnMeta={report?.column_meta}
                  t={translate}
                />
              )}
            </>
          )}
        </div>
      </div>

      {!savingAs || draft === null ? null : (
        <SaveReportAsModal
          // ⚠ **A BLANK BUILDER OPENS THE NAME BOX EMPTY** (`DEF-REP-7640`).
          // On a copy the dialog opens on the report a clerk is standing on,
          // which is right — *AR Ageing* becomes *AR Ageing 60+*. There is
          // nothing to stand on here, and prefilling the page's own title
          // would save a report literally called *New report* for every clerk
          // who pressed Save without reading the field. The dialog's schema
          // already refuses an empty name, so the refusal is the server's own
          // rule arriving one field earlier.
          initialName={blank ? "" : title}
          initialGroup={draft.group}
          initialSubGroup={draft.sub_group}
          initialVisibility={draft.visibility}
          groups={libraryQuery.data?.groups ?? []}
          onSave={(values) =>
            saveReportDefinition(
              {
                ...draftToWire(
                  { ...draft, ...values, sub_group: values.sub_group },
                  values.name,
                  // p022 callout ⑤ — WHAT THIS WAS COPIED FROM, so 1·2's
                  // *Based on* column is the difference between a catalogue
                  // and a junk drawer.
                  //
                  // ⚠ **NULL ON A BLANK BUILDER, AND THAT IS THE COLUMN'S
                  // OWN VOCABULARY** (`DEF-REP-7640`). p022 calls a report
                  // with no `based_on` *from scratch* and `reports.edit
                  // .fromScratch` has said so in eleven languages since
                  // `P5.4`. Sending `""` would put an empty string in a
                  // column whose whole job is to name a report.
                  blank ? null : key,
                ),
              },
              client,
            )
          }
          onSaved={(saved) => {
            setSavingAs(false);
            setDraft(null);
            // ⚠ **THE SERVER'S KEY, NEVER A SLUG THIS SCREEN COMPUTED**, and
            // it lands on the VIEWER rather than back in the builder: the act
            // is finished and the clerk wants to read what they just made.
            navigate(`${tenantPath(REPORTS_ROUTE)}/${saved.key}`);
          }}
          onClose={() => setSavingAs(false)}
        />
      )}
    </div>
  );
}

export default ReportEditorPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO ruling 2026-09-28 (12-governance/02-decision-log.md, `d8c4bc1cb`) · CR-142-BRC07 Phase 5 `P5.3`/`P5.11` · 05-prototype/09 Reports Build Brief.pdf p031-p033, rendered at scale 3 and read as IMAGES per B14 rule 42
// screens: 2·2 (A1 S47)
// generated: 2026-09-28 by lane REP-EDITOR-PAGE; AMENDED 2026-09-28 by lane REP-BUILD-YOUR-OWN (`DEF-REP-7640` — the `blank` mode at `/reports/custom/new`, PO ruling of the same day: "Opens the editor on a blank definition, then Save as")
// checklist: A=n/a(no backend half — no endpoint moved; `POST /reports/definitions` already creates from a draft with `based_on: null`) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportEditorPage.dom.test.tsx was shown red on every case before this file existed, and the `columnChoices` case was ALSO run against a copy of this page with the prop removed, where it fails on `1` column against `7`. G31: this file is listed in styles/route-b-migrated.txt in the same commit. [2026-09-28] The seven `DEF-REP-7640` cases were run against this page with `blank` forced false: all seven failed on `Unable to find a label with the text of: Dataset`, because the sections cannot be drawn until a draft exists and the draft was waiting for a report that never comes.
// exceptions: (1) the drawing's live table is GONE and a five-row preview stands in its place — the PO ruled the page with that cost stated (decision log, 2026-09-28) and §1 above is the answer this lane owed · (2) the columns are REVERSED against the drawing: sections left, preview right, because on a page the choosing is the screen · (3) the back arrow reads the REPORT's name and not *Reports* — on the drawing that arrow belonged to 2·1 · (4) `Save` is not drawn at all, only `Save as` (p032's PRIMARY ACTION row: copy-on-write is the rule and the wording is the safety) · (5) section ⑤ draws three levels and the drawing draws five rows — `Subtotals` and `Sort` are `DEF-REP-7200`, filed not built, because honouring them is the runner's half · (6) [`DEF-REP-7640`] on `blank` there is NO preview until the first save and no parameter bar at all — both read a saved report through `GET /reports/{key}`, which a draft with no key cannot reach. The cost is stated on screen in four words (`ReportBlankPreview`) and in the decision log rather than absorbed · (7) [`DEF-REP-7640`] the seven sections stay drawn while they are empty on a blank draft — they are the shape of the builder and they say what choosing a subject will give, where a screen growing three panels under the hand says less
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
