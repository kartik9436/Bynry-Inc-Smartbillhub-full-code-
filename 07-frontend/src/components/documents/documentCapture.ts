// ── Trace ──────────────────────────────────────────────
// Change:  **B14 rule 43**, ratified 2026-09-20 — PO, verbatim: *"document
//          sotrage - we need to make it compoentn so thatw e cna use it in
//          other palces also"* and *"make them coponents - dont write stand
//          alone code , engineer it"*.
// Rules:   B14 rule 43 (a piece of UI is a component; the test is
//          ADDRESSABILITY, not line count) · rule 21 (Tailwind utilities only;
//          every file in this folder is listed in
//          `src/styles/route-b-migrated.txt`) · rule 31 (no database id is
//          ever the visible value of a field) · rule 33 (a LABEL ≤ 3 words, a
//          FACT ≤ 6, RATIONALE zero words on screen) · rule 38 (where a
//          drawing and our UI rules disagree about how a FORM is built, the
//          rules win) · `BR-SHL-031` (the upload allowlist) · `BR-CUS-095`
//          (the tenant's own checklist decides what is required)
// Screens: `REQ-03.4` service-request capture, step 4 (Accounts blueprint
//          p078) — the host this was extracted FROM and is wired INTO.
// Tests:   `DocumentCapture.dom.test.tsx` (rendered output, never props) ·
//          `documentCaptureHosts.dom.test.tsx` (who renders it)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FOLDER EXISTS — IT IS AN EXTRACTION, NOT A SECOND IMPLEMENTATION
// ══════════════════════════════════════════════════════════════════════════
// Rule 43 was ruled on a measured failure: the PO said *"we have it … use
// it"* of a block that turned out to be written inline inside a page, so
// "use it" first meant making it a component. **The document capture was the
// same shape one screen over.** It was ~330 lines of JSX plus eight `useState`
// hooks and an `addDocument` function, all inline in
// `features/customers/ServiceRequestCapturePage.tsx` — 4,324 lines — and
// importable by nothing. A second host needing to take a document off a
// person had exactly two options: copy it, or ask for a backend it already
// had. Both were taken this week.
//
// ⚠ **THE MARKUP BELOW IS THAT BLOCK, MOVED, NOT RE-TYPED.** Same five
// columns in p078's order, same four filter chips, same two buttons, same
// `file_present` questions, same catalogue keys. A second spelling of a
// document table is precisely what rule 43 exists to refuse.
//
// ⚠ **WHAT IS SHARED IS THE FIELD SET AND THE CONSTRUCTION; WHAT IS NOT
// SHARED IS WHERE THE ROWS COME FROM (rule 43 clause 3).** Every host has its
// own route — a service request's documents hang off the request, an
// account's off the account — so this folder never names one. The host hands
// in rows and a way to write one, and owns its own endpoints.
//
// ⚠ **THE CATALOGUE KEYS ARE `customers.serviceRequest.*` AND THAT IS
// DELIBERATE, NOT LEFTOVER.** They are this product's DOCUMENT vocabulary —
// `Attach a file`, `Nothing attached`, `What it proves` — answered in all
// eleven catalogues (B14 rule 35) and already read by three screens. Minting a
// second namespace would be two spellings of one sentence, which is what rule
// 34 refuses. Renaming the existing ones moves every citation in eleven
// catalogues at once and belongs to whoever is ruling on the namespace, not
// to this extraction.

/**
 * **What a `t()` looks like to this folder** — the same shape every host
 * already holds. Passed in rather than hooked so a component can be rendered
 * by a test that names its own strings.
 */
export type DocumentTranslator = (key: string, options?: Record<string, unknown>) => string;

/**
 * **THE FIELD SET — rule 43 clause 3's "share the field set".**
 *
 * A structural subset of `ServiceRequestDocument`, so a host's own payload
 * satisfies it with no mapping at all. Every field here is one a document
 * table has to answer; nothing request-shaped is in it.
 *
 * ⚠ **`file_present`, NEVER `attached` (`DEF-CUS-5872`).** `attached` is
 * `bool(storage_ref)` and answers True for all six of the beta's seeded
 * placeholders, four of which also read `verified`. `file_present` answers
 * *is there a file*. Every question this folder asks about reading, opening or
 * sizing a document asks this one, and the type does not carry `attached` at
 * all so a host cannot reach for the wrong half by accident.
 */
export interface DocumentRow {
  id: string;
  doc_type: string;
  what_it_proves: string | null;
  /** The number ON the paper. ⚠ **NEVER PRINTED WHOLE** — every screen puts it
   *  through `maskLastFour` (PO ruling 2026-09-22, `BR-CUS-092(c)`). `null` on
   *  every row written before that date: nothing back-fills it, and nothing
   *  could, because the digits some old rows carry sit in `what_it_proves`
   *  beside words and telling the two apart is a guess. */
  document_number: string | null;
  /** What the file is called. Printed only beside a file that exists. */
  name: string | null;
  uploaded_at: string | null;
  /** Who attached it, **as a person**. ⚠ The uploader's uuid is deliberately
   *  not in this type — B14 rule 31, *"no Databse ID on screen - that is a
   *  rule"*. A field a screen must not print is better absent than invisible. */
  uploaded_by_name: string | null;
  /** ⊕ `DEF-CUS-9834` — `applicant` when the portal stored the file (the
   *  applicant brought it); absent or `null` for a clerk's upload. */
  uploaded_by_role?: "applicant" | null;
  /** The clerk's own *"required on this one"* tick, written when the row was
   *  made. It is ONE HALF of the answer — the tenant's checklist is the other
   *  (`BR-CUS-095`) — which is why the table asks the host's `requiredOf` and
   *  never reads this field directly. */
  required: boolean;
  size_bytes: number | null;
  /** What the clerk chose, written ONLY when the store losslessly re-deflated
   *  it. `null` means *stored exactly as it arrived*, not *unknown* — so the
   *  second figure appears precisely when the two differ. */
  original_size_bytes: number | null;
  file_present: boolean;
  /** `CR-158-BRC10` — what the store recorded the BYTES to be (`application/pdf`
   *  …), `null` with no file. Optional because older payloads omit it. */
  content_type?: string | null;
  verification_state: string;
  reject_reason: string | null;
}

/** `application/pdf` → `PDF`. The four types an upload door accepts, spelt the
 *  way a person names a file; anything else is `null` and simply not shown. */
export function documentFileType(contentType: string | null): string | null {
  switch ((contentType ?? "").split(";")[0].trim().toLowerCase()) {
    case "application/pdf":
      return "PDF";
    case "image/png":
      return "PNG";
    case "image/jpeg":
    case "image/jpg":
      return "JPG";
    case "text/csv":
    case "application/csv":
    case "application/vnd.ms-excel":
      return "CSV";
    default:
      return null;
  }
}

/**
 * **THE FORM'S FOUR CONTROLS, AS ONE VALUE.**
 *
 * A host holds this in its own state and hands it back changed. It is view
 * state and never part of whatever the host serialises: a browser `File`
 * belongs in neither a draft payload nor a query cache.
 */
export interface DocumentCaptureValue {
  /** One of the host's own `docTypes`. */
  docType: string;
  /** ⚠ A file input cannot be a controlled React input — the browser owns its
   *  value — so the chosen `File` lives here and the element is remounted to
   *  clear it. See `DocumentCaptureForm`'s `resetNonce`. */
  file: File | null;
  whatItProves: string;
  /** **The number ON the paper — PO ruling 2026-09-22, *"Yes, last four
   *  only"*.**
   *
   *  ⚠ **IT EXISTS BECAUSE ITS ABSENCE PUT A LICENCE NUMBER ON A LIST.** This
   *  form asked one free-text question — *what does this document prove* — and
   *  the column beside it on the reviewer's screen carried the same three
   *  words, so a clerk holding a driving licence had nowhere to put
   *  `865554556` and typed it there, where it printed in full
   *  (`DEF-CUS-6179`). `BR-CUS-092(c)` has required last-four-only on every
   *  read path since 2026-08-24.
   *
   *  **What it is NOT:** the SSN and the driving licence are `BR-CUS-092`'s two
   *  encrypted identifiers and have their own columns on `service_requests`.
   *  This is the reference number of whatever paper was handed over, kept whole
   *  so a clerk can read it back, and masked by every screen that shows it. */
  documentNumber: string;
  /** The clerk's own *"required on this one"*, which is a different fact from
   *  the tenant's checklist (`BR-CUS-095`). Both feed one answer; see
   *  `DocumentTable`'s `requiredOf`. */
  required: boolean;
}

/** Every control empty, with the host's first type chosen. */
export function emptyDocumentCapture(docType: string): DocumentCaptureValue {
  return { docType, file: null, whatItProves: "", documentNumber: "", required: false };
}

/**
 * What the browser's file picker filters on — **`BR-SHL-031`'s allowlist**.
 *
 * ⚠ **A CONVENIENCE, NEVER THE GUARD.** The server refuses anything outside
 * its own `ALLOWED_CONTENT_TYPES` with a **415**, and a clerk can defeat
 * `accept` in any picker. This only saves them choosing a file that was always
 * going to be refused.
 *
 * ⚠ **ONE SIGNED SENTENCE, ONE CONSTANT — AND THAT IS THIS FOLDER'S JOB.**
 * `SERVICE_REQUEST_DOCUMENT_ACCEPT` used to spell this string out a second
 * time, with a docstring explaining that it was *"the same string as
 * `ACCOUNT_DOCUMENT_ACCEPT`, and deliberately not imported from it"* because
 * that one is typed against the account door. Both objections were to
 * borrowing ANOTHER DOOR's constant; neither is an objection to a shared one.
 * `ACCOUNT_DOCUMENT_ACCEPT` still lives in `api/endpoints.ts` and is not this
 * lane's to move — named in the handover as the third door that should read
 * this.
 */
export const DOCUMENT_ACCEPT = ".pdf,.png,.jpg,.jpeg,.csv";

/**
 * **IS THIS FILE ONE THE SERVER WILL TAKE? — `DEF-CUS-6113`.**
 *
 * Returns the offending extension (`"txt"`, `"tif"`, …) when the file is
 * outside `accept`, and `null` when it is fine or when there is nothing to
 * check.
 *
 * ⚠ **`accept` ALONE IS A HINT AND A CLERK DEFEATS IT WITHOUT TRYING.** Every
 * file picker on every platform offers *All files*, and a drag-and-drop ignores
 * `accept` outright. So a `.txt` attached on New Connect step 1 was **accepted,
 * carried through seven more steps, refused 415 AFTER the connection was
 * created, and lost** — the done panel read *"1 document was not filed."*, with
 * no retry and no way back into the wizard. The allowlist is right
 * (`BR-SHL-031`); the MOMENT of the refusal was wrong.
 *
 * ⚠ **IT REFUSES BY EXTENSION AND NOT BY `File.type`, AND THAT IS ON PURPOSE.**
 * The browser's MIME guess is unreliable — Windows reports a `.csv` as
 * `application/vnd.ms-excel`, some report nothing at all — and the server's own
 * allowlist already carries FOUR spellings for two formats to survive exactly
 * that. An extension is what a clerk can see, name and act on, which is the
 * test `ALLOWED_EXTENSIONS` on the server side states in as many words.
 *
 * ⚠ **IT IS NOT THE GUARD AND DOES NOT PRETEND TO BE.** The server still
 * refuses with a 415 and nothing here weakens that; this saves a clerk the
 * eight steps between choosing a file and being told.
 */
export function refusedFileExtension(file: File | null, accept: string): string | null {
  if (file === null) {
    return null;
  }
  const allowed = accept
    .split(",")
    .map((one) => one.trim().toLowerCase())
    .filter((one) => one.startsWith("."));
  if (allowed.length === 0) {
    // Nothing declared is nothing to enforce — a host that passes an empty
    // `accept` has said it takes anything, and inventing a list here would be
    // this file deciding another door's allowlist.
    return null;
  }
  const name = file.name.toLowerCase();
  const dot = name.lastIndexOf(".");
  // A file with NO extension is left to the server. It is a real thing a
  // scanner produces, the server reads the declared media type rather than the
  // name, and refusing it here would refuse a file the door might take.
  if (dot <= 0 || dot === name.length - 1) {
    return null;
  }
  const extension = name.slice(dot);
  return allowed.includes(extension) ? null : extension.slice(1);
}

/**
 * **THE FOUR DRAWN FILTER CHIPS** — `All · Required · Missing · Rejected`
 * (Accounts blueprint p078, drawn on one row under the table).
 */
export const DOCUMENT_FILTERS = ["all", "required", "missing", "rejected"] as const;
export type DocumentFilter = (typeof DOCUMENT_FILTERS)[number];

/**
 * Is this document REQUIRED — and the answer has **three** values, not two.
 *
 * ⚠ **`null` IS A REAL ANSWER AND THE DRAWING DRAWS IT.** p078's `Anything
 * else` row shows `—` in REQUIRED, not `No`: a catch-all type is not something
 * a checklist can name, so *"is it required"* has no answer rather than a
 * negative one.
 *
 * The host supplies this because only the host knows its checklist
 * (`BR-CUS-095` — which ships ENTIRELY UNTICKED, so `Required` is legitimately
 * empty on a fresh tenant and the chip says so rather than naming two
 * documents a jurisdiction may not ask for).
 */
export type DocumentRequiredOf = (row: DocumentRow) => boolean | null;

/**
 * The table's rows, narrowed by the pressed chip.
 *
 * ⚠ **IT FILTERS ROWS, NOT TYPES.** p078 draws a TABLE of what this record
 * holds, not a tick-list of what it could hold: a type with no row is simply
 * not on the record yet, and the form below is how one arrives.
 */
export function filterDocumentRows<T extends DocumentRow>(
  rows: readonly T[],
  filter: DocumentFilter,
  requiredOf: (row: T) => boolean | null,
): T[] {
  return rows.filter((row) => {
    if (filter === "required") {
      return requiredOf(row) === true;
    }
    if (filter === "missing") {
      // ⚠ `file_present`, NEVER `attached` — see `DocumentRow`. A `Missing`
      // chip reading `attached` would hide the exact rows it exists to find.
      return row.file_present !== true;
    }
    if (filter === "rejected") {
      return row.verification_state === "rejected";
    }
    return true;
  });
}

/**
 * How big the file is, in the unit a person would say it in.
 *
 * ⚠ **FORMATTED ON THE SCREEN, NOT ON THE SERVER** — the same decision
 * `BR-SHL-034` records for dates: a server returning `"1.2 MB"` has chosen a
 * locale's decimal separator in the wrong place. The server sends a byte count
 * and this renders it.
 *
 * ⚠ **THERE IS A SECOND SPELLING OF THIS TODAY, IT IS STATED RATHER THAN
 * HIDDEN, AND A GUARD HOLDS THE TWO TOGETHER.** `formatBytes` lives inside
 * `features/customers/AccountDocumentsTab.tsx`, whose own comment says why
 * there must only ever be one — *"a second `formatBytes` is two answers to
 * `1.2 MB`"*. The kit is where a formatter every document screen needs
 * belongs, but that tab is another lane's file and folding it in is a move
 * this lane does not own; and a component in `components/` importing a whole
 * account TAB to borrow one function is a worse coupling than the one it
 * cures. So the implementation lives here, and
 * `DocumentCapture.dom.test.tsx` reads BOTH functions and fails if they ever
 * disagree on a table of byte values — the same drift guard
 * `applicantCapture.dom.test.tsx` uses for exactly this situation, proved RED
 * before it was trusted. **When the tab's owner folds it in, delete the guard
 * with the duplicate, not before.**
 */
export function formatDocumentSize(bytes: number, locale: string): string {
  if (bytes < 1024) {
    return `${bytes.toLocaleString(locale)} B`;
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${Math.round(kb).toLocaleString(locale)} KB`;
  }
  return `${(kb / 1024).toLocaleString(locale, { maximumFractionDigits: 1 })} MB`;
}

/** The longest a rejection reason may be ON THE ROW, in characters. */
export const REJECT_REASON_ROW_CHARS = 48;

/**
 * A stored rejection reason, cut to fit a table cell.
 *
 * ⚠ **IT IS CUT BY CHARACTERS AND NOT BY WORDS, AND THAT IS B14 RULE 33 BEING
 * OBEYED RATHER THAN DODGED.** Rule 33 caps what WE write — a label at three
 * words, a fact at six. **This is not our sentence**: `reject_reason` is free
 * text a reviewer typed, required by `reject_document`, and a six-word cut
 * would silently discard the half of a reason that says what to do about it.
 * So the instruction underneath the number is the one that binds here — *do
 * not print a paragraph in a table cell* — and the row shows a short form
 * while the whole text stays one hover away (PO 2026-09-22: *"show the reason
 * in short to user why it is rejected"*).
 *
 * ⚠ **THE ELLIPSIS IS ONE CHARACTER, NOT THREE FULL STOPS.** Three dots are a
 * different width at every font size and a screen reader says "dot dot dot".
 *
 * ⚠ **IT NEVER EMPTIES A NON-EMPTY REASON.** Whitespace is the caller's to
 * treat as absent; anything else answers at least one visible character,
 * because a cell that silently empties reads as *no reason was given* — which
 * is a different fact, and the one a clerk would repeat down a phone.
 */
export function shortReason(reason: string, limit: number = REJECT_REASON_ROW_CHARS): string {
  const text = reason.trim().replace(/\s+/gu, " ");
  if (text.length <= limit) {
    return text;
  }
  // Cut on a word boundary when there is one late enough to be worth using, so
  // a reason does not break mid-word for the sake of four characters.
  const cut = text.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  const kept = lastSpace > Math.floor(limit * 0.6) ? cut.slice(0, lastSpace) : cut;
  return `${kept.trimEnd()}…`;
}
