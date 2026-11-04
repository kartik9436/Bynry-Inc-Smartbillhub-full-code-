// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the *This tax* panel on the right of every
//           step of the New tax or fee form (images 04–17 of
//           `05-prototype/taxes-fees-2026-10-03/images/`).
// ───────────────────────────────────────────────────────
//
// What the tax will be, as it stands, beside every step: the rate in large
// type, its unit, a *Check the rate* pill over 20 %, seven facts, what it adds
// to a $60.00 bill, and the services it reaches as marks.
import { checkDropdownSummary } from "@/components/CheckDropdown";
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";

import { EXAMPLE_BILL, effectiveBasis, exampleBill, percentIsHigh, BASIS_PERCENT } from "./taxFormModel";
import type { TaxFormDraft } from "./taxFormModel";
import { ServiceMarker, labelOf, rateFigure, rateUnitKey } from "./taxFormShared";
import type { TaxFormLists, Translator } from "./taxFormShared";

const ROW = "flex items-baseline justify-between gap-3 text-base";

export function TaxSummaryPanel(props: { draft: TaxFormDraft; lists: TaxFormLists; t: Translator }) {
  const { draft, lists, t } = props;
  const figure = rateFigure(draft);
  const high = effectiveBasis(draft) === BASIS_PERCENT && percentIsHigh(draft.rate_percent);
  const effect = exampleBill(draft).effect;
  const reach = lists.reach;
  const liability = lists.liabilityAccounts.find((row) => row.value === draft.liability_gl_account_id);
  const services =
    draft.services.length === 0 ? lists.services : lists.services.filter((row) => draft.services.includes(row.value));
  const facts: [string, string, string][] = [
    ["name", t("rating.taxForm.summary.name"), draft.name.trim() || "—"],
    [
      "reaches",
      t("rating.taxForm.summary.reaches"),
      reach === null ? "—" : t("rating.taxForm.summary.premises", { count: reach.count }),
    ],
    ["services", t("rating.taxForm.field.services"), checkDropdownSummary(lists.services, draft.services, t("rating.taxForm.allServices"))],
    [
      "classes",
      t("rating.taxForm.summary.classes"),
      draft.customer_classes.length === 0
        ? t("rating.taxForm.summary.all")
        : checkDropdownSummary(lists.classes, draft.customer_classes, ""),
    ],
    [
      "starts",
      t("rating.taxForm.summary.starts"),
      draft.effective_from === "" ? "—" : formatDate(draft.effective_from, lists.timeZone, lists.dateFormat),
    ],
    ["filed", t("rating.taxForm.field.filed"), labelOf(lists.filingFrequencies, draft.filing_frequency) || "—"],
    // The account's CODE — the drawing prints `2200-02`, the label's first part.
    ["account", t("rating.taxForm.summary.account"), liability === undefined ? "—" : liability.label.split(" · ")[0]],
    // DEF-RAT-10027 (PO 2026-10-09) — the authority and the registration number
    // the tax files under, in full: *City of Queen West Finance · CQW-FR-0091*.
    [
      "registration",
      t("rating.taxForm.summary.registration"),
      labelOf(lists.authorityAccounts, draft.authority_account_id) || "—",
    ],
  ];
  return (
    <Panel as="aside" aria-label={t("rating.taxForm.summary.kicker")} data-tax-summary="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t("rating.taxForm.summary.kicker")}
      </p>
      <p className="m-0 mt-3 font-heading text-metric-lg font-semibold" data-tax-summary-rate="">
        {figure ?? "—"}
      </p>
      <p className="m-0 mt-2 text-lead text-neutral-700">{t(rateUnitKey(draft))}</p>
      {high && (
        <div className="mt-3" data-tax-summary-high="">
          <StatusPill tone="warning">{t("rating.taxForm.checkRate")}</StatusPill>
        </div>
      )}
      <dl className="m-0 mt-4 flex flex-col gap-2 border-t border-divider pt-4">
        {facts.map(([id, label, value]) => (
          <div key={id} className={ROW} data-tax-summary-fact={id}>
            <dt className="text-neutral-700">{label}</dt>
            <dd className="m-0 text-right font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      <div className={`${ROW} mt-4 border-t border-divider pt-4`}>
        <span className="text-neutral-700">{t("rating.taxForm.summary.onBill", { bill: EXAMPLE_BILL })}</span>
        {/* DEF-RAT-9306 — no figure is a dash, never $0.00: the example bill
            has none for a per-unit or per-meter tax, or before a rate. */}
        <span className="font-semibold tabular-nums" data-tax-summary-effect="">
          {effect === null ? "—" : `$${effect}`}
        </span>
      </div>
      {services.length > 0 && (
        <ul className="m-0 mt-3 flex list-none flex-wrap gap-1.5 p-0" aria-label={t("rating.taxForm.field.services")}>
          {services.map((row) => (
            <li
              key={row.value}
              className="inline-flex items-center gap-1.5 border border-divider bg-neutral-100 px-2 py-1 font-heading text-sm font-semibold"
            >
              <ServiceMarker code={row.value} />
              {row.label}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
