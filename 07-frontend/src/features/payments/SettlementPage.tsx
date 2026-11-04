// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.7` — §03 frame **5·2 Settlement**,
//           `05-prototype/06 Payments Page Blueprint.pdf` **p071** (the
//           address, the question, the head, the four tiles, the member table
//           and the two annotations) and **p072** (step 3 *What you can do to
//           it* and step 4 *What it changes*), read AS IMAGES at 2.0 (B14
//           rule 42).
// Screens:  5·2 Settlement (`S-NEW · PAY-P`) — entered from a row on 5·1
// Rules:    B14 rule 1 (the header's `←` names where it EXITS) · rule 2 (one
//           page header) · rules 12–17 (the member table's controls — p071's
//           own Rules row reads `B14 12–17 · 31 · 33 · hard rules 2 and 5`) ·
//           rule 31 (the address and the title are the PROVIDER'S reference) ·
//           rule 33 · rule 40 (the page-head title is 32px) · rule 43 ·
//           rule 21 · BR-SHL-020 (a plain sentence, never a raw code) ·
//           BR-TEN-003 / HR-1 (an unknown reference reads as ABSENT) · NFR-3
// Tests:    src/features/payments/settlementScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║        "Which 46 payments made up this $8,047.30?"                       ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 * p071's question for 5·2, and its TODAY line is one word: **"Nothing."**
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ THERE IS NOTHING TO DO HERE, AND THE DRAWING SPENDS A WHOLE STEP SAYING SO
 * ══════════════════════════════════════════════════════════════════════════
 * p072, step 3, titled *"What you can do to it — Nothing, and that is the
 * design"*, verbatim: *"It is a **statement of fact from a provider**. There is
 * nothing to approve, nothing to edit and nothing to cancel — if a payout is
 * wrong, the provider issues another one. Every action a clerk might want here
 * belongs to the **payment** inside it (tab 2) or to the **bank match**
 * (Finance). Drawn as a step rather than left out, because **a step with
 * nothing in it is a decision**, and a reader should be able to see it was
 * made."*
 *
 * So this page has **no header action, no row action but the eye, no bulk bar
 * and no dialog**. The absence is the specification, and it is asserted rather
 * than left to this comment (hard-won law 1).
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE FOUR TILES — GROSS · FEES · NET · BANK
 * ══════════════════════════════════════════════════════════════════════════
 * p071 ① — *"Fees · the difference between what a customer paid and what we
 * banked"*. ② — *"One credit · which is the whole reason a batch number is
 * needed"*.
 *
 * ⚠ **THE THREE MONEY FIGURES ARE THE PROVIDER'S, CHECKED AND NEVER
 * RE-DERIVED.** `ck_settlements_net_ties` refuses a stored row where
 * `gross − fees ≠ net`, so the screen prints the stored three. Computing a net
 * here would agree with us by construction and hide the one error a provider
 * can make that reaches the books.
 *
 * ⚠ **AND THE GROSS IS THE CUSTOMER'S MONEY.** A $100.00 card payment with a
 * $2.90 fee is a $100.00 payment and a $2.90 expense — never a $97.10 payment.
 * That is `CR-139-BRC07` §2.3, the money-correctness heart of this phase, and
 * it is why the member table draws GROSS and FEE as two columns rather than one
 * net figure.
 *
 * ⚠ **p071's FIGURES ARE ILLUSTRATIONS** (B14 rule 37): `$8,204.11`, `$156.81`,
 * `$8,047.30`, `1.91%`, `BRM-2609-0044` and the 46 are a demo tenant's.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE ADDRESS CARRIES THE PROVIDER'S REFERENCE, NOT THE KEY
 * ══════════════════════════════════════════════════════════════════════════
 * `/{tenant}/payments/settlements/STL-260921-CARD`, which is what p071 puts in
 * the address bar. B14 rule 31: an address bar is the most visible field a
 * screen has. `settlement_models.py` records why that reference is the
 * PROVIDER'S own string rather than a number we mint — the clerk is reading
 * the processor's statement, and a second number would give one payout two
 * names and guarantee somebody quotes the wrong one on the telephone.
 */
import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getSettlement, getSettlementMembers } from "@/api/settlementEndpoints";
import type { SettlementMemberRow } from "@/api/settlementEndpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { useCrumbLeaf } from "@/components/crumbLeaf";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { DEFAULT_PAGE_SIZE, serializeTableParams } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import { accountDetailPath } from "@/features/customers/customersShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { PAYMENTS_TAB_SETTLEMENTS, paymentsTabPath } from "./paymentsShared";
import { paymentDetailRoute } from "./paymentDetailShared";
import {
  BankMark,
  Percent,
  SettlementMoney,
  settlementMembersQueryKey,
  settlementQueryKey,
} from "./settlementsShared";
import type { Translator } from "./settlementsShared";

export interface SettlementPageProps extends RegionalProps {
  client?: ApiClient;
  locale?: string;
}

const INITIAL_STATE: TableRequestState = {
  q: "",
  // p071 draws the members newest-taken first.
  sort: "taken",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

/**
 * ⚠ **THE REQUEST IS BUILT FROM A STABLE SHAPE** — `serializeTableParams` reads
 * only `config.filters`, and this table declares none: p071 draws the toolbar
 * with `All` selected and no chip, and a filter the drawing does not evidence
 * is a control B14 rule 41 did not ask for. Declared explicitly so the empty
 * set is a decision a reader can see rather than an omission.
 */
const REQUEST_SHAPE: TableConfig<SettlementMemberRow> = {
  screenId: "PAY-P.members",
  getRowId: (row) => row.payment_no ?? row.account_no,
  defaultSort: { sort: INITIAL_STATE.sort, dir: INITIAL_STATE.dir },
  columns: [],
  filters: [],
};

export function SettlementPage(props: SettlementPageProps) {
  const { t } = useTranslation();
  // `apiErrorText` and the shared `BankMark` both take a plain `Translator`
  // rather than i18next's own `TFunction`, so the binding is made once here.
  const translate: Translator = (key, params) =>
    params === undefined ? t(key) : t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  // The address carries the PROVIDER'S REFERENCE (B14 rule 31), which is also
  // the breadcrumb leaf and the page title a clerk reads out.
  const { settlementRef = "" } = useParams<{ settlementRef: string }>();
  useCrumbLeaf(settlementRef === "" ? null : settlementRef);

  const [state, setState] = useState<TableRequestState>(INITIAL_STATE);

  const payout = useQuery({
    queryKey: settlementQueryKey(settlementRef),
    queryFn: () => getSettlement(client, settlementRef),
    retry: false,
  });

  const params = useMemo(() => serializeTableParams(state, REQUEST_SHAPE), [state]);
  const members = useQuery({
    queryKey: [...settlementMembersQueryKey(settlementRef), params.toString()],
    queryFn: () => getSettlementMembers(client, settlementRef, Object.fromEntries(params)),
    // Nothing to list until the payout resolves, and a 404 on the head would
    // otherwise be reported twice in two different sentences.
    enabled: payout.data !== undefined,
    retry: false,
  });

  const config = useMemo<TableConfig<SettlementMemberRow>>(
    () => ({
      screenId: "PAY-P.members",
      getRowId: (row) => row.payment_no ?? row.account_no,
      // B14 rule 19 — p071's own placeholder, and the server's `q` matches all
      // three things it names: the account number, the customer (through
      // customers' published search) and the payment's reference.
      searchPlaceholder: "payments.settlement.members.search",
      searchFields: ["account_no", "customer_name", "reference"],
      defaultSort: { sort: INITIAL_STATE.sort, dir: INITIAL_STATE.dir },
      filters: [],
      columns: [
        {
          key: "payment_no",
          label: t("payments.settlement.members.col.payment"),
          sortable: true,
          identity: true,
          // B14 rule 31 — the `PMT-` series number. A null is a STATED ABSENCE
          // in words, never the payment's key: `payment_no` is nullable so an
          // import path that cannot reach the series fails loudly instead of
          // colliding, and the screen has to render that state.
          // Record links (PO 2026-10-19): the number opens the payment.
          cell: (row) =>
            row.payment_no !== null ? (
              <InlineLinkTo to={tenantPath(paymentDetailRoute(row.payment_no))}>
                {row.payment_no}
              </InlineLinkTo>
            ) : (
              <span className="text-neutral-700">{t("payments.settlement.members.noNumber")}</span>
            ),
        },
        {
          key: "taken",
          label: t("payments.settlement.members.col.taken"),
          sortable: true,
          cell: (row) => (
            <DateCell
              value={row.taken_at}
              timeZone={timeZone}
              dateFormat={dateFormat}
              withTime
            />
          ),
        },
        {
          key: "account_no",
          label: t("payments.settlement.members.col.account"),
          cell: (row) =>
            row.account_id !== undefined && row.account_id !== "" ? (
              <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>
                {row.account_no}
              </InlineLinkTo>
            ) : (
              row.account_no
            ),
        },
        {
          key: "customer_name",
          label: t("payments.settlement.members.col.customer"),
          cell: (row) =>
            row.customer_name ?? (
              <span className="text-neutral-700">{t("payments.settlement.members.noName")}</span>
            ),
        },
        {
          key: "reference",
          label: t("payments.settlement.members.col.reference"),
          // What a person read off a device or a statement. A payment taken
          // without one is ordinary, so an absence here is a dash rather than
          // a sentence — it is not a finding.
          cell: (row) => row.reference ?? <span className="text-neutral-700">—</span>,
        },
        {
          key: "gross",
          label: t("payments.settlement.members.col.gross"),
          sortable: true,
          numeric: true,
          // ⚠ THE CUSTOMER'S OWN MONEY. Never the netted figure — see the
          // module docstring, and `ingest_payout` refuses a member whose gross
          // is not the payment's amount so the wrong version cannot get here.
          cell: (row) => (
            <SettlementMoney amount={row.gross} currency={row.currency} locale={props.locale} />
          ),
        },
        {
          key: "fee",
          label: t("payments.settlement.members.col.fee"),
          numeric: true,
          cell: (row) => (
            <SettlementMoney amount={row.fee} currency={row.currency} locale={props.locale} />
          ),
        },
      ],
    }),
    [t, timeZone, dateFormat, props.locale, tenantPath],
  );

  // B14 rule 1 — the header's `←` names where it EXITS to, which is the tab
  // this row was opened from. p071's *Doors* row: *"A row on 5·1. 1 door."*
  const backTo = {
    to: tenantPath(paymentsTabPath(PAYMENTS_TAB_SETTLEMENTS)),
    label: t("payments.tab.settlements"),
    testId: "settlement-back",
  };

  if (payout.isError && payout.data === undefined) {
    return (
      <>
        <PageHeader
          title={t("payments.settlement.detail.title")}
          backTo={backTo}
          kicker={t("payments.title")}
        />
        {/* BR-SHL-020: a plain sentence, never a raw code. An unknown or
            cross-tenant reference reads as ABSENT here exactly as it does on
            the wire — a 403 would confirm the row exists somewhere else
            (BR-TEN-003, HR-1). */}
        <Panel role="alert">
          <h3>{t("payments.settlement.detail.failedTitle")}</h3>
          <p className="met-panel-hint">{apiErrorText(payout.error, translate)}</p>
        </Panel>
      </>
    );
  }
  if (payout.data === undefined) {
    return (
      <>
        <PageHeader
          title={t("payments.settlement.detail.title")}
          backTo={backTo}
          kicker={t("payments.title")}
        />
        <LoadingSkeleton variant="kpi" />
      </>
    );
  }

  const view = payout.data;

  return (
    <>
      {/* B14 rule 40 — the page-head title is 32px, and `PageHeader` is where
          that lives. The TITLE IS THE PAYOUT'S REFERENCE, which p071 draws as
          the heading and which is the same string the address carries. */}
      <PageHeader
        title={view.code}
        backTo={backTo}
        kicker={t("payments.title")}
        rollup={
          // p071's sub-line: `Stripe · paid out 09/20 02:14 · 46 payments`.
          // Composed from three parts rather than one sentence key so the DATE
          // renders through `DateCell` in the tenant's own format and zone —
          // a date formatted into a translated string is the one place this
          // product has twice shipped a different day to a different reader.
          <>
            {view.provider}
            {" · "}
            {t("payments.settlement.detail.paidOut")}{" "}
            <DateCell
              value={view.paid_out_at}
              timeZone={timeZone}
              dateFormat={dateFormat}
              withTime
            />
            {" · "}
            {t("payments.settlement.detail.payments", { count: view.payments })}
          </>
        }
      />
      <KPIStrip
        kpis={[
          {
            id: "gross",
            label: t("payments.settlement.detail.tile.gross"),
            money: {
              amount: view.gross,
              currency: view.currency,
              basis: "posting",
              locale: props.locale,
            },
            detail: t("payments.settlement.detail.tile.grossDetail"),
          },
          {
            // ① — *"the difference between what a customer paid and what we
            // banked"*. The share is THIS payout's own and the server computed
            // it: hard rule 2 keeps that division off a float in the browser.
            id: "fees",
            label: t("payments.settlement.detail.tile.fees"),
            money: {
              amount: view.fees,
              currency: view.currency,
              basis: "posting",
              locale: props.locale,
            },
            detail: <Percent value={view.fee_share} />,
          },
          {
            id: "net",
            label: t("payments.settlement.detail.tile.net"),
            money: {
              amount: view.net,
              currency: view.currency,
              basis: "clearing",
              locale: props.locale,
            },
            detail: t("payments.settlement.detail.tile.netDetail"),
          },
          {
            // ② — *"One credit · which is the whole reason a batch number is
            // needed"*. The pill and the credit's reference are ONE fact,
            // rendered by the component both screens share (B14 rule 43).
            id: "bank",
            label: t("payments.settlement.detail.tile.bank"),
            value: <BankMark status={view.status} reference={view.bank_reference} t={translate} />,
            detail:
              view.bank_reference === null
                ? undefined
                : t("payments.settlement.detail.tile.bankDetail"),
          },
        ]}
      />
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={members.data?.rows ?? []}
        totalRows={members.data?.count ?? null}
        loading={members.isLoading}
        error={
          members.isError
            ? {
                reason: t("payments.settlement.members.failed"),
                onRetry: () => void members.refetch(),
              }
            : null
        }
        // B14 rule 17 — what is missing. ⚠ **NO CTA**, for p072's own reason:
        // a payout's membership is written by the provider's feed, and there is
        // nothing a clerk can press to put a payment inside one.
        empty={{
          title: t("payments.settlement.members.empty.title"),
          helper: t("payments.settlement.members.empty.helper"),
        }}
      />
    </>
  );
}

export default SettlementPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.7` · blueprint p071–p072 as images at 2.0 · DEF-PAY-6286
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A✔ B✔ C✔ D=n/a(there is no write — p072 step 3) E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/settlementScreens.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: the row's `…` overflow glyph p071 sketches is not built — p072's step 3 says a settlement has no actions, and a payment's own acts live on 2·2
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
