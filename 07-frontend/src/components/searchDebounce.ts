// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-5747 — the six portal lists took their page, their search
//          and their sort from the SERVER, and a search box that fires a
//          request per keystroke is what a client-held search never had to
//          think about.
// Contract: IS-3 (server-side search, debounced 300 ms, minimum 2 characters)
// Rules:   BR-CWP-011 (*"the SIGNED-IN surface calls the PORTAL edge and
//          nothing else"*) — which is why this is its own file and not an
//          import of `DataTable.tsx`, whose module scope calls the STAFF edge.
// Tests:   src/components/DataTable.test.tsx (the three IS-3 cases, unmoved) ·
//          src/portal/components/listTable.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The ONE search debouncer — framework-free, like the Toast queue.
 *
 * ⚠ **EXTRACTED FROM `DataTable.tsx` RATHER THAN COPIED (`DEF-CWP-5747`,
 * 2026-09-19), AND THE REASON IS A MODULE IMPORT AND NOT TIDINESS.**
 * `listTable.tsx`'s own docstring records why no portal file may import
 * `DataTable`: that module reads `getUserPreference` / `putUserPreference`
 * from `@/api/endpoints`, and `BR-CWP-011` says the signed-in surface calls the
 * PORTAL edge and nothing else. So the portal needed this function and could
 * not reach it. A second copy would have been the third one in this tree —
 * `FindTheAddress.tsx` and `UnitDetailPage.tsx` each hand-roll the same timer —
 * and a debounce that is 300 ms on one screen and 250 on another is a product
 * that feels inconsistent for no reason anybody can find.
 *
 * `DataTable.tsx` RE-EXPORTS both constants and this function, so every
 * existing importer — `ShellWithSession`, `FindTheAddress`, `DataTable.test` —
 * is untouched and there is still exactly one implementation.
 */

// IS-3: server-side search, debounced 300 ms, minimum 2 characters.
export const SEARCH_DEBOUNCE_MS = 300;
export const SEARCH_MIN_CHARS = 2;

export interface SearchDebouncer {
  type: (raw: string) => void;
  // Cancels any pending fire and syncs to "cleared" WITHOUT firing — the
  // caller performs its own state change (✕ clear is immediate per IS-3).
  clear: () => void;
}

export interface SearchDebounceOptions {
  /**
   * How many characters count as a query. IS-3's answer for a STAFF list is
   * two, and that is the default.
   *
   * ⚠ **THE PORTAL PASSES ONE, AND IT IS NOT A LOOSENING OF IS-3.** IS-3
   * governs the staff search across a tenant's whole population, where a
   * one-character query is a scan of everything. A customer's own list is
   * their own dozen bills or their own three meters, and the predicate this
   * replaces — a browser-side `includes` over rows already in hand — had no
   * minimum at all. Raising it to two would mean a customer typing `8` to find
   * meter `8841-C` silently gets their whole list back, which is a behaviour
   * this commit would be introducing rather than preserving.
   */
  minChars?: number;
}

/**
 * Fires the EFFECTIVE query — input under `minChars` counts as no query — and
 * only when it differs from the last fired value, so one settled keystroke
 * burst is one server request (`US-SHL-006` TC-3).
 */
export function createSearchDebouncer(
  fire: (q: string) => void,
  initialQuery = "",
  options: SearchDebounceOptions = {},
): SearchDebouncer {
  const minChars = options.minChars ?? SEARCH_MIN_CHARS;
  let lastFired = initialQuery.length >= minChars ? initialQuery : "";
  let timer: ReturnType<typeof setTimeout> | undefined;

  return {
    type: (raw: string) => {
      clearTimeout(timer);
      const effective = raw.length >= minChars ? raw : "";
      timer = setTimeout(() => {
        if (effective !== lastFired) {
          lastFired = effective;
          fire(effective);
        }
      }, SEARCH_DEBOUNCE_MS);
    },
    clear: () => {
      clearTimeout(timer);
      lastFired = "";
    },
  };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CWP-5747 — the portal pagination lane, 2026-09-19
// generated: 2026-09-19
// exceptions: none — this file declares no class and renders nothing (B14 r21)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
