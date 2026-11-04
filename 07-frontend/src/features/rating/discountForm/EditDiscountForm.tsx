// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — EDIT a discount, built from images
//           27–36 of `05-prototype/discounts-2026-10-03/images/` (B14 rules 42,
//           44, 37, 43, 21, 31, 33). Replaces `DiscountWizard.tsx` at
//           `plans-rates/discounts/:definitionId/edit`.
// Defects:  DEF-RAT-9292 (D35, D36, D38)
// Rules:    README point 7 — *"Edit is the same full-page form: Name and details
//           (same version; value, limits and start locked) · New value from a
//           date (old version ends the day before) · Fix a mistake (same dates,
//           reason required, old row kept)."* · the tax precedent, PO verbatim:
//           *"We dont use side panel for edit - you will need to send it back to
//           Edit form - You can use add form with variation"*
// Contract: CR-166-BRC10 §9 — `GET /discounts/{id}`, `PATCH /discounts/{id}`,
//           `POST /discounts/{id}/new-value`, `POST /discounts/{id}/corrections`
// ───────────────────────────────────────────────────────
//
// THE SAME FULL-PAGE FORM AS NEW, WITH A VARIATION. *What to change* sits on
// top; the chosen card (`?change=info|change|correct`, the address the details
// page links to) picks the step list and the set of LOCKED fields, and the New
// form's own section components render over a draft read back from the
// discount.
//
// ⚠ **SWITCHING CARDS STARTS THAT FLOW AGAIN FROM THE DISCOUNT AS SAVED.** A
// label typed under *Name and details* is not something *New value from a
// date* can send, so carrying it across would show it in the summary and then
// not save it. The draft is reset to the served row; the card says which flow
// is open (the tax edit's judgment 3, applied here unchanged).
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { correctDiscount, getDiscountForEdit, newDiscountValue, updateDiscountDetails } from "@/api/discountEditEndpoints";
import { refusalParams } from "@/api/refusalText";
import { formatDate } from "@/components/DateCell";
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

import { definitionPath } from "../definitionDetail";
import { DASHBOARD_ROUTE, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { DetailsStep } from "./DetailsStep";
import { DiscountSummaryPanel } from "./DiscountSummaryPanel";
import { EditDiscountChoiceCards } from "./EditDiscountChoiceCards";
import { EditDiscountReviewStep, changedDiscountRows } from "./EditDiscountReviewStep";
import { EditDiscountSavedPanel } from "./EditDiscountSavedPanel";
import { EditInfoDetailsStep, EditValueStep } from "./EditDiscountSteps";
import { EligibilityStep } from "./EligibilityStep";
import {
  CHANGE_PARAM,
  EDIT_STEPS,
  LEGACY_CORRECT_PARAM,
  correctionPayload,
  discountDraftFromRow,
  discountEditModeOf,
  editFieldHome,
  editStepGaps,
  editStepNumberOf,
  infoPatchPayload,
  isDraftRow,
  lockedFields,
  newValuePayload,
} from "./discountEditModel";
import type { DiscountEditMode, DiscountEditStepId } from "./discountEditModel";
import { emptyDiscountFormDraft, withListDefaults } from "./discountFormModel";
import type { DiscountFormDraft } from "./discountFormModel";
import { DISCOUNT_FORM_LAYOUT } from "./discountFormShared";
import { useDiscountFormLists } from "./useDiscountFormLists";

/** The URL param the open step lives in (BR-SHL-011 — a step is linkable). */
const STEP_PARAM = "step";

/** Literal keys, so G18 can see each one used. */
const COMMIT_KEYS: Record<DiscountEditMode, string> = {
  info: "rating.discountEdit.save.info",
  change: "rating.discountEdit.save.change",
  correct: "rating.discountEdit.save.correct",
};

/** The choices a draft cannot take — it has no version in force. */
const DRAFT_UNAVAILABLE: ReadonlySet<DiscountEditMode> = new Set<DiscountEditMode>(["change", "correct"]);

export interface EditDiscountFormProps {
  client?: ApiClient; // test seam — screens never build their own transport
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}

interface Saved {
  name: string;
  sentence: string;
}

export function EditDiscountForm(props: EditDiscountFormProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { definitionId = "" } = useParams<{ definitionId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const discountQuery = useQuery({
    queryKey: ["discounts", "item", definitionId, "edit"],
    queryFn: () => getDiscountForEdit(definitionId, client),
    enabled: definitionId !== "",
    retry: false,
  });
  const row = discountQuery.data;
  const isDraft = row !== undefined && isDraftRow(row);
  // A draft has one choice: whatever the address asked for, it edits in place.
  const mode: DiscountEditMode = isDraft ? "info" : discountEditModeOf(searchParams);
  const steps = EDIT_STEPS[mode];
  const original = useMemo(() => (row === undefined ? emptyDiscountFormDraft() : discountDraftFromRow(row)), [row]);

  const [draft, setDraft] = useState<DiscountFormDraft | null>(null);
  const [reason, setReason] = useState("");
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  const [shownStep, setShownStep] = useState<DiscountEditStepId | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);

  const { current, lists, options, permissions, translate } = useDiscountFormLists({
    draft: draft ?? original,
    client,
    dateFormat: props.dateFormat,
    timeZone: props.timeZone,
  });
  // The served row with the same list defaults the draft carries, so an
  // untouched box never reads as a change (an empty group IS *None*).
  const baseline = withListDefaults(original, options);
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  const detailPath = tenantPath(definitionPath("discount", definitionId));

  if (permissions.isPending || discountQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissions.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  if (row === undefined) {
    return (
      <FailedWithRetry
        title={translate("rating.discountEdit.loadFailed")}
        reason={refusalOf(discountQuery.error, translate).message}
        onRetry={() => void discountQuery.refetch()}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);
  const version = row.version ?? row.version_no ?? 1;
  const locked = lockedFields(mode, isDraft);
  const eligibility = options.eligibility;

  function patch(next: Partial<DiscountFormDraft>): void {
    setDraft((was) => ({ ...withListDefaults(was ?? original, options), ...next }));
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  function choose(next: DiscountEditMode): void {
    if (next === mode) return;
    setDraft(null);
    setReason("");
    setShownStep(null);
    setServerErrors({});
    setRefusal(null);
    setNav({ step: 1, reached: 1 });
    const params = new URLSearchParams(searchParams);
    params.set(CHANGE_PARAM, next);
    params.delete(LEGACY_CORRECT_PARAM);
    params.set(STEP_PARAM, "1");
    setSearchParams(params, { replace: true });
  }

  const stepId: DiscountEditStepId = steps[nav.step - 1]?.id ?? "details";
  const ctx = { eligibility, isDraft, liveFrom: baseline.effective_from, reason };
  const gaps = shownStep === stepId ? editStepGaps(mode, stepId, current, ctx) : {};
  const marks: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(gaps).map(([box, gap]) => [
        box,
        translate(
          gap.key,
          gap.params?.date === undefined ? gap.params : { ...gap.params, date: day(String(gap.params.date)) },
        ),
      ]),
    ),
    ...serverErrors,
  };
  const markCount = Object.keys(marks).length;
  const nothingChanged =
    mode !== "change" && changedDiscountRows({ mode, original: baseline, draft: current, lists, t: translate }).length === 0;

  /** A refusal from the server: mark each box, open the first box's step. */
  function applyRefusal(error: unknown): number | undefined {
    setRefusal(refusalOf(error, translate).message);
    if (!isApiError(error)) return undefined;
    const mapped: Record<string, string> = {};
    let first: number | undefined;
    for (const fieldError of error.fieldErrors) {
      const home = fieldError.field === null ? undefined : editFieldHome(mode, fieldError.field);
      if (home === undefined) continue;
      const params = refusalParams(fieldError.params, error.traceId);
      for (const key of ["current_start", "date", "from", "retire_on"]) {
        if (typeof params[key] === "string") params[key] = day(params[key] as string);
      }
      mapped[home.box] = translate(fieldError.message_key, params);
      const number = editStepNumberOf(home.step, steps);
      first = first === undefined ? number : Math.min(first, number);
    }
    setServerErrors(mapped);
    return first;
  }

  async function save(): Promise<Saved> {
    const payloadCtx = { eligibility };
    if (mode === "info") {
      const next = await updateDiscountDetails(
        definitionId,
        infoPatchPayload(baseline, current, { ...payloadCtx, isDraft }),
        client,
      );
      return { name: next.name, sentence: translate("rating.discountEdit.saved.info") };
    }
    if (mode === "change") {
      const next = await newDiscountValue(definitionId, newValuePayload(baseline, current, payloadCtx), client);
      const waits = next.status === "pending_approval";
      return {
        name: current.name.trim() || row?.name || "",
        sentence: waits
          ? translate("rating.discountEdit.saved.changeWaits", { v: next.version_no })
          : translate("rating.discountEdit.saved.change", { v: next.version_no, date: day(current.effective_from) }),
      };
    }
    const next = await correctDiscount(definitionId, correctionPayload(baseline, current, reason, payloadCtx), client);
    return {
      name: current.name.trim() || row?.name || "",
      sentence: translate("rating.discountEdit.saved.correct", { v: next.version_no, old: version }),
    };
  }

  async function commit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    try {
      const done = await save();
      void queryClient.invalidateQueries({ queryKey: ["discounts"] });
      setSaved(done);
      toast(translate("rating.discountEdit.saved.title", { name: done.name }));
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

  const stepProps = { draft: current, onChange: patch, lists, locked, t: translate };
  const onReason = (next: string) => {
    setReason(next);
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  };

  const wizardSteps: WizardStep[] = steps.map((spec) => {
    let content;
    if (spec.id === "details") {
      content = isDraft ? <DetailsStep {...stepProps} /> : <EditInfoDetailsStep {...stepProps} />;
    } else if (spec.id === "eligibility") {
      content = <EligibilityStep {...stepProps} startsLockedHelp={translate("rating.discountEdit.lock.value")} />;
    } else if (spec.id === "value") {
      content = (
        <EditValueStep
          {...stepProps}
          mode={mode === "correct" ? "correct" : "change"}
          liveFrom={baseline.effective_from}
          reason={reason}
          onReason={onReason}
        />
      );
    } else if (saved !== null) {
      content = (
        <EditDiscountSavedPanel
          name={saved.name}
          sentence={saved.sentence}
          t={translate}
          onBack={() => navigate(detailPath)}
        />
      );
    } else {
      content = (
        <EditDiscountReviewStep
          mode={mode}
          original={baseline}
          draft={current}
          version={version}
          reason={reason}
          lists={lists}
          t={translate}
        />
      );
    }
    return {
      id: spec.id,
      label: translate(spec.labelKey),
      content,
      validate: () => {
        const found = editStepGaps(mode, spec.id, current, ctx);
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
    <div className="flex flex-col gap-5" data-screen="edit-discount" data-discount-edit-mode={mode}>
      <PageHeader
        title={translate("rating.discountEdit.title", { name: row.name })}
        backTo={{ to: detailPath, label: row.name }}
      />
      {readOnly && <RefusalStrip role="note">{translate("rating.readOnlyReason")}</RefusalStrip>}
      {refusal !== null && markCount === 0 && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <EditDiscountChoiceCards
        mode={mode}
        onChoose={choose}
        disabled={saved !== null}
        unavailable={isDraft ? DRAFT_UNAVAILABLE : undefined}
        t={translate}
      />
      <FieldErrorsScope errors={marks}>
        <div className={DISCOUNT_FORM_LAYOUT} data-discount-layout="">
          <WizardFrame
            key={mode}
            steps={wizardSteps}
            nav={nav}
            onNavChange={goto}
            complete={saved !== null}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1
                ? { label: translate("rating.discountForm.cancel"), onCancel: () => navigate(detailPath) }
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
            commitLabel={translate(COMMIT_KEYS[mode])}
            commitDisabled={readOnly || nothingChanged}
            commitFailedTitle={translate("rating.discountEdit.saveFailed")}
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

export default EditDiscountForm;
