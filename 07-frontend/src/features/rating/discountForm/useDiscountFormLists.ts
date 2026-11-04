// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — the reads the discount form renders
//           from, lifted out of `NewDiscountWizard.tsx` so the New form and the
//           three EDIT variations (images 27–36) load the SAME lists the SAME
//           way (B14 rule 43: a piece of UI — here, its data — is reused by
//           import, never by a second copy). The tax form's
//           `useTaxFormLists.tsx` is the precedent (CR-165 task 7).
// Contract: CR-166-BRC10 §9 — `GET /discounts/form-options`; plus
//           `GET /settings/services`, `GET /charges`, `GET /shell/display`
// ───────────────────────────────────────────────────────
//
// ⚠ **A ROUTE THAT IS NOT SERVED IS AN EMPTY LIST, NEVER A BROKEN STEP.**
// Every read is `retry: false`; `form-options` and the charge codes fall back
// to an empty list, so the form renders with an empty dropdown either way.
import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { EMPTY_DISCOUNT_FORM_OPTIONS, getDiscountFormOptions } from "@/api/discountFormEndpoints";
import type { DiscountFormOptions } from "@/api/discountFormEndpoints";
import { getCharges, getMyPermissions, getShellDisplay, getTenantServices } from "@/api/endpoints";
import type { ChargeRow, MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";

import { SCOPE_ONE_SERVICE, withListDefaults } from "./discountFormModel";
import type { DiscountFormDraft } from "./discountFormModel";
import { localiseOptions } from "./discountFormShared";
import type { DiscountFormLists, Translator } from "./discountFormShared";

function emptyOnFailure<T>(read: () => Promise<T>, empty: T): () => Promise<T> {
  return async () => {
    try {
      return await read();
    } catch {
      return empty;
    }
  };
}

const CHARGES_PER = 200;

/** Every charge code (NFR-3: follow the count, never stop at page one). */
async function allChargeCodes(client: ApiClient): Promise<ChargeRow[]> {
  const rows: ChargeRow[] = [];
  for (let page = 1; ; page += 1) {
    const answer = await getCharges({ page, per: CHARGES_PER }, client);
    rows.push(...answer.results);
    if (answer.results.length === 0 || rows.length >= answer.count) return rows;
  }
}

function enabledServices(rows: readonly TenantServiceRow[] | undefined): TenantServiceRow[] {
  return (rows ?? []).filter((row) => row.enabled);
}

export interface DiscountFormData {
  /** The draft with the server's list defaults filled in (never over a choice). */
  current: DiscountFormDraft;
  lists: DiscountFormLists;
  options: DiscountFormOptions;
  permissions: UseQueryResult<MyPermissions | null>;
  translate: Translator;
}

export function useDiscountFormLists(props: {
  draft: DiscountFormDraft;
  client?: ApiClient;
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}): DiscountFormData {
  const { t, i18n } = useTranslation();
  const translate: Translator = (key, params) => t(key, params) as string;
  const client = props.client ?? api;
  const regional = useRegional(props);

  const permissions = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const optionsQuery = useQuery({
    queryKey: ["discounts", "form-options"],
    queryFn: emptyOnFailure(() => getDiscountFormOptions(client), EMPTY_DISCOUNT_FORM_OPTIONS),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const chargesQuery = useQuery({
    queryKey: ["discounts", "form", "charge-codes"],
    queryFn: emptyOnFailure(() => allChargeCodes(client), []),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const shellQuery = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const options = optionsQuery.data ?? EMPTY_DISCOUNT_FORM_OPTIONS;
  const current = withListDefaults(props.draft, options);
  const services = enabledServices(servicesQuery.data);
  const chosenService = services.find((row) => row.service === current.applies_to_service);

  const lists: DiscountFormLists = {
    programOwners: options.program_owners,
    exclusivityGroups: options.exclusivity_groups,
    eligibility: options.eligibility,
    enrollmentModes: localiseOptions("enrollment", options.enrollment_modes, translate),
    verification: localiseOptions("verification", options.verification, translate),
    lapse: localiseOptions("lapse", options.lapse, translate),
    budgetPeriods: localiseOptions("period", options.budget_periods, translate),
    budgetOut: localiseOptions("out", options.budget_out, translate),
    types: localiseOptions("type", options.types, translate),
    appliesTo: localiseOptions("scope", options.applies_to, translate),
    services: services.map((row) => ({ value: row.service, label: row.name })),
    chargeCodes: (chargesQuery.data ?? []).map((row) => ({ value: row.code, label: `${row.code} · ${row.name}` })),
    currency: shellQuery.data?.regional.currency ?? null,
    allowanceUnit:
      current.applies_to === SCOPE_ONE_SERVICE && chosenService !== undefined
        ? (chosenService.billed_uom ?? chosenService.primary_uom ?? null)
        : null,
    dateFormat: regional.dateFormat,
    timeZone: regional.timeZone,
    language: i18n.language,
  };

  return { current, lists, options, permissions, translate };
}
