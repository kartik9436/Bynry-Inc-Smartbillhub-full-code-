// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run (`/:tenant/billing/run`), the Bills
//           page's `Run` door
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/*.png (72 images, 36 states)
//           + inventory.md; mock-up mockup.html
// Stories:  US-BIL-036 … US-BIL-041 · journey J72
// Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md F1–F19
// Rules:    changes rows 9–46 (PO 2026-09-30) · B14 rules 21, 31, 32, 33, 36,
//           40, 42, 43, 44 · BR-SHL-018/019 (the wizard frame) · BR-SHL-025 (a
//           refused control says why) · hard-won law 2 (the door; the mirror)
// Defects:  DEF-BIL-8200 (two run screens — this is the one) · DEF-BIL-8216…8224
// ───────────────────────────────────────────────────────
/**
 * THE BILL RUN — ONE PAGE, FOUR STEPS: Scope · Check · Sign off · Send.
 *
 * It replaces the six-step `BillRunWizard` and the unreachable four-step
 * `RunWizardShell` (changes row 9; `DEF-BIL-8200`), both deleted with it.
 *
 * ## The steps and what each one writes
 *
 *   1. **Scope** — reads `GET /billing/runs/scope-preview` whenever a field
 *      changes; `Start checking` is `POST /billing/runs` (name and template
 *      always sent). Disabled while any refusal stands (`Fix N things first.`).
 *   2. **Check** — starts the Check as a job (`POST …/check`) and shows its
 *      `n of N` (`GET …/check`, DEF-BIL-8224); reads the SERVER's grouped
 *      findings (`GET …/check/findings`, DEF-BIL-8216) a tag or an account at
 *      a time; answers a tag (`…/check/decisions`), fixes a row through the
 *      owning module (`…/check/fix`), leaves a ready account out or puts it
 *      back, re-checks named accounts; `Price N accounts` starts `…/calculate`
 *      as a job and shows its progress (Calculating).
 *   3. **Sign off** — reads `…/sign-off-summary` (every figure, DEF-BIL-8220),
 *      `…/not-in-run` (paged) and `…/breaks`; `Sign off` is `…/release` with
 *      the five confirmations, each recorded separately.
 *   4. **Send** — `Send N bills` (danger tier) is `…/issue`; Sent reads the run
 *      back and Not in this run with each account's Pending-billing state; a
 *      selection starts `…/catch-up` or is left for the next cycle; the
 *      *Check report* tab reads `…/check/report` (the Check as at Send).
 *
 * ## Re-opening a run
 *
 * `?run=<id>` (the address `PastBillingRunsPanel` and every *Open BR-…* link
 * build) re-opens the run at the step its phase names: a draft at Check, a
 * calculated run at Sign off, an authorised one at Send, an issued one Sent.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient, JobRecord } from "@/api/client";
import {
  checkReadsKey,
  checkSummaryKey,
  createBulkRun,
  decideCheck,
  fixCheck,
  getCheckSummary,
  getRunCheck,
  getRunTemplates,
  getScopePreview,
  getSignOffSummary,
  getIssueProgress,
  issueRunMaybeBackground,
  leaveForNextCycle,
  leaveOutAccounts,
  recheckAccounts,
  resumeCheck,
  scopePreviewKey,
  signOffSummaryKey,
  startCheck,
  touchRunPresence,
} from "@/api/bulkRunEndpoints";
import type { CheckTag, FixHere, RunCheckState, ScopeFields, ScopePreview, ServedNotInRunRow } from "@/api/bulkRunEndpoints";
import { startCatchUpRun } from "@/api/billingOpsEndpoints";
import { getCycles, getTenantServices, releaseBillRun } from "@/api/endpoints";
import type { CycleRow } from "@/api/endpoints";
import type { Translator } from "@/components/FormModal";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { SubTabs } from "@/components/SubTabs";
import { FailedWithRetry } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import type { PageSize } from "@/components/tableTypes";
import { WizardFrame, initialWizardNav, jumpBackTo } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { ASSETS_ROUTE } from "@/features/assets/assetsShared";
import { ACCOUNT_NEW_ROUTE, ACCOUNTS_ROUTE, accountDetailPath } from "@/features/customers/customersShared";
import { CELL_FULL, PREMISES_ROUTE, unitDetailPath, useAccessCell, useRegional } from "@/features/metering/meteringShared";
import { READS_ROUTE } from "@/features/metering/readsShared";
import { PAYMENTS_ROUTE } from "@/features/payments/paymentsShared";
import { cycleDetailPath } from "@/features/tenancy/routesCyclesShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BILLING_PENDING_ROUTE } from "../billingOpsShared";
import { BILLING_PERMISSION, BILLING_ROUTE } from "../billingShared";
import { billRunPath, prefillFromCycle } from "../billRunShared";
import type { RunScopeForm } from "../billRunShared";
import {
  billRunBreaksKey,
  billRunDetailKey,
  billRunReadLockKey,
  billRunTotalsKey,
  calculateBillRunMaybeBackground,
  discardBillRun,
  getBillRun,
  getBillRunBreaks,
  getBillRunReadLock,
  getBillRunTotals,
  getJobRecord,
  retryBillRunBreak,
} from "../billRunEndpoints";
import { BILLING_PRINT_ROUTE } from "../PrintBillsPage";

import { ProgressPanel, RUN_PARAM, span } from "./bulkRunShared";
import type { RunFormat } from "./bulkRunShared";
import { TAGS } from "./bulkRunTaxonomy";
import type { FixScreen } from "./bulkRunTaxonomy";
import { CheckReport } from "./CheckReport";
import { CheckStep } from "./CheckStep";
import { READY_TAG } from "./CheckPanes";
import type { CheckLinks, CheckPaneActions, EstimateValues, FixValues } from "./CheckPanes";
import { NOT_IN_RUN_FIRST_PER, NotInRunList, getNotInRunPage, notInRunListKey } from "./NotInRunList";
import type { NotInRunFilter } from "./NotInRunList";
import { RunSummaryCard } from "./RunSummaryCard";
import type { CheckResult, RunFacts } from "./RunSummaryCard";
import {
  CycleDetails,
  PreviousRuns,
  RunCovers,
  ScopeListPanel,
  ScopeProblems,
  WhatToBill,
  scopeDueDate,
} from "./ScopeStep";
import type { ScopeLinks, ScopeListLinks, TemplateOption } from "./ScopeStep";
import { CatchUpStarted, NotSentPanel, SendCard, SentCard } from "./SendStep";
import {
  ByCustomerType,
  CONFIRMATIONS,
  FailedToDraftPanel,
  PaymentsAndBalances,
  RunSummaryPanel,
  SignOffConfirmations,
  SignOffWarnings,
  standingWarnings,
  warningLineCount,
  UsageAndCharges,
  WhoIsBilled,
} from "./SignOffStep";
import type { Confirmation } from "./SignOffStep";

const PREVIEW_DEBOUNCE_MS = 350;
const JOB_POLL_MS = 1000;
const PLANS_RATES_ROUTE = "/plans-rates";
const SETTINGS_ROUTE = "/settings";
const RUN_HISTORY_ROUTE = `${BILLING_ROUTE}/history`;

export function emptyFields(): ScopeFields {
  return { label: "", cycle_id: "", period_start: "", period_end: "", bill_date: "", due_days: "", template_id: "" };
}

/** The cycle's next period, bill date and days to pay, offered once — never
 *  over a value the clerk typed (the old wizard's `prefillFromCycle`). */
export function prefilled(fields: ScopeFields, cycle: CycleRow | null): ScopeFields {
  const form: RunScopeForm = {
    cycleId: fields.cycle_id,
    periodStart: fields.period_start,
    periodEnd: fields.period_end,
    billDate: fields.bill_date,
    dueDays: fields.due_days,
    services: [],
  };
  const next = prefillFromCycle(form, cycle);
  return {
    ...fields,
    period_start: next.periodStart,
    period_end: next.periodEnd,
    bill_date: next.billDate,
    due_days: next.dueDays,
  };
}

/** The Calculating panel's state: the job's n of N and, during its first pass,
 *  `stage: "preparing"` (DEF-BIL-9010). */
export interface CalculatingState {
  progress: { done: number; total: number; stage?: string } | null;
}

/** DEF-BIL-9010 — a job's progress as the panel draws it; a total the server
 *  does not know yet stays null rather than becoming a guessed number. */
function calculatingProgress(progress: unknown): CalculatingState["progress"] {
  if (progress === null || typeof progress !== "object") return null;
  const p = progress as { done?: number; total?: number | null; stage?: string };
  if (typeof p.done !== "number" || typeof p.total !== "number") return null;
  return { done: p.done, total: p.total, ...(p.stage ? { stage: p.stage } : {}) };
}

/** The step a re-opened run opens at, from its served phase — and Check while
 *  a Calculate job is still live, whatever drafts it has written (DEF-BIL-9010). */
export function stepForRun(run: {
  phase: string;
  calculating?: { status: string } | null;
  checking?: { status: string } | null;
}): { step: number; sent: boolean } {
  for (const live of [run.calculating, run.checking]) {
    if (live && (live.status === "queued" || live.status === "running")) return { step: 2, sent: false };
  }
  return stepForPhase(run.phase);
}

/** The step a re-opened run opens at, from its served phase. */
export function stepForPhase(phase: string | null | undefined): { step: number; sent: boolean } {
  if (phase === "issued") return { step: 4, sent: true };
  if (phase === "authorised") return { step: 4, sent: false };
  if (phase === "calculated") return { step: 3, sent: false };
  return { step: 2, sent: false };
}

export interface BulkRunPageProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: RunFormat["dateFormat"];
}

export function BulkRunPage(props: BulkRunPageProps) {
  const { t } = useTranslation();
  const translate: Translator = useCallback((key, params) => t(key, params) as string, [t]);
  const client = props.client ?? api;
  const regional = useRegional(props);
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const runId = params.get(RUN_PARAM);

  const cell = useAccessCell(BILLING_PERMISSION, client);
  const readOnlyReason = cell === null || cell === CELL_FULL ? null : translate("billing.rbac.readOnly");

  const [fields, setFields] = useState<ScopeFields>(emptyFields);
  const [debounced, setDebounced] = useState<ScopeFields>(fields);
  const [prevPage, setPrevPage] = useState(1);
  const [prevPer, setPrevPer] = useState<PageSize>(50);
  const [panel, setPanel] = useState<"nobody" | "missingMeter" | null>(null);
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav);
  const [sent, setSent] = useState(false);
  const [calculating, setCalculating] = useState<CalculatingState | null>(null);
  const [working, setWorking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [checkFocus, setCheckFocus] = useState<{ tag: string | null; account: string | null } | null>(null);
  const [ticked, setTicked] = useState<ReadonlySet<Confirmation>>(new Set());
  const [signedOffAt, setSignedOffAt] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [sending, setSending] = useState(false);
  // DEF-BIL-8422 — the issue job's n of N while Send runs.
  const [sendProgress, setSendProgress] = useState<{ done: number; total: number } | null>(null);
  const [notInFilter, setNotInFilter] = useState<NotInRunFilter>("all");
  const [breaksOpen, setBreaksOpen] = useState(false);
  const [notSentOpen, setNotSentOpen] = useState(false);
  const [retried, setRetried] = useState<ReadonlySet<string>>(new Set());
  const [catchUp, setCatchUp] = useState<{ id: string; accounts: number } | null>(null);
  const [sentTab, setSentTab] = useState<"sent" | "report">("sent");
  // DEF-BIL-9255 — Discard a DRAFT run (the confirm, its in-flight flag, and
  // the server's refusal sentence when it says no).
  const [discardOpen, setDiscardOpen] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [discardRefusal, setDiscardRefusal] = useState<string | null>(null);
  const opened = useRef<string | null>(null);
  // DEF-BIL-8809 — the run whose phase has been read and whose step is on
  // screen. Until then the step on screen is not the run's, so a read gated on
  // the step alone would wait for the run read.
  const [seenRun, setSeenRun] = useState<string | null>(null);
  const runSeen = runId !== null && seenRun === runId;

  const fmtCurrency = "USD";
  const fmt: RunFormat = { t: translate, currency: fmtCurrency, ...regional };

  // ── The run ───────────────────────────────────────────────────────────────
  const runQuery = useQuery({
    queryKey: runId === null ? ["bulk-run", "none"] : billRunDetailKey(runId),
    queryFn: () => getBillRun(runId as string, client),
    enabled: runId !== null,
    retry: false,
  });
  const run = runQuery.data ?? null;
  useEffect(() => {
    if (run === null || opened.current === run.id) return;
    opened.current = run.id;
    const at = stepForRun(run);
    setNav({ step: at.step, reached: at.step } as WizardNavState);
    setSent(at.sent);
    setSeenRun(run.id);
    setFields((was) => ({
      ...was,
      // DEF-BIL-8680 — the name the clerk typed, served on the run.
      label: run.label ?? was.label,
      cycle_id: run.scope.cycle_id ?? was.cycle_id,
      period_start: run.scope.period_start ?? was.period_start,
      period_end: run.scope.period_end ?? was.period_end,
      bill_date: run.scope.bill_date ?? was.bill_date,
      due_days: run.scope.due_days === null ? was.due_days : String(run.scope.due_days),
    }));
  }, [run]);

  const step = nav.step;
  // DEF-BIL-8809 — a cold open used to ask for every screen read only once the
  // run read had answered (~2.5 s at 40,008 bills), then queue them on three
  // web workers. The reads that Sign off AND Send both show — the Check's
  // findings summary, the drafts' summary, the breaks, Not in this run's first
  // page — key on the run id the address already carries, so they start BESIDE
  // the run read. A read only one phase shows (Sign off's figures, the Check
  // job's state) still waits for the phase. A run that is still at Check pays
  // for three of them it does not draw yet; at Check they are cheap (no drafts)
  // and the clerk's next step draws them.
  const beforePhase = runId !== null && !runSeen;
  const atOrPast = (at: number) => runId !== null && (beforePhase || step >= at);
  // In the order a cold open of a sent run needs them: Not in this run's
  // first page, the Sent card's total, its not-sent count (DEF-BIL-8809).
  const today = new Date().toISOString().slice(0, 10);
  // DEF-BIL-8809 — Not in this run's first page, in exactly the form the list
  // asks for it (all groups, page 1, 50, as at today), started beside the run
  // read; the list mounting later finds it answered.
  useQuery({
    queryKey: notInRunListKey(runId ?? "", "all", 1, NOT_IN_RUN_FIRST_PER, today),
    queryFn: () => getNotInRunPage(runId as string, "all", 1, NOT_IN_RUN_FIRST_PER, today, client),
    enabled: atOrPast(3),
    retry: false,
  });
  // DEF-BIL-8809 (server half) — the summary's headline alone: the page draws
  // its bills and amount and nothing else of the panel, which cost ~1.1 s at
  // 40,008 bills on the read the Sent card waits for.
  const summaryQuery = useQuery({
    queryKey: runId === null ? ["bulk-run", "no-summary"] : billRunTotalsKey(runId),
    queryFn: () => getBillRunTotals(runId as string, client),
    enabled: atOrPast(3),
    retry: false,
  });
  const breaksQuery = useQuery({
    queryKey: runId === null ? ["bulk-run", "no-breaks"] : billRunBreaksKey(runId, false),
    queryFn: () => getBillRunBreaks(runId as string, false, client),
    enabled: atOrPast(3),
    retry: false,
  });

  // ── Lookups ───────────────────────────────────────────────────────────────
  const cyclesQuery = useQuery({ queryKey: ["bulk-run", "cycles"], queryFn: () => getCycles(client), retry: false });
  // DEF-BIL-8222 — every bill template with a published version; a draft is
  // absent here and still refused by name at Start (*must be published*).
  const templatesQuery = useQuery({ queryKey: ["bulk-run", "templates"], queryFn: () => getRunTemplates(client), retry: false });
  // DEF-BIL-8809 — the services filter is drawn only beside Scope (the aside's
  // `scope` facts), so a re-opened run asks for it only if the clerk goes back
  // there; it is not one of the reads a cold open of a run queues behind.
  const servicesQuery = useQuery({
    queryKey: ["bulk-run", "services"],
    queryFn: () => getTenantServices(client),
    enabled: runId === null || (runSeen && nav.step === 1),
    retry: false,
  });
  const cycles = useMemo(() => cyclesQuery.data ?? [], [cyclesQuery.data]);
  const templates: TemplateOption[] = useMemo(
    () =>
      (templatesQuery.data?.rows ?? []).map((row) => ({
        value: row.id,
        label: translate("billing.bulkRun.scope.templateVersion", { name: row.name, version: row.version_no }),
      })),
    [templatesQuery.data, translate],
  );
  const services = (servicesQuery.data ?? []).filter((row) => row.enabled).map((row) => row.service);

  // ── Scope preview (debounced) ─────────────────────────────────────────────
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(fields), PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [fields]);
  const previewQuery = useQuery({
    queryKey: scopePreviewKey(debounced, prevPage, prevPer),
    queryFn: () => getScopePreview(debounced, prevPage, prevPer, client),
    enabled: runId === null && debounced.cycle_id !== "",
    retry: false,
    placeholderData: (previous) => previous,
  });
  const preview: ScopePreview | null = runId === null && fields.cycle_id !== "" ? (previewQuery.data ?? null) : null;

  const update = useCallback(
    (patch: Partial<ScopeFields>) => {
      setFields((was) => {
        const next = { ...was, ...patch };
        if (patch.cycle_id !== undefined && patch.cycle_id !== was.cycle_id) {
          return prefilled(next, cycles.find((c) => c.id === patch.cycle_id) ?? null);
        }
        return next;
      });
      setPrevPage(1);
    },
    [cycles],
  );
  // One published template → chosen for the clerk (DEF-BIL-8222).
  useEffect(() => {
    if (fields.template_id === "" && templates.length === 1) {
      setFields((was) => ({ ...was, template_id: templates[0].value }));
    }
  }, [templates, fields.template_id]);

  // ── The Check: its job (n of N, DEF-BIL-8224) and its served summary ──────
  const checkStateKey = ["bulk-run", runId, "check-state"] as const;
  const checkStateQuery = useQuery({
    queryKey: checkStateKey,
    queryFn: () => getRunCheck(runId as string, client),
    // DEF-BIL-8809 — the job's n of N is drawn on Check alone; Sent never shows it.
    enabled: runSeen && step === 2 && !sent,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.job?.status;
      return status === "queued" || status === "running" ? JOB_POLL_MS : false;
    },
  });
  const job = checkStateQuery.data?.job ?? null;
  const jobRunning = job !== null && (job.status === "queued" || job.status === "running");
  const checkSummaryQuery = useQuery({
    queryKey: runId === null ? ["bulk-run", "no-check"] : checkSummaryKey(runId),
    queryFn: () => getCheckSummary(runId as string, client),
    enabled: atOrPast(2) && !jobRunning,
    retry: false,
  });
  const checkSummary = checkSummaryQuery.data ?? null;
  const tiles = checkSummary?.tiles ?? null;

  const refreshChecks = useCallback(() => {
    setRefusal(null);
    if (runId === null) return;
    void queryClient.invalidateQueries({ queryKey: checkReadsKey(runId) });
    void queryClient.invalidateQueries({ queryKey: ["bulk-run", runId, "check-state"] });
    void queryClient.invalidateQueries({ queryKey: ["bulk-run", runId, "not-in-run"] });
  }, [queryClient, runId]);

  // The job finishing is what makes the saved Check readable again.
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !jobRunning) refreshChecks();
    wasRunning.current = jobRunning;
  }, [jobRunning, refreshChecks]);

  // Sign off's figures, every one served (DEF-BIL-8220, changes row 37).
  const signOffQuery = useQuery({
    queryKey: runId === null ? ["bulk-run", "no-sign-off"] : signOffSummaryKey(runId),
    queryFn: () => getSignOffSummary(runId as string, client),
    // DEF-BIL-8809 — Sign off's figures are drawn on Sign off and on Send
    // before it is sent (the warnings line); a SENT run shows neither.
    enabled: runSeen && step >= 3 && !sent,
    retry: false,
  });
  const summary = summaryQuery.data ?? null;
  const signOffSummary = signOffQuery.data ?? null;
  // DEF-BIL-8512 / F4 — who else has this run open, said every 30 s.
  const presenceQuery = useQuery({
    queryKey: ["bulk-run", runId, "presence"],
    queryFn: () => touchRunPresence(runId as string, client),
    enabled: runId !== null,
    retry: false,
    refetchInterval: 30_000,
  });
  const alsoHere = (presenceQuery.data?.others ?? []).map((row) => row.name);
  // DEF-BIL-8421, DEF-BIL-8581 — a SEND break (a bill Send could not issue) is listed apart
  // from the bills Calculate could not draft; each has its own panel and retry.
  const allBreaks = breaksQuery.data?.breaks ?? [];
  const breaks = allBreaks.filter((row) => row.stage !== "send");
  const sendBreaks = allBreaks.filter((row) => row.stage === "send");

  // ── Links (every one goes somewhere — changes row 42) ────────────────────
  const scopeLinks: ScopeLinks = {
    cycle: (id) => tenantPath(cycleDetailPath(id)),
    run: (id) => tenantPath(billRunPath(id)),
    allRuns: tenantPath(RUN_HISTORY_ROUTE),
  };
  const screenPath = (screen: FixScreen, accountId: string | null): string => {
    switch (screen) {
      case "accounts":
        return tenantPath(accountId === null ? ACCOUNTS_ROUTE : accountDetailPath(accountId));
      case "meterReads":
        return tenantPath(READS_ROUTE);
      case "plans":
        return tenantPath(PLANS_RATES_ROUTE);
      case "assets":
        return tenantPath(ASSETS_ROUTE);
      case "premises":
        return tenantPath(PREMISES_ROUTE);
      case "payments":
        return tenantPath(PAYMENTS_ROUTE);
      default:
        return tenantPath(SETTINGS_ROUTE);
    }
  };
  // DEF-BIL-8221 — the unit, on the tab where the fix starts (new tab).
  const scopeListLinks: ScopeListLinks = {
    addAccount: (unitId) => `${tenantPath(unitDetailPath(unitId))}?tab=account`,
    fitMeter: (unitId) => `${tenantPath(unitDetailPath(unitId))}?tab=assets`,
    account: (accountId) => screenPath("accounts", accountId),
  };
  // Record links (PO 2026-10-19) — every account number the wizard prints
  // opens that account, in a new tab like the Check panes' own cell.
  const accountHref = (accountId: string) => screenPath("accounts", accountId);
  const checkLinks: CheckLinks = { fix: screenPath, unit: (unitId) => tenantPath(unitDetailPath(unitId)) };

  // ── Check actions ─────────────────────────────────────────────────────────
  const refusalOf = (error: unknown) =>
    isApiError(error)
      ? translate(error.messageKey, { ...error.params, defaultValue: translate("billing.bulkRun.problemGeneric") })
      : translate("billing.bulkRun.problemGeneric");

  // DEF-BIL-8747 — a Send the server STOPPED (the same fault on bill after
  // bill) names its stop; any other failed Send keeps the generic line.
  const sendStopReason = (stopped: { message_key: string; params: Record<string, unknown> } | null | undefined) =>
    stopped == null
      ? translate("billing.bulkRun.problemGeneric")
      : translate(stopped.message_key, { ...stopped.params, defaultValue: translate("billing.bulkRun.problemGeneric") });

  /** One write, then the reads it changed — refused writes say why. */
  async function act(write: () => Promise<unknown>) {
    if (runId === null) return;
    if (readOnlyReason !== null) {
      setRefusal(readOnlyReason);
      return;
    }
    setWorking(true);
    setRefusal(null);
    try {
      await write();
      refreshChecks();
    } catch (error) {
      setRefusal(refusalOf(error));
    } finally {
      setWorking(false);
    }
  }

  // DEF-BIL-8224 — the Check runs as a job; its record gives n of N.
  async function runCheck() {
    await act(async () => {
      const started = await startCheck(runId as string, client);
      // DEF-BIL-9004 — the accepted job IS the Check's state from this moment.
      // The Check read takes ~2 s at 40,015 accounts, and until it answered
      // the old results stood with Price still pressable.
      if (started.background && started.job_id !== undefined) {
        const job = { id: started.job_id, status: "queued", progress: null, error: null };
        queryClient.setQueryData<RunCheckState>(checkStateKey, (was) => (was === undefined ? was : { ...was, job }));
      }
    });
  }
  // A run nobody has checked yet is checked on opening, once.
  const autoChecked = useRef<string | null>(null);
  // DEF-BIL-8417 — the run whose first Check has RETURNED. Until it has, a run
  // with no saved Check is being checked (the job may run inline, in the start
  // request itself), and the step says so rather than drawing 0 tiles.
  const [firstCheckDone, setFirstCheckDone] = useState<string | null>(null);
  useEffect(() => {
    const state = checkStateQuery.data;
    if (runId === null || step !== 2 || sent || state === undefined || jobRunning) return;
    if (state.counts.accounts > 0 || state.counts.checked_at !== null || autoChecked.current === runId) return;
    if (readOnlyReason !== null) return;
    autoChecked.current = runId;
    const started = runId;
    void runCheck().finally(() => setFirstCheckDone(started));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkStateQuery.data, runId, step, sent, jobRunning, readOnlyReason]);

  const checkActions: CheckPaneActions = {
    onDecide: (
      tag: CheckTag,
      choice: string,
      accountIds: readonly string[] | "all",
      reason?: string,
      serviceCode?: string | null,
      estimate?: EstimateValues,
    ) =>
      void act(() =>
        decideCheck(
          runId as string,
          accountIds === "all"
            ? { case: tag.code, choice, scope: "all", ...(reason === undefined ? {} : { reason }) }
            : {
                case: tag.code,
                choice,
                scope: "accounts",
                account_ids: [...accountIds],
                ...(serviceCode === undefined || serviceCode === null ? {} : { service_code: serviceCode }),
                ...(reason === undefined ? {} : { reason }),
                ...(estimate === undefined ? {} : { amount: estimate.amount, unit: estimate.unit }),
              },
          client,
        ),
      ),
    // DEF-BIL-8219 / DEF-BIL-8286 — a re-check names its accounts, and the
    // category a change touched when it knows it.
    onRecheck: (accountIds: readonly string[], categories?: readonly string[]) => {
      const ids = [...new Set(accountIds.filter((id) => id !== ""))];
      if (ids.length === 0) {
        refreshChecks();
        return;
      }
      void act(() => recheckAccounts(runId as string, ids, client, categories));
    },
    onFix: (accountId: string, fix: Exclude<FixHere, null>, values: FixValues) =>
      void act(() => fixCheck(runId as string, { account_id: accountId, fix, ...values }, client)),
    onLeaveOut: (accountIds: readonly string[], back: boolean) =>
      void act(() => leaveOutAccounts(runId as string, accountIds, back, client)),
  };

  // ── Step 1 → 2: create the run ───────────────────────────────────────────
  async function startChecking(): Promise<true | string> {
    if (runId !== null) return true;
    if (readOnlyReason !== null) return readOnlyReason;
    try {
      const created = await createBulkRun(fields, client);
      const id = created.id ?? created.run_id ?? null;
      if (id === null) return translate("billing.bulkRun.problemGeneric");
      opened.current = id;
      setSeenRun(id);
      setParams((was) => {
        const next = new URLSearchParams(was);
        next.set(RUN_PARAM, id);
        return next;
      });
      return true;
    } catch (error) {
      void previewQuery.refetch();
      if (isApiError(error) && error.fieldErrors.length > 0) {
        return translate("billing.bulkRun.scope.fixFirst", { count: error.fieldErrors.length });
      }
      return refusalOf(error);
    }
  }

  // ── Step 2 → 3: price the run (a job with progress) ──────────────────────
  async function price(): Promise<true | string> {
    if (runId === null) return translate("billing.bulkRun.problemGeneric");
    if (readOnlyReason !== null) return readOnlyReason;
    setCalculating({ progress: null });
    try {
      const outcome = await calculateBillRunMaybeBackground(runId, client);
      if (outcome.background) {
        for (;;) {
          const job: JobRecord = await getJobRecord(outcome.job_id, client);
          setCalculating({ progress: calculatingProgress(job.progress) });
          if (job.status === "succeeded") break;
          if (job.status === "failed") return translate("billing.bulkRun.calculating.failed");
          await new Promise((resolveTimer) => setTimeout(resolveTimer, JOB_POLL_MS));
        }
      }
      void queryClient.invalidateQueries({ queryKey: billRunDetailKey(runId) });
      return true;
    } catch (error) {
      return refusalOf(error);
    } finally {
      setCalculating(null);
    }
  }

  // DEF-BIL-9010 — a run re-opened while its Calculate job is still live shows
  // that job's progress (and stays on Check) until it ends, then the run read
  // is asked again and opens on Sign off as before. Same poll as `price`.
  const followed = useRef<string | null>(null);
  const mounted = useRef(true);
  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );
  const liveCalculate = run?.calculating ?? null;
  useEffect(() => {
    if (runId === null || liveCalculate === null || calculating !== null) return;
    if (liveCalculate.status !== "queued" && liveCalculate.status !== "running") return;
    if (followed.current === liveCalculate.id) return;
    followed.current = liveCalculate.id;
    const jobId = liveCalculate.id;
    setCalculating({ progress: calculatingProgress(liveCalculate.progress) });
    void (async () => {
      try {
        for (;;) {
          const job: JobRecord = await getJobRecord(jobId, client);
          if (!mounted.current) return;
          setCalculating({ progress: calculatingProgress(job.progress) });
          if (job.status !== "queued" && job.status !== "running") break;
          await new Promise((resolveTimer) => setTimeout(resolveTimer, JOB_POLL_MS));
        }
      } catch {
        // the run read below says where the run is; a failed poll draws nothing new
      } finally {
        if (mounted.current) {
          setCalculating(null);
          opened.current = null; // re-derive the step from the fresh run read
          void queryClient.invalidateQueries({ queryKey: billRunDetailKey(runId) });
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, liveCalculate?.id, liveCalculate?.status]);

  // ── Step 3 → 4: sign off (release, five facts) ───────────────────────────
  async function signOff(): Promise<true | string> {
    if (runId === null) return translate("billing.bulkRun.problemGeneric");
    if (run?.phase === "authorised" || signedOffAt !== null) return true;
    if (readOnlyReason !== null) return readOnlyReason;
    try {
      const released = await releaseBillRun(
        runId,
        {
          confirmations: {
            compliance: ticked.has("compliance"),
            email_mandate: ticked.has("email_mandate"),
            sms_mandate: ticked.has("sms_mandate"),
            autopay_mandate: ticked.has("autopay_mandate"),
            final: ticked.has("final"),
          },
          confirmed_at: new Date().toISOString(),
        },
        client,
      );
      setSignedOffAt(released.confirmed_at ?? new Date().toISOString());
      // DEF-BIL-8685 — the run detail now names who signed off; read it again.
      void queryClient.invalidateQueries({ queryKey: billRunDetailKey(runId) });
      return true;
    } catch (error) {
      return refusalOf(error);
    }
  }

  // ── Step 4: send ─────────────────────────────────────────────────────────
  async function send(): Promise<WizardCommitOutcome> {
    if (runId === null) return { ok: false, reason: translate("billing.bulkRun.problemGeneric") };
    setSending(true);
    setSendProgress(null);
    try {
      const outcome = await issueRunMaybeBackground(runId, { issued_at: new Date().toISOString() }, client);
      if (outcome.background) {
        // DEF-BIL-8710 — the Send's own read, which hands a Send whose worker
        // died back to the billing worker (`GET /jobs/{id}` never did).
        for (;;) {
          const job = (await getIssueProgress(runId, outcome.job_id, client)).job;
          setSendProgress(job?.progress ?? null);
          if (job === null || job.status === "succeeded") break;
          if (job.status === "failed") return { ok: false, reason: sendStopReason(job.stopped) };
          await new Promise((resolveTimer) => setTimeout(resolveTimer, JOB_POLL_MS));
        }
      }
      setSent(true);
      void queryClient.invalidateQueries({ queryKey: billRunDetailKey(runId) });
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: refusalOf(error) };
    } finally {
      setSending(false);
    }
  }

  // DEF-BIL-8421 / F3 — *Retry failed*: a new sign-off row for the bills
  // that are still drafts (release.py: a second authorised release is a
  // second row), then Send with nothing named — the run's remaining drafts,
  // which after a Send are exactly the failed ones. A sent bill is not a draft
  // and cannot go twice. The press is the confirmation, and its consequence is
  // stated on the panel.
  async function retryFailed() {
    if (runId === null) return;
    setWorking(true);
    setRefusal(null);
    try {
      const now = new Date().toISOString();
      await releaseBillRun(
        runId,
        {
          confirmations: {
            compliance: true,
            email_mandate: true,
            sms_mandate: true,
            autopay_mandate: true,
            final: true,
          },
          confirmed_at: now,
        },
        client,
      );
      const outcome = await issueRunMaybeBackground(runId, { issued_at: now }, client);
      if (outcome.background) {
        for (;;) {
          const job = (await getIssueProgress(runId, outcome.job_id, client)).job;
          setSendProgress(job?.progress ?? null);
          if (job === null || job.status === "succeeded") break;
          if (job.status === "failed") {
            setRefusal(sendStopReason(job.stopped));
            break;
          }
          await new Promise((resolveTimer) => setTimeout(resolveTimer, JOB_POLL_MS));
        }
      }
    } catch (error) {
      setRefusal(refusalOf(error));
    } finally {
      setWorking(false);
      void queryClient.invalidateQueries({ queryKey: billRunDetailKey(runId) });
      void queryClient.invalidateQueries({ queryKey: billRunBreaksKey(runId, false) });
    }
  }

  async function retryBreak(accountId: string) {
    if (runId === null) return;
    setWorking(true);
    try {
      await retryBillRunBreak(runId, accountId, client);
      setRetried((was) => new Set(was).add(accountId));
      void queryClient.invalidateQueries({ queryKey: billRunTotalsKey(runId) });
    } catch (error) {
      setRefusal(refusalOf(error));
    } finally {
      setWorking(false);
    }
  }

  async function startCatchUp(accountIds: readonly string[]) {
    if (runId === null || accountIds.length === 0) return;
    setWorking(true);
    try {
      const child = await startCatchUpRun(runId, { account_ids: [...accountIds] }, client);
      setCatchUp({ id: child.id, accounts: accountIds.length });
    } catch (error) {
      setRefusal(refusalOf(error));
    } finally {
      setWorking(false);
    }
  }

  // DEF-BIL-8223 — left in Pending billing, marked for the NEXT cycle.
  async function nextCycle(accountIds: readonly string[]) {
    if (runId === null || accountIds.length === 0) return;
    await act(() => leaveForNextCycle(runId, accountIds, new Date().toISOString(), client));
  }

  const goToCheck = (tag: string | null, account: string | null) => {
    setCheckFocus({ tag, account });
    setNav((was) => jumpBackTo(was, 2));
  };

  // DEF-BIL-9255 — throw a DRAFT run away. The server is the gate (a bill out,
  // a sign-off or a catch-up child refuses); the button only appears where the
  // run still reads draft and nothing has been signed or sent on this screen.
  const canDiscard =
    run !== null && run.status === "draft" && run.phase !== "authorised" && !sent && !sending && readOnlyReason === null;
  async function discard() {
    if (runId === null) return;
    setDiscarding(true);
    setDiscardRefusal(null);
    try {
      await discardBillRun(runId, client);
      setDiscardOpen(false);
      void queryClient.invalidateQueries({ queryKey: billRunDetailKey(runId) });
      opened.current = null;
      setNav(initialWizardNav());
      setParams((was) => {
        const next = new URLSearchParams(was);
        next.delete(RUN_PARAM);
        return next;
      });
    } catch (error) {
      setDiscardOpen(false);
      setDiscardRefusal(isApiError(error) ? refusalOf(error) : translate("billing.runDiscard.failed"));
    } finally {
      setDiscarding(false);
    }
  }

  // ── Derived facts ─────────────────────────────────────────────────────────
  const cycle = cycles.find((c) => c.id === fields.cycle_id) ?? null;
  const cycleName = cycle === null ? null : cycle.name === null ? cycle.code : `${cycle.code} · ${cycle.name}`;
  const templateName = templates.find((option) => option.value === fields.template_id)?.label ?? null;
  const dueDate = scopeDueDate(fields, preview);
  const facts: RunFacts = {
    runNo: run?.run_no ?? null,
    label: fields.label,
    cycleName,
    periodStart: fields.period_start,
    periodEnd: fields.period_end,
    billDate: fields.bill_date,
    dueDays: fields.due_days,
    dueDate,
    templateName,
  };
  // DEF-BIL-8691 — an overlap refuses the period without making it unreadable:
  // the aside still shows the period the clerk typed (D1 03).
  const refusalFields = new Set(
    (preview?.refusals ?? [])
      .filter((p) => p.code !== "period_overlap")
      .map((p) => p.field)
      .filter((f): f is string => f !== null),
  );
  const checkResult: CheckResult | null =
    tiles === null ? null : { ready: tiles.ready, decision: tiles.decisions, blocked: tiles.blocked };
  // DEF-BIL-8554 — the accounts Calculate will price, never every Ready one.
  const toPrice = tiles === null ? null : (tiles.to_price ?? tiles.ready);
  const neverChecked =
    runId !== null &&
    !sent &&
    readOnlyReason === null &&
    firstCheckDone !== runId &&
    checkStateQuery.data !== undefined &&
    checkStateQuery.data.counts.accounts === 0 &&
    checkStateQuery.data.counts.checked_at === null;
  // …and until the summary read has caught up with the Check that ran: a read
  // taken while the first Check was running says `checked: false` with 0
  // tiles, and drawing it would be the same false zero (DEF-BIL-8417).
  const summaryBehind =
    runId !== null &&
    !sent &&
    refusal === null &&
    checkSummary !== null &&
    !checkSummary.checked &&
    checkSummary.stop === null &&
    (checkStateQuery.data?.counts.accounts ?? 0) > 0;
  // DEF-BIL-8510 — a utility-wide stop recorded on the run (the Check never
  // started): the banner, never a Checking panel that waits for ever.
  const checkStop = checkStateQuery.data?.stop ?? checkSummary?.stop ?? null;
  const checking =
    checkStop === null && (jobRunning || neverChecked || summaryBehind) ? { progress: job?.progress ?? null } : null;
  // DEF-BIL-8511 — the Check job stopped part-way (a worker lost, a limit):
  // say how far it got and offer Resume, which hands it back to the worker.
  const checkStopped = checkStop === null && job !== null && job.status === "failed" ? { progress: job.progress ?? null } : null;
  // DEF-BIL-8684 — the Check's warnings that still stand, for Sign off and Send.
  const standing = standingWarnings(checkSummary);
  const notInLinks = {
    addAccount: () => tenantPath(ACCOUNT_NEW_ROUTE),
    pending: tenantPath(BILLING_PENDING_ROUTE),
    unit: (id: string) => tenantPath(unitDetailPath(id)),
  };
  const fixInCheck = (row: ServedNotInRunRow) =>
    goToCheck(row.group === "blocked" ? row.reason : row.group === "left_out" ? READY_TAG : null, row.account_id);

  // ── Steps ─────────────────────────────────────────────────────────────────
  const refusals = preview?.refusals.length ?? 0;
  const scopeBlocked =
    runId === null && (preview === null || refusals > 0 || readOnlyReason !== null || previewQuery.isFetching);

  const stepScope = (
    <div className="flex flex-col gap-5" data-step="scope">
      <ScopeProblems preview={preview} fmt={fmt} links={scopeLinks} onOpenPanel={setPanel} />
      <WhatToBill
        fields={fields}
        onChange={update}
        cycles={cycles}
        templates={templates}
        preview={preview}
        fmt={fmt}
        readOnly={runId !== null}
      />
      <CycleDetails preview={preview} label={fields.label} fmt={fmt} links={scopeLinks} />
      <RunCovers preview={preview} t={translate} />
      <PreviousRuns
        preview={preview}
        fmt={fmt}
        links={scopeLinks}
        page={prevPage}
        per={prevPer}
        onPage={setPrevPage}
        onPer={(next) => {
          setPrevPer(next);
          setPrevPage(1);
        }}
      />
      {previewQuery.isError && (
        <FailedWithRetry
          title={translate("billing.bulkRun.scope.previewFailed")}
          reason={refusalOf(previewQuery.error)}
          onRetry={() => void previewQuery.refetch()}
          onCancel={() => undefined}
        />
      )}
    </div>
  );

  const stepCheck =
    runId === null ? null : (
      <CheckStep
        runId={runId}
        client={client}
        // DEF-BIL-8809 — the findings summary now starts beside the run read and
        // can land before the job's state is asked; Check draws it only once
        // both are in, as it did when they were asked together.
        summary={checkStateQuery.isPending ? null : checkSummary}
        loading={checkSummaryQuery.isFetching || checkStateQuery.isPending}
        error={checkSummaryQuery.error}
        onRetry={refreshChecks}
        checking={checking}
        onCheckAgain={() => void runCheck()}
        stop={checkStop}
        stopped={checkStopped}
        onResume={() => void act(() => resumeCheck(runId, client))}
        calculating={calculating}
        working={working}
        refusal={refusal}
        actions={checkActions}
        links={checkLinks}
        focus={checkFocus}
        t={translate}
      />
    );

  const stepSignOff = (
    <div className="flex flex-col gap-5" data-step="sign-off">
      <RunSummaryPanel summary={signOffSummary} dueDate={dueDate} fmt={fmt} />
      <WhoIsBilled
        summary={signOffSummary}
        onSee={(filter) => {
          setNotInFilter(filter);
          const target = document.getElementById("not-in-run");
          if (target !== null && typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "start" });
        }}
        t={translate}
      />
      <UsageAndCharges summary={signOffSummary} fmt={fmt} />
      <PaymentsAndBalances summary={signOffSummary} fmt={fmt} accountHref={accountHref} />
      <ByCustomerType summary={signOffSummary} fmt={fmt} />
      {runId !== null && (
        <NotInRunList
          mode="signoff"
          runId={runId}
          client={client}
          asOf={today}
          filter={notInFilter}
          onFilter={setNotInFilter}
          onFixInCheck={fixInCheck}
          onCatchUp={() => undefined}
          onLeaveForNextCycle={() => undefined}
          working={working}
          links={notInLinks}
          t={translate}
        />
      )}
      <SignOffWarnings
        breaks={breaks.length}
        summary={signOffSummary}
        standing={standing}
        onSeeTag={(code) => goToCheck(code, null)}
        onSeeBreaks={() => setBreaksOpen(true)}
        onSeeWaived={() => goToCheck("base_only_billing", null)}
        fmt={fmt}
        accountHref={accountHref}
      />
      <SignOffConfirmations
        ticked={ticked}
        disabled={signedOffAt !== null || run?.phase === "authorised"}
        onToggle={(confirmation) =>
          setTicked((was) => {
            const next = new Set(was);
            if (next.has(confirmation)) next.delete(confirmation);
            else next.add(confirmation);
            return next;
          })
        }
        t={translate}
      />
    </div>
  );

  const sentCount = run?.counts.bills_issued ?? summary?.bills ?? 0;
  // DEF-BIL-8582 — the run read taken BEFORE the Send still says 0 issued; until
  // the read after it arrives, Sent would claim "0 bills sent". Keep Sending.
  const sentSettled = !(runQuery.isFetching && (run?.counts.bills_issued ?? 0) === 0);
  // DEF-BIL-8809 (server half) — the Sent card's *Meter reads* row, on its own
  // read since it left the run read (it was ~1.1 s of that read's 1.2 s on a
  // sent 40,008-bill run, and every screen waits for the run read). Asked only
  // where it is drawn; the row appears when it answers.
  const readLockQuery = useQuery({
    queryKey: runId === null ? ["bulk-run", "no-read-lock"] : billRunReadLockKey(runId),
    queryFn: () => getBillRunReadLock(runId as string, client),
    enabled: runId !== null && sent && sentSettled,
    retry: false,
  });
  const stepSend = sent && sentSettled ? (
    <div className="flex flex-col gap-5" data-step="sent">
      <SubTabs
        tabs={[
          { id: "sent", label: translate("billing.bulkRun.sentTab.sent") },
          { id: "report", label: translate("billing.bulkRun.sentTab.report") },
        ]}
        activeId={sentTab}
        onSelect={(id) => setSentTab(id as "sent" | "report")}
        label={translate("billing.bulkRun.sentTab.label")}
        data-sub-tabs="sent"
      />
      {sentTab === "report" && runId !== null ? (
        <CheckReport runId={runId} client={client} t={translate} fmt={fmt} accountHref={accountHref} />
      ) : (
        <>
          <SentCard
            sent={sentCount}
            notSent={sendBreaks.length}
            total={summary?.amount ?? null}
            dueDate={dueDate}
            meterReads={readLockQuery.data?.meter_reads ?? null}
            onSeeBreaks={() => setNotSentOpen(true)}
            links={{ viewRun: tenantPath(RUN_HISTORY_ROUTE), print: tenantPath(BILLING_PRINT_ROUTE) }}
            fmt={fmt}
          />
          {catchUp !== null && (
            <CatchUpStarted
              runLabel={translate("billing.bulkRun.catchUp.runLabel")}
              accounts={catchUp.accounts}
              periodStart={fields.period_start}
              periodEnd={fields.period_end}
              href={tenantPath(billRunPath(catchUp.id))}
              t={translate}
              fmt={fmt}
            />
          )}
          {runId !== null && (
            <NotInRunList
              mode="sent"
              runId={runId}
              client={client}
              asOf={today}
              filter={notInFilter}
              onFilter={setNotInFilter}
              onFixInCheck={() => undefined}
              onCatchUp={(ids) => void startCatchUp(ids)}
              onLeaveForNextCycle={(ids) => void nextCycle(ids)}
              working={working}
              links={notInLinks}
              t={translate}
            />
          )}
        </>
      )}
    </div>
  ) : sending || sent ? (
    <ProgressPanel
      name="sending"
      title={translate("billing.bulkRun.send.sendingTitle")}
      progress={sendProgress}
      note={translate("billing.bulkRun.send.sendingNote")}
      t={translate}
    />
  ) : (
    <SendCard
      runNo={run?.run_no ?? null}
      cycleName={cycleName}
      periodStart={fields.period_start}
      periodEnd={fields.period_end}
      signedOffAt={signedOffAt ?? run?.signed_off?.at ?? null}
      signedOffBy={run?.signed_off?.by ?? null}
      total={summary?.amount ?? null}
      bills={summary?.bills ?? null}
      dueDate={dueDate}
      templateName={templateName}
      warnings={warningLineCount(breaks.length, signOffSummary, standing)}
      acknowledged={acknowledged}
      onAcknowledged={setAcknowledged}
      disabled={readOnlyReason !== null}
      fmt={fmt}
    />
  );

  // DEF-BIL-8678 — no footer while the step's body is a progress panel or a
  // stop (D1 09, 10, 24, 34): the same faces `CheckStep` draws, in its order.
  const checkFaceBusy =
    runId !== null &&
    !sent &&
    (calculating !== null || checking !== null || checkStop !== null || checkSummary === null || checkStateQuery.isPending);
  const steps: WizardStep[] = [
    {
      id: "scope",
      label: translate("billing.bulkRun.step.scope"),
      content: stepScope,
      continueLabel: translate("billing.bulkRun.scope.start"),
      continueDisabled: scopeBlocked,
      validate: startChecking,
    },
    {
      id: "check",
      label: translate("billing.bulkRun.step.check"),
      content: stepCheck,
      continueLabel: translate("billing.bulkRun.check.price", { count: toPrice ?? 0 }),
      // DEF-BIL-9004 — never a Price button while a Check is under way or has
      // not saved a result yet (it read "Price 0 accounts" for 20 s and more).
      continueDisabled:
        tiles === null || jobRunning || checking !== null || calculating !== null || checkStateQuery.isPending || readOnlyReason !== null,
      actionsHidden: checkFaceBusy,
      validate: price,
    },
    {
      id: "sign-off",
      label: translate("billing.bulkRun.step.signOff"),
      content: stepSignOff,
      continueLabel: translate("billing.bulkRun.signOff.action"),
      continueDisabled:
        run?.phase !== "authorised" && signedOffAt === null && (ticked.size < CONFIRMATIONS.length || readOnlyReason !== null),
      validate: signOff,
    },
    {
      id: "send",
      label: translate("billing.bulkRun.step.send"),
      content: stepSend,
      actionsHidden: sending,
    },
  ];

  // The line beside the footer: why the forward button is off, or what it costs.
  const footnote =
    step === 1 && runId === null && refusals > 0
      ? { tone: "refusal" as const, text: translate("billing.bulkRun.scope.fixFirst", { count: refusals }) }
      : step === 2 && !checkFaceBusy && tiles !== null && tiles.blocked > 0
        ? { tone: "fact" as const, text: translate("billing.bulkRun.check.staysOutCount", { count: tiles.blocked }) }
        : null;

  const fullWidth = step === 2 && !sent;
  const layout = fullWidth
    ? "flex flex-col gap-4 [&_[data-wizard=frame]]:contents [&_[data-wizard=actions]]:mt-0 [&_[data-wizard=actions]]:border-t [&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4"
    : "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 gap-y-4 items-start " +
      "[&_[data-wizard=frame]]:contents " +
      "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
      "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-2 " +
      "[&_[data-wizard=actions]]:col-start-1 [&_[data-wizard=actions]]:row-start-3 " +
      "[&_[data-wizard=actions]]:mt-0 [&_[data-wizard=actions]]:border-t " +
      "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
      "[&_[data-wizard=blocked]]:col-start-1 [&_[data-wizard=blocked]]:row-start-5";

  const runLine =
    run === null
      ? null
      : [
          translate("billing.bulkRun.aside.run", { run: run.run_no ?? translate("billing.bulkRun.runUnnumbered") }),
          cycleName,
          fields.period_start === "" ? null : span(fields.period_start, fields.period_end, fmt),
        ]
          .filter(Boolean)
          .join(" · ");

  return (
    <div className="flex flex-col gap-5" data-screen="bulk-bill-run">
      <PageHeader
        title={translate("billing.bulkRun.title")}
        kicker={translate("billing.bulkRun.crumb")}
        rollup={runLine === null ? undefined : <span className="text-base text-neutral-700" data-run-line="">{runLine}</span>}
        secondaryActions={
          canDiscard ? (
            <Button variant="danger" data-run-discard="" onClick={() => setDiscardOpen(true)}>
              {translate("billing.runDiscard.action")}
            </Button>
          ) : undefined
        }
      />
      {readOnlyReason !== null && <RefusalStrip role="note">{readOnlyReason}</RefusalStrip>}
      {discardRefusal !== null && <RefusalStrip role="alert">{discardRefusal}</RefusalStrip>}
      {discardOpen && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): a draft run and its draft bills are deleted.
          confirmVariant="danger"
          title={translate("billing.runDiscard.title")}
          consequence={translate("billing.runDiscard.consequence")}
          confirmLabel={translate("billing.runDiscard.confirm")}
          working={discarding}
          onConfirm={() => void discard()}
          onCancel={() => setDiscardOpen(false)}
        />
      )}
      {alsoHere.length > 0 && (
        <p className="m-0 bg-info-100 px-3 py-2 text-base text-info-700" role="status" data-run-presence={alsoHere.length}>
          {translate("billing.bulkRun.presence.also", { names: alsoHere.join(", ") })}
        </p>
      )}
      <div className={layout} data-bulk-layout={fullWidth ? "full" : "aside"}>
        <WizardFrame
          steps={steps}
          nav={nav}
          onNavChange={(next) => {
            setCheckFocus(null);
            setNav(next);
          }}
          complete={sent}
          commitLabel={translate("billing.bulkRun.send.action", { count: summary?.bills ?? 0 })}
          commitVariant="danger"
          backAtStart
          doneMark="tick"
          actionNote={
            footnote === null ? undefined : (
              <span
                className={`text-base ${footnote.tone === "refusal" ? "font-semibold text-danger-700" : "text-neutral-700"}`}
                data-run-footnote={footnote.tone}
              >
                {footnote.text}
              </span>
            )
          }
          commitDisabled={!acknowledged || readOnlyReason !== null}
          commitFailedTitle={translate("billing.bulkRun.send.failed")}
          onCommit={send}
          onCommitted={() => undefined}
        />
        {!fullWidth && (
          <div className="col-start-2 row-start-2 row-span-3 flex flex-col gap-4 self-start">
            <RunSummaryCard
              facts={facts}
              scope={step === 1 ? { preview, services, refusalFields } : undefined}
              check={step >= 3 ? checkResult : undefined}
              drafts={step >= 3 && summary !== null ? { total: summary.amount, bills: summary.bills, sent } : undefined}
              fmt={fmt}
            />
          </div>
        )}
      </div>
      {panel !== null && (
        <ScopeListPanel
          panel={panel}
          preview={preview}
          cycleId={fields.cycle_id}
          client={client}
          links={scopeListLinks}
          t={translate}
          fmt={fmt}
          onClose={() => setPanel(null)}
        />
      )}
      {notSentOpen && (
        <NotSentPanel
          breaks={sendBreaks}
          working={working}
          onRetry={() => void retryFailed()}
          onClose={() => setNotSentOpen(false)}
          t={translate}
          accountHref={accountHref}
          tenantHref={tenantPath}
        />
      )}
      {breaksOpen && (
        <FailedToDraftPanel
          breaks={breaks}
          retried={retried}
          working={working}
          onRetry={(accountId) => void retryBreak(accountId)}
          onClose={() => setBreaksOpen(false)}
          fixHref={(tag, accountId) => screenPath(tag === null ? "accounts" : (TAGS.find((entry) => entry.id === tag)?.fix ?? "accounts"), accountId)}
          t={translate}
        />
      )}
    </div>
  );
}

export default BulkRunPage;
