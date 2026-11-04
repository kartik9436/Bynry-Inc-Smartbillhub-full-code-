// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 — the regional formatting service)
//           Screens: every screen that renders a date or a timestamp (83 of them)
// Rules:    BR-SHL-023 (tenant TZ + regional format, ONE formatting path) ·
//           IS-8 (Settings → Company → Regional & Formats feeds every date) ·
//           CLAUDE.md hard rule 3 (an explicit unit, never an assumed one) ·
//           hard-won law 3 (defaults fail closed — the unsafe option is the
//           one you type)
// Defect:   DEF-SHL-3964 (2026-09-05, the PO on the running product:
//           *"date and time format is set in the settings ... but date shown
//           everywhere in the product does not change with that format change.
//           If I change the language it changes across entire app, date does
//           not change."*)
// ───────────────────────────────────────────────────────
// THE TENANT'S DATE FORMAT AND TIME ZONE, PUBLISHED ONCE FOR THE WHOLE APP.
//
// This file exists because the product had no such place. `IS-8` says every
// date renders in the tenant's own format and every instant in the tenant's own
// zone; the way that was carried was an OPTIONAL prop, `RegionalProps`, threaded
// by hand through 160 call sites in 63 files — and the ROOT never set it. So
// `regionalOf` (as it was then called) fell through to `SEED_DATE_FORMAT`
// ("MM/DD/YYYY") and
// `SEED_TIME_ZONE` ("UTC") on every screen in the product, forever, with no
// crash, no blank and no raw key to notice. A Texas utility saved
// `America/Chicago` on the Settings page and read every timestamp five or six
// hours out; a payment taken at 7pm local showed as the next day.
//
// ⚠ WHY A CONTEXT AND NOT ANOTHER PROP. The setting beside it — LANGUAGE —
// worked perfectly the whole time, and the reason is instructive: the shell
// applies language to i18next GLOBALLY, so it needs no prop and cannot be
// dropped by an intermediate component that forgot to forward it. The two
// settings sit side by side on one Settings page. One of them was published and
// one of them was prop-drilled, and only the prop-drilled one was broken. This
// is the publishing half for the other one.
//
// ⚠ WHY THE VALUE IS `null` UNTIL IT IS KNOWN, AND WHY THERE IS NO DEFAULT.
// A default here would be a plausible wrong answer — which is the defect, not
// the cure. `createContext<TenantRegional | null>(null)` means a consumer can
// tell "not yet" from "the tenant says DD/MM/YYYY", and `ShellWithSession`
// renders no routed screen at all until it is the second one (decision D3 in
// this lane's record). Nothing in this file invents a format.
import { createContext, useContext, type ReactNode } from "react";

import type { RegionalDateFormat } from "@/components/DateCell";

/** What every date on every screen is rendered against (IS-8, BR-SHL-023). */
export interface TenantRegional {
  /** IANA name from `tenant_settings.timezone` — e.g. `America/Chicago`. */
  timeZone: string;
  /** One of the seven `RegionalDateFormat`s from `tenant_settings.date_format`. */
  dateFormat: RegionalDateFormat;
  /**
   * `DEF-CUS-5114` — the tenant's `CHAR(3)` from `tenant_settings.currency`, as
   * `GET /shell/display` serves it; `null`/absent when nothing published one.
   *
   * `BR-TEN-042`: one tenant, one currency. Every money screen that has an
   * account row reads the code off the row; this is for the screens that have
   * NO account yet — New account, a move-in into a vacant unit — which until
   * 2026-10-04 could only say *"Currency not known here"*. Read it through
   * `useTenantCurrency()`, never by re-reading `/shell/display` in a screen.
   *
   * OPTIONAL on purpose: an absent value means "not published", and the
   * consumer renders its stated absence — never a defaulted `USD` (hard rule 2,
   * `DEF-1121`). Nothing in this file invents a currency either.
   */
  currency?: string | null;
}

/** `null` = the tenant's settings have not been read back yet. Never a guess. */
const TenantRegionalContext = createContext<TenantRegional | null>(null);

/**
 * Publishes the tenant's regional settings to everything below.
 *
 * There is exactly ONE caller — `ShellWithSession` — and that is deliberate:
 * the shell is the single place the whole authenticated product passes through,
 * and it is where `i18n.changeLanguage` already applies the sibling setting.
 */
export function TenantRegionalProvider(props: { value: TenantRegional; children: ReactNode }) {
  return (
    <TenantRegionalContext.Provider value={props.value}>
      {props.children}
    </TenantRegionalContext.Provider>
  );
}

/**
 * The published settings, or `null` when nothing has published them.
 *
 * Screens do not call this — they call `useRegional(props)` in
 * `features/metering/meteringShared.tsx`, which prefers an explicitly supplied
 * prop and falls back to this. This is the raw read, for the shell's own gate
 * and for tests that need to assert the "not yet" state.
 */
export function useTenantRegional(): TenantRegional | null {
  return useContext(TenantRegionalContext);
}

/**
 * The tenant's currency, or `null` when nothing has published one
 * (`DEF-CUS-5114`, `BR-TEN-042`) — the ONE front-end reader of it.
 *
 * Use it where a screen shows money and has no account in scope to read the
 * code off. Where an account IS in scope, prefer the account's own code — it
 * is the same code under `BR-TEN-042`, and the row is what the figure came
 * from. An empty string is treated as not published.
 */
export function useTenantCurrency(): string | null {
  const currency = useContext(TenantRegionalContext)?.currency;
  return currency ? currency : null;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-3964 (lane REGION) — the wire the settings screen never had
// generated: 2026-09-05 by lane REGION, from the PO's report on the running product
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: none — this file renders no markup and adds no stylesheet class
//         (B14 rule 21 is therefore not engaged; see route-b-migrated.txt)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
