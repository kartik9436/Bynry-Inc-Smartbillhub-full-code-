// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-015 (single-bill correction) · US-BIL-016 (bulk; the case
//           list) · US-BIL-017 (the approval gate and the reasons) · US-BIL-031
//           (document-only correction). Screen: S30 (Fix a bill tab)
// Change:   CR-180-BRC10 (Fix a bill, revamped) — F1–F10. It REPLACES the
//           CR-101-BRC03 screen (six scope kinds, eighteen ticked reasons, a
//           case opened at step 1's Continue): `fixABillContract.ts`,
//           `fixABillSteps.tsx`, `FixWhatStepSingle.tsx`, `FixWhatStepBulk.tsx`,
//           `FixChangesStep.tsx`, `FixGoodwillStep.tsx` and `FixSendStep.tsx`
//           are deleted in the same change, not left dead.
// Drawing:  05-prototype/fix-a-bill-2026-10-12/01–24, read as images (B14 rules
//           41/42); our UI standard decides spacing, sizes and tokens (rule 44)
// Rulings:  decision log 2026-10-12 *FIX A BILL REVAMP* — four steps named
//           Bills · Fix · Check · Send, and the PO's shape instructions 1–12
// Contract: 12-governance/change-requests/CR-180-BRC10-fix-a-bill-revamp.md
//           §"The contract between server and screen" + additions A1–A6
// Rules:    BR-BIL-004 / HR-4 (an issued bill is never edited — a correction
//           is new rows) · BR-BIL-014 (NOTHING is written before Send; the
//           preview writes nothing) · BR-BIL-041/042 (the class is derived;
//           the strongest wins) · BR-BIL-044 (approval binds the previewed
//           figures; finance open for the approver) · NFR-3 · hard rule 2 ·
//           B14 rules 21, 31, 33, 36, 43, 44
// ───────────────────────────────────────────────────────
/**
 * FIX A BILL — FOUR STEPS: Bills · Fix · Check · Send.
 *
 *   1 **Bills** — two option cards INSIDE the step (One customer · Bulk), a
 *     sub-option dropdown that depends on the option, then the account (or the
 *     run, or the price mistake) and the bills it covers.
 *   2 **Fix** — ONE *What was wrong* table; every reason is a row type. *What
 *     happens* is derived from all the rows (R > C > D). Then the old bill and
 *     the new bill side by side, or the per-bill table for bulk.
 *   3 **Check** — for the customer, the existing bills, and for finance.
 *   4 **Send** — *I checked the amounts*, then **Send for approval**. THIS is
 *     where the case is created (`POST /corrections`); every earlier figure
 *     came from `POST /corrections/preview`, which writes nothing. The approver
 *     opens the same step and presses **Approve and issue**.
 *
 * ⚠ **NO SUMMARY PANEL BESIDE THE STEPS** (item 9, PO: *"on all step please
 * remove this section"*). The steps use the full width and each states its own
 * net change.
 *
 * ⚠ **THE CASE IS OPENED AT SEND, NOT AT STEP 1** (the first 2026-10-12 entry,
 * item 4): a clerk who looks and walks away used to leave a case that blocked
 * the bill (`BR-BIL-048`). Steps 1–3 here make only reads.
 */
import { useEffect, useMemo, useState } from "react";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError, api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  abandonCorrectionCase,
  followCorrectionJob,
  getCorrectionCaseV2,
  getCorrectionCases,
  getCorrectionCatalog,
  getCorrectionJob,
  getCorrectionOptions,
  getOneTimeAccount,
  resolveCorrectionScopeV2,
  startApproveAndIssue,
  startCorrectionPreview,
  startCorrectionResume,
  startCorrectionSend,
} from "@/api/billingOpsEndpoints";
import type {
  CorrectionCaseRow,
  CorrectionCaseV2,
  CorrectionDelivery,
  CorrectionJobProgress,
  CorrectionJobStage,
  CorrectionJobState,
  CorrectionPreview,
} from "@/api/billingOpsEndpoints";
import { getBillRunHistory, getInvoice, getTenantServices } from "@/api/endpoints";
import type { AccountRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { formatDate, todayInZone } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { WizardFrame, backOne, initialWizardNav } from "@/components/WizardFrame";
import type { WizardNavState, WizardStep } from "@/components/WizardFrame";
import { accountDetailPath } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import { PAYMENTS_ROUTE, useAccountSearch } from "@/features/payments/paymentsShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { FIX_A_BILL_PARAM } from "./billingOpsShared";
import { billDetailPath } from "./billingShared";
import { ONE_TIME_BILL_ROUTE } from "./oneTimeBill/OneTimeBillPage";
import { ComparePanel } from "./fixABill/BillCompare";
import {
  AccountBillsPanel,
  CaseBillsPanel,
  CoveredBillsPanel,
  CustomerPanel,
  PriceMistakePanel,
  RunPanel,
  WhatPanel,
} from "./fixABill/BillsStep";
import { BulkCheck, CustomerCheck, ExistingBills, ForFinance } from "./fixABill/CheckStep";
import {
  EMPTY_BILLS_FORM,
  billsRefusalKey,
  chooseOption,
  chooseSub,
  fixRefusalKey,
  itemsOf,
  monthLabel,
  scopeOf,
  togglePicked,
} from "./fixABill/fixABillModel";
import type { FixBillsForm, FixRow } from "./fixABill/fixABillModel";
import type { FixFmt } from "./fixABill/fixABillShared";
import { FixJobProgress } from "./fixABill/FixJobProgress";
import { BulkBillsPanel, PageChangesPanel } from "./fixABill/FixOutcome";
import {
  ApproveAndIssue,
  CorrectionClosed,
  CorrectionDone,
  CorrectionUnfinished,
  SendForApproval,
  WaitingForApproval,
} from "./fixABill/SendStep";
import type { SendHead } from "./fixABill/SendStep";
import { WhatWasWrongPanel } from "./fixABill/WhatWasWrong";

/** A bulk act's refusal is its ANSWER (DEF-BIL-10091): raised here as the
 *  same catalogue refusal the one-request route would have answered, so the
 *  screen words it exactly as it always did. */
function refuseIf(state: CorrectionJobState): void {
  if (state.refusal !== null) {
    throw new ApiError(422, {
      code: null,
      message_key: state.refusal.message_key,
      params: state.refusal.params ?? {},
    } as never);
  }
  if (state.status === "failed") {
    throw new ApiError(500, {
      code: null,
      message_key: "api.error.unexpected",
      params: {},
    } as never);
  }
}

export const correctionCatalogKey = ["corrections", "catalog"] as const;
export const correctionCasesKey = ["corrections", "cases"] as const;
export const correctionCaseKey = (caseId: string) => ["corrections", "case", caseId] as const;

/** The query parameter that opens an existing case — the approver's door. */
export const FIX_A_BILL_CASE_PARAM = "case";

/** How long the page waits after the last keystroke before re-asking the
 *  preview — long enough not to ask per character. */
const PREVIEW_DEBOUNCE_MS = 300;

function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const handle = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(handle);
  }, [value, ms]);
  return settled;
}

export interface FixABillTabProps {
  client?: ApiClient; // test seam — screens never build their own transport
  locale?: string;
  readOnly?: boolean;
  readOnlyReason?: string;
}

interface ChosenAccount {
  id: string;
  name: string | null;
  account_no: string | null;
  tone?: string | null;
}

/** A stored case's rows, back into the table's shape (read-only). */
function rowsOfCase(caseRow: CorrectionCaseV2): FixRow[] {
  return (caseRow.items ?? []).map((item, index) => ({
    uid: `case-${index}`,
    reason: item.reason,
    item: item.item,
    act: item.act ?? "",
    value: item.value ?? "",
    value2: item.value2 ?? "",
    applyTo: item.bill_ids,
  }));
}

export function FixABillTab(props: FixABillTabProps) {
  const { t, i18n } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const language = i18n.language || "en";
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const regional = useRegional({});
  const tenantPath = useTenantPath();
  const today = todayInZone(regional.timeZone);
  const [params, setParams] = useSearchParams();
  const blockedReason =
    props.readOnly === true ? (props.readOnlyReason ?? t("billing.rbac.readOnly")) : null;

  // ⚠ `accountId` COMES OFF THE ROUTE (`/accounts/{id}/issue-credit`), the bill
  // off `?bill=` (the bill detail's and the account rail's doors), the case off
  // `?case=` (the approver's door). Each is a prop nothing could forget to pass.
  const { accountId: routeAccountId } = useParams<{ accountId?: string }>();
  const fromAccount = routeAccountId !== undefined && routeAccountId !== "";
  const handedBill = params.get(FIX_A_BILL_PARAM) ?? "";
  const caseParam = params.get(FIX_A_BILL_CASE_PARAM) ?? "";

  const [form, setForm] = useState<FixBillsForm>(() => ({
    ...EMPTY_BILLS_FORM,
    accountId: fromAccount ? (routeAccountId as string) : "",
  }));
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav);
  const [term, setTerm] = useState("");
  const [chosen, setChosen] = useState<ChosenAccount | null>(null);
  const [rows, setRows] = useState<FixRow[]>([]);
  const [checked, setChecked] = useState(false);
  const [activeCase, setActiveCase] = useState<CorrectionCaseV2 | null>(null);
  const [closed, setClosed] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [billPage, setBillPage] = useState(1);
  const [billPer, setBillPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  const [bulkPage, setBulkPage] = useState(1);
  const [bulkPer, setBulkPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  // DEF-BIL-10091 — the bulk act running in the background, and how far it is.
  const [jobStage, setJobStage] = useState<CorrectionJobStage | null>(null);
  const [jobProgress, setJobProgress] = useState<CorrectionJobProgress | null>(null);

  const patchForm = (changes: Partial<FixBillsForm>) => setForm((was) => ({ ...was, ...changes }));

  // ── Reads ───────────────────────────────────────────────────────────────
  const catalogQuery = useQuery({
    queryKey: correctionCatalogKey,
    queryFn: () => getCorrectionCatalog(client),
    retry: false,
  });
  const casesQuery = useQuery({
    queryKey: correctionCasesKey,
    queryFn: () => getCorrectionCases(client),
    retry: false,
  });
  const caseQuery = useQuery({
    queryKey: correctionCaseKey(caseParam),
    queryFn: () => getCorrectionCaseV2(caseParam, client),
    enabled: caseParam !== "",
    retry: false,
  });
  // A case opened from the URL lands on Send — that is the step the approver
  // acts on, and every step before it is the case's own, read-only.
  useEffect(() => {
    if (caseQuery.data !== undefined) {
      setActiveCase(caseQuery.data);
      setNav({ step: 4, reached: 4 });
    }
  }, [caseQuery.data]);

  const handedQuery = useQuery({
    queryKey: ["invoices", "fix-a-bill-handed", handedBill],
    queryFn: () => getInvoice(handedBill, client),
    enabled: handedBill !== "" && caseParam === "",
    retry: false,
  });
  useEffect(() => {
    const bill = handedQuery.data;
    if (bill === undefined) return;
    setForm({ ...EMPTY_BILLS_FORM, accountId: bill.account_id, pickedIds: [bill.id] });
    setChosen({ id: bill.account_id, name: bill.customer_name, account_no: bill.account_no });
  }, [handedQuery.data]);

  const search = useAccountSearch(term, client, "fix-a-bill");
  const factsQuery = useQuery({
    queryKey: ["fix-a-bill", "account", form.accountId],
    queryFn: () => getOneTimeAccount(form.accountId, client),
    enabled: form.option === "one" && form.accountId !== "",
    retry: false,
  });
  useEffect(() => {
    const facts = factsQuery.data;
    if (facts !== undefined && chosen === null)
      setChosen({ id: facts.id, name: facts.name, account_no: facts.account_no });
  }, [factsQuery.data, chosen]);

  const accountScope = form.option === "one" ? scopeOf(form, false) : null;
  const accountBillsQuery = useQuery({
    queryKey: ["fix-a-bill", "account-bills", accountScope, billPage, billPer],
    queryFn: () =>
      resolveCorrectionScopeV2(accountScope!, { page: billPage, per: billPer }, client),
    enabled: accountScope !== null && activeCase === null,
    retry: false,
  });
  const scope = scopeOf(form);
  const pickedQuery = useQuery({
    queryKey: ["fix-a-bill", "picked", form.option === "one" ? scope : null],
    queryFn: () => resolveCorrectionScopeV2(scope!, { page: 1, per: 1 }, client),
    enabled: form.option === "one" && scope !== null && activeCase === null,
    retry: false,
  });
  const runsQuery = useQuery({
    queryKey: ["fix-a-bill", "runs"],
    // DEF-BIL-10090 — the cycle's runs, not each correction's one-bill rebill
    // run; a run with no issued bill has nothing to fix and is not offered.
    queryFn: async () => {
      const page = await getBillRunHistory({ per: 50, billType: "cycle" }, client);
      return { ...page, rows: page.rows.filter((run) => run.bills_issued > 0) };
    },
    enabled: form.option === "bulk" && form.sub === "run" && activeCase === null,
    retry: false,
  });
  const servicesQuery = useQuery({
    queryKey: ["fix-a-bill", "services"],
    queryFn: () => getTenantServices(client),
    enabled: form.option === "bulk" && form.sub === "run" && activeCase === null,
    retry: false,
  });
  const tenantOptionsQuery = useQuery({
    queryKey: ["fix-a-bill", "options", "tenant"],
    queryFn: () => getCorrectionOptions(null, client),
    enabled: form.option === "bulk" && activeCase === null,
    retry: false,
  });
  const coveredQuery = useQuery({
    queryKey: ["fix-a-bill", "covered", form.option === "bulk" ? scope : null, billPage, billPer],
    queryFn: () => resolveCorrectionScopeV2(scope!, { page: billPage, per: billPer }, client),
    enabled: form.option === "bulk" && scope !== null && activeCase === null,
    retry: false,
  });
  const scopedOptionsQuery = useQuery({
    queryKey: ["fix-a-bill", "options", scope],
    queryFn: () => getCorrectionOptions(scope, client),
    enabled: scope !== null && nav.step >= 2 && activeCase === null,
    retry: false,
  });

  // The bills the rows can apply to, oldest first — the picked ones on One
  // customer; on a case, the case's own.
  const accountRows = accountBillsQuery.data?.results ?? [];
  const pickedBills = accountRows
    .filter((row) => form.pickedIds.includes(row.invoice_id))
    .sort((a, b) => (a.period_end < b.period_end ? -1 : 1));
  const billIds = pickedBills.map((row) => row.invoice_id);
  const bulk =
    activeCase !== null
      ? (activeCase.preview?.scope_kind ?? "account") !== "account"
      : form.option === "bulk";
  const defaults = {
    billIds,
    bulk,
    billed: scopedOptionsQuery.data?.billed ?? null,
    meterIds: (scopedOptionsQuery.data?.meters ?? []).map((meter) => meter.asset_id),
  };

  const items = useMemo(() => itemsOf(rows, billIds), [rows, billIds]);
  // DEF-BIL-10091 — the page is NOT in the key: a bulk preview is priced
  // once, in the background, and its pages are read from the stored answer.
  const previewKey = JSON.stringify({ scope, items });
  const settledKey = useDebounced(previewKey, PREVIEW_DEBOUNCE_MS);
  const previewQuery = useQuery({
    queryKey: ["fix-a-bill", "preview", settledKey],
    queryFn: async (): Promise<{ preview: CorrectionPreview | null; jobId: string | null }> => {
      const settled = JSON.parse(settledKey) as { scope: typeof scope; items: typeof items };
      const answer = await startCorrectionPreview(
        { scope: settled.scope!, items: settled.items, as_of: today },
        client,
      );
      if (answer.kind === "done") return { preview: answer.data, jobId: null };
      await followJob(answer.jobId, "pricing");
      return { preview: null, jobId: answer.jobId };
    },
    // DEF-BIL-10078 — asked only of a SETTLED scope with at least one finished
    // row. The key is debounced, so enabling on the live `scope` fired a
    // preview whose body still carried `scope: null`, and an empty table fired
    // one the server refuses; each refusal writes a `security.attempt_refused`
    // audit row. Step 2's Continue says *add a correction* on its own.
    enabled:
      scope !== null &&
      items.length > 0 &&
      settledKey === previewKey &&
      nav.step >= 2 &&
      activeCase === null,
    placeholderData: keepPreviousData,
    retry: false,
  });

  // DEF-BIL-10091 — a background preview's answer, one page at a time (NFR-3).
  const previewJobId = activeCase === null ? (previewQuery.data?.jobId ?? null) : null;
  const previewPageQuery = useQuery({
    queryKey: ["fix-a-bill", "preview-page", previewJobId, bulkPage, bulkPer],
    queryFn: async () => {
      const state = await getCorrectionJob(
        previewJobId as string,
        { page: bulkPage, per: bulkPer },
        client,
      );
      refuseIf(state);
      return state.preview;
    },
    enabled: previewJobId !== null,
    placeholderData: keepPreviousData,
    retry: false,
  });

  const preview: CorrectionPreview | null =
    activeCase !== null
      ? (activeCase.preview ?? null)
      : previewJobId !== null
        ? (previewPageQuery.data ?? null)
        : (previewQuery.data?.preview ?? null);
  const previewError = previewQuery.isError
    ? previewQuery.error
    : previewPageQuery.isError
      ? previewPageQuery.error
      : null;
  const previewSettled =
    activeCase !== null ||
    (settledKey === previewKey &&
      !previewQuery.isFetching &&
      previewQuery.data !== undefined &&
      !previewQuery.isPlaceholderData &&
      (previewJobId === null ||
        (previewPageQuery.data !== undefined && !previewPageQuery.isPlaceholderData)));
  const shownRows = activeCase !== null ? rowsOfCase(activeCase) : rows;
  const locked = activeCase !== null;
  const approver = activeCase?.viewer_can_approve === true;

  // ── DEF-BIL-10091 · a bulk act is a job: follow it, then read its answer ──
  async function followJob(jobId: string, stage: CorrectionJobStage): Promise<CorrectionJobState> {
    setJobStage(stage);
    setJobProgress(null);
    try {
      const state = await followCorrectionJob(jobId, setJobProgress, client, {
        page: 1,
        per: bulkPer,
      });
      refuseIf(state);
      return state;
    } finally {
      setJobStage(null);
      setJobProgress(null);
    }
  }

  async function caseOfJob(jobId: string, stage: CorrectionJobStage): Promise<CorrectionCaseV2> {
    const state = await followJob(jobId, stage);
    if (state.case === null) throw new Error("the job finished with no case");
    return state.case;
  }

  // ── Acts — the only writes on this screen ───────────────────────────────
  const sendMutation = useMutation({
    mutationFn: async () => {
      const answer = await startCorrectionSend(
        {
          scope: scope!,
          items,
          as_of: today,
          preview_hash: preview?.preview_hash ?? "",
          ...(previewJobId !== null ? { preview_job_id: previewJobId } : {}),
        },
        client,
      );
      return answer.kind === "done" ? answer.data : caseOfJob(answer.jobId, "sending");
    },
  });
  const approveMutation = useMutation({
    mutationFn: async (args: { caseRow: CorrectionCaseV2; delivery: CorrectionDelivery | null }) => {
      const { caseRow, delivery } = args;
      const answer = await startApproveAndIssue(
        caseRow.id,
        {
          preview_hash: caseRow.preview_hash ?? caseRow.preview?.preview_hash ?? "",
          on_date: today,
          issued_at: new Date().toISOString(),
          // DEF-BIL-10535 — the clerk's Email · Paper · Both (one customer).
          ...(delivery !== null ? { delivery } : {}),
        },
        client,
      );
      return answer.kind === "done" ? answer.data : caseOfJob(answer.jobId, "checking");
    },
  });
  // DEF-BIL-10082 — resume: `/execute` runs the failed bills again and skips
  // every bill already done (rule 6), then the case detail is read back. A
  // bulk case resumes as a job (DEF-BIL-10091).
  const resumeMutation = useMutation({
    mutationFn: async (caseRow: CorrectionCaseV2) => {
      const answer = await startCorrectionResume(
        caseRow.id,
        { on_date: today, issued_at: new Date().toISOString() },
        client,
      );
      if (answer.kind === "job") return caseOfJob(answer.jobId, "issuing");
      return getCorrectionCaseV2(caseRow.id, client);
    },
  });
  const abandonMutation = useMutation({
    mutationFn: (args: { caseRow: CorrectionCaseV2; reason: string }) =>
      abandonCorrectionCase(args.caseRow.id, { reason: args.reason, on_date: today }, client),
  });

  function errorWords(error: unknown): string {
    return isApiError(error) ? apiErrorText(error, translate) : t("api.error.unexpected");
  }

  async function send(): Promise<void> {
    setRefusal(null);
    try {
      const opened = await sendMutation.mutateAsync();
      setActiveCase(opened);
      await queryClient.invalidateQueries({ queryKey: correctionCasesKey });
    } catch (error) {
      setRefusal(errorWords(error));
    }
  }

  async function approve(
    caseRow: CorrectionCaseV2,
    delivery: CorrectionDelivery | null,
  ): Promise<void> {
    setRefusal(null);
    try {
      setActiveCase(await approveMutation.mutateAsync({ caseRow, delivery }));
      await queryClient.invalidateQueries({ queryKey: correctionCasesKey });
    } catch (error) {
      setRefusal(errorWords(error));
    }
  }

  async function resume(caseRow: CorrectionCaseV2): Promise<void> {
    setRefusal(null);
    try {
      setActiveCase(await resumeMutation.mutateAsync(caseRow));
      await queryClient.invalidateQueries({ queryKey: correctionCasesKey });
    } catch (error) {
      setRefusal(errorWords(error));
    }
  }

  async function abandon(caseRow: CorrectionCaseV2, reason: string): Promise<void> {
    setRefusal(null);
    try {
      await abandonMutation.mutateAsync({ caseRow, reason });
      setClosed(true);
      await queryClient.invalidateQueries({ queryKey: correctionCasesKey });
    } catch (error) {
      setRefusal(errorWords(error));
    }
  }

  function startOver(): void {
    setForm({ ...EMPTY_BILLS_FORM, accountId: fromAccount ? (routeAccountId as string) : "" });
    setChosen(null);
    setTerm("");
    setRows([]);
    setChecked(false);
    setActiveCase(null);
    setClosed(false);
    setRefusal(null);
    setNav(initialWizardNav());
    setParams({}, { replace: true });
  }

  function chooseAccount(row: AccountRow | null): void {
    setChosen(
      row === null
        ? null
        : {
            id: row.id,
            name: row.name,
            account_no: row.account_no,
            tone: row.status_behavior_class,
          },
    );
    setForm((was) => ({ ...was, accountId: row?.id ?? "", pickedIds: [] }));
    setRows([]);
    setBillPage(1);
  }

  const catalog = catalogQuery.data;
  if (catalogQuery.isError) {
    return (
      <Panel role="alert" title={t("billing.fix.errorTitle")}>
        <p className="m-0 text-base text-danger-700">
          {apiErrorText(catalogQuery.error, translate)}
        </p>
      </Panel>
    );
  }
  if (catalog === undefined) return <LoadingSkeleton variant="card" />;

  const currency =
    preview?.currency ?? factsQuery.data?.currency ?? coveredQuery.data?.totals.currency ?? "USD";
  const fmt: FixFmt = { t: translate, currency, language };
  const dateWords = (iso: string | null) =>
    iso === null || iso === "" ? "—" : formatDate(iso, regional.timeZone, regional.dateFormat);
  const span = (start: string, end: string) => `${dateWords(start)} – ${dateWords(end)}`;

  const firstPicked = form.pickedIds[0] ?? "";
  const links = {
    cancel: tenantPath(firstPicked === "" ? "/billing" : billDetailPath(firstPicked)),
    oneTime: tenantPath(ONE_TIME_BILL_ROUTE),
    payments: tenantPath(PAYMENTS_ROUTE),
    account: tenantPath(form.accountId === "" ? "/accounts" : accountDetailPath(form.accountId)),
  };
  const applyBills =
    activeCase !== null
      ? (preview?.bills ?? []).map((bill) => ({
          id: bill.invoice_id,
          month: monthLabel(bill.period_end, language),
        }))
      : pickedBills.map((bill) => ({
          id: bill.invoice_id,
          month: monthLabel(bill.period_end, language),
        }));

  // ── Step 1 · Bills ──────────────────────────────────────────────────────
  const stepBills =
    activeCase !== null ? (
      <div className="flex flex-col gap-4">
        <CaseBillsPanel
          t={translate}
          fmt={fmt}
          span={span}
          bills={preview?.bills ?? []}
          count={preview?.count ?? 0}
        />
      </div>
    ) : (
      <div className="flex flex-col gap-4">
        <WhatPanel
          form={form}
          onOption={(option) => {
            setForm((was) => chooseOption(was, option));
            setRows([]);
            setBillPage(1);
            if (option === "one" && !fromAccount) setChosen(null);
          }}
          onSub={(sub) => {
            setForm((was) => chooseSub(was, sub));
            setRows([]);
          }}
          t={translate}
          locked={fromAccount || handedBill !== ""}
        />
        {form.option === "one" ? (
          <>
            <CustomerPanel
              t={translate}
              fmt={fmt}
              dateWords={dateWords}
              term={term}
              onTermChange={setTerm}
              search={search}
              matches={search.matches}
              chosen={chosen}
              onChoose={chooseAccount}
              facts={factsQuery.data ?? null}
              locked={fromAccount}
            />
            {form.accountId !== "" && (
              <AccountBillsPanel
                t={translate}
                fmt={fmt}
                language={language}
                span={span}
                several={form.sub === "several"}
                resolution={accountBillsQuery.data ?? null}
                picked={form.pickedIds}
                pickedTotals={pickedQuery.data ?? null}
                onToggle={(id) => {
                  setForm((was) => togglePicked(was, id));
                }}
                locked={false}
                page={billPage}
                per={billPer}
                onPage={setBillPage}
                onPer={(per) => {
                  setBillPer(per);
                  setBillPage(1);
                }}
              />
            )}
          </>
        ) : (
          <>
            {form.sub === "run" ? (
              <RunPanel
                t={translate}
                language={language}
                runs={runsQuery.data?.rows ?? []}
                runId={form.runId}
                onRun={(runId) => patchForm({ runId, runPart: "" })}
                part={form.runPart}
                onPart={(runPart) => patchForm({ runPart })}
                services={(servicesQuery.data ?? [])
                  .filter((s) => s.enabled)
                  .map((s) => ({ code: s.service, name: s.name }))}
                plans={tenantOptionsQuery.data?.plans ?? []}
                locked={false}
              />
            ) : (
              <PriceMistakePanel
                t={translate}
                dateFormat={regional.dateFormat}
                form={form}
                onChange={patchForm}
                targets={tenantOptionsQuery.data?.price_targets ?? []}
                locked={false}
              />
            )}
            <CoveredBillsPanel
              t={translate}
              fmt={fmt}
              resolution={coveredQuery.data ?? null}
              page={billPage}
              per={billPer}
              onPage={setBillPage}
              onPer={(per) => {
                setBillPer(per);
                setBillPage(1);
              }}
            />
          </>
        )}
      </div>
    );

  // ── Step 2 · Fix ────────────────────────────────────────────────────────
  const cls = preview?.correction_class ?? null;
  const showFigures = preview !== null && (activeCase !== null || items.length > 0);
  // DEF-BIL-10096 — a bill the server LEFT OUT of a bulk case (it cannot be
  // priced, or it is past the back-bill window) is listed, and the rest go on;
  // only a real problem blocks Continue.
  const LEFT_OUT_CODES = ["cannot_price", "beyond_the_back_bill_cap"];
  const allProblems = preview?.problems ?? [];
  const leftOut = allProblems.filter((one) => LEFT_OUT_CODES.includes(one.code));
  const previewProblems = allProblems.filter((one) => !LEFT_OUT_CODES.includes(one.code));
  const stepFix = (
    <div className="flex flex-col gap-4">
      <WhatWasWrongPanel
        t={translate}
        fmt={fmt}
        language={language}
        dateFormat={regional.dateFormat}
        dateWords={dateWords}
        sub={activeCase !== null ? (bulk ? "run" : "several") : form.sub}
        catalog={catalog}
        options={scopedOptionsQuery.data ?? null}
        rows={shownRows}
        onRows={(next) => {
          setRows(next);
          setChecked(false);
        }}
        bills={applyBills}
        defaults={defaults}
        links={links}
        locked={locked}
        planWarnings={preview?.plan_warnings ?? []}
      />
      {jobStage === "pricing" && (
        <FixJobProgress progress={jobProgress} stage="pricing" t={translate} />
      )}
      {previewError !== null && activeCase === null && (
        <p className="m-0 text-base text-danger-700" role="alert">
          {errorWords(previewError)}
        </p>
      )}
      {previewProblems.length > 0 && (
        <ul
          className="m-0 list-disc bg-danger-100 py-2 pl-8 text-base text-danger-700"
          role="alert"
        >
          {previewProblems.map((problem) => (
            <li key={problem.code}>
              {problem.message_key === undefined
                ? problem.detail
                : t(problem.message_key, { defaultValue: problem.detail })}
            </li>
          ))}
        </ul>
      )}
      {leftOut.length > 0 && (
        <ul className="m-0 list-disc bg-neutral-100 py-2 pl-8 text-base" data-fix-left-out-bills="">
          {leftOut.map((one) => (
            <li key={`${one.code}-${one.detail}`}>
              {t(one.message_key ?? "billing.fixBill.leftOut.cannotPrice", { bill: one.detail })}
            </li>
          ))}
        </ul>
      )}
      <div
        className={`flex flex-col gap-4 ${previewSettled ? "" : "opacity-60"}`}
        aria-busy={!previewSettled}
        data-fix-preview={previewSettled ? "settled" : "working"}
      >
        {showFigures && <PageChangesPanel changes={preview.page_changes} cls={cls} t={translate} />}
        {showFigures &&
          (bulk ? (
            <BulkBillsPanel
              preview={preview}
              t={translate}
              fmt={fmt}
              page={bulkPage}
              per={bulkPer}
              onPage={setBulkPage}
              onPer={(per) => {
                setBulkPer(per);
                setBulkPage(1);
              }}
            />
          ) : (
            <ComparePanel
              bills={preview.bills}
              cls={cls}
              net={preview.totals.net}
              t={translate}
              fmt={fmt}
            />
          ))}
      </div>
    </div>
  );

  // ── Step 3 · Check ──────────────────────────────────────────────────────
  const stepCheck =
    preview === null ? (
      <LoadingSkeleton variant="card" />
    ) : (
      <div className="flex flex-col gap-4">
        {bulk ? (
          <BulkCheck preview={preview} t={translate} fmt={fmt} />
        ) : (
          <CustomerCheck preview={preview} t={translate} fmt={fmt} dateWords={dateWords} />
        )}
        <ExistingBills preview={preview} cls={cls} t={translate} fmt={fmt} />
        <ForFinance preview={preview} approver={approver} t={translate} fmt={fmt} />
      </div>
    );

  // ── Step 4 · Send ───────────────────────────────────────────────────────
  const reasonWords = [
    ...new Set(shownRows.filter((row) => row.reason !== "").map((row) => row.reason)),
  ].map((reason) => t(`billing.fixBill.reason.${reason}`));
  const optionWord = t(`billing.fixBill.option.${bulk ? "bulk" : "one"}`);
  const head: SendHead = {
    kicker: [optionWord, reasonWords[0] ?? ""].filter((part) => part !== "").join(" · "),
    title: bulk
      ? t("billing.fixBill.covered.aside", {
          bills: preview?.count ?? 0,
          accounts: preview?.accounts ?? 0,
        })
      : [
          preview?.customer?.name ?? chosen?.name,
          preview?.customer?.account_no ?? chosen?.account_no,
        ]
          .filter((part): part is string => part !== null && part !== undefined && part !== "")
          .join(" · "),
    net: preview?.totals.net ?? activeCase?.net_delta ?? "0",
    bills: preview?.count ?? activeCase?.bills ?? 0,
  };
  const backToCheck = () => setNav((was) => backOne(was));
  const done = activeCase?.status === "done";
  // DEF-BIL-10082 — approved and run, with a bill still unresolved.
  const unfinished =
    activeCase !== null &&
    ["approved", "executing", "open", "failed"].includes(activeCase.status);
  const stepSend =
    closed || activeCase?.status === "abandoned" ? (
      <CorrectionClosed t={translate} onAnother={startOver} />
    ) : activeCase !== null && done ? (
      <CorrectionDone
        caseRow={activeCase}
        bulk={bulk}
        t={translate}
        fmt={fmt}
        accountHref={
          form.accountId !== ""
            ? tenantPath(accountDetailPath(form.accountId))
            : (activeCase.bills_detail[0]?.account_id ?? null) === null
              ? null
              : tenantPath(accountDetailPath(activeCase.bills_detail[0].account_id as string))
        }
        onViewCase={() => setParams({ [FIX_A_BILL_CASE_PARAM]: activeCase.id })}
        onAnother={startOver}
      />
    ) : activeCase !== null && unfinished ? (
      <CorrectionUnfinished
        head={head}
        caseRow={activeCase}
        t={translate}
        fmt={fmt}
        onRetry={() => void resume(activeCase)}
        onClose={() => void abandon(activeCase, t("billing.fixBill.send.closeReason"))}
        working={resumeMutation.isPending || abandonMutation.isPending}
        refusal={refusal}
        blockedReason={blockedReason}
      />
    ) : activeCase !== null && approver ? (
      <ApproveAndIssue
        head={head}
        caseRow={activeCase}
        t={translate}
        fmt={fmt}
        dateWords={dateWords}
        onBack={backToCheck}
        onSendBack={() => void abandon(activeCase, t("billing.fixBill.send.sendBackReason"))}
        onApprove={(delivery) => void approve(activeCase, delivery)}
        working={approveMutation.isPending || abandonMutation.isPending}
        refusal={refusal}
        blockedReason={blockedReason}
      />
    ) : activeCase !== null ? (
      <WaitingForApproval
        head={head}
        caseRow={activeCase}
        t={translate}
        fmt={fmt}
        onClose={() => void abandon(activeCase, t("billing.fixBill.send.closeReason"))}
        closing={abandonMutation.isPending}
        blockedReason={blockedReason}
      />
    ) : preview === null ? (
      <LoadingSkeleton variant="card" />
    ) : (
      <SendForApproval
        head={head}
        preview={preview}
        reasons={reasonWords.join(", ")}
        t={translate}
        fmt={fmt}
        checked={checked}
        onChecked={setChecked}
        onBack={backToCheck}
        onSend={() => void send()}
        sending={sendMutation.isPending}
        refusal={refusal}
        blockedReason={blockedReason}
      />
    );

  const steps: WizardStep[] = [
    {
      id: "fix-bills",
      label: t("billing.fixBill.step.bills"),
      hint: t("billing.fixBill.step.billsHint"),
      content: stepBills,
      validate: () => {
        if (activeCase !== null) return true;
        const key = billsRefusalKey(form);
        return key === null ? true : t(key);
      },
    },
    {
      id: "fix-fix",
      label: t("billing.fixBill.step.fix"),
      hint: t("billing.fixBill.step.fixHint"),
      content: stepFix,
      validate: () => {
        if (activeCase !== null) return true;
        const key = fixRefusalKey(rows);
        if (key !== null) return t(key);
        if (previewError !== null) return errorWords(previewError);
        if (!previewSettled) return t("billing.fixBill.refuse.previewing");
        if (previewProblems.length > 0) return t("billing.fixBill.refuse.problems");
        return true;
      },
    },
    {
      id: "fix-check",
      label: t("billing.fixBill.step.check"),
      hint: t("billing.fixBill.step.checkHint"),
      content: stepCheck,
    },
    {
      id: "fix-send",
      label: t("billing.fixBill.step.send"),
      hint: t("billing.fixBill.step.sendHint"),
      content:
        jobStage !== null && jobStage !== "pricing" ? (
          <div className="flex flex-col gap-4">
            <FixJobProgress progress={jobProgress} stage={jobStage} t={translate} />
            {stepSend}
          </div>
        ) : (
          stepSend
        ),
      actionsHidden: true,
    },
  ];

  return (
    <div className="flex flex-col gap-4" data-screen="fix-a-bill">
      <div className="flex justify-end">
        <Button size="sm" onClick={startOver}>
          {t("billing.fixBill.startOver")}
        </Button>
      </div>
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setNav}
        complete={done || closed}
        doneMark="tick"
        backAtStart
        commitLabel={t("billing.fixBill.send.send")}
        commitFailedTitle={t("billing.fixBill.send.failed")}
        onCommit={async () => ({ ok: true })}
        onCommitted={() => undefined}
      />
      <CasesPanel
        rows={casesQuery.data?.results ?? null}
        t={translate}
        locale={props.locale}
        onOpen={(id) => {
          setActiveCase(null);
          setClosed(false);
          setParams({ [FIX_A_BILL_CASE_PARAM]: id });
        }}
      />
    </div>
  );
}

/**
 * The cases already open — the approver's door into Send (US-BIL-016). Not in
 * the drawing, which draws one case being made; kept because without it an
 * approver has no way to reach a case they did not open themselves.
 */
function CasesPanel(props: {
  rows: CorrectionCaseRow[] | null;
  t: Translator;
  locale?: string;
  onOpen: (id: string) => void;
}) {
  const { t } = props;
  return (
    <Panel as="section" title={t("billing.fix.casesTitle")}>
      {props.rows === null ? (
        <LoadingSkeleton variant="table" />
      ) : props.rows.length === 0 ? (
        <p className="m-0 text-base text-neutral-700">{t("billing.fix.noCases")}</p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("billing.fix.col.case")}</th>
              <th scope="col">{t("billing.fix.col.class")}</th>
              <th scope="col">{t("billing.fix.col.bills")}</th>
              <th scope="col" className="text-right">
                {t("billing.fix.col.net")}
              </th>
              <th scope="col">{t("billing.fix.col.status")}</th>
            </tr>
          </thead>
          <tbody>
            {props.rows.map((row) => (
              <tr key={row.id}>
                <td>
                  {/* DEF-3158 — a case with no number never shows its id (B14 rule 31). */}
                  <InlineLink type="button" onClick={() => props.onOpen(row.id)}>
                    {row.case_no ?? t("billing.fix.noCaseNo")}
                  </InlineLink>
                </td>
                <td>
                  {t(`billing.fixBill.class.${row.correction_class}`, {
                    defaultValue: row.correction_class,
                  })}
                </td>
                <td>{row.bills ?? t("billing.fix.notCounted")}</td>
                <td className="text-right">
                  {row.closed_without_correcting === true ? (
                    "—"
                  ) : row.net_delta !== null && row.currency !== null ? (
                    <MoneyCell
                      amount={row.net_delta}
                      currency={row.currency}
                      locale={props.locale}
                    />
                  ) : (
                    t("billing.fix.notCounted")
                  )}
                </td>
                <td>
                  {/* DEF-BIL-10100 — a case closed without correcting is not "Done". */}
                  {row.closed_without_correcting === true ? (
                    <StatusPill tone="muted">{t("billing.fix.status.closed")}</StatusPill>
                  ) : (
                    <StatusPill tone={row.status === "done" ? "success" : "warning"}>
                      {t(`billing.fix.status.${row.status}`, { defaultValue: row.status })}
                    </StatusPill>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Panel>
  );
}

export default FixABillTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-180-BRC10 (sources: 12-governance/change-requests/CR-180-BRC10-fix-a-bill-revamp.md · decision log 2026-10-12 FIX A BILL REVAMP 1–12 · 05-prototype/fix-a-bill-2026-10-12/*.png read as images)
// generated: 2026-08-16 by story-coder (S30 Fix a bill tab); REBUILT 2026-10-12 by the CR-180-BRC10 screen lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — fixABill/FixABill.dom.test.tsx failed 21/21 against the CR-101 screen before this rebuild
// exceptions: E3 the case list below the wizard is kept (not drawn) as the approver's door · E3 Send's buttons sit in its card and the frame's row is hidden on that step
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
