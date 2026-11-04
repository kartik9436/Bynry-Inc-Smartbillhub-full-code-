// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — the New discount form, built from
//           images 05–18 of `05-prototype/discounts-2026-10-03/images/` (B14
//           rules 42, 44, 37, 43, 21, 33). Replaces `DiscountWizard.tsx` on the
//           NEW route only; the edit door stays on it until round 3.
// Defects:  DEF-RAT-9289 (D1–D13)
// Contract: CR-166-BRC10 §9 — `GET /discounts/form-options`, `POST /discounts`
//           (saves a draft; takes `program_owner`, `exclusivity_group`,
//           `eligibility` codes; currency is the utility's)
// ───────────────────────────────────────────────────────
//
// THE PAGE: it loads the lists, holds the ONE draft, and lays the step
// components and the summary panel onto the frame. Every step is a component in
// this folder and the steps are an ARRAY, so round 3's three edit variations
// mount the same steps with fields locked and a different `steps` list.
//
// ⚠ **NOTHING TYPED IS LOST.** The draft lives here, above every step, and is
// never reset by a refusal — a server error marks the box and opens its step;
// Back, Continue and the rail move between steps over the same draft.
//
// ⚠ **A ROUTE THAT IS NOT SERVED YET IS AN EMPTY LIST, NEVER A BROKEN STEP.**
// `form-options` is new in round 2; every read here is `retry: false` and falls
// back to an empty list, so the form renders with an empty dropdown either way.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { createDiscount } from "@/api/endpoints";
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

import { DEFINITION_ROUTES, definitionPath } from "../definitionDetail";
import { DASHBOARD_ROUTE, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { DetailsStep } from "./DetailsStep";
import { DiscountSavedPanel } from "./DiscountSavedPanel";
import { DiscountSummaryPanel } from "./DiscountSummaryPanel";
import { EligibilityStep } from "./EligibilityStep";
import { ReviewStep } from "./ReviewStep";
import {
  NEW_DISCOUNT_STEPS,
  SERVER_FIELD_BOXES,
  discountFormPayload,
  emptyDiscountFormDraft,
  stepGaps,
  stepNumberOf,
  withListDefaults,
} from "./discountFormModel";
import type { DiscountFormDraft, DiscountFormStepSpec, DiscountStepId } from "./discountFormModel";
import { DISCOUNT_FORM_LAYOUT } from "./discountFormShared";
import type { DiscountStepProps } from "./discountFormShared";
import { useDiscountFormLists } from "./useDiscountFormLists";

/** The URL param the open step lives in (BR-SHL-011 — a step is linkable). */
const STEP_PARAM = "step";

/** The two editing steps as components, keyed by the step array's ids. Review
 *  is not here: it reads the draft and edits nothing. */
export const DISCOUNT_STEP_COMPONENTS: Readonly<Record<Exclude<DiscountStepId, "review">, ComponentType<DiscountStepProps>>> = {
  details: DetailsStep,
  eligibility: EligibilityStep,
};

export interface NewDiscountWizardProps {
  client?: ApiClient; // test seam — screens never build their own transport
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}

export function NewDiscountWizard(props: NewDiscountWizardProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const steps: readonly DiscountFormStepSpec[] = NEW_DISCOUNT_STEPS;
  const [draft, setDraft] = useState<DiscountFormDraft>(emptyDiscountFormDraft);
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  /** The step whose empty boxes are marked — set by a refused Continue, so an
   *  empty form does not open shouting. */
  const [shownStep, setShownStep] = useState<DiscountStepId | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ id: string; name: string } | null>(null);
  const [drafting, setDrafting] = useState(false);

  const { current, lists, options, permissions: permissionsQuery, translate } = useDiscountFormLists({
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
  const listRoute = DEFINITION_ROUTES.discount.listRoute;

  function patch(next: Partial<DiscountFormDraft>): void {
    setDraft((was) => ({ ...withListDefaults(was, options), ...next }));
    // A box the clerk has just changed no longer carries the server's refusal.
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  const stepId: DiscountStepId = steps[nav.step - 1]?.id ?? "details";
  const gaps = shownStep === stepId ? stepGaps(stepId, current, options.eligibility) : {};
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
      const home = fieldError.field === null ? undefined : SERVER_FIELD_BOXES[fieldError.field];
      if (home === undefined) continue;
      mapped[home.box] = translate(fieldError.message_key, refusalParams(fieldError.params, error.traceId));
      const number = stepNumberOf(home.step, steps);
      first = first === undefined ? number : Math.min(first, number);
    }
    setServerErrors(mapped);
    return first;
  }

  function payload(): Record<string, unknown> {
    return discountFormPayload(current, { currency: lists.currency, eligibility: options.eligibility });
  }

  async function commit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    try {
      const row = await createDiscount(payload(), client);
      void queryClient.invalidateQueries({ queryKey: ["discounts"] });
      setSaved({ id: row.id, name: row.name });
      toast(translate("rating.discountForm.toast.saved", { name: row.name }));
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

  /** *Save draft & exit* — the same draft, kept now. A code and a label are
   *  what the server needs to keep anything, so those two are checked first. */
  async function saveDraftAndExit(): Promise<void> {
    const first = stepGaps("details", current, options.eligibility);
    if (first["discount-code"] !== undefined || first["discount-label"] !== undefined) {
      setShownStep("details");
      goto({ step: stepNumberOf("details", steps), reached: nav.reached });
      return;
    }
    setDrafting(true);
    setRefusal(null);
    try {
      const row = await createDiscount(payload(), client);
      void queryClient.invalidateQueries({ queryKey: ["discounts"] });
      toast(translate("rating.discountForm.toast.saved", { name: row.name }));
      navigate(tenantPath(listRoute));
    } catch (error) {
      const step = applyRefusal(error);
      if (step !== undefined) goto({ step, reached: Math.max(nav.reached, step) });
    } finally {
      setDrafting(false);
    }
  }

  function startAgain(): void {
    setDraft(emptyDiscountFormDraft());
    setSaved(null);
    setShownStep(null);
    setServerErrors({});
    setRefusal(null);
    goto({ step: 1, reached: 1 });
  }

  const stepProps: DiscountStepProps = { draft: current, onChange: patch, lists, t: translate };
  const wizardSteps: WizardStep[] = steps.map((spec) => {
    let content;
    if (spec.id === "review") {
      content =
        saved !== null ? (
          <DiscountSavedPanel
            draft={current}
            lists={lists}
            savedName={saved.name}
            t={translate}
            onOpen={() => navigate(tenantPath(definitionPath("discount", saved.id)))}
            onAnother={startAgain}
          />
        ) : (
          <ReviewStep
            draft={current}
            lists={lists}
            steps={steps}
            t={translate}
            onEdit={(step) => goto({ step, reached: nav.reached })}
          />
        );
    } else {
      const Step = DISCOUNT_STEP_COMPONENTS[spec.id];
      content = <Step {...stepProps} />;
    }
    return {
      id: spec.id,
      label: translate(spec.labelKey),
      content,
      validate: () => {
        const found = stepGaps(spec.id, current, options.eligibility);
        if (Object.keys(found).length > 0) {
          setShownStep(spec.id);
          return false;
        }
        setShownStep(null);
        return true;
      },
    };
  });

  return (
    <div className="flex flex-col gap-5" data-screen="new-discount">
      <PageHeader
        title={translate("rating.discountForm.title")}
        backTo={{ to: tenantPath(listRoute), label: translate("rating.discountForm.back") }}
        secondaryActions={
          saved === null ? (
            <Button disabled={readOnly || drafting} onClick={() => void saveDraftAndExit()}>
              {translate("rating.discountForm.saveDraft")}
            </Button>
          ) : undefined
        }
      />
      {readOnly && <RefusalStrip role="note">{translate("rating.readOnlyReason")}</RefusalStrip>}
      {refusal !== null && Object.keys(serverErrors).length === 0 && (
        <RefusalStrip role="alert">{refusal}</RefusalStrip>
      )}
      <FieldErrorsScope errors={marks}>
        <div className={DISCOUNT_FORM_LAYOUT} data-discount-layout="">
          <WizardFrame
            steps={wizardSteps}
            nav={nav}
            onNavChange={goto}
            complete={saved !== null}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1
                ? { label: translate("rating.discountForm.cancel"), onCancel: () => navigate(tenantPath(listRoute)) }
                : undefined
            }
            actionNote={
              markCount > 0 ? (
                <p
                  className="m-0 text-base font-semibold text-danger-700"
                  role="alert"
                  data-discount-fix-count={markCount}
                >
                  {translate("rating.discountForm.fixFirst", { count: markCount })}
                </p>
              ) : undefined
            }
            commitLabel={translate("rating.discountForm.commit")}
            commitDisabled={readOnly}
            commitFailedTitle={translate("rating.discountForm.saveFailed")}
            onCommit={commit}
            onCommitted={() => undefined}
          />
          <div className="col-start-2 row-start-2 row-span-2 self-start">
            <DiscountSummaryPanel draft={current} lists={lists} t={translate} />
          </div>
        </div>
      </FieldErrorsScope>
    </div>
  );
}

export default NewDiscountWizard;
