// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — ruling 13's *"A banner names an
//           upcoming version"* (image 24): *Water rate schedule v5 starts
//           01/01/2027. Usage charges $4.45 · $7.23 · $8.90 per kgal. See it*
// Rules:    B14 rule 33 (FACTS, no rationale) · BR-RAT-087 (the server's
//           display strings — nothing is priced here)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PRICES ARE READ, NOT GUESSED.** `upcoming[]` names the item and its
// date only. For a rate schedule the second sentence comes from a second read
// of the SAME page as of that date — the schedule's usage rows exactly as the
// Services tab would draw them on *See it* — so the banner can never show a
// figure the tab it links to does not. Shown once that read answers; the first
// sentence never waits for it.
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getPlanDetailRead } from "@/api/planDetailEndpoints";
import type { PlanUpcoming } from "@/api/planDetailEndpoints";
import type { PlanSections } from "@/api/planFormEndpoints";
import { InlineLinkTo } from "@/components/Surfaces";

import { usageRowRate } from "../planSections/PlanSections";

import { rateRange, upcomingHead, upcomingService } from "./planDetailModel";
import type { PlanRegional, Translator } from "./planDetailModel";

export function PlanUpcomingBanner(props: {
  planId: string;
  item: PlanUpcoming;
  sections: PlanSections;
  seeIt: string;
  client: ApiClient;
  regional: PlanRegional;
  t: Translator;
}) {
  const { item, t } = props;
  const service = upcomingService(item, props.sections);
  const later = useQuery({
    queryKey: ["plans", props.planId, "detail", item.effective_from],
    queryFn: () => getPlanDetailRead(props.planId, item.effective_from, props.client),
    enabled: service !== null && item.effective_from !== null,
    retry: false,
  });
  const laterService = later.data?.sections.services.find((line) => line.service === service?.service);
  // `DEF-RAT-9518` — worded as the usage table words it, in the language.
  const rates = laterService?.usage.rows.map((row) => usageRowRate(row, t)) ?? [];
  return (
    <div
      role="status"
      className="flex flex-wrap items-baseline gap-x-2 bg-info-100 px-3 py-2 text-sm text-info-700"
      data-plan-upcoming=""
    >
      <strong className="font-semibold">{upcomingHead(item, props.sections, props.regional, t)}</strong>
      {rates.length > 0 && (
        <span data-plan-upcoming-rates="">
          {t("rating.planDetail.banner.usage", { rates: rateRange(rates, " · ") })}
        </span>
      )}
      <InlineLinkTo to={props.seeIt} className="font-semibold" data-plan-upcoming-see="">
        {t("rating.planDetail.banner.seeIt")}
      </InlineLinkTo>
    </div>
  );
}
