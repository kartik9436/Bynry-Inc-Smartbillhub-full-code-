// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the plan details HEADER (images 24–37):
//           ← Plans, the NAME with its CODE, *PUBLISHED · V1 · Residential ·
//           09/01/2026 – 12/31/2026*, Edit and More ▾, the six tabs.
// Defects:  DEF-RAT-9334 (the page against the drawing) · DEF-RAT-9331 (the
//           class by NAME in the header line)
// Rules:    ruling 13 (*"The header is sticky"*, *"Arrow keys move between
//           tabs"*) · B14 rules 31, 33, 40 (the kit's one PageHeader, 32px) · 43
// ───────────────────────────────────────────────────────
import type { KeyboardEvent, ReactNode } from "react";

import type { PageHeaderTab } from "@/components/PageHeader";
import { PageHeader } from "@/components/PageHeader";

import { PlanVersionTag } from "../planListParts";
import { RatingStatusPill, planStatusTone } from "../ratingShared";
import { nextTab } from "./planDetailModel";
import type { PlanDetailTab, Translator } from "./planDetailModel";

/** The line under the title: status, version, then *Class · window*. */
export function PlanHeaderFacts(props: { status: string; version: number | null; place: string }) {
  return (
    <span className="flex flex-wrap items-center gap-2 text-base text-neutral-700" data-plan-header-facts="">
      <RatingStatusPill tone={planStatusTone(props.status)} stem="rating.plan.status" value={props.status} />
      <PlanVersionTag version={props.version} />
      {props.place !== "" && <span data-plan-header-window="">{props.place}</span>}
    </span>
  );
}

/**
 * ⚠ **STICKY, AND THE KIT'S HEADER IS NOT TOUCHED TO DO IT.** The wrapper sticks
 * to the top of the page's scroll box with the page's own background behind it,
 * so a long Services tab keeps the name, the actions and the tabs in view. Every
 * other screen mounting `PageHeader` is unchanged.
 *
 * ⚠ **ARROW KEYS ARE HANDLED HERE, ON THE STRIP'S WRAPPER**, for the same reason:
 * the kit's tab strip is a row of `role="tab"` buttons with no key handling, and
 * teaching it roving focus would change every tab strip in the product at once.
 * Left/Right (and Home/End) move to the next tab and focus it.
 */
export function PlanDetailHeader(props: {
  name: string;
  code: string;
  facts: ReactNode;
  backTo: string;
  actions: ReactNode;
  tabs: readonly PageHeaderTab[];
  activeTab: PlanDetailTab;
  onTab: (id: PlanDetailTab) => void;
  t: Translator;
}) {
  const { t } = props;
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const target = event.target as HTMLElement;
    if (target.getAttribute("role") !== "tab") return;
    const next = nextTab(props.activeTab, event.key);
    if (next === null) return;
    event.preventDefault();
    props.onTab(next);
    const strip = target.closest("[data-page-header-tabs]");
    const button = strip?.querySelector<HTMLElement>(`[data-tab="${next}"]`);
    button?.focus();
  }
  return (
    <div className="sticky top-0 z-30 bg-bg" onKeyDown={onKeyDown} data-plan-detail-header="">
      <PageHeader
        backTo={{ to: props.backTo, label: t("rating.planDetail.backToPlans") }}
        title={props.name}
        titleAfter={
          props.code.trim() === "" ? undefined : (
            <span className="ms-3 align-middle text-base font-semibold uppercase text-neutral-700" data-plan-code="">
              {props.code}
            </span>
          )
        }
        rollup={props.facts}
        secondaryActions={props.actions}
        tabs={props.tabs}
        activeTabId={props.activeTab}
        tabsLabel={t("rating.planDetail.tabsLabel")}
        onTabSelect={(tab) => props.onTab(tab.id as PlanDetailTab)}
      />
    </div>
  );
}
