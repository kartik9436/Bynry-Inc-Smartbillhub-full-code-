// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-SHL-6377` — the Product Owner pressed *Download error report*
//          on a failed property sale (`TRF-02`, *"The sale was not recorded.
//          Nothing changed hands."*) and reported *"Unable to download error
//          report"*. Measured the same day: the button called
//          `onDownloadReport={() => undefined}` on 99 of its 101 call sites and
//          the wizard frame's `noop` on the 100th.
// Rules:   A18 §4 · CLAUDE.md hard-won law 2 (built is not wired) and law 11
//          (a 99-file edit collides with every lane in those files) · B14 rule
//          43 (a piece of UI is a COMPONENT, not standalone code in a page)
// ───────────────────────────────────────────────────────
// THE *DOWNLOAD ERROR REPORT* BUTTON, AND THE REPORT IT DOWNLOADS — FOR EVERY
// FAILURE PANEL AT ONCE.
//
// ⚠ **WHY THE BUTTON BUILDS ITS OWN REPORT RATHER THAN ASKING THE SCREEN FOR
// ONE.** A18 §4 drew the button for an import that PRODUCES an error file, and
// the prop was required — so every later screen that used the panel for an
// ordinary failed load or a refused commit satisfied it with a handler that
// did nothing. There was never a report to hand over. Everything a useful one
// needs is already known without the screen: WHICH screen (the router's
// address, through the same register the corner tag reads), WHEN (the
// utility's zone, published by the shell), WHICH BUILD (`package.json`, the
// footer's source), WHAT the clerk was told (the panel's own two sentences) and
// WHICH REQUEST was refused (`api/failedRequests.ts`, noted by the transport).
// So the button assembles it and every one of the 101 call sites gains a
// working button without being edited.
//
// ⚠ **A CALLER'S OWN HANDLER STILL RUNS, AFTER THE DOWNLOAD.** A screen whose
// operation really produces a file can still hang its own action on the press;
// the report is on its way first, because a handler that navigates takes the
// page with it.
//
// ⚠ **WHY IT READS THE ROUTER RATHER THAN `window.location`, AND NEEDS NO
// ROUTER.** In the product the two agree — the app is one browser router — but
// a panel rendered under a memory router (every routed test in this repo)
// would otherwise name the wrong screen. `useInRouterContext` picks the branch
// once per mount, so no hook is ever called conditionally, and a panel drawn
// outside any router (static render tests) still renders and still downloads.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useInRouterContext, useLocation } from "react-router-dom";

import { APP_VERSION } from "./BuildVersion";

import { Button } from "./Button";
import { buildErrorReport, saveTextFile } from "./errorReport";
import { useTenantRegional } from "./TenantRegional";

import { lastFailedRequestSince } from "@/api/failedRequests";
import { resolveScreen } from "@/routing/screenIds";

/**
 * How long before the panel appeared a refusal may have arrived and still be
 * the one it is about. A refusal lands milliseconds before its panel draws; a
 * minute is generous for a slow retry and short enough that a failure from an
 * earlier visit is not blamed on this one.
 */
export const REFUSAL_WINDOW_MS = 60_000;

export interface ErrorReportButtonProps {
  /** The panel's two sentences, exactly as drawn. */
  title: string;
  reason: string;
  diagnostic?: string | null;
  /** A caller's own action, run AFTER the report has been handed to the browser. */
  onAfterDownload?: () => void;
}

interface Where {
  pathname: string;
  search: string;
}

/** The button. Routed or not, it downloads. */
export function ErrorReportButton(props: ErrorReportButtonProps) {
  return useInRouterContext() ? (
    <RoutedErrorReportButton {...props} />
  ) : (
    <ErrorReportButtonAt {...props} where={null} />
  );
}

function RoutedErrorReportButton(props: ErrorReportButtonProps) {
  const location = useLocation();
  return <ErrorReportButtonAt {...props} where={location} />;
}

function ErrorReportButtonAt(props: ErrorReportButtonProps & { where: Where | null }) {
  const { t } = useTranslation();
  const regional = useTenantRegional();
  // When the panel appeared — the button mounts with it and unmounts with it.
  const [shownAt] = useState(() => Date.now());

  function download(): void {
    const where = props.where ?? {
      pathname: window.location.pathname,
      search: window.location.search,
    };
    const screen = resolveScreen(where.pathname, where.search);
    // The register names staff screens; the customer portal keeps its own and
    // writes its id on `<body>` (`ScreenIdTag`'s machine-readable half), so
    // that is the fallback rather than a guess.
    const screenId = screen.r10 ?? (document.body.dataset.screenId || null);
    const report = buildErrorReport({
      screenId,
      pathname: where.pathname,
      search: where.search,
      at: Date.now(),
      timeZone: regional?.timeZone ?? null,
      version: APP_VERSION,
      title: props.title,
      reason: props.reason,
      diagnostic: props.diagnostic ?? null,
      request: lastFailedRequestSince(shownAt - REFUSAL_WINDOW_MS),
    });
    saveTextFile(report.fileName, report.text);
    props.onAfterDownload?.();
  }

  return (
    <Button variant="secondary" onClick={download} data-error-report="">
      {t("states.failed.downloadReport")}
    </Button>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-6377 (lane ERROR-REPORT)
// generated: 2026-09-23 by lane ERROR-REPORT
// tests: src/components/ErrorReport.dom.test.tsx — pressed under the real
//        `/:tenant/transfers/new` route; proved RED on 18818920f first
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ (at tip d351e5fee) · eslint --max-warnings 0✔ on the changed files · G31✔ G35✔ G123✔ G39✔ G42✔ · vitest ErrorReport.dom.test.tsx 5/5✔ (proved RED on 18818920f) · StateFrame/WizardFrame/DataTable/client suites✔
// exceptions: no className at all — the kit's `Button` carries every visual
//        (B14 rule 21 is therefore not engaged, and nothing is added to
//        `route-b-migrated.txt`)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
