// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-001 (EP-RBS-01) · CR-075 wave C task C4 (the wizard) ·
//          `OQ-WRK-12792` → A (PO 2026-10-13, verbatim *"1a, 2A 3A"*; decision
//          log *"THREE PO RULINGS ON THE LEFT-OVER SCREEN PIECES"*).
// Screens: RBS-004.run at `/{tenant}/runbooks/{key}/run` — the Check wizard
//          (`RBS-005`'s frames), a dotted sub-id of the runbook it runs.
// Rules:   `BR-RBS-002` (a Check writes nothing) · `BR-RBS-003` (live only
//          where the engine allows it — the SERVER refuses, by name) ·
//          `RBR-01` (every step listed before the first starts) · B14 rules 1,
//          6, 11, 21, 33, 43 · hard-won law 2 (built is not wired, and its
//          mirror).
// Defects: DEF-WRK-10123 (the wizard was built and never routed; a run started
//          from a small pop-up instead) · DEF-RBS-4286 (no per-step outcome is
//          served, so the progress list says *waiting*, never a guess) ·
//          DEF-RBS-4289 (no draft to save) · DEF-CWP-3925.
// Tests:   RunWizardPage.dom.test.tsx · RunWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// **THE ONE WAY A RUN STARTS.** The PO chose the full-screen wizard over the
// pop-up on 2026-10-13 — the recommendation had been to keep the pop-up — and
// the pop-up was deleted in the same change, so **Run ▶** on the setup page
// and *Run "Can we bill?" ▶* on the Runbooks home both land HERE.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT EACH STEP DOES, AND WHAT IT CANNOT YET DO — SAID PLAINLY (law 1)
// ══════════════════════════════════════════════════════════════════════════
//   1. **Scope.** The runbook's declared inputs and what this tenant set them
//      to (`GET /runbooks/{key}`, the read the setup page makes — one cache
//      key, so arriving from setup costs no request). Settings-owned inputs
//      are shown read-only with their Settings value and link
//      (`RunbookSettingsFields`). The pop-up's two questions are HERE, because
//      a wizard that dropped them would take *Run for real* away from the one
//      runbook that has it: **How to run** for an Action, and the runbook's
//      one-off text inputs (the New World push's *Day*).
//      ⚠ **NO *MATCHES* ROW.** `resolve(params)`'s live count is served by
//      nothing, so the row is not drawn and the button says what it does.
//   2. **Checking.** `POST /runbooks/{key}/runs` answers `202 {job_id}` and
//      this page polls `GET /jobs/{id}` (`api/client.ts::pollJob`). The step
//      list is the runbook's own, every step drawn from the first frame; no
//      per-step outcome is served (`DEF-RBS-4286`), so one step is *current*
//      and the rest are *waiting* — never a tick nobody recorded.
//   3. **Review.** The job's `result_link` names the run, and the page goes
//      to that run's frozen result, `RBS-006` at `/{tenant}/runbooks/{key}/
//      runs/{runId}` — which IS Review's body (`runWizardModel.ts`). So this
//      page never draws the wizard's own `review` and `done` phases; it hands
//      over to the screen that already draws them from the real report.
//   4. **Failed.** A job that ends `failed`, or a poll that gives up, is the
//      wizard's `checkFailed` state with *Try again ▶*. **Stop**, *Save as
//      draft* and *Tell support* are not drawn: no route stops a run, there
//      is no draft, and there is no in-app support destination.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import type { ApiClient, JobPollOptions } from "@/api/client";
import { api, isApiError, pollJob } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { ButtonLink } from "@/components/Button";
import { SelectField, TextField } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { RunbookSettingsFields, RunbookSettingsProvider } from "../RunbookSettingsFields";
import { settingValue } from "../setupModel";
import { settingsFieldRows } from "../setupScope";
import type { SetupValue } from "../setupTypes";
import { getRunbookDetail, startRun } from "../setupWire";
import { RunWizard } from "./RunWizard";
import type { RunInputRow } from "./RunWizard";
import type { RunPhase } from "./runWizardModel";

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** A key–value cell as one string — the wizard's inputs table takes text. */
function valueText(value: SetupValue, t: Translate): string {
  if (value.kind === "text") return value.text;
  if (value.kind === "pill") return value.label;
  return t("runbooks.setup.absent");
}

/**
 * The run the job made, from its `result_link` (`/api/runbooks/runs/{id}`,
 * `scheduler.run_scheduled_job`). `null` when the link names no run — then
 * the page says the check could not finish rather than inventing an address.
 */
export function runIdFromResultLink(link: string | null): string | null {
  if (link === null) return null;
  const match = /\/runbooks\/runs\/([^/?#]+)\/?$/.exec(link);
  return match === null ? null : decodeURIComponent(match[1]);
}

export function RunWizardPage(props: { client?: ApiClient; poll?: JobPollOptions }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const path = useTenantPath();
  const navigate = useNavigate();
  const showToast = useToast();
  const { timeZone, dateFormat } = useRegional({});
  // ⚠ FROM THE REAL PATH PATTERN (`DEF-CWP-3925`); the test mounts this page
  // under `/:tenant/runbooks/:key/run`, never bare.
  const { key = "" } = useParams<{ key: string }>();

  const [phase, setPhase] = useState<RunPhase>("scoping");
  const [mode, setMode] = useState<"dry" | "live">("dry");
  // A one-off day typed for this run is never the next run's answer: the
  // inputs live in this page's state and start EMPTY on every visit.
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const inFlight = useRef(false);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const detail = useQuery({
    // The setup page's own key — the same payload, so arriving from **Run ▶**
    // reads the cache instead of the network.
    queryKey: ["runbooks", "setup", key],
    queryFn: () => getRunbookDetail(key, client),
    enabled: key !== "",
  });

  if (detail.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const body = detail.data;
  if (body === undefined && isApiError(detail.error) && detail.error.status === 404) {
    // `DEF-WRK-10124` — this utility has not added the runbook yet (the home's
    // *Run "Can we bill?"* before runbook 1 is added). Not a failure to load:
    // the door is the template's own page, where *Add to my runbooks* lives.
    return (
      <div className="flex flex-col items-start gap-3 border border-divider p-6" data-run-wizard="not-added">
        <p className="m-0 font-heading text-base font-semibold">{t("runbooks.run.notAdded")}</p>
        <ButtonLink variant="primary" to={path(`/runbooks/templates/${encodeURIComponent(key)}`)}>
          {t("runbooks.run.addFromTemplates")}
        </ButtonLink>
      </div>
    );
  }
  if (body === undefined) {
    return (
      <FailedWithRetry
        title={t("runbooks.setup.failedTitle")}
        reason={refusalText(t, detail.error)}
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const runbookTo = path(`/runbooks/${encodeURIComponent(key)}`);
  const parameters = body.parameters ?? [];
  const ctx = { t, timeZone, dateFormat };
  // Settings-owned inputs are drawn by `RunbookSettingsFields` with Settings'
  // value; text inputs are this run's one-off answers. Neither goes in the
  // table, where its value would be the runbook's declared default.
  const textInputs = parameters.filter((one) => one.type === "text");
  const tableRows: RunInputRow[] = parameters
    .filter((one) => one.type !== "ref:setting" && one.type !== "text")
    .map((one) => ({ id: one.name, label: one.label, value: valueText(settingValue(one, ctx), t) }));
  const settingsFields = settingsFieldRows(parameters);
  const isAction = body.kind === "action";
  const live = isAction && mode === "live";

  const start = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    const chosen = Object.fromEntries(
      Object.entries(inputs).filter(([, value]) => value.trim() !== ""),
    );
    let jobId: string;
    try {
      const accepted = await startRun(key, { mode: isAction ? mode : "dry", parameters: chosen }, client);
      jobId = accepted.job_id;
    } catch (error) {
      // A refusal BEFORE anything was queued — *this runbook runs dry only*,
      // an input the declaration refuses. The server's sentence, and the clerk
      // stays on Scope to change the answer.
      inFlight.current = false;
      showToast(refusalText(t, error));
      return;
    }
    setPhase("checking");
    const controller = new AbortController();
    abort.current = controller;
    try {
      const job = await pollJob(client, jobId, { ...props.poll, signal: controller.signal });
      const runId = job.status === "succeeded" ? runIdFromResultLink(job.result_link) : null;
      if (runId === null) {
        setPhase("checkFailed");
      } else {
        navigate(path(`/runbooks/${encodeURIComponent(key)}/runs/${encodeURIComponent(runId)}`));
      }
    } catch {
      if (!controller.signal.aborted) setPhase("checkFailed");
    } finally {
      inFlight.current = false;
    }
  };

  const controls =
    isAction || textInputs.length > 0 || settingsFields.length > 0 ? (
      <>
        {isAction && (
          <SelectField
            id="run_mode"
            label={t("runbooks.setup.run.mode")}
            value={mode}
            onChange={(next) => setMode(next === "live" ? "live" : "dry")}
            options={[
              { value: "dry", label: t("runbooks.setup.run.dry") },
              { value: "live", label: t("runbooks.setup.run.live") },
            ]}
          />
        )}
        {textInputs.map((one) => (
          <TextField
            key={one.name}
            id={`run_${one.name}`}
            label={one.label}
            help={t("runbooks.setup.run.blankDefault")}
            value={inputs[one.name] ?? ""}
            onChange={(value) => setInputs({ ...inputs, [one.name]: value })}
          />
        ))}
        <RunbookSettingsFields fields={settingsFields} />
      </>
    ) : null;

  return (
    <RunbookSettingsProvider parameters={parameters} client={client}>
      <RunWizard
        runbookName={body.name}
        runbookTo={runbookTo}
        phase={phase}
        inputs={tableRows}
        matches={null}
        matchesValue={null}
        live={live}
        scopeControls={controls}
        steps={(body.definition?.steps ?? []).map((step) => ({ key: step.key, label: step.label }))}
        // Nothing serves a per-step outcome (`DEF-RBS-4286`): an empty map is
        // the honest state, and every row says *waiting* or *Never reached*.
        outcomes={{}}
        // Review and Done are `RBS-006`'s, reached by address (see the header):
        // these five are never drawn by this page.
        doneTiles={[]}
        doneHeadline=""
        needsYou={[]}
        needsYouSubjectLabel=""
        downloads={[]}
        review={null}
        onStart={() => void start()}
        onSaveDraft={null}
        onCancel={() => navigate(runbookTo)}
        onStop={null}
        onRetry={() => void start()}
        onTellSupport={null}
        onStepSelect={(step) => {
          // B14 rule 3: only a step already passed is clickable, and the only
          // one this page can be past is Scope — after a failed check.
          if (step === "scope") setPhase("scoping");
        }}
      />
    </RunbookSettingsProvider>
  );
}

export default RunWizardPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: OQ-WRK-12792 → A (PO 2026-10-13) · DEF-WRK-10123 · US-RBS-001 · CR-075 wave C task C4
// generated: 2026-10-13 by the runbook-wizard + settings-field lane
// checklist: A✔ B✔ C✔ D✔(GET /runbooks/{key} · POST /runbooks/{key}/runs · GET /jobs/{id}) E✔ F✔ G✔ H=n/a
// gates: vitest RunWizardPage.dom.test.tsx · G40 · G13 · G31 · tsc
// exceptions: no Matches count (nothing serves it) · no per-step outcomes (DEF-RBS-4286) · Stop / Save as draft / Tell support not drawn (no route, no draft, no destination) · Review and Done hand over to RBS-006 by address
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
