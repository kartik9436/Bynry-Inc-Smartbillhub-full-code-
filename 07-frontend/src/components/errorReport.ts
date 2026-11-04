// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-SHL-6377` — *"Unable to download error report"* (the Product
//          Owner, 2026-09-23, pressing it on a failed property sale at
//          `TRF-02`: *"The sale was not recorded. Nothing changed hands."*)
// Rules:   A18 §4 (Retry / Download error report / Cancel) · CLAUDE.md hard-won
//          law 2 (built is not wired) · B14 rule 31 (no database id as a
//          visible value — here, withheld from the file too) · change process
//          §7 (the version a report names is the one the footer shows)
// Decision: 12-governance/02-decision-log.md, 2026-09-23 — *"Fixed once, in the
//          shared failure panel, so every screen's button downloads a small
//          report — screen, time, version, what was attempted, the refusal's
//          code and sentence — rather than 99 call sites edited one by one."*
// ───────────────────────────────────────────────────────
// THE ERROR REPORT: WHAT FAILED, WHERE AND WHEN — AND NOTHING ABOUT WHO.
//
// Pure: it takes what the panel already knows and returns a file name and the
// file's text. The one impure function, `saveTextFile`, hands that to the
// browser. `ErrorReportButton` joins the two.
//
// ⚠ **THE LABELS ARE ENGLISH IN EVERY LANGUAGE, DELIBERATELY.** The file is for
// the people who answer a support call, and a report whose field names change
// with the clerk's language is eleven formats to read rather than one. It is
// the same reasoning `ScreenIdTag` records for the screen id — an id is an id
// in every language. What the CLERK read is carried exactly as they read it:
// the panel's two sentences go in verbatim, in whatever language the screen
// was in.
//
// ⚠ **WHAT IS LEFT OUT, AND WHY EACH ONE** — the file says the same in its own
// header, because a person handed a file is owed that before they send it on:
//   * **anything typed into the form** — the panel is handed no form value and
//     this file is handed nothing but the panel's props;
//   * **request and answer bodies, and the refusal's `params`** — a body is the
//     form, and `params` can carry a name or an amount;
//   * **query-string VALUES** outside a short list of navigation words
//     (`step`, `tab`, …) — `?q=` is whatever a clerk searched for;
//   * **any address segment that is not a plain route word or a printed
//     reference number** — the portal's draft link is a capability, and it is
//     a UUID in the address bar (`portal/draftToken.ts`); a rule that kept
//     UUIDs as "just ids" would put that link in a file somebody emails;
//   * **cookies, tokens, passwords, headers** — nothing here reads them.

/** Query parameters whose VALUES are navigation, never something a person typed. */
const NAVIGATION_PARAMS: ReadonlySet<string> = new Set([
  "step",
  "tab",
  "view",
  "page",
  "per",
  "sort",
]);

/** A navigation value is a short plain word or number; anything else is withheld too. */
const NAVIGATION_VALUE = /^[A-Za-z0-9_.-]{1,40}$/;

/** A route word: lower-case letters, `-` and `_` only. `transfers`, `meter-picker`. */
const ROUTE_WORD = /^[a-z](?:[a-z_-]*[a-z])?$/;

/** A reference the product PRINTS for a person: `AC-2026-00012`, `SR-26-0001`, `TRF-02`. */
const PRINTED_REFERENCE = /^[A-Z]{1,5}(?:-[A-Z0-9]{1,10}){1,4}$/;

export const WITHHELD = "(withheld)";

/**
 * One address, route words and printed references kept, everything else withheld.
 *
 * `keepReferences: false` (CR-169-BRC10) withholds the printed references too.
 * An error report is a file a person chooses to send to support, who need the
 * reference to find the record; an analytics event is sent by nobody's choice
 * to a third party, and the PO ruled account numbers out of it (CR §2 row 8,
 * §5). ONE cleaner with one switch, not a second copy — `src/analytics/privacy.ts`
 * is the only caller that turns it off.
 */
export function redactPath(path: string, options: { keepReferences?: boolean } = {}): string {
  const keepReferences = options.keepReferences ?? true;
  return path
    .split("/")
    .map((segment) =>
      segment === "" || ROUTE_WORD.test(segment) || (keepReferences && PRINTED_REFERENCE.test(segment))
        ? segment
        : WITHHELD,
    )
    .join("/");
}

/** `?step=5&q=Hollis` → `?step=5&q=(withheld)`. Names are the code's; values may be a person's. */
export function redactSearch(search: string): string {
  const params = new URLSearchParams(search);
  const parts: string[] = [];
  params.forEach((value, name) => {
    const keep = NAVIGATION_PARAMS.has(name) && NAVIGATION_VALUE.test(value);
    parts.push(`${name}=${keep ? value : WITHHELD}`);
  });
  return parts.length === 0 ? "" : `?${parts.join("&")}`;
}

/** The pieces of a wall-clock time in one zone, digits only. */
interface ZonedParts {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
}

function partsIn(at: number, timeZone: string): ZonedParts {
  const format = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const out: Record<string, string> = {};
  for (const part of format.formatToParts(new Date(at))) {
    out[part.type] = part.value;
  }
  return {
    year: out.year ?? "0000",
    month: out.month ?? "00",
    day: out.day ?? "00",
    hour: out.hour ?? "00",
    minute: out.minute ?? "00",
    second: out.second ?? "00",
  };
}

/**
 * The zone a time is written in: the utility's when this page knows it, and
 * UTC — SAID to be UTC — when it does not. A time with no zone beside it is the
 * defect `TenantRegional.tsx` was written to end (a 7pm payment read as the
 * next day), so the zone is always named.
 */
function zoneOf(timeZone: string | null): { zone: string; known: boolean } {
  if (timeZone === null || timeZone === "") {
    return { zone: "UTC", known: false };
  }
  try {
    new Intl.DateTimeFormat("en-US", { timeZone });
    return { zone: timeZone, known: true };
  } catch {
    return { zone: "UTC", known: false };
  }
}

/** Everything the report is built from. The panel knows all of it; nothing is fetched. */
export interface ErrorReportInput {
  /** `TRF-02`, or null where the screen register has no id for this address. */
  screenId: string | null;
  /** The router's pathname and search — redacted here, never by the caller. */
  pathname: string;
  search: string;
  /** `Date.now()` at the press. */
  at: number;
  /** The utility's IANA zone (`tenant_settings.timezone`), or null when not published here. */
  timeZone: string | null;
  /** `07-frontend/package.json`'s version — the one the footer shows. */
  version: string;
  /** The panel's two sentences, exactly as drawn. */
  title: string;
  reason: string;
  /** The panel's diagnostic line (`diagnosticOf`), when it drew one. */
  diagnostic: string | null;
  /** The last refusal the transport saw, when one arrived for this panel. */
  request: {
    method: string;
    path: string;
    status: number;
    code: string | null;
    messageKey: string;
    ref: string | null;
    at: number;
  } | null;
}

export interface ErrorReport {
  /** `TRF-02-error-20260923-1405.txt` — the zone's wall clock, to the minute. */
  fileName: string;
  text: string;
}

/** What the file says it leaves out, before anything else. Plain sentences. */
const HEADER = [
  "SMART360 Next error report",
  "",
  "Send this file to your support contact. It says what failed, where and when,",
  "and nothing about who.",
  "",
  "It deliberately leaves out: anything typed into the form; the body of any",
  "request or answer; the details a refusal carried; the values of search and",
  "filter settings in the address; record numbers and links in addresses;",
  "cookies, session tokens and passwords.",
  "",
  'The lines "What failed" and "Reason" are copied exactly as the screen showed',
  "them.",
];

/** Build the report. Pure — the same input always gives the same bytes. */
export function buildErrorReport(input: ErrorReportInput): ErrorReport {
  const { zone, known } = zoneOf(input.timeZone);
  const now = partsIn(input.at, zone);
  const stamp = `${now.year}-${now.month}-${now.day} ${now.hour}:${now.minute}:${now.second}`;
  const zoneNote = known ? zone : `${zone} (the utility's time zone was not known on this page)`;
  const screen = input.screenId ?? "unknown";

  const lines = [
    ...HEADER,
    "",
    `Screen:       ${screen}`,
    `Page:         ${redactPath(input.pathname)}${redactSearch(input.search)}`,
    `Time:         ${stamp} ${zoneNote}`,
    `Version:      ${input.version}`,
    "",
    `What failed:  ${input.title}`,
    `Reason:       ${input.reason}`,
    `Diagnostic:   ${input.diagnostic ?? "none shown"}`,
    "",
  ];

  if (input.request === null) {
    lines.push("Refused request: none recorded in the minute before this panel appeared.");
  } else {
    const seen = partsIn(input.request.at, zone);
    lines.push(
      "Refused request (the last one the product saw for this panel)",
      `  Method:       ${input.request.method}`,
      `  Path:         ${redactPath(input.request.path)}`,
      `  Status:       ${input.request.status}`,
      `  Code:         ${input.request.code ?? "none"}`,
      `  Message key:  ${input.request.messageKey}`,
      `  Reference:    ${input.request.ref ?? "none"}`,
      `  At:           ${seen.hour}:${seen.minute}:${seen.second} ${zone}`,
    );
  }
  lines.push("");

  // The id is the file's first word so a support inbox sorts by screen. A dot
  // in a sub-id (`PLN-01.charges`) is legal in a file name on every platform.
  const safeId = screen.replace(/[^A-Za-z0-9._-]/g, "-");
  const fileName = `${safeId}-error-${now.year}${now.month}${now.day}-${now.hour}${now.minute}.txt`;
  return { fileName, text: lines.join("\n") };
}

/**
 * Hand a text file to the browser's own download.
 *
 * The anchor is attached for the click (Firefox ignores a click on a detached
 * one) and removed straight after; the object URL is released a second later
 * rather than at once, because revoking it in the same task can cancel the
 * download in some browsers before it has read the bytes.
 */
export function saveTextFile(fileName: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-6377 (lane ERROR-REPORT)
// generated: 2026-09-23 by lane ERROR-REPORT
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ (at tip d351e5fee) · eslint --max-warnings 0✔ on the changed files · G31✔ G35✔ G123✔ G39✔ G42✔ · vitest ErrorReport.dom.test.tsx 5/5✔ (proved RED on 18818920f) · StateFrame/WizardFrame/DataTable/client suites✔
// exceptions: (1) NO i18n key for the file's labels — see the header; the
//         clerk's own sentences travel verbatim · (2) no markup and no
//         stylesheet class (B14 rule 21 not engaged)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
