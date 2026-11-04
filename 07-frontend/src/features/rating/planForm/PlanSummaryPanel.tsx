// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — the *This plan* panel on the right of
//           every step of the New plan form (images 04–23).
// ───────────────────────────────────────────────────────
//
// What the plan is, as it stands, beside every step: the monthly base charges
// in large type (ruling 12's words), the services as badges, and eight facts.
// Every figure is the server's or an exact sum of the server's (hard rule 2).
import { Panel } from "@/components/Panel";
import { checkDropdownSummary } from "@/components/CheckDropdown";

import { moneyShown } from "../planSections/PlanSections";
import { ServiceTags } from "../ratingShared";
import { combinedTaxPercent, minimumBillDisplay, monthlyBaseShown } from "./planFormModel";
import type { PlanFormDraft } from "./planFormModel";
import type { PlanFormLists, Translator } from "./planFormShared";

const ROW = "flex items-baseline justify-between gap-3 text-base";

export function PlanSummaryPanel(props: { draft: PlanFormDraft; lists: PlanFormLists; t: Translator }) {
  const { draft, lists, t } = props;
  const options = lists.options;
  const monthly = monthlyBaseShown(draft, options);
  const services = draft.services.map((row) => row.service).filter((service) => service !== "");
  const minimum = minimumBillDisplay(draft);
  const facts: [string, string, string][] = [
    ["name", t("rating.planForm.summary.name"), draft.name.trim() || "—"],
    ["code", t("rating.planForm.summary.code"), draft.code.trim() || "—"],
    [
      "classes",
      t("rating.planForm.summary.classes"),
      draft.customer_classes.length === 0
        ? t("rating.planForm.summary.all")
        : checkDropdownSummary(lists.classOptions, draft.customer_classes, ""),
    ],
    ["services", t("rating.planForm.summary.services"), String(services.length)],
    ["charges", t("rating.planForm.summary.charges"), String(draft.charge_codes.filter((row) => row.value !== "").length)],
    ["taxes", t("rating.planForm.summary.taxes"), combinedTaxPercent(draft, options) ?? t("rating.planForm.summary.none")],
    ["discounts", t("rating.planForm.summary.discounts"), String(draft.discounts.filter((row) => row.discount !== "").length)],
    ["minimum", t("rating.planForm.summary.minimum"), minimum === null ? "—" : moneyShown(minimum, lists.currency)],
  ];
  return (
    <Panel as="aside" aria-label={t("rating.planForm.summary.kicker")} data-plan-summary="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t("rating.planForm.summary.kicker")}
      </p>
      <p className="m-0 mt-3 font-heading text-metric-lg font-semibold" data-plan-summary-figure="">
        {moneyShown(monthly, lists.currency)}
      </p>
      <p className="m-0 mt-2 text-lead text-neutral-700">{t("rating.planForm.summary.unit")}</p>
      {services.length > 0 && (
        <div className="mt-4" data-plan-summary-services="">
          <ServiceTags services={services} />
        </div>
      )}
      <dl className="m-0 mt-4 flex flex-col gap-2 border-t border-divider pt-4">
        {facts.map(([id, label, value]) => (
          <div key={id} className={ROW} data-plan-summary-fact={id}>
            <dt className="text-neutral-700">{label}</dt>
            <dd className="m-0 text-right font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
