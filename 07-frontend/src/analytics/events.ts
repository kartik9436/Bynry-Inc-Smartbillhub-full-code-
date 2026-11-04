// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 row 8 and the event names under it (PO 2026-10-04).
// Tests:   src/analytics/events.test.ts
// ───────────────────────────────────────────────────────
//
// THE TYPED EVENT CATALOGUE. Every event the browser may send is named here
// with the ONLY property keys it may carry. A key that is not listed is dropped
// before it reaches PostHog, and so is a string value that is not a CODE —
// because a name, an amount, an address or a search text is never a code, a
// mis-wired call site cannot leak one even by passing it under a listed key.
//
// Names are `object_action`, snake case, past tense (CR §2). The module adds
// `environment`, `app`, `app_version`, `tenant` and `language` itself; a
// call site never passes them.

/** A code: a screen id, a list name, an error code, a status word. */
const CODE = /^[A-Za-z0-9_.:-]{1,64}$/;

/** A value that LOOKS like a code but is a printed record reference (AC-2026-00012). */
const PRINTED_REFERENCE = /^[A-Z]{1,5}(?:-[A-Z0-9]{1,10}){1,4}$/;

/**
 * `screen` is a code that may LOOK like a printed reference: the product's own
 * screen ids are spelled `ACC-01`, `DSH-01`, `PAY-02.send-notice`, the same
 * shape as `AC-2026-00012`. Only the keys that carry a screen id take it, so a
 * reference passed under any other key is still dropped. (Found by the walk:
 * every staff screen with a hyphenated id was sent with its id stripped.)
 */
type Kind = "code" | "screen" | "count" | "flag";

/** A screen id: the product's own register spelling. */
const SCREEN = /^[A-Za-z0-9_.:-]{1,64}$/;

/** event → property → the kind of value it may hold. */
export const EVENT_CATALOGUE = {
  user_signed_in: { surface: "code" },
  user_sign_in_failed: { surface: "code", reason: "code" },
  user_signed_out: { reason: "code" },
  screen_viewed: { screen: "screen", screen_a1: "screen" },
  list_searched: { list: "code", has_search: "flag", result_count: "count" },
  list_filtered: { list: "code", filter: "code", result_count: "count" },
  report_downloaded: { report: "screen", format: "code" },
  work_order_status_changed: { from: "code", to: "code" },
  action_refused: { screen: "screen", code: "code", status: "count" },
} as const satisfies Record<string, Record<string, Kind>>;

export type EventName = keyof typeof EVENT_CATALOGUE;

type ValueOf<K extends Kind> = K extends "count" ? number : K extends "flag" ? boolean : string;

/** The properties a call site may pass for one event — all optional. */
export type EventProperties<E extends EventName> = {
  [P in keyof (typeof EVENT_CATALOGUE)[E]]?: (typeof EVENT_CATALOGUE)[E][P] extends Kind
    ? ValueOf<(typeof EVENT_CATALOGUE)[E][P]> | null
    : never;
};

function keep(kind: Kind, value: unknown): boolean {
  switch (kind) {
    case "count":
      return typeof value === "number" && Number.isFinite(value) && value >= 0;
    case "flag":
      return typeof value === "boolean";
    case "screen":
      return typeof value === "string" && SCREEN.test(value);
    case "code":
      return typeof value === "string" && CODE.test(value) && !PRINTED_REFERENCE.test(value);
  }
}

/** Keep only the allow-listed keys holding a value of the declared kind. */
export function cleanEventProperties<E extends EventName>(
  event: E,
  properties: EventProperties<E>,
): Record<string, string | number | boolean> {
  const allowed: Record<string, Kind> | undefined = (EVENT_CATALOGUE as Record<string, Record<string, Kind>>)[event];
  if (allowed === undefined) {
    throw new Error(`analytics: "${String(event)}" is not in the event catalogue (src/analytics/events.ts)`);
  }
  const cleaned: Record<string, string | number | boolean> = {};
  for (const [name, value] of Object.entries(properties as Record<string, unknown>)) {
    const kind = allowed[name];
    if (kind !== undefined && keep(kind, value)) {
      cleaned[name] = value as string | number | boolean;
    }
  }
  return cleaned;
}
