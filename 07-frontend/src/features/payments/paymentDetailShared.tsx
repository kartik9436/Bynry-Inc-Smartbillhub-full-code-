// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.9` — screen 2·2 of
//           `05-prototype/06 Payments Page Blueprint.pdf`, **p035 read AS AN
//           IMAGE at scale 2.0** (B14 rule 42, PO: *"i want you to use drawing
//           images exactly to build screen; dont use text"*). p036 carries its
//           states, its words and the `2·2r` removal note.
// Story:    US-PAY-004  Screens: S33 · S21
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — standalone code inside
//           a page is not reuse) · rule 21 (Tailwind utilities; this file is on
//           `route-b-migrated.txt`) · rule 31 (no database id is a visible
//           value) · rule 32 (one sentence per section) · rule 33 (on-screen
//           text is capped by what it is for) · rule 35 (the words are the
//           catalogue's, in its own language) · rule 20 (ONE table type) ·
//           rule 39 (one spacing scale) · BR-PAY-021 (both dates, always)
// Tests:    src/features/payments/paymentDetailPage.dom.test.tsx
// ───────────────────────────────────────────────────────
// THE THREE PIECES SCREEN 2·2 IS MADE OF, EACH A COMPONENT.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE ELEVEN FACTS AND THE BILL TABLE ARE **MOVED**, NOT REWRITTEN
// ══════════════════════════════════════════════════════════════════════════
// p036's own words about the row panel this replaces: *"Its eleven facts and
// its two-column bill table are **kept exactly** and move to 2·2 — the drawing
// there is the same content with an address, a header strip and a history panel
// around it."*
//
// So `PaymentFacts` below is `paymentDetail.tsx`'s `PaymentDetailPanel` with
// its markup carried over and its reasoning intact. **Nothing about what a
// clerk reads changes in the swap** — which is the only way `P3.10` can delete
// the panel in the same commit without a clerk losing a fact.
//
// ⚠ **`appliedBills` IS REUSED AND NEVER RE-DERIVED, AND THAT IS A MONEY BUG
// WAITING IF IT IS NOT.** A release writes an append-only NEGATIVE mirror row
// against the same bill (`BR-PAY-1072`), so mapping `applied_to` raw lists a
// corrected bill TWICE with the money looking as though it went somewhere
// twice. That was `CS-36`, fixed on the *Applied to* COLUMN on 2026-09-02; a
// detail surface that re-derived it would re-open the same defect one screen
// along.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT THE DRAWING DRAWS THAT THE SERVER DOES NOT SERVE — AND WHY IT IS NOT
//   INVENTED HERE
// ══════════════════════════════════════════════════════════════════════════
// **⑥ RECONCILED is drawn as `BRM-2609-0041`.** No such series exists:
// `bank_rec_match_sets` has no code column and mints no number, and the only
// value there is a bare uuid — which B14 rule 31 forbids on a screen.
// **B14 rule 37 settles it: a figure drawn in a wireframe is an ILLUSTRATION,
// never a fact to build to.** So the cell shows what IS established — the
// deposit batch's own `DEP-` code and the tie's counts, which is where the
// drawing's own sub-line *"Three batches, one credit"* comes from — and the
// absence is stated in words. `OQ-PAY-12602` asks the PO whether a match set
// should get a series; nothing here is blocked either way.
//
// **⑤ SOURCE's second half — *who or which provider* — is `null` today.** The
// counter session link is `CR-136-BRC07`'s and is not on `payments` yet, and
// `entry` alone does not name a person (a transfer leg and a bounce are both
// `entry`). Stated, not guessed.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { PaymentRow, PaymentStatus } from "@/api/endpoints";
import type {
  BounceFacts,
  PaymentDetail,
  PaymentHistoryRow,
  PaymentReconciliation,
  PaymentSource,
} from "@/api/paymentDetailEndpoints";
import { DateCell } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkAnchor } from "@/components/Surfaces";
import { Dash, Fact, FactList } from "@/features/metering/meteringShared";

import {
  Money,
  PAYMENTS_ROUTE,
  appliedBills,
  paymentStatusLabel,
  paymentStatusTone,
  paymentTypeLabel,
  releasedByCorrection,
} from "./paymentsShared";

// ══════════════════════════════════════════════════════════════════════════
// THE ADDRESS ITSELF — declared HERE and not on the page, to break a cycle
// ══════════════════════════════════════════════════════════════════════════
// `PaymentDetailPage` imports `CorrectReferenceModal` and `PaymentsPage` from
// `PaymentsPage.tsx`, and `PaymentsPage.tsx` needs this builder for the 👁 row
// action and the identity column's link. **Declaring it on the page would make
// those two files import each other** — a cycle that bundles, renders, and then
// hands one of the two modules a half-initialised namespace at import time,
// which is a class of bug that shows up as `undefined is not a function` on one
// route and on no other.
//
// This module imports from `./paymentsShared` and from nothing else in the
// feature, so `PaymentsPage.tsx → paymentDetailShared.tsx → paymentsShared.tsx`
// stays acyclic. `PaymentDetailPage` re-exports both names so a reader looking
// for the route beside the screen still finds it.

/** `/:tenant/payments/:paymentRef` — the address `P3.1` made possible. */
export const PAYMENT_DETAIL_ROUTE = `${PAYMENTS_ROUTE}/:paymentRef`;

/**
 * The link every list row and every message now builds.
 *
 * ⚠ **THE `PMT-` NUMBER, NOT THE uuid — B14 rule 31.** An address a clerk
 * pastes into a message is about as visible as a value gets, and the drawing
 * agrees (`/:tenant/payments/PMT-2609-000418`). The id is the fallback for a
 * row whose number billing could not resolve; the server resolves either.
 */
export function paymentDetailRoute(paymentNo: string): string {
  return `${PAYMENTS_ROUTE}/${encodeURIComponent(paymentNo)}`;
}

export interface RegionalDetailProps {
  /** The tenant's `CHAR(3)`, read off the response — the one place this page
   *  can learn it (`BR-TEN-042`'s one-currency lock). Null renders the stated
   *  absence `Money` already draws, never a guess. */
  currency: string | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

// ══════════════════════════════════════════════════════════════════════════
// THE HEADER STRIP — p035, four cells between the head and the facts
// ══════════════════════════════════════════════════════════════════════════

/**
 * One cell of the strip: a LABEL, a value, and an optional line under it.
 *
 * ⚠ **THE LABEL IS ≤ 3 WORDS AND IS NOT A SENTENCE, AND THE SUB-LINE IS A FACT
 * AT ≤ 6 WORDS** — B14 rule 33's first two caps, which is why this component
 * takes them as separate props rather than as one blob a caller could fill with
 * a paragraph. The drawn cells obey it: *SOURCE · Counter · Dana Whitfield ·
 * Main counter*.
 */
/**
 * `DEF-PAY-10698` · LBX-04 — what a reversal said, as short lines a clerk
 * reads: *"Bank memo: NSF"*, *"+$30.00 NSF fee"*, or *"NSF fee not charged:
 * bank error"*. Empty when the reversal recorded neither.
 */
export function bounceLines(
  facts: BounceFacts | null | undefined,
  t: (key: string, options?: Record<string, unknown>) => string,
): string[] {
  if (!facts) {
    return [];
  }
  const lines: string[] = [];
  if (facts.bank_memo) {
    lines.push(t("payments.reverse.bankMemoLine", { memo: facts.bank_memo }));
  }
  if (facts.nsf_fee_waived_reason) {
    lines.push(t("payments.reverse.nsfFee.waived", { reason: facts.nsf_fee_waived_reason }));
  } else if (
    facts.nsf_fee_status === "charged" &&
    facts.nsf_fee_amount &&
    facts.nsf_fee_currency
  ) {
    lines.push(
      t("payments.reverse.nsfFee.charged", {
        amount: formatMoney(facts.nsf_fee_amount, facts.nsf_fee_currency),
      }),
    );
  }
  return lines;
}

function StripCell(props: { label: string; children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-5 py-3 first:pl-0">
      <span className="text-xs font-extrabold tracking-wide uppercase text-neutral-700">
        {props.label}
      </span>
      <span className="text-h5 font-extrabold text-text">{props.children}</span>
      {props.sub !== undefined && (
        <span className="text-sm text-neutral-700">{props.sub}</span>
      )}
    </div>
  );
}

/**
 * `CR-174-BRC10` — the *which provider* half of ⑤ for money a payment AGENT
 * took: *"Kiosk · 4471"*, and on a returned payment's reversing row the bank's
 * own code, *"Bank code R01"*. `null` when no agent took it, so the strip falls
 * back to the counter line exactly as before. An unknown channel word reads
 * *Other* — the server already folds it, and the catalogue default says so too.
 */
export function agentLine(
  source: PaymentSource,
  t: (key: string, options?: Record<string, unknown>) => string,
): string | null {
  const parts: string[] = [];
  if (source.channel) {
    parts.push(
      t(`payments.channel.${source.channel}`, { defaultValue: t("payments.channel.other") }),
    );
  }
  if (source.terminal) parts.push(source.terminal);
  if (source.return_code) parts.push(t("payments.detail.bankCode", { code: source.return_code }));
  return parts.length > 0 ? parts.join(" · ") : null;
}

/**
 * ⑤ SOURCE · BATCH · ⑥ RECONCILED · STATUS — the strip, as drawn on p035.
 *
 * ⚠ **THE STORED WORD IS TRANSLATED, NEVER MATCHED ON THE DRAWN ONE.**
 * `origin` holds `entry · webhook · import`; *Counter · Digital · Post* are
 * catalogue LABELS. A screen that switched on the drawn word would render
 * nothing for every payment in the database — which is the silent-failure shape
 * hard-won law 2 is about, and it passes `tsc`.
 */
export function PaymentHeaderStrip(props: {
  source: PaymentSource;
  batchRef: string | null;
  /** Record links (PO 2026-10-19): where the batch code opens — the deposit
   *  batch's page. `null`/absent for an import run or no batch, and the code
   *  then stays text. */
  batchHref?: string | null;
  reconciled: PaymentReconciliation | null;
  /** The SIXTH value, `cancelled`, arrived with `payments/0036` — see
   *  `PAYMENT_STATUSES`, whose own note records that this list read five for
   *  the hours between the migration landing and `P3.11`. */
  status: PaymentStatus;
  /** `DEF-PAY-10016` — the reason code this payment was taken back for, or
   *  `null`. Drawn under the status, which itself does not change. */
  reversedFor?: string | null;
  /** `DEF-PAY-10698` · LBX-04 — the bank memo and the NSF fee of that
   *  reversal, drawn under the reason. */
  reversal?: BounceFacts | null;
}) {
  const { t } = useTranslation();
  const { source, reconciled } = props;
  return (
    <div
      data-testid="payment-header-strip"
      className="mb-6 grid grid-cols-1 gap-x-4 border-y border-divider py-1 md:grid-cols-4"
    >
      <StripCell
        label={t("payments.detail.source")}
        sub={
          agentLine(source, (key, options) => t(key, options)) ?? (source.taken_by !== null ? (
            // `DEF-PAY-10734` — the clerk AND the till they took it at.
            source.counter_session_ref !== null ? (
              `${source.taken_by} · ${source.counter_session_ref}`
            ) : (
              source.taken_by
            )
          ) : (
            // ⚠ A STATED ABSENCE, NOT A BLANK. *"we could not name who"* and
            // *"nobody took it"* are different facts; an empty line says the
            // second and only the first is true.
            <Dash>{t("payments.detail.noTakenBy")}</Dash>
          ))
        }
      >
        {/* ⚠ **`payments.source.*` — THE LIST'S OWN KEYS, REUSED.** The cell
            one screen over renders `t(\`payments.source.${row.origin}\`)`;
            a second family here would be the same three words twice, free to
            drift into *Counter* on one screen and *Window* on the other. */}
        {/* `DEF-PAY-10734` (L2-03 b) — an import says WHICH kind (*Lockbox*,
            *File*) rather than the drawing's *Post* (*"Mail"*) for every file.
            A label only; `origin` stays `import` (CR-132). */}
        {/* PO 2026-10-30 Q6 — the store network the file named wins over the
            kind of import: *Store · Hy-Vee*, never *File*. */}
        {source.store_network ? (
          t("payments.source.store", { network: source.store_network })
        ) : source.origin === "import" && source.import_kind ? (
          t(`payments.source.importKind.${source.import_kind}`, {
            defaultValue: t("payments.source.import"),
          })
        ) : source.origin !== null && source.origin !== "" ? (
          t(`payments.source.${source.origin}`, {
            defaultValue: t("payments.row.noSource"),
          })
        ) : (
          <Dash>{t("payments.row.noSource")}</Dash>
        )}
      </StripCell>

      <StripCell
        label={t("payments.col.batch")}
        sub={props.batchRef !== null ? t("payments.detail.batchAttached") : undefined}
      >
        {props.batchRef === null ? (
          <Dash>{t("payments.detail.noBatch")}</Dash>
        ) : props.batchHref !== undefined && props.batchHref !== null ? (
          <InlineLinkAnchor href={props.batchHref}>{props.batchRef}</InlineLinkAnchor>
        ) : (
          props.batchRef
        )}
      </StripCell>

      <StripCell
        label={t("payments.detail.reconciled")}
        sub={
          reconciled === null || reconciled.matched_at === null
            ? undefined
            : // The drawing's own sub-line — *"Three batches, one credit"* — is
              // a COUNT and not a list of primary keys, which is what the
              // server serves and what B14 rule 31 requires.
              // ⚠ **TWO KEYS AND A `count`, BECAUSE ONE STRING SAID *"1 bank
              //    lines"*.** Found in Chromium, by looking (hard-won law 6) —
              //    `tsc` and every suite were green on it. i18next pluralises
              //    on the `count` variable BY NAME, so the bank-line half owns
              //    that name and the batch half is interpolated beside it.
              // `DEF-PAY-10323` — MATCHED and RECONCILED are two states and the
              // cell said neither; the batch's own status word now leads, in
              // the deposits list's own catalogue words.
              [
                t(`payments.deposits.status.${reconciled.batch_status}`),
                t("payments.detail.matchCounts", {
                  batches: reconciled.batch_count ?? 0,
                  count: reconciled.bank_line_count ?? 0,
                }),
              ].join(" · ")
        }
      >
        {reconciled === null ? (
          <Dash>{t("payments.detail.notReconciled")}</Dash>
        ) : reconciled.matched_at === null ? (
          // Banked, not yet tied to a statement. A real state, said as one.
          <Dash>{t("payments.detail.bankedNotMatched")}</Dash>
        ) : (
          // ⚠ THE BATCH'S OWN CODE, NEVER THE MATCH SET'S uuid — see the header.
          reconciled.batch_code
        )}
      </StripCell>

      <StripCell
        label={t("payments.col.status")}
        // `DEF-PAY-10016` — a returned payment keeps its own status (hard rule
        // 4: the reversal is a new row), so the fact is said beside it in the
        // reversal's own words: *Cleared* · *Returned by the bank*.
        sub={
          props.reversedFor
            ? [
                t(`payments.reverse.reason.${props.reversedFor}`, {
                  defaultValue: t("payments.status.reversed"),
                }),
                ...bounceLines(props.reversal, (key, options) => t(key, options)),
              ].join(" · ")
            : undefined
        }
      >
        <StatusPill tone={paymentStatusTone(props.status)}>
          {paymentStatusLabel(props.status, (key, params) => t(key, params))}
        </StatusPill>
      </StripCell>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE ELEVEN FACTS AND THE TWO-COLUMN BILL TABLE — moved from the row panel
// ══════════════════════════════════════════════════════════════════════════

export interface PaymentFactsProps extends RegionalDetailProps {
  row: PaymentRow;
  accountHref: string;
  /** Record links (PO 2026-10-19): the address of one applied-to bill. Absent,
   *  the bill numbers stay text. */
  billHref?: (invoiceId: string) => string;
}

/**
 * *This payment* — the eleven facts in the JSX's own order, then the bill
 * table.
 *
 * ELEVEN, and p035's *Fields* row names them: Account (a link) · Customer ·
 * Amount · Status · Type · Purpose · Method · Reference · Posted · Cleared ·
 * Memo. **All eleven stay** (p036).
 */
export function PaymentFacts(props: PaymentFactsProps) {
  const { t } = useTranslation();
  const row = props.row;
  const bills = appliedBills(row);
  const corrected = releasedByCorrection(row);

  return (
    <div>
      <FactList>
        <Fact label={t("payments.col.account")}>
          <InlineLinkAnchor href={props.accountHref}>
            {row.account_no ?? t("payments.row.noAccountNo")}
          </InlineLinkAnchor>
        </Fact>
        <Fact label={t("payments.col.customer")}>
          {row.customer_name ?? <Dash>{t("payments.row.noCustomer")}</Dash>}
        </Fact>
        <Fact label={t("payments.col.amount")}>
          <Money amount={row.amount} currency={props.currency ?? row.currency} />
        </Fact>
        <Fact label={t("payments.col.status")}>
          <StatusPill tone={paymentStatusTone(row.status)}>
            {paymentStatusLabel(row.status, (key, params) => t(key, params))}
          </StatusPill>
        </Fact>
        <Fact label={t("payments.col.type")}>
          {paymentTypeLabel(row.type, (key, params) => t(key, params))}
        </Fact>
        <Fact label={t("payments.col.purpose")}>{t(`payments.purpose.${row.purpose}`)}</Fact>
        <Fact label={t("payments.col.method")}>
          {row.method_name ?? <Dash>{t("payments.row.noMethod")}</Dash>}
        </Fact>
        <Fact label={t("payments.col.confirmation")}>
          {row.confirmation !== null && row.confirmation !== "" ? (
            <span className="font-mono">{row.confirmation}</span>
          ) : (
            <Dash />
          )}
        </Fact>
        {/* BR-PAY-021's pair, both of them, always. A null clearing date is
            `processing` — the money has not arrived, which is a STATE and not a
            missing value — so it says so rather than drawing the same dash a
            genuinely absent field draws. p036's *States* row ratifies exactly
            this: *"a null clearing date renders 'Not cleared yet', NOT the dash
            a genuinely absent field draws"*. */}
        <Fact label={t("payments.col.postedAt")}>
          <DateCell
            value={row.posted_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </Fact>
        <Fact label={t("payments.col.clearedAt")}>
          {row.cleared_at !== null ? (
            <DateCell
              value={row.cleared_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          ) : (
            <Dash>{t("payments.row.notCleared")}</Dash>
          )}
        </Fact>
        <Fact label={t("payments.form.memo")}>
          {row.memo !== null && row.memo !== "" ? row.memo : <Dash />}
        </Fact>
      </FactList>

      {/* ⚠ **`table.data-table` — B14 rule 20's ONE table type.** Two columns
          and no more: p036, *"Then a table with exactly two columns: Bill and
          Applied."* */}
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">{t("payments.detail.billCol")}</th>
            <th scope="col">{t("payments.detail.appliedCol")}</th>
          </tr>
        </thead>
        <tbody>
          {bills.length === 0 ? (
            <tr>
              <td colSpan={2}>
                {/* p036: *"a payment that met no bill draws a NAMED ABSENCE,
                    not an empty table — 'a carried credit, or money that has
                    not cleared' is a real outcome, said in words"*. */}
                <Dash>{t("payments.row.appliedToNone")}</Dash>
              </td>
            </tr>
          ) : (
            bills.map((bill) => (
              <tr key={bill.invoiceId}>
                <td>
                  {/* B14 rule 31: the bill's NUMBER, never `invoice_id`. When
                      billing could not resolve one the amount still shows,
                      because the money is the fact. */}
                  {bill.invoiceNumber === null ? (
                    <Dash>{t("payments.row.billNumberUnavailable")}</Dash>
                  ) : props.billHref !== undefined ? (
                    <InlineLinkAnchor href={props.billHref(bill.invoiceId)}>
                      {bill.invoiceNumber}
                    </InlineLinkAnchor>
                  ) : (
                    bill.invoiceNumber
                  )}
                </td>
                <td className="cell-num">
                  {bill.net !== null ? (
                    <Money amount={bill.net} currency={props.currency ?? row.currency} />
                  ) : (
                    <Dash>{t("payments.money.sumUnavailable")}</Dash>
                  )}
                  {bill.releasedBack !== null && (
                    <span className="block text-sm text-neutral-700">
                      {corrected
                        ? t("payments.row.releasedByCorrection")
                        : t("payments.row.releasedByReversal")}
                    </span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// ⑦ THE HISTORY PANEL — *"it is what makes ④ honest"* (p035)
// ══════════════════════════════════════════════════════════════════════════

/**
 * `WHEN · WHAT · WHO · NOTE`, read from `audit_log` through `P3.4`.
 *
 * ⚠ **IT SAYS NOTHING ABOUT HOW LONG THE TRAIL SURVIVES, AND THE SILENCE IS
 * DELIBERATE (`P3.18`, PO ruling 2026-09-23).** `audit_log` is pruned on a
 * retention schedule and a correction's row is pruned with everything else —
 * the server carries that as the `unavailable[]` CODE
 * `history_is_pruned_like_every_audit_row`, **for a caller to reason about and
 * never to render**. **B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN**, so
 * a panel that explained the retention policy in order to be honest would break
 * rule 33 while trying to obey the ruling. **What honesty requires here is an
 * ABSENCE: never claim permanence.** This panel claims nothing.
 *
 * ⚠ **`what` IS AN AUDIT CODE AND THE WORDS ARE THE CATALOGUE'S** (B14 rule 35).
 * A trail half in English for a Spanish-speaking clerk is what a server-side
 * sentence produces, so the code travels and the eleven catalogues translate it.
 */
export function PaymentHistoryPanel(props: {
  rows: PaymentHistoryRow[];
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The read could not be made — a DIFFERENT fact from *nothing happened*,
   *  and only one of them is safe to draw as an empty table. */
  unreadable?: boolean;
}) {
  const { t } = useTranslation();
  if (props.unreadable === true) {
    return (
      <p className="text-base text-neutral-700" role="note">
        {t("payments.detail.historyUnreadable")}
      </p>
    );
  }
  if (props.rows.length === 0) {
    return (
      <p className="text-base text-neutral-700" role="note">
        {t("payments.detail.historyEmpty")}
      </p>
    );
  }
  return (
    <table className="data-table" data-testid="payment-history">
      <thead>
        <tr>
          <th scope="col">{t("payments.detail.historyWhen")}</th>
          <th scope="col">{t("payments.detail.historyWhat")}</th>
          <th scope="col">{t("payments.detail.historyWho")}</th>
          <th scope="col">{t("payments.detail.historyNote")}</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row, index) => (
          <tr key={`${row.at}-${row.what}-${index}`}>
            <td>
              <DateCell value={row.at} timeZone={props.timeZone} dateFormat={props.dateFormat} />
            </td>
            <td>
              {/* B14 rule 35 — the CODE resolves against the catalogue; an
                  unknown code says so rather than printing itself, because a
                  raw `payment.receipt_resent` on screen is an internal
                  reference and rule 31 forbids it. */}
              {t(`payments.audit.${row.what}`, {
                defaultValue: t("payments.detail.historyUnknownAction"),
              })}
            </td>
            <td>
              {/* A NAME, never a user id (B14 rule 31). A removed user keeps
                  their history and the screen states the absence. */}
              {row.who?.name ?? <Dash>{t("payments.detail.historyNoWho")}</Dash>}
            </td>
            <td>
              {/* `DEF-PAY-10017` — a closed reason code reads in the catalogue's
                  words; words a person typed are printed as typed. */}
              {row.note_key
                ? t(row.note_key, { defaultValue: row.note ?? "" })
                : row.note !== null && row.note !== ""
                  ? row.note
                  : <Dash />}
              {/* DEF-PAY-10698 · LBX-04 — a reversal's bank memo and NSF fee. */}
              {bounceLines(row, (key, options) => t(key, options)).map((line) => (
                <div key={line} className="text-sm text-neutral-700">
                  {line}
                </div>
              ))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Every fact the page needs, in one shape, so the page reads as a page and
 *  not as a fetch. */
export type PaymentDetailData = PaymentDetail;
