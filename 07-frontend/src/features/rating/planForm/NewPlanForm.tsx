// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — the New plan form, five steps
//           *Details · Services · Charges · Billing · Review*, built from images
//           04–23 of `05-prototype/plans-2026-10-03/images/` (B14 rules 42, 44,
//           37, 43, 21, 33). Replaces `PlanWizard.tsx` on the NEW route only;
//           the Edit route stays on it until round 3 (task 8) retires it.
// Defects:  DEF-RAT-9332 (the form against the drawing) · DEF-RAT-9328 (late
//           fee — form side) · DEF-RAT-9287 · DEF-RAT-9285
// Contract: CR-167-BRC10 §7.3 — `GET /plans/form-options`, `POST /plans`
//           (`publish: false` saves a draft, `publish: true` publishes)
// ───────────────────────────────────────────────────────
//
// THE PAGE: it loads the lists, holds the ONE draft, and lays the step
// components and *This plan* onto the frame — the discount form's structure,
// copied. Every step is a component in this folder and the steps are an
// ARRAY, so round 3's three Edit choices mount the same steps with fields
// locked and a different `steps` list.
//
// ⚠ **NOTHING TYPED IS LOST.** The draft lives here, above every step, and is
// never reset by a refusal — a server error marks the box and opens its step.
//
// ⚠ **REVIEW ENDS *Save as draft* · *Publish plan* (ruling 10).** Both are the
// SAME call, `POST /plans`, with `publish` false or true (BR-SHL-019: one
// transactional write). *Publish plan* is the frame's commit; *Save as draft*
// rides in the frame's own action row (`commitCompanion`, beside the commit) so the footer is
// one row of one size.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { savePlanForm } from "@/api/planFormEndpoints";
import { refusalParams } from "@/api/refusalText";
import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FieldErrorsScope } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { refusalOf } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { planDetailRoute } from "../planDetail/planDetailModel";
import { DASHBOARD_ROUTE, PLANS_RATES_ROUTE, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { BillingStep } from "./BillingStep";
import { ChargesStep } from "./ChargesStep";
import { DetailsStep } from "./DetailsStep";
import { PlanSavedPanel } from "./PlanSavedPanel";
import { PlanSummaryPanel } from "./PlanSummaryPanel";
import { ReviewStep } from "./ReviewStep";
import { ServicesStep } from "./ServicesStep";
import {
  NEW_PLAN_STEPS,
  SERVER_FIELD_BOXES,
  allGaps,
  draftSections,
  emptyPlanFormDraft,
  planFormPayload,
  stepGaps,
  stepNumberOf,
  withOptionDefaults,
} from "./planFormModel";
import type { PayloadContext, PlanFormDraft, PlanFormStepSpec, PlanStepId } from "./planFormModel";
import { PLAN_FORM_LAYOUT, optionLabel } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";
import { usePlanFormLists } from "./usePlanFormLists";

/** The URL param the open step lives in (BR-SHL-011 — a step is linkable). */
const STEP_PARAM = "step";

export const PLANS_LIST_ROUTE = `${PLANS_RATES_ROUTE}/plans`;

/**
 * One editing step by its id. Written as JSX rather than a lookup table so
 * every step is visibly MOUNTED (G40 reads `<Name`; a component reached only
 * through a map reads as dead UI). Review is not here: it reads the draft
 * through the shared sections.
 */
export function PlanStep(props: PlanStepProps & { id: Exclude<PlanStepId, "review"> }) {
  const { id, ...stepProps } = props;
  switch (id) {
    case "details":
      return <DetailsStep {...stepProps} />;
    case "services":
      return <ServicesStep {...stepProps} />;
    case "charges":
      return <ChargesStep {...stepProps} />;
    case "billing":
      return <BillingStep {...stepProps} />;
  }
}

export interface NewPlanFormProps {
  client?: ApiClient; // test seam — screens never build their own transport
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}

interface SavedPlan {
  id: string;
  name: string;
  published: boolean;
  startsOn: string | null;
}

export function NewPlanForm(props: NewPlanFormProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const steps: readonly PlanFormStepSpec[] = NEW_PLAN_STEPS;
  const [draft, setDraft] = useState<PlanFormDraft>(emptyPlanFormDraft);
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  /** The step whose gaps are marked — set by a refused Continue or a refused
   *  publish, so an empty form does not open shouting. */
  const [shownStep, setShownStep] = useState<PlanStepId | null>(null);
  const [publishTried, setPublishTried] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedPlan | null>(null);
  const [saving, setSaving] = useState(false);

  const { current, lists, options, permissions: permissionsQuery, translate } = usePlanFormLists({
    draft,
    client,
    dateFormat: props.dateFormat,
    timeZone: props.timeZone,
  });

  if (permissionsQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  const readOnly = ratingIsReadOnly(access);

  const context: PayloadContext = {
    classLabel: (value) => optionLabel(options.customer_classes, value),
    serviceLabel: (value) => optionLabel(options.services, value),
  };

  function patch(next: Partial<PlanFormDraft>): void {
    setDraft((was) => ({ ...withOptionDefaults(was, options), ...next }));
    // A box the clerk has just changed no longer carries the server's refusal.
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  const stepId: PlanStepId = steps[nav.step - 1]?.id ?? "details";
  const gaps = shownStep === stepId ? stepGaps(stepId, current, publishTried) : {};
  const marks: Record<string, string> = {
    ...Object.fromEntries(Object.entries(gaps).map(([box, key]) => [box, translate(key)])),
    ...serverErrors,
  };
  const markCount = Object.keys(marks).length;

  /** A refusal from the server: mark each box, open the first box's step. */
  function applyRefusal(error: unknown): number | undefined {
    setRefusal(refusalOf(error, translate).message);
    if (!isApiError(error)) return undefined;
    const mapped: Record<string, string> = {};
    let first: number | undefined;
    for (const fieldError of error.fieldErrors) {
      const home = fieldError.field === null ? undefined : SERVER_FIELD_BOXES[fieldError.field.split("[")[0] ?? ""];
      if (home === undefined) continue;
      mapped[home.box] = translate(fieldError.message_key, refusalParams(fieldError.params, error.traceId));
      const number = stepNumberOf(home.step, steps);
      first = first === undefined ? number : Math.min(first, number);
    }
    setServerErrors(mapped);
    return first;
  }

  /** Mark the first step with a gap and open it; its number, or `null` when
   *  there is none. */
  function refuseOnGaps(publish: boolean): number | null {
    const { firstStep } = allGaps(current, steps, publish);
    if (firstStep === null) return null;
    const spec = steps[firstStep - 1];
    setPublishTried(publish);
    setShownStep(spec?.id ?? null);
    goto({ step: firstStep, reached: Math.max(nav.reached, firstStep) });
    return firstStep;
  }

  async function save(publish: boolean): Promise<SavedPlan> {
    const row = await savePlanForm(planFormPayload(current, publish, context), client);
    void queryClient.invalidateQueries({ queryKey: ["plans"] });
    return { id: row.id, name: row.name || current.name.trim(), published: publish, startsOn: row.effective_from ?? (current.effective_from || null) };
  }

  /** *Publish plan* — the frame's commit. */
  async function commit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    const gapStep = refuseOnGaps(true);
    if (gapStep !== null) {
      // DEF-RAT-9362 — `refusedOnStep`: the box and *Fix N things first.* say
      // it; the frame's failure card would read as a refused publish.
      return {
        ok: false,
        reason: translate("rating.planForm.fixFirst", { count: Math.max(1, markCount) }),
        refusedOnStep: gapStep,
      };
    }
    try {
      const done = await save(true);
      setSaved(done);
      toast(translate("rating.planForm.toast.published", { name: done.name }));
      return { ok: true };
    } catch (error) {
      const step = applyRefusal(error);
      if (step !== undefined) {
        goto({ step, reached: Math.max(nav.reached, step) });
        return { ok: false, reason: refusalOf(error, translate).message, refusedOnStep: step };
      }
      return { ok: false, reason: refusalOf(error, translate).message };
    }
  }

  /** *Save as draft* (Review) and *Save draft & exit* (header) — the same
   *  draft, kept now. A name and a code are what the server needs to keep
   *  anything, so those two are checked first. */
  async function saveDraft(exit: boolean): Promise<void> {
    const first = stepGaps("details", current);
    if (first["plan-name"] !== undefined || first["plan-code"] !== undefined) {
      setShownStep("details");
      goto({ step: stepNumberOf("details", steps), reached: nav.reached });
      return;
    }
    if (!exit && refuseOnGaps(false) !== null) return;
    setSaving(true);
    setRefusal(null);
    try {
      const done = await save(false);
      toast(translate("rating.planForm.toast.saved", { name: done.name }));
      if (exit) navigate(tenantPath(PLANS_LIST_ROUTE));
      else setSaved(done);
    } catch (error) {
      const step = applyRefusal(error);
      if (step !== undefined) goto({ step, reached: Math.max(nav.reached, step) });
    } finally {
      setSaving(false);
    }
  }

  const sections = draftSections(current, options, {
    ...context,
    currency: lists.currency,
    classLabels: (values) => options.customer_classes.filter((row) => values.includes(row.value)),
  });

  const stepProps: PlanStepProps = { draft: current, onChange: patch, lists, t: translate };
  const wizardSteps: WizardStep[] = steps.map((spec) => {
    let content;
    if (spec.id === "review") {
      content =
        saved !== null ? (
          <PlanSavedPanel
            name={saved.name}
            published={saved.published}
            startsOn={saved.startsOn}
            lists={lists}
            t={translate}
            onOpen={() => navigate(tenantPath(planDetailRoute(saved.id)))}
          />
        ) : (
          <ReviewStep
            {...stepProps}
            sections={sections}
            onEdit={(step) => goto({ step: stepNumberOf(step, steps), reached: nav.reached })}
          />
        );
    } else {
      content = <PlanStep {...stepProps} id={spec.id} />;
    }
    return {
      id: spec.id,
      label: translate(spec.labelKey),
      content,
      validate: () => {
        const found = stepGaps(spec.id, current);
        if (Object.keys(found).length > 0) {
          setPublishTried(false);
          setShownStep(spec.id);
          return false;
        }
        setShownStep(null);
        return true;
      },
    };
  });

  const onReview = stepId === "review" && saved === null;
  return (
    <div className="flex flex-col gap-5" data-screen="new-plan">
      <PageHeader
        title={translate("rating.planForm.title")}
        backTo={{ to: tenantPath(PLANS_LIST_ROUTE), label: translate("rating.planForm.back") }}
        secondaryActions={
          saved === null ? (
            <Button disabled={readOnly || saving} onClick={() => void saveDraft(true)}>
              {translate("rating.planForm.saveDraftExit")}
            </Button>
          ) : undefined
        }
      />
      {readOnly && <RefusalStrip role="note">{translate("rating.readOnlyReason")}</RefusalStrip>}
      {refusal !== null && Object.keys(serverErrors).length === 0 && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <FieldErrorsScope errors={marks}>
        <div className={PLAN_FORM_LAYOUT} data-plan-layout="">
          <WizardFrame
            steps={wizardSteps}
            nav={nav}
            onNavChange={goto}
            complete={saved !== null}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1
                ? { label: translate("rating.planForm.cancel"), onCancel: () => navigate(tenantPath(PLANS_LIST_ROUTE)) }
                : undefined
            }
            actionNote={
              markCount > 0 ? (
                <p className="m-0 text-base font-semibold text-danger-700" role="alert" data-plan-fix-count={markCount}>
                  {translate("rating.planForm.fixFirst", { count: markCount })}
                </p>
              ) : undefined
            }
            commitCompanion={
              onReview ? (
                <Button disabled={readOnly || saving} onClick={() => void saveDraft(false)} data-plan-save-draft="">
                  {translate("rating.planForm.saveAsDraft")}
                </Button>
              ) : undefined
            }
            commitLabel={translate("rating.planForm.publish")}
            commitDisabled={readOnly || saving}
            commitFailedTitle={translate("rating.planForm.publishFailed")}
            onCommit={commit}
            onCommitted={() => undefined}
          />
          <div className="col-start-2 row-start-2 row-span-2 self-start sticky top-4">
            <PlanSummaryPanel draft={current} lists={lists} t={translate} />
          </div>
        </div>
      </FieldErrorsScope>
    </div>
  );
}

export default NewPlanForm;
