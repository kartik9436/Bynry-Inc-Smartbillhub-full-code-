// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard, step 3 · Billing) · CR-171-BRC10
//           P2.28–P2.31 (lane MVI-WIZ-BILL), images 41–44
// Rules:    §9.MONEY (the contract) · OQ-BIL-12788 CLOSED (a) (a move-in fee
//           is never taxed at move-in) · decision log 2026-10-05 *"FOUR PO
//           RULINGS"* (2) (a billing clerk records the discount and the
//           exemption — no System Admin state) · J4 (Pay now is an advance on
//           the first bill) · PO 2026-10-02 (unit prices to four places, totals
//           to two) · BR-CUS-029 · BR-CUS-059 · BR-BIL-036 · B14 rules 20, 21,
//           31, 33, 36, 43, 44
// ───────────────────────────────────────────────────────
//
// Step 3 is six panels, top to bottom, as images 41–44 draw them: **Plan**
// (with *See full rates*), **Preferences**, **Discounts**, **Tax**, **Fees**
// and **Payment**. The old body — the unit pricing panel, two bare ticks, the
// tax fields, the hand-typed discount list and the whole Deposit step — is
// REPLACED: the deposit is now the Fees table's first row and the money for
// it is the Payment panel's (§9.MONEY: *"`required` with `take_now: false` is
// the new form's normal answer — the money is `payment`'s"*).
//
// Its own state is `ctx.own.billing` — held by the wizard through
// `useStepBillingOwn()` below, handed back on the context (`DEF-CUS-9729`).
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getMoveInPricing, moveInMoneyKeys } from "@/api/moveInMoneyEndpoints";
import type { MoveInMoneyQuery } from "@/api/moveInMoneyEndpoints";
import { todayInZone } from "@/components/DateCell";
import type { WizardStepVerdict } from "@/components/WizardFrame";

import { useAccountCategories } from "../customersShared";
import { DiscountsSection, pairedSettings, PreferencesSection, TaxSection } from "./BillingExtras";
import { billingHydrate, billingPark, billingPayload, billingProblems, emptyStepBillingOwn } from "./billingModel";
import type { StepBillingOwn } from "./billingModel";
import { FeesTable } from "./FeesTable";
import type { MoveInWizardContext, StepOwn } from "./moveInWizardContext";
import { MoveInPayment } from "./MoveInPayment";
import { MoveInPlanPanel } from "./MoveInPlanPanel";

export type { StepBillingOwn } from "./billingModel";

export function useStepBillingOwn(): StepOwn<StepBillingOwn> {
  const [value, set] = useState<StepBillingOwn>(emptyStepBillingOwn);
  const own: StepOwn<StepBillingOwn> = {
    value,
    set,
    payload: billingPayload(value),
    park: billingPark(value),
    hydrate: (parked) => set(billingHydrate(parked)),
  };
  return own;
}

/** The query every Billing read takes: the unit, the class, the Start ticks. */
export function billingQuery(ctx: MoveInWizardContext): MoveInMoneyQuery {
  return { unitId: ctx.outgoingUnitId, accountType: ctx.customer.account_type, services: [...ctx.ticked] };
}

/** Step 3 as the rail draws it. */
export function StepBilling(props: { ctx: MoveInWizardContext }) {
  const { ctx } = props;
  const { value: own, set } = ctx.own.billing;
  const { t } = ctx;

  const query = billingQuery(ctx);
  const ready = query.unitId !== "" && query.accountType !== "";
  // ONE read serves the Plan panel, *See full rates* AND the Fees table's
  // plan rows (`pricing.fees` is `GET /move-ins/fees`' own answer), so the
  // table and the plan cannot describe two different plans.
  const pricing = useQuery({
    queryKey: moveInMoneyKeys.pricing(query),
    queryFn: () => getMoveInPricing(query, ctx.client),
    enabled: ready,
    retry: false,
  });
  const status: "pending" | "failed" | "ready" = pricing.isError
    ? "failed"
    : pricing.data === undefined
      ? "pending"
      : "ready";

  // The plan rows land in the step's own state, so Complete sends exactly
  // the rows the clerk saw (and Continue waits for them).
  const rowsKey = pricing.data === undefined ? null : JSON.stringify(pricing.data.fees.rows);
  useEffect(() => {
    if (pricing.data === undefined) return;
    if (JSON.stringify(own.planRows) === rowsKey) return;
    set({ ...own, planRows: pricing.data.fees.rows });
    // `own` is read fresh each render; only a NEW answer should write.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowsKey, own.planRows === null]);

  const categories = useAccountCategories(ctx.client);
  const classLabel = categories.all.find((c) => c.code === ctx.customer.account_type)?.name ?? "";
  const problems = useMemo(() => billingProblems(own), [own]);
  const today = todayInZone(ctx.timeZone);
  const tried = ctx.tried.billing;
  const currency = pricing.data?.fees.currency ?? ctx.currency ?? "USD";

  return (
    <div className="flex flex-col gap-5" data-move-in-billing="">
      <MoveInPlanPanel
        status={status}
        pricing={pricing.data}
        classLabel={classLabel}
        dateFormat={ctx.dateFormat}
        timeZone={ctx.timeZone}
        t={t}
      />
      <PreferencesSection
        own={own}
        set={set}
        preferences={ctx.preferences}
        setPreferences={ctx.setPreferences}
        paired={pairedSettings(pricing.data?.plan?.claimable_discounts ?? [])}
        client={ctx.client}
        t={t}
      />
      <DiscountsSection
        own={own}
        set={set}
        // DEF-CUS-9779: only discounts a person claims — never the automatic
        // ones the system grants itself. ⚖️ AMENDED 2026-10-06 (DEF-RAT-9833,
        // PO D2 (b)): Autopay and Paperless are claimable again and switch
        // their preference On; Municipal account stays out.
        offered={pricing.data?.plan?.claimable_discounts ?? []}
        preferences={ctx.preferences}
        setPreferences={ctx.setPreferences}
        problems={problems}
        tried={tried}
        t={t}
      />
      <TaxSection
        own={own}
        set={set}
        taxes={pricing.data?.plan?.taxes ?? []}
        problems={problems}
        tried={tried}
        dateFormat={ctx.dateFormat}
        client={ctx.client}
        t={t}
      />
      <FeesTable
        own={own}
        set={set}
        status={status}
        query={query}
        currency={currency}
        classLabel={classLabel}
        client={ctx.client}
        t={t}
        tried={tried}
      />
      <MoveInPayment
        own={own}
        set={set}
        ready={status === "ready" && own.planRows !== null}
        currency={currency}
        dateFormat={ctx.dateFormat}
        today={today}
        problems={problems}
        tried={tried}
        client={ctx.client}
        t={t}
      />
    </div>
  );
}

/** Continue waits for the plan's rows and for every field §9.MONEY would
 *  refuse at Complete (`billingModel.billingProblems`). */
export function stepBillingVerdict(ctx: MoveInWizardContext): WizardStepVerdict {
  ctx.markTried("billing");
  return billingProblems(ctx.own.billing.value).length === 0;
}
