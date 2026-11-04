// ── Trace ──────────────────────────────────────────────
// Story:    CR-168-BRC10 round 2 (lane ORDERS-LIST) — P1.4, DEF-WRK-9570
// Rules:    WS-21 (the four windows the drawing offers) · images 02, 12, 13
// Tests:    src/features/work/cr168OrdersList.dom.test.tsx ·
//           src/features/work/OrderEditPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE DEFINITION OF A VISIT WINDOW, READ BY THE EDIT PAGE AND THE BULK
// DIALOGS.** Until CR-168 the edit page owned the two named windows and the bulk
// Reschedule dialog asked for *Window opens* and *Window closes* as free text,
// so `UU898` reached the server as a window (`DEF-WRK-9570`). Two screens that
// write the same two columns now take their moments from the same function.

/** *Any time* is the ABSENCE of a window; *Exact appointment* is a start and no end. */
export type WindowChoice = "any" | "morning" | "afternoon" | "exact";

/** The two named windows, in the utility's own time (the server stores the
 *  moment as given; the help line under the control says whose clock it is). */
export const NAMED_WINDOWS: Record<"morning" | "afternoon", [string, string]> = {
  morning: ["08:00", "12:00"],
  afternoon: ["12:00", "17:00"],
};

/** `YYYY-MM-DD` and nothing looser — a date box hands us exactly this. */
export function isDay(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/u.test(value);
}

/** The moments a day and a window choice write. `exact` needs `HH:MM`. */
export function windowMoments(
  day: string,
  choice: WindowChoice,
  exact = "",
): { window_start: string | null; window_end: string | null } {
  if (choice === "any") return { window_start: null, window_end: null };
  if (choice === "exact") {
    return { window_start: exact ? `${day}T${exact}:00` : null, window_end: null };
  }
  const [from, to] = NAMED_WINDOWS[choice];
  return { window_start: `${day}T${from}:00`, window_end: `${day}T${to}:00` };
}

/** Today in the browser's calendar, as a date box wants it. */
export function todayDay(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}
