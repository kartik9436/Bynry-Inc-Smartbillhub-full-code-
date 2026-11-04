// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C2.
// Screens: RBS-006 (`S152`) at `/{tenant}/runbooks/{key}/runs/{runId}`.
// Rules:   `07-endpoints.md` rows 9 and 10 · `BR-RBS-020` (frozen at close) ·
//          `NFR-3` · B14 rule 31 · `BR-SHL-023` (one formatting path).
// Tests:   RunResultPage.dom.test.tsx · RunResult.dom.test.tsx
// Defects: DEF-RBS-4284 · DEF-SHL-4283 · DEF-CWP-3925.
// ───────────────────────────────────────────────────────
// THE PAGE THAT FEEDS THE RENDERER, AND THE ONLY PLACE THAT KNOWS THERE IS A
// SERVER. `RunResult` is pure over its view model, exactly as `RunbookSetup` is
// — one definition of what a screen draws, assertable by a unit test, paintable
// by a render-check in a real browser, and drivable by the server.
//
// ══════════════════════════════════════════════════════════════════════════
// THERE **IS** A MAPPER HERE, AND `runbooksEndpoints.ts` ARGUES AGAINST ONE
// ══════════════════════════════════════════════════════════════════════════
// That file's header says the wire shape IS the renderer's shape and that a
// mapper would be "a contract nobody agreed". It was right WHEN IT WAS WRITTEN:
// `D1` had not landed and inventing a payload would have been guessing. `D1`
// has landed, and `GET /runbooks/runs/{id}` serves a RUN ROW —
// `runbook_name`, `started_at`, `took_seconds`, `status`, `counts` — not a
// `RunHeader`. So the two shapes are different, they are different for a good
// reason, and this is the boundary that reconciles them.
//
// ⚠ **THE REPORT IS THE EXCEPTION AND IT IS NOT MAPPED AT ALL.**
// `GET /runbooks/runs/{id}/report` is a passthrough of `runbook_runs.report`,
// and its own docstring names what a helpful serializer would cost: a run
// closed before `DEF-RBS-4284` is frozen in the old shape and one closed after
// it in the new, **and both are correct**, because the report is what was
// composed that day. Translating between them here would rewrite the first
// result this product ever produced. `BR-RBS-020`.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IS NOT HERE, STATED SO NOBODY ASSUMES IT (law 1)
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **RECORDS PAGING GOES NO FURTHER THAN THE FROZEN REPORT, AND THAT IS A
// BOUNDARY RATHER THAN AN OVERSIGHT.** A CHECK over one subject — runbook 1 is
// the only runbook that exists — puts its findings IN the report, so the block
// is handed the whole list with its total and there is exactly one page.
// `GET /runbooks/runs/{id}/records` serves something ELSE: the per-record plan
// and outcome rows a VOLUME runbook writes (`BR-RBS-035`), and no runbook
// writes one yet because nothing writes at all until phase 2. Wiring it now
// would be a query against a table this product cannot fill — dead UI with a
// network call attached.
// `RunResultPage.dom.test.tsx` asserts the boundary by ADDRESS: the day a
// volume runbook lands, that test names this file.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { runbooksApi } from "@/api/runbooksEndpoints";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useTenantRegional } from "@/components/TenantRegional";
import { formatDate } from "@/components/DateCell";
import type { PageSize } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { useTenantPath } from "@/routing/tenantPath";

import { formatTook } from "./home/runbooksHomeModel";
import { RunResult } from "./RunResult";
import type { RunHeader, RunResultView } from "./resultTypes";

/** The run row `GET /runbooks/runs/{id}` actually serves. Named here rather
 *  than in `resultTypes.ts` because it is the WIRE, not the view — and keeping
 *  the two apart is the whole reason this file exists. */
interface RunRow {
  runbook_key: string;
  runbook_name: string;
  status: string;
  started_at: string | null;
  took_seconds: number | null;
  has_report: boolean;
}

/** A run still going cannot be re-run; anything settled can. The reason is a
 *  SENTENCE a clerk reads, capped at six words (B14 rule 33). */
function rerunOf(status: string, t: (k: string) => string): RunHeader["rerun"] {
  return status === "running" || status === "queued"
    ? { enabled: false, reason: t("runbooks.result.rerunBusy") }
    : { enabled: true };
}

export function RunResultPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const showToast = useToast();
  const client = props.client ?? runbooksApi;

  // ⚠ FROM THE REAL PATH PATTERN. `DEF-CWP-3925`: a component mounted bare
  // inside a `MemoryRouter` with no `/:tenant/…` route gets `undefined` here and
  // builds every address as `//host/…` — a protocol-relative URL that reads as
  // a perfectly good string to `toContain`.
  const { tenant = "", key = "", runId = "" } = useParams<{
    tenant: string;
    key: string;
    runId: string;
  }>();

  const [records, setRecords] = useState({ page: 1, per: 50 as PageSize, chip: "all" });

  const headerQuery = useQuery<RunRow>({
    queryKey: ["runbooks", "run", runId],
    queryFn: async () => {
      const response = await client.get<RunRow>(`/runbooks/runs/${encodeURIComponent(runId)}`);
      if (response.data === null) {
        throw new Error(`empty ${response.status} body where the contract promises one`);
      }
      return response.data;
    },
  });

  const reportQuery = useQuery<{ blocks: RunResultView["report"] }>({
    queryKey: ["runbooks", "run", runId, "report"],
    queryFn: async () => {
      const response = await client.get<{ blocks: RunResultView["report"] }>(
        `/runbooks/runs/${encodeURIComponent(runId)}/report`,
      );
      if (response.data === null) {
        throw new Error(`empty ${response.status} body where the contract promises one`);
      }
      return response.data;
    },
  });

  // ⚠ **THE TENANT'S ZONE AND FORMAT COME FROM THE SHELL, NOT FROM
  // `GET /settings/regional`.** That endpoint is Admin-only, and reading it
  // from a screen is `DEF-SHL-4283` — nine components still do, so a Billing
  // Clerk meets a refusal on each. `useTenantRegional()` is what the shell
  // publishes from `GET /shell/display`, which every signed-in role may read.
  const regional = useTenantRegional();

  // ⚠ **THE FIX ROUTES ARE MADE ABSOLUTE HERE — `DEF-RBS-4329`.** A runbook
  // emits `settings/services`; React Router resolves a relative `to` against
  // the CURRENT route, so every Fix link on this screen used to point at
  // `…/runs/<id>/settings/services` and open onto "not built yet". This is the
  // only place in the runbooks screens that knows the tenant, which is why the
  // builder is passed DOWN through the block context rather than looked up in
  // the cell.
  const tenantPath = useTenantPath();

  if (headerQuery.isPending || reportQuery.isPending || regional === null) {
    return <LoadingSkeleton variant="table" />;
  }
  if (headerQuery.isError || reportQuery.isError) {
    return (
      <FailedWithRetry
        title={t("runbooks.result.failedTitle")}
        reason={refusalText(t, headerQuery.error ?? reportQuery.error)}
        onRetry={() => {
          void headerQuery.refetch();
          void reportQuery.refetch();
        }}
        onDownloadReport={() => undefined}
      />
    );
  }

  const row = headerQuery.data;
  const view: RunResultView = {
    header: {
      runbookName: row.runbook_name,
      // An ADDRESS, assembled here where the tenant slug is known, never handed
      // to the renderer as a key for it to guess at.
      runbookTo: `/${tenant}/runbooks/${encodeURIComponent(row.runbook_key ?? key)}`,
      title:
        row.started_at === null
          ? t("runbooks.result.notStarted")
          : `${t("runbooks.result.run")} · ${formatDate(row.started_at, regional.timeZone, regional.dateFormat, true)}`,
      // ⚠ **`formatTook`, NOT `${seconds}s` — `DEF-RBS-4341`.** The server
      // serves a float, so the fourth KPI tile read **`TOOK 8.933829s`** on the
      // real screen the first time it drew. `RBS-006-R1` spells it `12s`, and
      // `runbooksHomeModel.formatTook` already renders exactly that spelling
      // (`12s` · `1m 04s`) for `RBS-001`'s run table. Reaching for a second
      // formatter is how two screens end up disagreeing about the same fact;
      // reaching for the one that already owns the job is the habit CLAUDE.md
      // asks for before writing anything that touches shared ground.
      took: formatTook(row.took_seconds) ?? undefined,
      rerun: rerunOf(row.status, t),
    },
    report: reportQuery.data.blocks,
    records,
  };

  return (
    <RunResult
      view={view}
      ctx={{
        timeZone: regional.timeZone,
        dateFormat: regional.dateFormat,
        toHref: tenantPath,
      }}
      loading={false}
      onRecordsQuery={setRecords}
      // ⚠ **REQUIRED AND WIRED, AND WHAT THEY DO TODAY IS TELL THE TRUTH.**
      // `POST /runbooks/{key}/runs` is task `L` and the download routes are
      // `D1`'s CSVs, which this wave does not reach. The two alternatives are
      // both named in CLAUDE.md and both are worse: a greyed button over a
      // screen that later ships is hard-won law 2's mirror (the customer portal
      // had two working doors out of eight that way), and an optional handler
      // nothing passes is law 2's front half and `G13`'s whole question.
      onRerun={() => showToast(t("runbooks.result.rerunLater"))}
      onDownload={() => showToast(t("runbooks.result.downloadLater"))}
      onDecide={() => showToast(t("runbooks.result.decideLater"))}
      onAct={() => showToast(t("runbooks.result.actLater"))}
    />
  );
}
