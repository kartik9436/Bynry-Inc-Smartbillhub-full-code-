// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-004 (S33 Record payments: search, the type/method/status/
//           purpose filters, the "Applied to" column, the capability row's
//           default posting-date-desc sort and its filter totals) ·
//           US-PAY-001 (the S22/S35 Record modal — account, amount, BOTH
//           BR-PAY-021 dates, method, reference, allocation choice, memo, and
//           the result panel that says what the money paid) ·
//           US-PAY-002 (the payment PURPOSE this form could not send until
//           2026-08-15) · US-PAY-005 (the S32 Summary tab, wired here) ·
//           US-PAY-013 (the S34 Outstandings tab, wired here)
//           Screens: S33 (AppShell sidebar → Payments → Record payments) · S22
//           · S35 · S32 · S34
// Rules:    BR-PAY-001 (the staff allocation choice) · BR-PAY-002 (payments are
//           append-only — this screen offers no edit affordance on any row and
//           no write wrapper exists for one) · BR-PAY-010 (allocation order) ·
//           BR-PAY-012 (purpose — all FOUR are offered now) ·
//           BR-PAY-021 (posting date ≠ clearing date; both collected, both
//           columns) · BR-PAY-022 (the single-entry field set) · BR-PAY-024
//           (the receipt this deployment does not queue) · BR-PAY-026 (the
//           method list is the tenant's own, live) · BR-PAY-027 (the IS-5
//           capability row) · BR-PAY-028 (one submit token per opened form) ·
//           BR-PAY-033 (the posting date is PRE-FILLED and overridable) ·
//           BR-SHL-010 (a capability not declared is not rendered) ·
//           BR-SHL-011 (the URL grammar) · BR-SHL-012 (the A18 states) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-023 (one money path) ·
//           BR-SHL-025 (a forbidden or unhonourable control renders disabled
//           WITH its reason) · BR-SHL-034 (one date formatter) · BR-SHL-044
//           (one page header)
// ───────────────────────────────────────────────────────
// S33 — the Payments page. The payments WRITE PATH landed on 2026-08-11: a
// payment could be recorded, allocated across the customer's open bills and
// posted to the books, under nineteen passing tests, with `apps/payments/api.py`
// a one-line docstring in front of it. **No human being could record a
// payment.** This is the screen; `POST /accounts/{id}/payments` and
// `GET /payments` are the two endpoints it calls, and both are served.
//
// WHAT THE PROTOTYPE DRAWS ON THIS PAGE AND THIS SCREEN DOES NOT, each named on
// screen rather than mimed:
//
//   · **No bulk toolbar.** The prototype's "3 selected · $988.70 total" bar
//     offers Reverse · Reapply to bill · Send receipts · Post to QuickBooks.
//     Every one of them is another story's write endpoint and not one exists;
//     three of the four are additionally BLOCKED on PO decisions that have not
//     been made (the bounce, refund and collections questions in
//     `12-governance/12-payments-decision-batch.md`). A checkbox column whose
//     only actions are absent selects rows for nothing.
//   · **No row action menu.** Same reason: View · Reverse · Reapply · Send
//     receipt · Refund. There is no payment DETAIL route either (no contract
//     row defines one), and what a detail would add — what the payment paid —
//     is on the row already.
//   · **No CSV export.** `POST /exports` registers no `payments` resource, and
//     BR-SHL-010 keeps an undeclared capability unrendered.
//   · **No "Import lockbox", "Post adjustment" or "Issue credit" header
//     action.** US-PAY-003 (whose posting-date semantics are OQ-131, blocking)
//     and the adjustment/credit family, none of them served.
//
// AND ONE THING THAT WAS TRUE HERE UNTIL 2026-08-15 AND IS NOT ANY MORE: this
// docstring used to say *"No Summary tab and no Outstandings tab … both tabs
// render what they are waiting for"*. Both read-models had shipped complete and
// tested by then and the tabs still rendered the *awaiting* panel over the top
// of them — hard-won law 2 at feature scale. `SummaryTab.tsx` (S32) and
// `OutstandingsTab.tsx` (S34) are the callers, and no tab on this page renders
// an "arrives with" panel any more.
//
// AND ONE PLACE THE PROTOTYPE IS RIGHT AND THIS SCREEN IS BEHIND: the prototype
// opens the Payments page on **Record payments**; this one opens on Summary,
// because the ratified sidebar (BR-SHL-001) maps `/payments` to Summary. Both
// divergences are recorded in `paymentsShared.tsx` and in this lane's report.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  PAYMENT_ORIGINS,
  REVERSAL_REASONS,
  correctPaymentReference,
  getPayments,
  reversePayment,
} from "@/api/endpoints";
// CR-059 CS-31 (task 36). The plan read lives in `bankRecEndpoints.ts` rather
// than in `endpoints.ts` for that file's own recorded reason: 15,000 lines that
// three lanes edit on any afternoon is where a pathspec commit eats somebody's
// work (hard-won law 11).
import { getReversalPlan } from "@/api/bankRecEndpoints";
import type {
  CorrectedReference,
  PaymentMethodOption,
  PaymentRow,
  PaymentsPageResponse,
  PaymentsTotals,
  RecordedPayment,
  ReversalReason,
  ReversedPayment,
} from "@/api/endpoints";
import { Button, ButtonLink } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DataTable } from "@/components/DataTable";
import { DateCell, todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { EyeIcon, PencilIcon, RollBackIcon, SwapIcon, TagIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import {
  RowAction,
  RowActionLink,
  RowActions,
  RowActionsMore,
  RowMenuAction,
} from "@/components/RowActions";
import { PermissionDenied } from "@/components/StateFrame";
// `CR-135` `P1.9` — the kit's resting chip, for §03 2·1's Source column. Not a
// `StatusPill`: a source is not a status, and a second badge is what B14 rule 5
// exists to stop.
import { Chip } from "@/components/Chip";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import {InlineLinkAnchor} from "@/components/Surfaces";
import { dateRangeFilter, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { billDetailPath } from "@/features/billing/billingShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import {
  CELL_FULL,
  Dash,
  GuardedButton,
  ROLE_SYSTEM_ADMIN,
  isDenied,
  useRegional,
  useAccessCell,
  useTenantRole,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import {
  FINANCE_PERMISSION,
  FINANCE_TAB_REVENUE,
  financeTabPath,
} from "@/features/ledger/financeShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BulkRefundModal,
  BulkReverseModal,
  BulkRunPanel,
  EMPTY_SELECTION,
  PaymentsBulkBar,
  bulkFailureText,
  bulkReapplyRefusal,
  bulkReceiptRefusal,
  bulkRefundRefusal,
  bulkReverseRefusal,
  deselectMany,
  failedRows,
  getSelectionTotal,
  keyFor,
  reapplyOne,
  receiptOne,
  refreshSelection,
  refundOne,
  reverseOne,
  rowLabel,
  runPerRow,
  selectionTotalKey,
  succeededIds,
  toggleSelected,
} from "./paymentsBulk";
import type {
  BulkActionId,
  BulkRun,
  PaymentSelection,
  PerRowOutcome,
} from "./paymentsBulk";
import { OutstandingsTab } from "./OutstandingsTab";
import { BANK_MEMO_MAX, NsfFeeChoice, NsfFeeLine } from "./reverseNsfFee";
// `CR-135` `P1.5` — the Imports tab's own body. Four lines of configuration
// over `components/workflow/ImportRunsList`, which is the shared run list this
// task extracted: *"A fourth caller, not a fourth implementation."*
import { PAYMENTS_IMPORT_NEW_ROUTE, PaymentsImportsTab } from "./PaymentsImportsTab";
import { CountersTab } from "./CountersTab";
// 5·1 (`CR-139-BRC07` `P5.7`) — the payouts a processor actually made, and the
// one door onto 5·2. A COMPONENT rather than a block in this page (B14 rule 43).
import { SettlementsTab } from "./SettlementsTab";
import { CounterHeadSlot } from "./CounterDoors";
import { counterRoute } from "./counterShared";
import { SummaryTab } from "./SummaryTab";
import {
  appliedBills,
  releasedByCorrection,
  PAYMENTS_PERMISSION,
  PAYMENTS_RECORD_NEW_ROUTE,
  PAYMENTS_TABS,
  PAYMENTS_TABS_AWAITING_A_SCREEN,
  PAYMENTS_TAB_COUNTER,
  PAYMENTS_TAB_IMPORTS,
  PAYMENTS_TAB_OUTSTANDINGS,
  PAYMENTS_TAB_RECORD,
  PAYMENTS_TAB_SETTLEMENTS,
  PAYMENTS_TAB_SUMMARY,
  COLLECTIONS_LADDER_ROUTE,
  REFUNDS_ROUTE,
  listRouteAbsent,
  methodOptions,
  PAYMENT_STATUS_FILTER_ORDER,
  paymentStatusLabel,
  paymentStatusTone,
  paymentTypeLabel,
  paymentsDisplayCurrency,
  paymentsTabFrom,
  paymentsTabPath,
  PROBLEM_CODES_DELETED_ON_PURPOSE,
  firstRecordOutcome,
  remainingToAllocate,
} from "./paymentsShared";
import { paymentDetailRoute } from "./paymentDetailShared";
import { depositBatchRoute } from "./depositsShared";
// `CR-135` `P1.6` — B14 rule 43: these are COMPONENTS in their own file, not
// three hundred lines inline in a page that is already 2,900 long.
import { MovePaymentModal, ReapplyPaymentModal } from "./paymentMoveReapply";
import { PrintReceiptButton } from "./PrintReceipt";

import "./payments.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const paymentsQueryKey = (query: string) => ["payments", query] as const;

export interface PaymentsCells {
  /**
   * The TENANT-RELATIVE address of screen 2·2 for this row — `CR-137-BRC07`
   * `P3.9`/`P3.10`.
   *
   * ⚠ **IT LIVES HERE BECAUSE THIS IS WHERE `tenantPath` IS.** `paymentsCells`
   * already closes over it; `paymentsTableConfig` does not, and threading a
   * second copy through `extras` would be two ways to build one address —
   * which is how a figure drifts (decision log, 2026-09-05).
   */
  detailTo: (row: PaymentRow) => string;
  paymentNo: (row: PaymentRow) => JSX.Element;
  postedAt: (row: PaymentRow) => JSX.Element;
  clearedAt: (row: PaymentRow) => JSX.Element;
  account: (row: PaymentRow) => JSX.Element;
  customer: (row: PaymentRow) => JSX.Element;
  type: (row: PaymentRow) => JSX.Element;
  method: (row: PaymentRow) => JSX.Element;
  confirmation: (row: PaymentRow) => JSX.Element;
  appliedTo: (row: PaymentRow) => JSX.Element;
  amount: (row: PaymentRow) => JSX.Element;
  status: (row: PaymentRow) => JSX.Element;
  purpose: (row: PaymentRow) => JSX.Element;
  receiptNo: (row: PaymentRow) => JSX.Element;
  /** §03 2·1 ④ — *"the three ways money reaches this list"*. */
  source: (row: PaymentRow) => JSX.Element;
  /** §03 2·1 ⑤ — *"the id every payment carries"*, where one exists. */
  batch: (row: PaymentRow) => JSX.Element;
}

/**
 * The Reverse row action, as the table takes it (CR-059 CS-5, task 16).
 *
 * ⚠ **`reasonFor` RETURNING A SENTENCE DOES NOT HIDE THE CONTROL — IT DISABLES
 * IT AND SHOWS THE SENTENCE** (BR-SHL-025, and the backend lane asked for it by
 * name). `reverse_payment` is `@require_role(SYSTEM_ADMIN)` since 2026-09-01
 * (`BR-PAY-1070`), so **the Billing Clerk who takes the 292.87 cheque at the
 * counter cannot record its return** — that asymmetry is the rule as ruled, and
 * a clerk who cannot see the control has no way to learn it. The four disabled
 * bulk actions on S34 Outstandings are the precedent, in this same feature.
 */
export interface PaymentsReverseAffordance {
  /** `null` = allowed. Anything else disables the icon and becomes its tooltip. */
  reasonFor: (row: PaymentRow) => string | null;
  onReverse: (row: PaymentRow) => void;
}

/**
 * CR-059 CS-34 (task 42) — the second row action, and it has **no `reasonFor`**.
 *
 * That absence is the design and not an omission. Every refusal this door makes
 * is one the SCREEN CANNOT SEE:
 *
 *   · the tender is refused once the payment is in a deposit batch, and
 *     `PaymentRow.deposit_batch_id` is documented on its own type as *always
 *     null — nothing writes the column*. A client-side guard built on it would
 *     be a guess dressed as a rule, and it would guess wrong in the direction
 *     that matters: it would OFFER the field on a banked payment.
 *   · the money fields are refused by name, and this form never sends them.
 *   · the role is not gated at all — the route takes `AnyTenantRole`, *"the
 *     clerk who records a payment"* — so there is no role reason to compute.
 *
 * So the control is offered on every row and the SERVER's refusal is what the
 * clerk reads (BR-SHL-025: server-side enforcement is THE enforcement). The
 * `Reverse` action beside it computes a reason precisely because each of its
 * branches mirrors a refusal this row's own fields CAN answer.
 */
export interface PaymentsCorrectAffordance {
  onCorrect: (row: PaymentRow) => void;
}

/**
 * `CR-135` `P1.6` — the third and fourth row actions, and they have **no
 * `reasonFor` either**, for `PaymentsCorrectAffordance`'s reason exactly.
 *
 * Every refusal a move or a reapply makes is one this screen cannot see:
 * BR-PAY-867 refuses a move while the deposit batch is RECONCILED, and whether
 * a batch is reconciled is not on the payment row; the reapply service refuses
 * a target set that does not sum to the payment. Both arrive as a 422 the form
 * renders as a sentence. Guessing here would produce a tooltip that disagrees
 * with the server, which is worse than no tooltip (`DEF-PAY-5128`'s shape).
 *
 * ⚠ **A REVERSAL CANNOT BE MOVED OR REAPPLIED AND THAT ONE *IS* ON THE ROW**,
 * so it is the one refusal stated here — the same test `reverseBlockedReason`
 * already makes, on the same two facts.
 */
export interface PaymentsMoveAffordance {
  onMove: (row: PaymentRow) => void;
}

/**
 * The ONE refusal a move or a reapply makes that IS readable off the row: a
 * reversing row is not a payment, so there is nothing to re-point.
 *
 * ⚠ **IT DELIBERATELY DOES NOT REPEAT `reverseBlockedReason`'s OTHER TWO.**
 * The admin gate is the REVERSAL's (`BR-PAY-1070`), and `processing` blocks a
 * bounce because the money has not arrived — neither is a rule about moving a
 * payment between accounts or between bills, and asserting one here would be
 * this screen inventing a refusal the service does not make.
 */
export function correctionBlockedReason(row: PaymentRow, t: Translator): string | null {
  if (row.status === "reversed" || row.amount.trim().startsWith("-")) {
    return t("payments.reverse.isReversal");
  }
  return null;
}

export interface PaymentsReapplyAffordance {
  onReapply: (row: PaymentRow) => void;
}

/**
 * CR-059 CS-41 (the bulk toolbar) — **the tick rides in the IDENTITY cell, and
 * this is not a layout preference.**
 *
 * A new `select` COLUMN would be invisible to every clerk who has ever saved a
 * column set. `columnsFromPreference` filters the stored key list against the
 * config and DataTable filters it again on render, so a key that was not in the
 * saved list is simply not shown — and a column that did not exist when the
 * preference was written can never be in it. The checkbox column, and therefore
 * the whole feature, would be MISSING for exactly the users who customise their
 * list, silently, with `tsc` and every assertion green. That is hard-won law 2's
 * shape reached by a different road.
 *
 * `BR-SHL-013` guarantees the identity column can never be hidden, whatever was
 * stored — DataTable re-inserts it on every render — so the tick beside the
 * payment number is the one place on this table that cannot be preferenced away.
 * It also costs no new column key, no stylesheet class (G31 is AT its 470
 * ceiling) and no second place for a row's identity to live.
 */
export interface PaymentsSelectAffordance {
  isSelected: (row: PaymentRow) => boolean;
  onToggle: (row: PaymentRow) => void;
}

/** CR-059 CS-39 — what one row opens into. Absent = the capability does not
 *  exist on this list, exactly as BR-SHL-010 requires: no expander column, no
 *  per-row disclosure and no Expand all. */
export interface PaymentsTableExtras {
  select?: PaymentsSelectAffordance;
  /**
   * The shared table's expandable-row capability (`BR-SHL-010`: a capability
   * not declared is not rendered).
   *
   * ⚠ **NO PAYMENTS CALLER PASSES IT SINCE `P3.10` (2026-09-23)**, so the
   * payments table draws no expander column at all — the 👁 row action opens
   * screen 2·2 at its own address instead. It is KEPT on this type rather than
   * deleted because it is the shared kit's prop and this config is built by
   * three callers; removing it here would be a change to `TableConfig`'s
   * surface dressed as a payments clean-up.
   */
  renderExpanded?: (row: PaymentRow) => ReactNode;
  /** `CR-135` `P1.6` — the doors onto 2·3f and 2·3g. They ride in `extras`
   *  rather than as a fifth and sixth positional argument because two callers
   *  build this config for `parseTableParams` alone and pass none of them. */
  move?: PaymentsMoveAffordance;
  reapply?: PaymentsReapplyAffordance;
  /**
   * ⚠ **`"account"` HIDES THE `Account` AND `Customer` COLUMNS, AND THAT IS THE
   * DRAWING (B14 rule 41, ACC-T03).** The blueprint draws eight columns on the
   * account's own Payments tab — Payment # · Posted · Type · Method · Reference
   * · Applied to · Amount · Status — and neither of those two is among them: the
   * account is the page a clerk is standing on and its number is in the header
   * three lines above, so the columns repeat a fact the screen already states
   * and cost the width the drawn eight need.
   *
   * They are HIDDEN BY DEFAULT rather than removed, so the column chooser can
   * still put them back. S33 — the utility-wide list, where the account is the
   * one thing that tells two rows apart — passes nothing and is unchanged.
   */
  scope?: "all" | "account";
}

/**
 * Why this row cannot be reversed, or `null`.
 *
 * PURE, so every branch is provable without a browser — and every branch mirrors
 * a refusal the SERVICE already makes, rather than inventing one:
 *
 *   · the role — `BR-PAY-1070`, Admin-only, gated in the service AND on the
 *     route. A null role (the permissions read has not answered) offers the
 *     control, because the server is the boundary either way.
 *   · `processing` — `US-PAY-009` TC-5: *"NSF is a clearing failure
 *     (BR-PAY-021); processing payments cancel instead"*. Money that never
 *     arrived has nothing to come back.
 *   · a reversing row — reversing a reversal would re-apply money the bank has
 *     taken. A customer who pays again after a bounce makes a NEW payment
 *     (`BR-PAY-036`).
 *
 * ⚠ **IT DOES NOT ASK WHETHER THIS PAYMENT WAS ALREADY REVERSED, AND IT CANNOT.**
 * The original keeps its `cleared` status — only the reversing row is marked —
 * and `PaymentRow` carries no link to one. So the screen does not guess: a
 * second Reverse answers **200 with the FIRST reversal** and `created: false`,
 * and the result panel says so. Guessing here would either hide a control that
 * works or promise one that does not.
 *
 * The sign test reads the DECIMAL STRING and never parses it — a `Number()` on
 * money is the float CLAUDE.md rule 2 keeps out, in the place it is most
 * tempting.
 */
export function reverseBlockedReason(
  row: PaymentRow,
  role: string | null,
  t: Translator,
): string | null {
  if (role !== null && role !== ROLE_SYSTEM_ADMIN) {
    return t("payments.reverse.adminOnly");
  }
  if (row.status === "processing") {
    return t("payments.reverse.notCleared");
  }
  if (row.status === "reversed" || row.amount.trim().startsWith("-")) {
    return t("payments.reverse.isReversal");
  }
  return null;
}

/**
 * The US-PAY-004 capability row, as the shared table framework reads it
 * (BR-SHL-010: a capability not declared here is not rendered).
 *
 * Column keys are the SERVER's sort names where a column is sortable, so the
 * request stays the contract's (`PAYMENT_SORTS`). The default set is the
 * prototype's own eight (Date · Account · Type · Method · Confirmation ·
 * Applied to · Amount · Status) minus its leading checkbox, which selects rows
 * for bulk actions that do not exist; the five IS-5 "available" extras follow.
 *
 * ⚠ **`reverse` IS OPTIONAL AND THE OMISSION IS NOT A DEAD PROP (law 2).** Two
 * callers build this config for `parseTableParams`/`serializeTableParams` only —
 * those read column KEYS and never render a cell — and the ONE caller that
 * renders rows (`PaymentsTable`, which serves BOTH S33 and the account's
 * Payments tab) always passes it. So the actions column exists wherever a row
 * is drawn and nowhere else, and the S21 tab gets the Reverse action from the
 * same line of code as S33 rather than from a second implementation.
 */
export function paymentsTableConfig(
  t: Translator,
  cells: PaymentsCells,
  reverse?: PaymentsReverseAffordance,
  correct?: PaymentsCorrectAffordance,
  extras: PaymentsTableExtras = {},
): TableConfig<PaymentRow> {
  const select = extras.select;
  return {
    screenId: "S33",
    // ⚠⚠ **THE FILTERS ARE DECLARED HERE, AND UNTIL 2026-09-23 THEY WERE NOT
    // — WHICH MADE EVERY FILTER ON THIS LIST DECORATIVE (`DEF-PAY-6293`).**
    // The PAGE stores all table state in the URL through
    // `serializeTableParams(next, config)` using THIS config, and
    // `PaymentsTable` builds a SECOND one (`{ ...baseConfig, filters:
    // paymentsFilters(…) }`) that only the `FilterBar` and `DataTable` see.
    // `serializeTableParams` writes `f.<name>` **only for filters its config
    // declares**, and `parseTableParams` restores only those — so a value the
    // bar set was dropped on the way out, ignored on the way back in, and the
    // controlled checkbox snapped straight back to unticked.
    //
    // **Measured in a browser:** *Source → Post* left the address at
    // `?sort=posted_at&dir=desc` and the pager at `1–50 of 146`; *Status →
    // Reversed* and *Type → Credit* did the same. The server was never at
    // fault — 146 payments, 72 `origin=import`, 74 `origin=entry`.
    //
    // ⚠ **THE OPTION LISTS HERE ARE EMPTY ON PURPOSE AND THAT IS NOT A
    // WEAKENING.** Only the NAMES travel: `filterParamNames` is what
    // serialize and parse walk, and neither validates a value against an
    // option list. The OPTIONS are the run-time vocabulary — the tenant's
    // live payment methods and the batches on the page — which only
    // `PaymentsTable` can know, and its spread still overrides this whole
    // key. So the bar renders from the enriched copy exactly as before and
    // the address bar finally round-trips.
    filters: paymentsFilters(t, [], "YYYY-MM-DD", []),
    columns: [
      // BR-SHL-013: the identity column can never be hidden. The PMT- number is
      // minted at record (BR-TEN-035) and the column is nullable in the schema,
      // so the cell still renders a stated absence rather than a blank.
      //
      // CR-059 CS-41: when this table can select, the tick rides HERE — see
      // `PaymentsSelectAffordance` for why a new column would ship invisible.
      // The checkbox is named by the payment NUMBER and never by its id
      // (B14 rule 31), and the number renders through the SAME cell either way,
      // so a selecting table and a plain one cannot draw identity differently.
      {
        key: "payment_no",
        label: t("payments.col.paymentNo"),
        identity: true,
        cell:
          select === undefined
            ? cells.paymentNo
            : (row: PaymentRow) => (
                <span>
                  <input
                    type="checkbox"
                    aria-label={t("payments.bulk.selectRow", {
                      number: row.payment_no ?? t("payments.row.noNumber"),
                    })}
                    checked={select.isSelected(row)}
                    onChange={() => select.onToggle(row)}
                  />{" "}
                  {cells.paymentNo(row)}
                </span>
              ),
      },
      // §03 2·1 ④ and ⑤, in the drawn order: SOURCE and BATCH sit between the
      // payment number and Posted, and both are marked NEW on the page.
      //
      // ⚠ `DEF-PAY-9105` — OFF the account's own tab by default, like Account and
      // Customer below. §03 2·1 is the UTILITY-WIDE list; the account's Payments
      // tab (`ACC-T03`) draws its own eight and neither of these. They stay in
      // the column chooser there, so the fact is one click away, not gone.
      {
        key: "source",
        label: t("payments.col.source"),
        defaultVisible: extras.scope !== "account",
        cell: cells.source,
      },
      {
        key: "batch",
        label: t("payments.col.batch"),
        defaultVisible: extras.scope !== "account",
        cell: cells.batch,
      },
      {
        key: "posted_at",
        label: t("payments.col.postedAt"),
        sortable: true,
        cell: cells.postedAt,
      },
      {
        key: "account",
        label: t("payments.col.account"),
        sortable: true,
        defaultVisible: extras.scope !== "account",
        cell: cells.account,
      },
      {
        key: "customer",
        label: t("payments.col.customer"),
        defaultVisible: extras.scope !== "account",
        cell: cells.customer,
      },
      { key: "type", label: t("payments.col.type"), cell: cells.type },
      { key: "method", label: t("payments.col.method"), cell: cells.method },
      { key: "confirmation", label: t("payments.col.confirmation"), cell: cells.confirmation },
      { key: "applied_to", label: t("payments.col.appliedTo"), cell: cells.appliedTo },
      {
        key: "amount",
        label: t("payments.col.amount"),
        sortable: true,
        numeric: true,
        cell: cells.amount,
      },
      { key: "status", label: t("payments.col.status"), sortable: true, cell: cells.status },
      // The IS-5 "available" set. `cleared_at` is sortable because the server
      // sorts on it (BR-PAY-021 makes both dates first-class), and the other
      // four are display-only.
      {
        key: "cleared_at",
        label: t("payments.col.clearedAt"),
        sortable: true,
        defaultVisible: false,
        cell: cells.clearedAt,
      },
      {
        key: "purpose",
        label: t("payments.col.purpose"),
        defaultVisible: false,
        cell: cells.purpose,
      },
      // ⚠ **THE `deposit_batch_id` COLUMN IS GONE AND `batch` ABOVE IS WHAT
      // REPLACED IT (`CR-135` `P1.9`, and it closes `DEF-2353`'s screen half).**
      // It was hidden by default and its cell stated *"this list does not carry
      // the batch"* — true when it was written, and false the moment the read
      // began serving `batch_ref`. Two columns for one fact, one of them saying
      // the fact is unavailable, is how a screen comes to contradict itself.
      // CS-44 asked for the batch's CODE here and `batch` is that code.
      {
        key: "receipt_no",
        label: t("payments.col.receiptNo"),
        defaultVisible: false,
        cell: cells.receiptNo,
      },
      // CR-059 CS-5 (task 16) and CS-34 (task 42) — the TWO row actions this
      // screen has. B14 rule 15: an ICON with an accessible name, never a text
      // link (G37 holds it).
      //
      // The prototype draws five here (View · Reverse · Reapply · Send receipt ·
      // Refund) and these are the ones with a route: `/reallocate` is CS-11
      // and unbuilt, BR-PAY-024's receipt queue is US-PAY-025's and unbuilt,
      // the refund is raised from the ACCOUNT (S58, task 18) because the PO
      // ruled a refund belongs to the account, and there deliberately is no
      // `GET /payments/{id}` for a View to open.
      //
      // ⚠ **THE COLUMN EXISTS IF EITHER AFFORDANCE IS PASSED, AND BOTH ARE
      // OPTIONAL FOR THE REASON THE SECTION HEADER ALREADY GIVES (law 2).** Two
      // callers build this config for `parseTableParams`/`serializeTableParams`
      // only and render no cell; the one caller that renders rows passes both.
      ...(reverse === undefined &&
      correct === undefined &&
      extras.move === undefined &&
      extras.reapply === undefined
        ? []
        : [
            {
              key: "actions",
              label: t("payments.col.actions"),
              /**
               * ⛔ **`DEF-PAY-6214` — THIS CELL DREW FOUR VISIBLE GLYPHS AND
               * TWO OF THEM WERE OFF THE SCREEN.**
               *
               * Measured in Chromium on `brazosbend`, 2026-09-22, at the
               * drawing's own 1440: the table is **1,214px inside a 1,120px
               * scroller**, and the four buttons end at 1374, 1410, **1446 and
               * 1482** — so `Move` and `Reverse` sat 6px and 42px PAST the
               * right edge of the window, reachable only by scrolling the
               * table sideways. At 1280 the scroller is 960 and it is worse.
               *
               * **B14 rule 15 has said the answer since it was ratified:**
               * *"Max 2 visible + `…` overflow."* `G37` counts the
               * `<RowAction`s in this cell into a variable and never compares
               * it to that cap, which is why four of them passed every check
               * (hard-won law 7 — a counter nothing asserts on).
               *
               * **And the blueprint puts these two in the overflow by name.**
               * §03 frames 2·3f and 2·3g both give their door as *"The row
               * overflow on 2·1, and 2·2. 2 doors — there are none today"*,
               * and 2·1 draws the ACTIONS column as two glyphs and a `…`.
               *
               * So: `✎ Correct reference` and `↺ Reverse` stay on the row —
               * the everyday clerical fix and the money act, which is the pair
               * a clerk scans for — and Move and Reapply move into the `…`,
               * where the drawing already had them. **No capability leaves**
               * (`DEF-PAY-6199`'s check): both are still one press away and
               * both keep their reason when they cannot act.
               */
              cell: (row: PaymentRow) => (
                <RowActions>
                  {/* ⚠ **👁 DETAIL — `CR-137-BRC07` `P3.10`, AND IT IS THE HALF
                      OF THE SWAP THAT ARRIVES.** p036's own note on the row
                      panel this replaces: *"It has no address, so it cannot be
                      linked, bookmarked or returned to after a refresh —
                      **which is also why the row actions have no View icon**."*
                      The address exists now, so the icon does.

                      A LINK and not a button: an address a clerk can
                      middle-click, open in a new tab and paste into a message
                      is the whole point of `P3.9`, and an `onClick` that calls
                      `navigate` loses all three.

                      The `PMT-` NUMBER is what the address carries (B14 rule
                      31 — an address bar is the most visible field a screen
                      has); the uuid is the fallback for a row whose number
                      billing could not resolve, and the server takes either. */}
                  <RowActionLink
                    label={t("payments.detail.view")}
                    icon={<EyeIcon />}
                    to={cells.detailTo(row)}
                  />
                  {correct !== undefined && (
                    <RowAction
                      label={t("payments.correct.action")}
                      icon={<PencilIcon />}
                      onClick={() => correct.onCorrect(row)}
                    />
                  )}
                  {/* ⚠ **REVERSE MOVED INTO THE `…` IN THE SAME COMMIT, AND THE
                      DRAWING SAYS TO.** p030 ⑥, verbatim: *"👁 Detail · ✎ Edit,
                      then `…` for Receipt and Cancel · **B14 15 caps visible
                      icons at TWO**"*. Adding the eye beside `✎` and `↺` would
                      have made THREE visible — a NEW rule 15 breach introduced
                      by the fix for something else — and `G37` counts these
                      into a variable it never compares to the cap, so nothing
                      would have said so (hard-won law 7: a counter nothing
                      asserts on). **No capability leaves**: Reverse is one
                      press away and keeps its reason when it cannot act. */}
                  {(reverse !== undefined ||
                    extras.reapply !== undefined ||
                    extras.move !== undefined) && (
                    <RowActionsMore label={t("table.rowActions.more")}>
                      {reverse !== undefined && (
                        <RowMenuAction
                          label={t("payments.reverse.action")}
                          icon={<RollBackIcon />}
                          reason={reverse.reasonFor(row)}
                          danger
                          onClick={() => reverse.onReverse(row)}
                        />
                      )}
                      {/* `CR-135` `P1.6` — 2·3g. `TagIcon` because a reapply
                          NAMES which bill the money meets; `icons.tsx`'s verb
                          table carries the choice, so the next lane does not
                          pick a different glyph for the same verb. The glyph
                          is KEPT inside the menu on purpose — rule 15's own
                          note: *"a clerk who learns `⇄` on one table
                          recognises it on the next"*. */}
                      {extras.reapply !== undefined && (
                        <RowMenuAction
                          label={t("payments.reapply.action")}
                          icon={<TagIcon />}
                          reason={correctionBlockedReason(row, t)}
                          onClick={() => extras.reapply?.onReapply(row)}
                        />
                      )}
                      {/* `CR-135` `P1.6` — 2·3f. `SwapIcon` is the verb table's
                          re-point glyph. NOT danger tier here: B14 rule 6 puts
                          the danger tier on the COMMIT, and the commit is the
                          modal's footer button, where `submitVariant="danger"`
                          puts it. */}
                      {extras.move !== undefined && (
                        <RowMenuAction
                          label={t("payments.move.action")}
                          icon={<SwapIcon />}
                          reason={correctionBlockedReason(row, t)}
                          onClick={() => extras.move?.onMove(row)}
                        />
                      )}
                    </RowActionsMore>
                  )}
                </RowActions>
              ),
            },
          ]),
    ],
    getRowId: (row) => row.id,
    // IS-3 / the capability row: account #, customer, confirmation #, address —
    // the SERVER searches all four, because the list is paginated in the
    // database.
    // VERIFIED AGAINST THE PREDICATE 2026-09-09 (`CR-089` wave K, `PUJ-52`):
    // `payments/selectors.py::_apply_search` ORs `account__account_no |
    // confirmation` with `_account_ids_by_customer_name` AND with
    // `_account_ids_at_address`, which walks *payment → account → property*
    // through customers' published read. All four, no more.
    // ⚠ **`address` IS METERING'S OWN MATCH AND IS WIDER THAN THE WORD** — the
    // predicate the Properties screen searches with, so the town, the property
    // number and the owner reach it too.
    searchFields: ["account_no", "customer_name", "confirmation", "address"],
    // ⚠ **B14 rule 19, AND THE COPY SAYS `reference`, NOT `confirmation`.**
    // The stored column is `confirmation`; the column header a clerk reads on
    // this very table is `payments.col.confirmation` → **"Reference"**. A prompt
    // naming a field name the screen never shows is only marginally better than
    // "Search this list", so the prompt uses the word on the header. (DEF-510's
    // register row has no r10 sentence for S33 — r10 line 8188 is a WIZARD
    // PICKER, not this toolbar, and copying it would be inventing law.)
    searchPlaceholder: "payments.list.searchPlaceholder",
    // IS-2 / the capability row: posting date desc. The newest payment is the
    // one a clerk is looking at, and the SERVER applies it.
    defaultSort: { sort: "posted_at", dir: "desc" },
    // CR-059 CS-39 — *"a clerk clicks PMT-2608-000412 and lands on a page for
    // that payment showing what it paid, bill by bill"*. There is no
    // `GET /payments/{id}` and no detail route, so the row opens where it sits
    // through the shared table's own expandable-row capability. Absent on the
    // two callers that build this config only to parse and serialize params:
    // BR-SHL-010, a capability not declared here is not rendered, and those two
    // draw no expander column at all.
    renderExpanded: extras.renderExpanded,
  };
}

/**
 * The capability row's declared filters (BR-SHL-011's `f.<name>=` grammar).
 *
 * The METHOD options are the tenant's LIVE list, served on the same response as
 * the rows (BR-PAY-026 / BR-REP-006) — a hardcoded set here would go stale the
 * first time a tenant added "Bill-pay portal", and the Record form reads the
 * same list so the two can never disagree.
 *
 * ⚠ **THIS DOCSTRING SAID THE DATE RANGES WERE *"deliberately NOT rendered"*
 * UNTIL 2026-09-03, AND THAT SENTENCE OUTLIVED ITS REASON (`DEF-3504`, hard-won
 * law 1).** It was true and it was well argued: *"the shared FilterBar renders
 * option lists only, and an empty select where a date range belongs narrows
 * nothing while looking as though it had"*. The Product Owner then walked all
 * four Record payments tabs and said *"I cannot filter payment by date"*, and
 * the reason had already stopped being about payments at all — the server
 * accepts all four date params and `PAYMENT_FILTERS` has always declared them.
 * The gap was one missing kind on a SHARED type, and a sibling lane widened
 * `TableFilterConfig` to carry a `dateRange` descriptor.
 *
 * **So the ranges are declared here now, and they are two entries.** A range is
 * ONE control and ONE chip to a clerk and TWO `f.<name>` params on the wire —
 * `f.posted_from` and `f.posted_to`, the names `apps/payments/selectors.py`
 * already matches — so nothing moves on the API and `paymentsParamsFrom` spreads
 * them straight through with everything else. The count and the total narrow
 * with the rows because all three come off the same filtered response, and the
 * range survives a refresh through the request state's existing round trip
 * rather than a second mechanism.
 *
 * ⚠ **`dateFormat` IS A PARAMETER FOR THE SAME REASON `dateRangeFilter` DEMANDS
 * IT.** IS-8 renders a date in the TENANT's regional format and the native date
 * input renders in the BROWSER's, so the chip is the only place a tenant sees
 * theirs. Requiring it means this screen cannot declare a range and forget it.
 */
export function paymentsFilters(
  t: Translator,
  methods: readonly PaymentMethodOption[],
  dateFormat: RegionalDateFormat,
  /** The rows this page is showing, for §03 2·1 ③'s BATCH filter.
   *
   *  ⚠ **THE OPTIONS ARE THE BATCHES ON SCREEN, AND THAT IS A DELIBERATE SCOPE
   *  RATHER THAN A SHORTCUT.** The honest alternatives were a served list of
   *  every batch the tenant has ever cut — unbounded, which `NFR-5` forbids
   *  outright and `NFR-3` would make a second paged read — or a typed box,
   *  which `TableFilterConfig` cannot express and which asks a clerk to
   *  remember a code. A clerk reaching for this filter is LOOKING at the row;
   *  the batches on the page are exactly the ones they can name.
   *
   *  ⚠ **AND THE CHIP STILL RENDERS FOR A VALUE THAT IS NOT ON THE PAGE.**
   *  `FilterBar` falls back to the raw value when no option matches it
   *  (`filter.options.find(…)?.label ?? value`), and its `active` set is
   *  computed from the DECLARED filters rather than the offerable ones — so a
   *  batch filter carried in a bookmarked URL shows its chip and is removable
   *  even on a page where no row belongs to it. */
  rows: readonly PaymentRow[] = [],
) {
  // Deduped and sorted so the offer menu is stable between renders; a `Set`
  // keyed on the CODE, because two rows in one batch are one option.
  const batches = Array.from(
    new Set(rows.map((row) => row.batch_ref).filter((ref): ref is string => ref !== null)),
  ).sort();
  return [
    {
      name: "status",
      label: t("payments.filter.status"),
      // CR-186-BRC10 (PO 2026-10-21): every payment is `posted` at entry and
      // `cleared` at bank reconciliation, so those two lead, in lifecycle
      // order. `cancelled` was missing from this list since `payments/0036`
      // and is offered now. `processing` stays — rows already holding it keep it.
      options: PAYMENT_STATUS_FILTER_ORDER.map((code) => ({
        value: code,
        label: t(`payments.status.${code}`),
      })),
    },
    {
      name: "type",
      label: t("payments.filter.type"),
      options: (["payment", "credit", "adjustment"] as const).map((code) => ({
        value: code,
        label: t(`payments.type.${code}`),
      })),
    },
    {
      name: "method",
      label: t("payments.filter.method"),
      options: methodOptions(methods),
    },
    // §03 2·1 ② the SOURCE filter — *"`Digital | Counter | Post` · B14 12
    // removable chip"*. The VALUES are what `payments.origin` stores; the
    // labels are the catalogue's, the same split `method` already makes.
    // Hardcoded here rather than served, and that is not the `method` case:
    // the three are a CHECK constraint a tenant cannot extend, so a list off
    // the wire would be a round trip to learn a constant.
    {
      name: "origin",
      label: t("payments.filter.source"),
      options: PAYMENT_ORIGINS.map((code) => ({
        value: code,
        label: t(`payments.source.${code}`),
      })),
    },
    // §03 2·1 ③ the BATCH filter — *"one batch at a time"*, and the frame's own
    // badge reads **GAINS 2 COLUMNS · 2 FILTERS · 1 BUTTON**. ⛔ `DEF-PAY-6227`:
    // the Source filter landed with the columns and this second one did not,
    // found by the `P2.7` lane checking this frame against the drawing.
    //
    // Drawn as the chip `Batch: CTR-260921-DW ×`, which is an ILLUSTRATION
    // (B14 rule 37) — the value is the code the product mints, a deposit
    // batch's `DEP-` code or an import run's number, never either table's uuid.
    //
    // ⚠ **THE VALUE IS THE LABEL HERE, AND THAT IS NOT A SHORTCUT.** Every
    // other filter on this screen sends a stored CODE and shows a catalogue
    // word; a batch's code IS the human-facing reference — B14 rule 31's own
    // *"where the reference is genuinely what a user needs — a batch number …
    // it has a HUMAN-FACING number and that is what is shown"* — so a second
    // spelling would be a second thing to keep in step.
    {
      name: "batch",
      label: t("payments.col.batch"),
      options: batches.map((code) => ({ value: code, label: code })),
    },
    {
      name: "purpose",
      label: t("payments.filter.purpose"),
      options: (["bill", "deposit", "plan_down", "prepay"] as const).map((code) => ({
        value: code,
        label: t(`payments.purpose.${code}`),
      })),
    },
    // CR-059 CS-40 (DEF-3504). BR-PAY-021's pair, both offered, because the two
    // dates answer different questions: the POSTING date is what billing
    // consumes and what a month-end close is cut on, and the CLEARING date is
    // what the bank matched. A clerk reconciling August needs whichever of the
    // two their question is about, and the server has always accepted both.
    dateRangeFilter({
      name: "posted",
      label: t("payments.filter.posted"),
      from: "posted_from",
      to: "posted_to",
      dateFormat,
    }),
    dateRangeFilter({
      name: "cleared",
      label: t("payments.filter.cleared"),
      from: "cleared_from",
      to: "cleared_to",
      dateFormat,
    }),
  ];
}

/**
 * The one sentence the table shows when the request failed (BR-SHL-020).
 *
 * Pure and exported so the distinction is PROVABLE without a browser: a 404
 * from a COLLECTION route means this API serves no payments list, and anything
 * else is the server's own `message_key` through the catalog. Both routes are
 * served today; this stays derived rather than deleted, because the day someone
 * drops the `config/urls.py` include the screen must say so rather than render
 * an empty ledger that reads as "no payments were ever taken".
 */
export function paymentsFailureReason(error: unknown, t: Translator): string {
  return listRouteAbsent(error) ? t("payments.list.failed.noEndpoint") : apiErrorText(error, t);
}

/** The request state → the wrapper's params. One translation, one place. */
export function paymentsParamsFrom(
  state: TableRequestState,
  extraFilters: Record<string, string> = {},
) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: { ...state.filters, ...extraFilters },
  };
}

// ⚠ **`isoToday()` LIVED HERE AND IT RETURNED THE UTC DAY. IT IS DELETED
// (`P0.7` of the payments blueprint, PO ruling 2026-09-22).**
//
// It read `new Date().toISOString().slice(0, 10)` — the calendar date in UTC,
// not in the utility's own timezone — and it pre-filled `posted_at` on the
// Record form, the Adjust form and two more on the account screen. **A shift
// that ends after 17:00 in UTC−7 stamps its payments into tomorrow**, which
// is the worked case the blueprint puts on this row, and the counter (phase 2)
// makes it routine rather than occasional: a till IS a shift.
//
// **The replacement is the kit's own `todayInZone(timeZone)`** and not a
// second helper — B14 rule 43, and `DEF-MET-4991` already wrote exactly this
// function for the three asset date fields that proposed no date at all. Two
// functions answering *what day is it here* is how two screens come to
// disagree about a utility's business day. The zone is the one `useRegional`
// already resolves on every one of these screens (`IS-8`, Settings → Company
// → Regional), which is the same source `DateCell` displays an instant in — so
// the day a clerk is offered and the day they then read back cannot differ.
//
// ⚠ **GOING FORWARD ONLY — PO ruling 2026-09-22, verbatim: *"Going forward
// only"*.** Nothing already recorded moves, and no backfill exists or may be
// written: `payments.posted_at` is frozen by CLAUDE.md hard rule 4 and is NOT
// one of the three columns `payments/0014` lets a correction touch, so
// restamping a past payment's day would be a new row and never an edit.
//
// ⚠ **`billingOpsShared.todayIso()` IS THE SAME BUG ONE MODULE OVER** and is
// deliberately NOT touched here: it is another lane's file and its callers
// stamp a write rather than propose a bound. Reported, not fixed.

// ── The cells ──────────────────────────────────────────────────────────────

/**
 * Every cell in one place. Each honesty rule the module docstring names is one
 * cell here, and each is asserted by a test.
 */
export function paymentsCells(
  t: Translator,
  tenantPath: (path: string) => string,
  timeZone: string,
  dateFormat: RegionalDateFormat,
): PaymentsCells {
  return {
    detailTo: (row) => tenantPath(paymentDetailRoute(row.payment_no ?? row.id)),
    // BR-TEN-035 mints the number at record, so a served null is an older row
    // or a partial response — never "this payment has no number".
    //
    // ⚠ **IT IS A LINK SINCE `CR-137-BRC07` `P3.9`, AND THIS COMMENT USED TO
    // SAY WHY IT COULD NOT BE.** It read *"There is no payment DETAIL route to
    // link to (none is contracted), so this is text"*, and `paymentDetail.tsx`
    // carried the matching promise — *"it becomes an `InlineLinkAnchor` the day
    // the route exists"*. The route exists. **A promise in a comment that
    // outlives its condition is hard-won law 1**, so it is cashed in the same
    // commit that makes it true rather than left for a later lane to find.
    paymentNo: (row) =>
      row.payment_no !== null ? (
        <InlineLinkAnchor href={tenantPath(paymentDetailRoute(row.payment_no))}>
          {row.payment_no}
        </InlineLinkAnchor>
      ) : (
        <Dash>{t("payments.row.noNumber")}</Dash>
      ),
    // BR-PAY-021: the date BILLING consumes. Never derived, never a clock.
    postedAt: (row) => (
      <DateCell value={row.posted_at} timeZone={timeZone} dateFormat={dateFormat} />
    ),
    // …and the date the BANK matches on. A null is `processing` — the money has
    // not arrived — which is a STATE and not a missing value, so it says so
    // rather than rendering the same "—" a genuinely absent field would.
    clearedAt: (row) =>
      row.cleared_at !== null ? (
        <DateCell value={row.cleared_at} timeZone={timeZone} dateFormat={dateFormat} />
      ) : (
        <Dash>{t("payments.row.notCleared")}</Dash>
      ),
    account: (row) => (
      <InlineLinkAnchor href={tenantPath(accountDetailPath(row.account_id))}>
        {row.account_no ?? t("payments.row.noAccountNo")}
      </InlineLinkAnchor>
    ),
    // Customers' primary CONTACT (BR-CUS-054's entity is unbuilt). A null means
    // no contact was recorded — the server REFUSES rather than nulling when it
    // could not read one, so this branch is never "we did not look".
    customer: (row) =>
      row.customer_name !== null ? (
        <span>{row.customer_name}</span>
      ) : (
        <Dash>{t("payments.row.noCustomer")}</Dash>
      ),
    type: (row) => <span>{paymentTypeLabel(row.type, t)}</span>,
    // BR-PAY-026: the tenant lookup's NAME, never its code. A row with no
    // instrument (a credit, an adjustment) carries none, and B2 leaves the
    // column nullable for exactly that.
    method: (row) =>
      row.method_name !== null ? (
        <span>{row.method_name}</span>
      ) : (
        <Dash>{t("payments.row.noMethod")}</Dash>
      ),
    confirmation: (row) => (
      <>
        {row.confirmation !== null && row.confirmation !== "" ? (
          <span className="pay-id">{row.confirmation}</span>
        ) : (
          <Dash />
        )}
        {/* LBX-04 — a reversing row carries the bank's words. */}
        {row.bank_memo ? (
          <div className="pay-form-note" data-bank-memo="">
            {t("payments.reverse.bankMemoLine", { memo: row.bank_memo })}
          </div>
        ) : null}
      </>
    ),
    // The prototype's "Applied to" cell. EVERY bill the payment met — showing
    // the first would understate what the money did — and an empty list is a
    // stated fact: a processing payment has met nothing yet, and a carried
    // credit met no bill by instruction (BR-PAY-010).
    //
    // ⛔ **CR-059 CS-36 · task 20 — THIS LISTED A CORRECTED BILL TWICE AND SAID
    // NOTHING (2026-09-02).** It mapped `applied_to` raw, and a release writes
    // an append-only NEGATIVE mirror row against the same bill (BR-PAY-1072),
    // so Ajinkya's 100.00 showed `2608-0141` and `2608-0141` — the same key
    // twice, in React and to a person — with the money looking as though it had
    // gone somewhere twice. The figures were right; there was no word for what
    // happened. Now: one line per BILL, netted, and a line that lost money says
    // WHY it lost it. See `paymentsShared`'s section header for why the sign of
    // the payment is what tells a correction from a bounce.
    appliedTo: (row) => {
      const bills = appliedBills(row);
      if (bills.length === 0) {
        return <Dash>{t("payments.row.appliedToNone")}</Dash>;
      }
      const corrected = releasedByCorrection(row);
      return (
        <span className="pay-applied">
          {bills.map((bill) => (
            <span className="pay-applied-item" key={bill.invoiceId}>
              {bill.invoiceNumber === null ? (
                t("payments.row.billNumberUnavailable")
              ) : (
                <InlineLinkAnchor href={tenantPath(billDetailPath(bill.invoiceId))}>
                  {bill.invoiceNumber}
                </InlineLinkAnchor>
              )}
              {bill.releasedBack !== null && (
                <span className="pay-sub">
                  {corrected
                    ? t("payments.row.releasedByCorrection")
                    : t("payments.row.releasedByReversal")}
                </span>
              )}
            </span>
          ))}
        </span>
      );
    },
    // CLAUDE.md #2: the decimal STRING and its CHAR(3) code travel together from
    // the database to the pixel; nothing here parses, sums or rounds one.
    //
    // ⛔ **CR-059 CS-38 · task 25 — A CONCESSION READ AS MONEY RECEIVED.** The
    // spec's words are *"a signed credit row, described as a concession and not
    // as money received"*, and this cell printed `$25.00` for a goodwill credit
    // exactly as it prints `$25.00` for a customer's cheque. On the account's
    // own Payments tab — the screen a clerk opens when the customer rings about
    // the letter that told them about it — the two were indistinguishable
    // except by scanning one of thirteen columns.
    //
    // ⚠ **NO SIGN IS WRITTEN, AND THAT IS NOT TIMIDITY.** Whether a credit's
    // sign lives on `amount` is B2's own O-4 residue and no signed document
    // closes it; a minus drawn here would be this lane answering an open
    // question on a money figure. The SENTENCE says what the row is, which is
    // what the spec asked for and needs no sign at all.
    amount: (row) => (
      <>
        <MoneyCell amount={row.amount} currency={row.currency} />
        {/* ONE sentence for both non-payment types. The Type column beside it
            already says which — Credit or Adjustment — and repeating that here
            would be the description budget spent twice (B14 rule 32). */}
        {row.type !== "payment" && (
          <span className="pay-sub">{t("payments.row.notMoneyReceived")}</span>
        )}
      </>
    ),
    status: (row) => (
      <StatusPill tone={paymentStatusTone(row.status)}>
        {paymentStatusLabel(row.status, t)}
      </StatusPill>
    ),
    purpose: (row) => <span>{t(`payments.purpose.${row.purpose}`)}</span>,
    // ⛔ **CR-059 CS-44 · THE ABSENCE THIS CELL STATED HAD EXPIRED, AND THE CELL
    // ITSELF HELD A RULE VIOLATION NOTHING COULD FIRE (DEF-2353 · DEF-2352).**
    //
    // CS-44 asks for `DEP-260808-CHK` here and asks one thing first: check it is
    // still true that the column is empty. **It is not.** `deposit_batches` IS
    // built — `bankrec_models.DepositBatch` on a real table with its own `code`
    // — and `reconciliation.py` stamps membership with
    // `.update(deposit_batch_id=batch.pk)`, which `bankrec_read.py` then counts
    // members off. What still hardcodes `None` is the payments LIST read
    // (`selectors.py`), whose module docstring says *"nothing writes it, so it
    // is always null and that is the truth"* — a sentence that was true when it
    // was written and stopped being true in somebody else's lane. That is
    // `DEF-2353`, one line in a file this lane must not touch.
    //
    // ⚠ **AND THIS CELL USED TO PRINT `row.deposit_batch_id` — A RAW UUID — AS
    // THE VISIBLE VALUE OF THE FIELD, WHICH B14 RULE 31 FORBIDS.** Nothing could
    // see it: the branch is unreachable while the server nulls the column, every
    // fixture carries null because the type says it always is, rule 31 is
    // RATIFIED AND UNENFORCED (no gate here reads rendered output), and it would
    // have started running on the day someone else fixed DEF-2353 in a commit
    // with no reason to open this file.
    //
    // ⚠ **AND THE CELL IS NOW GONE ENTIRELY — `batch` ABOVE IS WHAT REPLACED
    // IT (`CR-135` `P1.9`), AND THAT CLOSES `DEF-2353`'s SCREEN HALF.** The
    // list read serves the batch's own `DEP-` CODE as `batch_ref`, which is
    // exactly what CS-44 asked for; keeping a second, hidden column that says
    // *"this list does not carry the batch"* beside one that does is how a
    // screen comes to contradict itself.
    // BR-PAY-024 auto-queues a receipt on every cleared payment. That queue
    // write is US-PAY-025's and is not built, so a number here would name a
    // receipt nobody sent.
    receiptNo: (row) =>
      row.receipt_no !== null ? (
        <span className="pay-id">{row.receipt_no}</span>
      ) : (
        <Dash>{t("payments.row.noReceipt")}</Dash>
      ),
    // ── §03 2·1 ④ SOURCE — *"the three ways money reaches this list"* ──────
    //
    // ⛔ **`DEF-PAY-6212`.** `payments/0030` landed the column and its CHECK on
    // 2026-09-22 and NO READER FOLLOWED IT, so a fact the database has held for
    // a day never reached a screen. Hard-won law 2 in its plainest form.
    //
    // ⚠ **THE KIT'S `Chip`, NOT A `StatusPill` AND NOT A NEW BADGE.** The
    // drawing draws a bordered box and a source is not a STATUS — a pill is the
    // status chip and colouring `Post` as though it were a state would make the
    // column read as a verdict on the money. `Chip` with no `onRemove` is the
    // resting, non-removable shape, and it is what the kit already has (B14
    // rule 5: a chip is not a third button size, and it is drawn once).
    //
    // ⚠ **THE LABEL IS THE CATALOGUE'S AND THE VALUE IS THE COLUMN'S.** The
    // stored words are `entry · webhook · import`; the drawn words are
    // *Counter · Digital · Post*, and `models.PAYMENT_ORIGINS` records the PO's
    // 2026-09-22 ruling that the stored words do not move. A null is a row
    // written before the column existed and it says so rather than being
    // guessed into one of the three (B14 rule 31 — the stored code is never
    // what a clerk reads).
    // PO 2026-10-30 Q6 — a payment a store network took (the file's Network
    // column) names it: *Store · Hy-Vee*. Every other row keeps its word.
    source: (row) =>
      row.store_network ? (
        <Chip>{t("payments.source.store", { network: row.store_network })}</Chip>
      ) : row.origin !== null ? (
        <Chip>{t(`payments.source.${row.origin}`)}</Chip>
      ) : (
        <Dash>{t("payments.row.noSource")}</Dash>
      ),
    // ── §03 2·1 ⑤ BATCH — *"the id every payment carries"* ─────────────────
    //
    // ⛔ **`DEF-PAY-6213`, AND IT WAS REPORTED AS *"not servable at all"*.** It
    // is a READ that was missing, never a link that did not exist:
    // `import_run_rows.created_record_id` has named the payment each imported
    // row created since the eighth import target landed.
    //
    // ⚠ **THE DRAWN IDS ARE ILLUSTRATIONS (B14 rule 37).** The page draws
    // `CTR-260921-DW`, `IMP-260921-LBX` and `STL-2609-CARD`; what is served is
    // the code the product actually mints — a deposit batch's `DEP-` code or
    // the import run's own number.
    //
    // ⚠ **A CARD TAKEN AND NOT YET SETTLED HAS NO BATCH, AND THE DRAWING SAYS
    // SO ITSELF.** Its gap note ⑦: *"'every payment carries a batch id' and
    // 'the digital batch id arrives at settlement' cannot both be true at the
    // moment a card is taken"*, and there is no settlement run in the product.
    // So the absence is STATED — never a blank cell, which reads as a failed
    // load — and its words are a fact rather than a rationale (B14 rule 33).
    // Record links (PO 2026-10-19): a DEPOSIT batch's code opens the batch.
    // An import run's number has no page here and stays text.
    batch: (row) =>
      row.batch_ref === null ? (
        <Dash>{t("payments.row.noBatch")}</Dash>
      ) : row.batch_kind === "deposit" && row.batch_id != null ? (
        <InlineLinkAnchor
          className="pay-id"
          href={tenantPath(depositBatchRoute(row.batch_id))}
        >
          {row.batch_ref}
        </InlineLinkAnchor>
      ) : (
        <span className="pay-id">{row.batch_ref}</span>
      ),
  };
}

// ── The filter totals (US-PAY-004 TC-1) ────────────────────────────────────

/**
 * "N payments · $X in this view", as the server can actually answer it.
 *
 * LABEL·VALUE pairs rather than a sentence: the money figure must go through
 * MoneyCell (BR-SHL-023), and a translated fragment either side of a component
 * is the concatenated sentence B8 forbids — it also breaks in German and Hindi
 * word order.
 *
 * A null `amount` is rendered as the SERVER's own reason, never as $0.00: it
 * means the filter matched nothing, every currency in it differs, or nothing in
 * it was cash.
 *
 * ⚠ **THE MONEY FIGURE IS THE DAY'S CASH AND IT LEAVES CREDITS OUT, SO THE LINE
 * SAYS SO WHENEVER IT DID (`DEF-3207`, `CR-059` CS-35 task 23).** Until
 * 2026-09-02 the server refused to state ANY figure once a credit was in the
 * filtered set, and task 22 shipped the ability to record one on that same day —
 * so a clerk granting one $25.00 concession lost the whole day's takings. The
 * figure is now the cash, which is what ties to the drawer, and a row it left
 * out must be VISIBLE: a total that quietly covers less than the list above it
 * is worse than one that refuses, because nothing on screen says which.
 *
 * The excluded rows are COUNTED and never summed — whether a credit's sign lives
 * on `amount` is B2's own O-4 residue and is still nobody's to decide here.
 */
export function PaymentsTotalsLine(props: { totals: PaymentsTotals | undefined; t: Translator }) {
  const { t, totals } = props;
  const excluded = totals?.excluded_count ?? 0;
  return (
    <span className="pay-rollup">
      <span className="pay-rollup-item">
        <span className="pay-rollup-label">{t("payments.totals.count")}</span>
        <span className="pay-rollup-value">{totals?.count ?? 0}</span>
      </span>
      <span className="pay-rollup-item">
        {/* The KEY is unchanged and its WORDS moved: it used to read "Total in
            this view" and the figure is now the cash. Renaming the key would
            have left a dead entry in eleven catalogues and taught nothing. */}
        <span className="pay-rollup-label">{t("payments.totals.amount")}</span>
        <span className="pay-rollup-value">
          {totals?.amount != null && totals.currency != null ? (
            <MoneyCell amount={totals.amount} currency={totals.currency} />
          ) : (
            <span className="cus-awaits">
              {t(`payments.totals.unavailable.${totals?.amount_unavailable ?? "no_rows"}`)}
            </span>
          )}
        </span>
      </span>
      {/* Only when there IS something to say. A permanent "0 excluded" would be
          B14 rule 32's noise on a line a clerk reads every day. */}
      {excluded > 0 && (
        <span className="pay-rollup-item">
          <span className="pay-rollup-label">{t("payments.totals.notCash")}</span>
          <span className="pay-rollup-value">{excluded}</span>
        </span>
      )}
    </span>
  );
}

// ── The result panel (US-PAY-001 §5) ───────────────────────────────────────

/**
 * What the payment PAID — shown after the modal closes, not swallowed.
 *
 * A clerk who has just taken $292.87 has to see where it went: the allocator
 * worked the split out inside the same transaction and throwing it away would
 * make the screen ask the server again for a figure it was already given.
 *
 * ⛔ **AT MOST TWO SENTENCES — `DEF-PAY-10783`, PO 2026-10-31 P11 = A.** The
 * panel said *"Recorded PMT-…"*, then *"The books were updated in the same
 * step: cash up, receivables down."* (or its not-yet-posted twin), then *"This
 * money met no bill…"*, then every allow-listed outcome — up to five sentences
 * a clerk reads at the counter with a customer waiting. The ruling: *"Recorded.
 * Receipt # PY-…"* plus at most ONE warning. So the ledger and met-no-bill
 * sentences are DELETED (B14 rule 33: rationale is removed, never shortened;
 * *Carried as credit* already states the second as a figure), the receipt
 * number moves into the first sentence, and `outcomes` is cut to the first by
 * `RECORD_RESULT_PRIORITY`. The figures (received, applied, credit, the bills
 * met) are FACTS, not sentences, and stay.
 */
export function RecordPaymentPanel(props: { recorded: RecordedPayment; onDismiss: () => void }) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { recorded } = props;
  // `DEF-PAY-10733` (L3-01) — allow-listed, worded, said once. See
  // `RECORD_RESULT_CLERK_CODES` for why the rest of `problems[]` is silent here.
  const outcome = firstRecordOutcome((key, params) => t(key, params), recorded.problems);
  return (
    <div className="pay-result" role="status">
      <div className="pay-result-head">
        <h3>
          {!recorded.created
            ? t("payments.result.replay")
            : recorded.payment_no !== null
              ? t("payments.result.recordedReceipt", { number: recorded.payment_no })
              : t("payments.result.recordedOnly")}
        </h3>
        {/* PO 2026-10-30, Q3 = A — paper in the customer's hand now. */}
        <PrintReceiptButton paymentId={recorded.id} />
        <Button variant="ghost"  onClick={props.onDismiss}>
          {t("payments.result.dismiss")}
        </Button>
      </div>
      <dl className="met-facts">
        {/* `DEF-PAY-10733` — the payment number IS the receipt number; since
            `DEF-PAY-10783` it is said in the heading, *"Recorded. Receipt #
            PY-…"*, and not again here. */}
        <div>
          <dt>{t("payments.result.amount")}</dt>
          <dd>
            <MoneyCell amount={recorded.amount} currency={recorded.currency} />
          </dd>
        </div>
        <div>
          <dt>{t("payments.result.applied")}</dt>
          <dd>
            <MoneyCell amount={recorded.applied} currency={recorded.currency} />
          </dd>
        </div>
        <div>
          {/* BR-PAY-010 / BR-PAY-012: whatever no bill could absorb is carried
              as an account credit. Shown always, including at 0.00 — "nothing
              was left over" is the fact a clerk needs, and hiding the row when
              it is zero would make its absence ambiguous. */}
          <dt>{t("payments.result.creditCarried")}</dt>
          <dd>
            <MoneyCell amount={recorded.credit_carried} currency={recorded.currency} />
          </dd>
        </div>
      </dl>
      {recorded.allocations.length > 0 && (
        <ul className="pay-result-allocations">
          {recorded.allocations.map((entry) => (
            <li key={entry.invoice_id ?? entry.invoice_number ?? entry.amount}>
              {/* Record links (PO 2026-10-19): the bill this money met opens. */}
              {entry.invoice_id !== null && entry.invoice_number !== null ? (
                <InlineLinkAnchor
                  className="pay-id"
                  href={tenantPath(billDetailPath(entry.invoice_id))}
                >
                  {entry.invoice_number}
                </InlineLinkAnchor>
              ) : (
                <span className="pay-id">
                  {entry.invoice_number ?? t("payments.row.billNumberUnavailable")}
                </span>
              )}
              <MoneyCell amount={entry.amount} currency={recorded.currency} />
            </li>
          ))}
        </ul>
      )}
      {outcome !== null && (
        <ul className="pay-result-problems">
          <li data-outcome={outcome.code}>{outcome.words}</li>
        </ul>
      )}
    </div>
  );
}

// ── The Record modal (S22 / S35) ───────────────────────────────────────────

const AMOUNT_PATTERN = /^\d+(\.\d{1,6})?$/;

// Every digit is a zero: "0", "0.00", "0.000000". AMOUNT_PATTERN has already
// refused a sign and anything non-numeric, so for a value that reaches here
// "not all zeros" IS "greater than zero" — decided on the DIGITS, with no
// float in the path (CLAUDE.md rule 2).
const ALL_ZEROS_PATTERN = /^0*(\.0*)?$/;

/**
 * Client validation is UX only — the SERVER is authoritative (B8 forms) and
 * refuses every one of these again with its own rule id. The amount is checked
 * as a STRING pattern rather than parsed: a `Number()` here would be the float
 * CLAUDE.md rule 2 exists to keep out of money, in the one place it is most
 * tempting.
 *
 * That sentence was FALSE until 2026-08-15 — the positivity check under it read
 * `Number.parseFloat(value) > 0`, a float on a money string in the file whose
 * docstring says there is none (hard-won law 1: a comment claiming a guarantee
 * is not the guarantee; found while fixing DEF-088 and reported with it). The
 * check now tests the digits, so the docstring describes the code.
 */
export function recordPaymentSchema(t: Translator) {
  return z.object({
    account_id: z.string().min(1, t("payments.form.accountRequired")),
    amount: z
      .string()
      .regex(AMOUNT_PATTERN, t("payments.form.amountInvalid"))
      .refine((value) => !ALL_ZEROS_PATTERN.test(value), {
        message: t("payments.form.amountPositive"),
      }),
    posted_at: z.string().min(1, t("payments.form.postedAtRequired")),
  });
}

// ══════════════════════════════════════════════════════════════════════════
// ⛔ `RecordPaymentModal` IS GONE FROM THIS FILE — `DEF-PAY-6317`, 2026-09-23
// ══════════════════════════════════════════════════════════════════════════
// It moved, whole and unchanged, to `RecordPaymentPage.tsx` as the exported
// COMPONENT `RecordPaymentForm` inside the page at
// `/:tenant/payments/record/new`. Blueprint p037, frame 2·3a, in the frame
// header itself: *"today: a modal · agreed: `/:tenant/payments/record/new` —
// a page, not a modal"*. The PO reported it on the deployed build with the
// drawing beside the product: ***"record payment is form - not modal"***.
//
// ⚠ **IT IS NOT KEPT HERE AS WELL.** p036 states the discipline for the same
// move one frame up — *"leaving both would give the product two answers to one
// question, which is how a figure starts to drift"* — and a component nothing
// mounts is hard-won law 2's dead UI. The three doors that used to open it
// (this page's head button, the table's empty-state CTA and 1·1's Summary
// tile) are ADDRESSES now, not handlers, for `DEF-CWP-3925`'s reason.
//
// `recordPaymentSchema` above STAYS: `AccountActions.tsx` imports it for the
// account screen's own twin of this form, and that form is `S22` and is not
// what 2·3a redraws.

// ── The Reverse modal and its result (S35 · CR-059 CS-5, task 16) ──────────
//
// ══════════════════════════════════════════════════════════════════════════
// FOUR REASONS FROM 2026-09-03, AND ONE WAS THE SPEC UNTIL THAT MORNING
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS SECTION SAID "ONE REASON, AND THAT IS THE SPEC RATHER THAN A
// SHORTCUT" AND IT WAS RIGHT WHILE IT STOOD (hard-won law 1).**
// `BR-PAY-011` names four reversal reasons and the column has always carried
// all four; `reversal.SUPPORTED_REASONS` was `(nsf,)` and the service refused
// the other three BY NAME, because that rule's windows (ACH 60d, card 120d),
// its approval path and its consequence message were **CS-31 and not built**.
// CS-5's own screen note asked for one reason for exactly that reason, and
// offering four over a service that accepts one is a modal that fails on submit.
//
// **CS-31 (tasks 35 and 36) built all three clauses**, so the picker is now
// four options over a service that honours four — and the three new ones are
// what a two-person office actually hits: a wrong amount, a duplicate, a
// chargeback, a disputed payment. CS-31's own case: *"A customer hands over a
// cheque for 100.00. The clerk types 1,000.00 and presses Record."* Before
// today the account was left 900.00 in credit that the next bill would spend.
//
// ══════════════════════════════════════════════════════════════════════════
// THE WINDOW, THE APPROVAL AND THE CONSEQUENCES ALL COME FROM THE SERVER
// ══════════════════════════════════════════════════════════════════════════
// `GET /payments/{id}/reversal-plan` is read whenever the reason or the date
// changes, and CS-31 says why it is a server read rather than three client
// rules: *"It must be computed by the service, not assembled on the screen, or
// the warning and the outcome can disagree."* So this file computes NONE of
// them — not whether the window has expired, not whether an approval is needed,
// not what re-opens. It renders what the plan says, and `can_reverse` is served
// rather than derived from three fields here.
//
// **A BOUNCE ASKS FOR NO PLAN AND THAT IS THE RULE, NOT AN OPTIMISATION.** The
// bank decided it, so there is no window to be outside of and nobody to
// approve; the row's own `applied_to` preview below has served that case since
// task 16 and costs no request.
//
// ══════════════════════════════════════════════════════════════════════════
// THE LOCKED-BATCH REFUSAL CS-5 ASKS FOR IS **NOT** BUILT, AND THAT IS CORRECT
// ══════════════════════════════════════════════════════════════════════════
// CS-5 asks for *"the locked-batch refusal shown BEFORE the button, not as an
// error after it"*, and §10's P2 spells the sentence out. **That state no
// longer exists.** The PO closed `OQ-134` on 2026-08-12: a bounce inside a
// reconciled batch is lawful — the batch total stands and the bounce is new
// rows. What the service still refuses is a payment naming a batch it cannot
// READ, which is a broken reference and not a state a screen can pre-empt.
// Drawing the refusal anyway would put a rule on screen that nobody holds.
//
// ══════════════════════════════════════════════════════════════════════════
// THE CONSEQUENCES ARE PREVIEWED FROM THE ROW, AND NOT EVERY ONE CAN BE
// ══════════════════════════════════════════════════════════════════════════
// P2 asks for the consequences before committing. The bills come from the row's
// own `applied_to` — the same join the "Applied to" column renders — so the
// preview costs no request and cannot disagree with the list a clerk is looking
// at. Two of P2's three lines are NOT drawn and neither is an oversight:
//
//   · **the original due date.** Nothing serves it and nothing may invent it.
//     The bill re-opens at its OWN `invoices.due_date`, which the reversal
//     never writes — that is how the late-fee clock keeps running.
//   · **"NSF count 1 → 2".** No read publishes the count before the bounce.
//     The RESULT carries the count after it, from the customers seam, and the
//     panel shows that instead of a subtraction nobody can check.

/**
 * `returned_on` is required and `bank_fee`, when given, is a money STRING.
 *
 * The fee is validated as a pattern rather than parsed, for the reason
 * `recordPaymentSchema` gives: a `Number()` here would be a float on money.
 * **Blank stays blank and is sent as absent** — a bank that charged nothing has
 * no entry to make, and a `0.00` would ask the ledger for a balanced pair of
 * nothing.
 */
export function reversePaymentSchema(t: Translator, approvalRequired = false) {
  return z.object({
    returned_on: z.string().min(1, t("payments.reverse.returnedOnRequired")),
    // LBX-04 (PO 2026-10-30) — the bank's own words, at most 60 characters.
    bank_memo: z
      .string()
      .optional()
      .refine((value) => (value ?? "").trim().length <= BANK_MEMO_MAX, {
        message: t("payments.reverse.bankMemoTooLong"),
      }),
    // DEF-PAY-10698 — the NSF fee may be unticked only WITH a reason.
    charge_nsf_fee: z.boolean().optional(),
    nsf_fee_waive_reason: z.string().optional(),
    // CR-059 CS-33 (task 67) — how much of the payment came back.
    //
    // ⚠ **BLANK IS NOT ZERO AND IT IS NOT INVALID.** Absent means *"the whole
    // of what still stands"*, which is what every caller meant before CS-33 and
    // is still what this modal submits by default; `0.00` would be a reversal
    // that takes nothing back and the SERVICE refuses it by name. So the field
    // validates as a pattern when it has digits and is left alone when it does
    // not — never parsed with `Number()`, which would be a float on money
    // (CLAUDE.md rule 2), in the one place it is most tempting.
    //
    // **Whether the figure is too big is NOT checked here.** BR-PAY-884's
    // ceiling is the sum of every reversal against the payment, the database
    // re-sums it on INSERT, and a row locked by another clerk can move it
    // between this render and the submit. A client copy of that rule would
    // refuse a lawful amount some of the time and allow an unlawful one the
    // rest — so the screen SHOWS the remainder and the server decides.
    amount: z
      .string()
      .refine((value) => value === "" || AMOUNT_PATTERN.test(value), {
        message: t("payments.form.amountInvalid"),
      })
      .refine((value) => value === "" || !ALL_ZEROS_PATTERN.test(value), {
        message: t("payments.form.amountPositive"),
      }),
    bank_fee: z
      .string()
      .refine((value) => value === "" || AMOUNT_PATTERN.test(value), {
        message: t("payments.form.amountInvalid"),
      }),
    // BR-PAY-011's approval clause. The field is only REQUIRED when the SERVER
    // said one is needed — this side never predicts it, because a second copy
    // of *"applied to an issued bill, or a closed month"* is a second place for
    // that rule to drift. The marker beside the label follows the same fact.
    approval: z
      .string()
      .optional()
      .refine((value) => !approvalRequired || (value ?? "").trim() !== "", {
        message: t("payments.reverse.approvalRequired"),
      }),
  }).superRefine((values, ctx) => {
    // DEF-PAY-10698 — an unticked NSF fee needs its reason (PO 2026-10-30).
    if (values.charge_nsf_fee === false && (values.nsf_fee_waive_reason ?? "").trim() === "") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["nsf_fee_waive_reason"],
        message: t("payments.reverse.nsfFee.waiveReasonRequired"),
      });
    }
  });
}

export function ReversePaymentModal(props: {
  client: ApiClient;
  payment: PaymentRow;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onReversed: (result: ReversedPayment) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { payment } = props;
  const [returnedOn, setReturnedOn] = useState("");
  const [bankFee, setBankFee] = useState("");
  // LBX-04 (PO 2026-10-30) — this box was *Memo* and is now the bank's own
  // words, *Bank memo*, saved on the REVERSING row (hard rule 4).
  const [memo, setMemo] = useState("");
  // DEF-PAY-10698 — the NSF fee is ticked by default; unticking needs a reason.
  const [chargeNsfFee, setChargeNsfFee] = useState(true);
  const [waiveReason, setWaiveReason] = useState("");
  // CR-059 CS-33 (task 67). Blank = the whole of what still stands, which is
  // the default every caller before this change had and the one a clerk gets
  // by touching nothing.
  const [amount, setAmount] = useState("");
  // CR-059 CS-31 (task 36) — four reasons, and the bounce is the default
  // because it is the one that needs no window and no approval. A caller who
  // changes nothing therefore gets the least restrictive path and can never be
  // walked into a staff correction by a pre-selected option.
  const [reason, setReason] = useState<ReversalReason>("nsf");
  const [approval, setApproval] = useState("");
  const staff = reason !== "nsf";
  // The plan is read only for a STAFF correction with a date to judge it on.
  // A bounce asks for nothing: the bank decided it (see this section's header).
  // CR-059 CS-33 — a PART reversal asks for the plan too, whatever the reason.
  //
  // The bounce's *"no plan"* rule stands and is not weakened: a returned item
  // is the bank's decision, so there is no window to be outside of and nobody
  // to approve, and a clerk taking the whole payment back still asks for
  // nothing. What a PARTIAL asks is a different question — *"what does this
  // payment still stand for?"* — and that figure is the server's, because after
  // one partial reversal it is no longer `payment.amount`.
  const partial = amount.trim() !== "";
  const plan = useQuery({
    queryKey: ["payments", "reversal-plan", payment.id, reason, returnedOn],
    queryFn: () => getReversalPlan(payment.id, { reason, on: returnedOn }, props.client),
    enabled: (staff || partial) && returnedOn !== "",
    retry: false,
  });
  // What the payment will stand for once this reversal lands. The SERVER's
  // `stands_for` minus what the clerk typed — never `payment.amount` minus it,
  // which is the same figure only until the first partial reversal.
  //
  // `remainingToAllocate` is the exact BigInt subtraction this feature already
  // owns — *"what is held, less what has been aimed"* — and reusing it is what
  // keeps one implementation of decimal money on this screen rather than two
  // (hard-won law 5). Never `Number()`: rule 2, in the place it is most
  // tempting.
  const standsAfter =
    plan.data === undefined || !partial
      ? null
      : remainingToAllocate(plan.data.stands_for, { reversed: amount.trim() });
  const approvalRequired = plan.data?.approval.required === true;
  // A bounce PAUSES the ladder and a person resumes it. What the PO ruled on
  // 2026-08-12 is WHERE it restarts (at the first step, so a customer whose
  // cheque bounced is not met with a disconnection notice as their first
  // contact), not that it should happen with nobody asking. Default off.
  const [resumeCollections, setResumeCollections] = useState(false);
  // Hard rule 6 / BR-PAY-028: ONE token per opened form, minted once. The door
  // REFUSES a body without it, and CS-33 removes the database index underneath
  // it, so this becomes the last per-submit guard standing.
  const [submitToken] = useState(() => crypto.randomUUID());

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await reversePayment(
        payment.id,
        {
          returned_on: returnedOn,
          reason,
          bank_memo: memo.trim() === "" ? null : memo.trim(),
          charge_nsf_fee: reason === "nsf" ? chargeNsfFee : true,
          nsf_fee_waive_reason:
            reason === "nsf" && !chargeNsfFee ? waiveReason.trim() : null,
          // Sent only when there is one to send. An empty string would be an
          // approval nobody gave, recorded in `audit_log` as though they had.
          approval: approval.trim() === "" ? null : approval.trim(),
          // Absent, never zero — see the schema.
          bank_fee: bankFee === "" ? null : bankFee,
          // CR-059 CS-33. Absent means the whole of what still stands; a blank
          // box must not become `"0"`, which the service refuses by name.
          amount: amount.trim() === "" ? null : amount.trim(),
          resume_collections: resumeCollections,
          idempotency_key: submitToken,
        },
        props.client,
      );
      props.onReversed(result);
      return { ok: true };
    } catch (error) {
      // The service's own `@require_role(SYSTEM_ADMIN)` and every BR-PAY-013
      // refusal land here and are SHOWN: server-side enforcement is THE
      // enforcement (BR-SHL-025), never second-guessed on this side.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("payments.reverse.title")}
      kicker={t("payments.reverse.kicker", {
        number: payment.payment_no ?? t("payments.row.noNumber"),
      })}
      schema={reversePaymentSchema(translate, approvalRequired)}
      values={{
        returned_on: returnedOn,
        bank_fee: bankFee,
        approval,
        amount,
        bank_memo: memo,
        charge_nsf_fee: reason === "nsf" ? chargeNsfFee : true,
        nsf_fee_waive_reason: waiveReason,
      }}
      submitLabel={t("payments.reverse.submit")}
      /* ⚠ **`P3.12` — THE WARNING MOVES ONTO THE ACT, NOT JUST THE DOOR (B14
         rule 6).** Reverse is one of rule 6's four named examples, and until
         this line the ROW ACTION that opens this dialog was danger-tiered
         (`PaymentsPage.tsx`, the `RollBackIcon` action, `danger`) while the
         button that actually takes the money back rendered **exactly like
         Save**.

         The blueprint measured it at §03 frame 2·3e: `WorkingButton` has taken
         a `CommitTier` since `DEF-712` and `FormModal` has threaded
         `submitVariant` straight through to it since the `DEF-718` sibling fix
         — and the string `submitVariant` did not occur ANYWHERE in this file,
         so all three payments modals passed none.

         ⚠ **THIS IS THE HOLE B14's OWN STATUS COLUMN NAMES, NOT ONE NOBODY HAD
         GOT TO.** Rule 6 is enforced on RENDERED OUTPUT for a `WizardFrame`
         commit and for a `ConfirmDialog` commit, and the row ends *"still
         unchecked: a commit button that composes NEITHER shared component"*. A
         `FormModal` composes neither, and payments is the module sitting in it.
         `P3.16` is the test that closes it.

         The row action KEEPS its `danger`, and that is not a duplicate: rule 6
         governs the COMMIT, and the drawing shows the door red as well. */
      submitVariant="danger"
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* FOUR reasons (CR-059 CS-31). The reason decides which flow runs — a
          bounce counts against the customer and sends them a letter; a staff
          correction does neither — so it is the first thing on the form and
          never a detail at the bottom. */}
      <SelectField
        id="reason"
        label={t("payments.reverse.reason")}
        value={reason}
        onChange={(value) => {
          setReason(value as ReversalReason);
          setApproval("");
        }}
        options={REVERSAL_REASONS.map((code) => ({
          value: code,
          label: t(`payments.reverse.reason.${code}`),
        }))}
        help={t("payments.reverse.reasonHelp")}
      />
      {/* DEF-PAY-10698 — the NSF fee, BEFORE Confirm (PO 2026-10-30):
          billing's quote for this payment's plan, then the tick. */}
      {reason === "nsf" && chargeNsfFee && (
        <NsfFeeLine
          paymentId={payment.id}
          reason={reason}
          returnedOn={returnedOn}
          client={props.client}
        />
      )}
      {reason === "nsf" && (
        <NsfFeeChoice
          idPrefix=""
          charge={chargeNsfFee}
          onCharge={setChargeNsfFee}
          waiveReason={waiveReason}
          onWaiveReason={setWaiveReason}
        />
      )}
      {/* WHAT A STAFF CORRECTION DOES NOT DO. It is the sentence that stops a
          clerk reaching for the bounce because it is the familiar one: this
          counts no returned payment against the customer and sends no letter. */}
      {staff && (
        <p className="pay-resolve-facts">{t("payments.reverse.staffCorrection")}</p>
      )}
      {/* THE WINDOW, AS A SENTENCE. CS-31 asks for it *"as a reason rather than
          a boolean so it can be shown"* — the tender, the days and the limit,
          all from the server. */}
      {staff && plan.data !== undefined && !plan.data.window.within && (
        <p className="pay-attention" role="note">
          {t("payments.reverse.outsideWindow", {
            days: plan.data.window.days_elapsed,
            limit: plan.data.window.limit_days,
          })}
        </p>
      )}
      {/* THE CONSEQUENCE PANEL, SERVER-COMPOSED. The bills and the credit come
          from the plan rather than from an addition done here, so the warning
          and the outcome cannot disagree (CS-31's own reason).

          ⚠ **`P0.12` — IT IS THE KIT'S BOX NOW, AND THE SENTENCE DID NOT
          CHANGE.** It was a bare `<p className="pay-form-note">`, which is the
          class this screen uses for a HELPER under a field — so the one
          statement on the form that says what the commit will do was drawn in
          the same weight as *"Leave blank if there was none."* B14 rule 11 asks
          for a box, the kit has had one since 2026-09-05, and the blueprint
          files this screen as one of three rule-11 violations. Nothing about
          the figures moves: they are still the server's plan, unread by this
          component. */}
      {staff && plan.data !== undefined && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.consequence.tag")}
          data-consequence="reverse"
          title={t("payments.reverse.planSummary", {
            count: plan.data.consequences.bills_reopening.length,
            total: plan.data.consequences.bills_reopening_total,
          })}
          // ⚠ NOT `staffCorrection`, which is drawn above and is about the
          // REASON rather than the outcome — a box repeating the sentence four
          // lines over it is the description budget B14 rule 32 caps, and the
          // second copy is the one a clerk stops reading.
          body={t("payments.reverse.consequence.body")}
        />
      )}
      {staff && plan.data?.consequences.credit_goes_negative === true && (
        <p className="pay-attention" role="note">
          {t("payments.reverse.creditGoesNegative")}
        </p>
      )}
      {/* BR-PAY-011's approval clause, asked for only when the SERVER says it
          is needed, and it names WHICH trigger fired rather than saying that
          something is wrong. */}
      {approvalRequired && (
        <>
          <p className="pay-attention" role="note">
            {t("payments.reverse.approvalWhy")}
          </p>
          <TextField
            id="approval"
            label={t("payments.reverse.approval")}
            value={approval}
            onChange={setApproval}
            required
            multiline
            help={t("payments.reverse.approvalHelp")}
          />
        </>
      )}
      {/* ── CR-059 CS-33 (task 67) — HOW MUCH OF IT CAME BACK ──────────────
          CS-33's own case: a cheque where the words and the figures disagree
          and the bank honours the lower. Before this, the office had to reverse
          the whole thing and record a second payment for the part that stood —
          *"the customer's history then shows a payment that bounced when it did
          not"*, and on a cheque that is an NSF count and a cash-only flag.

          BLANK IS THE DEFAULT AND MEANS ALL OF IT. The field is not pre-filled
          with the amount: a pre-filled figure is one a clerk scrolls past, and
          the whole-payment case is the common one that needs no typing at all.
          The help line names the figure so the box is not a guess. */}
      <TextField
        id="amount"
        label={t("payments.reverse.amount")}
        value={amount}
        onChange={setAmount}
        numeric
        help={t("payments.reverse.amountHelp")}
      />
      {/* WHAT WILL STILL STAND AFTERWARDS — the server's figure, minus what was
          typed. Drawn only once the plan has answered, because a remainder
          measured off the wrong base is worse than no remainder: after one
          partial reversal `payment.amount` is not what the payment stands for.
          A figure that could not be read renders as a stated absence. */}
      {partial && plan.data !== undefined && (
        <p className="pay-form-note">
          {standsAfter === null ? (
            t("payments.reverse.stillStandsUnavailable")
          ) : (
            <>
              {t("payments.reverse.stillStands")}{" "}
              <MoneyCell amount={standsAfter} currency={payment.currency} />
            </>
          )}
        </p>
      )}
      {partial && plan.isPending && (
        <p className="pay-form-note">{t("payments.reverse.stillStandsLoading")}</p>
      )}
      {/* What comes back, before the button. The bills are the row's own
          `applied_to`; the amounts are the money each of them absorbed, which
          is exactly what goes back on. */}
      <p className="pay-form-note">{t("payments.reverse.willReopen")}</p>
      {payment.applied_to.length > 0 ? (
        <ul className="pay-result-allocations">
          {payment.applied_to.map((entry) => (
            <li key={entry.invoice_id}>
              <span className="pay-id">
                {entry.invoice_number ?? t("payments.row.billNumberUnavailable")}
              </span>
              <MoneyCell amount={entry.amount} currency={payment.currency} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="pay-result-none">{t("payments.reverse.willReopenNone")}</p>
      )}
      {/* BR-PAY-021: a bounce hangs off the CLEARING side, so this is the day
          the BANK returned the item and never the browser's. Deliberately NOT
          pre-filled — unlike the Record form's posting date, which proposes
          today because a clerk taking money is taking it now. A returned item
          arrives on a statement days later, and a pre-filled today would be
          accepted unread. */}
      <DatePickerField
        id="returned_on"
        label={t("payments.reverse.returnedOn")}
        value={returnedOn}
        onChange={setReturnedOn}
        dateFormat={props.dateFormat}
        required
        help={t("payments.reverse.returnedOnHelp")}
      />
      {/* OUR bank's charge for handling the returned item — DR 6800, its own
          entry, touching no customer balance. NOT the customer's returned-cheque
          fee: that is billing's charge code and the result says so on every
          bounce. */}
      <TextField
        id="bank_fee"
        label={t("payments.reverse.bankFee")}
        value={bankFee}
        onChange={setBankFee}
        numeric
        help={t("payments.reverse.bankFeeHelp")}
      />
      <TextField
        id="bank_memo"
        label={t("payments.reverse.bankMemo")}
        value={memo}
        onChange={setMemo}
      />
      <CheckboxField
        id="resume_collections"
        label={t("payments.reverse.resume")}
        checked={resumeCollections}
        onChange={setResumeCollections}
      />
    </FormModal>
  );
}

/**
 * What the bounce DID — shown after the modal closes, not swallowed.
 *
 * Every figure is the server's, worked out inside the same transaction:
 * `PE-7`'s **−292.87** reversing row, the **292.87** put back on the bills, and
 * the signed credit position afterwards. Asking the server again for a number it
 * has just handed over would be perverse, and the two answers could differ.
 *
 * ⚠ **THE BILLS ARE NAMED FROM THE ORIGINAL ROW, NOT FROM THE RESULT.** The
 * service's `reopened[]` carries `invoice_id` and an amount and no bill number,
 * and **a database id is never the visible value of a field** (B14 rule 31).
 * So each re-opened bill is matched back to the row's own `applied_to` for its
 * number, and a bill that cannot be matched states that rather than printing
 * the id.
 */
export function ReversedPaymentPanel(props: {
  result: ReversedPayment;
  original: PaymentRow;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { result, original } = props;
  const numberOf = (invoiceId: string): string | null =>
    original.applied_to.find((entry) => entry.invoice_id === invoiceId)?.invoice_number ?? null;
  return (
    <div className="pay-result" role="status">
      <div className="pay-result-head">
        <h3>
          {result.created
            ? t("payments.reverse.done", {
                number: result.payment_no ?? t("payments.row.noNumber"),
              })
            : t("payments.reverse.replay")}
        </h3>
        <Button variant="ghost" onClick={props.onDismiss}>
          {t("payments.result.dismiss")}
        </Button>
      </div>
      <dl className="met-facts">
        <div>
          {/* NEGATIVE, and it stays negative: an unsigned 292.87 here would tell
              a clerk a second payment had arrived. */}
          <dt>{t("payments.reverse.amountLabel")}</dt>
          <dd>
            <MoneyCell amount={result.amount} currency={result.currency} />
          </dd>
        </div>
        <div>
          <dt>{t("payments.reverse.reinstated")}</dt>
          <dd>
            <MoneyCell amount={result.allocations_reversed} currency={result.currency} />
          </dd>
        </div>
        <div>
          {/* May be BELOW zero, and nothing floors it. A customer already
              refunded a credit whose payment then bounced owes that money back
              (PO 2026-08-11, OQ-132: "Yes, it's a real debt"). */}
          <dt>{t("payments.reverse.creditAfter")}</dt>
          <dd>
            <MoneyCell amount={result.credit_position_after} currency={result.currency} />
          </dd>
        </div>
        {/* CR-059 CS-33 — what is LEFT of the payment, and only on a partial.
            A full reversal leaves nothing standing and a 0.00 beside "still
            stands" would read as a figure somebody measured rather than as the
            end of the payment. `still_stands` is the SERVICE's: this panel does
            no subtraction, so it cannot disagree with the ceiling that refuses
            the next reversal. */}
        {result.is_partial && (
          <div>
            <dt>{t("payments.reverse.stillStandsLabel")}</dt>
            <dd>
              <MoneyCell amount={result.still_stands} currency={result.currency} />
            </dd>
          </div>
        )}
        <div>
          {/* null is NOT zero: the seam did not run. A replay does not re-count
              a bounce, and "we did not count" is a different fact from "the
              count is zero". */}
          <dt>{t("payments.reverse.nsfCountLabel")}</dt>
          <dd>
            {result.nsf_count !== null ? (
              result.nsf_count
            ) : (
              <Dash>{t("payments.reverse.nsfCountUnknown")}</Dash>
            )}
          </dd>
        </div>
      </dl>
      {result.reopened.length > 0 ? (
        <ul className="pay-result-allocations">
          {result.reopened.map((bill) => (
            <li key={bill.invoice_id}>
              {/* Record links (PO 2026-10-19): the reopened bill opens. */}
              {numberOf(bill.invoice_id) === null ? (
                <span className="pay-id">{t("payments.row.billNumberUnavailable")}</span>
              ) : (
                <InlineLinkAnchor
                  className="pay-id"
                  href={tenantPath(billDetailPath(bill.invoice_id))}
                >
                  {numberOf(bill.invoice_id)}
                </InlineLinkAnchor>
              )}
              <MoneyCell amount={bill.amount} currency={result.currency} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="pay-result-none">{t("payments.reverse.reopenedNone")}</p>
      )}
      {/* OUR bank's charge, stated either way — "no fee was posted" is the fact
          a clerk reconciling the statement needs, and an absent row would leave
          it ambiguous. */}
      <p className="pay-result-ledger">
        {result.bank_fee !== null
          ? t("payments.reverse.bankFeePosted")
          : t("payments.reverse.bankFeeNone")}
      </p>
      {result.problems.length > 0 && (
        <ul className="pay-result-problems">
          {/* `DEF-PAY-10736` (L2-05) — a code deleted on purpose (the
              balance-cache note) says nothing here either. */}
          {result.problems
            .filter((problem) => !PROBLEM_CODES_DELETED_ON_PURPOSE.includes(problem.code))
            .map((problem) => (
              <li key={problem.code}>
                {t(`payments.problem.${problem.code}`, {
                  defaultValue: t("payments.problem.unknown"),
                })}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

// ── Correct a reference (CR-059 CS-34 · task 42) ───────────────────────────
//
// WHY THIS EXISTS AT ALL. A payment row is append-only — CLAUDE.md hard rule 4,
// enforced by a database trigger and not by a convention. On 2026-09-02 the
// Product Owner narrowed that rule for exactly three columns, in their own
// words *"(a) Allow those fields to change"*: the cheque or confirmation
// number, the memo, and the tender. The reason it mattered is small-sounding
// and expensive — **the reference is what a bank line is matched on**, so a
// mistyped cheque number is an unmatched line and a reconciliation nobody can
// finish. Every other column, and DELETE in every status, is exactly as frozen
// as it was.
//
// WHAT THIS FORM SENDS, AND WHY IT IS A SHORT LIST. Only fields the clerk
// actually CHANGED. Sending an untouched value back would write an audit row
// recording that a field was corrected from itself, and the audit trail is the
// only place the previous value survives at all — see the retention note below,
// which is why filling it with noise is not a cosmetic problem.

/**
 * The reference, memo and tender the form is about to send — CHANGED ONLY.
 *
 * `null` means *"the clerk did not touch this"* and the field is omitted from
 * the body; the service's own signature reads a missing field the same way, so
 * the two halves agree by construction rather than by comment. An empty string
 * is a real correction — a clerk clearing a reference typed in error — and is
 * NOT collapsed into `null` here.
 */
export function correctReferenceChanges(
  row: PaymentRow,
  draft: { reference: string; memo: string; tenderId: string },
  currentTenderId: string,
): { reference?: string; memo?: string; tender_id?: string } {
  const changes: { reference?: string; memo?: string; tender_id?: string } = {};
  if (draft.reference !== (row.confirmation ?? "")) {
    changes.reference = draft.reference;
  }
  if (draft.memo !== (row.memo ?? "")) {
    changes.memo = draft.memo;
  }
  if (draft.tenderId !== "" && draft.tenderId !== currentTenderId) {
    changes.tender_id = draft.tenderId;
  }
  return changes;
}

export function correctReferenceSchema(t: Translator) {
  return z.object({
    // The service refuses a blank note by name — *"a correction needs a note
    // saying why"* — and this mirrors it rather than inventing it, so a clerk
    // is told before the round trip instead of after it.
    note: z.string().min(1, t("payments.correct.noteRequired")),
  });
}

/**
 * S35's Correct-reference modal.
 *
 * ⚠ **THE TENDER IS REFUSED ONCE THE PAYMENT IS BANKED, AND THIS SCREEN CANNOT
 * KNOW THAT.** Deposit batches group by TILL and tender (BR-PAY-025 as amended
 * 2026-09-22, `P0.6` — it was day and tender), so moving the tender on
 * a payment already inside one would put it in the wrong batch. The service
 * refuses it, naming the batch. The screen does not pre-empt that refusal
 * because `PaymentRow.deposit_batch_id` is documented on its own type as always
 * null — a guard built on it would offer the field precisely when it must not.
 * The field carries the condition as help text instead, which is the honest
 * half: a clerk is told the rule before they try.
 */
export function CorrectReferenceModal(props: {
  client: ApiClient;
  payment: PaymentRow;
  methods: readonly PaymentMethodOption[];
  onClose: () => void;
  onCorrected: (result: CorrectedReference) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { payment, methods } = props;
  // The tender the row is on, as an ID. The row carries the CODE (BR-PAY-026's
  // vocabulary) and the correction door takes the key, so the two are joined
  // here through the list both the filter and this picker already share.
  const currentTenderId = methods.find((option) => option.code === payment.method)?.id ?? "";
  const [reference, setReference] = useState(payment.confirmation ?? "");
  const [memo, setMemo] = useState(payment.memo ?? "");
  const [tenderId, setTenderId] = useState(currentTenderId);
  const [note, setNote] = useState("");

  const changes = correctReferenceChanges(payment, { reference, memo, tenderId }, currentTenderId);
  const nothingChanged = Object.keys(changes).length === 0;

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    if (nothingChanged) {
      // Not a rule this screen invented: the service refuses a body with all
      // three absent — *"nothing was given to correct"*. Answered here so the
      // clerk reads which control to touch rather than a generic rejection,
      // because the server's own detail text never reaches a screen
      // (BR-SHL-020 r2).
      return { ok: false, error: { code: "", message_key: "payments.correct.nothingChanged" } };
    }
    try {
      const result = await correctPaymentReference(
        payment.id,
        { ...changes, note },
        props.client,
      );
      props.onCorrected(result);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("payments.correct.title")}
      kicker={t("payments.correct.kicker", {
        number: payment.payment_no ?? t("payments.row.noNumber"),
      })}
      schema={correctReferenceSchema(translate)}
      values={{ note }}
      submitLabel={t("payments.correct.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <TextField
        id="reference"
        label={t("payments.correct.reference")}
        value={reference}
        onChange={setReference}
      />
      <TextField
        id="memo"
        label={t("payments.correct.memo")}
        value={memo}
        onChange={setMemo}
      />
      <SelectField
        id="tender_id"
        label={t("payments.correct.tender")}
        value={tenderId}
        onChange={setTenderId}
        options={methods.map((option) => ({ value: option.id, label: option.name }))}
        // ⚠ `DEF-PAY-10735` (L3-05) — a payment with NO method held `""` while
        // the select, having no empty option, DREW the first method (ACH). The
        // clerk saw ACH, saved a reference fix, and believed the tender was
        // already ACH. The empty option says what is true; choosing it sends no
        // `tender_id` (`correctReferenceChanges`). Only offered when the
        // payment really has no method: on a paid-by-cheque row it would read
        // as "remove the method", which this door cannot do.
        placeholder={currentTenderId === "" ? t("payments.correct.noMethod") : undefined}
        help={t("payments.correct.tenderHelp")}
      />
      {/* The service refuses a correction with no reason, so the marker is the
          rule and not a house style. */}
      <TextField
        id="note"
        label={t("payments.correct.note")}
        value={note}
        onChange={setNote}
        required
      />
      {/* ⚠ **`P0.12` — B14 RULE 11'S BOX, ON THE SECOND OF THE THREE MONEY
          FORMS.** This is the ONE in-place write CLAUDE.md hard rule 4 allows,
          narrowed by the PO on 2026-09-02 to exactly three columns, and the
          thing a clerk most needs to know before pressing Save is what it does
          NOT touch: **no money moves.** A correction that reads as though it
          might is a correction a clerk will avoid, and they will reverse the
          payment instead — which is a new row, a new number, and a reversal on
          a customer's history for a mistyped cheque number.

          ⚠ **THIS SENTENCE USED TO END *"It is NOT the retention disclosure
          below it"*, AND THERE IS NO LONGER A DISCLOSURE BELOW IT (`P3.18`,
          2026-09-23).** `CorrectionRetentionNote` rendered a `<details>` in
          eleven languages saying the old value *"is not kept for ever"* and that
          whether it is kept longer *"has not been decided"*. **It has been
          decided** — the PO ruled on 2026-09-23 that a correction's audit row is
          pruned like any other — and **the honest build is SILENCE rather than
          a corrected disclaimer**: B14 rule 33 puts RATIONALE at ZERO WORDS ON
          SCREEN, so a screen explaining the retention policy in order to be
          honest breaks rule 33 while trying to obey the ruling. This box stays
          and is untouched: *what is about to change* is rule 11's subject and a
          fact a clerk acts on, which is precisely what rationale is not.

          ⚠ **DRAWN ALWAYS, AND NOT GATED ON "SOMETHING CHANGED" — WHICH THE
          FIRST DRAFT OF THIS DID.** The statement is a fact about the FORM, not
          about the current edits: this door cannot move money whatever a clerk
          types into it, because `payments/0014`'s allow list is three columns
          wide at the database. Gating it would have hidden it in the state the
          modal OPENS in — pre-filled, nothing changed — which is the only
          state a hesitating clerk is ever looking at. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.consequence.tag")}
        data-consequence="correct"
        title={t("payments.correct.consequence.title")}
        body={t("payments.correct.consequence.body")}
      />
    </FormModal>
  );
}

/**
 * What the correction did — and what it does NOT promise.
 *
 * ⚠ **`previous` IS SHOWN AND IS NEVER CALLED A RECORD.** The Product Owner
 * accepted, when they ruled `OQ-1322`, that the replaced value then lives in the
 * audit trail and nowhere else — and on **2026-09-23 they ruled `OQ-1340` too:
 * that audit row is pruned like any other** (*"keep the same rule s; when audit
 * log is delete - it is deleted thats okay"*). So the prohibition is permanent
 * rather than provisional: **nothing here may describe this path as a permanent
 * record of the old value, ever.** This panel shows the old value beside the new
 * one, which is what a clerk needs at the moment they press the button, and it
 * makes no claim about how long that value survives.
 *
 * ⚠ **AND IT SAYS NOTHING AT ALL ABOUT RETENTION, WHICH IS A CHANGE (`P3.18`).**
 * This docstring ended *"the disclosure below says, in a sentence, that it is not
 * kept for ever"*, and that disclosure — `CorrectionRetentionNote` — is deleted.
 * **B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN**, so obeying the ruling
 * by explaining the retention policy would have broken rule 33 while trying to
 * obey it. **The honest build is silence: never claim permanence, and do not
 * explain why.** The fact stays on the wire, where a caller can reason about it,
 * as `amendment_history_is_not_a_permanent_record` on `unavailable[]`.
 */
export function CorrectedReferencePanel(props: {
  result: CorrectedReference;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const { result } = props;
  const fields = Object.keys(result.corrected);
  return (
    <div className="pay-result">
      <div className="pay-result-head">
        <h3>
          {t("payments.correct.doneTitle", {
            number: result.payment_no ?? t("payments.row.noNumber"),
          })}
        </h3>
        <Button variant="secondary" size="sm" onClick={props.onDismiss}>
          {/* The SAME word the Record and Reverse panels use — one vocabulary
              for one act, rather than a third key saying "Dismiss" again. */}
          {t("payments.result.dismiss")}
        </Button>
      </div>
      <div className="pay-pair-list">
        {fields.map((field) => (
          <p key={field} className="pay-form-note">
            {t("payments.correct.movedFrom", {
              field: t(`payments.correct.field.${field}`, {
                defaultValue: t("payments.correct.field.unknown"),
              }),
              // A field that was EMPTY before has a real previous value and it
              // is "nothing" — never a blank cell, which reads as a failed
              // read rather than as a fact.
              was: result.previous[field] ?? t("payments.correct.wasEmpty"),
              now: result.corrected[field] ?? t("payments.correct.wasEmpty"),
            })}
          </p>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// `CorrectionRetentionNote` WAS HERE AND IS DELETED — `P3.18`, 2026-09-23
// ═══════════════════════════════════════════════════════════════════════════
// It rendered a closed `<details>` on BOTH the Correct-reference form and the
// result panel, in all eleven catalogues:
//
//     "The old value is not kept for ever"
//     "The value you replace is recorded in the audit trail and nowhere else,
//      and audit records are removed after a time. **Whether these are kept for
//      longer has not been decided.**"
//
// ⚠ **THE LAST SENTENCE STOPPED BEING TRUE ON 2026-09-23.** The PO closed
// `OQ-1340` — *"keep the same rule s; when audit log is delete - it is deleted
// thats okay"* — so `audit_log` has ONE retention rule and a correction's row is
// inside it. The copy said a decision was outstanding hours after it was taken.
//
// ⚠ **AND THE FIX IS DELETION, NOT A REWORD, WHICH IS THE PART WORTH READING.**
// The obvious repair is to correct the sentence to *"the old value is removed on
// the retention schedule"* — **and that is still a breach.** B14 rule 33 puts
// **RATIONALE — why the product works this way — at ZERO WORDS ON SCREEN**, and
// rule 33's own amendment says rationale is **REMOVED, not shortened**: cutting a
// *why* to six words keeps the breach and makes it terser. A retention policy is
// the purest rationale there is. **So a screen that explains retention in order
// to be honest breaks rule 33 while trying to obey the ruling**, which is the
// trap the `CR-137-BRC07` board names in §1.3 and the decision log names by
// date.
//
// **What honesty actually requires here is an ABSENCE: never claim permanence.**
// `CorrectedReferencePanel` shows the old value beside the new one and promises
// nothing about it; the Correct-reference form states what the write does and
// stops. Neither says the word *record*.
//
// **The fact is not lost — it moved to where a MACHINE reads it.** Every
// successful correction response still carries it on `unavailable[]`, renamed in
// the same commit from `amendment_history_retention_unruled` (a name that
// asserted a decision was outstanding) to
// `amendment_history_is_not_a_permanent_record`. `apps/payments/amendments.py`
// carries the reasoning.
//
// ⚠ **`payments.correct.retentionSummary` AND `payments.correct.retentionDetail`
// WERE RETIRED FROM ALL ELEVEN CATALOGUES** through `10-scripts/i18n_fanin.py`'s
// `retire`, never by hand — one lane lost 44 locale keys hand-editing these
// files (CLAUDE.md law 11). A key left behind with no call site is dead weight;
// a call site left behind with no key renders the KEY to a clerk.

// ── The rows table ─────────────────────────────────────────────────────────

export interface PaymentsTableProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /** `f.account_id` when this table is the S21 Payments tab; absent on S33. */
  accountId?: string;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  onLoaded?: (page: PaymentsPageResponse | undefined) => void;
  emptyCtaReason: string | null;
  onEmptyCta: () => void;
}

export function PaymentsTable(props: PaymentsTableProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const { timeZone, dateFormat } = useRegional(props);
  // CR-059 CS-5 (task 16). `BR-PAY-1070` gates the SERVICE on the role, and A4
  // grades a SURFACE rather than a single action — so the role code answers it,
  // exactly as the read-detail screen's OQ-043 control does. A null answer (the
  // permissions read has not returned) offers the control: the server's own
  // `@require_role` is the boundary either way.
  const role = useTenantRole(client);
  // The payment a clerk pressed Reverse on, and what the bounce did. BOTH are
  // held, because the result names its bills by joining back to the ORIGINAL
  // row's `applied_to` — the service's own `reopened[]` carries only ids, and a
  // database id is never the visible value of a field (B14 rule 31).
  const [reversing, setReversing] = useState<PaymentRow | null>(null);
  const [reversed, setReversed] = useState<{ result: ReversedPayment; original: PaymentRow } | null>(
    null,
  );
  // CR-059 CS-34 (task 42). The payment a clerk pressed Correct on, and what
  // the correction did. Unlike the reversal pair, the RESULT stands alone —
  // it carries the payment number and both values, so nothing has to be joined
  // back to the original row to render it.
  const [correcting, setCorrecting] = useState<PaymentRow | null>(null);
  const [corrected, setCorrected] = useState<CorrectedReference | null>(null);
  // `CR-135` `P1.6` — the payment a clerk pressed Move or Reapply on. Neither
  // needs a RESULT held beside it the way the reversal does: both services
  // answer with every bill NAMED by number, so nothing has to be joined back
  // to the original row to render the outcome (B14 rule 31).
  const [moving, setMoving] = useState<PaymentRow | null>(null);
  const [reapplying, setReapplying] = useState<PaymentRow | null>(null);

  // ═══════════════════════════════════════════════════════════════════════════
  // CR-059 CS-41 + CS-43 — THE SELECTION AND WHAT IS BEING DONE TO IT
  // ═══════════════════════════════════════════════════════════════════════════
  // The selection is a MAP FROM ID TO ROW, not a list of ids, and that is CS-43:
  // holding the row at tick time is what lets the bar count and total across
  // pages instead of silently shrinking when page two is shown. See
  // `paymentsBulk.tsx`'s own header for the whole reasoning.
  const [selection, setSelection] = useState<PaymentSelection>(EMPTY_SELECTION);
  // Which action a clerk pressed and WHICH ROWS it was aimed at, captured when
  // the modal opens. A retry re-opens the same modal over the failed rows only,
  // so the clerk re-states the reason and the date rather than a run inheriting
  // form values it can no longer show them.
  const [asking, setAsking] = useState<{ action: BulkActionId; targets: PaymentRow[] } | null>(
    null,
  );
  const [run, setRun] = useState<BulkRun | null>(null);
  // One idempotency key per payment, minted once and kept for the life of this
  // mount. A retry MUST carry the key its first attempt carried, or an ambiguous
  // network failure becomes a SECOND refund against the same overpayment.
  const bulkKeys = useRef(new Map<string, string>());

  const cells = paymentsCells(translate, tenantPath, timeZone, dateFormat);
  const baseConfig = paymentsTableConfig(
    translate,
    cells,
    {
      reasonFor: (row) => reverseBlockedReason(row, role, translate),
      onReverse: setReversing,
    },
    { onCorrect: setCorrecting },
    {
      // `CR-135` `P1.6` — 2·3f and 2·3g, whose Doors line in the blueprint is
      // *"The row overflow on 2·1, and 2·2"*. This is 2·1.
      move: { onMove: setMoving },
      reapply: { onReapply: setReapplying },
      select: {
        isSelected: (row) => selection.has(row.id),
        onToggle: (row) => setSelection((current) => toggleSelected(current, row)),
      },
      // ⚠ **`CR-059` CS-39's `renderExpanded` USED TO BE DECLARED ON `config`
      // BELOW AND IS GONE (`CR-137-BRC07` `P3.10`).** This note explained why
      // it could not be declared here — the panel needed the tenant's `CHAR(3)`
      // and only the list response carries it — and that reasoning outlived the
      // panel by one commit. The detail is a PAGE now and reads its own
      // currency off `GET /payments/{id}`.
      scope: props.accountId === undefined ? "all" : "account",
    },
  );
  const extraFilters: Record<string, string> =
    props.accountId === undefined ? {} : { account_id: props.accountId };
  const params = paymentsParamsFrom(props.state, extraFilters);
  const listQuery = useQuery({
    queryKey: paymentsQueryKey(
      `${serializeTableParams(props.state, baseConfig).toString()}|${props.accountId ?? ""}`,
    ),
    queryFn: () => getPayments(params, client),
    // A missing route is not a flaky network: retrying a 404 three times only
    // delays the honest answer.
    retry: false,
  });

  const rows = listQuery.data?.results ?? [];
  const failed = listQuery.isError && listQuery.data === undefined;
  const routeAbsent = failed && listRouteAbsent(listQuery.error);
  // The tenant's CHAR(3), off the SAME response as the rows — the one place this
  // screen can learn it (BR-TEN-042). Null renders a stated absence, never a
  // guess, wherever money is drawn.
  const currency = paymentsDisplayCurrency(listQuery.data);

  // CR-059 CS-43. A selection outlives a page, a sort and a refetch, so a held
  // row can be older than what the server would answer today. Re-snapshotting
  // every selected row that comes back on THIS page costs nothing and closes
  // that gap for every row a clerk can see; a row on another page keeps the
  // figures it was ticked with, which is what `selectionTotal` sums and what
  // the server's own selection total will replace when it lands.
  const loadedRows = listQuery.data?.results;
  useEffect(() => {
    if (loadedRows === undefined) {
      return;
    }
    setSelection((current) => refreshSelection(current, loadedRows));
  }, [loadedRows]);

  // CR-059 CS-43 — THE SELECTION TOTAL IS READ FROM THE SERVER.
  //
  // ⚠ **IT IS NOT A BROWSER SUM, AND THAT IS TWO SEPARATE RULES.** The
  // first is CS-43's own: the list is paginated in the database, so whatever the
  // browser is holding is one page. The second is CS-35's, and it is the one
  // that decides the arithmetic: the figure is the day's CASH and EXCLUDES
  // credits and adjustments — *"or it will not tie to the drawer"* — so a sum of
  // every ticked row would put a goodwill credit into a total a clerk is about
  // to press Refund on. `selectors.selection_total` applies `payments_totals`'
  // rules to ids instead of a filter, deliberately, so this screen cannot hold
  // two answers to one question (hard-won law 5).
  //
  // Keyed on the SORTED ids, so ticking A then B and B then A is one cache entry
  // and not two requests for one figure. Disabled on an empty selection: the bar
  // is not drawn then, and asking for the total of nothing is a round trip whose
  // answer nobody reads.
  const selectedIds = [...selection.keys()];
  const selectionTotalQuery = useQuery({
    queryKey: selectionTotalKey(selectedIds),
    queryFn: () => getSelectionTotal(selectedIds, client),
    enabled: selectedIds.length > 0,
    // A missing route is not a flaky network, and the bar states the absence.
    retry: false,
  });

  // The method vocabulary rides on the SAME response as the rows, so the filter
  // can never offer a method the list does not know about.
  const config: TableConfig<PaymentRow> = {
    ...baseConfig,
    // ⚠ **THE ROWS GO IN TOO (`P2.8` ③).** Hard-won law 2: the batch filter's
    // options come off the SAME response that renders the Batch column, so the
    // filter can never offer a batch the list does not know about — which is
    // the reasoning the `methods` argument beside it already records.
    filters: paymentsFilters(
      translate,
      listQuery.data?.methods ?? [],
      dateFormat,
      listQuery.data?.results ?? [],
    ),
    // ⚠ **THE ROW PANEL IS GONE — `CR-137-BRC07` `P3.10`, 2026-09-23.**
    // `CS-39` asked for *"a clerk clicks PMT-2608-000412 and lands on a PAGE
    // for that payment"*, and until `P3.1` there was no `GET /payments/{id}`
    // and no route, so the row opened where it sat through `renderExpanded`.
    // **Both exist now**, so the honest shape is the page: an expansion has no
    // address, cannot be linked, bookmarked or returned to after a refresh, and
    // leaving BOTH would give the product two answers to one question — which
    // is how a figure starts to drift (p036's own words).
    //
    // The eleven facts and the two-column bill table are KEPT EXACTLY and live
    // in `paymentDetailShared.tsx`; the 👁 row action above is the door.
    // `P3.17` asserts the panel's absence AND the page's presence in one test,
    // so the swap cannot half-land.
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // CR-059 CS-41 — THE RUN. N ROWS ARE N SEQUENTIAL CALLS AND NONE OF THEM IS
  // ALLOWED TO END THE OTHERS.
  // ═══════════════════════════════════════════════════════════════════════════
  // Read `paymentsBulk.tsx`'s header before changing anything here. The four
  // properties this function exists to hold: the calls are SEQUENTIAL, a failure
  // is RECORDED and the loop CONTINUES, every row ends with its OWN verdict, and
  // afterwards the SUCCESSES ARE DESELECTED while the FAILURES STAY SELECTED so
  // a second press retries only what did not happen. That last one is a money
  // rule, not a nicety: a second refund raised over a first is money out twice.
  // Q4 (PO 2026-10-30, `DEF-PAY-10747`) — Send receipts and Reapply collect
  // nothing from the clerk, so they run straight from the bar: no modal, the
  // same per-row run and the same result panel as Reverse and Refund. A retry
  // re-runs only the failed rows, and both acts are safe to repeat (a waiting
  // receipt answers "waiting"; held credit already moved answers "nothing to
  // reapply").
  function runDirect(action: "receipts" | "reapply", targets: readonly PaymentRow[]) {
    if (action === "receipts") {
      void runBulk(
        "receipts",
        targets,
        (row) => bulkReceiptRefusal(row, translate),
        (row) => receiptOne(row, client),
      );
      return;
    }
    const onDate = todayInZone(timeZone);
    void runBulk(
      "reapply",
      targets,
      (row) => bulkReapplyRefusal(row, translate),
      (row) => reapplyOne(row, onDate, client),
    );
  }

  async function runBulk(
    action: BulkActionId,
    targets: readonly PaymentRow[],
    refusalFor: (row: PaymentRow) => string | null,
    call: (row: PaymentRow) => Promise<string | null | void>,
  ): Promise<void> {
    const started: BulkRun = { action, total: targets.length, outcomes: [], running: true };
    setRun(started);
    const outcomes: PerRowOutcome[] = [];
    await runPerRow(
      targets,
      refusalFor,
      (row) => rowLabel(row, translate),
      call,
      (error) => bulkFailureText(error, translate),
      (outcome) => {
        outcomes.push(outcome);
        // A new object every time, so the progress a clerk watches is the
        // progress the loop is actually making rather than a count that appears
        // when the whole run is over.
        setRun({ action, total: targets.length, outcomes: [...outcomes], running: true });
      },
    );
    const finished: BulkRun = { action, total: targets.length, outcomes, running: false };
    setRun(finished);
    const done = succeededIds(finished);
    if (done.length > 0) {
      setSelection((current) => deselectMany(current, done));
      // Money moved (a reversal writes new rows; a refund raises a row the
      // queue shows), so every payments read on this page is stale.
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
      fireToast(t("payments.bulk.toast", { count: done.length }));
    }
  }

  return (
    <>
      {routeAbsent && (
        <ArrivesWith
          title={t("payments.list.awaits.endpointTitle")}
          message={t("payments.list.awaits.endpoint")}
        />
      )}
      {reversed !== null && (
        <ReversedPaymentPanel
          result={reversed.result}
          original={reversed.original}
          onDismiss={() => setReversed(null)}
        />
      )}
      {corrected !== null && (
        <CorrectedReferencePanel result={corrected} onDismiss={() => setCorrected(null)} />
      )}
      {/* CR-059 CS-41's bar and CS-43's figure. It appears only with a
          selection, exactly as S34's does, and it sits OUTSIDE the table rather
          than in `downloadSlot` — G43 clause (c) refuses a control placed there,
          and DEF-1085 is what that clause is made of. */}
      {selection.size > 0 && (
        <PaymentsBulkBar
          selection={selection}
          role={role}
          currency={currency}
          // `undefined` while the read is in flight or after it failed. The bar
          // says it has no total rather than substituting a browser sum, which
          // would be a different figure under the same label.
          total={selectionTotalQuery.data}
          running={run !== null && run.running ? run.action : null}
          progress={
            run !== null && run.running
              ? { done: run.outcomes.length, total: run.total }
              : null
          }
          onClear={() => setSelection(EMPTY_SELECTION)}
          onReverse={() =>
            setAsking({ action: "reverse", targets: [...selection.values()] })
          }
          onRefund={() => setAsking({ action: "refund", targets: [...selection.values()] })}
          onSendReceipts={() => runDirect("receipts", [...selection.values()])}
          onReapply={() => runDirect("reapply", [...selection.values()])}
        />
      )}
      {run !== null && !run.running && (
        <BulkRunPanel
          run={run}
          refundsHref={tenantPath(REFUNDS_ROUTE)}
          onRetry={
            failedRows(run, selection).length === 0
              ? null
              : run.action === "receipts" || run.action === "reapply"
                ? () => runDirect(run.action as "receipts" | "reapply", failedRows(run, selection))
                : () => setAsking({ action: run.action, targets: failedRows(run, selection) })
          }
          onDismiss={() => setRun(null)}
        />
      )}
      <DataTable<PaymentRow>
        config={config}
        state={props.state}
        onStateChange={props.onStateChange}
        rows={rows}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          failed
            ? {
                reason: paymentsFailureReason(listQuery.error, translate),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar
            filters={config.filters ?? []}
            state={props.state}
            onStateChange={props.onStateChange}
          />
        }
        // No `downloadSlot`: `POST /exports` registers no `payments` resource,
        // and BR-SHL-010 keeps an undeclared capability unrendered.
        empty={{
          title: t("payments.list.emptyTitle"),
          helper: t("payments.list.emptyHelper"),
          ctaLabel: t("payments.action.record"),
          ctaReason: props.emptyCtaReason,
          onCta: props.onEmptyCta,
        }}
      />
      {reversing !== null && (
        <ReversePaymentModal
          client={client}
          payment={reversing}
          dateFormat={dateFormat}
          onClose={() => setReversing(null)}
          onReversed={(result) => {
            setReversed({ result, original: reversing });
            setReversing(null);
            // A REPLAY is not a second bounce and must not be toasted as one:
            // the door answers 200 with the FIRST reversal and `created: false`,
            // which is the right answer to a double click and the wrong thing
            // to congratulate somebody for.
            fireToast(
              result.created
                ? t("payments.reverse.toast", {
                    number: result.payment_no ?? t("payments.row.noNumber"),
                  })
                : t("payments.reverse.replay"),
            );
            // The bills re-opened and a new negative row exists, so every
            // payments read on this page is now stale.
            void queryClient.invalidateQueries({ queryKey: ["payments"] });
          }}
        />
      )}
      {correcting !== null && (
        <CorrectReferenceModal
          client={client}
          payment={correcting}
          // The SAME list the filter and the Record form read, off the SAME
          // response as the rows (BR-PAY-026), so a correction can never offer
          // a tender the list does not know about.
          methods={listQuery.data?.methods ?? []}
          onClose={() => setCorrecting(null)}
          onCorrected={(result) => {
            setCorrected(result);
            setCorrecting(null);
            fireToast(
              t("payments.correct.toast", {
                number: result.payment_no ?? t("payments.row.noNumber"),
              }),
            );
            // The reference, memo or tender on a row in this list has moved, so
            // every payments read on this page is stale. NO money moved — this
            // path posts nothing to the ledger — so nothing else is invalidated.
            void queryClient.invalidateQueries({ queryKey: ["payments"] });
          }}
        />
      )}
      {/* `CR-135` `P1.6` — 2·3f. The move writes a reversal on the source and a
          new payment on the destination, so BOTH accounts' positions move and
          every payments read on this page is stale afterwards. */}
      {moving !== null && (
        <MovePaymentModal
          client={client}
          payment={moving}
          timeZone={timeZone}
          onClose={() => setMoving(null)}
          onMoved={(result) => {
            setMoving(null);
            // A REPLAY answers 200 with the FIRST move and `created: false` —
            // the same shape the reversal door has, and for the same reason: a
            // double click is not a second move and must not be toasted as one.
            fireToast(
              result.created
                ? t("payments.move.toast", {
                    number:
                      result.moved_payment_no ??
                      result.destination_payment_no ??
                      t("payments.row.noNumber"),
                  })
                : t("payments.move.replay"),
            );
            void queryClient.invalidateQueries({ queryKey: ["payments"] });
          }}
        />
      )}
      {/* `CR-135` `P1.6` — 2·3g. NOTHING is posted to the ledger: the cash total
          did not change, only which bill it met, so a reapply that posted would
          double-count the money. Only the payments reads are invalidated. */}
      {reapplying !== null && (
        <ReapplyPaymentModal
          client={client}
          payment={reapplying}
          timeZone={timeZone}
          onClose={() => setReapplying(null)}
          onReapplied={(result) => {
            setReapplying(null);
            fireToast(
              t("payments.reapply.toast", {
                number: result.payment_no ?? t("payments.row.noNumber"),
              }),
            );
            void queryClient.invalidateQueries({ queryKey: ["payments"] });
          }}
        />
      )}
      {/* CR-059 CS-41 — what a run needs before it can send anything. Each modal
          collects ONE set of values for the whole run and closes; the run then
          happens on the page, because its outcomes are per row and a modal can
          show one error (`BulkRunPanel` is where they land). */}
      {asking !== null && asking.action === "reverse" && (
        <BulkReverseModal
          // `P1.8` — the ROWS, not a count. The confirm computes its own split
          // with the same predicate the run below uses, so the figure in the
          // button is the figure that will run.
          rows={asking.targets}
          role={role}
          currency={currency}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setAsking(null)}
          onConfirm={(values) => {
            const targets = asking.targets;
            setAsking(null);
            void runBulk(
              "reverse",
              targets,
              (row) => bulkReverseRefusal(row, role, translate),
              (row) =>
                reverseOne(row, values, keyFor(bulkKeys.current, row.id), client),
            );
          }}
        />
      )}
      {asking !== null && asking.action === "refund" && (
        <BulkRefundModal
          rows={asking.targets}
          currency={currency}
          dateFormat={dateFormat}
          onClose={() => setAsking(null)}
          onConfirm={(values) => {
            const targets = asking.targets;
            setAsking(null);
            void runBulk(
              "refund",
              targets,
              (row) => bulkRefundRefusal(row, translate),
              (row) =>
                refundOne(
                  row,
                  values.method,
                  values.requestedAt,
                  keyFor(bulkKeys.current, row.id),
                  client,
                ),
            );
          }}
        />
      )}
    </>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface PaymentsPageProps extends RegionalProps {
  client?: ApiClient; // test seam
  /** BR-PAY-033's pre-filled posting date, injected so tests are deterministic
   *  and so the tenant-timezone "today" can replace the browser's when
   *  US-SHL-013's formatting service lands. */
  today?: string;
}

export function PaymentsPage(props: PaymentsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  // ⚠ **THE RESULT ARRIVES FROM THE PAGE, IN ROUTER STATE — `DEF-PAY-6317`.**
  // `RecordPaymentPanel` below is what a clerk reads after a payment lands:
  // the number, the amount, what it met, what carried as credit and whether it
  // reached the books. It used to be set by the modal that sat on this screen.
  // 2·3a is a PAGE now (p037), so the write happens at another address and the
  // panel would have had NO CALLER — dead UI over a live component, which is
  // hard-won law 2 in the direction `G13` cannot see.
  //
  // So the page hands the result back through `navigate(..., { state })`, this
  // reads it once into its own state, and the entry is CLEARED from history so
  // a refresh or a Back does not replay a panel about a payment recorded ten
  // minutes ago.
  const location = useLocation();
  const handoff = (location.state as { recordedPayment?: RecordedPayment } | null) ?? null;
  const [recorded, setRecorded] = useState<RecordedPayment | null>(
    handoff?.recordedPayment ?? null,
  );
  useEffect(() => {
    if (handoff?.recordedPayment !== undefined) {
      // `replace` so Back goes where the clerk came from, not onto a stale
      // result. The panel is already in state by now.
      navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
    }
    // The handoff is consumed exactly once, on the render that carries it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handoff?.recordedPayment]);
  // ⚠ HOISTED ABOVE THE `asOf` STATE ON 2026-09-22 (`P0.7`) AND THE ORDER IS
  // THE POINT: the day this screen PROPOSES is now read from the tenant's own
  // zone, so the zone has to be resolved before the state that uses it.
  // `useRegional` is a hook, so it stays unconditional and at the top — moving
  // it changes the order of the hook calls, not whether they all run.
  const { timeZone, dateFormat } = useRegional(props);
  // BR-TEN-043 / the payments README's first rule: `as_of` is REQUIRED on both
  // read-models and is NOT defaulted silently in the client. A day is PROPOSED
  // here — exactly as the Record form proposes its posting date — and each tab
  // shows the field, so a clerk reconciling yesterday asks for yesterday. The
  // API deliberately holds no clock at all (BR-TEN-043).
  //
  // ⚠ **THIS COMMENT SAID *"the browser's day"* AND CITED `OQ-153`/`DEF-082`
  // AS OPEN UNTIL 2026-09-22, AND BOTH HALVES WERE STALE.** `OQ-153` is CLOSED
  // — *midnight in the utility's own timezone*, PO 2026-08-12 — and `DEF-082`
  // shipped the control that made choosing a zone possible on 2026-08-15. What
  // is proposed is now the TENANT's day (`todayInZone`), which is the same
  // source `DateCell` renders an instant in, so the day a clerk is offered and
  // the day they read back afterwards cannot disagree.
  const [asOf, setAsOf] = useState(props.today ?? todayInZone(timeZone));

  const active = paymentsTabFrom(routeParams.tab);
  const cell = useAccessCell(PAYMENTS_PERMISSION, client);
  // `CR-140-BRC07` — the Debtors head's *Write-offs* door opens Revenue & AR,
  // which gates on A4's Finance cell. Read here, unconditionally, because it is
  // a hook; it shares `/me/permissions` with the line above, so it costs no
  // request.
  const financeCell = useAccessCell(FINANCE_PERMISSION, client);
  // BR-SHL-025: "Full" writes; anything else renders the control disabled WITH
  // the reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("payments.rbac.readOnly");

  const config = paymentsTableConfig(
    translate,
    paymentsCells(translate, tenantPath, "UTC", "MM/DD/YYYY"),
  );
  const state = parseTableParams(searchParams, config);
  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }

  // The method vocabulary the Record form offers comes from the SAME list
  // response the table renders, so the form can never propose a method the
  // ledger has retired (BR-PAY-026).
  //
  // It runs on ALL THREE TABS now, and the second reason is the awkward one:
  // `GET /outstandings` and `GET /payments/summary` serve every amount with NO
  // CHAR(3) currency code, and `MoneyCell` cannot render one without it. This
  // response carries the tenant's own code (`totals.currency`, and a `currency`
  // on every row) under BR-TEN-042's one-currency lock, so S32 and S34 read it
  // from here rather than assuming USD — which would print a wrong symbol on a
  // Canadian tenant's books. REPORTED: the honest fix is a `currency` member on
  // both read-model bodies, which is a backend change this lane may not make.
  const listQuery = useQuery({
    queryKey: paymentsQueryKey(`${serializeTableParams(state, config).toString()}|`),
    queryFn: () => getPayments(paymentsParamsFrom(state), client),
    retry: false,
  });
  const currency = paymentsDisplayCurrency(listQuery.data);

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("payments.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (listQuery.isError && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  return (
    <div className="pay-page">
      {/* US-SHL-020 / BR-SHL-044: this screen DECLARES a header, it does not
          draw one. The prototype's Payments head is an H1 plus its roll-up
          `.sub`, its page actions and the three-tab strip. */}
      <PageHeader
        // ⚠ **THE IMPORTS TAB CARRIES ITS OWN HEAD, AND ONLY THAT TAB.** §03
        // frame 4·1 draws the head as `PAYMENTS › IMPORTS` over **Imports**,
        // where 2·1, 2·1b and 7·1 all draw plain **Payments** with no kicker.
        // Read off the rendered page at 2.0 rather than off the task table's
        // prose (B14 rule 42). Nothing else on this page moves: the tab had no
        // screen at all until this commit, so this is not a head a clerk has
        // seen say something else.
        // ⚠ **THE COUNTER TAB CARRIES ITS OWN HEAD TOO (`CR-136-BRC07`
        // `P2.6`).** §03 frame 3·1 draws `PAYMENTS › COUNTERS` over
        // **Counters**, exactly as 4·1 draws it over **Imports** — read off
        // the rendered page at 2.0 rather than off the task table's prose
        // (B14 rule 42). 2·1, 2·1b and 7·1 still draw plain **Payments** with
        // no kicker and none of them moves.
        title={
          active === PAYMENTS_TAB_IMPORTS
            ? t("payments.imports.title")
            : active === PAYMENTS_TAB_COUNTER
              ? t("payments.counter.list.title")
              : t("payments.title")
        }
        kicker={
          active === PAYMENTS_TAB_IMPORTS
            ? t("payments.imports.kicker")
            : active === PAYMENTS_TAB_COUNTER
              ? t("payments.counter.list.kicker")
              : undefined
        }
        rollup={
          active === PAYMENTS_TAB_RECORD ? (
            <PaymentsTotalsLine totals={listQuery.data?.totals} t={translate} />
          ) : undefined
        }
        primaryAction={
          active === PAYMENTS_TAB_RECORD ? (
            // ⚠ **AN ADDRESS, NOT A HANDLER — `DEF-PAY-6317` + `DEF-CWP-3925`.**
            // This opened `RecordPaymentModal` over the list until 2026-09-23;
            // 2·3a's agreed form is a PAGE (p037), so the door navigates. A
            // control whose destination is a closure carries nothing a test can
            // assert, which is how the portal shipped six doors onto the wrong
            // screens — so the way IN is a `ButtonLink` with a `to`.
            //
            // BR-SHL-025 still decides whether there IS a way in: a deployment
            // that cannot write payments keeps the button and disables it WITH
            // ITS REASON, which is what `GuardedButton` is for. Only the
            // allowed branch becomes a link.
            writeBlockedReason === null ? (
              <ButtonLink
                variant="primary"
                to={tenantPath(PAYMENTS_RECORD_NEW_ROUTE)}
                data-record-door="head"
              >
                {t("payments.action.record")}
              </ButtonLink>
            ) : (
              <GuardedButton
                label={t("payments.action.record")}
                reason={writeBlockedReason}
                variant="primary"
                onClick={() => undefined}
              />
            )
          ) : active === PAYMENTS_TAB_COUNTER ? (
            // ⚠ **3·1's OWN PRIMARY ACTION, AND ONLY THIS TAB'S.** p052:
            // *"Primary action: **Start counter →** — it navigates, so B14
            // rule 4 gives it the arrow"*. Putting the same control on the
            // OTHER SIX payments screens is `P2.7` and is a different task; it
            // reuses this address rather than growing a second handler.
            //
            // A `ButtonLink` and not an `onClick` for `DEF-CWP-3925`'s reason:
            // a handler carries no address, so the one assertion that could
            // catch this door breaking cannot be written.
            // ⚠ **TWO STATES, AND THE SECOND IS THE ONE THAT GETS LOST.**
            // 2·1 ①: *"when your counter is already open this same slot reads
            // `Your counter · CTR-260921-DW · open` and is the door back to
            // it"*. A slot that always says *Start counter →* offers an act
            // `uq_counter_sessions_open_owner` will refuse.
            <CounterHeadSlot
              variant="primary"
              client={client}
              dateFormat={dateFormat}
              writeBlockedReason={writeBlockedReason}
            />
          ) : active === PAYMENTS_TAB_IMPORTS ? (
            // ⚠ **ONE DOOR, AND IT IS AN ADDRESS.** 4·1's own row reads
            // *"Doors: The Imports tab. **1 door.**"* and its note ① —
            // *"Import → · **one door, not two**"* — records that a second
            // `Scan` button stood beside it until 2026-09-22 and came OFF:
            // a sack of cheques is a SOURCE CARD on Extract, not a second
            // pipeline, so removing it takes a screen away rather than adding
            // one. A `ButtonLink` and not an `onClick` for `DEF-CWP-3925`'s
            // reason: a handler carries no address, so the one assertion that
            // could catch this door breaking cannot be written.
            writeBlockedReason === null ? (
              <ButtonLink variant="primary" to={tenantPath(PAYMENTS_IMPORT_NEW_ROUTE)}>
                {t("payments.imports.action.import")}
              </ButtonLink>
            ) : (
              <GuardedButton
                label={t("payments.imports.action.import")}
                reason={writeBlockedReason}
                variant="primary"
                onClick={() => undefined}
              />
            )
          ) : undefined
        }
        // ⚠ **`P0.8`/`P0.9` — THE DOOR IS THE TAB'S OWN `path`, NOT ITS ID.**
        // The sidebar renders no submenus (PO 2026-08-10), so a payments tab is
        // reachable ONLY from this strip; two of the seven do not live under
        // `/payments` at all, and deriving the address from the id sent Refunds
        // to `/payments/refunds`, which nothing mounts.
        //
        // ⚠ **THE LADDER'S DOOR IS BELOW, ON THE DEBTORS TAB.** Its tab left the
        // strip with the drawing and its screen did not, and a live screen with
        // no door is the defect `P0.9`'s outcome exists to prevent.
        // ⚠ **A `ButtonLink` AND NOT A `Button` WITH AN `onClick`, DELIBERATELY.**
        // A click handler carries no address, so the one assertion that could
        // catch this door breaking cannot be written — which is precisely how
        // `DEF-CWP-3925` cost the customer portal six of its eight doors. This
        // renders an `<a href>` that `sevenTabs.dom.test.tsx` reads.
        // ⚠ **`P2.7` — THE COUNTER SLOT ON EVERY PAYMENTS SCREEN.** 2·1 ①
        // calls it *"NEW — AND IT WAS MISSING ENTIRELY"*, and draws it to the
        // LEFT of `Record payment`, which is what `secondaryActions` is. The
        // Counter tab carries it as its own PRIMARY instead (3·1 draws it
        // alone there), so it is not drawn twice on one head.
        secondaryActions={
          <>
            {active !== PAYMENTS_TAB_COUNTER && (
              <CounterHeadSlot
                client={client}
                dateFormat={dateFormat}
                writeBlockedReason={writeBlockedReason}
              />
            )}
            {active === PAYMENTS_TAB_OUTSTANDINGS && (
              <ButtonLink variant="secondary" to={tenantPath(COLLECTIONS_LADDER_ROUTE)}>
                {t("payments.tab.collections")}
              </ButtonLink>
            )}
            {/* ⚠ **`CR-140-BRC07` — ONE MORE DOOR TO THE ONE QUEUE.** PO
                2026-09-23, verbatim: *"3 Add a Write-offs link on the Debtors
                tab? (b) add it - fix it"* (`OQ-PAY-12613`). The only way out
                of payments to the approval queue was the panel
                `OutstandingsTab` draws AFTER a request is made, so a clerk
                checking on Monday's $1,202.40 on Tuesday had nothing to press.
                This departs from blueprint 7·3b's *"1 door"* by that ruling.

                **`financeTabPath`, never a literal** — it is the one place that
                decides where a Finance tab lives, and the result panel's door
                (`DEF-PAY-6329`) goes through it too, so the two cannot drift
                apart. **It is NOT `/finance/write-offs`**: that route and its
                page were deleted on purpose (`CR-135` P1.10) and a second door
                must never become a second queue.

                ⚠ **NOT DRAWN WHERE IT WOULD OPEN A REFUSAL.** Revenue & AR
                gates on `finance_reconcile_export`, which A4 gives a System
                Admin and an Executive and NOT a Billing Clerk — for a clerk
                this link would open *"Permission denied"*, a dead door onto a
                live screen. `BR-SHL-003` hides navigation into a module a role
                cannot reach; a null cell (not answered yet) hides nothing
                (`BR-SHL-025`). `writeOffsHeadDoor.dom.test.tsx` asserts the
                destination by address, screen id and mounted component, and
                all three visibility states. */}
            {active === PAYMENTS_TAB_OUTSTANDINGS && !isDenied(financeCell) && (
              <ButtonLink variant="secondary" to={tenantPath(financeTabPath(FINANCE_TAB_REVENUE))}>
                {t("payments.outstandings.writeOffs")}
              </ButtonLink>
            )}
          </>
        }
        tabs={PAYMENTS_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId={active}
        tabsLabel={t("payments.tabsLabel")}
        onTabSelect={(tab) => navigate(tenantPath(paymentsTabPath(tab.id)))}
      />

      {active === PAYMENTS_TAB_RECORD ? (
        <>
          {recorded !== null && (
            <RecordPaymentPanel recorded={recorded} onDismiss={() => setRecorded(null)} />
          )}
          <PaymentsTable
            client={client}
            state={state}
            onStateChange={setState}
            emptyCtaReason={writeBlockedReason}
            // The list's own empty state opens the same page (`DEF-PAY-6317`).
            onEmptyCta={() => navigate(tenantPath(PAYMENTS_RECORD_NEW_ROUTE))}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
          {/* Hard-won law 2, stated rather than hidden: what the prototype
              draws on this tab, what this screen cannot serve yet, and what
              each of them is waiting for.

              ⚠ THE *ROW AND BULK ACTIONS* PANEL WAS DELETED HERE (DEF-3030,
              2026-09-01) AND MUST NOT COME BACK IN THAT FORM. It told a clerk
              in eleven languages that reversing a payment and issuing a refund
              *"are not built"* and that two decisions *"the Product Owner has
              not made yet"* were open. All three clauses were false by the time
              a clerk read them: `POST /payments/{id}/reverse` landed with
              CR-059 task 15 and the Reverse row action above calls it, the
              three refund routes landed with task 17, and the two questions
              were RULED on 2026-08-11 (OQ-132) and 2026-08-12 (OQ-133). It
              would have sat on the same page as the Reverse control,
              contradicting it.

              The lesson is the panel's SHAPE, not its sentences: an absence
              claim that names no route rots silently every time a backend lane
              opens a door, and no gate in this repo reads rendered output. The
              two panels left both name what they wait for.

              ⚠ AND THEY ARE CLOSED SINCE 2026-09-03 (B14 rule 32). The PO, of
              exactly these two panels: *"why this content on this screen"*.
              Both are still here, still in the DOM, still counted by G38 —
              `ArrivesWith` and its `tracks` attribute are untouched, because
              G38 reads the CALL SITE and the expiry mechanism is the thing that
              must not be lost. What changed is that a clerk recording a cheque
              no longer reads two paragraphs about a lockbox importer and a
              filter bar before they get to the list. */}
          <details>
            <summary className="field-help">{t("payments.list.awaits.moreAbout")}</summary>
            <div className="pay-awaiting-grid">
              {/* ⛔ **THE DATE-RANGE PANEL IS GONE, AND ITS KEYS ARE DELETED
                  FROM ALL ELEVEN CATALOGUES RATHER THAN LEFT AS DEAD ENTRIES
                  (CR-059 CS-40 · `DEF-3504`).** It said the list *"already
                  answers a posted-date range and a cleared-date range, and this
                  page cannot yet offer them"*. It can now — the two ranges are
                  declared in `paymentsFilters` and draw in the same `+ Filter ▾`
                  panel as every other one. A screen claiming an absence is not
                  the absence (hard-won law 1, pointed the other way), and this
                  is the same removal the reverse/refund panel got on the day
                  those routes landed: the copy goes, and a test asserts the key
                  no longer resolves so it cannot come back quietly. */}
              <ArrivesWith
                title={t("payments.list.awaits.importTitle")}
                message={t("payments.list.awaits.import")}
              />
            </div>
          </details>
        </>
      ) : PAYMENTS_TABS_AWAITING_A_SCREEN[active] !== undefined ? (
        // ⚠ **`P0.8` — THE THREE TABS PHASE 0 LANDS WITH NO SCREEN, SAYING SO
        // PLAINLY.** PO ruling 2026-09-22, verbatim: *"go as per phase 0 ; we
        // are going to implement all phases one by one so fcus on current
        // one."* Three options were put — add each tab when its screen lands,
        // all seven with the three saying plainly that they are not built, all
        // seven with three greyed out. The second was chosen.
        //
        // The copy is a stated absence and nothing more (B14 rules 32 and 33):
        // a fact of at most six words, then one six-word sentence naming what
        // will arrive here. No rule id, no phase number, no reasoning — that is
        // what `data-tracks` and this comment are for.
        // ⚠ **THE FALLBACKS ARE NOT DECORATION — WITHOUT THEM THIS BRANCH
        // SHOWS A CLERK A DOTTED CODE (`G112`, 2026-09-23).** The keys are
        // COMPUTED from the tab id, so no catalogue can hold them in advance:
        // `payments.awaits.` names nothing in `en.json` today, and i18next
        // returns the key itself when it cannot resolve one. Today that is
        // harmless — `PAYMENTS_TABS_AWAITING_A_SCREEN` is EMPTY, every hold
        // having expired with its screen — but the map is deliberately kept
        // for the next tab that ships without one, and the day it is used is
        // the day a raw key would reach a screen. **A fallback is what makes
        // a mechanism safe to use again**, which is the opposite of parking
        // the gap and letting it rot.
        //
        // The generic wording is the honest one: the specific tab's name is
        // already in the tab strip above it, and B14 rule 33 caps a fact at
        // six words. A tab that wants better words adds its own keys.
        <ArrivesWith
          title={t(`payments.awaits.${active}Title`, {
            defaultValue: t("payments.awaits.fallbackTitle"),
          })}
          message={t(`payments.awaits.${active}`, {
            defaultValue: t("payments.awaits.fallback"),
          })}
          tracks={PAYMENTS_TABS_AWAITING_A_SCREEN[active]}
        />
      ) : active === PAYMENTS_TAB_COUNTER ? (
        // `PAY-04` / 3·1 (`CR-136-BRC07` `P2.6`) — the supervisor's list of
        // every till, open and closed, and the four acts on it. Until this
        // commit the tab rendered a stated absence over a `counter_sessions`
        // table that nothing wrote.
        <CountersTab
          client={client}
          // ⛔ **`DEF-PAY-6226`'s TYPE HALF — `tsc` HAS BEEN RED ON THIS BRANCH
          // FOR THESE TWO LINES (TS2322, twice).** `PaymentsPageProps extends
          // RegionalProps`, where both are OPTIONAL; `CountersTab` declares
          // both required. The RESOLVED pair has been in scope since the top of
          // this component — `const { timeZone, dateFormat } = useRegional(props)`
          // — and is what every other call site on this page already passes.
          // Two identifiers, and it blocks every lane's type check.
          timeZone={timeZone}
          dateFormat={dateFormat}
          writeBlockedReason={writeBlockedReason}
          onOpenCounter={(code) => navigate(tenantPath(counterRoute(code)))}
        />
      ) : active === PAYMENTS_TAB_IMPORTS ? (
        // S35 (`CR-135` `P1.5`) — 4·1 *Batches*, the lockbox and store-collected
        // run history. The body is `components/workflow/ImportRunsList`, which
        // is the list premises, assets and accounts have each been drawing
        // their own copy of; payments is its fourth caller and its second
        // mount. The ONE door onto the runner is the header button above.
        <PaymentsImportsTab
          client={client}
          writeBlockedReason={writeBlockedReason}
          onImport={() => navigate(tenantPath(PAYMENTS_IMPORT_NEW_ROUTE))}
        />
      ) : active === PAYMENTS_TAB_SETTLEMENTS ? (
        // 5·1 (`CR-139-BRC07` `P5.7`) — *"The bank shows one credit. Which
        // payments is it?"*. Until this commit the tab rendered a stated
        // absence, correctly: there was no table, no feed and no endpoint.
        // `payments/0038`–`0039` landed the two tables and `P5.9` the feed;
        // the read landed with this screen (`DEF-PAY-6286`).
        //
        // ⚠ **NO `writeBlockedReason` IS PASSED, AND THAT IS NOT AN OMISSION.**
        // p070's *Primary action* row reads *"None — this is a read"* and p072
        // spends a whole step on it: a payout has nothing to approve, edit or
        // cancel. A prop for a write this screen does not have would be dead
        // UI pointing the other way.
        <SettlementsTab client={client} timeZone={timeZone} dateFormat={dateFormat} />
      ) : active === PAYMENTS_TAB_SUMMARY ? (
        // S32 (US-PAY-005) — five panels over `GET /payments/summary`. Until
        // this lane the tab rendered an *awaiting* panel over a complete,
        // tested read-model: hard-won law 2 in its purest form.
        <SummaryTab
          client={client}
          asOf={asOf}
          onAsOfChange={setAsOf}
          currency={currency}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          onOpenOutstandings={() => navigate(tenantPath("/payments/outstandings"))}
          // ⚠ **1·1's *Record payment* TILE NOW OPENS THE FORM, NOT THE LIST
          // (`DEF-PAY-6317`).** p030 names *"the Summary tab's **Record
          // payment**"* as one of the list's ten doors, and until 2·3a had an
          // address the best this could do was land the clerk on the table so
          // they could press the head button. It goes straight there now.
          onRecordPayment={() => navigate(tenantPath(PAYMENTS_RECORD_NEW_ROUTE))}
        />
      ) : (
        // S34 (US-PAY-013) — the AR list, its ageing strip and the two bulk
        // actions that have endpoints (US-PAY-012 write-off, US-PAY-014
        // collections run). `paymentsTabFrom` answers one of exactly three
        // values, so there is no fourth branch and no *awaiting* panel left on
        // this page: every tab the sidebar names now lands on a built screen.
        <OutstandingsTab
          client={client}
          asOf={asOf}
          onAsOfChange={setAsOf}
          currency={currency}
          writeBlockedReason={writeBlockedReason}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
    </div>
  );
}

export default PaymentsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-004@0f1a7c3 (story+rules snapshot — EP-PAY-01 US-PAY-004 lead story; co-packet US-PAY-001, same epic; 08-payments/02-business-rules.md; 11b §1 + §2.9)
// generated: 2026-08-11 by story-coder (W4 payments FRONTEND lane — S33 + the S22/S35 Record modal, the screens the payments write path landed without)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ · eslint --max-warnings 0✔ · vitest✔ (RED-PROVED FIRST: "Failed to load url ./PaymentsPage … Does the file exist?") · vite build✔ · run_gates✔ · [2026-08-15 DEF-088 display-precision lane] RED PROVED FIRST — the S30 tax line rendered `<span class="cell-money-amount">$8.2985</span>` and all 6 new assertions failed against the pre-fix formatter (verbatim in the lane report). MEASURED, THIS LANE'S OWN FILES ONLY: MoneyCell.test.tsx 8 tests (was 6) · BillDetailPage.test.tsx 22 tests / 3 skipped (was 20 / 3) · PaymentsPage.test.tsx 17 tests (was 15) — 44 passed / 3 todo across the three, all green. The FULL suite total is deliberately not quoted: a concurrent 07-frontend settings lane was adding files throughout, so no whole-suite number here would be reproducible. tsc --noEmit✔ · eslint --max-warnings 0✔ · vite build✔ · node --test server.test.mjs 10/10✔ · tsc -p tsconfig.e2e.json✔ · run_gates: 20 PASS · 0 FAIL at this lane's 17:55 baseline; the failures present at hand-off are named in the lane report and none is this lane's — no file it touched appears in any of them
// exceptions: (1) NO bulk toolbar and NO row-action menu — every action the prototype offers (Reverse · Reapply · Send receipts · Refund · Post to QuickBooks) is another story's endpoint and none exists; three of them are additionally blocked on unanswered PO decisions (OQ-132..137). A checkbox column selecting rows for nothing is worse than none · (2) NO CSV export: `POST /exports` registers no `payments` resource (BR-SHL-010) · (3) SUPERSEDED 2026-09-03 (CR-059 CS-40 / DEF-3504) — was "NO date-range filters rendered although the server accepts four: the shared FilterBar renders option lists only". The shared FilterBar renders a declared `dateRange` now, and this screen declares two of them — posted and cleared, on the server's own `posted_from`/`posted_to`/`cleared_from`/`cleared_to` params. The awaiting panel that named the absence is deleted from all eleven catalogues rather than left as a dead entry · (4) the Record form drives TWO of BR-PAY-001's four allocation choices; `specific` and `split` render DISABLED with their reason (OQ-154 — no endpoint serves an account's OPEN bill position, and a picker built on `GET /invoices` would show the ISSUED total where the OPEN balance belongs) · (5) SUPERSEDED 2026-08-15 — was "the form sends purpose `bill` only and says so on screen"; `apps/payments/purposes.py` built the deposit, plan-down and prepay linkages and the form now offers all four of BR-PAY-012's purposes · (6) the posting date is pre-filled from the BROWSER's date; the tenant-timezone "today" arrives with US-SHL-013 and the instant a bare date becomes is OQ-153 · (7) no account BALANCE is shown in the Record modal where the prototype shows "Current balance $247.30": `accounts.balance` is customers' CACHED column which this payment does not update (B1/DB-16), so the figure would be stale the moment it mattered
// amended:   2026-08-15 by story-coder (payments FRONTEND visible-half lane) — the S32 and S34 tabs are WIRED (this file rendered an *awaiting* panel over two complete, tested read-models), the record modal gained BR-PAY-012's purpose picker (it sent `bill` and nothing else while `purposes.py` had built all four), and `GET /payments` now runs on all three tabs because it is the only response these screens can read the tenant's CHAR(3) currency off. TWO CLAIMS IN THIS FILE'S OWN DOCSTRING WERE FALSIFIED AND REWRITTEN (hard-won law 1): "No Summary tab and no Outstandings tab", and "why this form sends only `bill`".
// exceptions [2026-08-15]: (8) `GET /outstandings` and `GET /payments/summary` carry NO currency code; the tenant's is read off the payments list (BR-TEN-042's one-currency lock) and a stated absence renders when it cannot be — REPORTED · (9) no tab on this page renders an "arrives with" panel any more, so `payments.arrives.summary` and `payments.arrives.outstandings` were DELETED from all eleven catalogues rather than left as dead keys · (10) `payments.form.purposeNote` was deleted for the same reason and because its sentence had become false
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
