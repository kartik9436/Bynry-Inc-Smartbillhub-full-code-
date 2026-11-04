// ── Trace ──────────────────────────────────────────────
// Task:    Finance blueprint `P1.21` — *"New entries — the batch screen"*.
//          The screen half of `BR-LED-798`, whose backend half is `P1.22`.
// Drawing: 05-prototype/07 Finance Blueprint.pdf — **p029** is the wireframe,
//          its eight numbered notes and the binding FIELDS table; **p030**
//          carries FOR / DOORS / PRIMARY ACTION / TABLE CONTROLS / WRITE
//          SURFACES / RULES and the "Components to use" table.
//          Built from the RENDERED IMAGES (B14 rule 42).
// Rules:   BR-LED-798 (a batch posts in full or not at all, and every entry is
//          checked before the first is attempted — PO ruling 2026-09-24) ·
//          BR-LED-003 (drafts freely editable; balanced + memo at post; posted
//          is immutable) · BR-LED-025 (two decimals at the edge) · BR-TEN-043
//          (the moment is an INPUT, never a clock) · B14 rules 4 · 6 · 7 · 32 ·
//          33 · 38 · 40 · 43 · 44 · hard rules 4 · 6 · 7 · 8
// ───────────────────────────────────────────────────────
//
// 1·5a — COMPOSE A BATCH OF JOURNAL ENTRIES, THEN POST IT IN ONE ACT.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS A SCREEN AND NOT THE MODAL IT REPLACES
// ══════════════════════════════════════════════════════════════════════════
// p030's TODAY row: *"A `FormModal` over 1·1 that composes ONE entry with a
// free-form line list. No address, no batch, no draft to return to."* A finance
// officer closing a month types five entries, and the modal made that five
// separate acts with nothing holding them together.
//
// **PO ruling 2026-09-23: the screen takes *"1 or more entries"*, each row its
// own journal entry.** p029 note 2: *"Entry · the composer. Every field for one
// entry, and the add control lives here."*
//
// ⚠ **`PageHeader` AND NOT `WizardFrame`, AND THE DRAWING SAYS WHY:**
// *"Replaces the modal's header and footer. **Not `WizardFrame`** — composing
// is a loop, not a sequence of steps."* A numbered rail over a thing you do
// three times in any order would be a lie about the shape of the work.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A ROW CANNOT BE UNBALANCED (p029 note 3)
// ══════════════════════════════════════════════════════════════════════════
// *"Debit and credit account, one amount — **this is what makes a row an
// entry**. Two accounts and one figure cannot be unbalanced, so `BR-LED-003`
// holds by construction rather than by validation."*
//
// That is the whole reason the composer takes TWO ACCOUNT PICKERS and ONE
// AMOUNT rather than the modal's free-form line list. There is no "must
// balance" footer on this screen because there is nothing it could ever say.
//
// ══════════════════════════════════════════════════════════════════════════
// POSTING: SAVE EACH DRAFT, THEN POST THE BATCH IN ONE CALL
// ══════════════════════════════════════════════════════════════════════════
// `POST /ledger/journal-entries/post-batch` takes ENTRY IDS, so a composed
// entry has to exist as a draft before it can be posted. *Post all N ✓*
// therefore saves every unsaved entry as a draft and then makes ONE batch call.
//
// ⚠ **THAT IS N+1 CALLS AND THE GUARANTEE IS UNHARMED, WHICH IS WORTH SAYING
// ONCE.** `BR-LED-798`'s promise is about POSTING — *"no journal entry, no
// journal line and no allocated number"* on a failure — and the posting is the
// one transaction. A draft is not in the books (`BR-LED-003`): a save that
// fails half way leaves drafts, which are freely editable and deletable and
// carry no number, so nothing a reader of the books would ever have to explain.
// **A loop over `postManualJournalEntry` would be a different thing entirely**
// and is the option the PO rejected.

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getChartOfAccounts,
  postManualJournalBatch,
  saveManualJournalDraft,
} from "@/api/endpoints";
import type { LedgerChartRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { PencilIcon, TrashIcon } from "@/components/icons";
import { useToast } from "@/components/Toast";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";
import { JOURNAL_ENTRY_TYPES } from "./JournalEntryModal";

/** One composed entry, exactly as p029's FIELDS table defines it.
 *
 *  Every money value is a STRING the whole way. A `Number()` anywhere here is
 *  the float CLAUDE.md rule 2 exists to keep out of money, in the one place it
 *  looks harmless. */
export interface ComposedEntry {
  /** Client-side only, for React keys and for the remove control. It is NEVER
   *  rendered (B14 rule 31). */
  key: string;
  entryDate: string;
  type: string;
  memo: string;
  debitAccountId: string;
  creditAccountId: string;
  amount: string;
  /** Set once the entry has been saved as a draft, so a retry does not create
   *  a second draft for the same composed row (hard rule 6's spirit). */
  entryId?: string;
}

/** `BR-LED-025` — two decimals at the edge, and the edge is here.
 *
 *  The server refuses a third decimal on a journal line; catching it in the
 *  composer means the clerk fixes it while the form is still open rather than
 *  after pressing the one irreversible button on the screen. */
export function amountProblem(raw: string): "empty" | "shape" | "decimals" | null {
  const value = raw.trim();
  if (value === "") {
    return "empty";
  }
  if (!/^\d+(\.\d+)?$/.test(value)) {
    return "shape";
  }
  const [, fraction = ""] = value.split(".");
  return fraction.length > 2 ? "decimals" : null;
}

/** What stops THIS composed entry being added, or `null`.
 *
 *  ⚠ **THE TWO ACCOUNTS MUST DIFFER**, which p029's FIELDS table states on the
 *  Credit account row: *"Same source. **Refused if equal to the debit
 *  account**"*. An entry debiting and crediting one account moves nothing and
 *  would post cleanly — a balanced, numbered, immutable no-op in the books. */
export function composerProblem(entry: Omit<ComposedEntry, "key">): string | null {
  if (entry.entryDate.trim() === "") {
    return "date";
  }
  if (entry.debitAccountId === "" || entry.creditAccountId === "") {
    return "accounts";
  }
  if (entry.debitAccountId === entry.creditAccountId) {
    return "sameAccount";
  }
  const money = amountProblem(entry.amount);
  if (money !== null) {
    return `amount.${money}`;
  }
  return null;
}

/** What stops the BATCH posting, or `null`.
 *
 *  ⚠ **A MEMO IS REQUIRED TO POST AND NOT TO ADD**, which is the FIELDS table's
 *  own `Required: To post`. `BR-LED-003` needs it because a posted entry is
 *  immutable, so the memo is the only place the WHY can ever be written — but
 *  a clerk composing five rows should be able to get the figures down first.
 *  The server's own pre-check refuses the same thing (`BR-LED-798`); this is
 *  the screen saying it first, which is the half of option (c) the PO chose. */
export function batchProblem(entries: readonly ComposedEntry[]): string | null {
  if (entries.length === 0) {
    return "empty";
  }
  if (entries.some((entry) => entry.memo.trim() === "")) {
    return "memo";
  }
  return null;
}

export interface JournalBatchPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  locale?: string;
  /** `BR-TEN-043` — the instant this screen stamps on a post. A SEAM, not a
   *  convenience: nothing in a money path may read a clock the caller did not
   *  state, and a test must be able to name it. */
  now?: () => string;
}

export function JournalBatchPage(props: JournalBatchPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const { dateFormat } = useRegional(props);
  const toast = useToast();
  const stamp = props.now ?? (() => new Date().toISOString());

  const today = stamp().slice(0, 10);
  const [entries, setEntries] = useState<ComposedEntry[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  // p029 note 5: "+ Add line ... pushes the composed entry into the table and
  // clears the form, KEEPING THE DATE" — a batch is usually one day.
  const [draft, setDraft] = useState<Omit<ComposedEntry, "key">>({
    entryDate: today,
    type: "standard",
    memo: "",
    debitAccountId: "",
    creditAccountId: "",
    amount: "",
  });

  // ⚠ **`f.status=active` IS NOT TIDINESS.** A deactivated account is refused
  // by the posting service, so an unfiltered picker would offer rows every
  // submit would bounce — the DEF-114 shape. And the FIELDS table is explicit:
  // "GET /ledger/accounts — **never a literal array**".
  const chart = useQuery({
    queryKey: ["ledger", "chart", "batch-picker"],
    queryFn: () => getChartOfAccounts({ status: "active" }, client),
    retry: false,
  });
  // ⚠ Its own `useMemo`, because `?? []` builds a NEW array on every render and
  // would make the memo below re-run every time — eslint's
  // `react-hooks/exhaustive-deps` refuses it, correctly.
  const accounts: LedgerChartRow[] = useMemo(() => chart.data?.rows ?? [], [chart.data]);
  const accountOptions = useMemo(
    () =>
      accounts.map((row) => ({
        value: row.account_id,
        // B14 rule 31 — the CODE and the NAME, never the uuid.
        label: `${row.code} · ${row.name}`,
      })),
    [accounts],
  );
  const accountLabel = (id: string) => {
    const row = accounts.find((one) => one.account_id === id);
    return row === undefined ? "" : row.code;
  };

  const problem = composerProblem(draft);
  const blocker = batchProblem(entries);

  function addEntry() {
    if (problem !== null) {
      return;
    }
    const composed: ComposedEntry = { ...draft, key: `${Date.now()}-${entries.length}` };
    setEntries((current) =>
      editing === null
        ? [...current, composed]
        : current.map((one) => (one.key === editing ? { ...composed, key: one.key } : one)),
    );
    setEditing(null);
    // The DATE is kept; everything else clears. p029 note 5, and the FIELDS
    // table's own "Cleared after Add — each entry needs its own reason".
    setDraft({
      entryDate: draft.entryDate,
      type: "standard",
      memo: "",
      debitAccountId: "",
      creditAccountId: "",
      amount: "",
    });
  }

  async function saveDrafts(): Promise<string[]> {
    const ids: string[] = [];
    const saved: ComposedEntry[] = [];
    for (const entry of entries) {
      const result = await saveManualJournalDraft(
        {
          entry_id: entry.entryId,
          entry_date: entry.entryDate,
          type: entry.type,
          memo: entry.memo,
          lines: [
            { ledger_account_id: entry.debitAccountId, side: "debit", amount: entry.amount },
            { ledger_account_id: entry.creditAccountId, side: "credit", amount: entry.amount },
          ],
        },
        client,
      );
      ids.push(result.entry_id);
      saved.push({ ...entry, entryId: result.entry_id });
    }
    setEntries(saved);
    return ids;
  }

  async function onSaveDrafts() {
    setWorking(true);
    setRefusal(null);
    try {
      await saveDrafts();
      toast(t("finance.batch.draftsSaved", { count: entries.length }));
    } catch (failure) {
      setRefusal(apiErrorText(failure, (key: string, params?: Record<string, unknown>) => t(key, params)));
    } finally {
      setWorking(false);
    }
  }

  async function onPostAll() {
    setConfirmOpen(false);
    setWorking(true);
    setRefusal(null);
    try {
      const ids = await saveDrafts();
      // ONE call. See this file's header for why a loop would be the option
      // the Product Owner rejected.
      const posted = await postManualJournalBatch(ids, stamp(), client);
      toast(t("finance.batch.posted", { count: posted.entry_count }));
      navigate(tenantPath("/finance?view=journal"));
    } catch (failure) {
      // `BR-LED-798`'s pre-check names every offending entry in ONE answer, and
      // the sentence it sends is what a clerk needs to act on.
      setRefusal(apiErrorText(failure, (key: string, params?: Record<string, unknown>) => t(key, params)));
    } finally {
      setWorking(false);
    }
  }

  const postedCount = entries.filter((one) => one.entryId !== undefined).length;

  return (
    <>
      <PageHeader
        kicker={t("finance.batch.kicker")}
        title={t(
          routeParams.entryId === undefined ? "finance.batch.title" : "finance.batch.editTitle",
        )}
        // p029 note 1 — "3 drafts · none posted", the batch's state in FOUR
        // words. A FACT under B14 rule 33's six-word cap, and it rides in
        // `status` rather than as a second heading (B14 rule 2: one page head).
        status={t("finance.batch.state", { drafts: entries.length, posted: postedCount })}
        backTo={{ to: tenantPath("/finance?view=journal"), label: t("finance.batch.exit") }}
        secondaryActions={
          <>
            {/* p030's PRIMARY ACTION row: "Post all 3 ✓, page head right, AFTER
                Cancel and Save drafts" — so the order on screen is Cancel,
                Save drafts, then the commit. */}
            <Button variant="ghost" onClick={() => navigate(tenantPath("/finance?view=journal"))}>
              {t("finance.batch.cancel")}
            </Button>
            <Button
              variant="secondary"
              disabled={entries.length === 0 || working}
              onClick={() => void onSaveDrafts()}
            >
              {t("finance.batch.saveDrafts")}
            </Button>
          </>
        }
        // p029 note 8 — "the count is in the button, so nobody posts three
        // thinking it is one". B14 rule 4: `Verb ✓` commits. B14 rule 6: a
        // destructive commit is the DANGER tier, and posting is irreversible
        // (hard rule 4).
        primaryAction={
          <Button
            variant="danger"
            disabled={blocker !== null || working}
            title={blocker === null ? undefined : t(`finance.batch.blocked.${blocker}`)}
            onClick={() => setConfirmOpen(true)}
          >
            {t("finance.batch.postAll", { count: entries.length })}
          </Button>
        }
      />

      {refusal !== null && (
        <Panel role="alert">
          <p className="m-0 text-body leading-body text-danger-700">{refusal}</p>
        </Panel>
      )}

      {/* ── p029 note 2 · THE COMPOSER ─────────────────────────────────── */}
      <Panel>
        <h3 className="mt-0 mb-4 font-heading text-h5 leading-heading">
          {t("finance.batch.composerTitle")}
        </h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <DatePickerField
            id="batch-date"
            label={t("finance.batch.field.date")}
            value={draft.entryDate}
            onChange={(value) => setDraft({ ...draft, entryDate: value })}
            dateFormat={dateFormat}
            required
          />
          <SelectField
            id="batch-type"
            label={t("finance.batch.field.type")}
            value={draft.type}
            onChange={(value) => setDraft({ ...draft, type: value })}
            options={JOURNAL_ENTRY_TYPES.map((value) => ({
              value,
              label: t(`finance.journal.type.${value}`, { defaultValue: value }),
            }))}
            required
          />
          <TextField
            id="batch-amount"
            label={t("finance.batch.field.amount")}
            value={draft.amount}
            onChange={(value) => setDraft({ ...draft, amount: value })}
            numeric
            required
          />
          <SelectField
            id="batch-debit"
            label={t("finance.batch.field.debit")}
            value={draft.debitAccountId}
            onChange={(value) => setDraft({ ...draft, debitAccountId: value })}
            options={accountOptions}
            placeholder={t("finance.batch.choose")}
            required
          />
          <SelectField
            id="batch-credit"
            label={t("finance.batch.field.credit")}
            value={draft.creditAccountId}
            onChange={(value) => setDraft({ ...draft, creditAccountId: value })}
            options={accountOptions}
            placeholder={t("finance.batch.choose")}
            error={
              problem === "sameAccount" ? t("finance.batch.blocked.sameAccount") : undefined
            }
            required
          />
          <TextField
            id="batch-memo"
            label={t("finance.batch.field.memo")}
            value={draft.memo}
            onChange={(value) => setDraft({ ...draft, memo: value })}
          />
        </div>
        <div className="mt-4 flex items-center gap-2">
          {/* B14 rule 4 — `+ Noun` opens a creator. The PO's own name for it. */}
          <Button
            variant="secondary"
            disabled={problem !== null}
            title={problem === null ? undefined : t(`finance.batch.blocked.${problem}`)}
            onClick={addEntry}
          >
            {t(editing === null ? "finance.batch.addLine" : "finance.batch.updateLine")}
          </Button>
        </div>
      </Panel>

      {/* ── p029 note 6 · THE ENTRIES ──────────────────────────────────── */}
      <Panel>
        <h3 className="mt-0 mb-4 font-heading text-h5 leading-heading">
          {t("finance.batch.entriesTitle", { count: entries.length })}
        </h3>
        {entries.length === 0 ? (
          // B14 rule 32/33 — a FACT and an INSTRUCTION, six words each, and no
          // sentence explaining why the table is empty.
          <p className="m-0 text-body leading-body text-neutral-700" role="note">
            {t("finance.batch.empty")}
          </p>
        ) : (
          // p030: "No toolbar or pager — a batch you are composing is not a
          // list; UI-RULES 16 exempts it." So this is the ONE table type (B14
          // rule 20) without the shared list chrome around it.
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("finance.batch.col.date")}</th>
                <th scope="col">{t("finance.batch.col.memo")}</th>
                <th scope="col">{t("finance.batch.col.debit")}</th>
                <th scope="col">{t("finance.batch.col.credit")}</th>
                <th scope="col" className="text-right">
                  {t("finance.batch.col.amount")}
                </th>
                <th scope="col">{t("finance.batch.col.state")}</th>
                <th scope="col">{t("finance.batch.col.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, index) => (
                <tr key={entry.key}>
                  <td>{index + 1}</td>
                  <td>{entry.entryDate}</td>
                  <td>{entry.memo}</td>
                  <td>{accountLabel(entry.debitAccountId)}</td>
                  <td>{accountLabel(entry.creditAccountId)}</td>
                  {/* ⚠ **NO CURRENCY CODE, AND THAT IS CLAUDE.md RULE 2 RATHER
                      THAN AN OMISSION.** *"the code rides WITH the figure, never
                      assumed."* A composed entry has no server row yet, so
                      there is no stamped currency to show: the journal list's
                      own money cells read `row.currency`, served per entry,
                      and this figure is the clerk's own input echoed back
                      before anything has been written. `MoneyCell` requires a
                      CHAR(3) and would have to be given a guess.
                      **The moment it posts it becomes a ledger amount and the
                      journal list renders it through the one formatting path
                      (`BR-SHL-023`), code and all.** */}
                  <td className="text-right font-mono tabular-nums">{entry.amount}</td>
                  <td>
                    <StatusPill tone="warning">{t("finance.journal.status.draft")}</StatusPill>
                  </td>
                  <td>
                    {/* p029 note 6 — "each editable and removable BEFORE
                        posting". Both controls disappear the moment the batch
                        is in the books, because hard rule 4 makes them
                        impossible rather than merely unwise. */}
                    <RowActions>
                      <RowAction
                        label={t("finance.batch.editEntry")}
                        icon={<PencilIcon />}
                        onClick={() => {
                          setEditing(entry.key);
                          setDraft({ ...entry });
                        }}
                      />
                      <RowAction
                        label={t("finance.batch.removeEntry")}
                        icon={<TrashIcon />}
                        danger
                        onClick={() =>
                          setEntries((current) => current.filter((one) => one.key !== entry.key))
                        }
                      />
                    </RowActions>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {/* p029 note 7 — the summary reads the BATCH, not one entry. */}
      {confirmOpen && (
        <ConfirmDialog
          title={t("finance.batch.confirmTitle", { count: entries.length })}
          // B14 rule 33 — a CONSEQUENCE before an irreversible act: at most two
          // sentences, six words each, never cut below clarity. p030 names this
          // dialog "the one thing that stays a modal ... names the count and
          // that it cannot be undone".
          consequence={t("finance.batch.confirmBody", { count: entries.length })}
          confirmLabel={t("finance.batch.confirmAction")}
          working={working}
          // B14 rule 6 — posting is irreversible (hard rule 4), so the commit
          // is the danger tier and not the standard primary.
          confirmVariant="danger"
          onConfirm={() => void onPostAll()}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </>
  );
}
