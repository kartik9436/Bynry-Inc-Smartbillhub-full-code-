// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-3964 — the tenant's date format and time zone never reached
//          a screen, because nothing published them.
// Rules:   IS-8 · BR-SHL-023 · hard-won law 3 (defaults fail closed)
// ───────────────────────────────────────────────────────
// WHAT A TENANT'S REGIONAL SETTINGS LOOK LIKE, FOR TESTS THAT MOUNT THE REAL
// SHELL.
//
// `ShellWithSession` renders no routed screen until it knows the tenant's date
// format and time zone (decision D3), so a test that mounts `APP_ROUTES` now
// has to say which tenant it is testing — otherwise it gets the holding state
// and its own assertions fail on a skeleton. That is the correct posture and
// it is the whole point of the defect: nothing renders a date nobody chose.
//
// This exists so those tests state it in ONE line instead of restating sixteen
// fields, and so the values are named in one place rather than guessed at in
// each. It is a fixture — it is imported by test files only and never reaches
// the bundle — and it is deliberately NOT a default inside the shell, which is
// exactly the mistake being fixed.
import type { RegionalSettings } from "@/api/endpoints";

/**
 * What `provision_tenant` writes for a new United States tenant in Texas —
 * `apps/tenancy/services.provision_tenant`, which seeds `DATE_FORMATS[0]` and
 * derives the zone from the state.
 */
export const SEEDED_REGIONAL: RegionalSettings = {
  country: "United States",
  state: "TX",
  timezone: "America/Chicago",
  language: "en-US",
  first_day_of_week: "sunday",
  currency: "USD",
  number_format: "1,234.56",
  date_format: "MM/DD/YYYY",
  time_format: "12-hour",
  fy_start_month: 1,
  fy_start_day: 1,
  accounting_method: null,
  close_cadence: "monthly",
  close_day: "last day",
  lock_closed_periods: false,
  current_period: null,
};

/** The same, with whichever fields a case wants to vary. */
export function regionalSaying(over: Partial<RegionalSettings> = {}): RegionalSettings {
  return { ...SEEDED_REGIONAL, ...over };
}
