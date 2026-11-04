// ── Trace ──────────────────────────────────────────────
// Defect: DEF-SHL-4272 — the app shell's boot read moved from two Admin/
//         Executive settings endpoints to one `GET /shell/display` that any
//         signed-in role may make.
// Rules:  BR-SHL-252 (formatting and branding are not settings administration)
// Tests:  every suite that mounts a routed screen through ShellWithSession
// ───────────────────────────────────────────────────────
import type { ShellDisplay } from "@/api/endpoints";

/**
 * The smallest `GET /shell/display` payload that lets `ShellWithSession` hand
 * control to its Outlet — for suites that mount a routed screen and are about
 * something else entirely.
 *
 * ⚠ **THIS EXISTS BECAUSE NINE FIXTURES EACH HELD THEIR OWN COPY OF "WHAT THE
 * SHELL NEEDS TO BOOT", AND ON 2026-09-06 ALL NINE WENT RED AT ONCE.** The
 * shell WAITS until it knows the tenant's timezone and date format
 * (`DEF-SHL-3964` decision D3 — a plausible wrong date is worse than a wait),
 * so a fixture that does not seed them gets a 389-character loading skeleton
 * for **every address in the product**. That is not a visible failure: it is a
 * suite quietly measuring nothing, which is exactly what
 * `sidebarReachability.test.tsx` did from 2026-08-16 until it was repaired.
 *
 * So the knowledge lives in ONE place now. The next time the shell's gate
 * moves, this file changes and the nine suites do not.
 *
 * `regional` takes whatever the suite already had — these fixtures typically
 * hold a full `RegionalSettings`, and the extra fields are harmless. What the
 * shell actually reads is `timezone` and `date_format`; both must be present
 * and the format must be one of the seven `RegionalDateFormat`s, or the shell
 * treats the pair as NOT KNOWN and holds.
 */
export function shellBootSeed(
  regional: Partial<ShellDisplay["regional"]>,
  period: ShellDisplay["period"] = null,
): ShellDisplay {
  // Picked FIELD BY FIELD rather than spread. Callers hand this a full
  // `RegionalSettings`, and a spread would carry `accounting_method`,
  // `close_cadence`, `close_day` and `lock_closed_periods` into a payload the
  // real endpoint deliberately does not serve — so a screen could read finance
  // policy in a test and 404 on it in the product.
  //
  // ⚠ **`period` DEFAULTS TO `null`, WHICH IS "THIS TENANT HAS SET NO FISCAL
  // YEAR START" AND NOT "DO NOT CARE" (`DEF-SHL-4283`, 2026-09-06).** Seven
  // Finance-frame screens and the by-premises report read the period from this
  // payload now, so a suite that mounts one of them and leaves this at the
  // default is asserting against the *no period configured* branch. That is a
  // real state and testing it is fine — but pass a card if the screen under
  // test is meant to have one, or the suite measures the empty branch while
  // reporting the screen's name. A spread of `RegionalSettings.current_period`
  // is NOT the same shape: this one carries no `close_by`, because that field
  // is `close_day` in another shape and stays on `GET /settings/regional`.
  return {
    period,
    regional: {
      country: regional.country ?? null,
      timezone: regional.timezone ?? null,
      language: regional.language ?? null,
      first_day_of_week: regional.first_day_of_week ?? null,
      currency: regional.currency ?? null,
      number_format: regional.number_format ?? null,
      date_format: regional.date_format ?? null,
      time_format: regional.time_format ?? null,
    },
    company: {
      legal_name: null,
      dba_name: null,
      has_logo: false,
      logo_ref: null,
      mark: { letters: "", background_hex: null, ink_hex: null, contrast_ratio: null },
      brand_primary_hex: null,
    },
  };
}
