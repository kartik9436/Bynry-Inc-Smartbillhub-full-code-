// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — the six Counter screens. Blueprint §03
//           frames 3·1 (p051–p052) and 3·2 (p052–p053).
// Rules:    B14 rule 43 (a piece of UI is a component — and a cache key shared
//           by five callers is a piece) · `CR-136-BRC07` §3.2
// ───────────────────────────────────────────────────────
// The react-query keys the six Counter screens share.
//
// ⚠ **THEY LIVE HERE AND NOT IN `counterShared.tsx` FOR ONE REASON: THIS FILE
// IS `.ts` AND THAT ONE IS `.tsx`.** The four dialogs invalidate these keys and
// import nothing else from the screens; keeping the keys free of JSX means a
// dialog does not pull a table component into its module graph to learn the
// name of a cache entry.
//
// ⚠ **FIVE WRITERS INVALIDATE `countersQueryKey()` AND THAT IS THE POINT.**
// Start, Close, Force close and Declare each change a row on 3·1, and 3·2's
// own read changes with them. A key spelled out at each of those five call
// sites is five spellings free to drift, and a stale supervisor list is
// exactly the screen `CR-136-BRC07`'s done-when is about — *"a supervisor can
// see the three tills nobody counted"*.

/** Every counter list read, whatever its filters. The list state is appended
 *  by the caller so one invalidation clears every filtered view at once. */
export const countersQueryKey = () => ["payments", "counters"] as const;

/** One till — 3·2's read. Keyed by the CODE the address carries, never by an
 *  id (B14 rule 31, and see `api/counterEndpoints.ts`). */
export const counterQueryKey = (code: string) => ["payments", "counters", code] as const;

/** *Is MY counter open?* — `P2.7`'s page-head slot and `P2.9`'s record banner
 *  are two readers of one answer, and a stale one puts a clerk's money in the
 *  wrong till. Every act on a counter invalidates `countersQueryKey()`, which
 *  is this key's PREFIX, so opening or closing a till refreshes both at once. */
export const myOpenCounterQueryKey = () => ["payments", "counters", "mine", "open"] as const;

/** The payments a till has taken — 3·2's list underneath, filtered by batch. */
export const counterPaymentsQueryKey = (code: string) =>
  ["payments", "counters", code, "payments"] as const;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §4 row `P2.6` · blueprint p051–p059 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
