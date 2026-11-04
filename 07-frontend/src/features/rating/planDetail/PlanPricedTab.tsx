// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the Services, Charges and Billing tabs
//           (images 26–30, 37). Each MOUNTS the shared `PlanSections` — the
//           component Review mounts (ruling 11) — with every name a link and a
//           section's *Edit* opening that step of the Edit form.
// Defects:  DEF-RAT-9334 (sections, versions and from-dates, `$` on money) ·
//           DEF-RAT-9286 (no count drawn above a section can contradict its rows)
// Rules:    ruling 8 (version pill and *from MM/DD/YYYY* on every item) ·
//           ruling 11 · ruling 13 (*"Services fold to one line, with Expand
//           all"*, *"Priced as of a date"*, *"A section's Edit opens that step"*)
// ───────────────────────────────────────────────────────
import { useState } from "react";

import type { PlanSections as PlanSectionsData } from "@/api/planFormEndpoints";

import { PlanSections } from "../planSections/PlanSections";
import type { PlanSectionId } from "../planSections/PlanSections";
import { PlanPricedAsOf } from "./PlanPricedAsOf";
import { foldedServiceLine } from "./planDetailModel";
import type { PlanRegional, Translator } from "./planDetailModel";

/** What each priced tab shows, in the shared component's order (§10). */
export const TAB_SECTIONS: Readonly<Record<"services" | "charges" | "billing", readonly PlanSectionId[]>> = {
  services: ["services", "servicesTotals"],
  charges: ["charges", "taxes"],
  billing: ["deposits", "discounts", "billingTerms"],
};

export function PlanPricedTab(props: {
  tab: "services" | "charges" | "billing";
  sections: PlanSectionsData;
  asOf: string;
  today: string;
  onAsOf: (value: string) => void;
  /** `null` on a read-only role: no section offers Edit. */
  onEdit: ((section: PlanSectionId) => void) | null;
  regional: PlanRegional;
  t: Translator;
}) {
  const { t, sections } = props;
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const all = sections.services.map((line) => line.service);
  const allOpen = all.length > 0 && all.every((code) => open.has(code));
  const isServices = props.tab === "services";
  return (
    <div className="flex flex-col gap-4" data-plan-priced-tab={props.tab}>
      <PlanPricedAsOf
        value={props.asOf}
        today={props.today}
        onChange={props.onAsOf}
        expand={
          isServices && all.length > 0
            ? { allOpen, onToggle: () => setOpen(allOpen ? new Set() : new Set(all)) }
            : undefined
        }
        regional={props.regional}
        t={t}
      />
      <PlanSections
        sections={sections}
        show={TAB_SECTIONS[props.tab]}
        t={t}
        dateFormat={props.regional.dateFormat}
        timeZone={props.regional.timeZone}
        links
        onEdit={props.onEdit === null ? undefined : (section) => props.onEdit?.(section)}
        fold={
          isServices
            ? {
                open,
                onToggle: (service) => {
                  const next = new Set(open);
                  if (next.has(service)) next.delete(service);
                  else next.add(service);
                  setOpen(next);
                },
                line: (section) => foldedServiceLine(section, sections.currency, t),
              }
            : undefined
        }
      />
    </div>
  );
}
