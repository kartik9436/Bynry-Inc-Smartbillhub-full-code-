// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — every list the rule form
//           offers and every NAME the rule screens print for a value the rule
//           holds as an id, read once and shared by the builder and the
//           rule's own page.
// Rules:    B14 rule 31 (an id travels, a name is read) · `BR-NOT-017` (the
//           messages are Notifications' own rows) · NFR-5 (no list is cut to a
//           maximum on the server's side; the pickers ask for 200 by name, the
//           figure the crews picker already asks for, CR-168 §20.3 gap 4)
// ───────────────────────────────────────────────────────
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import {
  getLookupEntries,
  getNotificationRules,
  getRolesMatrix,
  getTenantServices,
} from "@/api/endpoints";

import { listCrewsView, listStaffChoices } from "../crewsEndpoints";
import { getRaiseOptions, listTemplates } from "../workEndpoints";
import { getRuleProcesses } from "./ruleEndpoints";
import type { RuleProcesses } from "./ruleEndpoints";
import { emptyNames } from "./ruleModel";
import type { RuleNames } from "./ruleModel";

export interface Choice {
  value: string;
  label: string;
}

export interface MessageChoice extends Choice {
  audience: string;
}

export interface ServiceChoice extends Choice {
  /** The units this service is read in — the continuous-flow minimum's unit
   *  (hard rule 3). */
  units: string[];
}

export interface RuleLookups {
  processes: RuleProcesses | undefined;
  names: RuleNames;
  templates: Choice[];
  priorities: Choice[];
  technicians: Choice[];
  crews: Choice[];
  roles: Choice[];
  people: Choice[];
  services: ServiceChoice[];
  assetTypes: Choice[];
  /** Every catalogue message, with its audience — `customer` or `staff`. */
  messages: MessageChoice[];
  ready: boolean;
}

const PER = 200;

/**
 * @param enabled `false` on a tab that draws no rule at all (Jobs, Audit), so
 * eight reads are not made for nothing.
 */
export function useRuleLookups(client: ApiClient, enabled = true): RuleLookups {
  const processes = useQuery({
    queryKey: ["work", "rules", "processes"],
    queryFn: () => getRuleProcesses(client),
    enabled,
  });
  const templates = useQuery({
    queryKey: ["work", "rules", "templates"],
    queryFn: () => listTemplates({ per: PER }, client),
    enabled,
  });
  const raise = useQuery({
    queryKey: ["work", "raise-options"],
    queryFn: () => getRaiseOptions(client),
    enabled,
  });
  const technicians = useQuery({
    queryKey: ["work", "rules", "technicians"],
    queryFn: () => listCrewsView<{ id: string; name: string }>("technicians", { per: PER }, client),
    enabled,
  });
  const crews = useQuery({
    queryKey: ["work", "rules", "crews"],
    queryFn: async () => {
      const [ours, contractors] = await Promise.all([
        listCrewsView<{ id: string; name: string }>("crews", { per: PER }, client),
        listCrewsView<{ id: string; name: string }>("contractors", { per: PER }, client),
      ]);
      return [...ours.results, ...contractors.results];
    },
    enabled,
  });
  const roles = useQuery({
    queryKey: ["work", "rules", "roles"],
    queryFn: async () => (await getRolesMatrix(client)).data?.roles ?? [],
    enabled,
  });
  const people = useQuery({
    queryKey: ["work", "rules", "people"],
    queryFn: () => listStaffChoices(client),
    enabled,
  });
  const services = useQuery({
    queryKey: ["work", "rules", "services"],
    queryFn: () => getTenantServices(client),
    enabled,
  });
  const assetTypes = useQuery({
    queryKey: ["work", "rules", "asset-types"],
    queryFn: () => getLookupEntries("asset_types", { per: PER }, client),
    enabled,
  });
  const messages = useQuery({
    queryKey: ["work", "rules", "messages"],
    queryFn: () => getNotificationRules(client),
    enabled,
  });

  return useMemo(() => {
    const names = emptyNames();
    // A draft (`version` 0, `BR-WRK-011`) and a deactivated template
    // (`BR-WRK-012`) raise nothing, so neither is offered.
    const templateRows = (templates.data?.results ?? []).filter((row) => row.active && row.version >= 1);
    for (const row of templates.data?.results ?? []) names.templates[row.id] = row.name;
    for (const row of raise.data?.priorities ?? []) names.priorities[row.id] = row.name;
    for (const row of technicians.data?.results ?? []) names.technicians[row.id] = row.name;
    for (const row of crews.data ?? []) names.crews[row.id] = row.name;
    for (const row of roles.data ?? []) names.roles[row.code] = row.name;
    for (const row of people.data?.results ?? []) {
      names.people[row.user_id] = row.full_name ?? row.email;
    }
    const serviceRows = (services.data ?? []).filter((row) => row.enabled);
    for (const row of serviceRows) names.services[row.service] = row.name;
    for (const row of assetTypes.data?.results ?? []) names.assetTypes[row.id] = row.name;
    for (const row of messages.data?.results ?? []) names.channels[row.key] = row.channels;

    return {
      processes: processes.data,
      names,
      templates: templateRows.map((row) => ({ value: row.id, label: row.name })),
      priorities: (raise.data?.priorities ?? []).map((row) => ({ value: row.id, label: row.name })),
      technicians: (technicians.data?.results ?? []).map((row) => ({ value: row.id, label: row.name })),
      crews: (crews.data ?? []).map((row) => ({ value: row.id, label: row.name })),
      roles: (roles.data ?? []).map((row) => ({ value: row.code, label: row.name })),
      people: (people.data?.results ?? [])
        .filter((row) => row.status === "active")
        .map((row) => ({ value: row.user_id, label: row.full_name ?? row.email })),
      services: serviceRows.map((row) => ({
        value: row.service,
        label: row.name,
        units: [row.primary_uom, row.alt_uom, row.billed_uom].filter(
          (unit, index, all): unit is string =>
            typeof unit === "string" && unit !== "" && all.indexOf(unit) === index,
        ),
      })),
      assetTypes: (assetTypes.data?.results ?? []).map((row) => ({ value: row.id, label: row.name })),
      messages: (messages.data?.results ?? []).map((row) => ({
        value: row.key,
        label: row.key,
        audience: row.audience,
      })),
      ready: processes.data !== undefined,
    };
  }, [
    processes.data,
    templates.data,
    raise.data,
    technicians.data,
    crews.data,
    roles.data,
    people.data,
    services.data,
    assetTypes.data,
    messages.data,
  ]);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §7.3 · §20.1 · §20.3 gap 4 · images 57, 59, 61, 62
// generated: 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/rules
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
