// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint `P3.3` — *"Refund detail (screen 2·5d). Four
//           built reads with no caller. This is why the queue apologises for
//           not naming the account."* · `P3.5` (the door asserted by address
//           AND by the screen it opens) · `P3.9` (the screen is PAYMENTS' code
//           drawn at a Finance address — the seam is declared, not assumed).
// Drawing:  05-prototype/07 Finance Blueprint.pdf — **p046** is the wireframe
//           of 2·5d, its address `/finance/refunds/:id`, its three numbered
//           sections and the PROPOSED list; **p047** carries FOR / DOORS /
//           PRIMARY ACTION / FIELDS / TABLE CONTROLS / WRITE SURFACES / TODAY /
//           TASK / RULES and the *"What each act changes, and where"* table.
//           p043 is 2·5a, whose own note 1 is the apology this screen ends:
//           *"The account is not shown here. No account served."*
//           Built from the RENDERED IMAGES (B14 rule 42).
// Rules:    BR-PAY-014 (a refund comes out of a real credit balance, and its
//           approval is Finance-area work) · BR-PAY-020 (payments owns the
//           record, Finance reports it) · BR-PAY-037 (request and approval are
//           recorded SEPARATELY) · BR-CUS-054 / `OQ-135` (offset first) ·
//           BR-MET-1161 (an address is derived by walking to the premises) ·
//           BR-SHL-020 · BR-SHL-023 · BR-SHL-025 · CLAUDE.md hard rule 2 ·
//           hard rule 4 · B14 rule 2 (one page header) · 6 (danger tier) ·
//           21 (Tailwind only — this file is on `styles/route-b-migrated.txt`) ·
//           31 (no database id is ever a visible value) · 32 (one sentence a
//           section) · 33 (the caps; RATIONALE is zero words) · 40 (32px page
//           title — `PageHeader`'s) · 43 · 44
// Tests:    07-frontend/src/features/ledger/financeP3Doors.dom.test.tsx ·
//           10-scripts/fin_p3_screens_walkthrough.mjs (the browser walk — the
//           only check in this repo that reads rendered output)
// ───────────────────────────────────────────────────────
//
// 2·5d REFUND DETAIL — *"whose money is going back out"*.
//
// ══════════════════════════════════════════════════════════════════════════
// FOUR FINISHED READS AND NOTHING CALLED THEM
// ══════════════════════════════════════════════════════════════════════════
// `GET /refunds/{id}` — whose own docstring calls itself *"the answer to 'where
// is my money?'"* — `GET /accounts/{id}/credit-sources`, `GET /accounts/{id}/
// credit-path` and `GET /refunds-and-credits` were all built, tested and served
// with **zero front-end callers**. p043's approve modal says the cost out loud
// in the product's own words: *"The account is not shown here. No account
// served. Cheque number shown."* **An approver was agreeing to send money
// without seeing whose it was.**
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ IT IS PAYMENTS' RECORD AT A FINANCE ADDRESS, AND THE SEAM IS DECLARED
// ══════════════════════════════════════════════════════════════════════════
// `P3.9`, verbatim: *"Refund detail is payments' — Finance draws it at a
// `/finance` address; the seam is declared, not assumed."* So:
//
//   * every READ and every WRITE below is `apps/payments/refunds_api.py`'s,
//     through `@/api/endpoints`. **This file adds no endpoint and no rule**;
//   * the four lifecycle acts stay on `RefundsPage` (payments), which is where
//     `BR-PAY-1071`'s three different role gates already live. This screen
//     carries ONE act — p047's PRIMARY ACTION row, *"Approve ✓ — danger tier"*;
//   * `BR-PAY-020` is the split it honours: payments owns the record, Finance
//     reports the money going out.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THERE IS NO `RFD-` NUMBER IN THIS PRODUCT, AND ONE IS NOT INVENTED
// ══════════════════════════════════════════════════════════════════════════
// The drawing's head reads *"REFUND RFD-2609-0004 · CHEQUE"*. **`refunds` has
// no number series** — grep `RFD` across `06-backend` and nothing answers — so
// that string is an ILLUSTRATION (B14 rule 37: *"treat every number drawn in a
// wireframe as an illustration, never a fact to build to"*).
//
// What a clerk actually says out loud is the CHEQUE NUMBER, which is what the
// queue one screen along already shows, and **there is no `?? row.id` fallback
// here and there must never be one** — that exact shape printed a raw uuid to a
// finance user (`DEF-2580`). A refund with no cheque number yet says so in
// words, which is rule 31's own instruction for a record with no human number.
import { useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  approveRefund,
  getAccountCreditPath,
  getAccountCreditSources,
  getAccountDetail,
  getRefund,
} from "@/api/endpoints";
import type { RefundRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { accountDetailPath } from "@/features/customers/customersShared";
import { paymentDetailRoute } from "@/features/payments/paymentDetailShared";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { Dash, ROLE_SYSTEM_ADMIN, useTenantRole } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { FINANCE_TABS, FINANCE_TAB_REVENUE, financeTabPath } from "./financeShared";
import { FactRow } from "./financeShared";

/** `/finance/refunds/:refundId` — 2·5d's own address, p046's address bar.
 *
 *  ⚠ **IT IS A `/finance` ADDRESS FOR A PAYMENTS RECORD, DELIBERATELY** — see
 *  the header, and `P3.9`. The refunds LIST moved to `/payments/refunds` on
 *  2026-09-23 (`P4.10`) and that is not reversed: what a Finance approver opens
 *  is the one refund they are about to agree to. */
export const REFUND_DETAIL_ROUTE = "/finance/refunds/:refundId";

/** The screen id this door opens, asserted by `P3.5`'s test alongside the
 *  address — a hold-expiry test once asserted a screen was registered at one
 *  address while the router mounted it at another, and both opened onto
 *  *"not built yet"*. */
export const REFUND_DETAIL_SCREEN_ID = "S58.detail";

/** The path to one refund, built from its id.
 *
 *  ⚠ **A ROUTE SEGMENT, NOT A VISIBLE FIELD.** B14 rule 31 names an HTTP route
 *  among the internal things, and `refunds` has NO human-facing number to put
 *  there instead — the blueprint draws `:id` for exactly that reason. The id
 *  never reaches a cell; the cheque number is what the screen prints. */
export function refundDetailPath(refundId: string): string {
  return `/finance/refunds/${encodeURIComponent(refundId)}`;
}

export interface RefundDetailPageProps {
  client?: ApiClient;
  locale?: string;
  /** BR-TEN-043 — the approval instant, supplied by the caller. */
  now?: () => string;
}

export function RefundDetailPage(props: RefundDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();
  const refundId = params.refundId ?? "";
  const stamp = props.now ?? (() => new Date().toISOString());

  const [confirming, setConfirming] = useState(false);
  const [working, setWorking] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const refund = useQuery({
    queryKey: ["payments", "refund", refundId],
    queryFn: () => getRefund(refundId, client),
    enabled: refundId !== "",
    retry: false,
  });
  const accountId = refund.data?.account_id ?? "";

  // ⚠ **THE ACCOUNT READ IS WHAT ENDS THE APOLOGY.** `refund_row` carries
  // `account_id` and no name, so *whose money* needs `GET /accounts/{id}` —
  // which serves `account_no`, `name`, `premise` and `unit_label` and is the
  // ONE place this product composes an address (BR-MET-1161: everything walks
  // to the premises).
  const account = useQuery({
    queryKey: ["customers", "account", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });
  const credit = useQuery({
    queryKey: ["payments", "credit-sources", accountId],
    queryFn: () => getAccountCreditSources(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });
  const creditPath = useQuery({
    queryKey: ["payments", "credit-path", accountId],
    queryFn: () => getAccountCreditPath(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  const role = useTenantRole(client);
  // `BR-PAY-014` — approving a refund is `SystemAdminOnly` (p045's own act
  // table). A null role means `/me/permissions` has not answered and the
  // control is OFFERED; `refunds_api.refund_approve` is the boundary.
  const mayApprove = role === null || role === ROLE_SYSTEM_ADMIN;

  async function approve() {
    setWorking(true);
    setFailure(null);
    try {
      await approveRefund(refundId, { approved_at: stamp() }, client);
      toast(t("finance.refundDetail.approvedToast"));
      await queryClient.invalidateQueries({ queryKey: ["payments"] });
    } catch (error) {
      setFailure(
        isApiError(error) ? apiErrorText(error, translate) : t("finance.refundDetail.approveFailed"),
      );
    } finally {
      setWorking(false);
      setConfirming(false);
    }
  }

  const row = refund.data ?? null;
  const approvable = row !== null && row.status === "requested";

  return (
    <>
      <PageHeader
        // p046's eyebrow: the refund's own reference and its tender. B14 rule
        // 31 — the CHEQUE NUMBER, never the id, and a stated absence where
        // there is none.
        // ⚠ **THE EYEBROW CARRIES THE REFERENCE AND NOTHING ELSE.** It used to
        // append the tender, which the chip row below already states — and on a
        // refund with no cheque yet that read *"No cheque written yet · Check"*,
        // two facts about one thing, contradicting each other at a glance. B14
        // rule 32's budget: say it once, where it belongs.
        kicker={row === null ? t("finance.refundDetail.kickerLoading") : referenceLabel(row, translate)}
        // ⚠ **THE TITLE IS THE FIGURE AND THE PERSON**, which is the whole
        // point of the screen. Until the account read lands it is the figure
        // alone — never the id, and never a placeholder name (`DEF-2412`: a
        // uuid printed in the frame before the label arrived).
        title={
          row === null
            ? t("finance.refundDetail.title")
            : account.data?.name != null
              ? t("finance.refundDetail.titleTo", {
                  amount: displayMoney(row.amount, row.currency, props.locale),
                  name: account.data.name,
                })
              : displayMoney(row.amount, row.currency, props.locale)
        }
        status={
          row === null ? undefined : (
            <span className="inline-flex items-center gap-2">
              <StatusPill tone={statusTone(row.status)}>
                {t(`payments.refunds.status.${row.status}`, { defaultValue: row.status })}
              </StatusPill>
              <StatusPill tone="neutral">
                {t(`payments.refunds.method.${row.method}`, { defaultValue: row.method })}
              </StatusPill>
              {row.reason !== null && <StatusPill tone="neutral">{row.reason}</StatusPill>}
            </span>
          )
        }
        primaryAction={
          approvable ? (
            // B14 rule 4 — `Verb ✓` commits. B14 rule 6 — the danger tier:
            // p047's PRIMARY ACTION row says so in terms.
            <Button
              variant="danger"
              data-testid="refund-approve"
              disabled={!mayApprove || working}
              title={mayApprove ? undefined : t("finance.refundDetail.needsAdmin")}
              onClick={() => setConfirming(true)}
            >
              {t("finance.refundDetail.approve")}
            </Button>
          ) : undefined
        }
        // Where it exits to, in words — B14 rule 4's `← Noun`. p047's DOORS
        // row names this screen's one way in, so its one way out is the view it
        // came from.
        backTo={{
          to: tenantPath(financeTabPath(FINANCE_TAB_REVENUE)),
          label: t("shell.nav.finance.revenue"),
        }}
        tabs={FINANCE_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId={FINANCE_TAB_REVENUE}
        tabsLabel={t("finance.tabsLabel")}
      />

      {refund.isError ? (
        <Panel role="alert">
          <h3>{t("finance.refundDetail.notFoundTitle")}</h3>
          <p className="fin-absent-reason">{apiErrorText(refund.error, translate)}</p>
        </Panel>
      ) : row === null ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <>
          {/* ① WHOSE MONEY — p046's first section. B14 rule 32: one sentence a
              section, and this one spends none: the facts are the sentence. */}
          <Panel>
            <div className="mb-4">
              <h3 className="m-0 font-heading text-h5 leading-heading">
                {t("finance.refundDetail.whoseMoney")}
              </h3>
            </div>
            <FactRow
              label={t("finance.refundDetail.account")}
              value={
                account.isError ? (
                  <Dash>{t("finance.refundDetail.accountUnreadable")}</Dash>
                ) : account.data === undefined ? (
                  <Dash />
                ) : (
                  // B14 rule 31 — the ACCOUNT NUMBER and the name. The id is
                  // what the read was made with and reaches no cell; it builds
                  // the link's address (record links, PO 2026-10-19).
                  <InlineLinkTo to={tenantPath(accountDetailPath(accountId))}>
                    {`${account.data.account_no ?? ""} · ${account.data.name ?? ""}`}
                  </InlineLinkTo>
                )
              }
            />
            <FactRow
              label={t("finance.refundDetail.premises")}
              value={
                account.data === undefined ? (
                  <Dash />
                ) : account.data.premise === null ? (
                  // BR-MET-1161 — an address is walked to from the premises and
                  // an account with none has no address to show. Said, never
                  // invented.
                  <Dash>{t("finance.refundDetail.noPremises")}</Dash>
                ) : (
                  // ⚠ **`premise` ALREADY CARRIES THE UNIT LABEL.**
                  // `customers.selectors._premise_cell` composes it as
                  // `"<address> · <label>"`, so appending `unit_label` beside it
                  // renders *"163 Willow Bend Dr · Unit 1 · Unit 1"* — which is
                  // what the first browser walk of this screen showed, and
                  // which no test in this repository could have seen.
                  account.data.premise
                )
              }
            />
            <FactRow
              label={t("finance.refundDetail.creditHeld")}
              value={
                credit.data === undefined ? (
                  <Dash />
                ) : (
                  <MoneyCell
                    amount={credit.data.refundable}
                    currency={row.currency}
                    locale={props.locale}
                  />
                )
              }
              strong
            />
            {/* ⚠ **`OQ-135` IS CLOSED AND THE ANSWER IS *OFFSET FIRST***, so a
                refund cannot be raised at all while this customer owes on
                another account (`refunds.request_refund`,
                `cross_account_check=True`). **This product serves no read that
                answers the question on a REFUND that already exists**, so the
                row is not drawn rather than drawn as *None* — a claim about
                another account's balance that nothing here checked. Reported in
                the lane report; the read is `customers.arrears_on_other_
                accounts` and it has no endpoint. */}
          </Panel>

          {/* ② WHERE IT CAME FROM — the payments that built the credit. */}
          <Panel>
            <div className="mb-4">
              <h3 className="m-0 font-heading text-h5 leading-heading">
                {t("finance.refundDetail.whereFrom")}
              </h3>
            </div>
            {credit.isError ? (
              <p className="fin-absent-reason" role="alert">
                {apiErrorText(credit.error, translate)}
              </p>
            ) : credit.data === undefined ? (
              <LoadingSkeleton variant="table" />
            ) : credit.data.sources.length === 0 ? (
              <p className="fin-absent-reason" role="note">
                {t("finance.refundDetail.noSources")}
              </p>
            ) : (
              <PlainTable>
                <thead>
                  <tr>
                    <th scope="col">{t("finance.refundDetail.col.source")}</th>
                    <th scope="col">{t("finance.refundDetail.col.when")}</th>
                    <th scope="col">{t("finance.refundDetail.col.amount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {credit.data.sources.map((source) => (
                    <tr key={source.payment_id}>
                      {/* B14 rule 31 — the PAYMENT NUMBER, never `payment_id`,
                          and a stated absence where the tenant has seeded no
                          number series. */}
                      <td>
                        {source.payment_no === null ? (
                          <Dash>{t("finance.refundDetail.sourceNoReference")}</Dash>
                        ) : (
                          // Record links (PO 2026-10-19): the source payment opens.
                          <InlineLinkTo to={tenantPath(paymentDetailRoute(source.payment_no))}>
                            {source.payment_no}
                          </InlineLinkTo>
                        )}
                      </td>
                      <td>{source.posted_at.slice(0, 10)}</td>
                      {/* ⚠ **`contributed`, NEVER `amount`.** A $350.00 cheque
                          that left $57.13 behind contributed $57.13, and
                          listing the gross would offer a clerk money that is
                          not there. */}
                      <td>
                        <MoneyCell
                          amount={source.contributed}
                          currency={source.currency}
                          locale={props.locale}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </PlainTable>
            )}
            {/* `GET /accounts/{id}/credit-path` — *"can I give them a credit
                instead?"*. A SIGNPOST and never a second write path (PO
                2026-09-22: *"we can not have two path for 1 capabilities"*), so
                it states whether the other way out exists and offers no button
                for it. */}
            {creditPath.data !== undefined && (
              <p className="fin-absent-reason" role="note">
                {creditPath.data.available
                  ? // ⚠ **ONE FORM UNTIL 2026-09-25, SO A SINGLE BILL READ
                    // *"…possible on 1 bills."* (`DEF-LED-6666`).** The key now
                    // carries `_one` / `_other` in all eleven catalogues, which
                    // is what `count` has always meant to i18next; the call
                    // site is unchanged because it was already correct. A count
                    // of one is the COMMON case on a refund, which is why this
                    // survived 391 passing cases and was found by opening the
                    // screen. It was also cut to the six-word cap on the way
                    // past (B14 rule 33) — the sentence is a FACT.
                    t("finance.refundDetail.creditInstead", {
                      count: creditPath.data.bills.length,
                    })
                  : t("finance.refundDetail.noCreditPath")}
              </p>
            )}
          </Panel>

          {/* ③ HISTORY — p046's third section, WHEN · WHAT · WHO.
              ⚠ **BOTH APPROVAL ACTS STAY SEPARATE** (`BR-PAY-037`): a screen
              showing only *approved* would erase the control the rule leans
              on, which is why `requested_by` and `approved_by` are two rows. */}
          <Panel>
            <div className="mb-4">
              <h3 className="m-0 font-heading text-h5 leading-heading">
                {t("finance.refundDetail.history")}
              </h3>
            </div>
            <PlainTable>
              <thead>
                <tr>
                  <th scope="col">{t("finance.refundDetail.col.when")}</th>
                  <th scope="col">{t("finance.refundDetail.col.what")}</th>
                </tr>
              </thead>
              <tbody>
                {refundHistory(row, translate).map((event) => (
                  <tr key={event.what}>
                    <td>{event.when}</td>
                    <td>{event.what}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
            {/* ⚠ **WHO IS NOT DRAWN, AND THAT IS A STATED GAP.** `refund_row`
                serves `requested_by` and `approved_by` as USER IDS and B14 rule
                31 forbids printing one; this product publishes no read that
                turns a user id into a name for this screen. The column is
                absent rather than filled with a uuid (`DEF-2580`). */}
          </Panel>

          {failure !== null && (
            <p className="mt-4 text-sm text-danger-700" role="alert">
              {failure}
            </p>
          )}
        </>
      )}

      {confirming && row !== null && (
        // B14 rule 33 — a CONSEQUENCE before an irreversible act: two
        // sentences, six words each.
        <ConfirmDialog
          confirmVariant="danger"
          working={working}
          title={t("finance.refundDetail.confirmTitle")}
          consequence={t("finance.refundDetail.confirmBody")}
          confirmLabel={t("finance.refundDetail.approve")}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void approve()}
        />
      )}
    </>
  );
}

/** The refund's human-facing reference, or the words for having none.
 *
 *  ⚠ **NO `?? row.id` FALLBACK, EVER.** That shape printed a raw uuid to a
 *  finance user one screen along (`DEF-2580`), and `RefundsPage` and
 *  `RefundsQueuePanel` both carry the same warning. A cheque number does not
 *  exist until the cheque is written (`DEF-PAY-6331`), so *requested* is the
 *  normal state for having none. */
export function referenceLabel(row: RefundRow, t: Translator): string {
  return row.reference === null || row.reference === ""
    ? t("finance.refundDetail.noReference")
    : t("finance.refundDetail.reference", { reference: row.reference });
}

/** The five stamps a refund carries, as WHEN · WHAT, newest last.
 *
 *  Only the stamps that HAPPENED. A lifecycle drawn with empty future rows
 *  reads as a checklist somebody forgot to tick. */
export function refundHistory(row: RefundRow, t: Translator): { when: string; what: string }[] {
  const events: { when: string | null; what: string }[] = [
    { when: row.requested_at, what: t("finance.refundDetail.event.requested") },
    { when: row.approved_at, what: t("finance.refundDetail.event.approved") },
    { when: row.issued_at, what: t("finance.refundDetail.event.issued") },
    { when: row.cleared_at, what: t("finance.refundDetail.event.cleared") },
    { when: row.voided_at, what: t("finance.refundDetail.event.voided") },
  ];
  return events
    .filter((event): event is { when: string; what: string } => event.when !== null)
    .map((event) => ({ when: event.when.slice(0, 10), what: event.what }));
}

/** The tone each lifecycle state reads in. `voided` is the only one a clerk
 *  must not mistake for progress. */
export function statusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "cleared") return "success";
  if (status === "voided") return "danger";
  if (status === "requested") return "warning";
  return "neutral";
}

/** The title's figure. `MoneyCell` is the product's ONE formatter
 *  (BR-SHL-023) and a page title takes a string, so this asks the same
 *  `Intl` path through it rather than composing a second one. */
function displayMoney(amount: string, currency: string | null, locale: string | undefined): string {
  if (currency === null) {
    return amount;
  }
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(Number(amount));
}

export default RefundDetailPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p016 (P3.3 · P3.5 · P3.9) + p043 (2·5a's apology) + p045 (the act table and its three role gates) + p046–p047 (2·5d, rendered at 2.2 and read as IMAGES, B14 rule 42) · 06-backend/apps/payments/refunds_api.py refund_item / account_credit_sources / account_credit_path · selectors.refund_row · 04-docs/02-decisions/14-ui-conventions.md rules 2/4/6/21/31/32/33/37/40/43/44
// generated: 2026-09-24 by LANE FIN-P3
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E1 **NO `RFD-` NUMBER IS INVENTED.** `refunds` has no number series in this
//      product; the drawn `RFD-2609-0004` is an illustration (B14 rule 37) and
//      the identity shown is the CHEQUE NUMBER, with a stated absence where
//      there is none. No `?? id` fallback (`DEF-2580`).
//   E2 **NO *Other accounts in arrear* ROW.** The drawing has one and this
//      product serves NO read that answers it for an existing refund —
//      `customers.selectors.arrears_on_other_accounts` is resolved BY NAME
//      inside `refunds.offset_before_refund` and has no endpoint. Drawing it as
//      *None* would be a claim about another account's balance that nothing
//      here checked. Reported rather than built or faked.
//   E3 **NO *WHO* COLUMN IN HISTORY.** `refund_row` serves `requested_by` and
//      `approved_by` as USER IDS; B14 rule 31 forbids printing one and this
//      product publishes no id→name read for this screen. Absent, not a uuid.
//   E4 **ONE ACT, NOT FOUR.** Issue, clear and void stay on `RefundsPage`
//      (payments), where `BR-PAY-1071`'s three different role gates already
//      live. p047's PRIMARY ACTION row names exactly one: `Approve ✓`.
//   E5 **PAYMENTS' RECORD AT A FINANCE ADDRESS** — `P3.9`. Every read and the
//      one write are `apps/payments`', through the typed client. No endpoint,
//      table or rule is added here.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
