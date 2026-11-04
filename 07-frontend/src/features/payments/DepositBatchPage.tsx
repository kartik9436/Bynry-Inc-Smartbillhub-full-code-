// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-023 (S39 — the header, the four KPI tiles, the payments-in-
//           batch table, the bank-side panel, the reconciliation trail and the
//           BR-PAY-004 lock with Unreconcile as its only reversal) ·
//           US-PAY-022 (S40 — the "Why doesn't this match?" modal: every
//           difference explained with a reason AND a GL, to zero)
//           Screens: S39 · S40
// Rules:    BR-PAY-004 (reconciled batches LOCK; Unreconcile is the only
//           reversal, and it costs a written reason) · BR-PAY-019 (reason AND
//           GL on every difference) · BR-PAY-035 ("Force match anyway"
//           permanently SUPERSEDED — there is no such control here and no
//           request body could express one) · BR-PAY-040 (a card day
//           reconciles NET with the processor's fee as its OWN line to the
//           signed 6800 Bank fees) · BR-PAY-002 (nothing is edited in place) ·
//           BR-SHL-020 · BR-SHL-023 · BR-SHL-025 · BR-SHL-044
// ───────────────────────────────────────────────────────
// S39 batch detail, and the S40 modal that makes a difference explainable.
//
// ══════════════════════════════════════════════════════════════════════════
// THE MODAL IS WHERE THE PROTOTYPE AND THE SIGNED RULES DISAGREE MOST
// ══════════════════════════════════════════════════════════════════════════
// UtilityBilling.html:5568-5600 draws the modal this screen is built from — the
// three tiles (We recorded / Bank shows / Difference), the member list, the
// likely-explanation card and the audit note. **Four of its controls are not
// here, and each absence is a signed rule rather than an omission:**
//
//   1. **"Force match anyway"** (line 5597). BR-PAY-035 made it PERMANENTLY
//      SUPERSEDED. It is not disabled and not hidden — `reconcile_batch` has no
//      path that accepts a residual, so there is no body this form could POST
//      that would do it. Drawing a disabled button would say the feature exists.
//   2. **The GL picker's account NUMBERS.** The prototype offers "6200 ·
//      Merchant Fees" and "1020 · Undeposited Funds"; **neither is in any
//      signed chart** (DEF-067 — B5 line 74 ❄️ has 1000 Cash, 1010 Undeposited
//      funds and 6800 Bank fees). The fee account arrives from the server BY
//      DESIGNATION (`bank_fees`) and is never typed here; when the tenant has
//      designated none, the form SAYS SO and asks for one rather than guessing.
//   3. **"Add $30.00 NSF fee" / "Notify her by email"** on a member row. The
//      bounce belongs to `apps/payments/reversal.py` and the PO placed it on
//      the PAYMENT (OQ-134, 2026-08-12). The same ruling holds the batch total
//      STILL at $2,840.00 when cheque #4021's $100.00 is returned — a control
//      here would imply the total moves, and it does not (hard rule 4).
//   4. **A "Reconciled ✓" state that is reachable twice.** BR-PAY-004 locks the
//      batch; Resolve disappears and Unreconcile appears, because the service
//      refuses the other one and a control that fails on click is worse than no
//      control (BR-SHL-025).
//
// ══════════════════════════════════════════════════════════════════════════
// THE TIE-OUT IS CHECKED HERE ONLY TO SAVE A ROUND TRIP
// ══════════════════════════════════════════════════════════════════════════
// US-PAY-022 §7: *"Σ reason-coded explanations + Σ member corrections =
// difference, then difference = 0 at reconcile."* The SERVER is the
// enforcement. This form computes the same sum on BigInt over the NUMERIC(18,6)
// grid (never a float — `Number("9758.11") - Number("8154.50")` is
// `1603.6100000000005821`) purely so a clerk sees what is still unexplained
// while typing instead of after submitting. A green tick here is never
// permission.
//
// ⚠ **THAT EXAMPLE USED TO BE THE CARD DAY'S OWN PAIR AND IT DOES NOT
// REPRODUCE** (`DEF-PAY-6650`): `Number("5120.40") - Number("4972.90")` is
// exactly `147.5` on this engine, as is `Number("-172.50") -
// Number("-147.50")`. The conclusion was right and the evidence was not, which
// is hard-won law 1 in a code comment — a worked number nothing re-runs. The
// pair above IS inexact, and `batchLineActions.dom.test.tsx` now asserts both
// halves, so the claim is re-run rather than restated.
import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getDepositBatch,
  reconcileDepositBatch,
  unreconcileDepositBatch,
} from "@/api/bankRecEndpoints";
import type { DepositBatchDetail, DepositBatchMember } from "@/api/bankRecEndpoints";
import { getPaymentDetail } from "@/api/paymentDetailEndpoints";
import { getPayments } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { TrashIcon } from "@/components/icons";
import { RowAction } from "@/components/RowActions";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { isDenied, useAccessCell, useTenantRole } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BANKREC_PERMISSION,
  BankFigure,
  BatchMemberActions,
  DEPOSITS_ROUTE,
  GapNotes,
  bankAbsenceReason,
  batchStatusLabel,
  batchStatusTone,
  amountForInput,
  driftOf,
  explainsTheDifference,
  isZeroAmount,
  residualOf,
  sumOf,
  trailEventLabel,
} from "./depositsShared";
import { paymentDetailRoute } from "./paymentDetailShared";
// `P3.10` reuses the product's OWN money forms rather than drawing a second
// pair here — see the two modals at the foot of this screen for why.
import { CorrectReferenceModal, ReversePaymentModal } from "./PaymentsPage";

import "./payments.css";

export const depositBatchQueryKey = (batchId: string) =>
  ["payments", "deposit-batch", batchId] as const;

/** One row of the S40 form: a reason, a GL account and a SIGNED amount.
 *  The card day's processor fee is `-147.50`, and the sign is the clerk's to
 *  state — the form never flips it, because a difference in the other direction
 *  is an OVERAGE and calling it a fee would post a negative expense over a real
 *  question (the same refusal `derive_processor_fee` makes server-side). */
export interface ResolutionDraft {
  reason_code: string;
  gl_account_id: string;
  amount: string;
  note: string;
}

export const EMPTY_RESOLUTION: ResolutionDraft = {
  // NOTHING DEFAULTS THE REASON. BR-PAY-019 requires one on every difference
  // and a seeded "processor_fee" would put the commonest answer on a cash
  // shortage, a bounced cheque and a bank error alike.
  reason_code: "",
  gl_account_id: "",
  amount: "",
  note: "",
};

/** A signed decimal with a period — the only shape the amount box reads. */
const AMOUNT_SHAPE = /^-?\d+(\.\d+)?$/;
/** …and money is STORED to four places (hard rule 2, PO re-sign 2026-08-22),
 *  so a fifth is refused rather than silently rounded (`DEF-PAY-10704`). It
 *  read `\d{1,6}` — the NUMERIC(18,6) container — until the lockbox audit. */
const AMOUNT_PLACES = /^-?\d+(\.\d{1,4})?$/;

/**
 * The sentence the amount box carries for what is typed in it NOW, or
 * `undefined` when it reads — `LBX-02` (`DEF-PAY-10704`).
 *
 * Shown as the clerk types rather than on the press, because the press is the
 * one thing this form withholds until the residual is $0.00 (p055): an
 * unreadable amount makes the residual unknown, which keeps `Record ✓` shut,
 * so a refusal that waited for the press would never be seen at all. `"1,5"`
 * is neither 1.5 nor 15 — it is refused and counted as nothing.
 */
export function amountProblem(value: string, t: Translator): string | undefined {
  const text = value.trim();
  if (text === "") {
    return undefined; // a row still being filled in, not a wrong one
  }
  if (!AMOUNT_SHAPE.test(text)) {
    return t("payments.deposits.form.amountInvalid");
  }
  if (!AMOUNT_PLACES.test(text)) {
    return t("payments.deposits.form.amountPlaces");
  }
  return undefined;
}

export function resolutionSchema(t: Translator) {
  return z.object({
    reason_code: z.string().min(1, t("payments.deposits.form.reasonRequired")),
    // BR-PAY-019's other half. A difference posted to no account is money that
    // left the tie-out and landed nowhere.
    gl_account_id: z.string().min(1, t("payments.deposits.form.glRequired")),
    amount: z
      .string()
      .regex(AMOUNT_SHAPE, t("payments.deposits.form.amountInvalid"))
      .regex(AMOUNT_PLACES, t("payments.deposits.form.amountPlaces"))
      .refine((value) => !/^-?0*(\.0*)?$/.test(value), {
        // A zero explains nothing and would post a journal line for money that
        // did not move — the service refuses it too. That stays true at a
        // ZERO difference as well: there the form sends no row at all rather
        // than a 0.00 one (`LBX-01`).
        message: t("payments.deposits.form.amountNonZero"),
      }),
  });
}

/**
 * The whole form's schema — `P3.12`.
 *
 * ⚠ **THE FIELD IDS ARE THE ZOD PATH, AND THEY HAVE TO BE.** `FormModal` maps an
 * issue to a field with `issue.path.join(".")`, so row 2's amount is
 * `resolutions.1.amount` and the `TextField` carrying it must use exactly that
 * id or the message renders nowhere at all — a validation failure a clerk
 * experiences as a button that does nothing.
 *
 * `.min(1)` is not decoration: a reconcile with no explanations is what the
 * server refuses whenever the difference is non-zero, and an empty list would
 * reach it as a body rather than as a form error.
 *
 * ⚠ **AND ONLY WHEN IT IS NON-ZERO (`LBX-01`, `DEF-PAY-10700`).** At a
 * difference of exactly $0.00 there is nothing to explain, the server takes
 * an empty list (`reconcile_batch` sums nothing to nothing), and demanding a
 * row there — while refusing a 0.00 one — made a batch that matched the bank
 * to the penny impossible to reconcile. `differenceIsZero` is `false` for an
 * unknown difference, so *we do not know* still demands a row.
 */
export function resolutionsSchema(t: Translator, differenceIsZero = false) {
  return z.object({
    resolutions: z.array(resolutionSchema(t)).min(differenceIsZero ? 0 : 1),
  });
}

/** One row of the draft list, changed, without mutating the array React holds. */
export function withRow(
  rows: readonly ResolutionDraft[],
  index: number,
  change: Partial<ResolutionDraft>,
): ResolutionDraft[] {
  return rows.map((row, at) => (at === index ? { ...row, ...change } : row));
}

// ── Panels ────────────────────────────────────────────────────────────────

/* ⚠ **`NUM` AND NOT `fin-num` — AND THE OLD CLASS RENDERED NOTHING**
 * (`DEF-PAY-6652`). `.fin-num { text-align: right }` is a bare class at
 * specificity (0,1,0) and `PlainTable` writes `[&_td]:text-left` on the TABLE,
 * which compiles to a descendant selector at (0,1,1) — so every money column on
 * this screen has been ragged-LEFT since the plain-table skin moved into
 * utilities. Measured in Chromium: `className === "fin-num"`, computed
 * `text-align: left`.
 *
 * `[&&]:` doubles the class's own selector and out-ranks the parent's variant.
 * It is this repo's established idiom — `workflowKit.NUM_CELL` and eight cells
 * of `AssetLifecycleTab` — and it is NOT `!important`, which would win the same
 * argument by leaving nothing able to answer it.
 *
 * `tabular-nums` travels with it because `.fin-num` carried it too, and a money
 * column that is right-aligned with proportional digits still does not line up. */
const NUM = "[&&]:text-right tabular-nums";

/** `CR-186-BRC10` ruling 3 — a batch carries a total PER TENDER (Dana · 14 Oct:
 *  cash $300.00 + cheques $500.00 = $800.00). Served by the engine
 *  (`reconciliation.tender_totals`), never summed here, so a cancelled member
 *  can never be counted on screen while the batch total leaves it out. Draws
 *  nothing for an older batch, which holds one tender and says so in its row. */
export function TenderTotalsPanel(props: {
  detail: DepositBatchDetail;
  t: Translator;
  locale?: string;
}) {
  const { detail, t } = props;
  const rows = detail.tender_totals ?? [];
  if (detail.batch.all_tenders !== true || rows.length === 0) {
    return null;
  }
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("payments.deposits.tendersTitle")}</h3>
      </div>
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.col.method")}</th>
            <th scope="col" className={NUM}>
              {t("payments.deposits.col.payments")}
            </th>
            <th scope="col" className={NUM}>
              {t("payments.col.amount")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.method_code ?? "none"}>
              <td>{row.method_name ?? row.method_code ?? t("payments.deposits.noMethod")}</td>
              <td className={NUM}>{row.count}</td>
              <td className={NUM}>
                <MoneyCell
                  amount={row.amount ?? "0"}
                  currency={detail.batch.currency}
                  locale={props.locale}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </Panel>
  );
}

export function MembersPanel(props: {
  detail: DepositBatchDetail;
  t: Translator;
  locale?: string;
  /** `P3.10`'s three acts. ABSENT means the row draws no actions cell at all —
   *  which is what the S40 modal's read-only preview wants, and is how this
   *  panel stays one component for both (hard-won law 2 cuts the other way
   *  too: an optional prop that IS passed by the screen is not dead UI). */
  actions?: {
    role: string | null;
    openTo: (member: DepositBatchMember) => string;
    onCorrect: (member: DepositBatchMember) => void;
    onReverse: (member: DepositBatchMember) => void;
  };
}) {
  const { detail, t, actions } = props;
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("payments.deposits.membersTitle")}</h3>
        <span className="pay-see">{t("payments.deposits.membersSee")}</span>
      </div>
      {detail.members.length === 0 ? (
        <p className="pay-absent" role="note">
          {t("payments.deposits.membersEmpty")}
        </p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("payments.col.confirmation")}</th>
              <th scope="col">{t("payments.col.account")}</th>
              <th scope="col" className={NUM}>
                {t("payments.col.amount")}
              </th>
              <th scope="col">{t("payments.col.clearedAt")}</th>
              {actions !== undefined && (
                <th scope="col">{t("payments.col.actions")}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {detail.members.map((member) => (
              <tr key={member.payment_id}>
                <td>
                  {/* A cheque number, or the payment's own number, or a stated
                      absence — never an empty cell. Cash carries no cheque
                      number and an empty string would read as a lost one. */}
                  {member.confirmation ?? member.payment_no ?? t("payments.deposits.noReference")}
                </td>
                <td>{member.account_no ?? t("payments.deposits.noAccountNo")}</td>
                <td className={NUM}>
                  <MoneyCell
                    amount={member.amount ?? "0"}
                    currency={member.currency}
                    locale={props.locale}
                  />
                  {/* ⚠ **`P3.11`, ON THE LINE THAT MOVED.** A batch total that
                      no longer sums is a fact about ONE member, and a KPI tile
                      alone makes a clerk read nine rows to find which. The
                      reversing row is not in this table and never can be
                      (hard rule 4 — it is a NEW row, outside the batch), so
                      without this the line that came back looks exactly like
                      the eight that did not. */}
                  {!isZeroAmount(member.reversed_amount) && (
                    <span className="mt-1 block text-xs text-danger-700">
                      {t("payments.deposits.memberReversed")}
                    </span>
                  )}
                </td>
                <td>
                  {/* A payment with no clearing date is POSTED and its batch is
                      not yet reconciled with the bank (`CR-186-BRC10`, PO
                      2026-10-21) — a STATE, not a missing value. */}
                  {member.cleared_at === null
                    ? t("payments.deposits.notCleared")
                    : member.cleared_at.slice(0, 10)}
                </td>
                {actions !== undefined && (
                  <td>
                    <BatchMemberActions
                      member={member}
                      t={t}
                      role={actions.role}
                      openTo={actions.openTo(member)}
                      onCorrect={() => actions.onCorrect(member)}
                      onReverse={() => actions.onReverse(member)}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2}>{t("payments.deposits.recordedTotal")}</td>
              <td className={NUM}>
                <BankFigure
                  amount={detail.batch.recorded_total}
                  currency={detail.batch.currency}
                  reason={t("payments.deposits.noRecordedTotal")}
                  locale={props.locale}
                />
              </td>
              <td />
              {actions !== undefined && <td />}
            </tr>
          </tfoot>
        </PlainTable>
      )}
    </Panel>
  );
}

export function BankSidePanel(props: {
  detail: DepositBatchDetail;
  t: Translator;
  locale?: string;
}) {
  const { detail, t } = props;
  if (detail.bank_line === null) {
    // NOT a panel of empty fields. "The bank has not shown us this deposit" is
    // a state with its own sentence; empty rows read as data that failed to
    // load, and a clerk would refresh instead of importing a statement.
    return (
      <Panel>
        <div className="fin-panel-head">
          <h3>{t("payments.deposits.bankSideTitle")}</h3>
        </div>
        <p className="pay-absent" role="note">
          {bankAbsenceReason(detail.batch.status, t)}
        </p>
      </Panel>
    );
  }
  const line = detail.bank_line;
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("payments.deposits.bankSideTitle")}</h3>
        <span className="pay-see">{t("payments.deposits.bankSideSee")}</span>
      </div>
      <PlainTable>
        <tbody>
          <tr>
            <td>{t("payments.deposits.bank.postingDate")}</td>
            <td>{line.posted_on ?? t("payments.deposits.noDate")}</td>
          </tr>
          <tr>
            <td>{t("payments.deposits.bank.reference")}</td>
            <td>{line.reference ?? t("payments.deposits.noReference")}</td>
          </tr>
          <tr>
            <td>{t("payments.deposits.bank.account")}</td>
            <td>
              {line.bank_account_name ?? t("payments.deposits.noBankAccount")}
              {line.bank_account_mask !== null && ` ••${line.bank_account_mask}`}
            </td>
          </tr>
          <tr>
            <td>{t("payments.deposits.bank.amount")}</td>
            <td>
              <MoneyCell
                amount={line.amount ?? "0"}
                currency={line.currency}
                locale={props.locale}
              />
            </td>
          </tr>
          <tr>
            <td>{t("payments.deposits.bank.statement")}</td>
            <td>
              {line.period_start ?? "?"} – {line.period_end ?? "?"}
              {line.line_no !== null &&
                ` · ${t("payments.deposits.bank.line", { n: line.line_no })}`}
            </td>
          </tr>
        </tbody>
      </PlainTable>
    </Panel>
  );
}

export function TrailPanel(props: { detail: DepositBatchDetail; t: Translator }) {
  const { detail, t } = props;
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("payments.deposits.trailTitle")}</h3>
        <span className="pay-see">{t("payments.deposits.trailSee")}</span>
      </div>
      {detail.trail.length === 0 ? (
        <p className="pay-absent" role="note">
          {t("payments.deposits.trailEmpty")}
        </p>
      ) : (
        <ol className="pay-trail">
          {/* OLDEST FIRST, as served. A trail answers "what happened to this
              money, in order?" and reversing it makes a reader reconstruct the
              sequence in their head. It is append-only server-side, so this is
              the whole history and never a window on it (US-PAY-023 TC-4). */}
          {detail.trail.map((row) => (
            <li key={row.id}>
              {/* The instant is served as a full ISO timestamp; the trail reads
                  as a sequence of MOMENTS, so the date and the time of day are
                  what a person needs and the offset is noise on every row.
                  Sliced rather than reformatted: this app has ONE date
                  formatter and a trail entry is not a business date — it is the
                  exact instant an event was stamped (BR-TEN-043). */}
              <span className="pay-trail-when">
                {row.occurred_at === null ? "" : row.occurred_at.slice(0, 16).replace("T", " ")}
              </span>
              <span className="pay-trail-what">{trailEventLabel(row.event, t)}</span>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

export function ResolutionsPanel(props: {
  detail: DepositBatchDetail;
  t: Translator;
  locale?: string;
}) {
  const { detail, t } = props;
  if (detail.resolutions.length === 0) {
    return null;
  }
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("payments.deposits.resolutionsTitle")}</h3>
      </div>
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.col.reason")}</th>
            <th scope="col" className={NUM}>
              {t("payments.col.amount")}
            </th>
            <th scope="col">{t("payments.deposits.col.note")}</th>
          </tr>
        </thead>
        <tbody>
          {detail.resolutions.map((row) => (
            <tr key={row.id}>
              <td>{row.reason_code}</td>
              <td className={NUM}>
                <MoneyCell
                  amount={row.amount ?? "0"}
                  currency={row.currency}
                  locale={props.locale}
                />
              </td>
              <td>{row.note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </Panel>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface DepositBatchPageProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function DepositBatchPage(props: DepositBatchPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const cell = useAccessCell(BANKREC_PERMISSION, client);
  const batchId = routeParams.batchId ?? "";

  const [resolveOpen, setResolveOpen] = useState(false);
  // `P3.12` — a LIST, because a difference has as many causes as it has causes.
  // See `ResolveDifferenceModal` for the worked case this exists for.
  const [drafts, setDrafts] = useState<ResolutionDraft[]>([EMPTY_RESOLUTION]);
  const [unreconcileOpen, setUnreconcileOpen] = useState(false);
  const [unreconcileReason, setUnreconcileReason] = useState("");
  // `P3.10` — which member's form is open, by payment id. One at a time: a
  // modal opened from inside a modal is forbidden and two correction forms on
  // one screen is two answers to "which payment am I correcting?".
  const [correcting, setCorrecting] = useState<DepositBatchMember | null>(null);
  const [reversing, setReversing] = useState<DepositBatchMember | null>(null);
  const role = useTenantRole(client);

  const detailQuery = useQuery({
    queryKey: depositBatchQueryKey(batchId),
    queryFn: () => getDepositBatch(batchId, client),
    retry: false,
    enabled: batchId !== "",
  });

  const reconcileMutation = useMutation({
    mutationFn: (resolutions: readonly ResolutionDraft[]) =>
      reconcileDepositBatch(
        batchId,
        {
          posted_at: new Date().toISOString(),
          // EVERY row, not the first. `reconciliation.reconcile_batch` has taken
          // a list since it was written and checks that they SUM to the
          // difference; sending one of several would fail that check with the
          // clerk's other explanations silently dropped.
          resolutions: resolutions.map((resolution) => ({
            reason_code: resolution.reason_code,
            gl_account_id: resolution.gl_account_id,
            amount: resolution.amount,
            note: resolution.note === "" ? undefined : resolution.note,
          })),
        },
        client,
      ),
  });

  // `P3.10` — the payment behind the row a clerk pressed, loaded only then.
  // `payment_no` addresses it (the server takes either) and the id is the
  // fallback for a row whose number billing could not resolve.
  const openMember = correcting ?? reversing;
  const paymentQuery = useQuery({
    queryKey: ["payments", "detail", openMember?.payment_id ?? ""],
    queryFn: () =>
      getPaymentDetail(client, openMember?.payment_no ?? openMember?.payment_id ?? ""),
    retry: false,
    enabled: openMember !== null,
  });
  // The tender list the correction form's chooser needs. `per: 1` because the
  // PAYMENTS are not wanted — only the `methods` the same response carries,
  // which is where `PaymentDetailPage` gets them too.
  const methodsQuery = useQuery({
    queryKey: ["payments", "methods-for-correct"],
    queryFn: () => getPayments({ per: 1 }, client),
    retry: false,
    enabled: correcting !== null,
  });

  const unreconcileMutation = useMutation({
    mutationFn: (reason: string) =>
      unreconcileDepositBatch(batchId, { reason, posted_at: new Date().toISOString() }, client),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />
    );
  }
  if (detailQuery.isError && isPermissionDenied(detailQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />
    );
  }

  const detail = detailQuery.data;
  const failed = detailQuery.isError && detail === undefined;

  async function handleResolve(): Promise<FormSubmitOutcome> {
    try {
      const result = await reconcileMutation.mutateAsync(drafts);
      setResolveOpen(false);
      setDrafts([EMPTY_RESOLUTION]);
      toast(t("payments.deposits.reconciled", { code: result.code }));
      await queryClient.invalidateQueries({ queryKey: depositBatchQueryKey(batchId) });
      await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
      return { ok: true };
    } catch (error) {
      // The server's tie-out refusal lands here as a sentence naming exactly
      // how much is unexplained. It is SHOWN (BR-SHL-020): a reconcile that
      // failed silently would leave a clerk believing the day was signed off.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  /**
   * `LBX-01` (`DEF-PAY-10700`) — the batch matches the bank to the penny, so
   * it reconciles with NO explanation rows, in one press. Same endpoint, same
   * server tie-out (`explained == difference`, here `0 == 0`), same lock.
   * Worked: DEP-261026-0007, recorded $870.50, bank $870.50 → Reconciled.
   * A refusal is SHOWN (BR-SHL-020), never swallowed.
   */
  async function handleReconcileAtZero(): Promise<void> {
    try {
      const result = await reconcileMutation.mutateAsync([]);
      toast(t("payments.deposits.reconciled", { code: result.code }));
      await queryClient.invalidateQueries({ queryKey: depositBatchQueryKey(batchId) });
      await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
    } catch (error) {
      toast(apiErrorText(error, translate));
    }
  }

  async function handleUnreconcile(): Promise<FormSubmitOutcome> {
    try {
      await unreconcileMutation.mutateAsync(unreconcileReason);
      setUnreconcileOpen(false);
      setUnreconcileReason("");
      toast(t("payments.deposits.unreconciled"));
      await queryClient.invalidateQueries({ queryKey: depositBatchQueryKey(batchId) });
      await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  const difference = detail?.batch.difference ?? null;
  // Only rows a clerk has actually typed an amount into count towards the
  // residual. A blank row is a row still being filled in, not an explanation
  // of $0.00 — and `residualOf` returns `null` for an unreadable amount, which
  // is *we do not know what is left* and keeps the commit shut.
  const typedAmounts = drafts.map((row) => row.amount).filter((amount) => amount.trim() !== "");
  // `LBX-02` — an amount the form REFUSES is counted as nothing at all, not
  // as the number it nearly is: a fifth decimal would otherwise tie on screen
  // and be refused on the press, and `"1,5"` is unreadable either way.
  const unreadable = typedAmounts.some((amount) => amountProblem(amount, translate) !== undefined);
  const residual = unreadable ? null : residualOf(difference, typedAmounts);
  const ties = !unreadable && explainsTheDifference(difference, typedAmounts);
  const differenceIsZero = isZeroAmount(difference);
  // `P3.11` — what the members still stand for, less what was frozen at the
  // cut. Taken from the SERVED `live_total`; a client that re-derived it from
  // `members` would compute 0.00 for ever (`DEF-PAY-6651`).
  const drift = driftOf(detail?.batch.recorded_total ?? null, detail?.live_total ?? null);

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("payments.deposits.detailKicker", { code: detail?.batch.code ?? "" })}
        title={detail?.batch.code ?? t("payments.deposits.detailTitle")}
        backTo={{ to: tenantPath(DEPOSITS_ROUTE), label: t("payments.deposits.backToList") }}
        status={
          detail === undefined ? undefined : (
            <StatusPill tone={batchStatusTone(detail.batch.status)}>
              {batchStatusLabel(detail.batch.status, translate, {
                difference: detail.batch.difference,
                currency: detail.batch.currency,
                locale: props.locale,
              })}
            </StatusPill>
          )
        }
        secondaryActions={
          detail === undefined ? undefined : detail.batch.locked ? (
            // BR-PAY-004: LOCKED. Unreconcile is the only way back, it is
            // audited, and it costs a written reason. Resolve is not rendered —
            // the service refuses a second reconcile outright.
            <Button
              variant="secondary"
              onClick={() => setUnreconcileOpen(true)}
            >
              {t("payments.deposits.unreconcile")}
            </Button>
          ) : detail.bank_line === null ? (
            // Nothing to reconcile AGAINST. A batch reconciles against what the
            // BANK said (BR-PAY-019); with no statement line the control would
            // fail on click, so it renders as its reason instead (BR-SHL-025).
            <span className="pay-absent" role="note">
              {t("payments.deposits.noBankLineYet")}
            </span>
          ) : isZeroAmount(detail.batch.difference) ? (
            // `LBX-01` — nothing to explain, so p051's own primary action,
            // `Reconcile ✓`, with no form in front of it. A form here could
            // only ask for a row the difference does not have.
            <Button
              variant="primary"
              disabled={reconcileMutation.isPending}
              onClick={() => void handleReconcileAtZero()}
            >
              {t("payments.deposits.reconcileCommit")}
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => {
                setDrafts([
                  {
                    ...EMPTY_RESOLUTION,
                    // The DIFFERENCE is pre-filled because it is a served fact and
                    // the clerk is explaining exactly it. The REASON and the GL
                    // are not: BR-PAY-019 wants a human's judgement on both, and
                    // a seeded reason would put "processor fee" on a cash
                    // shortage.
                    //
                    // ⚠ ONE row pre-filled with the WHOLE difference, not two
                    // split by a guess. `P3.12` exists so a clerk can say the
                    // 172.50 is a 147.50 fee AND a 25.00 chargeback; deciding
                    // the split for them would put the commonest answer on
                    // every day and defeat the reason list exactly as one
                    // forced reason does.
                    //
                    // Never a 0.00 (`LBX-01`): a zero row is refused, so
                    // pre-filling one put a refusal in the form before the
                    // clerk had typed anything.
                    amount:
                      difference === null || isZeroAmount(difference)
                        ? ""
                        : amountForInput(difference),
                  },
                ]);
                setResolveOpen(true);
              }}
            >
              {t("payments.deposits.resolveDifference")}
            </Button>
          )
        }
      />

      {failed ? (
        <Panel role="alert">
          <h3>{t("payments.deposits.errorTitle")}</h3>
          <p className="pay-absent">{apiErrorText(detailQuery.error, translate)}</p>
        </Panel>
      ) : detail === undefined ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <>
          <KPIStrip
            kpis={[
              {
                id: "recorded",
                label: t("payments.deposits.kpi.weRecorded"),
                money: {
                  amount: detail.batch.recorded_total ?? "0",
                  currency: detail.batch.currency,
                  basis: "posting",
                  locale: props.locale,
                },
                detail: t("payments.deposits.kpi.payments", {
                  count: detail.batch.payment_count ?? 0,
                }),
              },
              // ⚠ **`P3.11` — THE TILE THAT SAYS A LOCKED BATCH NO LONGER SUMS.**
              //
              // It equals RECORDED until a payment inside the batch is
              // reversed, and then it does not. A reversal inside a LOCKED
              // batch is lawful — `_refuse_if_batch_locked` permits it because
              // *"the bank statement the batch was agreed against did not
              // change"* (PO 2026-08-12, OQ-134) — so `recorded_total` stays
              // frozen and correct while the money behind it comes back, and
              // until now **no screen said so**. Worked on the branch:
              // `DEP-260808-0002`, recorded $2,388.84, one member of $501.33
              // returned, live $1,887.51.
              //
              // **IT CHANGES NO RULE** (p016: *"Show the difference; change no
              // rule"*). The frozen total is not touched, the lock is not
              // weakened, and nothing here writes.
              //
              // ⚠ **A `value` TILE AND NOT A `money` TILE, FOR THE REASON THE
              // TWO BELOW ARE**: `live_total` is null on a payload from a server
              // that does not serve it yet, and a KPI tile is exactly where a
              // plausible $0.00 does the most damage. `BankFigure` states the
              // absence instead.
              {
                id: "live",
                label: t("payments.deposits.kpi.livePayments"),
                value: (
                  <BankFigure
                    amount={detail.live_total}
                    currency={detail.batch.currency}
                    reason={t("payments.deposits.kpi.liveUnavailable")}
                    locale={props.locale}
                  />
                ),
                detail: isZeroAmount(drift) ? (
                  t("payments.deposits.kpi.reversalsIncluded")
                ) : drift === null ? (
                  t("payments.deposits.kpi.reversalsIncluded")
                ) : (
                  // B14 rule 33 — a FACT, and the figure carries the meaning.
                  // NOT a sentence explaining reconciliation: that is
                  // RATIONALE and rationale is zero words on screen.
                  <span className="text-danger-700">
                    {t("payments.deposits.kpi.sinceTheCut")}{" "}
                    <MoneyCell
                      amount={drift}
                      currency={detail.batch.currency}
                      locale={props.locale}
                    />
                  </span>
                ),
              },
              // THE TWO TILES THAT MUST NOT LIE. `bank_total` and `difference`
              // are null until the bank speaks, and a KPI tile is exactly where
              // a plausible $0.00 does the most damage — so these two are plain
              // `value` tiles carrying `BankFigure`, not `money` tiles that
              // would need an amount.
              {
                id: "bank",
                label: t("payments.deposits.kpi.bankShows"),
                value: (
                  <BankFigure
                    amount={detail.batch.bank_total}
                    currency={detail.batch.currency}
                    reason={bankAbsenceReason(detail.batch.status, translate)}
                    locale={props.locale}
                  />
                ),
              },
              {
                id: "difference",
                label: t("payments.deposits.kpi.difference"),
                value: (
                  <BankFigure
                    amount={detail.batch.difference}
                    currency={detail.batch.currency}
                    reason={bankAbsenceReason(detail.batch.status, translate)}
                    locale={props.locale}
                  />
                ),
                detail: t("payments.deposits.kpi.toExplain"),
              },
              // ⚠ **THERE IS NO FIFTH `status` TILE, AND IT WAS REMOVED IN THE
              // COMMIT THAT ADDED *Live payments*.** Three reasons, and the
              // first is the one that decides it:
              //
              //   1. **The drawing draws FOUR** (p050) and a status tile is not
              //      one of them. B14 rule 44 — the drawing says WHAT is on the
              //      screen and how it is arranged.
              //   2. **It said what the `StatusPill` two inches above it
              //      already says.** `PageHeader` carries the batch's status as
              //      a pill on every render of this screen, so *Reconciled*
              //      appeared twice; and the lock is stated by which control
              //      the head offers — `Unreconcile` when locked, `Resolve
              //      difference` when not.
              //   3. `.kpi-grid` is `repeat(auto-fit, minmax(240px, 1fr))`, so
              //      a FIFTH tile wraps at 1440 and leaves one orphan on a row
              //      of its own. Measured on the running screen before this
              //      line was written, not predicted.
            ]}
          />

          <div className="pay-two-col">
            <MembersPanel
              detail={detail}
              t={translate}
              locale={props.locale}
              // `P3.10` — the three lawful acts p049 found missing. The `openTo`
              // address carries the `PMT-` NUMBER and not the uuid (B14 rule 31
              // — an address bar is the most visible field a screen has); the
              // id is the fallback for a row whose number billing could not
              // resolve, and the server resolves either.
              actions={{
                role,
                openTo: (member) =>
                  tenantPath(paymentDetailRoute(member.payment_no ?? member.payment_id)),
                onCorrect: setCorrecting,
                onReverse: setReversing,
              }}
            />
            <div>
              <TenderTotalsPanel detail={detail} t={translate} locale={props.locale} />
              <BankSidePanel detail={detail} t={translate} locale={props.locale} />
              <TrailPanel detail={detail} t={translate} />
            </div>
          </div>
          <ResolutionsPanel detail={detail} t={translate} locale={props.locale} />
          <GapNotes gaps={detail.unavailable} t={translate} />
        </>
      )}

      {resolveOpen && detail !== undefined && (
        <FormModal
          title={t("payments.deposits.resolveTitle")}
          kicker={t("payments.deposits.resolveKicker", { code: detail.batch.code })}
          schema={resolutionsSchema(translate, differenceIsZero)}
          values={{ resolutions: drafts }}
          submitLabel={t("payments.deposits.resolveSubmit")}
          onSubmit={handleResolve}
          onClose={() => setResolveOpen(false)}
          // ⚠ **`Record ✓` IS GATED ON THE RESIDUAL, AND UNTIL NOW IT WAS NOT
          // (`P3.12`).** This file's exception (5) read *"the client-side
          // tie-out is advisory only and never gates submit"*, on the reasoning
          // that a client which thought it knew better would be a second
          // implementation of a signed rule. p055 rules otherwise and it is
          // right: the blueprint draws `Record ✓ · enabled only at a residual
          // of $0.00`, and disabling a commit is not a second implementation of
          // the tie-out — the SERVER still decides, and this screen merely
          // stops offering a press that must fail. That is BR-SHL-025 in its
          // own words, and `commitBlocked` renders the reason as announced
          // text rather than as a tooltip.
          //
          // `residual === null` — the bank has not spoken, or an amount will
          // not parse — BLOCKS. *We do not know what is left* is the one state
          // where a plausible zero must not open a money commit.
          commitBlocked={ties ? undefined : t("payments.deposits.form.residualBlocks")}
        >
          <p className="pay-form-note">{t("payments.deposits.resolveHelp")}</p>
          {/* The three tiles the prototype puts at the top of this modal, as a
              fact line — the clerk is explaining a specific gap and must see
              both sides of it while typing. */}
          <div className="pay-resolve-facts">
            <span>
              {t("payments.deposits.kpi.weRecorded")}:{" "}
              <BankFigure
                amount={detail.batch.recorded_total}
                currency={detail.batch.currency}
                reason={t("payments.deposits.noRecordedTotal")}
                locale={props.locale}
              />
            </span>
            <span>
              {t("payments.deposits.kpi.bankShows")}:{" "}
              <BankFigure
                amount={detail.batch.bank_total}
                currency={detail.batch.currency}
                reason={bankAbsenceReason(detail.batch.status, translate)}
                locale={props.locale}
              />
            </span>
            <span>
              {t("payments.deposits.kpi.difference")}:{" "}
              <BankFigure
                amount={detail.batch.difference}
                currency={detail.batch.currency}
                reason={bankAbsenceReason(detail.batch.status, translate)}
                locale={props.locale}
              />
            </span>
          </div>
          {/* ⚠ **ONE ROW PER CAUSE — `P3.12`, AND IT IS WHY THE REASON LIST
              EXISTS.** p054's finding, in full: a card day short by $172.50 is
              routinely a **$147.50 processor fee PLUS a $25.00 chargeback** —
              two reasons, two GL accounts. With one row a clerk picks one of
              them for the whole amount, which files $25 of chargeback as a fee
              and *"defeats the reason the reason list exists: it was introduced
              so a finance user could ask how much of a quarter was fees and how
              much was error."*

              **The SERVICE has taken a list since it was written**
              (`reconciliation.reconcile_batch(… resolutions: tuple[…])`) and
              already checks they sum to the difference. Only the form drew one
              row. So this adds NO endpoint, NO rule and NO column — it stops
              throwing away a capability the engine already had. */}
          {drafts.map((row, index) => (
            // ⚠ **TWO FIELDS PER LINE, NOT THE DRAWING'S FIVE ACROSS — B14
            // RULE 38.** p055 draws the repeating row as a table: reason, GL,
            // amount, note and a ✕ in one line. *"Where a drawing and our UI
            // rules disagree about how a FORM IS BUILT, the UI rules win"* —
            // side-by-side fields are CONSTRUCTION, and one screen's drawing
            // does not get to change how every dialog in the product is built.
            //
            // It is also measured rather than argued: the 560px card leaves
            // ~512px of body, so five across gives each input about 90px. Built
            // that way first and photographed, the inputs read "proce",
            // "bank_", "returnec" and the help wrapped into columns one word
            // wide. **What the row CONTAINS is still the drawing's** — the same
            // four fields, repeating, with the same ✕.
            <div
              key={index}
              className="mb-3 grid grid-cols-1 gap-x-3 gap-y-2 border-b border-b-divider pb-3 sm:grid-cols-[1fr_1fr_auto] sm:items-start"
            >
              <TextField
                id={`resolutions.${index}.reason_code`}
                label={t("payments.deposits.form.reason")}
                value={row.reason_code}
                onChange={(value) => setDrafts(withRow(drafts, index, { reason_code: value }))}
                required
                // The help sits on the FIRST row only. B14 rule 32 — one
                // sentence per section — and five rows each repeating the same
                // instruction is the same sentence five times.
                help={index === 0 ? t("payments.deposits.form.reasonHelp") : undefined}
              />
              <TextField
                id={`resolutions.${index}.gl_account_id`}
                label={t("payments.deposits.form.gl")}
                value={row.gl_account_id}
                onChange={(value) => setDrafts(withRow(drafts, index, { gl_account_id: value }))}
                required
                // The DESIGNATION is named in the help, never a number: the chart is
                // tenant-customisable (US-LED-005) and the prototype's 6200/1020 are
                // in no signed chart at all (DEF-067).
                help={index === 0 ? t("payments.deposits.form.glHelp") : undefined}
              />
              <TextField
                id={`resolutions.${index}.amount`}
                label={t("payments.deposits.form.amount")}
                value={row.amount}
                onChange={(value) => setDrafts(withRow(drafts, index, { amount: value }))}
                numeric
                required
                // `LBX-02` — what is typed NOW, never what was typed at the
                // last press. Absent when it reads, so a press-time refusal
                // (a zero row) still arrives from the form's context.
                error={amountProblem(row.amount, translate)}
                help={index === 0 ? t("payments.deposits.form.amountHelp") : undefined}
              />
              <div className="sm:col-span-2">
                <TextField
                  id={`resolutions.${index}.note`}
                  label={t("payments.deposits.form.note")}
                  value={row.note}
                  onChange={(value) => setDrafts(withRow(drafts, index, { note: value }))}
                  help={index === 0 ? t("payments.deposits.form.noteHelp") : undefined}
                />
              </div>
              {/* ⚠ **DISABLED WITH ITS REASON ON THE LAST ROW, NOT HIDDEN**
                  (BR-SHL-025). A difference always needs at least one
                  explanation, and a ✕ that disappears on the row above teaches
                  nothing. */}
              <RowAction
                label={t("payments.deposits.form.removeRow")}
                icon={<TrashIcon />}
                danger
                reason={
                  drafts.length === 1 && !differenceIsZero
                    ? t("payments.deposits.form.needsOneRow")
                    : null
                }
                onClick={() => setDrafts(drafts.filter((_, at) => at !== index))}
              />
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setDrafts([...drafts, EMPTY_RESOLUTION])}
          >
            {t("payments.deposits.form.addExplanation")}
          </Button>

          {/* ⚠ **THE RUNNING RESIDUAL — DIFFERENCE, EXPLAINED, WHAT IS LEFT.**
              p055 draws the trio and enables `Record ✓` only at `$0.00`. The
              subtraction is exact `BigInt` on the `NUMERIC(18,6)` grid:
              `Number("-172.50") - Number("-147.50")` is `-25.000000000000004`,
              and a residual that never quite reaches zero is a button that
              never enables. */}
          <div className="mt-4 border-t border-t-divider pt-3">
            <p className="flex justify-between py-1">
              <span>{t("payments.deposits.kpi.difference")}</span>
              <span className={NUM}>
                <BankFigure
                  amount={difference}
                  currency={detail.batch.currency}
                  reason={bankAbsenceReason(detail.batch.status, translate)}
                  locale={props.locale}
                />
              </span>
            </p>
            <p className="flex justify-between py-1">
              <span>{t("payments.deposits.form.explained")}</span>
              <span className={NUM}>
                <BankFigure
                  amount={unreadable ? null : sumOf(typedAmounts)}
                  currency={detail.batch.currency}
                  reason={t("payments.deposits.form.amountUnreadable")}
                  locale={props.locale}
                />
              </span>
            </p>
            <p
              className={
                "flex justify-between py-1 font-heading " +
                (ties ? "text-success-700" : "text-danger-700")
              }
              role="note"
              data-testid="resolve-residual"
            >
              <span>{t("payments.deposits.form.residual")}</span>
              <span className={NUM}>
                <BankFigure
                  amount={residual}
                  currency={detail.batch.currency}
                  reason={t("payments.deposits.form.residualUnknown")}
                  locale={props.locale}
                />
              </span>
            </p>
          </div>
        </FormModal>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          `P3.10`'s TWO MONEY FORMS ARE THE PRODUCT'S OWN, NOT SECOND COPIES
          ══════════════════════════════════════════════════════════════════
          Correcting a reference and reversing a payment are nine-field money
          forms with their own refusals, their own consequence boxes and their
          own reversal plan. `CorrectReferenceModal` and `ReversePaymentModal`
          already exist and are already tested, and the Finance blueprint's own
          warning about these three tasks is that the expensive mistake is to
          *rebuild something that already exists and is already tested*. B14
          rule 43 says the same thing from the other end.

          ⚠ **THEY TAKE A `PaymentRow` AND A BATCH MEMBER IS NOT ONE**, so the
          row is FETCHED when the clerk presses, rather than assembled here out
          of the eight fields this table happens to hold. A hand-built row would
          carry plausible defaults for `applied_to`, `purpose` and the cheque
          triple — and the reversal form reads those to decide what re-opens.
          One GET is the honest price of reusing the real form. */}
      {(correcting ?? reversing) !== null && paymentQuery.data !== undefined && (
        <>
          {correcting !== null && (
            <CorrectReferenceModal
              client={client}
              payment={paymentQuery.data}
              methods={methodsQuery.data?.methods ?? []}
              onClose={() => setCorrecting(null)}
              onCorrected={() => {
                setCorrecting(null);
                void queryClient.invalidateQueries({
                  queryKey: depositBatchQueryKey(batchId),
                });
              }}
            />
          )}
          {reversing !== null && (
            <ReversePaymentModal
              client={client}
              payment={paymentQuery.data}
              // The same default `PaymentDetailPage` uses. Nothing wires the
              // tenant's format into either screen yet; when something does, it
              // reaches both from one place rather than from two.
              dateFormat="MM/DD/YYYY"
              onClose={() => setReversing(null)}
              onReversed={() => {
                setReversing(null);
                // The batch's `live_total` MOVES on a reversal and its
                // `recorded_total` does not — which is the whole of `P3.11`.
                // Re-reading the batch is what makes the drift appear the
                // moment it is created rather than on the next visit.
                void queryClient.invalidateQueries({
                  queryKey: depositBatchQueryKey(batchId),
                });
              }}
            />
          )}
        </>
      )}

      {unreconcileOpen && detail !== undefined && (
        <FormModal
          title={t("payments.deposits.unreconcileTitle")}
          kicker={t("payments.deposits.unreconcileKicker", { code: detail.batch.code })}
          schema={z.object({
            reason: z.string().min(1, t("payments.deposits.form.unreconcileReasonRequired")),
          })}
          values={{ reason: unreconcileReason }}
          submitLabel={t("payments.deposits.unreconcileSubmit")}
          onSubmit={handleUnreconcile}
          onClose={() => setUnreconcileOpen(false)}
        >
          <p className="pay-form-note">{t("payments.deposits.unreconcileWarning")}</p>
          <TextField
            id="reason"
            label={t("payments.deposits.form.unreconcileReason")}
            value={unreconcileReason}
            onChange={setUnreconcileReason}
            required
            multiline
            help={t("payments.deposits.form.unreconcileReasonHelp")}
          />
        </FormModal>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-023@5b2e814 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-022 §1/§3/§5 + US-PAY-023 §1/§3/§5 · 08-payments/02-business-rules.md BR-PAY-002/004/019/035/040 · 08-qa/01-e2e/journeys/J14-lockbox-day.md steps 5-7 · 05-prototype/UtilityBilling.html lines 4021-4090 + 5568-5600; co-packet US-PAY-022)
// generated: 2026-08-16 by story-coder (payments SURFACE lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the S39/S40 test file failed to resolve this module before it existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) "Force match anyway" is NOT drawn and NOT disabled — BR-PAY-035 made it permanently superseded and no request body this form can build would reconcile a residual, so a disabled control would claim the feature exists · (2) no GL account NUMBER appears anywhere; the account is named by DESIGNATION and the prototype's 6200 Merchant Fees / 1020 Undeposited are in no signed chart (DEF-067 — the signed one has 1000 Cash, 1010 Undeposited funds, 6800 Bank fees) · (3) the prototype's per-member "Bounced (NSF)" select and its "$30.00 NSF fee" / "Notify by email" checkboxes are NOT here: the bounce is `reversal.py`'s and lives on the PAYMENT (PO 2026-08-12, OQ-134), and the same ruling holds the batch total still — a control here would imply it moves · (4) ONE resolution per submit. The engine accepts many and the S40 design shows one difference with one explanation; a repeating-row editor is a bigger form than the ruled case needs, and it is REPORTED rather than half-built · (5) the client-side tie-out is advisory only and never gates submit — the server's is the enforcement (US-PAY-022 §7) · (6) the two absent-figure KPI tiles are `value` tiles rather than `money` tiles ON PURPOSE: a money tile needs an amount, and there is none until the bank speaks
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
