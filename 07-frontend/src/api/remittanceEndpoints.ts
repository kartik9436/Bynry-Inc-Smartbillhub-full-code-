// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.8` — the Scan source on 4·3a's Extract stage.
//           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p067–p068,
//           read AS IMAGES at 2.0 (B14 rule 42).
// Rules:    CLAUDE.md hard rule 2 (money is a DECIMAL STRING on the wire; the
//           barcode carries MINOR UNITS and the conversion is the server's)
// ───────────────────────────────────────────────────────
// The one door onto the remittance grammar.
//
// ⚠ **THE GRAMMAR IS NOT IMPLEMENTED ON THIS SIDE, AND THAT IS THE POINT.**
// `CR-139-BRC07` §6: *"`P5.8` calls `apps.billing.remittance.parse()` — do not
// re-derive the grammar; that is the whole reason it is a module."* A second
// Code 39 mod-43 check character written in TypeScript is two implementations
// that can disagree about whether a scan was mis-read, on the one path whose
// entire job is to catch a mis-read.
import type { ApiClient, ApiResponse } from "./client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One line a scanner typed, taken apart and CHECKED. */
export interface ScannedRemittance {
  /** `ACC-1042` — the account the bill was addressed to. */
  account_no: string;
  /** `BL-2608-0117` — the bill. A payment scanned twice for one bill is the
   *  mistake a desk actually makes, so this is what the caller de-duplicates
   *  on. */
  invoice_no: string;
  /** The amount as a DECIMAL STRING — `"142.18"`. Hard rule 2: never a JSON
   *  number, and never divided by 100 in the browser. */
  amount: string;
  /** What the barcode literally carried — `14218`. Kept so a screen can show a
   *  clerk exactly what was read when a figure looks wrong. */
  amount_minor: number;
  /** The mod-43 check character the line ended with, already verified. */
  check: string;
}

/**
 * `POST /billing/remittance/parse` — **it verifies and REFUSES.**
 *
 * There is no *parse loosely* mode: an empty scan, a bad check character, a
 * wrong field count and a non-digit amount each come back as a refusal with a
 * sentence saying which. `P5.14`'s outcome is *"a mis-scan fails visibly"* and
 * `P5.15`'s is *"a scan with no barcode fails visibly rather than silently
 * keying nothing"*.
 */
export function parseRemittanceLine(
  client: ApiClient,
  line: string,
): Promise<ScannedRemittance> {
  return client
    .post<ScannedRemittance>("/billing/remittance/parse", { line })
    .then((response) => requireData(response));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.8` · blueprint p067–p068 as images at 2.0
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/components/workflow/paymentsSourceAndWriteMode.test.tsx
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
