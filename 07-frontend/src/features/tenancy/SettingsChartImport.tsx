// ── Trace ──────────────────────────────────────────────
// Change:   CR-008 Tab 1 (SET-11.coa) — *"↑ Import CSV: ETL-style flow (upload
//           → map columns code/name/type → validate → load) with dedupe on
//           code"*, PO 2026-08-17.
//           Screens: SET-11 → Chart of accounts
// Rules:    BR-LED-015 (every chart change audits) · BR-SHL-020 (a failure is a
//           sentence, never a code) · BR-SHL-025 (a control this role may not
//           use renders DISABLED with its reason) · US-LED-005 (the chart is
//           the tenant's own) · CLAUDE.md rule 1 (tenant scoping — the server's)
// ───────────────────────────────────────────────────────
// THE FOUR STEPS, AND WHY THE FILE NEVER LEAVES THE BROWSER.
//
// r10 draws *upload → map columns → validate → load*, and the MAP step is the
// reason the parsing is here rather than on the server: mapping is a person
// looking at their own spreadsheet's headers and saying *"column B is the
// name"*. A server that took the raw file would have to GUESS that, which is
// exactly the step the design gives to a human.
//
// So: this component reads the file, shows the headers it found, lets the user
// point each of code/name/type at one of them, and posts ROWS. Every judgment
// about those rows — is the type real, is the code already taken, is it twice
// in this file, is it inside the reserved 2200 tax series — is the SERVER's
// (`apps/ledger/services.import_accounts`), and this screen only draws the
// answer. A second copy of those rules here would be a second chart-of-accounts
// policy, free to disagree with the one that actually writes.
//
// ⚠ **`existing` IS NOT AN ERROR AND IS NOT A CHANGE.** A code the tenant
// already has is SKIPPED — never renamed to whatever the spreadsheet said —
// because that account may carry a GL designation the posting service resolves
// every journal entry through. The count is shown so a re-import of the same
// file reads as *"180 already here, nothing to do"* rather than as a failure.
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { importLedgerAccounts } from "@/api/endpoints";
import type { ChartImportResult, ChartImportRow } from "@/api/endpoints";

import { apiErrorText } from "./settingsShared";
import { Button } from "@/components/Button";
import { Note } from "@/components/TextBits";
import { RefusalStrip } from "@/components/Surfaces";

/** The three fields an account needs, in the order the CR names them. */
export const IMPORT_FIELDS = ["code", "name", "type"] as const;
export type ImportField = (typeof IMPORT_FIELDS)[number];

export interface ParsedFile {
  headers: string[];
  rows: string[][];
}

/**
 * A comma-separated file, parsed the way a spreadsheet exports one.
 *
 * Quoted fields are honoured (`"Water revenue, base"` is ONE field) and a
 * doubled quote inside a quoted field is a literal quote — those two are the
 * whole of RFC 4180 that a chart of accounts ever meets, and getting them
 * wrong splits an account name into two columns silently.
 *
 * Pure, and exported, so the parsing is provable without a browser or a File.
 */
export function parseDelimited(text: string): ParsedFile {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          quoted = false;
        }
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      // A CRLF is ONE break, not two — otherwise every Windows export gains an
      // empty row between every real one and the preview reads as half junk.
      if (char === "\r" && text[index + 1] === "\n") {
        index += 1;
      }
      row.push(field);
      field = "";
      rows.push(row);
      row = [];
    } else {
      field += char;
    }
  }
  row.push(field);
  rows.push(row);
  const cleaned = rows.filter((line) => line.some((cell) => cell.trim() !== ""));
  if (cleaned.length === 0) {
    return { headers: [], rows: [] };
  }
  return {
    headers: cleaned[0].map((cell) => cell.trim()),
    rows: cleaned.slice(1),
  };
}

/**
 * The column a header probably is — a STARTING POINT the user overrides, never
 * a decision. Matching is exact-after-lower-casing on the field's own name, so
 * `Code`/`code`/`CODE` land and `Account Code` deliberately does not: a fuzzy
 * match that is right four times out of five is worse than a blank picker,
 * because the fifth is a chart of accounts loaded under the wrong column.
 */
export function guessMapping(headers: readonly string[]): Record<ImportField, string> {
  const mapping = { code: "", name: "", type: "" } as Record<ImportField, string>;
  for (const field of IMPORT_FIELDS) {
    const found = headers.find((header) => header.trim().toLowerCase() === field);
    mapping[field] = found ?? "";
  }
  return mapping;
}

/** The mapped rows, exactly as the server takes them. */
export function rowsFromMapping(
  parsed: ParsedFile,
  mapping: Record<ImportField, string>,
): ChartImportRow[] {
  const at = (field: ImportField): number => parsed.headers.indexOf(mapping[field]);
  const codeAt = at("code");
  const nameAt = at("name");
  const typeAt = at("type");
  return parsed.rows.map((row) => ({
    code: (codeAt >= 0 ? (row[codeAt] ?? "") : "").trim(),
    name: (nameAt >= 0 ? (row[nameAt] ?? "") : "").trim(),
    // Lower-cased here because that is a FORMAT of the same value, not a
    // judgment about it: the vocabulary is the server's and it refuses an
    // unknown one by name.
    type: (typeAt >= 0 ? (row[typeAt] ?? "") : "").trim().toLowerCase(),
  }));
}

/** Every field pointed at a column that exists — the Validate button's gate. */
export function mappingIsComplete(mapping: Record<ImportField, string>): boolean {
  return IMPORT_FIELDS.every((field) => mapping[field] !== "");
}

export interface ChartImportModalProps {
  client?: ApiClient;
  onClose: () => void;
  onImported: (created: number) => void;
}

export function ChartImportModal(props: ChartImportModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [parsed, setParsed] = useState<ParsedFile | null>(null);
  const [fileName, setFileName] = useState("");
  const [mapping, setMapping] = useState<Record<ImportField, string>>({
    code: "",
    name: "",
    type: "",
  });
  const [report, setReport] = useState<ChartImportResult | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  async function handleFile(file: File | undefined): Promise<void> {
    if (file === undefined) {
      return;
    }
    setProblem(null);
    setReport(null);
    const text = await file.text();
    const next = parseDelimited(text);
    setFileName(file.name);
    setParsed(next);
    setMapping(guessMapping(next.headers));
  }

  async function run(commit: boolean): Promise<void> {
    if (parsed === null) {
      return;
    }
    setWorking(true);
    setProblem(null);
    try {
      const result = await importLedgerAccounts(rowsFromMapping(parsed, mapping), commit, client);
      setReport(result);
      if (result.committed) {
        props.onImported(result.created?.length ?? 0);
      }
    } catch (error) {
      // BR-SHL-020: the server's own sentence, never a status code — the
      // all-or-nothing refusal names how many rows are bad and out of how many.
      setProblem(isApiError(error) ? apiErrorText(error, t) : t("api.error.unexpected"));
    } finally {
      setWorking(false);
    }
  }

  const counts = report?.counts ?? {};
  const blocked = (counts.invalid ?? 0) + (counts.duplicate_in_file ?? 0);

  return (
    // The shared modal frame's own classes (`components/FormModal.tsx`), not a
    // second set: this dialog is not a FormModal because it has three acts
    // (choose · validate · load) where that component has one submit, but it
    // must not look like a different product because of it. IS-10: Esc closes.
    <div
      className="modal-overlay"
      role="presentation"
      onClick={props.onClose}
      onKeyDown={(event) => event.key === "Escape" && props.onClose()}
    >
      <div
        className="modal-card settings-import-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t("settings.accounting.import.title")}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <div className="modal-kicker">{t("settings.accounting.kicker")}</div>
            <h4 className="modal-title">{t("settings.accounting.import.title")}</h4>
          </div>
        </div>
        <div className="modal-body">
        <Note>{t("settings.accounting.import.lede")}</Note>

        {/* STEP 1 — the file. */}
        <label className="field-label" htmlFor="chart-import-file">
          {t("settings.accounting.import.fileLabel")}
        </label>
        <input
          className="input"
          id="chart-import-file"
          type="file"
          accept=".csv,text/csv,text/plain"
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
        {fileName !== "" && (
          <Note>
            {t("settings.accounting.import.fileChosen", {
              file: fileName,
              rows: parsed?.rows.length ?? 0,
            })}
          </Note>
        )}

        {/* STEP 2 — the mapping. The design's own step, and a human's. */}
        {parsed !== null && parsed.headers.length > 0 && (
          <div className="settings-import-mapping">
            <h3 className="settings-frame-title">{t("settings.accounting.import.mapTitle")}</h3>
            {IMPORT_FIELDS.map((field) => (
              <div key={field} className="settings-rule-field">
                <label className="field-label" htmlFor={`chart-import-${field}`}>
                  {t(`settings.accounting.import.field.${field}`)}
                </label>
                <select
                  className="input"
                  id={`chart-import-${field}`}
                  value={mapping[field]}
                  onChange={(event) =>
                    setMapping({ ...mapping, [field]: event.target.value })
                  }
                >
                  <option value="">{t("settings.accounting.import.chooseColumn")}</option>
                  {parsed.headers.map((header) => (
                    <option key={header} value={header}>
                      {header}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        )}

        {problem !== null && (
          <RefusalStrip role="alert">
            {problem}
          </RefusalStrip>
        )}

        {/* STEP 3 — what the SERVER made of it. Counts first: a person wants
            "how many arrive" before "which line is wrong". */}
        {report !== null && (
          <div className="settings-import-report">
            <p className="settings-preview-line">
              {t("settings.accounting.import.counts", {
                new: counts.new ?? 0,
                existing: counts.existing ?? 0,
                invalid: counts.invalid ?? 0,
                duplicate: counts.duplicate_in_file ?? 0,
              })}
            </p>
            {report.committed && (
              <Note role="status">
                {t("settings.accounting.import.loaded", { count: report.created?.length ?? 0 })}
              </Note>
            )}
            {!report.committed && blocked > 0 && (
              <p className="settings-warning" role="status">
                {t("settings.accounting.import.blocked", { count: blocked })}
              </p>
            )}
            <table className="settings-table">
              <thead>
                <tr>
                  <th>{t("settings.accounting.import.col.line")}</th>
                  <th>{t("settings.accounting.col.code")}</th>
                  <th>{t("settings.accounting.col.accountName")}</th>
                  <th>{t("settings.accounting.col.type")}</th>
                  <th>{t("settings.accounting.import.col.outcome")}</th>
                </tr>
              </thead>
              <tbody>
                {report.rows.slice(0, 200).map((row) => (
                  <tr key={row.line}>
                    <td className="cell-num">{row.line}</td>
                    <td className="cell-num">{row.code ?? ""}</td>
                    <td>{row.name ?? ""}</td>
                    <td>{row.type ?? ""}</td>
                    <td>
                      {t(`settings.accounting.import.outcome.${row.outcome}`)}
                      {row.reason !== undefined &&
                        ` — ${t(`settings.accounting.import.reason.${row.reason}`)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {report.rows.length > 200 && (
              <Note>
                {t("settings.accounting.import.truncated", { count: report.rows.length - 200 })}
              </Note>
            )}
          </div>
        )}

        </div>
        <div className="modal-foot">
          <Button variant="ghost"  onClick={props.onClose}>
            {t("settings.accounting.import.close")}
          </Button>
          <Button
            variant="secondary"
            disabled={parsed === null || !mappingIsComplete(mapping) || working}
            // BR-SHL-025 — the reason is on the control, never a vanished one.
            title={
              parsed === null
                ? t("settings.accounting.import.needFile")
                : !mappingIsComplete(mapping)
                  ? t("settings.accounting.import.needMapping")
                  : undefined
            }
            onClick={() => void run(false)}
          >
            {t("settings.accounting.import.validate")}
          </Button>
          <Button
            variant="primary"
            // LOAD is deliberately gated on a VALIDATE having been run and come
            // back clean. The server refuses a bad file anyway; this stops a
            // person clicking Load on a file nobody has looked at yet.
            disabled={report === null || blocked > 0 || report.committed || working}
            title={
              report === null
                ? t("settings.accounting.import.needValidate")
                : blocked > 0
                  ? t("settings.accounting.import.blockedShort")
                  : undefined
            }
            onClick={() => void run(true)}
          >
            {t("settings.accounting.import.load", { count: counts.new ?? 0 })}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ChartImportModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-008@11-change-requests.md §CR-008 + its PO RULINGS 2026-08-17 (ruling 3: *"we only need file no live integration"*, which makes this the ONLY way a utility's own chart arrives)
// generated: 2026-08-17 by story-coder (CR-008 SET-11 lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔
// exceptions: E4 the preview table draws at most 200 rows and says how many it did not draw — a 900-row chart in a modal is unreadable and the COUNTS above it are the summary that matters · E4 there is no column-header row detection: the FIRST line is the header, which is what every spreadsheet export writes, and a file without one shows its first account in the picker so the mistake is visible before anything is posted · E3 nothing here retries a partial load, because there is no partial load to retry — the server commits all-or-nothing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
