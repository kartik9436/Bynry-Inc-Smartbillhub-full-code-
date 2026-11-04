// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-021 (S38 — the three-step wizard: upload the statement,
//           review what auto-matched, and pair by hand what the exact rule
//           could not)
//           Screens: S38 · S37 · S40
// Rules:    BR-PAY-019 (auto-match on amount EQUAL + date within the tenant's
//           tolerance; every difference carries reason + GL) · BR-PAY-021 (the
//           match compares the bank's posting date) · BR-PAY-028 (file + tags
//           import idempotency 🔒 — the same statement twice is REFUSED with
//           who and when) · BR-PAY-035 (no force match) · BR-PAY-004 (a
//           reconciled batch is not a candidate) · BR-SHL-020 · BR-SHL-025
// ───────────────────────────────────────────────────────
// S38 — the deposits bank import. ⚠ **THE TITLE WAS CUT TO "Import a
// statement" ON 2026-09-24 (`P1.19`), AND THIS LINE QUOTED THE OLD ONE.** The
// Finance blueprint p053 names it as the one string it tags `P1.19` by name:
// the product's title was a TEN-WORD SENTENCE — *"Import a bank statement and
// match it to your deposits"* — and B14 rule 33 caps a heading at three words.
// The drawing supplies the replacement, so the words are the agreement's and
// not a lane's. `payments.deposits.wizardTitle`, all eleven catalogues.
//
// ══════════════════════════════════════════════════════════════════════════
// THE FILE NEVER TOUCHES THIS SCREEN'S LOGIC
// ══════════════════════════════════════════════════════════════════════════
// The browser reads the bytes and base64s them; `apps/payments/lockbox.py` is
// the ONLY parser in this product, and it stays that way. Nothing here counts
// rows, guesses a delimiter or reads a header — a second parser would be a
// second place a bank's CSV dialect is understood, and the two would disagree.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE PROTOTYPE DRAWS THAT THIS DOES NOT
// ══════════════════════════════════════════════════════════════════════════
//   · **The "connect your bank" (Plaid) card** on step 1. EP-PAY-06 §Scope puts
//     it OUT of v1 — an integrations seam with no ratified rule — so it is not
//     drawn at all rather than drawn dead.
//   · **The step-2 KPI figures "31 lines · 28 matched · 3 need a look".** Those
//     are a demo statement's. Every tile here is counted server-side from the
//     rows this screen shows.
//   · **"Confirm & reconcile" as step 3.** The prototype's third step
//     reconciles every matched batch at once. BR-PAY-019 requires a reason AND
//     a GL on every DIFFERENCE, and a bulk confirm cannot collect one — so this
//     wizard ends by handing each line to S39/S40, where the explanation is
//     given. The batches that tie EXACTLY still need a person to reconcile
//     them, and that is a real limitation, REPORTED here rather than papered
//     over with a bulk button that would silently skip the exceptions.
//
// ══════════════════════════════════════════════════════════════════════════
// IT IS ON THE SHARED `WizardFrame` SINCE 2026-09-24 — `P1.14` · `DEF-PAY-6558`
// ══════════════════════════════════════════════════════════════════════════
// Finance blueprint p053–p054, read as IMAGES (B14 rule 42). p053's correction
// box states what was here, verbatim: *"The previous version of this document
// drew this as two screens with a step strip. It is one page: step 1 always
// renders, step 2 is a conditional panel below it (`{statementId !== null &&
// …}`). There is no rail, no fence and no shared frame."* And: *"No Finance or
// Payments file imports `WizardFrame`. Twenty files across tenancy, assets,
// metering, rating and customers use it; this one — named `BankImportWizard.tsx`
// — builds its steps as two `<h3>` headings."* p054's RULES row: *"Breaks ✗ B14
// rule 3 (a 2+ stage flow uses the numbered step rail) · ✗ BR-SHL-018 · ✗
// BR-SHL-019"*.
//
// **TWO STEPS, AND THE THIRD WORD ON THE DRAWN RAIL IS A STEP THIS PRODUCT HAS
// ALREADY DECLINED.** p053 draws `1 Upload — 2 Review — 3 Confirm`; p053's own
// "Components to use" table says `WizardFrame · the two steps`, and p054's
// PRIMARY ACTION row says *"`Upload ↑`, then the frame's single commit"*. B14
// rule 37 is written for exactly this — two parts of one blueprint stating the
// same fact differently — and says to build the shape they agree on. They agree
// on Upload then Review. **They disagree about Confirm, and the repo already
// settled it:** exception (2) above, unchanged since 2026-08-16, records that a
// bulk confirm cannot collect the reason and GL `BR-PAY-019` requires on every
// difference. Building a third step here would be resolving that by choosing a
// value, which the prime directive forbids.
//
// **WHAT THE MOVE ACTUALLY BUYS, AND IT IS THE OUTCOME ROW'S OWN SENTENCE** —
// *"A clerk can step back to fix the account without losing the upload"*:
// `reached` is the forward fence (BR-SHL-018), a completed step is
// back-clickable, and the account, the dates and the statement all live in this
// component's state, so a back-jump retains every one of them. The upload is
// single-flighted by the frame with A18 §3's working state and A18 §4's
// failure-with-state-preserved, which is what `BR-PAY-028`'s duplicate refusal
// has always needed and never had: it NAMES who imported the file first and
// when, and that sentence used to land in a bare `<p>` under a file input.
import { useMemo, useRef, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {useNavigate} from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getBankAccounts,
  getStatementReview,
  importBankStatement,
  matchBankLine,
} from "@/api/bankRecEndpoints";
import type {
  LinePostingResult,
  StatementLineRow,
  StatementReview,
} from "@/api/bankRecEndpoints";
import { Button } from "@/components/Button";
import { SelectField, TextField } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { InlineLink, InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { isDenied, useAccessCell } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BANKREC_PERMISSION,
  DEPOSITS_ROUTE,
  GapNotes,
  depositBatchRoute,
  matchStateLabel,
  matchStateTone,
} from "./depositsShared";
import { BankFeeForm, MatchReturnForm, matchedToText } from "./StatementLineActions";

import "./payments.css";

export const bankAccountsQueryKey = ["payments", "bank-accounts"] as const;
export const statementQueryKey = (id: string) => ["payments", "bank-statement", id] as const;

/** The bytes, base64, without a second parser anywhere near them. */
export async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

// ── Step 2's review table ─────────────────────────────────────────────────

export function StatementReviewTable(props: {
  review: StatementReview;
  t: Translator;
  locale?: string;
  batchPath: (batchId: string) => string;
  onPair: (bankLineId: string) => void;
  /** LBX-05 — a line the bank took OUT: match it to the payment it returns,
   *  or post it as the bank's fee. Absent hides both (a read-only table). */
  onLineAction?: (kind: "match_return" | "bank_fee", row: StatementLineRow) => void;
}) {
  const { review, t } = props;
  return (
    <div className="pay-table-scroll">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.deposits.col.bankPosting")}</th>
            <th scope="col">{t("payments.deposits.col.bankReference")}</th>
            <th scope="col" className="fin-num">
              {t("payments.deposits.col.bankAmount")}
            </th>
            <th scope="col">{t("payments.deposits.col.matchedDeposit")}</th>
            <th scope="col" className="fin-num">
              {t("payments.deposits.col.ourAmount")}
            </th>
            <th scope="col" className="fin-num">
              {t("payments.deposits.col.difference")}
            </th>
            <th scope="col">{t("payments.deposits.col.match")}</th>
            <th scope="col">{t("payments.deposits.col.fix")}</th>
          </tr>
        </thead>
        <tbody>
          {review.rows.map((row) => (
            <tr
              key={row.bank_line_id}
              className={row.state === "auto" ? undefined : "pay-row-attention"}
            >
              <td>{row.posted_on ?? ""}</td>
              <td>{row.reference ?? t("payments.deposits.noReference")}</td>
              <td className="fin-num">
                <MoneyCell
                  amount={row.amount ?? "0"}
                  currency={row.currency}
                  locale={props.locale}
                />
              </td>
              <td>
                {row.batch_id === null ? (
                  // NOT an em dash. An unmatched line is either a candidate a
                  // human should look at or a credit that is none of ours, and
                  // the two need different work — the state column says which
                  // and this cell says plainly that nothing is tied.
                  <span className="pay-absent">{t("payments.deposits.notTied")}</span>
                ) : (
                  <InlineLinkTo to={props.batchPath(row.batch_id)}>
                    {row.batch_code}
                  </InlineLinkTo>
                )}
              </td>
              <td className="fin-num">
                {row.recorded_total === null ? (
                  <span className="pay-absent">{t("payments.deposits.notTied")}</span>
                ) : (
                  <MoneyCell
                    amount={row.recorded_total}
                    currency={row.currency}
                    locale={props.locale}
                  />
                )}
              </td>
              <td className="fin-num">
                {row.difference === null ? (
                  <span className="pay-absent">{t("payments.deposits.notTied")}</span>
                ) : (
                  <MoneyCell
                    amount={row.difference}
                    currency={row.currency}
                    locale={props.locale}
                  />
                )}
              </td>
              <td>
                <StatusPill tone={matchStateTone(row.state)}>
                  {matchStateLabel(row.state, t)}
                </StatusPill>
              </td>
              <td>
                {props.onLineAction !== undefined &&
                (row.actions ?? []).includes("match_return") ? (
                  <span className="pay-inline-field">
                    <InlineLink
                      type="button"
                      onClick={() => props.onLineAction?.("match_return", row)}
                    >
                      {t("payments.deposits.lines.matchReturn")}
                    </InlineLink>
                    <InlineLink
                      type="button"
                      onClick={() => props.onLineAction?.("bank_fee", row)}
                    >
                      {t("payments.deposits.lines.bankFee")}
                    </InlineLink>
                  </span>
                ) : row.state === "explained" ? (
                  // B14 rule 34's one pair of words: a matched return or a fee
                  // line is IN THE BOOKS; an ordinary explanation is RECORDED.
                  <>
                    <div className="pay-absent">
                      {row.posted === true
                        ? t("payments.deposits.lines.inTheBooks")
                        : t("payments.deposits.lines.recorded")}
                    </div>
                    {/* P1 a1-3 (PO 2026-10-31) — whose cheque it was, on its
                        own line under the state. */}
                    {matchedToText(
                      row.reference,
                      row.returned_customer_name,
                      row.returned_account_no,
                    ) !== null && (
                      <div data-matched-to="">
                        {matchedToText(
                          row.reference,
                          row.returned_customer_name,
                          row.returned_account_no,
                        )}
                      </div>
                    )}
                  </>
                ) : row.state === "needs_a_look" ? (
                  <InlineLink
 type="button"
 onClick={() => props.onPair(row.bank_line_id)}
                  >
                    {t("payments.deposits.pair")}
                  </InlineLink>
                ) : row.state === "matched_off_by" && row.batch_id !== null ? (
                  // Tied, and the difference is still owed an explanation —
                  // which is S40's job, on the batch. The wizard hands it over
                  // rather than growing a second reconcile form.
                  <InlineLinkTo to={props.batchPath(row.batch_id)}>
                    {t("payments.deposits.resolve")}
                  </InlineLinkTo>
                ) : (
                  <span className="pay-absent">
                    {row.state === "auto"
                      ? t("payments.deposits.nothingToDo")
                      : t("payments.deposits.notOurs")}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface BankImportWizardProps {
  client?: ApiClient; // test seam
  locale?: string;
}

/** A statement balance as the bank prints it — signed (an overdrawn account
 *  closes negative), up to 4 decimals (hard rule 2). Blank is NOT zero. */
export function isStatementBalance(value: string): boolean {
  return /^-?\d+(\.\d{1,4})?$/.test(value.trim());
}

export function BankImportWizard(props: BankImportWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();
  const cell = useAccessCell(BANKREC_PERMISSION, client);
  const fileRef = useRef<HTMLInputElement>(null);

  const [bankAccountId, setBankAccountId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  // W3 (`DEF-PAY-10767`, PO 2026-10-30 *"W3-A"*): the statement's own two
  // figures, typed as printed, so the reconciliation can say "Bank shows
  // $616.10 · books $616.10". Strings end to end — never a float (rule 2).
  const [openingBalance, setOpeningBalance] = useState("");
  const [closingBalance, setClosingBalance] = useState("");
  const [statementId, setStatementId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pairing, setPairing] = useState<string | null>(null);
  const [lineAction, setLineAction] = useState<{
    kind: "match_return" | "bank_fee";
    row: StatementLineRow;
  } | null>(null);
  /**
   * ⚠ **THE FORWARD FENCE (`BR-SHL-018`), AND `reached` IS THE HALF THAT
   * MATTERS.** `step` is where the clerk is; `reached` is the furthest step
   * they have legitimately got to, so a completed step is back-clickable and an
   * unreached one is not. A wizard passing `reached: step` has no fence at all
   * — a pasted `?step=2` would open the review over a statement that was never
   * uploaded, which is the assertion `cr138_p4_refunds_and_notice_walkthrough`
   * had to write for the notice wizard one screen over.
   */
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });

  const accountsQuery = useQuery({
    queryKey: bankAccountsQueryKey,
    queryFn: () => getBankAccounts(client),
    retry: false,
  });

  const reviewQuery = useQuery({
    queryKey: statementQueryKey(statementId ?? ""),
    queryFn: () => getStatementReview(statementId ?? "", client),
    retry: false,
    enabled: statementId !== null,
  });

  const importMutation = useMutation({
    mutationFn: async (file: File) =>
      importBankStatement(
        {
          bank_account_id: bankAccountId,
          period_start: periodStart,
          period_end: periodEnd,
          opening_balance: openingBalance.trim(),
          closing_balance: closingBalance.trim(),
          file_name: file.name,
          file_base64: await fileToBase64(file),
          // BR-TEN-043 — the CALLER states the moment. The browser is the
          // caller; the server reads no clock (gate G6).
          imported_at: new Date().toISOString(),
        },
        client,
      ),
  });

  const pairMutation = useMutation({
    mutationFn: (input: { batchId: string; bankLineId: string }) =>
      matchBankLine(
        input.batchId,
        { bank_line_id: input.bankLineId, occurred_at: new Date().toISOString() },
        client,
      ),
  });


  const accounts = accountsQuery.data ?? [];
  const review = reviewQuery.data;
  const ready =
    bankAccountId !== "" &&
    periodStart !== "" &&
    periodEnd !== "" &&
    isStatementBalance(openingBalance) &&
    isStatementBalance(closingBalance);

  /**
   * ⚠ **THE UPLOAD IS THE WIZARD'S ONE TRANSACTIONAL CALL AND IT IS NOW THE
   * FRAME'S (`BR-SHL-019`, `P1.14`).** It used to fire from the file input's
   * `onChange`, so there was no working state, no single-flight guard and no
   * A18 §4 failure frame — `BR-PAY-028`'s duplicate refusal, which names who
   * imported the file first and when, landed in a bare `<p>` under the input.
   *
   * It is a `WizardStepVerdict`, which the frame explicitly permits to do the
   * work its own Continue implies — *"a step may therefore do the work its own
   * Continue implies and answer when it is done"* — and the frame single-flights
   * the press, so a second click is not a second import.
   *
   * ⚠ **AN ALREADY-UPLOADED STATEMENT ADVANCES WITHOUT RE-SENDING.** A clerk
   * who steps back to fix the account and forward again must not write every
   * bank line a second time; `BR-PAY-028` would refuse it by name, but the
   * refusal would read as a defect rather than as the guard working.
   */
  async function uploadStep(): Promise<boolean | string> {
    if (statementId !== null) {
      return true; // already imported — a back-jump forward is not a second import
    }
    const file = fileRef.current?.files?.[0];
    if (file === undefined) {
      // A STRING blocks and says why. The generic *"fill in what's marked
      // above"* is wrong here: nothing is marked, because the unmet condition
      // is a file rather than a field (DEF-936's whole shape).
      return t("payments.deposits.form.fileRequired");
    }
    setUploadError(null);
    try {
      const result = await importMutation.mutateAsync(file);
      setStatementId(result.statement_import_id);
      toast(t("payments.deposits.imported", { lines: result.line_count }));
      await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
      return true;
    } catch (error) {
      // BR-PAY-028's duplicate refusal lands here, and it NAMES who imported the
      // file first and when. Showing it is the whole control: silently
      // re-importing would write every bank line a second time and every one
      // would look like money the bank sent twice.
      const reason = isApiError(error)
        ? apiErrorText(error, translate)
        : t("api.error.unexpected");
      if (fileRef.current !== null) {
        // Cleared so the SAME file can be chosen again after a refusal is fixed.
        fileRef.current.value = "";
      }
      return reason;
    }
  }

  async function handlePair(batchId: string): Promise<void> {
    if (pairing === null) {
      return;
    }
    try {
      const result = await pairMutation.mutateAsync({ batchId, bankLineId: pairing });
      setPairing(null);
      // A pairing is NOT a reconcile. The toast says what is still owed so
      // nobody reads "matched" as "done" (BR-PAY-035 — the difference must be
      // explained with a reason and a GL before anything reconciles).
      //
      // ⚠ THE FIGURE GOES THROUGH THE ONE MONEY FORMATTER, and it did not on
      // the first pass: the toast read **"Paired — -147.500000 still to
      // explain"** in a browser — the raw NUMERIC(18,6) string, with no
      // currency beside it. Both halves are money law (CLAUDE.md rule 2, and
      // BR-SHL-023's single formatting path), and a toast is exactly the place
      // that gets forgotten because no cell renders it. Found by looking at the
      // running app (hard-won law 6) and by nothing else.
      toast(
        t("payments.deposits.paired", {
          difference: formatMoney(result.difference, result.currency, props.locale),
        }),
      );
      await queryClient.invalidateQueries({ queryKey: statementQueryKey(statementId ?? "") });
      await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
    } catch (error) {
      setUploadError(
        isApiError(error) ? apiErrorText(error, translate) : t("api.error.unexpected"),
      );
    }
  }

  /** LBX-05 — a returned line matched or a fee posted: say what landed. */
  async function lineActionDone(result: LinePostingResult): Promise<void> {
    setLineAction(null);
    toast(
      !result.created
        ? t("payments.deposits.lines.replay")
        : result.posted
          ? t("payments.deposits.lines.done")
          : t("payments.deposits.lines.linked"),
    );
    await queryClient.invalidateQueries({ queryKey: statementQueryKey(statementId ?? "") });
    await queryClient.invalidateQueries({ queryKey: ["payments", "bank-reconciliation"] });
    await queryClient.invalidateQueries({ queryKey: ["payments", "statement-review"] });
  }

  /**
   * ⚠ **THE FRAME'S COMMIT, AND WHAT IT HONESTLY IS.**
   *
   * Every write this flow makes has already landed by the time a clerk reaches
   * it — the statement on step 1, each hand-pairing on step 2 — so `Done ✓`
   * WRITES NOTHING and says so here rather than pretending. It refuses while
   * the review has not arrived, which is the one state where leaving would hide
   * work the clerk has not seen.
   *
   * ⚠ **THE THIRD STEP p053 DRAWS IS NOT MISSING, IT IS DECLINED.** A bulk
   * *Confirm & reconcile* cannot collect the reason and GL `BR-PAY-019` requires
   * on every difference — exception (2) in this file's own lifecycle notes,
   * recorded 2026-08-16 and unchanged. Building one here to fill the frame's
   * commit slot would resolve a settled design point by choosing a value.
   */
  async function finish(): Promise<WizardCommitOutcome> {
    if (statementId === null || review === undefined) {
      return { ok: false, reason: t("payments.deposits.wizardNotReviewed") };
    }
    await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
    return { ok: true };
  }

  // ── The two steps, as the shared frame's own shape (`P1.14`) ─────────────
  //
  // ⚠ **`content` IS BUILT FROM THIS COMPONENT'S STATE, AND THAT IS WHAT
  // RETAINS THE VALUES ON A BACK-JUMP** (`BR-SHL-018`) — the frame's own words.
  // The account, the dates and the statement id all live above; stepping back
  // re-renders the same inputs over the same state rather than remounting an
  // empty form.
  //
  // ⚠ **NEITHER PANEL CARRIES AN `<h3>` ANY MORE.** The rail names the steps,
  // and a heading repeating the rail's own word would be two names for one
  // step — B14 rule 2's argument, one level down.
  const stepOne = (
    <Panel>
      {accountsQuery.isLoading ? (
        <LoadingSkeleton variant="card" />
      ) : accounts.length === 0 ? (
        // A REAL and common first-run state, said plainly. `import_bank_
        // statement` refuses an account that is not this tenant's live one, so
        // an empty picker is the honest shape rather than a form that fails on
        // submit (BR-SHL-025).
        <p className="pay-absent" role="note">
          {t("payments.deposits.noBankAccounts")}
        </p>
      ) : (
        <>
          <SelectField
            id="bank_account_id"
            label={t("payments.deposits.form.bankAccount")}
            value={bankAccountId}
            onChange={setBankAccountId}
            required
            placeholder={t("payments.deposits.form.bankAccountPlaceholder")}
            options={accounts.map((account) => ({
              value: account.id,
              label: account.mask === null ? account.name : `${account.name} ••${account.mask}`,
            }))}
          />
          <TextField
            id="period_start"
            label={t("payments.deposits.form.periodStart")}
            value={periodStart}
            onChange={setPeriodStart}
            required
            placeholder="2026-08-01"
            help={t("payments.deposits.form.periodHelp")}
          />
          <TextField
            id="period_end"
            label={t("payments.deposits.form.periodEnd")}
            value={periodEnd}
            onChange={setPeriodEnd}
            required
            placeholder="2026-08-14"
          />
          <TextField
            id="opening_balance"
            label={t("payments.deposits.form.openingBalance")}
            value={openingBalance}
            onChange={setOpeningBalance}
            numeric
            required
            placeholder="0.00"
            help={t("payments.deposits.form.balanceHelp")}
          />
          <TextField
            id="closing_balance"
            label={t("payments.deposits.form.closingBalance")}
            value={closingBalance}
            onChange={setClosingBalance}
            numeric
            required
            placeholder="0.00"
          />
          <div className="field">
            <label htmlFor="statement_file">{t("payments.deposits.form.file")}</label>
            <p className="field-help">{t("payments.deposits.form.fileHelp")}</p>
            {/* ⚠ **IT NO LONGER UPLOADS ON `onChange` — `Continue` DOES**
                (`P1.14`). Choosing a file is not the act; sending it is, and the
                frame is what gives that act a working state, a single-flight
                guard and a failure that keeps every entered value. */}
            <input
              ref={fileRef}
              id="statement_file"
              type="file"
              className="input"
              accept=".csv,text/csv"
              disabled={!ready || importMutation.isPending || statementId !== null}
            />
            {!ready && (
              <p className="pay-absent" role="note">
                {t("payments.deposits.form.fileBlocked")}
              </p>
            )}
          </div>
          {uploadError !== null && (
            <p className="form-message" role="alert">
              {uploadError}
            </p>
          )}
        </>
      )}
    </Panel>
  );

  const stepTwo = (
    <Panel>
      {reviewQuery.isLoading || review === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
          <KPIStrip
            kpis={[
              {
                id: "lines",
                label: t("payments.deposits.kpi.bankLines"),
                value: review.tiles.lines,
              },
              {
                id: "auto",
                label: t("payments.deposits.kpi.matched"),
                value: review.tiles.auto,
                detail: t("payments.deposits.kpi.matchedDetail"),
              },
              {
                id: "look",
                label: t("payments.deposits.kpi.needALook"),
                value: review.tiles.needs_a_look + review.tiles.matched_off_by,
                detail: t("payments.deposits.kpi.needALookDetail"),
              },
              {
                id: "not_ours",
                label: t("payments.deposits.kpi.notOurs"),
                value: review.tiles.not_in_our_system,
                detail: t("payments.deposits.kpi.notOursDetail"),
              },
            ]}
          />
          <StatementReviewTable
            review={review}
            t={translate}
            locale={props.locale}
            batchPath={(batchId) => tenantPath(depositBatchRoute(batchId))}
            onPair={setPairing}
            onLineAction={(kind, row) => setLineAction({ kind, row })}
          />
          <GapNotes gaps={review.unavailable} t={translate} />
          {/* The declined third step, stated rather than drawn. The prototype's
              bulk "Confirm & reconcile" cannot collect the reason and GL
              BR-PAY-019 requires on every difference, so each batch is
              reconciled on its own detail screen — and this says so. */}
          <p className="pay-absent" role="note">
            {t("payments.deposits.step3Note")}
          </p>
        </>
      )}
    </Panel>
  );

  const steps: WizardStep[] = useMemo(
    () => [
      // ⚠ **THE RAIL'S OWN WORDS, NOT THE OLD HEADINGS.** `payments.deposits
      // .step1` reads *"1 · Upload the statement"* — the number was IN the
      // heading because there was no rail to carry it, and reusing it here
      // would draw *"① 1 · Upload the statement"*. p053 draws `1 Upload` and
      // `2 Review`; B14 rule 33 caps a label at three words.
      {
        id: "upload",
        label: t("payments.deposits.railUpload"),
        validate: uploadStep,
        content: stepOne,
      },
      { id: "review", label: t("payments.deposits.railReview"), content: stepTwo },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stepOne, stepTwo, t],
  );

  // ⚠ **THE PERMISSION EXITS SIT BELOW EVERY HOOK (DEF-GOV-8540, 2026-09-30).**
  // They were above `steps`' useMemo, so a 403 arriving after the first render
  // (the cell or the accounts query resolving) ran one hook fewer and React
  // threw on hook order instead of drawing PermissionDenied.
  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />
    );
  }
  if (accountsQuery.isError && isPermissionDenied(accountsQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />
    );
  }

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("payments.deposits.wizardKicker")}
        title={t("payments.deposits.wizardTitle")}
        rollup={t("payments.deposits.wizardSub")}
        backTo={{ to: tenantPath(DEPOSITS_ROUTE), label: t("payments.deposits.backToList") }}
      />

      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setNav}
        commitLabel={t("payments.deposits.wizardDone")}
        commitFailedTitle={t("payments.deposits.wizardDoneFailed")}
        onCommit={finish}
        onCommitted={() => navigate(tenantPath(DEPOSITS_ROUTE))}
      />

      {lineAction !== null && review !== undefined && (
        lineAction.kind === "match_return" ? (
          <MatchReturnForm
            line={lineAction.row}
            currency={review.currency}
            locale={props.locale}
            client={client}
            onClose={() => setLineAction(null)}
            onDone={(result) => void lineActionDone(result)}
          />
        ) : (
          <BankFeeForm
            line={lineAction.row}
            currency={review.currency}
            locale={props.locale}
            client={client}
            onClose={() => setLineAction(null)}
            onDone={(result) => void lineActionDone(result)}
          />
        )
      )}

      {/* ── Pairing by hand — the ONLY way a non-equal line gets tied ── */}
      {pairing !== null && review !== undefined && (
        <Panel>
          <div className="fin-panel-head">
            <h3>{t("payments.deposits.pairTitle")}</h3>
          </div>
          <p className="pay-form-note">{t("payments.deposits.pairHelp")}</p>
          {review.open_batches.length === 0 ? (
            <p className="pay-absent" role="note">
              {t("payments.deposits.noOpenBatches")}
            </p>
          ) : (
            <ul className="pay-pair-list">
              {review.open_batches.map((batch) => (
                <li key={batch.id}>
                  <Button variant="secondary" onClick={() => void handlePair(batch.id)}>
                    {batch.code} · {batch.deposited_on} ·{" "}
                    <MoneyCell
                      amount={batch.recorded_total ?? "0"}
                      currency={batch.currency}
                      locale={props.locale}
                    />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <Button variant="ghost" onClick={() => setPairing(null)}>
            {t("forms.cancel")}
          </Button>
        </Panel>
      )}
    </div>
  );
}


// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-021@5b2e814 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-021 §1/§3/§5 · 08-payments/02-business-rules.md BR-PAY-019/021/028/035 · 08-qa/01-e2e/journeys/J14-lockbox-day.md step 5 · 05-prototype/UtilityBilling.html lines 3940-4000)
// generated: 2026-08-16 by story-coder (payments SURFACE lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the S38 test file failed to resolve this module before it existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) the prototype's Plaid "connect your bank" card is NOT drawn — EP-PAY-06 §Scope puts direct bank feeds out of v1 as an integrations seam with no ratified rule, and drawing it dead would promise it · (2) THERE IS NO BULK "Confirm & reconcile" STEP 3. BR-PAY-019 requires a reason AND a GL on every DIFFERENCE and a bulk confirm cannot collect one; each batch reconciles on S39/S40 instead. Batches that tie EXACTLY still need a person, which is a real limitation and is STATED on the screen rather than hidden behind a button that would skip the exceptions · (3) the file is base64'd in the browser and parsed ONLY by `lockbox.py` — a second parser would be a second understanding of a bank's CSV dialect · (4) the step-2 tiles are counted SERVER-side over the rows shown; the prototype's "31 lines / 28 matched / 3 need a look" is a demo statement's · (5) pairing shows the OPEN batches only — a reconciled one is locked (BR-PAY-004) and `match_bank_line` refuses it, so offering it would be a control that fails on click
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
