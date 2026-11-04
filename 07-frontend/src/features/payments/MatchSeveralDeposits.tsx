// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10780 (one bank line to several deposits, from the line)
// Rulings:  decision log 2026-10-30 "Eight open payment questions answered" —
//           Q2 = A, the entry point is an ADD button on Reconcile a bank
//           statement · 2026-10-30 "Match to several deposits mock-up approved"
//           — https://claude.ai/artifact/NjuPsrGvZNwtfU74ctoCdU, *"this is
//           correct"*, approved as drawn
// Screens:  S37's statement (Finance › Deposits & Bank › Reconcile a bank
//           statement, Finance blueprint p56)
// Rules:    CS-17 (a set ties EXACTLY — never within tolerance) · B14 rule 21
//           (Tailwind, listed on route-b-migrated.txt in the same commit) ·
//           rule 31 (the deposit's LABEL, never its id) · rule 33 · rule 43
// ───────────────────────────────────────────────────────
// The worked case the PO approved: the Hy-Vee transfer **CFP-STL-1029,
// $833.30**, is three deposits — DEP-261029-0043 $266.80 + DEP-261029-0044
// $313.00 + DEP-261021-0031 $253.50. Tick two and the dialog says *Still to
// find $253.50*; tick the third and it says *Equals the bank line* and
// *Match 3 deposits* lights; tick the $412.15 counter deposit as well and it
// says *Over by $412.15*.
//
// ⚠ **IT CALLS THE EXISTING `POST /bank-rec/match-set` AND ADDS NO RULE.** The
// server refuses a set that does not foot, a deposit outside the matching
// window and a reconciled deposit, by name; this dialog only refuses to SEND
// a set it can already see does not foot, which is the mock-up's own
// behaviour (Match enabled only when the ticked total equals the line). Any
// other refusal is the server's sentence, shown in the dialog.
//
// ⚠ **ONLY A CREDIT GETS THE BUTTON.** Deposits are money IN; a line the bank
// took OUT can never equal a set of them, so offering the button there would
// be a control that cannot succeed. Money-out lines keep Match to payment /
// Bank fee on the import review.
//
// The arithmetic is scaled BigInt through `depositsShared` — never a float.
import { useState } from "react";

import { useTranslation } from "react-i18next";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { createMatchSet } from "@/api/bankRecEndpoints";
import type { DepositBatchRow, MatchSetResult, StatementLineRow } from "@/api/bankRecEndpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { ModalShell } from "@/components/FormModal";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { WorkingButton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { depositOwnerLabel, residualOf, scaledDecimal, sumOf } from "./depositsShared";

/** The line the dialog is about — read off the statement's unexplained rows. */
export interface SeveralDepositsLine {
  bank_line_id: string;
  reference: string | null;
  posted_on: string | null;
  amount: string | null;
}

/** True only for a credit the bank posted — see the module header. */
export function canMatchSeveral(amount: string | null): boolean {
  if (amount === null) {
    return false;
  }
  const scaled = scaledDecimal(amount);
  return scaled !== null && scaled > 0n;
}

export type SeveralVerdict =
  | { kind: "none"; ticked: string }
  | { kind: "short"; ticked: string; left: string }
  | { kind: "over"; ticked: string; over: string }
  | { kind: "equal"; ticked: string };

/**
 * The running total and what it means against the bank line. `left` and
 * `over` are UNSIGNED: the word carries the direction (*Still to find* /
 * *Over by*), exactly as the mock-up draws them.
 */
export function severalVerdict(lineAmount: string, tickedAmounts: readonly string[]): SeveralVerdict {
  const ticked = sumOf(tickedAmounts) ?? "0";
  const left = residualOf(lineAmount, tickedAmounts);
  const scaled = left === null ? null : scaledDecimal(left);
  if (tickedAmounts.length === 0 || scaled === null) {
    return { kind: "none", ticked };
  }
  if (scaled === 0n) {
    return { kind: "equal", ticked };
  }
  if (scaled > 0n) {
    return { kind: "short", ticked, left: left as string };
  }
  return { kind: "over", ticked, over: (left as string).slice(1) };
}

/** Where a deposit came from — the tender's name, or whose till banked it. */
export function depositSource(batch: DepositBatchRow, t: Translator): string {
  return batch.method_name ?? depositOwnerLabel(batch.channel ?? null, t);
}

function verdictText(verdict: SeveralVerdict, currency: string, t: Translator, locale?: string) {
  switch (verdict.kind) {
    case "equal":
      return t("payments.deposits.several.equals");
    case "short":
      return t("payments.deposits.several.stillToFind", {
        amount: formatMoney(verdict.left, currency, locale),
      });
    case "over":
      return t("payments.deposits.several.overBy", {
        amount: formatMoney(verdict.over, currency, locale),
      });
    default:
      return "";
  }
}

/** Money columns right-aligned. `PlainTable` sets `text-left` on every cell
 *  through a descendant selector, which a plain `text-right` on the cell
 *  cannot beat; an attribute-scoped variant can, without `!important`. */
const NUMERIC_COLUMN = "[&_td[data-num]]:text-right [&_th[data-num]]:text-right";

const VERDICT_TONE: Record<SeveralVerdict["kind"], string> = {
  none: "bg-neutral-100 text-neutral-900",
  short: "bg-neutral-100 text-neutral-900",
  over: "bg-danger-100 text-danger-700",
  equal: "bg-success-100 text-success-700",
};

export function MatchSeveralDepositsModal(props: {
  line: SeveralDepositsLine;
  /** The statement review's own `open_batches` — bankable, not yet matched. */
  openBatches: readonly DepositBatchRow[];
  currency: string;
  locale?: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  onDone: (result: MatchSetResult, count: number) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [ticked, setTicked] = useState<string[]>([]);
  const [working, setWorking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const lineAmount = props.line.amount ?? "0";
  const chosen = props.openBatches.filter((batch) => ticked.includes(batch.id));
  const verdict = severalVerdict(
    lineAmount,
    chosen.map((batch) => batch.recorded_total ?? "0"),
  );
  const ready = verdict.kind === "equal";
  const label = props.line.reference ?? t("payments.deposits.noReference");

  function toggle(batchId: string): void {
    setRefusal(null);
    setTicked((current) =>
      current.includes(batchId) ? current.filter((one) => one !== batchId) : [...current, batchId],
    );
  }

  async function submit(): Promise<void> {
    if (!ready || working) {
      return;
    }
    setWorking(true);
    setRefusal(null);
    try {
      const result = await createMatchSet(
        {
          bank_line_ids: [props.line.bank_line_id],
          batch_ids: chosen.map((batch) => batch.id),
          // BR-TEN-043 — the caller names the moment; the server reads no clock.
          occurred_at: new Date().toISOString(),
        },
        props.client,
      );
      props.onDone(result, chosen.length);
    } catch (error) {
      setRefusal(
        isApiError(error)
          ? apiErrorText(error, translate) || t(formErrorEnvelope(error).message_key)
          : t("api.error.unexpected"),
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <ModalShell title={t("payments.deposits.several.title")} onClose={props.onClose} busy={working}>
      <div className="modal-body" data-match-several="">
        <p className="m-0 mb-3 text-sm text-neutral-700" data-several-line="">
          {label} ·{" "}
          {props.line.posted_on === null ? null : (
            <DateCell
              value={props.line.posted_on}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          )}{" "}
          · {t("payments.deposits.several.bankShows")}{" "}
          <MoneyCell amount={lineAmount} currency={props.currency} locale={props.locale} />
        </p>
        {props.openBatches.length === 0 ? (
          <p className="m-0 text-base text-neutral-700" role="note">
            {t("payments.deposits.noOpenBatches")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <PlainTable className={NUMERIC_COLUMN}>
              <thead>
                <tr>
                  <th scope="col">
                    <span className="sr-only">{t("payments.deposits.several.tick")}</span>
                  </th>
                  <th scope="col">{t("payments.deposits.several.colDeposit")}</th>
                  <th scope="col">{t("payments.deposits.several.colSource")}</th>
                  <th scope="col">{t("payments.deposits.several.colDay")}</th>
                  <th scope="col" data-num="">
                    {t("payments.deposits.kpi.weRecorded")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {props.openBatches.map((batch) => {
                  const id = `several-${batch.id}`;
                  return (
                    <tr key={batch.id}>
                      <td>
                        <input
                          id={id}
                          type="checkbox"
                          checked={ticked.includes(batch.id)}
                          onChange={() => toggle(batch.id)}
                          aria-label={t("payments.deposits.several.tickOne", {
                            deposit: batch.code,
                          })}
                        />
                      </td>
                      <td>
                        {/* The deposit's LABEL, never its id (B14 rule 31). */}
                        <label htmlFor={id}>{batch.code}</label>
                      </td>
                      <td>{depositSource(batch, translate)}</td>
                      <td>
                        {batch.deposited_on === null ? null : (
                          <DateCell
                            value={batch.deposited_on}
                            timeZone={props.timeZone}
                            dateFormat={props.dateFormat}
                          />
                        )}
                      </td>
                      <td data-num="">
                        <MoneyCell
                          amount={batch.recorded_total ?? "0"}
                          currency={props.currency}
                          locale={props.locale}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </PlainTable>
          </div>
        )}
        <p
          className={`m-0 mt-3 flex flex-wrap justify-between gap-2 px-3 py-2 text-base font-semibold ${VERDICT_TONE[verdict.kind]}`}
          data-several-verdict={verdict.kind}
          aria-live="polite"
        >
          <span>
            {t("payments.deposits.several.ticked", {
              count: chosen.length,
              amount: formatMoney(verdict.ticked, props.currency, props.locale),
            })}
          </span>
          <span>{verdictText(verdict, props.currency, translate, props.locale)}</span>
        </p>
        {refusal !== null && (
          <RefusalStrip role="alert" data-several-refusal="">
            {refusal}
          </RefusalStrip>
        )}
      </div>
      <div className="modal-foot">
        <Button variant="ghost" onClick={props.onClose}>
          {t("forms.cancel")}
        </Button>
        <WorkingButton working={working} onClick={() => void submit()} disabled={!ready}>
          {chosen.length > 1
            ? t("payments.deposits.several.matchN", { count: chosen.length })
            : t("payments.deposits.several.match")}
        </WorkingButton>
      </div>
    </ModalShell>
  );
}

/** The row's two buttons: the existing *Explain* and the new one (a credit only). */
export function UnexplainedLineActions(props: {
  amount: string | null;
  onExplain: () => void;
  onMatchSeveral: () => void;
  /** P2 = A (PO 2026-10-31) — the server's offer for a line the bank took
   *  OUT; each button shows only when it is offered AND its handler is wired. */
  actions?: readonly ("match_return" | "bank_fee")[];
  onMatchReturn?: () => void;
  onBankFee?: () => void;
}) {
  const { t } = useTranslation();
  const offered = props.actions ?? [];
  return (
    <div className="flex flex-wrap gap-2">
      {offered.includes("match_return") && props.onMatchReturn !== undefined && (
        <Button variant="secondary" onClick={props.onMatchReturn} data-line-match-return="">
          {t("payments.deposits.lines.matchReturn")}
        </Button>
      )}
      {offered.includes("bank_fee") && props.onBankFee !== undefined && (
        <Button variant="secondary" onClick={props.onBankFee} data-line-bank-fee="">
          {t("payments.deposits.lines.bankFee")}
        </Button>
      )}
      <Button variant="secondary" onClick={props.onExplain}>
        {t("payments.deposits.statement.explain")}
      </Button>
      {canMatchSeveral(props.amount) && (
        <Button variant="secondary" onClick={props.onMatchSeveral} data-match-several-open="">
          {t("payments.deposits.several.open")}
        </Button>
      )}
    </div>
  );
}

/**
 * The lines tied inside a set, read off the statement review's own rows
 * (`state: "set_matched"`). After the match the line leaves *Lines nobody has
 * explained* — the server stops counting it — and reads here as the mock-up
 * draws it: *Matched · 3 deposits*, with the deposits it was tied to.
 */
export function SetMatchedLines(props: {
  rows: readonly StatementLineRow[];
  currency: string;
  locale?: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const rows = props.rows.filter((row) => row.state === "set_matched");
  if (rows.length === 0) {
    return null;
  }
  return (
    <div className="overflow-x-auto" data-set-matched-lines="">
      <PlainTable className={NUMERIC_COLUMN}>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.several.colLine")}</th>
            <th scope="col">{t("payments.deposits.col.date")}</th>
            <th scope="col" data-num="">
              {t("payments.deposits.kpi.bankShows")}
            </th>
            <th scope="col">{t("payments.deposits.several.colMatchedTo")}</th>
            <th scope="col">{t("payments.deposits.several.colState")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const codes = row.match_set_batch_codes ?? [];
            return (
              <tr key={row.bank_line_id}>
                <td>{row.reference ?? t("payments.deposits.noReference")}</td>
                <td>
                  {row.posted_on === null ? null : (
                    <DateCell
                      value={row.posted_on}
                      timeZone={props.timeZone}
                      dateFormat={props.dateFormat}
                    />
                  )}
                </td>
                <td data-num="">
                  <MoneyCell
                    amount={row.amount ?? "0"}
                    currency={props.currency}
                    locale={props.locale}
                  />
                </td>
                <td>{codes.join(", ")}</td>
                <td>
                  <StatusPill tone="success">
                    {t("payments.deposits.several.matchedState", { count: codes.length })}
                  </StatusPill>
                </td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    </div>
  );
}
