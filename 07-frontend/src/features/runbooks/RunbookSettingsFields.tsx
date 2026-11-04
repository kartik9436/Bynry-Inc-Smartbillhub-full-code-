// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 (EP-RBS-01) — `OQ-WRK-12793` → A
//          (PO 2026-10-13, verbatim *"1a, 2A 3A"*; decision log *"THREE PO
//          RULINGS ON THE LEFT-OVER SCREEN PIECES"*).
// Screens: RBS-004.3 (the Scope tab) · RBS-004's Change-scope dialog ·
//          RBS-004.run (the Check wizard's scope step).
// Rules:   `RBR-03` (policy is READ, never duplicated) · B14 rules 1, 21, 31,
//          33, 43 · hard-won law 2 (built is not wired) · law 3 (defaults
//          fail closed).
// Defects: DEF-WRK-10122 (the field was built and never mounted; setup drew a
//          `ref:setting` input greyed out over the runbook's own DEFAULT).
// Tests:   RunbookSettingsFields.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// **A RUNBOOK INPUT THAT LIVES IN SETTINGS IS SHOWN READ-ONLY, WITH A LINK TO
// SETTINGS — AND THE VALUE IS THE ONE SETTINGS HOLDS.** The PO's worked case:
// *"Days to pay: 20, from Settings"*.
//
// ⚠ **WHAT THE SCREEN DREW BEFORE WAS NOT THE SETTING.** `selectors.
// _parameter_settings` serves `value` as *the tenant's answer, or the declared
// default*, and a tenant cannot answer a `ref:setting` input on the runbook at
// all — so for every one of them `value` IS the default typed in the runbook's
// Python module. The Scope tab printed it and the scope dialog printed it in a
// greyed box, and both read as *what Settings says* when it was nothing of the
// kind. This file never reads `parameter.value` for a `ref:setting` input.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THE VALUE COMES FROM — AN EXPLICIT TABLE, AND WHY IT IS SHORT
// ══════════════════════════════════════════════════════════════════════════
// `setting_key` is a dotted name the runbook module chose
// (`billing.eligibility_months`), and no server route resolves it. What DOES
// exist is the Settings families every engine already reads:
// `GET /settings/{slug}` (`api/endpoints.ts::getRulePage`), the same read the
// Settings screen itself makes. So `SETTINGS_SOURCES` names, for each key that
// corresponds to a REAL Settings field, which family and which field — and a
// key that is NOT in the table is drawn *Not set in Settings*, which is true:
// Settings holds no such value today. **Nothing is guessed and nothing falls
// back to the runbook's default.** Measured 2026-10-13: 23 `ref:setting`
// inputs across the shipped runbooks name 22 distinct keys; FIVE were mapped
// that day and the other 17 were counted in `DEF-WRK-10122`.
//
// ⚠ **RE-MEASURED 2026-10-14 (`DEF-WRK-10122`, decision log *"THE 77 OPEN
// TASKS"* item 11): SEVEN ARE REAL SETTINGS FIELDS, NOT FIVE.** Two of the
// seventeen were NAME mismatches — the runbook module chose a dotted name and
// Settings holds the same fact under its own:
//   * `payments.match_amount_tolerance` (Bank reconciliation's *Auto-match
//     tolerance*, BR-PAY-019) IS `finance-controls.bank_match_amount_tolerance`,
//     edited on Settings → Accounting;
//   * `notifications.quiet_hours` (Leak alert's *Quiet hours*, BR-NOT-009) IS
//     the notification settings' `quiet_hours_start`–`quiet_hours_end`
//     (`GET /notification-settings`), edited on Settings → Notifications.
// **The other FIFTEEN have no Settings field at all** — searched in every
// Settings family (`apps/tenancy/settings_families.py`) and in the
// notification settings, and named nowhere outside `apps/runbooks/`. They stay
// *Not set in Settings*, which is true, and nothing is invented for them:
//   `assets.change_out_age_years` · `billing.rate_preview_compare_to` ·
//   `customers.orphan_definition` · `customers.vacant_definition` ·
//   `integrations.gis.never_touch` · `metering.read_validation` ·
//   `metering.read_validation.est_max_consecutive` (a per-SERVICE field — the
//   note below) · `metering.read_validation.hand_to_billing` ·
//   `metering.read_validation.rollover` · `money.rounding` ·
//   `notifications.channel_fallback` · `notifications.suppression_re_enable` ·
//   `payments.collections_exclusions` · `payments.collections_last_tier`
//   (its own runbook says *"NO SETTINGS ROW HOLDS IT TODAY"*) ·
//   `runbooks.gate_mode`.
//
// ⚠ **`read-validation` IS NOT IN THE TABLE ON PURPOSE.** That family is
// per SERVICE since CR-038 A1 — one floor per utility service, in its own unit
// — so *"Estimate gaps up to"* has no single value to print. Picking one
// service's answer would be the plausible wrong answer law 3 exists to stop.
import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import { getNotificationSettings, getRulePage } from "@/api/endpoints";
import type { RuleDocument, RulePageSlug } from "@/api/endpoints";
import { formatMoney, formatMoneyInput } from "@/components/MoneyCell";
import { formatPercent } from "@/components/PercentCell";
import { useTenantCurrency } from "@/components/TenantRegional";
import { SettingsOwnedField, SettingsOwnedProvider } from "@/components/SettingsOwnedField";
import type { SettingsOwnedValues } from "@/components/SettingsOwnedField";
import { useTenantPath } from "@/routing/tenantPath";

import { settingsOwnedParameters } from "./setupScope";
import type { SettingsFieldRow } from "./setupScope";
import type { WireParameterSetting } from "./setupWire";

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** The notification settings (`GET /notification-settings`) — the one source
 *  here that is not a rule page. Named as a slug so one table carries both. */
const NOTIFICATION_SETTINGS = "notification-settings";
type SettingsReadSlug = RulePageSlug | typeof NOTIFICATION_SETTINGS;

/** One Settings field a runbook key reads, and where a clerk edits it. */
interface SettingsSource {
  slug: SettingsReadSlug;
  /** The field — or, for a `window`, the START field (`end` names the other). */
  field: string;
  end?: string;
  format: "months" | "hours" | "percent" | "choice" | "money" | "window";
  /** The Settings address, tenant segment excluded. */
  to: string;
}

const BUDGET_BILLING = "/settings/reference-data/reference-data?list=budget_billing";
const BILLING_DEFAULTS = "/settings/reference-data/reference-data?list=billing_defaults";

/**
 * Runbook `setting_key` → the REAL Settings field it reads.
 *
 * Every row is a field `apps/tenancy/settings_families.py` declares and the
 * Settings screen edits. ⚠ `collections.final_notice_hours` is edited on
 * Settings → Notifications since CR-009 (the ladder's timings moved there; the
 * STORE did not), so its link goes there and its read stays `collections`.
 */
export const SETTINGS_SOURCES: Readonly<Record<string, SettingsSource>> = {
  "billing.eligibility_months": {
    slug: "budget-billing",
    field: "eligibility_months",
    format: "months",
    to: BUDGET_BILLING,
  },
  "billing.relevel_drift_pct": {
    slug: "budget-billing",
    field: "relevel_drift_pct",
    format: "percent",
    to: BUDGET_BILLING,
  },
  "billing.relevel_cadence_months": {
    slug: "budget-billing",
    field: "relevel_cadence_months",
    format: "months",
    to: BUDGET_BILLING,
  },
  "collections.final_notice_hours": {
    slug: "collections",
    field: "final_notice_hours",
    format: "hours",
    to: "/settings/reference-data/notifications", // moved under Configure 2026-10-22
  },
  "payments.allocation_order": {
    slug: "billing-defaults",
    field: "allocation_order",
    format: "choice",
    to: BILLING_DEFAULTS,
  },
  // `DEF-WRK-10122` (2026-10-14) — two name mismatches, mapped to the field
  // Settings really holds (see the table's note above).
  "payments.match_amount_tolerance": {
    slug: "finance-controls",
    field: "bank_match_amount_tolerance",
    format: "money",
    to: "/settings/accounting",
  },
  "notifications.quiet_hours": {
    slug: NOTIFICATION_SETTINGS,
    field: "quiet_hours_start",
    end: "quiet_hours_end",
    format: "window",
    to: "/settings/reference-data/notifications", // moved under Configure 2026-10-22
  },
};

/** Where *Open settings →* goes for a key Settings does not hold: Settings'
 *  own front page, never a dead link and never a guess at a sub-page. */
const SETTINGS_HOME = "/settings";

/** One stored Settings value as a reader reads it. `null` = UNSET (never zero). */
function shown(
  source: SettingsSource,
  document: Record<string, unknown> | undefined,
  t: Translate,
  currency: string | null,
): string | null {
  const raw = document?.[source.field];
  if (raw === null || raw === undefined || raw === "") return null;
  const value = String(raw);
  switch (source.format) {
    case "money":
      // Hard rule 2: an amount DISPLAYS 2, as a decimal string end to end. The
      // currency rides with it (BR-TEN-042) and is never assumed: without one
      // the figure prints bare rather than under a symbol nobody published.
      return currency === null ? formatMoneyInput(value) : formatMoney(value, currency);
    case "window": {
      // BR-NOT-009 — a wall-clock window in the tenant's time, start to end.
      const end = source.end === undefined ? null : document?.[source.end];
      if (end === null || end === undefined || end === "") return null;
      return `${value}–${String(end)}`;
    }
    case "months":
      return t("runbooks.setup.settings.months", { n: value });
    case "hours":
      return t("runbooks.setup.settings.hours", { n: value });
    case "percent":
      // Hard rule 2: a percentage DISPLAYS 2. The stored form is points.
      return formatPercent(value, "points");
    case "choice":
      // The Settings screen's own words for the choice — one catalogue, so the
      // two screens cannot name one setting two ways.
      return t(`settings.rules.choice.${source.field}.${value}`, { defaultValue: value });
  }
}

/** What the read says: the values map, or `null` while it is not known. */
export interface RunbookSettingsRead {
  values: SettingsOwnedValues | null;
  failed: boolean;
}

const ReadFailedContext = createContext(false);

/**
 * Reads the Settings families this runbook's `ref:setting` inputs need — each
 * family ONCE, however many inputs share it — and publishes the answer through
 * `SettingsOwnedProvider`. A runbook with no such input publishes an empty,
 * LOADED map and makes no request.
 *
 * ⚠ **A FAILED READ IS STATED, NOT RETRIED SILENTLY AND NOT DEFAULTED.** Any
 * family failing withholds the whole map (`null`) and flags `failed`, so every
 * field says *Could not load* rather than half the fields showing values and
 * half showing *Not set in Settings*, which would be a false statement about
 * Settings caused by a network error.
 */
export function RunbookSettingsProvider(props: {
  parameters: readonly WireParameterSetting[];
  client?: ApiClient;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const owned = settingsOwnedParameters(props.parameters);
  const currency = useTenantCurrency();
  const slugs = Array.from(
    new Set(
      owned
        .map((one) => SETTINGS_SOURCES[one.setting_key ?? ""]?.slug)
        .filter((slug): slug is SettingsReadSlug => slug !== undefined),
    ),
  ).sort();
  const reads = useQueries({
    queries: slugs.map((slug) => ({
      // This screen's own prefix, deliberately not `api/queryClient.ts`'s —
      // the reason `RunbookSetupPage` gives for its own keys.
      queryKey: ["runbooks", "settings-owned", slug],
      queryFn: (): Promise<Record<string, unknown>> =>
        slug === NOTIFICATION_SETTINGS
          ? (getNotificationSettings(client) as unknown as Promise<Record<string, unknown>>)
          : getRulePage(slug, client),
    })),
  });

  const failed = reads.some((read) => read.isError);
  const pending = reads.some((read) => read.isPending);
  let values: SettingsOwnedValues | null = null;
  if (!failed && !pending) {
    const documents: Record<string, Record<string, unknown> | RuleDocument | undefined> = {};
    slugs.forEach((slug, index) => {
      documents[slug] = reads[index]?.data;
    });
    const map: Record<string, ReactNode> = {};
    for (const one of owned) {
      const key = one.setting_key ?? "";
      const source = SETTINGS_SOURCES[key];
      if (source === undefined) continue; // Settings holds no such field: *Not set*.
      const text = shown(source, documents[source.slug], t, currency);
      if (text !== null) map[key] = text;
    }
    values = map;
  }

  return (
    <ReadFailedContext.Provider value={failed}>
      <SettingsOwnedProvider values={values}>{props.children}</SettingsOwnedProvider>
    </ReadFailedContext.Provider>
  );
}

/**
 * The Settings-owned inputs, each read-only with its link (`SettingsOwnedField`).
 * Draws nothing at all when there are none — an empty frame here would be a
 * heading over nothing.
 */
export function RunbookSettingsFields(props: { fields: readonly SettingsFieldRow[] }) {
  const { t } = useTranslation();
  const path = useTenantPath();
  const failed = useContext(ReadFailedContext);
  if (props.fields.length === 0) return null;
  return (
    <div className="flex flex-col gap-2" data-runbook-settings="">
      {props.fields.map((field) => (
        <SettingsOwnedField
          key={field.name}
          setting={field.setting}
          label={field.label}
          to={path(SETTINGS_SOURCES[field.setting]?.to ?? SETTINGS_HOME)}
          ownedBy={t("runbooks.setup.settings.from")}
          absent={{
            notLoaded: failed
              ? t("runbooks.setup.settings.failed")
              : t("runbooks.setup.settings.loading"),
            notSet: t("runbooks.setup.settings.notSet"),
          }}
          openLabel={t("runbooks.setup.steps.openSettings")}
        />
      ))}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: OQ-WRK-12793 → A (PO 2026-10-13) · DEF-WRK-10122 · 09-component-inventory.md Part 5 §5
// generated: 2026-10-13 by the runbook-wizard + settings-field lane
// checklist: A✔ B=n/a C✔ D✔(GET /settings/{budget-billing,collections,billing-defaults,finance-controls} · GET /notification-settings) E✔ F✔ G✔ H=n/a
// gates: vitest RunbookSettingsFields.dom.test.tsx · G40 · G13 · G31 · tsc
// amended: 2026-10-14 (DEF-WRK-10122) — two name mismatches mapped (bank match
//   tolerance, quiet hours); the fifteen keys with no Settings field listed by name
// exceptions: a key with no row in SETTINGS_SOURCES reads "Not set in Settings" — Settings holds no such field (the fifteen are named in the table's note); read-validation is per service and is not mapped
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
