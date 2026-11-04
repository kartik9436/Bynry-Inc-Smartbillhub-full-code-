// ── Trace ──────────────────────────────────────────────
// Change:  **B14 rule 43** — the drawn document table, extracted out of
//          `ServiceRequestCapturePage.tsx` step 4 so a second host can render
//          it instead of copying it. See `documentCapture.ts`'s header.
// Rules:   B14 rule 20 (one table type) · rule 31 (no database id on screen) ·
//          rule 33 (a FACT ≤ 6 words) · rule 21 (Tailwind only) ·
//          `DEF-CUS-5872` (`file_present`, never `attached`)
// Screens: `REQ-03.4`, Accounts blueprint p078 (TOP) — read as a page image
//          per B14 rule 42; the small labels there are vector art and a text
//          search for `UPLOADED BY` returns nothing.
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";

import { EyeIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLink } from "@/components/Surfaces";

import { DocumentStateCell } from "./DocumentStateCell";
import { documentFileType, formatDocumentSize } from "./documentCapture";
import type { DocumentRequiredOf, DocumentRow, DocumentTranslator } from "./documentCapture";

/**
 * **THE DRAWN TABLE — `DOCUMENT · REQUIRED · FILE · UPLOADED BY · STATE`**,
 * five columns in p078's order, plus an actions column that appears only when
 * a host gives it something to do.
 *
 * ⚠ **IT RENDERS WHAT IT IS GIVEN AND FETCHES NOTHING.** The block it was
 * extracted from read the SERVER rather than a draft, and that is what makes a
 * document survive a wizard being closed — but WHICH server call is the host's
 * business, and a component that fetched would have one route baked into it
 * and be usable by exactly one screen. That is the thing rule 43 is against.
 *
 * ⚠ **EVERY CELL ASKS `file_present`, NEVER `attached` (`DEF-CUS-5872`).** All
 * six `service_request_documents` rows on the beta carry a ref shaped
 * `sample-data://cr030/…`, none resolves to a stored document, every `size` is
 * NULL and FOUR READ `verified`. Printing `Verified` beside an em dash tells a
 * clerk somebody checked a file that does not exist.
 */
export function DocumentTable(props: {
  rows: readonly DocumentRow[];
  t: DocumentTranslator;
  /** The locale a size is spelt in — `i18n.language`, never the server's. */
  locale: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  requiredOf: DocumentRequiredOf;
  /**
   * **What to do about a document that HAS a file.**
   *
   * ⚠ **IT IS OPTIONAL AND SOMETHING PASSES IT — hard-won law 2 IN BOTH
   * DIRECTIONS.** An optional prop nothing passes is dead UI; a row of facts
   * with nothing to press over a file the server has had a download route for
   * all along is that law's MIRROR, which is the shape the move-in block still
   * has (`moveInRequestBlocks.RequestDocuments`: file name, what it proves,
   * where it stands, and ZERO clickable controls). `openStoredDocument` in
   * this folder is how a host fills it, and `ServiceRequestCapturePage` does.
   *
   * ⚠ **THE CONTROL IS DRAWN ONLY OVER `file_present`.** A row recording *the
   * applicant is expected to bring this* has nothing to open, and offering it
   * would be the same claim `DEF-CUS-5872` is about.
   */
  onOpen?: (row: DocumentRow) => void;
  /** `CR-158-BRC10` — save the file rather than open it. Drawn beside `Open`
   *  only when a host passes it, and only over a row with a file. */
  onDownload?: (row: DocumentRow) => void;
  /** The row being opened, so its control can say so rather than going quiet. */
  openingId?: string | null;
  /** A refusal the host wants printed under the table — an expired or
   *  unreachable link, named rather than swallowed. */
  openError?: string | null;
  /**
   * **The label a document TYPE code is read as** — `CR-163-BRC10` item 25,
   * `DEF-CUS-9187`. Absent, the cell reads the SERVICE REQUEST's vocabulary
   * (`customers.serviceRequest.docType.*`), which is every existing host. An
   * ACCOUNT's documents are typed from a different list (`contract`, `kyc`,
   * …), so the New Connection detail printed the raw code `contract`.
   * Opt-in under B14 rule 36: absent renders byte-for-byte as before.
   */
  docTypeLabel?: (code: string) => string;
  /**
   * **Drop Required and State** where the host has no answer to either — an
   * account's documents carry no checklist and no reviewer's verdict, so the
   * two columns were blank on every row (`DEF-CUS-9187`, the PO's *"filled or
   * dropped"*). Opt-in; absent draws both, as before.
   */
  withoutChecklist?: boolean;
  /**
   * **The row's open control as B14 rule 15 draws a row action: an EYE, with
   * the file name itself a link** (`CR-163-BRC10` item 24, `DEF-CUS-9186`) —
   * the account's own Documents tab's shape (`DEF-CUS-9147`, 2.454.2). Opt-in:
   * absent keeps the text button every existing host draws.
   */
  openAsIcon?: boolean;
  /**
   * **Image 21's four columns** — `DEF-CUS-9764`, a move-in request's
   * Documents tab: Document · Needed (a REQUIRED chip where `requiredOf` says
   * so, `—` otherwise) · File (the NAME, which opens it) · Added (date · who).
   * No State and no Actions column: the drawing has neither. Opt-in under B14
   * rule 36; absent renders byte-for-byte as before.
   */
  neededLayout?: boolean;
}) {
  const { t } = props;
  if (props.neededLayout === true) {
    return <NeededLayoutTable {...props} />;
  }
  const canOpen = props.onOpen !== undefined;
  const withChecklist = props.withoutChecklist !== true;
  const asIcon = props.openAsIcon === true && canOpen;
  return (
    <>
      <table className="data-table" data-table="capture-documents">
        <thead>
          <tr>
            <th>{t("customers.serviceRequest.documents.col.document")}</th>
            {withChecklist && <th>{t("customers.serviceRequest.capture.col.required")}</th>}
            <th>{t("customers.serviceRequest.capture.col.file")}</th>
            <th>{t("customers.serviceRequest.capture.col.uploadedBy")}</th>
            {withChecklist && <th>{t("customers.serviceRequest.capture.col.state")}</th>}
            {canOpen && <th>{t("customers.serviceRequest.capture.col.actions")}</th>}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.id} data-doc-row={row.doc_type}>
              <td>
                <span className="block text-text" data-doc-name="">
                  {props.docTypeLabel !== undefined
                    ? props.docTypeLabel(row.doc_type)
                    : t(`customers.serviceRequest.docType.${row.doc_type}`, {
                        defaultValue: row.doc_type,
                      })}
                </span>
                {/* What it proves is the clerk's own note and is asked for on
                    the form below rather than as a column. It is shown under
                    the name so a reopened record can be checked against what
                    was typed. */}
                {row.what_it_proves !== null && row.what_it_proves !== "" && (
                  <span className="block text-neutral-700" data-doc-proves="">
                    {row.what_it_proves}
                  </span>
                )}
              </td>
              {withChecklist && (
                <td data-doc-required="">
                  {/* Yes · No · — . The em dash is DRAWN, not invented: p078's
                    `Anything else` row shows one, because the catch-all type is
                    not something a checklist can name. */}
                  {props.requiredOf(row) === null
                    ? "—"
                    : props.requiredOf(row) === true
                      ? t("customers.serviceRequest.capture.required.yes")
                      : t("customers.serviceRequest.capture.required.no")}
                </td>
              )}
              <td data-doc-file="">
                {/* ⚠ **NAME AND SIZE, AND NEITHER WITHOUT A FILE.** The drawn
                    cell reads `driving-licence.pdf · 1.2 MB`. A row with no
                    artefact reads `—` even when it carries a NAME — which all
                    six seeded rows do — because this column answers *is there a
                    file*, and printing a filename beside nothing is the claim
                    this component must not make. */}
                {row.file_present === true && (row.name ?? null) !== null ? (
                  <>
                    {asIcon && (
                      // `DEF-CUS-9186` — the NAME opens the file, as the eye does.
                      <InlineLink
                        data-doc-file-link={row.doc_type}
                        onClick={() => props.onOpen?.(row)}
                      >
                        {row.name}
                      </InlineLink>
                    )}
                    <span className="tabular-nums">
                      {/* `CR-158-BRC10` — name · TYPE · size. The type is what
                          the store recorded the bytes to be, so a file a
                          customer named `.pdf` that is a photo says PNG. */}
                      {[
                        asIcon ? null : row.name,
                        documentFileType(row.content_type ?? null),
                        typeof row.size_bytes === "number"
                          ? formatDocumentSize(row.size_bytes, props.locale)
                          : null,
                      ]
                        .filter((part): part is string => part !== null && part !== "")
                        .map((part, index) => (asIcon || index > 0 ? ` · ${part}` : part))
                        .join("")}
                    </span>
                    {/* ⚠ Shown ONLY when the two differ. `original_size_bytes`
                        is `null` for a file stored exactly as it arrived, so a
                        second figure appears precisely when a clerk who chose a
                        3.1 MB file would otherwise wonder why it says 400 KB. */}
                    {typeof row.original_size_bytes === "number" && (
                      <span className="block text-neutral-700 tabular-nums">
                        {t("customers.serviceRequest.capture.shrunkFrom", {
                          size: formatDocumentSize(row.original_size_bytes, props.locale),
                        })}
                      </span>
                    )}
                  </>
                ) : (
                  "—"
                )}
              </td>
              <td data-doc-by="">
                {/* `S. Ortiz · 05/04/2026`. ⚠ **THE NAME, NEVER THE USER ID —
                    B14 rule 31**, in the PO's own words (*"no Databse ID on
                    screen - that is a rule"*). `DocumentRow` does not carry the
                    uuid at all, so this cell cannot print it by accident.

                    ⚠ **`?? null` AND NOT `!== null`, AND A BROWSER WALK IS
                    WHY.** `row.uploaded_by_name !== null` is TRUE when the key
                    is ABSENT, so the cell printed the literal word `undefined`
                    beside a real date the first time this ran against a server
                    that had not picked the field up yet. Typescript cannot
                    catch it: the payload is typed `string | null` and the
                    server is free to be older than the type. */}
                {uploadedBy(row, props.timeZone, props.dateFormat, props.t)}
              </td>
              {/* ══════════════════════════════════════════════════════════
                  **STATE IS THE REVIEWER'S VERDICT, AND IT HAS TWO VALUES —
                  PO ruling 2026-09-22**, verbatim: *"once you remove the virus
                  check - you will ahveonly two cases verified or rejected in
                  case of rejected show the reason in short to user why it is
                  rejected."*

                  **It had FOUR** — `Not checked`, `Nothing attached`,
                  `Rejected`, `Verified` — and two of them were not verdicts at
                  all. `Not checked` read, to the PO, as the virus check — and
                  the scan itself stayed on the wire until the PO asked a
                  second time on 2026-09-23 (`DEF-SHL-6347`); it is gone now. `Nothing attached` is a fact about the
                  FILE, and the FILE column one place left already states it as
                  `—`; printing it twice made *no file yet* and *reviewed and
                  refused* read as one kind of thing.

                  ⚠ **SO THE CELL IS EMPTY UNTIL SOMEBODY DECIDES, AND THAT IS
                  THE READING TAKEN OF "only two cases".** A row with no file
                  and a row attached-but-unreviewed both show nothing here —
                  they are told apart by the FILE column, which answers *is
                  there a file* while this one answers *what was decided*. One
                  column, one question. Recorded in the decision log of
                  2026-09-22 so a later lane meeting a blank cell knows it is
                  deliberate.

                  ⚠ **THE REJECTION REASON WAS ALREADY STORED AND ALREADY
                  PRINTED** — `ServiceRequestDocument.reject_reason`, written by
                  `reject_document` from the detail page's `Reject`, which
                  REQUIRES one. What is new is the TRUNCATION: it is free text
                  a human typed, so B14 rule 33's six-word cap cannot bind it,
                  and a paragraph in a table cell is what the cap is for. The
                  row shows the short form; `title` gives the whole of it on
                  demand, which is the same affordance the kit uses elsewhere
                  for a value longer than its cell.
                  ══════════════════════════════════════════════════════════ */}
              {/* ⚠ **THE CELL IS A COMPONENT NOW — B14 rule 43.** This logic
                  was written out here and two other tables printed the same
                  fact differently: the request detail's Documents tab still
                  drew a third neutral `Not yet checked` pill and never showed
                  the reason, and step 6's review table read the raw
                  `verification_state` with no `file_present` guard at all. One
                  verdict, one place. */}
              {withChecklist && (
                <td data-doc-state="">
                  <DocumentStateCell row={row} t={t} />
                </td>
              )}
              {canOpen && (
                <td data-doc-actions="">
                  {row.file_present && asIcon ? (
                    // B14 rule 15 — a row action is an ICON with its name as
                    // the tooltip; `DEF-CUS-9147`'s account tab draws this one.
                    <RowActions>
                      <RowAction
                        icon={<EyeIcon />}
                        label={t("customers.account.documents.open")}
                        onClick={() => props.onOpen?.(row)}
                      />
                    </RowActions>
                  ) : row.file_present ? (
                    <span className="inline-flex flex-wrap gap-3">
                      <button
                        type="button"
                        className="text-accent-700 underline underline-offset-2 disabled:text-neutral-700 disabled:no-underline"
                        data-doc-open={row.doc_type}
                        disabled={props.openingId === row.id}
                        onClick={() => props.onOpen?.(row)}
                      >
                        {/* Rule 33: a LABEL is ≤ 3 words and is not a sentence. */}
                        {t("customers.serviceRequest.capture.openTheFile")}
                      </button>
                      {props.onDownload !== undefined && (
                        <button
                          type="button"
                          className="text-accent-700 underline underline-offset-2"
                          data-doc-download={row.doc_type}
                          onClick={() => props.onDownload?.(row)}
                        >
                          {t("customers.serviceRequest.documents.download")}
                        </button>
                      )}
                    </span>
                  ) : (
                    /* ⚠ **NOT A DISABLED CONTROL.** There is no file, so there
                       is no act being withheld from this clerk — a greyed
                       `Open` whose reason they have to infer is the shape rule
                       43's sibling law was written about. The STATE cell one
                       column left already says `Nothing attached`. */
                    "—"
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {(props.openError ?? null) !== null && (
        <p className="field-error" role="alert" data-doc-open-error="">
          {props.openError}
        </p>
      )}
    </>
  );
}

/** `DEF-CUS-9764` — image 21's table. See `neededLayout` on `DocumentTable`. */
function NeededLayoutTable(props: Parameters<typeof DocumentTable>[0]) {
  const { t } = props;
  return (
    <table className="data-table" data-table="capture-documents" data-doc-layout="needed">
      <thead>
        <tr>
          <th>{t("customers.serviceRequest.documents.col.document")}</th>
          <th>{t("customers.moveIn.customer.docs.col.needed")}</th>
          <th>{t("customers.serviceRequest.capture.col.file")}</th>
          <th>{t("customers.moveDetail.documents.colAdded")}</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr key={row.id} data-doc-row={row.doc_type}>
            <td>
              <span className="block text-text" data-doc-name="">
                {props.docTypeLabel !== undefined
                  ? props.docTypeLabel(row.doc_type)
                  : t(`customers.serviceRequest.docType.${row.doc_type}`, { defaultValue: row.doc_type })}
              </span>
            </td>
            <td data-doc-required="">
              {props.requiredOf(row) === true ? (
                <StatusPill tone="warning">{t("customers.moveIn.customer.docs.required")}</StatusPill>
              ) : (
                "—"
              )}
            </td>
            <td data-doc-file="">
              {row.file_present === true && (row.name ?? null) !== null ? (
                props.onOpen !== undefined ? (
                  <InlineLink data-doc-file-link={row.doc_type} onClick={() => props.onOpen?.(row)}>
                    {row.name}
                  </InlineLink>
                ) : (
                  row.name
                )
              ) : (
                "—"
              )}
            </td>
            <td data-doc-by="">{addedOn(row, props.timeZone, props.dateFormat, props.t)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** ⊕ `DEF-CUS-9834` — who brought it: a clerk by name, and a portal
 *  applicant by name WITH the role (*Kyle Mark (applicant)*), because nobody on
 *  staff uploaded that file and the name alone would read as a colleague. */
function uploaderWord(row: DocumentRow, t: DocumentTranslator): string | null {
  const who = row.uploaded_by_name ?? null;
  if (who === null) return null;
  return row.uploaded_by_role === "applicant"
    ? t("customers.documents.uploadedByApplicant", { name: who })
    : who;
}

/** Image 21's *Added* cell — `10/03/2026 · Asha Verma`: the date first. */
function addedOn(
  row: DocumentRow,
  timeZone: string,
  dateFormat: RegionalDateFormat,
  t: DocumentTranslator,
): ReactNode {
  const who = uploaderWord(row, t);
  const when = row.uploaded_at ?? null;
  if (when === null) {
    return "—";
  }
  const on = formatDate(when, timeZone, dateFormat);
  return who === null ? on : `${on} · ${who}`;
}

/** `S. Ortiz · 05/04/2026`, or an em dash when nobody and no date is held. */
function uploadedBy(
  row: DocumentRow,
  timeZone: string,
  dateFormat: RegionalDateFormat,
  t: DocumentTranslator,
): ReactNode {
  const who = uploaderWord(row, t);
  const when = row.uploaded_at ?? null;
  if (when === null) {
    return "—";
  }
  const on = formatDate(when, timeZone, dateFormat);
  return who === null ? on : `${who} · ${on}`;
}
