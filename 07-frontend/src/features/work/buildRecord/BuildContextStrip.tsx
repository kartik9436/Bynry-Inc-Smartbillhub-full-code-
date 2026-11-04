// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 11 — New Connection step 4's context strip
//           (`step4-charges.png`'s seven cells). MOVED here unchanged from
//           `features/customers/NewConnectChargesStep.tsx` by `DEF-GOV-10114`
//           (2026-10-14): G93 — a build's panels live ONCE, in
//           `features/work/buildViews.tsx` / `features/work/buildRecord/`, and
//           every screen COMPOSES them. The step imports it from here.
// Rules:    B14 rules 31, 33, 43 · G93 (`10-scripts/gates/g93_one_build_destination.py`)
// Tests:    src/features/customers/NewConnectRedesignSteps45.dom.test.tsx (the strip's
//           seven cells, read through the step that mounts it)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getUnitPlanOptions } from "@/api/endpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { connectScopeWord, draftUnits, draftUnitServices } from "@/features/customers/newConnectDraft";
import type { NewConnectDraft } from "@/features/customers/newConnectDraft";
import { newConnectPlansQueryKey } from "@/features/customers/NewConnectPremiseStep";
import type { Translator } from "@/features/customers/newConnectShared";
import { EmptyValue } from "@/features/customers/newConnectStepKit";
import { ServiceTags } from "@/features/rating/ratingShared";

// ══════════════════════════════════════════════════════════════════════════
// THE CONTEXT STRIP — `step4-charges.png`'s seven cells
// ══════════════════════════════════════════════════════════════════════════

/**
 * **WHAT THE CLERK IS PRICING, ACROSS THE TOP OF THE STEP.**
 *
 * Customer · Premise · Scope · Units · Services · Counted · Plan.
 *
 * ⚠ **EVERY CELL IS A FACT AND NOTHING HERE IS TYPED** (B14 rule 33 — a FACT
 * is six words). It is a read-back of steps 1 to 3, put where money is about
 * to be decided, so a clerk pricing the wrong build sees it before they price
 * it rather than on the review screen afterwards.
 *
 * ⚠ **NO DATABASE ID REACHES IT** (B14 rule 31). The PLAN cell in particular
 * holds `draft.planApartments`, which is a tariff UUID; it is resolved to the
 * plan's NAME through the same query and the same cache key step 2 uses
 * (`newConnectPlansQueryKey`), so the two screens cannot name one plan two
 * ways and the lookup costs no second request. A plan the list does not answer
 * for draws the em dash rather than its id.
 *
 * ⚠ **`Counted` IS THREE COUNTS AND NOT A MONEY FIGURE** — units · meters ·
 * premises, from `quoteCounts`, which is the same derivation the charge lines'
 * Qty cell reads. One derivation, so the strip and the table cannot disagree
 * about the same build.
 */
export function BuildContextStrip(props: {
  draft: NewConnectDraft;
  counts: { units: number; meters: number; premises: number };
  t: Translator;
  client?: ApiClient;
}) {
  const units = draftUnits(props.draft);
  const services = draftUnitServices(props.draft);
  const mapped = Array.from(new Set(Object.values(services).flat())).sort();
  // The plan's NAME, from the cache step 2 already filled. `enabled` keeps a
  // build with no plan from asking for a list it has no question about.
  const plansQuery = useQuery({
    queryKey: newConnectPlansQueryKey,
    queryFn: () => getUnitPlanOptions({ per: 200 }, props.client ?? api),
    enabled: props.draft.planApartments !== "",
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const planName =
    (plansQuery.data?.results ?? []).find((plan) => plan.id === props.draft.planApartments)?.name ??
    null;
  const unitLabels = units.map((unit) => unit.label).join(", ");
  return (
    <div
      className="mb-4 grid grid-cols-7 border border-divider bg-surface max-lg:grid-cols-2"
      data-build-context=""
    >
      <ContextCell
        what={props.t("customers.newConnect.context.customer", { defaultValue: "Customer" })}
        mark="customer"
      >
        {props.draft.owner.name.trim() === "" ? (
          <EmptyValue tracks="step-1" />
        ) : (
          props.draft.owner.name.trim()
        )}
      </ContextCell>
      <ContextCell
        what={props.t("customers.newConnect.context.premise", { defaultValue: "Premise" })}
        mark="premise"
      >
        {props.draft.premise.name.trim() !== "" ? (
          props.draft.premise.name.trim()
        ) : props.draft.premise.address.trim() !== "" ? (
          props.draft.premise.address.trim()
        ) : (
          <EmptyValue tracks="step-2" />
        )}
      </ContextCell>
      <ContextCell
        what={props.t("customers.newConnect.context.scope", { defaultValue: "Scope" })}
        mark="scope"
      >
        {connectScopeWord(props.draft.scope, props.t)}
      </ContextCell>
      <ContextCell
        what={props.t("customers.newConnect.context.units", { defaultValue: "Units" })}
        mark="units"
      >
        {units.length === 0 ? (
          <EmptyValue tracks="step-3" />
        ) : (
          <span className="tabular-nums">{`${units.length} · ${unitLabels}`}</span>
        )}
      </ContextCell>
      <ContextCell
        what={props.t("customers.newConnect.context.services", { defaultValue: "Services" })}
        mark="services"
      >
        {mapped.length === 0 ? <EmptyValue tracks="step-3" /> : <ServiceTags services={mapped} />}
      </ContextCell>
      {/* ⚠ **THREE COUNTS, NEVER A PRICE.** What a count is worth is
          `charge_code_line`'s to say, and its own docstring forbids a caller
          multiplying first. */}
      <ContextCell
        what={props.t("customers.newConnect.context.counted", { defaultValue: "Counted" })}
        mark="counted"
      >
        <span className="tabular-nums">
          {`${props.counts.units} · ${props.counts.meters} · ${props.counts.premises}`}
        </span>
      </ContextCell>
      <ContextCell
        what={props.t("customers.newConnect.context.plan", { defaultValue: "Plan" })}
        mark="plan"
      >
        {/* ⚠ **`step-3`: a plan is chosen on the UNITS step now, not a step
            of its own — see the same correction on the Review glance cell. */}
        {planName === null ? <EmptyValue tracks="step-3" /> : planName}
      </ContextCell>
    </div>
  );
}

function ContextCell(props: { what: string; mark: string; children: ReactNode }) {
  return (
    <div className="border-r border-divider p-3 last:border-r-0" data-context-cell={props.mark}>
      <div className="text-sm text-neutral-700">{props.what}</div>
      <div className="font-medium" data-context-value={props.mark}>
        {props.children}
      </div>
    </div>
  );
}
