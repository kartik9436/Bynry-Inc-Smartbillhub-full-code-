// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — the reads the New plan form renders
//           from, in their own hook so round 3's Edit choices load the SAME
//           lists the SAME way (the discount and tax forms' precedent).
// Contract: CR-167-BRC10 §7.3 — `GET /plans/form-options`; plus
//           `GET /shell/display` for the utility's currency when the options
//           do not carry it yet.
// ───────────────────────────────────────────────────────
//
// ⚠ **A ROUTE THAT IS NOT SERVED IS AN EMPTY LIST, NEVER A BROKEN STEP.**
// `form-options` is new in round 2; it is read with `retry: false` and falls
// back to empty lists, so the form renders with empty dropdowns either way.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getMyPermissions, getShellDisplay } from "@/api/endpoints";
import type { MyPermissions } from "@/api/endpoints";
import { EMPTY_PLAN_FORM_OPTIONS, getPlanFormOptions } from "@/api/planFormEndpoints";
import type { PlanFormOptions, PlanNoteAttribute } from "@/api/planFormEndpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DEFINITION_ROUTES } from "../definitionDetail";
import { SERVICES_SETTINGS_ROUTE } from "../ratingShared";
import { NOTE_ATTRIBUTE_CLASS, NOTE_ATTRIBUTE_SERVICE, withOptionDefaults } from "./planFormModel";
import type { PlanFormDraft } from "./planFormModel";
import type { PlanFormLists, Translator } from "./planFormShared";

export const PLAN_FORM_OPTIONS_KEY = ["plans", "form-options"] as const;

export interface PlanFormData {
  current: PlanFormDraft;
  lists: PlanFormLists;
  options: PlanFormOptions;
  permissions: UseQueryResult<MyPermissions | null>;
  translate: Translator;
}

/** What a note may be about: a customer class or a service, each with its
 *  served list — never a list typed out here (hard-won law 2). */
export function noteAttributes(options: PlanFormOptions, t: Translator): PlanNoteAttribute[] {
  const rows: PlanNoteAttribute[] = [];
  if (options.customer_classes.length > 0) {
    rows.push({ key: NOTE_ATTRIBUTE_CLASS, label: t("rating.plan.customerClassLabel"), values: options.customer_classes });
  }
  if (options.services.length > 0) {
    rows.push({
      key: NOTE_ATTRIBUTE_SERVICE,
      label: t("rating.filter.service"),
      values: options.services.map((row) => ({ value: row.value, label: row.label })),
    });
  }
  return rows;
}

/** What `?classes=` names: the ticked classes in the served order, or — for
 *  *Every customer class* (`[]`, ruling 4) — every class the server serves. */
export function classesAsked(selected: readonly string[], served: readonly string[]): string[] {
  if (selected.length === 0) return [...served];
  const known = served.filter((value) => selected.includes(value));
  return known.length === selected.length ? known : [...selected].sort();
}

export function usePlanFormLists(props: {
  draft: PlanFormDraft;
  client?: ApiClient;
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}): PlanFormData {
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
  // `DEF-RAT-9351` — the classes the plan is for go WITH the request, so each
  // schedule's base resolves as the plan's own read resolves it. The class
  // list itself arrives in the first answer, so *Every customer class* asks
  // once with none and then with every class; the previous answer stays on
  // screen meanwhile, so a row already chosen never blanks (`placeholderData`).
  const [knownClasses, setKnownClasses] = useState<string[]>([]);
  const classes = classesAsked(props.draft.customer_classes, knownClasses);
  const optionsQuery = useQuery({
    queryKey: [...PLAN_FORM_OPTIONS_KEY, classes.join(",")],
    queryFn: async () => {
      try {
        return await getPlanFormOptions(null, client, classes);
      } catch {
        return EMPTY_PLAN_FORM_OPTIONS;
      }
    },
    placeholderData: (previous) => previous,
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const shellQuery = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const options = optionsQuery.data ?? EMPTY_PLAN_FORM_OPTIONS;
  const served = options.customer_classes.map((row) => row.value).join(",");
  useEffect(() => {
    setKnownClasses((was) => (was.join(",") === served ? was : served === "" ? [] : served.split(",")));
  }, [served]);
  const current = withOptionDefaults(props.draft, options);
  const lists: PlanFormLists = {
    options,
    classOptions: options.customer_classes,
    noteAttributes: noteAttributes(options, translate),
    currency: options.currency ?? shellQuery.data?.regional.currency ?? null,
    dateFormat: regional.dateFormat,
    timeZone: regional.timeZone,
    servicesSettingsHref: tenantPath(SERVICES_SETTINGS_ROUTE),
    newChargeCodeHref: tenantPath(`${DEFINITION_ROUTES.charge.listRoute}/new`),
  };
  return { current, lists, options, permissions, translate };
}
