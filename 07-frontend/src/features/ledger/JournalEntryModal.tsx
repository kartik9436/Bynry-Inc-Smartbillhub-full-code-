// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-011 (S57 Manual journal entry: Date · Type · Memo · GL rows
//           with Debit/Credit · the running "Must balance" footer · + Add line
//           · the audit notice — draft → post, balanced at post) ·
//           US-LED-012 (the accrual and its day-1 auto-reversal, linked both
//           ways) · US-LED-013 (the posted-entry "edit" = reverse + repost)
//           Screens: S57 · S56
// Rules:    BR-LED-003 (a draft is freely editable and worthless; BALANCED and
//           a memo are required AT POST; a posted entry is immutable forever;
//           System Admin or Billing Clerk per the PO's closure of OQ-175) ·
//           BR-LED-005 (day-1 auto-reversal) · BR-LED-021 (the JE- number,
//           stamped at post) · BR-LED-015 (every draft/post/delete audits) ·
//           BR-TEN-038 (a date in a closed period auto-forwards) ·
//           BR-TEN-043 (event time is an INPUT — the screen states the moment) ·
//           BR-SHL-017 (the field kit + inline validation) · BR-SHL-020
//           (plain-language failure) · BR-SHL-023 (ONE money formatting path) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           disabled WITH its reason) · IS-1 (modal) · IS-10 (Esc / ✕ /
//           backdrop close, focus trap) · CLAUDE.md rule 2 (money is a decimal
//           STRING, never a float) · rule 4 · rule 5
// ───────────────────────────────────────────────────────
// S57 — the one place a human puts money into the books by hand.
//
// ══════════════════════════════════════════════════════════════════════════
// AN UNBALANCED ENTRY CANNOT BE SUBMITTED — AND THAT IS THE WEAKEST OF THREE
// ══════════════════════════════════════════════════════════════════════════
// US-LED-011 §1 asks for a *"running 'Must balance' footer"* and this file
// draws it, with *Post entry ✓* DISABLED while the entry does not foot. That
// is a courtesy. The rule is enforced twice more and both are behind this
// screen: `apps.ledger.manual_je.post_manual_je` asserts the balance against
// the lines that actually exist, and `ledger/0002`'s DEFERRED trigger asserts
// it again inside the database at COMMIT. A forged request that never opens
// this modal is refused by the second, and if that were ever wrong, by the
// third. Nothing about the rule depends on a button being grey.
//
// **THE FOOTER FIGURE IS THE SERVER'S.** `gap`, `debits` and `credits` all
// arrive from `POST /ledger/journal-entries/drafts`; this file adds, subtracts
// and rounds nothing (CLAUDE.md rule 2, BR-SHL-023). Before the first save the
// footer says so rather than computing a local total — a client-side sum that
// agreed with the server right up until the day it mattered is exactly the
// second derivation BR-REP-002 exists to prevent.
//
// ══════════════════════════════════════════════════════════════════════════
// A DRAFT MAY BE UNBALANCED. THAT IS THE RULING, NOT A LOOPHOLE
// ══════════════════════════════════════════════════════════════════════════
// BR-LED-003: *drafts freely editable/deletable before post*. A six-line
// reclass is unbalanced between every keystroke, so *Save draft* accepts it and
// the footer shows the gap. A draft is WORTHLESS in the PO's own word — it sums
// into no report and deleting one leaves the books byte-identical.
//
// ══════════════════════════════════════════════════════════════════════════
// THERE IS NO EDIT CONTROL FOR A POSTED ENTRY, ANYWHERE
// ══════════════════════════════════════════════════════════════════════════
// Hard rule 4. The modal opens in one of two modes and a posted entry has
// neither: it is READ-ONLY here, and the only correction is *Reverse + repost*
// on the S56 list, which writes two NEW entries. Offering an edit that will be
// refused teaches a clerk that the product is unreliable rather than that the
// books are.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS DIVERGES FROM `05-prototype/UtilityBilling.html` (law 6)
// ══════════════════════════════════════════════════════════════════════════
//   · **THE PROTOTYPE'S GL PICKER NAMES ACCOUNTS THAT ARE IN NO SIGNED CHART.**
//     Its two selects offer `1010 · Operating Cash`, `4100 · Electric Revenue`,
//     `6100 · Bad Debt Expense`, `4910 · Penalties & Fees`, `2300 · Sales Tax
//     Payable` and `4200 · Water Revenue`. The finance-signed chart (B5 line 74,
//     ❄️ FROZEN 2026-08-08) says **1010 is Undeposited funds** (cash is 1000),
//     **6800 is Bank fees and 6900 is Bad debt** (there is no 6100), **4200 is
//     Late-fee revenue and 4210 NSF & other fee revenue** (there is no 4910),
//     **2300 is the Customer deposit liability** (tax payable is the 2200
//     series, minted per authority) and **water revenue is 4110/4115** (4200 is
//     not it). Every one of those six would post money into the wrong account.
//     The picker here is filled from the TENANT's live chart, in code order,
//     and this file contains no account number at all.
//   · **"Post to audit log (required)" is not a checkbox.** The prototype draws
//     a pre-ticked one. BR-LED-015 makes the audit row unconditional and the
//     server writes it whatever a checkbox said, so a control that cannot be
//     unticked is a control that lies about who is in charge. It renders as the
//     sentence it always was.
//   · **The prototype's Type list reads "Reversing accrual".** The ratified
//     enum (r13 #2) is `standard | accrual | reversing`; the label is the
//     enum's, so a screen and a database column cannot mean different things.
import { useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  deleteManualJournalDraft,
  postManualJournalEntry,
  saveManualJournalDraft,
} from "@/api/endpoints";
import type {
  LedgerChartRow,
  ManualJournalDraft,
  ManualJournalLine,
  ManualJournalPosted,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { MoneyCell } from "@/components/MoneyCell";
import { ModalShell, SelectField, TextField } from "@/components/FormModal";
import { WorkingButton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { gapSentence } from "./financeShared";

import "./finance.css";

/** The ratified enum (B2 r13 #2), NOT the prototype's three labels. A screen
 *  and a database column may not mean different things. */
export const JOURNAL_ENTRY_TYPES = ["standard", "accrual", "reversing"] as const;

/** One row of the modal's GL table, as the operator has it half-typed.
 *
 *  `debit` and `credit` are two separate STRING boxes rather than one amount
 *  plus a side, because that is the table the prototype draws and the one an
 *  accountant reads. They are folded into `{side, amount}` at submit, which is
 *  the shape `journal_lines` actually stores (`amount >= 0`, the SIDE says
 *  which way the money went). Both stay strings the whole way — a `Number()`
 *  here is the float CLAUDE.md rule 2 exists to keep out of money, in the one
 *  place it looks harmless. */
export interface JournalRowDraft {
  accountId: string;
  debit: string;
  credit: string;
}

export function emptyRow(): JournalRowDraft {
  return { accountId: "", debit: "", credit: "" };
}

/**
 * The modal's rows → the wire's lines.
 *
 * A row with neither box filled is DROPPED: S57 opens with two empty rows and
 * a *+ Add line* button, so a three-line entry always arrives with blanks
 * behind it. A row with BOTH boxes filled is a single row claiming to be two
 * lines, and it is sent as the DEBIT with the credit ignored — no: it is
 * refused before submit by `rowProblem`, so this function never sees one.
 */
export function toWireLines(rows: readonly JournalRowDraft[]): ManualJournalLine[] {
  const lines: ManualJournalLine[] = [];
  for (const row of rows) {
    const debit = row.debit.trim();
    const credit = row.credit.trim();
    if (row.accountId === "" && debit === "" && credit === "") {
      continue;
    }
    if (debit !== "") {
      lines.push({ ledger_account_id: row.accountId, side: "debit", amount: debit });
    } else if (credit !== "") {
      lines.push({ ledger_account_id: row.accountId, side: "credit", amount: credit });
    } else {
      // An account chosen and no amount typed. Sent as-is with an empty amount
      // so the SERVER names the row it refuses — a client that swallowed it
      // would drop a line the operator can see on screen.
      lines.push({ ledger_account_id: row.accountId, side: "debit", amount: "" });
    }
  }
  return lines;
}

/**
 * The catalogue key naming what is wrong with one row, or null.
 *
 * Pure and exported so the rule is testable without a browser. It is the
 * COURTESY half — every one of these is refused again by the server.
 */
export function rowProblem(row: JournalRowDraft): string | null {
  const debit = row.debit.trim();
  const credit = row.credit.trim();
  if (row.accountId === "" && debit === "" && credit === "") {
    return null; // an untouched row
  }
  if (row.accountId === "") {
    return "finance.je.error.accountRequired";
  }
  if (debit !== "" && credit !== "") {
    return "finance.je.error.oneSideOnly";
  }
  if (debit === "" && credit === "") {
    return "finance.je.error.amountRequired";
  }
  const amount = debit !== "" ? debit : credit;
  if (!/^\d+(\.\d{1,6})?$/.test(amount)) {
    // A NEGATIVE DEBIT IS A CREDIT WEARING THE WRONG WORD: `journal_lines`
    // carries `amount >= 0` and the side says the direction, so a minus here
    // would balance a pair arithmetically and make the trial balance's own
    // Debit column meaningless.
    return "finance.je.error.amountFormat";
  }
  return null;
}

/** Every row's problem, in row order, so the operator sees which line. */
export function rowProblems(rows: readonly JournalRowDraft[]): (string | null)[] {
  return rows.map(rowProblem);
}

/**
 * May *Post entry ✓* be pressed at all?
 *
 * Four conditions, and NONE of them is the enforcement — see the file header.
 * A saved draft is required because the server posts a ROW, not a payload:
 * `gap` and `balanced` are facts about lines that exist in the database, which
 * is the only version of "balanced" that can be trusted.
 */
export function canPost(draft: ManualJournalDraft | null, memo: string): boolean {
  return draft !== null && draft.balanced && memo.trim() !== "" && draft.line_count > 0;
}

export interface JournalEntryModalProps {
  accounts: readonly LedgerChartRow[];
  /** The tenant's own accounting day — the served period's end, which
   *  `GeneralLedgerPage` takes from `useFinancePeriod` and therefore from
   *  `GET /shell/display` (`DEF-SHL-4283`, 2026-09-06; it was the admin-only
   *  `GET /settings/regional` before). Never
   *  `new Date()` — a modal that defaulted to the browser's calendar would
   *  book a Texas clerk's Monday entry into Sunday from a laptop set to UTC
   *  (DEF-094's shape). */
  defaultEntryDate: string;
  /** BR-TEN-043 — the instant the caller stamps on the post. Passed IN so a
   *  double-submitted form stamps one moment and a test can state it. */
  now: () => string;
  onClose: () => void;
  onPosted: (posted: ManualJournalPosted) => void;
  /** The prefilled correction from *Reverse + repost*, loaded but NOT written
   *  (`repost_draft_is_not_persisted`) — *Save draft* is what makes it a row. */
  prefill?: { lines: ManualJournalLine[]; memo: string } | null;
  client?: ApiClient;
  locale?: string;
  currency?: string | null;
}

export function JournalEntryModal(props: JournalEntryModalProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const toast = useToast();

  const [entryDate, setEntryDate] = useState(props.defaultEntryDate);
  const [entryType, setEntryType] = useState<string>("standard");
  const [memo, setMemo] = useState(props.prefill?.memo ?? "");
  const [rows, setRows] = useState<JournalRowDraft[]>(() => {
    if (props.prefill == null || props.prefill.lines.length === 0) {
      return [emptyRow(), emptyRow()];
    }
    return props.prefill.lines.map((line) => ({
      accountId: line.ledger_account_id,
      debit: line.side === "debit" ? line.amount : "",
      credit: line.side === "credit" ? line.amount : "",
    }));
  });
  const [draft, setDraft] = useState<ManualJournalDraft | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Editing the rows invalidates the SAVED balance. Clearing it is what stops
  // the footer claiming "Balanced ✓" about a set of lines the operator has
  // since changed — the stalest possible green light on a money screen.
  useEffect(() => {
    setDraft(null);
  }, [rows, entryDate, entryType]);

  const problems = useMemo(() => rowProblems(rows), [rows]);
  const firstProblem = problems.find((problem) => problem !== null) ?? null;
  // WHY the Post button is off, in the operator's own words — never a bare
  // grey control (BR-SHL-025). Order matters: a row error is the thing to fix
  // first, and "not saved yet" is a state, not a fault.
  const postBlockedReason =
    firstProblem !== null
      ? t(firstProblem)
      : draft === null
        ? t("finance.je.postBlocked.notSaved")
        : !draft.balanced
          ? t("finance.je.postBlocked.unbalanced", { gap: draft.gap })
          : memo.trim() === ""
            ? t("finance.je.postBlocked.memo")
            : null;
  const currency = draft?.currency ?? props.currency ?? null;

  const setRow = (index: number, patch: Partial<JournalRowDraft>) => {
    setRows((current) =>
      current.map((row, position) => (position === index ? { ...row, ...patch } : row)),
    );
  };

  async function save(): Promise<ManualJournalDraft | null> {
    setFailure(null);
    setBusy(true);
    try {
      const saved = await saveManualJournalDraft(
        {
          entry_id: draft?.entry_id,
          entry_date: entryDate,
          type: entryType,
          memo,
          lines: toWireLines(rows),
        },
        client,
      );
      setDraft(saved);
      return saved;
    } catch (error) {
      setFailure(
        isApiError(error) ? apiErrorText(error, translate) : t("finance.je.error.saveFailed"),
      );
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function post() {
    const saved = draft ?? (await save());
    if (saved === null) {
      return;
    }
    if (!saved.balanced) {
      // Defence in depth against a stale click: the server refuses this too.
      setFailure(t("finance.je.error.unbalanced", { gap: saved.gap }));
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      const posted = await postManualJournalEntry(saved.entry_id, props.now(), client);
      toast(t("finance.je.postedToast"));
      props.onPosted(posted);
    } catch (error) {
      setFailure(
        isApiError(error) ? apiErrorText(error, translate) : t("finance.je.error.postFailed"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    if (draft !== null) {
      try {
        await deleteManualJournalDraft(draft.entry_id, client);
      } catch {
        // A draft that could not be deleted is still worthless (BR-LED-003) and
        // is visible on the S56 list under its own Draft pill, so the modal
        // closes rather than trapping the operator inside it.
      }
    }
    props.onClose();
  }

  return (
    <ModalShell
      title={t("finance.je.title")}
      kicker={t("finance.tab.gl")}
      onClose={() => void discard()}
    >
      <div className="modal-body fin-je-body">
        <div className="fin-two-col">
          <TextField
            id="je-date"
            label={t("finance.je.field.date")}
            value={entryDate}
            onChange={setEntryDate}
            required
            help={t("finance.je.field.dateHelp")}
          />
          <SelectField
            id="je-type"
            label={t("finance.je.field.type")}
            value={entryType}
            onChange={setEntryType}
            required
            options={JOURNAL_ENTRY_TYPES.map((value) => ({
              value,
              label: t(`finance.journal.type.${value}`),
            }))}
            help={t("finance.je.field.typeHelp")}
          />
        </div>
        <TextField
          id="je-memo"
          label={t("finance.je.field.memo")}
          value={memo}
          onChange={setMemo}
          required
          placeholder={t("finance.je.field.memoPlaceholder")}
          help={t("finance.je.field.memoHelp")}
        />

        <PlainTable className="fin-je-table">
          <thead>
            <tr>
              <th scope="col">{t("finance.je.col.account")}</th>
              <th scope="col" className="fin-num">
                {t("finance.je.col.debit")}
              </th>
              <th scope="col" className="fin-num">
                {t("finance.je.col.credit")}
              </th>
              <th scope="col">{t("finance.je.col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                <td>
                  <select
                    aria-label={t("finance.je.col.account")}
                    id={`je-account-${index}`}
                    className="input"
                    value={row.accountId}
                    onChange={(event) => setRow(index, { accountId: event.target.value })}
                  >
                    <option value="">{t("finance.je.field.accountPlaceholder")}</option>
                    {/* The TENANT's live chart, in code order. The prototype's
                        six hardcoded accounts are in no signed chart — see the
                        file header for what each of them would have done. */}
                    {props.accounts.map((account) => (
                      <option key={account.account_id} value={account.account_id}>
                        {`${account.code} · ${account.name}`}
                      </option>
                    ))}
                  </select>
                  {problems[index] !== null && (
                    <span className="fin-absent-reason" role="alert">
                      {t(problems[index] as string)}
                    </span>
                  )}
                </td>
                <td className="fin-num">
                  <input
                    id={`je-debit-${index}`}
                    aria-label={t("finance.je.col.debit")}
                    className="input"
                    inputMode="decimal"
                    value={row.debit}
                    onChange={(event) => setRow(index, { debit: event.target.value })}
                    placeholder="0.00"
                  />
                </td>
                <td className="fin-num">
                  <input
                    id={`je-credit-${index}`}
                    aria-label={t("finance.je.col.credit")}
                    className="input"
                    inputMode="decimal"
                    value={row.credit}
                    onChange={(event) => setRow(index, { credit: event.target.value })}
                    placeholder="0.00"
                  />
                </td>
                <td>
                  <InlineLink
 type="button"
 onClick={() =>
 setRows((current) =>
 current.length <= 1
 ? [emptyRow()]
 : current.filter((_, position) => position !== index),
 )
 }
                  >
                    {t("finance.je.removeLine")}
                  </InlineLink>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="fin-total-row">
              <td>{t("finance.je.mustBalance")}</td>
              <td className="fin-num">
                {/* SERVED figures, or the honest "not saved yet". A client-side
                    sum here would be a second derivation of the one number the
                    whole screen turns on. */}
                {draft === null || currency === null ? (
                  <span className="met-muted">{t("finance.je.notSavedYet")}</span>
                ) : (
                  <MoneyCell amount={draft.debits} currency={currency} locale={props.locale} />
                )}
              </td>
              <td className="fin-num">
                {draft === null || currency === null ? (
                  <span className="met-muted">{t("finance.je.notSavedYet")}</span>
                ) : (
                  <MoneyCell amount={draft.credits} currency={currency} locale={props.locale} />
                )}
              </td>
              <td>
                {draft !== null && (
                  <span className="fin-je-balance">
                    <StatusPill tone={draft.balanced ? "success" : "danger"}>
                      {draft.balanced ? t("finance.je.balanced") : t("finance.je.outOfBalance")}
                    </StatusPill>
                    {/* The GAP goes through `MoneyCell` like every other figure
                        on this screen (BR-SHL-023 — ONE money formatting path).
                        Interpolated into the sentence it printed the raw stored
                        string, "10.000000", beside four properly formatted
                        columns — found by looking at the rendered modal in a
                        browser (law 6). */}
                    {!draft.balanced && currency !== null && (
                      <MoneyCell amount={draft.gap} currency={currency} locale={props.locale} />
                    )}
                  </span>
                )}
              </td>
            </tr>
          </tfoot>
        </PlainTable>

        <InlineLink type="button" onClick={() => setRows((c) => [...c, emptyRow()])}>
          {t("finance.je.addLine")}
        </InlineLink>

        {/* BR-LED-015 — the audit row is UNCONDITIONAL. The prototype draws a
            pre-ticked checkbox; a control that cannot be unticked is a control
            that lies about who is in charge. */}
        <p className="fin-absent-reason" role="note">
          {t("finance.je.auditNotice")}
        </p>

        {draft?.date_note != null && (
          // BR-TEN-038 — the date landed in a closed period and was FORWARDED.
          // Said while the modal is still open, not after the confirm.
          <p className="fin-absent-reason" role="alert">
            {t("finance.je.dateForwarded", { date: draft.entry_date ?? "" })}
          </p>
        )}
        {(draft?.unavailable ?? []).map((gap) => (
          <p key={gap.code} className="fin-absent-reason" role="note">
            {gapSentence(gap, translate)}
          </p>
        ))}
        {failure !== null && (
          <p className="fin-absent-reason" role="alert">
            {failure}
          </p>
        )}
      </div>
      <div className="modal-foot">
        <Button variant="ghost"  onClick={() => void discard()}>
          {t("finance.je.cancel")}
        </Button>
        <WorkingButton working={busy} onClick={() => void save()}>
          {t("finance.je.saveDraft")}
        </WorkingButton>
        {/* DISABLED until the SAVED draft foots and a memo exists. The reason
            is rendered beside it (BR-SHL-025) rather than left to be guessed —
            a grey button with no explanation is how a clerk decides the
            product is broken. */}
        {/* NOT `WorkingButton`, and the difference is the whole feature: that
            component disables only while a request is in flight, and this
            control must ALSO be unpressable while the entry does not foot
            (US-LED-011 §1). `aria-disabled` is not used in its place — a
            control a screen reader announces as pressable and the handler then
            ignores is worse than one that is plainly off. */}
        <span title={postBlockedReason ?? undefined}>
          <Button
            variant="primary"
            data-testid="je-post"
            disabled={busy || postBlockedReason !== null}
            onClick={() => void post()}
          >
            {busy ? t("states.working") : t("finance.je.post")}
          </Button>
        </span>
      </div>
    </ModalShell>
  );
}

export default JournalEntryModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-011@eec4f0e (sources, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-011 §1-§8 + US-LED-012 + US-LED-013 · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-4 + LE-8 · 04-docs/01-spec/11b-api-audit.md §2.10 · 05-prototype/UtilityBilling.html lines 5530-5546)
// generated: 2026-08-16 by story-coder (the ledger surface lane — S57 had no screen and `apps/ledger/manual_je.py` had no caller)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the S57 test file could not resolve `./JournalEntryModal` before this file existed, and the SERVER refusal of an unbalanced post was proved on live Postgres (409 BIZ-STATE, the draft still a draft). tsc✔ · eslint✔ · vitest✔ · vite build✔
// exceptions: (1) the GL picker is filled from the TENANT's live chart and this file holds NO account number — the prototype's six hardcoded accounts (1010 Operating Cash · 4100 Electric Revenue · 6100 Bad Debt Expense · 4910 Penalties & Fees · 2300 Sales Tax Payable · 4200 Water Revenue) contradict the ❄️ finance-signed chart on every one of them, and posting to any would put money in the wrong account. Reported, not ported · (2) "Post to audit log (required)" is NOT a checkbox: BR-LED-015 makes the row unconditional, so it renders as the sentence it always was · (3) the Type labels are the RATIFIED enum (standard/accrual/reversing), not the prototype's "Reversing accrual" · (4) the balance footer renders the SERVER's `gap` and shows "not saved yet" before the first save rather than computing a local total — a second derivation of the one number the screen turns on · (5) a DRAFT may be saved unbalanced (BR-LED-003) and only the POST is gated · (6) there is NO edit control for a posted entry anywhere in this file (hard rule 4); the one correction is Reverse + repost on S56
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
