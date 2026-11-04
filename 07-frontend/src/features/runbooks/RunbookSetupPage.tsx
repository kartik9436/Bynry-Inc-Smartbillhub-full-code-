// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 (CR-075 wave C task C3) · **US-RBS-040
//          (CR-075 wave E tasks E4 and E6)** — the mapper, the Activity tab
//          over real data, and the two commits that stopped refusing.
// Screens: RBS-004 (`S150`) at `/{tenant}/runbooks/{key}`, tabs at `#steps` …
// Rules:   `07-endpoints.md` row 2 (`GET`), row 3 (`PUT`), row 8 (the Runs
//          tab's page) · `NFR-3` (server pagination) · `BR-RBS-038` (every
//          edit writes a version; a template change is OFFERED, never applied)
//          · `BR-SHL-020` (a refusal is plain language) · B14 rule 32.
// Defects: DEF-RBS-4308 (the wire and the view model never met — this page is
//          where they meet) · DEF-RBS-4311 (a live route behind a dead
//          control) · DEF-CWP-3925 (mount under the REAL path pattern).
// Tests:   RunbookSetupPage.dom.test.tsx · setupModel.test.ts
// ───────────────────────────────────────────────────────
// THE PAGE THAT FEEDS THE RENDERER, AND WHY IT IS A SECOND FILE.
//
// `RunbookSetup` is PURE over its view model: no fetch, no query key, no
// router beyond the tab hash. That is what lets the same component be asserted
// by a unit test, painted by the render-check in a real browser, and driven by
// the server, all from one definition of what it draws. This file is the only
// place that knows there is a server at all.
//
// ══════════════════════════════════════════════════════════════════════════
// TWO READS, NOT ONE — AND THAT IS `NFR-3` RATHER THAN A CONVENIENCE
// ══════════════════════════════════════════════════════════════════════════
// `GET /runbooks/{key}` carries the runbook's FACTS. `RBS-004.6`'s Runs tab is
// `GET /runbooks/runs?f.runbook={key}`, which is already a paged list with a
// runbook filter, already ordered on a total key in SQL, already tested against
// 51 rows. The C3 draft sent `runs_page`/`runs_per` to the detail route and the
// endpoint has never read either — two paging surfaces over one list is
// `G114`'s whole subject, and three shipped Work screens drew empty tables over
// exactly that. So the page number lives here, travels to the history route,
// and the renderer draws the page it is handed. Nothing anywhere slices an
// array.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT STOPPED REFUSING IN WAVE E, AND WHAT IS STILL HELD — SAID PLAINLY
// ══════════════════════════════════════════════════════════════════════════
// `DEF-RBS-4311`: **Change limits** and **Pause** were refusing over
// `PUT /runbooks/{key}`, which landed the same day the hold was written. That
// is hard-won law 2's mirror — the customer portal had two working doors out of
// eight this way, five cards refusing over screens shipped days earlier, with
// `tsc`, 42 test files, 391 cases and every gate green over it. Both now call
// the route.
//
//   * **Change limits** → `PUT {cap, gate_mode}`. The two fields `RBS-004.5`
//     draws that `services.EDITABLE_SETTINGS` accepts.
//   * **Pause / Resume** → `PUT {enabled}`. One fact, no form.
//   * **Review →** (the template-update offer) → `PUT {accept_template_update:
//     true}`. `BR-RBS-038`: offered, never applied, and this press is the
//     *pressed*.
//   * **Change scope** NOW OPENS — `CR-075` wave `T`, and the hold that stood
//     here was TRUE right up until it was not. `EDITABLE_SETTINGS` held eight
//     schedule-and-limit fields and no parameter value, so the button had
//     nothing to write (`DEF-RBS-4338`); wave `T` added `runbooks.parameters`,
//     the domain route and the ninth editable setting, and **the hold-expiry
//     test in `RunbookSetupPage.test.tsx` went red naming this button on the
//     commit that added `listParameterDomain` to `setupWire.ts`** — which is a
//     lane tripping the clock while doing the very work that expires the hold,
//     rather than a promise nobody was keeping. It is turned around rather than
//     deleted: the same case now asserts that the button WRITES.
//   * **Run ▶** NOW OPENS — `CR-173-BRC10` (2026-10-07) built
//     `POST /runbooks/{key}/runs`, and the export-surface case in
//     `RunbookSetupPage.test.tsx` went red on `startRun` exactly as it was
//     written to.
//   * ⚠ **AND FROM 2026-10-13 IT IS A LINK TO THE CHECK WIZARD, NOT A POP-UP**
//     (`OQ-WRK-12792` → A, PO verbatim *"1a, 2A 3A"*; `DEF-WRK-10123`). The
//     small dialog that asked *Dry run* or *Run for real* and the runbook's
//     text inputs is DELETED, not hidden: the wizard at
//     `/{tenant}/runbooks/{key}/run` (`RBS-004.run`) asks the same two things
//     and is the ONE way a run starts. The recommendation had been to keep the
//     pop-up; the PO chose the wizard. `startRun` is now called from
//     `run/RunWizardPage.tsx` and from nowhere here.
//   * Settings-owned inputs are read by `RunbookSettingsProvider`, which wraps
//     the whole page so the Scope tab and the scope dialog read ONE answer
//     (`OQ-WRK-12793` → A, `DEF-WRK-10122`).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { useParams } from "react-router-dom";
import { useTenantPath } from "@/routing/tenantPath";

import type { ApiClient } from "@/api/client";
import { api, formErrorEnvelope, isApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import type { PageSize } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { useRegional } from "@/features/metering/meteringShared";

import { RunbookSettingsProvider } from "./RunbookSettingsFields";
import { RunbookSetup } from "./RunbookSetup";
import { ScopeModal } from "./ScopeModal";
import { toSetupView } from "./setupModel";
import { editRunbook, getRunbookDetail, listRunsForRunbook } from "./setupWire";
import type { RunbookDetailBody } from "./setupWire";
import { LIMITS_SCHEMA, limitsDraft, limitsToWire } from "./setupLimits";
import type { LimitsDraft } from "./setupLimits";
import { scopeDraft, scopeToWire } from "./setupScope";
import type { ScopeDraft } from "./setupScope";

/** The schedule dialog's draft: by hand, or once a day at a local time. */
interface ScheduleDraft {
  runs: "manual" | "schedule";
  time: string; // "HH:MM", on the utility's own clock
}

const SCHEDULE_SCHEMA = z.object({
  runs: z.enum(["manual", "schedule"]),
  time: z.string().refine((value) => /^([01]\d|2[0-3]):[0-5]\d$/.test(value.trim()), {
    message: "errors.val-002",
  }),
});

/** A stored `M H * * *` read back as `HH:MM`; anything else starts at 06:00. */
function scheduleDraftOf(schedule: { trigger_kind: string; cron: string | null }): ScheduleDraft {
  const parts = (schedule.cron ?? "").trim().split(/\s+/);
  const daily = parts.length === 5 && parts.slice(2).every((one) => one === "*");
  const minute = Number(parts[0]);
  const hour = Number(parts[1]);
  const time =
    daily && Number.isInteger(minute) && Number.isInteger(hour)
      ? `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`
      : "06:00";
  return { runs: schedule.trigger_kind === "schedule" ? "schedule" : "manual", time };
}

/** PUT body. The time zone is the UTILITY's (Settings → regional), so 21:30
 *  means 21:30 where the utility is — PO 2026-10-07 Q2/Q6. */
function scheduleToWire(draft: ScheduleDraft, zone: string) {
  if (draft.runs === "manual") return { trigger_kind: "manual" };
  const [hour, minute] = draft.time.trim().split(":").map(Number);
  return { trigger_kind: "schedule", cron: `${minute} ${hour} * * *`, timezone: zone };
}

export function RunbookSetupPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const showToast = useToast();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional({});
  const path = useTenantPath();

  // ⚠ THE SLUG FROM THE REAL PATH PATTERN. `DEF-CWP-3925`: a component mounted
  // bare inside a `MemoryRouter` with no `/:tenant/…` route gets `undefined`
  // from `useParams()` and builds every address as `//portal/…` — a
  // protocol-relative URL to another host that reads as a perfectly good string
  // to `toContain`. The tests for this screen mount `APP_ROUTES` at a real
  // address for exactly that reason.
  const { key = "" } = useParams<{ key: string }>();

  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const [limits, setLimits] = useState<LimitsDraft | null>(null);
  // `null` is *the scope sheet is shut*. A draft is built from the SERVER's
  // current answer each time it opens, never remembered between openings — a
  // form seeded from anything but the server can silently re-send a stale value.
  const [scope, setScope] = useState<ScopeDraft | null>(null);
  // `CR-173-BRC10` — the schedule's own editor. Seeded from the server's
  // answer each time it opens, never remembered between openings.
  const [scheduleDraft, setScheduleDraft] = useState<ScheduleDraft | null>(null);

  const detail = useQuery<RunbookDetailBody>({
    // ONE key from the whole request. The literal prefix is this screen's own
    // and is deliberately not in `api/queryClient.ts`: three lanes were
    // appending to that shared file the hour this was written, and two lanes
    // appending to one module is mechanism two of hard-won law 11.
    queryKey: ["runbooks", "setup", key],
    queryFn: () => getRunbookDetail(key, client),
    enabled: key !== "",
  });

  const runs = useQuery({
    queryKey: ["runbooks", "setup-runs", key, page, per],
    queryFn: () => listRunsForRunbook(key, { page, per }, client),
    enabled: key !== "",
  });

  /** Every write on this screen lands the same way: the server's own new
   *  payload replaces the cached one, so seven tabs redraw from one object and
   *  nothing refetches what it was just told. */
  const write = useMutation({
    mutationFn: (body: Parameters<typeof editRunbook>[1]) => editRunbook(key, body, client),
    onSuccess: (updated) => {
      queryClient.setQueryData(["runbooks", "setup", key], updated);
      // The catalogue and the library both draw this runbook's state, so their
      // cached pages are now stale. The whole prefix goes rather than one key:
      // a row that says *Paused* over a runbook that is running is the same lie
      // one screen over.
      void queryClient.invalidateQueries({ queryKey: ["runbooks"] });
      setLimits(null);
      setScope(null);
    },
    onError: (error) => showToast(refusalText(t, error)),
  });

  if (detail.isPending) {
    return <LoadingSkeleton variant="card" />;
  }

  const body = detail.data;
  if (body === undefined) {
    // The whole screen fails, not one tab: the page head, the tab counts and
    // every tab body come from this one payload, so there is nothing honest to
    // draw around a failure.
    return (
      <FailedWithRetry
        title={t("runbooks.setup.failedTitle")}
        reason={refusalText(t, detail.error)}
        onRetry={() => void detail.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const view = toSetupView(
    body,
    { page, per, loading: runs.isPending, data: runs.data },
    { t, timeZone, dateFormat },
  );

  /** What a control does before its endpoint exists: says so, in one sentence.
   *
   *  ⚠ **THE SENTENCE NAMES NO WAVE, NO TASK AND NO RULE ID.** B14 rule 32:
   *  no rule id or internal code in clerk-facing copy. *"Not connected yet"* is
   *  what a clerk needs; which wave connects it is this comment's job and the
   *  test's, not the screen's. */
  return (
    <RunbookSettingsProvider parameters={body.parameters ?? []} client={client}>
      {/* `E3` — *Template updated · 1 new step · Review →*, and pressing it is
          the ONLY thing in this product that applies it (`BR-RBS-038`). The
          counts are the server's; the words are the catalogue's, because
          *Template updated* is the same sentence for all 26 runbooks and
          *1 new step* is not. Nothing is drawn when there is nothing on offer. */}
      {body.template_update !== null && (
        <div
          className="mt-4 flex flex-wrap items-center gap-3 border-l-4 border-l-warning-500 px-4 py-3"
          data-template-update=""
        >
          <p className="m-0 text-base font-bold text-neutral-900">
            {t("runbooks.setup.update.offered", {
              added: body.template_update.steps_added,
              removed: body.template_update.steps_removed,
            })}
          </p>
          <Button
            size="sm"
            onClick={() => write.mutate({ accept_template_update: true })}
            disabled={write.isPending}
          >
            {t("runbooks.setup.update.review")}
          </Button>
        </div>
      )}

      <RunbookSetup
        view={view}
        runTo={path(`/runbooks/${encodeURIComponent(key)}/run`)}
        onPauseToggle={() => write.mutate({ enabled: body.enabled === false })}
        onChangeScope={() => setScope(scopeDraft(body.parameters ?? []))}
        onChangeLimits={() => setLimits(limitsDraft(body))}
        onChangeSchedule={() => setScheduleDraft(scheduleDraftOf(body.schedule))}
        onRunsPage={setPage}
        onRunsPer={(next) => {
          setPer(next);
          // A new page size is a new list, so it starts at page 1. Leaving the
          // page number alone is how a person lands on an empty page 3 of a
          // 2-page result and reads it as "nothing here".
          setPage(1);
        }}
      />

      {/* `RBS-004.3` — **Change scope**, which stopped refusing in wave `T`
          (`BR-RBS-042`, `DEF-RBS-4338`). The whole document travels, because a
          delta cannot say *put this input back to what it shipped with*; the
          word *all* travels as the word, because expanding it here is the one
          mistake the rule exists to prevent. */}
      {scope !== null && (
        <ScopeModal
          runbookKey={key}
          parameters={body.parameters ?? []}
          draft={scope}
          onChange={setScope}
          onClose={() => setScope(null)}
          client={client}
          onSubmit={async () => {
            try {
              await write.mutateAsync(scopeToWire(scope, body.parameters ?? []));
              return { ok: true };
            } catch (error) {
              // The SERVER's sentence, never one this screen invented: only the
              // server can say *this utility does not sell Trash*, because only
              // the server can read this tenant's domain.
              if (isApiError(error)) {
                return { ok: false, error: formErrorEnvelope(error) };
              }
              return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
            }
          }}
        />
      )}

      {scheduleDraft !== null && (
        <FormModal
          title={t("runbooks.setup.schedule.title")}
          schema={SCHEDULE_SCHEMA}
          values={scheduleDraft}
          submitLabel={t("runbooks.setup.schedule.save")}
          onClose={() => setScheduleDraft(null)}
          onSubmit={async () => {
            try {
              await write.mutateAsync(scheduleToWire(scheduleDraft, timeZone));
              setScheduleDraft(null);
              return { ok: true };
            } catch (error) {
              if (isApiError(error)) {
                return { ok: false, error: formErrorEnvelope(error) };
              }
              return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
            }
          }}
        >
          <SelectField
            id="schedule_runs"
            label={t("runbooks.setup.schedule.runs")}
            value={scheduleDraft.runs}
            onChange={(runs) =>
              setScheduleDraft({ ...scheduleDraft, runs: runs === "schedule" ? "schedule" : "manual" })
            }
            options={[
              { value: "manual", label: t("runbooks.setup.schedule.byHand") },
              { value: "schedule", label: t("runbooks.setup.schedule.daily") },
            ]}
          />
          {scheduleDraft.runs === "schedule" && (
            <TextField
              id="schedule_time"
              label={t("runbooks.setup.schedule.time")}
              help={t("runbooks.setup.schedule.timeHelp", { zone: timeZone })}
              value={scheduleDraft.time}
              onChange={(time) => setScheduleDraft({ ...scheduleDraft, time })}
            />
          )}
        </FormModal>
      )}

      {limits !== null && (
        <FormModal
          title={t("runbooks.setup.limits.change")}
          schema={LIMITS_SCHEMA}
          values={limits}
          submitLabel={t("runbooks.setup.limits.save")}
          onClose={() => setLimits(null)}
          onSubmit={async () => {
            try {
              await write.mutateAsync(limitsToWire(limits));
              return { ok: true };
            } catch (error) {
              // The SERVER's sentence, never one this screen invented —
              // `services.update_runbook` refuses a frozen field BY NAME and
              // `refusalText` is where that key becomes words.
              if (isApiError(error)) {
                return { ok: false, error: formErrorEnvelope(error) };
              }
              return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
            }
          }}
        >
          <TextField
            id="cap"
            numeric
            label={t("runbooks.setup.limits.mostPerRun")}
            help={t("runbooks.setup.limits.capHelp")}
            value={limits.cap}
            onChange={(cap) => setLimits({ ...limits, cap })}
          />
          <SelectField
            id="gate_mode"
            label={t("runbooks.setup.limits.approval")}
            value={limits.gate_mode}
            onChange={(gate_mode) => setLimits({ ...limits, gate_mode })}
            options={[
              {
                value: "approve_each_run",
                label: t("runbooks.setup.gate.approve_each_run"),
              },
              {
                value: "approved_up_front",
                label: t("runbooks.setup.gate.approved_up_front"),
              },
            ]}
          />
        </FormModal>
      )}
    </RunbookSettingsProvider>
  );
}

export default RunbookSetupPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · US-RBS-001 (wave C task C3) · US-RBS-040 (wave E tasks E4, E6)
// generated: 2026-09-06 by the CR-075 wave C · C3 build lane
// amended:   2026-09-06 by the CR-075 wave E · E4/E5/E6 lane — the mapper
//            (DEF-RBS-4308), the Runs tab's own read, and three commits that
//            stopped refusing over routes that had landed (DEF-RBS-4311)
// checklist: A✔ B✔ C✔ D✔(GET /runbooks/{key} · PUT /runbooks/{key} · GET /runbooks/runs) E✔ F✔
//         G✔ H=deferred(PO 2026-08-09)
// gates: tsc (local install, never npx) · vitest RunbookSetupPage.dom.test.tsx · G13 · G40
// exceptions: `Run ▶` (wave L) and `Change scope` (no parameter-values store,
//         DEF-RBS-4338) still refuse; each carries a hold-expiry test that goes
//         red the day its route exists
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
