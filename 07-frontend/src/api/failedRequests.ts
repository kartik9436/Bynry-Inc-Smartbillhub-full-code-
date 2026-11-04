// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-SHL-6377` — *"Unable to download error report"* (the Product
//          Owner, 2026-09-23, on a failed property sale at `TRF-02`)
// Rules:   A18 §4 (the failure panel's *Download error report*) · TD-16 (keys,
//          never server prose) · CLAUDE.md hard-won law 2
// ───────────────────────────────────────────────────────
// THE LAST FEW REQUESTS THE SERVER REFUSED — WHAT THE ERROR REPORT DESCRIBES.
//
// ⚠ **WHY THE TRANSPORT KEEPS THIS AND NOT THE SCREEN.** The failure panel
// (`FailedWithRetry`) is drawn by 101 call sites and is handed two sentences —
// a title and a reason — and never the error that caused them. Threading the
// error through would mean editing every one of those screens while other
// lanes are editing them too, which is exactly the collision CLAUDE.md law 11
// exists to prevent. Every refusal a screen can show came through ONE client
// (`api/client.ts`), so that is the one place that can say what the request
// was — and it says it here, once, for every screen.
//
// ⚠ **WHAT IS KEPT IS CODES, NEVER CONTENT.** A method, a CONTRACT path with
// its query string cut off (a search term is what a clerk typed), a status, the
// envelope's `code` and `message_key`, and the short support reference. Never
// the request body, never the answer's `params` (a refusal's params can carry a
// name or an amount), never a header. `errorReport.ts` further withholds any
// path segment that is not a plain route word, because a path can carry a
// capability — the portal's draft link is a UUID in the address.
//
// ⚠ **IT IS A HINT FOR SUPPORT, NEVER AN AUTHORITY.** Nothing reads it back to
// decide anything; it lives in memory, in this tab only, and is gone on reload.

/** One refusal, as the transport saw it arrive. */
export interface FailedRequest {
  readonly method: string;
  /** The CONTRACT path the screen asked for — no tenant prefix, no query string. */
  readonly path: string;
  readonly status: number;
  readonly code: string | null;
  readonly messageKey: string;
  /** The reference a person reads aloud to support (`5F2B-9C1D`), when there is one. */
  readonly ref: string | null;
  /** `Date.now()` when the refusal arrived. */
  readonly at: number;
}

/** How many are kept. A report describes ONE; the rest are there so a later
 *  unrelated refusal cannot push the right one out before it is asked for. */
const KEPT = 8;

let recent: readonly FailedRequest[] = [];

/** Called by `api/client.ts` for every refusal it throws, and by nothing else. */
export function noteFailedRequest(entry: Omit<FailedRequest, "at">): void {
  const path = entry.path.split("?")[0] ?? "";
  recent = [...recent.slice(-(KEPT - 1)), { ...entry, path, at: Date.now() }];
}

/** The newest refusal that arrived at or after `since`, or null. */
export function lastFailedRequestSince(since: number): FailedRequest | null {
  for (let index = recent.length - 1; index >= 0; index -= 1) {
    const entry = recent[index];
    if (entry !== undefined && entry.at >= since) {
      return entry;
    }
  }
  return null;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-6377 (lane ERROR-REPORT) — the PO's decision-log entry of
//         2026-09-23, "*DOWNLOAD ERROR REPORT* DOES NOTHING ON 99 SCREENS"
// generated: 2026-09-23 by lane ERROR-REPORT
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ (at tip d351e5fee) · eslint --max-warnings 0✔ on the changed files · G31✔ G35✔ G123✔ G39✔ G42✔ · vitest ErrorReport.dom.test.tsx 5/5✔ (proved RED on 18818920f) · StateFrame/WizardFrame/DataTable/client suites✔
// exceptions: none — no markup, no stylesheet class, no catalogue key
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
