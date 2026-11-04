// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.8` — the Scan source's input. ⚠ **THE TASK ROW
//           IS TITLED *switched on* AND THE CARD IS NOT** — `P5.10`'s BARS are
//           owed, so this ships BEHIND a held card (decision log 2026-09-23).
//           Blueprint
//           `05-prototype/06 Payments Page Blueprint.pdf` **p067 ①** and
//           **p068 ②**, read AS IMAGES at 2.0 (B14 rule 42).
// Screens:  4·3a Import — the runner's Extract stage, payments target
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class) · rule 32
//           (one sentence per section) · rule 33 (a LABEL ≤ 3 words, a FACT
//           ≤ 6, an INSTRUCTION ≤ 6 per sentence, RATIONALE zero) · rule 38
//           (where a drawing and our UI rules disagree about how a FORM is
//           built, the UI rules win) · rule 43 (a piece of UI is a COMPONENT)
//           · BR-SHL-020 (a plain sentence, never a raw code) · BR-SHL-025
// Tests:    src/components/workflow/paymentsSourceAndWriteMode.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **A scanner is a keyboard.** p068 ②, verbatim: *"A barcode scanner is a
 * keyboard — it types what it reads and presses Enter. No driver, no
 * integration, no pairing. So Scan paper is a source card and a focused input,
 * and everything after it is the runner: the same mapping, the same rules, the
 * same rejects, the same dry run, the same receipt."*
 *
 * So this component is one focused text input, a list of what has been scanned,
 * and nothing else. There is no device to pair, no permission to ask for and
 * nothing to configure.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ THE GRAMMAR IS NOT RE-DERIVED HERE, AND THAT IS THE WHOLE REASON FOR A
 * ROUND TRIP
 * ══════════════════════════════════════════════════════════════════════════
 * `CR-139-BRC07` §6: *"`P5.8` calls `apps.billing.remittance.parse()` — do not
 * re-derive the grammar; that is the whole reason it is a module."* A second
 * Code 39 mod-43 implementation in TypeScript is two things that can disagree
 * about whether a scan was mis-read, on the one path whose job is to catch a
 * mis-read. `POST /billing/remittance/parse` is the one door.
 *
 * ⚠ **A REFUSAL IS SHOWN AND THE SCAN IS NOT KEPT.** `remittance.parse` raises
 * on an empty scan, a bad check character, a wrong field count and a non-digit
 * amount. `P5.14`'s outcome is *"a mis-scan fails visibly"* and `P5.15`'s is
 * *"a scan with no barcode fails visibly rather than silently keying nothing"*
 * — so a refused line is reported where the clerk is looking and the row is not
 * added.
 *
 * ⚠ **A DUPLICATE IS REFUSED TOO, AND IT IS THE LIKELIEST MISTAKE AT A DESK.**
 * A wedge scanner fires on a double-press and a clerk working through a sack
 * cannot tell one beep from two. The same bill twice would be two payments for
 * one customer, so a bill already in the batch is named rather than added.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ WHAT LEAVES THIS COMPONENT IS ROWS, NOT A PAYMENT
 * ══════════════════════════════════════════════════════════════════════════
 * `onScanned` hands the caller the accumulated rows. The runner takes them
 * through its own mapping, rules, dry run and receipt exactly as it takes a
 * file's — *"everything after it is the runner"* — so nothing here writes,
 * allocates or posts, and the partial-commit ruling and the SAVEPOINT that
 * makes it safe on PostgreSQL are the importer's, unchanged.
 */
import { useEffect, useRef, useState } from "react";

import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { parseRemittanceLine } from "@/api/remittanceEndpoints";
import type { ScannedRemittance } from "@/api/remittanceEndpoints";
import { apiErrorText } from "@/features/tenancy/settingsShared";

export interface ScanInputProps {
  client?: ApiClient;
  /** Every bill scanned so far, in the order they were scanned. */
  rows: readonly ScannedRemittance[];
  onRowsChange: (rows: readonly ScannedRemittance[]) => void;
  /** BR-SHL-025: null = this deployment can write; a string says why not. */
  writeBlockedReason?: string | null;
}

export function ScanInput(props: ScanInputProps) {
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>) =>
    params === undefined ? t(key) : t(key, params);
  const client = props.client ?? api;
  const field = useRef<HTMLInputElement | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // ⚠ **FOCUSED ON MOUNT, WHICH IS THE WHOLE FEATURE.** A wedge scanner types
  // into whatever has focus; a clerk holding a sack of bills in both hands
  // cannot click a field first. p068 ② calls it *"a source card and a focused
  // input"* in exactly those words.
  useEffect(() => {
    field.current?.focus();
  }, []);

  function record(scanned: ScannedRemittance): void {
    const already = props.rows.some((row) => row.invoice_no === scanned.invoice_no);
    if (already) {
      setRefusal(t("workflow.scan.duplicate", { bill: scanned.invoice_no }));
      return;
    }
    setRefusal(null);
    props.onRowsChange([...props.rows, scanned]);
  }

  function submit(line: string): void {
    const typed = line.trim();
    if (typed === "") {
      // p068's empty case, designed rather than discovered: a scanner that
      // reads no barcode sends no characters at all, so Enter on an empty field
      // is the ORDINARY shape of a failed scan.
      setRefusal(t("workflow.scan.empty"));
      return;
    }
    setBusy(true);
    parseRemittanceLine(client, typed)
      .then(record)
      .catch((error: unknown) => setRefusal(apiErrorText(error, translate)))
      .finally(() => {
        setBusy(false);
        // The field is cleared and re-focused whichever way it went, because
        // the next bill is already under the scanner.
        if (field.current !== null) {
          field.current.value = "";
          field.current.focus();
        }
      });
  }

  const blocked = props.writeBlockedReason ?? null;

  return (
    <div className="flex flex-col gap-4" data-workflow="scan">
      <label className="flex flex-col gap-2">
        {/* B14 rule 33 — a LABEL is at most three words and carries no
            sentence; the INSTRUCTION under it is one six-word sentence. */}
        <span className="font-semibold">{t("workflow.scan.label")}</span>
        <input
          ref={field}
          type="text"
          className="input"
          data-workflow="scan-field"
          autoComplete="off"
          disabled={blocked !== null || busy}
          title={blocked ?? undefined}
          aria-label={t("workflow.scan.label")}
          placeholder={t("workflow.scan.placeholder")}
          onKeyDown={(event) => {
            // ⚠ **ENTER IS THE SCANNER'S OWN TERMINATOR, NOT A FORM SUBMIT.**
            // A wedge sends the characters and then a carriage return; letting
            // that bubble would submit whatever form the runner is inside and
            // navigate away from a half-scanned sack.
            if (event.key !== "Enter") {
              return;
            }
            event.preventDefault();
            submit(event.currentTarget.value);
          }}
        />
        <span className="text-neutral-700">{t("workflow.scan.help")}</span>
      </label>

      {blocked !== null && (
        // BR-SHL-025: a disabled control owes the reader its reason, where they
        // are looking.
        <p className="text-neutral-700" role="note" data-workflow="scan-blocked">
          {blocked}
        </p>
      )}

      {refusal !== null && (
        // BR-SHL-020 — a plain sentence, never a raw code, and it is an ALERT
        // rather than a note: a mis-scan the clerk does not notice is a bill
        // that silently never got keyed.
        <p className="text-danger-700" role="alert" data-workflow="scan-refusal">
          {refusal}
        </p>
      )}

      <ScannedRows rows={props.rows} t={translate} />
    </div>
  );
}

/**
 * What has been scanned so far.
 *
 * ⚠ **A COMPONENT AND NOT A BLOCK INSIDE `ScanInput`** (B14 rule 43): the
 * receipt stage will want the same list, and a component declared inside
 * another render is a new component type on every render.
 *
 * ⚠ **IT IS NOT A `DataTable`.** B14 rule 16 exempts a wizard summary table
 * from the pagination footer, and this list is bounded by what one person can
 * scan in one sitting — a toolbar, a column chooser and a pager over fourteen
 * rows is the noise rule 32 is about.
 */
export function ScannedRows(props: {
  rows: readonly ScannedRemittance[];
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { rows, t } = props;
  if (rows.length === 0) {
    // An empty state that says what is missing, in one six-word sentence.
    return (
      <p className="text-neutral-700" data-workflow="scan-empty">
        {t("workflow.scan.none")}
      </p>
    );
  }
  return (
    <table className="data-table" data-workflow="scan-rows">
      <caption className="text-left text-neutral-700">
        {t("workflow.scan.counted", { count: rows.length })}
      </caption>
      <thead>
        <tr>
          <th scope="col">{t("workflow.scan.col.account")}</th>
          <th scope="col">{t("workflow.scan.col.bill")}</th>
          <th scope="col">{t("workflow.scan.col.amount")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.invoice_no}>
            {/* B14 rule 31 — every one of these is a human-facing number the
                clerk can read off the paper in their hand. */}
            <td>{row.account_no}</td>
            <td>{row.invoice_no}</td>
            {/* ⚠ **THE SERVER'S DECIMAL STRING, PRINTED.** The barcode carries
                MINOR UNITS and `remittance.py` converts them exactly; dividing
                by 100 here would be a float on a money path (hard rule 2). */}
            <td className="tabular-nums">{row.amount}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default ScanInput;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.8` · blueprint p067–p068 as images at 2.0 · apps/billing/remittance.py (`P5.10`)
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A✔ B✔ C✔ D=n/a(this writes nothing; the runner's own commit does) E=HELD(the card stays `available: false` until `documents.py` draws the bars — `scanSourceIsReachableAndHeld.dom.test.tsx` is the refusal and `paymentsSourceAndWriteMode.test.tsx` mounts this component so it cannot rot meanwhile) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/components/workflow/paymentsSourceAndWriteMode.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: the scanned list is NOT a `DataTable` — B14 rule 16 exempts a wizard summary table, and a pager over fourteen rows is rule 32's noise
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
