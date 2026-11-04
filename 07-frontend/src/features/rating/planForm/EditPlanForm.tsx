// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — EDIT a plan, built from images 37–44
//           of `05-prototype/plans-2026-10-03/images/` (B14 rules 42, 44, 37,
//           43, 21, 31, 33). Replaces `PlanWizard.tsx` at
//           `plans-rates/plans/:planId/edit`, which round 3 retires.
// Defects:  DEF-RAT-9332 (Edit half) · DEF-RAT-9328 (Edit half) · DEF-RAT-9330
//           (*Publish new version* is ONE call — no second publish to refuse)
// Rules:    PO ruling 1 — *"Edit uses the same form, with three 'What to
//           change' cards: Name and details (same version), Change from a date
//           (new version), Fix a mistake (same dates, with a reason)"* ·
//           ruling 10 — *"When editing, these are Save new version and Publish
//           new version"* · the tax and discount precedent, PO verbatim: *"We
//           dont use side panel for edit - you will need to send it back to
//           Edit form - You can use add form with variation"*
// Contract: CR-167-BRC10 §7.3 / §9 — `GET /plans/{id}`, `PATCH /plans/{id}`,
//           `POST /plans/{id}/versions`, `POST /plans/{id}/corrections`,
//           `POST /plans/{id}/publish` (a draft)
// ───────────────────────────────────────────────────────
//
// THE SAME FULL-PAGE FORM AS NEW, WITH A VARIATION. *What to change* sits on
// top; the chosen card (`?change=info|change|correct`) picks the step list and
// the set of LOCKED fields, and the New form's own step components render over
// a draft read back from the plan. `?step=<n>` opens a step within the chosen
// card's own steps — the address a details-page section's *Edit* uses
// (image 37; lane PLAN-DETAIL, agreed 2026-10-03, CR-167 §14).
//
// ⚠ **A DRAFT HAS ONE CHOICE AND EDITS IN PLACE.** It has no version in force,
// so the cards are not drawn: it opens the New form's five steps with nothing
// locked, and Review ends *Save as draft* · *Publish plan*.
//
// ⚠ **SWITCHING CARDS STARTS THAT FLOW AGAIN FROM THE PLAN AS SAVED.** A name
// typed under *Name and details* is not something *Change from a date* can
// send, so carrying it across would show it in *This plan* and then not save
// it (the tax edit's judgment 3, applied unchanged).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  correctPlan,
  getPlanForEdit,
  latestVersionStart,
  newPlanVersion,
  patchPlan,
  publishDraftPlan,
} from "@/api/planEditEndpoints";
import { refusalParams } from "@/api/refusalText";
import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FieldErrorsScope } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { refusalOf } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { planDetailRoute } from "../planDetail/planDetailModel";
import { DASHBOARD_ROUTE, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { EditPlanChoiceCards } from "./EditPlanChoiceCards";
import { EditPlanReviewStep } from "./EditPlanReviewStep";
import { EditPlanSavedPanel } from "./EditPlanSavedPanel";
import { EditInfoDetailsStep } from "./EditPlanSteps";
import { PlanStep } from "./NewPlanForm";
import { PlanSummaryPanel } from "./PlanSummaryPanel";
import { ReviewStep } from "./ReviewStep";
import {
  CHANGE_PARAM,
  STEP_PARAM,
  allEditGaps,
  changedFields,
  correctionPayload,
  dayText,
  editFieldHome,
  editStepGaps,
  editSteps,
  isDraftPlan,
  lockedFields,
  newVersionPayload,
  nextVersionNumber,
  openingDraft,
  patchPayload,
  planDraftFromRow,
  planEditModeOf,
  stepFromParams,
  withPlanItems,
} from "./planEditModel";
import type { EditGapContext, PlanEditMode } from "./planEditModel";
import { draftSections, emptyPlanFormDraft, stepNumberOf } from "./planFormModel";
import type { PayloadContext, PlanFormDraft, PlanStepId } from "./planFormModel";
import { PLAN_FORM_LAYOUT, optionLabel } from "./planFormShared";
import type { PlanFormLists, PlanStepProps } from "./planFormShared";
import { noteAttributes, usePlanFormLists } from "./usePlanFormLists";

/** Literal keys, so G18 can see each one used. */
const COMMIT_KEYS: Record<PlanEditMode, string> = {
  info: "rating.planEdit.save.info",
  change: "rating.planEdit.save.publishVersion",
  correct: "rating.planEdit.save.correct",
};

export interface EditPlanFormProps {
  client?: ApiClient; // test seam — screens never build their own transport
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}

interface Saved {
  name: string;
  sentence: string;
}

export function EditPlanForm(props: EditPlanFormProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { planId = "" } = useParams<{ planId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const planQuery = useQuery({
    queryKey: ["plans", "item", planId, "edit"],
    queryFn: () => getPlanForEdit(planId, client),
    enabled: planId !== "",
    retry: false,
  });
  const today = planQuery.data;
  const isDraft = today !== undefined && isDraftPlan(today);
  const mode: PlanEditMode = isDraft ? "info" : planEditModeOf(searchParams);
  // *Change from a date* builds on the LATEST version (the server copies the
  // version in force on the new start), so when a later one is already filed
  // the form reads the plan AS OF that version's start.
  const laterStart = !isDraft && mode === "change" && today !== undefined ? latestVersionStart(today) : null;
  const laterQuery = useQuery({
    queryKey: ["plans", "item", planId, "edit", laterStart],
    queryFn: () => getPlanForEdit(planId, client, laterStart),
    enabled: laterStart !== null,
    retry: false,
  });
  const row = laterStart === null ? today : laterQuery.data;
  const steps = editSteps(mode, isDraft);

  const [draft, setDraft] = useState<PlanFormDraft | null>(null);
  const [reason, setReason] = useState("");
  const [navState, setNav] = useState<WizardNavState | null>(null);
  const [shownStep, setShownStep] = useState<PlanStepId | null>(null);
  const [publishTried, setPublishTried] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [saving, setSaving] = useState(false);

  // The plan's classes go with the lists request (`DEF-RAT-9351`), so each
  // schedule's base resolves for the classes this plan is for.
  const classesDraft = useMemo(
    () => ({
      ...emptyPlanFormDraft(),
      customer_classes: row === undefined ? [] : row.sections.details.customer_classes.map((one) => one.value),
    }),
    [row],
  );
  const data = usePlanFormLists({
    draft: draft ?? classesDraft,
    client,
    dateFormat: props.dateFormat,
    timeZone: props.timeZone,
  });
  const { permissions, translate } = data;
  // The plan's OWN items join the lists, so every row opens on its value and
  // Review draws what the plan's own read resolved (`withPlanItems`).
  const options = useMemo(
    () => (row === undefined ? data.options : withPlanItems(data.options, row.sections)),
    [row, data.options],
  );
  const lists: PlanFormLists = {
    ...data.lists,
    options,
    classOptions: options.customer_classes,
    noteAttributes: noteAttributes(options, translate),
  };
  const original = useMemo(() => (row === undefined ? emptyPlanFormDraft() : planDraftFromRow(row, options)), [row, options]);
  const current = draft ?? openingDraft(original, mode, isDraft);
  const nav: WizardNavState = navState ?? (() => {
    const step = stepFromParams(searchParams, steps);
    return { step, reached: step };
  })();
  const day = (value: string) => dayText(value, lists.timeZone, lists.dateFormat);
  const detailPath = tenantPath(planDetailRoute(planId));

  if (permissions.isPending || planQuery.isPending || (laterStart !== null && laterQuery.isPending)) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissions.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  if (row === undefined) {
    return (
      <FailedWithRetry
        title={translate("rating.planEdit.loadFailed")}
        reason={refusalOf(planQuery.error ?? laterQuery.error, translate).message}
        onRetry={() => void (laterStart === null ? planQuery.refetch() : laterQuery.refetch())}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);
  const locked = lockedFields(mode, isDraft);
  const liveFrom = row.effective_from ?? "";
  const liveTo = row.effective_to ?? "";
  const nextVersion = nextVersionNumber(row);

  const payloadCtx: PayloadContext = {
    classLabel: (value) => optionLabel(options.customer_classes, value),
    serviceLabel: (value) => optionLabel(options.services, value),
  };

  function patch(next: Partial<PlanFormDraft>): void {
    setDraft((was) => ({ ...(was ?? current), ...next }));
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  function choose(next: PlanEditMode): void {
    if (next === mode) return;
    setDraft(null);
    setReason("");
    setShownStep(null);
    setPublishTried(false);
    setServerErrors({});
    setRefusal(null);
    setNav({ step: 1, reached: 1 });
    const params = new URLSearchParams(searchParams);
    params.set(CHANGE_PARAM, next);
    params.set(STEP_PARAM, "1");
    setSearchParams(params, { replace: true });
  }

  const stepId: PlanStepId = steps[nav.step - 1]?.id ?? steps[0]?.id ?? "details";
  const gapCtx = (publish: boolean): EditGapContext => ({ isDraft, liveFrom, reason, publish });
  const gaps = shownStep === stepId ? editStepGaps(mode, stepId, current, gapCtx(publishTried)) : {};
  const marks: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(gaps).map(([box, gap]) => [
        box,
        translate(gap.key, gap.params?.date === undefined ? gap.params : { ...gap.params, date: day(String(gap.params.date)) }),
      ]),
    ),
    ...serverErrors,
  };
  const markCount = Object.keys(marks).length;
  const moved = changedFields(mode, isDraft, original, current);
  const nothingChanged = moved.length === 0;

  /** A refusal from the server: mark each box, open the first box's step. */
  function applyRefusal(error: unknown): number | undefined {
    setRefusal(refusalOf(error, translate).message);
    if (!isApiError(error)) return undefined;
    const mapped: Record<string, string> = {};
    let first: number | undefined;
    for (const fieldError of error.fieldErrors) {
      const home = fieldError.field === null ? undefined : editFieldHome(fieldError.field, steps);
      if (home === undefined) continue;
      const params = refusalParams(fieldError.params, error.traceId);
      for (const key of ["date", "start", "today"]) {
        if (typeof params[key] === "string") params[key] = day(params[key] as string);
      }
      mapped[home.box] = translate(fieldError.message_key, params);
      const number = stepNumberOf(home.step, steps);
      first = first === undefined ? number : Math.min(first, number);
    }
    setServerErrors(mapped);
    return first;
  }

  /** Mark the first step with a gap and open it; its number, or `null` when
   *  there is none. */
  function refuseOnGaps(publish: boolean): number | null {
    const { firstStep } = allEditGaps(mode, steps, current, gapCtx(publish));
    if (firstStep === null) return null;
    setPublishTried(publish);
    setShownStep(steps[firstStep - 1]?.id ?? null);
    goto({ step: firstStep, reached: Math.max(nav.reached, firstStep) });
    return firstStep;
  }

  const name = current.name.trim() || row.name;

  /** One save of this choice. `publish` is the commit; `false` the companion
   *  (*Save new version*, a draft's *Save as draft*). */
  async function save(publish: boolean): Promise<Saved> {
    const id = row?.id || planId;
    if (isDraft) {
      if (moved.length > 0) await patchPlan(id, patchPayload(true, original, current, payloadCtx), client);
      if (publish) {
        await publishDraftPlan(id, client);
        return { name, sentence: translate("rating.planEdit.saved.draftPublished") };
      }
      return { name, sentence: translate("rating.planEdit.saved.draft") };
    }
    if (mode === "info") {
      await patchPlan(id, patchPayload(false, original, current, payloadCtx), client);
      return { name, sentence: translate("rating.planEdit.saved.info") };
    }
    if (mode === "change") {
      await newPlanVersion(id, newVersionPayload(original, current, reason, publish, payloadCtx), client);
      return {
        name,
        sentence: publish
          ? translate("rating.planEdit.saved.change", { v: nextVersion, date: day(current.effective_from) })
          : translate("rating.planEdit.saved.changeDraft", { v: nextVersion }),
      };
    }
    await correctPlan(id, correctionPayload(original, current, reason, row?.version ?? 1, payloadCtx), client);
    return { name, sentence: translate("rating.planEdit.saved.correct", { v: row?.version ?? 1 }) };
  }

  async function run(publish: boolean): Promise<WizardCommitOutcome> {
    setRefusal(null);
    const gapStep = refuseOnGaps(publish);
    if (gapStep !== null) {
      // `refusedOnStep`: the boxes say it, and *Fix N things first.* beside the
      // buttons (image 42) — never the frame's failure card, which would read
      // as the SERVER refusing a save that was never sent.
      return {
        ok: false,
        reason: translate("rating.planForm.fixFirst", { count: Math.max(1, markCount) }),
        refusedOnStep: gapStep,
      };
    }
    setSaving(true);
    try {
      const done = await save(publish);
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
      setSaved(done);
      toast(translate("rating.planEdit.saved.title", { name: done.name }));
      return { ok: true };
    } catch (error) {
      const step = applyRefusal(error);
      if (step !== undefined) {
        goto({ step, reached: Math.max(nav.reached, step) });
        return { ok: false, reason: refusalOf(error, translate).message, refusedOnStep: step };
      }
      return { ok: false, reason: refusalOf(error, translate).message };
    } finally {
      setSaving(false);
    }
  }

  const stepProps: PlanStepProps = { draft: current, onChange: patch, lists, locked, t: translate };
  const onReason = (next: string) => {
    setReason(next);
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  };
  const openStep = (step: PlanStepId) => goto({ step: stepNumberOf(step, steps), reached: nav.reached });
  const sections = draftSections(current, options, {
    ...payloadCtx,
    currency: lists.currency,
    classLabels: (values) => options.customer_classes.filter((one) => values.includes(one.value)),
  });

  const wizardSteps: WizardStep[] = steps.map((spec) => {
    let content;
    if (spec.id !== "review") {
      content =
        spec.id === "details" && !isDraft ? <EditInfoDetailsStep {...stepProps} /> : <PlanStep {...stepProps} id={spec.id} />;
    } else if (saved !== null) {
      content = <EditPlanSavedPanel name={saved.name} sentence={saved.sentence} t={translate} onBack={() => navigate(detailPath)} />;
    } else if (isDraft) {
      content = <ReviewStep {...stepProps} sections={sections} onEdit={openStep} />;
    } else {
      content = (
        <EditPlanReviewStep
          {...stepProps}
          mode={mode}
          original={original}
          sections={sections}
          version={row.version}
          nextVersion={nextVersion}
          liveFrom={liveFrom}
          liveTo={liveTo}
          units={row.units}
          reason={reason}
          onReason={onReason}
          onEdit={openStep}
        />
      );
    }
    return {
      id: spec.id,
      label: translate(spec.labelKey),
      content,
      validate: () => {
        if (spec.id === "review") return true;
        const found = editStepGaps(mode, spec.id, current, gapCtx(false));
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
  const companionKey = isDraft ? "rating.planForm.saveAsDraft" : mode === "change" ? "rating.planEdit.save.version" : null;
  const commitKey = isDraft ? "rating.planForm.publish" : COMMIT_KEYS[mode];
  // *Save changes* and *Save correction* have nothing to save until something
  // moved (the server refuses an empty correction); a new version may change
  // only its dates, and a draft may be published as it stands.
  const commitBlocked = !isDraft && mode !== "change" && nothingChanged;

  return (
    <div className="flex flex-col gap-5" data-screen="edit-plan" data-plan-edit-mode={isDraft ? "draft" : mode}>
      <PageHeader title={translate("rating.planEdit.title", { name: row.name })} backTo={{ to: detailPath, label: row.name }} />
      {readOnly && <RefusalStrip role="note">{translate("rating.readOnlyReason")}</RefusalStrip>}
      {refusal !== null && Object.keys(serverErrors).length === 0 && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      {!isDraft && <EditPlanChoiceCards mode={mode} onChoose={choose} disabled={saved !== null} t={translate} />}
      <FieldErrorsScope errors={marks}>
        <div className={PLAN_FORM_LAYOUT} data-plan-layout="">
          <WizardFrame
            key={isDraft ? "draft" : mode}
            steps={wizardSteps}
            nav={nav}
            onNavChange={goto}
            complete={saved !== null}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1 ? { label: translate("rating.planForm.cancel"), onCancel: () => navigate(detailPath) } : undefined
            }
            actionNote={
              markCount > 0 ? (
                <p className="m-0 text-base font-semibold text-danger-700" role="alert" data-plan-fix-count={markCount}>
                  {translate("rating.planForm.fixFirst", { count: markCount })}
                </p>
              ) : undefined
            }
            commitCompanion={
              onReview && companionKey !== null ? (
                <Button disabled={readOnly || saving} onClick={() => void run(false)} data-plan-save-companion="">
                  {translate(companionKey)}
                </Button>
              ) : undefined
            }
            commitLabel={translate(commitKey)}
            commitDisabled={readOnly || saving || commitBlocked}
            commitFailedTitle={translate("rating.planEdit.saveFailed")}
            onCommit={() => run(true)}
            onCommitted={() => undefined}
          />
          <div className="col-start-2 row-start-2 row-span-2 self-start">
            <PlanSummaryPanel draft={current} lists={lists} t={translate} />
          </div>
        </div>
      </FieldErrorsScope>
    </div>
  );
}

export default EditPlanForm;
