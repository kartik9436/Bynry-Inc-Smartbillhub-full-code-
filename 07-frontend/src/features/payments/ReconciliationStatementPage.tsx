// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · wave W8 · task 48 (P8) — the screen the four W8 backends
//           were written for. CS-14 (the period statement) · CS-16 (a
//           resolution may hang off a LINE) · CS-17 (the match SET) · CS-18
//           (the difference-reason lookup and its report).
// Defects:  DEF-PAY-10785 (P1 a1-3 — In the books names whose cheque) ·
//           DEF-PAY-10788 (P2 = A — Match to payment and Bank fee here, PO
//           2026-10-31, the SAME forms as the import review)
// Story:    US-PAY-020 (S37) · US-PAY-021 (S38) · US-PAY-022 (S40)
//           Screens: S37 · S40
// Rules:    BR-PAY-019 (bank rec is FINANCE work; every difference carries a
//           reason AND a general-ledger account) · BR-PAY-035 ("Force match
//           anyway" permanently SUPERSEDED) · BR-PAY-004 (a reconciled batch
//           LOCKS) · BR-SHL-020 (plain language when something is absent) ·
//           BR-SHL-023 (ONE money formatting path) · BR-SHL-025 (a control
//           this deployment cannot honour renders disabled WITH its reason) ·
//           BR-TEN-043 (the caller names the moment; no clock in a money path)
//           · B14 rule 21 (this directory is NOT on route-b-migrated.txt, so
//           every class here is one a stylesheet already declares) · rule 31
//           (no database id is the visible value of a field) · rule 32 (one
//           sentence per section; a stated absence is a closed `<details>`)
// ───────────────────────────────────────────────────────
// Reconcile one imported bank statement.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS: FOUR FINISHED BACKENDS BEHIND ONE UNBUILT SCREEN
// ══════════════════════════════════════════════════════════════════════════
// `GET /bank-statements/{id}/reconciliation`, `POST /bank-lines/{id}/resolve`,
// `POST /bank-rec/match-set` and `GET /bank-rec/differences` have all been
// mounted, tested and unreachable since 2026-09-01. `apps/payments/api.py`
// says so in its own words above them — *"NONE OF THESE HAS A SCREEN CONTROL
// YET … the endpoints are live and unreachable from the product"* — which is
// hard-won law 2 stated by the lane that built them and left for somebody to
// act on. Nothing in this product could reconcile a bank statement.
//
// ══════════════════════════════════════════════════════════════════════════
// IT STATES TWO FACTS AND EXPLAINS THE GAP. IT ADJUSTS NEITHER SIDE.
// ══════════════════════════════════════════════════════════════════════════
// PO ruling 2026-09-02 (`OQ-1310` closed), verbatim: *"we need to go on
// factual basis, if bank as report we count if bank did not report we dont
// count, and if clark wants to balance the book they can always make journal
// entries on their own - that is allowed"*.
//
// So the tie-out strip carries the bank's own closing figure, the ledger's own
// cash figure and the difference between them — and NOTHING on this screen
// adds a reconciling item to either side. There is no adjusted balance here
// because there is none on the body, and a screen that quietly nudged one side
// until it matched the other would be auto-fixing the books.
//
// ⚠ **`bank_equals_books` IS A FACT AND NOT A VERDICT, AND THIS SCREEN NEVER
// PRINTS THE WORDS "NOT RECONCILED".** A period with legitimate deposits in
// transit is properly reconciled and reads `false`. The reconciling items are
// the answer and a clerk decides.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE ARITHMETIC THIS SCREEN DOES, AND WHY IT IS NOT AN INVENTION
// ══════════════════════════════════════════════════════════════════════════
// `residualOf` below asks the only question that turns this from a report into
// a control: **do the listed items account for the whole difference?** The
// identity it uses is not this lane's — it is written down twice in the
// repository, in `bankrec_read.reconciliation_statement`'s own docstring and
// in CR-059's task 43 row, in these words:
//
//     "the bank says 48,112.40, the books say 46,946.12, and the 1,166.28
//      between them is exactly the three items (1,122.78 − 44.50 + 88.00)"
//
// So: deposits in transit, LESS outstanding refund cheques, PLUS unexplained
// lines. The server deliberately serves no `sign` on an item — those signs
// were deleted on 2026-09-02 so that no screen could render an item as an
// addend to a balance — and this screen keeps that: **no item is ever drawn
// with a sign, and the subtraction exists only to produce ONE SENTENCE.**
// Either the items account for the difference, or a named amount does not.
// Recorded as a lane judgment in `12-governance/02-decision-log.md`.
//
// It is computed on scaled BigInt through `depositsShared.scaledDecimal`, so
// nothing here is a float: `Number("1122.78") - Number("44.50")` is the shape
// of every money defect this repository has logged.
//
// ⚠ **AND IT IS NULL, NEVER ZERO, WHENEVER ANY INPUT IS NULL.** A statement
// imported before the balance columns existed has no bank figure and a chart
// with no designated cash account has no book figure; "we could not do the
// sum" and "the two agree" are different answers and only one is good news
// (DEF-127, the defect this whole family is named after).
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS SCREEN REFUSES TO DRAW
// ══════════════════════════════════════════════════════════════════════════
//   1. **A general-ledger account NUMBER typed by hand.** The chart is the
//      tenant's own and the account is CHOSEN from it, by code and name. The
//      id is the option's value and never its visible text (B14 rule 31).
//   2. **"Force match anyway."** BR-PAY-035 made it permanently superseded and
//      no request body this screen can build would reconcile a residual. It is
//      not disabled here; it does not exist.
//   3. **A "posted" tick on an explained line.** Creating a journal entry from
//      a bank line is batch decision G3 and is unruled, so an explanation
//      records the reason and the account and the books are untouched. The
//      screen says so in a closed `<details>` rather than leaving a clerk to
//      assume the books have caught up.
//   4. **A way to dissolve a match set.** CS-17 rules the set IN and rules
//      nothing about undoing one; the service and the database have no such
//      path, so a control here would promise something no code could honour.
import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createMatchSet,
  getDepositBatches,
  getDifferenceReport,
  getReconciliationStatement,
  getStatementReview,
  resolveBankLine,
} from "@/api/bankRecEndpoints";
import type {
  DepositBatchRow,
  DifferenceReport,
  LinePostingResult,
  ReconcilingItem,
  ReconcilingItemRow,
  ReconciliationStatement,
  StatementImportRow,
} from "@/api/bankRecEndpoints";
import { getLedgerAccounts } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { PlainTable } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import type { RegionalDateFormat } from "@/components/DateCell";
import { isDenied, useRegional, useAccessCell } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  MatchSeveralDepositsModal,
  SetMatchedLines,
  UnexplainedLineActions,
} from "./MatchSeveralDeposits";
import { BankFeeForm, MatchReturnForm, matchedToText } from "./StatementLineActions";
import {
  BANKREC_PERMISSION,
  BankFigure,
  DEPOSITS_ROUTE,
  GapNotes,
  amountForInput,
  scaledDecimal,
} from "./depositsShared";

import "./payments.css";

export const reconciliationQueryKey = (statementId: string) =>
  ["payments", "bank-reconciliation", statementId] as const;

export const differenceReportQueryKey = (from: string, to: string) =>
  ["payments", "bank-rec-differences", from, to] as const;

/** The tenant's chart, for the explain form's account picker. Its own key so a
 *  chart edited in another tab is refetched here rather than read from a cache
 *  this screen never invalidates. */
export const glAccountsQueryKey = ["payments", "bank-rec", "gl-accounts"] as const;

const SCALE = 6; // NUMERIC(18,6) — the storage grid, and the wire's own

/**
 * A scaled BigInt back to an exact decimal STRING, for `MoneyCell`.
 *
 * Nothing here rounds and nothing here formats — display rounding is
 * `MoneyCell`'s and is the only one in this product (BR-SHL-023). This just
 * puts the decimal point back where the scale says it is.
 */
export function scaledToDecimal(value: bigint): string {
  const negative = value < 0n;
  const digits = (negative ? -value : value).toString().padStart(SCALE + 1, "0");
  const whole = digits.slice(0, digits.length - SCALE);
  const fraction = digits.slice(digits.length - SCALE);
  return `${negative ? "-" : ""}${whole}.${fraction}`;
}

/** One reconciling item off the body, by code, or undefined when the server
 *  did not send it. Undefined is NOT zero — see the module docstring. */
export function itemOf(
  body: ReconciliationStatement,
  code: string,
): ReconcilingItem | undefined {
  return body.reconciling_items.find((item) => item.code === code);
}

/**
 * How much of the difference the listed items do NOT account for.
 *
 * `null` means the question could not be asked: the bank's figure, the books'
 * figure or one of the three item totals is missing, and a residual computed
 * over a hole would read as "everything is explained" on a statement nobody
 * could reconcile. `0n` means they account for it exactly.
 *
 * The identity is quoted in this module's header and is the server's own,
 * from `bankrec_read.reconciliation_statement`: deposits in transit LESS
 * outstanding refund cheques PLUS unexplained lines. It is used for one
 * sentence and produces no figure that is ever added to a balance.
 */
export function residualOf(body: ReconciliationStatement): bigint | null {
  const difference = body.difference_bank_less_books;
  if (difference === null) {
    return null;
  }
  const target = scaledDecimal(difference);
  if (target === null) {
    return null;
  }
  let explained = 0n;
  const signs: [string, bigint][] = [
    ["deposits_in_transit", 1n],
    ["outstanding_refunds", -1n],
    ["unexplained_lines", 1n],
  ];
  for (const [code, sign] of signs) {
    const item = itemOf(body, code);
    if (item === undefined || item.amount === null) {
      return null;
    }
    const scaled = scaledDecimal(item.amount);
    if (scaled === null) {
      return null;
    }
    explained += sign * scaled;
  }
  return target - explained;
}

/** The row's own date, whichever of the three shapes it is. A deposit carries
 *  a banking day, a refund an issue day and a bank line a posting day — three
 *  different facts that share one column on this table. */
export function itemRowDate(row: ReconcilingItemRow): string | null {
  return row.deposited_on ?? row.issued_on ?? row.posted_on ?? null;
}

/** What a clerk reads in the identity column. NEVER the id (B14 rule 31): a
 *  deposit has its `DEP-` label, a refund its reference, and a bank line the
 *  line number the statement itself prints. */
export function itemRowLabel(row: ReconcilingItemRow, t: Translator): string {
  if (row.code !== undefined && row.code !== null) {
    return row.code;
  }
  if (row.reference !== undefined && row.reference !== null && row.reference !== "") {
    return row.reference;
  }
  if (row.line_no !== undefined && row.line_no !== null) {
    return t("payments.deposits.bank.line", { n: row.line_no });
  }
  return t("payments.deposits.noReference");
}

/** An age in whole days, or the stated absence. `0` is a real answer — an item
 *  banked on the period end is nought days old — so the falsy test that would
 *  swallow it is written out long-hand. */
export function ageText(days: number | null, t: Translator): string {
  return days === null
    ? t("payments.deposits.statement.noAge")
    : t("payments.deposits.statement.days", { count: days });
}

/** A served date, or its stated absence. `DateCell` takes a `string` and this
 *  family's dates are all nullable — a refund issued before the column was
 *  filled has none — so a blank cell would read as a load failure rather than
 *  as the fact that nobody recorded a date (BR-SHL-020). */
export function StatementDate(props: {
  value: string | null;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  if (props.value === null || props.value === "") {
    return (
      <span className="pay-absent" role="note">
        {props.t("payments.deposits.noDate")}
      </span>
    );
  }
  return (
    <DateCell value={props.value} timeZone={props.timeZone} dateFormat={props.dateFormat} />
  );
}

// ── The tie-out ────────────────────────────────────────────────────────────

/**
 * Three figures and ONE sentence.
 *
 * The sentence is the whole point of the screen: *do the items below account
 * for the difference?* A reconciliation that lists items without answering it
 * is a report, and the person reading it still has to do the sum by hand —
 * which is what they were doing before this screen existed.
 */
export function TieOut(props: {
  body: ReconciliationStatement;
  t: Translator;
  locale?: string;
}) {
  const { body, t } = props;
  const residual = residualOf(body);
  return (
    <>
      <KPIStrip
        kpis={[
          {
            id: "bank",
            label: t("payments.deposits.kpi.bankShows"),
            value: (
              <BankFigure
                amount={body.bank_closing_balance}
                currency={body.currency}
                reason={t("payments.deposits.statement.bankUnknown")}
                locale={props.locale}
              />
            ),
          },
          {
            id: "books",
            label: t("payments.deposits.statement.booksSay"),
            value: (
              <BankFigure
                amount={body.book_cash_balance}
                currency={body.currency}
                reason={t("payments.deposits.statement.booksUnknown")}
                locale={props.locale}
              />
            ),
          },
          {
            id: "difference",
            label: t("payments.deposits.kpi.difference"),
            value: (
              <BankFigure
                amount={body.difference_bank_less_books}
                currency={body.currency}
                reason={t("payments.deposits.statement.differenceUnknown")}
                locale={props.locale}
              />
            ),
          },
        ]}
      />
      {/* `bank_equals_books` is null when the comparison could not be made,
          and that is a THIRD answer rather than a worse "they differ". */}
      {body.bank_equals_books === true ? (
        <p className="pay-ties" role="note">
          {t("payments.deposits.statement.agree")}
        </p>
      ) : residual === null ? (
        <p className="pay-absent" role="note">
          {t("payments.deposits.statement.cannotCheck")}
        </p>
      ) : residual === 0n ? (
        <p className="pay-ties" role="note">
          {t("payments.deposits.statement.explains")}
        </p>
      ) : (
        // ⚠ THE LINE THIS SCREEN EXISTS FOR. A difference the items do not
        // account for is money nobody has explained, and it is named with its
        // figure rather than left for a clerk to subtract by hand.
        <p className="pay-attention" role="note">
          <span className="pay-chip-label">
            {t("payments.deposits.statement.residualLabel")}
          </span>{" "}
          <MoneyCell
            amount={scaledToDecimal(residual)}
            currency={body.currency}
            locale={props.locale}
          />
        </p>
      )}
    </>
  );
}

// ── What explains it ───────────────────────────────────────────────────────

export function ReconcilingItemsTable(props: {
  body: ReconciliationStatement;
  t: Translator;
  locale?: string;
}) {
  const { body, t } = props;
  return (
    <div className="pay-table-scroll">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.statement.colItem")}</th>
            <th scope="col" className="fin-num">
              {t("payments.deposits.statement.colCount")}
            </th>
            <th scope="col" className="fin-num">
              {t("payments.col.amount")}
            </th>
            <th scope="col">{t("payments.deposits.statement.colOldest")}</th>
          </tr>
        </thead>
        <tbody>
          {body.reconciling_items.map((item) => (
            <tr key={item.code}>
              <td>{t(`payments.deposits.statement.item.${item.code}`, { defaultValue: item.code })}</td>
              <td className="fin-num">{item.count}</td>
              <td className="fin-num">
                {/* No sign and no signed amount: these EXPLAIN the difference
                    and are not addends to either side (PO 2026-09-02). */}
                <BankFigure
                  amount={item.amount}
                  currency={body.currency}
                  reason={t("payments.deposits.statement.itemUnknown")}
                  locale={props.locale}
                />
              </td>
              <td>{ageText(item.oldest_age_days, t)}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

// ── The lines nobody has explained ─────────────────────────────────────────

export interface ExplainDraft {
  reason_code: string;
  gl_account_id: string;
  amount: string;
  note: string;
}

export const EMPTY_EXPLAIN: ExplainDraft = {
  // NOTHING DEFAULTS THE REASON. BR-PAY-019 wants a human's judgement, and a
  // seeded "processor fee" would land on a cash shortage and a bank error
  // alike — the same argument the batch-level form already makes.
  reason_code: "",
  gl_account_id: "",
  amount: "",
  note: "",
};

export function explainSchema(t: Translator) {
  return z.object({
    reason_code: z.string().min(1, t("payments.deposits.form.reasonRequired")),
    gl_account_id: z.string().min(1, t("payments.deposits.form.glRequired")),
    amount: z
      .string()
      .regex(/^-?\d+(\.\d{1,6})?$/, t("payments.deposits.form.amountInvalid"))
      .refine((value) => !/^-?0*(\.0*)?$/.test(value), {
        message: t("payments.deposits.form.amountNonZero"),
      }),
  });
}

export function UnexplainedTable(props: {
  item: ReconcilingItem | undefined;
  currency: string;
  t: Translator;
  locale?: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  selected: readonly string[];
  onToggle: (bankLineId: string) => void;
  onExplain: (row: ReconcilingItemRow) => void;
  /** DEF-PAY-10780 — "+ Match to several deposits" on a credit line. */
  onMatchSeveral: (row: ReconcilingItemRow) => void;
  /** P2 = A (PO 2026-10-31) — Match to payment / Bank fee on a line the bank
   *  took OUT. Absent hides both. */
  onLineAction?: (kind: "match_return" | "bank_fee", row: ReconcilingItemRow) => void;
}) {
  const { item, t } = props;
  if (item === undefined || item.rows.length === 0) {
    return (
      <p className="pay-ties" role="note">
        {t("payments.deposits.statement.unexplainedNone")}
      </p>
    );
  }
  return (
    <div className="pay-table-scroll">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.statement.colTie")}</th>
            <th scope="col">{t("payments.deposits.col.bankReference")}</th>
            <th scope="col">{t("payments.deposits.col.date")}</th>
            <th scope="col" className="fin-num">
              {t("payments.col.amount")}
            </th>
            <th scope="col">{t("payments.deposits.statement.colOldest")}</th>
            <th scope="col">{t("payments.deposits.col.action")}</th>
          </tr>
        </thead>
        <tbody>
          {item.rows.map((row) => {
            const lineId = row.bank_line_id ?? "";
            return (
              <tr key={lineId}>
                <td>
                  <input
                    type="checkbox"
                    checked={props.selected.includes(lineId)}
                    onChange={() => props.onToggle(lineId)}
                    aria-label={itemRowLabel(row, t)}
                  />
                </td>
                <td>{itemRowLabel(row, t)}</td>
                <td>
                  <StatementDate
                    value={itemRowDate(row)}
                    t={t}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                </td>
                <td className="fin-num">
                  <BankFigure
                    amount={row.amount}
                    currency={props.currency}
                    reason={t("payments.deposits.statement.itemUnknown")}
                    locale={props.locale}
                  />
                </td>
                <td>{ageText(row.age_days, t)}</td>
                <td>
                  <UnexplainedLineActions
                    amount={row.amount}
                    onExplain={() => props.onExplain(row)}
                    onMatchSeveral={() => props.onMatchSeveral(row)}
                    actions={row.actions}
                    onMatchReturn={
                      props.onLineAction === undefined
                        ? undefined
                        : () => props.onLineAction?.("match_return", row)
                    }
                    onBankFee={
                      props.onLineAction === undefined
                        ? undefined
                        : () => props.onLineAction?.("bank_fee", row)
                    }
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    </div>
  );
}

// ── Differences by reason (CS-18) ──────────────────────────────────────────

export function DifferencesTable(props: {
  report: DifferenceReport;
  t: Translator;
  locale?: string;
}) {
  const { report, t } = props;
  if (report.rows.length === 0) {
    return (
      <p className="pay-absent" role="note">
        {t("payments.deposits.statement.differencesNone")}
      </p>
    );
  }
  const names = new Map(report.reasons.map((reason) => [reason.code, reason.name]));
  return (
    <div className="pay-table-scroll">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.col.reason")}</th>
            <th scope="col">{t("payments.deposits.statement.colGlAccount")}</th>
            <th scope="col" className="fin-num">
              {t("payments.deposits.statement.colCount")}
            </th>
            <th scope="col" className="fin-num">
              {t("payments.col.amount")}
            </th>
          </tr>
        </thead>
        <tbody>
          {report.rows.map((row) => (
            <tr key={`${row.reason_code}|${row.gl_account_id}`}>
              {/* The tenant's own NAME for the reason where it has one; the
                  stored code is what the books group on and is the honest
                  fallback for a reason since deactivated (BR-TEN-034). */}
              <td>{names.get(row.reason_code) ?? row.reason_code}</td>
              <td>
                {row.gl_account_code === null && row.gl_account_name === null ? (
                  // B14 rule 31 — an account the chart could not name renders
                  // its absence, never its uuid.
                  <span className="pay-absent">
                    {t("payments.deposits.statement.noGlAccount")}
                  </span>
                ) : (
                  `${row.gl_account_code ?? ""} ${row.gl_account_name ?? ""}`.trim()
                )}
              </td>
              <td className="fin-num">{row.count}</td>
              <td className="fin-num">
                <BankFigure
                  amount={row.total}
                  currency={report.currency}
                  reason={t("payments.deposits.statement.itemUnknown")}
                  locale={props.locale}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

// ── LBX-05 · lines matched to a return or posted as a fee ──────────────────

export function PostedLinesTable(props: {
  body: ReconciliationStatement;
  t: Translator;
  locale?: string;
}) {
  const { body, t } = props;
  const rows = body.posted_lines?.rows ?? [];
  return (
    <div className="pay-table-scroll">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.col.date")}</th>
            <th scope="col">{t("payments.deposits.col.bankReference")}</th>
            <th scope="col">{t("payments.deposits.lines.what")}</th>
            <th scope="col">{t("payments.deposits.lines.payment")}</th>
            <th scope="col" className="fin-num">
              {t("payments.col.amount")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.bank_line_id}>
              <td>{row.posted_on ?? ""}</td>
              <td>
                {/* P1 a1-3 — "RET1029-01 → Clara Castillo · AC-2026-00003". */}
                {matchedToText(row.reference, row.customer_name, row.account_no) ??
                  row.reference ??
                  t("payments.deposits.noReference")}
              </td>
              <td>
                {row.kind === "returned_item"
                  ? t("payments.deposits.lines.kindReturned")
                  : t("payments.deposits.lines.bankFee")}
              </td>
              <td>{row.cheque ?? row.payment_no ?? ""}</td>
              <td className="fin-num">
                <BankFigure
                  amount={row.amount}
                  currency={body.currency}
                  reason={t("payments.deposits.statement.itemUnknown")}
                  locale={props.locale}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

/** A reconciliation row as the statement-line forms read it. */
export function moneyOutLine(row: ReconcilingItemRow) {
  return {
    bank_line_id: row.bank_line_id ?? "",
    reference: row.reference ?? null,
    posted_on: row.posted_on ?? null,
    amount: row.amount,
    search_hint: row.search_hint ?? null,
  };
}

// ── The stated absence (B14 rule 32) ───────────────────────────────────────

/**
 * A `<details>` CLOSED by default, on `billing/billRunShared.tsx`'s `RunGap`
 * pattern and with its own classes rather than Tailwind utilities: this
 * directory is NOT on `route-b-migrated.txt`, so a utility written here is a
 * class no stylesheet declares and renders as nothing at all.
 *
 * `data-tracks` carries the row that will close the absence, on the ELEMENT
 * and never in the sentence — a clerk at a two-person utility can do nothing
 * with an internal id (B14 rule 31).
 */
export function StatementAbsence(props: {
  summary: string;
  message: string;
  tracks: string;
}) {
  return (
    <details data-tracks={props.tracks} className="pay-absent">
      <summary>{props.summary}</summary>
      <p role="note">{props.message}</p>
    </details>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface ReconciliationStatementPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  locale?: string;
}

export function ReconciliationStatementPage(props: ReconciliationStatementPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();
  const cell = useAccessCell(BANKREC_PERMISSION, client);
  const { timeZone, dateFormat } = useRegional(props);

  // WHICH STATEMENT, in the URL. A reconciliation is a document somebody signs
  // off and then sends to their accountant; a selection held only in component
  // state could not be linked to, and re-opening the page would silently
  // reconcile a different month.
  const [searchParams, setSearchParams] = useSearchParams();
  const chosen = searchParams.get("statement") ?? "";

  const [explaining, setExplaining] = useState<ReconcilingItemRow | null>(null);
  const [draft, setDraft] = useState<ExplainDraft>(EMPTY_EXPLAIN);
  const [tieOpen, setTieOpen] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [batches, setBatches] = useState<string[]>([]);
  const [several, setSeveral] = useState<ReconcilingItemRow | null>(null);
  // P2 = A — the import review's two forms, opened on a reconciliation row.
  const [lineAction, setLineAction] = useState<{
    kind: "match_return" | "bank_fee";
    row: ReconcilingItemRow;
  } | null>(null);

  // The statements already imported ride on the S37 list body, so this screen
  // adds no route of its own to learn what there is to reconcile.
  const listQuery = useQuery({
    queryKey: ["payments", "deposit-batches", ""] as const,
    queryFn: () => getDepositBatches({}, client),
    retry: false,
  });

  const statementQuery = useQuery({
    queryKey: reconciliationQueryKey(chosen),
    queryFn: () => getReconciliationStatement(chosen, client),
    retry: false,
    enabled: chosen !== "",
  });

  // The batches a set may be tied to, and the reason vocabulary, both read off
  // reads that already exist. `open_batches` is the S38 review's own list.
  const reviewQuery = useQuery({
    queryKey: ["payments", "statement-review", chosen] as const,
    queryFn: () => getStatementReview(chosen, client),
    retry: false,
    enabled: chosen !== "",
  });

  const period = statementQuery.data?.statement;
  const from = period?.period_start ?? "";
  const to = period?.period_end ?? "";
  const differencesQuery = useQuery({
    queryKey: differenceReportQueryKey(from, to),
    queryFn: () => getDifferenceReport({ from, to }, client),
    retry: false,
    enabled: from !== "" && to !== "",
  });

  const glQuery = useQuery({
    queryKey: glAccountsQueryKey,
    queryFn: () => getLedgerAccounts(client),
    retry: false,
  });

  const explainMutation = useMutation({
    mutationFn: (input: { bankLineId: string; draft: ExplainDraft }) =>
      resolveBankLine(
        input.bankLineId,
        {
          reason_code: input.draft.reason_code,
          gl_account_id: input.draft.gl_account_id,
          amount: input.draft.amount,
          // BR-TEN-043 — the caller names the moment. The server holds no
          // clock at all on this path.
          occurred_at: new Date().toISOString(),
          note: input.draft.note === "" ? undefined : input.draft.note,
        },
        client,
      ),
  });

  const tieMutation = useMutation({
    mutationFn: (input: { lines: string[]; batches: string[] }) =>
      createMatchSet(
        {
          bank_line_ids: input.lines,
          batch_ids: input.batches,
          occurred_at: new Date().toISOString(),
        },
        client,
      ),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />
    );
  }
  if (statementQuery.isError && isPermissionDenied(statementQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />
    );
  }

  const imports: StatementImportRow[] = listQuery.data?.statement_imports ?? [];
  const openBatches: DepositBatchRow[] = reviewQuery.data?.open_batches ?? [];
  const body = statementQuery.data;
  const failed = statementQuery.isError && body === undefined;

  async function invalidate(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: ["payments", "bank-reconciliation"] });
    await queryClient.invalidateQueries({ queryKey: ["payments", "statement-review"] });
    await queryClient.invalidateQueries({ queryKey: ["payments", "bank-rec-differences"] });
    await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
  }

  async function handleExplain(): Promise<FormSubmitOutcome> {
    const bankLineId = explaining?.bank_line_id ?? "";
    if (bankLineId === "") {
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
    try {
      const result = await explainMutation.mutateAsync({ bankLineId, draft });
      setExplaining(null);
      setDraft(EMPTY_EXPLAIN);
      // ⚠ A REPLAY IS NOT A SECOND EXPLANATION AND IS NOT TOASTED AS ONE. The
      // door answers 200 with the row that already exists and `created:false`;
      // congratulating somebody for work that did not happen is the shape the
      // correction screen shipped a refusal for on 2026-09-02.
      toast(
        result.created
          ? t("payments.deposits.statement.explainDone")
          : t("payments.deposits.statement.explainReplay"),
      );
      await invalidate();
      return { ok: true };
    } catch (error) {
      // The server's refusals land here and are SHOWN (BR-SHL-020): a line
      // already carrying a DIFFERENT explanation is refused quoting what it
      // says, and a MATCHED line is refused because its difference belongs on
      // the batch. A form that closed silently on either would tell a clerk
      // the work was done.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  async function handleTie(): Promise<FormSubmitOutcome> {
    try {
      const result = await tieMutation.mutateAsync({ lines, batches });
      setTieOpen(false);
      setLines([]);
      setBatches([]);
      toast(
        result.created
          ? t("payments.deposits.statement.tieDone", { batches: result.batch_codes.join(", ") })
          : t("payments.deposits.statement.tieReplay"),
      );
      await invalidate();
      return { ok: true };
    } catch (error) {
      // The set's two sides must foot EXACTLY and the server names both sums
      // when they do not. Nothing here apportions a difference — nothing rules
      // how to apportion one across five members.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  /** P2 = A — a returned line matched or a fee posted: say what landed, the
   *  import review's own three sentences, and re-read both bodies. */
  async function lineActionDone(result: LinePostingResult): Promise<void> {
    setLineAction(null);
    toast(
      !result.created
        ? t("payments.deposits.lines.replay")
        : result.posted
          ? t("payments.deposits.lines.done")
          : t("payments.deposits.lines.linked"),
    );
    await queryClient.invalidateQueries({ queryKey: reconciliationQueryKey(chosen) });
    await queryClient.invalidateQueries({ queryKey: ["payments", "statement-review"] });
    await queryClient.invalidateQueries({ queryKey: ["payments", "bank-rec-differences"] });
  }

  const unexplained = body === undefined ? undefined : itemOf(body, "unexplained_lines");
  const reasons = differencesQuery.data?.reasons ?? [];

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("payments.deposits.statement.kicker")}
        title={t("payments.deposits.statement.title")}
        backTo={{ to: tenantPath(DEPOSITS_ROUTE), label: t("payments.deposits.backToList") }}
      />

      <Panel>
        <div className="fin-panel-head">
          <h3>{t("payments.deposits.statement.pick")}</h3>
        </div>
        {imports.length === 0 ? (
          <p className="pay-absent" role="note">
            {t("payments.deposits.statement.pickNone")}
          </p>
        ) : (
          <SelectField
            id="statement"
            label={t("payments.deposits.bank.statement")}
            value={chosen}
            onChange={(value) =>
              setSearchParams(value === "" ? {} : { statement: value }, { replace: true })
            }
            placeholder={t("payments.deposits.statement.pickPrompt")}
            options={imports.map((row) => ({
              // The id is the option's VALUE and never its visible text
              // (B14 rule 31) — a clerk picks a bank account and a month.
              value: row.id,
              label: `${row.bank_account_name ?? t("payments.deposits.noBankAccount")} · ${
                row.period_start ?? ""
              } — ${row.period_end ?? ""}`,
            }))}
          />
        )}
      </Panel>

      {chosen === "" ? null : failed ? (
        <Panel role="alert">
          <h3>{t("payments.deposits.errorTitle")}</h3>
          <p className="pay-absent">{apiErrorText(statementQuery.error, translate)}</p>
        </Panel>
      ) : body === undefined ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <>
          <TieOut body={body} t={translate} locale={props.locale} />

          <Panel>
            <div className="fin-panel-head">
              <h3>{t("payments.deposits.statement.itemsTitle")}</h3>
            </div>
            <ReconcilingItemsTable body={body} t={translate} locale={props.locale} />
          </Panel>

          <Panel>
            <div className="fin-panel-head">
              <h3>{t("payments.deposits.statement.unexplainedTitle")}</h3>
              {/* CS-17's control. Disabled WITH its reason rather than hidden
                  (BR-SHL-025): a clerk whose bank posted two deposits as one
                  credit must be able to see that the product can do it. */}
              <Button
                variant="secondary"
                disabled={lines.length === 0 || openBatches.length === 0}
                onClick={() => setTieOpen(true)}
              >
                {t("payments.deposits.statement.tie")}
              </Button>
              {(lines.length === 0 || openBatches.length === 0) && (
                <span className="pay-absent" role="note">
                  {t("payments.deposits.statement.tieNeeds")}
                </span>
              )}
            </div>
            <UnexplainedTable
              item={unexplained}
              currency={body.currency}
              t={translate}
              locale={props.locale}
              timeZone={timeZone}
              dateFormat={dateFormat}
              selected={lines}
              onToggle={(lineId) =>
                setLines((current) =>
                  current.includes(lineId)
                    ? current.filter((one) => one !== lineId)
                    : [...current, lineId],
                )
              }
              onExplain={(row) => {
                setDraft({
                  ...EMPTY_EXPLAIN,
                  // The LINE's own amount is pre-filled because it is a served
                  // fact and the clerk is explaining exactly it. The reason and
                  // the account are not — BR-PAY-019 wants a human on both.
                  amount: row.amount === null ? "" : amountForInput(row.amount),
                });
                setExplaining(row);
              }}
              onMatchSeveral={(row) => setSeveral(row)}
              onLineAction={(kind, row) => setLineAction({ kind, row })}
            />
          </Panel>

          {/* DEF-PAY-10780 — a line tied to several deposits reads
              "Matched · N deposits" (the approved mock-up). */}
          {(reviewQuery.data?.rows ?? []).some((row) => row.state === "set_matched") && (
            <Panel>
              <div className="fin-panel-head">
                <h3>{t("payments.deposits.several.title")}</h3>
              </div>
              <SetMatchedLines
                rows={reviewQuery.data?.rows ?? []}
                currency={body.currency}
                locale={props.locale}
                timeZone={timeZone}
                dateFormat={dateFormat}
              />
            </Panel>
          )}

          {/* LBX-05 (G3 ruled 2026-10-30) — lines the bank took OUT that are
              now IN THE BOOKS: a returned cheque matched to its payment, and
              the bank's fee. Already inside the books' cash above. */}
          {(body.posted_lines?.count ?? 0) > 0 && (
            <Panel>
              <div className="fin-panel-head">
                <h3>{t("payments.deposits.lines.inTheBooks")}</h3>
              </div>
              <PostedLinesTable body={body} t={translate} locale={props.locale} />
            </Panel>
          )}

          {body.explained_not_posted.count > 0 && (
            <Panel>
              <div className="fin-panel-head">
                <h3>{t("payments.deposits.statement.explainedNotPosted")}</h3>
              </div>
              <p className="pay-rollup">
                <span className="pay-rollup-label">
                  {t("payments.deposits.statement.colCount")}
                </span>
                <span className="pay-rollup-value">{body.explained_not_posted.count}</span>
                <span className="pay-rollup-label">{t("payments.col.amount")}</span>
                <span className="pay-rollup-value">
                  <BankFigure
                    amount={body.explained_not_posted.amount}
                    currency={body.currency}
                    reason={t("payments.deposits.statement.itemUnknown")}
                    locale={props.locale}
                  />
                </span>
              </p>
              <StatementAbsence
                summary={t("payments.deposits.statement.notPosted")}
                message={t("payments.deposits.statement.notPostedBody")}
                tracks="OQ-1310"
              />
            </Panel>
          )}

          <Panel>
            <div className="fin-panel-head">
              <h3>{t("payments.deposits.statement.differencesTitle")}</h3>
            </div>
            {differencesQuery.data === undefined ? (
              <LoadingSkeleton variant="table" />
            ) : (
              <DifferencesTable
                report={differencesQuery.data}
                t={translate}
                locale={props.locale}
              />
            )}
          </Panel>

          <GapNotes gaps={body.unavailable} t={translate} />
        </>
      )}

      {lineAction !== null && body !== undefined && (
        lineAction.kind === "match_return" ? (
          <MatchReturnForm
            line={moneyOutLine(lineAction.row)}
            currency={body.currency}
            locale={props.locale}
            client={client}
            onClose={() => setLineAction(null)}
            onDone={(result) => void lineActionDone(result)}
          />
        ) : (
          <BankFeeForm
            line={moneyOutLine(lineAction.row)}
            currency={body.currency}
            locale={props.locale}
            client={client}
            onClose={() => setLineAction(null)}
            onDone={(result) => void lineActionDone(result)}
          />
        )
      )}

      {explaining !== null && body !== undefined && (
        <FormModal
          title={t("payments.deposits.statement.explainTitle")}
          kicker={itemRowLabel(explaining, translate)}
          schema={explainSchema(translate)}
          values={draft}
          submitLabel={t("payments.deposits.statement.explainSubmit")}
          onSubmit={handleExplain}
          onClose={() => setExplaining(null)}
        >
          <p className="pay-form-note">{t("payments.deposits.statement.explainHelp")}</p>
          <p className="pay-resolve-facts">
            <span>
              {t("payments.deposits.col.date")}:{" "}
              <StatementDate
                value={itemRowDate(explaining)}
                t={translate}
                timeZone={timeZone}
                dateFormat={dateFormat}
              />
            </span>
            <span>
              {t("payments.col.amount")}:{" "}
              <BankFigure
                amount={explaining.amount}
                currency={body.currency}
                reason={t("payments.deposits.statement.itemUnknown")}
                locale={props.locale}
              />
            </span>
          </p>
          {reasons.length === 0 ? (
            // ⚠ AN EMPTY REASON LIST IS LAWFUL AND COMMON. It is discretionary
            // reference data and every tenant provisioned before 2026-09-01 has
            // none; the server still accepts any non-blank reason from them, so
            // the form ASKS rather than blocking the workflow it governs.
            <TextField
              id="reason_code"
              label={t("payments.deposits.form.reason")}
              value={draft.reason_code}
              onChange={(value) => setDraft({ ...draft, reason_code: value })}
              required
              help={t("payments.deposits.statement.reasonsNone")}
            />
          ) : (
            <SelectField
              id="reason_code"
              label={t("payments.deposits.form.reason")}
              value={draft.reason_code}
              onChange={(value) => {
                const picked = reasons.find((one) => one.code === value);
                setDraft({
                  ...draft,
                  reason_code: value,
                  // The reason's OWN account, where the tenant mapped one. It
                  // is a suggestion and stays editable: the account a
                  // difference posts to is BR-PAY-019's other half and a
                  // clerk may overrule the default.
                  gl_account_id: picked?.default_gl_account_id ?? draft.gl_account_id,
                });
              }}
              required
              placeholder={t("payments.deposits.statement.reasonPrompt")}
              options={reasons.map((reason) => ({ value: reason.code, label: reason.name }))}
            />
          )}
          <SelectField
            id="gl_account_id"
            label={t("payments.deposits.form.gl")}
            value={draft.gl_account_id}
            onChange={(value) => setDraft({ ...draft, gl_account_id: value })}
            required
            placeholder={t("payments.deposits.statement.glPrompt")}
            // The chart's own CODE and NAME. The id is the option's value and
            // is never read by a person (B14 rule 31) — and no account NUMBER
            // is written into this file, because the chart is the tenant's.
            options={(glQuery.data ?? []).map((account) => ({
              value: account.id,
              label: `${account.code} ${account.name}`,
            }))}
          />
          <TextField
            id="amount"
            label={t("payments.deposits.form.amount")}
            value={draft.amount}
            onChange={(value) => setDraft({ ...draft, amount: value })}
            numeric
            required
            help={t("payments.deposits.form.amountHelp")}
          />
          <TextField
            id="note"
            label={t("payments.deposits.form.note")}
            value={draft.note}
            onChange={(value) => setDraft({ ...draft, note: value })}
            multiline
            help={t("payments.deposits.form.noteHelp")}
          />
          <StatementAbsence
            summary={t("payments.deposits.statement.notPosted")}
            message={t("payments.deposits.statement.notPostedBody")}
            tracks="OQ-1310"
          />
        </FormModal>
      )}

      {several !== null && body !== undefined && (
        <MatchSeveralDepositsModal
          line={{
            bank_line_id: several.bank_line_id ?? "",
            reference: itemRowLabel(several, translate),
            posted_on: itemRowDate(several),
            amount: several.amount,
          }}
          openBatches={openBatches}
          currency={body.currency}
          locale={props.locale}
          timeZone={timeZone}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setSeveral(null)}
          onDone={(result, count) => {
            const label = itemRowLabel(several, translate);
            setSeveral(null);
            // A replay is not a second match and is not toasted as one.
            toast(
              result.created
                ? t("payments.deposits.several.done", {
                    line: label,
                    count,
                    amount: formatMoney(result.matched_total, result.currency, props.locale),
                  })
                : t("payments.deposits.statement.tieReplay"),
            );
            void invalidate();
          }}
        />
      )}

      {tieOpen && (
        <FormModal
          title={t("payments.deposits.statement.tieTitle")}
          kicker={t("payments.deposits.statement.tie")}
          schema={{ safeParse: () => ({ success: true as const, data: {} }) } as never}
          values={{}}
          submitLabel={t("payments.deposits.statement.tieSubmit")}
          onSubmit={handleTie}
          onClose={() => setTieOpen(false)}
        >
          <p className="pay-form-note">{t("payments.deposits.statement.tieHelp")}</p>
          <fieldset className="pay-pair-list">
            <legend>{t("payments.deposits.statement.tieBatches")}</legend>
            {openBatches.length === 0 ? (
              <p className="pay-absent" role="note">
                {t("payments.deposits.noOpenBatches")}
              </p>
            ) : (
              openBatches.map((batch) => (
                <label key={batch.id}>
                  <input
                    type="checkbox"
                    checked={batches.includes(batch.id)}
                    onChange={() =>
                      setBatches((current) =>
                        current.includes(batch.id)
                          ? current.filter((one) => one !== batch.id)
                          : [...current, batch.id],
                      )
                    }
                  />
                  {/* The batch LABEL, never its id (B14 rule 31). */}
                  {batch.code}
                </label>
              ))
            )}
          </fieldset>
        </FormModal>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-020@5b2e814 (CR-059 §8 CS-14/CS-16/CS-17/CS-18 verbatim + §10 P8; 12-governance/11-change-requests.md task rows 43-46 and 48; 06-backend/apps/payments/bankrec_read.py + reconciliation.py payload builders, read field for field; 04-docs/02-decisions/14-ui-conventions.md rules 21/31/32)
// generated: 2026-09-02 by story-coder (CR-059 W8 screen lane — four finished backends behind one unbuilt screen)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reconciliationStatement.test.tsx failed to resolve this module before it existed, and each of its four behaviour assertions was shown red against a deliberately broken implementation; verbatim in the lane report. tsc✔ · vitest✔ · vite build✔
// exceptions: (1) `residualOf` performs the ONE subtraction on this screen. The identity is the SERVER's, quoted verbatim in the module header from `bankrec_read.reconciliation_statement` and from CR-059's task 43 row, and it produces ONE SENTENCE and no figure that is ever added to a balance — no item is drawn with a sign, which is what the PO's 2026-09-02 ruling deleted from the body. Recorded as a lane judgment in the decision log · (2) there is no adjusted bank balance anywhere on this screen, because there is none on the body · (3) the words "not reconciled" appear nowhere: `bank_equals_books` is a fact and a period with legitimate deposits in transit reads false · (4) no GL account NUMBER is typed here — the chart is the tenant's own and the account is chosen from it by code and name · (5) there is no dissolve control for a match set: CS-17 rules the set in and rules nothing about undoing one, and neither the service nor the database has a path · (6) CS-15 (matching an OUTGOING item to its bank line) is task 47 and is not built, so no refund cheque on this screen carries a match control — the outstanding-refunds item is listed and aged and nothing more
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
