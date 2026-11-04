// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the NEW Accounts tab (images 20, 25).
//           PO 2026-10-03: *"can you add tab and show the list of accounts who
//           are getting this discount?"*
// Defect:   DEF-RAT-9291 D30 (no way to see who gets it)
// Rules:    NFR-3 (paged, searched and filtered by the SERVER) · BR-SHL-011
//           (the list's state is URL state) · BR-SHL-012 (an empty list is the
//           kit's empty block, never an empty header) · B14 rule 31 (the
//           account NUMBER, never its id) · ruling 2 (only an account whose
//           plan carries it can be enrolled — the server refuses by name) ·
//           BR-RAT-079 (a proof is served to a System Admin only, as the
//           account document to open — DEF-CUS-9780) · DEF-RAT-9792 (no
//           + Enroll an account on an Automatic discount)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS MONTH IS A DASH, WITH NO WORDS.** The server serves `this_month`
// as `null` until `DEF-2430` records a grant at issue (decision log
// 2026-10-03). Image 20's `−$6.30` is an illustration (B14 rule 37).
//
// ⚠ **⤓ IS THE SERVER'S CSV OF THE WHOLE FILTERED SET (`DEF-1005`, CR-166
// follow-up 2026-10-03).** `GET /discounts/{id}/accounts?format=csv` with the
// same search, filters and sort as the table, streamed 500 rows a read — never
// the page on screen, never capped (NFR-3, NFR-5). The plan Units tab's shape.
//
// ⚠ **IMAGE 25's EMPTY STATE IS DRAWN AS A HEADER ROW OVER *Nobody receives it
// yet.*; THE KIT DRAWS ITS EMPTY BLOCK INSTEAD.** BR-SHL-012 forbids an empty
// header, and B14 rule 44 gives our standard the build. Same words.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  DISCOUNT_ACCOUNT_STATUSES,
  endDiscountEnrolment,
  enrolAccountInDiscount,
  getDiscountAccountPage,
  getDiscountAccountsCsv,
  getDiscountPlanPage,
  verifyDiscountEnrolment,
} from "@/api/discountDetailEndpoints";
import type { DiscountAccountRow } from "@/api/discountDetailEndpoints";
import { getAccounts } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { openDocumentContent } from "@/components/documents/openStoredDocument";
import { DownloadButton } from "@/components/DownloadButton";
import { formatDate, todayInZone } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { EyeIcon } from "@/components/icons";
import { useToast } from "@/components/Toast";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { accountDocumentContentPath } from "@/features/customers/AccountDocumentsTab";
import { accountDetailPath } from "@/features/customers/customersShared";
import { refusalOf } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { saveCsv } from "../planDetail/saveCsv";

import { SECTION_HEADING } from "../discountForm/discountFormShared";
import { DASH } from "./discountDetailModel";
import type { DiscountRegional, Translator } from "./discountDetailModel";

/** The tab's list state lives in the URL beside `?tab=` (BR-SHL-011). */
export const ACCOUNTS_PARAM_PREFIX = "acc.";

/** Receiving is the good state, proof pending is waiting, renewal due warns. */
export function accountStatusTone(status: string): StatusTone {
  if (status === "receiving") return "success";
  if (status === "renewal_due") return "warning";
  return "neutral";
}

/** Literal keys, so G18 sees each one used. */
const STATUS_KEYS: Readonly<Record<string, string>> = {
  receiving: "rating.discountDetail.accounts.status.receiving",
  proof_pending: "rating.discountDetail.accounts.status.proof_pending",
  renewal_due: "rating.discountDetail.accounts.status.renewal_due",
};

export function accountStatusWord(status: string, t: Translator): string {
  const key = STATUS_KEYS[status];
  return key === undefined ? status : t(key);
}

export function discountAccountsConfig(
  t: Translator,
  plans: readonly { value: string; label: string }[],
  cells: {
    account: (row: DiscountAccountRow) => ReactNode;
    customer: (row: DiscountAccountRow) => ReactNode;
    enrolled: (row: DiscountAccountRow) => ReactNode;
    renewBy: (row: DiscountAccountRow) => ReactNode;
    thisMonth: (row: DiscountAccountRow) => ReactNode;
    status: (row: DiscountAccountRow) => ReactNode;
    end: (row: DiscountAccountRow) => ReactNode;
  },
): TableConfig<DiscountAccountRow> {
  return {
    screenId: "S9.discounts.accounts",
    columns: [
      {
        key: "account_number",
        label: t("rating.discountDetail.accounts.col.account"),
        sortable: true,
        identity: true,
        cell: cells.account,
      },
      { key: "customer_name", label: t("rating.discountDetail.accounts.col.customer"), cell: cells.customer },
      { key: "plan", label: t("rating.definition.tax.plans.col.plan") },
      {
        key: "enrolled_on",
        label: t("rating.discountDetail.accounts.col.enrolled"),
        sortable: true,
        cell: cells.enrolled,
      },
      { key: "renew_by", label: t("rating.discountDetail.accounts.col.renewBy"), sortable: true, cell: cells.renewBy },
      {
        key: "this_month",
        label: t("rating.discountDetail.accounts.col.thisMonth"),
        numeric: true,
        cell: cells.thisMonth,
      },
      { key: "status", label: t("rating.col.status"), cell: cells.status },
      { key: "actions", label: "", locked: true, cell: cells.end },
    ],
    getRowId: (row) => row.enrolment_id,
    searchFields: ["account_number", "customer_name"],
    searchPlaceholder: "rating.discountDetail.accounts.search",
    filters: [
      {
        name: "status",
        label: t("rating.col.status"),
        options: DISCOUNT_ACCOUNT_STATUSES.map((value) => ({ value, label: accountStatusWord(value, t) })),
      },
      ...(plans.length === 0
        ? []
        : [{ name: "plan", label: t("rating.definition.tax.plans.col.plan"), options: [...plans] }]),
    ],
    defaultSort: { sort: "account_number", dir: "asc" },
  };
}

/** × on a row — end ONE enrollment on a date, with a reason (both required). */
export function EndEnrolmentDialog(props: {
  row: DiscountAccountRow;
  client: ApiClient;
  regional: DiscountRegional;
  onClose: () => void;
  onDone: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [endedOn, setEndedOn] = useState(todayInZone(props.regional.timeZone));
  const [reason, setReason] = useState("");
  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await endDiscountEnrolment(props.row.enrolment_id, { ended_on: endedOn, reason: reason.trim() }, props.client);
      props.onDone();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }
  return (
    <FormModal
      title={t("rating.discountDetail.accounts.endTitle", { account: props.row.account_number ?? DASH })}
      schema={z.object({
        ended_on: z.string().min(1, t("rating.discountDetail.accounts.endDateRequired")),
        reason: z.string().trim().min(1, t("rating.discountDetail.accounts.reasonRequired")),
      })}
      values={{ ended_on: endedOn, reason }}
      submitLabel={t("rating.discountDetail.accounts.endSubmit")}
      submitVariant="danger"
      onSubmit={submit}
      onClose={props.onClose}
    >
      <DatePickerField
        id="ended_on"
        label={t("rating.discountDetail.accounts.lastDay")}
        value={endedOn}
        onChange={setEndedOn}
        dateFormat={props.regional.dateFormat}
        required
      />
      <TextField id="reason" label={t("rating.taxDetail.retire.reason")} value={reason} onChange={setReason} required />
    </FormModal>
  );
}

const ACCOUNT_SEARCH_PER = 20;

/** *+ Enroll an account* — found by typing (the server searches, NFR-3). */
export function EnrollAccountDialog(props: {
  discountId: string;
  client: ApiClient;
  onClose: () => void;
  onDone: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [term, setTerm] = useState("");
  const [accountId, setAccountId] = useState("");
  const query = useQuery({
    queryKey: ["accounts", "search", term],
    queryFn: () => getAccounts({ q: term, page: 1, per: ACCOUNT_SEARCH_PER }, props.client),
    enabled: term.trim().length >= 2,
    retry: false,
  });
  const options = (query.data?.results ?? []).map((account) => ({
    value: account.id,
    label: [account.account_no, account.name].filter((part) => part !== null && part !== "").join(" · "),
  }));
  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await enrolAccountInDiscount(accountId, props.discountId, props.client);
      props.onDone();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }
  return (
    <FormModal
      title={t("rating.discountDetail.accounts.enrollTitle")}
      schema={z.object({ account: z.string().min(1, t("rating.discountDetail.accounts.accountRequired")) })}
      values={{ account: accountId }}
      submitLabel={t("rating.discountDetail.accounts.enrollSubmit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <RemoteSearchSelectField
        id="account"
        label={t("rating.discountDetail.accounts.col.account")}
        term={term}
        onTermChange={(next) => {
          setTerm(next);
          setAccountId("");
        }}
        status={{
          idle: term.trim().length < 2,
          searching: query.isFetching,
          searched: query.isSuccess,
          failed: query.isError,
        }}
        options={options}
        value={accountId}
        onChange={setAccountId}
        words={{
          tooShort: t("rating.discountDetail.accounts.searchShort"),
          searching: t("rating.taxDetail.plans.search.searching"),
          failed: t("rating.taxDetail.plans.search.failed"),
          noMatch: t("rating.taxDetail.plans.search.noMatch"),
        }}
        required
      />
    </FormModal>
  );
}

export function DiscountAccountsTab(props: {
  discountId: string;
  client: ApiClient;
  readOnly: boolean;
  /** `DEF-RAT-9792` — an Automatic discount draws no *+ Enroll an account*:
   *  the nightly sync grants and ends it, and the server refuses a hand
   *  enrolment by name. ⚖️ AMENDED 2026-10-06 (`DEF-RAT-9833`, PO D2 (b):
   *  *"clark can add it later also on account"*) — TRUE only for an Automatic
   *  discount NO person may add (Municipal account); Autopay and Paperless
   *  keep the button and the add switches the account's setting On. */
  handEnrolmentRefused?: boolean;
  regional: DiscountRegional;
  t: Translator;
}) {
  const { t, regional } = props;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [ending, setEnding] = useState<DiscountAccountRow | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [verifying, setVerifying] = useState<string | null>(null);
  const toast = useToast();

  // The Plan filter's options are this discount's own plans — a short list
  // the server pages (one row per plan, never per account).
  const plansQuery = useQuery({
    queryKey: ["discounts", props.discountId, "plans", 1, 200],
    queryFn: () => getDiscountPlanPage(props.discountId, { page: 1, per: 200 }, props.client),
    enabled: props.discountId !== "",
  });
  const planOptions = (plansQuery.data?.rows ?? []).map((plan) => ({ value: plan.plan_id, label: plan.plan }));
  const day = (value: string | null) =>
    value === null ? DASH : formatDate(value, regional.timeZone, regional.dateFormat);
  const readOnlyReason = props.readOnly ? t("rating.readOnlyReason") : null;

  const config = discountAccountsConfig(t, planOptions, {
    account: (row) => (
      <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))} className="font-semibold">
        {row.account_number ?? DASH}
      </InlineLinkTo>
    ),
    customer: (row) => (
      <div className="flex flex-col">
        <span>{row.customer_name ?? DASH}</span>
        {row.premises_address !== null && row.premises_address !== "" && (
          <span className="text-sm text-neutral-700">{row.premises_address}</span>
        )}
      </div>
    ),
    enrolled: (row) => <span className="tabular-nums">{day(row.enrolled_on)}</span>,
    renewBy: (row) => <span className="tabular-nums">{day(row.renew_by)}</span>,
    thisMonth: (row) => <span className="tabular-nums">{row.this_month ?? DASH}</span>,
    status: (row) => <StatusPill tone={accountStatusTone(row.status)}>{accountStatusWord(row.status, t)}</StatusPill>,
    end: (row) => {
      // DEF-CUS-9780 — the proof taken at the counter, on the enrolment it
      // supports, for the System Admin who verifies it (served to nobody else).
      const proofId = row.status === "proof_pending" ? (row.proof_document_id ?? "") : "";
      const endLabel = t("rating.discountDetail.accounts.end", { account: row.account_number ?? DASH });
      return (
        <RowActions>
          {proofId !== "" && (
            <RowAction
              label={t("rating.discountDetail.accounts.viewProof", { account: row.account_number ?? DASH })}
              icon={<EyeIcon />}
              onClick={() => openDocumentContent(accountDocumentContentPath(row.account_id, proofId), "view")}
            />
          )}
          {/* DEF-RAT-9325 — the proof is on file: Proof pending → Receiving. */}
          {row.status === "proof_pending" && (
            <RowAction
              label={t("rating.discountDetail.accounts.verify", { account: row.account_number ?? DASH })}
              icon={<span aria-hidden="true">✓</span>}
              reason={readOnlyReason}
              working={verifying === row.enrolment_id}
              onClick={() => void verify(row)}
            />
          )}
          {/* B14 rule 15 — two icons visible, the rest behind `…`. Only a row
              with proof on file carries three, so only there does End move. */}
          {proofId !== "" ? (
            <RowActionsMore label={t("table.rowActions.more")}>
              <RowMenuAction
                label={endLabel}
                icon={<span aria-hidden="true">×</span>}
                reason={readOnlyReason}
                danger
                onClick={() => setEnding(row)}
              />
            </RowActionsMore>
          ) : (
            <RowAction
              label={endLabel}
              icon={<span aria-hidden="true">×</span>}
              reason={readOnlyReason}
              danger
              onClick={() => setEnding(row)}
            />
          )}
        </RowActions>
      );
    },
  });

  const state = parseTableParams(searchParams, config, ACCOUNTS_PARAM_PREFIX);
  const query = useQuery({
    queryKey: ["discounts", props.discountId, "accounts", serializeTableParams(state, config).toString()],
    queryFn: () =>
      getDiscountAccountPage(
        props.discountId,
        {
          q: state.q,
          status: state.filters.status,
          plan: state.filters.plan,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
        },
        props.client,
      ),
    enabled: props.discountId !== "",
    placeholderData: (previous) => previous,
  });

  function setState(next: TableRequestState): void {
    const merged = new URLSearchParams(searchParams);
    for (const key of [...merged.keys()]) {
      if (key.startsWith(ACCOUNTS_PARAM_PREFIX)) merged.delete(key);
    }
    serializeTableParams(next, config, ACCOUNTS_PARAM_PREFIX).forEach((value, key) => merged.set(key, value));
    setSearchParams(merged, { replace: true });
  }
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["discounts", props.discountId] });
  };

  async function verify(row: DiscountAccountRow): Promise<void> {
    setVerifying(row.enrolment_id);
    try {
      await verifyDiscountEnrolment(row.enrolment_id, props.client);
      toast(t("rating.discountDetail.accounts.verified", { account: row.account_number ?? DASH }));
      refresh();
    } catch (error) {
      toast(refusalOf(error, t).message);
    } finally {
      setVerifying(null);
    }
  }

  async function download(): Promise<void> {
    try {
      const body = await getDiscountAccountsCsv(
        props.discountId,
        { q: state.q, status: state.filters.status, plan: state.filters.plan, sort: state.sort, dir: state.dir },
        props.client,
      );
      saveCsv(body, "discount-accounts.csv");
    } catch {
      toast(t("rating.planDetail.csvFailed"));
    }
  }

  return (
    <Panel as="section" aria-labelledby="discount-detail-accounts" data-discount-accounts="">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id="discount-detail-accounts" className={`${SECTION_HEADING} mb-0`}>
          {t("rating.discountDetail.tab.accounts")}
        </h2>
        {props.handEnrolmentRefused !== true && (
          <Button
            variant="secondary"
            disabled={props.readOnly}
            title={readOnlyReason ?? undefined}
            onClick={() => setEnrolling(true)}
            data-discount-enroll=""
          >
            {t("rating.discountDetail.accounts.enroll")}
          </Button>
        )}
      </div>
      <DataTable<DiscountAccountRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError && query.data === undefined
            ? { reason: t("rating.discountDetail.accounts.failed"), onRetry: () => void query.refetch() }
            : undefined
        }
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
        downloadSlot={<DownloadButton onDownload={() => void download()} />}
        empty={{ title: t("rating.discountDetail.accounts.empty"), helper: "" }}
      />
      {ending !== null && (
        <EndEnrolmentDialog
          row={ending}
          client={props.client}
          regional={regional}
          onClose={() => setEnding(null)}
          onDone={() => {
            // DEF-RAT-9326: FormModal leaves closing to its caller.
            setEnding(null);
            refresh();
          }}
          t={t}
        />
      )}
      {enrolling && (
        <EnrollAccountDialog
          discountId={props.discountId}
          client={props.client}
          onClose={() => setEnrolling(false)}
          onDone={() => {
            // DEF-RAT-9326: FormModal leaves closing to its caller.
            setEnrolling(false);
            refresh();
          }}
          t={t}
        />
      )}
    </Panel>
  );
}
