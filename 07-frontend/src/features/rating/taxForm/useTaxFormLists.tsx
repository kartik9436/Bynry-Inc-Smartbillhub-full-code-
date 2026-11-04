// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — the reads the tax form renders from, lifted
//           out of `NewTaxWizard.tsx` so the New form and the three EDIT
//           variations (images 24–33) load the SAME lists the SAME way
//           (B14 rule 43: a piece of UI — here, its data — is reused by
//           import, never by a second copy).
// Contract: CR-165-BRC10 §9 — `GET /settings/services`, `GET /taxes/form-options`,
//           `GET /settings/authority-accounts`, `GET /ledger/accounts`,
//           `GET /taxes/matched-premises`
// ───────────────────────────────────────────────────────
//
// ⚠ **A ROUTE THAT IS NOT SERVED IS AN EMPTY LIST, NEVER A BROKEN STEP.**
// Every read is `retry: false`; the round-2 routes fall back to an empty list.
import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  TAX_CUSTOMER_CLASSES,
  TAX_DISCOUNT_TREATMENTS,
  TAX_ROUNDING_RULES,
  getLedgerAccounts,
  getMatchedPremises,
  getMyPermissions,
  getTaxJurisdictions,
  getTenantServices,
} from "@/api/endpoints";
import type { MyPermissions } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import {
  EMPTY_TAX_FORM_OPTIONS,
  authorityAccountLabel,
  getAuthorityAccounts,
  getTaxFormOptions,
} from "@/api/taxFormEndpoints";
import type { TaxFormOption, TaxFormOptions } from "@/api/taxFormEndpoints";
import type { TaxEditRow } from "@/api/taxEditEndpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BOUNDARY_EVERYWHERE, enabledServiceOptions, withListDefaults } from "./taxFormModel";
import type { TaxFormDraft } from "./taxFormModel";
import { ServiceMarker, localiseOptions } from "./taxFormShared";
import type { TaxFormLists, Translator } from "./taxFormShared";

/** Settings › Accounting › Tax filing accounts — where the utility's tax
 *  registration number with each authority is kept. The SUB-TAB address, so
 *  *Add one* opens that section directly (DEF-RAT-10027, PO 2026-10-09). */
export const AUTHORITY_ACCOUNTS_SETTINGS_ROUTE = "/settings/accounting/authorities";

/**
 * DEF-RAT-10028 — A PICKER MUST CONTAIN ITS SAVED VALUE.
 *
 * A select whose value is not among its options draws its PLACEHOLDER, so a
 * saved liability account the chart no longer offers (deactivated since the
 * tax was saved — `GET /ledger/accounts` is read with `f.status=active`) and a
 * retired registration number (the list offers active ones only) both read as
 * *"Choose an account"* over a value the tax still holds. Where the value is
 * missing, the tax's OWN label for it — which the tax read carries — is added
 * as one more option, so the box says what is saved. Never the id (B14 rule
 * 31): a value with no label is left to the placeholder.
 *
 * ⚠ The brief's suspected cause — *"getLedgerAccounts reads ONE page of 50"* —
 * was measured and is not what happens: `GET /ledger/accounts` is unpaginated
 * by design (`apps/ledger/chart_api.accounts`) and served all 128 accounts of
 * the seeded chart, the saved 128th showing correctly. The placeholder comes
 * from a saved value that is not ACTIVE, which this function covers whatever
 * the reason the value is missing.
 */
export function withSavedOption(
  options: TaxFormOption[],
  value: string,
  saved: TaxFormOption | null,
): TaxFormOption[] {
  if (value === "" || saved === null || saved.value !== value || saved.label === "") return options;
  return options.some((option) => option.value === value) ? options : [...options, saved];
}

/** The tax read's own labels for the values its pickers hold. */
function savedLabels(row: TaxEditRow | undefined): {
  liability: TaxFormOption | null;
  authorityAccount: TaxFormOption | null;
} {
  if (row === undefined) return { liability: null, authorityAccount: null };
  const code = (row.gl_account_code ?? "").trim();
  const name = (row.gl_account_name ?? "").trim();
  return {
    liability:
      row.liability_gl_account_id && (code !== "" || name !== "")
        ? { value: row.liability_gl_account_id, label: [code, name].filter((part) => part !== "").join(" · ") }
        : null,
    authorityAccount: row.authority_account
      ? { value: row.authority_account.id, label: row.authority_account.label }
      : null,
  };
}

/** Literal keys, so G18 can see every one of them is used. */
const ROUNDING_KEYS: Record<(typeof TAX_ROUNDING_RULES)[number], string> = {
  half_up: "rating.taxForm.rounding.half_up",
  half_even: "rating.taxForm.rounding.half_even",
  up: "rating.taxForm.rounding.up",
  down: "rating.taxForm.rounding.down",
  truncate: "rating.taxForm.rounding.truncate",
};
const DISCOUNT_KEYS: Record<(typeof TAX_DISCOUNT_TREATMENTS)[number], string> = {
  after: "rating.taxForm.discount.after",
  before: "rating.taxForm.discount.before",
};

function emptyOnFailure<T>(read: () => Promise<T>, empty: T): () => Promise<T> {
  return async () => {
    try {
      return await read();
    } catch {
      return empty;
    }
  };
}

export interface TaxFormData {
  /** The draft with the server's list defaults filled in (never over a choice). */
  current: TaxFormDraft;
  lists: TaxFormLists;
  options: TaxFormOptions;
  placeBoundaries: string[];
  permissions: UseQueryResult<MyPermissions | null>;
  translate: Translator;
}

export function useTaxFormLists(props: {
  draft: TaxFormDraft;
  client?: ApiClient;
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
  /** EDIT only — the tax as read, whose labels stand in for a saved value the
   *  lists no longer offer (DEF-RAT-10028). `undefined` on the New wizard.
   *  ⚠ REQUIRED-BUT-UNDEFINABLE RATHER THAN OPTIONAL (`DEF-GOV-10106`): this
   *  is a hook, so its callers pass an object literal (`savedRow: row`) and
   *  never a JSX attribute — G13 cannot see that caller and read the optional
   *  form as dead. Required, `tsc` makes every caller state it. */
  savedRow: TaxEditRow | undefined;
}): TaxFormData {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params) as string;
  const client = props.client ?? api;
  const regional = useRegional(props);
  const tenantPath = useTenantPath();

  const permissions = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const jurisdictionsQuery = useQuery({
    queryKey: queryKeys.taxJurisdictions,
    queryFn: () => getTaxJurisdictions(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const optionsQuery = useQuery({
    queryKey: ["taxes", "form-options"],
    queryFn: emptyOnFailure(() => getTaxFormOptions(client), EMPTY_TAX_FORM_OPTIONS),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const authorityAccountsQuery = useQuery({
    queryKey: ["settings", "authority-accounts"],
    queryFn: emptyOnFailure(() => getAuthorityAccounts(client), []),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const ledgerQuery = useQuery({
    queryKey: queryKeys.ledgerAccounts,
    queryFn: emptyOnFailure(() => getLedgerAccounts(client), []),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const options = optionsQuery.data ?? EMPTY_TAX_FORM_OPTIONS;
  const placeBoundaries = options.boundaries.filter((row) => row.needs_place).map((row) => row.value);
  const current = withListDefaults(props.draft, options);
  const scopeKind = current.boundary === "" || current.boundary === BOUNDARY_EVERYWHERE ? "" : current.boundary;
  const scopeValue = placeBoundaries.includes(current.boundary) ? current.place_name.trim() : "";

  const reachQuery = useQuery({
    queryKey: [
      "taxes",
      "matched-premises",
      scopeKind,
      scopeValue,
      [...current.customer_classes].sort().join(","),
      [...current.services].sort().join(","),
    ],
    queryFn: () =>
      getMatchedPremises(scopeKind, scopeValue, current.customer_classes, current.services, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const saved = savedLabels(props.savedRow);
  const authorities = (jurisdictionsQuery.data ?? []).map((row) => ({ value: row.id, label: row.name }));
  // DEF-RAT-10027 — only the numbers held with THIS tax's authority, plus the
  // ones typed before an authority could be picked (no link, so no way to know).
  const heldNumbers = (authorityAccountsQuery.data ?? [])
    .filter(
      (row) =>
        current.jurisdiction === "" || row.jurisdiction_id === null || row.jurisdiction_id === current.jurisdiction,
    )
    .map((row) => ({ value: row.id, label: authorityAccountLabel(row) }));
  // A saved due rule the option list has not delivered still reads in words —
  // never as its code: `localiseOptions` names it from the catalogue, and an
  // empty label is left to the placeholder by `withSavedOption`.
  const dueRules = localiseOptions("due", options.due_rules, translate);
  const savedDue = localiseOptions("due", [{ value: current.due_date_rule, label: "" }], translate)[0] ?? null;

  const lists: TaxFormLists = {
    authorities,
    boundaries: localiseOptions("boundary", options.boundaries, translate),
    placeBoundaries,
    services: enabledServiceOptions(servicesQuery.data).map((row) => ({
      ...row,
      marker: <ServiceMarker code={row.value} />,
    })),
    classes: TAX_CUSTOMER_CLASSES.map((code) => ({ value: code, label: translate(`rating.customerClass.${code}`) })),
    bases: localiseOptions("basis", options.bases, translate),
    rounding: TAX_ROUNDING_RULES.map((rule) => ({ value: rule, label: translate(ROUNDING_KEYS[rule]) })),
    discounts: TAX_DISCOUNT_TREATMENTS.map((value) => ({ value, label: translate(DISCOUNT_KEYS[value]) })),
    liabilityAccounts: withSavedOption(
      (ledgerQuery.data ?? []).map((row) => ({ value: row.id, label: `${row.code} · ${row.name}` })),
      current.liability_gl_account_id,
      saved.liability,
    ),
    filingFrequencies: localiseOptions("filing", options.filing_frequencies, translate),
    dueRules: withSavedOption(dueRules, current.due_date_rule, savedDue),
    authorityAccounts: withSavedOption(heldNumbers, current.authority_account_id, saved.authorityAccount),
    authorityAccountsHeld: heldNumbers.length,
    authorityName: authorities.find((row) => row.value === current.jurisdiction)?.label ?? "",
    reach: reachQuery.data ?? null,
    dateFormat: regional.dateFormat,
    timeZone: regional.timeZone,
    authorityAccountsHref: tenantPath(AUTHORITY_ACCOUNTS_SETTINGS_ROUTE),
  };

  return { current, lists, options, placeBoundaries, permissions, translate };
}

/**
 * The frame draws rail, content and footer as one column; this lays its parts
 * onto two — the rail across both, the step and its footer on the left, the
 * summary on the right — by the `data-wizard` hooks it already renders (the
 * one-time bill's device, `OneTimeBillPage.tsx`). The frame's own refusal line
 * is hidden because this form says *Fix N things first.* beside Continue
 * instead (images 08, 11, 14, 29, 32), and two sentences for one refusal is
 * one too many (B14 rule 33).
 */
export const TAX_FORM_LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 items-start " +
  "[&_[data-wizard=frame]]:contents " +
  "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
  "[&_[data-wizard=rail]]:mb-5 [&_[data-wizard=rail]]:border [&_[data-wizard=rail]]:bg-surface " +
  "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-2 " +
  "[&_[data-wizard=content]]:mb-0 " +
  "[&_[data-wizard=actions]]:col-start-1 [&_[data-wizard=actions]]:row-start-3 " +
  "[&_[data-wizard=actions]]:mt-5 [&_[data-wizard=actions]]:border-t " +
  "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
  "[&_[data-wizard=blocked]]:hidden";
